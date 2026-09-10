# Implementation Plan — Dynamic Data + Live Routing (+ Engines + Backend Synthesis + Frontend Wiring)

Date: 2026-09-10
Plan of record for executing `docs/superpowers/specs/2026-09-10-dynamic-data-live-routing-design.md`
(user-approved design; includes the two amendments: GraphHopper explicitly optional/experimental,
and mandatory safe-zone capacity constraints with an explicit capacity gap / unallocated demand).

## Goal

Make every remaining static/demo panel dynamic, fed by real (collected/live) data — with a visible,
labelled architecture:

- The map shows **danger zones** (evacuate, driven by live risk factors + active hazard geometry)
  and the **safest zone** for the current disaster, with **live road routes** drawn on the map.
- Routing runs on real local engines from OpenStreetMap data: **OSRM** (fast, primary),
  **Valhalla** (advanced, risk-aware, isochrones), **GraphHopper** (optional/experimental only).
  "MapCN" is our existing MapLibre/MapContainer renderer — no new map library.
- Relocation visualizes safe zones + routes on the map.
- Nothing is silently demo; every block carries provenance (live / sim / demo_fallback) as specified.

## Architecture

```
browser (Vite/TS)                     FastAPI (/api/v1)                     Docker (deploy/engines)
────────────────────                  ─────────────────────                 ─────────────────────
Pages wire new client methods ──▶    evacuation/overview      ──▶ hazards, relocation_service,
Overview · RiskIntelligence           priorities                risk_service, routing_service,
Priorities · Reports                  reports/summary            hazard_aware_routing, optimizer    ──▶ PostgreSQL (risk_scores,
ScenarioAnalysis                      scenarios/run (live-seed)  engine status reachable/ready              safe_zone_candidates, ...)
MapContainer(maplibre) ◀── GeoJSON ──▶ engines?region=             │
                                      ─┐                          └─▶ OSRM :5000  (primary)
                                        └─ policy:                 ▶ Valhalla :8002 (advanced)
            ROUTE_STANDARD PRIMARY=osrm  FALLBACK=valhalla         ▶ GraphHopper :8989 (optional)
            ROUTE_ADVANCED PRIMARY=valhalla FALLBACK=none
            ROUTE_MATRIX  PRIMARY=osrm  FALLBACK=valhalla
            OPTIMIZATION SOLVER=ortools (greedy fallback)
```

New persisted data lives in **named Docker volumes** under `deploy/engines/` (PBF + OSRM extract +
Valhalla tiles + GH graph cache) so engine restarts never rebuild graphs.

## Tech stack

- Backend: FastAPI + asyncio httpx, SQLAlchemy/asyncpg (PostGIS on Render), OR-Tools CP-SAT (greedy
  fallback), pytest/unittest discover.
- Engines: `osrm/osrm-backend` :5000, `ghcr.io/gis-ops/docker-valhalla` :8002,
  `ghcr.io/gis-ops/docker-graphhopper` (pinned) :8989; Kerala extract from Geofabrik.
- Frontend: React + Vite + TypeScript, maplibre-gl via MapContainer, Playwright e2e.
- Data: OpenStreetMap (Mali/France), Geofabrik PBF, live weather/hazard tables in Render PostGIS.

## Global constraints (from the approved spec)

1. **Never fake LIVE.** Any computed number must be either real (observed or derived from live data)
   or explicitly labelled (SIMULATED / DEMO / RECOMMENDATION). Demo fallbacks are used only when the
   real source is unreachable, and are always labelled.
2. **Readiness is real.** An engine is `ready` only after a real routing request succeeds against a
   real Kerala dataset. Container up ≠ ready.
3. **Fallback must be visible.** When the standard engine is not ready, the route may come from the
   fallback engine, but the response MUST report which engine actually served.
4. **Capacity is a hard constraint.** Allocation may never exceed a safe zone's safe capacity; any
   excess is reported as an explicit **capacity gap / unallocated demand**, never silently dropped.
5. **GeoJSON first.** Hazard polygons, danger zones, safe zones, affected areas and routes are
   delivered as GeoJSON and rendered directly on MapLibre — no client-side geometry invention.
6. **No invented values.** Every endpoint reuses the existing risk/hazard/relocation/routing services;
   no new fake baselines are introduced anywhere.
7. **Preserve UI & architecture.** This phase changes what feeds each page and adds map layers; it
   does not redesign screens or replace APIs that already work.
8. **Push target is GitHub `origin`/main only.**

## File structure (new / modified)

New:
- `deploy/engines/docker-compose.yml` — OSRM, Valhalla, GraphHopper services + volumes + ports
- `deploy/engines/up.ps1` — launcher: pull images, download PBF if absent, start stack
- `deploy/engines/smoke.py` — per-engine reachable/ready check (real requests), used by CI + humans
- `backend/app/services/evacuation_service.py` — overview assembly service
- `backend/app/api/v1/evacuation.py` — `GET /api/v1/evacuation/overview`
- `backend/app/api/v1/reports.py` — `GET /api/v1/reports/summary`
- `backend/tests/test_evacuation.py`, `backend/tests/test_reports.py`,
  `backend/tests/test_engines_status.py`, `backend/tests/test_priorities.py`
- `frontend/e2e/evacuation-overview.spec.ts`, `frontend/e2e/priorities.spec.ts`,
  `frontend/e2e/reports.spec.ts`

Modified:
- `backend/app/services/multi_engine_routing.py` — `engines_status` reachable/ready split; OSRM probe
  fix (`/health` → real `/route`); GH `experimental` flag; policy helpers
- `backend/app/services/optimizer.py` — add `total_capacity`, `capacity_gap` to `OptimizationOutput`
  + both solvers
- `backend/app/services/relocation_service.py` — surface optimizer capacity gap in plan outputs;
  candidate-site → `SiteInput` helper for live demand
- `backend/app/api/v1/risk.py` — `risk_priorities` live-first ranking via new
  `risk_service.district_priorities`
- `backend/app/services/risk_service.py` — add `district_priorities` (live risk_scores ledger with
  DEMO fallback)
- `backend/app/api/v1/scenarios.py` — live-seed scenario inputs, remove hardcoded
  base_risk/base_demand/total_capacity; keep SIMULATED labelling
- `backend/app/main.py` — register evacuation + reports routers
- `backend/app/core/config.py` — engine URL settings (default localhost for kerala)
- `frontend/src/types/index.ts` — Evacuation types, engine status type updates
- `frontend/src/api/client.ts` — `getEvacuationOverview`, `getRiskPriorities` (exists), `getReportSummary`
- `frontend/src/pages/Overview.tsx` — wire evacuation overview + danger/hazard/safe-zone/route layers
- `frontend/src/pages/RiskIntelligence.tsx` — safe-zone + route + engine runner
- `frontend/src/pages/Priorities.tsx` — API data with DEMO fallback labels
- `frontend/src/pages/Reports.tsx` — API summary per section, keep SectionLabel
- `frontend/src/pages/ScenarioAnalysis.tsx` — live-seeded defaults + SIMULATED banner (already present)

---

## Task A1 — Docker Compose: engine images + persistent volumes

> Scope: `deploy/engines/`. One commit.

Files:
- `deploy/engines/docker-compose.yml`
- `deploy/engines/.env.example`
- `deploy/engines/up.ps1`

Interfaces (verified 2026-09-10):
- OSRM: image `osrm/osrm-backend`, health never at `/health` — readiness = `GET /route/v1/driving/...?overview=false` → 200 + routes.
- Valhalla: `ghcr.io/gis-ops/docker-valhalla`; readiness = `GET /status` → `{"status":"ok"}` then small `POST /route` → 200.
- GraphHopper: `ghcr.io/gis-ops/docker-graphhopper` (pin a release tag, e.g. `9.0`, verified earlier; fall back to
  `israelhikingmap/graphhopper` which tags through 11.0). Readiness = `GET /info` → 200, then `GET /route?point=...&profile=car` → `paths`.
- PBF source: `https://download.geofabrik.de/asia/india/kerala-latest.osm.pbf` (~50 MB).

Steps:
1. Write `docker-compose.yml`:
   - `osrm`: image, container_name `sentinel-osrm`, ports `5000:5000`, volumes:
     `- ./data/osrm:/data` (host bind under repo — persistent), command
     `osrm-extract -p /opt/car.lua /data/kerala-latest.osm.pbf && osrm-partition /data/kerala-latest.osrm && osrm-customize /data/kerala-latest.osrm && osrm-routed --algorithm mld --max-table-size 8000 /data/kerala-latest.osrm`.
     Extract/partition/customize steps should run only when the osrm file is absent (entrypoint guard script) —
     simplest reliable approach: separate one-shot `osrm-build` service run with
     `docker compose run --rm osrm-build`, then the `osrm` service runs only `osrm-routed`.
   - `valhalla`: image `ghcr.io/gis-ops/docker-valhalla`, container_name `sentinel-valhalla`, ports `8002:8002`,
     env `tile_urls=https://download.geofabrik.de/asia/india/kerala-latest.osm.pbf`, `use_tiles_ignore_pbf=true`,
     `force_rebuild=false`, `build_elevation=false`, `build_admins=false`, `build_time_zones=false`, `build_tar=false`,
     volume `./data/valhalla:/custom_files`.
   - `graphhopper`: image `ghcr.io/gis-ops/docker-graphhopper:9.0` (or pinned community tag), container_name
     `sentinel-graphhopper`, ports `8989:8989`, command `--url https://download.geofabrik.de/asia/india/kerala-latest.osm.pbf --graph-cache-dir /data/gh-cache --import`,
     env via `JAVA_OPTS="-Xmx2g"`, volume `./data/gh-cache:/data/gh-cache` plus `./data/gh-cache:/graph-cache`.
   - `profiles: { }` disabled to keep bbox agreement with the app default.
2. Write `.env.example` with `KERALA_PBF_URL` override.
3. Write `up.ps1`:
   - `if (-not (Test-Path data/osrm/kerala-latest.osrm))` → download PBF once (Invoke-WebRequest) into
     `data/osrm/`, run `docker compose run --rm osrm-build`.
   - `docker compose up -d` (osrm-routed, valhalla, graphhopper).
   - Print `docker compose ps`.
   - **DoS/aval note:** run PowerShell and docker in separate invocations in the harness (Start-Process + probe
     in one bash call gets killed).
4. Run `deploy/engines/up.ps1`. First build may take 10–20 min (download + extract).
5. Gate: `docker compose ps` shows 3 containers. **Do not call this ready yet.**

> Run + verify + commit `feat(engines): docker compose for OSRM/Valhalla/GraphHopper (kerala)`.

---

## Task A2 — smoke.py: reachable vs ready, real requests

> Scope: `deploy/engines/smoke.py`. One commit.

Files:
- `deploy/engines/smoke.py`

Interfaces:
- OSRM: `GET http://localhost:5000/route/v1/driving/76.93,10.01;77.16,10.03?overview=false` → 200, JSON `routes`.
- Valhalla: `GET http://127.0.0.1:8002/status` → `{"status":"ok"}`; then `POST /route` body
  `{"locations":[{"lat":10.01,"lon":76.93},{"lat":10.03,"lon":77.16}],"costing":"auto"}` → 200, JSON `trip`.
- GH: `GET http://localhost:8989/info` → 200; then `GET /route?point=10.01,76.93&point=10.03,77.16&profile=car` → 200, JSON `paths`.

Steps:
1. `smoke.py` probes in order OSRM → Valhalla → GH. For each: first a cheap probe (reachable), then a real
   routing request (ready). Output table: `reachable` / `ready` / `latency_ms` / `detail`. Non-zero exit if any
   configured engine is not `ready` (flag `--require=osrm,valhalla,graphhopper` controllable for CI; default requires OSRM+Valhalla,
   GH reported but not required).
2. Run `backend/.venv311/Scripts/python.exe deploy/engines/smoke.py`.
3. Gate: OSRM and Valhalla `ready=true`, GH `ready=true` (built this session) OR GH shown `reachable`+`ready` differences honestly.

> Run + verify + commit `feat(engines): smoke.py reachable/ready real-request checks`.

---

## Task B1 — engines_status: reachable vs ready, policy helpers

> Scope: backend engine model. One commit.

Files:
- `backend/app/services/multi_engine_routing.py`

Interfaces (exact current shape, verified):
- `engines_status(region_key: str = "kerala") -> dict` at `multi_engine_routing.py:433`. Currently probes
  OSRM `/health` (which OSRM does NOT expose → always `ok=False` when configured) and returns
  `{region, engines: {graphhopper, osrm, valhalla: {tier, ok, detail, url}}, note, checked_at}`.

Steps:
1. Replace the OSRM probe with the real route request (see A2) so `ok` can actually become true when OSRM is up.
2. Add per-engine `reachable` (probe HTTP 200) and `ready` (real Kerala route 200 + valid payload shape).
3. Keep `ok` = `ready` (backward compatible). Add `experimental: true` to `graphhopper` and
   `role` (`primary` / `advanced` / `optional`) per the approved policy.
4. Add `policy` block to the response:
   ```python
   "policy": {
       "ROUTE_STANDARD": "osrm -> valhalla",
       "ROUTE_ADVANCED": "valhalla -> none",
       "ROUTE_MATRIX": "osrm -> valhalla",
       "OPTIMIZATION": "ortools (greedy fallback)",
   }
   ```
5. Add helper `pick_engine(region_key, policy_key) -> str` returning the first `ready` engine in the policy
   chain (or `None` when none ready).
6. Tests (`backend/tests/test_engines_status.py`): with URLs pointing at unreachable hosts, `reachable=False`,
   `ready=False`, `ok=False`, `detail` contains "Not configured"/"Unreachable"; `policy` present. Mock httpx
   (monkeypatch `engines_status` internals) for the `ready=True` path.
7. Gate: `python -m unittest discover -s tests -p "test_*.py"` from `backend/` — full suite stays green, new
   tests pass.

> Run + verify + commit `feat(routing): engines_status reachable/ready + policy pick`.

---

## Task B2 — evacuation overview endpoint (backend synthesis)

> Scope: new read-only synthesis endpoint reusing existing services. One commit.

Files:
- `backend/app/services/evacuation_service.py`
- `backend/app/api/v1/evacuation.py`
- `backend/app/main.py` (register router)
- `backend/tests/test_evacuation.py`

Interfaces (verified):
- `hazard_service.current_hazards(db, region=None)` → dict with `events` (id, type, severity, geometry GeoJSON, ...).
- `relocation_service.calculate_demand(session, district_id)` → `{data_status, total_demand, demand_habitations, habitations:[{habitation_id,name,population,current_score,relocation_demand}], note}`.
- `relocation_service.get_safe_zone_sites(session, district_id)` → list of rows `{id,name,source,geom,suitability_score,safety_score,estimated_capacity,constraint_pass,constraint_evidence,lon,lat}` or `None` when DB down.
- `safe_zone_service.get_safe_zones(db, district_id, refresh=False)` → FeatureCollection (map-ready).
- `hazard_aware_routing.hazard_aware_route(session, habitation_id, site_id, engine="graphhopper", avoid_hazards=True)` → OK payload with `hazard_analysis` (route_risk_score, risk_label), or UNAVAILABLE payload, or `None`.
- `optimizer.run_optimization(demand, sites, max_distance_km, data_status)` → `OptimizationOutput`.

Steps:
1. `evacuation_service.build_overview(session, region, disaster_type=None)`:
   - Resolve district from region (`idukki` default). `disaster_type` optional; when absent, take the dominant
     active hazard type from `current_hazards`; when no hazard present, `disaster_type=None` and the
     recommendation reverts to normal-conditions guidance (never invent a disaster).
   - **Hazards block**: `current_hazards(db, region)` events + their GeoJSON polygons (danger zones). Every
     event carries `data_status` from the source. When empty, `events=[]`, `danger_zones=[]`,
     `status="NO_ACTIVE_EVENT"`, labelled live.
   - **Affected habitations**: `calculate_demand(session, district_id)` → demand_habitations with
     `relocation_demand>0` as "affected" list, plus total population at risk = sum of populations of affected.
   - **Demand / capacity / gap**: total demand = `total_demand`; capacity = sum of `estimated_capacity` over
     `get_safe_zone_sites`; `capacity_gap = max(0, demand - capacity)`; `unallocated` = optimizer field.
   - **Safe zones (GeoJSON)**: reuse `safe_zone_service.get_safe_zones` FeatureCollection; each feature adds
     `properties.distance_km` (via spatial/OSRM when available, else labeled DEMO distance) and `capacity`.
   - **Recommended safe zone + route**: pick best site by (suitability_score × safety_score /100) then
     `hazard_aware_route(session, habitation_id=worst_affected, site_id=selected_site, engine=policy.pick_engine(ROUTE_ADVANCED))`.
     Route GeoJSON LineString, distance_km, duration_min, route_risk_score, risk_label, engine that served,
     `served_by` + `fallback_used`. If route unavailable → block carries `status="UNAVAILABLE"`, reason.
   - **Alternatives**: `route_alternatives(session, habitation_id, site_id, engine)` (or next 3 best sites),
     cap 3.
   - **Evacuation status**: severity summary from affected/population/gap + hazard severity.
   - **Provenance per block**: live / demo_fallback / simulated with region, generated_at.
2. `evacuation.py`:
   ```python
   @router.get("/overview")
   async def evacuation_overview(
       region: str = Query("idukki"),
       disaster_type: Optional[str] = Query(None),
       db: AsyncSession = Depends(get_db),
   ):
       return await evacuation_service.build_overview(db, region, disaster_type=disaster_type)
   ```
3. Register `include_router(evacuation.router, prefix="/api/v1/evacuation", tags=["evacuation"])`.
4. `backend/tests/test_evacuation.py`: mock `current_hazards` → known event; mock `calculate_demand`; mock
   `get_safe_zone_sites`; assert blocks present, GeoJSON shapes, `capacity_gap` math, provenance keys. Test
   DB-down → every block labelled `demo_fallback` and endpoint still 200.
5. Gate: full suite green; manual probe `.venv311/Scripts/python.exe -c "import httpx; print(httpx.get('http://127.0.0.1:8000/api/v1/evacuation/overview?region=idukki').status_code)"` (harness quirk: run server and probe in **separate** invocations).

> Run + verify + commit `feat(evacuation): read-only overview synthesis endpoint`.

---

## Task B3 — priorities: live-first ranking (real scores, never invented)

> Scope: risk API. One commit.

Files:
- `backend/app/services/risk_service.py` (add `district_priorities`)
- `backend/app/api/v1/risk.py` (`risk_priorities` uses it)
- `backend/tests/test_priorities.py`

Interfaces:
- `risk_priorities(district_id)` at `risk.py:58` — currently static `RPI_BY_HABITATION` demo ranking, always `DEMO`.
- `calculate_demand` already joins latest `risk_scores.current_score`.

Steps:
1. `risk_service.district_priorities(session, district_id)`:
   - Query latest `risk_scores.current_score` per habitation (same LATERAL pattern as `calculate_demand`).
   - When DB/data available: rank habitations desc by `current_score`, return `data_status="DERIVED"`,
     `weights` = the same documented RPI weights, `note` explains ranking uses live scores with the same
     thresholds as the risk engine. Never re-invent a score — reuse `current_score`.
   - On DB error: fall back to the current demo ranking with `data_status="DEMO"` and `reason` (never fake LIVE).
2. `risk_priorities` → `return await risk_service.district_priorities(db, district_id=district_id)`.
3. Tests: DB-down → DEMO + reason; DB rows present → DERIVED + ordering.assertSequenceEqual by current_score desc.
4. Gate: full suite green.

> Run + verify + commit `feat(risk): live-first district priorities (never invented) `.

---

## Task B4 — reports summary endpoint

> Scope: read-only report synthesis. One commit.

Files:
- `backend/app/api/v1/reports.py`
- `backend/app/main.py` (register)
- `backend/tests/test_reports.py`

Interfaces:
- Existing: `risk_intelligence`, `risk_current`, `risk_drivers`, `decision_trace`, `hazard detail`,
  `candidate_sites`, `calculate_demand`, `site_capacity`, `optimization_result`, relocation plan getters,
  routing engines + hazard-aware route.

Steps:
1. `GET /api/v1/reports/summary?habitation_id=munnar-central&plan_id=<optional>` assembles, from existing
   services (no new data invented):
   - H (habitation): detail from `get_habitation_detail`, risk current + timeline + drivers.
   - H (demand/allocation): relocation demand, candidate sites with capacity, optimization result
     (feasibility + allocations + `capacity_gap`/`unallocated`), plan status if `plan_id` given.
   - H (route): hazard-aware route (primary OSRM → fallback Valhalla) with `served_by`.
   - H (hazard context): current active events near habitation.
   Each section carries its own `SectionLabel`-compatible `data_type`/`data_status` and provenance. Response
   shape mirrors the existing `Reports.tsx` section structure (district / risk / habitation / demand /
   capacity / optimization / scenario / routing) so the frontend swap is surgical.
2. Register router.
3. Tests: sections present + provenance keys; DB-down yields demo_fallback labelled sections, still 200.
4. Gate: full suite green.

> Run + verify + commit `feat(reports): summary synthesis endpoint`.

---

## Task B5 — scenarios: live seeding, no invented baselines

> Scope: `backend/app/api/v1/scenarios.py`. One commit.

Interfaces (verified):
- `run_scenario` currently hardcodes `base_risk=94`, `base_demand=4210`, `total_capacity=7100`,
  `hazard_component=35.2`, and returns SIMULATED-labelled results. `ScenarioRequest` has
  `habitation_id`, `label`, `rainfall_multiplier`, `population_change_pct`, `capacity_reduction_pct`,
  `road_disruption`.

Steps:
1. Seed inputs from live sources when available:
   - `base_demand` ← `calculate_demand(session, district)` `total_demand` (live risk-derived).
   - `base_risk` ← latest `risk_scores.current_score` for `habitation_id` (via `get_current_risk` service).
   - `total_capacity` ← sum of `get_safe_zone_sites` `estimated_capacity` (live candidates).
   - `hazard_component` ← derived from active hazard severity count via `current_hazards` (live basis) — if
     none active, `0` with note.
   When any live source is unreachable, keep the scenario runnable but mark those inputs
   `{"source":"demo_fallback","value":N,"reason":"..."}` and the response banner still `SIMULATED SCENARIO`.
2. Apply the user multipliers on top of the (live or declared-fallback) seeds; label output per the approved
   provenance contract; never present seeds as current conditions.
3. Tests: with live db present → seeds reflect demand/capacity; DB down → demo_fallback seeds + reasons;
   response `data_type == "SIMULATED"` in both cases.
4. Gate: full suite green.

> Run + verify + commit `feat(scenarios): live-seeded inputs, no invented baselines`.

---

## Task B6 — optimizer: capacity total + explicit capacity gap

> Scope: `backend/app/services/optimizer.py` + plan surface. One commit.

Interfaces (verified):
- `OptimizationOutput` (optimizer.py:47) has `status,total_demand,total_allocated,unallocated,allocations,objective_value,constraints_applied,solver_note,data_type,data_status` — **no total_capacity / capacity_gap**.
- Both `_run_cpsat` and `_run_greedy` already respect per-site `c_safe` ceilings and compute `unallocated`.

Steps:
1. Add `total_capacity: int = 0` and `capacity_gap: int = 0` to `OptimizationOutput` (default 0 keeps any
   other producers/tests compiling).
2. In both solvers: `total_capacity = sum(s.c_safe for s in feasible)`,
   `capacity_gap = max(0, demand - total_capacity)`. Set fields. When INFEASIBLE (no feasible sites),
   `total_capacity=0`, `capacity_gap=demand`.
3. In `create_plan` (relocation_service.py), include `total_capacity` / `capacity_gap` in the persisted and
   returned plan payload, alongside existing `unallocated`.
4. Tests: demand > capacity → `capacity_gap == demand - capacity`, `status=="PARTIAL"` (greedy) or
   FEASIBLE-with-empty-sites INFEASIBLE (cpsat); demand ≤ capacity → `capacity_gap==0`.
5. Gate: full suite green.

> Run + verify + commit `feat(optimizer): total_capacity + explicit capacity_gap surfacing`.

---

## Task C1 — frontend types + client methods

> Scope: `frontend/src/types/index.ts`, `frontend/src/api/client.ts`. One commit.

New types:
```ts
interface EngineProbe { tier: string; ok: boolean; reachable: boolean; ready: boolean;
  experimental?: boolean; role?: string; detail: string; url: string | null }
interface EnginesStatus { region: string; engines: Record<string, EngineProbe>; policy: Record<string, string>; checked_at: string }
interface EvacuationOverview { region: string; disaster_type: string | null; generated_at: string;
  hazards: {...}; danger_zones: GeoJSON; affected: {...}; demand: { total: number; capacity: number; gap: number; unallocated: number };
  safe_zones: FeatureCollection; recommendation: {...}; routes: [...] ; provenance: Record<string, any> }
interface ReportSummary { sections: {...} ; provenance: Record<string, any> }
```
New client methods (mirror existing style):
```ts
getEvacuationOverview: (region = 'idukki', disasterType?: string) =>
  fetchJSON(`/api/v1/evacuation/overview?region=${region}${disasterType ? `&disaster_type=${encodeURIComponent(disasterType)}` : ''}`),
getReportSummary: (habitationId: string, planId?: number) =>
  fetchJSON(`/api/v1/reports/summary?habitation_id=${encodeURIComponent(habitationId)}${planId ? `&plan_id=${planId}` : ''}`),
```
Update `getRoutingEngines` return type to `EnginesStatus`; update engine-status consumers to prefer `ready`.

Steps: 1) types; 2) client methods; 3) `tsc --noEmit` + `eslint --max-warnings 0` green.

> Run + verify + commit `feat(web): evacuation/report client methods + engine status types`.

---

## Task C2 — Overview: live danger zones + safe zone + route on the map

> Scope: `frontend/src/pages/Overview.tsx`. One commit.

Current state (verified): Overview fetches `api.getDistrictOverview('idukki')` into `this.overview`
(`source='api'` or `'demo_fallback'`); `MapContainer` at line 441 gets `habitations={DEMO_HABITATIONS}`
(hardcoded, not live) + `showHazardLayer`; legend map at 449; stats from `getOverviewStats()`.
`MapContainer` already supports `hazardGeoJSON`, `showHazardLayer`, `safeZonesGeoJSON`,
`showSafeZonesLayer`, `routeFeature`, `routeLabel`.

Steps:
1. Add an overview state loader `loadEvacuation()` calling `api.getEvacuationOverview('idukki')`; on failure
   keep current behaviour (DEMO) but set a visible badge `Overview data: demo fallback (reason)`.
2. Replace `habitations={DEMO_HABITATIONS}` with live habitations from
   `api.getHabitationsGeoJSON('idukki')` when available (fallback → DEMO_HABITATIONS labelled).
3. Wire map layers:
   - `hazardGeoJSON` = overview danger_zone polygons; keep `showHazardLayer` toggle (rename label to
     "Danger zones (live hazard geometry)").
   - `safeZonesGeoJSON` = overview.safe_zones; `showSafeZonesLayer` toggle.
   - `routeFeature`/`routeLabel` = recommendation route GeoJSON once loaded (trigger via "Evacuate now" button);
   include engine served + risk badge in the overlay label.
4. Add a status strip under the map: demand, capacity, capacity_gap (red when >0), recommended safe zone,
   route risk label, provenance chip (live / demo_fallback / SIMULATED).
5. Gate: `npm run build` from `frontend/`; e2e smoke via Playwright asserts map draws danger-zone text overlay
   when hazards present (or demo fallback label when absent).

> Run + verify + commit `feat(overview): live danger zones + safe zone + route layers`.

---

## Task C3 — RiskIntelligence / Decision: evacuation runner + engine dots

> Scope: `frontend/src/pages/RiskIntelligence.tsx`, `frontend/src/pages/DecisionIntelligence.tsx` (light).

Current state (verified): RiskIntelligence already wires `hazardGeoJSON`+`showHazardLayer` (~307-308) and
relocation runner with safe-zone tiles + route; DecisionIntelligence has the engine selector. Relocation
already toggles OSM + hazard-avoidance.

Steps:
1. Pass `safeZonesGeoJSON` + `showSafeZonesLayer` + `routeFeature`/`routeLabel` from the evacuation overview
   into RiskIntelligence's MapContainer (same props block as Overview in C2, no new map code).
2. Replace the fixed engine in the route runner with `pick_engine` from live `getRoutingEngines('kerala')`
   (prefer `ready` engines: osrm → valhalla); show served-by line after response.
3. Update engine selector chips in DecisionIntelligence: green only when `ready`; grey `reachable` triangle
   (warn "reachable but not ready"); GH labelled "experimental".
4. Gate: build + tsc + eslint green.

> Run + verify + commit `feat(risk): safe-zone/route layers + ready-based engine selection`.

---

## Task C4 — Priorities page: API data with DEMO fallback

> Scope: `frontend/src/pages/Priorities.tsx`. One commit.

Current state (verified): uses `DEMO_DISTRICT_OVERVIEW.district` + `DEMO_HABITATIONS`, enriches with static
RPI data, no API call, filter state at line 40.

Steps:
1. Fetch `api.getRiskPriorities('idukki')` (already exists in client). Shape: `{habitations: [{id, rpi_score, ...}]}`.
2. Enrich each row with existing UI mapping (name/priority via existing RISK labels); keep the exact current
   table layout. Add a top badge `data_status` chip: "Live risk scores" vs "DEMO fallback (reason)".
3. On API failure → existing DEMO path (label it).
4. Gate: build + e2e `priorities.spec.ts` asserts a rendered row and the data-status chip text.

> Run + verify + commit `feat(priorities): live risk priorities with labelled fallback`.

---

## Task C5 — Reports page: backend summary per section

> Scope: `frontend/src/pages/Reports.tsx`. One commit.

Current state (verified): every section reads DEMO constants (`DEMO_DISTRICT_OVERVIEW`, `DEMO_MUNNAR_CENTRAL`,
`DEMO_CANDIDATE_SITES`, `DEMO_OPTIMIZATION_RESULT`, etc.); `SectionLabel` component exists; scenario banner
labels SIMULATED.

Steps:
1. Add a `load()` that calls `api.getReportSummary('munnar-central')`; store + pass to each section component.
2. Section by section (district / risk / habitation / demand / capacity / optimization / scenario / routing):
   swap the DEMO constant for the API field when present; keep the component and JSX identical otherwise; set
   `SectionLabel type` from the section's `data_type` (OBSERVED/DERIVED/ESTIMATED/SIMULATED/RECOMMENDATION) and
   append provenance when `data_status !== 'live'`.
3. If the API returns a demo_fallback block, keep the DEMO constant as display data but label it.
4. Gate: build + e2e `reports.spec.ts` asserts each section renders + the section nav unchanged (2/2 pass).

> Run + verify + commit `feat(reports): API-backed report sections with provenance labels`.

---

## Task C6 — ScenarioAnalysis: live-seeded defaults

> Scope: `frontend/src/pages/ScenarioAnalysis.tsx`. One commit.

Current state (verified): params default `DEMO_SCENARIO_PRESETS[0]` (line ~146); `api.runScenario` at change
(~156); SIMULATED banner already present (~332). Backend now live-seeds (Task B5).

Steps:
1. On mount, fetch `api.getEvacuationOverview('idukki')` to pre-populate the input controls (disaster type,
   base demand, capacity) as **read-only reference values labelled "live baseline"**, still applying the user's
   multipliers; never hardcode `4210`/`7100` in this page.
2. Keep the SIMULATED SCENARIO banner. Display which inputs were live-seeded vs demo fallback (from B5
   provenance).
3. Gate: build + existing e2e still passes.

> Run + verify + commit `feat(scenarios): live-seeded inputs + sample provenance on page`.

---

## Task D1 — end-to-end verification + delivery

> Scope: full suite + documented honesty. One commit.

Steps:
1. Backend: full `unittest` discover green (including new test files).
2. Frontend: `tsc --noEmit`, `eslint --max-warnings 0`, `vite build`.
3. Live engines: run `deploy/engines/smoke.py`; confirm OSRM+Valhalla `ready`, GH `ready` (or honestly
   `reachable`/`ready` state). Then manual probe of `/api/v1/evacuation/overview` with engines live.
4. Playwright: `frontend/e2e/evacuation-overview.spec.ts`, `priorities.spec.ts`, `reports.spec.ts` pass;
   re-run `osm-layers.spec.ts` (regression). Screenshots to `.artifacts/` (text/DOM assertions are the source
   of truth — agent cannot view images).
5. Update `DELIVERY_REPORT.md` (root) with Phase 7 rows: WORKING (engines ready + evacuation overview live),
   PARTIALLY-WORKING (any labelled-fallback panels), BLOCKED (if any).
6. Push `origin` main only.

> Verify → report → `feat(phase7): dynamic data + live routing …` commit pushed.

---

## Post-implementation verification (must all pass before claiming completion)

- [ ] `backend/.venv311/Scripts/python.exe -m unittest discover -s backend/tests -p "test_*.py"` — green.
- [ ] `frontend`: `npx tsc --noEmit`, `npx eslint . --max-warnings 0`, `npm run build` — green.
- [ ] `deploy/engines/smoke.py` — OSRM + Valhalla `ready=true` (GH optional).
- [ ] `GET /api/v1/evacuation/overview?region=idukki` (engines live) — blocks populated, `capacity_gap`
      explicit, provenance per block.
- [ ] playwright specs: osm-layers (regression), evacuation-overview, priorities, reports — pass.
- [ ] Honesty canary (observation 0007): grep the diff for any new hardcoded risk/demand/capacity constants —
      `base_risk`, `4210`, `7100` absent from all live paths (scenario seeds labelled).
- [ ] Both engines that served are reported (`served_by`); no silent cross-engine swap.
- [ ] Observation log updated (task-observer) at `C:/Users/User/skill-observations/observation-log/`.