"""API tests for Phase 6 routing endpoints (hazard-aware / alternatives / isochrones / matrix)."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class Phase6ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_hazard_aware_endpoint_404_on_unknown_ids(self):
        r = self.client.post(
            "/api/v1/routing/hazard-aware",
            json={"habitation_id": "no-such", "site_id": "no-such"},
        )
        self.assertEqual(r.status_code, 404)

    def test_hazard_aware_endpoint_returns_analysis_with_mocked_route(self):
        import app.services.hazard_aware_routing as h
        coords = [[77.0, 10.0], [77.2, 10.0]]
        ok_route = {
            "status": "OK", "habitation_id": "h1", "site_id": "s1",
            "engine": "graphhopper", "region": {"key": "kerala"},
            "route": {"label": "base"}, "route_geojson": {"geometry": {"coordinates": coords}},
            "hazard_analysis": h.score_route_coords(coords, []),
        }
        with patch.object(h, "_resolve_region_gate", return_value=(type("C", (), {"key": "kerala"}), None)), \
             patch.object(h, "_best_portfolio_route", return_value=[ok_route]):
            r = self.client.post(
                "/api/v1/routing/hazard-aware",
                json={"habitation_id": "h1", "site_id": "s1", "engine": "graphhopper"},
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "OK")
        self.assertIn("hazard_analysis", body)
        self.assertIn("avoidance", body)
        self.assertTrue(body["hazard_analysis"]["hazard_empty"])

    def test_alternatives_endpoint_unknown_ids_404(self):
        r = self.client.post(
            "/api/v1/routing/alternatives",
            json={"habitation_id": "x", "site_id": "y"},
        )
        self.assertEqual(r.status_code, 404)

    def test_isochrones_honest_unavailable_offline(self):
        # No Valhalla URL configured → honest UNAVAILABLE, never fake polygons.
        r = self.client.post(
            "/api/v1/routing/isochrones",
            json={"region": "kerala", "lat": 10.0, "lon": 77.1, "contours_min": [10, 20]},
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "UNAVAILABLE")
        self.assertIn("no valhalla", body["reason"].lower())
        self.assertEqual(body["feature_collection"]["features"], [])

    def test_matrix_endpoint_unknown_ids_honest(self):
        r = self.client.post(
            "/api/v1/routing/matrix",
            json={"habitation_ids": ["x"], "site_ids": ["y"]},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data_status"], "UNAVAILABLE")

    def test_engines_status_shape(self):
        r = self.client.get("/api/v1/routing/engines", params={"region": "kerala"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()["engines"].keys()), {"graphhopper", "osrm", "valhalla"})


if __name__ == "__main__":
    unittest.main()