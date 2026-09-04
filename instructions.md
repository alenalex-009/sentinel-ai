# Sentinel AI — Implementation Contract

## SIH PS 26191
**Intelligent Identification of Hazard-Based Red Zones, Carrying Capacity Assessment, and Immediate Relocation Needs for Vulnerable Habitations**

Organization: Ministry of Home Affairs  
Department: National Disaster Response Force (NDRF), DM Division  
Theme: Disaster Management

---

## 1. Product Definition

Sentinel AI is a GIS-first disaster decision-support platform.

It answers:
- Which habitations are at risk, and why?
- Who is affected, and who needs attention first?
- Where can they technically relocate?
- Can those sites support them?
- What plan should an authority review?

Pilot: **Idukki, Kerala**  
Main demonstration habitation: **Munnar Central, Ward 04, Devikulam Taluk**

---

## 2. Non-Negotiable Trust Rules

- Sentinel AI is decision support, NOT an autonomous government authority.
- Never claim to issue evacuation/relocation orders.
- AI is an explanation layer, NOT the safety-critical decision engine.
- Deterministic GIS/math/optimization engines produce decisions.
- Operational/current risk is separate from permanent settlement suitability.
- A temporary rainfall spike must NOT automatically become a permanent Red Zone.
- Candidate locations are "Technically Screened Candidates" unless official approval exists.
- Never fabricate live government data, approvals, sources, confidence or results.
- Clearly distinguish: OBSERVED / DERIVED / ESTIMATED / SIMULATED / RECOMMENDATION.
- If data is unavailable, show UNAVAILABLE / STALE / DEMO / SIMULATION status.
- Prototype weights are configurable baselines, not official government formulas.

---

## 3. Tech Stack

### Frontend
- React + TypeScript + Vite
- Tailwind CSS
- MapLibre GL
- Recharts / ECharts

### Backend
- Python + FastAPI

### Database
- PostgreSQL + PostGIS

### GIS
- GeoPandas, Shapely, Rasterio, GDAL

### Optimization
- Google OR-Tools

### Map Stack
- Basemap: CARTO Dark Matter (keyless)
- Hazard overlays: Bhuvan / ISRO WMS
- GIS library: MapLibre GL
- Fallback: Local GeoJSON seed data (DEMO MODE label)

Use a modular monolith. Do not over-engineer with Kubernetes/microservices.

---

## 4. UI Direction

The product must feel like: **Modern GIS + Emergency Operations Center + Decision Intelligence**

NOT: cyberpunk / sci-fi / gaming / cryptocurrency / generic AI chatbot.

### Use:
- Professional deep-slate dark theme
- Restrained semantic colors
- Readable typography
- High information density, low visual clutter
- Subtle borders
- Real GIS as a first-class element
- Contextual AI actions

### Avoid:
- Excessive neon/glow
- Decorative terrain
- Excessive cards/card nesting
- Tiny text
- Giant footers
- Excessive animations
- AI branding dominating the interface

### Layout
- One shared **68px global navigation rail** (left side)
- Authority navigation: Overview · Risk · Habitations · Priorities · Relocation · Scenarios · Reports · Data & Sources

---

## 5. Approved Screens

### Screen 01 — Command Overview
Purpose: 30-second district situational awareness.

Show:
- Idukki current status
- Critical/high-risk habitations count
- People at risk
- Relocation/capacity status
- What Changed?
- Priority actions
- Large central GIS map
- Telemetry anomalies
- Data freshness/provenance

GIS is the main visual element.

### Screen 08 — Risk & GIS Intelligence
Primary question: "Where is the risk, and how has it changed?"

Layout: GlobalNav → Layers & Filters → Large GIS workspace → Risk Intelligence panel

Controls: CURRENT / BASELINE / CHANGE

Layers: Hazards · Risk · Exposure · Context/Lifelines

Show:
- Current risk, baseline, change/delta
- Risk distribution
- Top drivers
- Significant shifts
- Human impact
- Freshness and confidence

Habitation popup (Munnar Central):
- Risk 94 | Change +29 | Primary hazard: Landslide
- Exposed population: 4,210
- [Investigate] button

### Screen 09 — Habitation Investigation
Primary question: "Why is this habitation critical, and what should we investigate next?"

Case: Munnar Central · Ward 04 · Devikulam Taluk · Idukki, Kerala

Show:
- Risk 94/100 | Baseline 65 | Change +29
- Population 4,210 | Vulnerability HIGH | Priority IMMEDIATE
- Local GIS: habitation boundary, debris/runout, flood buffer, road/lifeline disruption, muster point

Evidence chain:
1. HAZARD — Heavy rainfall + high soil saturation (OBSERVED)
2. EXPOSURE — Population exposed (DERIVED)
3. VULNERABILITY — Structural/access vulnerability (DERIVED)
4. RISK — 94/100 (DERIVED)
5. PRIORITY — Immediate relocation assessment (RECOMMENDATION)

Show: vulnerability dimensions, historical context, Evidence & Sources, operational risk, permanent settlement suitability (kept separate).

Recommendation: "Prioritize Munnar Central for immediate relocation assessment and candidate-site screening."

Actions: [REVIEW CANDIDATE SITES] [EXPLAIN THIS RISK]

### Screen 10 — Decision Intelligence
Primary question: "How did Sentinel AI reach this decision?"

Decision trace:
OBSERVED HAZARDS → EXPOSURE → VULNERABILITY → OPERATIONAL RISK → RELOCATION PRIORITY → SITE/CAPACITY CHECK → SYSTEM RECOMMENDATION

Supporting: Top Risk Drivers · Evidence & Sources · Decision Impact · System Recommendation · Explain This Decision

---

## 6. Core Models

### Risk Model (configurable baseline)
```
Risk = 0.40 × Hazard
     + 0.20 × Exposure
     + 0.25 × Vulnerability
     + 0.15 × (Hazard × Vulnerability Interaction)
```

### Vulnerability Dimensions
- Demographic: 30%
- Socioeconomic: 20%
- Infrastructure: 25%
- Accessibility: 25%

### Relocation Priority Index
```
RPI = 0.35 × Risk
    + 0.20 × Vulnerability
    + 0.15 × Exposed Population
    + 0.15 × Historical Impact
    + 0.15 × Urgency
```

Priority levels: IMMEDIATE / SHORT-TERM / MEDIUM-TERM

### Carrying Capacity
```
C_safe = min(land, water, healthcare, education, infrastructure, environment)
```
Only calculate dimensions supported by available data.

### Site Suitability
- Safety: 30%
- Capacity: 20%
- Infrastructure: 20%
- Accessibility: 15%
- Water/resources: 10%
- Environmental suitability: 5%

### Optimization (OR-Tools)
Minimize: distance/cost + residual hazard exposure + infrastructure deficit

Constraints:
- population ≤ safe capacity
- hazard ≤ hard threshold
- site technically feasible
- distance acceptable
- valid origin/destination pairing

---

## 7. First Implementation Priority — Vertical Slice

User must be able to:
1. Open Sentinel AI
2. Select Idukki
3. See the map
4. Search/select a habitation
5. See hazards
6. See population
7. See exposure/vulnerability
8. See risk
9. See risk drivers
10. See relocation priority

Then extend: Red-Zone/permanent suitability → candidate sites → capacity → relocation → optimization → dynamic data → scenarios → AI → reports.

---

## 8. Data Sources

| Source | Data |
|--------|------|
| ISRO/NRSC/NDEM | Hazard/risk zonation, damage assessment |
| Bhuvan | LULC, flood hazard, erosion, water bodies, WMS/WMTS |
| Survey of India | Administrative boundaries, DTM/elevation |
| IMD | Rainfall, weather, forecasts, warnings |
| CWC | Flood forecasting, river information |
| Census of India | Population, demographic indicators |
| KSDMA | Flood/landslide susceptibility, historical disaster data |
| data.gov.in | Infrastructure, hospital data |
| UDISE+ | School infrastructure |

Kerala evidence:
- 2018 GSI: 1,626 landslides; 689 dwelling units recommended for relocation
- 2019 KSDMA: 719 investigated sites; 411 recommended for relocation

---

## 9. Data Display Rules

- Always label: OBSERVED · DERIVED · ESTIMATED · SIMULATED · RECOMMENDATION
- Show data freshness and provenance on every panel
- If external API unavailable: show DEMO MODE or DATA UNAVAILABLE
- Never make simulated data look live
- Distinguish operational risk from permanent settlement suitability

---

## 10. Reusable Components Required

```
AppShell
GlobalNav
TopBar
MapContainer
RiskBadge
PriorityBadge
DataTypeBadge
FreshnessBadge
EvidencePanel
HabitationCard
CandidateSiteCard
CapacityBreakdown
DecisionTrace
ScenarioControl
AIExplanation
```

---

## 11. SIH Golden Demo Flow

Overview → Risk & GIS → Munnar Central → Habitation Investigation → Decision Intelligence → Priorities → Relocation Intelligence → Candidate Site → Suitability → Capacity → Relocation Planning → Scenario → Report → Data & Sources

Evaluator must clearly see:
SITUATION → RISK → WHY → PRIORITY → PERMANENT STATUS → SAFE CANDIDATES → CAPACITY → OPTIMIZATION → RELOCATION PLAN → WHAT-IF → AI EXPLANATION → HUMAN DECISION

---

## 12. Engineering Rules

- Before coding: inspect repository, read instructions.md, inspect existing code
- Preserve existing useful work
- Do not blindly replace the project
- Create reusable components and typed models
- Do not hardcode model values throughout UI components
- Handle: missing data, API failures, no candidate sites, capacity shortage, loading states, empty states, errors
- Check TypeScript/build/runtime errors after each major stage
