"""Dynamic current risk (Slice 3).

Baseline (permanent susceptibility) risk comes from the deterministic engine
components (demo_data canonical). The event-escalation term is now FED by live
sources:

  - 72h rainfall at the habitation's nearest weather station (DERIVED from
    live OBSERVED weather) → existing rain escalation formula
    (0.05 x (rain72 - 150), only above the trigger).
  - active hazard_events exposure intensity at the habitation point (0-100)
    → ESCALATION_EVENT_COEFF x intensity, summed with the rain term and capped
    together by ESCALATION_CAP.

current operational risk = min(100, baseline susceptibility + escalation).

Each live recompute is persisted to risk_scores as a NEW ledger row (baseline
retained per row) so the DB keeps a timeline of risk deltas. When no live
source is present the endpoint returns the labeled DEMO path unchanged — never
fabricates an escalation.

Soil saturation and river level are NOT available from the primary live source
(WeatherAPI.com); both feed the escalation formula as 0 and are reported
UNAVAILABLE in the basis — the coefficients are documented Sentinel AI
baselines, not official government formulas.
"""

from __future__ import annotations

import json

import logging

import math
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services import data_read, demo_data
from app.services import hazard_service as hazard_svc
from app.services.hazard_service import exposure_intensity
from app.services.risk_engine import compute_event_escalation

# district id → live-weather region (source of station input for habitations).
DISTRICT_REGION = {"idukki": "kerala"}

logger = logging.getLogger(__name__)

# ── In-process freshness cache (keyed by district) ──────────────────────────
_cache: dict = {}
LAST_CACHE_KEYS: list = []


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def station_for(lat: float, lon: float) -> Optional[dict]:
    """Nearest pilot weather station to a point (haversine)."""
    from app.services.weather_service import WEATHER_STATIONS

    best, best_d = None, None
    for s in WEATHER_STATIONS:
        d = _haversine_km(lat, lon, s.latitude, s.longitude)
        if best_d is None or d < best_d:
            best, best_d = s, d
    if best is None:
        return None
    return {"id": best.id, "region": best.region, "place": best.place}


def base_components(habitation_id: str) -> dict:
    """Deterministic base-susceptibility components for a habitation."""
    comps = demo_data.RISK_COMPONENTS_BY_HABITATION.get(
        habitation_id,
        {"hazard": 0.0, "exposure": 0.0, "vulnerability": 0.0, "interaction": 0.0},
    )
    return dict(comps)


def baseline_score(habitation_id: str) -> float:
    """Engine base susceptibility = sum of the four deterministic components.

    Falls back to the demo narrative baseline (risk_score - risk_change) only
    when the canonical components are missing, so the DEMO path never crashes.
    """
    comps = base_components(habitation_id)
    if sum(comps.values()) > 0:
        return round(sum(comps.values()), 2)
    h = next(
        (x for x in demo_data.get_habitation_list("idukki")["habitations"]
         if x["id"] == habitation_id),
        None,
    )
    if h:
        return round(h["risk_score"] - h["risk_change"], 2)
    return 0.0


def compute_dynamic_score(
    habitation_id: str,
    rainfall_mm_72h: Optional[float] = None,
    hazard_intensity: float = 0.0,
) -> dict:
    """Current operational risk = baseline + live-driven escalation (0-100).

    Escalation = rain formula (only above RAINFALL_TRIGGER_MM; saturation and
    river feed as 0 because no live source) + ESCALATION_EVENT_COEFF x active
    hazard exposure intensity, floored at 0 and capped by ESCALATION_CAP.
    """
    base = baseline_score(habitation_id)
    rain = rainfall_mm_72h if rainfall_mm_72h is not None else 0.0
    esc_weather = compute_event_escalation(rain, 0.0, 0.0)
    esc_event = settings.ESCALATION_EVENT_COEFF * max(0.0, hazard_intensity)
    esc_total = min(max(0.0, esc_weather + esc_event), settings.ESCALATION_CAP)
    current = min(100.0, base + esc_total)
    return {
        "baseline_score": round(base, 2),
        "event_escalation": round(esc_total, 2),
        "escalation_weather": round(esc_weather, 2),
        "escalation_hazard": round(esc_event, 2),
        "current_score": round(current, 2),
        "current_score_rounded": int(round(current)),
        "equation": (
            f"baseline {base:.2f} + escalation {esc_total:.2f} "
            f"(rain {esc_weather:.2f} + events {esc_event:.2f}) = "
            f"{current:.2f} (capped by {settings.ESCALATION_CAP})"
        ),
    }


def _exposure_for_habitation(lat: float, lon: float, events: list) -> dict:
    """Max exposure intensity of active events at a point + covering ids."""
    best_intensity, covering = 0.0, []
    for ev in events:
        dist = _haversine_km(
            lat, lon, ev["centroid_lat"], ev["centroid_lon"]
        )
        if dist > ev.get("buffer_radius_km", 0):
            continue
        intensity = exposure_intensity(
            dist, ev["severity_score"], ev["buffer_radius_km"]
        )
        covering.append(ev["event_id"])
        if intensity > best_intensity:
            best_intensity = intensity
    return {"hazard_intensity": best_intensity, "covering_event_ids": covering}


# ── Read/load helpers ───────────────────────────────────────────────────────

async def _weather_map(session: AsyncSession) -> dict:
    """Latest observation per station (72h window) with honest basis."""
    w = await data_read.get_recent_weather(session, region=None, hours=72)
    obs = w.get("observations", [])
    by_station = {o["station_id"]: o for o in obs}
    return {
        "data_status": w.get("data_status"),
        "reason": w.get("reason"),
        "row_count": w.get("row_count", 0),
        "by_station": by_station,
    }


def _live_available(weather: dict) -> bool:
    return weather.get("data_status") in ("LIVE", "STALE")


async def _persist_recompute(session: AsyncSession, rows: list) -> bool:
    """Ledger insert of one live recompute per habitation (baseline retained)."""
    if session is None or not rows:
        return False
    try:
        for r in rows:
            await session.execute(
                text(
                    """
                    INSERT INTO risk_scores (
                        habitation_id, current_score, baseline_score,
                        hazard_component, exposure_component,
                        vulnerability_component, interaction_component,
                        event_escalation_component, live_inputs,
                        data_type, data_status
                    ) VALUES (
                        :habitation_id, :current_score, :baseline_score,
                        :hazard_component, :exposure_component,
                        :vulnerability_component, :interaction_component,
                        :event_escalation, CAST(:live_inputs AS jsonb),
                        'DERIVED', 'LIVE'
                    )
                    """
                ),
                {
                    "habitation_id": r["habitation_id"],
                    "current_score": r["current_score"],
                    "baseline_score": r["baseline_score"],
                    "hazard_component": r["hazard_component"],
                    "exposure_component": r["exposure_component"],
                    "vulnerability_component": r["vulnerability_component"],
                    "interaction_component": r["interaction_component"],
                    "event_escalation": r["event_escalation_component"],
                    "live_inputs": json.dumps(r["live_inputs"]),
                },
            )
        await session.commit()
        return True
    except Exception:
        await session.rollback()
        return False


async def get_timeline(
    session: AsyncSession,
    habitation_id: str,
    limit: int = 30,
) -> dict:
    """Recent recompute history for one habitation (risk-delta timeline)."""
    limit = max(1, min(int(limit or 30), 200))
    try:
        result = await session.execute(
            text(
                """
                SELECT computed_at, current_score, baseline_score,
                       event_escalation_component
                FROM risk_scores
                WHERE habitation_id = :hid
                ORDER BY computed_at DESC
                LIMIT :limit
                """
            ),
            {"hid": habitation_id, "limit": limit},
        )
        rows = result.mappings().all()
    except Exception:
        return {"data_status": "UNAVAILABLE", "reason": "database connection failed", "points": []}
    if not rows:
        return {"data_status": "EMPTY", "reason": "no recompute rows persisted yet", "points": []}
    points = [
        {
            "computed_at": r["computed_at"].isoformat(),
            "current_score": r["current_score"],
            "baseline_score": r["baseline_score"],
            "event_escalation": r["event_escalation_component"],
        }
        for r in rows
    ]
    return {
        "data_status": "LIVE",
        "habitation_id": habitation_id,
        "points": points,
    }


# ── Public entry points ─────────────────────────────────────────────────────

def _demo_list_entry(h: dict) -> dict:
    """The labeled DEMO path: current = demo narrative, escalation = change."""
    hid = h["id"]
    return {
        "id": hid,
        "name": h["name"],
        "population": h["population"],
        "latitude": h["latitude"],
        "longitude": h["longitude"],
        "priority": h["priority"],
        "primary_hazard": h["primary_hazard"],
        "baseline_score": round(h["risk_score"] - h["risk_change"], 2),
        "event_escalation": float(h["risk_change"]),
        "escalation_weather": None,
        "escalation_hazard": None,
        "current_score": float(h["risk_score"]),
        "current_score_rounded": int(round(h["risk_score"])),
        "data_status": "DEMO",
        "data_type": "DERIVED",
        "live_inputs": None,
    }


async def current_risk(
    session: AsyncSession,
    district_id: str = "idukki",
    ttl: Optional[int] = None,
) -> dict:
    """Dynamic current risk for a district, fed by live weather + events.

    LIVE when weather observations are present (all habitations keyed to their
    nearest station); DEMO labeled fallback otherwise — never fabricated.
    """
    ttl = settings.RISK_CACHE_TTL_S if ttl is None else ttl
    cache_key = district_id
    now_ts = time.time()
    cached = _cache.get(cache_key)
    if cached and (now_ts - cached["ts"]) < ttl:
        return cached["payload"]

    if district_id not in DISTRICT_REGION:
        return {
            "data_status": "UNAVAILABLE",
            "reason": f"unknown district: {district_id}",
            "district_id": district_id,
            "computed_at": _now().isoformat(),
            "habitations": [],
        }
    region = DISTRICT_REGION[district_id]
    habitations = demo_data.get_habitation_list(district_id).get("habitations", [])

    weather = await _weather_map(session)

    # Active events for the region that sources this district's stations.
    events_payload = await hazard_svc.current_hazards(
        session,
        region=region,
        ttl=settings.HAZARD_CACHE_TTL_S,
    )
    events = events_payload.get("events", [])
    event_basis = {
        "data_status": events_payload.get("data_status"),
        "events_considered": len(events),
        "reason": events_payload.get("reason"),
    }

    basis = {
        "weather": {
            "data_status": weather.get("data_status"),
            "reason": weather.get("reason"),
            "observations": weather.get("row_count", 0),
        },
        "hazard_events": event_basis,
        "soil_saturation": {
            "data_status": "UNAVAILABLE",
            "reason": "no live soil-moisture source connected — feeds escalation as 0",
        },
        "river_level": {
            "data_status": "UNAVAILABLE",
            "reason": "no live river-gauge source connected — feeds escalation as 0",
        },
    }

    if not _live_available(weather):
        payload = {
            "data_status": "DEMO",
            "district_id": district_id,
            "computed_at": _now().isoformat(),
            "mode": "current",
            "basis": basis,
            "note": (
                "No live weather — returning the labeled DEMO risk path "
                "(demo narrative current/baseline). Dynamic risk activates "
                "only when weather observations are present."
            ),
            "habitations": [_demo_list_entry(h) for h in habitations],
        }
        _cache[cache_key] = {"ts": now_ts, "payload": payload}
        return payload

    # Live path: per-habitation dynamic risk from nearest-station weather + event exposure.
    rows_to_persist = []
    entries = []
    live_count = 0
    for h in habitations:
        hid = h["id"]
        station = station_for(h["latitude"], h["longitude"])
        obs = weather["by_station"].get(station["id"]) if station else None
        exposure = _exposure_for_habitation(h["latitude"], h["longitude"], events)

        if obs is None:
            # No observation for the nearest station → honest per-habitation DEMO (no live input).
            entries.append(_demo_list_entry(h))
            continue
        live_count += 1
        score = compute_dynamic_score(
            hid,
            rainfall_mm_72h=obs.get("rainfall_mm_72h"),
            hazard_intensity=exposure["hazard_intensity"],
        )
        comps = base_components(hid)
        live_inputs = {
            "station_id": station["id"],
            "station_place": station["place"],
            "rainfall_mm_72h": obs.get("rainfall_mm_72h"),
            "soil_saturation_pct": None,
            "river_level_anomaly_m": None,
            "hazard_intensity": exposure["hazard_intensity"],
            "covering_event_ids": exposure["covering_event_ids"],
        }
        entries.append({
            "id": hid,
            "name": h["name"],
            "population": h["population"],
            "latitude": h["latitude"],
            "longitude": h["longitude"],
            "priority": h["priority"],
            "primary_hazard": h["primary_hazard"],
            "baseline_score": score["baseline_score"],
            "event_escalation": score["event_escalation"],
            "escalation_weather": score["escalation_weather"],
            "escalation_hazard": score["escalation_hazard"],
            "current_score": score["current_score"],
            "current_score_rounded": score["current_score_rounded"],
            "data_status": "LIVE",
            "data_type": "DERIVED",
            "live_inputs": live_inputs,
            "equation": score["equation"],
        })
        rows_to_persist.append({
            "habitation_id": hid,
            "current_score": score["current_score"],
            "baseline_score": score["baseline_score"],
            "hazard_component": comps["hazard"],
            "exposure_component": comps["exposure"],
            "vulnerability_component": comps["vulnerability"],
            "interaction_component": comps["interaction"],
            "event_escalation_component": score["event_escalation"],
            "live_inputs": live_inputs,
        })

    persisted = await _persist_recompute(session, rows_to_persist)

    payload = {
        "data_status": "LIVE",
        "district_id": district_id,
        "computed_at": _now().isoformat(),
        "mode": "current",
        "basis": basis,
        "persisted": persisted,
        "note": (
            "Current operational risk = baseline susceptibility + live escalation "
            "(72h rainfall at nearest station; active hazard event exposure). "
            "Escalation feeds as 0 when below trigger or no event covers the point. "
            "Coefficients are Sentinel AI configurable baselines — not official formulas."
        ),
        "habitations": entries,
        "live_habitations": live_count,
    }
    _cache[cache_key] = {"ts": now_ts, "payload": payload}
    return payload


def _rpi_weights() -> dict:
    return {
        "risk": settings.RPI_WEIGHT_RISK,
        "vulnerability": settings.RPI_WEIGHT_VULNERABILITY,
        "exposed_population": settings.RPI_WEIGHT_EXPOSED_POP,
        "historical": settings.RPI_WEIGHT_HISTORICAL,
        "urgency": settings.RPI_WEIGHT_URGENCY,
    }


def _priority_demo_payload(district_id: str, reason: str) -> dict:
    """Honest DEMO fallback — the documented RPI ranking, labelled not-live."""
    habitations = demo_data.get_habitation_list(district_id)["habitations"]
    rpi_data = demo_data.RPI_BY_HABITATION
    ranked = sorted(
        [{**h, "rpi_score": rpi_data.get(h["id"], 0)} for h in habitations],
        key=lambda x: x["rpi_score"],
        reverse=True,
    )
    return {
        "data_status": "DEMO",
        "data_type": "DERIVED",
        "district_id": district_id,
        "reason": reason,
        "weights": _rpi_weights(),
        "note": (
            "RPI = 0.35×Risk + 0.20×Vulnerability + 0.15×Population + 0.15×Historical "
            "+ 0.15×Urgency. Configurable baseline weights — not official formula."
        ),
        "habitations": ranked,
    }


async def district_priorities(session: AsyncSession, district_id: str = "idukki") -> dict:
    """Live-first district RPI ranking from the latest persisted risk scores.

    DERIVED when live risk rows exist — rankings come from current_score as
    recomputed by the risk engine, never re-invented here. On DB error / empty
    ledger, the DEMO ranking is returned with a reason (never a fake LIVE).
    """
    try:
        result = await session.execute(
            text(
                """
                SELECT h.id, h.name, h.population, r.current_score
                FROM habitations h
                JOIN LATERAL (
                    SELECT current_score
                    FROM risk_scores rs
                    WHERE rs.habitation_id = h.id
                    ORDER BY rs.computed_at DESC
                    LIMIT 1
                ) r ON true
                WHERE h.district_id = :district_id
                """
            ),
            {"district_id": district_id},
        )
    except Exception as exc:  # noqa: BLE001 — DB down must not 500
        logger.warning(
            f"[risk] priorities query failed for {district_id}: {type(exc).__name__}: {exc}"
        )
        return _priority_demo_payload(
            district_id, reason=f"risk_scores query failed: {type(exc).__name__}"
        )

    rows = result.mappings().all()
    if not rows:
        return _priority_demo_payload(
            district_id,
            reason="no live risk_scores rows persisted yet — demo ranking shown "
                   "(scores are never re-invented)",
        )

    ranked = sorted(
        [{
            "habitation_id": r["id"],
            "name": r["name"],
            "population": r["population"] or 0,
            "current_score": float(r["current_score"] or 0),
            "current_score_rounded": int(round(r["current_score"] or 0)),
        } for r in rows],
        key=lambda x: x["current_score"],
        reverse=True,
    )
    return {
        "data_status": "DERIVED",
        "data_type": "DERIVED",
        "district_id": district_id,
        "weights": _rpi_weights(),
        "note": (
            "Ranking uses the latest live current_score per habitation (persisted by "
            "the risk engine) with the documented RPI baseline weights. Scores are "
            "recomputed live, never re-invented; thresholds match the risk engine."
        ),
        "habitations": ranked,
    }