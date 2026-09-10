"""Hazard-aware routing + alternatives / isochrones / matrix endpoints (Phase 6).

All post bodies are versioned under /api/v1/routing and return honest
provenance: a requested engine that cannot answer yields status=UNAVAILABLE
with an explicit reason — never a relabelled distance.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import hazard_aware_routing, multi_engine_routing

router = APIRouter()


class PairRoutingRequest(BaseModel):
    habitation_id: str
    site_id: str
    engine: str = Field("graphhopper", description="osrm | graphhopper | valhalla")
    avoid_hazards: bool = True


class AlternativesRequest(PairRoutingRequest):
    max_alternatives: int = Field(3, ge=1, le=5)


class IsochronesRequest(BaseModel):
    region: str = "kerala"
    lat: float
    lon: float
    contours_min: list = Field(
        [10, 20, 30], description="reachable minutes; up to 6 contours"
    )


class MatrixRequest(BaseModel):
    habitation_ids: list
    site_ids: list


@router.post("/hazard-aware")
async def hazard_aware(payload: PairRoutingRequest, db: AsyncSession = Depends(get_db)):
    """Engined route scored against active hazard buffers (+ avoidance)."""
    result = await hazard_aware_routing.hazard_aware_route(
        db, payload.habitation_id, payload.site_id,
        payload.engine, payload.avoid_hazards,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown habitation or candidate site: "
                   f"{payload.habitation_id} / {payload.site_id}",
        )
    return result


@router.post("/alternatives")
async def alternatives(payload: AlternativesRequest, db: AsyncSession = Depends(get_db)):
    """Alternative route candidates from the requested engine (index 0 = primary)."""
    result = await multi_engine_routing.route_alternatives(
        db, payload.habitation_id, payload.site_id,
        payload.engine, payload.max_alternatives,
    )
    if not result.get("routes") and result.get("status") == "UNAVAILABLE" \
            and "Unknown" in (result.get("reason") or ""):
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@router.post("/isochrones")
async def isochrones(payload: IsochronesRequest):
    """Valhalla isochrones (drive-time polygons) around a point."""
    return await multi_engine_routing.valhalla_isochrones(
        payload.region, payload.lat, payload.lon, payload.contours_min
    )


@router.post("/matrix")
async def matrix(payload: MatrixRequest, db: AsyncSession = Depends(get_db)):
    """GraphHopper distance/duration matrix, rows=habit, columns=sites."""
    return await multi_engine_routing.graphhopper_matrix(
        db, payload.habitation_ids, payload.site_ids
    )