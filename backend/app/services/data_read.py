"""Read access to ingested real data (weather + earthquakes).

Async (SQLAlchemy) — used by API routers. Pure DB reads; no fabrication.
When a table is empty or the DB is unavailable, callers receive an explicit
EMPTY/UNAVAILABLE payload with evidence, never guessed values.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.data_status import SourceAvailability


async def _rows(session: AsyncSession, sql: str, params: dict) -> Optional[list]:
    try:
        result = await session.execute(text(sql), params)
        return result.mappings().all()
    except Exception:
        return None


async def get_recent_weather(
    session: AsyncSession,
    region: Optional[str] = None,
    hours: int = 72,
) -> dict:
    """Most recent weather observations per station (optionally filtered).

    Returns a normalized list with honest freshness. Never synthesizes rows.
    """
    if hours < 1 or hours > 7 * 24:
        hours = 72
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    params = {"since": since}
    where = "observed_at >= :since"
    if region:
        where += " AND region = :region"
        params["region"] = region

    sql = f"""
        SELECT station_id, region, observed_at, temp_c, humidity_pct,
               wind_kph, gust_kph, precip_mm_1h, rainfall_mm_24h,
               rainfall_mm_72h, condition_text, data_type, data_status
        FROM weather_observations
        WHERE {where}
        ORDER BY observed_at DESC
    """
    rows = await _rows(session, sql, params)
    if rows is None:
        return {
            "data_status": "UNAVAILABLE",
            "reason": "database connection failed",
            "observations": [],
        }
    if not rows:
        return {
            "data_status": "EMPTY",
            "reason": f"no weather observations in the last {hours}h",
            "observations": [],
        }

    # Freshness signal: newest observed_at of the returned window.
    newest = max(r["observed_at"] for r in rows)
    age_min = (datetime.now(timezone.utc) - newest).total_seconds() / 60
    status = (
        SourceAvailability.STALE
        if age_min > settings_note_stale_minutes()
        else SourceAvailability.LIVE
    )

    return {
        "data_status": status.value,
        "row_count": len(rows),
        "max_age_minutes": round(age_min, 1),
        "observations": [
            {
                "station_id": r["station_id"],
                "region": r["region"],
                "observed_at": r["observed_at"].isoformat(),
                "temp_c": r["temp_c"],
                "humidity_pct": r["humidity_pct"],
                "wind_kph": r["wind_kph"],
                "precip_mm_1h": r["precip_mm_1h"],
                "rainfall_mm_24h": r["rainfall_mm_24h"],
                "rainfall_mm_72h": r["rainfall_mm_72h"],
                "condition_text": r["condition_text"],
                "data_type": r["data_type"],
                "data_status": r["data_status"],
            }
            for r in rows
        ],
    }


def settings_note_stale_minutes() -> float:
    # observations older than ~2x the poll interval are STALE
    return 2 * (settings.WEATHER_CACHE_TTL_S / 60)


async def get_forecast(
    session: AsyncSession,
    region: Optional[str] = None,
) -> dict:
    """Latest 3-day forecast per station."""
    params: dict = {}
    where = "forecast_for >= :since"
    params["since"] = datetime.now(timezone.utc)
    if region:
        where += " AND region = :region"
        params["region"] = region

    sql = f"""
        SELECT station_id, region, forecast_for, rainfall_mm_expected,
               max_temp_c, min_temp_c, avg_humidity_pct,
               chance_of_rain_pct, condition_text, issued_at
        FROM weather_forecasts
        WHERE {where}
        ORDER BY station_id, forecast_for
    """
    rows = await _rows(session, sql, params)
    if rows is None:
        return {"data_status": "UNAVAILABLE", "reason": "database connection failed", "forecast": []}
    if not rows:
        return {"data_status": "EMPTY", "reason": "no forecasts ingested", "forecast": []}

    return {
        "data_status": "LIVE",
        "row_count": len(rows),
        "forecast": [
            {
                "station_id": r["station_id"],
                "region": r["region"],
                "forecast_for": r["forecast_for"].isoformat(),
                "rainfall_mm_expected": r["rainfall_mm_expected"],
                "max_temp_c": r["max_temp_c"],
                "min_temp_c": r["min_temp_c"],
                "avg_humidity_pct": r["avg_humidity_pct"],
                "chance_of_rain_pct": r["chance_of_rain_pct"],
                "condition_text": r["condition_text"],
                "issued_at": r["issued_at"].isoformat() if r["issued_at"] else None,
            }
            for r in rows
        ],
    }


async def get_earthquakes(
    session: AsyncSession,
    region: Optional[str] = None,
    since: Optional[str] = None,
    magnitude_min: Optional[float] = None,
    limit: int = 200,
) -> dict:
    """Recent/historical earthquakes from the ingested USGS catalog.

    Coordinates are matched against the region reference bounds from
    regions.py (honest coverage gate, not a claim of exhaustiveness).
    """
    where, params = [], {}
    if since:
        try:
            params["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            return {
                "data_status": "UNAVAILABLE",
                "reason": f"invalid since timestamp: {since}",
                "earthquakes": [],
            }
        where.append("occurred_at >= :since")
    if magnitude_min is not None:
        where.append("magnitude >= :mag")
        params["mag"] = magnitude_min

    region_sql = ""
    if region:
        from app.core.regions import REGIONS
        r = REGIONS.get(region)
        if not r:
            return {
                "data_status": "UNAVAILABLE",
                "reason": f"unknown region: {region}",
                "earthquakes": [],
            }
        min_lat, max_lat, min_lon, max_lon = r.reference_bounds
        region_sql = (
            "latitude BETWEEN :min_lat AND :max_lat"
            " AND longitude BETWEEN :min_lon AND :max_lon"
        )
        params.update(
            {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon}
        )

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    if where_sql and region_sql:
        where_sql += " AND "
        where_sql += region_sql
    elif region_sql:
        where_sql = " WHERE " + region_sql

    sql = f"""
        SELECT usgs_id, occurred_at, magnitude, depth_km, place,
               latitude, longitude, mag_type, status, reviewed,
               data_type, data_status
        FROM earthquake_events
        {where_sql}
        ORDER BY occurred_at DESC
        LIMIT {int(limit)}
    """
    rows = await _rows(session, sql, params)
    if rows is None:
        return {"data_status": "UNAVAILABLE", "reason": "database connection failed", "earthquakes": []}
    if not rows:
        return {
            "data_status": "EMPTY",
            "reason": "no earthquakes match the given filters",
            "earthquakes": [],
        }

    return {
        "data_status": "LIVE",
        "row_count": len(rows),
        "earthquakes": [
            {
                "usgs_id": r["usgs_id"],
                "occurred_at": r["occurred_at"].isoformat(),
                "magnitude": r["magnitude"],
                "mag_type": r["mag_type"],
                "depth_km": r["depth_km"],
                "place": r["place"],
                "latitude": r["latitude"],
                "longitude": r["longitude"],
                "status": r["status"],
                "reviewed": r["reviewed"],
                "data_type": r["data_type"],
                "data_status": r["data_status"],
            }
            for r in rows
        ],
    }


async def get_earthquake_coverage(session: AsyncSession) -> dict:
    """Dataset coverage facts for the ingested USGS catalog."""
    rows = await _rows(
        session,
        """
        SELECT
            count(*) AS total,
            min(occurred_at) AS first_ts,
            max(occurred_at) AS last_ts,
            min(magnitude) AS mag_min,
            max(magnitude) AS mag_max,
            min(latitude) AS lat_min,
            max(latitude) AS lat_max,
            min(longitude) AS lon_min,
            max(longitude) AS lon_max,
            count(*) FILTER (WHERE reviewed) AS reviewed_count
        FROM earthquake_events
        """,
        {},
    )
    if rows is None:
        return {"data_status": "UNAVAILABLE", "reason": "database connection failed"}
    if not rows or rows[0]["total"] == 0:
        return {"data_status": "EMPTY", "reason": "earthquake_events table empty — run ingestion"}
    r = rows[0]
    return {
        "data_status": "LIVE",
        "total_records": r["total"],
        "time_range": [r["first_ts"].isoformat(), r["last_ts"].isoformat()],
        "magnitude_range": [r["mag_min"], r["mag_max"]],
        "latitude_range": [r["lat_min"], r["lat_max"]],
        "longitude_range": [r["lon_min"], r["lon_max"]],
        "reviewed_records": r["reviewed_count"],
        "source": "USGS earthquake catalog (India subset)",
    }