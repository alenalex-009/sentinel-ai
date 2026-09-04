# Sentinel AI

**SIH PS 26191** — Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations

Organization: Ministry of Home Affairs | NDRF, DM Division | Theme: Disaster Management

---

## What is Sentinel AI?

Sentinel AI is a GIS-first disaster decision-support platform for proactive disaster-risk management and relocation planning. It connects authoritative hazard data to evidence-based relocation recommendations for vulnerable habitations.

Pilot: **Idukki, Kerala** | Demo habitation: **Munnar Central, Ward 04, Devikulam Taluk**

---

## Quick Start

```bash
# Clone the repository
git clone https://gitlab.com/sentinel-ai3/sentinel-ai.git
cd sentinel-ai

# Start all services
docker compose up --build
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

- **Basemap**: CARTO Dark Matter (keyless)
- **Hazard overlays**: Bhuvan / ISRO WMS
- **GIS library**: MapLibre GL
- **Fallback**: Local GeoJSON seed data (DEMO MODE)

---

## Data Sources

ISRO/NRSC · Bhuvan · Survey of India · IMD · CWC · Census of India · KSDMA · data.gov.in · UDISE+

---

## Important

Sentinel AI is **decision support**, not an autonomous government authority. All outputs are clearly labelled: OBSERVED / DERIVED / ESTIMATED / SIMULATED / RECOMMENDATION.

See [instructions.md](./instructions.md) for the full implementation contract.
