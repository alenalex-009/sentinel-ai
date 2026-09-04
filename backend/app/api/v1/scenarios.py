"""Scenario analysis API endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ScenarioRequest(BaseModel):
    habitation_id: str
    rainfall_multiplier: Optional[float] = 1.0
    population_change_pct: Optional[float] = 0.0
    capacity_reduction_pct: Optional[float] = 0.0
    road_disruption: Optional[bool] = False


@router.post("/run")
async def run_scenario(request: ScenarioRequest):
    """Run a what-if scenario. Results are always labelled SIMULATED."""
    from app.services.demo_data import run_scenario_simulation
    return run_scenario_simulation(request.dict())
