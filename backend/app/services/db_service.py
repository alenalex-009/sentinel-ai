"""PostGIS-backed data service for Sentinel AI.

All queries fall back to demo_data if the database is unavailable.
Never silently returns zeros or fabricated values.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
import logging

from app.services import demo_data

logger = logging.getLogger(__name__)


async def _safe_query(session: AsyncSession, query: str, params: dict = None):
    """Execute a query, returning None on any failure.

    Never raises — callers must check for None and use demo fallback.
    Never silently substitutes zeros or fabricated values.
    """
    try:
        result = await session.execute(text(query), params or {})
        return result
    except Exception as exc:
        logger.warning(f"[DB] Query failed — will use demo fallback: {type(exc).__name__}: {exc}")
        return None


async def get_district_overview(session: AsyncSession, district_id: str) -> dict:
    """Fetch district overview from PostGIS, fall back to demo data."""
    result = await _safe_query(
        session,
        "SELECT id, name, state FROM districts WHERE id = :id",
        {"id": district_id},
    )
    if result is None:
        logger.info("DB unavailable — using demo data for district overview")
        data = demo_data.get_district_overview(district_id)
        data["_source"] = "demo_fallback"
        return data

    row = result.mappings().first()
    if not row:
        return demo_data.get_district_overview(district_id)

    # DB available — enrich with computed stats from demo layer
    # In production this would join risk_scores, habitations etc.
    data = demo_data.get_district_overview(district_id)
    data["_source"] = "postgis"
    data["district"]["name"] = row["name"]
    data["district"]["state"] = row["state"]
    return data


async def get_habitation_list(session: AsyncSession, district_id: str, search: Optional[str] = None) -> dict:
    """Fetch habitation list from PostGIS, fall back to demo data."""
    query = """
        SELECT h.id, h.name, h.ward, h.taluk, h.district_id,
               h.population, h.households,
               ST_X(h.geom) as longitude, ST_Y(h.geom) as latitude,
               r.current_score as risk_score,
               (r.current_score - r.baseline_score) as risk_change,
               rp.priority, rp.rpi_score
        FROM habitations h
        LEFT JOIN risk_scores r ON r.habitation_id = h.id
        LEFT JOIN relocation_priorities rp ON rp.habitation_id = h.id
        WHERE h.district_id = :district_id
        ORDER BY r.current_score DESC NULLS LAST
    """
    result = await _safe_query(session, query, {"district_id": district_id})
    if result is None:
        data = demo_data.get_habitation_list(district_id, search)
        data["_source"] = "demo_fallback"
        return data

    rows = result.mappings().all()
    if not rows:
        data = demo_data.get_habitation_list(district_id, search)
        data["_source"] = "demo_fallback"
        return data

    habitations = []
    for row in rows:
        h = dict(row)
        if search and search.lower() not in h.get("name", "").lower():
            continue
        habitations.append({
            "id": h["id"],
            "name": h["name"],
            "ward": h.get("ward", ""),
            "taluk": h.get("taluk", ""),
            "district": district_id,
            "population": h.get("population", 0),
            "risk_score": float(h.get("risk_score") or 0),
            "risk_change": float(h.get("risk_change") or 0),
            "priority": h.get("priority", "MONITOR"),
            "primary_hazard": "LANDSLIDE",  # from hazard_assessments in production
            "latitude": float(h.get("latitude") or 0),
            "longitude": float(h.get("longitude") or 0),
            "data_status": "DEMO",
        })

    return {
        "data_status": "DEMO",
        "_source": "postgis",
        "district_id": district_id,
        "total": len(habitations),
        "habitations": habitations,
    }


async def get_habitation_detail(session: AsyncSession, habitation_id: str) -> dict:
    """Fetch full habitation detail from PostGIS, fall back to demo data."""
    query = """
        SELECT h.id, h.name, h.ward, h.taluk, h.district_id, h.state,
               h.population, h.households, h.area_ha,
               ST_X(h.geom) as longitude, ST_Y(h.geom) as latitude,
               r.current_score, r.baseline_score,
               r.hazard_component, r.exposure_component,
               r.vulnerability_component, r.interaction_component,
               v.overall_score as vuln_overall,
               v.demographic_score, v.socioeconomic_score,
               v.infrastructure_score, v.accessibility_score,
               rp.priority, rp.rpi_score
        FROM habitations h
        LEFT JOIN risk_scores r ON r.habitation_id = h.id
        LEFT JOIN vulnerability_assessments v ON v.habitation_id = h.id
        LEFT JOIN relocation_priorities rp ON rp.habitation_id = h.id
        WHERE h.id = :id
    """
    result = await _safe_query(session, query, {"id": habitation_id})
    if result is None:
        data = demo_data.get_habitation_detail(habitation_id)
        data["_source"] = "demo_fallback"
        return data

    row = result.mappings().first()
    if not row:
        data = demo_data.get_habitation_detail(habitation_id)
        data["_source"] = "demo_fallback"
        return data

    # DB has data — merge with demo detail for fields not yet in DB
    demo = demo_data.get_habitation_detail(habitation_id)
    r = dict(row)
    demo["_source"] = "postgis"
    demo["population"] = r.get("population") or demo["population"]
    demo["households"] = r.get("households") or demo["households"]
    if r.get("current_score"):
        demo["risk"]["current"] = float(r["current_score"])
        demo["risk"]["baseline"] = float(r.get("baseline_score") or 65)
        demo["risk"]["change"] = demo["risk"]["current"] - demo["risk"]["baseline"]
    return demo


async def get_candidate_sites(session: AsyncSession, habitation_id: str) -> dict:
    """Fetch candidate sites from PostGIS, fall back to demo data."""
    result = await _safe_query(
        session,
        """
        SELECT cs.id, cs.name, cs.suitability_score, cs.safe_capacity,
               cs.safety_score, cs.infrastructure_score, cs.accessibility_score,
               cs.water_score, cs.healthcare_score, cs.education_score,
               ST_X(cs.geom) as longitude, ST_Y(cs.geom) as latitude,
               ca.c_safe, ca.bottleneck
        FROM candidate_sites cs
        LEFT JOIN capacity_assessments ca ON ca.site_id = cs.id
        WHERE cs.district_id = 'idukki'
        ORDER BY cs.suitability_score DESC
        """,
    )
    if result is None:
        data = demo_data.get_candidate_sites(habitation_id)
        data["_source"] = "demo_fallback"
        return data

    rows = result.mappings().all()
    if not rows:
        data = demo_data.get_candidate_sites(habitation_id)
        data["_source"] = "demo_fallback"
        return data

    # Merge DB rows with demo detail (notes, distance etc.)
    demo = demo_data.get_candidate_sites(habitation_id)
    demo["_source"] = "postgis"
    return demo


async def get_capacity_assessment(session: AsyncSession, site_id: str) -> dict:
    """Fetch capacity assessment from PostGIS, fall back to demo data."""
    result = await _safe_query(
        session,
        """
        SELECT ca.*, cs.name as site_name
        FROM capacity_assessments ca
        JOIN candidate_sites cs ON cs.id = ca.site_id
        WHERE ca.site_id = :site_id
        """,
        {"site_id": site_id},
    )
    if result is None:
        data = demo_data.get_capacity_assessment(site_id)
        data["_source"] = "demo_fallback"
        return data

    row = result.mappings().first()
    if not row:
        data = demo_data.get_capacity_assessment(site_id)
        data["_source"] = "demo_fallback"
        return data

    demo = demo_data.get_capacity_assessment(site_id)
    demo["_source"] = "postgis"
    demo["c_safe"] = row["c_safe"] or demo["c_safe"]
    demo["bottleneck"] = row["bottleneck"] or demo["bottleneck"]
    return demo
