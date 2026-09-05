"""Road routing API endpoints (Phase 4 — GraphHopper + OpenStreetMap)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services import routing_service
from app.services.routing_service import region_base_url

router = APIRouter()


@router.get("/regions")
async def routing_regions():
    """Configured routing regions and their dataset status."""
    from app.core.regions import REGIONS
    return {
        "data_status": "DEMO",
        "note": (
            "Region list is configuration, not coverage. A region is routable only "
            "when its dataset is loaded (dataset_status=development with the query "
            "inside dataset coverage) AND its GraphHopper service answers."
        ),
        "regions": [
            {
                "key": r.key,
                "display": r.display,
                "dataset_status": r.dataset_status,
                "dataset": r.dataset_label,
                "service_configured": region_base_url(r.key) is not None,
            }
            for r in REGIONS.values()
        ],
    }


@router.get("/route/{habitation_id}/{site_id}")
async def road_route(
    habitation_id: str,
    site_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Road distance + travel time (OpenStreetMap + GraphHopper).

    Unknown ids → 404. GraphHopper unavailable → status UNAVAILABLE with
    route=null (never a relabelled straight-line distance).
    """
    result = await routing_service.route_road(db, habitation_id, site_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown habitation or candidate site: {habitation_id} / {site_id}",
        )
    return result


@router.get("/comparison/{habitation_id}")
async def distance_comparison(
    habitation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """DEMO/ESTIMATED vs PostGIS geodesic vs GraphHopper road distance."""
    rows = await routing_service.compare_distances(db, habitation_id)
    if not rows.get("rows"):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown habitation: {habitation_id}",
        )
    return rows
