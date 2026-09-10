"""Application configuration."""

from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://sentinel:sentinel_dev@localhost:5432/sentinel_ai"
    DEMO_MODE: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # External data sources
    BHUVAN_WMS_URL: str = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms"
    IMD_API_URL: str = "https://api.imd.gov.in"  # placeholder

    # Real-time weather (WeatherAPI.com — current + 3-day forecast + alerts).
    # The key is a SERVER-SIDE secret from backend/.env; it is never sent to
    # the frontend or committed. When unset, weather endpoints report
    # UNAVAILABLE-with-reason and the demo fallback stays labeled DEMO.
    WEATHER_API_KEY: Optional[str] = None
    WEATHER_API_BASE_URL: str = "https://api.weatherapi.com/v1"
    WEATHER_TIMEOUT_S: float = 10.0
    WEATHER_CACHE_TTL_S: int = 900

    # USGS historical earthquake catalog (CSV ingestion source). Absolute path
    # to the raw USGS India catalog; server-side only (often outside the repo).
    EARTHQUAKE_CSV_PATH: str = ""
    EARTHQUAKE_SOURCE_URL: str = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/csv.php"

    # Spatial analysis (Phase 3)
    SITE_PROXIMITY_RADIUS_M: float = 5000.0  # deterministic default radius

    # Road routing (Phase 4 — GraphHopper over OpenStreetMap)
    # GRAPHHOPPER_URL is the legacy single-instance default; region-aware
    # deployments override the per-region URLs below (docker-compose sets
    # GRAPHHOPPER_KERALA_URL=http://graphhopper-kerala:8989).
    GRAPHHOPPER_URL: str = "http://localhost:8989"
    GRAPHHOPPER_KERALA_URL: Optional[str] = None
    GRAPHHOPPER_VIZAG_URL: Optional[str] = None
    GRAPHHOPPER_ASSAM_URL: Optional[str] = None
    GRAPHHOPPER_PROFILE: str = "car"
    GRAPHHOPPER_TIMEOUT_S: float = 15.0
    ROUTE_CACHE_TTL_S: int = 300  # in-process route cache (simple, no distributed store)

    # ── Multi-engine routing (Phase 5C) ────────────────────────────────
    # All engines consume OpenStreetMap data. OSRM pre-bakes edge weights at
    # import time → sub-ms queries ("fast"); Valhalla costs edges at request
    # time → runtime-flexible + isochrones ("advanced"); GraphHopper sits
    # between and is the pre-existing integration. A failed/unconfigured
    # engine degrades to UNAVAILABLE with an explicit reason — the API never
    # relabels a fallback as the requested engine's result.
    OSRM_KERALA_URL: Optional[str] = None          # e.g. http://localhost:5000
    OSRM_VIZAG_URL: Optional[str] = None
    OSRM_ASSAM_URL: Optional[str] = None
    OSRM_PROFILE: str = "driving"                  # osrm-routed profile name
    OSRM_TIMEOUT_S: float = 8.0

    VALHALLA_KERALA_URL: Optional[str] = None      # e.g. http://localhost:8002
    VALHALLA_VIZAG_URL: Optional[str] = None
    VALHALLA_ASSAM_URL: Optional[str] = None
    VALHALLA_COSTING: str = "auto"                 # auto | bicycle | pedestrian | truck
    VALHALLA_TIMEOUT_S: float = 12.0

    # Risk model weights (configurable baseline — not official government formula)
    RISK_WEIGHT_HAZARD: float = 0.40
    RISK_WEIGHT_EXPOSURE: float = 0.20
    RISK_WEIGHT_VULNERABILITY: float = 0.25
    RISK_WEIGHT_INTERACTION: float = 0.15

    # Vulnerability sub-weights
    VULN_WEIGHT_DEMOGRAPHIC: float = 0.30
    VULN_WEIGHT_SOCIOECONOMIC: float = 0.20
    VULN_WEIGHT_INFRASTRUCTURE: float = 0.25
    VULN_WEIGHT_ACCESSIBILITY: float = 0.25

    # RPI weights
    RPI_WEIGHT_RISK: float = 0.35
    RPI_WEIGHT_VULNERABILITY: float = 0.20
    RPI_WEIGHT_EXPOSED_POP: float = 0.15
    RPI_WEIGHT_HISTORICAL: float = 0.15
    RPI_WEIGHT_URGENCY: float = 0.15

    # Hazard-event activation (Slice 2) — live weather/quake → active events.
    # A rain hazard activates only when a station's 72h rainfall (DERIVED from
    # live weather) meets RAINFALL_TRIGGER_MM; an earthquake hazard activates
    # only for recent (HAZARD_QUAKE_ACTIVE_DAYS) events with magnitude >=
    # EARTHQUAKE_ALERT_MAG_MIN. Severity ladder + buffer formulas live in
    # hazard_service.py (documented there).
    EARTHQUAKE_ALERT_MAG_MIN: float = 5.0     # quake magnitude activation floor
    HAZARD_QUAKE_ACTIVE_DAYS: int = 7          # quake stays "current" this long
    HAZARD_CACHE_TTL_S: int = 300              # in-process current-hazard cache

    # Event-escalation model (current/operational risk = base risk + escalation)
    # Trigger thresholds below which a source contributes zero escalation.
    RAINFALL_TRIGGER_MM: float = 150.0        # 72h cumulative rainfall threshold
    SATURATION_TRIGGER_PCT: float = 80.0       # soil saturation threshold (%)
    RIVER_LEVEL_TRIGGER_M: float = 1.5         # river level anomaly threshold (m)
    # Escalation coefficients (per unit of exceedance above trigger):
    #   escalation = rain_coeff x (mm - 150) + sat_coeff x (pct - 80)
    #              + river_coeff x (m - 1.5), floored at 0 and capped.
    ESCALATION_RAIN_COEFF: float = 0.05
    ESCALATION_SATURATION_COEFF: float = 0.40
    ESCALATION_RIVER_COEFF: float = 1.50
    ESCALATION_CAP: float = 15.0
    # NOTE: coefficients/thresholds are Sentinel AI configurable baselines for
    # the SIH demo — NOT official government formulas.

    # Dynamic current risk (Slice 3) — the escalation model above is fed by
    # LIVE weather_observations + active hazard_events; each live recompute is
    # persisted to risk_scores as a ledger row (baseline retained per row).
    RISK_CACHE_TTL_S: int = 300          # in-process dynamic-risk cache
    RISK_SCORE_STALE_HOURS: float = 6.0  # data_status STALE after this age
    # Extra escalation per unit of active-hazard exposure intensity (0-100)
    # measured at the habitation point. Capped together with the rain/sat/river
    # formula by ESCALATION_CAP. Documented baseline, not an official rule.
    ESCALATION_EVENT_COEFF: float = 0.50

    # Safe-zone engine (Slice 4) — deterministic candidate discovery + hard
    # constraint checks + suitability scoring over real spatial tables.
    SAFE_ZONE_CACHE_TTL_S: int = 300           # in-process safe-zone cache
    SAFE_ZONE_GRID_RADIUS_KM: float = 15.0     # discovery radius around district centroid
    SAFE_ZONE_GRID_SPACING_KM: float = 3.0     # discovery grid spacing
    SAFE_ZONE_FAULT_BUFFER_KM: float = 10.0    # exclusion buffer around fault/epicenter points
    SAFE_ZONE_HAZARD_BUFFER_KM: float = 0.0    # exclusion buffer around active hazard polygons
    SAFE_ZONE_MIN_SUITABILITY: float = 50.0    # suitability floor for a GREEN recommendation
    SAFE_ZONE_MIN_SAFETY: float = 40.0         # safety floor for a GREEN recommendation
    # Exclusion multipliers are documented Sentinel AI baselines — not official
    # government land-assessment rules.

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
