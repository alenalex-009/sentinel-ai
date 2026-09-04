"""Validation endpoint — exposes model audit trail for transparency."""

from fastapi import APIRouter
from app.services.risk_validation import (
    validate_munnar_central,
    validate_site_a_capacity,
    validate_suitability_site_a,
)

router = APIRouter()


@router.get("/risk/munnar-central")
async def validate_risk():
    """Audit trail: risk model computation for Munnar Central."""
    return validate_munnar_central()


@router.get("/capacity/site-a")
async def validate_capacity():
    """Audit trail: C_safe computation for Site A."""
    return validate_site_a_capacity()


@router.get("/suitability/site-a")
async def validate_suitability():
    """Audit trail: suitability score computation for Site A."""
    return validate_suitability_site_a()


@router.get("/all")
async def validate_all():
    """Run all model validations and return audit report."""
    return {
        "data_status": "DEMO",
        "note": "Model validation audit. All weights are configurable baselines — not official government formulas.",
        "risk": validate_munnar_central(),
        "capacity": validate_site_a_capacity(),
        "suitability": validate_suitability_site_a(),
    }
