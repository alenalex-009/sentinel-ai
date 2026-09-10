"""Weather polling → PostGIS (weather_observations, weather_forecasts).

Poller: for each configured station, fetch current + 3-day forecast, derive
rolling 24h/72h rainfall windows, and upsert. Concurrency-safe (UNIQUE
constraints + ON CONFLICT); idempotent per (station_id, observed_at).

Uses a sync engine (psycopg2) so it can run as a plain CLI/cron job without
an event loop, mirroring the earthquake ingester. The FastAPI layer reads
these tables through the async engine.
"""

import asyncio
import logging
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values

from app.core.config import settings
from app.services import weather_service

logger = logging.getLogger(__name__)

_OBSERVATION_COLS = (
    "station_id", "region", "observed_at", "temp_c", "humidity_pct",
    "wind_kph", "gust_kph", "precip_mm_1h", "totalprecip_mm_24h",
    "rainfall_mm_24h", "rainfall_mm_72h", "condition_text", "source",
    "data_type", "data_status",
)

_FORECAST_COLS = (
    "station_id", "region", "forecast_for", "rainfall_mm_expected",
    "max_temp_c", "min_temp_c", "avg_humidity_pct", "chance_of_rain_pct",
    "condition_text", "source", "data_type", "data_status",
)


def _connect():
    return psycopg2.connect(settings.DATABASE_URL, connect_timeout=5)


def _upsert_observations(conn, rows: list[tuple]) -> int:
    if not rows:
        return 0
    sql = (
        "INSERT INTO weather_observations (" + ", ".join(_OBSERVATION_COLS) + ") "
        "VALUES %s "
        "ON CONFLICT (station_id, observed_at) DO UPDATE SET "
        "temp_c = EXCLUDED.temp_c, humidity_pct = EXCLUDED.humidity_pct, "
        "wind_kph = EXCLUDED.wind_kph, gust_kph = EXCLUDED.gust_kph, "
        "precip_mm_1h = EXCLUDED.precip_mm_1h, "
        "rainfall_mm_24h = EXCLUDED.rainfall_mm_24h, "
        "rainfall_mm_72h = EXCLUDED.rainfall_mm_72h, "
        "condition_text = EXCLUDED.condition_text, fetched_at = NOW()"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=100)
    return len(rows)


def _upsert_forecasts(conn, rows: list[tuple]) -> int:
    if not rows:
        return 0
    sql = (
        "INSERT INTO weather_forecasts (" + ", ".join(_FORECAST_COLS) + ") "
        "VALUES %s "
        "ON CONFLICT (station_id, forecast_for) DO UPDATE SET "
        "rainfall_mm_expected = EXCLUDED.rainfall_mm_expected, "
        "max_temp_c = EXCLUDED.max_temp_c, min_temp_c = EXCLUDED.min_temp_c, "
        "avg_humidity_pct = EXCLUDED.avg_humidity_pct, "
        "chance_of_rain_pct = EXCLUDED.chance_of_rain_pct, "
        "condition_text = EXCLUDED.condition_text, issued_at = NOW()"
    )
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=100)
    return len(rows)


async def _fetch_station(station):
    """Fetch current + forecast concurrently for one station."""
    current, forecast = await asyncio.gather(
        weather_service.fetch_current(station),
        weather_service.fetch_forecast(station, days=3),
    )
    return current, forecast


def ingest_station(conn, station: weather_service.WeatherStation) -> dict:
    """Fetch one station and upsert current + forecast. Never fabricates.

    Returns a per-station summary; a failed live fetch yields an explicit
    error payload (the caller decides how to surface it).
    """
    summary = {
        "station_id": station.id,
        "region": station.region,
        "observations": 0,
        "forecasts": 0,
        "rainfall_mm_72h": None,
        "rainfall_mm_24h": None,
        "error": None,
    }

    ok, reason = weather_service._provider_available()
    if not ok:
        summary["error"] = f"provider unavailable: {reason}"
        return summary

    try:
        current, forecast = asyncio.run(_fetch_station(station))
    except weather_service.WeatherUnavailable as exc:
        summary["error"] = str(exc)
        return summary

    if forecast:
        rainfall = weather_service.derive_rolling_rainfall(forecast)
        summary["rainfall_mm_24h"] = rainfall["rainfall_mm_24h"]
        summary["rainfall_mm_72h"] = rainfall["rainfall_mm_72h"]
    else:
        rainfall = {"rainfall_mm_24h": None, "rainfall_mm_72h": None}

    obs_rows = []
    if current is not None:
        obs_rows.append((
            current.station_id, station.region, current.observed_at,
            current.temp_c, current.humidity_pct, current.wind_kph,
            current.gust_kph, current.precip_mm_1h, current.totalprecip_mm_24h,
            rainfall["rainfall_mm_24h"], rainfall["rainfall_mm_72h"],
            current.condition_text, current.source, "OBSERVED", "OBSERVED",
        ))

    fc_rows = [
        (
            d.station_id, station.region, d.forecast_for, d.totalprecip_mm,
            d.max_temp_c, d.min_temp_c, d.avg_humidity_pct,
            d.chance_of_rain_pct, d.condition_text, d.source,
            "OBSERVED", "OBSERVED",
        )
        for d in forecast
    ]

    summary["observations"] = _upsert_observations(conn, obs_rows)
    summary["forecasts"] = _upsert_forecasts(conn, fc_rows)
    return summary


def run_all() -> dict:
    """Poll all configured stations once. Returns aggregate summary."""
    if not settings.WEATHER_API_KEY:
        return {
            "status": "UNAVAILABLE",
            "reason": "WEATHER_API_KEY not configured (server-side env)",
            "stations": [],
        }
    conn = _connect()
    try:
        per_station = [ingest_station(conn, s) for s in weather_service.WEATHER_STATIONS]
        conn.commit()
    finally:
        conn.close()

    errors = [s for s in per_station if s.get("error")]
    return {
        "status": "PARTIAL" if (per_station and errors) else ("OK" if not errors else "UNAVAILABLE"),
        "reason": (
            "; ".join(f"{s['station_id']}: {s['error']}" for s in errors)
            if errors else None
        ),
        "stations": per_station,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import json
    import sys
    logging.basicConfig(level=logging.INFO)
    result = run_all()
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result["status"] != "UNAVAILABLE" else 1)