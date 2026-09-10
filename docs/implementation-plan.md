# Sentinel AI — Product Implementation Plan (SIH PS 26191)

Authorized by: Master Implementation Prompt (P0/P1/P2 + vertical Slice 1-8).
Canonical build target: `D:\sentinel-ai` (user-confirmed; `C:\...\Downloads\sentinel-ai` is a stale copy).
Today's date: 2026-09-10. Repo at HEAD `4aed343` with 10 uncommitted audit fixes tracked separately.

## Ground rules (from master prompt + audit)

- Build **real, end-to-end** capability: real data → backend ingestion → PostGIS → domain/optimization/GIS/Routing → API → frontend → map → real result.
- Never silently label a fallback as the engine's real output. Demo fallback stays, visibly labeled DEMO / SIMULATED / FALLBACK; live results labeled OBSERVED / DERIVED / RECOMMENDATION per trust tiers.
- Do **not** delete or discard existing honest prototype work — it becomes the labeled fallback layer.
- Vertical slices build on each other. **Each slice: build → test → verify → report** (§48 template). Only declare a capability functional with verification evidence (tests pass / API live check / browser walkthrough).
- No deterministic earthquake *prediction* claims — historical, current event, and derived hazard only (§23, §53).
- Weather API key is a server-side secret: `backend/.env` only (gitignored), referenced as env var `WEATHER_API_KEY`, never shipped to frontend or committed.
- Earthquake source dataset: `C:\Users\User\Downloads\USGS_India_Earthquakes_2000_2026 (1) (1).csv` (5,446 rows, USGS schema, 2000-01-02 → 2026-09-03). Not part of the repo — ingestion reads from a configurable path.

## Status legend

- [!] = needs work from this plan
- [x] = exists and functional (verified)
- [d] = exists as DEMO/labeled fallback only
- [~] = exists, partially wired, needs real source/refactor

## Slice 1 — Data backbone (P0)

Goal: real, verifiable data lives in PostGIS and is served by the API; demo seed remains the labeled fallback.

### 1a. Weather provider (real, OBSERVED)
- [!] `backend/app/services/weather_service.py` — client for OpenWeather-compatible REST API using `WEATHER_API_KEY` (34-char key → provider-agnostic adapter; endpoints: current weather + forecast by lat/lon; 3-hourly forecast for intake).
- [!] `backend/app/core/config.py`: add `WEATHER_API_KEY: Optional[str]`, `WEATHER_API_BASE_URL`, `WEATHER_TIMEOUT_S`, `WEATHER_CACHE_TTL_S`.
- [!] `backend/app/ingestion/weather_ingester.py` — poller: stations defined in `regions.py` (Munnar/Idukki + Vizag + Assam coords), writes to new tables.
- [!] Schema additions (`backend/db/schema.sql`):
  - `weather_observations` (station_id, observed_at, temp_c, rainfall_mm_1h, rainfall_mm_24h, rainfall_mm_72h, humidity_pct, wind_kmh, soil_moisture_pct nullable, data_status OBSERVED, source).
  - `weather_forecasts` (station_id, forecast_for, rainfall_mm_24h, max_temp_c, min_temp_c, severity_hint, issued_at, data_status OBSERVED).
- Test: `backend/tests/test_weather_ingestion.py` — mock httpx responses → row counts + column values + derived 72h rainfall aggregate.
- API: `/api/v1/data/weather?region=idukki&window=72h` returning OBSERVED rows (or empty + labeled reason when key/source unavailable).

### 1b. Earthquake ingestion (real historical, DERIVED→historical context)
- [!] `backend/app/ingestion/earthquake_ingester.py` — reads USGS CSV: normalize `time` (ISO), `id` unique, `mag` nullable-safe, geometry point(geom,4326), fields nst/gap/dmin/rms/nullable. Idempotent upsert on `usgs_id`.
- [!] Schema (`earthquake_events`): usgs_id PK, occurred_at, magnitude, mag_type, depth_km, latitude, longitude, geom POINT, place, status, location_source, mag_source, ingested_at, data_status raw→DERIVED.
- [!] `backend/scripts/ingest_earthquakes.py` — CLI (path arg; default to config `EARTHQUAKE_CSV_PATH`); prints ingest summary.
- [d→!] Return "source dataset coverage" (year range, count, bbox) to frontend DataSources page.
- Test: `backend/tests/test_earthquake_ingestion.py` — sample CSV in tmp_path → 0 rows skipped cleanly, upsert idempotent, geoms valid.
- API: `/api/v1/hazards/earthquakes?region=..&since=..&magnitude_min=..` + `/api/v1/hazards/earthquakes/coverage`.

### 1c. Operational data plumbing (foundation for Slices 2,3,4)
- [!] `weather` + `earthquakes` join smoothing for risk (done in Slice 3, interface stubbed here via `hazard_sources` registry listing live providers + freshness per region).
- [!] Extend `app/api/v1/data_status.py` to report per-provider live freshness (last observed_at, row counts, source label) — powers ApiStatusBanner + DataSources page truthfully.
- Verify: `docker compose up -d db`, apply schema, run both ingestors, restart backend, hit both new endpoints; pytest green (weather + earthquake tests pass, existing 31 tests still pass).

**Slice 1 report** at `docs/build-log/01-data.md` (§48 template below).

## Slice 2 — Hazard / disaster intelligence (P0)

- [!] `hazard_events` table (event_id, hazard_type, severity, active, geom POLYGON/buffer, started_at, source, data_status OBSERVED|DERIVED).
- [!] `hazard_service.py` — current active event model: rainfall exceedance from live weather (RAINFALL_TRIGGER_MM 150/72h) → event activation; earthquake magnitude ≥ threshold near region → event; severity ladder.
- [~] Wire `hazard_assessments` for habitations from active events (intensity = distance/hazard decay) instead of static seed only; static stays as DEMO fallback when no live data.
- [!] API `/api/v1/hazards/current` + `/api/v1/hazards/detail/{event_id}`; frontend `RiskIntelligence`/map overlay for active hazard polygons + owner consciousness of events list.
- Tests: activation logic unit tests (rain over/under threshold, mag threshold, geographic reach), API contract tests.

**Slice 2 report** at `docs/build-log/02-hazard.md`.

## Slice 3 — Dynamic risk (P0)

- [!] `risk_engine` gains `dynamic` variant: baseline (existing deterministic) + escalation terms from live hazard events (rain/saturation/river from weather) already parameterized in config — now fed by real `weather_observations`/`hazard_events`, values cached per region w/ freshness.
- [!] Persist per-habitation `risk_scores` rows each recompute with `data_type=DERIVED`, retention of baseline; keep DEMO baseline computed path when live source absent.
- [~] Frontend `RiskIntelligence`: show live escalation breakdown only when OBSERVED data present; timeline of risk deltas; keep current stat panel.
- Tests: end-to-end recompute with fixture weather rows → score matches manual calc; no-source path falls back to baseline unbroke.

**Slice 3 report** at `docs/build-log/03-dynamic-risk.md`.

## Slice 4 — Safe zones (P0)

- [!] Replace/augment `screening.py`'s PSARA+GST heuristic with a **safe-zone engine**: 
  - hard constraints (slope ≤ t, away from fault lines using `earthquake_events` spatial clustering, away from active hazard polygons, land-use/water proximity),
  - suitability scoring (existing sub-scores) over real `habitations` + raster-free GIS (shapely/PostGIS SRID-4326 ops; DEM steepness from `--`; document basis).
- [!] `safe_zone_candidates` table + new candidate discovery from district bounds; de-dupe vs existing `candidate_sites`.
- [~] API `/api/v1/spatial/safe-zones` returns candidates with constraint evidence + score components; map layer toggle.
- Tests: candidate generation deterministic; constraint exclusion correctness; geometry validity.

**Slice 4 report** at `docs/build-log/04-safe-zones.md`.

## Slice 5 — Relocation workflow (P0)

- [~] Allocation: wire `relocation.py` optimization to **real** current risk output of Slice 3 + real candidate site capacities from Slice 4. Replace DEMO_OPTIMIZATION_RESULT in AllocationTab with live `/api/v1/relocation/optimize`.
- [!] Carry capacity: `capacity_assessments` computed from real constraints surfaced per site (water, land parcel, infra) — deterministic model, documented as Sentinel AI baseline, labeled RECOMMENDATION.
- [!] Relocation plan lifecycle: plan create → assignments (optimizer) → status transitions (draft→approved→executing→completed) with `relocation_plans` + `relocation_assignments` tables; authority can recalc risk and re-run optimizer.
- [!] UI: Relocation page get live plan + allocation table + per-habitation reallocation state; keep demo plan only as labeled fallback.
- Tests: optimizer over fixture risk+capacity matches CP-SAT expectation; plan workflow transition tests; API tests.

**Slice 5 report** at `docs/build-log/05-relocation.md`.

## Slice 6 — Routing real + on map (P0)

- [!] Start routing stack: docker compose up GraphHopper (kerala OSM) + OSRM + Valhalla; multi-engine service already honest about UNAVAILABLE — flip to live when containers ready.
- [!] GeoJSON route rendering on map (Route layer) — `MapContainer` gains overlay for `route_lines`; fetch route on habitations click/pair.
- [~] Default engine: set sensible default (graphhopper-kerala) rather than unconfigured osrm; per-region default in `regions.py`.
- Tests: route service integration (skip if engines down, assert honest UNAVAILABLE); route GeoJSON fallback rendering.

**Slice 6 report** at `docs/build-log/06-routing.md`.

## Slice 7 — Disaster-aware routing (P1/P0-decision)

- [!] Route weighting: hazard event polygons from Slice 2 + `earthquake_events` proximity → cost penalty on edges through active hazard zones; OSRM/Valhalla custom-model or GH weighted edges where supported; shapely pre-filter fallback (edges reweighted client of distance-to-hazard).
- [!] `route_options` response: normal vs advised-disaster route w/ risk delta + explanation (shortest vs safer, ETA tradeoff).
- [!] UI: route panel toggles disaster-aware, map overlay of hazard polygons vs both routes.
- Tests: deterministic penalty math; degraded mode when hazard events empty.

**Slice 7 report** at `docs/build-log/07-disaster-routing.md`.

## Slice 8 — Complete authority workflow (P0/P1)

- [!] End-to-end: ingest (S1) → hazard (S2) → dynamic risk (S3) → safe zones (S4) → relocation (S5) → reachability/routing (S6/S7) as one authority journey: "see district → see live risk → see active hazards → generate safe zones → run optimizer → approve plan → plan status flows".
- [!] Explanations: every recommendation + score endpoint returns human-readable reason path (already partially in risk/optimizer — formalize response `explanation[steps]` consistent with DecisionIntelligence trace).
- [!] Report generation (P1): PDF/HTML district report from real data (build from Slice 1-5 data, not GENERATED_AT demo).
- [~] Demo/real mode switch behavior: when DB empty or provider down, UI shows DEMO banner with replaced data; when real, removes banner for those sections only. ApiStatusBanner semantics adjusted.
- Tests: full-stack journey test with PostGIS up (httpx against backend, asserting real rows), frontend walkthrough recorded in report.

**Slice 8 report** at `docs/build-log/08-workflow.md`.

## P1 (after slices where not absorbed)
- Historical comparison charts (earthquakes × rainfall vs risk over time).
- Dynamic priorities: `relocation_priorities` recomputed from Slice 3 real scores (replaces static RPI data, keeps formula).
- GraphHopper matrix endpoint for large allocation runs.
- Valhalla isochrone 15/30/60 min reachability for safe zones + route reach tool.
- Additional hazard types (landslide rainfall threshold, cyclone winds) parameterized.

## P2 (polish/deferred)
- Integration test suite with PostGIS+engines live; auth + user roles; notifications (new event → authority alert); PDF report export polish.

## §48 Report template (one per slice)

```markdown
# Slice N — <name>
Date, committer state, HEAD.
## What changed
- backend: files/endpoints
- frontend: pages/components
- schema: tables/columns
## Tests run (evidence)
- command + output summary (pass/fail counts)
- new tests added
## Live verification
- API calls + observed responses (redacted secrets)
- browser walkthrough notes/screenshots
## Labels honored
- DEMO fallback paths that remain; OBSERVED/DERIVED labels per endpoint
## Known limitations / next slice dependency
```

Build log lives in `docs/build-log/`.

## Execution order
1. Slice 1 (this session): config + schema + ingesters (weather, earthquake) + data_status + API + tests + PostGIS verify → report.
2. Slice 2–5 sequential (hazard → risk → safe zones → relocation), each tested + reported.
3. Slice 6–7 routing bring-up (docker engines) + map overlays + tests.
4. Slice 8 full workflow + reports + labels audit.

Commit after each slice (explicit instruction from master prompt is that each capability must be evidenced; commits are per-slice, not per-file).