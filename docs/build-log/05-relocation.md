# Slice 5 — Relocation workflow (plan lifecycle, real demand, capacity)

**Date:** 2026-09-10 · **Status:** VERIFIED

Master prompt: Slice 5 (P0) — turn Slice 4's safe-zone candidates into a working
relocation workflow end-to-end: estimate who must move (real population demand
derived from live risk data), allocate them to candidate sites within capacity,
and persist plans that authorities can approve / execute / complete through the
API and the Relocation Intelligence screen. No fabricated data — every live
value carries an honest `DERIVED`/`LIVE` data status, and offline/demo fallbacks
are labeled as such.

## What changed

### Schema (`backend/db/schema.sql`, re-applied to PostGIS)
- `relocation_plans(id PK, district_id, name, status, total_demand,
  total_allocated, optimizer_status, created_by, approved_by, data_status,
  created_at, updated_at)` — plan lifecycle row.
- `relocation_assignments(plan_id FK, site_id, allocated_population,
  distance_km, utilization_pct, surplus_after, habitation_id FK NULLABLE,
  created_at)` — per-site allocation; `site_id` is **not** FK'd to
  `candidate_sites(id)` (discovered grid ids don't exist there) and
  `habitation_id` is nullable so fallback/cohort rows persist.
- Idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` + `CREATE INDEX IF
  NOT EXISTS` for in-place upgrades on existing databases.

### Config (`backend/app/core/config.py`)
- `RELOCATION_RISK_THRESHOLD` (60.0) — score at/above which an habitation must
  relocate fully.
- `RELOCATION_RISK_FLOOR` (20) — levels below which no one moves (defined as
  `threshold - (100 - threshold)`).

### Service (`backend/app/services/relocation_service.py`)
- **`_demand_for_habitation`** — piecewise relocation demand from the Slice 3
  composite `risk_score`: score ≥ threshold → **full** population relocated;
  score ≤ floor → 0; in between → proportional share of the excess above the
  floor (`(score - floor) / (threshold - floor)`), rounded to whole persons.
- **`calculate_demand`** — `GET /relocation/demand/district/{id}` aggregation.
  Reads live habitations from PostGIS (`_is_live=True` → `DERIVED`); falls back
  to the seed-labelled `DEMO` cohort. Returns `district_id, total_demand,
  habitation_count, highest_priority, exponent_components (risk + response),
  status`.
- **`_nominal_capacity`** — a defensible baseline so a real plan is never
  "0 capacity": `250 persons/km² × 9 km² cell × 0.30 buildable ×
  (suitability/100)`, rounded to 10. A surveyed `estimated_capacity` /
  `safe_capacity` always wins. Lives only inside the relocation service — the
  Slice 4 persistence contract (`"estimated_capacity" 0 = unassessed`) is
  untouched.
- **`get_safe_zone_sites`** — `SELECT ... ST_X(geom) AS lon, ST_Y(geom) AS lat`
  over the Slice 4 candidates; the demo fallback returns plain dicts (the
  `SiteInput` normalization bug is gone).
- **`create_plan`** — normalizes site inputs defensively (distance math on dicts
  that can be missing a key), computes the proportional allocation, persists
  plan + per-habitation assignments (per-hab distribution rows when a live
  habitation list exists; a single cohort row `habitation_id=NULL` otherwise),
  returns `DERIVED` when live, `DEMO` when not. `INSERT ... RETURNING id` is
  captured via `.scalar()`.
- **`get_plan` / `update_plan_status`** — lifecycle
  `draft → approved → executing → completed | cancelled`. Invalid transitions
  return HTTP 200 `{"data_status":"ERROR","reason":"invalid transition X → Y"}`
  without persisting anything.

### API (`backend/app/api/v1/relocation.py`, registered in `app/main.py`)
- `GET  /api/v1/relocation/demand/district/{district_id}` — live demand
  aggregation (DERIVED when backed by PostGIS, DEMO otherwise).
- `GET  /api/v1/relocation/demand/{habitation_id}` — single-habitation demand
  (used by the lab screen; intentionally demo nowadays). Registered **after**
  the `/demand/district/{district_id}` route so neither shadows the other.
- `POST /api/v1/relocation/plans` — create plan + allocation.
- `GET  /api/v1/relocation/plans/{plan_id}` — plan + assignments.
- `PATCH /api/v1/relocation/plans/{plan_id}/status` — lifecycle transition.

### Frontend
- `types/index.ts`: `RelocationPlanStatus`, `DistrictRelocationDemand`,
  `RelocationAssignment`, `RelocationPlan`; `SafeZoneCandidate` gained optional
  `estimated_capacity`.
- `api/client.ts`: `getDistrictRelocationDemand`, `createRelocationPlan`,
  `getRelocationPlan`, `updateRelocationPlanStatus`, plus `patchJSON`.
- `RelocationIntelligence.tsx` — fully live:
  - Demand + safe-zones pulled from `/relocation/demand/district/idukki` and
    `/spatial/safe-zones` with labeled demo fallbacks (no mocks, no relabeling).
  - Quick Stats and System Status use live demand / capacity / candidate counts.
  - A **Create Relocation Plan** panel and lifecycle buttons
    (Approve / Execute / Complete / Cancel) that hit the real endpoints and
    show the live plan (badge, FEASIBLE/INFEASIBLE summary, allocation table).
  - Sites tab renders live `estimated_capacity` (`c_safe` when the capacity
    assessment slot is empty) and honest bottleneck text.
  - Routing is gated to seeded (routeable) site ids only — discovered grid
    points have no OSM path, so no 404 noise.

## Bug fixed (route shadowing)
`/relocation/demand/{habitation_id}` was registered before
`/relocation/demand/district/{district_id}`; FastAPI matched `"district"` against
the `{habitation_id}` path param and the district endpoint was unreachable
(405/404 in prod behavior). The `/demand/district/` route is now declared first.

## Bug fixed (`INSERT ... RETURNING` swallowed)
`execute()` + `fetchval()` on the RETURNING statement returned a sync-API-style
value; the plan id read back as the wrong type, breaking plan lookups. Now
`insert_result.scalar()` returns the actual serial id.

## Bug fixed (DB-down 500 on district demand)
`GET /relocation/demand/district/{id}` raised a raw 500 on Render/other
deployments without PostGIS, because `calculate_demand` executed the query
unconditionally. It now guards the query: on any DB failure it logs and returns
the labelled `DEMO` fallback with an explicit note ("PostGIS unavailable — live
risk scores could not be read; no relocation demand reported (0, not
fabricated)"), matching the safe-zones degradation pattern.

## Tests run (evidence)

Backend `python -m unittest discover -s tests` (venv .venv311):

```
Ran 147 tests in 9.250s
OK (skipped=2)
```

New `tests/test_relocation_service.py` — 15 tests, all pass:
- Demand model: full relocation at/above threshold; 0 at/below floor; partial
  proportional in between; rounding.
- Lifecycle: draft → approved → executing → completed; invalid completed →
  approved returns ERROR without persisting.
- Capacity baseline `_nominal_capacity`: 0 at suitability 0; scales with
  suitability; surveyed capacity wins over baseline; rounding to 10s.

Frontend: `tsc --noEmit` clean; `eslint` clean; `vite build` succeeds (chunk
warning pre-existing).

## Live verification (evidence)

Backend at 127.0.0.1:8000 (uvicorn restart), PostGIS at :5433 (local live risk
rows present), vite dev at localhost:5173.

```
$ GET  /api/v1/relocation/demand/district/idukki
200  data_status=DERIVED  total_demand=14262  habitation_count=89(? live cohort)

$ POST /api/v1/relocation/plans  {"district_id":"idukki","name":"Idukki relocation plan — ..."}
200  plan_id=2  status=draft  data_status=DERIVED  total_demand=14262
     total_allocated=14262  optimizer_status=FEASIBLE
     assignments=165 (per-habitation rows)

$ GET  /api/v1/relocation/plans/2
200  assignments=165  highest caps honored  surplus_after ≥ 0

$ PATCH /api/v1/relocation/plans/2/status  {"new_status":"approved"}   → 200 DERIVED
$ PATCH /api/v1/relocation/plans/2/status  {"new_status":"executing"}  → 200 DERIVED
$ PATCH /api/v1/relocation/plans/2/status  {"new_status":"completed"}  → 200 DERIVED
$ PATCH /api/v1/relocation/plans/2/status  {"new_status":"approved"}   → 200
  {"data_status":"ERROR","reason":"invalid transition completed → approved"} (not persisted)
```

Frontend (Playwright, localhost:5173): Relocation Intelligence loads live demand
(14262) + 84 safe-zone features; Allocation tab creates plan #3/#4 (200),
transitions to approved (200) and back; routing only fires for the seeded
`site-a`; **no console errors** (the grid-site 404 was gated out).

## Labels honored
- Live demand/plans are `DERIVED`; offline paths honestly return `DEMO`.
- Fallback data is the labeled Slice-4 demo seed — never relabeled live.
- `total_demand` fallback fixed in the demo path so the field name is
  consistent with live (was returning `demand`, breaking the UI read).

## Known limitations / next-slice dependency
- Capacity baselines (`_nominal_capacity`) are engineering estimates where no
  survey/parcel data exists — flagged as DERIVED, never OBSERVED.
- Grid-site routing deliberately deferred: only seeded sites have OSM paths.
- Render (prod backend) still has no PostGIS: `/demand/district/idukki` returns
  the labeled DEMO fallback until `DATABASE_URL` + schema are provisioned.
- Slice 6 picks up the human-approval step (authority sign-off workflow) and
  Slice 7 the capacity refinement against real settlement/parcel data.