"""Phase 5B — Derived screening ranges + historical data availability.

Real spatial geometry (candidate-site points) is buffered by PostGIS; a
deterministic shapely fallback keeps the demo working when the database is
unreachable. No official hazard/boundary polygons exist in the seed dataset,
so nothing here is presented as an official danger zone.
"""

import json
import math
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import demo_data
from app.services.db_service import _safe_query

_DEMO_SITES = demo_data.get_candidate_sites("munnar-central")["sites"]
_SRID = 4326

_ZONE_MEANING_NOTE = (
    "DERIVED SCREENING RANGE — a geodesic buffer around a technically screened "
    "candidate site, sized from the site's assessed safe capacity and colored "
    "from its suitability/safety scores and capacity bottleneck. This is NOT an "
    "official danger zone, hazard boundary, or government land approval."
)
_ZONE_METHOD_POSTGIS = (
    "PostGIS ST_Buffer(geography, radius_m, 'quad_segs=32') — WGS84 geodesic buffer"
)
_ZONE_METHOD_FALLBACK = (
    "shapely buffer on demo coordinates (approximate metres->degrees at site "
    "latitude — database unavailable)"
)


def _zone_status(suitability, safety, hard_passed) -> str:
    """Deterministic three-tier classification from EXISTING model outputs.

    - RED    'Exclusion / High Risk'        : hard constraint failure, or
              suitability < 50, or safety < 40 (no current site qualifies).
    - YELLOW 'Caution / Limited Suitability': suitability < 70 (constrained
              but not excluded — e.g. Site C at 68/100).
    - GREEN  'Technically Suitable'         : hard constraints passed and
              suitability >= 70 and safety >= 60.
    """
    if not hard_passed or suitability < 50 or safety < 40:
        return "red"
    if suitability < 70:
        return "yellow"
    return "green"


def _zone_radius_km(c_safe: float, max_c_safe: float) -> float:
    """Deterministic capacity-weighted screening radius, clamped 0.75-2.5 km."""
    if not max_c_safe:
        return 0.75
    return round(min(2.5, max(0.75, 0.75 + 1.25 * (c_safe / max_c_safe))), 2)


def _zone_feature(site: dict, radius_km: float, status: str, geometry: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "site_id": site["id"],
            "site_name": site["name"],
            "status": status,
            "label": (
                "Exclusion / High Risk" if status == "red"
                else "Caution / Limited Suitability" if status == "yellow"
                else "Technically Suitable"
            ),
            "classification": "DERIVED",
            "derived": True,
            "authoritative": False,
            "method": _ZONE_METHOD_POSTGIS,
            "radius_km": radius_km,
            "basis": {
                "suitability_score": site.get("suitability_score"),
                "safety_score": site.get("safety_score"),
                "bottleneck": site.get("bottleneck"),
                "c_safe": site.get("c_safe"),
            },
            "data_status": site.get("data_status") or "DEMO",
        },
    }


def _shapely_buffer_geojson(lat: float, lon: float, radius_km: float) -> dict:
    """Approximate geodesic buffer via shapely (application-level fallback).

    Local equirectangular projection around the site: buffer the point in
    metres, then map the ring back to lon/lat degrees. DEMO fallback only —
    the PostGIS path is preferred and always used when the DB answers.
    """
    from shapely.geometry import Point, mapping

    m_per_deg_lat = 111320.0
    m_per_deg_lon = 111320.0 * max(math.cos(math.radians(lat)), 0.01)
    radius_m = radius_km * 1000.0
    x0, y0 = lon * m_per_deg_lon, lat * m_per_deg_lat
    ring = mapping(Point(x0, y0).buffer(radius_m, quad_segs=32))
    coords = [
        [x / m_per_deg_lon, y / m_per_deg_lat]
        for (x, y) in ring["coordinates"][0]
    ]
    return {"type": "Polygon", "coordinates": [coords]}


async def get_screening_zones(session: AsyncSession, district_id: str = "idukki") -> dict:
    """GeoJSON of DERIVED screening ranges around technically screened sites.

    PostGIS ST_Buffer(geography) when the database answers; deterministic
    shapely fallback on demo coordinates otherwise. Fallback is always
    labelled — never silently substituted.
    """
    result = await _safe_query(
        session,
        """
        SELECT cs.id, cs.name, cs.suitability_score, cs.safety_score,
               cs.safe_capacity, cs.hard_constraints_passed, cs.data_status,
               ca.c_safe, ca.bottleneck,
               ST_Y(cs.geom) AS lat, ST_X(cs.geom) AS lon
        FROM candidate_sites cs
        LEFT JOIN capacity_assessments ca ON ca.site_id = cs.id
        WHERE cs.district_id = :district_id
        ORDER BY cs.suitability_score DESC
        """,
        {"district_id": district_id},
    )

    sites = None
    if result is not None:
        rows = result.mappings().all()
        if rows:
            sites = [dict(r) for r in rows]

    if sites is None:
        sites = [
            {
                "id": s["id"], "name": s["name"],
                "suitability_score": s["suitability_score"],
                "safety_score": s["safety_score"],
                "safe_capacity": s["safe_capacity"],
                "hard_constraints_passed": s.get("hard_constraints_passed", True),
                "data_status": s["data_status"],
                "c_safe": s["safe_capacity"],
                "bottleneck": s.get("bottleneck_dimension"),
                "lat": s["latitude"], "lon": s["longitude"],
            }
            for s in _DEMO_SITES
        ]
        source = "demo_fallback"
    else:
        source = "postgis"

    max_c = max((float(s["c_safe"] or s["safe_capacity"] or 0) for s in sites), default=1.0)
    features = []
    for s in sites:
        c_safe = float(s["c_safe"] or s["safe_capacity"] or 0)
        radius_km = _zone_radius_km(c_safe, max_c)
        status = _zone_status(
            float(s["suitability_score"] or 0),
            float(s["safety_score"] or 0),
            bool(s.get("hard_constraints_passed")),
        )
        geom = None
        if source == "postgis":
            buf = await _safe_query(
                session,
                "SELECT ST_AsGeoJSON(ST_Buffer(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius, 'quad_segs=32')::geometry) AS geojson",
                {"lon": float(s["lon"]), "lat": float(s["lat"]), "radius": radius_km * 1000.0},
            )
            buf_row = None
            if buf is not None:
                buf_row = buf.mappings().first()
            if buf_row is not None:
                geom = json.loads(buf_row["geojson"])
        feature = _zone_feature(s, radius_km, status, geom or {})
        feature["properties"]["_source"] = source if geom else "demo_fallback"
        if geom is None:
            feature["properties"]["method"] = _ZONE_METHOD_FALLBACK
            geom = _shapely_buffer_geojson(float(s["lat"]), float(s["lon"]), radius_km)
        feature["geometry"] = geom
        features.append(feature)

    counts = {"red": 0, "yellow": 0, "green": 0}
    for f in features:
        counts[f["properties"]["status"]] += 1

    return {
        "type": "FeatureCollection",
        "features": features,
        "district_id": district_id,
        "data_status": "DEMO",
        "classification": "DERIVED",
        "_source": source,
        "geometry_source": (
            "PostGIS candidate_sites.geom buffered via ST_Buffer(geography)"
            if source == "postgis"
            else "demo_data coordinates (DEMO — database unavailable)"
        ),
        "geometry_type": "Polygon",
        "srid": _SRID,
        "status_counts": counts,
        "zone_meaning_note": _ZONE_MEANING_NOTE,
        "note": (
            "Only derived screening ranges are emitted — the seed dataset contains "
            "no official hazard/exclusion polygons, and none are fabricated."
        ),
    }


# ─── Historical data availability ────────────────────────────────────────────
# Honest registry of what historical spatial/context data actually exists per
# region. No period is invented: a period is listed only when the project has
# some real record of it (a live layer, or documented event context).

_BHUVAN_KERALA_2019_WMS = (
    "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?SERVICE=WMS&VERSION=1.1.1"
    "&REQUEST=GetMap&LAYERS=disaster:Kerala_2019_Event&STYLES=&FORMAT=image/png"
    "&TRANSPARENT=true&SRS=EPSG:3857&WIDTH=256&HEIGHT=256&BBOX={bbox-epsg-3857}"
)

# Region -> historical periods available to the prototype.
_HISTORICAL_PERIODS: dict = {
    "kerala": [
        {
            "period": "current",
            "label": "Current (operational)",
            "availability": "current",
            "classification": "DERIVED",
            "spatial_layer": None,
            "note": (
                "Operational risk and suitability from the current data pipeline. "
                "Not a historical event."
            ),
        },
        {
            "period": "2018",
            "label": "2018 — Kerala floods & landslides",
            "availability": "context_only",
            "classification": "OBSERVED",
            "source": "KSDMA / GSI investigation records (documented in habitation history)",
            "spatial_layer": None,
            "note": (
                "No machine-readable spatial layer for 2018 exists in the project "
                "dataset. Event context (major displacement; GSI investigation; "
                "689 dwelling units recommended for relocation) is documented in "
                "habitation records as DEMO narrative only."
            ),
        },
        {
            "period": "2019",
            "label": "2019 — Kerala flood event",
            "availability": "live_overlay",
            "classification": "OBSERVED",
            "source": "Bhuvan / ISRO-NRSC",
            "spatial_layer": {
                "type": "wms",
                "layer": "disaster:Kerala_2019_Event",
                "url": _BHUVAN_KERALA_2019_WMS,
                "attribution": "Bhuvan / ISRO-NRSC — Kerala 2019 event layer",
            },
            "note": (
                "Real ISRO/NRSC historical event WMS overlay (verified reachable). "
                "Visual context only — never a numeric input to the risk engine."
            ),
        },
    ]
}

# Append the 2021 context-only period, plus the empty-region reasons.
_HISTORICAL_PERIODS["kerala"].append(
    {
        "period": "2021",
        "label": "2021 — October landslides",
        "availability": "context_only",
        "classification": "OBSERVED",
        "source": "KSDMA records (documented in habitation history)",
        "spatial_layer": None,
        "note": (
            "No machine-readable spatial layer for 2021 in the project dataset. "
            "Event context (partial slope failure, 3 structures damaged) is "
            "documented as DEMO narrative only."
        ),
    }
)
_HISTORICAL_PERIODS["vizag"] = []
_HISTORICAL_PERIODS["assam"] = []

_HISTORICAL_REGION_REASONS = {
    "vizag": (
        "No historical hazard/event layer is registered for the Vizag prototype "
        "region in the project data sources. Current operational data only."
    ),
    "assam": (
        "No historical hazard/event layer is registered for the Assam prototype "
        "region in the project data sources. Current operational data only."
    ),
}


def get_historical_periods(region_key: str) -> Optional[dict]:
    """Historical data availability for a routing region.

    Returns None for unknown regions (caller raises HTTP 404). Periods carry
    provenance; a period is never fabricated and current data is never relabelled
    as historical.
    """
    if region_key not in _HISTORICAL_PERIODS:
        return None
    periods = _HISTORICAL_PERIODS[region_key]
    if not periods:
        return {
            "region": region_key,
            "status": "UNAVAILABLE",
            "periods": [],
            "reason": _HISTORICAL_REGION_REASONS.get(
                region_key, "No historical layers registered for this region."
            ),
        }
    return {
        "region": region_key,
        "status": "AVAILABLE",
        "periods": periods,
        "note": (
            "Periods with availability=live_overlay have a real spatial layer; "
            "availability=context_only periods have documented event context but "
            "no machine-readable geometry. Current data is never relabelled as historical."
        ),
    }
