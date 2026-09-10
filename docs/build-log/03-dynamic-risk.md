# Slice 3 — Dynamic current risk (live escalation + recompute ledger)

**Date:** 2026-09-10 · **Status:** VERIFIED

Master prompt: Slice 3 (P0) — a current-risk value per habitation that moves
with live inputs (72h rainfall window, active hazard exposure), persisted as a
recompute ledger so every change to a habitation's risk is an auditable row,
served to the dashboard as a **Live Escalation** panel and a **Risk Delta
Timeline**. Deterministic baseline stays intact; live data *escalates* it when
the input clears its trigger.

## What changed

### Config (`backend/app/core/config.py`)
- `RISK_CACHE_TTL_S` (300) — in-process current-risk cache per district.
- `RISK_SCORE_STALE_HOURS` (6.0) — weather basis honored as live input but
  labeled STALE until it refreshes.
- `ESCALATION_EVENT_COEFF` (0.50) — weight of active-hazard exposure on the
  current score (capped with rainfall, combined cap `ESCALATION_CAP` 15).

### Schema (`backend/db/schema.sql`, applied to PostGIS)
- `risk_scores` gains `event_escalation_component FLOAT` (the live delta) and
  `live_inputs JSONB` (rainfall mm/72h, station_id, hazard intensity, basis).
- `idx_risk_scores_computed` index on `(habitation_id, computed_at DESC)` for
  latest-row lookups; idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` +
  `CREATE INDEX IF NOT EXISTS` so existing databases upgrade on apply.

### Service (`backend/app/services/risk_service.py`)
- **Baseline** = sum of the fixed engine components (from the seeded
  `risk_scores` row — e.g. munnar-central 80.21). Never mutated.
- **Escalation** (applied only when live inputs are available):
  - Rainfall: `0.05 × (rain72 − 150)` — the hazard trigger from Slice 2, feeding
    a LAND/exposure-graded delta once rain clears 150 mm.
  - Events: `ESCALATION_EVENT_COEFF × exposure intensity` for any active hazard
    event covering the habitation (distance-decayed, from Slice 2). Region map
    `idukki → kerala` routes weather + event lookups.
  - Combined cap `ESCALATION_CAP` (15); current = baseline + escalation, clamped
    [0, 100].
- **Live-ness**: weather `LIVE`/`STALE` + hazard event call must succeed; soil
  saturation + river level are reported UNAVAILABLE and feed 0 (honest, not
  fabricated zeros).
- **DEMO fallback unchanged**: no live path → the demo narrative (current =
  risk_score, escalation = risk_change, `data_status=DEMO`) is returned as-is.
- **Ledger**: every live recompute INSERTs a new `risk_scores` row
  (`data_type=DERIVED`, `data_status=LIVE`, `live_inputs` JSONB via
  `CAST(:live_inputs AS jsonb)`), keeping `baseline_score` from the seed.
  Timeline query returns the recompute history per habitation.
- Module-style imports of `data_read`/`hazard_service` keep services unit-test
  patchable.

### API (`backend/app/api/v1/risk.py`, registered in `app/main.py`)
- `GET /api/v1/risk/current?district_id=idukki` — cohort of habitations with
  baseline / escalation / current scores + per-source basis (weather state,
  events considered), persisted flag, data_status LIVE|DEMO.
- `GET /api/v1/risk/current/timeline/{habitation_id}` — recompute history
  (current, baseline, escalation, computed_at); EMPTY when none.

### Bug fixed (legacy joins vs. new ledger cardinality)
Slice 3 made `risk_scores` a ledger, but the three consumers that joined it
directly were still written for one-row-per-habitation:
`db_service.get_habitation_list`, `db_service.get_habitation_detail`, and
`spatial_service.get_habitation_geojson` produced one habitation row *per
recompute*. Symptom: `/api/v1/habitations?district=idukki` returned 15 rows and
React logged duplicate-key warnings; the spatial test caught it as `15 != 5`.
Fixed with the latest-row join:
`LEFT JOIN (SELECT DISTINCT ON (habitation_id) ... FROM risk_scores ORDER BY
habitation_id, computed_at DESC) r ...` (list, detail, geojson). Habitation
list now surfaces the *latest* live score — coherent with the Live Escalation
panel.

### Frontend (Slice 3 wire-up)
- `types`: `DataStatus` gains `EMPTY`; new `CurrentRiskBasis`, `RiskSourceBasis`,
  `DynamicRiskLiveInputs`, `CurrentRiskHabitation`, `CurrentRiskResponse`,
  `RiskDeltaPoint`, `RiskTimelineResponse`.
- `api/client.ts`: `getCurrentRisk(districtId)`, `getRiskTimeline(habitationId)`.
- `FreshnessBadge`: `EMPTY` badge variant (slate) so the union stays total.
- `RiskIntelligence`: fetches both APIs (API-first, EMPTY falls back to an empty
  panel so nothing is fabricated), renders:
  - **Live Escalation** panel (only when `data_status=LIVE`): LIVE badge,
    per-habitation base / +esc / now bars, rain mm/72h · hazards · station,
    basis line `Weather STALE · active events 0 · soil/river UNAVAILABLE`.
  - **Risk Delta Timeline**: current vs. baseline sparkline from the recompute
    ledger for the selected habitation (skipped when `points.length === 0`).

## Tests run (evidence)

`python -m unittest discover -s tests` from `backend/` (venv .venv311):

```
Ran 104 tests in 8.415s
OK (skipped=2)
```

New `tests/test_risk_dynamic.py` — 20 tests, all pass:
- Baseline composition = engine component sum; no live inputs → DEMO fallback.
- Escalation math: below rain trigger → +0; at/above trigger formula; event
  coefficient × exposure; combined cap at `ESCALATION_CAP`.
- Live vs. stale weather: STALE is honored with the STALE basis label; failed
  live calls label to-demand and never fabricate.
- Ledger: recompute INSERTs a fresh row, baseline_score from the seed retained;
  `DISTINCT ON` latest-row join returns exactly one entry per habitation (the
  regression net the 15-row bug needed).
- API contract (TestClient, patched services): `/risk/current` LIVE shape +
  DEMO fallback shape; timeline known/unknown id.

Frontend: `tsc --noEmit` clean; `eslint . --max-warnings 0` clean; `vite build`
succeeds. (ESLint/tsc re-verified after the final key fix.)

## Live verification (evidence)

Backend at 127.0.0.1:8000, PostGIS at :5433, vite dev at localhost:5173.

```
$ GET /api/v1/risk/current?district_id=idukki
data_status=LIVE  habitations=5  persisted=True
munnar-central  base 80.21  esc +0.0  now 80.21   rain 14.53mm/72h (munnar, STALE)
rajakkad        base 70.50  esc +0.0  now 70.50
kanthalloor     base 63.40  esc +0.0  now 63.40
marayoor        base 53.90  esc +0.0  now 53.90
adimali         base 44.30  esc +0.0  now 44.30
basis: weather=STALE(3)  events=0  soil/river=UNAVAILABLE (feed 0)
```

- Escalation is 0 for all five because the live weather (14.53mm/72h) is below
  the 150mm rain trigger and no event covers Kerala — the *correct* no-op, not a
  missing path. A rain-≥150 or event-reach scenario is covered by unit tests.
- `persisted=True`: PostGIS `risk_scores` holds one DERIVED/LIVE row per
  habitation with `live_inputs.rainfall = 14.53`, station `munnar`; the seed
  rows (risk 94/81/73/61/48) remain untouched below.
- Timeline: `GET /risk/current/timeline/munnar-central` → LIVE, 2 points — the
  newest (base 80.21, cur 80.21, esc 0.0) and the original seed (base 65,
  cur 94, esc null) — the ledger retaining its history.
- Frontend (Playwright, localhost:5173 → vite proxy → backend): Risk
  Intelligence page renders the **Live Escalation** panel (LIVE badge, base
  80.21, `14.53mm/72h`, `+0.0`, `haz 0`, basis line) and the **Risk Delta
  Timeline** once Munnar Central is selected (current vs. baseline legend);
  left habitations list now shows the five *live* scores; Active Hazards panel
  intact; **no console errors** (duplicate-key warnings from the cardinality
  bug are gone).

## Labels honored
- Live path only when live-or-stale inputs resolve; DEMO fallback returns the
  demo narrative byte-for-byte (current = risk_score, escalation = risk_change).
- STALE weather is consumed but honestly labelled (`Weather STALE · events 0`).
- Soil saturation and river level are UNAVAILABLE and feed 0 — visible in the
  basis line instead of hidden.
- Ledger rows are DERIVED/LIVE; seed rows keep their original DEMO status and
  baseline, so any "before/after" comparison is auditable in `risk_scores`.

## Known limitations / next-slice dependency
- Escalation formulas and the 150mm rain trigger are Sentinel AI baselines
  (config-driven), not government standard curves.
- Current risk only escalates via rainfall + hazard exposure; soil/river feeds
  are UNAVAILABLE until a live layer exists (would slot into `live_inputs`).
- The recompute ledger grows one row per live GET per habitation; the
  cache (TTL 300s) bounds writes at dashboard cadence, but a retention job is
  future work.
- Slice 4 consumes the risk cohort (`.sort by current_score` → safe-zone
  prioritization) and the `risk_scores` ledger as the source of truth for what
  "current risk" means when evacuation options are ranked.