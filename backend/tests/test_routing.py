"""Phase 4/5 routing tests — GraphHopper over OpenStreetMap (Kerala/Vizag/Assam).

Route tests auto-skip when the relevant region's GraphHopper service is
unreachable. The unavailable-path tests (never relabel straight-line as road)
always run.
"""

import asyncio
import unittest

import httpx

from app.core.config import settings
from app.core.regions import REGIONS, coordinates_inside, region_for_coordinates
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.services import routing_service, spatial_service
from app.services.optimizer import build_sites_from_demo, run_optimization
from app.services.routing_service import region_base_url

# Known-good real places inside each loaded extract (lat, lon). These are
# dataset-level smoke pairs — the seed has no Vizag/Assam habitation records.
SAMPLE_PAIRS = {
    # Munnar Central -> Site A (Kerala seed geometry)
    "kerala": ((10.0889, 77.0595), (10.1123, 77.0812)),
    # Visakhapatnam urban area
    "vizag": ((17.7384, 83.3007), (17.7700, 83.3600)),
    # Guwahati urban area
    "assam": ((26.1830, 91.7510), (26.1600, 91.7000)),
}


def _gh_reachable(region_key: str = "kerala") -> bool:
    base = region_base_url(region_key)
    if not base:
        return False
    try:
        r = httpx.get(f"{base.rstrip('/')}/info", timeout=6)
        return r.status_code == 200
    except Exception:
        return False


GH_OK = _gh_reachable("kerala")
NEED_GH = unittest.skipUnless(GH_OK, "GraphHopper not reachable — skipping")
REGION_GH_OK = {k: _gh_reachable(k) for k in REGIONS}


def _skip_region(region_key: str):
    return unittest.skipUnless(
        REGION_GH_OK.get(region_key), f"GraphHopper {region_key} not reachable — skipping"
    )


def _pg_ok() -> bool:
    try:
        import psycopg2
        conn = psycopg2.connect(settings.DATABASE_URL, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


DB_OK = _pg_ok()
NEED_BOTH = unittest.skipUnless(GH_OK and DB_OK, "GraphHopper + PostGIS required — skipping")


async def _run(fn, *args, **kwargs):
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    try:
        async with AsyncSession(engine) as session:
            return await fn(session, *args, **kwargs)
    finally:
        await engine.dispose()


class RoadRouteTests(unittest.TestCase):
    @NEED_BOTH
    def test_valid_road_route_deterministic_and_provenance(self):
        a = asyncio.run(_run(routing_service.route_road, "munnar-central", "site-a"))
        self.assertEqual(a["status"], "OK")
        self.assertEqual(a["_source"], "graphhopper")
        route = a["route"]
        self.assertGreater(route["distance_km"], 0)
        self.assertGreater(route["duration_min"], 0)
        self.assertEqual(route["classification"], "DERIVED")
        self.assertIn("OpenStreetMap + GraphHopper", route["source"])
        self.assertTrue(route["method"].startswith("road-network route"))
        # route GeoJSON present (only when a real route was returned)
        self.assertEqual(a["route_geojson"]["geometry"]["type"], "LineString")
        for lon, lat in a["route_geojson"]["geometry"]["coordinates"][:5]:
            self.assertTrue(76.9 <= lon <= 77.3, f"lon out of range: {lon}")
            self.assertTrue(9.9 <= lat <= 10.3, f"lat out of range: {lat}")
        # deterministic + cached second call
        b = asyncio.run(_run(routing_service.route_road, "munnar-central", "site-a"))
        self.assertEqual(a["route"]["distance_km"], b["route"]["distance_km"])
        self.assertTrue(b["route"]["cache"])

    @NEED_BOTH
    def test_road_longer_than_geodesic(self):
        road = asyncio.run(_run(routing_service.route_road, "munnar-central", "site-a"))
        geo = asyncio.run(_run(spatial_service.get_spatial_distance, "munnar-central", "site-a"))
        self.assertEqual(road["status"], "OK")
        self.assertIsNotNone(geo)
        self.assertGreaterEqual(
            road["route"]["distance_km"] + 1e-9,
            geo["distance_km"],
            "road distance must not be shorter than the straight-line distance",
        )

    def test_unknown_ids_return_none(self):
        self.assertIsNone(asyncio.run(_run(
            routing_service.route_road, "nope", "site-a"
        )))
        self.assertIsNone(asyncio.run(_run(
            routing_service.route_road, "munnar-central", "nope"
        )))

    def test_unavailable_never_mislabeled_as_road(self):
        res = asyncio.run(_run(
            routing_service.route_road, "munnar-central", "site-a",
            base_url="http://127.0.0.1:1",
        ))
        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "UNAVAILABLE")
        self.assertIsNone(res["route"])
        self.assertNotIn("distance_km", res)
        self.assertIn("must NOT be treated as road distance", res["note"])


class ComparisonTests(unittest.TestCase):
    @NEED_BOTH
    def test_comparison_matrix_rows(self):
        cmp = asyncio.run(_run(routing_service.compare_distances, "munnar-central"))
        self.assertEqual(len(cmp["rows"]), 3)
        for row in cmp["rows"]:
            self.assertIsNotNone(row["demo_km"])
            self.assertIsNotNone(row["geodesic_km"])
            self.assertIn(row["road_status"], ("OK", "UNAVAILABLE"))
            if row["road_status"] == "OK":
                self.assertGreater(row["road_km"], 0)
                self.assertGreater(row["duration_min"], 0)
                self.assertGreaterEqual(row["road_km"] + 1e-9, row["geodesic_km"])


class RegionConfigTests(unittest.TestCase):
    """Region model + region validation (no DB / no GraphHopper needed)."""

    def test_supported_regions(self):
        self.assertEqual(set(REGIONS.keys()), {"kerala", "vizag", "assam"})

    def test_region_for_coordinates(self):
        # Kerala (Munnar pilot coords)
        self.assertEqual(region_for_coordinates(10.0889, 77.0595, 10.0756, 77.0623), "kerala")
        # Vizag sample
        self.assertEqual(region_for_coordinates(17.71, 83.30, 17.86, 83.32), "vizag")
        # Assam sample
        self.assertEqual(region_for_coordinates(26.18, 91.75, 26.36, 92.00), "assam")

    def test_cross_region_is_rejected(self):
        # Kerala habitation + Vizag site must NOT resolve to any single region
        self.assertIsNone(region_for_coordinates(10.0889, 77.0595, 17.71, 83.30))
        # fully uncovered coordinates
        self.assertIsNone(region_for_coordinates(0.0, 0.0, 1.0, 1.0))

    def test_dataset_status(self):
        # Phase 5: all three regions have real loaded datasets (development =
        # prototype-area coverage, documented in the label — never claimed as
        # full-state or production). No region may report "required"/NOT LOADED.
        for key in ("kerala", "vizag", "assam"):
            self.assertEqual(REGIONS[key].dataset_status, "development", key)
            self.assertIsNotNone(REGIONS[key].dataset_coverage, key)
            self.assertNotIn("NOT LOADED", REGIONS[key].dataset_label)

    def test_coordinates_inside(self):
        kerala = REGIONS["kerala"].dataset_coverage
        self.assertTrue(coordinates_inside(kerala, 10.0889, 77.0595))   # Munnar Central
        self.assertTrue(coordinates_inside(kerala, 10.2012, 77.1567))   # Marayoor
        self.assertTrue(coordinates_inside(kerala, 10.0012, 76.9834))   # Adimali
        self.assertFalse(coordinates_inside(kerala, 9.0, 76.5))         # outside extract
        self.assertFalse(coordinates_inside(None, 17.71, 83.30))
        vizag = REGIONS["vizag"].dataset_coverage
        self.assertTrue(coordinates_inside(vizag, 17.7384, 83.3007))
        self.assertFalse(coordinates_inside(vizag, 18.30, 83.40))       # outside extract

    def test_region_base_url(self):
        kerala_expected = settings.GRAPHHOPPER_KERALA_URL or settings.GRAPHHOPPER_URL
        self.assertEqual(region_base_url("kerala"), kerala_expected)
        self.assertEqual(region_base_url("vizag"), settings.GRAPHHOPPER_VIZAG_URL)
        self.assertEqual(region_base_url("assam"), settings.GRAPHHOPPER_ASSAM_URL)
        self.assertIsNone(region_base_url("mars"))


class CrossRegionGateTests(unittest.TestCase):
    """Cross-region / uncovered pairs must return UNAVAILABLE — never a route."""

    @unittest.skipUnless(DB_OK, "PostGIS required for coordinate resolution")
    def test_kerala_pair_with_explicit_vizag_region_is_rejected(self):
        # Kerala coordinates asked to route through the Vizag dataset: the
        # dataset gate must refuse (coordinates outside the Vizag extract).
        res = asyncio.run(_run(
            routing_service.route_road, "munnar-central", "site-a",
            region="vizag",
        ))
        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "UNAVAILABLE")
        self.assertIsNone(res["route"])
        self.assertIn("not loaded", res["reason"].lower())
        self.assertEqual(res["region"]["key"], "vizag")
        self.assertEqual(res["region"]["dataset_status"], "development")

    @unittest.skipUnless(DB_OK, "PostGIS required for coordinate resolution")
    def test_kerala_pair_with_explicit_assam_region_is_rejected(self):
        res = asyncio.run(_run(
            routing_service.route_road, "munnar-central", "site-a",
            region="assam",
        ))
        self.assertIsNotNone(res)
        self.assertEqual(res["status"], "UNAVAILABLE")
        self.assertIsNone(res["route"])
        self.assertEqual(res["region"]["key"], "assam")

    def test_cross_region_coordinates_never_resolve(self):
        # Kerala habitation + Vizag site coords — no single region matches.
        self.assertIsNone(region_for_coordinates(10.0889, 77.0595, 17.71, 83.30))

    @unittest.skipUnless(DB_OK, "PostGIS required for coordinate resolution")
    def test_unsupported_region(self):
        res = asyncio.run(_run(
            routing_service.route_road, "munnar-central", "site-a",
            region="mars",
        ))
        self.assertEqual(res["status"], "UNAVAILABLE")
        self.assertIn("Unsupported routing region", res["reason"])

class RegionLiveRouteTests(unittest.TestCase):
    """Live GraphHopper: provenance carries the actual region + dataset."""

    @NEED_BOTH
    def test_route_payload_has_kerala_region_provenance(self):
        res = asyncio.run(_run(routing_service.route_road, "munnar-central", "site-a"))
        self.assertEqual(res["status"], "OK")
        self.assertEqual(res["region"]["key"], "kerala")
        self.assertEqual(res["region"]["dataset_status"], "development")
        self.assertIn("Idukki", res["region"]["dataset"])
        self.assertEqual(
            res["route_geojson"]["properties"]["region"], "kerala"
        )

    @NEED_BOTH
    def test_comparison_road_region(self):
        cmp = asyncio.run(_run(routing_service.compare_distances, "munnar-central"))
        for row in cmp["rows"]:
            self.assertEqual(row["road_region"], "kerala")

    @NEED_BOTH
    def test_kerala_all_three_sites_route(self):
        """Golden Munnar demo: all three candidate sites must be road-routable
        from Munnar Central against the loaded Kerala dataset."""
        for site_id in ("site-a", "site-b", "site-c"):
            res = asyncio.run(_run(routing_service.route_road, "munnar-central", site_id))
            self.assertEqual(res["status"], "OK", site_id)
            self.assertGreater(res["route"]["distance_km"], 0)
            self.assertEqual(res["route"]["classification"], "DERIVED")


class RegionDatasetLiveTests(unittest.TestCase):
    """Dataset-level validation for the loaded regional extracts.

    Routes two real places inside each region's extract directly through that
    region's GraphHopper service (lat,lon order). The seed has no Vizag/Assam
    habitation records, so these validate the datasets, not habitation ids.
    """

    def _raw_route(self, region_key: str):
        base = region_base_url(region_key)
        self.assertIsNotNone(base, f"no service URL for {region_key}")
        (lat1, lon1), (lat2, lon2) = SAMPLE_PAIRS[region_key]
        params = {
            "profile": "car",
            "point": [f"{lat1},{lon1}", f"{lat2},{lon2}"],
            "points_encoded": "false",
            "instructions": "false",
        }
        r = httpx.get(f"{base.rstrip('/')}/route", params=params, timeout=30)
        self.assertEqual(r.status_code, 200, r.text[:300])
        data = r.json()
        self.assertTrue(data.get("paths"), f"no paths for {region_key}: {data.get('message')}")
        return data["paths"][0]

    @_skip_region("vizag")
    def test_vizag_dataset_real_route(self):
        path = self._raw_route("vizag")
        self.assertGreater(float(path["distance"]), 0)
        self.assertGreater(float(path["time"]), 0)
        coords = path["points"]["coordinates"]
        self.assertGreater(len(coords), 1)
        # GeoJSON coords are [lon, lat] and must stay inside the extract bounds
        vizag = REGIONS["vizag"].dataset_coverage
        for lon, lat in coords:
            self.assertTrue(coordinates_inside(vizag, lat, lon), f"out of bounds: {lon},{lat}")

    @_skip_region("assam")
    def test_assam_dataset_real_route(self):
        path = self._raw_route("assam")
        self.assertGreater(float(path["distance"]), 0)
        self.assertGreater(float(path["time"]), 0)
        coords = path["points"]["coordinates"]
        self.assertGreater(len(coords), 1)
        assam = REGIONS["assam"].dataset_coverage
        for lon, lat in coords:
            self.assertTrue(coordinates_inside(assam, lat, lon), f"out of bounds: {lon},{lat}")

    @NEED_GH
    def test_kerala_dataset_real_route_raw(self):
        path = self._raw_route("kerala")
        self.assertGreater(float(path["distance"]), 0)

    def test_dataset_health_all_regions(self):
        """/info must report the car profile on every configured region service."""
        for key in REGIONS:
            base = region_base_url(key)
            if not base:
                continue
            try:
                r = httpx.get(f"{base.rstrip('/')}/info", timeout=8)
            except Exception:
                continue
            if r.status_code == 200:
                profiles = [p.get("name") for p in r.json().get("profiles", [])]
                self.assertIn("car", profiles, key)


class OptimizerDistanceInputTests(unittest.TestCase):
    """Optimizer accepts routing distances without changing hard constraints."""

    @NEED_BOTH
    def test_optimizer_with_real_distances_respects_capacity(self):
        sites = build_sites_from_demo()
        # override distances with PostGIS geodesic inputs
        for s in sites:
            d = asyncio.run(_run(
                spatial_service.get_spatial_distance, "munnar-central", s.id
            ))
            self.assertIsNotNone(d)
            s.distance_km = d["distance_km"]
        result = run_optimization(demand=4210, sites=sites)
        self.assertEqual(result.status, "FEASIBLE")
        self.assertEqual(result.total_allocated, 4210)
        self.assertEqual(result.unallocated, 0)
        for alloc in result.allocations:
            site = next(s for s in sites if s.id == alloc.site_id)
            self.assertLessEqual(alloc.allocated_population, site.c_safe)
        self.assertEqual(sum(a.allocated_population for a in result.allocations), 4210)

    def test_demo_default_unchanged(self):
        # frozen golden baseline (Phase 1) must hold with the default inputs
        result = run_optimization(demand=4210, sites=build_sites_from_demo())
        self.assertEqual(result.status, "FEASIBLE")
        alloc = {a.site_id: a.allocated_population for a in result.allocations}
        self.assertEqual(alloc.get("site-c"), 1800)
        self.assertEqual(alloc.get("site-a"), 2410)
        self.assertEqual(alloc.get("site-b", 0), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
