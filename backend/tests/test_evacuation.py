"""Task B2 — evacuation overview synthesis tests.

Service tests mock every live dependency (hazards, demand, safe zones, route
helpers) so assertions focus on synthesis shape, provenance and gap math. The
DB-down path exercises the demo_fallback labelling without a database.
"""

import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app
from app.services.optimizer import OptimizationOutput

_HAZARD_EVENT = {
    "event_id": "e1",
    "hazard_type": "LANDSLIDE",
    "severity_level": "SEVERE",
    "severity_score": 90.0,
    "centroid_lat": 10.0,
    "centroid_lon": 77.0,
    "started_at": "2026-09-10T00:00:00+00:00",
    "source": "test-source",
    "data_type": "RAINFALL-PERSISTED",
}

_HAZARDS_PAYLOAD = {
    "data_status": "LIVE",
    "generated_at": "2026-09-10T00:00:00+00:00",
    "region": "all",
    "summary": "1 active hazard event(s).",
    "events": [_HAZARD_EVENT],
    "feature_collection": {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"event_id": "e1", "hazard_type": "LANDSLIDE"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[77.0, 10.0], [77.1, 10.0], [77.1, 10.1], [77.0, 10.1]]],
            },
        }],
    },
}

_EMPTY_HAZARDS_PAYLOAD = {
    "data_status": "EMPTY",
    "generated_at": "2026-09-10T00:00:00+00:00",
    "region": "all",
    "summary": "No active events.",
    "events": [],
    "feature_collection": {"type": "FeatureCollection", "features": []},
}

_DEMAND_PAYLOAD = {
    "data_status": "DERIVED",
    "district_id": "idukki",
    "total_demand": 1200,
    "demand_habitations": 2,
    "habitations": [
        {"habitation_id": "h1", "name": "Munnar Central", "population": 800,
         "current_score": 85.0, "relocation_demand": 800},
        {"habitation_id": "h2", "name": "Habitation B", "population": 400,
         "current_score": 70.0, "relocation_demand": 400},
        {"habitation_id": "h3", "name": "Habitation C", "population": 500,
         "current_score": 20.0, "relocation_demand": 0},
    ],
    "note": "Test demand.",
}

_DEMO_DEMAND_PAYLOAD = {
    "data_status": "DEMO",
    "district_id": "idukki",
    "total_demand": 0,
    "habitations": [],
    "note": "PostGIS unavailable.",
}

_SITES = [
    {"id": "s1", "name": "Site A", "geom": None, "suitability_score": 80.0,
     "safety_score": 90.0, "estimated_capacity": 600, "constraint_pass": True,
     "constraint_evidence": None, "lon": 77.08, "lat": 10.11},
    {"id": "s2", "name": "Site B", "geom": None, "suitability_score": 70.0,
     "safety_score": 80.0, "estimated_capacity": 400, "constraint_pass": True,
     "constraint_evidence": None, "lon": 77.2, "lat": 10.2},
]

_SZ_PAYLOAD = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [77.08, 10.11]},
         "properties": {"id": "s1", "name": "Site A", "longitude": 77.08, "latitude": 10.11,
                        "suitability_score": 80.0, "safety_score": 90.0,
                        "estimated_capacity": 600, "status": "green", "data_status": "DEMO"}},
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [77.2, 10.2]},
         "properties": {"id": "s2", "name": "Site B", "longitude": 77.2, "latitude": 10.20,
                        "suitability_score": 70.0, "safety_score": 80.0,
                        "estimated_capacity": 400, "status": "green", "data_status": "DEMO"}},
    ],
    "data_status": "DEMO",
    "status_counts": {"green": 2, "yellow": 0, "red": 0},
    "_source": "postgis",
    "note": "Test safe zones.",
}

_SZ_EMPTY_PAYLOAD = {
    "type": "FeatureCollection", "features": [], "data_status": "DEMO",
    "status_counts": {"green": 0, "yellow": 0, "red": 0},
    "_source": "empty — discovery not run", "note": "Empty.",
}

_OK_ROUTE = {
    "status": "OK",
    "habitation_id": "h1",
    "site_id": "s1",
    "engine": "valhalla",
    "region": {"key": "kerala", "display": "Kerala"},
    "route": {"distance_m": 8234.1, "distance_km": 8.23, "duration_min": 12.4,
              "duration_s": 744.0, "unit": "km", "time_unit": "min",
              "classification": "DERIVED", "source": "OpenStreetMap + Valhalla",
              "method": "road-network route", "computed_at": "2026-09-10T00:00:00+00:00"},
    "route_geojson": {
        "type": "Feature",
        "geometry": {"type": "LineString",
                     "coordinates": [[77.0625, 10.0889], [77.08, 10.11]]},
        "properties": {"habitation_id": "h1", "site_id": "s1", "engine": "valhalla"},
    },
    "hazard_analysis": {"route_risk_score": 30.0, "risk_label": "MODERATE",
                        "exposures": [], "events_evaluated": 1, "hazard_empty": False},
    "avoidance": {"enabled": True, "avoided": False, "candidates_count": 1},
}

_OK_ALTERNATIVES = {
    "status": "OK",
    "engine": "valhalla",
    "routes": [{"index": 0, "distance_km": 8.23}, {"index": 1, "distance_km": 9.1}],
}

_FAKE_OPT = OptimizationOutput(
    status="PARTIAL", total_demand=1200, total_allocated=1000, unallocated=200,
    allocations=[], objective_value=0.0, constraints_applied=[], solver_note="test",
    data_status="DERIVED",
)


def _patch_live_services():
    stack = ExitStack()
    stack.enter_context(patch("app.services.hazard_service.current_hazards",
                              new=AsyncMock(return_value=_HAZARDS_PAYLOAD)))
    stack.enter_context(patch("app.services.relocation_service.calculate_demand",
                              new=AsyncMock(return_value=_DEMAND_PAYLOAD)))
    stack.enter_context(patch("app.services.relocation_service.get_safe_zone_sites",
                              new=AsyncMock(return_value=list(_SITES))))
    stack.enter_context(patch("app.services.safe_zone_service.get_safe_zones",
                              new=AsyncMock(return_value=_SZ_PAYLOAD)))
    stack.enter_context(patch("app.services.evacuation_service._resolve_habitation",
                              new=AsyncMock(return_value=(10.0889, 77.0625, "postgis"))))
    stack.enter_context(patch("app.services.multi_engine_routing.pick_engine",
                              new=AsyncMock(return_value="valhalla")))
    stack.enter_context(patch("app.services.hazard_aware_routing.hazard_aware_route",
                              new=AsyncMock(return_value=_OK_ROUTE)))
    stack.enter_context(patch("app.services.multi_engine_routing.route_alternatives",
                              new=AsyncMock(return_value=_OK_ALTERNATIVES)))
    stack.enter_context(patch("app.services.evacuation_service.run_optimization",
                              return_value=_FAKE_OPT))
    return stack


def _patch_dbdown_services():
    stack = ExitStack()
    stack.enter_context(patch("app.services.hazard_service.current_hazards",
                              new=AsyncMock(return_value=_EMPTY_HAZARDS_PAYLOAD)))
    stack.enter_context(patch("app.services.relocation_service.calculate_demand",
                              new=AsyncMock(return_value=_DEMO_DEMAND_PAYLOAD)))
    stack.enter_context(patch("app.services.relocation_service.get_safe_zone_sites",
                              new=AsyncMock(return_value=None)))
    stack.enter_context(patch("app.services.safe_zone_service.get_safe_zones",
                              new=AsyncMock(return_value=_SZ_EMPTY_PAYLOAD)))
    stack.enter_context(patch("app.services.evacuation_service.run_optimization",
                              return_value=_FAKE_OPT))
    return stack


class EvacuationServiceTests(unittest.IsolatedAsyncioTestCase):

    async def test_live_overview_shape_and_blocks(self):
        from app.services import evacuation_service as ev
        with _patch_live_services():
            out = await ev.build_overview(None, "idukki")
        self.assertEqual(out["data_status"], "LIVE")
        self.assertEqual(out["region"], "idukki")
        self.assertEqual(out["disaster_type"], "LANDSLIDE")
        # hazards
        self.assertEqual(out["hazards"]["status"], "ACTIVE")
        self.assertEqual(len(out["hazards"]["danger_zones"]), 1)
        self.assertEqual(out["hazards"]["provenance"]["source"], "live")
        # affected
        self.assertEqual(out["affected_habitations"]["affected_count"], 2)
        self.assertEqual(out["affected_habitations"]["population_at_risk"], 1200)
        # demand / capacity / gap math
        dc = out["demand_capacity"]
        self.assertEqual(dc["total_demand"], 1200)
        self.assertEqual(dc["capacity"], 1000)
        self.assertEqual(dc["capacity_gap"], 200)
        self.assertEqual(dc["optimization"]["unallocated"], 200)
        # safe zones enriched
        fc = out["safe_zones"]["feature_collection"]["features"]
        self.assertEqual(len(fc), 2)
        enabling = {f["properties"]["id"]: f["properties"] for f in fc}
        self.assertEqual(enabling["s1"]["capacity"], 600)
        self.assertIsNotNone(enabling["s1"]["distance_km"])
        self.assertEqual(enabling["s1"]["distance_basis"], "straight-line (DEMO)")
        # recommendation uses policy picker
        rec = out["recommendation"]
        self.assertEqual(rec["status"], "OK")
        self.assertEqual(rec["engine"], "valhalla")
        self.assertEqual(rec["served_by"], "valhalla")
        self.assertEqual(rec["recommended_site"]["id"], "s1")
        self.assertFalse(rec["fallback_used"])
        self.assertEqual(rec["route"]["distance_km"], 8.23)
        self.assertEqual(rec["hazard_analysis"]["risk_label"], "MODERATE")
        # alternatives
        self.assertEqual(out["alternatives"]["status"], "OK")
        self.assertLessEqual(len(out["alternatives"]["routes"]), 3)
        # evacuation status
        es = out["evacuation_status"]
        self.assertTrue(es["hazard_active"])
        self.assertEqual(es["capacity_gap"], 200)
        self.assertEqual(es["level"], "CRITICAL")
        for block in ("hazards", "affected_habitations", "demand_capacity",
                      "safe_zones", "recommendation", "alternatives", "evacuation_status"):
            self.assertIn("provenance", out[block])
            self.assertIn("generated_at", out[block]["provenance"])

    async def test_db_down_endpoint_is_honest_and_200(self):
        from app.services import evacuation_service as ev
        with _patch_dbdown_services():
            out = await ev.build_overview(None, "idukki")
        self.assertEqual(out["data_status"], "DEMO")
        self.assertEqual(out["hazards"]["status"], "NO_ACTIVE_EVENT")
        self.assertEqual(out["hazards"]["provenance"]["source"], "empty")
        self.assertEqual(out["affected_habitations"]["affected_count"], 0)
        self.assertEqual(out["affected_habitations"]["provenance"]["source"], "demo_fallback")
        self.assertEqual(out["demand_capacity"]["capacity"], 0)
        self.assertEqual(out["demand_capacity"]["capacity_gap"], 0)
        self.assertEqual(out["demand_capacity"]["provenance"]["source"], "demo_fallback")
        self.assertEqual(out["safe_zones"]["provenance"]["source"], "demo_fallback")
        self.assertEqual(out["safe_zones"]["feature_collection"]["features"], [])
        self.assertEqual(out["recommendation"]["status"], "UNAVAILABLE")
        self.assertEqual(out["recommendation"]["engine"], None)
        self.assertEqual(out["alternatives"]["status"], "UNAVAILABLE")
        self.assertEqual(out["evacuation_status"]["level"], "NORMAL")


class EvacuationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = lambda: None
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_db, None)

    def test_overview_endpoint_200_with_mocked_services(self):
        with _patch_dbdown_services():
            r = self.client.get("/api/v1/evacuation/overview",
                                params={"region": "idukki"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "DEMO")
        self.assertIn("hazards", body)
        self.assertIn("recommendation", body)
        self.assertIn("evacuation_status", body)

    def test_overview_endpoint_reports_no_active_event(self):
        with _patch_dbdown_services():
            r = self.client.get("/api/v1/evacuation/overview")
        self.assertEqual(r.json()["hazards"]["status"], "NO_ACTIVE_EVENT")


if __name__ == "__main__":
    unittest.main()