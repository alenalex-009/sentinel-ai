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
        used_for="Rainfall intensity input to hazard model. Threshold: 150mm/72hr.",
        year_reference="Real-time (DEMO: 2024-08-15)",
        update_frequency="Hourly (live); DEMO uses static snapshot",
        availability=SourceAvailability.DEMO,
        limitations="Live IMD API not connected in demo. Static snapshot used.",
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
        name="Flood Hazard Layer",
        organization="ISRO / NRSC — Bhuvan",
        url="https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
        data_type="OBSERVED",
        used_for="Flood hazard component of risk model. Map overlay.",
        year_reference="2021",
        update_frequency="Periodic",
        availability=SourceAvailability.DEMO,
        limitations="Bhuvan WMS may be unreachable from demo environment.",
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
            "Risk = 0.40×Hazard + 0.20×Exposure + 0.25×Vulnerability + 0.15×Interaction."
        ),
        model_version="v0.1.0 — SIH demo build",
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


def get_all_source_statuses() -> list[dict]:
    """Return all data source statuses as dicts."""
    return [
        {
            "id": s.id,
            "name": s.name,
            "organization": s.organization,
            "url": s.url,
            "data_type": s.data_type,
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
    """Probe Bhuvan WMS endpoint. Returns availability status."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
                params={"SERVICE": "WMS", "REQUEST": "GetCapabilities"},
            )
            if resp.status_code == 200:
                return SourceAvailability.LIVE
    except Exception:
        pass
    return SourceAvailability.UNAVAILABLE
