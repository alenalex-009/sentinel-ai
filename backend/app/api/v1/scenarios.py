"""Scenario analysis API endpoints.

All results are explicitly labelled SIMULATED.
Never presented as live forecasts or authoritative data.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from math import floor
from typing import Optional
from app.services.optimizer import run_optimization, build_sites_from_demo
from app.services import demo_data

router = APIRouter()


class ScenarioRequest(BaseModel):
    habitation_id: str = "munnar-central"
    label: str = "Custom"
    rainfall_multiplier: float = Field(default=1.0, ge=0.1, le=5.0)
    population_change_pct: float = Field(default=0.0, ge=-50.0, le=200.0)
    capacity_reduction_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    road_disruption: bool = False


@router.post("/run")
async def run_scenario(request: ScenarioRequest):
    """Run a what-if scenario. All results are SIMULATED."""
    base_risk = 94
    base_demand = 4210
    total_capacity = 7100  # sum of all site c_safe values

    # Simulated risk: rainfall multiplier drives hazard component
    hazard_component = 35.2  # 0.40 x 88 base hazard susceptibility — matches demo seed
    hazard_delta = (request.rainfall_multiplier - 1.0) * hazard_component * 1.4
    simulated_risk = min(100, max(0, round(base_risk + hazard_delta)))

    # Simulated demand (explicit half-up rounding == frontend Math.round)
    simulated_demand = int(floor(base_demand * (1 + request.population_change_pct / 100) + 0.5))

    # Simulated capacity
    effective_capacity = round(total_capacity * (1 - request.capacity_reduction_pct / 100))
    if request.road_disruption:
        # Site B (2100 capacity) becomes inaccessible
        effective_capacity = max(0, effective_capacity - 2100)

    simulated_gap = simulated_demand - effective_capacity

    simulated_priority = (
        "IMMEDIATE" if simulated_risk >= 75
        else "SHORT-TERM" if simulated_risk >= 50
        else "MEDIUM-TERM"
    )

    # Run optimizer under scenario constraints
    sites = build_sites_from_demo()
    if request.road_disruption:
        sites = [s for s in sites if s.id != "site-b"]
    if request.capacity_reduction_pct > 0:
        factor = 1 - request.capacity_reduction_pct / 100
        for s in sites:
            s.c_safe = max(0, int(s.c_safe * factor))

    opt_result = run_optimization(
        demand=simulated_demand,
        sites=sites,
        data_status="SIMULATION",
    )

    impact_parts = []
    if request.rainfall_multiplier != 1.0:
        impact_parts.append(f"Rainfall ×{request.rainfall_multiplier} → Risk {simulated_risk}/100")
    if request.population_change_pct != 0:
        impact_parts.append(f"Population {'+' if request.population_change_pct > 0 else ''}{request.population_change_pct}% → Demand {simulated_demand:,}")
    if request.capacity_reduction_pct != 0:
        impact_parts.append(f"Capacity −{request.capacity_reduction_pct}% → Available {effective_capacity:,}")
    if request.road_disruption:
        impact_parts.append("Road disruption → Site B inaccessible")
    if simulated_gap > 0:
        impact_parts.append(f"Capacity gap: {simulated_gap:,} persons unallocated")

    return {
        "data_status": "SIMULATION",
        "data_type": "SIMULATED",
        "warning": "SIMULATED — Not live data. For planning and demonstration purposes only.",
        "params": request.dict(),
        "simulated_risk": simulated_risk,
        "simulated_priority": simulated_priority,
        "simulated_demand": simulated_demand,
        "simulated_capacity_available": effective_capacity,
        "simulated_gap": simulated_gap,
        "impact_summary": " · ".join(impact_parts) or "No change from baseline",
        "optimization": {
            "status": opt_result.status,
            "total_allocated": opt_result.total_allocated,
            "unallocated": opt_result.unallocated,
            "allocations": [
                {
                    "site_id": a.site_id,
                    "site_name": a.site_name,
                    "allocated_population": a.allocated_population,
                    "distance_km": a.distance_km,
                    "utilization_pct": a.utilization_pct,
                }
                for a in opt_result.allocations
            ],
            "solver_note": opt_result.solver_note,
            "data_type": "SIMULATED",
        },
    }
