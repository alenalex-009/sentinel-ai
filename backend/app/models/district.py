"""District and administrative boundary models."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.types import DataStatus


class DistrictSummary(BaseModel):
    id: str
    name: str
    state: str
    total_habitations: int
    critical_habitations: int
    high_risk_habitations: int
    total_population_at_risk: int
    immediate_relocation_needed: int
    data_status: DataStatus
    last_updated: datetime


class DistrictOverview(BaseModel):
    district: DistrictSummary
    what_changed: List[dict]
    priority_actions: List[dict]
    telemetry_anomalies: List[dict]
    data_freshness: dict
