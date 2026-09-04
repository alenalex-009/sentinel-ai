"""Relocation intelligence API endpoints."""

from fastapi import APIRouter, Query
from app.services.demo_data import (
    get_candidate_sites,
    get_capacity_assessment,
    get_relocation_demand,
    get_optimization_result,
)

router = APIRouter()


@router.get("/demand/{habitation_id}")
async def relocation_demand(habitation_id: str):
    return get_relocation_demand(habitation_id)


@router.get("/candidates")
async def candidate_sites(habitation_id: str = Query("munnar-central")):
    return get_candidate_sites(habitation_id)


@router.get("/capacity/{site_id}")
async def site_capacity(site_id: str):
    return get_capacity_assessment(site_id)


@router.get("/optimization/{habitation_id}")
async def optimization_result(habitation_id: str):
    return get_optimization_result(habitation_id)
