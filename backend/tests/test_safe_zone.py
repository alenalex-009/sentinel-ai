"""Slice 4 — safe-zone engine tests.

Pure-logic tests (grid, haversine, classify, scoring) always run; the
DB-backed discovery, constraint evaluation and API contract are exercised with
`_safe_query`-level helpers patched so no real database is needed.

Run from backend/:
    python -m unittest tests.test_safe_zone -v
"""

import unittest
from unittest import mock

from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import safe_zone_service as sz
from app.main import app

_CENTROID = (10.1123, 77.0812)  # near site-a so de-dupe triggers


class FakeSession:
    """Stub AsyncSession-like object — persistence calls succeed silently."""

    async def execute(self, *a, **kw):
        class _R:
            async def all(self):  # pragma: no cover
                return []

        return _R()

    async def commit(self):
        return None

    async def rollback(self):
        return None


def _evidence(fault_km=None, hazard_km=None, fail=None):
    """Canned evaluate_point-style evidence dict."""
    constraints = {
        "slope": {"passed": None, "status": "UNAVAILABLE", "reason": "no DEM"},
        "land_use": {"passed": None, "status": "UNAVAILABLE", "reason": "no layer"},
        "water_proximity": {"passed": None, "status": "UNAVAILABLE", "reason": "no layer"},
    }
    if fault_km is None:
        constraints["fault_proximity"] = {"passed": None, "status": "UNAVAILABLE"}
    else:
        passed = fault_km >= settings.SAFE_ZONE_FAULT_BUFFER_KM
        constraints["fault_proximity"] = {"passed": passed, "status": "OK" if passed else "FAIL"}
    if hazard_km is None:
        constraints["active_hazard"] = {"passed": None, "status": "UNAVAILABLE"}
    else:
        passed = hazard_km >= 0.0
        constraints["active_hazard"] = {"passed": passed, "status": "OK" if passed else "FAIL"}

    if fail is None:
        failed = [
            k for k, v in constraints.items()
            if isinstance(v, dict) and v.get("passed") is False
        ]
    else:
        failed = fail
    return {
        "constraint_pass": not failed,
        "constraining": failed,
        "constraints": constraints,
        "basis": {
            "fault": {"nearest_epicenter_km": fault_km},
            "active_hazard": {"nearest_polygon_km": hazard_km},
        },
    }


class GridAndGeoLogicTests(unittest.TestCase):
    def test_grid_points_deterministic(self):
        a = sz.grid_points(10.0, 77.0, 5.0, 3.0)
        b = sz.grid_points(10.0, 77.0, 5.0, 3.0)
        self.assertEqual(a, b)

    def test_grid_points_all_within_radius(self):
        r = 5.0
        pts = sz.grid_points(10.0, 77.0, r, 3.0)
        self.assertGreater(len(pts), 1)
        for lat, lon in pts:
            self.assertLessEqual(sz._haversine_km(10.0, 77.0, lat, lon), r + 1e-6)

    def test_grid_grows_with_radius(self):
        small = sz.grid_points(10.0, 77.0, 3.0, 3.0)
        big = sz.grid_points(10.0, 77.0, 6.0, 3.0)
        self.assertGreater(len(big), len(small))

    def test_haversine_symmetric(self):
        d1 = sz._haversine_km(10.0, 77.0, 10.5, 77.5)
        d2 = sz._haversine_km(10.5, 77.5, 10.0, 77.0)
        self.assertAlmostEqual(d1, d2, places=6)
        self.assertGreater(d1, 0)

    def test_haversine_zero(self):
        self.assertAlmostEqual(sz._haversine_km(10.0, 77.0, 10.0, 77.0), 0.0, places=6)


class ClassifyTests(unittest.TestCase):
    def test_green_threshold(self):
        self.assertEqual(sz.classify(80, 80, True), "green")

    def test_yellow_suitability_below_70(self):
        self.assertEqual(sz.classify(68, 80, True), "yellow")

    def test_red_safety_below_40(self):
        self.assertEqual(sz.classify(80, 35, True), "red")

    def test_red_hard_constraint_failure(self):
        self.assertEqual(sz.classify(80, 80, False), "red")

    def test_red_suitability_below_50(self):
        self.assertEqual(sz.classify(45, 80, True), "red")


class ScoreCandidateTests(unittest.TestCase):
    def test_existing_uses_seeded_suitability_and_capacity(self):
        site = {"id": "site-a", "name": "Site A", "suitability_score": 82.0, "safe_capacity": 3200,
                "lat": _CENTROID[0], "lon": _CENTROID[1]}
        out = sz.score_candidate(_CENTROID[0], _CENTROID[1], _evidence(fault_km=50, hazard_km=80), existing=site)
        self.assertEqual(out["suitability_score"], 82.0)
        self.assertEqual(out["estimated_capacity"], 3200)
        self.assertEqual(out["suitability_basis"], "seeded site assessment")

    def test_discovered_uses_nominal_basis(self):
        out = sz.score_candidate(10.1, 77.0, _evidence(fault_km=50, hazard_km=80))
        self.assertEqual(out["suitability_score"], 65.0)
        self.assertEqual(out["estimated_capacity"], 0)
        self.assertEqual(out["capacity_basis"], "no parcel data — capacity unassessed")

    def test_fault_proximity_penalty_math(self):
        # buf 10 km; epicenter 18 km → penalty = 30*(1-(8/30)) = 22 → safety 58
        out = sz.score_candidate(10.1, 77.0, _evidence(fault_km=18.0, hazard_km=80))
        self.assertAlmostEqual(out["safety_score"], 58.0, places=4)

    def test_far_fault_no_penalty(self):
        out = sz.score_candidate(10.1, 77.0, _evidence(fault_km=60, hazard_km=80))
        self.assertEqual(out["safety_score"], 80.0)

    def test_hazard_proximity_penalty(self):
        # hazard at 20 km → penalty = 30*(1-(20/40)) = 15 → safety 65
        out = sz.score_candidate(10.1, 77.0, _evidence(fault_km=60, hazard_km=20))
        self.assertAlmostEqual(out["safety_score"], 65.0, places=4)

    def test_inside_fault_buffer_zeroes_safety(self):
        out = sz.score_candidate(10.1, 77.0, _evidence(fault_km=2.0, hazard_km=80))
        self.assertEqual(out["safety_score"], 0.0)

    def test_unavailable_inputs_no_penalty(self):
        out = sz.score_candidate(10.1, 77.0, _evidence())
        self.assertEqual(out["safety_score"], 80.0)
        self.assertEqual(out["suitability_score"], 65.0)


class EvaluatePointTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_ok_passes(self):
        with mock.patch.object(sz, "_fault_distance_km", return_value=50.0), \
             mock.patch.object(sz, "_nearest_hazard_km", return_value=80.0):
            ev = await sz.evaluate_point(FakeSession(), 77.0, 10.0)
        self.assertTrue(ev["constraint_pass"])
        self.assertEqual(ev["constraints"]["fault_proximity"]["status"], "OK")
        self.assertEqual(ev["constraints"]["active_hazard"]["status"], "OK")

    async def test_fault_too_close_fails(self):
        with mock.patch.object(sz, "_fault_distance_km", return_value=2.0), \
             mock.patch.object(sz, "_nearest_hazard_km", return_value=80.0):
            ev = await sz.evaluate_point(FakeSession(), 77.0, 10.0)
        self.assertFalse(ev["constraint_pass"])
        self.assertIn("fault_proximity", ev["constraining"])
        self.assertEqual(ev["constraints"]["fault_proximity"]["status"], "FAIL")

    async def test_hazard_inside_fails(self):
        with mock.patch.object(sz, "_fault_distance_km", return_value=50.0), \
             mock.patch.object(sz, "_nearest_hazard_km", return_value=0.0):
            ev = await sz.evaluate_point(FakeSession(), 77.0, 10.0)
        self.assertFalse(ev["constraint_pass"])
        self.assertIn("active_hazard", ev["constraining"])

    async def test_db_down_is_unavailable_not_fail(self):
        with mock.patch.object(sz, "_fault_distance_km", return_value=None), \
             mock.patch.object(sz, "_nearest_hazard_km", return_value=None):
            ev = await sz.evaluate_point(FakeSession(), 77.0, 10.0)
        self.assertTrue(ev["constraint_pass"])
        self.assertEqual(ev["constraints"]["fault_proximity"]["status"], "UNAVAILABLE")
        self.assertEqual(ev["constraints"]["active_hazard"]["status"], "UNAVAILABLE")


class DiscoverCandidatesTests(unittest.IsolatedAsyncioTestCase):
    async def test_discover_includes_existing_sites(self):
        existing = [
            {"id": "site-a", "name": "Site A", "suitability_score": 82.0, "safe_capacity": 3200,
             "lat": 10.1123, "lon": 77.0812},
            {"id": "site-b", "name": "Site B", "suitability_score": 74.0, "safe_capacity": 2100,
             "lat": 10.0634, "lon": 77.1234},
        ]
        with mock.patch.object(sz, "_district_point", return_value=_CENTROID), \
             mock.patch.object(sz, "_existing_sites", return_value=existing), \
             mock.patch.object(sz, "evaluate_point", return_value=_evidence(fault_km=50, hazard_km=80)), \
             mock.patch.object(sz, "_persist_candidates") as persist:
            out = await sz.discover_candidates(FakeSession(), "idukki")
        persist.assert_called_once()
        sites = [c for c in out["candidates"] if c["source"] == "existing"]
        self.assertEqual(len(sites), 2)
        self.assertEqual(sites[0]["id"], "idukki-site-site-a")
        self.assertEqual(sites[0]["suitability_score"], 82.0)

    def _discover(self, existing):
        async def _run():
            with mock.patch.object(sz, "_district_point", return_value=_CENTROID), \
                 mock.patch.object(sz, "_existing_sites", return_value=existing), \
                 mock.patch.object(sz, "evaluate_point", return_value=_evidence(fault_km=50, hazard_km=80)), \
                 mock.patch.object(sz, "_persist_candidates"), \
                 mock.patch.object(settings, "SAFE_ZONE_GRID_RADIUS_KM", 5.0), \
                 mock.patch.object(settings, "SAFE_ZONE_GRID_SPACING_KM", 3.0):
                return await sz.discover_candidates(FakeSession(), "idukki")
        return _run()

    async def test_discover_deterministic_ids(self):
        existing = [{"id": "site-a", "name": "Site A", "suitability_score": 82.0, "safe_capacity": 3200,
                     "lat": 10.1123, "lon": 77.0812}]
        r1 = await self._discover(existing)
        r2 = await self._discover(existing)
        ids1 = [c["id"] for c in r1["candidates"]]
        ids2 = [c["id"] for c in r2["candidates"]]
        self.assertEqual(ids1, ids2)
        self.assertEqual(len(set(ids1)), len(ids1))

    async def test_discover_dedupes_grid_near_existing(self):
        existing = [{"id": "site-a", "name": "Site A", "suitability_score": 82.0, "safe_capacity": 3200,
                     "lat": 10.1123, "lon": 77.0812}]
        out = await self._discover(existing)
        # no discovered point should sit within merge half-spacing of site-a
        for c in out["candidates"]:
            if c["source"] == "discovered":
                self.assertGreater(
                    sz._haversine_km(c["latitude"], c["longitude"], 10.1123, 77.0812),
                    settings.SAFE_ZONE_GRID_SPACING_KM / 2.0 - 1e-6,
                    msg=f"{c['id']} too close to existing site-a",
                )

    async def test_discover_marks_persisted(self):
        existing = [{"id": "site-a", "name": "Site A", "suitability_score": 82.0, "safe_capacity": 3200,
                     "lat": 10.1123, "lon": 77.0812}]
        out = await self._discover(existing)
        self.assertTrue(out["persisted"])
        self.assertEqual(out["district_id"], "idukki")
        self.assertGreater(out["candidates_count"], 0)

    async def test_discover_centroid_unavailable_is_empty(self):
        with mock.patch.object(sz, "_district_point", return_value=None):
            out = await sz.discover_candidates(FakeSession(), "idukki")
        self.assertEqual(out["candidates_count"], 0)
        self.assertEqual(out["candidates"], [])


class SafeZoneApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self._d = sz.discover_candidates
        self._g = sz.get_safe_zones

    def tearDown(self):
        sz.discover_candidates = self._d
        sz.get_safe_zones = self._g

    async def _fake_discover(self, session, district_id="idukki"):
        return {
            "district_id": district_id,
            "source": "postgis",
            "data_status": "DEMO",
            "candidates": [{
                "id": "idukki-site-site-a", "name": "Site A", "source": "existing",
                "latitude": 10.1123, "longitude": 77.0812,
                "suitability_score": 82.0, "safety_score": 80.0,
                "estimated_capacity": 3200, "constraint_pass": True,
                "constraints": {}, "constraining": [], "status": "green",
                "data_status": "DEMO", "data_type": "DERIVED",
            }],
            "candidates_count": 1,
            "persisted": True,
        }

    async def _fake_zones(self, session, district_id="idukki", refresh=False):
        return {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [77.0812, 10.1123]},
                "properties": {"id": "idukki-site-site-a", "name": "Site A", "status": "green"},
            }],
            "district_id": district_id,
            "data_status": "DEMO",
            "classification": "DERIVED",
            "status_counts": {"green": 1, "yellow": 0, "red": 0},
            "candidates_count": 1,
        }

    def test_post_discover_endpoint(self):
        sz.discover_candidates = self._fake_discover
        r = self.client.post("/api/v1/spatial/safe-zones/discover?district_id=idukki")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["district_id"], "idukki")
        self.assertEqual(body["candidates_count"], 1)
        self.assertTrue(body["persisted"])

    def test_get_safe_zones_endpoint(self):
        sz.get_safe_zones = self._fake_zones
        r = self.client.get("/api/v1/spatial/safe-zones?district_id=idukki")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["type"], "FeatureCollection")
        self.assertEqual(body["features"][0]["properties"]["status"], "green")
        self.assertEqual(body["status_counts"]["green"], 1)


if __name__ == "__main__":
    unittest.main()