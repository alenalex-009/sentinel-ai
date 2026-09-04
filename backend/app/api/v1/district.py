"""District overview API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.db_service import get_district_overview

router = APIRouter()


@router.get("/{district_id}/overview")
async def district_overview(
    district_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get 30-second situational overview for a district."""
    return await get_district_overview(db, district_id)


@router.get("/")
async def list_districts():
    """List available districts."""
    return {
        "districts": [
            {"id": "idukki", "name": "Idukki", "state": "Kerala", "pilot": True}
        ]
    }
