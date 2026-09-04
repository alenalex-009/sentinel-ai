"""Relocation intelligence API endpoints."""

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services import demo_data
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


@router.get("/capacity/{site_id}")
async def site_capacity(
    site_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Carrying capacity assessment for a candidate site."""
    return await get_capacity_assessment(db, site_id)


@router.get("/optimization/{habitation_id}")
async def optimization_result(habitation_id: str):
    """Run OR-Tools CP-SAT optimization for multi-site allocation."""
    demand_data = demo_data.get_relocation_demand(habitation_id)
    demand = demand_data["relocation_demand"]
    sites = build_sites_from_demo()
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
    }
