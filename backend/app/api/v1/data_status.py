"""Data source status API endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter
from app.services.data_status import (
    get_all_source_statuses, check_bhuvan_wms, SourceAvailability,
)
from app.db.database import check_db_health
from app.core.config import settings
from app.services import routing_service

router = APIRouter()


@router.get("/")
async def list_data_sources():
    """List all data sources with availability and provenance.

    Availability is the demo-mode baseline; the Bhuvan WMS and GraphHopper
    entries are probed at request time (real network checks) and their
    last_checked/last_successful timestamps are genuine timestamps of those
    probes. A LIVE flag means the service answered at check time — not that
    live data is ingested. All other sources are static DEMO because no live
    integration exists for them in this build.
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

    return {
        "data_status": "DEMO" if settings.DEMO_MODE else "LIVE",
        "demo_mode": settings.DEMO_MODE,
        "note": (
            "Reachability is probed for Bhuvan WMS (tile request) and GraphHopper "
            "(/info) only; a LIVE flag means the service answered at check time, "
            "not that live data is ingested. Other sources are DEMO (no live "
            "integration in this build)."
        ),
        "sources": sources,
    }


@router.get("/health")
async def system_health():
    """System health: database + external sources."""
    db_health = await check_db_health()
    bhuvan_status = await check_bhuvan_wms()
    gh_regions = await routing_service.graphhopper_health_regions()
    gh_ok = bool(gh_regions) and all(v["ok"] for v in gh_regions.values())
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
        "demo_mode": settings.DEMO_MODE,
        "note": "External source checks are non-blocking. Demo fallback always available.",
    }
