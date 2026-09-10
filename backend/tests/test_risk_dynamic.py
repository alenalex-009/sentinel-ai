"""Slice 3 — dynamic current risk tests (live feed → escalation → persistence).

Pure-logic tests always run. The DB-backed flows (live recompute + timeline)
are exercised with data_read.get_recent_weather and hazard_service.current_hazards
patched to canned live sources; the service then talks to a stub session for
persistence/reads only, so no real DB is needed and nothing is fabricated.

Run from backend/:
    python -m unittest tests.test_risk_dynamic -v
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi.testclient import TestClient

from app.services import risk_service, data_read, hazard_service
from app.core.config import settings
from app.main import app

_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def _weather_observation(
    station_id="munnar",
    rain72=26.0,
    rain24=10.0,
    observed_at=None,
):
    return {
        "station_id": station_id,
        "region": "kerala",
        "observed_at": (observed_at or _NOW).isoformat(),
        "temp_c": 19.5,
        "humidity_pct": 82.0,
        "wind_kph": 6.0,
        "precip_mm_1h": 0.5,
        "rainfall_mm_24h": rain24,
        "rainfall_mm_72h": rain72,
        "condition_text": "Partly cloudy",
        "data_type": "DERIVED",
        "data_status": "OBSERVED",
    }


def _quake_event(
    event_id="quake-test",
    severity=60.0,
    lat=10.0889,
    lon=77.0595,
    radius=20.0,
):
    return {
        "event_id": event_id,
        "hazard_type": "EARTHQUAKE",
        "severity_level": "HIGH",
        "severity_label": "Warning",
        "severity_score": severity,
        "active": True,
        "started_at": "2026-09-10T12:00:00+00:00",
        "source": "test",
        "data_type": "OBSERVED",
        "centroid_lat": lat,
        "centroid_lon": lon,
        "buffer_radius_km": radius,
        "event_meta": {"usgs_id": "test"},
    }


class FakeSession:
    """Stub AsyncSession-like object that records executed SQL / commits."""

    def __init__(self, timeline_rows=None):
        self.executed = []
        self.committed = 0
        self.rolled_back = 0
        self.timeline_rows = timeline_rows or []

    async def execute(self, sql, params=None):
        self.executed.append(str(sql))
        rows = self.timeline_rows

        class Mapping:
            def all(self):
                return rows

        class Result:
            def mappings(self):
                return Mapping()

        return Result()

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        self.rolled_back += 1


# ── Pure logic ──────────────────────────────────────────────────────────────

class BaselineTests(unittest.TestCase):
    def test_baseline_is_engine_component_sum(self):
        # Munnar Central canonical base susceptibility = 35.2+16.8+18.46+9.75
        self.assertAlmostEqual(risk_service.baseline_score("munnar-central"), 80.21, delta=0.01)

    def test_base_components_present_for_all_demo_habitations(self):
        for hid in ("munnar-central", "rajakkad", "kanthalloor", "marayoor", "adimali"):
            comps = risk_service.base_components(hid)
            self.assertAlmostEqual(sum(comps.values()), risk_service.baseline_score(hid), delta=0.01)


class ComputeDynamicScoreTests(unittest.TestCase):
    def test_rain_below_trigger_no_escalation(self):
        s = risk_service.compute_dynamic_score("munnar-central", rainfall_mm_72h=60.0)
        self.assertEqual(s["event_escalation"], 0.0)
        self.assertAlmostEqual(s["current_score"], s["baseline_score"], delta=0.01)

    def test_rain_above_trigger_formula_matches_manual_calc(self):
        # 0.05 x (250 - 150) = 5.0 (below cap)
        s = risk_service.compute_dynamic_score("munnar-central", rainfall_mm_72h=250.0)
        self.assertAlmostEqual(s["escalation_weather"], 5.0, delta=0.01)
        self.assertAlmostEqual(
            s["current_score"], s["baseline_score"] + 5.0, delta=0.01
        )

    def test_heavy_rain_capped_by_escalation_cap(self):
        # 0.05 x (650 - 150) = 25 -> capped at ESCALATION_CAP (15)
        s = risk_service.compute_dynamic_score("munnar-central", rainfall_mm_72h=650.0)
        self.assertAlmostEqual(s["event_escalation"], settings.ESCALATION_CAP, delta=0.01)

    def test_event_exposure_adds_to_escalation_until_cap(self):
        # 0.5 x 20 intensity = 10 (rain below trigger -> weather 0)
        s = risk_service.compute_dynamic_score("munnar-central", rainfall_mm_72h=10.0, hazard_intensity=20.0)
        self.assertAlmostEqual(s["escalation_hazard"], 10.0, delta=0.01)
        self.assertAlmostEqual(s["current_score"], s["baseline_score"] + 10.0, delta=0.01)

    def test_no_inputs_identity(self):
        s = risk_service.compute_dynamic_score("munnar-central")
        self.assertEqual(s["event_escalation"], 0.0)
        self.assertEqual(s["current_score_rounded"], int(round(s["baseline_score"])))


class StationAndExposureTests(unittest.TestCase):
    def test_nearest_station_for_kerala_point(self):
        st = risk_service.station_for(10.0889, 77.0595)
        self.assertEqual(st["id"], "munnar")
        self.assertEqual(st["region"], "kerala")

    def test_exposure_covering_event(self):
        out = risk_service._exposure_for_habitation(10.0889, 77.0595, [_quake_event()])
        self.assertEqual(out["covering_event_ids"], ["quake-test"])
        self.assertGreater(out["hazard_intensity"], 0)

    def test_exposure_far_event_zero(self):
        out = risk_service._exposure_for_habitation(
            10.0012, 76.9834, [_quake_event(lat=31.36, lon=80.33, radius=17.0)]
        )
        self.assertEqual(out["hazard_intensity"], 0.0)
        self.assertEqual(out["covering_event_ids"], [])
        self.assertLess(risk_service._haversine_km(10.0012, 76.9834, 31.36, 80.33), 2500.0)


# ── Async flows (patched live sources, stub session) ────────────────────────

class CurrentRiskFlowTests(unittest.IsolatedAsyncioTestCase):
    @mock.patch.object(data_read, "get_recent_weather")
    @mock.patch.object(hazard_service, "current_hazards")
    async def test_live_flow_rain_below_trigger(self, g_haz, g_weather):
        async def fake_weather(session, region=None, hours=72):
            return {
                "data_status": "LIVE",
                "row_count": 1,
                "observations": [_weather_observation(rain72=26.0)],
            }

        async def fake_hazards(session, region=None, ttl=None):
            return {"data_status": "LIVE", "events": []}

        g_weather.side_effect = fake_weather
        g_haz.side_effect = fake_hazards

        sess = FakeSession()
        out = await risk_service.current_risk(sess, district_id="idukki", ttl=0)
        self.assertEqual(out["data_status"], "LIVE")
        self.assertEqual(out["live_habitations"], 5)
        self.assertEqual(len(out["habitations"]), 5)
        for e in out["habitations"]:
            self.assertEqual(e["data_status"], "LIVE")
            self.assertEqual(e["event_escalation"], 0.0)
            self.assertEqual(e["live_inputs"]["station_id"], "munnar")
        self.assertEqual(out["basis"]["weather"]["data_status"], "LIVE")
        self.assertIn("soil_saturation", out["basis"])
        self.assertTrue(out["persisted"])
        self.assertTrue(sess.committed >= 1)
        inserts = [sql for sql in sess.executed if "INSERT INTO risk_scores" in sql]
        self.assertEqual(len(inserts), 5)

    @mock.patch.object(data_read, "get_recent_weather")
    @mock.patch.object(hazard_service, "current_hazards")
    async def test_live_flow_heavy_rain_escalates_all(self, g_haz, g_weather):
        async def fake_weather(session, region=None, hours=72):
            return {
                "data_status": "LIVE",
                "row_count": 1,
                "observations": [_weather_observation(rain72=650.0)],
            }

        async def fake_hazards(session, region=None, ttl=None):
            return {"data_status": "LIVE", "events": []}

        g_weather.side_effect = fake_weather
        g_haz.side_effect = fake_hazards

        out = await risk_service.current_risk(FakeSession(), district_id="idukki", ttl=0)
        for e in out["habitations"]:
            self.assertAlmostEqual(e["event_escalation"], settings.ESCALATION_CAP, delta=0.01)
            self.assertGreaterEqual(e["current_score"], e["baseline_score"])

    @mock.patch.object(data_read, "get_recent_weather")
    @mock.patch.object(hazard_service, "current_hazards")
    async def test_live_flow_covering_event_adds_hazard_escalation(self, g_haz, g_weather):
        async def fake_weather(session, region=None, hours=72):
            return {
                "data_status": "LIVE",
                "row_count": 1,
                "observations": [_weather_observation(rain72=26.0)],
            }

        # Quake centered exactly on Munnar Central (severity 60, radius 20km).
        async def fake_hazards(session, region=None, ttl=None):
            return {"data_status": "LIVE", "events": [_quake_event()]}

        g_weather.side_effect = fake_weather
        g_haz.side_effect = fake_hazards

        out = await risk_service.current_risk(FakeSession(), district_id="idukki", ttl=0)
        munnar = next(e for e in out["habitations"] if e["id"] == "munnar-central")
        self.assertGreater(munnar["escalation_hazard"], 0)
        self.assertEqual(munnar["live_inputs"]["covering_event_ids"], ["quake-test"])
        # 0.5 * ~60 = 30 capped at 15
        self.assertAlmostEqual(munnar["event_escalation"], settings.ESCALATION_CAP, delta=0.01)

    @mock.patch.object(data_read, "get_recent_weather")
    @mock.patch.object(hazard_service, "current_hazards")
    async def test_demo_fallback_when_no_weather(self, g_haz, g_weather):
        async def fake_weather(session, region=None, hours=72):
            return {"data_status": "UNAVAILABLE", "reason": "database connection failed", "observations": []}

        async def fake_hazards(session, region=None, ttl=None):
            return {"data_status": "EMPTY", "events": []}

        g_weather.side_effect = fake_weather
        g_haz.side_effect = fake_hazards
        sess = FakeSession()
        out = await risk_service.current_risk(sess, district_id="idukki", ttl=0)
        self.assertEqual(out["data_status"], "DEMO")
        self.assertEqual(len(out["habitations"]), 5)
        for e in out["habitations"]:
            self.assertEqual(e["data_status"], "DEMO")
            self.assertIsNotNone(e["event_escalation"])  # demo narrative change
        self.assertFalse(out.get("persisted", False))
        self.assertEqual(sess.committed, 0)
        self.assertEqual([s for s in sess.executed if "INSERT INTO risk_scores" in s], [])

    async def test_unknown_district(self):
        out = await risk_service.current_risk(FakeSession(), district_id="nope", ttl=0)
        self.assertEqual(out["data_status"], "UNAVAILABLE")


class TimelineTests(unittest.IsolatedAsyncioTestCase):
    def _rows(self):
        return [
            {
                "computed_at": _NOW - timedelta(hours=2),
                "current_score": 95.2,
                "baseline_score": 80.2,
                "event_escalation_component": 15.0,
            },
            {
                "computed_at": _NOW - timedelta(hours=1),
                "current_score": 80.2,
                "baseline_score": 80.2,
                "event_escalation_component": 0.0,
            },
        ]

    async def test_timeline_live(self):
        sess = FakeSession(timeline_rows=self._rows())
        out = await risk_service.get_timeline(sess, "munnar-central", limit=10)
        self.assertEqual(out["data_status"], "LIVE")
        self.assertEqual(len(out["points"]), 2)
        self.assertEqual(out["points"][0]["current_score"], 95.2)
        self.assertEqual(out["points"][1]["event_escalation"], 0.0)

    async def test_timeline_empty(self):
        out = await risk_service.get_timeline(FakeSession(), "munnar-central", limit=10)
        self.assertEqual(out["data_status"], "EMPTY")

    async def test_timeline_database_unavailable(self):
        class BrokenSession(FakeSession):
            async def execute(self, sql, params=None):
                raise RuntimeError("db down")

        out = await risk_service.get_timeline(BrokenSession(), "munnar-central", limit=10)
        self.assertEqual(out["data_status"], "UNAVAILABLE")


# ── API contract ─────────────────────────────────────────────────────────────

class RiskApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self._orig_current = risk_service.current_risk
        self._orig_timeline = risk_service.get_timeline

    def tearDown(self):
        risk_service.current_risk = self._orig_current
        risk_service.get_timeline = self._orig_timeline

    def test_current_endpoint_shape(self):
        async def fake_current(db, district_id="idukki"):
            return {
                "data_status": "LIVE",
                "district_id": district_id,
                "computed_at": "2026-09-10T12:00:00+00:00",
                "mode": "current",
                "basis": {"weather": {"data_status": "LIVE"}},
                "persisted": True,
                "habitations": [
                    {
                        "id": "munnar-central", "name": "Munnar Central",
                        "baseline_score": 80.21, "event_escalation": 0.0,
                        "current_score": 80.21, "current_score_rounded": 80,
                        "data_status": "LIVE", "data_type": "DERIVED",
                        "live_inputs": {"station_id": "munnar", "rainfall_mm_72h": 26.0},
                    }
                ],
            }

        risk_service.current_risk = fake_current
        r = self.client.get("/api/v1/risk/current?district_id=idukki")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "LIVE")
        h = body["habitations"][0]
        for key in (
            "id", "name", "baseline_score", "event_escalation",
            "current_score", "current_score_rounded", "data_status",
            "data_type", "live_inputs",
        ):
            self.assertIn(key, h)
        self.assertIn("basis", body)

    def test_timeline_endpoint_empty_for_unknown(self):
        async def fake_timeline(db, habitation_id, limit=30):
            return {"data_status": "EMPTY", "reason": "no recompute rows persisted yet", "points": []}

        risk_service.get_timeline = fake_timeline
        r = self.client.get("/api/v1/risk/current/timeline/nonexistent")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "EMPTY")
        self.assertEqual(body["points"], [])


if __name__ == "__main__":
    unittest.main()