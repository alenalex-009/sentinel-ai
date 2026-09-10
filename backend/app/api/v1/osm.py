"""OpenStreetMap (Overpass API) vector-layers API (Phase 6).

Serves OSM feature layers — roads, buildings, facilities, water — as
provenance-carrying GeoJSON FeatureCollections. The OSM basemap TILES used by
the frontend are a separate concern (CARTO/OASM raster style) and keep their
own attribution in MapContainer.tsx.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services import osm_service
from app.core.config import settings

router = APIRouter()

CATEGORY_LABELS = {
    "roads": "Road network (highway=*)",
    "buildings": "Buildings (building=*)",
    "facilities": "Facilities (amenity/healthcare/emergency/social/power)",
    "water": "Water features (natural=water / waterway / reservoir)",
}


def _wrap(payload: dict) -> dict:
    """Promote the FeatureCollection to top level, keeping provenance keys.

    Never mutates the payload — the same dict may be held by the in-process
    cache, so popping the feature_collection key here would poison it.
    """
    fc = payload.get("feature_collection", {"type": "FeatureCollection", "features": []})
    out = {**fc, **payload}
    return out


@router.get("/categories")
async def osm_categories():
    """OSM feature categories exposed by Sentinel AI + their query meaning."""
    return {
        "data_status": "DEMO",
        "categories": [
            {"key": k, "label": CATEGORY_LABELS[k]} for k in osm_service._CATEGORIES
        ],
        "endpoint": "/api/v1/osm/{category}?bbox=minLon,minLat,maxLon,maxLat",
        "note": (
            "Bounding box is required and bounded to "
            f"{settings.OSM_MAX_BBOX_DEG2} deg² to stay within public Overpass "
            "slot limits. Results carry data_status LIVE (fresh Overpass) or "
            "CACHED (in-process / PostGIS freshness window)."
        ),
    }


@router.get("/coverage")
async def osm_coverage():
    """Which pilot regions overlap the fetched layers (dataset context)."""
    from app.core.regions import REGIONS
    return {
        "data_status": "DEMO",
        "note": (
            "OSM feature queries are bbox-driven, not region-gated. These are the "
            "known pilot dataset footprints for context only."
        ),
        "regions": [
            {
                "key": r.key,
                "display": r.display,
                "dataset_status": r.dataset_status,
                "dataset": r.dataset_label,
            }
            for r in REGIONS.values()
        ],
    }


@router.get("/status")
async def osm_status():
    """Provider reachability + cache stats (honest probe at request time)."""
    ok = False
    detail = ""
    try:
        elements = await osm_service._query_overpass(
            "[out:json][timeout:25];node[\"place\"=\"town\"](9.9,76.8,10.4,77.3);out 1;"
        )
        ok = True
        detail = f"Overpass reachable; probe returned {len(elements)} element(s)"
    except Exception as exc:
        detail = f"Overpass probe failed: {type(exc).__name__}: {exc}"
    return {
        "provider": "Overpass API",
        "url": settings.OSM_OVERPASS_URL,
        "reachable": ok,
        "detail": detail,
        "cache_entries": len(osm_service._OSM_CACHE),
        "cache_ttl_s": settings.OSM_CACHE_TTL_S,
        "max_bbox_deg2": settings.OSM_MAX_BBOX_DEG2,
        "max_features": settings.OSM_MAX_FEATURES,
        "checked_at": osm_service._now_iso(),
    }


@router.get("/features")
async def osm_features(
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat (EPSG:4326)"),
    refresh: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """All OSM feature categories combined in one queryable GeoJSON payload."""
    try:
        parsed = osm_service.parse_bbox(bbox)
    except osm_service.OSMInvalidRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        payload = await osm_service.get_all_features(db, parsed, refresh=bool(refresh))
    except osm_service.OSMError as exc:
        raise HTTPException(status_code=503, detail=f"OSM provider unavailable: {exc}")
    return _wrap(payload)


@router.get("/geojson")
async def osm_geojson(
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat (EPSG:4326)"),
    refresh: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Alias of /features — same combined GeoJSON output."""
    return await osm_features(bbox=bbox, refresh=refresh, db=db)


@router.get("/{category}")
async def osm_layer(
    category: str,
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat (EPSG:4326)"),
    refresh: int = Query(0, description="1 to bypass cached tiers"),
    db: AsyncSession = Depends(get_db),
):
    """One OSM feature category (roads|buildings|facilities|water) as GeoJSON."""
    if category not in ("roads", "buildings", "facilities", "water"):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown OSM category '{category}' — use roads|buildings|facilities|water",
        )
    try:
        parsed = osm_service.parse_bbox(bbox)
    except osm_service.OSMInvalidRequest as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        payload = await osm_service.get_osm_features(
            db, category, parsed, refresh=bool(refresh)
        )
    except osm_service.OSMError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"OSM provider unavailable: {exc}",
        )
    return _wrap(payload)