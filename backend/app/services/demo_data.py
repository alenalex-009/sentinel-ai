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
        # Return simplified data for other habitations
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
            {
                "step": 1,
                "label": "HAZARD",
                "description": "Heavy rainfall + high soil saturation",
                "data_type": DataType.OBSERVED,
                "source": "IMD + KSDMA Sensors (DEMO)",
                "value": "287mm / 72hr | Soil 94%",
            },
            {
                "step": 2,
                "label": "EXPOSURE",
                "description": "Population within hazard zone",
                "data_type": DataType.DERIVED,
                "source": "Census 2011 projected + Bhuvan LULC (DEMO)",
                "value": "4,210 persons | 1,053 households",
            },
            {
                "step": 3,
                "label": "VULNERABILITY",
                "description": "Structural and access vulnerability",
                "data_type": DataType.DERIVED,
                "source": "Census + KSDMA + Field Data (DEMO)",
                "value": "74/100 — HIGH",
            },
            {
                "step": 4,
                "label": "RISK",
                "description": "Composite risk score",
                "data_type": DataType.DERIVED,
                "source": "Sentinel AI Risk Engine (DEMO)",
                "value": "94/100 (Baseline: 65, Change: +29)",
            },
            {
                "step": 5,
                "label": "PRIORITY",
                "description": "Immediate relocation assessment recommended",
                "data_type": DataType.RECOMMENDATION,
                "source": "Sentinel AI RPI Engine (DEMO)",
                "value": "IMMEDIATE — RPI 88/100",
            },
        ],
        "permanent_settlement_suitable": False,
        "permanent_suitability_note": (
            "This area falls within a high landslide susceptibility zone per KSDMA mapping. "
            "Permanent settlement suitability assessment is separate from current operational risk. "
            "Official Red Zone designation requires government authority review. "
            "This is a TECHNICALLY SCREENED CANDIDATE for further assessment only."
        ),
        "system_recommendation": (
            "Prioritize Munnar Central for immediate relocation assessment and candidate-site screening. "
            "Current risk elevation is driven by active rainfall event. "
            "Permanent settlement suitability requires separate formal assessment."
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
    """GeoJSON FeatureCollection for MapLibre rendering."""
    habitations = get_habitation_list(district_id)["habitations"]
    features = []
    for h in habitations:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [h["longitude"], h["latitude"]],
            },
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
    return {
        "type": "FeatureCollection",
        "data_status": DataStatus.DEMO,
        "features": features,
    }


def get_risk_intelligence(district_id: str, mode: str) -> dict:
    return {
        "data_status": DataStatus.DEMO,
        "mode": mode,
        "district_id": district_id,
        "risk_distribution": {
            "critical": 23,
            "high": 67,
            "medium": 189,
            "low": 568,
        },
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
        "human_impact": {
            "total_at_risk": 142300,
            "immediate_action": 8420,
            "data_type": DataType.DERIVED,
        },
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
            {"step": 6, "node": "SITE / CAPACITY CHECK", "value": "3 candidate sites screened", "data_type": DataType.DERIVED},
            {"step": 7, "node": "SYSTEM RECOMMENDATION", "value": "Initiate relocation assessment for Ward 04", "data_type": DataType.RECOMMENDATION},
        ],
    }


def get_candidate_sites(habitation_id: str) -> dict:
    return {
        "data_status": DataStatus.DEMO,
        "habitation_id": habitation_id,
        "note": "Technically Screened Candidates only. Official approval required before relocation.",
        "sites": [
            {
                "id": "site-a",
                "name": "Devikulam Plateau Site A",
                "distance_km": 4.2,
                "suitability_score": 82,
                "safe_capacity": 3200,
                "safety_score": 88,
                "infrastructure_score": 79,
                "accessibility_score": 85,
                "water_score": 76,
                "healthcare_score": 71,
                "education_score": 68,
                "latitude": 10.1123,
                "longitude": 77.0812,
                "data_type": DataType.DERIVED,
            },
            {
                "id": "site-b",
                "name": "Pallivasal Flatland Site B",
                "distance_km": 7.8,
                "suitability_score": 74,
                "safe_capacity": 2100,
                "safety_score": 91,
                "infrastructure_score": 65,
                "accessibility_score": 72,
                "water_score": 83,
                "healthcare_score": 58,
                "education_score": 61,
                "latitude": 10.0634,
                "longitude": 77.1234,
                "data_type": DataType.DERIVED,
            },
            {
                "id": "site-c",
                "name": "Munnar Town Periphery Site C",
                "distance_km": 2.1,
                "suitability_score": 68,
                "safe_capacity": 1800,
                "safety_score": 79,
                "infrastructure_score": 88,
                "accessibility_score": 92,
                "water_score": 71,
                "healthcare_score": 89,
                "education_score": 85,
                "latitude": 10.0756,
                "longitude": 77.0623,
                "data_type": DataType.DERIVED,
            },
        ],
    }


def get_capacity_assessment(site_id: str) -> dict:
    capacities = {
        "site-a": {
            "land": 3800, "water": 3200, "healthcare": 4500,
            "education": 3600, "infrastructure": 3400, "environment": 5000,
        },
        "site-b": {
            "land": 2800, "water": 2100, "healthcare": 2600,
            "education": 2400, "infrastructure": 2900, "environment": 3500,
        },
        "site-c": {
            "land": 2200, "water": 1800, "healthcare": 3200,
            "education": 2800, "infrastructure": 3100, "environment": 2500,
        },
    }
    dims = capacities.get(site_id, capacities["site-a"])
    bottleneck = min(dims, key=dims.get)
    c_safe = dims[bottleneck]
    return {
        "data_status": DataStatus.DEMO,
        "site_id": site_id,
        "c_safe": c_safe,
        "bottleneck": bottleneck,
        "dimensions": dims,
        "required_population": 4210,
        "surplus_deficit": c_safe - 4210,
        "data_type": DataType.DERIVED,
    }


def run_scenario_simulation(params: dict) -> dict:
    base_risk = 94
    rainfall_mult = params.get("rainfall_multiplier", 1.0)
    simulated_risk = min(100, base_risk * rainfall_mult)
    return {
        "data_status": DataStatus.SIMULATION,
        "warning": "SIMULATED — Not live data. For planning purposes only.",
        "input_params": params,
        "simulated_risk": round(simulated_risk, 1),
        "simulated_priority": Priority.IMMEDIATE if simulated_risk >= 75 else Priority.SHORT_TERM,
        "data_type": DataType.SIMULATED,
    }
