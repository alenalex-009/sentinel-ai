"""Road routing API endpoints (Phase 4/5C — OSRM / GraphHopper / Valhalla over OpenStreetMap)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services import routing_service
from app.services import multi_engine_routing
from app.services.routing_service import region_base_url

router = APIRouter()


@router.get("/engines")
async def routing_engines(region: str = Query("kerala")):
    """Per-engine availability for the routing selector (OSRM/GraphHopper/Valhalla)."""
    return await multi_engine_routing.engines_status(region)


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
    engine: str = Query("graphhopper", description="osrm | graphhopper | valhalla"),
    db: AsyncSession = Depends(get_db),
):
    """Road distance + travel time via the requested engine.

    Unknown ids → 404. Requested engine unavailable → status UNAVAILABLE with
    route=null and an explicit reason (never a relabelled straight-line
    distance, and never a silent other-engine result).
    """
    result = await multi_engine_routing.route_with_engine(db, habitation_id, site_id, engine)
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
