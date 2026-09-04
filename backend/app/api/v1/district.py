"""District overview API endpoints."""

from fastapi import APIRouter
from app.services.demo_data import get_district_overview

router = APIRouter()


@router.get("/{district_id}/overview")
async def district_overview(district_id: str):
    """Get 30-second situational overview for a district."""
    return get_district_overview(district_id)


@router.get("/")
async def list_districts():
    """List available districts."""
    return {
        "districts": [
            {
                "id": "idukki",
                "name": "Idukki",
                "state": "Kerala",
                "pilot": True,
            }
        ]
    }
