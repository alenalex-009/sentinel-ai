"""Habitation API endpoints."""

from fastapi import APIRouter, Query
from typing import Optional
from app.services.demo_data import get_habitation_list, get_habitation_detail

router = APIRouter()


@router.get("/")
async def list_habitations(
    district_id: str = Query("idukki"),
    search: Optional[str] = Query(None),
):
    """List habitations with risk summary."""
    return get_habitation_list(district_id, search)


@router.get("/{habitation_id}")
async def habitation_detail(habitation_id: str):
    """Get full habitation investigation data."""
    return get_habitation_detail(habitation_id)


@router.get("/geojson/district/{district_id}")
async def habitations_geojson(district_id: str):
    """GeoJSON FeatureCollection of all habitations in a district."""
    from app.services.demo_data import get_habitations_geojson
    return get_habitations_geojson(district_id)
