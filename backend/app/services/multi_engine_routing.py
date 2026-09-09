"""Multi-engine road routing over OpenStreetMap (Phase 5C).

Engines (all consume OSM extracts; one service per region, mirroring the
region-per-GraphHopper pattern):

  ┌──────────────┬─────────────┬──────────────────────────────────────────┐
  │ engine       │ tier        │ character                                │
  ├──────────────┼─────────────┼──────────────────────────────────────────┤
  │ osrm         │ fast        │ pre-baked CH graph → sub-ms queries      │
  │ graphhopper  │ balanced    │ pre-existing integration (Phase 4)       │
  │ valhalla     │ advanced    │ runtime costing, time-aware, tiled graph │
  └──────────────┴─────────────┴──────────────────────────────────────────┘

Design rules (inherited from the GraphHopper integration — they are hard
rules, not conventions):
  - A road result is returned ONLY when the requested engine answered with a
    valid route. A failed/unconfigured engine yields status=UNAVAILABLE with
    an explicit reason — never a relabelled straight-line or other-engine
    distance.
  - Every result carries provenance (engine, source, classification, method,
    units) and stays DEMO (no official emergency-travel-time claim).
  - In-process TTL cache keyed on (engine, region, pair, profile/costing).
  - Region resolution and dataset coverage gates are shared with the
    GraphHopper path (regions.py + spatial_service resolution).

HTTP shapes consumed:
  - OSRM:   GET {base}/route/v1/{profile}/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson
  - Valhalla: POST {base}/route  {"locations":[{lat,lon},...],"costing":...,
              "shape_format":"geojson"}  (locations use lat/lon order)
  - GraphHopper: unchanged (see routing_service.py)
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import settings
from app.core.regions import REGIONS, coordinates_inside, region_for_coordinates
from app.services.routing_service import (
    _cache_get,
    _cache_set,
    _region_payload,
    region_base_url as graphhopper_base_url,
)

logger = logging.getLogger(__name__)

ENGINE_TIERS = {
    "osrm": "fast",
    "graphhopper": "balanced",
    "valhalla": "advanced",
}

ENGINE_LABELS = {
    "osrm": "OpenStreetMap + OSRM",
    "graphhopper": "OpenStreetMap + GraphHopper",
    "valhalla": "OpenStreetMap + Valhalla",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _osrm_base_url(region_key: str) -> Optional[str]:
    """Resolve a region's OSRM base URL from settings (env-driven)."""
    env_name = {
        "kerala": "OSRM_KERALA_URL",
        "vizag": "OSRM_VIZAG_URL",
        "assam": "OSRM_ASSAM_URL",
    }.get(region_key)
    if env_name is None:
        return None
    return (getattr(settings, env_name, None) or "").rstrip("/") or None


def _valhalla_base_url(region_key: str) -> Optional[str]:
    env_name = {
        "kerala": "VALHALLA_KERALA_URL",
        "vizag": "VALHALLA_VIZAG_URL",
        "assam": "VALHALLA_ASSAM_URL",
    }.get(region_key)
    if env_name is None:
        return None
    return (getattr(settings, env_name, None) or "").rstrip("/") or None


def _unavailable(
    habitation_id: str,
    site_id: str,
    engine: str,
    reason: str,
    region_key: Optional[str] = None,
) -> dict:
    """Explicit non-route response — never contains a road distance value."""
    region = REGIONS.get(region_key) if region_key else None
    return {
        "habitation_id": habitation_id,
        "site_id": site_id,
        "engine": engine,
        "engine_tier": ENGINE_TIERS[engine],
        "status": "UNAVAILABLE",
        "route": None,
        "route_geojson": None,
        "reason": reason,
        "classification": "DERIVED",
        "source": ENGINE_LABELS[engine],
        "method": "road-network route",
        "region": _region_payload(region),
        "note": (
            f"{ENGINE_LABELS[engine]} did not return a route. No road distance "
            "is provided; straight-line (geodesic) distance must NOT be "
            "treated as road distance."
        ),
        "computed_at": _now_iso(),
        "_source": f"{engine}_unavailable",
    }


def _region_gate(habitation_id: str, site_id: str, engine: str, coords):
    """Shared region + dataset-coverage gate. Returns (region_cfg, error)."""
    hab_lat, hab_lon, site_lat, site_lon = coords
    region = region_for_coordinates(hab_lat, hab_lon, site_lat, site_lon)
    if region is None:
        return None, _unavailable(
            habitation_id, site_id, engine,
            "Coordinates are not covered by a single routing region "
            "(cross-region or uncovered request) — no route attempted.",
        )
    if region not in REGIONS:
        return None, _unavailable(
            habitation_id, site_id, engine,
            f"Unsupported routing region: {region}", region,
        )
    region_cfg = REGIONS[region]
    if not coordinates_inside(region_cfg.dataset_coverage, hab_lat, hab_lon) or not \
            coordinates_inside(region_cfg.dataset_coverage, site_lat, site_lon):
        return None, _unavailable(
            habitation_id, site_id, engine,
            f"Routing dataset for region '{region}' is not loaded for this "
            f"area. {region_cfg.dataset_label}",
            region,
        )
    return region_cfg, None


def _route_payload(
    habitation_id: str,
    site_id: str,
    engine: str,
    region_cfg,
    distance_m: float,
    duration_s: float,
    coords: list,
    method_detail: str,
) -> dict:
    route = {
        "distance_m": round(distance_m, 1),
        "distance_km": round(distance_m / 1000.0, 2),
        "duration_min": round(duration_s / 60.0, 1),
        "duration_s": round(duration_s, 1),
        "unit": "km",
        "time_unit": "min",
        "classification": "DERIVED",
        "source": ENGINE_LABELS[engine],
        "method": method_detail,
        "cache": False,
        "computed_at": _now_iso(),
        "points_count": len(coords),
    }
    return {
        "habitation_id": habitation_id,
        "site_id": site_id,
        "engine": engine,
        "engine_tier": ENGINE_TIERS[engine],
        "status": "OK",
        "region": _region_payload(region_cfg),
        "route": route,
        "route_geojson": {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "habitation_id": habitation_id,
                "site_id": site_id,
                "source": ENGINE_LABELS[engine],
                "method": "road-network route",
                "distance_km": route["distance_km"],
                "duration_min": route["duration_min"],
                "engine": engine,
                "region": region_cfg.key,
            },
        },
        "note": (
            f"Road-network result from OpenStreetMap via {ENGINE_LABELS[engine]}. "
            "Travel time is an estimate, NOT official emergency travel time."
        ),
        "computed_at": _now_iso(),
        "_source": engine,
    }


async def route_osrm(
    habitation_id: str,
    site_id: str,
    coords,
    region_cfg=None,
) -> dict:
    """OSRM routed route. coords = (hab_lat, hab_lon, site_lat, site_lon)."""
    hab_lat, hab_lon, site_lat, site_lon = coords
    if region_cfg is None:
        region_cfg, err = _region_gate(habitation_id, site_id, "osrm", coords)
        if err is not None:
            return err
    base = _osrm_base_url(region_cfg.key)
    if not base:
        return _unavailable(
            habitation_id, site_id, "osrm",
            f"No OSRM service configured for region '{region_cfg.key}' "
            f"(set OSRM_{region_cfg.key.upper()}_URL).",
            region_cfg.key,
        )

    profile = settings.OSRM_PROFILE
    key = f"osrm|{base}|{habitation_id}|{site_id}|{profile}"
    cached = _cache_get(key)
    if cached is not None:
        if cached.get("route"):
            cached["route"]["cache"] = True
        return cached

    url = (
        f"{base}/route/v1/{profile}/"
        f"{hab_lon},{hab_lat};{site_lon},{site_lat}"
        "?overview=full&geometries=geojson&annotations=false"
    )
    try:
        async with httpx.AsyncClient(timeout=settings.OSRM_TIMEOUT_S) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return _unavailable(
                habitation_id, site_id, "osrm",
                f"OSRM returned HTTP {resp.status_code}", region_cfg.key,
            )
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return _unavailable(
                habitation_id, site_id, "osrm",
                f"OSRM code={data.get('code')} (no route)", region_cfg.key,
            )
        route = data["routes"][0]
        distance_m = float(route.get("distance") or 0.0)
        duration_s = float(route.get("duration") or 0.0)
        if distance_m <= 0 or duration_s <= 0:
            return _unavailable(
                habitation_id, site_id, "osrm",
                "OSRM returned non-positive distance/duration", region_cfg.key,
            )
        coords_list = [
            [float(c[0]), float(c[1])]
            for c in (route.get("geometry") or {}).get("coordinates", [])
        ]
        payload = _route_payload(
            habitation_id, site_id, "osrm", region_cfg,
            distance_m, duration_s, coords_list,
            f"road-network route (OSRM, profile={profile})",
        )
        _cache_set(key, payload)
        return payload
    except Exception as exc:
        logger.warning(f"[routing/osrm] request failed: {type(exc).__name__}: {exc}")
        return _unavailable(
            habitation_id, site_id, "osrm",
            f"OSRM request failed: {type(exc).__name__}", region_cfg.key,
        )


async def route_valhalla(
    habitation_id: str,
    site_id: str,
    coords,
    region_cfg=None,
) -> dict:
    """Valhalla routed route. coords = (hab_lat, hab_lon, site_lat, site_lon)."""
    hab_lat, hab_lon, site_lat, site_lon = coords
    if region_cfg is None:
        region_cfg, err = _region_gate(habitation_id, site_id, "valhalla", coords)
        if err is not None:
            return err
    base = _valhalla_base_url(region_cfg.key)
    if not base:
        return _unavailable(
            habitation_id, site_id, "valhalla",
            f"No Valhalla service configured for region '{region_cfg.key}' "
            f"(set VALHALLA_{region_cfg.key.upper()}_URL).",
            region_cfg.key,
        )

    costing = settings.VALHALLA_COSTING
    key = f"valhalla|{base}|{habitation_id}|{site_id}|{costing}"
    cached = _cache_get(key)
    if cached is not None:
        if cached.get("route"):
            cached["route"]["cache"] = True
        return cached

    body = {
        "locations": [
            {"lat": hab_lat, "lon": hab_lon},
            {"lat": site_lat, "lon": site_lon},
        ],
        "costing": costing,
        "shape_format": "geojson",
        "id": f"{habitation_id}->{site_id}",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.VALHALLA_TIMEOUT_S) as client:
            resp = await client.post(f"{base}/route", json=body)
        if resp.status_code != 200:
            return _unavailable(
                habitation_id, site_id, "valhalla",
                f"Valhalla returned HTTP {resp.status_code}", region_cfg.key,
            )
        data = resp.json()
        # Valhalla returns 200 with an error body when the request itself fails.
        if data.get("error_code") or data.get("error"):
            return _unavailable(
                habitation_id, site_id, "valhalla",
                f"Valhalla error {data.get('error_code')}: {data.get('error')}",
                region_cfg.key,
            )
        path = (data.get("trip") or {}).get("legs") or []
        if not path:
            return _unavailable(
                habitation_id, site_id, "valhalla",
                "Valhalla returned no legs", region_cfg.key,
            )
        distance_km = float(data["trip"].get("summary", {}).get("length") or 0.0)
        duration_s = float(data["trip"].get("summary", {}).get("time") or 0.0)
        if distance_km <= 0 or duration_s <= 0:
            return _unavailable(
                habitation_id, site_id, "valhalla",
                "Valhalla returned non-positive distance/time", region_cfg.key,
            )
        coords_list: list = []
        for leg in path:
            shape = (leg.get("shape") or "")
            if isinstance(shape, str):
                # polyline6 encoded — decode without external deps
                coords_list.extend(_decode_polyline6(shape))
            elif isinstance(shape, list):
                # geojson shape: [[lon, lat], ...]
                coords_list.extend([float(c[0]), float(c[1])] for c in shape)
        payload = _route_payload(
            habitation_id, site_id, "valhalla", region_cfg,
            distance_km * 1000.0, duration_s, coords_list,
            f"road-network route (Valhalla, costing={costing})",
        )
        _cache_set(key, payload)
        return payload
    except Exception as exc:
        logger.warning(f"[routing/valhalla] request failed: {type(exc).__name__}: {exc}")
        return _unavailable(
            habitation_id, site_id, "valhalla",
            f"Valhalla request failed: {type(exc).__name__}", region_cfg.key,
        )


def _decode_polyline6(encoded: str):
    """Decode a Valhalla polyline6 string into [[lon,lat], ...]."""
    coords = []
    index = lat = lng = 0
    while index < len(encoded):
        for shift_storage in ("lat", "lng"):
            result = shift = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if shift_storage == "lat":
                lat += delta
            else:
                lng += delta
        coords.append([lng * 1e-6, lat * 1e-6])
    return coords


async def route_with_engine(session, habitation_id: str, site_id: str, engine: str) -> Optional[dict]:
    """Resolve both endpoints, apply shared gates, dispatch to the engine.

    Returns None only when either id is unknown everywhere (caller → 404).
    """
    from app.services.spatial_service import _resolve_habitation, _resolve_site

    engine = engine if engine in ENGINE_TIERS else "graphhopper"

    hab = await _resolve_habitation(session, habitation_id)
    site = await _resolve_site(session, site_id)
    if hab is None or site is None:
        return None
    hab_lat, hab_lon, _ = hab
    site_lat, site_lon, _ = site
    coords = (hab_lat, hab_lon, site_lat, site_lon)

    region_cfg, err = _region_gate(habitation_id, site_id, engine, coords)
    if err is not None:
        return err

    if engine == "osrm":
        return await route_osrm(habitation_id, site_id, coords, region_cfg)
    if engine == "valhalla":
        return await route_valhalla(habitation_id, site_id, coords, region_cfg)

    # graphhopper — delegate to the existing implementation (it re-resolves
    # and re-gates internally; cheap because both are cache/db hits). Its
    # payloads predate the multi-engine schema, so stamp the engine metadata
    # here to keep every response shape identical.
    from app.services.routing_service import route_road
    result = await route_road(session, habitation_id, site_id, region=region_cfg.key)
    if result is not None:
        result.setdefault("engine", "graphhopper")
        result.setdefault("engine_tier", ENGINE_TIERS["graphhopper"])
        result.setdefault("route_geojson", None)
    return result


async def engines_status(region_key: str = "kerala") -> dict:
    """Probe every configured engine for the region (used by the UI selector)."""
    results = {}

    gh_url = graphhopper_base_url(region_key)
    if gh_url:
        from app.services.routing_service import graphhopper_health
        ok, detail = await graphhopper_health(region=region_key)
        results["graphhopper"] = {
            "tier": ENGINE_TIERS["graphhopper"], "ok": ok,
            "detail": detail, "url": gh_url,
        }
    else:
        results["graphhopper"] = {
            "tier": ENGINE_TIERS["graphhopper"], "ok": False,
            "detail": "Not configured", "url": None,
        }

    osrm_url = _osrm_base_url(region_key)
    if osrm_url:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{osrm_url}/health")
            results["osrm"] = {
                "tier": ENGINE_TIERS["osrm"],
                "ok": resp.status_code == 200,
                "detail": f"HTTP {resp.status_code}",
                "url": osrm_url,
            }
        except Exception as exc:
            results["osrm"] = {
                "tier": ENGINE_TIERS["osrm"], "ok": False,
                "detail": f"Unreachable: {type(exc).__name__}", "url": osrm_url,
            }
    else:
        results["osrm"] = {
            "tier": ENGINE_TIERS["osrm"], "ok": False,
            "detail": "Not configured", "url": None,
        }

    valhalla_url = _valhalla_base_url(region_key)
    if valhalla_url:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{valhalla_url}/status")
            results["valhalla"] = {
                "tier": ENGINE_TIERS["valhalla"],
                "ok": resp.status_code == 200,
                "detail": f"HTTP {resp.status_code}",
                "url": valhalla_url,
            }
        except Exception as exc:
            results["valhalla"] = {
                "tier": ENGINE_TIERS["valhalla"], "ok": False,
                "detail": f"Unreachable: {type(exc).__name__}", "url": valhalla_url,
            }
    else:
        results["valhalla"] = {
            "tier": ENGINE_TIERS["valhalla"], "ok": False,
            "detail": "Not configured", "url": None,
        }

    return {
        "region": region_key,
        "engines": results,
        "note": (
            "All engines route on OpenStreetMap data. OSRM = fast (pre-baked "
            "graph), Valhalla = advanced (runtime costing, isochrones), "
            "GraphHopper = balanced. Engine status reflects this deployment "
            "only — routes are served only by engines that answer."
        ),
        "checked_at": _now_iso(),
    }
