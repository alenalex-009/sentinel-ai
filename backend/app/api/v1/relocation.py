"""Relocation intelligence API endpoints."""

from fastapi import APIRouter, Query
from app.services.demo_data import get_candidate_sites, get_capacity_assessment

router = APIRouter()


@router.get("/candidates")
async def candidate_sites(
    habitation_id: str = Query("munnar-central"),
):
    """Technically screened candidate relocation sites."""
    return get_candidate_sites(habitation_id)


@router.get("/capacity/{site_id}")
async def site_capacity(site_id: str):
    """Carrying capacity assessment for a candidate site."""
    return get_capacity_assessment(site_id)
