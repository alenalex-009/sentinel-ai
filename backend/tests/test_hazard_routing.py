"""Tests for hazard-aware routing, alternatives, isochrones and matrix (Phase 6)."""

import unittest
from unittest.mock import patch


class ScoreRouteTests(unittest.TestCase):
    def setUp(self):
        from app.services import hazard_aware_routing as h
        self.h = h

    def _line(self, lon_a, lat_a, lon_b, lat_b, steps=2):
        return [[lon_a + (lon_b - lon_a) * i / (steps - 1),
                 lat_a + (lat_b - lat_a) * i / (steps - 1)] for i in range(steps)]

    def test_outside_buffer_scores_zero(self):
        # Idukki: ~90km line east-west; hazard 40km north → no inside length.
        coords = self._line(76.8, 9.7, 77.5, 9.7)
        events = [{
            "event_id": "e1", "hazard_type": "RAINFALL",
            "severity_level": "SEVERE", "severity_score": 90.0,
            "centroid_lat": 10.2, "centroid_lon": 77.1,
            "buffer_radius_km": 15.0,
        }]
        analysis = self.h.score_route_coords(coords, events)
        self.assertEqual(analysis["exposures"], [])
        self.assertEqual(analysis["route_risk_score"], 0.0)
        self.assertEqual(analysis["risk_label"], "LOW")

    def test_inside_buffer_reports_exposure_and_score(self):
        coords = self._line(77.0, 10.0, 77.2, 10.0, steps=5)
        events = [{
            "event_id": "e1", "hazard_type": "RAINFALL",
            "severity_level": "SEVERE", "severity_score": 90.0,
            "centroid_lat": 10.0, "centroid_lon": 77.1,
            "buffer_radius_km": 50.0,  # covers the whole line
        }]
        analysis = self.h.score_route_coords(coords, events)
        self.assertEqual(len(analysis["exposures"]), 1)
        exp = analysis["exposures"][0]
        self.assertEqual(exp["event_id"], "e1")
        self.assertAlmostEqual(exp["fraction"], 1.0, places=3)
        self.assertEqual(exp["contribution"], 90.0)
        self.assertEqual(analysis["route_risk_score"], 90.0)
        self.assertEqual(analysis["risk_label"], "EXTREME")

    def test_partial_exposure_scales_with_fraction(self):
        # 30km line, hazard buffer 8km around the far end → partial fraction
        coords = self._line(77.0, 10.0, 77.3, 10.0, steps=20)
        events = [{
            "event_id": "e1", "hazard_type": "QUAKE",
            "severity_level": "MODERATE", "severity_score": 40.0,
            "centroid_lat": 10.0, "centroid_lon": 77.3,
            "buffer_radius_km": 8.0,
        }]
        analysis = self.h.score_route_coords(coords, events)
        self.assertEqual(len(analysis["exposures"]), 1)
        exp = analysis["exposures"][0]
        self.assertLess(exp["fraction"], 0.5)
        self.assertAlmostEqual(
            exp["contribution"],
            round(20.0 * exp["fraction"], 1), places=1,
        )

    def test_risk_labels(self):
        self.assertEqual(self.h._risk_label(5), "LOW")
        self.assertEqual(self.h._risk_label(10), "MODERATE")
        self.assertEqual(self.h._risk_label(40), "HIGH")
        self.assertEqual(self.h._risk_label(99), "EXTREME")


class HazardAwareRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from app.services import hazard_aware_routing as h
        self.h = h

    @patch("app.services.hazard_aware_routing.current_hazards")
    @patch("app.services.hazard_aware_routing._resolve_region_gate")
    @patch("app.services.hazard_aware_routing._best_portfolio_route")
    async def test_ok_route_gets_analysis_even_with_empty_hazards(
        self, portfolio, gate, current_hazards
    ):
        session = object()
        gate.return_value = (type("Cfg", (), {"key": "kerala"}), None)
        current_hazards.return_value = {"events": []}
        coords = [[77.0, 10.0], [77.3, 10.0]]
        base = {
            "status": "OK", "habitation_id": "h1", "site_id": "s1",
            "engine": "graphhopper", "region": {}, "route": {},
            "route_geojson": {"geometry": {"coordinates": coords}},
            "hazard_analysis": self.h.score_route_coords(coords, []),
        }
        portfolio.return_value = [base]
        result = await self.h.hazard_aware_route(session, "h1", "s1")
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["hazard_analysis"]["route_risk_score"], 0.0)
        self.assertTrue(result["hazard_analysis"]["hazard_empty"])
        self.assertFalse(result["avoidance"]["avoided"])

    @patch("app.services.hazard_aware_routing.current_hazards")
    @patch("app.services.hazard_aware_routing._resolve_region_gate")
    @patch("app.services.hazard_aware_routing._best_portfolio_route")
    async def test_unavailable_engine_is_honest(self, portfolio, gate, current_hazards):
        session = object()
        gate.return_value = (type("Cfg", (), {"key": "kerala"}), None)
        current_hazards.return_value = {"events": []}
        unavailable = {
            "status": "UNAVAILABLE", "reason": "no osrm configured",
            "habitation_id": "h1", "site_id": "s1", "engine": "osrm",
        }
        portfolio.return_value = [unavailable]
        result = await self.h.hazard_aware_route(session, "h1", "s1", engine="osrm")
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIsNone(result["hazard_analysis"]["route_risk_score"])
        self.assertEqual(result["hazard_analysis"]["reason"], "no osrm configured")

    @patch("app.services.hazard_aware_routing.current_hazards")
    @patch("app.services.hazard_aware_routing._resolve_region_gate")
    @patch("app.services.hazard_aware_routing._best_portfolio_route")
    async def test_avoidance_switches_when_alternative_is_safer(
        self, portfolio, gate, current_hazards
    ):
        session = object()
        cfg = type("Cfg", (), {"key": "kerala"})
        gate.return_value = (cfg, None)
        events = [{
            "event_id": "e1", "hazard_type": "RAINFALL",
            "severity_level": "SEVERE", "severity_score": 90.0,
            "centroid_lat": 10.0, "centroid_lon": 77.05,
            "buffer_radius_km": 50.0,
        }]
        current_hazards.return_value = {"events": events}

        def mk(coords, label):
            return {
                "status": "OK", "habitation_id": "h1", "site_id": "s1",
                "engine": "graphhopper", "region": {}, "route": {"label": label},
                "route_geojson": {"geometry": {"coordinates": coords}},
                "hazard_analysis": self.h.score_route_coords(coords, events),
            }

        base = mk([[77.0, 10.0], [77.1, 10.0]], "base")   # wholly inside → high risk
        safe = mk([[77.0, 10.0], [77.1, 11.0]], "safe")   # ~110km north → 0 risk
        # but base may be safer than safe on fractions — force clear separation
        base["hazard_analysis"]["route_risk_score"] = 90.0
        base["hazard_analysis"]["risk_label"] = "EXTREME"
        safe["hazard_analysis"]["route_risk_score"] = 0.0
        safe["hazard_analysis"]["risk_label"] = "LOW"
        portfolio.return_value = [base, safe]

        result = await self.h.hazard_aware_route(session, "h1", "s1", avoid_hazards=True)
        self.assertTrue(result["avoidance"]["avoided"])
        self.assertEqual(result["route"]["label"], "safe")

        result_no = await self.h.hazard_aware_route(session, "h1", "s1", avoid_hazards=False)
        self.assertFalse(result_no["avoidance"]["avoided"])
        self.assertEqual(result_no["route"]["label"], "base")


if __name__ == "__main__":
    unittest.main()