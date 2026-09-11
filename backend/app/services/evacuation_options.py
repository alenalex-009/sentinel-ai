"""Automatic evacuation option synthesis (map-driven relocation workflow).

For one affected habitation (explicit, or the district's highest-demand
habitation), evaluate EVERY live safe-zone candidate and rank them:

  origin coords (PostGIS) → policy engine (ROUTE_STANDARD osrm→valhalla,
  ROUTE_ADVANCED valhalla→none) → hazard-aware route per site →
  route risk + capacity + ETA ranking → recommended_route +
  alternative_routes[] + rejected_options[].

Honesty rules (project contract):
  - A route appears only when a real engine answered; `served_by` is the
    engine that actually served (never the policy pick).
  - UNAVAILABLE options carry the engine's reason — no fabricated geometry.
  - capacity_gap = max(0, demand - capacity); unallocated is reported, never
    silently absorbed.
  - A HIGH/EXTREME-risk route (hazard intersection) can be returned for
    inspection but is never the recommendation.
  - No coordinates, roads, polygons or ETAs are invented; the DEMO path
    returns an empty option set with a reason.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import (
    hazard_aware_routing,
    hazard_service,
    multi_engine_routing,
    relocation_service,
    risk_service,
)

logger = logging.getLogger(__name__)

# Rejection cut-offs (documented baselines, matching the hazard-aware
# router's labels): MODERATE routes stay viable alternatives; HIGH/EXTREME
# routes cross an active hazard buffer and are never recommended.
_NON_RECOMMENDED_LABELS = {"HIGH", "EXTREME"}

# Bound the work: routes are only computed for candidates that could host
# someone (capacity > 0). Zero-capacity discovery points are still listed
# as evaluated, with the honest rejection reason.
_MAX_ROUTED_SITES = 8


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    import math
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _site_route_id(s: dict) -> str:
    """Id the routing resolvers understand: base candidate-site id first."""
    return str(s.get("base_site_id") or s["id"])


def _events_near_origin(events: list, lat: float, lon: float) -> list:
    """Active events whose buffer actually covers the origin point."""
    near = []
    for ev in events or []:
        c_lat, c_lon = ev.get("centroid_lat"), ev.get("centroid_lon")
        radius = float(ev.get("buffer_radius_km") or 0)
        if c_lat is None or c_lon is None or radius <= 0:
            continue
        if _haversine_km(lat, lon, float(c_lat), float(c_lon)) <= radius:
            near.append(ev.get("event_id"))
    return near


def _risk_sort_key(opt: dict):
    # Lowest risk first; among equals prefer capacity-sufficient, then ETA.
    return (
        opt["risk_score"] if opt["risk_score"] is not None else 999.0,
        0 if opt["capacity_sufficient"] else 1,
        opt["duration_min"] if opt["duration_min"] is not None else 9999.0,
    )


def _recommendation_reason(opt: dict, origin_demand: int, hazards_active: int) -> str:
    """Human-readable explanation assembled from the ACTUAL result values."""
    parts = []
    risk = opt.get("risk_label")
    score = opt.get("risk_score")
    if risk:
        parts.append(
            f"{risk} validated route risk (score {score})" if score is not None
            else f"{risk} route risk"
        )
    if hazards_active > 0:
        exposures = (opt.get("hazard_exposure") or {}).get("events") or []
        if not exposures:
            parts.append(f"avoids all {hazards_active} active hazard buffer(s)")
        else:
            parts.append(f"crosses {len(exposures)} hazard buffer(s)")
    else:
        parts.append("no active hazard events on the route")
    cap = opt.get("capacity_available") or 0
    if cap >= origin_demand:
        parts.append(f"capacity {cap:,} covers demand {origin_demand:,}")
    else:
        parts.append(
            f"largest viable capacity {cap:,} vs demand {origin_demand:,} "
            "— multi-site allocation required"
        )
    parts.append(f"{opt.get('distance_km')} km / {opt.get('eta_min')} min via {opt.get('served_by')}")
    return "Recommended: " + "; ".join(parts) + "."


def _alternative_reason(opt: dict, recommended: Optional[dict], origin_demand: int) -> str:
    parts = []
    if opt.get("capacity_available", 0) < origin_demand:
        parts.append(
            f"capacity {opt.get('capacity_available'):,} below demand {origin_demand:,}"
        )
    if recommended:
        d_risk = (opt.get("risk_score") or 0) - (recommended.get("risk_score") or 0)
        d_eta = (opt.get("eta_min") or 0) - (recommended.get("eta_min") or 0)
        if d_risk > 0:
            parts.append(f"+{round(d_risk, 1)} risk points vs recommended")
        if d_eta > 0:
            parts.append(f"{round(d_eta)} min slower than recommended")
        if d_risk < 0:
            parts.append(f"{round(-d_risk, 1)} risk points lower, ranked lower on capacity/ETA fit")
    return "Alternative: " + ("; ".join(parts) + "." if parts else "viable option.")


def _rejected_reason(opt: dict) -> str:
    return opt.get("reason") or "not viable"


async def build_evacuation_options(
    session: AsyncSession,
    district_id: str = "idukki",
    habitation_id: Optional[str] = None,
    policy: str = "ROUTE_STANDARD",
    region: Optional[str] = None,
) -> dict:
    """Evaluate every safe-zone candidate for one origin and rank the options."""
    generated_at = _now_iso()
    policy = policy if policy in multi_engine_routing._ROUTING_POLICY_CHAINS else "ROUTE_STANDARD"
    region = region or risk_service.DISTRICT_REGION.get(district_id, "kerala")

    # 1. Live district demand (drives origin choice + capacity summary).
    demand = await relocation_service.calculate_demand(session, district_id)
    demand_status = getattr(demand.get("data_status"), "value", demand.get("data_status"))
    hab_rows = [h for h in (demand.get("habitations") or [])
                if (h.get("relocation_demand") or 0) > 0]

    # 2. Live safe-zone candidates (None == DB down, [] == none discovered).
    sites = await relocation_service.get_safe_zone_sites(session, district_id)

    degraded = {
        "data_status": "UNAVAILABLE",
        "district_id": district_id,
        "generated_at": generated_at,
        "origin": None,
        "recommended_route": None,
        "alternative_routes": [],
        "rejected_options": [],
        "capacity_summary": None,
        "reason": "",
        "policy": policy,
        "note": (
            "No route is fabricated when live inputs are missing — see reason."
        ),
    }

    if sites is None or demand_status not in ("DERIVED", "LIVE"):
        degraded["data_status"] = "DEMO"
        degraded["reason"] = (
            "PostGIS unavailable — live demand/safe-zone data could not be read; "
            "no evacuation options are fabricated."
        )
        return degraded

    if not sites:
        degraded["data_status"] = "EMPTY"
        degraded["reason"] = (
            "No safe-zone candidates pass hard constraints for this district yet — "
            "run safe-zone discovery first."
        )
        return degraded

    if not hab_rows:
        degraded["data_status"] = "EMPTY"
        degraded["reason"] = "No habitation currently requires relocation (all scores below threshold)."
        return degraded

    # 3. Origin: explicit habitation, else the highest-demand affected one.
    if habitation_id:
        origin_row = next((h for h in demand.get("habitations", [])
                           if h.get("habitation_id") == habitation_id), None)
        # Explicit id with zero demand is still evaluated (operator choice),
        # but coordinates must exist.
        if origin_row is None:
            origin_row = {"habitation_id": habitation_id, "name": habitation_id,
                          "relocation_demand": 0}
    else:
        origin_row = max(hab_rows, key=lambda h: h.get("relocation_demand") or 0)

    origin_id = origin_row.get("habitation_id") or origin_row.get("id")
    origin_demand = int(origin_row.get("relocation_demand") or 0)
    o_lat, o_lon = origin_row.get("latitude"), origin_row.get("longitude")
    if o_lat is None or o_lon is None:
        # Fall back to the spatial resolver (PostGIS habitations.geom).
        from app.services.spatial_service import _resolve_habitation
        resolved = await _resolve_habitation(session, origin_id)
        if resolved is None:
            degraded["reason"] = f"Origin habitation {origin_id} has no resolvable coordinates."
            return degraded
        o_lat, o_lon = resolved[0], resolved[1]

    # 4. Policy engine pick (osrm→valhalla | valhalla→none). Honest: no
    #    engine means no routes, with the reason carried on every option.
    engine = await multi_engine_routing.pick_engine(region, policy)
    chain = multi_engine_routing._ROUTING_POLICY_CHAINS[policy]
    primary = chain[0]
    engine_reason = None if engine else (
        f"no ready routing engine for policy {policy} "
        f"({', '.join(chain)} unavailable)"
    )

    # 5. Hazard context for the origin (drives exposure + reasons).
    hazards = await hazard_service.current_hazards(session, region=region)
    events = hazards.get("events") or []
    events_near_origin = _events_near_origin(events, float(o_lat), float(o_lon))

    # 6. Evaluate every candidate.
    options_ok, alternatives, rejected = [], [], []
    routed = 0
    for s in sites:
        cap = int(s.get("estimated_capacity") or 0)
        base = {
            "site_id": str(s["id"]),
            "route_site_id": _site_route_id(s),
            "destination": {
                "id": str(s["id"]),
                "name": s.get("name") or s["id"],
                "latitude": s.get("lat"),
                "longitude": s.get("lon"),
                "capacity": cap,
                "suitability_score": s.get("suitability_score"),
                "safety_score": s.get("safety_score"),
                "status": s.get("constraint_pass"),
            },
            "capacity_available": cap,
            "engine_requested": engine,
        }
        if cap <= 0:
            rejected.append({**base, "status": "REJECTED", "reason":
                             "no assessed safe capacity — discovery-grid candidate, not yet a viable destination"})
            continue
        if engine is None:
            rejected.append({**base, "status": "UNAVAILABLE", "reason": engine_reason})
            continue
        if routed >= _MAX_ROUTED_SITES:
            rejected.append({**base, "status": "NOT_EVALUATED", "reason":
                             f"evaluation cap ({_MAX_ROUTED_SITES} routed sites) reached"})
            continue
        routed += 1
        route = await hazard_aware_routing.hazard_aware_route(
            session, origin_id, _site_route_id(s), engine=engine, avoid_hazards=True)
        if route is None:
            rejected.append({**base, "status": "REJECTED", "reason":
                             "candidate has no resolvable road-network endpoint"})
            continue
        if route.get("status") != "OK":
            rejected.append({**base, "status": "UNAVAILABLE",
                             "reason": route.get("reason") or "engine returned no route"})
            continue

        served_by = route.get("engine")
        analysis = route.get("hazard_analysis") or {}
        exposures = analysis.get("exposures") or []
        risk_score = analysis.get("route_risk_score")
        risk_label = analysis.get("risk_label")
        rd = route.get("route") or {}
        option = {
            **base,
            "status": "OK",
            "origin": {
                "id": origin_id,
                "name": origin_row.get("name") or origin_id,
                "latitude": float(o_lat),
                "longitude": float(o_lon),
                "relocation_demand": origin_demand,
            },
            "distance_km": rd.get("distance_km"),
            "duration_min": rd.get("duration_min"),
            "eta_min": rd.get("duration_min"),
            "risk_score": risk_score,
            "risk_label": risk_label,
            "hazard_exposure": {
                "events": [e.get("event_id") for e in exposures],
                "inside_km_total": round(sum(e.get("inside_km") or 0 for e in exposures), 2),
                "events_evaluated": analysis.get("events_evaluated", len(events)),
            },
            "capacity_sufficient": cap >= origin_demand,
            "engine": served_by,
            "served_by": served_by,
            "fallback_used": bool(served_by and served_by != primary),
            "route_geojson": route.get("route_geojson"),
            "avoidance": route.get("avoidance"),
        }
        if risk_label in _NON_RECOMMENDED_LABELS:
            rejected.append({**{k: v for k, v in option.items() if k != "route_geojson"},
                             "status": "REJECTED",
                             "reason": f"route risk {risk_label} (score {risk_score}) — crosses/near an active hazard buffer"})
            continue
        options_ok.append(option)

    # 7. Rank: lowest risk, then capacity fit, then ETA.
    options_ok.sort(key=_risk_sort_key)
    recommended = options_ok[0] if options_ok else None
    for opt in options_ok[1:]:
        alternatives.append(opt)

    if recommended:
        recommended["recommendation_rank"] = 1
        recommended["recommendation_reason"] = _recommendation_reason(
            recommended, origin_demand, len(events))
        for i, opt in enumerate(alternatives, start=2):
            opt["recommendation_rank"] = i
            opt["recommendation_reason"] = _alternative_reason(
                opt, recommended, origin_demand)
    for opt in rejected:
        opt["recommendation_reason"] = _rejected_reason(opt)

    total_capacity = sum(int(s.get("estimated_capacity") or 0) for s in sites)
    district_demand = int(demand.get("total_demand") or 0)
    capacity_summary = {
        "data_status": demand_status,
        "origin_demand": origin_demand,
        "district_total_demand": district_demand,
        "total_capacity": total_capacity,
        "capacity_gap": max(0, origin_demand - total_capacity),
        "capacity_gap_formula": "max(0, demand - capacity)",
        "unallocated_demand": max(0, origin_demand - total_capacity),
        "note": (
            "Gap is origin-habitation demand minus total candidate capacity. "
            "Multi-site OR-Tools allocation (relocation plan) distributes demand "
            "across sites; unallocated is what no site can absorb."
        ),
    }

    any_ok = bool(options_ok)
    data_status = "LIVE" if any_ok and demand_status in ("DERIVED", "LIVE") else (
        "DEMO" if not any_ok and demand_status == "DEMO" else
        ("DERIVED" if any_ok else "UNAVAILABLE")
    )

    return {
        "data_status": data_status,
        "district_id": district_id,
        "habitation_id": origin_id,
        "generated_at": generated_at,
        "origin": {
            "id": origin_id,
            "name": origin_row.get("name") or origin_id,
            "latitude": float(o_lat),
            "longitude": float(o_lon),
            "relocation_demand": origin_demand,
            "events_near_origin": events_near_origin,
        },
        "policy": policy,
        "engine_policy": (
            f"{policy} ({multi_engine_routing.ROUTING_POLICY.get(policy, '')})"
        ),
        "engine": engine,
        "engine_unavailable_reason": engine_reason,
        "hazards": {
            "data_status": getattr(hazards.get("data_status"), "value", hazards.get("data_status")),
            "active_events": len(events),
        },
        "recommended_route": recommended,
        "alternative_routes": alternatives,
        "rejected_options": rejected,
        "evaluated_sites": len(sites),
        "routed_sites": routed,
        "capacity_summary": capacity_summary,
        "ranking_rule": (
            "Viable options are ranked by validated route risk (hazard-aware "
            "score), then capacity fit, then travel time. HIGH/EXTREME-risk "
            "routes are returned for inspection but never recommended. The "
            "fastest route is not automatically the recommendation."
        ),
        "note": (
            "Routes come only from engines that answered; served_by names the "
            "engine that actually served. Zero-capacity discovery candidates "
            "are listed with their honest rejection reason."
        ),
        "provenance": {
            "source": "live" if any_ok else "demo_fallback",
            "generated_at": generated_at,
        },
    }
