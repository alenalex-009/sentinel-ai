"""Data source status tracking for Sentinel AI.

Tracks availability, freshness, provenance and limitations
for every external data source used by the platform.

Never makes live connections required for demo.
If unavailable: returns explicit UNAVAILABLE status.
"""

from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from app.core.config import settings


class SourceAvailability(str, Enum):
    LIVE = "LIVE"
    DEMO = "DEMO"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass
class DataSourceStatus:
    id: str
    name: str
    organization: str
    url: str
    data_type: str                    # OBSERVED | DERIVED | ESTIMATED
    used_for: str
    year_reference: str
    update_frequency: str
    availability: SourceAvailability
    last_checked: Optional[datetime] = None
    last_successful: Optional[datetime] = None
    age_hours: Optional[float] = None
    limitations: str = ""
    model_version: Optional[str] = None
    error_message: Optional[str] = None


# Static registry of all data sources used by Sentinel AI
# Availability is set to DEMO for all sources in demo mode.
# In production, a background task would ping each source and update availability.
DATA_SOURCE_REGISTRY: list[DataSourceStatus] = [
    DataSourceStatus(
        id="ksdma-landslide",
        name="Landslide Susceptibility Map",
        organization="KSDMA (Kerala State Disaster Management Authority)",
        url="https://sdma.kerala.gov.in",
        data_type="OBSERVED",
        used_for="Hazard intensity — landslide component of risk model",
        year_reference="2019",
        update_frequency="Periodic (post-event)",
        availability=SourceAvailability.DEMO,
        limitations="Static susceptibility map. Does not reflect real-time soil saturation. 2019 vintage.",
        model_version="KSDMA 2019 investigation dataset",
    ),
    DataSourceStatus(
        id="imd-rainfall",
        name="Rainfall Observations & Forecasts",
        organization="India Meteorological Department (IMD)",
        url="https://mausam.imd.gov.in",
        data_type="OBSERVED",
        used_for=(
            "Official IMD rainfall (reference). Rainfall INPUT to the hazard "
            "model currently comes live from the WeatherAPI.com provider "
            "(see weatherapi source) because IMD has no open real-time API in "
            "this build."
        ),
        year_reference="Real-time (DEMO: 2024-08-15)",
        update_frequency="Hourly (live via weatherapi placeholder)",
        availability=SourceAvailability.DEMO,
        limitations=(
            "Live IMD API not connected. Real-time rainfall is served by the "
            "weatherapi provider; IMD remains the reference source when an "
            "official feed is connected."
        ),
    ),
    DataSourceStatus(
        id="bhuvan-lulc",
        name="Land Use / Land Cover (LULC)",
        organization="ISRO / NRSC — Bhuvan",
        url="https://bhuvan.nrsc.gov.in",
        data_type="OBSERVED",
        used_for="Exposure mapping, candidate site land availability estimation",
        year_reference="2022-23",
        update_frequency="Annual",
        availability=SourceAvailability.DEMO,
        limitations="WMS layer may be unavailable in demo. Local GeoJSON fallback used.",
    ),
    DataSourceStatus(
        id="bhuvan-flood",
        name="Kerala Disaster Event Layers (Bhuvan WMS)",
        organization="ISRO / NRSC — Bhuvan (Bhuvan is the ISRO/NRSC geospatial platform)",
        url="https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
        data_type="OBSERVED",
        used_for=(
            "Visual map overlay of HISTORICAL Kerala disaster events served by ISRO/NRSC "
            "(e.g. disaster:Kerala_2019_Event, disaster:Landslides_2021_Oct_KL). "
            "Overlay-only — NOT used as a numeric input to the risk engine in this build."
        ),
        year_reference="2019 & 2021 historical events",
        update_frequency="Periodic (historical product)",
        availability=SourceAvailability.DEMO,  # runtime-probed on /data-sources and /data-sources/health
        limitations=(
            "Bhuvan WMS serves historical event layers only — no live hazard feed. "
            "Service response can be slow; browser tile loading may lag or fail when the "
            "network is unavailable. Reachability is probed at request time."
        ),
    ),
    DataSourceStatus(
        id="census-2011",
        name="Census of India 2011 — Village/Ward Data",
        organization="Office of the Registrar General & Census Commissioner",
        url="https://censusindia.gov.in",
        data_type="OBSERVED",
        used_for="Population, households, demographic vulnerability indicators",
        year_reference="2011 (projected to 2024)",
        update_frequency="Decennial. 2021 census pending.",
        availability=SourceAvailability.DEMO,
        limitations="Census 2011 is most recent available. Population figures are projected estimates.",
    ),
    DataSourceStatus(
        id="cwc-river",
        name="River Level & Flood Forecasting",
        organization="Central Water Commission (CWC)",
        url="https://cwc.gov.in",
        data_type="OBSERVED",
        used_for="Flood hazard input. River level anomaly detection.",
        year_reference="Real-time (DEMO: 2024-08-15)",
        update_frequency="Hourly (live); DEMO uses static snapshot",
        availability=SourceAvailability.DEMO,
        limitations="Live CWC API not connected in demo.",
    ),
    DataSourceStatus(
        id="data-gov-health",
        name="Health Facility Data",
        organization="data.gov.in / NHM Kerala",
        url="https://data.gov.in",
        data_type="ESTIMATED",
        used_for="Healthcare carrying capacity dimension for candidate sites",
        year_reference="2022",
        update_frequency="Annual",
        availability=SourceAvailability.DEMO,
        limitations="Catchment capacity estimated from facility type and bed count.",
    ),
    DataSourceStatus(
        id="udise-schools",
        name="UDISE+ School Infrastructure",
        organization="Ministry of Education — UDISE+",
        url="https://udiseplus.gov.in",
        data_type="ESTIMATED",
        used_for="Education carrying capacity dimension for candidate sites",
        year_reference="2022-23",
        update_frequency="Annual",
        availability=SourceAvailability.DEMO,
        limitations="Enrolment capacity estimated from school count and average capacity.",
    ),
    DataSourceStatus(
        id="sentinel-risk-engine",
        name="Sentinel AI Risk Engine",
        organization="Sentinel AI (SIH PS 26191)",
        url="#",
        data_type="DERIVED",
        used_for="Risk scores, RPI, vulnerability composite, carrying capacity C_safe",
        year_reference="v0.1.0",
        update_frequency="On data refresh",
        availability=SourceAvailability.DEMO,
        limitations=(
            "Weights are configurable project baselines — not official government formulas. "
            "Risk = 0.40×Hazard + 0.20×Exposure + 0.25×Vulnerability + 0.15×Interaction, "
            "plus a deterministic event-escalation term for current operational risk. "
            "All outputs are DERIVED and require human authority review."
        ),
        model_version="v0.1.0 — SIH demo build",
    ),
    DataSourceStatus(
        id="weatherapi",
        name="WeatherAPI.com — Current Conditions & 3-day Forecast",
        organization="WeatherAPI.com",
        url=settings.WEATHER_API_BASE_URL,
        data_type="OBSERVED",
        used_for=(
            "Live current weather + 72h rolling rainfall and 3-day rainfall "
            "forecast -> event-escalation inputs to dynamic risk (Slice 3)."
        ),
        year_reference="Real-time",
        update_frequency="Hourly (poller)",
        availability=(
            SourceAvailability.LIVE
            if settings.WEATHER_API_KEY
            else SourceAvailability.UNAVAILABLE
        ),
        limitations=(
            "Rainfall is point-station derived (lat/lon queries, e.g. Munnar). "
            "72h rolling rainfall is derived from the 3-day forecast as a "
            "Sentinel AI baseline — not IMD official station data. Stops being "
            "labeled OBSERVED-derived if the poller has not written in a while."
        ),
        model_version="WeatherAPI.com v1 (3-day forecast)",
    ),
    DataSourceStatus(
        id="usgs-earthquakes",
        name="USGS Earthquake Catalog (India, historical)",
        organization="US Geological Survey (USGS)",
        url=settings.EARTHQUAKE_SOURCE_URL,
        data_type="OBSERVED",
        used_for=(
            "Historical earthquake catalogue -> fault-zone proximity constraints "
            "for safe-zone siting (Slice 4) and earthquake hazard context "
            "(recent events) for dynamic risk (Slice 3)."
        ),
        year_reference="2000-01-01 → present",
        update_frequency="Bulked CSV ingestion; USGS feed is near-real-time",
        availability=(
            SourceAvailability.UNAVAILABLE
            if not settings.EARTHQUAKE_CSV_PATH
            else SourceAvailability.DEMO
        ),
        limitations=(
            "Historical context, NOT a prediction source. No deterministic "
            "earthquake forecasting is claimed. Records are point events "
            "(USGS best-hypocenter estimates)."
        ),
        model_version="USGS earthquake catalogue (CSV)",
    ),
    DataSourceStatus(
        id="graphhopper-routing",
        name="OpenStreetMap Road Network Routing (GraphHopper)",
        organization="OpenStreetMap (ODbL) / GraphHopper (self-hosted)",
        url=(
            settings.GRAPHHOPPER_KERALA_URL or settings.GRAPHHOPPER_URL
        ),
        data_type="DERIVED",
        used_for=(
            "Road-network distance and travel time between habitations and "
            "candidate sites for relocation planning (region-aware: kerala / "
            "vizag / assam)."
        ),
        year_reference=(
            "OSM via Overpass API, 2026-09-04. Loaded: Kerala (Idukki pilot "
            "region, covers all Kerala prototype habitations), Vizag "
            "(Visakhapatnam urban pilot), Assam (Guwahati urban pilot). "
            "Prototype-area coverage only — not full-state."
        ),
        update_frequency="On demand (cached 5 min)",
        availability=SourceAvailability.UNAVAILABLE,  # runtime-probed on /data-sources
        limitations=(
            "LIVE only when the region's GraphHopper service answered a route "
            "request for a loaded dataset. Road distance ≠ geodesic distance; "
            "travel time is an estimate, not official emergency travel time. "
            "Datasets are prototype-area extracts (Idukki / Vizag city / "
            "Guwahati), not full-state coverage — see osm/README.md."
        ),
        model_version="GraphHopper 8.0 (profile: car)",
    ),
    DataSourceStatus(
        id="ortools-optimizer",
        name="OR-Tools CP-SAT Optimizer",
        organization="Google OR-Tools (open source)",
        url="https://developers.google.com/optimization",
        data_type="DERIVED",
        used_for="Multi-site relocation allocation optimization",
        year_reference="v9.10",
        update_frequency="On demand",
        availability=SourceAvailability.DEMO,
        limitations=(
            "Optimization results are RECOMMENDATION only. "
            "Requires human authority review before any relocation action."
        ),
        model_version="OR-Tools 9.10 CP-SAT",
    ),
]


# Display-friendly data-type labels per source (single source of truth used by
# the Data & Sources UI; the frontend consumes this registry through the API).
DATA_TYPES_BY_SOURCE = {
    "ksdma-landslide": ["Raster", "Vector"],
    "imd-rainfall": ["Station data", "Gridded", "Forecast"],
    "bhuvan-lulc": ["Raster", "WMS"],
    "bhuvan-flood": ["Raster", "WMS"],
    "census-2011": ["Tabular", "Shapefile"],
    "cwc-river": ["Station data", "Forecast"],
    "data-gov-health": ["Tabular", "GeoJSON"],
    "udise-schools": ["Tabular"],
    "weatherapi": ["Station data", "Forecast"],
    "usgs-earthquakes": ["Tabular", "Point events"],
    "sentinel-risk-engine": ["Computed"],
    "ortools-optimizer": ["Computed"],
    "graphhopper-routing": ["Road network", "Route"],
}


def get_all_source_statuses() -> list[dict]:
    """Return all data source statuses as dicts."""
    return [
        {
            "id": s.id,
            "name": s.name,
            "organization": s.organization,
            "url": s.url,
            "data_type": s.data_type,
            "data_types": DATA_TYPES_BY_SOURCE.get(s.id, [s.data_type]),
            "used_for": s.used_for,
            "year_reference": s.year_reference,
            "update_frequency": s.update_frequency,
            "availability": s.availability,
            "last_checked": s.last_checked.isoformat() if s.last_checked else None,
            "last_successful": s.last_successful.isoformat() if s.last_successful else None,
            "age_hours": s.age_hours,
            "limitations": s.limitations,
            "model_version": s.model_version,
            "error_message": s.error_message,
        }
        for s in DATA_SOURCE_REGISTRY
    ]


async def check_bhuvan_wms() -> SourceAvailability:
    """Probe the Bhuvan WMS GetMap endpoint with a validated layer.

    Uses a tiny tile request for disaster:Kerala_2019_Event (verified to exist in
    the ISRO/NRSC capabilities). A real PNG response means the service is
    reachable and the overlay can render in the browser. GetCapabilities is not
    used here because that document can take minutes to stream.
    Returns LIVE when a usable image is returned, else UNAVAILABLE.
    """
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
                params={
                    "SERVICE": "WMS",
                    "VERSION": "1.1.1",
                    "REQUEST": "GetMap",
                    "LAYERS": "disaster:Kerala_2019_Event",
                    "STYLES": "",
                    "FORMAT": "image/png",
                    "TRANSPARENT": "true",
                    "SRS": "EPSG:3857",
                    "WIDTH": "64",
                    "HEIGHT": "64",
                    "BBOX": "8344425,1169340,8358725,1183640",
                },
            )
            if (
                resp.status_code == 200
                and resp.headers.get("content-type", "").startswith("image/")
            ):
                return SourceAvailability.LIVE
    except Exception:
        pass
    return SourceAvailability.UNAVAILABLE
