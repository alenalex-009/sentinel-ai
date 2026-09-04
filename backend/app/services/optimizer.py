"""OR-Tools CP-SAT optimization service for Sentinel AI.

Objective: minimize weighted (distance × population) + residual hazard exposure
           + infrastructure deficit

Constraints:
  - allocated population per site ≤ c_safe
  - hazard score at site ≤ hard threshold (40)
  - site must have passed hard feasibility constraints
  - total allocated ≤ total demand
  - distance ≤ max_distance_km

All results are labelled RECOMMENDATION.
Never claim a result is real unless actually computed by the solver.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SiteInput:
    id: str
    name: str
    c_safe: int                  # safe carrying capacity
    distance_km: float           # distance from source habitation
    suitability_score: float     # 0-100
    safety_score: float          # 0-100 (higher = safer)
    infrastructure_score: float  # 0-100
    hard_constraints_passed: bool


@dataclass
class AllocationOutput:
    site_id: str
    site_name: str
    allocated_population: int
    distance_km: float
    utilization_pct: float
    surplus_after: int


@dataclass
class OptimizationOutput:
    status: str                        # FEASIBLE | INFEASIBLE | PARTIAL | ERROR
    total_demand: int
    total_allocated: int
    unallocated: int
    allocations: List[AllocationOutput]
    objective_value: float
    constraints_applied: List[str]
    solver_note: str
    data_type: str = "RECOMMENDATION"
    data_status: str = "DEMO"


HARD_HAZARD_THRESHOLD = 40.0   # sites with safety_score < (100 - threshold) are excluded
MAX_DISTANCE_KM = 15.0
SCALE = 100                     # integer scaling for CP-SAT


def run_optimization(
    demand: int,
    sites: List[SiteInput],
    max_distance_km: float = MAX_DISTANCE_KM,
    data_status: str = "DEMO",
) -> OptimizationOutput:
    """Run CP-SAT optimization. Falls back to greedy if OR-Tools unavailable."""
    try:
        from ortools.sat.python import cp_model
        return _run_cpsat(demand, sites, max_distance_km, cp_model, data_status)
    except ImportError:
        logger.warning("OR-Tools not available — using greedy fallback")
        return _run_greedy(demand, sites, max_distance_km, data_status, solver_note="Greedy fallback (OR-Tools not installed)")
    except Exception as exc:
        logger.error(f"OR-Tools optimization failed: {exc}")
        return _run_greedy(demand, sites, max_distance_km, data_status, solver_note=f"Greedy fallback (CP-SAT error: {exc})")


def _run_cpsat(demand, sites, max_distance_km, cp_model, data_status) -> OptimizationOutput:
    """Real CP-SAT optimization."""
    model = cp_model.CpModel()

    # Filter feasible sites
    feasible = [
        s for s in sites
        if s.hard_constraints_passed
        and s.distance_km <= max_distance_km
        and (100 - s.safety_score) <= HARD_HAZARD_THRESHOLD
    ]

    if not feasible:
        return OptimizationOutput(
            status="INFEASIBLE",
            total_demand=demand,
            total_allocated=0,
            unallocated=demand,
            allocations=[],
            objective_value=0,
            constraints_applied=["No sites passed hard safety/distance constraints"],
            solver_note="No technically feasible candidate sites available.",
            data_status=data_status,
        )

    # Decision variables: allocation[i] = population allocated to site i (integer)
    alloc_vars = []
    for site in feasible:
        var = model.NewIntVar(0, site.c_safe, f"alloc_{site.id}")
        alloc_vars.append(var)

    # Constraint: total allocated ≤ demand
    model.Add(sum(alloc_vars) <= demand)

    # Constraint: total allocated ≥ min(demand, total_capacity)
    total_cap = sum(s.c_safe for s in feasible)
    model.Add(sum(alloc_vars) >= min(demand, total_cap))

    # Objective: minimize weighted distance × allocation + infrastructure deficit
    # Scale to integers: distance * SCALE, infra_deficit * SCALE
    obj_terms = []
    for i, site in enumerate(feasible):
        dist_cost = int(site.distance_km * SCALE)
        infra_deficit = int((100 - site.infrastructure_score) * SCALE // 10)
        obj_terms.append((dist_cost + infra_deficit) * alloc_vars[i])

    model.Minimize(sum(obj_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)

    status_map = {
        cp_model.OPTIMAL: "FEASIBLE",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "PARTIAL",
        cp_model.MODEL_INVALID: "ERROR",
    }
    result_status = status_map.get(status, "ERROR")

    allocations = []
    total_allocated = 0
    obj_val = 0.0

    if result_status in ("FEASIBLE", "PARTIAL"):
        for i, site in enumerate(feasible):
            alloc = solver.Value(alloc_vars[i])
            if alloc > 0:
                util = round((alloc / site.c_safe) * 100)
                surplus = site.c_safe - alloc
                allocations.append(AllocationOutput(
                    site_id=site.id,
                    site_name=site.name,
                    allocated_population=alloc,
                    distance_km=site.distance_km,
                    utilization_pct=util,
                    surplus_after=surplus,
                ))
                total_allocated += alloc
        obj_val = solver.ObjectiveValue()

    unallocated = demand - total_allocated

    constraints = [
        f"population ≤ c_safe per site",
        f"hazard score ≤ {HARD_HAZARD_THRESHOLD} (hard threshold)",
        f"distance ≤ {max_distance_km} km",
        "hard feasibility constraints passed",
        "minimize: weighted distance + infrastructure deficit",
    ]

    return OptimizationOutput(
        status=result_status,
        total_demand=demand,
        total_allocated=total_allocated,
        unallocated=unallocated,
        allocations=allocations,
        objective_value=obj_val,
        constraints_applied=constraints,
        solver_note=(
            f"Solved with OR-Tools CP-SAT. Status: {result_status}. "
            f"Objective value: {obj_val:.0f}. "
            f"{len(feasible)} feasible sites evaluated."
        ),
        data_status=data_status,
    )


def _run_greedy(
    demand: int,
    sites: List[SiteInput],
    max_distance_km: float,
    data_status: str,
    solver_note: str = "Greedy allocation",
) -> OptimizationOutput:
    """Greedy fallback: allocate to highest-suitability sites first."""
    feasible = [
        s for s in sites
        if s.hard_constraints_passed
        and s.distance_km <= max_distance_km
        and (100 - s.safety_score) <= HARD_HAZARD_THRESHOLD
    ]

    if not feasible:
        return OptimizationOutput(
            status="INFEASIBLE",
            total_demand=demand,
            total_allocated=0,
            unallocated=demand,
            allocations=[],
            objective_value=0,
            constraints_applied=["No feasible sites"],
            solver_note="No technically feasible candidate sites available.",
            data_status=data_status,
        )

    # Sort: closest first (minimize distance), then by suitability
    ranked = sorted(feasible, key=lambda s: (s.distance_km, -s.suitability_score))

    remaining = demand
    allocations = []
    obj_val = 0.0

    for site in ranked:
        if remaining <= 0:
            break
        alloc = min(remaining, site.c_safe)
        util = round((alloc / site.c_safe) * 100)
        surplus = site.c_safe - alloc
        allocations.append(AllocationOutput(
            site_id=site.id,
            site_name=site.name,
            allocated_population=alloc,
            distance_km=site.distance_km,
            utilization_pct=util,
            surplus_after=surplus,
        ))
        obj_val += site.distance_km * alloc
        remaining -= alloc

    total_allocated = demand - remaining
    status = "FEASIBLE" if remaining == 0 else "PARTIAL"

    return OptimizationOutput(
        status=status,
        total_demand=demand,
        total_allocated=total_allocated,
        unallocated=remaining,
        allocations=allocations,
        objective_value=obj_val,
        constraints_applied=[
            "population ≤ c_safe per site",
            f"distance ≤ {max_distance_km} km",
            "hard feasibility constraints passed",
        ],
        solver_note=solver_note,
        data_status=data_status,
    )


def build_sites_from_demo() -> List[SiteInput]:
    """Build SiteInput list from demo seed data for testing."""
    return [
        SiteInput(id="site-c", name="Munnar Town Periphery — Site C",
                  c_safe=1800, distance_km=2.1, suitability_score=68,
                  safety_score=79, infrastructure_score=88, hard_constraints_passed=True),
        SiteInput(id="site-a", name="Devikulam Plateau — Site A",
                  c_safe=3200, distance_km=4.2, suitability_score=82,
                  safety_score=88, infrastructure_score=79, hard_constraints_passed=True),
        SiteInput(id="site-b", name="Pallivasal Flatland — Site B",
                  c_safe=2100, distance_km=7.8, suitability_score=74,
                  safety_score=91, infrastructure_score=65, hard_constraints_passed=True),
    ]
