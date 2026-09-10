"""Data source status API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db, check_db_health
from app.services.data_status import (
    get_all_source_statuses, check_bhuvan_wms, SourceAvailability,
)
from app.core.config import settings
from app.services import routing_service

router = APIRouter()


async def _ingested_rows(db: AsyncSession, table: str) -> int:
    """Count rows in an ingestion table, or -1 when the DB is unreachable."""
    try:
        result = await db.execute(text(f"SELECT count(*) FROM {table}"))
        return result.scalar_one()
    except Exception:
        return -1


async def _live_inject(db: AsyncSession, sources: list[dict]) -> None:
    """Overlay runtime availability for real-data providers (weatherapi, usgs)."""
    now = datetime.now(timezone.utc)

    weather_rows = await _ingested_rows(db, "weather_observations")
    for s in sources:
        if s["id"] != "weatherapi":
            continue
        if weather_rows > 0:
            s["availability"] = SourceAvailability.LIVE.value
            s["last_checked"] = now.isoformat()
            s["last_successful"] = now.isoformat()
            s["ingested_rows"] = weather_rows
        elif weather_rows == -1:
            s["availability"] = SourceAvailability.UNAVAILABLE.value
            s["last_checked"] = now.isoformat()
            s["error_message"] = "database unreachable — cannot confirm ingestion"
        else:
            s["availability"] = SourceAvailability.UNAVAILABLE.value
            s["last_checked"] = now.isoformat()
            s["error_message"] = "no weather_observations rows yet — run scripts/ingest_weather.py"

    eq_rows = await _ingested_rows(db, "earthquake_events")
    for s in sources:
        if s["id"] != "usgs-earthquakes":
            continue
        if not settings.EARTHQUAKE_CSV_PATH:
            s["availability"] = SourceAvailability.UNAVAILABLE.value
            s["error_message"] = "EARTHQUAKE_CSV_PATH not configured (server-side)"
        elif eq_rows > 0:
            s["availability"] = SourceAvailability.LIVE.value
            s["last_checked"] = now.isoformat()
            s["last_successful"] = now.isoformat()
            s["ingested_rows"] = eq_rows
        elif eq_rows == -1:
            s["availability"] = SourceAvailability.UNAVAILABLE.value
            s["last_checked"] = now.isoformat()
            s["error_message"] = "database unreachable — cannot confirm ingestion"
        else:
            s["availability"] = SourceAvailability.UNAVAILABLE.value
            s["last_checked"] = now.isoformat()
            s["error_message"] = "earthquake_events empty — run scripts/ingest_earthquakes.py"


@router.get("")
async def list_data_sources(
    db: AsyncSession = Depends(get_db),
):
    """List all data sources with availability and provenance.

    Availability is the demo-mode baseline; Bhuvan WMS, GraphHopper and the
    real-data ingestion tables (weatherapi, USGS earthquakes) are probed at
    request time (real network checks + DB row counts) and their
    last_checked/last_successful timestamps are genuine. A LIVE flag means the
    provider answered / rows exist at check time — not that live data is
    ingested for every listed source.
    """
    sources = get_all_source_statuses()
    now = datetime.now(timezone.utc)

    bhuvan_status = await check_bhuvan_wms()
    for s in sources:
        if s["id"] == "bhuvan-flood":
            s["availability"] = bhuvan_status.value
            s["last_checked"] = now.isoformat()
            if bhuvan_status == SourceAvailability.LIVE:
                s["last_successful"] = now.isoformat()

    gh_regions = await routing_service.graphhopper_health_regions()
    gh_ok = bool(gh_regions) and all(v["ok"] for v in gh_regions.values())
    gh_detail = (
        "; ".join(f"{k}={v['ok']}" for k, v in gh_regions.items())
        if gh_regions else "no regions configured"
    )
    for s in sources:
        if s["id"] == "graphhopper-routing":
            s["availability"] = SourceAvailability.LIVE.value if gh_ok else SourceAvailability.UNAVAILABLE.value
            s["last_checked"] = now.isoformat()
            if gh_ok:
                s["last_successful"] = now.isoformat()
            s["error_message"] = None if gh_ok else gh_detail
            s["region_services"] = [
                {
                    "region": k,
                    "reachable": v["ok"],
                    "detail": v["detail"],
                    "url": v["url"],
                }
                for k, v in gh_regions.items()
            ]

    await _live_inject(db, sources)

    return {
        "data_status": "DEMO" if settings.DEMO_MODE else "LIVE",
        "demo_mode": settings.DEMO_MODE,
        "note": (
            "Reachability is probed for Bhuvan WMS (tile request), GraphHopper "
            "(/info), WeatherAPI.com and the USGS earthquake catalog (DB row "
            "counts); a LIVE flag means the service answered / data is ingested "
            "at check time. Other sources are DEMO (no live integration in this "
            "build)."
        ),
        "sources": sources,
    }


@router.get("/health")
async def system_health(
    db: AsyncSession = Depends(get_db),
):
    """System health: database + external sources."""
    db_health = await check_db_health()
    bhuvan_status = await check_bhuvan_wms()
    gh_regions = await routing_service.graphhopper_health_regions()
    gh_ok = bool(gh_regions) and all(v["ok"] for v in gh_regions.values())

    weather_note = None
    eq_note = None
    if db_health["status"] == "ok":
        weather_rows = await _ingested_rows(db, "weather_observations")
        eq_rows = await _ingested_rows(db, "earthquake_events")
        weather_note = f"{weather_rows} observations" if weather_rows >= 0 else "db probe failed"
        eq_note = f"{eq_rows} events" if eq_rows >= 0 else "db probe failed"

    return {
        "database": db_health,
        "bhuvan_wms": bhuvan_status,
        "graphhopper": {
            "ok": gh_ok,
            "regions": {
                k: {"ok": v["ok"], "detail": v["detail"]}
                for k, v in gh_regions.items()
            },
        },
        "live_data": {
            "weatherapi": weather_note,
            "usgs_earthquakes": eq_note,
        },
        "demo_mode": settings.DEMO_MODE,
        "note": "External source checks are non-blocking. Demo fallback always available.",
    }
