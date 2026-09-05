# Sentinel AI

**SIH PS 26191** — Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations

Organization: Ministry of Home Affairs | NDRF, DM Division | Theme: Disaster Management

---

## What is Sentinel AI?

Sentinel AI is a GIS-first disaster decision-support platform for proactive disaster-risk management and relocation planning. It connects authoritative hazard data to evidence-based relocation recommendations for vulnerable habitations.

Pilot: **Idukki, Kerala** | Demo habitation: **Munnar Central, Ward 04, Devikulam Taluk**

---

## Quick Start (Docker)

Everything runs containerized — the only prerequisite is Docker Desktop (or
Docker Engine + Compose v2). PostgreSQL/PostGIS is initialised automatically
from `backend/db/schema.sql` + `seed.sql` on first start.

### Option A — Core demo (no road routing; fastest)

```bash
git clone https://github.com/alenalex-009/sentinel-ai.git
cd sentinel-ai

docker compose up -d --build db backend frontend
```

The app runs fully (map, risk, relocation, data-status). Routing endpoints
report `UNAVAILABLE` per region until datasets are added — never fabricated.

### Option B — Full stack with GraphHopper road routing

Routing artifacts are external and gitignored by design (large binaries). Fetch
them once, then start everything:

```bash
# 1) GraphHopper 8.0 engine jar (pinned version, not committed)
curl -L -o graphhopper/graphhopper-web-8.0.jar \
  https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/8.0/graphhopper-web-8.0.jar

# 2) Regional OSM road extracts (Kerala / Vizag / Assam — Overpass API).
#    Linux / macOS / Git Bash:  bash osm/download_regions.sh
#    See osm/README.md for bboxes, verification, and manual downloads.

# 3) Start every service (db, backend, frontend, graphhopper-kerala/-vizag/-assam)
docker compose up -d --build
```

Services:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Database: localhost:5432

---

## Development Setup

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Database
```bash
# Requires PostgreSQL + PostGIS
createdb sentinel_ai
psql sentinel_ai < backend/db/schema.sql
psql sentinel_ai < backend/db/seed.sql
```

---

## Architecture

```
sentinel-ai/
├── frontend/          # React + TypeScript + Vite + Tailwind + MapLibre GL
├── backend/           # Python + FastAPI + PostGIS
├── docker-compose.yml
└── instructions.md    # Implementation contract
```

---

## Map Stack

- **Basemap**: OpenStreetMap raster tiles (keyless)
- **Hazard overlays**: Bhuvan / ISRO WMS (historical event overlay)
- **Road routing**: self-hosted GraphHopper 8.0 (Kerala / Vizag / Assam extracts)
- **GIS library**: MapLibre GL
- **Fallback**: Local GeoJSON seed data (DEMO MODE)

---

## Data Sources

ISRO/NRSC · Bhuvan · Survey of India · IMD · CWC · Census of India · KSDMA · data.gov.in · UDISE+

---

## Important

Sentinel AI is **decision support**, not an autonomous government authority. All outputs are clearly labelled: OBSERVED / DERIVED / ESTIMATED / SIMULATED / RECOMMENDATION.

See [instructions.md](./instructions.md) for the full implementation contract.
