# Sentinel AI — Phase 7: Fully Dynamic Data + Live Routing Design

Date: 2026-09-10
Status: Approved design (Sections 1–3) — implementation pending user review of this spec.

## 1. Objective

Turn every page into a data-driven screen: danger zones, safe-zone candidates,
and evacuation routes rendered live on the MapLibre map, powered by real
routing engines (OSRM / Valhalla / GraphHopper) running locally in Docker
against a Kerala extract. All static/demo content across the app moves to
backend-fed values with clearly labelled DEMO fallback. No invented values, no
UI placeholders, no architecture rewrites.

## 2. Non-goals

- No openrouteservice (ORS).
- No new routing engine — MapCN = the existing MapLibre/MapContainer renderer.
- No new design system; reuse MapContainer layers, DataTypeBadge, provenance chips.
- No silent mixing of DEMO and LIVE data.
- No claiming a route is "safe" just because an engine returned it.

## 3. Architecture principles

- Keep the existing FastAPI services and routes; add only minimal read-only
  synthesis endpoints.
- Every geographic result the frontend renders carries usable GeoJSON geometry
  (hazards → Polygon/MultiPolygon, safe zones → Point/Polygon, affected areas →
  Polygon/Point, routes → LineString).
- Every synthesis endpoint exposes a provenance object:
  `{"source": "live"|"demo_fallback"|"simulated", "demo": bool, "reason"?, "generated_at", "region"}`.
- Engines report honestly: a container responding is NOT a ready router.

## 4. Live routing engines (Docker)

- Docker Desktop (present on this machine) runs Linux containers; compose file
  at `deploy/engines/docker-compose.yml`.
- Data: `kerala-latest.osm.pbf` from Geofabrik (~50 MB), persisted in a named
  volume; generated datasets (OSRM extract, Valhalla tiles, GraphHopper graph)
  also persisted so container restarts do not rebuild.
- Services and ports: OSRM `osrm/osrm-backend` → 5000, Valhalla
  `ghcr.io/gis-ops/docker-valhalla` → 8002, GraphHopper
  `ghcr.io/gis-ops/docker-graphhopper` (pinned release) → 8989.
- Launcher `deploy/engines/up.ps1`: starts Docker Desktop if the daemon is
  down, runs `docker compose up -d`, then polls per-engine readiness
  (below); never treats "container up" as "router ready".
- Readiness (real request against the Kerala dataset, per engine):
  - OSRM: `GET /route/v1/driving/{lon,lat;lon,lat}?overview=false` → 200 + `routes[]`
  - Valhalla: `GET /status` = `{"status":"ok"}` **then** small `POST /route` → 200
  - GraphHopper: `GET /info` → 200 **then** `GET /route?point=…&profile=car` → 200 + `paths[]`
- Backend `.env` overrides: `OSRM_KERALA_URL=http://localhost:5000`,
  `VALHALLA_KERALA_URL=http://127.0.0.1:8002`,
  `GRAPHHOPPER_KERALA_URL=http://localhost:8989`.

## 5. Routing policy (exact)

```
ROUTE_STANDARD   primary=OSRM   fallback=Valhalla   (route to a safe zone)
ROUTE_ADVANCED   primary=Valhalla  fallback=NONE   (risk-aware / advanced)
ROUTE_MATRIX     primary=OSRM   fallback=Valhalla  (travel matrix)
OPTIMIZATION     solver=OR-Tools
```

- Standard/matrix calls try the primary engine; if it is not `ready`, retry the
  fallback transparently and report which engine served.
- **GraphHopper is explicitly OPTIONAL/EXPERIMENTAL.** It is never required by
  the core relocation pipeline, never a fallback in ROUTE_STANDARD /
  ROUTE_ADVANCED / ROUTE_MATRIX, and its status is surfaced as experimental in
  the engine selector. Enabling it beyond reachable/ready reporting is outside
  this phase.

## 6. Relocation pipeline (logical flow)

```
Affected locations
  → hazard + risk assessment
  → safe-zone candidates (with capacity ceilings)
  → OSRM travel matrix (express), Valhalla fallback
  → OR-Tools optimization CONSTRAINED by safe-zone capacity
  → optimal population → safe-zone allocation
  → explicit capacity gap / unallocated demand reported when it occurs
  → Valhalla advanced route (fallback NONE)
  → route validation against active hazard geometry
  → GeoJSON route
  → MapLibre map
```

Safe-zone capacity is a hard constraint of the optimization, never a soft
assumption: the optimizer may not over-allocate any safe zone beyond its
`estimated_capacity`, and when total demand exceeds total capacity the output
MUST report an explicit **capacity gap** and **unallocated demand** rather than
silently forcing assignments. The evacuation overview and the relocation
plan/assignment outputs all expose these two figures with their provenance.

### 6.1 Hazard-aware route validation (mandatory)

Routing engines do not know Sentinel's disaster-risk polygons. The backend
must, for every evacuation route:

```
route geometry → intersect with active hazard/closure geometry
→ route risk score → reject/recalculate unsafe route when necessary
→ GeoJSON + risk score returned
```

A route is never reported "safe" merely because OSRM/Valhalla returned it.
`hazard_aware_routing.py` already implements score + alternatives; it stays the
core of this step.

## 7. Backend endpoint contract (new, read-only, reuse services)

### 7.1 `GET /api/v1/evacuation/overview?region=idukki&disaster_type=landslide|flood`

Synthesis for the Command screen. Blocks (each with provenance):
- `disaster_type` is optional on the overview; when omitted it defaults to the
  current dominant live hazard. Explicit values are only honoured for
  read-only scoping of the recommended action — the overview always reflects
  current conditions (never simulated).
- current hazards + severity (hazard service, `current_hazards`)
- hazard/danger-zone GeoJSON polygons
- affected habitations/locations + population
- evacuation demand / capacity / gap (relocation demand service)
- safe-zone candidates + capacity as GeoJSON (safe-zones service)
- recommended safe zone
- recommended route + GeoJSON geometry (+ risk score)
- alternative routes when available
- route distance, ETA, risk score
- current evacuation status
- data provenance for every block

### 7.2 `GET /api/v1/priorities?region=idukki`

Ranked relocation priority from the existing risk-index model (real scores —
never invented). Each row: habitation/location, risk score, hazard type,
severity, affected population, priority level, recommended action,
coordinates/GeoJSON, provenance.

### 7.3 `GET /api/v1/reports/summary?habitation_id=&plan_id=`

Report assembled from existing risk, risk-drivers, hazards, habitation,
relocation-plan, decision and (where applicable) routing data. Provenance +
demo/fallback status per section. `generated_at` timestamp.

### 7.4 Scenario Analysis

Continue routing through the existing `POST /api/v1/scenarios/simulate`. Seed
inputs from available live hazard, location, OSM-context, population,
safe-zone and routing data. Users may simulate supported disaster types even
when they are not the current dominant hazard, but the result is always
labelled **SIMULATED SCENARIO** and is never presented as current/live.

### 7.5 `GET /api/v1/routing/engines?region=kerala`

Each engine exposes two independent states:

```json
{ "osrm":      { "reachable": true, "ready": true,  "ok": true },
  "valhalla":  { "reachable": true, "ready": false, "ok": false },
  "graphhopper":{"reachable": false,"ready": false, "ok": false, "reason": "container down" } }
```

- `reachable` = the container/service responds.
- `ready` = a real Kerala routing request succeeded.
- `ok` retained for backward compatibility and always equals `ready`.
- When not usable: `status="UNAVAILABLE"`, `reason=<actual reason>`.
- UI green only when `ready=true`.

## 8. Frontend wiring per page (no placeholders, no invented data)

1. **Overview (Command)** — replace hardcoded stats with `/evacuation/overview`;
   map pipes danger-zone GeoJSON, safe-zone GeoJSON, recommended + alternative
   routes into existing layers; habitation markers from `getHabitations`
   (DEMO fallback). Per-block LIVE/CACHED/DEMO chips. Auto-pick best `ready`
   engine per policy for "Evacuate now".
2. **Risk & GIS Intelligence** — wire hazard GeoJSON + safe-zone GeoJSON + a
   "route to best safe zone" runner into its MapContainer; source labels.
3. **Priorities** — rows from `/priorities`; whole-block DEMO on API failure.
4. **Reports** — sections from `/reports/summary` with per-section provenance
   and `generated_at`; download stays client-side.
5. **Scenario Analysis** — inputs auto-seeded from live data; all supported
   disaster types selectable; permanent **SIMULATED SCENARIO** banner.
6. **Engine selector** — green only when `ready`; amber "starting" when
   reachable-not-ready; red UNAVAILABLE + reason otherwise; never a fake route.

## 9. Provenance contract (every synthesis endpoint)

Live block:
```json
{ "source": "live", "demo": false, "generated_at": "...", "region": "idukki" }
```
Fallback block:
```json
{ "source": "demo_fallback", "demo": true, "region": "idukki", "reason": "OSRM unavailable" }
```
Simulated block:
```json
{ "source": "simulated", "demo": true, "label": "SIMULATED SCENARIO", "reason": "user-chosen disaster type", "region": "idukki" }
```

## 10. Verification gates (evidence before assertions)

- Backend full suite (`python -m unittest discover -s tests`) stays green;
  new tests for all synthesis endpoints + engine-status reachable/ready split.
- `deploy/engines/smoke.py` performs the per-engine real-request readiness
  checks against Kerala data and prints a READY/NOT-READY table.
- Frontend: `tsc --noEmit`, eslint (`--max-warnings 0`), `vite build`.
- Playwright e2e: Overview danger/safe/route layers render and provenance
  chips show real values; priorities/reports/scenario pages paint from API;
  engine dots reflect `ready`.
- Honest degradation confirmed: engines stopped → UNAVAILABLE shown, not fake.

## 11. Risks / limits

- First engine build takes ~10–20 min (OSM extract processing under Docker);
  data is persisted so subsequent starts are fast.
- Public Overpass remains intermittently slow (mitigated by mirror pick +
  retries, Phase 6) — OSM layer chips may report differently between runs.
- Engine state on machine reboot = UNAVAILABLE (honest, by design).
- Render/VERCEL deployments still lack PostGIS provisioning; upstream of the
  local engine work, prod pages whose DB is unreachable fall back to labelled
  DEMO (unchanged).