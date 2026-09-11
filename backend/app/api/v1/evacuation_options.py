"""Automatic evacuation option endpoints (map-driven relocation workflow).

GET /api/v1/routing/options — evaluates every live safe-zone candidate for an
affected habitation, ranks the routes (hazard-aware risk, capacity fit, ETA)
and returns recommended_route + alternative_routes[] + rejected_options[]
with honest provenance. Read-only; never fabricates a route.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import evacuation_options

router = APIRouter()


@router.get("/options")
async def evacuation_options_ep(
    district_id: str = Query("idukki"),
    habitation_id: Optional[str] = Query(None, description="origin habitation; default = highest-demand affected"),
    policy: str = Query("ROUTE_STANDARD", description="ROUTE_STANDARD | ROUTE_ADVANCED"),
    region: Optional[str] = Query(None, description="override routing region (default from district)"),
    db: AsyncSession = Depends(get_db),
):
    """Automatically evaluate all safe zones for an origin and rank them.

    The recommended route is chosen without manual site selection: policy
    engines (OSRM→Valhalla) produce real road routes, every route is scored
    against active hazards, and capacity fit is checked. Engines that did
    not answer leave honest UNAVAILABLE options — no fake geometry.
    """
    return await evacuation_options.build_evacuation_options(
        db, district_id=district_id, habitation_id=habitation_id,
        policy=policy, region=region,
    )
