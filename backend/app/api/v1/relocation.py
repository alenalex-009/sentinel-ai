"""Relocation intelligence API endpoints."""

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services import demo_data, spatial_service, routing_service
from app.services.db_service import get_candidate_sites, get_capacity_assessment
from app.services.optimizer import run_optimization, build_sites_from_demo

router = APIRouter()


@router.get("/demand/{habitation_id}")
async def relocation_demand(habitation_id: str):
    """Relocation demand derived from habitation data."""
    return demo_data.get_relocation_demand(habitation_id)


@router.get("/candidates")
async def candidate_sites(
    habitation_id: str = Query("munnar-central"),
    db: AsyncSession = Depends(get_db),
):
    """Technically screened candidate relocation sites."""
    return await get_candidate_sites(db, habitation_id)


@router.get("/sites/geojson")
async def candidate_sites_geojson(
    district_id: str = Query("idukki"),
    db: AsyncSession = Depends(get_db),
):
    """GeoJSON FeatureCollection of technically screened candidate sites.

    Point geometry only (seed dataset). "Technically Screened Candidate" —
    NOT government-approved land.
    """
    return await spatial_service.get_candidate_sites_geojson(db, district_id)


@router.get("/capacity/{site_id}")
async def site_capacity(
    site_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Carrying capacity assessment for a candidate site."""
    return await get_capacity_assessment(db, site_id)


@router.get("/optimization/{habitation_id}")
async def optimization_result(
    habitation_id: str,
    distance_source: str = Query("demo"),
    db: AsyncSession = Depends(get_db),
):
    """Run OR-Tools CP-SAT optimization for multi-site allocation.

    distance_source selects the distance inputs used by the objective:
      - demo     (default): existing DEMO/ESTIMATED seed distances (golden baseline)
      - geodesic : PostGIS ST_Distance(geography) straight-line distances
      - road     : OpenStreetMap + GraphHopper road-network distances (when available)
    Hard constraints (population ≤ c_safe, safety threshold, ≤15 km) are unchanged.
    When road routing is unavailable the DEMO distance is kept and explicitly
    labelled — never relabelled as a road distance.
    """
    mode = distance_source if distance_source in ("demo", "geodesic", "road") else "demo"
    demand_data = demo_data.get_relocation_demand(habitation_id)
    demand = demand_data["relocation_demand"]
    sites = build_sites_from_demo()

    used_distances = []
    if mode == "geodesic":
        for s in sites:
            d = await spatial_service.get_spatial_distance(db, habitation_id, s.id)
            if d is not None:
                s.distance_km = d["distance_km"]
                used_distances.append({
                    "site_id": s.id, "type": "geodesic", "km": d["distance_km"],
                    "method": d["method"],
                })
            else:
                used_distances.append({
                    "site_id": s.id, "type": "demo", "km": s.distance_km,
                    "note": "Target unavailable in PostGIS — kept DEMO/ESTIMATED distance.",
                })
    elif mode == "road":
        for s in sites:
            r = await routing_service.route_road(db, habitation_id, s.id)
            if r is not None and r["status"] == "OK":
                s.distance_km = r["route"]["distance_km"]
                used_distances.append({
                    "site_id": s.id, "type": "road", "km": s.distance_km,
                    "duration_min": r["route"]["duration_min"],
                    "region": (r.get("region") or {}).get("key"),
                    "method": r["route"]["method"],
                })
            else:
                reason = r["reason"] if r else "target unknown"
                used_distances.append({
                    "site_id": s.id, "type": "demo", "km": s.distance_km,
                    "note": f"GraphHopper unavailable ({reason}) — kept DEMO/ESTIMATED distance. Not relabelled as road.",
                })
    else:
        for s in sites:
            used_distances.append({
                "site_id": s.id, "type": "demo", "km": s.distance_km,
                "method": "DEMO/ESTIMATED seed distance",
            })

    result = run_optimization(demand=demand, sites=sites)
    return {
        "data_status": result.data_status,
        "habitation_id": habitation_id,
        "status": result.status,
        "total_demand": result.total_demand,
        "total_allocated": result.total_allocated,
        "unallocated": result.unallocated,
        "allocations": [
            {
                "site_id": a.site_id,
                "site_name": a.site_name,
                "allocated_population": a.allocated_population,
                "distance_km": a.distance_km,
                "utilization_pct": a.utilization_pct,
                "surplus_after": a.surplus_after,
            }
            for a in result.allocations
        ],
        "objective_value": result.objective_value,
        "constraints_applied": result.constraints_applied,
        "data_type": result.data_type,
        "solver_note": result.solver_note,
        "distance_input": {
            "mode": mode,
            "used": used_distances,
            "note": (
                "Hard constraints (population ≤ c_safe, safety threshold, distance ≤ 15 km) "
                "are unchanged across modes. Distances labelled road come only from "
                "GraphHopper; geodesic from PostGIS; demo is the seed baseline."
            ),
        },
    }
