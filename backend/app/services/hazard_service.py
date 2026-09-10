"""Hazard / disaster intelligence — current active event model (Slice 2).

Activation rules (honest, config-driven — never fabricated):
  - RAIN hazard: station 72h rainfall (DERIVED from live OBSERVED weather)
    meets settings.RAINFALL_TRIGGER_MM (150) → LANDSLIDE/FLOOD event at the
    station with a circular buffer whose radius grows with severity.
  - EARTHQUAKE hazard: recent (HAZARD_QUAKE_ACTIVE_DAYS) catalog event with
    magnitude >= settings.EARTHQUAKE_ALERT_MAG_MIN (5.0) → event buffered by
    magnitude.
Severity ladder (score 0-100): LOW <25 · MODERATE 25-49 · HIGH 50-74 ·
SEVERE >=75. Buffers are ESTIMATED exposure reach (circular, km-scale), not
surveyed footprints.

formulas (documented baselines, not government thresholds):
  rain severity      = 30 + (rain72 - 150) * 0.10, capped at 100
  quake severity     = 30 + (mag - 5.0) * 40,     capped at 100
  buffer radius (km) = min(60, max(10, rain: 10 + sev*0.4 | quake: 15 + (mag-5)*20))
  exposure intensity = severity_score * (1 - min(1, dist_km / buffer_radius_km))
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.regions import REGIONS
from app.services import data_read

# ── Severity ladder ────────────────────────────────────────────────────────
SEVERITY_LOW = "LOW"
SEVERITY_MODERATE = "MODERATE"
SEVERITY_HIGH = "HIGH"
SEVERITY_SEVERE = "SEVERE"

SEVERITY_LABELS = {
    SEVERITY_LOW: "Watch",
    SEVERITY_MODERATE: "Advisory",
    SEVERITY_HIGH: "Warning",
    SEVERITY_SEVERE: "Extreme",
}

# score bases / coefficients (documented baselines)
RAIN_SEVERITY_BASE = 30.0          # score exactly at the rainfall trigger
RAIN_SEVERITY_PER_MM = 0.10
QUAKE_SEVERITY_BASE = 30.0         # score exactly at the magnitude alert floor
QUAKE_SEVERITY_PER_MAG_STEP = 40.0
BUFFER_MIN_KM = 10.0
BUFFER_MAX_KM = 60.0
BUFFER_KM_PER_SEVERITY = 0.4       # rain: 10 + sev*0.4 → 10..50 km
QUAKE_BUFFER_KM_PER_MAG = 20.0     # quake: 15 + (mag-5)*20 → 15..60 km
BUFFER_SEGMENTS = 48

# Predominant wet-season hazard per pilot region (used for rain events only).
REGION_PRIMARY_HAZARD = {
    "kerala": "LANDSLIDE",
    "vizag": "LANDSLIDE",
    "assam": "FLOOD",
}

# ── In-process freshness cache (keyed by region | "all") ────────────────────
_cache: dict = {}
LAST_CACHE_KEYS: list = []


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value) -> Optional[datetime]:
    """Accept aware datetime or ISO-8601 string → aware datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _severity_from_score(score: float) -> tuple[str, str]:
    score = min(100.0, max(0.0, score))
    if score >= 75:
        return SEVERITY_SEVERE, SEVERITY_LABELS[SEVERITY_SEVERE]
    if score >= 50:
        return SEVERITY_HIGH, SEVERITY_LABELS[SEVERITY_HIGH]
    if score >= 25:
        return SEVERITY_MODERATE, SEVERITY_LABELS[SEVERITY_MODERATE]
    return SEVERITY_LOW, SEVERITY_LABELS[SEVERITY_LOW]


def severity_from_score(score: float) -> tuple[str, str]:
    """Public ladder lookup: (level, label) for a 0-100 severity score."""
    return _severity_from_score(score)


def _circle_polygon(lat: float, lon: float, radius_km: float) -> dict:
    """GeoJSON Polygon approximating a WGS84 circle at radius_km.

    Meters-per-degree is equirectangular (lat 111320, lon 111320*cos(lat)).
    Documented basis: distance decay is km-scale exposure estimation, not a
    surveyed footprint.
    """
    m_lat = 111320.0
    m_lon = 111320.0 * math.cos(math.radians(lat))
    r_m = radius_km * 1000.0
    coords = []
    for i in range(BUFFER_SEGMENTS):
        bearing = 2.0 * math.pi * i / BUFFER_SEGMENTS
        d_lat = r_m * math.cos(bearing) / m_lat
        d_lon = r_m * math.sin(bearing) / m_lon
        coords.append([round(lon + d_lon, 6), round(lat + d_lat, 6)])
    coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _event_geom_ring(geom: dict) -> str:
    """WKT ring (no SRID prefix) for persisting a GeoJSON polygon ring."""
    ring = geom["coordinates"][0]
    return "(" + ", ".join(f"{lon} {lat}" for lon, lat in ring) + ")"


def _hazard_type_for_region(region: Optional[str]) -> str:
    return REGION_PRIMARY_HAZARD.get(region or "", "MULTI_HAZARD")


def _rain_event(station: dict) -> Optional[dict]:
    """Build a rain-activated hazard event from a weather observation, or None."""
    rain72 = station.get("rainfall_mm_72h")
    if rain72 is None or rain72 < settings.RAINFALL_TRIGGER_MM:
        return None
    trigger = settings.RAINFALL_TRIGGER_MM
    score = min(100.0, RAIN_SEVERITY_BASE + (rain72 - trigger) * RAIN_SEVERITY_PER_MM)
    level, label = _severity_from_score(score)
    radius = min(BUFFER_MAX_KM, max(BUFFER_MIN_KM, BUFFER_MIN_KM + score * BUFFER_KM_PER_SEVERITY))
    started = _as_datetime(station["observed_at"])
    if started is None:
        return None
    event_id = f"rain-{station['station_id']}-{started.strftime('%Y%m%dT%H%MZ')}"
    return {
        "event_id": event_id,
        "hazard_type": _hazard_type_for_region(station.get("region")),
        "severity_level": level,
        "severity_label": label,
        "severity_score": round(score, 1),
        "active": True,
        "started_at": started,
        "source": "WeatherAPI.com live rainfall (72h window, DERIVED from OBSERVED)",
        "data_type": "DERIVED",
        "centroid_lat": station["latitude"],
        "centroid_lon": station["longitude"],
        "buffer_radius_km": round(radius, 1),
        "event_meta": {
            "station_id": station["station_id"],
            "region": station.get("region"),
            "rainfall_mm_72h": rain72,
            "rainfall_mm_24h": station.get("rainfall_mm_24h"),
            "trigger_mm": trigger,
            "formula": "severity = 30 + (rain72 - 150) * 0.10, cap 100",
        },
    }


def _quake_event(q: dict) -> Optional[dict]:
    """Build a quake-activated hazard event from a catalog row, or None."""
    if q["magnitude"] is None or q["magnitude"] < settings.EARTHQUAKE_ALERT_MAG_MIN:
        return None
    alert_mag = settings.EARTHQUAKE_ALERT_MAG_MIN
    score = min(
        100.0,
        QUAKE_SEVERITY_BASE + (q["magnitude"] - alert_mag) * QUAKE_SEVERITY_PER_MAG_STEP,
    )
    level, label = _severity_from_score(score)
    radius = min(
        BUFFER_MAX_KM,
        max(BUFFER_MIN_KM, (15.0 + (q["magnitude"] - alert_mag) * QUAKE_BUFFER_KM_PER_MAG)),
    )
    started = _as_datetime(q["occurred_at"])
    if started is None:
        return None
    return {
        "event_id": f"quake-{q['usgs_id']}",
        "hazard_type": "EARTHQUAKE",
        "severity_level": level,
        "severity_label": label,
        "severity_score": round(score, 1),
        "active": True,
        "started_at": started,
        "source": "USGS earthquake catalog (India) — recent OBSERVED event",
        "data_type": "OBSERVED",
        "centroid_lat": q["latitude"],
        "centroid_lon": q["longitude"],
        "buffer_radius_km": round(radius, 1),
        "event_meta": {
            "usgs_id": q["usgs_id"],
            "place": q.get("place"),
            "magnitude": q["magnitude"],
            "depth_km": q.get("depth_km"),
            "alert_magnitude_min": alert_mag,
            "formula": "severity = 30 + (mag - 5.0) * 40, cap 100",
        },
    }


def _finalize_event(ev: dict) -> dict:
    """Add derived geom + serialization fields to a built event."""
    ev = dict(ev)
    geom = _circle_polygon(ev["centroid_lat"], ev["centroid_lon"], ev["buffer_radius_km"])
    ev["geom"] = geom
    return ev


def exposure_intensity(distance_km: float, severity_score: float, buffer_radius_km: float) -> float:
    """Linear distance-decay of event severity onto a point (0-100)."""
    if buffer_radius_km <= 0:
        return round(severity_score, 1)
    decay = 1.0 - min(1.0, max(0.0, distance_km / buffer_radius_km))
    return round(severity_score * decay, 1)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_current_events(weather_rows: list, quake_rows: list) -> list:
    """Pure: weather + quake rows → serialized active hazard events."""
    events = []
    for w in weather_rows:
        ev = _rain_event(w)
        if ev:
            events.append(_finalize_event(ev))
    for q in quake_rows:
        ev = _quake_event(q)
        if ev:
            events.append(_finalize_event(ev))
    events.sort(key=lambda e: e["severity_score"], reverse=True)
    return events


@dataclass
class HazardSourceBasis:
    weather: dict = field(default_factory=dict)
    earthquakes: dict = field(default_factory=dict)


async def _load_sources(
    session: AsyncSession, region: Optional[str]
) -> tuple[list, list, HazardSourceBasis]:
    """Read live weather + recent quakes for a region with honest source basis."""
    basis = HazardSourceBasis()
    weather_rows: list = []
    quake_rows: list = []

    w = await data_read.get_recent_weather(session, region=region, hours=72)
    basis.weather = {
        "data_status": w.get("data_status"),
        "reason": w.get("reason"),
        "observations": w.get("row_count", 0),
    }
    for obs in w.get("observations", []):
        # data_read omits lat/lon; join station registry coordinates for geometry.
        from app.services.weather_service import station_by_id

        station = station_by_id(obs["station_id"])
        if station is None:
            continue
        weather_rows.append(
            {**obs, "latitude": station.latitude, "longitude": station.longitude}
        )

    since_iso = (_now() - timedelta(days=settings.HAZARD_QUAKE_ACTIVE_DAYS)).isoformat()
    q = await data_read.get_earthquakes(
        session,
        region=region,
        since=since_iso,
        magnitude_min=settings.EARTHQUAKE_ALERT_MAG_MIN,
        limit=200,
    )
    basis.earthquakes = {
        "data_status": q.get("data_status"),
        "reason": q.get("reason"),
        "recorded": q.get("row_count", 0),
        "window_days": settings.HAZARD_QUAKE_ACTIVE_DAYS,
        "magnitude_min": settings.EARTHQUAKE_ALERT_MAG_MIN,
    }
    quake_rows = q.get("earthquakes", [])
    return weather_rows, quake_rows, basis


async def _persist_events(session: AsyncSession, events: list) -> bool:
    """Best-effort persistence of the current active set; deactivates stale."""
    if session is None:
        return False
    try:
        for ev in events:
            await session.execute(
                text(
                    """
                    INSERT INTO hazard_events (
                        event_id, hazard_type, severity_level, severity_score,
                        active, geom, centroid_lat, centroid_lon,
                        buffer_radius_km, started_at, last_confirmed_at,
                        source, data_type, event_meta
                    ) VALUES (
                        :event_id, :hazard_type, :severity_level, :severity_score,
                        TRUE, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326),
                        :centroid_lat, :centroid_lon, :buffer_radius_km,
                        :started_at, NOW(), :source, :data_type,
                        CAST(:event_meta AS jsonb)
                    )
                    ON CONFLICT (event_id) DO UPDATE SET
                        active = TRUE,
                        severity_level = EXCLUDED.severity_level,
                        severity_score = EXCLUDED.severity_score,
                        geom = EXCLUDED.geom,
                        buffer_radius_km = EXCLUDED.buffer_radius_km,
                        last_confirmed_at = NOW(),
                        event_meta = EXCLUDED.event_meta,
                        updated_at = NOW()
                    """
                ),
                {
                    "event_id": ev["event_id"],
                    "hazard_type": ev["hazard_type"],
                    "severity_level": ev["severity_level"],
                    "severity_score": ev["severity_score"],
                    "geom": json.dumps(ev["geom"]),
                    "centroid_lat": ev["centroid_lat"],
                    "centroid_lon": ev["centroid_lon"],
                    "buffer_radius_km": ev["buffer_radius_km"],
                    "started_at": ev["started_at"],
                    "source": ev["source"],
                    "data_type": ev["data_type"],
                    "event_meta": json.dumps(ev["event_meta"]),
                },
            )
        ids = [ev["event_id"] for ev in events]
        if ids:
            stmt = text(
                """
                UPDATE hazard_events SET active = FALSE, updated_at = NOW()
                WHERE active = TRUE AND event_id NOT IN :ids
                """
            ).bindparams(bindparam("ids", expanding=True))
            await session.execute(stmt, {"ids": ids})
        else:
            await session.execute(
                text(
                    """
                    UPDATE hazard_events SET active = FALSE, updated_at = NOW()
                    WHERE active = TRUE
                    """
                )
            )
        await session.commit()
        return True
    except Exception:
        await session.rollback()
        return False


def _active_feature_collection(events: list) -> dict:
    features = [
        {
            "type": "Feature",
            "properties": {
                "event_id": ev["event_id"],
                "hazard_type": ev["hazard_type"],
                "severity_level": ev["severity_level"],
                "severity_label": ev["severity_label"],
                "severity_score": ev["severity_score"],
                "started_at": ev["started_at"].isoformat(),
                "source": ev["source"],
                "data_type": ev["data_type"],
            },
            "geometry": ev["geom"],
        }
        for ev in events
        if ev["active"]
    ]
    return {"type": "FeatureCollection", "features": features}


def _serialize_event(ev: dict) -> dict:
    out = dict(ev)
    out["started_at"] = ev["started_at"].isoformat()
    out.pop("geom", None)  # geometry lives in the feature_collection
    return out


async def current_hazards(
    session: AsyncSession,
    region: Optional[str] = None,
    ttl: Optional[int] = None,
) -> dict:
    """The current operational hazard picture (cached for ttl seconds)."""
    ttl = settings.HAZARD_CACHE_TTL_S if ttl is None else ttl
    cache_key = region or "all"
    now_ts = time.time()
    cached = _cache.get(cache_key)
    if cached and (now_ts - cached["ts"]) < ttl:
        return cached["payload"]

    if region and region not in REGIONS:
        return {
            "data_status": "UNAVAILABLE",
            "reason": f"unknown region: {region}",
            "generated_at": _now().isoformat(),
            "events": [],
            "feature_collection": {"type": "FeatureCollection", "features": []},
        }

    weather_rows, quake_rows, basis = await _load_sources(session, region)
    events = [e for e in build_current_events(weather_rows, quake_rows) if e["active"]]
    persisted = await _persist_events(session, events)

    any_source = basis.weather.get("data_status") in ("LIVE", "STALE") or \
        basis.earthquakes.get("data_status") in ("LIVE", "STALE")
    status = "LIVE" if any_source else "EMPTY"
    summary = (
        f"{len(events)} active hazard event(s). "
        + ("Rainfall below trigger / no alert quakes (monitoring live sources)." if not events else
           "See events list for severity, source and evidence.")
    )

    payload = {
        "data_status": status,
        "generated_at": _now().isoformat(),
        "region": region or "all",
        "ttl_seconds": ttl,
        "persisted": persisted,
        "summary": summary,
        "source_basis": {
            "weather": basis.weather,
            "earthquakes": basis.earthquakes,
        },
        "events": [_serialize_event(e) for e in events],
        "feature_collection": _active_feature_collection(events),
    }
    _cache[cache_key] = {"ts": now_ts, "payload": payload}
    return payload


async def get_event_detail(session: AsyncSession, event_id: str) -> dict:
    """Detail for one event: geometry + exposure intensity on demo habitations."""
    payload = await current_hazards(session, region=None, ttl=settings.HAZARD_CACHE_TTL_S)
    event = next((e for e in payload["events"] if e["event_id"] == event_id), None)
    if event is None:
        return {
            "data_status": "EMPTY",
            "reason": f"no active hazard event with id: {event_id}",
            "event": None,
            "affected_habitations": [],
        }

    from app.services.demo_data import get_habitation_list

    affected, region = [], event.get("event_meta", {}).get("region")
    for hab in get_habitation_list("idukki").get("habitations", []):
        dist = _haversine_km(
            event["centroid_lat"], event["centroid_lon"], hab["latitude"], hab["longitude"]
        )
        if dist > event["buffer_radius_km"]:
            continue
        affected.append(
            {
                "habitation_id": hab["id"],
                "name": hab["name"],
                "region": region or "idukki",
                "latitude": hab["latitude"],
                "longitude": hab["longitude"],
                "exposure_intensity": exposure_intensity(
                    dist, event["severity_score"], event["buffer_radius_km"]
                ),
                "distance_km": round(dist, 1),
                "basis": {
                    "distance_decay": f"severity {event['severity_score']} x (1 - {round(dist,1)}/{event['buffer_radius_km']}km)",
                    "habitation_at_risk": True,
                },
            }
        )
    affected.sort(key=lambda a: a["exposure_intensity"], reverse=True)
    return {
        "data_status": "LIVE",
        "event": event,
        "affected_habitations": affected,
        "basis_note": (
            "Exposure intensity = severity_score x (1 - distance/buffer_radius). "
            "Circular estimated reach — not a surveyed footprint."
        ),
    }