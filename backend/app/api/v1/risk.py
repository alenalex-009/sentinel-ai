"""Risk intelligence API endpoints."""

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services import demo_data

router = APIRouter()


@router.get("/intelligence")
async def risk_intelligence(
    district_id: str = Query("idukki"),
    mode: str = Query("current"),
):
    """Risk intelligence panel data for the district."""
    return demo_data.get_risk_intelligence(district_id, mode)


@router.get("/drivers/{habitation_id}")
async def risk_drivers(habitation_id: str):
    """Top risk drivers for a specific habitation."""
    return demo_data.get_risk_drivers(habitation_id)


@router.get("/decision-trace/{habitation_id}")
async def decision_trace(habitation_id: str):
    """Full decision intelligence trace for a habitation."""
    return demo_data.get_decision_trace(habitation_id)


@router.get("/priorities")
async def risk_priorities(
    district_id: str = Query("idukki"),
):
    """District-wide RPI ranking."""
    habitations = demo_data.get_habitation_list(district_id)["habitations"]
    # Canonical RPI scores live in demo_data (single source shared with the
    # detail endpoint). Rajakkad = 78 (>=75) so its IMMEDIATE priority matches
    # the engine classification threshold.
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
        "note": "RPI = 0.35×Risk + 0.20×Vulnerability + 0.15×Population + 0.15×Historical + 0.15×Urgency. Configurable baseline weights.",
        "habitations": ranked,
    }
