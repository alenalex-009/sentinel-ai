"""Evacuation overview synthesis (Phase 7, Task B2).

Read-only aggregation reusing existing live services — hazards, relocation
demand, safe-zone candidates and the routing policy picker. Every block
carries provenance (live / derived / demo_fallback / empty) so fallback data
is never presented as live. Never invent a disaster: when no active hazard
exists the overview reports normal-conditions guidance.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from app.services import (
    hazard_aware_routing,
    hazard_service,
    multi_engine_routing,
    relocation_service,
    safe_zone_service,
)
from app.services.optimizer import SiteInput, run_optimization
from app.services.spatial_service import _resolve_habitation

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provenance(source: str, region: Optional[str], generated_at: str) -> dict:
    return {"source": source, "region": region, "generated_at": generated_at}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km (WGS84 sphere approximation)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _dominant_payload(event: dict) -> dict:
    return {
        "event_id": event.get("event_id"),
        "hazard_type": event.get("hazard_type"),
        "severity_level": event.get("severity_level"),
        "severity_score": event.get("severity_score"),
        "centroid_lat": event.get("centroid_lat"),
        "centroid_lon": event.get("centroid_lon"),
        "started_at": event.get("started_at"),
        "source": event.get("source"),
        "data_type": event.get("data_type"),
    }


def _site_inputs(sites: list, worst_coords: Optional[tuple]) -> list:
    out = []
    for s in sites:
        lat, lon = s.get("lat"), s.get("lon")
        dist = 0.0
        if worst_coords and lat is not None and lon is not None:
            dist = round(_haversine_km(worst_coords[0], worst_coords[1], float(lat), float(lon)), 2)
        out.append(SiteInput(
            id=str(s["id"]),
            name=str(s.get("name") or s["id"]),
            c_safe=int(s.get("estimated_capacity") or 0),
            distance_km=dist,
            suitability_score=float(s.get("suitability_score") or 0),
            safety_score=float(s.get("safety_score") or 0),
            infrastructure_score=50.0,
            hard_constraints_passed=True,
        ))
    return out


def _site_payload(row: dict) -> dict:
    return {
        "id": row["id"],
        "name": row.get("name"),
        "lon": row.get("lon"),
        "lat": row.get("lat"),
        "suitability_score": row.get("suitability_score"),
        "safety_score": row.get("safety_score"),
        "estimated_capacity": row.get("estimated_capacity"),
    }


async def _resolve_worst_coords(session, worst_id: Optional[str]) -> Optional[tuple]:
    if not worst_id:
        return None
    resolved = await _resolve_habitation(session, worst_id)
    if not resolved:
        return None
    lat, lon, _source = resolved[0], resolved[1], (resolved[2] if len(resolved) > 2 else None)
    return (float(lat), float(lon))


async def build_overview(
    session,
    district_id: str = "idukki",
    disaster_type: Optional[str] = None,
) -> dict:
    """Assemble the evacuation overview for one district from live services."""
    generated_at = _now_iso()

    # 1. Hazards block — live operational picture (never invented).
    hazards = await hazard_service.current_hazards(session, region=None)
    events = hazards.get("events") or []
    danger_zones = (hazards.get("feature_collection") or {}).get("features") or []
    hazard_status = hazards.get("data_status", "EMPTY")
    dominant = max(events, key=lambda e: e.get("severity_score") or 0) if events else None
    chosen_type = disaster_type or (dominant.get("hazard_type") if dominant else None)
    hazards_block = {
        "data_status": hazard_status,
        "status": "NO_ACTIVE_EVENT" if not events else "ACTIVE",
        "disaster_type": chosen_type,
        "summary": hazards.get("summary"),
        "events_count": len(events),
        "events": events,
        "danger_zones": danger_zones,
        "danger_zones_count": len(danger_zones),
        "dominant_event": _dominant_payload(dominant) if dominant else None,
        "provenance": _provenance(
            "live" if hazard_status == "LIVE" else "empty", None, generated_at),
    }

    # 2. Affected habitations block.
    demand_data = await relocation_service.calculate_demand(session, district_id)
    habs = demand_data.get("habitations") or []
    affected = [h for h in habs if (h.get("relocation_demand") or 0) > 0]
    population_at_risk = int(sum(h.get("population") or 0 for h in affected))
    worst = (
        max(habs, key=lambda h: ((h.get("relocation_demand") or 0), (h.get("current_score") or 0)))
        if habs else None
    )
    demand_status = demand_data.get("data_status", "DEMO")
    affected_block = {
        "data_status": demand_status,
        "status": "NO_AFFECTED" if not affected else "AFFECTED",
        "affected_count": len(affected),
        "population_at_risk": population_at_risk,
        "habitations": affected,
        "note": demand_data.get("note"),
        "provenance": _provenance(
            "live" if demand_status == "DERIVED" else "demo_fallback", district_id, generated_at),
    }

    # 3. Demand / capacity / gap.
    sites = await relocation_service.get_safe_zone_sites(session, district_id)
    db_up = sites is not None
    safe_sites = list(sites) if sites else []
    capacity = int(sum(int(s.get("estimated_capacity") or 0) for s in safe_sites))
    total_demand = int(demand_data.get("total_demand") or 0)
    capacity_gap = max(0, total_demand - capacity)

    worst_id = worst.get("habitation_id") if worst else None
    worst_coords = await _resolve_worst_coords(session, worst_id)

    unallocated, opt_status, opt_note = None, "NOT_RUN", None
    if total_demand > 0 and safe_sites:
        opt = run_optimization(
            total_demand, _site_inputs(safe_sites, worst_coords),
            data_status=demand_status,
        )
        unallocated = int(opt.unallocated)
        opt_status = opt.status
        opt_note = opt.solver_note

    demand_capacity_block = {
        "data_status": demand_status,
        "total_demand": total_demand,
        "capacity": capacity,
        "capacity_gap": capacity_gap,
        "optimization": {
            "status": opt_status,
            "unallocated": unallocated,
            "solver_note": opt_note,
            "distance_basis": "straight-line (approx) — not a routed distance",
        },
        "note": "Gap is demand minus total safe-zone capacity; unallocated comes "
                "from the capacity optimizer and may exceed the gap when sites "
                "fall outside the distance bound.",
        "provenance": _provenance(
            "live" if db_up else "demo_fallback", district_id, generated_at),
    }

    # 4. Safe zones block — GeoJSON enriched with capacity + demo distance.
    sz = await safe_zone_service.get_safe_zones(session, district_id)
    features = []
    for f in sz.get("features") or []:
        props = dict(f.get("properties") or {})
        row = next((s for s in safe_sites if str(s.get("id")) == str(props.get("id"))), None)
        props["capacity"] = int(row["estimated_capacity"]) if row else props.get("estimated_capacity")
        dist = None
        if worst_coords and row and row.get("lat") is not None and row.get("lon") is not None:
            dist = round(_haversine_km(
                worst_coords[0], worst_coords[1], float(row["lat"]), float(row["lon"])), 2)
        props["distance_km"] = dist
        props["distance_basis"] = "straight-line (DEMO)" if dist is not None else None
        features.append({
            "type": "Feature",
            "geometry": f.get("geometry"),
            "properties": props,
        })
    safe_zone_block = {
        "data_status": sz.get("data_status", "DEMO"),
        "feature_collection": {"type": "FeatureCollection", "features": features},
        "capacity_total": capacity,
        "status_counts": sz.get("status_counts", {}),
        "source": sz.get("_source"),
        "note": sz.get("note"),
        "provenance": _provenance(
            "live" if db_up else "demo_fallback", district_id, generated_at),
    }

    # 5. Recommendation — best safe zone + hazard-aware route (ROUTE_ADVANCED).
    best_site = (
        max(safe_sites, key=lambda s: (
            float(s.get("suitability_score") or 0) * float(s.get("safety_score") or 0) / 100.0
        )) if safe_sites else None
    )
    engine = None
    route = None
    if best_site and worst_id:
        engine = await multi_engine_routing.pick_engine("kerala", "ROUTE_ADVANCED")
        if engine:
            route = await hazard_aware_routing.hazard_aware_route(
                session, worst_id, best_site["id"], engine=engine, avoid_hazards=True)

    if not best_site:
        rec_status, rec_reason = "UNAVAILABLE", "no safe-zone candidate sites"
    elif not worst_id:
        rec_status, rec_reason = "UNAVAILABLE", "no affected habitation to route from"
    elif not engine:
        rec_status, rec_reason = "UNAVAILABLE", "no ready advanced engine (ROUTE_ADVANCED)"
    elif route is None:
        rec_status, rec_reason = "UNAVAILABLE", "unknown habitation or candidate-site id"
    else:
        rec_status = route.get("status", "UNAVAILABLE")
        rec_reason = route.get("reason") if rec_status != "OK" else None

    route_payload = None
    hazard_analysis = None
    avoidance = None
    route_feature = None
    if route and rec_status == "OK":
        route_payload = route.get("route")
        hazard_analysis = route.get("hazard_analysis")
        avoidance = route.get("avoidance")
        route_feature = route.get("route_geojson")

    # The engine that actually served, read from the route payload — never
    # asserted from the policy pick (mirrors reports.py honesty rules).
    served_by = (route or {}).get("engine") if rec_status == "OK" else None
    recommendation_block = {
        "status": rec_status,
        "reason": rec_reason,
        "route_policy": "ROUTE_ADVANCED (valhalla -> none)",
        "engine": engine,
        "served_by": served_by,
        "fallback_used": bool(served_by and served_by != "valhalla"),
        "recommended_site": _site_payload(best_site) if best_site else None,
        "route": route_payload,
        "route_feature": route_feature,
        "hazard_analysis": hazard_analysis,
        "avoidance": avoidance,
        "provenance": _provenance(
            "live" if rec_status == "OK" else "demo_fallback", district_id, generated_at),
    }

    # 6. Alternatives — to the recommended route (cap 3).
    if engine and best_site and worst_id:
        alternatives_block = await multi_engine_routing.route_alternatives(
            session, worst_id, best_site["id"], engine, max_alternatives=3)
        alternatives_block["provenance"] = _provenance(
            "live" if alternatives_block.get("status") == "OK" else "demo_fallback",
            district_id, generated_at)
    else:
        alternatives_block = {
            "status": "UNAVAILABLE",
            "reason": ("no ready advanced engine" if not engine else
                       "no safe-zone candidate sites"),
            "routes": [],
            "provenance": _provenance("demo_fallback", district_id, generated_at),
        }

    # 7. Evacuation status.
    hazard_active = bool(dominant)
    if capacity_gap > 0 and hazard_active:
        evac_level = "CRITICAL"
    elif capacity_gap > 0:
        evac_level = "HIGH"
    else:
        evac_level = dominant.get("severity_level") if hazard_active else "NORMAL"
    evacuation_status = {
        "level": evac_level,
        "hazard_active": hazard_active,
        "disaster_type": chosen_type,
        "affected_count": len(affected),
        "population_at_risk": population_at_risk,
        "total_demand": total_demand,
        "capacity": capacity,
        "capacity_gap": capacity_gap,
        "unallocated": unallocated,
        "summary": (
            f"{len(affected)} habitation(s) affected, {population_at_risk} people at risk, "
            f"demand {total_demand} vs capacity {capacity} "
            f"(gap {capacity_gap})."
            if hazard_active else
            "No active hazard — normal-conditions guidance. Evacuation is not warranted "
            "by current data."
        ),
        "provenance": _provenance(
            "live" if (hazard_active or demand_status == "DERIVED") else "demo_fallback",
            district_id, generated_at),
    }

    statuses = [hazard_status, demand_status, safe_zone_block["data_status"]]
    if hazard_status == "LIVE":
        overall_status = "LIVE"
    elif demand_status == "DERIVED":
        overall_status = "DERIVED"
    elif "DEMO" in statuses:
        overall_status = "DEMO"
    else:
        overall_status = "EMPTY"

    return {
        "data_status": overall_status,
        "region": district_id,
        "disaster_type": chosen_type,
        "generated_at": generated_at,
        "note": (
            "Evacuation synthesis overview. Every block carries its own provenance "
            "(live / derived / demo_fallback / empty) — fallback data is never "
            "presented as live, and no disaster is invented from empty inputs."
        ),
        "hazards": hazards_block,
        "affected_habitations": affected_block,
        "demand_capacity": demand_capacity_block,
        "safe_zones": safe_zone_block,
        "recommendation": recommendation_block,
        "alternatives": alternatives_block,
        "evacuation_status": evacuation_status,
        "provenance": _provenance(
            "live" if overall_status == "LIVE" else
            ("derived" if overall_status == "DERIVED" else "demo_fallback"),
            district_id, generated_at),
    }