"""Phase 5B tests — derived screening zones + historical data availability.

Zone geometry tests auto-skip when PostGIS is unreachable; pure-model tests
(zone classification, radius rule, historical registry) always run.
"""

import asyncio
import unittest
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.services import screening

# ─── Database availability (mirrors test_spatial.py) ─────────────────────────

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
except Exception:  # pragma: no cover
    DB_OK = False


def _async_url() -> str:
    url = settings.DATABASE_URL
    if "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def _run(fn, *args, **kwargs):
    engine = create_async_engine(_async_url())
    try:
        async with AsyncSession(engine) as session:
            return await fn(session, *args, **kwargs)
    finally:
        await engine.dispose()


class _NoDbSession:
    """Stub session: forces the demo fallback path (queries return None)."""


class ZoneClassificationTests(unittest.TestCase):
    """Pure classification rules — no database involved."""

    def test_green_when_suitability_and_safety_pass(self):
        self.assertEqual(screening._zone_status(82, 88, True), "green")

    def test_yellow_when_suitability_below_70(self):
        self.assertEqual(screening._zone_status(68, 79, True), "yellow")

    def test_bottleneck_does_not_force_yellow(self):
        # A bottleneck is a capacity constraint, not a suitability failure.
        self.assertEqual(screening._zone_status(82, 88, True), "green")

    def test_red_on_hard_constraint_failure(self):
        self.assertEqual(screening._zone_status(82, 88, False), "red")

    def test_red_on_low_suitability_or_safety(self):
        self.assertEqual(screening._zone_status(45, 88, True), "red")
        self.assertEqual(screening._zone_status(82, 35, True), "red")

    def test_radius_rule_deterministic_and_clamped(self):
        self.assertEqual(screening._zone_radius_km(3200, 3200), 2.0)
        self.assertEqual(screening._zone_radius_km(2100, 3200), 1.57)
        self.assertEqual(screening._zone_radius_km(1800, 3200), 1.45)
        self.assertLessEqual(screening._zone_radius_km(99999, 1), 2.5)
        self.assertEqual(screening._zone_radius_km(1, 3200), 0.75)


class ScreeningZonesFallbackTests(unittest.TestCase):
    """Demo-fallback zone output — deterministic, honest provenance."""

    async def _fallback_zones(self):
        with patch.object(screening, "_safe_query", new=async_null):
            return await screening.get_screening_zones(_NoDbSession())

    def test_fallback_returns_three_derived_polygon_zones(self):
        fc = asyncio.run(self._fallback_zones())
        self.assertEqual(fc["_source"], "demo_fallback")
        self.assertEqual(len(fc["features"]), 3)
        for f in fc["features"]:
            self.assertEqual(f["geometry"]["type"], "Polygon")
            p = f["properties"]
            self.assertEqual(p["classification"], "DERIVED")
            self.assertTrue(p["derived"])
            self.assertFalse(p["authoritative"])
            self.assertIn("shapely", p["method"])
            self.assertIn("DEMO", p["data_status"])
            self.assertIn("site_id", p)

    def test_fallback_statuses_match_model(self):
        fc = asyncio.run(self._fallback_zones())
        by_id = {f["properties"]["site_id"]: f["properties"] for f in fc["features"]}
        # site-a 82/88 no bottleneck -> green; site-b 74/91 -> green;
        # site-c 68/79 bottleneck=land -> yellow. No red zones currently.
        self.assertEqual(by_id["site-a"]["status"], "green")
        self.assertEqual(by_id["site-b"]["status"], "green")
        self.assertEqual(by_id["site-c"]["status"], "yellow")
        self.assertEqual(fc["status_counts"], {"red": 0, "yellow": 1, "green": 2})

    def test_fallback_radii_match_seed_capacity(self):
        fc = asyncio.run(self._fallback_zones())
        by_id = {f["properties"]["site_id"]: f["properties"] for f in fc["features"]}
        self.assertEqual(by_id["site-a"]["radius_km"], 2.0)
        self.assertEqual(by_id["site-b"]["radius_km"], 1.57)
        self.assertEqual(by_id["site-c"]["radius_km"], 1.45)

    def test_zone_meaning_note_present(self):
        fc = asyncio.run(self._fallback_zones())
        self.assertIn("DERIVED SCREENING RANGE", fc["zone_meaning_note"])
        self.assertIn("NOT an official danger zone", fc["zone_meaning_note"])


@unittest.skipUnless(DB_OK, "PostGIS required")
class ScreeningZonesDbTests(unittest.TestCase):
    """Real PostGIS ST_Buffer output."""

    def test_postgis_zones_source_and_method(self):
        fc = asyncio.run(_run(screening.get_screening_zones))
        self.assertEqual(fc["_source"], "postgis")
        self.assertEqual(len(fc["features"]), 3)
        for f in fc["features"]:
            self.assertEqual(f["geometry"]["type"], "Polygon")
            self.assertEqual(f["properties"]["_source"], "postgis")
            self.assertIn("ST_Buffer", f["properties"]["method"])
            self.assertEqual(f["properties"]["classification"], "DERIVED")

    def test_postgis_statuses_match_demo_model(self):
        fc = asyncio.run(_run(screening.get_screening_zones))
        by_id = {f["properties"]["site_id"]: f["properties"] for f in fc["features"]}
        self.assertEqual(by_id["site-a"]["status"], "green")
        self.assertEqual(by_id["site-c"]["status"], "yellow")
        self.assertEqual(fc["status_counts"], {"red": 0, "yellow": 1, "green": 2})


class HistoricalPeriodsTests(unittest.TestCase):
    """Honest per-region historical availability."""

    def test_kerala_lists_only_real_periods(self):
        info = screening.get_historical_periods("kerala")
        self.assertEqual(info["status"], "AVAILABLE")
        periods = [p["period"] for p in info["periods"]]
        self.assertEqual(periods, ["current", "2018", "2019", "2021"])

    def test_2019_has_real_bhuvan_overlay(self):
        info = screening.get_historical_periods("kerala")
        p2019 = next(p for p in info["periods"] if p["period"] == "2019")
        self.assertEqual(p2019["availability"], "live_overlay")
        self.assertEqual(p2019["classification"], "OBSERVED")
        self.assertEqual(p2019["source"], "Bhuvan / ISRO-NRSC")
        layer = p2019["spatial_layer"]
        self.assertEqual(layer["type"], "wms")
        self.assertEqual(layer["layer"], "disaster:Kerala_2019_Event")
        self.assertIn("bhuvan-vec2.nrsc.gov.in", layer["url"])
        self.assertIn("never a numeric input", p2019["note"])

    def test_context_only_periods_never_fabricate_geometry(self):
        info = screening.get_historical_periods("kerala")
        for p in info["periods"]:
            if p["period"] in ("2018", "2021"):
                self.assertEqual(p["availability"], "context_only")
                self.assertIsNone(p["spatial_layer"])
                self.assertEqual(p["classification"], "OBSERVED")
                self.assertIn("No machine-readable spatial layer", p["note"])

    def test_current_period_is_not_relabelled_historical(self):
        info = screening.get_historical_periods("kerala")
        cur = next(p for p in info["periods"] if p["period"] == "current")
        self.assertEqual(cur["availability"], "current")
        self.assertIsNone(cur["spatial_layer"])

    def test_vizag_and_assam_unavailable_with_reason(self):
        for region in ("vizag", "assam"):
            info = screening.get_historical_periods(region)
            self.assertEqual(info["status"], "UNAVAILABLE")
            self.assertEqual(info["periods"], [])
            self.assertIn("No historical hazard/event layer", info["reason"])

    def test_unknown_region_returns_none(self):
        self.assertIsNone(screening.get_historical_periods("mars"))


async def async_null(*args, **kwargs):
    return None
