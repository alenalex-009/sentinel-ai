"""Hazard / disaster intelligence API (Slice 2).

Active hazard events built from LIVE sources only (rainfall exceedance from
live weather; recent alert-magnitude earthquakes). Never fabricated; an empty
current picture returns EMPTY with the source basis, not guessed events.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import hazard_service

router = APIRouter()


@router.get("/current")
async def current_hazards(
    region: Optional[str] = Query(None, description="kerala | vizag | assam"),
    db: AsyncSession = Depends(get_db),
):
    """The current operational hazard picture (active events + GeoJSON overlay)."""
    return await hazard_service.current_hazards(db, region=region)


@router.get("/detail/{event_id}")
async def hazard_detail(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """One hazard event: geometry + exposure intensity on affected habitations."""
    return await hazard_service.get_event_detail(db, event_id)