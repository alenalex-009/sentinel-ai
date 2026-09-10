"""Slice 2 — hazard-service tests (activation logic, severity, reach, API).

Pure-logic tests always run. The DB-backed `current_hazards` flow and the API
contract are exercised with data_read patched to a canned live source — the
service then talks to a stub session for persistence only, so no real DB is
needed and no fabricated events are introduced.

Run from backend/:
    python -m unittest tests.test_hazard_service -v
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi.testclient import TestClient

from app.services import hazard_service, data_read
from app.main import app

_NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def _weather_row(
    station_id="munnar",
    region="kerala",
    rain72=280.0,
    rain24=90.0,
    observed_at=None,
    lat=10.0889,
    lon=77.0595,
):
    return {
        "station_id": station_id,
        "region": region,
        "latitude": lat,
        "longitude": lon,
        "observed_at": observed_at or _NOW,
        "rainfall_mm_72h": rain72,
        "rainfall_mm_24h": rain24,
        "temp_c": 19.5,
        "data_type": "DERIVED",
        "data_status": "OBSERVED",
    }


def _quake_row(usgs_id="us5000xyz", mag=5.0, lat=10.2, lon=77.1, occurred_at=None, place="Munnar area"):
    return {
        "usgs_id": usgs_id,
        "occurred_at": occurred_at or _NOW,
        "magnitude": mag,
        "place": place,
        "latitude": lat,
        "longitude": lon,
        "depth_km": 20.0,
        "data_type": "OBSERVED",
        "data_status": "OBSERVED",
    }


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


class SeverityLadderTests(unittest.TestCase):
    def test_ladder_boundaries(self):
        self.assertEqual(hazard_service.severity_from_score(0)[0], "LOW")
        self.assertEqual(hazard_service.severity_from_score(24.9)[0], "LOW")
        self.assertEqual(hazard_service.severity_from_score(25)[0], "MODERATE")
        self.assertEqual(hazard_service.severity_from_score(49.9)[0], "MODERATE")
        self.assertEqual(hazard_service.severity_from_score(50)[0], "HIGH")
        self.assertEqual(hazard_service.severity_from_score(74.9)[0], "HIGH")
        self.assertEqual(hazard_service.severity_from_score(75)[0], "SEVERE")
        self.assertEqual(hazard_service.severity_from_score(150)[0], "SEVERE")

    def test_scores_clamped(self):
        self.assertAlmostEqual(hazard_service.severity_from_score(500)[0], "SEVERE")


class RainActivationTests(unittest.TestCase):
    def test_rain_below_trigger_no_event(self):
        row = _weather_row(rain72=149.0)
        self.assertIsNone(hazard_service._rain_event(row))

    def test_rain_at_trigger_event_moderate(self):
        row = _weather_row(rain72=150.0)
        ev = hazard_service._rain_event(row)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["severity_level"], "MODERATE")
        self.assertAlmostEqual(ev["severity_score"], 30.0, delta=0.1)
        self.assertEqual(ev["hazard_type"], "LANDSLIDE")  # kerala primary

    def test_rain_heavy_event_high(self):
        row = _weather_row(rain72=650.0)
        ev = hazard_service._rain_event(row)
        self.assertIsNotNone(ev)
        score = 30.0 + (650.0 - 150.0) * 0.10
        self.assertAlmostEqual(ev["severity_score"], min(100.0, score), delta=0.1)
        self.assertIn(ev["severity_level"], {"HIGH", "SEVERE"})


class QuakeActivationTests(unittest.TestCase):
    def test_quake_below_alert_mag_no_event(self):
        q = _quake_row(mag=4.9)
        self.assertIsNone(hazard_service._quake_event(q))

    def test_quake_at_alert_mag_event(self):
        q = _quake_row(mag=5.0)
        ev = hazard_service._quake_event(q)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["severity_level"], "MODERATE")
        self.assertNotIn("geom", ev)  # geometry is attached at finalization only

    def test_quake_large_event_severe(self):
        q = _quake_row(mag=6.75)
        ev = hazard_service._quake_event(q)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["hazard_type"], "EARTHQUAKE")
        self.assertIn(ev["severity_level"], {"SEVERE"})


class GeographicReachTests(unittest.TestCase):
    def test_exposure_intensity_linear_decay(self):
        self.assertAlmostEqual(hazard_service.exposure_intensity(0.0, 80.0, 20.0), 80.0)
        self.assertAlmostEqual(hazard_service.exposure_intensity(10.0, 80.0, 20.0), 40.0)
        self.assertAlmostEqual(hazard_service.exposure_intensity(20.0, 80.0, 20.0), 0.0)
        self.assertAlmostEqual(hazard_service.exposure_intensity(999.0, 80.0, 20.0), 0.0)

    def test_circle_polygon_radius_order(self):
        small = hazard_service._circle_polygon(10.0, 77.0, 10.0)
        big = hazard_service._circle_polygon(10.0, 77.0, 40.0)
        xs = [c[0] for c in small["coordinates"][0]]
        xb = [c[0] for c in big["coordinates"][0]]
        self.assertLess(max(xs) - min(xs), max(xb) - min(xb))

    def test_haversine_sanity(self):
        d = hazard_service._haversine_km(10.0889, 77.0595, 10.0889, 77.0595)
        self.assertAlmostEqual(d, 0.0, delta=0.01)
        d2 = hazard_service._haversine_km(10.0, 77.0, 10.0, 77.1)
        self.assertGreater(d2, 5.0)


class BuildEventsTests(unittest.TestCase):
    def test_build_current_events_filters(self):
        events = hazard_service.build_current_events(
            [_weather_row(rain72=60.0)], [_quake_row(mag=4.0)]
        )
        self.assertEqual(events, [])

    def test_build_current_events_sorts_by_severity(self):
        events = hazard_service.build_current_events(
            [_weather_row(rain72=500.0, station_id="munnar"), _weather_row(rain72=200.0, station_id="vizag")],
            [],
        )
        self.assertEqual(len(events), 2)
        self.assertGreater(events[0]["severity_score"], events[1]["severity_score"])
        for ev in events:
            self.assertEqual(ev["geom"]["type"], "Polygon")

    def test_build_events_geom_serializable(self):
        events = hazard_service.build_current_events(
            [_weather_row(rain72=300.0)], [_quake_row(mag=6.0)]
        )
        self.assertEqual(len(events), 2)
        gjson = events[0]["geom"]["coordinates"]
        self.assertGreater(len(gjson[0]), 3)


class CurrentHazardsFlowTests(unittest.IsolatedAsyncioTestCase):
    @mock.patch.object(data_read, "get_recent_weather")
    @mock.patch.object(data_read, "get_earthquakes")
    async def test_current_hazards_activation_end_to_end(self, gq, gw):
        async def fake_weather(session, region=None, hours=72):
            return {
                "data_status": "LIVE",
                "row_count": 1,
                "observations": [_weather_row(rain72=260.0)],
            }

        async def fake_quakes(session, region=None, since=None, magnitude_min=None, limit=200):
            return {
                "data_status": "LIVE",
                "row_count": 1,
                "earthquakes": [_quake_row(mag=5.4)],
            }

        gw.side_effect = fake_weather
        gq.side_effect = fake_quakes
        out = await hazard_service.current_hazards(FakeSession(), region="kerala", ttl=0)
        self.assertEqual(out["data_status"], "LIVE")
        ids = {e["event_id"].split("-")[0] for e in out["events"]}
        self.assertEqual(ids, {"rain", "quake"})
        self.assertEqual(out["feature_collection"]["type"], "FeatureCollection")
        self.assertEqual(len(out["feature_collection"]["features"]), 2)
        self.assertTrue(out["persisted"])

    @mock.patch.object(data_read, "get_recent_weather")
    @mock.patch.object(data_read, "get_earthquakes")
    async def test_current_hazards_below_threshold_empty(self, gq, gw):
        async def fake_weather(session, region=None, hours=72):
            return {
                "data_status": "LIVE",
                "row_count": 1,
                "observations": [_weather_row(rain72=20.0)],
            }

        async def fake_quakes(session, region=None, since=None, magnitude_min=None, limit=200):
            return {
                "data_status": "LIVE",
                "row_count": 1,
                "earthquakes": [_quake_row(mag=3.2)],
            }

        gw.side_effect = fake_weather
        gq.side_effect = fake_quakes
        out = await hazard_service.current_hazards(FakeSession(), region="kerala", ttl=0)
        self.assertEqual(out["data_status"], "LIVE")
        self.assertEqual(out["events"], [])

    async def test_current_hazards_unknown_region(self):
        out = await hazard_service.current_hazards(FakeSession(), region="nope", ttl=0)
        self.assertEqual(out["data_status"], "UNAVAILABLE")

    @mock.patch.object(data_read, "get_recent_weather")
    @mock.patch.object(data_read, "get_earthquakes")
    async def test_detail_affects_only_in_buffer(self, gq, gw):
        async def fake_weather(session, region=None, hours=72):
            return {
                "data_status": "LIVE",
                "row_count": 1,
                "observations": [_weather_row(rain72=260.0)],
            }

        async def fake_quakes(session, region=None, since=None, magnitude_min=None, limit=200):
            return {"data_status": "EMPTY", "earthquakes": []}

        gw.side_effect = fake_weather
        gq.side_effect = fake_quakes
        out = await hazard_service.current_hazards(FakeSession(), region="kerala", ttl=0)
        ev_id = out["events"][0]["event_id"]
        detail = await hazard_service.get_event_detail(FakeSession(), ev_id)
        self.assertEqual(detail["data_status"], "LIVE")
        self.assertEqual(detail["event"]["event_id"], ev_id)
        for h in detail["affected_habitations"]:
            self.assertLessEqual(h["distance_km"], out["events"][0]["buffer_radius_km"])
            self.assertLessEqual(h["exposure_intensity"], detail["event"]["severity_score"])


class HazardApiContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self._orig = hazard_service.current_hazards
        self.calls = []

    def tearDown(self):
        hazard_service.current_hazards = self._orig

    def test_current_endpoint_shape(self):
        async def fake_current(session, region=None, ttl=None):
            return {
                "data_status": "LIVE",
                "generated_at": "2026-09-10T12:00:00+00:00",
                "region": region or "all",
                "events": [
                    {
                        "event_id": "rain-munnar-20260910T1200Z",
                        "hazard_type": "LANDSLIDE",
                        "severity_level": "HIGH",
                        "severity_label": "Warning",
                        "severity_score": 57.0,
                        "active": True,
                        "started_at": "2026-09-10T12:00:00+00:00",
                        "source": "test",
                        "data_type": "DERIVED",
                        "centroid_lat": 10.09,
                        "centroid_lon": 77.06,
                        "buffer_radius_km": 32.8,
                        "event_meta": {"station_id": "munnar"},
                    }
                ],
                "feature_collection": {"type": "FeatureCollection", "features": []},
                "source_basis": {"weather": {"data_status": "LIVE"}, "earthquakes": {"data_status": "LIVE"}},
            }

        hazard_service.current_hazards = fake_current
        r = self.client.get("/api/v1/hazards/current?region=kerala")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "LIVE")
        self.assertEqual(body["region"], "kerala")
        ev = body["events"][0]
        for key in (
            "event_id", "hazard_type", "severity_level", "severity_score",
            "active", "started_at", "source", "data_type",
            "centroid_lat", "centroid_lon", "buffer_radius_km", "event_meta",
        ):
            self.assertIn(key, ev)

    def test_detail_endpoint_unknown_event(self):
        async def fake_current(session, region=None, ttl=None):
            return {
                "data_status": "LIVE",
                "region": "all",
                "events": [],
                "feature_collection": {"type": "FeatureCollection", "features": []},
                "source_basis": {},
            }

        hazard_service.current_hazards = fake_current
        r = self.client.get("/api/v1/hazards/detail/not-a-real-event")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["data_status"], "EMPTY")


if __name__ == "__main__":
    unittest.main()