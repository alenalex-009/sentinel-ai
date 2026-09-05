"""Spatial analysis API endpoints (Phase 3 + Phase 5B)."""

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.core.config import settings
from app.services import spatial_service, screening

router = APIRouter()


@router.get("/distance/{habitation_id}/{site_id}")
async def spatial_distance(
    habitation_id: str,
    site_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Geodesic straight-line distance (metres) habitation → candidate site.

    Deterministic PostGIS ST_Distance(geography) result. Unknown ids → 404.
    """
    result = await spatial_service.get_spatial_distance(db, habitation_id, site_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown habitation or candidate site: {habitation_id} / {site_id}",
        )
    return result


@router.get("/proximity/{habitation_id}")
async def spatial_proximity(
    habitation_id: str,
    radius_m: float = Query(settings.SITE_PROXIMITY_RADIUS_M, ge=100, le=100000),
    db: AsyncSession = Depends(get_db),
):
    """Candidate sites within a deterministic radius of a habitation."""
    result = await spatial_service.get_proximate_sites(db, habitation_id, radius_m)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown habitation: {habitation_id}",
        )
    return result


@router.get("/zones")
async def screening_zones(
    district_id: str = Query("idukki"),
    db: AsyncSession = Depends(get_db),
):
    """DERIVED screening ranges (green/yellow/red) around candidate sites.

    PostGIS ST_Buffer on real site geometry. Zones are derived screening
    ranges — never official hazard boundaries or government approvals.
    """
    return await screening.get_screening_zones(db, district_id)


@router.get("/history/{region}")
async def historical_periods(region: str):
    """Historical data availability for a routing region (honest registry)."""
    result = screening.get_historical_periods(region.lower())
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown region: {region}. Supported: kerala, vizag, assam",
        )
    return result
