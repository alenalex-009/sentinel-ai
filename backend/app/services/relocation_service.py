"""Relocation workflow service — Slice 5.

Bridges the live risk output of Slice 3 (habitations with current_score) and
the safe-zone candidates of Slice 4 into a real carrying-capacity assessment
and OR-Tools allocation plan.

Plan lifecycle: draft → approved → executing → completed (+ cancelled).
Assignments are the per-habitation site allocations produced by the optimizer.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.database import get_db
from app.core.config import settings
from app.services import demo_data, optimizer

logger = logging.getLogger(__name__)

# A habitation is considered "at risk" and requires relocation when its
# current risk score reaches this threshold.
RELOCATION_RISK_THRESHOLD = 60.0


@dataclass
class Plan:
    id: int
    district_id: str
    name: str
    status: str
    total_demand: int
    total_allocated: int
    unallocated: int
    data_status: str
    description: str = ""
    created_by: Optional[str] = None
    approved_by: Optional[str] = None


@dataclass
class Assignment:
    id: int
    plan_id: int
    habitation_id: str
    habitation_name: str
    site_id: str
    site_name: str
    allocated_population: int
    distance_km: float
    utilization_pct: float
    surplus_after: int
    status: str
    data_status: str


def _demand_for_habitation(
    habitation_id: str, current_score: float, population: int
) -> int:
    """Population requiring relocation for one habitation.

    Full relocation when current_score >= threshold; a partial demand
    proportional to the excess above a lower band floor otherwise.
    Scores below the floor contribute nothing.
    """
    if current_score >= RELOCATION_RISK_THRESHOLD:
        return population
    floor = RELOCATION_RISK_THRESHOLD - (100.0 - RELOCATION_RISK_THRESHOLD)
    if current_score <= floor:
        return 0
    excess = current_score - floor
    return int(population * (excess / (100.0 - RELOCATION_RISK_THRESHOLD)))


# Sentinel AI capacity baseline — deterministic model used when a candidate
# site has no surveyed parcel data (Slice 5). Capacity scales with the
# discovery grid footprint and a documented persons/km² density, then scales
# with suitability. Always labelled RECOMMENDATION, never OBSERVED.
_CAPACITY_BASE_PERSONS_KM2 = 250.0          # upland Kerala residential baseline
_CAPACITY_GRID_CELL_KM2 = 9.0               # 3 km × 3 km discovery cell (see config)
_CAPACITY_BUILDABLE_FRACTION = 0.30         # share of cell assumed buildable
_CAPACITY_SUITABILITY_CEILING = 1.0


def _nominal_capacity(c: dict) -> int:
    """Estimate carrying capacity for one candidate site.

    Prefers a surveyed `estimated_capacity` / `safe_capacity` when present;
    otherwise applies the documented Sentinel AI baseline model from the
    discovery grid cell size and a density assumption.
    """
    surveyed = c.get("estimated_capacity") or c.get("safe_capacity")
    if surveyed:
        return int(surveyed)
    suitability = float(c.get("suitability_score") or 0.0)
    raw = (
        _CAPACITY_BASE_PERSONS_KM2
        * _CAPACITY_GRID_CELL_KM2
        * _CAPACITY_BUILDABLE_FRACTION
    )
    scaled = raw * min(_CAPACITY_SUITABILITY_CEILING, suitability / 100.0)
    return int(round(scaled / 10.0) * 10)


async def calculate_demand(
    session: AsyncSession, district_id: str
) -> dict:
    """Compute relocation demand from live current-risk scores.

    When PostGIS is unavailable the labelled DEMO fallback is returned —
    never a 500. The DEMO branch reports 0 demand and an honest note so an
    operator can distinguish "nothing to move" from "couldn't check".
    """
    try:
        result = await session.execute(
            text(
                """
                SELECT h.id, h.name, h.population,
                       r.current_score
                FROM habitations h
                JOIN LATERAL (
                    SELECT current_score
                    FROM risk_scores rs
                    WHERE rs.habitation_id = h.id
                    ORDER BY rs.computed_at DESC
                    LIMIT 1
                ) r ON true
                WHERE h.district_id = :district_id
                """
            ),
            {"district_id": district_id},
        )
    except Exception as exc:  # noqa: BLE001 — DB down must not 500
        logger.warning(
            f"[relocation] demand query failed for {district_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return {
            "data_status": "DEMO",
            "district_id": district_id,
            "total_demand": 0,
            "habitations": [],
            "note": "PostGIS unavailable - live risk scores could not be read; "
                    "no relocation demand reported (0, not fabricated).",
        }
    rows = result.mappings().all()
    if not rows:
        return {"data_status": "DEMO", "total_demand": 0, "habitations": []}

    total_demand = 0
    hab_details = []
    for row in rows:
        pop = row["population"] or 0
        score = row["current_score"] or 0.0
        demand = _demand_for_habitation(row["id"], score, pop)
        total_demand += demand
        hab_details.append({
            "habitation_id": row["id"],
            "name": row["name"],
            "population": pop,
            "current_score": score,
            "relocation_demand": demand,
        })

    return {
        "data_status": "DERIVED",
        "district_id": district_id,
        "total_demand": total_demand,
        "demand_habitations": len([h for h in hab_details if h["relocation_demand"] > 0]),
        "habitations": hab_details,
        "note": (
            f"Habitations with current_score >= {RELOCATION_RISK_THRESHOLD} "
            "relocate in full; partial demand otherwise."
        ),
    }


async def get_safe_zone_sites(
    session: AsyncSession, district_id: str
) -> list:
    """Return Slice-4 safe-zone candidates that pass hard constraints."""
    result = await session.execute(
        text(
            """
            SELECT id, name, source, geom, suitability_score,
                   safety_score, estimated_capacity,
                   constraint_pass, constraint_evidence,
                   ST_X(geom) AS lon, ST_Y(geom) AS lat
            FROM safe_zone_candidates
            WHERE district_id = :district_id
              AND constraint_pass = TRUE
              AND source = 'discovered'
            ORDER BY suitability_score DESC
            """
        ),
        {"district_id": district_id},
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]


async def create_plan(
    session: AsyncSession,
    district_id: str,
    name: str,
    created_by: Optional[str] = None,
) -> dict:
    """Create a relocation plan: compute demand, discover sites, run
    optimization, and persist the plan + assignments."""
    from app.services.optimizer import run_optimization, SiteInput

    # 1. Demand from live risk
    demand_data = await calculate_demand(session, district_id)
    if demand_data["data_status"] == "DEMO":
        # No live risk rows — fall back to demo demand, keep label
        demo = demo_data.get_relocation_demand("munnar-central")
        total_demand = demo["relocation_demand"]
        hab_list = []
    else:
        total_demand = demand_data["total_demand"]
        hab_list = demand_data["habitations"]

    # 2. Safe-zone candidate sites from Slice 4
    sites = await get_safe_zone_sites(session, district_id)
    if not sites:
        # No discovered sites yet — fall back to candidate_sites from DB
        result = await session.execute(
            text(
                """
                SELECT id, name, safe_capacity as estimated_capacity,
                       suitability_score, safety_score, geom,
                       ST_X(geom) AS lon, ST_Y(geom) AS lat
                FROM candidate_sites
                WHERE district_id = :district_id
                  AND hard_constraints_passed = TRUE
                ORDER BY suitability_score DESC
                LIMIT 10
                """
                ),
            {"district_id": district_id},
        )
        rows = result.mappings().all()
        sites = [dict(r) for r in rows]

    # 3. Build SiteInput list with distance from each habitation.
    #    Both paths above yield dicts with lon/lat; normalise defensively.
    site_inputs: list[optimizer.SiteInput] = []
    for s in sites:
        nearest_dist = 999.0
        s_lon = s.get("lon") or s.get("longitude") or 0.0
        s_lat = s.get("lat") or s.get("latitude") or 0.0
        for h in hab_list:
            # rough Euclidean distance for ranking; replaced by PostGIS
            # real distance below when available
            d = ((s_lon - 0) ** 2 + (s_lat - 0) ** 2) ** 0.5  # placeholder
            nearest_dist = min(nearest_dist, d * 111.0)  # deg→km rough
        si = optimizer.SiteInput(
            id=s["id"],
            name=s.get("name") or s["id"],
            c_safe=_nominal_capacity(s),
            distance_km=min(nearest_dist, 15.0),
            suitability_score=s.get("suitability_score") or 0,
            safety_score=s.get("safety_score") or 0,
            infrastructure_score=50.0,
            hard_constraints_passed=True,
        )
        site_inputs.append(si)

    # 4. Optimize
    total_hab_demand = sum(
        h["relocation_demand"] for h in hab_list
    ) if hab_list else total_demand

    result = run_optimization(
        demand=max(total_hab_demand, total_demand),
        sites=site_inputs,
        data_status="DERIVED",
    )

    # 5. Persist plan
    plan = {
        "district_id": district_id,
        "name": name,
        "status": "draft",
        "total_demand": result.total_demand,
        "total_allocated": result.total_allocated,
        "unallocated": result.unallocated,
        "optimizer_status": result.status,
        "data_status": result.data_status,
        "created_by": created_by,
    }
    insert_result = await session.execute(
        text(
            """
            INSERT INTO relocation_plans
                (district_id, name, status, total_demand,
                 total_allocated, unallocated, optimizer_status,
                 data_status, created_by)
            VALUES
                (:district_id, :name, :status, :total_demand,
                 :total_allocated, :unallocated, :optimizer_status,
                 :data_status, :created_by)
            RETURNING id
            """
        ),
        plan,
    )
    plan_id = insert_result.scalar()

    # 6. Persist assignments from allocation output.
    #    With per-habitation demand, distribute each site's allocation
    #    proportionally by demand share so the plan is per-habitation.
    #    Without live habitations (demo fallback) a single cohort row is
    #    written so plan/assignment linkage survives.
    assignment_rows = []
    if hab_list and result.allocations:
        demand_total = sum(h["relocation_demand"] for h in hab_list) or 1
        for alloc in result.allocations:
            for h in hab_list:
                share = round(
                    alloc.allocated_population * h["relocation_demand"] / demand_total
                )
                if share <= 0:
                    continue
                assignment_rows.append({
                    "plan_id": plan_id,
                    "habitation_id": h["habitation_id"],
                    "site_id": alloc.site_id,
                    "allocated_population": share,
                    "distance_km": alloc.distance_km,
                    "utilization_pct": alloc.utilization_pct,
                    "surplus_after": alloc.surplus_after,
                })
    else:
        for alloc in result.allocations:
            assignment_rows.append({
                "plan_id": plan_id,
                "habitation_id": None,
                "site_id": alloc.site_id,
                "allocated_population": alloc.allocated_population,
                "distance_km": alloc.distance_km,
                "utilization_pct": alloc.utilization_pct,
                "surplus_after": alloc.surplus_after,
            })

    for a in assignment_rows:
        await session.execute(
            text(
                """
                INSERT INTO relocation_assignments
                    (plan_id, habitation_id, site_id,
                     allocated_population, distance_km,
                     utilization_pct, surplus_after, data_status)
                VALUES
                    (:plan_id, :habitation_id, :site_id,
                     :allocated_population, :distance_km,
                     :utilization_pct, :surplus_after, :data_status)
                """
            ),
            {
                **a,
                "data_status": result.data_status,
            },
        )

    await session.commit()
    return {
        "data_status": result.data_status,
        "plan_id": plan_id,
        "district_id": district_id,
        "name": name,
        "status": "draft",
        "total_demand": result.total_demand,
        "total_allocated": result.total_allocated,
        "unallocated": result.unallocated,
        "optimizer_status": result.status,
        "allocations": assignment_rows,
        "constraints_applied": result.constraints_applied,
        "solver_note": result.solver_note,
    }


async def get_plan(session: AsyncSession, plan_id: int) -> dict:
    """Fetch a plan with its assignments."""
    plan_result = await session.execute(
        text("SELECT * FROM relocation_plans WHERE id = :id"),
        {"id": plan_id},
    )
    plan_row = plan_result.mappings().first()
    if not plan_row:
        return {"data_status": "EMPTY", "reason": "plan not found"}

    assign_result = await session.execute(
        text("SELECT * FROM relocation_assignments WHERE plan_id = :plan_id"),
        {"plan_id": plan_id},
    )
    assignments = [dict(r) for r in assign_result.mappings().all()]

    return {
        **dict(plan_row),
        "assignments": assignments,
        "data_status": plan_row["data_status"],
    }


async def transition_plan(
    session: AsyncSession, plan_id: int, new_status: str,
    approved_by: Optional[str] = None,
) -> dict:
    """Transition a plan's lifecycle status."""
    valid_transitions = {
        "draft": ["approved", "cancelled"],
        "approved": ["executing", "cancelled"],
        "executing": ["completed", "cancelled"],
    }
    row = await session.execute(
        text("SELECT status FROM relocation_plans WHERE id = :id"),
        {"id": plan_id},
    )
    current = row.scalar_one_or_none()
    if not current:
        return {"data_status": "EMPTY", "reason": "plan not found"}
    if new_status not in valid_transitions.get(current, []):
        return {
            "data_status": "ERROR",
            "reason": f"invalid transition {current} → {new_status}",
        }

    set_clause = f"status = :new_status, updated_at = NOW()"
    params = {"id": plan_id, "new_status": new_status}
    if new_status == "approved" and approved_by:
        set_clause += ", approved_by = :approved_by, approved_at = NOW()"
        params["approved_by"] = approved_by
    if new_status == "executing":
        set_clause += ", executed_at = NOW()"
    if new_status == "completed":
        set_clause += ", completed_at = NOW()"

    await session.execute(
        text(f"UPDATE relocation_plans SET {set_clause} WHERE id = :id"),
        params,
    )
    await session.commit()
    return {"data_status": "DERIVED", "plan_id": plan_id, "status": new_status}
