"""Risk intelligence API endpoints."""

from fastapi import APIRouter, Query
from app.services.risk_engine import compute_risk
from app.services.demo_data import get_risk_intelligence

router = APIRouter()


@router.get("/intelligence")
async def risk_intelligence(
    district_id: str = Query("idukki"),
    mode: str = Query("current"),  # current | baseline | change
):
    """Risk intelligence panel data for the district."""
    return get_risk_intelligence(district_id, mode)


@router.get("/drivers/{habitation_id}")
async def risk_drivers(habitation_id: str):
    """Top risk drivers for a specific habitation."""
    from app.services.demo_data import get_risk_drivers
    return get_risk_drivers(habitation_id)


@router.get("/decision-trace/{habitation_id}")
async def decision_trace(habitation_id: str):
    """Full decision intelligence trace for a habitation."""
    from app.services.demo_data import get_decision_trace
    return get_decision_trace(habitation_id)
