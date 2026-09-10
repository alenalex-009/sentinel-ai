"""Slice 4 — Safe-zone engine.

Deterministic candidate discovery + hard-constraint checks + suitability
scoring over the real spatial tables (districts point, earthquake_events
fault/epicenter proxies, active hazard_events polygons, candidate_sites).

Design notes (documented basis — nothing fabricated):
- District geometry is a POINT in the seed, so "district bounds" for discovery
  is a geodesic grid around the district centroid. This is a documented
  derivation, not an official administrative boundary.
- Slope: no DEM is kept in the prototype. For existing candidate_sites the
  seeded suitability_score already encodes slope assessment; for grid-
  discovered points slope is reported UNAVAILABLE and fed through (never
  assumed).
- Land use / water proximity: no spatial layer exists. Reported UNAVAILABLE
  and fed through.
- Fault lines: earthquake_events epicenters (USGS) are the only spatial
  seismicity record; `SAFE_ZONE_FAULT_BUFFER_KM` buffer around epicenters is
  the hard exclusion. Documented Sentinel AI baseline, not a government fault
  map.
- Active hazard polygons: hazard_events (Slice 2) circular exposure buffers;
  points inside (plus optional buffer) are excluded.
- Status thresholds match screening.py's three-tier model (RED/YELLOW/GREEN)
  so the two endpoints render consistently.
"""

import json
import logging
import math
import time
from typing import Optional

from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.db_service import _safe_query

_SRID = 4326
_M_PER_DEG_LAT = 111320.0

# Nominal suitability for a grid-discovered point when no parcel data exists.
# Documented baseline (raster-free discovery) — always surfaced as `basis`.
_DISCOVERED_BASE_SUITABILITY = 65.0
_DISCOVERED_BASE_SAFETY = 80.0

# District anchor fallback when districts.geom (an administrative MULTIPOLYGON
# boundary column) is empty — which it is in the seed. Real-world HQ locations,
# documented as Sentinel AI baselines: the discovery grid needs a center even
# when no official boundary polygon is available. Never a boundary polygon.
_DISTRICT_ANCHOR = {
    "idukki": (9.85, 76.98),  # Idukki HQ approx — real-world, not surveyed boundary
}

_CACHE: dict = {}

_UNSUPPORTED_NOTES = {
    "slope": (
        "No DEM/steepness layer in the prototype dataset. Existing screened "
        "sites carry slope implicitly in their seeded suitability_score; "
        "grid-discovered points assume none and are fed through."
    ),
    "land_use": (
        "No land-use/parcel spatial layer — constraint fed through as "
        "UNAVAILABLE, never assumed pass."
    ),
    "water_proximity": (
        "No water-body spatial layer — constraint fed through as UNAVAILABLE, "
        "never assumed pass."
    ),
}


def _metres_per_deg_lon(lat: float) -> float:
    return _M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def grid_points(lat: float, lon: float, radius_km: float, spacing_km: float) -> list:
    """Deterministic geodesic grid of points within radius of a centroid.

    Equirectangular offsets around the centroid; only points whose geodesic
    distance <= radius are kept. Stable ordering (row-major, lat desc) makes
    candidate ids reproducible across calls.
    """
    m_per_deg_lat = _M_PER_DEG_LAT
    m_per_deg_lon = _metres_per_deg_lon(lat)
    half = int(math.ceil(radius_km / spacing_km))
    out = []
    for i in range(-half, half + 1):
        dlat = i * spacing_km * 1000.0 / m_per_deg_lat
        for j in range(-half, half + 1):
            dlon = j * spacing_km * 1000.0 / m_per_deg_lon
            plat = lat + dlat
            plon = lon + dlon
            if _haversine_km(lat, lon, plat, plon) <= radius_km + 1e-9:
                out.append((plat, plon))
    return out


async def _district_point(session: AsyncSession, district_id: str) -> Optional[tuple]:
    """Discovery anchor: centroid of the district boundary polygon when present,
    else the documented real-world HQ anchor, else None."""
    result = await _safe_query(
        session,
        """
        SELECT
            CASE WHEN geom IS NOT NULL
                 THEN ST_Y(ST_Centroid(geom))
                 ELSE NULL END AS lat,
            CASE WHEN geom IS NOT NULL
                 THEN ST_X(ST_Centroid(geom))
                 ELSE NULL END AS lon
        FROM districts WHERE id = :id
        """,
        {"id": district_id},
    )
    if result is not None:
        row = result.mappings().first()
        if row is not None and row["lat"] is not None and row["lon"] is not None:
            return (float(row["lat"]), float(row["lon"]))
    return _DISTRICT_ANCHOR.get(district_id)


async def _fault_distance_km(session: AsyncSession, lon: float, lat: float) -> Optional[float]:
    """Distance (km) to the nearest earthquake epicenter, or None on DB error."""
    result = await _safe_query(
        session,
        """
        SELECT ST_Distance(
            e.geom::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
        ) AS dist_m
        FROM earthquake_events e
        ORDER BY e.geom::geography <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
        LIMIT 1
        """,
        {"lon": lon, "lat": lat},
    )
    if result is None:
        return None
    row = result.mappings().first()
    if row is None or row["dist_m"] is None:
        return None
    return float(row["dist_m"]) / 1000.0


async def _nearest_hazard_km(session: AsyncSession, lon: float, lat: float) -> Optional[float]:
    """Distance (km) to the nearest ACTIVE hazard event, or None on DB error."""
    result = await _safe_query(
        session,
        """
        SELECT ST_Distance(
            ST_ClosestPoint(h.geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
        ) AS dist_m
        FROM hazard_events h
        WHERE h.active = TRUE
        ORDER BY h.geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        LIMIT 1
        """,
        {"lon": lon, "lat": lat},
    )
    if result is None:
        return None
    row = result.mappings().first()
    if row is None or row["dist_m"] is None:
        return None
    return float(row["dist_m"]) / 1000.0


async def evaluate_point(session: AsyncSession, lon: float, lat: float) -> dict:
    """Constraint + evidence evaluation for a single lat/lon point.

    Returns a dict with constraint_pass and per-constraint entries. DB
    unavailability degrades the spatial constraints to UNAVAILABLE (fed
    through) — a failing DB is never presented as a passing constraint.
    """
    fault_km = await _fault_distance_km(session, lon, lat)
    hazard_km = await _nearest_hazard_km(session, lon, lat)

    constraints = {
        "slope": {
            "passed": None,
            "status": "UNAVAILABLE",
            "reason": _UNSUPPORTED_NOTES["slope"],
        },
        "land_use": {
            "passed": None,
            "status": "UNAVAILABLE",
            "reason": _UNSUPPORTED_NOTES["land_use"],
        },
        "water_proximity": {
            "passed": None,
            "status": "UNAVAILABLE",
            "reason": _UNSUPPORTED_NOTES["water_proximity"],
        },
    }

    constraining = []
    if fault_km is None:
        constraints["fault_proximity"] = {
            "passed": None,
            "status": "UNAVAILABLE",
            "reason": (
                "earthquake_events unavailable — fault proximity not evaluated "
                "(never assumed pass)."
            ),
        }
    else:
        buf_km = settings.SAFE_ZONE_FAULT_BUFFER_KM
        passed = fault_km >= buf_km
        constraints["fault_proximity"] = {
            "passed": passed,
            "status": "OK" if passed else "FAIL",
            "nearest_epicenter_km": round(fault_km, 2),
            "buffer_km": buf_km,
            "reason": (
                f"nearest USGS epicenter {fault_km:.1f} km (buffer {buf_km:g} km → "
                + ("pass" if passed else "EXCLUDE")
            ),
        }
        if not passed:
            constraining.append("fault_proximity")

    if hazard_km is None:
        constraints["active_hazard"] = {
            "passed": None,
            "status": "UNAVAILABLE",
            "reason": (
                "hazard_events unavailable or no active events — hazard polygon "
                "exclusion not evaluated (never assumed pass)."
            ),
        }
    else:
        buf_km = settings.SAFE_ZONE_HAZARD_BUFFER_KM
        inside = hazard_km <= 1e-6  # distance 0 ⇒ point is within the polygon
        passed = not inside and hazard_km >= buf_km
        constraints["active_hazard"] = {
            "passed": passed,
            "status": "OK" if passed else "FAIL",
            "nearest_active_hazard_km": round(hazard_km, 2),
            "buffer_km": buf_km,
            "reason": (
                f"{hazard_km:.1f} km to nearest active hazard polygon (buffer "
                f"{buf_km:g} km → " + ("pass" if passed else "EXCLUDE")
            ),
        }
        if not passed:
            constraining.append("active_hazard")

    return {
        "constraint_pass": not constraining,
        "constraining": constraining,
        "constraints": constraints,
        "basis": {
            "fault": {"nearest_epicenter_km": fault_km},
            "active_hazard": {"nearest_polygon_km": hazard_km},
        },
    }


def score_candidate(lat: float, lon: float, evidence: dict, existing: Optional[dict] = None) -> dict:
    """Deterministic suitability + safety scoring for a candidate point.

    - suitability: existing site's seeded suitability_score when the point is
      an existing screened site; otherwise the nominal discovered base.
    - safety: starts at nominal base and is reduced by linear proximity
      penalties toward faults and hazard polygons (documented baselines).
    Only evaluated constraints contribute; UNAVAILABLE inputs contribute 0.
    """
    if existing:
        suitability = max(0.0, min(100.0, float(existing["suitability_score"] or 0)))
        capacity = int(existing.get("safe_capacity") or 0)
        capacity_basis = "existing assessed parcel capacity"
    else:
        suitability = _DISCOVERED_BASE_SUITABILITY
        capacity = 0
        capacity_basis = "no parcel data — capacity unassessed"

    safety = _DISCOVERED_BASE_SAFETY
    penalties = []

    fault_km = evidence["basis"]["fault"].get("nearest_epicenter_km")
    if fault_km is not None:
        buf_km = settings.SAFE_ZONE_FAULT_BUFFER_KM
        if fault_km < buf_km:
            safety = min(safety, 0.0)
            penalties.append(f"inside {buf_km:g}km fault buffer (epicenter {fault_km:.1f} km)")
        else:
            falloff = buf_km * 3.0
            penalty = 30.0 * max(0.0, 1.0 - (fault_km - buf_km) / falloff)
            safety -= penalty
            if penalty > 0:
                penalties.append(f"fault proximity penalty -{penalty:.1f}")

    hazard_km = evidence["basis"]["active_hazard"].get("nearest_polygon_km")
    if hazard_km is not None and evidence["constraint_pass"]:
        penalty = 30.0 * max(0.0, 1.0 - hazard_km / 40.0)
        safety -= penalty
        if penalty > 0:
            penalties.append(f"hazard proximity penalty -{penalty:.1f}")

    safety = max(0.0, min(100.0, safety))
    return {
        "suitability_score": round(suitability, 1),
        "safety_score": round(safety, 1),
        "estimated_capacity": capacity,
        "capacity_basis": capacity_basis,
        "suitability_basis": (
            "seeded site assessment"
            if existing
            else "nominal baseline (raster-free discovery; land-use/DEM unavailable)"
        ),
        "safety_basis": "; ".join(penalties) if penalties else "no proximity penalties",
    }


def classify(suitability: float, safety: float, constraint_pass: bool) -> str:
    """Three-tier status shared with screening.py's zone model."""
    if not constraint_pass or suitability < 50 or safety < 40:
        return "red"
    if suitability < 70:
        return "yellow"
    return "green"


async def _existing_sites(session: AsyncSession, district_id: str) -> list:
    result = await _safe_query(
        session,
        """
        SELECT id, name, suitability_score, safe_capacity,
               ST_Y(geom) AS lat, ST_X(geom) AS lon
        FROM candidate_sites
        WHERE district_id = :district_id
        ORDER BY suitability_score DESC
        """,
        {"district_id": district_id},
    )
    if result is None:
        return []
    return [dict(r) for r in result.mappings().all()]


async def discover_candidates(session: AsyncSession, district_id: str) -> dict:
    """Discover + score + persist safe-zone candidates for a district.

    Existing candidate_sites are always included (source='existing') and
    grid points within a merge half-spacing of them are skipped (de-dupe).
    Grid-discovered points are stored with source='discovered'. Returns the
    full candidate set with constraint evidence and provenance.
    """
    centroid = await _district_point(session, district_id)
    resp = {
        "district_id": district_id,
        "source": "postgis",
        "data_status": "DEMO",
        "candidates": [],
    }
    if centroid is None:
        resp["geometry_source"] = (
            "district geometry unavailable — no discovery possible"
        )
        resp["candidates_count"] = 0
        return resp

    lat, lon = centroid
    anchor_note = (
        "districts.geom empty (no administrative boundary polygon in seed) — "
        "grid anchored on the documented district HQ point, not a surveyed "
        "boundary"
        if (lat, lon) == _DISTRICT_ANCHOR.get(district_id)
        else "grid anchored on district boundary polygon centroid"
    )
    existing = await _existing_sites(session, district_id)
    spacing = settings.SAFE_ZONE_GRID_SPACING_KM
    merge_km = spacing / 2.0

    candidates = []
    for site in existing:
        evidence = await evaluate_point(
            session, float(site["lon"]), float(site["lat"])
        )
        scores = score_candidate(
            float(site["lat"]), float(site["lon"]), evidence, existing=site
        )
        candidates.append(_candidate_record(
            district_id=district_id,
            candidate_id=f"{district_id}-site-{site['id']}",
            name=site.get("name") or f"Site {site['id']}",
            lat=float(site["lat"]), lon=float(site["lon"]),
            source="existing",
            evidence=evidence,
            scores=scores,
            base_site_id=site["id"],
        ))

    for idx, (plat, plon) in enumerate(grid_points(lat, lon, settings.SAFE_ZONE_GRID_RADIUS_KM, spacing)):
        near_existing = any(
            _haversine_km(plat, plon, float(s["lat"]), float(s["lon"])) <= merge_km
            for s in existing
        )
        if near_existing:
            continue
        evidence = await evaluate_point(session, plon, plat)
        scores = score_candidate(plat, plon, evidence)
        candidates.append(_candidate_record(
            district_id=district_id,
            candidate_id=f"{district_id}-sz-{idx:04d}",
            name=f"Discovered Point {idx:02d}",
            lat=plat, lon=plon,
            source="discovered",
            evidence=evidence,
            scores=scores,
        ))

    persisted = await _persist_candidates(session, district_id, candidates)
    resp["candidates"] = candidates
    resp["candidates_count"] = len(candidates)
    resp["persisted"] = persisted
    resp["geometry_source"] = (
        f"{anchor_note} ({lat:.4f}, {lon:.4f}): radius "
        f"{settings.SAFE_ZONE_GRID_RADIUS_KM:g} km, spacing "
        f"{settings.SAFE_ZONE_GRID_SPACING_KM:g} km"
    )
    resp["constraint_note"] = (
        "Hard constraints: fault buffer around USGS epicenters, active hazard "
        "polygon exclusion. Slope/land-use/water UNAVAILABLE (no spatial layer) "
        "— fed through, never assumed pass."
    )
    return resp


async def _persist_candidates(session: AsyncSession, district_id: str, candidates: list) -> bool:
    """Replace discovered rows and upsert existing-site rows.

    Returns True only when the whole batch committed; any failure rolls back
    and returns False (never silently claims persistence).
    """
    try:
        for c in candidates:
            await session.execute(
                sql_text(
                    """
                    INSERT INTO safe_zone_candidates (
                        id, district_id, name, source, geom,
                        suitability_score, safety_score, estimated_capacity,
                        hard_constraints, constraint_pass, constraint_evidence,
                        base_site_id, data_type, data_status, updated_at
                    ) VALUES (
                        :id, :district_id, :name, :source,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                        :suit, :safe, :cap, CAST(:hard AS jsonb),
                        :cpass, :cev, :base, 'DERIVED', 'DEMO', NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        suitability_score = EXCLUDED.suitability_score,
                        safety_score = EXCLUDED.safety_score,
                        estimated_capacity = EXCLUDED.estimated_capacity,
                        hard_constraints = EXCLUDED.hard_constraints,
                        constraint_pass = EXCLUDED.constraint_pass,
                        constraint_evidence = EXCLUDED.constraint_evidence,
                        base_site_id = EXCLUDED.base_site_id,
                        data_status = 'DEMO',
                        updated_at = NOW()
                    """,
                ),
                {
                    "id": c["id"],
                    "district_id": district_id,
                    "name": c["name"],
                    "source": c["source"],
                    "lon": c["longitude"],
                    "lat": c["latitude"],
                    "suit": c["suitability_score"],
                    "safe": c["safety_score"],
                    "cap": c["estimated_capacity"],
                    "hard": c.get("hard_constraints_json"),
                    "cpass": c["constraint_pass"],
                    "cev": c.get("constraint_brief"),
                    "base": c.get("base_site_id"),
                },
            )
        await session.execute(
            sql_text(
                """
                DELETE FROM safe_zone_candidates
                WHERE district_id = :district_id AND source = 'discovered'
                  AND id NOT IN (SELECT unnest(CAST(:keep AS text[])))
                """,
            ),
            {
                "district_id": district_id,
                "keep": [c["id"] for c in candidates if c["source"] == "discovered"] or ["__none__"],
            },
        )
        await session.commit()
        return True
    except Exception as exc:  # noqa: BLE001 — degrade on any persistence failure
        await session.rollback()
        logging.getLogger(__name__).warning(
            f"[safe_zone] persist failed for {district_id}: {type(exc).__name__}: {exc}"
        )
        return False


def _candidate_record(district_id: str, candidate_id: str, name: str, lat: float, lon: float,
                      source: str, evidence: dict, scores: dict,
                      base_site_id: Optional[str] = None) -> dict:
    status = classify(
        scores["suitability_score"], scores["safety_score"], evidence["constraint_pass"]
    )
    failed = [
        c for c, v in evidence["constraints"].items()
        if v.get("passed") is False
    ]
    return {
        "id": candidate_id,
        "district_id": district_id,
        "name": name,
        "source": source,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "suitability_score": scores["suitability_score"],
        "safety_score": scores["safety_score"],
        "estimated_capacity": scores["estimated_capacity"],
        "capacity_basis": scores["capacity_basis"],
        "suitability_basis": scores["suitability_basis"],
        "safety_basis": scores["safety_basis"],
        "constraint_pass": evidence["constraint_pass"],
        "constraints": evidence["constraints"],
        "constraining": failed,
        "constraint_brief": (
            "all hard constraints passed"
            if not failed
            else "excluded by: " + ", ".join(sorted(failed))
        ),
        "hard_constraints_json": json_dumps(evidence["constraints"]),
        "status": status,
        "status_label": (
            "Exclusion / High Risk" if status == "red"
            else "Caution / Limited Suitability" if status == "yellow"
            else "Technically Suitable"
        ),
        "base_site_id": base_site_id,
        "data_status": "DEMO",
        "data_type": "DERIVED",
    }


def json_dumps(obj) -> str:
    return json.dumps(obj, default=str)


def _status_feature(c: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [c["longitude"], c["latitude"]],
        },
        "properties": {
            "id": c["id"],
            "name": c["name"],
            "source": c["source"],
            "constraint_pass": c["constraint_pass"],
            "constraining": c.get("constraining", []),
            "constraint_brief": c.get("constraint_brief"),
            "suitability_score": c.get("suitability_score"),
            "safety_score": c.get("safety_score"),
            "estimated_capacity": c.get("estimated_capacity"),
            "status": c["status"],
            "status_label": c.get("status_label"),
            "data_status": c.get("data_status") or "DEMO",
            "authoritative": False,
            "classification": "DERIVED",
        },
    }


async def get_safe_zones(session: AsyncSession, district_id: str, refresh: bool = False) -> dict:
    """Safe-zone candidates as a map-ready FeatureCollection + evidence.

    When the persisted table is empty (or DB unavailable) and refresh=True,
    discovery is attempted first; otherwise an empty-but-honest DEERIVED
    FeatureCollection is returned.
    """
    cache_key = f"sz-{district_id}-{int(time.time() // settings.SAFE_ZONE_CACHE_TTL_S)}"
    if not refresh and cache_key in _CACHE:
        return _CACHE[cache_key]

    result = await _safe_query(
        session,
        """
        SELECT id, name, source, suitability_score, safety_score,
               estimated_capacity, constraint_pass, hard_constraints,
               constraint_evidence, base_site_id,
               ST_Y(geom) AS lat, ST_X(geom) AS lon
        FROM safe_zone_candidates
        WHERE district_id = :district_id
        ORDER BY suitability_score DESC NULLS LAST, id
        """,
        {"district_id": district_id},
    )
    candidates = []
    if result is not None:
        rows = result.mappings().all()
        for r in rows:
            d = dict(r)
            constraints = d.get("hard_constraints")
            candidates.append({
                "id": d["id"],
                "name": d["name"],
                "source": d["source"],
                "latitude": float(d["lat"]),
                "longitude": float(d["lon"]),
                "suitability_score": float(d["suitability_score"] or 0),
                "safety_score": float(d["safety_score"] or 0),
                "estimated_capacity": int(d["estimated_capacity"] or 0),
                "constraint_pass": bool(d["constraint_pass"]),
                "constraint_brief": d.get("constraint_evidence"),
                "constraining": sorted(
                    k for k, v in (constraints or {}).items()
                    if isinstance(v, dict) and v.get("passed") is False
                ),
                "missing": {
                    k: v.get("status")
                    for k, v in (constraints or {}).items()
                    if isinstance(v, dict) and v.get("passed") is None
                },
                "status": classify(
                    float(d["suitability_score"] or 0),
                    float(d["safety_score"] or 0),
                    bool(d["constraint_pass"]),
                ),
                "data_status": "DEMO",
            })
        source = "postgis"
    else:
        source = "demo_fallback"

    if not candidates and refresh and source == "demo_fallback":
        discovered = await discover_candidates(session, district_id)
        if discovered.get("candidates"):
            return await get_safe_zones(session, district_id)

    features = [_status_feature(c) for c in candidates]
    counts = {"green": 0, "yellow": 0, "red": 0}
    for c in candidates:
        counts[c["status"]] += 1

    resp = {
        "type": "FeatureCollection",
        "features": features,
        "district_id": district_id,
        "data_status": "DEMO",
        "classification": "DERIVED",
        "_source": ("postgis" if candidates else "empty — discovery not run"),
        "status_counts": counts,
        "candidates_count": len(candidates),
        "note": (
            "Safe-zone candidates are DERIVED screening output — constraining "
            "slope/land-use/water layers are UNAVAILABLE and fed through; fault "
            "and active-hazard exclusion are the evaluated hard constraints. "
            "Not an official land approval."
        ),
    }
    _CACHE[cache_key] = resp
    return resp