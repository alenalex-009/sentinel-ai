"""Live weather client + normalization (WeatherAPI.com).

Fetches current conditions and a 3-day forecast for a lat/lon, normalizing
provider fields into Sentinel AI's station-centric schema. The API key lives
only in backend/.env (settings.WEATHER_API_KEY) and is never exposed to the
frontend.

Integrity rules:
- A missing key or failed request returns an explicit UNAVAILABLE payload
  with reason — never fabricated readings.
- 72h rolling rainfall is DERIVED from the provider's 3-day forecast sums as
  a Sentinel AI baseline; the raw provider fields stay OBSERVED.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx

from app.core.config import settings


@dataclass
class WeatherStation:
    id: str
    region: str
    place: str
    latitude: float
    longitude: float


# Weather stations mirror the routing pilot regions. Coordinates are the
# pilot habitations / region centers — NOT claimed as official boM/IMD siting.
WEATHER_STATIONS: List[WeatherStation] = [
    WeatherStation(id="munnar", region="kerala", place="Munnar", latitude=10.0889, longitude=77.0595),
    WeatherStation(id="vizag", region="vizag", place="Visakhapatnam", latitude=17.72, longitude=83.30),
    WeatherStation(id="guwahati", region="assam", place="Guwahati", latitude=26.14, longitude=91.73),
]


def station_by_id(station_id: str) -> Optional[WeatherStation]:
    for s in WEATHER_STATIONS:
        if s.id == station_id:
            return s
    return None


@dataclass
class CurrentWeather:
    station_id: str
    observed_at: datetime
    temp_c: Optional[float]
    humidity_pct: Optional[float]
    wind_kph: Optional[float]
    gust_kph: Optional[float]
    precip_mm_1h: Optional[float]
    totalprecip_mm_24h: Optional[float]
    condition_text: Optional[str]
    source: str = "weatherapi"


@dataclass
class ForecastDay:
    station_id: str
    forecast_for: datetime
    totalprecip_mm: Optional[float]
    max_temp_c: Optional[float]
    min_temp_c: Optional[float]
    avg_humidity_pct: Optional[float]
    chance_of_rain_pct: Optional[float]
    condition_text: Optional[str]
    source: str = "weatherapi"


def _provider_available() -> tuple[bool, str]:
    if not settings.WEATHER_API_KEY:
        return False, "WEATHER_API_KEY not configured (server-side env)"
    if not settings.WEATHER_API_BASE_URL:
        return False, "WEATHER_API_BASE_URL not configured"
    return True, ""


async def _get(params: dict) -> Optional[dict]:
    """One typed GET against the weather provider; None on any failure."""
    ok, reason = _provider_available()
    if not ok:
        raise WeatherUnavailable(reason)
    try:
        async with httpx.AsyncClient(timeout=settings.WEATHER_TIMEOUT_S) as client:
            resp = await client.get(
                f"{settings.WEATHER_API_BASE_URL}/current.json",
                params={"key": settings.WEATHER_API_KEY, **params},
            )
            if resp.status_code != 200:
                raise WeatherUnavailable(f"provider HTTP {resp.status_code}")
            data = resp.json()
            if "error" in data:
                raise WeatherUnavailable(
                    f"provider error: {data['error'].get('message', 'unknown')}"
                )
            return data
    except WeatherUnavailable:
        raise
    except Exception as exc:
        raise WeatherUnavailable(f"weather fetch failed: {type(exc).__name__}: {exc}")


class WeatherUnavailable(Exception):
    """Raised when the live weather provider cannot serve a request.

    Carries an explicit, user-readable reason — the caller surfaces it as
    UNAVAILABLE instead of fabricating readings.
    """


def _parse_current(station: WeatherStation, data: dict) -> CurrentWeather:
    c = data.get("current", {})

    def _f(key: str) -> Optional[float]:
        v = c.get(key)
        return None if v is None else float(v)

    # Provider last_updated_epoch is UTC epoch seconds.
    epoch = c.get("last_updated_epoch")
    observed_at = (
        datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        if epoch
        else datetime.now(timezone.utc)
    )

    return CurrentWeather(
        station_id=station.id,
        observed_at=observed_at,
        temp_c=_f("temp_c"),
        humidity_pct=_f("humidity"),
        wind_kph=_f("wind_kph"),
        gust_kph=_f("gust_kph"),
        precip_mm_1h=_f("precip_mm"),
        # provider's rolling 24h gauge is not exposed separately; fall back to
        # forecast-day total (below) for the 24h/72h derived windows.
        totalprecip_mm_24h=None,
        condition_text=c.get("condition", {}).get("text"),
    )


async def fetch_current(station: WeatherStation) -> Optional[CurrentWeather]:
    data = await _get({"q": f"{station.latitude},{station.longitude}", "aqi": "no"})
    return _parse_current(station, data)


async def fetch_forecast(station: WeatherStation, days: int = 3) -> List[ForecastDay]:
    """Fetch 3-day daily forecast, normalized per day (00:00 IST period start)."""
    try:
        async with httpx.AsyncClient(timeout=settings.WEATHER_TIMEOUT_S) as client:
            resp = await client.get(
                f"{settings.WEATHER_API_BASE_URL}/forecast.json",
                params={
                    "key": settings.WEATHER_API_KEY,
                    "q": f"{station.latitude},{station.longitude}",
                    "days": days,
                    "aqi": "no",
                    "alerts": "no",
                },
            )
            if resp.status_code != 200:
                raise WeatherUnavailable(f"provider HTTP {resp.status_code}")
            data = resp.json()
    except WeatherUnavailable:
        raise
    except Exception as exc:
        raise WeatherUnavailable(f"forecast fetch failed: {type(exc).__name__}: {exc}")

    days_out = []
    for entry in data.get("forecast", {}).get("forecastday", []):
        day = entry.get("day", {})
        def _f(k: str) -> Optional[float]:
            v = day.get(k)
            return None if v is None else float(v)
        days_out.append(
            ForecastDay(
                station_id=station.id,
                forecast_for=datetime.strptime(entry["date"], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                ),
                totalprecip_mm=_f("totalprecip_mm"),
                max_temp_c=_f("maxtemp_c"),
                min_temp_c=_f("mintemp_c"),
                avg_humidity_pct=_f("avghumidity"),
                chance_of_rain_pct=_f("daily_chance_of_rain"),
                condition_text=day.get("condition", {}).get("text"),
            )
        )
    return days_out


def derive_rolling_rainfall(forecast: List[ForecastDay]) -> dict:
    """Derive Sentinel AI rolling rainfall windows from the 3-day forecast.

    rainfall_mm_24h = next 24h (day 0) forecast total; rainfall_mm_72h = sum
    of the 3-day totals. Both are DERIVED baselines for the risk engine's
    RAINFALL_TRIGGER_MM (150mm/72h), never labeled as observed station data.
    """
    totals = [d.totalprecip_mm for d in forecast if d.totalprecip_mm is not None]
    if not totals:
        return {"rainfall_mm_24h": None, "rainfall_mm_72h": None, "derived_from_days": 0}
    return {
        "rainfall_mm_24h": round(float(totals[0]), 2),
        "rainfall_mm_72h": round(sum(float(t) for t in totals), 2),
        "derived_from_days": len(totals),
    }