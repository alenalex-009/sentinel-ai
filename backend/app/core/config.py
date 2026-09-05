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

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
