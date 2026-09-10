"""Hazard-aware route scoring: route geometry x active hazard buffers.

Phase 6C. Combines the multi-engine router with the live hazard picture:
  - base route  → scored against every hazard exposure geometry
  - alternatives → rescored, best (lowest-risk) route returned when it is
    meaningfully safer than the base (avoid_hazards=true)
  - every score is explainable: per-event length inside the buffer, severity
    weight, and the segment-based sharing method used to compute it.

Honesty rules (inherited from the routing engines):
  - No hazard score is produced from DEMO hazard geometry; exposures only
    come from `current_hazards()` active events.
  - UNAVAILABLE engines produce no route and therefore no risk score — the
    response says so explicitly instead of guessing.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.services import multi_engine_routing
from app.services.hazard_service import _haversine_km, current_hazards

logger = logging.getLogger(__name__)

SEVERITY_WEIGHTS = {
    "LOW": 5,
    "MODERATE": 20,
    "HIGH": 50,
    "SEVERE": 90,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _risk_label(score: float) -> str:
    if score >= 75:
        return "EXTREME"
    if score >= 40:
        return "HIGH"
    if score >= 10:
        return "MODERATE"
    return "LOW"


def _event_weight(severity_level: str) -> float:
    return float(SEVERITY_WEIGHTS.get(str(severity_level).upper(), 5))


def route_inside_km(coords: list, centroid_lat: float, centroid_lon: float,
                    buffer_radius_km: float) -> float:
    """Length of `coords` (line) that falls inside the hazard buffer.

    Segment-based sharing: sample the segment midpoint for inside/outside,
    apply that status to the full segment. Deterministic, O(n), explained in
    the response as an approximation.
    """
    inside = 0.0
    for p1, p2 in zip(coords, coords[1:]):
        mid_lat = (p1[1] + p2[1]) / 2.0
        mid_lon = (p1[0] + p2[0]) / 2.0
        seg_km = _haversine_km(p1[1], p1[0], p2[1], p2[0])
        if _haversine_km(mid_lat, mid_lon, centroid_lat, centroid_lon) <= buffer_radius_km:
            inside += seg_km
    return round(inside, 3)


def total_route_km(coords: list) -> float:
    return sum(
        _haversine_km(p1[1], p1[0], p2[1], p2[0])
        for p1, p2 in zip(coords, coords[1:])
    )


def score_route_coords(coords: list, events: list) -> dict:
    """Compute exposures + aggregate risk 0..100 for a route geometry.

    `events` are `current_hazards()["events"]` entries. The returned dict is
    the `hazard_analysis` block attached to every route response.
    """
    total = total_route_km(coords)
    exposures = []
    total_score = 0.0
    for ev in events:
        buff = float(ev.get("buffer_radius_km") or 0)
        if buff <= 0:
            continue
        inside_km = route_inside_km(
            coords, float(ev["centroid_lat"]), float(ev["centroid_lon"]), buff
        )
        if inside_km <= 0:
            continue
        fraction = round(min(1.0, inside_km / total), 4) if total > 0 else 1.0
        weight = _event_weight(ev.get("severity_level", "LOW"))
        contribution = round(weight * fraction, 1)
        total_score += contribution
        exposures.append({
            "event_id": ev.get("event_id"),
            "hazard_type": ev.get("hazard_type"),
            "severity_level": ev.get("severity_level"),
            "severity_score": ev.get("severity_score"),
            "buffer_radius_km": buff,
            "inside_km": inside_km,
            "fraction": fraction,
            "weight": weight,
            "contribution": contribution,
        })
    total_score = round(min(100.0, total_score), 1)
    return {
        "route_risk_score": total_score,
        "risk_label": _risk_label(total_score),
        "method": (
            "segment-midpoint sharing: each route segment counts as inside a "
            "hazard buffer when its midpoint falls within the buffer radius."
        ),
        "exposures": exposures,
    }


def _route_coords(payload: dict) -> Optional[list]:
    geojson = payload.get("route_geojson") or {}
    return (geojson.get("geometry") or {}).get("coordinates")


async def _best_portfolio_route(session, habitation_id: str, site_id: str,
                                engine: str, events: list) -> list:
    """All candidate routes (base + alternatives) with scores attached."""
    base = await multi_engine_routing.route_with_engine(session, habitation_id, site_id, engine)
    if base is None or base.get("status") != "OK":
        return [base]
    candidates = [base]
    try:
        alts = await multi_engine_routing.route_alternatives(
            session, habitation_id, site_id, engine, max_alternatives=3
        )
        for r in alts.get("routes") or []:
            candidates.append({**base, "route": r["route"], "route_geojson": r["route_geojson"]})
    except Exception as exc:
        logger.info(f"[hazard-aware] alternatives unavailable, using base only: {exc}")
    for c in candidates:
        coords = _route_coords(c)
        c["hazard_analysis"] = (
            score_route_coords(coords, events) if coords else {
                "route_risk_score": None, "risk_label": None,
                "method": "no route geometry — risk not scored", "exposures": [],
            }
        )
    return candidates


async def hazard_aware_route(
    session,
    habitation_id: str,
    site_id: str,
    engine: str = "graphhopper",
    avoid_hazards: bool = True,
) -> Optional[dict]:
    """Score the engine route against active hazards; avoid when requested.

    Returns None (→ 404), an UNAVAILABLE payload (engine or region gate), or
    an OK payload that always carries `hazard_analysis`.
    """
    engine = engine if engine in multi_engine_routing.ENGINE_TIERS else "graphhopper"

    region_cfg, err = await _resolve_region_gate(session, habitation_id, site_id, engine)
    if region_cfg is None:
        return None if err is None else err

    events = (await current_hazards(session, region=region_cfg.key)).get("events") or []

    candidates = await _best_portfolio_route(session, habitation_id, site_id, engine, events)
    base = candidates[0]
    if base is None:
        return None
    if base.get("status") != "OK":
        return {**base, "hazard_analysis": {
            "route_risk_score": None, "risk_label": "UNKNOWN",
            "method": "no road route returned — hazard exposure not scored",
            "exposures": [], "reason": base.get("reason"),
        }}

    chosen = base
    avoided = False
    if avoid_hazards and len(candidates) > 1:
        scored = [c for c in candidates if c.get("hazard_analysis", {}).get("route_risk_score") is not None]
        if scored:
            scored.sort(key=lambda c: c["hazard_analysis"]["route_risk_score"])
            best = scored[0]
            base_score = base["hazard_analysis"]["route_risk_score"]
            best_score = best["hazard_analysis"]["route_risk_score"]
            if best is not base and best_score < base_score - 5.0:
                chosen = best
                avoided = True

    out = {k: v for k, v in chosen.items()}
    out["avoidance"] = {
        "enabled": avoid_hazards,
        "avoided": avoided,
        "note": (
            "The lowest-risk candidate was selected because it scored more "
            "than 5 risk points below the engine's base route."
            if avoided else
            "Base route kept: no alternative was meaningfully safer "
            "(< 5 risk-point improvement)."
        ),
        "candidates_count": len(candidates),
    }
    out["hazard_analysis"] = {
        **chosen.get("hazard_analysis", {}),
        "events_evaluated": len(events),
        "hazard_empty": len(events) == 0,
    }
    return out


async def _resolve_region_gate(session, habitation_id: str, site_id: str, engine: str):
    from app.core.regions import REGIONS
    from app.services.spatial_service import _resolve_habitation, _resolve_site

    hab = await _resolve_habitation(session, habitation_id)
    site = await _resolve_site(session, site_id)
    if hab is None or site is None:
        return None, None
    hab_lat, hab_lon, _ = hab
    site_lat, site_lon, _ = site
    coords = (hab_lat, hab_lon, site_lat, site_lon)
    cfg, err = multi_engine_routing._region_gate(habitation_id, site_id, engine, coords)
    return cfg, err