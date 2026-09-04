"""Data source status API endpoints."""

from fastapi import APIRouter
from app.services.data_status import get_all_source_statuses, check_bhuvan_wms
from app.db.database import check_db_health

router = APIRouter()


@router.get("/")
async def list_data_sources():
    """List all data sources with availability and provenance."""
    return {
        "data_status": "DEMO",
        "sources": get_all_source_statuses(),
    }


@router.get("/health")
async def system_health():
    """System health: database + external sources."""
    db_health = await check_db_health()
    bhuvan_status = await check_bhuvan_wms()
    return {
        "database": db_health,
        "bhuvan_wms": bhuvan_status,
        "demo_mode": True,
        "note": "External source checks are non-blocking. Demo fallback always available.",
    }
