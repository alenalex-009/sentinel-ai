"""Habitation API endpoints."""

from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.db_service import get_habitation_list, get_habitation_detail
from app.services import spatial_service

router = APIRouter()


@router.get("/")
async def list_habitations(
    district_id: str = Query("idukki"),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List habitations with risk summary."""
    return await get_habitation_list(db, district_id, search)


@router.get("/geojson/district/{district_id}")
async def habitations_geojson(
    district_id: str,
    db: AsyncSession = Depends(get_db),
):
    """GeoJSON FeatureCollection of habitation points, sourced from PostGIS.

    Falls back to demo coordinates only when the database is unavailable.
    """
    return await spatial_service.get_habitation_geojson(db, district_id)


@router.get("/{habitation_id}")
async def habitation_detail(
    habitation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full habitation investigation data."""
    result = await get_habitation_detail(db, habitation_id)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
