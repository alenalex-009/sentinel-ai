"""Task B4 — reports summary synthesis endpoint tests.

Live path mocks every live service; the DB-down path swaps them for their
honest DEMO/UNAVAILABLE fallbacks and still expects a 200 with labelled
sections. Section names mirror Reports.tsx (district / habitation / demand /
capacity / optimization / scenario / routing / hazard_context / plan).

Regression targets:
  - capacity_gap = max(0, demand - capacity) — a shortage, never a surplus.
  - optimization runs the real solver over the LIVE candidate sites with the
    LIVE demand (never the DEMO 4210 constant mixed into live provenance).
  - served_by / fallback_used reflect the engine that actually served.
"""

import copy
import unittest
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.db.database import get_db
from app.main import app

_RISK_LIVE = {
    "data_status": "LIVE",
    "district_id": "idukki",
    "basis": {"weather": {"data_status": "LIVE"}},
    "habitations": [{
        "id": "munnar-central", "name": "Munnar Central", "population": 4210,
        "current_score": 94.0, "current_score_rounded": 94,
        "baseline_score": 80.21, "data_status": "LIVE",
    }],
}

_RISK_DEMO = {"data_status": "DEMO", "district_id": "idukki", "basis": {}, "habitations": []}

_TIMELINE = {
    "data_status": "LIVE", "habitation_id": "munnar-central",
    "points": [{"computed_at": "2026-09-10T00:00:00+00:00",
                "current_score": 94, "baseline_score": 80.21, "event_escalation": 13.65}],
}
_TIMELINE_UNAVAIL = {"data_status": "UNAVAILABLE", "reason": "database connection failed",
                     "points": []}

_DEMAND = {
    "data_status": "DERIVED", "district_id": "idukki", "total_demand": 800,
    "habitations": [{"habitation_id": "munnar-central", "name": "Munnar Central",
                     "population": 800, "current_score": 85.0, "relocation_demand": 800}],
}
_DEMAND_DEMO = {"data_status": "DEMO", "district_id": "idukki", "total_demand": 0,
                "habitations": []}

# Capacity (500) is deliberately BELOW the habitation demand (800) so the
# capacity_gap / unallocated assertions exercise the shortage formula.
_SITES = [{
    "id": "site-a", "name": "Site A", "lon": 77.0812, "lat": 10.1123,
    "suitability_score": 82.0, "safety_score": 88.0, "estimated_capacity": 500,
    "constraint_pass": True, "constraint_evidence": None,
}]

_OK_ROUTE = {
    "status": "OK", "habitation_id": "munnar-central", "site_id": "site-a",
    "engine": "osrm", "region": {"key": "kerala"},
    "route": {"distance_km": 4.2, "duration_min": 12.0},
    "route_geojson": {"type": "Feature",
                      "geometry": {"type": "LineString",
                                   "coordinates": [[77.0595, 10.0889], [77.0812, 10.1123]]}},
    "hazard_analysis": {"route_risk_score": 10.0, "risk_label": "LOW"},
    "avoidance": {"enabled": True, "avoided": False},
}

# Same route but served by the fallback engine (Valhalla) — proves that
# served_by / fallback_used track the engine that actually served.
_OK_ROUTE_FALLBACK = dict(_OK_ROUTE, engine="valhalla")

_HAZARDS = {
    "data_status": "LIVE",
    "events": [{
        "event_id": "e1", "hazard_type": "LANDSLIDE", "severity_level": "SEVERE",
        "severity_score": 90.0, "centroid_lat": 10.08, "centroid_lon": 77.06,
        "buffer_radius_km": 20.0, "started_at": "2026-09-10T00:00:00+00:00",
        "source": "test",
    }],
    "feature_collection": {"type": "FeatureCollection", "features": []},
}
_HAZARDS_EMPTY = {"data_status": "EMPTY", "events": [],
                  "feature_collection": {"type": "FeatureCollection", "features": []}}

_PLAN = {"data_status": "DERIVED", "id": 7, "name": "Test Plan", "status": "approved",
         "assignments": []}
_PLAN_UNAVAIL = {"data_status": "UNAVAILABLE", "reason": "PostGIS unavailable"}

# What db_service returns when PostGIS is up (DB rows merged over demo shape).
_DISTRICT_LIVE = {
    "data_status": "DERIVED",
    "district": {"id": "idukki", "name": "Idukki", "state": "Kerala",
                 "total_habitations": 847},
    "what_changed": [],
    "_source": "postgis",
}
_DETAIL_LIVE = {
    "data_status": "DERIVED",
    "id": "munnar-central", "name": "Munnar Central",
    "ward": "Ward 04", "taluk": "Devikulam", "district": "Idukki", "state": "Kerala",
    "population": 4210, "households": 1053,
    "latitude": 10.0889, "longitude": 77.0595,
    "_source": "postgis",
}

# What db_service returns when PostGIS is down (labelled demo fallback).
_DISTRICT_DEMO = {
    "data_status": "DEMO",
    "district": {"id": "idukki", "name": "Idukki", "state": "Kerala"},
    "what_changed": [],
    "_source": "demo_fallback",
}
_DETAIL_DEMO = {
    "data_status": "DEMO",
    "id": "munnar-central", "name": "Munnar Central",
    "latitude": 10.0889, "longitude": 77.0595,
    "_source": "demo_fallback",
}


def _patch_live(engine="osrm", route=None, plan=_PLAN):
    stack = ExitStack()
    stack.enter_context(patch("app.services.db_service.get_district_overview",
                              new=AsyncMock(return_value=dict(_DISTRICT_LIVE))))
    stack.enter_context(patch("app.services.db_service.get_habitation_detail",
                              new=AsyncMock(return_value=dict(_DETAIL_LIVE))))
    stack.enter_context(patch("app.services.risk_service.current_risk",
                              new=AsyncMock(return_value=_RISK_LIVE)))
    stack.enter_context(patch("app.services.risk_service.get_timeline",
                              new=AsyncMock(return_value=_TIMELINE)))
    stack.enter_context(patch("app.services.relocation_service.calculate_demand",
                              new=AsyncMock(return_value=dict(_DEMAND))))
    stack.enter_context(patch("app.services.relocation_service.get_safe_zone_sites",
                              new=AsyncMock(return_value=copy.deepcopy(_SITES))))
    stack.enter_context(patch("app.services.multi_engine_routing.pick_engine",
                              new=AsyncMock(return_value=engine)))
    stack.enter_context(patch("app.services.hazard_aware_routing.hazard_aware_route",
                              new=AsyncMock(return_value=route or _OK_ROUTE)))
    stack.enter_context(patch("app.services.hazard_service.current_hazards",
                              new=AsyncMock(return_value=_HAZARDS)))
    stack.enter_context(patch("app.services.relocation_service.get_plan",
                              new=AsyncMock(return_value=plan)))
    return stack


def _patch_dbdown():
    stack = ExitStack()
    stack.enter_context(patch("app.services.db_service.get_district_overview",
                              new=AsyncMock(return_value=dict(_DISTRICT_DEMO))))
    stack.enter_context(patch("app.services.db_service.get_habitation_detail",
                              new=AsyncMock(return_value=dict(_DETAIL_DEMO))))
    stack.enter_context(patch("app.services.risk_service.current_risk",
                              new=AsyncMock(return_value=_RISK_DEMO)))
    stack.enter_context(patch("app.services.risk_service.get_timeline",
                              new=AsyncMock(return_value=_TIMELINE_UNAVAIL)))
    stack.enter_context(patch("app.services.relocation_service.calculate_demand",
                              new=AsyncMock(return_value=_DEMAND_DEMO)))
    stack.enter_context(patch("app.services.relocation_service.get_safe_zone_sites",
                              new=AsyncMock(return_value=None)))
    stack.enter_context(patch("app.services.multi_engine_routing.pick_engine",
                              new=AsyncMock(return_value=None)))
    stack.enter_context(patch("app.services.hazard_service.current_hazards",
                              new=AsyncMock(return_value=_HAZARDS_EMPTY)))
    stack.enter_context(patch("app.services.relocation_service.get_plan",
                              new=AsyncMock(return_value=_PLAN_UNAVAIL)))
    return stack


_ALL_SECTIONS = ("district", "habitation", "demand", "capacity", "optimization",
                 "scenario", "routing", "hazard_context", "plan")


class ReportSummaryServiceTests(unittest.IsolatedAsyncioTestCase):

    async def test_live_report_sections_and_provenance(self):
        from app.api.v1 import reports
        with _patch_live():
            out = await reports.build_report_summary(None, habitation_id="munnar-central",
                                                     plan_id=7)
        self.assertEqual(set(out["sections"].keys()), set(_ALL_SECTIONS))
        for section in _ALL_SECTIONS:
            block = out["sections"][section]
            self.assertIn("data_status", block)
            self.assertIn("data_type", block)
            self.assertIn("provenance", block)
        self.assertEqual(out["sections"]["district"]["data_status"], "DERIVED")
        self.assertEqual(out["sections"]["district"]["source"], "postgis")
        # Detail (postgis) + live risk + live timeline aggregate to LIVE.
        self.assertEqual(out["sections"]["habitation"]["data_status"], "LIVE")
        self.assertEqual(out["sections"]["routing"]["served_by"], "osrm")
        self.assertFalse(out["sections"]["routing"]["fallback_used"])
        self.assertEqual(out["sections"]["routing"]["route"]["status"], "OK")
        self.assertEqual(out["sections"]["hazard_context"]["events_nearby_count"], 1)
        self.assertEqual(out["sections"]["hazard_context"]["events_nearby"][0]["event_id"], "e1")
        self.assertEqual(out["sections"]["capacity"]["site_capacity_total"], 500)
        self.assertIsNotNone(out["sections"]["plan"]["plan"]["id"])
        # Scenario section is always SIMULATED-labelled, never live.
        self.assertEqual(out["sections"]["scenario"]["data_type"], "SIMULATED")

    async def test_capacity_gap_is_shortage_not_surplus(self):
        # Demand 800 vs capacity 500 → gap must be 300 (max(0, demand-capacity)),
        # never the surplus formula or an allocated-based value.
        from app.api.v1 import reports
        with _patch_live():
            out = await reports.build_report_summary(None, habitation_id="munnar-central")
        cap = out["sections"]["capacity"]
        self.assertEqual(cap["site_capacity_total"], 500)
        self.assertEqual(cap["capacity_gap"], 300)
        opt = out["sections"]["optimization"]["optimization"]
        self.assertEqual(opt["total_demand"], 800)
        self.assertEqual(opt["total_allocated"], 500)
        self.assertEqual(opt["unallocated"], 300)

    async def test_optimization_uses_live_sites_not_demo_constants(self):
        # Live path: the solver must run over the live site-a (c_safe=500) with
        # live demand 800 — the DEMO constants (4210, site-b, site-c) must not
        # leak into a DERIVED-labelled response.
        from app.api.v1 import reports
        with _patch_live():
            out = await reports.build_report_summary(None, habitation_id="munnar-central")
        opt = out["sections"]["optimization"]["optimization"]
        self.assertEqual(out["sections"]["optimization"]["data_status"], "DERIVED")
        self.assertEqual(opt["total_demand"], 800)
        alloc_ids = [a["site_id"] for a in opt["allocations"]]
        self.assertEqual(alloc_ids, ["site-a"])
        self.assertNotIn("site-b", alloc_ids)
        self.assertNotIn("site-c", alloc_ids)

    async def test_routing_served_by_reflects_actual_engine(self):
        # pick_engine chose valhalla and the route payload says valhalla served
        # — served_by must report valhalla with fallback_used=True (never a
        # hardcoded primary engine).
        from app.api.v1 import reports
        with _patch_live(engine="valhalla", route=_OK_ROUTE_FALLBACK):
            out = await reports.build_report_summary(None, habitation_id="munnar-central")
        routing = out["sections"]["routing"]
        self.assertEqual(routing["served_by"], "valhalla")
        self.assertTrue(routing["fallback_used"])
        self.assertEqual(routing["route"]["status"], "OK")

    async def test_db_up_but_no_sites_is_empty_not_demo(self):
        # DB reachable, zero discovered sites → EMPTY capacity section with a
        # NOT_RUN optimizer — never demo candidates dressed as live.
        from app.api.v1 import reports
        with _patch_live() as stack:
            stack.enter_context(patch("app.services.relocation_service.get_safe_zone_sites",
                                     new=AsyncMock(return_value=[])))
            out = await reports.build_report_summary(None, habitation_id="munnar-central")
        cap = out["sections"]["capacity"]
        self.assertEqual(cap["data_status"], "EMPTY")
        self.assertEqual(cap["site_capacity_total"], 0)
        self.assertEqual(cap["capacity_gap"], 800)
        opt = out["sections"]["optimization"]["optimization"]
        self.assertEqual(opt["status"], "NOT_RUN")
        self.assertIsNone(out["sections"]["routing"]["site_id"])

    async def test_db_down_sections_are_honest(self):
        from app.api.v1 import reports
        with _patch_dbdown():
            out = await reports.build_report_summary(None, plan_id=7)
        self.assertEqual(out["data_status"], "DEMO")
        routing = out["sections"]["routing"]
        self.assertEqual(routing["route"]["status"], "UNAVAILABLE")
        self.assertEqual(routing["data_status"], "UNAVAILABLE")
        self.assertIsNone(routing["served_by"])
        self.assertFalse(routing["fallback_used"])
        # Coherent DEMO narrative: demo candidates (7100) with demo demand 4210.
        cap = out["sections"]["capacity"]
        self.assertEqual(cap["data_status"], "DEMO")
        self.assertEqual(cap["site_capacity_total"], 7100)
        self.assertEqual(cap["capacity_gap"], 0)
        opt = out["sections"]["optimization"]["optimization"]
        self.assertEqual(opt["total_demand"], 4210)
        self.assertEqual(opt["status"], "FEASIBLE")
        self.assertEqual(out["sections"]["hazard_context"]["data_status"], "EMPTY")
        self.assertEqual(out["sections"]["plan"]["data_status"], "UNAVAILABLE")
        for name in _ALL_SECTIONS:
            self.assertIn("provenance", out["sections"][name])


class ReportSummaryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = lambda: None
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_db, None)

    def test_summary_endpoint_live_200(self):
        with _patch_live():
            r = self.client.get("/api/v1/reports/summary", params={
                "habitation_id": "munnar-central", "plan_id": 7})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("sections", body)
        self.assertEqual(body["sections"]["routing"]["served_by"], "osrm")
        self.assertEqual(body["sections"]["capacity"]["capacity_gap"], 300)

    def test_summary_endpoint_db_down_200(self):
        with _patch_dbdown():
            r = self.client.get("/api/v1/reports/summary",
                                params={"habitation_id": "munnar-central"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "DEMO")
        self.assertEqual(body["sections"]["routing"]["data_status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()