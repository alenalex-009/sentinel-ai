"""Evacuation overview API endpoints (Phase 7, Task B2)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import evacuation_service

router = APIRouter()


@router.get("/overview")
async def evacuation_overview(
    region: str = Query("idukki", description="district id"),
    disaster_type: Optional[str] = Query(None, description="force a disaster type"),
    db: AsyncSession = Depends(get_db),
):
    """Read-only synthesis overview for evacuation decision support.

    Aggregates live hazards, relocation demand, safe-zone capacity and the
    policy-chosen engine route. Always 200: unavailable blocks are reported
    honestly, never fabricated.
    """
    return await evacuation_service.build_overview(db, region, disaster_type=disaster_type)