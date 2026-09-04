"""Application configuration."""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://sentinel:sentinel_dev@localhost:5432/sentinel_ai"
    DEMO_MODE: bool = True
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # External data sources
    BHUVAN_WMS_URL: str = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms"
    IMD_API_URL: str = "https://api.imd.gov.in"  # placeholder

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

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
