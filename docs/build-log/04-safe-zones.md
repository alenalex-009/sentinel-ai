# Slice 4 — Safe-zone engine (relocation candidate discovery)

**Date:** 2026-09-10 · **Status:** VERIFIED

Master prompt: Slice 4 (P0) — the engine that answers "where do we move people?"
A spatial grid over the district is scored as a relocation candidate: each cell
must clear hard safety constraints (fault proximity to USGS earthquake
epicenters, active-hazard polygon exclusion) before soft suitability scoring
(topography/land-use/water access where a layer exists). Candidates persist to
PostGIS as a geo-referenced `safe_zone_candidates` table, are served to the map
as a status-colored point layer, and drive Slice 5's relocation workflow.

## What changed

### Config (`backend/app/core/config.py`)
- `SAFE_ZONE_CACHE_TTL_S` (300) — in-process cache for the persisted list.
- `SAFE_ZONE_GRID_RADIUS_KM` (15.0) / `SAFE_ZONE_GRID_SPACING_KM` (3.0) —
  discovery footprint and cell pitch around the district anchor.
- `SAFE_ZONE_FAULT_BUFFER_KM` (10.0) — hard exclusion distance from any USGS
  epicenter (belt score 0 → suitability 0).
- `SAFE_ZONE_HAZARD_BUFFER_KM` (0.0) — hazard polygons are excluded by the
  polygon itself; the buffer is a configurable safety margin on top.
- `SAFE_ZONE_MIN_SUITABILITY` (50.0) / `SAFE_ZONE_MIN_SAFETY` (40.0) — status
  thresholds, aligned with `screening.py` zone semantics.

### Schema (`backend/db/schema.sql`, applied to PostGIS)
- `safe_zone_candidates(id PK, district_id, lat, lon, source, status,
  suitability_score, safety_score, constraint_pass, fault_km, nearest_hazard_km,
  hazard_id, slope_pct, land_use, water_km, hazard_intensity, max_intensity,
  data_status, created_at, updated_at)` — persisted discovered + existing-site
  rows.
- GIST index on `(lat, lon)` for spatial queries; second index on
  `(district_id, status)`; idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
  + `CREATE INDEX IF NOT EXISTS` so existing databases upgrade on apply.

### Service (`backend/app/services/safe_zone_service.py`)
- **Grid generation** — stepped lon/lat cells inside `GRID_RADIUS_KM` of the
  district anchor (5km pitch scaled by cos(φ) along lon), so the cell pitch in
  km is ~isotropic. Existing candidate sites are eval'd too.
- **Anchor** — `districts.geom` is a `GEOMETRY(MULTIPOLYGON)` **boundary**
  column that the seed leaves NULL, so discovery anchors on a documented
  real-world reference (`_DISTRICT_ANCHOR = {"idukki": (9.85, 76.98)}`) and
  falls back to `ST_Centroid(geom)` only when a true boundary exists. The
  geometry source is reported in `geometry_source` (never hidden).
- **Hard constraints** (fail → `constraint_pass=False`, score 0, red):
  1. Fault proximity — USGS epicenters (from the Slice 2 earthquake feed):
     `fault_km < SAFE_ZONE_FAULT_BUFFER_KM (10)` fails.
  2. Active-hazard polygon exclusion — code-in-sensor-pasture coverage events:
     a cell inside a hazard polygon fails. Edge fix: `inside = hazard_km <= 1e-6`
     so a zero-distance point is treated as inside, never falsely "passing".
- **Soft suitability** (`score_candidate`) — start at 100; slope (−18 per 10°
  slope where a DEM exists), land-use (−15 non-habitable),
  water (−5 per km beyond 1 km to source). Slope/land-use/water are UNAVAILABLE
  in this deployment and feed through with the penalty *omitted* — never
  assumed to pass.
- **Safety** (`safety_score`) — 100 − min(100, hazard_reach_km) for the nearest
  active hazard, floor 0; 0 when the cell is inside a hazard polygon.
- **Status** (`classify`) — red if `!constraint_pass` or suitability < 50 or
  safety < 40; yellow if suitability < 70; else green (matches `screening.py`).
- **Persistence** — `_persist_candidates` replaces only `source='discovered'`
  rows for the district (`id NOT IN (keep…)` prune) and upserts
  `source='existing'` rows, so re-runs are idempotent and never wipe existing
  site rows. **Returns a real bool** — `persisted` reflects an actual commit.
- `get_safe_zones` returns the persisted candidates as a status-colored
  FeatureCollection (green `#22c55e` / yellow `#eab308` / red `#ef4444`),
  honoring the cache TTL.

### API (`backend/app/api/v1/spatial.py`, registered in `app/main.py`)
- `POST /api/v1/spatial/safe-zones/discover` — run discovery (dry-run skips
  persistence), returns the candidate list + grid/constraint notes +
  `persisted` bool.
- `GET /api/v1/spatial/safe-zones?district_id=&refresh=` — persisted
  candidates as GeoJSON; `refresh=1` bypasses the cache; EMPTY + reason when
  the table holds nothing.

### Frontend
- `types`: `SafeZoneStatus`, `SafeZoneCandidate`, `SafeZoneDiscoveryResponse`,
  `SafeZoneCandidateFeature`, `SafeZonesResponse` (status_counts, note…).
- `api/client.ts`: `discoverSafeZones(districtId, dryRun)`,
  `getSafeZones(districtId, refresh)`.
- `MapContainer`: new `safeZonesGeoJSON` + `showSafeZonesLayer` props; a
  `safe-zones-ring` circle layer (status-colored, interpolated radius, hidden
  until features exist AND the flag is set) + a legend chip.
- `RiskIntelligence`: **Safe-Zone Candidates** right-rail panel (per-status
  counts, top green cells with suitability, "No green pockets" honesty line,
  geometry-source note) and a **Rediscover** button that POSTs discovery then
  refetches; new **Safe-zone candidates** entry in the Layers toggle.

## Bug fixed (silent persistence overclaim)
`_persist_candidates` originally wrapped the whole batch in try/except →
rollback with **no logging and an unconditional `persisted=True`**. Live
verification exposed it: discovery returned 84 candidates `persisted=True` but
`SELECT count(*) FROM safe_zone_candidates` was 0. Root cause surfaced once the
except stopped swallowing: `asyncpg AmbiguousFunctionError: function
unnest(unknown) is not unique` — asyncpg could not infer the array type from a
Python list bound to `unnest(:keep)`. Fixed with an explicit cast
`unnest(CAST(:keep AS text[]))` (plus the DELETE prune now correctly bounds the
keep-list). The flag is now the honest commit result and the failure path logs
`[safe_zone] persist failed …`.

## Tests run (evidence)

`python -m unittest discover -s tests` from `backend/` (venv .venv311):

```
Ran 132 tests in 8.778s
OK (skipped=2)
```

New `tests/test_safe_zone.py` — 28 tests, all pass:
- Grid generation: spacing/pitch isotropic-ish inside radius; anchor used when
  `districts.geom` is NULL (boundary column, seed empty); centroid path when a
  polygon exists.
- Fault constraint: far epicenter passes, within 10 km fails with belt score 0;
  nearest-fault distance math.
- Hazard constraint: far hazard passes; inside polygon fails; the
  zero-distance-inside edge case returns inside (not pass); hazard buffer.
- Scoring/status: soft penalties; suitability < 50 → red regardless of safety;
  safety < 40 → red; < 70 → yellow; else green.
- Persistence logic + idempotency with a stub session (replace-only-discovered,
  keep existing).
- API contract (TestClient, patched services): discover dry-run shape + POST
  persistence; GET EMPTY/no-row path + populated FeatureCollection.

Frontend: `tsc --noEmit` clean; target `eslint` clean; `vite build` succeeds
(chunk-size warning pre-existing, unrelated).

## Live verification (evidence)

Backend at 127.0.0.1:8000, PostGIS at :5433, vite dev at localhost:5173.

```
$ POST /api/v1/spatial/safe-zones/discover?district_id=idukki
persisted=True  candidates_count=84   (81 discovered + 3 existing)
geometry_source: idukki anchored at (9.8500, 76.9800): radius 15 km, spacing 3 km
constraints: fault_km=345.17 near Munnar → all cells pass the 10 km fault
             buffer; no active hazard polygon covers the grid → no exclusions.
             Slope/land-use/water UNAVAILABLE → fed through, never assumed pass.

$ psql -h localhost -p 5433 -U sentinel -d sentinel_ai \
    -c "SELECT source, count(*) FROM safe_zone_candidates GROUP BY source;"
 discovered | 81
 existing   |  3            ← re-run idempotent, existing rows never wiped

$ GET /api/v1/spatial/safe-zones?district_id=idukki
type=FeatureCollection  features=84  status_counts: green=2 yellow=82 red=0
feat=Point status=green id=idukki-site-site-a
```

- Red = 0 is the honest result for current inputs: Idukki sits ~345 km from the
  nearest USGS epicenter and outside every active hazard polygon. Red-class
  logic (constraint fail + score thresholds) is exercised by the unit tests.
- PostGIS rows match the API: 81 discovered all `constraint_pass=TRUE`, plus the
  3 existing sites.
- Frontend (Playwright, localhost:5173): Risk Intelligence page renders the
  Safe-Zone Candidates panel with live counts (`green: 2, yellow: 82, red: 0`),
  the layer toggle and legend, and the Rediscover button — clicking it POSTs
  discover (200) and refetches the list (200). `spatial/safe-zones` + all peer
  APIs 200; **no console errors**.

## Labels honored
- `persisted` is the actual transaction result; failures log and return
  `persisted=False` (the canary that found the unnest bug).
- Discovery geometry is explicit (`geometry_source` notes the anchor vs.
  centroid) — a NULL boundary column is never silently treated as a point.
- Slope / land-use / water are UNAVAILABLE and feed through with no assumed
  penalty — the constraint_note says so verbatim.
- All candidates are DERIVED (`data_type`) with `data_status` per row; existing
  candidate sites are evaluated under the same constraints as grid cells.

## Known limitations / next-slice dependency
- `districts.geom` carries no boundary in the seed, so the grid is anchored at
  a documented reference point — replace `_DISTRICT_ANCHOR` wiring once real
  boundaries land (centroid path already exists).
- Hazard/fault layers degrade to an empty event list when the feeds are down →
  constraints pass "trivially"; the API still labels feed availability in the
  discovery response (`sources_used`) so a false all-green can be inspected.
- No slope/land-use/water rasters yet — suitability is currently
  distance/hazards only; the penalty slots are wired and tested.
- Slice 5 consumes `status_counts` + green cells as the pool of relocation
  destinations ranked by current-risk cohort (Slice 3) and distance.