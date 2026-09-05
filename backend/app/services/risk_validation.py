"""Risk model validation and audit for Sentinel AI.

Verifies that seed/demo values are internally consistent with the
configured model weights. Run this at startup in debug mode.

All weights are configurable baselines — NOT official government formulas.
"""

import logging
from app.core.config import settings
from app.services.risk_engine import (
    compute_vulnerability, compute_risk, compute_rpi,
    compute_current_risk,
    classify_priority, classify_vulnerability,
)

logger = logging.getLogger(__name__)


def validate_munnar_central() -> dict:
    """Validate Munnar Central demo values against the risk engine.

    Returns a dict with computed vs stored values and any discrepancies.
    """
    # Input values (from seed data / KSDMA + IMD sources)
    hazard_input = 88.0        # DERIVED from KSDMA susceptibility + IMD rainfall
    exposure_input = 84.0      # DERIVED: population density in hazard zone (normalised)
    demographic = 78.0
    socioeconomic = 71.0
    infrastructure = 76.0
    accessibility = 69.0

    # Compute vulnerability
    vuln = compute_vulnerability(demographic, socioeconomic, infrastructure, accessibility)
    # Expected: 0.30*78 + 0.20*71 + 0.25*76 + 0.25*69
    #         = 23.4 + 14.2 + 19.0 + 17.25 = 73.85 ≈ 74

    # Compute base (susceptibility) risk
    risk = compute_risk(hazard_input, exposure_input, vuln)
    # Risk = 0.40*88 + 0.20*84 + 0.25*73.85 + 0.15*(88/100*73.85/100*100)
    #      = 35.2 + 16.8 + 18.46 + 9.75
    #      = 80.21  (base susceptibility risk — NOT the current operational score)

    # Compute current (event-adjusted) operational risk.
    # Current risk = base risk + deterministic event escalation, where escalation
    # is driven ONLY by active-event triggers above their thresholds:
    #   0.05*(287-150) + 0.40*(94-80) + 1.50*(2.3-1.5) = 6.85 + 5.6 + 1.2 = 13.65
    #   80.21 + 13.65 = 93.86  ->  displayed/rounded as 94 (matches demo seed).
    # This preserves the base-vs-event distinction: a temporary rainfall spike
    # escalates CURRENT operational risk without changing permanent suitability.
    current = compute_current_risk(
        base_risk=risk,
        rainfall_mm=287.0,          # IMD: 287mm / 72hr (OBSERVED, DEMO)
        soil_saturation_pct=94.0,   # KSDMA sensors: 94% (OBSERVED, DEMO)
        river_level_anomaly_m=2.3,  # CWC: +2.3m above normal (OBSERVED, DEMO)
    )

    # Compute RPI from the CURRENT (event-adjusted) risk — relocation priority
    # responds to the present situation, matching the demo seed's RPI = 88
    # (documented as 0.35 x 94 + ...).
    pop_norm = 84.0   # 4210 persons normalised against district max ~5600
    historical = 94.0  # high historical impact (2018, 2019, 2021 events)
    urgency = 87.0     # current active rainfall event
    rpi = compute_rpi(float(current["current_risk_rounded"]), vuln, pop_norm, historical, urgency)

    priority = classify_priority(rpi)
    vuln_level = classify_vulnerability(vuln)

    # Component breakdown
    interaction = (hazard_input / 100) * (vuln / 100) * 100
    hazard_component = settings.RISK_WEIGHT_HAZARD * hazard_input
    exposure_component = settings.RISK_WEIGHT_EXPOSURE * exposure_input
    vuln_component = settings.RISK_WEIGHT_VULNERABILITY * vuln
    interaction_component = settings.RISK_WEIGHT_INTERACTION * interaction

    result = {
        "habitation": "Munnar Central",
        "inputs": {
            "hazard": hazard_input,
            "exposure": exposure_input,
            "demographic": demographic,
            "socioeconomic": socioeconomic,
            "infrastructure": infrastructure,
            "accessibility": accessibility,
        },
        "event_triggers": {
            "rainfall_mm_72h": 287.0,
            "soil_saturation_pct": 94.0,
            "river_level_anomaly_m": 2.3,
            "thresholds": {
                "rainfall_mm": settings.RAINFALL_TRIGGER_MM,
                "saturation_pct": settings.SATURATION_TRIGGER_PCT,
                "river_level_m": settings.RIVER_LEVEL_TRIGGER_M,
            },
        },
        "computed": {
            "vulnerability": round(vuln, 2),
            "vulnerability_level": vuln_level,
            "base_risk": round(risk, 2),
            "event_escalation": current["event_escalation"],
            "current_risk": current["current_risk"],
            "current_risk_rounded": current["current_risk_rounded"],
            "stored_demo_risk": 94,
            "current_risk_matches_seed": current["current_risk_rounded"] == 94,
            "rpi": round(rpi, 2),
            "priority": priority,
            "hazard_component": round(hazard_component, 2),
            "exposure_component": round(exposure_component, 2),
            "vulnerability_component": round(vuln_component, 2),
            "interaction_component": round(interaction_component, 2),
        },
        "weights_used": {
            "hazard": settings.RISK_WEIGHT_HAZARD,
            "exposure": settings.RISK_WEIGHT_EXPOSURE,
            "vulnerability": settings.RISK_WEIGHT_VULNERABILITY,
            "interaction": settings.RISK_WEIGHT_INTERACTION,
        },
        "escalation_weights_used": {
            "rain": settings.ESCALATION_RAIN_COEFF,
            "saturation": settings.ESCALATION_SATURATION_COEFF,
            "river": settings.ESCALATION_RIVER_COEFF,
            "cap": settings.ESCALATION_CAP,
        },
        "equation": current["equation"],
        "note": (
            "Current operational risk 94 = base (susceptibility) risk "
            + f"{current['base_risk']:.2f} + event escalation {current['event_escalation']:.2f} "
            + f"= {current['current_risk']:.2f}, rounded to {current['current_risk_rounded']}. "
            "The escalation term isolates temporary rainfall/saturation/river triggers "
            "(0.05 x rain excess mm + 0.40 x saturation excess pts + 1.50 x river excess m) "
            "and does NOT change baseline susceptibility or permanent suitability. "
            "All values DERIVED. Weights and escalation coefficients are configurable "
            "Sentinel AI baselines — not official government formulas."
        ),
    }

    logger.info(
        f"[Validation] Munnar Central: vuln={vuln:.2f}, base_risk={risk:.2f}, "
        f"escalation={current['event_escalation']}, current={current['current_risk']} "
        f"(rounded {current['current_risk_rounded']}), rpi={rpi:.2f}, priority={priority}"
    )
    return result


def validate_site_a_capacity() -> dict:
    """Validate Site A C_safe calculation."""
    dimensions = {
        "land": 3800,
        "water": 3200,   # bottleneck
        "healthcare": 4500,
        "education": 3600,
        "infrastructure": 3400,
        "environment": 5000,
    }
    c_safe = min(dimensions.values())
    bottleneck = min(dimensions, key=dimensions.get)
    demand = 4210
    surplus_deficit = c_safe - demand

    result = {
        "site": "Devikulam Plateau — Site A",
        "dimensions": dimensions,
        "c_safe": c_safe,
        "bottleneck": bottleneck,
        "demand": demand,
        "surplus_deficit": surplus_deficit,
        "can_absorb_alone": surplus_deficit >= 0,
        "note": "C_safe = min(all dimensions). All dimensions ESTIMATED from secondary sources.",
    }
    logger.info(f"[Validation] Site A: c_safe={c_safe}, bottleneck={bottleneck}, gap={surplus_deficit}")
    return result


def validate_suitability_site_a() -> dict:
    """Validate Site A suitability score.

    Suitability = 0.30*safety + 0.20*capacity_norm + 0.20*infrastructure
                + 0.15*accessibility + 0.10*water + 0.05*environment
    """
    safety = 88.0
    capacity_norm = 76.0   # c_safe/max_possible normalised
    infrastructure = 79.0
    accessibility = 85.0
    water = 76.0
    environment = 80.0     # estimated from ecology layer

    suitability = (
        0.30 * safety
        + 0.20 * capacity_norm
        + 0.20 * infrastructure
        + 0.15 * accessibility
        + 0.10 * water
        + 0.05 * environment
    )
    # = 26.4 + 15.2 + 15.8 + 12.75 + 7.6 + 4.0 = 81.75 ≈ 82

    result = {
        "site": "Devikulam Plateau — Site A",
        "inputs": {
            "safety": safety, "capacity_norm": capacity_norm,
            "infrastructure": infrastructure, "accessibility": accessibility,
            "water": water, "environment": environment,
        },
        "computed_suitability": round(suitability, 2),
        "seed_suitability": 82,
        "match": abs(suitability - 82) < 1.0,
        "weights": {"safety": 0.30, "capacity": 0.20, "infrastructure": 0.20,
                    "accessibility": 0.15, "water": 0.10, "environment": 0.05},
    }
    logger.info(f"[Validation] Site A suitability: computed={suitability:.2f}, seed=82")
    return result
