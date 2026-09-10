# Slice 1 — Real Data Backbone (weather + earthquake ingestion)

**Date:** 2026-09-10 · **HEAD:** `4aed343` + uncommitted Slice-1 work · **Status:** VERIFIED

Master prompt: Slice 1 (P0) — real, verifiable data lives in PostGIS and is
served by the API; the demo seed remains the labeled fallback.

## What changed

### Config
- `backend/.env` (gitignored) — `WEATHER_API_KEY` (WeatherAPI.com, server-side
  only), `EARTHQUAKE_CSV_PATH` (USGS India CSV), and `DATABASE_URL` on port
  5433 (host Postgres already owns 5432).
- `backend/.env.example` (committed) — documents the variables without values.
- `backend/app/core/config.py` — `WEATHER_API_KEY`, `WEATHER_API_BASE_URL`,
  `WEATHER_TIMEOUT_S`, `WEATHER_CACHE_TTL_S`, `EARTHQUAKE_CSV_PATH`,
  `EARTHQUAKE_SOURCE_URL`.

### Schema (`backend/db/schema.sql`, applied to PostGIS)
- `weather_observations` — current conditions per station, data_status OBSERVED,
  rainfall_mm_24h/72h as DERIVED rolling windows; UNIQUE(station_id, observed_at).
- `weather_forecasts` — 3-day forecast per station; UNIQUE(station_id, forecast_for).
- `earthquake_events` — USGS catalog: usgs_id PK, occurred_at, magnitude,
  mag_type, depth_km, place, lat/lon, geom POINT(4326), nst/gap/dmin/rms,
  errors, status, location/mag source, reviewed; OBSERVED.
- GIS indexes on geom for all three.

### New services / ingestion
- `app/services/weather_service.py` — WeatherAPI.com client (current +
  3-day forecast + alerts), station registry (munnar/vizag/guwahati), DERIVED
  24h/72h rolling rainfall baseline, `WeatherUnavailable` with explicit reason.
- `app/ingestion/weather_ingester.py` — sync poller (psycopg2) → PostGIS,
  upsert-on-conflict, per-station summary, honest UNAVAILABLE when the key is
  missing or provider fails. httpx URL logging silenced (key lives in query).
- `app/ingestion/earthquake_ingester.py` — USGS CSV parse/normalize (skips
  non-earthquake types, missing coords/time/id), upsert on usgs_id, geom built
  as SRID 4326 POINT.
- `app/services/data_read.py` — async read layer: recent weather, forecast,
  earthquakes (region/magnitude/since filters via regions.py reference bounds),
  earthquake coverage facts. EMPTY + UNAVAILABLE-with-reason, never fabricated.
- `app/api/v1/data.py` — `/api/v1/data/weather`, `/api/v1/data/weather/forecast`,
  `/api/v1/data/earthquakes`, `/api/v1/data/earthquakes/coverage`. Registered in
  `app/main.py`.
- `scripts/ingest_weather.py`, `scripts/ingest_earthquakes.py` — CLIs (JSON or
  human output, exit codes).

### Data-source registry (`app/services/data_status.py`, `app/api/v1/data_status.py`)
- New entries: `weatherapi` (OBSERVED/LIVE) and `usgs-earthquakes`
  (OBSERVED/LIVE) with honest limitations text.
- `/api/v1/data-sources` and `/api/v1/data-sources/health` now probe the
  ingestion tables at request time (row counts) and flip LIVE only when rows
  exist; includes `ingested_rows` and explicit `error_message` when empty/unreachable.
- `imd-rainfall` clarity: real-time rainfall input now comes from the
  weatherapi provider; IMD remains the reference source.

## Tests run (evidence)

`python -m unittest discover -s tests` from `backend/` (venv .venv311):

```
Ran 64 tests in 5.052s
OK (skipped=2)
```

- New file `tests/test_data_ingestion.py` — 9 tests, all pass:
  - Earthquake CSV: valid-row parse (geometry, mag, reviewed), rejects
    explosion type, rejects missing coords/time/id.
  - Weather: DERIVED 24h/72h rainfall math (10/120/30 → 160), no-data → None,
    station lookup, provider-unavailable-without-key.
  - Read API: unknown region → UNAVAILABLE with reason.
- Existing suite: 55 → 64 tests now run; PostGIS-backed tests that previously
  skipped now execute and pass (engine reachable on :5433). 2 still skip
  (routing services not running this slice).

## Live verification (evidence)

### Earthquake ingestion (real USGS CSV, 5,446 rows)
```
$ python scripts/ingest_earthquakes.py
{"status": "OK", "rows_read": 5446, "rows_inserted": 5446, "rows_failed": 0}
```
PostGIS: `total=5446, with_geom=5446, reviewed=5446`, time 2000-01-02 →
2026-09-03, mag 3.1 → 7.7. Region check: kerala bounds → 0 (genuine: Kerala is
seismically quiet), vizag → 2, assam → 807.

### Weather ingestion (live WeatherAPI.com, key from backend/.env)
```
munnar   obs=1 fc=3 rain24h=3.86 rain72h=14.53   (kerala)
vizag    obs=1 fc=3 rain24h=1.01 rain72h=7.89
guwahati obs=1 fc=3 rain24h=10.94 rain72h=26.3   (assam)
```

### API responses (backend at 127.0.0.1:8000, PostGIS at :5433)
- `GET /api/v1/data/weather?region=kerala&hours=72` → `LIVE`, 1 row, munnar
  temp_c 19.5, rainfall_mm_72h 14.53, data_type/status OBSERVED.
- `GET /api/v1/data/weather?hours=72` → `LIVE`, 3 rows, max_age_min ~6.5.
- `GET /api/v1/data/earthquakes?region=assam&limit=3` → `LIVE`, 3 recent quakes
  (2026-08-10 M4.2, 2026-07-25 M4.5, 2026-07-21 M4.2).
- `GET /api/v1/data/earthquakes/coverage` → `LIVE`, 5446 records, ranges as above.
- `GET /api/v1/data-sources` → `weatherapi: LIVE ingested_rows=3`,
  `usgs-earthquakes: LIVE ingested_rows=5446`.
- `GET /health` → database ok; live_data weatherapi "3 observations",
  usgs_earthquakes "5446 events".

## Labels honored
- Weather rows and forecasts: `OBSERVED` (provider as-served); 24h/72h rainfall
  windows: `DERIVED` with formula documented.
- Earthquake rows: `OBSERVED` (USGS as-served), explicitly historical context —
  no prediction claims.
- API/data-sources: LIVE only when real rows exist; EMPTY and UNAVAILABLE-with-
  reason otherwise. Demo fallback paths in db_service/demo_data untouched.

## Known limitations / next-slice dependency
- Weather rainfall is point-station derived from WeatherAPI.com 3-day forecast
  (Sentinel AI baseline), not IMD official station data for the district.
- Weather poller is manual CLI right now; a cron/scheduler wiring is Slice 2-3
  work so hazard escalation is driven by live values.
- Earthquake ingestion is bulk-from-CSV; near-real-time USGS feed could be added.
- Host port conflict: docker `db` publishes 5433 (host Postgres owns 5432); all
  local + compose URLs must use 5433.
- Slice 2 depends on `weather_observations` (rain threshold) +
  `earthquake_events` (recent quake context) — both ready.