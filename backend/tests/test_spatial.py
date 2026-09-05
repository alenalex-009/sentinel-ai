"""Phase 3 spatial tests — Sentinel AI.

PostGIS-backed tests auto-skip when the database is unreachable (e.g. local
environments without the docker stack); pure-model tests (Phase 1 risk math,
Bhuvan registry spec) always run.

Run from backend/:
    python -m unittest discover -s tests -v
"""

import asyncio
import math
import unittest

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.services import data_status, demo_data, spatial_service

# ─── Database availability ────────────────────────────────────────────────────

try:
    import psycopg2

    def _db_reachable() -> bool:
        try:
            conn = psycopg2.connect(settings.DATABASE_URL, connect_timeout=3)
            conn.close()
            return True
        except Exception:
            return False

    DB_OK = _db_reachable()
except Exception:  # pragma: no cover — psycopg2 absent
    DB_OK = False


def _async_url() -> str:
    url = settings.DATABASE_URL
    if "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _query_sync(sql: str) -> list:
    conn = psycopg2.connect(settings.DATABASE_URL, connect_timeout=3)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


async def _run(fn, *args, **kwargs):
    # Fresh engine per call: asyncpg connections are bound to the event loop,
    # and every test runs in its own asyncio.run loop.
    engine = create_async_engine(_async_url())
    try:
        async with AsyncSession(engine) as session:
            return await fn(session, *args, **kwargs)
    finally:
        await engine.dispose()


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


_NEED_DB = unittest.skipUnless(DB_OK, "PostGIS database not reachable — skipping")


class SpatialSchemaTests(unittest.TestCase):
    """Raw PostGIS geometry facts (schema + SRID + no fabricated polygons)."""

    @_NEED_DB
    def test_geometry_columns_srid_and_type(self):
        rows = _query_sync(
            "SELECT f_table_name, f_geometry_column, type, srid "
            "FROM geometry_columns "
            "WHERE f_table_name IN ('habitations','candidate_sites') "
            "  AND f_geometry_column = 'geom' "
            "ORDER BY f_table_name"
        )
        table_map = {r[0]: (r[1], r[2], r[3]) for r in rows}
        self.assertEqual(table_map["habitations"], ("geom", "POINT", 4326))
        self.assertEqual(table_map["candidate_sites"], ("geom", "POINT", 4326))

    @_NEED_DB
    def test_no_polygon_rows_seeded(self):
        """boundary columns exist in the schema but hold no fabricated polygons."""
        hab = _query_sync("SELECT count(*) FROM habitations WHERE boundary IS NOT NULL")[0][0]
        site = _query_sync("SELECT count(*) FROM candidate_sites WHERE boundary IS NOT NULL")[0][0]
        self.assertEqual(hab, 0)
        self.assertEqual(site, 0)


class HabitationGeoJsonTests(unittest.TestCase):
    @_NEED_DB
    def test_postgis_geojson_has_five_point_features(self):
        fc = asyncio.run(_run(spatial_service.get_habitation_geojson, "idukki"))
        self.assertEqual(fc["_source"], "postgis")
        self.assertEqual(fc["srid"], 4326)
        self.assertEqual(fc["geometry_type"], "Point")
        features = fc["features"]
        self.assertEqual(len(features), 5)
        ids = {f["properties"]["id"] for f in features}
        self.assertEqual(
            ids,
            {"munnar-central", "rajakkad", "kanthalloor", "marayoor", "adimali"},
        )
        for f in features:
            self.assertEqual(f["type"], "Feature")
            self.assertEqual(f["geometry"]["type"], "Point")
            lon, lat = f["geometry"]["coordinates"]
            self.assertTrue(76.9 <= lon <= 77.3, f"lon out of range: {lon}")
            self.assertTrue(9.9 <= lat <= 10.3, f"lat out of range: {lat}")
            self.assertIn("population", f["properties"])
            self.assertIn("risk_score", f["properties"])

    @_NEED_DB
    def test_geojson_emits_no_polygons(self):
        hab_fc = asyncio.run(_run(spatial_service.get_habitation_geojson, "idukki"))
        sites_fc = asyncio.run(_run(spatial_service.get_candidate_sites_geojson))
        for fc in (hab_fc, sites_fc):
            self.assertTrue(fc["features"])
            for f in fc["features"]:
                self.assertEqual(f["geometry"]["type"], "Point")


class CandidateSitesGeoJsonTests(unittest.TestCase):
    @_NEED_DB
    def test_postgis_sites_geojson(self):
        fc = asyncio.run(_run(spatial_service.get_candidate_sites_geojson))
        self.assertEqual(fc["_source"], "postgis")
        self.assertEqual(len(fc["features"]), 3)
        site_c = next(f for f in fc["features"] if f["properties"]["id"] == "site-c")
        self.assertEqual(site_c["properties"]["c_safe"], 1800)
        self.assertEqual(site_c["properties"]["bottleneck"], "land")
        self.assertTrue("approval_status_note" in fc)
        self.assertIn("NOT", fc["approval_status_note"].upper())


class DistanceTests(unittest.TestCase):
    @_NEED_DB
    def test_distance_deterministic_and_postgis(self):
        a = asyncio.run(_run(
            spatial_service.get_spatial_distance, "munnar-central", "site-a"
        ))
        b = asyncio.run(_run(
            spatial_service.get_spatial_distance, "munnar-central", "site-a"
        ))
        self.assertIsNotNone(a)
        self.assertEqual(a, b)  # deterministic
        self.assertEqual(a["_source"], "postgis")
        self.assertEqual(a["unit"], "m")
        self.assertEqual(a["classification"], "DERIVED")
        self.assertTrue(a["method"].startswith("PostGIS ST_Distance"))
        self.assertGreater(a["distance_m"], 0)
        self.assertLess(a["distance_m"], 20000)
        # Cross-check against haversine computed from the same DB coordinates.
        row = _query_sync(
            "SELECT h.id, ST_Y(h.geom), ST_X(h.geom), s.id, ST_Y(s.geom), ST_X(s.geom) "
            "FROM habitations h CROSS JOIN candidate_sites s "
            "WHERE h.id = 'munnar-central' AND s.id = 'site-a'"
        )[0]
        hlat, hlon, slat, slon = row[1], row[2], row[4], row[5]
        approx = _haversine_m(hlat, hlon, slat, slon)
        self.assertAlmostEqual(a["distance_m"], approx, delta=approx * 0.02)

    @_NEED_DB
    def test_unknown_ids_return_none(self):
        self.assertIsNone(asyncio.run(_run(
            spatial_service.get_spatial_distance, "nope", "site-a"
        )))
        self.assertIsNone(asyncio.run(_run(
            spatial_service.get_spatial_distance, "munnar-central", "nope"
        )))


class ProximityTests(unittest.TestCase):
    @_NEED_DB
    def test_proximity_within_large_radius_returns_all(self):
        res = asyncio.run(_run(
            spatial_service.get_proximate_sites, "munnar-central", 100000.0
        ))
        self.assertEqual(res["_source"], "postgis")
        ids = {r["site_id"] for r in res["results"]}
        self.assertEqual(ids, {"site-a", "site-b", "site-c"})
        distances = [r["distance_m"] for r in res["results"]]
        self.assertEqual(distances, sorted(distances))  # ascending by distance
        for r in res["results"]:
            self.assertLessEqual(r["distance_m"], 100000.0)

    @_NEED_DB
    def test_proximity_tiny_radius_returns_none(self):
        res = asyncio.run(_run(
            spatial_service.get_proximate_sites, "munnar-central", 1.0
        ))
        self.assertEqual(res["_source"], "postgis")
        self.assertEqual(res["results"], [])

    @_NEED_DB
    def test_proximity_unknown_habitation_none(self):
        self.assertIsNone(asyncio.run(_run(
            spatial_service.get_proximate_sites, "nope", 100000.0
        )))


class Phase1AndPhase2RegressionTests(unittest.TestCase):
    """Frozen behaviors from Phase 1 / Phase 2 must not change."""

    def test_phase1_risk_math_unchanged(self):
        from app.services.risk_validation import validate_munnar_central
        res = validate_munnar_central()
        c = res["computed"]
        self.assertAlmostEqual(c["base_risk"], 80.21, places=2)
        self.assertAlmostEqual(c["event_escalation"], 13.65, places=2)
        self.assertEqual(c["current_risk_rounded"], 94)
        self.assertTrue(c["current_risk_matches_seed"])

    def test_bhuvan_registry_spec_unchanged(self):
        sources = {s["id"]: s for s in data_status.get_all_source_statuses()}
        self.assertIn("bhuvan-flood", sources)
        self.assertTrue(sources["bhuvan-flood"]["name"].startswith("Kerala Disaster Event Layers"))
        self.assertEqual(
            data_status.DATA_TYPES_BY_SOURCE["bhuvan-flood"], ["Raster", "WMS"]
        )
        risk_lim = sources["sentinel-risk-engine"]["limitations"]
        self.assertIn("event-escalation", risk_lim)

    def test_canonical_values_frozen(self):
        demo = demo_data.get_candidate_sites("munnar-central")["sites"]
        site_c = next(s for s in demo if s["id"] == "site-c")
        self.assertEqual(site_c["safe_capacity"], 1800)
        self.assertEqual(site_c["bottleneck_dimension"], "land")


if __name__ == "__main__":
    unittest.main(verbosity=2)
