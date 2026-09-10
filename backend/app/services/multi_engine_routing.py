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

# Phase 7 policy roles: OSRM is the fast primary, Valhalla the advanced engine
# (risk-aware routes + isochrones), GraphHopper optional/experimental only.
ENGINE_ROLE = {
    "osrm": "primary",
    "valhalla": "advanced",
    "graphhopper": "optional",
}

ROUTING_POLICY = {
    "ROUTE_STANDARD": "osrm -> valhalla",
    "ROUTE_ADVANCED": "valhalla -> none",
    "ROUTE_MATRIX": "osrm -> valhalla",
    "OPTIMIZATION": "ortools (greedy fallback)",
}

_ROUTING_POLICY_CHAINS = {
    "ROUTE_STANDARD": ("osrm", "valhalla"),
    "ROUTE_ADVANCED": ("valhalla",),
    "ROUTE_MATRIX": ("osrm", "valhalla"),
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


# ── Engine status: reachable vs ready (Phase 7, Task B1) ────────────────────
# reachable = a cheap probe answered (service reachable).
# ready = a real Kerala routing request returned a valid payload.
# A running container is NOT ready (spec constraint #2). ok == ready (kept
# for backward compatibility).

_ENGINE_PROBE_TIMEOUT_S = 6.0

# Real Kerala smoke pair used for readiness (inside every region's extract).
_OSRM_READY_URL = "{base}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
_OSRM_READY_COORDS = ("76.93", "10.01", "77.16", "10.03")
_VALHALLA_READY_BODY = {
    "locations": [{"lat": 10.01, "lon": 76.93}, {"lat": 10.03, "lon": 77.16}],
    "costing": "auto",
}
_GH_READY_URL = "{base}/route?point={lat1},{lon1}&point={lat2},{lon2}&profile={profile}"


async def _engine_probe(engine: str, base_url: str) -> tuple:
    """Cheap reachability probe. Returns (reachable: bool, detail: str)."""
    url = base_url.rstrip("/")
    def _json(resp):
        try:
            return resp.json()
        except ValueError:
            return {}
    try:
        if engine == "osrm":
            probe_url = _OSRM_READY_URL.format(
                base=url, lon1=_OSRM_READY_COORDS[0], lat1=_OSRM_READY_COORDS[1],
                lon2=_OSRM_READY_COORDS[2], lat2=_OSRM_READY_COORDS[3],
            )
            async with httpx.AsyncClient(timeout=_ENGINE_PROBE_TIMEOUT_S) as client:
                resp = await client.get(probe_url)
            return resp.status_code == 200, f"HTTP {resp.status_code}"
        if engine == "valhalla":
            async with httpx.AsyncClient(timeout=_ENGINE_PROBE_TIMEOUT_S) as client:
                resp = await client.get(f"{url}/status")
            ok = resp.status_code == 200 and bool(_json(resp).get("available_actions"))
            return ok, f"HTTP {resp.status_code}"
        async with httpx.AsyncClient(timeout=_ENGINE_PROBE_TIMEOUT_S) as client:
            resp = await client.get(f"{url}/info")
        ok = resp.status_code == 200 and bool(_json(resp).get("profiles"))
        return ok, f"HTTP {resp.status_code}"
    except Exception as exc:
        return False, f"Unreachable: {type(exc).__name__}"


async def _engine_ready(engine: str, base_url: str) -> bool:
    """Real routing request against the Kerala dataset. Returns ready: bool."""
    url = base_url.rstrip("/")
    try:
        if engine == "osrm":
            probe_url = _OSRM_READY_URL.format(
                base=url, lon1=_OSRM_READY_COORDS[0], lat1=_OSRM_READY_COORDS[1],
                lon2=_OSRM_READY_COORDS[2], lat2=_OSRM_READY_COORDS[3],
            )
            async with httpx.AsyncClient(timeout=settings.OSRM_TIMEOUT_S) as client:
                resp = await client.get(probe_url)
            if resp.status_code != 200:
                return False
            data = resp.json()
            return data.get("code") == "Ok" and bool(data.get("routes"))
        if engine == "valhalla":
            body = dict(_VALHALLA_READY_BODY)
            body["costing"] = settings.VALHALLA_COSTING
            async with httpx.AsyncClient(timeout=settings.VALHALLA_TIMEOUT_S) as client:
                resp = await client.post(f"{url}/route", json=body)
            if resp.status_code != 200:
                return False
            data = resp.json()
            return "trip" in data and not data.get("error_code") and not data.get("error")
        g_url = _GH_READY_URL.format(
            base=url, lat1="10.01", lon1="76.93",
            lat2="10.03", lon2="77.16", profile=settings.GRAPHHOPPER_PROFILE,
        )
        async with httpx.AsyncClient(timeout=min(settings.GRAPHHOPPER_TIMEOUT_S, 15.0)) as client:
            resp = await client.get(g_url)
        if resp.status_code != 200:
            return False
        paths = resp.json().get("paths")
        return isinstance(paths, list) and bool(paths)
    except Exception as exc:
        logger.warning(f"[routing/status] {engine} ready probe failed: {type(exc).__name__}")
        return False


def _engine_entry(engine: str, base_url: Optional[str], reachable: bool, ready: bool,
                  detail: str) -> dict:
    return {
        "tier": ENGINE_TIERS[engine],
        "role": ENGINE_ROLE[engine],
        "ok": ready,
        "reachable": reachable,
        "ready": ready,
        "detail": detail,
        "url": base_url,
    }


def _engine_url(region_key: str, engine: str) -> Optional[str]:
    if engine == "osrm":
        return _osrm_base_url(region_key)
    if engine == "valhalla":
        return _valhalla_base_url(region_key)
    return graphhopper_base_url(region_key)


async def engines_status(region_key: str = "kerala") -> dict:
    """Probe every configured engine for the region (used by the UI selector).

    Per engine: `reachable` (cheap probe) and `ready` (real Kerala routing
    request); `ok` == `ready` (backward compatible). GraphHopper is marked
    `experimental`. The `policy` block documents the approved routing policy.
    """
    results = {}
    for engine in ("osrm", "valhalla", "graphhopper"):
        base_url = _engine_url(region_key, engine)
        if not base_url:
            results[engine] = _engine_entry(engine, None, False, False, "Not configured")
            if engine == "graphhopper":
                results[engine]["experimental"] = True
            continue
        reachable, detail = await _engine_probe(engine, base_url)
        if not reachable:
            results[engine] = _engine_entry(engine, base_url, False, False, detail)
        else:
            ready = await _engine_ready(engine, base_url)
            results[engine] = _engine_entry(
                engine, base_url, True, ready,
                "reachable (probe ok); real routing request "
                + ("ok" if ready else "failed — not ready"),
            )
        if engine == "graphhopper":
            results[engine]["experimental"] = True

    return {
        "region": region_key,
        "engines": results,
        "policy": dict(ROUTING_POLICY),
        "note": (
            "All engines route on OpenStreetMap data. OSRM = primary (fast, "
            "ROUTE_STANDARD/ROUTE_MATRIX), Valhalla = advanced (ROUTE_ADVANCED, "
            "risk-aware, isochrones), GraphHopper = optional/experimental. "
            "reachable = the service answers a probe; ready = a real Kerala "
            "routing request succeeded; ok = ready. Routes are served only by "
            "engines that are ready."
        ),
        "checked_at": _now_iso(),
    }


async def pick_engine(region_key: str = "kerala", policy_key: str = "ROUTE_STANDARD") -> Optional[str]:
    """First `ready` engine in a policy chain, else None.

    ROUTE_STANDARD / ROUTE_MATRIX → osrm → valhalla; ROUTE_ADVANCED →
    valhalla only. Returns None when no engine in the chain is ready.
    """
    chain = _ROUTING_POLICY_CHAINS.get(policy_key)
    if not chain:
        return None
    status = await engines_status(region_key)
    for engine in chain:
        if status.get("engines", {}).get(engine, {}).get("ready"):
            return engine
    return None


# ── Alternatives / isochrones / matrix (Phase 6) ─────────────────────────────

def _alternative_payload(habitation_id: str, site_id: str, engine: str,
                         region_cfg, index: int, distance_m: float,
                         duration_s: float, coords: list, method_detail: str) -> dict:
    route = {
        "index": index,
        "distance_m": round(distance_m, 1),
        "distance_km": round(distance_m / 1000.0, 2),
        "duration_min": round(duration_s / 60.0, 1),
        "duration_s": round(duration_s, 1),
        "classification": "DERIVED",
        "source": ENGINE_LABELS[engine],
        "method": method_detail,
        "computed_at": _now_iso(),
        "points_count": len(coords),
    }
    return {
        "habitation_id": habitation_id,
        "site_id": site_id,
        "engine": engine,
        "index": index,
        "route": route,
        "route_geojson": {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "habitation_id": habitation_id, "site_id": site_id,
                "engine": engine, "region": region_cfg.key,
                "alternative_index": index,
                "distance_km": route["distance_km"],
                "duration_min": route["duration_min"],
            },
        },
    }


async def route_alternatives(
    session, habitation_id: str, site_id: str, engine: str,
    max_alternatives: int = 3,
) -> dict:
    """Request up to N alternative routes from the requested engine.

    Usually 3 shorter/equal routes at most; engines decide the pool. Never a
    relabel — UNAVAILABLE when the engine cannot answer. The primary route is
    included as index 0 so `avoid_hazards` can compare against it.
    """
    engine = engine if engine in ENGINE_TIERS else "graphhopper"
    if max_alternatives < 1 or max_alternatives > 5:
        max_alternatives = 3

    resolved = await _resolve_pair(session, habitation_id, site_id, engine)
    if resolved is None:
        return {"habitation_id": habitation_id, "site_id": site_id, "engine": engine,
                "status": "UNAVAILABLE", "reason": "Unknown habitation or site", "routes": []}
    coords, region_cfg, err = resolved
    if err is not None:
        return {**err, "routes": [], "status": "UNAVAILABLE"}

    base_url = _base_url_for(engine, region_cfg.key)
    if not base_url:
        return {"habitation_id": habitation_id, "site_id": site_id, "engine": engine,
                "status": "UNAVAILABLE", "routes": [],
                "reason": f"No {engine} service configured for region '{region_cfg.key}'"}

    hab_lat, hab_lon, site_lat, site_lon = coords
    try:
        if engine == "osrm":
            url = (
                f"{base_url}/route/v1/{settings.OSRM_PROFILE}/"
                f"{hab_lon},{hab_lat};{site_lon},{site_lat}"
                f"?alternatives={max_alternatives - 1}&overview=full&geometries=geojson&steps=false"
            )
            async with httpx.AsyncClient(timeout=settings.OSRM_TIMEOUT_S) as client:
                resp = await client.get(url)
            if resp.status_code != 200 or not resp.json().get("routes"):
                raise OSError(f"OSRM alternatives HTTP {resp.status_code}")
            routes = resp.json()["routes"]
            alts = []
            for i, r in enumerate(routes[:max_alternatives]):
                coords_list = [[float(c[0]), float(c[1])]
                               for c in (r.get("geometry") or {}).get("coordinates", [])]
                alts.append(_alternative_payload(
                    habitation_id, site_id, engine, region_cfg, i,
                    float(r.get("distance") or 0), float(r.get("duration") or 0),
                    coords_list, f"road-network alternative (OSRM, profile={settings.OSRM_PROFILE})"))
        elif engine == "valhalla":
            body = {
                "locations": [{"lat": hab_lat, "lon": hab_lon},
                              {"lat": site_lat, "lon": site_lon}],
                "costing": settings.VALHALLA_COSTING,
                "shape_format": "geojson",
                "alternatives": {"target_count": max_alternatives - 1},
                "id": f"{habitation_id}->{site_id}",
            }
            async with httpx.AsyncClient(timeout=settings.VALHALLA_TIMEOUT_S) as client:
                resp = await client.post(f"{base_url}/route", json=body)
            if resp.status_code != 200 or (resp.json() or {}).get("error_code"):
                raise OSError(f"Valhalla alternatives {resp.status_code}: {resp.text[:120]}")
            legs = (resp.json().get("trip") or {}).get("legs") or []
            alts = []
            for i, leg in enumerate(legs[:max_alternatives]):
                shape = leg.get("shape") or ""
                coords_list = (_decode_polyline6(shape) if isinstance(shape, str)
                               else [[float(c[0]), float(c[1])] for c in shape])
                summary = leg.get("summary") or {}
                alts.append(_alternative_payload(
                    habitation_id, site_id, engine, region_cfg, i,
                    float(summary.get("length") or 0) * 1000.0,
                    float(summary.get("time") or 0), coords_list,
                    f"road-network alternative (Valhalla, costing={settings.VALHALLA_COSTING})"))
        else:  # graphhopper
            params = {
                "profile": settings.GRAPHHOPPER_PROFILE,
                "point": [f"{hab_lat},{hab_lon}", f"{site_lat},{site_lon}"],
                "points_encoded": "false",
                "instructions": "false",
                "alternative_route.max_paths": max_alternatives,
            }
            async with httpx.AsyncClient(timeout=settings.GRAPHHOPPER_TIMEOUT_S) as client:
                resp = await client.get(f"{base_url}/route", params=params)
            if resp.status_code != 200:
                raise OSError(f"GraphHopper alternatives HTTP {resp.status_code}")
            paths = resp.json().get("paths") or []
            alts = []
            for i, p in enumerate(paths[:max_alternatives]):
                coords_list = [[float(c[0]), float(c[1])]
                               for c in (p.get("points") or {}).get("coordinates", [])]
                alts.append(_alternative_payload(
                    habitation_id, site_id, engine, region_cfg, i,
                    float(p.get("distance") or 0), float(p.get("time") or 0) / 1000.0,
                    coords_list,
                    f"road-network alternative (GraphHopper, profile={settings.GRAPHHOPPER_PROFILE})"))
    except Exception as exc:
        logger.warning(f"[routing/{engine}] alternatives failed: {type(exc).__name__}: {exc}")
        return {"habitation_id": habitation_id, "site_id": site_id, "engine": engine,
                "status": "UNAVAILABLE", "routes": [],
                "reason": f"{engine} alternatives request failed: {type(exc).__name__}",
                "computed_at": _now_iso()}

    return {
        "habitation_id": habitation_id,
        "site_id": site_id,
        "engine": engine,
        "status": "OK" if alts else "UNAVAILABLE",
        "routes": alts,
        "region": _region_payload(region_cfg),
        "note": (
            "Alternative routes are candidates for hazard-aware selection, NOT "
            "official evacuation corridors. Verify every route before use."
        ),
        "computed_at": _now_iso(),
        "_source": engine,
    }


# `_resolve_pair` is defined after the helpers it needs; force the async
# boundary cleanly so route_alternatives reads naturally above.
async def _resolve_pair(session, habitation_id: str, site_id: str, engine: str):
    from app.services.spatial_service import _resolve_habitation, _resolve_site
    hab = await _resolve_habitation(session, habitation_id)
    site = await _resolve_site(session, site_id)
    if hab is None or site is None:
        return None
    hab_lat, hab_lon, _ = hab
    site_lat, site_lon, _ = site
    coords = (hab_lat, hab_lon, site_lat, site_lon)
    region_cfg, err = _region_gate(habitation_id, site_id, engine, coords)
    return (coords, region_cfg, err)


def _base_url_for(engine: str, region_key: str) -> Optional[str]:
    if engine == "osrm":
        return _osrm_base_url(region_key)
    if engine == "valhalla":
        return _valhalla_base_url(region_key)
    return graphhopper_base_url(region_key)


async def valhalla_isochrones(region_key: str, lat: float, lon: float,
                              contours_min: list) -> dict:
    """Valhalla /isochrone → GeoJSON FeatureCollection (honest UNAVAILABLE)."""
    region_cfg = REGIONS.get(region_key)
    if region_cfg is None or not coordinates_inside(region_cfg.dataset_coverage, lat, lon):
        return {
            "data_status": "UNAVAILABLE",
            "reason": f"Coordinates outside '{region_key}' dataset coverage — no isochrones.",
            "feature_collection": {"type": "FeatureCollection", "features": []},
        }
    base = _valhalla_base_url(region_key)
    if not base:
        return {
            "data_status": "UNAVAILABLE",
            "reason": f"No Valhalla service configured for region '{region_key}'.",
            "feature_collection": {"type": "FeatureCollection", "features": []},
        }
    body = {
        "locations": [{"lat": lat, "lon": lon}],
        "costing": settings.VALHALLA_COSTING,
        "contours": [{"time": int(m)} for m in contours_min[:6]],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.VALHALLA_TIMEOUT_S) as client:
            resp = await client.post(f"{base}/isochrone", json=body)
        if resp.status_code != 200:
            return {
                "data_status": "UNAVAILABLE",
                "reason": f"Valhalla isochrone HTTP {resp.status_code}",
                "feature_collection": {"type": "FeatureCollection", "features": []},
            }
        data = resp.json()
        features = data.get("features") or []
        # Valhalla edges share a common exterior ring; keep the smallest rings
        # per contour for legibility (properties.contour carries the minutes).
        fc = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": f.get("geometry"),
                 "properties": {"contour_min": f.get("properties", {}).get("contour", {}).get("time"),
                                "color": f.get("properties", {}).get("fillColor")}}
                for f in features
            ],
        }
        return {
            "data_status": "LIVE",
            "source": f"OpenStreetMap + Valhalla ({base})",
            "region": region_key,
            "computed_at": _now_iso(),
            "feature_collection": fc,
        }
    except Exception as exc:
        return {
            "data_status": "UNAVAILABLE",
            "reason": f"Valhalla isochrone failed: {type(exc).__name__}",
            "feature_collection": {"type": "FeatureCollection", "features": []},
        }


async def graphhopper_matrix(session, habitation_ids: list, site_ids: list) -> dict:
    """GraphHopper /matrix: real row=habitation, col=site distances + durations.

    Honest UNAVAILABLE when the service is down or ids unknown. Coordinates
    come from the live registry (not hardcoded demo numbers).
    """
    from app.services.spatial_service import _resolve_habitation, _resolve_site
    habs, sites = [], []
    for hid in habitation_ids[:10]:
        h = await _resolve_habitation(session, hid)
        if h:
            habs.append((hid, h[0], h[1]))
    for sid in site_ids[:10]:
        s = await _resolve_site(session, sid)
        if s:
            sites.append((sid, s[0], s[1]))
    if not habs or not sites:
        return {"data_status": "UNAVAILABLE",
                "reason": "Unknown habitation or site id",
                "rows": [], "columns": [], "matrix": None}

    region = region_for_coordinates(habs[0][1], habs[0][2], sites[0][1], sites[0][2])
    if region is None or not graphhopper_base_url(region):
        return {"data_status": "UNAVAILABLE",
                "reason": "No single GraphHopper region covers the requested pair.",
                "rows": [h[0] for h in habs], "columns": [s[0] for s in sites],
                "matrix": None}
    base = graphhopper_base_url(region)
    points = [[lat, lon] for _, lat, lon in habs]
    to_points = [[lat, lon] for _, lat, lon in sites]
    body = {
        "points": points, "to_points": to_points,
        "out_arrays": ["distances", "durations"],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.GRAPHHOPPER_TIMEOUT_S) as client:
            resp = await client.post(f"{base}/matrix", json=body)
        if resp.status_code != 200:
            return {"data_status": "UNAVAILABLE",
                    "reason": f"GraphHopper matrix HTTP {resp.status_code}",
                    "rows": [h[0] for h in habs], "columns": [s[0] for s in sites],
                    "matrix": None}
        data = resp.json()
        distances = data.get("distances") or []
        durations = data.get("durations") or []
        return {
            "data_status": "LIVE",
            "source": "OpenStreetMap + GraphHopper",
            "region": region,
            "rows": [h[0] for h in habs],
            "columns": [s[0] for s in sites],
            "distances_km": [
                [round((d or 0) / 1000.0, 2) for d in row] for row in distances
            ],
            "durations_min": [
                [round((t or 0) / 60.0, 1) for t in row] for row in durations
            ],
            "computed_at": _now_iso(),
        }
    except Exception as exc:
        return {"data_status": "UNAVAILABLE",
                "reason": f"GraphHopper matrix failed: {type(exc).__name__}",
                "rows": [h[0] for h in habs], "columns": [s[0] for s in sites],
                "matrix": None}
