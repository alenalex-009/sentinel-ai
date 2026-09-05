"""Regional routing dataset configuration (Phase 4.5 / Phase 5).

Supported routing regions: KERALA, VIZAG, ASSAM.

Each region maps to its own GraphHopper service + dataset. A single GraphHopper
instance cannot safely hot-swap datasets (graphs are built at import time), so
the reliable pattern is one engine per region — the backend selects the service
for the coordinates being routed.

Bounds are REFERENCE bounds used only to guard against cross-region routing
(never a coverage claim): routing still fails with UNAVAILABLE when the region's
dataset is not actually loaded for the queried coordinates.

Dataset status:
  - development: a real OSM dataset IS loaded for the region (prototype-area
    coverage — see `dataset_label` and `osm/README.md` for exact coverage;
    none of these are full-state or production datasets)
  - required:    dataset NOT loaded — exact required dataset documented here
"""

from dataclasses import dataclass
from typing import Optional, Tuple

# (min_lat, max_lat, min_lon, max_lon) — approximate reference bounds
Bounds = Tuple[float, float, float, float]

# Actual geographic bounds of each loaded extract (min_lat, max_lat,
# min_lon, max_lon). These ARE the dataset-coverage gate: routing for a pair
# is attempted only when both endpoints fall inside them.
_EXTRACT_BOUNDS: dict = {
    # Kerala (Idukki pilot region): all 5 prototype habitations (adimali,
    # kanthalloor, marayoor, munnar-central, rajakkad) + 3 candidate sites.
    "kerala": (9.90, 10.31, 76.88, 77.26),
    # Visakhapatnam (Vizag) urban pilot.
    "vizag": (17.55, 17.90, 83.10, 83.45),
    # Assam pilot: Guwahati urban area (no Assam habitation/site records exist
    # in the seed yet — dataset provides real routing for the pilot area only).
    "assam": (26.05, 26.30, 91.60, 91.95),
}


@dataclass(frozen=True)
class RegionConfig:
    key: str
    display: str
    reference_bounds: Bounds
    dataset_status: str            # "development" | "required"
    dataset_label: str
    dataset_coverage: Optional[Bounds]  # actual loaded-extract bounds
    url_env: str                   # settings field carrying the service URL
    default_url: Optional[str] = None


REGIONS: dict = {
    "kerala": RegionConfig(
        key="kerala",
        display="Kerala",
        reference_bounds=(8.0, 13.0, 74.5, 77.7),
        dataset_status="development",
        dataset_label=(
            "Kerala — OSM regional extract (Overpass API, 2026-09-04), Idukki "
            "pilot region ~38x47 km (9.90-10.31N, 76.88-77.26E): covers ALL "
            "Kerala prototype habitations (Munnar Central, Adimali, Rajakkad, "
            "Kanthalloor, Marayoor) and candidate sites. Not full-state "
            "coverage. Replaces the earlier Munnar-only development extract."
        ),
        dataset_coverage=_EXTRACT_BOUNDS["kerala"],
        url_env="GRAPHHOPPER_KERALA_URL",
        default_url="http://localhost:8989",
    ),
    "vizag": RegionConfig(
        key="vizag",
        display="Visakhapatnam (Vizag), Andhra Pradesh",
        reference_bounds=(15.5, 19.5, 79.5, 84.5),
        dataset_status="development",
        dataset_label=(
            "Vizag — OSM urban extract (Overpass API, 2026-09-04), "
            "Visakhapatnam urban pilot ~39x33 km (17.55-17.90N, 83.10-83.45E). "
            "Covers the Vizag city prototype area. Not district- or "
            "state-wide coverage; no Vizag habitation/site seed records exist "
            "yet, so ID-based routing remains UNAVAILABLE until such records "
            "are added."
        ),
        dataset_coverage=_EXTRACT_BOUNDS["vizag"],
        url_env="GRAPHHOPPER_VIZAG_URL",
        default_url=None,
    ),
    "assam": RegionConfig(
        key="assam",
        display="Assam",
        reference_bounds=(24.0, 28.5, 89.5, 97.2),
        dataset_status="development",
        dataset_label=(
            "Assam — OSM urban extract (Overpass API, 2026-09-04), Guwahati "
            "urban pilot ~28x39 km (26.05-26.30N, 91.60-91.95E). Covers the "
            "Guwahati prototype area. Not state-wide coverage; no Assam "
            "habitation/site seed records exist yet, so ID-based routing "
            "remains UNAVAILABLE until such records are added."
        ),
        dataset_coverage=_EXTRACT_BOUNDS["assam"],
        url_env="GRAPHHOPPER_ASSAM_URL",
        default_url=None,
    ),
}


def region_keys() -> list:
    return list(REGIONS.keys())


def region_for_coordinates(lat1: float, lon1: float, lat2: float, lon2: float) -> Optional[str]:
    """Single region whose reference bounds contain BOTH points.

    Returns None when no single region covers both coordinates — the caller
    must not route (incompatible or uncovered), never guess.
    """
    matches = []
    for key, r in REGIONS.items():
        min_lat, max_lat, min_lon, max_lon = r.reference_bounds
        inside = (
            min_lat <= lat1 <= max_lat and min_lon <= lon1 <= max_lon
            and min_lat <= lat2 <= max_lat and min_lon <= lon2 <= max_lon
        )
        if inside:
            matches.append(key)
    return matches[0] if len(matches) == 1 else None


def coordinates_inside(bounds: Optional[Bounds], lat: float, lon: float) -> bool:
    if bounds is None:
        return False
    min_lat, max_lat, min_lon, max_lon = bounds
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
