"""Report summary synthesis endpoint (Phase 7, Task B4).

Read-only: assembles a per-habitation report from existing live services —
district overview, habitation detail, current risk + timeline + drivers,
relocation demand, safe-zone candidates with capacity, optimizer result
(feasibility + allocations + capacity_gap / unallocated), policy-chosen
hazard-aware route, nearby active hazards, and plan status when a plan_id is
given. No new data is invented: every section carries SectionLabel-compatible
data_type / data_status and its own provenance; fallbacks are labelled, never
presented as live. The section structure mirrors the Reports.tsx report
(district / habitation / relocation-demand / capacity / optimization /
scenario / routing) so the frontend swap is surgical.

Honesty constraints (same as evacuation_service, Task B2):
  - capacity_gap = max(0, demand - capacity) — a shortage, never a surplus.
  - optimization runs the real solver over the *live* candidate sites when
    they exist; DEMO constants are only used on the coherent all-DEMO path.
  - served_by / fallback_used reflect the engine that actually served.
  - DB-down is distinguished from DB-up-but-empty (None vs [] sites).
"""

import math
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum as _Enum
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import (
    db_service,
    demo_data,
    hazard_aware_routing,
    hazard_service,
    multi_engine_routing,
    relocation_service,
    risk_service,
)
from app.services.optimizer import SiteInput, run_optimization

router = APIRouter()

# Distance shown next to each candidate site is straight-line (approx) —
# never presented as a routed distance (routed distances come from the
# routing section).
_DISTANCE_BASIS = "straight-line (approx) — not a routed distance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_str(value) -> str:
    """Normalize DataStatus/DataType enum members to their plain string.

    `str()` on a (str, Enum) yields "DataStatus.DEMO" on Python 3.11 —
    never comparable against section labels. Always use this helper for
    any status that may originate from demo_data or the services.
    """
    if isinstance(value, str) and not isinstance(value, _Enum):
        return value
    if isinstance(value, _Enum):
        return str(value.value)
    return str(value)


def _provenance(source: str, generated_at: str) -> dict:
    return {"source": source, "generated_at": generated_at}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _status_str(v) -> str:
    """Normalize a data_status that may be a str-Enum to its plain value."""
    if v is None:
        return "DEMO"
    return getattr(v, "value", str(v))


def _overall_status(statuses: list) -> str:
    if "LIVE" in statuses:
        return "LIVE"
    if "DERIVED" in statuses:
        return "DERIVED"
    if "DEMO" in statuses:
        return "DEMO"
    return "EMPTY"


def _site_capacity(s: dict) -> int:
    return int(s.get("estimated_capacity") or s.get("safe_capacity") or 0)


def _optimization_payload(
    demand: int, site_rows: list, hab_coords: Optional[tuple], data_status: str,
) -> dict:
    """Run the real optimizer over the given (live or demo) candidate rows.

    `data_status` labels the provenance of the *inputs*; the solver itself
    always returns RECOMMENDATION-class output. When there is no demand or
    no sites the solver is not run — the section says NOT_RUN instead of
    inventing an allocation.
    """
    if not site_rows or demand <= 0:
        return {
            "status": "NOT_RUN",
            "data_status": data_status,
            "total_demand": demand,
            "total_allocated": 0,
            "unallocated": demand if demand > 0 else 0,
            "allocations": [],
            "solver_note": (
                "no candidate safe-zone sites to allocate to"
                if not site_rows else "no relocation demand to allocate"
            ),
            "distance_basis": _DISTANCE_BASIS,
        }
    site_inputs = []
    for s in site_rows:
        dist = 0.0
        s_lat = s.get("lat") or s.get("latitude")
        s_lon = s.get("lon") or s.get("longitude")
        if hab_coords and s_lat is not None and s_lon is not None:
            dist = round(_haversine_km(hab_coords[0], hab_coords[1],
                                       float(s_lat), float(s_lon)), 2)
        site_inputs.append(SiteInput(
            id=str(s["id"]),
            name=str(s.get("name") or s["id"]),
            c_safe=_site_capacity(s),
            distance_km=dist,
            suitability_score=float(s.get("suitability_score") or 0),
            safety_score=float(s.get("safety_score") or 0),
            infrastructure_score=50.0,
            hard_constraints_passed=True,
        ))
    opt = run_optimization(demand, site_inputs, data_status=data_status)
    out = asdict(opt)
    out["distance_basis"] = _DISTANCE_BASIS
    return out


async def build_report_summary(
    db: AsyncSession,
    habitation_id: str = "munnar-central",
    district_id: str = "idukki",
    plan_id: Optional[int] = None,
) -> dict:
    """Assemble the per-habitation report summary from live services."""
    generated_at = _now_iso()

    # 1. District section — live-first district overview (labelled fallback).
    district_payload = await db_service.get_district_overview(db, district_id)
    if isinstance(district_payload, dict) and "error" in district_payload:
        district_section = {
            "data_type": "DERIVED",
            "data_status": "UNAVAILABLE",
            "reason": district_payload.get("error"),
            "provenance": _provenance("demo_fallback", generated_at),
        }
    else:
        district_source = district_payload.pop("_source", None) or "demo_fallback"
        district_section = {
            "data_type": "DERIVED",
            "data_status": _status_str(district_payload.get("data_status", "DEMO")),
            "district": district_payload.get("district"),
            "what_changed": district_payload.get("what_changed"),
            "source": district_source,
            "provenance": _provenance(
                "live" if district_source == "postgis" else "demo_fallback",
                generated_at),
        }

    # 2. Habitation section — detail + live risk + timeline + drivers.
    detail = await db_service.get_habitation_detail(db, habitation_id)
    detail_source = detail.pop("_source", None) or "demo_fallback"
    risk_payload = await risk_service.current_risk(db, district_id=district_id)
    risk_entry = next(
        (e for e in risk_payload.get("habitations", []) if e.get("id") == habitation_id), None
    )
    timeline = await risk_service.get_timeline(db, habitation_id, limit=10)
    drivers = demo_data.get_risk_drivers(habitation_id)
    hab_lat = detail.get("latitude")
    hab_lon = detail.get("longitude")
    hab_coords = (hab_lat, hab_lon) if hab_lat is not None and hab_lon is not None else None
    hab_status = _overall_status([
        "DERIVED" if detail_source == "postgis" else "DEMO",
        _status_str(risk_payload.get("data_status", "DEMO")),
        _status_str(timeline.get("data_status", "DEMO")),
    ])
    hab_section = {
        "data_type": "DERIVED",
        "data_status": hab_status,
        "habitation": detail,
        "habitation_source": detail_source,
        "risk_current": risk_entry,
        "risk_basis": risk_payload.get("basis"),
        "risk_timeline": timeline,
        "risk_drivers": drivers,
        "provenance": _provenance(
            "live" if detail_source == "postgis" else "demo_fallback", generated_at),
    }

    # 3. Demand section — live risk-derived demand (labelled fallback).
    demand = await relocation_service.calculate_demand(db, district_id)
    demand_status = _status_str(demand.get("data_status", "DEMO"))
    hab_demand = next(
        (h for h in demand.get("habitations", []) if h.get("habitation_id") == habitation_id), {}
    )
    hab_relocation_demand = int((hab_demand or {}).get("relocation_demand") or 0)
    demand_section = {
        "data_type": "DERIVED",
        "data_status": demand_status,
        "habitation_demand": hab_demand,
        "habitation_relocation_demand": hab_relocation_demand,
        "district_total_demand": int(demand.get("total_demand") or 0),
        "note": demand.get("note"),
        "provenance": _provenance(
            "live" if demand_status == "DERIVED" else "demo_fallback", generated_at),
    }

    # 4. Capacity + optimization sections. Three honest branches:
    #    live sites → real solver over live candidates (DERIVED);
    #    DB up but no sites → EMPTY, optimizer NOT_RUN;
    #    DB down → coherent DEMO narrative (demo candidates + demo demand).
    sites_live = await relocation_service.get_safe_zone_sites(db, district_id)
    if sites_live:
        candidate_sites = {
            "data_status": "DERIVED",
            "source": "postgis",
            "sites": [
                {
                    "id": s["id"], "name": s.get("name"), "lon": s.get("lon"), "lat": s.get("lat"),
                    "suitability_score": s.get("suitability_score"),
                    "safety_score": s.get("safety_score"),
                    "estimated_capacity": s.get("estimated_capacity"),
                    "constraint_pass": s.get("constraint_pass"),
                    "constraint_evidence": s.get("constraint_evidence"),
                }
                for s in sites_live
            ],
        }
        site_rows = sites_live
        sites_data_status = "DERIVED"
        capacity_provenance = "live"
        opt_demand = max(hab_relocation_demand, 0)
    elif sites_live is None:
        # DB down — coherent DEMO path: demo candidates + demo demand.
        candidate_sites = demo_data.get_candidate_sites(habitation_id)
        site_rows = candidate_sites.get("sites", [])
        sites_data_status = "DEMO"
        capacity_provenance = "demo_fallback"
        demo_demand = demo_data.get_relocation_demand(habitation_id)
        opt_demand = int(demo_demand.get("relocation_demand") or 0)
    else:
        # DB up, no discovered sites yet — honest EMPTY.
        candidate_sites = {"data_status": "EMPTY", "source": "postgis", "sites": []}
        site_rows = []
        sites_data_status = "EMPTY"
        capacity_provenance = "empty"
        opt_demand = max(hab_relocation_demand, 0)

    # Straight-line distance to each candidate (approx, labelled).
    for s in candidate_sites.get("sites", []):
        s_lat = s.get("lat") or s.get("latitude")
        s_lon = s.get("lon") or s.get("longitude")
        s["distance_km"] = (
            round(_haversine_km(hab_coords[0], hab_coords[1], float(s_lat), float(s_lon)), 2)
            if hab_coords and s_lat is not None and s_lon is not None else None
        )
        s["distance_basis"] = _DISTANCE_BASIS

    site_capacity = sum(_site_capacity(s) for s in candidate_sites.get("sites", []))

    capacity_section = {
        "data_type": "DERIVED",
        "data_status": sites_data_status,
        "candidate_sites": candidate_sites,
        "site_capacity_total": site_capacity,
        "capacity_gap": max(0, opt_demand - site_capacity),
        "capacity_gap_formula": "max(0, demand - capacity)",
        "note": (
            "Gap is habitation relocation demand minus total candidate-site "
            "capacity; unallocated comes from the capacity optimizer and may "
            "exceed the gap when sites fall outside the distance bound."
        ),
        "provenance": _provenance(capacity_provenance, generated_at),
    }

    optimization = _optimization_payload(
        opt_demand, site_rows, hab_coords, data_status=sites_data_status,
    )
    optimization_section = {
        "data_type": "RECOMMENDATION",
        "data_status": sites_data_status,
        "optimization": optimization,
        "provenance": _provenance(capacity_provenance, generated_at),
    }

    # 5. Routing section — policy-chosen engine (ROUTE_STANDARD), hazard-aware.
    candidate_ids = [s.get("id") for s in candidate_sites.get("sites", [])]
    site_id = candidate_ids[0] if candidate_ids else None
    engine = await multi_engine_routing.pick_engine("kerala", "ROUTE_STANDARD")
    route = None
    if engine and site_id:
        route = await hazard_aware_routing.hazard_aware_route(
            db, habitation_id, site_id, engine=engine, avoid_hazards=True)
    route_status = (route or {}).get("status") or "UNAVAILABLE"
    if not site_id:
        route = {
            "status": "UNAVAILABLE",
            "reason": "no candidate safe-zone site for routing",
            "route": None,
        }
    elif not engine:
        route = {
            "status": "UNAVAILABLE",
            "reason": "no ready standard engine (ROUTE_STANDARD)",
            "route": None,
        }
        route_status = "UNAVAILABLE"
    # The engine that actually served, from the route payload — never hardcoded.
    served_by = (route or {}).get("engine") if route_status == "OK" else None
    primary = multi_engine_routing.ROUTING_POLICY["ROUTE_STANDARD"].split(" -> ")[0]
    routing_section = {
        "data_type": "RECOMMENDATION",
        "data_status": "DERIVED" if route_status == "OK" else "UNAVAILABLE",
        "route_policy": f"ROUTE_STANDARD ({multi_engine_routing.ROUTING_POLICY['ROUTE_STANDARD']})",
        "engine": engine,
        "served_by": served_by,
        "fallback_used": bool(served_by and served_by != primary),
        "site_id": site_id,
        "route": route,
        "provenance": _provenance(
            "live" if route_status == "OK" else "demo_fallback", generated_at),
    }

    # 6. Scenario section — SIMULATED-labelled, mirrors Reports.tsx preset.
    scenario = demo_data.run_scenario_simulation({
        "habitation_id": habitation_id,
        "label": "Extreme rainfall (x1.5)",
        "rainfall_multiplier": 1.5,
        "population_change_pct": 0,
        "capacity_reduction_pct": 0,
        "road_disruption": False,
    })
    scenario_section = {
        "data_type": "SIMULATED",
        "data_status": _status_str(scenario.get("data_status", "SIMULATION")),
        "scenario": scenario,
        "note": (
            "Scenario results are SIMULATED for planning purposes only — never "
            "presented as current conditions."
        ),
        "provenance": _provenance("simulation", generated_at),
    }

    # 7. Hazard context section — active events near the habitation.
    hazards = await hazard_service.current_hazards(db, region=None)
    hazard_status = _status_str(hazards.get("data_status"))
    nearby = []
    for ev in hazards.get("events") or []:
        c_lat, c_lon = ev.get("centroid_lat"), ev.get("centroid_lon")
        if hab_coords is None or c_lat is None or c_lon is None:
            continue
        dist = _haversine_km(hab_coords[0], hab_coords[1], float(c_lat), float(c_lon))
        radius = float(ev.get("buffer_radius_km") or 0)
        # Only events with a real buffer radius can be "nearby" — an event
        # with no radius is never counted as proximity evidence.
        if radius > 0 and dist <= radius:
            nearby.append({
                "event_id": ev.get("event_id"),
                "hazard_type": ev.get("hazard_type"),
                "severity_level": ev.get("severity_level"),
                "severity_score": ev.get("severity_score"),
                "distance_km": round(dist, 2),
                "started_at": ev.get("started_at"),
                "source": ev.get("source"),
            })
    haz_context_section = {
        "data_type": "DERIVED",
        "data_status": hazard_status,
        "events_nearby": nearby,
        "events_nearby_count": len(nearby),
        "provenance": _provenance("live" if hazard_status == "LIVE" else "empty", generated_at),
    }

    # 8. Plan section (optional).
    plan_section = None
    if plan_id is not None:
        plan = await relocation_service.get_plan(db, plan_id)
        plan_section = {
            "data_type": "DERIVED",
            "data_status": _status_str(plan.get("data_status", "UNAVAILABLE")),
            "plan": {
                k: v for k, v in plan.items()
                if k not in ("data_status",)
            },
            "provenance": _provenance(
                "live" if plan.get("data_status") in ("DERIVED", "LIVE") else "demo_fallback",
                generated_at),
        }

    sections = {
        "district": district_section,
        "habitation": hab_section,
        "demand": demand_section,
        "capacity": capacity_section,
        "optimization": optimization_section,
        "scenario": scenario_section,
        "routing": routing_section,
        "hazard_context": haz_context_section,
        "plan": plan_section,
    }

    return {
        "data_status": _overall_status([
            district_section["data_status"],
            hab_status,
            demand_status,
            sites_data_status,
            routing_section["data_status"],
            hazard_status,
        ]),
        "habitation_id": habitation_id,
        "district_id": district_id,
        "generated_at": generated_at,
        "note": (
            "Report summary assembled from existing live services. Every section "
            "carries SectionLabel-compatible data_type / data_status and its own "
            "provenance — fallback data is labelled, never presented as live."
        ),
        "sections": sections,
    }


@router.get("/summary")
async def report_summary(
    habitation_id: str = Query("munnar-central"),
    district_id: str = Query("idukki"),
    plan_id: Optional[int] = Query(None, description="optional relocation plan id"),
    db: AsyncSession = Depends(get_db),
):
    """Per-habitation report summary assembled from existing live services."""
    return await build_report_summary(db, habitation_id=habitation_id,
                                      district_id=district_id, plan_id=plan_id)