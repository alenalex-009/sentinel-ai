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


def compute_event_escalation(
    rainfall_mm: float,
    soil_saturation_pct: float,
    river_level_anomaly_m: float,
) -> float:
    """Compute the event-escalation term for current/operational risk.

    Base (susceptibility) risk reflects permanent hazard + exposure + vulnerability.
    A temporary rainfall/saturation/river event must NOT permanently reclassify a
    habitation, so its effect is isolated in a separate, deterministic escalation
    term that is added to base risk only for the CURRENT operational score:

      escalation = 0.05 x (rain_mm - 150)   [only above 150mm/72h]
                 + 0.40 x (sat_pct - 80)    [only above 80%]
                 + 1.50 x (river_m - 1.5)   [only above +1.5m]
      current operational risk = min(100, base risk + escalation)

    Coefficients and thresholds are Sentinel AI configurable baselines for the
    SIH demo — NOT official government formulas. Escalation is floored at zero
    (no event -> no change) and capped by settings.ESCALATION_CAP.
    """
    rain_excess = max(0.0, rainfall_mm - settings.RAINFALL_TRIGGER_MM)
    sat_excess = max(0.0, soil_saturation_pct - settings.SATURATION_TRIGGER_PCT)
    river_excess = max(0.0, river_level_anomaly_m - settings.RIVER_LEVEL_TRIGGER_M)

    escalation = (
        settings.ESCALATION_RAIN_COEFF * rain_excess
        + settings.ESCALATION_SATURATION_COEFF * sat_excess
        + settings.ESCALATION_RIVER_COEFF * river_excess
    )
    return min(max(0.0, escalation), settings.ESCALATION_CAP)


def compute_current_risk(
    base_risk: float,
    rainfall_mm: float,
    soil_saturation_pct: float,
    river_level_anomaly_m: float,
) -> dict:
    """Combine deterministic base risk with the event-escalation term.

    Returns the exact, unrounded current risk plus its two explainable parts.
    The rounded integer is what the UI displays (e.g. 93.86 -> 94).
    """
    escalation = compute_event_escalation(
        rainfall_mm, soil_saturation_pct, river_level_anomaly_m
    )
    current = min(100.0, base_risk + escalation)
    return {
        "base_risk": round(base_risk, 2),
        "event_escalation": round(escalation, 2),
        "current_risk": round(current, 2),
        "current_risk_rounded": int(round(current)),
        "equation": (
            f"base risk {base_risk:.2f} + event escalation {escalation:.2f} "
            f"= current operational risk {current:.2f} "
            f"(displayed as {int(round(current))})"
        ),
    }
