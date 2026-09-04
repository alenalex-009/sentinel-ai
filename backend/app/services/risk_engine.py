"""Deterministic risk computation engine.

Weights are configurable baselines — NOT official government formulas.
All outputs are DERIVED unless inputs are OBSERVED.
"""

from app.core.config import settings
from app.models.types import DataType, Priority, VulnerabilityLevel


def compute_vulnerability(
    demographic: float,
    socioeconomic: float,
    infrastructure: float,
    accessibility: float,
) -> float:
    """Compute composite vulnerability score (0-100)."""
    return (
        settings.VULN_WEIGHT_DEMOGRAPHIC * demographic
        + settings.VULN_WEIGHT_SOCIOECONOMIC * socioeconomic
        + settings.VULN_WEIGHT_INFRASTRUCTURE * infrastructure
        + settings.VULN_WEIGHT_ACCESSIBILITY * accessibility
    )


def compute_risk(
    hazard: float,
    exposure: float,
    vulnerability: float,
) -> float:
    """Compute composite risk score (0-100).

    Risk = 0.40 x Hazard + 0.20 x Exposure + 0.25 x Vulnerability
           + 0.15 x (Hazard x Vulnerability Interaction)
    """
    interaction = (hazard / 100) * (vulnerability / 100) * 100
    return (
        settings.RISK_WEIGHT_HAZARD * hazard
        + settings.RISK_WEIGHT_EXPOSURE * exposure
        + settings.RISK_WEIGHT_VULNERABILITY * vulnerability
        + settings.RISK_WEIGHT_INTERACTION * interaction
    )


def compute_rpi(
    risk: float,
    vulnerability: float,
    exposed_population_norm: float,  # 0-100 normalized
    historical_impact: float,
    urgency: float,
) -> float:
    """Compute Relocation Priority Index (0-100)."""
    return (
        settings.RPI_WEIGHT_RISK * risk
        + settings.RPI_WEIGHT_VULNERABILITY * vulnerability
        + settings.RPI_WEIGHT_EXPOSED_POP * exposed_population_norm
        + settings.RPI_WEIGHT_HISTORICAL * historical_impact
        + settings.RPI_WEIGHT_URGENCY * urgency
    )


def classify_priority(rpi: float) -> Priority:
    """Classify relocation priority from RPI score."""
    if rpi >= 75:
        return Priority.IMMEDIATE
    elif rpi >= 50:
        return Priority.SHORT_TERM
    elif rpi >= 30:
        return Priority.MEDIUM_TERM
    else:
        return Priority.MONITOR


def classify_vulnerability(score: float) -> VulnerabilityLevel:
    """Classify vulnerability level from score."""
    if score >= 80:
        return VulnerabilityLevel.VERY_HIGH
    elif score >= 60:
        return VulnerabilityLevel.HIGH
    elif score >= 40:
        return VulnerabilityLevel.MEDIUM
    elif score >= 20:
        return VulnerabilityLevel.LOW
    else:
        return VulnerabilityLevel.VERY_LOW


def compute_carrying_capacity(
    land_capacity: float,
    water_capacity: float,
    healthcare_capacity: float,
    education_capacity: float,
    infrastructure_capacity: float,
    environment_capacity: float,
) -> dict:
    """Compute safe carrying capacity as minimum of all dimensions.

    C_safe = min(land, water, healthcare, education, infrastructure, environment)
    Only include dimensions with reliable data.
    """
    dimensions = {
        "land": land_capacity,
        "water": water_capacity,
        "healthcare": healthcare_capacity,
        "education": education_capacity,
        "infrastructure": infrastructure_capacity,
        "environment": environment_capacity,
    }
    bottleneck = min(dimensions, key=dimensions.get)
    c_safe = dimensions[bottleneck]
    return {
        "c_safe": c_safe,
        "bottleneck": bottleneck,
        "dimensions": dimensions,
    }
