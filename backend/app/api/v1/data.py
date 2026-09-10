"""Real-data endpoints for weather and earthquake ingestion.

These endpoints read OBSERVED rows that the ingestion pollers wrote to
PostGIS. They never fabricate readings. An empty/unreachable database returns
an explicit EMPTY/UNAVAILABLE payload with the reason.

Live fetch (on-demand provider polling) is intentionally NOT performed inside
GET handlers — ingestion is a separate poller (CLI/cron) so the API layer stays
watch-only. The DataSources page can trigger a manual poll through a separate
action endpoint if needed.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import data_read
from app.services.data_status import SourceAvailability

router = APIRouter()


def _require_ok(payload: dict):
    """Raise 503 only for hard failures; EMPTY is a legitimate empty dataset."""
    if payload.get("data_status") == SourceAvailability.UNAVAILABLE.value:
        raise HTTPException(status_code=503, detail=payload.get("reason", "unavailable"))


@router.get("/weather")
async def recent_weather(
    region: Optional[str] = Query(None, pattern="^(kerala|vizag|assam)$"),
    hours: int = Query(72, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
):
    """Most recent weather observations per station (last `hours`)."""
    payload = await data_read.get_recent_weather(db, region=region, hours=hours)
    return payload


@router.get("/weather/forecast")
async def weather_forecast(
    region: Optional[str] = Query(None, pattern="^(kerala|vizag|assam)$"),
    db: AsyncSession = Depends(get_db),
):
    """Ingested 3-day forecast per station."""
    payload = await data_read.get_forecast(db, region=region)
    return payload


@router.get("/earthquakes")
async def earthquakes(
    region: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    magnitude_min: Optional[float] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Earthquakes from the ingested USGS catalog (historical context only)."""
    payload = await data_read.get_earthquakes(
        db, region=region, since=since, magnitude_min=magnitude_min, limit=limit
    )
    _require_ok(payload)
    return payload


@router.get("/earthquakes/coverage")
async def earthquake_coverage(db: AsyncSession = Depends(get_db)):
    """Coverage facts for the ingested USGS catalog."""
    payload = await data_read.get_earthquake_coverage(db)
    _require_ok(payload)
    return payload