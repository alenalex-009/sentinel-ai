"""OSM vector-layer provider (Phase 6) — Overpass API → GeoJSON.

Sentinel AI pulls OSM *feature* data (roads, buildings, facilities, water)
from the public Overpass API and serves it as provenance-carried GeoJSON on
/api/v1/osm/*. This is FEATURE data; the raster TILES (CARTO / OSM basemap)
are a separate concern handled by the frontend basemap.

Hard rules:
  - A result is labelled LIVE only when Overpass answered on this request;
    CACHED when served from the in-process or PostGIS freshness window;
    UNAVAILABLE-with-reason otherwise. Fallbacks are never labelled LIVE.
  - Every payload keeps `fetched_at` (UTC ISO) and an explicit `source`
    (public Overpass instance URL) + `cache` flag for the UI.
  - Requests are bounded by bbox area, feature count and request time, and
    retried with exponential backoff on transient errors only.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx

from app.core.config import settings
from app.core.regions import REGIONS, coordinates_inside

logger = logging.getLogger(__name__)

# In-process TTL cache: {key: (expires, payload)}. PostGIS is an optional
# second tier (see _persist/_load below); memory keeps the demo honest even
# when the database is down (as on the Render free tier).
_OSM_CACHE: dict = {}

# Overpass QL per category. Queries scope to the bbox and return full geometry
# (`out geom`) so the API never needs a second round trip for coordinates.
_QUERIES: dict = {
    "roads": (
        'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|'
        'unclassified|residential|living_street|service|track|road)$"]'
        "({{bbox}});out geom;"
    ),
    "buildings": 'way["building"]({{bbox}});out geom;',
    "facilities": (
        '(nwr["amenity"]({{bbox}});nwr["healthcare"]({{bbox}});'
        'nwr["emergency"]({{bbox}});nwr["social_facility"]({{bbox}});'
        'nwr["power"="substation"]({{bbox}}););out geom;'
    ),
    "water": (
        '(way["natural"="water"]({{bbox}});way["waterway"]({{bbox}});'
        'way["water"]({{bbox}});nwr["landuse"="reservoir"]({{bbox}}););out geom;'
    ),
}

# Feature "kind" ordering for rendering + the tags that become feature props.
_CATEGORIES = ("roads", "buildings", "facilities", "water")

# Tags copied verbatim onto the GeoJSON feature properties.
_CORE_TAGS = ("name", "highway", "building", "amenity", "healthcare", "emergency",
              "natural", "waterway", "water", "landuse", "power", "social_facility",
              "sport", "religion", "operator")

_BBOX_MSG = (
    "bbox must be minLon,minLat,maxLon,maxLat with minLon<maxLon and "
    "minLat<maxLat (EPSG:4326, decimal degrees)"
)


class OSMError(Exception):
    """Overpass provider error — converted to HTTP 503/502 by the API layer."""


class OSMInvalidRequest(Exception):
    """Bad request from the caller — converted to HTTP 400 by the API layer."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_bbox(raw: Optional[str]) -> tuple:
    """Validate + order a bbox string; raise OSMInvalidRequest on bad input."""
    if not raw:
        raise OSMInvalidRequest(_BBOX_MSG)
    try:
        parts = [float(x) for x in raw.split(",")]
    except ValueError:
        raise OSMInvalidRequest(_BBOX_MSG)
    if len(parts) != 4:
        raise OSMInvalidRequest(_BBOX_MSG)
    min_lon, min_lat, max_lon, max_lat = parts
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise OSMInvalidRequest(_BBOX_MSG)
    area_deg2 = (max_lon - min_lon) * (max_lat - min_lat)
    if area_deg2 > settings.OSM_MAX_BBOX_DEG2:
        raise OSMInvalidRequest(
            f"Requested bbox area {area_deg2:.2f} deg² exceeds the "
            f"{settings.OSM_MAX_BBOX_DEG2} deg² per-request limit (Overpass "
            "public slots reject oversized bounding boxes)."
        )
    return min_lon, min_lat, max_lon, max_lat


def _bbox_ql(bbox: tuple) -> str:
    return f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}"  # Overpass wants south,west,north,east


def _region_for_bbox(bbox: tuple) -> tuple:
    """Human region context for a bbox centre, if it falls in a routing region."""
    center_lat = (bbox[1] + bbox[3]) / 2.0
    center_lon = (bbox[0] + bbox[2]) / 2.0
    for key, r in REGIONS.items():
        inside = (r.dataset_coverage is not None
                  and coordinates_inside(r.dataset_coverage, center_lat, center_lon))
        if inside:
            return key, r.display
    return None, None


def _is_closed_ring(coords: list) -> bool:
    return (
        len(coords) >= 4
        and coords[0][0] == coords[-1][0]
        and coords[0][1] == coords[-1][1]
    )


def _coords_for_element(elem: dict) -> Optional[list]:
    """Coordinate list for a node (lon,lat) or way/relation with `geometry`."""
    if elem.get("type") == "node":
        if "lat" in elem and "lon" in elem:
            return [[elem["lon"], elem["lat"]]]
        return None
    geom = elem.get("geometry")
    if not geom:
        return None
    return [[float(g["lon"]), float(g["lat"])] for g in geom]


def _geometry_for_element(elem: dict, coords: Optional[list]) -> Optional[dict]:
    """Best-effort GeoJSON geometry: Polygon for closed areas, LineString else."""
    if not coords:
        return None
    if len(coords) == 1:
        return {"type": "Point", "coordinates": coords[0]}
    if _is_closed_ring(coords):
        return {"type": "Polygon", "coordinates": [coords]}
    return {"type": "LineString", "coordinates": coords}


def _props_for_element(elem: dict, category: str) -> dict:
    tags = elem.get("tags") or {}
    kind = "other"
    for key in ("highway", "building", "amenity", "healthcare", "emergency",
                "natural", "waterway", "water", "landuse", "power",
                "social_facility", "sport", "religion", "operator"):
        if tags.get(key):
            value = tags[key]
            kind = key if value in ("yes", "no") else value
            break
    props = {
        "osm_id": elem.get("id"),
        "osm_type": elem.get("type"),
        "category": category,
        "kind": kind,
    }
    for k in _CORE_TAGS:
        if tags.get(k):
            props[k] = tags[k]
    if len(props["kind"]) > 40:
        props["kind"] = props["kind"][:40]
    return props


def build_feature_collection(elements: list, category: str) -> dict:
    """Normalize raw Overpass elements → GeoJSON FeatureCollection."""
    features = []
    for elem in elements:
        coords = _coords_for_element(elem)
        geometry = _geometry_for_element(elem, coords)
        if not geometry:
            continue
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": _props_for_element(elem, category),
        })
        if len(features) >= settings.OSM_MAX_FEATURES:
            break
    return {"type": "FeatureCollection", "features": features}


def _cache_key(category: str, bbox_sig: str) -> str:
    return f"{category}|{bbox_sig}"


def _cache_get(key: str) -> Optional[dict]:
    entry = _OSM_CACHE.get(key)
    if not entry:
        return None
    expires, payload = entry
    if time.time() > expires:
        _OSM_CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: dict) -> None:
    _OSM_CACHE[key] = (time.time() + settings.OSM_CACHE_TTL_S, payload)


def _build_overpass_payload(category: str, bbox: tuple, features: dict) -> dict:
    region_key, region_label = _region_for_bbox(bbox)
    return {
        "category": category,
        "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
        "source": settings.OSM_OVERPASS_URL,
        "fetched_at": _now_iso(),
        "cache": False,
        "data_status": "LIVE",
        "count": len(features.get("features", [])),
        "region": {
            "key": region_key,
            "display": region_label,
            "dataset_status": REGIONS[region_key].dataset_status if region_key else None,
        },
        "feature_collection": features,
    }


async def _overpass_urls() -> list:
    primary = settings.OSM_OVERPASS_URL.rstrip("/")
    fallbacks = [
        u.rstrip("/")
        for u in settings.OSM_OVERPASS_FALLBACK_URLS.split(",") if u.strip()
    ]
    return [primary, *fallbacks]


async def _pick_overpass_url() -> str:
    """First responsive mirror (fast /api/status probe, 6s each).

    Keeps failover quick when the primary flaps behind its gateway: a dead
    mirror costs ~6s, not a full query timeout. If nothing responds the
    primary is still tried (your configured URL is the safest bet for a
    genuine query attempt).
    """
    headers = {"User-Agent": settings.OSM_USER_AGENT, "Accept": "application/json"}
    urls = await _overpass_urls()
    for url in urls:
        try:
            status_url = (
                url[:-len("/api/interpreter")] + "/api/status"
                if url.endswith("/api/interpreter") else url + "/status"
            )
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(status_url, headers=headers)
            if resp.status_code == 200:
                return url
        except Exception:
            continue
    return urls[0]


async def _query_overpass(ql: str, url: Optional[str] = None) -> list:
    """POST a QL query to Overpass with mirror fallback + retry/backoff.

    The primary endpoint (overpass-api.de) intermittently flaps behind a 504
    gateway; each mirror in the chain is tried in order, with per-mirror
    exponential backoff, before an honest OSMError is raised.

    Raises OSMError on transport failure or a query-level Overpass error
    (Overpass answers 400/200-with-`remark` for bad queries — those are raised
    immediately, they are not retryable).
    """
    headers = {
        "User-Agent": settings.OSM_USER_AGENT,
        "Accept": "application/json",
    }
    last_exc: Optional[Exception] = None
    if url:
        candidates = [url]                      # explicit mirror (tests / retries)
    else:
        url = await _pick_overpass_url()         # fast responsive probe
        candidates = [url] + [
            u for u in await _overpass_urls() if u != url
        ]
    for url in candidates:
        for attempt in range(1, settings.OSM_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.OSM_TIMEOUT_S) as client:
                    resp = await client.post(
                        url, data={"data": ql}, headers=headers,
                    )
            except Exception as exc:
                last_exc = OSMError(
                    f"Overpass transport error: {type(exc).__name__}: {exc}"
                )
                if attempt < settings.OSM_ATTEMPTS:
                    delay = settings.OSM_BACKOFF_BASE_S * (2 ** (attempt - 1))
                    logger.warning(
                        f"[osm] {url} attempt {attempt}/{settings.OSM_ATTEMPTS} "
                        f"transport error: {type(exc).__name__}; retrying in {delay}s"
                    )
                    await _sleep(delay)
                    continue
                break

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    last_exc = OSMError(
                        f"Overpass returned non-JSON response: {resp.text[:120]!r}"
                    )
                    if attempt < settings.OSM_ATTEMPTS:
                        delay = settings.OSM_BACKOFF_BASE_S * (2 ** (attempt - 1))
                        logger.warning(
                            f"[osm] {url} attempt {attempt}/{settings.OSM_ATTEMPTS} "
                            f"non-JSON response (gateway busy?); retrying in {delay}s"
                        )
                        await _sleep(delay)
                        continue
                    break
                if data.get("remark"):
                    raise OSMError(
                        f"Overpass query rejected: {data['remark'][:400]}"
                    )
                return data.get("elements") or []
            if resp.status_code in (429, 500, 502, 503, 504):
                # busy limiter / gateway — retry this mirror, then try the next.
                last_exc = OSMError(
                    f"Overpass returned HTTP {resp.status_code} "
                    f"({resp.text[:80].strip()!r})"
                )
                if attempt < settings.OSM_ATTEMPTS:
                    delay = settings.OSM_BACKOFF_BASE_S * (2 ** (attempt - 1))
                    logger.warning(
                        f"[osm] {url} attempt {attempt}/{settings.OSM_ATTEMPTS} "
                        f"HTTP {resp.status_code}; retrying in {delay}s"
                    )
                    await _sleep(delay)
                    continue
                break
            raise OSMError(
                f"Overpass returned HTTP {resp.status_code}: {resp.text[:200]}"
            )

    if last_exc is None:
        last_exc = OSMError("Overpass returned no recoverable response")
    raise last_exc


async def _sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


def _as_datetime(value) -> Optional["datetime"]:
    """ISO string → naive/aware datetime for asyncpg params."""
    from datetime import datetime as _dt
    if value is None:
        return None
    if isinstance(value, _dt):
        return value
    try:
        return _dt.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


# ── PostGIS tier (optional; silently degrades when DB is down) ─────────────

def _table_for(category: str) -> str:
    return {
        "roads": "osm_roads",
        "buildings": "osm_buildings",
        "facilities": "osm_facilities",
        "water": "osm_water_features",
    }[category]


async def persist_features(session, category: str, payload: dict) -> bool:
    """Write-through Live results into the PostGIS osm_* tables.

    Returns False (no raise) whenever the database is unavailable — the
    in-process cache above keeps the demo working without PostGIS.
    """
    table = _table_for(category)
    fc = payload.get("feature_collection", {}).get("features", [])
    if not fc:
        return False
    try:
        from sqlalchemy import text
        sql = text(
            f"INSERT INTO {table} (osm_type, osm_id, name, tags, category, geom, fetched_at) "
            "VALUES (:osm_type,:osm_id,:name,CAST(:tags AS jsonb),:category,"
            "ST_SetSRID(ST_GeomFromGeoJSON(:geom),4326),:fetched_at) "
            "ON CONFLICT (osm_type, osm_id) DO NOTHING"
        )
        rows = 0
        for f in fc:
            props = f.get("properties", {})
            await session.execute(
                sql,
                {
                    "osm_type": props.get("osm_type"),
                    "osm_id": props.get("osm_id"),
                    "name": props.get("name"),
                    "tags": json.dumps(props),
                    "category": category,
                    "geom": json.dumps(f.get("geometry")),
                    "fetched_at": _as_datetime(payload.get("fetched_at")),
                },
            )
            rows += 1
        await session.commit()
        return rows > 0
    except Exception as exc:
        logger.warning(f"[osm] PostGIS write-through skipped: {type(exc).__name__}")
        try:
            await session.rollback()
        except Exception:
            pass
        return False


async def load_from_db(session, category: str, bbox: tuple) -> Optional[dict]:
    """Read a fresh CACHED layer from PostGIS within the TTL window."""
    table = _table_for(category)
    sql = (
        f"SELECT osm_type, osm_id, name, tags, category, ST_AsGeoJSON(geom) AS gj, fetched_at "
        f"FROM {table} "
        "WHERE geom && ST_MakeEnvelope(:min_lon,:min_lat,:max_lon,:max_lat,4326)"
        "  AND fetched_at > now() - make_interval(secs => :ttl_s) "
        "ORDER BY fetched_at DESC"
    )
    try:
        from sqlalchemy import text
        result = await session.execute(
            text(sql),
            {"min_lon": bbox[0], "min_lat": bbox[1],
             "max_lon": bbox[2], "max_lat": bbox[3],
             "ttl_s": settings.OSM_CACHE_TTL_S},
        )
        rows = result.fetchall()
        if not rows:
            return None
        features = []
        for osm_type, osm_id, name, tags, cat, gj, fetched_at in rows:
            geometry = json.loads(gj)
            features.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": {"osm_id": osm_id, "osm_type": osm_type, "name": name,
                               "category": cat, "kind": (tags or {}).get("kind", "other"),
                               **({k: v for k, v in (tags or {}).items() if k != "kind"})},
            })
        payload = {
            "category": category,
            "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
            "source": f"postgis.{table}",
            "fetched_at": fetched_at.isoformat(),
            "cache": True,
            "data_status": "CACHED",
            "count": len(features),
            "feature_collection": {"type": "FeatureCollection", "features": features},
            "_cache_tier": "postgis",
        }
        return payload
    except Exception as exc:
        logger.warning(f"[osm] PostGIS read skipped: {type(exc).__name__}")
        return None


async def get_osm_features(
    session,
    category: str,
    bbox: tuple,
    refresh: bool = False,
) -> dict:
    """Public entry point — CATEGORY features for BBBox.

    Tier order: in-process TTL → PostGIS fresh rows → live Overpass (LIVE,
    write-through to PostGIS when available).
    """
    if category not in _CATEGORIES:
        raise OSMInvalidRequest(
            f"Unknown OSM category '{category}' — use one of {list(_CATEGORIES)}"
        )
    sig = ",".join(f"{v:.5f}" for v in bbox)
    key = _cache_key(category, sig)

    if not refresh:
        cached = _cache_get(key)
        if cached is not None:
            out = dict(cached)  # copy — never mutate the canonical cache entry
            out["cache"] = True
            out["data_status"] = "CACHED"
            out["_cache_tier"] = "memory"
            return out
        db_payload = await load_from_db(session, category, bbox)
        if db_payload is not None:
            _cache_set(key, db_payload)
            return db_payload

    ql = (
        f"[out:json][timeout:{int(settings.OSM_TIMEOUT_S)}];"
        + _QUERIES[category].replace("{{bbox}}", _bbox_ql(bbox))
    )
    elements = await _query_overpass(ql)
    fc = build_feature_collection(elements, category)
    payload = _build_overpass_payload(category, bbox, fc)
    _cache_set(key, payload)
    payload["persisted"] = await persist_features(session, category, payload)
    return payload


async def get_all_features(session, bbox: tuple, refresh: bool = False) -> dict:
    """Union layer across all categories (used by /osm/features & /osm/geojson)."""
    sub = []
    for cat in _CATEGORIES:
        p = await get_osm_features(session, cat, bbox, refresh=refresh)
        sub.append(p)
    fc = {"type": "FeatureCollection",
          "features": [f for p in sub for f in
                       p["feature_collection"].get("features", [])]}
    provenance = {
        "category": "features",
        "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
        "source": settings.OSM_OVERPASS_URL,
        "fetched_at": _now_iso(),
        "cache": any(p.get("cache") for p in sub),
        "data_status": "CACHED" if any(p.get("cache") for p in sub) else "LIVE",
        "count": len(fc.get("features", [])),
        "categories": {cat: p["count"] for cat, p in zip(_CATEGORIES, sub)},
        "feature_collection": fc,
    }
    for p in sub:
        if p.get("region", {}).get("key"):
            provenance["region"] = p["region"]
            break
    return provenance