"""Road-network routing service (Phase 4) — GraphHopper over OpenStreetMap.

Obtains road distance / travel time between PostGIS habitation geometry and
candidate-site geometry through a self-hosted GraphHopper instance.

Hard rules:
  - A road result is returned ONLY when GraphHopper answered with a valid
    route. Fallbacks are never labelled as road distances.
  - Coordinates are passed as lon,lat (GraphHopper point order).
  - Every result carries provenance (source, classification, method, units)
    and is clearly DEMO (no official emergency-travel-time claim).
  - In-process TTL cache keeps the demo to a handful of GraphHopper calls.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.core.regions import REGIONS, coordinates_inside, region_for_coordinates
from app.services.spatial_service import _resolve_habitation, _resolve_site

logger = logging.getLogger(__name__)

_ROUTE_CACHE: dict = {}


def _cache_key(habitation_id: str, site_id: str, profile: str, base_url: str) -> str:
    return f"{base_url}|{habitation_id}|{site_id}|{profile}"


def _cache_get(key: str) -> Optional[dict]:
    entry = _ROUTE_CACHE.get(key)
    if not entry:
        return None
    expires, payload = entry
    if time.time() > expires:
        _ROUTE_CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: dict, ttl_s: int = None) -> None:
    _ROUTE_CACHE[key] = (time.time() + (ttl_s or settings.ROUTE_CACHE_TTL_S), payload)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def graphhopper_health(base_url: str = None, region: Optional[str] = None) -> tuple:
    """Probe GraphHopper /info. Returns (healthy: bool, detail: str)."""
    url = base_url or region_base_url(region or "kerala") or settings.GRAPHHOPPER_URL
    url = url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=min(settings.GRAPHHOPPER_TIMEOUT_S, 6.0)) as client:
            resp = await client.get(f"{url}/info")
        if resp.status_code == 200:
            data = resp.json()
            profiles = [p.get("name") for p in data.get("profiles", [])]
            return True, f"GraphHopper reachable; profiles={profiles}"
        return False, f"GraphHopper /info returned HTTP {resp.status_code}"
    except Exception as exc:
        return False, f"GraphHopper unreachable: {type(exc).__name__}"


async def graphhopper_health_regions() -> dict:
    """Probe /info on every configured region's GraphHopper service.

    Returns {region_key: {"ok": bool, "detail": str, "url": str|None}}.
    Region is only reachable when the region's own engine answers.
    """
    out = {}
    for key in REGIONS:
        ok, detail = await graphhopper_health(region=key)
        out[key] = {"ok": ok, "detail": detail, "url": region_base_url(key)}
    return out


def _unavailable_response(
    habitation_id: str,
    site_id: str,
    reason: str,
    region_key: Optional[str] = None,
) -> dict:
    """Explicit non-route response — never contains a road distance value."""
    region = REGIONS.get(region_key) if region_key else None
    return {
        "habitation_id": habitation_id,
        "site_id": site_id,
        "status": "UNAVAILABLE",
        "route": None,
        "reason": reason,
        "classification": "DERIVED",
        "source": "OpenStreetMap + GraphHopper",
        "method": "road-network route",
        "region": _region_payload(region),
        "note": (
            "GraphHopper did not return a route. No road distance is provided; "
            "straight-line (geodesic) distance must NOT be treated as road distance."
        ),
        "computed_at": _now_iso(),
        "_source": "graphhopper_unavailable",
    }


def _region_payload(region) -> dict:
    if region is None:
        return {"key": None, "display": None, "dataset_status": None, "dataset": None}
    return {
        "key": region.key,
        "display": region.display,
        "dataset_status": region.dataset_status,
        "dataset": region.dataset_label,
    }


def region_base_url(region_key: str) -> Optional[str]:
    """Resolve a region's GraphHopper base URL (env override, else default)."""
    region = REGIONS.get(region_key)
    if region is None:
        return None
    env_value = getattr(settings, region.url_env, None)
    return (env_value or region.default_url or "").rstrip("/") or None


async def route_road(
    session,
    habitation_id: str,
    site_id: str,
    region: Optional[str] = None,
    base_url: str = None,
    profile: str = None,
    timeout_s: float = None,
) -> Optional[dict]:
    """Road distance + travel time habitation → candidate site via GraphHopper.

    Region selection:
      - explicit `region` (kerala|vizag|assam) is validated and used;
      - otherwise the region is derived from the coordinates' reference bounds.
    The region's dataset must actually be loaded (dataset coverage gate) and
    the GraphHopper service must answer — otherwise UNAVAILABLE. Cross-region
    or uncovered requests never route.

    Returns None only when either id is unknown everywhere (caller → 404).
    """
    profile = profile or settings.GRAPHHOPPER_PROFILE
    timeout_s = timeout_s or settings.GRAPHHOPPER_TIMEOUT_S

    hab = await _resolve_habitation(session, habitation_id)
    site = await _resolve_site(session, site_id)
    if hab is None or site is None:
        return None
    hab_lat, hab_lon, _ = hab
    site_lat, site_lon, _ = site

    # ── Region resolution / validation ──────────────────────────────────────
    if region is None:
        region = region_for_coordinates(hab_lat, hab_lon, site_lat, site_lon)
        if region is None:
            return _unavailable_response(
                habitation_id,
                site_id,
                "Coordinates are not covered by a single routing region "
                "(cross-region or uncovered request) — no route attempted.",
            )
    if region not in REGIONS:
        return _unavailable_response(
            habitation_id, site_id, f"Unsupported routing region: {region}", region
        )
    region_cfg = REGIONS[region]

    # ── Dataset gate: never route through a graph whose dataset isn't loaded ─
    if not coordinates_inside(region_cfg.dataset_coverage, hab_lat, hab_lon) or not coordinates_inside(
        region_cfg.dataset_coverage, site_lat, site_lon
    ):
        return _unavailable_response(
            habitation_id,
            site_id,
            f"Routing dataset for region '{region}' is not loaded for this area. "
            f"{region_cfg.dataset_label}",
            region,
        )

    base_url = base_url or region_base_url(region)
    if not base_url:
        return _unavailable_response(
            habitation_id,
            site_id,
            f"No GraphHopper service configured for region '{region}' "
            f"(set {region_cfg.url_env}). {region_cfg.dataset_label}",
            region,
        )
    base_url = base_url.rstrip("/")

    key = _cache_key(habitation_id, site_id, profile, base_url)
    cached = _cache_get(key)
    if cached is not None:
        cached["route"]["cache"] = True
        return cached

    try:
        # GraphHopper /route expects point=lat,lon (NOT lon,lat).
        params = {
            "profile": profile,
            "point": [f"{hab_lat},{hab_lon}", f"{site_lat},{site_lon}"],
            "points_encoded": "false",
            "instructions": "false",
            "locale": "en",
        }
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(f"{base_url}/route", params=params)
        if resp.status_code != 200:
            logger.warning(f"[routing] GraphHopper HTTP {resp.status_code}: {resp.text[:200]}")
            return _unavailable_response(
                habitation_id, site_id, f"GraphHopper returned HTTP {resp.status_code}", region
            )
        data = resp.json()
        paths = data.get("paths") or []
        if not paths:
            return _unavailable_response(
                habitation_id, site_id, "GraphHopper returned no paths", region
            )
        path = paths[0]
        distance_m = float(path.get("distance") or 0.0)
        duration_ms = float(path.get("time") or 0.0)
        if distance_m <= 0 or duration_ms <= 0:
            return _unavailable_response(
                habitation_id, site_id, "GraphHopper returned non-positive distance/time", region
            )

        coords = [[float(c[0]), float(c[1])] for c in (path.get("points") or {}).get("coordinates", [])]
        route = {
            "distance_m": round(distance_m, 1),
            "distance_km": round(distance_m / 1000.0, 2),
            "duration_min": round(duration_ms / 60000.0, 1),
            "duration_s": round(duration_ms / 1000.0, 1),
            "unit": "km",
            "time_unit": "min",
            "classification": "DERIVED",
            "source": "OpenStreetMap + GraphHopper",
            "method": f"road-network route (GraphHopper, profile={profile})",
            "profile": profile,
            "cache": False,
            "computed_at": _now_iso(),
            "points_count": len(coords),
        }
        payload = {
            "habitation_id": habitation_id,
            "site_id": site_id,
            "status": "OK",
            "region": _region_payload(region_cfg),
            "route": route,
            "route_geojson": {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
                "properties": {
                    "habitation_id": habitation_id,
                    "site_id": site_id,
                    "source": "OpenStreetMap + GraphHopper",
                    "method": "road-network route",
                    "distance_km": route["distance_km"],
                    "duration_min": route["duration_min"],
                    "profile": profile,
                    "region": region,
                },
            },
            "note": (
                "Road-network result from OpenStreetMap via GraphHopper. "
                "Travel time is an estimate, NOT official emergency travel time."
            ),
            "computed_at": _now_iso(),
            "_source": "graphhopper",
        }
        _cache_set(key, payload)
        return payload
    except Exception as exc:
        logger.warning(f"[routing] GraphHopper request failed: {type(exc).__name__}: {exc}")
        return _unavailable_response(
            habitation_id, site_id, f"GraphHopper request failed: {type(exc).__name__}", region
        )


async def compare_distances(session, habitation_id: str) -> dict:
    """Habitation→site distance comparison: DEMO seed vs PostGIS geodesic vs road."""
    rows = []
    from app.services import demo_data
    from app.services.spatial_service import get_spatial_distance

    sites = demo_data.get_candidate_sites(habitation_id)["sites"]
    for s in sites:
        road = await route_road(session, habitation_id, s["id"])
        geo = await get_spatial_distance(session, habitation_id, s["id"])
        rows.append({
            "site_id": s["id"],
            "site_name": s["name"],
            "demo_km": s["distance_km"],
            "demo_label": "ESTIMATED/DEMO seed distance (not measured)",
            "geodesic_km": geo["distance_km"] if geo else None,
            "geodesic_method": geo["method"] if geo else None,
            "geodesic_source": "PostGIS ST_Distance(geography)" if geo and geo["_source"] == "postgis" else "haversine fallback (demo coordinates)",
            "road_km": road["route"]["distance_km"] if road and road["status"] == "OK" else None,
            "duration_min": road["route"]["duration_min"] if road and road["status"] == "OK" else None,
            "road_status": road["status"] if road else "UNKNOWN",
            "road_region": road["region"]["key"] if road and road.get("region") else None,
            "road_source": "OpenStreetMap + GraphHopper",
        })
    return {
        "habitation_id": habitation_id,
        "data_status": "DEMO",
        "columns": {
            "demo_km": "Estimated/demo distance — existing seed input",
            "geodesic_km": "Geodesic straight-line — PostGIS ST_Distance(geography)",
            "road_km": "Road-network distance — OpenStreetMap + GraphHopper (only when road_status=OK)",
        },
        "rows": rows,
        "note": (
            "Road distance ≠ geodesic distance ≠ demo estimate. Road results are "
            "returned only when the region's GraphHopper dataset is loaded and "
            "the service answered with a valid route."
        ),
    }
