# Routing datasets — regional OSM extracts (Kerala / Vizag / Assam)

Operator guide for the GraphHopper routing datasets. **OSM extracts are external
data**: they are never committed to Git, never baked into the GraphHopper image,
and live only in this bind-mounted `osm/` directory (gitignored — see
`.gitignore`). One GraphHopper engine runs per region; the backend picks the
engine from the coordinates being routed.

GraphHopper graphs are built at **import time** — a running instance must never
have its dataset swapped. Each regional service therefore has its own persistent
cache volume and its own extract.

## 1. Why datasets are external

- PBF/XML extracts are large binary/text data, not source code.
- OSM data is © OpenStreetMap contributors (ODbL) — keeping it out of the repo
  avoids redistributing it inside the project and keeps the source tree small.
- Datasets change as OSM is edited; they are refreshed independently of code.

## 2. Where each dataset goes

```
osm/
├── README.md          ← this file (committed)
├── kerala.osm         ← Kerala (Idukki pilot region)   — NOT committed
├── vizag.osm          ← Vizag urban pilot              — NOT committed
├── assam.osm          ← Assam (Guwahati) pilot         — NOT committed
└── munnar.osm         ← legacy Munnar dev extract (kept for regression; not
                         used by the running services any more)
```

`.gitignore` ignores `/osm/*.osm` and `/osm/*.osm.pbf`.

## 3. Currently loaded datasets (real OSM data, 2026-09-04)

| Region | File | Coverage | Status |
|---|---|---|---|
| kerala | `kerala.osm` (22.7 MB) | **Idukki pilot region** ~38×47 km: 9.90–10.31°N, 76.88–77.26°E — covers **all** Kerala prototype habitations (Munnar Central, Adimali, Rajakkad, Kanthalloor, Marayoor) and all 3 candidate sites | `development` (prototype-area, not full-state) |
| vizag | `vizag.osm` (20.1 MB) | **Visakhapatnam urban pilot** ~39×33 km: 17.55–17.90°N, 83.10–83.45°E | `development` (prototype-area, not district/state) |
| assam | `assam.osm` | **Guwahati urban pilot** ~28×39 km: 26.05–26.30°N, 91.60–91.95°E | `development` (prototype-area, not state-wide) |

No Vizag or Assam habitation/candidate-site records exist in the seed yet, so
ID-based routing (`/routing/route/{hab}/{site}`) for those regions correctly
returns UNAVAILABLE (target not found / dataset gate). The datasets themselves
are validated with direct point-to-point routes — see §8.

## 4. How each dataset was obtained

All three were fetched from the **Overpass API** (`overpass-api.de`, retrying
`overpass.kumi.systems` / `overpass.private.coffee` / `overpass.osm.jp` when
busy) on 2026-09-04, using this query with the region's bbox (S,W,N,E):

```
[out:xml][timeout:900][maxsize:2000000000];
(
  way["highway"](S,W,N,E);
);
(._;>;);
out body;
```

| Region | Bbox (S,W,N,E) | highway ways | file size |
|---|---|---|---|
| kerala | 9.90,76.88,10.31,77.26 | 11,177 | 22.7 MB (255,518 nodes) |
| vizag | 17.55,83.10,17.90,83.45 | 31,087 | 20.1 MB (188,083 nodes) |
| assam | 26.05,91.60,26.30,91.95 | 14,808* | ~30 MB* |

Notes:

- Geofabrik publishes **no** India state extracts (verified 2026-09-04 — all
  state URLs return 404), so Overpass was the practical legitimate source.
  India-wide PBFs were deliberately avoided (1.7 GB).
- Overpass output must be **reordered** so `<node>` elements precede `<way>`
  elements before GraphHopper will import it:
  `python tools/reorder_osm.py osm/<region>.osm` (in `backend/` venv context).
- The extracts contain highway ways and their nodes only (no relations), which
  is sufficient for car routing in the pilot areas.

## 5. How to verify a dataset

1. File exists and parses:
   `python -c "import xml.etree.ElementTree as ET; ET.parse('osm/vizag.osm'); print('ok')"`
2. Way/node counts: `grep -c "<way " osm/vizag.osm` etc.
3. GraphHopper imports it (§6) and `/info` reports `profiles: [car]`.
4. A real route succeeds (§8). A healthy `/info` with the wrong PBF is NOT
   sufficient — always route two known places inside the bbox.

## 6. How to start GraphHopper (all three regions)

```bash
docker compose up -d --build graphhopper-kerala graphhopper-vizag graphhopper-assam
```

Each service imports its own dataset on first start (this takes minutes and is
recorded in `docker logs sentinel_graphhopper_vizag`). The prepared graph is
cached in the service's named volume, so restarts are fast afterwards.

First import / rebuild of caches (delete caches first, then start):

```bash
docker compose down
docker volume rm sentinel_ai_ghdata_kerala sentinel_ai_ghdata_vizag sentinel_ai_ghdata_assam
docker compose up -d --build graphhopper-kerala graphhopper-vizag graphhopper-assam
```

(Volume names may be prefixed by the compose project name.)

## 7. Health checks

```bash
curl -s http://localhost:8989/info    # kerala  (car profile expected)
curl -s http://localhost:8991/info    # vizag
curl -s http://localhost:8992/info    # assam
curl -s http://localhost:8000/api/v1/data-sources/health   # backend view
curl -s http://localhost:8000/api/v1/routing/regions       # region config
```

## 8. Testing a route

Via the app (Kerala, Munnar Central → Site A):

```bash
curl -s "http://localhost:8000/api/v1/routing/route/munnar-central/site-a"
curl -s "http://localhost:8000/api/v1/routing/comparison/munnar-central"
```

Dataset-level validation (any region, raw GraphHopper, points must lie inside
the region's bbox and near roads; GraphHopper's point order is **lat,lon**):

```bash
curl -sG "http://localhost:8991/route" \
  --data-urlencode "profile=car" \
  --data-urlencode "point=17.7384,83.3007" \
  --data-urlencode "point=17.7700,83.3600" \
  --data-urlencode "points_encoded=false" --data-urlencode "instructions=false"
```

Known-good sample pairs used by the test suite:

| Region | From (lat,lon) | To (lat,lon) |
|---|---|---|
| kerala | 10.0889, 77.0595 (Munnar Central) | 10.1123, 77.0812 (Site A) |
| vizag | 17.7384, 83.3007 | 17.7700, 83.3600 |
| assam | 26.1830, 91.7510 | 26.1600, 91.7000 |

## 9. How to add / update a region

1. Obtain the extract (§4) and place it at `osm/<key>.osm`.
2. Add/update the `graphhopper-<key>` service in `docker-compose.yml`
   (bind-mount the file at `/data/region.osm`, give it its own cache volume,
   pick a host port, set `GRAPHHOPPER_<KEY>_URL` on the backend service).
3. Update `backend/app/core/regions.py`: `dataset_status`, `dataset_label`,
   and `dataset_coverage` (the actual extract bounds — used as the routing
   gate so the system never claims coverage beyond the loaded file).
4. Rebuild the cache volume (§6) and validate (§5–§8).

## 10. Coverage limitations (be honest)

- **Kerala** covers the Idukki pilot region only — the area of the current
  prototype habitations. Not full-state: routing between, say, Trivandrum and
  Kozhikode is UNAVAILABLE (not fabricated).
- **Vizag** covers the Visakhapatnam urban area only (no district hinterland).
- **Assam** covers the Guwahati urban area only (no Assam habitation records
  exist in the seed yet; this dataset makes the pilot area routable when they
  are added).
- OSM is community data: completeness/quality varies; single `car` profile; no
  live traffic, no official emergency travel times. Travel-time estimates are
  DERIVED, never authoritative.

## 11. Licensing / attribution

- OSM data: © OpenStreetMap contributors, licensed under the **ODbL**
  (https://www.openstreetmap.org/copyright). Extracts were obtained from the
  public Overpass API; the app must retain OSM attribution wherever routing
  output is shown.
- Routing output is **derived** from OSM road data (classification: DERIVED).
- GraphHopper is **Apache 2.0** (https://github.com/graphhopper/graphhopper).
- GraphHopper 8.0 runs on Java 21 (`graphhopper/Dockerfile`), engine-only
  image; road data is mounted externally, never baked in.
- Routing ETAs are estimates and must never be presented as official emergency
  travel time.
