"""Habitation data models."""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.models.types import (
    DataType, Priority, HazardType, VulnerabilityLevel, DataStatus
)


class HazardInfo(BaseModel):
    type: HazardType
    intensity: float  # 0-100
    data_type: DataType
    source: str
    description: str


class VulnerabilityBreakdown(BaseModel):
    overall: float  # 0-100
    level: VulnerabilityLevel
    demographic: float
    socioeconomic: float
    infrastructure: float
    accessibility: float
    data_type: DataType


class RiskScore(BaseModel):
    current: float  # 0-100
    baseline: float  # 0-100
    change: float  # delta
    hazard_component: float
    exposure_component: float
    vulnerability_component: float
    interaction_component: float
    data_type: DataType
    computed_at: datetime


class RelocationPriority(BaseModel):
    priority: Priority
    rpi_score: float  # 0-100
    risk_component: float
    vulnerability_component: float
    exposed_population_component: float
    historical_impact_component: float
    urgency_component: float
    data_type: DataType


class EvidenceItem(BaseModel):
    step: int
    label: str
    description: str
    data_type: DataType
    source: Optional[str] = None
    value: Optional[str] = None


class HabitationGeoJSON(BaseModel):
    type: str = "Feature"
    geometry: Dict[str, Any]
    properties: Dict[str, Any]


class HabitationDetail(BaseModel):
    id: str
    name: str
    ward: str
    taluk: str
    district: str
    state: str
    population: int
    households: int
    area_ha: float
    latitude: float
    longitude: float
    hazards: List[HazardInfo]
    vulnerability: VulnerabilityBreakdown
    risk: RiskScore
    relocation_priority: RelocationPriority
    evidence_chain: List[EvidenceItem]
    permanent_settlement_suitable: bool
    permanent_suitability_note: str
    data_status: DataStatus
    last_updated: datetime
    geojson: Optional[HabitationGeoJSON] = None


class HabitationListItem(BaseModel):
    id: str
    name: str
    ward: str
    taluk: str
    district: str
    population: int
    risk_score: float
    risk_change: float
    priority: Priority
    primary_hazard: HazardType
    latitude: float
    longitude: float
    data_status: DataStatus
