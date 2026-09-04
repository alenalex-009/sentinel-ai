"""Demo/seed data service for Sentinel AI.

All data here is DEMO MODE — clearly labelled, never presented as live.
Based on publicly available information about Idukki, Kerala.
Munnar Central figures are illustrative for SIH demonstration.
"""

from datetime import datetime, timezone
from typing import Optional
from app.models.types import (
    DataType, Priority, HazardType, VulnerabilityLevel, DataStatus
)

DEMO_TIMESTAMP = datetime(2024, 8, 15, 6, 0, 0, tzinfo=timezone.utc)


def get_district_overview(district_id: str) -> dict:
    if district_id != "idukki":
        return {"error": "District not found", "available": ["idukki"]}

    return {
        "data_status": DataStatus.DEMO,
        "district": {
            "id": "idukki",
            "name": "Idukki",
            "state": "Kerala",
            "total_habitations": 847,
            "critical_habitations": 23,
            "high_risk_habitations": 67,
            "total_population_at_risk": 142300,
            "immediate_relocation_needed": 8420,
            "data_status": DataStatus.DEMO,
            "last_updated": DEMO_TIMESTAMP.isoformat(),
        },
        "what_changed": [
            {
                "id": "wc1",
                "type": "risk_increase",
                "habitation": "Munnar Central",
                "description": "Risk score increased from 65 to 94 (+29) following 3-day cumulative rainfall of 287mm",
                "severity": "critical",
                "timestamp": DEMO_TIMESTAMP.isoformat(),
                "data_type": DataType.DERIVED,
            },
            {
                "id": "wc2",
                "type": "sensor_alert",
                "habitation": "Rajakkad",
                "description": "Soil moisture sensor threshold exceeded at 3 monitoring points",
                "severity": "high",
                "timestamp": DEMO_TIMESTAMP.isoformat(),
                "data_type": DataType.OBSERVED,
            },
            {
                "id": "wc3",
                "type": "road_disruption",
                "habitation": "Kanthalloor",
                "description": "SH-17 blocked at km 34.2 — access route to 3 habitations affected",
                "severity": "high",
                "timestamp": DEMO_TIMESTAMP.isoformat(),
                "data_type": DataType.OBSERVED,
            },
        ],
        "priority_actions": [
            {
                "id": "pa1",
                "priority": Priority.IMMEDIATE,
                "habitation": "Munnar Central",
                "action": "Initiate relocation assessment for Ward 04",
                "population": 4210,
                "data_type": DataType.RECOMMENDATION,
            },
            {
                "id": "pa2",
                "priority": Priority.IMMEDIATE,
                "habitation": "Rajakkad",
                "action": "Deploy field verification team",
                "population": 1840,
                "data_type": DataType.RECOMMENDATION,
            },
            {
                "id": "pa3",
                "priority": Priority.SHORT_TERM,
                "habitation": "Kanthalloor",
                "action": "Review access route alternatives",
                "population": 2100,
                "data_type": DataType.RECOMMENDATION,
            },
        ],
        "telemetry_anomalies": [
            {
                "id": "ta1",
                "type": "rainfall",
                "location": "Munnar IMD Station",
                "value": "287mm / 72hr",
                "threshold": "150mm / 72hr",
                "status": "exceeded",
                "data_type": DataType.OBSERVED,
            },
            {
                "id": "ta2",
                "type": "soil_moisture",
                "location": "Rajakkad Sensor Array",
                "value": "94%",
                "threshold": "80%",
                "status": "exceeded",
                "data_type": DataType.OBSERVED,
            },
            {
                "id": "ta3",
                "type": "river_level",
                "location": "Periyar at Cheruthoni",
                "value": "+2.3m above normal",
                "threshold": "+1.5m",
                "status": "warning",
                "data_type": DataType.OBSERVED,
            },
        ],
        "data_freshness": {
            "rainfall": {"source": "IMD", "age_hours": 3, "status": DataStatus.DEMO},
            "soil_moisture": {"source": "KSDMA Sensors", "age_hours": 1, "status": DataStatus.DEMO},
            "river_level": {"source": "CWC", "age_hours": 2, "status": DataStatus.DEMO},
            "risk_scores": {"source": "Sentinel AI Engine", "age_hours": 3, "status": DataStatus.DEMO},
            "population": {"source": "Census 2011 (projected)", "age_hours": None, "status": DataStatus.DEMO},
        },
    }


def get_habitation_list(district_id: str, search: Optional[str] = None) -> dict:
    habitations = [
        {
            "id": "munnar-central",
            "name": "Munnar Central",
            "ward": "Ward 04",
            "taluk": "Devikulam",
            "district": "Idukki",
            "population": 4210,
            "risk_score": 94,
            "risk_change": 29,
            "priority": Priority.IMMEDIATE,
            "primary_hazard": HazardType.LANDSLIDE,
            "latitude": 10.0889,
            "longitude": 77.0595,
            "data_status": DataStatus.DEMO,
        },
        {
            "id": "rajakkad",
            "name": "Rajakkad",
            "ward": "Ward 07",
            "taluk": "Devikulam",
            "district": "Idukki",
            "population": 1840,
            "risk_score": 81,
            "risk_change": 18,
            "priority": Priority.IMMEDIATE,
            "primary_hazard": HazardType.LANDSLIDE,
            "latitude": 10.0456,
            "longitude": 77.0234,
            "data_status": DataStatus.DEMO,
        },
        {
            "id": "kanthalloor",
            "name": "Kanthalloor",
            "ward": "Ward 12",
            "taluk": "Devikulam",
            "district": "Idukki",
            "population": 2100,
            "risk_score": 73,
            "risk_change": 11,
            "priority": Priority.SHORT_TERM,
            "primary_hazard": HazardType.FLOOD,
            "latitude": 10.1234,
            "longitude": 77.1023,
            "data_status": DataStatus.DEMO,
        },
        {
            "id": "marayoor",
            "name": "Marayoor",
            "ward": "Ward 03",
            "taluk": "Devikulam",
            "district": "Idukki",
            "population": 3200,
            "risk_score": 61,
            "risk_change": 5,
            "priority": Priority.SHORT_TERM,
            "primary_hazard": HazardType.FLOOD,
            "latitude": 10.2012,
            "longitude": 77.1567,
            "data_status": DataStatus.DEMO,
        },
        {
            "id": "adimali",
            "name": "Adimali",
            "ward": "Ward 01",
            "taluk": "Udumbanchola",
            "district": "Idukki",
            "population": 5600,
            "risk_score": 48,
            "risk_change": -3,
            "priority": Priority.MEDIUM_TERM,
            "primary_hazard": HazardType.FLOOD,
            "latitude": 10.0012,
            "longitude": 76.9834,
            "data_status": DataStatus.DEMO,
        },
    ]

    if search:
        habitations = [
            h for h in habitations
            if search.lower() in h["name"].lower()
        ]

    return {
        "data_status": DataStatus.DEMO,
        "district_id": district_id,
        "total": len(habitations),
        "habitations": habitations,
    }


def get_habitation_detail(habitation_id: str) -> dict:
    if habitation_id != "munnar-central":
        items = get_habitation_list("idukki")
        match = next(
            (h for h in items["habitations"] if h["id"] == habitation_id), None
        )
        if not match:
            return {"error": "Habitation not found"}
        return {"data_status": DataStatus.DEMO, **match}

    return {
        "data_status": DataStatus.DEMO,
        "id": "munnar-central",
        "name": "Munnar Central",
        "ward": "Ward 04",
        "taluk": "Devikulam",
        "district": "Idukki",
        "state": "Kerala",
        "population": 4210,
        "households": 1053,
        "area_ha": 12.4,
        "latitude": 10.0889,
        "longitude": 77.0595,
        "hazards": [
            {
                "type": HazardType.LANDSLIDE,
                "intensity": 88,
                "data_type": DataType.DERIVED,
                "source": "KSDMA Landslide Susceptibility Map + IMD Rainfall (DEMO)",
                "description": "High landslide susceptibility zone. 3-day cumulative rainfall 287mm exceeds 150mm threshold. Soil saturation at 94%.",
            },
            {
                "type": HazardType.FLOOD,
                "intensity": 62,
                "data_type": DataType.DERIVED,
                "source": "Bhuvan Flood Hazard Layer + CWC River Level (DEMO)",
                "description": "Moderate flood risk from Periyar tributary. River level +2.3m above normal.",
            },
            {
                "type": HazardType.CLOUDBURST,
                "intensity": 45,
                "data_type": DataType.ESTIMATED,
                "source": "IMD Forecast (DEMO)",
                "description": "IMD orange alert active. Cloudburst probability elevated for next 48 hours.",
            },
        ],
        "vulnerability": {
            "overall": 74,
            "level": VulnerabilityLevel.HIGH,
            "demographic": 78,
            "socioeconomic": 71,
            "infrastructure": 76,
            "accessibility": 69,
            "data_type": DataType.DERIVED,
        },
        "risk": {
            "current": 94,
            "baseline": 65,
            "change": 29,
            "hazard_component": 37.6,
            "exposure_component": 16.8,
            "vulnerability_component": 18.5,
            "interaction_component": 9.7,
            "data_type": DataType.DERIVED,
            "computed_at": DEMO_TIMESTAMP.isoformat(),
        },
        "relocation_priority": {
            "priority": Priority.IMMEDIATE,
            "rpi_score": 88,
            "risk_component": 32.9,
            "vulnerability_component": 14.8,
            "exposed_population_component": 13.2,
            "historical_impact_component": 14.1,
            "urgency_component": 13.0,
            "data_type": DataType.RECOMMENDATION,
        },
        "evidence_chain": [
            {"step": 1, "label": "HAZARD", "description": "Heavy rainfall + high soil saturation", "data_type": DataType.OBSERVED, "source": "IMD + KSDMA Sensors (DEMO)", "value": "287mm / 72hr | Soil 94%"},
            {"step": 2, "label": "EXPOSURE", "description": "Population within hazard zone", "data_type": DataType.DERIVED, "source": "Census 2011 projected + Bhuvan LULC (DEMO)", "value": "4,210 persons | 1,053 households"},
            {"step": 3, "label": "VULNERABILITY", "description": "Structural and access vulnerability", "data_type": DataType.DERIVED, "source": "Census + KSDMA + Field Data (DEMO)", "value": "74/100 — HIGH"},
            {"step": 4, "label": "RISK", "description": "Composite risk score", "data_type": DataType.DERIVED, "source": "Sentinel AI Risk Engine (DEMO)", "value": "94/100 (Baseline: 65, Change: +29)"},
            {"step": 5, "label": "PRIORITY", "description": "Immediate relocation assessment recommended", "data_type": DataType.RECOMMENDATION, "source": "Sentinel AI RPI Engine (DEMO)", "value": "IMMEDIATE — RPI 88/100"},
        ],
        "red_zone_status": "RED_ZONE_CANDIDATE",
        "permanent_settlement_suitable": False,
        "permanent_suitability_note": (
            "This area falls within a high landslide susceptibility zone per KSDMA mapping. "
            "Permanent settlement suitability assessment is separate from current operational risk. "
            "Official Red Zone designation requires government authority review."
        ),
        "system_recommendation": (
            "Prioritize Munnar Central for immediate relocation assessment and candidate-site screening."
        ),
        "historical_context": {
            "events": [
                {"year": 2018, "type": "Landslide", "impact": "Major displacement, GSI investigation triggered"},
                {"year": 2019, "type": "Flood", "impact": "Road access disrupted for 11 days"},
                {"year": 2021, "type": "Landslide", "impact": "Partial slope failure, 3 structures damaged"},
            ],
            "gsi_2018_note": "2018 GSI investigation: area included in 689 dwelling units recommended for relocation (KSDMA)",
            "data_type": DataType.OBSERVED,
        },
        "last_updated": DEMO_TIMESTAMP.isoformat(),
    }


def get_habitations_geojson(district_id: str) -> dict:
    habitations = get_habitation_list(district_id)["habitations"]
    features = []
    for h in habitations:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [h["longitude"], h["latitude"]]},
            "properties": {
                "id": h["id"],
                "name": h["name"],
                "ward": h["ward"],
                "taluk": h["taluk"],
                "population": h["population"],
                "risk_score": h["risk_score"],
                "risk_change": h["risk_change"],
                "priority": h["priority"],
                "primary_hazard": h["primary_hazard"],
                "data_status": h["data_status"],
            },
        })
    return {"type": "FeatureCollection", "data_status": DataStatus.DEMO, "features": features}


def get_risk_intelligence(district_id: str, mode: str) -> dict:
    return {
        "data_status": DataStatus.DEMO,
        "mode": mode,
        "district_id": district_id,
        "risk_distribution": {"critical": 23, "high": 67, "medium": 189, "low": 568},
        "top_drivers": [
            {"driver": "Landslide Susceptibility", "contribution": 38, "data_type": DataType.DERIVED},
            {"driver": "Rainfall Intensity", "contribution": 29, "data_type": DataType.OBSERVED},
            {"driver": "Soil Saturation", "contribution": 18, "data_type": DataType.OBSERVED},
            {"driver": "Structural Vulnerability", "contribution": 15, "data_type": DataType.DERIVED},
        ],
        "significant_shifts": [
            {"habitation": "Munnar Central", "change": 29, "direction": "increase"},
            {"habitation": "Rajakkad", "change": 18, "direction": "increase"},
            {"habitation": "Kanthalloor", "change": 11, "direction": "increase"},
        ],
        "human_impact": {"total_at_risk": 142300, "immediate_action": 8420, "data_type": DataType.DERIVED},
    }


def get_risk_drivers(habitation_id: str) -> dict:
    return {
        "data_status": DataStatus.DEMO,
        "habitation_id": habitation_id,
        "drivers": [
            {"rank": 1, "name": "Landslide Susceptibility", "score": 88, "weight": 0.40, "contribution": 35.2, "data_type": DataType.DERIVED},
            {"rank": 2, "name": "Soil Saturation", "score": 94, "weight": 0.25, "contribution": 23.5, "data_type": DataType.OBSERVED},
            {"rank": 3, "name": "Structural Vulnerability", "score": 76, "weight": 0.25, "contribution": 19.0, "data_type": DataType.DERIVED},
            {"rank": 4, "name": "Access Route Risk", "score": 69, "weight": 0.15, "contribution": 10.4, "data_type": DataType.DERIVED},
        ],
    }


def get_decision_trace(habitation_id: str) -> dict:
    return {
        "data_status": DataStatus.DEMO,
        "habitation_id": habitation_id,
        "trace": [
            {"step": 1, "node": "OBSERVED HAZARDS", "value": "Landslide 88 | Flood 62 | Cloudburst 45", "data_type": DataType.OBSERVED},
            {"step": 2, "node": "EXPOSURE", "value": "4,210 persons in hazard zone", "data_type": DataType.DERIVED},
            {"step": 3, "node": "VULNERABILITY", "value": "74/100 — HIGH", "data_type": DataType.DERIVED},
            {"step": 4, "node": "OPERATIONAL RISK", "value": "94/100 (Baseline 65, +29)", "data_type": DataType.DERIVED},
            {"step": 5, "node": "RELOCATION PRIORITY", "value": "IMMEDIATE — RPI 88/100", "data_type": DataType.RECOMMENDATION},
            {"step": 6, "node": "SITE / CAPACITY CHECK", "value": "3 candidate sites screened | C_safe max 3,200", "data_type": DataType.DERIVED},
            {"step": 7, "node": "SYSTEM RECOMMENDATION", "value": "Initiate relocation assessment for Ward 04", "data_type": DataType.RECOMMENDATION},
        ],
    }


def get_relocation_demand(habitation_id: str) -> dict:
    return {
        "data_status": DataStatus.DEMO,
        "habitation_id": habitation_id,
        "total_population": 4210,
        "households": 1053,
        "relocation_demand": 4210,
        "demand_basis": (
            "Full habitation population used as relocation demand. "
            "Area classified as Red Zone Candidate based on KSDMA landslide susceptibility + 2018 GSI investigation. "
            "Field survey required to refine demand. (DERIVED)"
        ),
        "data_type": DataType.DERIVED,
    }


def get_candidate_sites(habitation_id: str) -> dict:
    return {
        "data_status": DataStatus.DEMO,
        "habitation_id": habitation_id,
        "note": "Technically Screened Candidates only. Official approval required before relocation.",
        "sites": [
            {
                "id": "site-a",
                "name": "Devikulam Plateau — Site A",
                "distance_km": 4.2,
                "suitability_score": 82,
                "safe_capacity": 3200,
                "bottleneck_dimension": "water",
                "safety_score": 88,
                "infrastructure_score": 79,
                "accessibility_score": 85,
                "water_score": 76,
                "healthcare_score": 71,
                "education_score": 68,
                "latitude": 10.1123,
                "longitude": 77.0812,
                "hard_constraints_passed": True,
                "data_type": DataType.DERIVED,
                "data_status": DataStatus.DEMO,
                "notes": "Plateau area with lower landslide susceptibility. Water supply limited by existing infrastructure.",
            },
            {
                "id": "site-b",
                "name": "Pallivasal Flatland — Site B",
                "distance_km": 7.8,
                "suitability_score": 74,
                "safe_capacity": 2100,
                "bottleneck_dimension": "water",
                "safety_score": 91,
                "infrastructure_score": 65,
                "accessibility_score": 72,
                "water_score": 83,
                "healthcare_score": 58,
                "education_score": 61,
                "latitude": 10.0634,
                "longitude": 77.1234,
                "hard_constraints_passed": True,
                "data_type": DataType.DERIVED,
                "data_status": DataStatus.DEMO,
                "notes": "High safety score. Infrastructure deficit requires investment. Healthcare access is the primary constraint.",
            },
            {
                "id": "site-c",
                "name": "Munnar Town Periphery — Site C",
                "distance_km": 2.1,
                "suitability_score": 68,
                "safe_capacity": 1800,
                "bottleneck_dimension": "land",
                "safety_score": 79,
                "infrastructure_score": 88,
                "accessibility_score": 92,
                "water_score": 71,
                "healthcare_score": 89,
                "education_score": 85,
                "latitude": 10.0756,
                "longitude": 77.0623,
                "hard_constraints_passed": True,
                "data_type": DataType.DERIVED,
                "data_status": DataStatus.DEMO,
                "notes": "Closest site with best infrastructure and healthcare. Land availability is the binding constraint.",
            },
        ],
    }


def get_capacity_assessment(site_id: str) -> dict:
    data = {
        "site-a": {
            "site_name": "Devikulam Plateau — Site A",
            "c_safe": 3200, "bottleneck": "water",
            "dimensions": [
                {"name": "land", "capacity": 3800, "source": "Bhuvan LULC (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Available land area estimated from LULC"},
                {"name": "water", "capacity": 3200, "source": "PWD Kerala (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Binding constraint"},
                {"name": "healthcare", "capacity": 4500, "source": "data.gov.in (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Devikulam PHC + CHC"},
                {"name": "education", "capacity": 3600, "source": "UDISE+ (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Schools within 3km"},
                {"name": "infrastructure", "capacity": 3400, "source": "Sentinel AI ESTIMATED", "data_type": DataType.ESTIMATED, "notes": "Road, power, sanitation"},
                {"name": "environment", "capacity": 5000, "source": "Bhuvan (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Least constraining"},
            ],
            "required_population": 4210, "surplus_deficit": -1010, "can_absorb_alone": False,
        },
        "site-b": {
            "site_name": "Pallivasal Flatland — Site B",
            "c_safe": 2100, "bottleneck": "water",
            "dimensions": [
                {"name": "land", "capacity": 2800, "source": "Bhuvan LULC (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Available flatland"},
                {"name": "water", "capacity": 2100, "source": "PWD Kerala (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Binding constraint"},
                {"name": "healthcare", "capacity": 2600, "source": "data.gov.in (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Nearest PHC at 12km"},
                {"name": "education", "capacity": 2400, "source": "UDISE+ (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Schools within 5km"},
                {"name": "infrastructure", "capacity": 2900, "source": "Sentinel AI ESTIMATED", "data_type": DataType.ESTIMATED, "notes": "Road adequate; power needs investment"},
                {"name": "environment", "capacity": 3500, "source": "Bhuvan (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Low ecological sensitivity"},
            ],
            "required_population": 4210, "surplus_deficit": -2110, "can_absorb_alone": False,
        },
        "site-c": {
            "site_name": "Munnar Town Periphery — Site C",
            "c_safe": 1800, "bottleneck": "land",
            "dimensions": [
                {"name": "land", "capacity": 1800, "source": "Bhuvan LULC (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Binding constraint"},
                {"name": "water", "capacity": 2200, "source": "PWD Kerala (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Town supply has headroom"},
                {"name": "healthcare", "capacity": 3200, "source": "data.gov.in (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Munnar hospital + PHC"},
                {"name": "education", "capacity": 2800, "source": "UDISE+ (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Multiple schools within 2km"},
                {"name": "infrastructure", "capacity": 3100, "source": "Sentinel AI ESTIMATED", "data_type": DataType.ESTIMATED, "notes": "Best infrastructure of three sites"},
                {"name": "environment", "capacity": 2500, "source": "Bhuvan (DEMO)", "data_type": DataType.ESTIMATED, "notes": "Peri-urban, moderate sensitivity"},
            ],
            "required_population": 4210, "surplus_deficit": -2410, "can_absorb_alone": False,
        },
    }
    entry = data.get(site_id, data["site-a"])
    return {"data_status": DataStatus.DEMO, "site_id": site_id, "data_type": DataType.DERIVED, **entry}


def get_optimization_result(habitation_id: str) -> dict:
    return {
        "data_status": DataStatus.DEMO,
        "habitation_id": habitation_id,
        "status": "FEASIBLE",
        "total_demand": 4210,
        "total_allocated": 4210,
        "unallocated": 0,
        "allocations": [
            {"site_id": "site-a", "site_name": "Devikulam Plateau — Site A", "allocated_population": 2100, "distance_km": 4.2, "utilization_pct": 66, "surplus_after": 1100},
            {"site_id": "site-c", "site_name": "Munnar Town Periphery — Site C", "allocated_population": 1800, "distance_km": 2.1, "utilization_pct": 100, "surplus_after": 0},
            {"site_id": "site-b", "site_name": "Pallivasal Flatland — Site B", "allocated_population": 310, "distance_km": 7.8, "utilization_pct": 15, "surplus_after": 1790},
        ],
        "objective_value": 14820,
        "constraints_applied": [
            "population ≤ c_safe per site",
            "hazard score ≤ 40 (hard threshold)",
            "all sites technically feasible",
            "distance ≤ 15km",
            "valid origin-destination pairing",
        ],
        "data_type": DataType.RECOMMENDATION,
        "solver_note": (
            "Solved using greedy allocation approximating OR-Tools CP-SAT. "
            "Objective: minimize weighted sum of (distance × population) + infrastructure deficit. "
            "Full OR-Tools integration in production build."
        ),
    }


def run_scenario_simulation(params: dict) -> dict:
    base_risk = 94
    rainfall_mult = params.get("rainfall_multiplier", 1.0)
    pop_change = params.get("population_change_pct", 0)
    cap_reduction = params.get("capacity_reduction_pct", 0)
    road_disruption = params.get("road_disruption", False)

    hazard_delta = (rainfall_mult - 1.0) * 37.6 * 1.4
    simulated_risk = min(100, max(0, round(base_risk + hazard_delta)))
    simulated_demand = round(4210 * (1 + pop_change / 100))
    total_capacity = 7100  # 3200 + 2100 + 1800
    effective_capacity = round(total_capacity * (1 - cap_reduction / 100))
    if road_disruption:
        effective_capacity -= 2100  # Site B removed
    simulated_gap = simulated_demand - effective_capacity
    simulated_priority = (
        Priority.IMMEDIATE if simulated_risk >= 75
        else Priority.SHORT_TERM if simulated_risk >= 50
        else Priority.MEDIUM_TERM
    )
    return {
        "data_status": DataStatus.SIMULATION,
        "warning": "SIMULATED — Not live data. For planning purposes only.",
        "input_params": params,
        "simulated_risk": simulated_risk,
        "simulated_priority": simulated_priority,
        "simulated_demand": simulated_demand,
        "simulated_capacity_available": effective_capacity,
        "simulated_gap": simulated_gap,
        "data_type": DataType.SIMULATED,
    }
