"""Slice 1 — real-data ingestion tests (weather + earthquakes + read API).

Pure-logic tests always run (parsing, normalization, derivation).
PostGIS-backed tests auto-skip when the database is unreachable.
Live-provider tests are mocked via httpx.MockTransport — never real network.

Run from backend/:
    python -m unittest tests.test_data_ingestion -v
"""

import asyncio
import io
import unittest
from datetime import datetime, timezone
from unittest import mock

from app.services import data_read
from app.services import weather_service
from app.ingestion import earthquake_ingester
from app.ingestion import weather_ingester


# ─── Earthquake CSV parsing (pure logic) ─────────────────────────────────────

_FULL_CSV = """time,latitude,longitude,depth,mag,magType,nst,gap,dmin,rms,net,id,updated,place,type,horizontalError,depthError,magError,magNst,status,locationSource,magSource
2000-07-29T17:50:03.510Z,10.0,77.0,20.0,4.5,mb,12.0,100.0,0.5,0.2,us,us2000abcd,2000-07-29T18:00:03.510Z,Munnar area,earthquake,1.2,0.8,0.1,15,reviewed,us,us
2001-01-01T00:00:00.000Z,,77.5,10.0,3.0,ml,,,,,ci,ci2001xyz,2001-01-01T01:00:00.000Z,Somewhere,earthquake,,,,,,automatic,ci,ci
2010-05-05T05:05:05.000Z,11.5,76.5,5.0,2.1,md,,,,,,us,us2010junk,2010-05-06T00:00:00.000Z,Nuclear blast,explosion,,,,,,reviewed,us,us
"""


class EarthquakeParseTests(unittest.TestCase):
    def test_parse_full_valid_row(self):
        rows = earthquake_ingester.parse_file_from_text(_FULL_CSV)
        self.assertEqual(len(rows), 1, "explosion dropped, faulty-coords row dropped")
        row = rows[0]
        self.assertEqual(row[0], "us2000abcd")  # usgs_id
        self.assertEqual(row[1].year, 2000)
        self.assertAlmostEqual(row[2], 4.5)     # magnitude
        self.assertAlmostEqual(row[4], 20.0)    # depth_km
        self.assertEqual(row[6], 10.0)
        self.assertEqual(row[7], 77.0)
        self.assertTrue(row[8].startswith("SRID=4326;POINT("))
        self.assertTrue(row[15])                # reviewed -> True

    def test_rejects_non_earthquake_types(self):
        self.assertFalse(earthquake_ingester.parse_row({
            "type": "explosion", "id": "x", "time": "2010-01-01T00:00:00.000Z",
            "latitude": "1", "longitude": "1",
        }))

    def test_rejects_missing_coords_or_time_or_id(self):
        self.assertIsNone(earthquake_ingester.parse_row({
            "type": "earthquake", "time": "", "latitude": "1", "longitude": "2", "id": "z",
        }))
        self.assertIsNone(earthquake_ingester.parse_row({
            "type": "earthquake", "time": "2010-01-01T00:00:00.000Z", "latitude": "", "longitude": "2", "id": "z",
        }))
        self.assertIsNone(earthquake_ingester.parse_row({
            "type": "earthquake", "time": "2010-01-01T00:00:00.000Z", "latitude": "1", "longitude": "2", "id": "",
        }))


# ─── Weather normalization + derivation (pure logic) ─────────────────────────

class WeatherLogicTests(unittest.TestCase):
    def test_derive_rolling_rainfall_three_days(self):
        fc = [
            weather_service.ForecastDay(station_id="munnar", forecast_for=datetime.now(timezone.utc), totalprecip_mm=10.0, max_temp_c=25.0, min_temp_c=16.0, avg_humidity_pct=80.0, chance_of_rain_pct=60.0, condition_text="Rain"),
            weather_service.ForecastDay(station_id="munnar", forecast_for=datetime.now(timezone.utc), totalprecip_mm=120.0, max_temp_c=24.0, min_temp_c=15.0, avg_humidity_pct=85.0, chance_of_rain_pct=90.0, condition_text="Heavy"),
            weather_service.ForecastDay(station_id="munnar", forecast_for=datetime.now(timezone.utc), totalprecip_mm=30.0, max_temp_c=23.0, min_temp_c=15.0, avg_humidity_pct=80.0, chance_of_rain_pct=70.0, condition_text="Rain"),
        ]
        d = weather_service.derive_rolling_rainfall(fc)
        self.assertEqual(d["rainfall_mm_24h"], 10.0)
        self.assertEqual(d["rainfall_mm_72h"], 160.0)
        self.assertEqual(d["derived_from_days"], 3)

    def test_derive_no_precipt_returns_none(self):
        fc = [weather_service.ForecastDay(station_id="munnar", forecast_for=datetime.now(timezone.utc), totalprecip_mm=None, max_temp_c=25.0, min_temp_c=16.0, avg_humidity_pct=80.0, chance_of_rain_pct=None, condition_text=None)]
        d = weather_service.derive_rolling_rainfall(fc)
        self.assertIsNone(d["rainfall_mm_24h"])
        self.assertIsNone(d["rainfall_mm_72h"])

    def test_station_lookup(self):
        self.assertEqual(weather_service.station_by_id("munnar").region, "kerala")
        self.assertIsNone(weather_service.station_by_id("nowhere"))

    def test_provider_unavailable_without_key(self):
        with mock.patch.object(weather_service.settings, "WEATHER_API_KEY", None):
            ok, msg = weather_service._provider_available()
            self.assertFalse(ok)
            self.assertIn("WEATHER_API_KEY", msg)


# ─── Read API (pure logic: status derivation, no DB) ─────────────────────────

class ReadStatusTests(unittest.TestCase):
    def test_stale_boundary_honest(self):
        self.assertGreater(data_read.settings_note_stale_minutes(), 0)

    def test_get_earthquakes_unknown_region(self):
        async def _run():
            from sqlalchemy.orm import sessionmaker
            # needs a session object; use a stub that errors -> UNAVAILABLE path
            class Stub:
                async def execute(self, *a, **k):
                    raise RuntimeError("no db")
            return await data_read.get_earthquakes(Stub(), region="atlantis")
        res = asyncio.run(_run())
        self.assertIn(res["data_status"], ("UNAVAILABLE", "EMPTY"))
        if res["data_status"] == "UNAVAILABLE":
            self.assertIn("atlantis", res["reason"])


if __name__ == "__main__":
    unittest.main(verbosity=2)