# Slice 2 — Hazard / disaster intelligence (active events + map overlay)

**Date:** 2026-09-10 · **Status:** VERIFIED

Master prompt: Slice 2 (P0) — active hazard events built from LIVE sources
only (rainfall exceedance from live weather; recent alert-magnitude quakes),
served to the frontend as a GeoJSON overlay + owner-conscious events list.
Never fabricated: an empty operational picture returns EMPTY with the source
basis, not guessed events.

## What changed

### Config (`backend/app/core/config.py`)
- `EARTHQUAKE_ALERT_MAG_MIN` (5.0) — quake magnitude activation floor.
- `HAZARD_QUAKE_ACTIVE_DAYS` (7) — quake stays "current" this long.
- `HAZARD_CACHE_TTL_S` (300) — in-process current-hazard cache.

### Schema (`backend/db/schema.sql`, applied to PostGIS)
- `hazard_events` table: deterministic `event_id` PK, hazard_type, severity
  level/score, active, geom POLYGON(4326) buffer, centroid, buffer_radius_km,
  started_at, last_confirmed_at, source, data_type (OBSERVED|DERIVED), event_meta
  JSONB. Upsert on event_id; recomputes deactivate stale events. GIST index on
  geom + active index.

### Service (`backend/app/services/hazard_service.py`)
- Severity ladder: LOW <25 · MODERATE 25-49 · HIGH 50-74 · SEVERE ≥75.
- **Rain activation**: station 72h rainfall (DERIVED from live OBSERVED weather)
  ≥ `RAINFALL_TRIGGER_MM` (150) → LANDSLIDE/FLOOD event (region-mapped) with a
  circular buffer. severity = 30 + (rain72-150)×0.10 (cap 100); buffer 10-50 km.
- **Quake activation**: recent (7-day) catalog event with magnitude ≥ 5.0 →
  EARTHQUAKE event. severity = 30 + (mag-5.0)×40 (cap 100); buffer 15-60 km.
- **Exposure intensity** (distance decay): severity × (1 − min(1, dist/radius));
  used by the detail endpoint for affected habitations. Circular buffers are
  documented as ESTIMATED reach, not surveyed footprints.
- `current_hazards()` — reads live weather + recent quakes (`data_read`), builds
  events, persists (upsert + deactivate stale) best-effort, caches per region,
  returns events + `feature_collection` (GeoJSON for the map).
- `get_event_detail()` — one event + affected habitations with exposure
  intensity + distance-decay basis.
- Event `started_at` normalized to aware datetime (accepts ISO strings from
  data_read and datetimes from tests).
- Persistence deactivation uses an expanding bindparam (psycopg2 would mangle a
  plain tuple into a ROW constructor); `:event_meta::jsonb` cast uses
  `CAST(:event_meta AS jsonb)` (SQLAlchemy text() swallows `::` into the bind
  name).

### API (`backend/app/api/v1/hazards.py`, registered in `app/main.py`)
- `GET /api/v1/hazards/current?region=kerala|vizag|assam` — active events +
  GeoJSON overlay + per-source basis (weather/quakes status + reasons).
- `GET /api/v1/hazards/detail/{event_id}` — event + affected habitations.

### Bug fixed in Slice 1 surface (`backend/app/services/data_read.py`)
- `get_earthquakes` bound `since` as an ISO string; asyncpg rejects str for a
  timestamptz comparison → query exception misreported as "database connection
  failed". Now parses `since` to an aware datetime; invalid values return
  UNAVAILABLE-with-reason. This was the exact path hazard activation used.

### Frontend (Slice 2 wire-up)
- `types`: `HazardType` + `EARTHQUAKE`; `HazardEvent`, `CurrentHazardsResponse`,
  `HazardDetailResponse`, `HazardSeverityLevel`.
- `api/client.ts`: `getCurrentHazards(region?)`, `getHazardDetail(eventId)`.
- `MapContainer`: new `hazardGeoJSON` prop; `hazards` source + `hazards-fill`
  (0.22 opacity, severity-colored) + `hazards-outline` layers; data swap + toggle
  with the existing `showHazardLayer` control (shares it with the Bhuvan
  historical overlay).
- `RiskIntelligence` page: fetches live current hazards (API-first, empty
  fallback), renders the hazard overlay, adds an **Active Hazards** panel listing
  each event (type, severity badge, date, reach, data-type/place) with a per-source
  status line, plus a severity legend.

## Tests run (evidence)

`python -m unittest discover -s tests` from `backend/` (venv .venv311):

```
Ran 84 tests in 5.002–5.342s
OK (skipped=2)
```

New `tests/test_hazard_service.py` — 20 tests, all pass:
- Severity ladder boundaries (0/24.9/25/49.9/50/74.9/75/150) and clamping.
- Rain activation: below trigger (149) → none; at trigger → MODERATE LANDSLIDE
  (kerala primary); heavy (650mm) → HIGH/SEVERE with formula-checked score.
- Quake activation: 4.9 → none (below floor); 5.0 → MODERATE; 6.75 → SEVERE;
  no `geom` on the raw builder (attached at finalization).
- Geographic reach: exposure intensity decay at 0/50%/100% radius; circle
  polygon radius ordering; haversine sanity.
- `build_current_events`: filters below-threshold inputs → []; sorts by
  severity; polygons serializable.
- Current-hazards flow (patched data_read, stub session): rain+quake both
  activated → LIVE with 2 features, persisted; below-threshold → LIVE 0 events;
  unknown region → UNAVAILABLE; detail returns only in-buffer habitations with
  intensity ≤ severity_score.
- API contract (TestClient, patched service): `/current` shape; `/detail`
  unknown id → EMPTY.

Frontend: `tsc --noEmit` clean; `eslint . --max-warnings 0` clean; `vite build`
succeeds.

## Live verification (evidence)

Backend at 127.0.0.1:8000, PostGIS at :5433, vite dev at localhost:5173.

```
$ GET /api/v1/hazards/current
data_status=LIVE  events=1  persisted=True  region=all
event=quake-us7000tdv4  EARTHQUAKE  MODERATE(34.0)
started=2026-09-03T08:16:36Z  geo=(31.3618, 80.33)  buf=17.0 km
  feature_collection.features=1 (Polygon)
  source_basis: weather=STALE  quakes=LIVE
```

- The single active event is a REAL catalog quake (USGS us7000tdv4, M5.1,
  2026-09-03, "115 km NE of Joshimath") — genuine activation from ingested USGS
  data. No race/polling hazard exists right now: munnar/vizag/guwahati 72h rain
  are below the 150mm trigger (guwahati ~26mm), so no rain events — the correct
  empty-contribution result.
- `persisted=True` confirmed in PostGIS (`hazard_events` row active=TRUE,
  severity MODERATE 34.0; stale deactivation verified by recompute).
- Region filter: `?region=assam` → LIVE, 0 events (assam quakes in window: none
  ≥5.0). `?region=kerala` → LIVE 0 events.
- `/hazards/detail/quake-us7000tdv4` → LIVE; affected habitations = 0 because the
  epicenter (Uttarakhand) is outside the Idukki demo habitation set — honested
  empty reach, not fabricated overlap.
- Frontend (Playwright, localhost:5173 → vite proxy → backend): Risk Intelligence
  page renders **Active Hazards** panel showing the EARTHQUAKE chip (MODERATE /
  34, 10 Sep, 17 km reach, OBSERVED) and the source basis line
  `weather=STALE · quakes=LIVE`; no console errors; map receives the LIVE
  feature_collection (1 Polygon) for the overlay. Proxy round-trip verified:
  `localhost:5173/api/v1/hazards/current` → LIVE events=1 persisted=True
  features=1.

## Labels honored
- Rain events: DERIVED (severity from the DERIVED 72h rainfall window over
  OBSERVED provider fields); quake events: OBSERVED (USGS as-served).
- Fixed-hazard intensity for habitations is NOT yet wired from events — the
  static seed hazard_assessments remain the DEMO fallback; the `[~]` slice item
  is delivered as the detail-endpoint decay math + demo-habitation exposure
  (interoperable with risk in Slice 3), keeping static-as-DEMO fallback intact.
- Buffers explicitly "estimated exposure reach — not a surveyed footprint".

## Known limitations / next-slice dependency
- Detail exposure currently evaluates the Idukki demo habitations; a DB-backed
  habitation layer (Slice 3+) broadens reach.
- Hazard severity ladder and buffer formulas are documented Sentinel AI baselines
  (config-driven thresholds, service-defined severity math) — not government
  formulas.
- Persistence keeps history: recompute deactivates (active=FALSE) instead of
  deleting, so `hazard_events` accumulates a current-picture ledger.
- Slice 3 consumes `hazard_events` + `weather_observations` to drive the dynamic
  risk escalation (live → baseline+escalation), retained DEMO baseline when no
  live data.