"""Shared enums and type definitions for Sentinel AI."""

from enum import Enum


class DataType(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    ESTIMATED = "ESTIMATED"
    SIMULATED = "SIMULATED"
    RECOMMENDATION = "RECOMMENDATION"


class Priority(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    SHORT_TERM = "SHORT-TERM"
    MEDIUM_TERM = "MEDIUM-TERM"
    MONITOR = "MONITOR"
    NONE = "NONE"


class HazardType(str, Enum):
    LANDSLIDE = "LANDSLIDE"
    FLOOD = "FLOOD"
    CLOUDBURST = "CLOUDBURST"
    EROSION = "EROSION"
    MULTI_HAZARD = "MULTI_HAZARD"


class VulnerabilityLevel(str, Enum):
    VERY_HIGH = "VERY HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY LOW"


class DataStatus(str, Enum):
    LIVE = "LIVE"
    DEMO = "DEMO"
    SIMULATION = "SIMULATION"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
