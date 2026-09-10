"""PostGIS spatial analysis service for Sentinel AI (Phase 3).

Real spatial operations are performed by PostGIS against the seeded geometry:
  - habitations.geom / candidate_sites.geom   (GEOMETRY(POINT, 4326))
Every result carries provenance (method, classification, data_status) and
falls back to deterministic haversine math on demo coordinates only when the
database is unavailable or the target row is absent from PostGIS.

Only points exist in the seed dataset — no boundary/hazard polygons are
invented anywhere in this module.
"""

import json
import math
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services import demo_data
from app.services.db_service import _safe_query

# Canonical demo universe (used for fallback coordinates and 404 semantics).
_DEMO_HABITATIONS = demo_data.get_habitation_list("idukki")["habitations"]
_DEMO_SITES = demo_data.get_candidate_sites("munnar-central")["sites"]

_DEMO_HAB_BY_ID = {h["id"]: h for h in _DEMO_HABITATIONS}
_DEMO_SITE_BY_ID = {s["id"]: s for s in _DEMO_SITES}

_SRID = 4326
_DISTANCE_UNIT = "m"

_GEOJSON_NOTE = (
    "Point geometry only — the seed dataset contains no boundary, hazard, "
    "debris/runout, or muster-point polygons. No such geometry is fabricated."
)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (WGS84 sphere approximation)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _round1(value: float) -> float:
    return round(float(value), 1)


# ─── Target resolution (PostGIS first, demo fallback) ─────────────────────────

async def _resolve_habitation(session: AsyncSession, habitation_id: str):
    """Return (lat, lon, source) or None when the id is unknown everywhere."""
    result = await _safe_query(
        session,
        "SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM habitations WHERE id = :id",
        {"id": habitation_id},
    )
    db_ok = result is not None
    if db_ok:
        row = result.mappings().first()
        if row:
            return float(row["lat"]), float(row["lon"]), "postgis"
    demo = _DEMO_HAB_BY_ID.get(habitation_id)
    if demo:
        return float(demo["latitude"]), float(demo["longitude"]), "demo"
    return None


async def _resolve_site(session: AsyncSession, site_id: str):
    """Return (lat, lon, source) or None when the id is unknown everywhere."""
    result = await _safe_query(
        session,
        "SELECT ST_Y(geom) AS lat, ST_X(geom) AS lon FROM candidate_sites WHERE id = :id",
        {"id": site_id},
    )
    db_ok = result is not None
    if db_ok:
        row = result.mappings().first()
        if row:
            return float(row["lat"]), float(row["lon"]), "postgis"
    demo = _DEMO_SITE_BY_ID.get(site_id)
    if demo:
        return float(demo["latitude"]), float(demo["longitude"]), "demo"
    return None


# ─── GeoJSON endpoints ────────────────────────────────────────────────────────

async def get_habitation_geojson(session: AsyncSession, district_id: str) -> dict:
    """GeoJSON FeatureCollection of habitation points, sourced from PostGIS."""
    result = await _safe_query(
        session,
        """
        SELECT h.id, h.name, h.ward, h.taluk, h.district_id,
               h.population, h.households, h.data_status,
               r.current_score, r.baseline_score,
               (r.current_score - r.baseline_score) AS risk_change,
               rp.priority,
               ST_AsGeoJSON(h.geom) AS geojson
        FROM habitations h
        LEFT JOIN (
            SELECT DISTINCT ON (habitation_id) habitation_id, current_score, baseline_score
            FROM risk_scores
            ORDER BY habitation_id, computed_at DESC
        ) r ON r.habitation_id = h.id
        LEFT JOIN relocation_priorities rp ON rp.habitation_id = h.id
        WHERE h.district_id = :district_id
        ORDER BY r.current_score DESC NULLS LAST
        """,
        {"district_id": district_id},
    )
    if result is not None:
        rows = result.mappings().all()
        if rows:
            features = []
            for row in rows:
                geometry = json.loads(row["geojson"])
                r = dict(row)
                features.append({
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "id": r["id"],
                        "name": r["name"],
                        "ward": r.get("ward"),
                        "taluk": r.get("taluk"),
                        "district_id": r.get("district_id"),
                        "population": r.get("population"),
                        "households": r.get("households"),
                        "risk_score": float(r["current_score"]) if r.get("current_score") is not None else None,
                        "risk_change": float(r["risk_change"]) if r.get("risk_change") is not None else 0.0,
                        "priority": r.get("priority"),
                        "data_status": r.get("data_status") or "DEMO",
                    },
                })
            return {
                "type": "FeatureCollection",
                "features": features,
                "data_status": "DEMO",
                "district_id": district_id,
                "_source": "postgis",
                "geometry_source": "PostGIS habitations.geom (GEOMETRY(POINT, 4326))",
                "geometry_type": "Point",
                "srid": _SRID,
                "note": _GEOJSON_NOTE,
            }

    # Demo fallback (database unavailable or empty)
    fc = demo_data.get_habitations_geojson(district_id)
    fc["_source"] = "demo_fallback"
    fc["district_id"] = district_id
    fc["geometry_source"] = "demo_data coordinates (DEMO — database unavailable)"
    fc["geometry_type"] = "Point"
    fc["srid"] = _SRID
    fc["note"] = _GEOJSON_NOTE
    return fc


async def get_candidate_sites_geojson(
    session: AsyncSession, district_id: str = "idukki"
) -> dict:
    """GeoJSON FeatureCollection of technically screened candidate sites."""
    result = await _safe_query(
        session,
        """
        SELECT cs.id, cs.name, cs.district_id, cs.suitability_score,
               cs.safe_capacity, cs.hard_constraints_passed, cs.data_status,
               ca.c_safe, ca.bottleneck,
               ST_AsGeoJSON(cs.geom) AS geojson
        FROM candidate_sites cs
        LEFT JOIN capacity_assessments ca ON ca.site_id = cs.id
        WHERE cs.district_id = :district_id
        ORDER BY cs.suitability_score DESC
        """,
        {"district_id": district_id},
    )
    if result is not None:
        rows = result.mappings().all()
        if rows:
            features = []
            for row in rows:
                geometry = json.loads(row["geojson"])
                r = dict(row)
                features.append({
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "id": r["id"],
                        "name": r["name"],
                        "district_id": r.get("district_id"),
                        "suitability_score": float(r["suitability_score"]) if r.get("suitability_score") is not None else None,
                        "safe_capacity": r.get("safe_capacity"),
                        "c_safe": r.get("c_safe"),
                        "bottleneck": r.get("bottleneck"),
                        "hard_constraints_passed": r.get("hard_constraints_passed"),
                        "data_status": r.get("data_status") or "DEMO",
                    },
                })
            return {
                "type": "FeatureCollection",
                "features": features,
                "data_status": "DEMO",
                "district_id": district_id,
                "_source": "postgis",
                "geometry_source": "PostGIS candidate_sites.geom (GEOMETRY(POINT, 4326))",
                "geometry_type": "Point",
                "srid": _SRID,
                "approval_status_note": (
                    "Technically Screened Candidate points only — NOT "
                    "government-approved or legally acquired land. Official "
                    "approval is required before any relocation."
                ),
                "note": _GEOJSON_NOTE,
            }

    # Demo fallback
    features = []
    for s in _DEMO_SITES:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s["longitude"], s["latitude"]]},
            "properties": {
                "id": s["id"],
                "name": s["name"],
                "suitability_score": s["suitability_score"],
                "safe_capacity": s["safe_capacity"],
                "c_safe": s["safe_capacity"],
                "bottleneck": s["bottleneck_dimension"],
                "hard_constraints_passed": s["hard_constraints_passed"],
                "data_status": s["data_status"],
            },
        })
    return {
        "type": "FeatureCollection",
        "features": features,
        "data_status": "DEMO",
        "district_id": district_id,
        "_source": "demo_fallback",
        "geometry_source": "demo_data coordinates (DEMO — database unavailable)",
        "geometry_type": "Point",
        "srid": _SRID,
        "approval_status_note": (
            "Technically Screened Candidate points only — NOT government-approved "
            "or legally acquired land. Official approval is required before any relocation."
        ),
        "note": _GEOJSON_NOTE,
    }


# ─── Distance / proximity ─────────────────────────────────────────────────────

async def get_spatial_distance(
    session: AsyncSession, habitation_id: str, site_id: str
) -> Optional[dict]:
    """Geodesic straight-line distance habitation → candidate site.

    Returns None when either id is unknown (caller raises HTTP 404).
    Deterministic: same inputs always produce the same output.
    """
    hab = await _resolve_habitation(session, habitation_id)
    site = await _resolve_site(session, site_id)
    if hab is None or site is None:
        return None

    hab_lat, hab_lon, hab_src = hab
    site_lat, site_lon, site_src = site

    if hab_src == "postgis" and site_src == "postgis":
        result = await _safe_query(
            session,
            """
            SELECT ST_Distance(h.geom::geography, s.geom::geography) AS dist_m
            FROM habitations h CROSS JOIN candidate_sites s
            WHERE h.id = :hid AND s.id = :sid
            """,
            {"hid": habitation_id, "sid": site_id},
        )
        if result is not None:
            row = result.mappings().first()
            if row and row["dist_m"] is not None:
                distance_m = _round1(row["dist_m"])
                method = "PostGIS ST_Distance(geography) — WGS84 geodesic (straight-line)"
                source_geometry = (
                    "PostGIS habitations.geom / candidate_sites.geom (POINT, EPSG:4326)"
                )
                _source = "postgis"
                distance_m = _round1(row["dist_m"])
                return _distance_response(
                    habitation_id, site_id, distance_m, method, source_geometry, _source
                )

    # Fallback: deterministic haversine on demo coordinates.
    distance_m = _round1(_haversine_m(hab_lat, hab_lon, site_lat, site_lon))
    method = "haversine great-circle (fallback — demo coordinates, database unavailable)"
    source_geometry = "demo_data coordinates (DEMO)"
    return _distance_response(
        habitation_id, site_id, distance_m, method, source_geometry, "demo_fallback"
    )


def _distance_response(habitation_id: str, site_id: str, distance_m: float,
                       method: str, source_geometry: str, _source: str) -> dict:
    return {
        "habitation_id": habitation_id,
        "site_id": site_id,
        "distance_m": distance_m,
        "distance_km": round(distance_m / 1000.0, 2),
        "unit": _DISTANCE_UNIT,
        "classification": "DERIVED",
        "method": method,
        "distance_type": "straight-line geodesic",
        "source_geometry": source_geometry,
        "note": (
            "Straight-line/geodesic distance only — NOT road travel distance. "
            "GraphHopper routing is not integrated."
        ),
        "data_status": "DEMO",
        "_source": _source,
    }


async def get_proximate_sites(
    session: AsyncSession, habitation_id: str, radius_m: float
) -> Optional[dict]:
    """Candidate sites within a deterministic radius of a habitation."""
    hab = await _resolve_habitation(session, habitation_id)
    if hab is None:
        return None
    hab_lat, hab_lon, hab_src = hab

    if hab_src == "postgis":
        result = await _safe_query(
            session,
            """
            SELECT s.id, s.name, ca.c_safe, ca.bottleneck,
                   ST_Distance(h.geom::geography, s.geom::geography) AS dist_m
            FROM candidate_sites s
            CROSS JOIN habitations h
            LEFT JOIN capacity_assessments ca ON ca.site_id = s.id
            WHERE h.id = :hid
              AND ST_DWithin(h.geom::geography, s.geom::geography, :radius)
            ORDER BY dist_m
            """,
            {"hid": habitation_id, "radius": radius_m},
        )
        if result is not None:
            rows = result.mappings().all()
            results = [
                {
                    "site_id": row["id"],
                    "site_name": row["name"],
                    "distance_m": _round1(row["dist_m"]),
                    "distance_km": round(float(row["dist_m"]) / 1000.0, 2),
                    "c_safe": row.get("c_safe"),
                    "bottleneck": row.get("bottleneck"),
                    "within_radius": True,
                }
                for row in rows
            ]
            method = "PostGIS ST_DWithin(geography) + ST_Distance(geography)"
            return {
                "habitation_id": habitation_id,
                "radius_m": radius_m,
                "method": method,
                "threshold_note": "Deterministic configurable radius threshold.",
                "results": results,
                "data_status": "DEMO",
                "_source": "postgis",
            }

    # Fallback: haversine over the demo candidate universe.
    results = []
    for s in _DEMO_SITES:
        d = _haversine_m(hab_lat, hab_lon, s["latitude"], s["longitude"])
        if d <= radius_m:
            results.append({
                "site_id": s["id"],
                "site_name": s["name"],
                "distance_m": _round1(d),
                "distance_km": round(d / 1000.0, 2),
                "c_safe": s["safe_capacity"],
                "bottleneck": s["bottleneck_dimension"],
                "within_radius": True,
            })
    results.sort(key=lambda x: x["distance_m"])
    return {
        "habitation_id": habitation_id,
        "radius_m": radius_m,
        "method": "haversine great-circle (fallback — demo coordinates, database unavailable)",
        "threshold_note": "Deterministic configurable radius threshold.",
        "results": results,
        "data_status": "DEMO",
        "_source": "demo_fallback",
    }


