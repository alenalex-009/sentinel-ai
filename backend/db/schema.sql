-- Sentinel AI — PostGIS Schema v2 (Phase 3)
-- SIH PS 26191 | Pilot: Idukki, Kerala

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Districts
CREATE TABLE IF NOT EXISTS districts (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    state VARCHAR(128) NOT NULL,
    geom GEOMETRY(MULTIPOLYGON, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Habitations
CREATE TABLE IF NOT EXISTS habitations (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    ward VARCHAR(64),
    taluk VARCHAR(128),
    district_id VARCHAR(64) REFERENCES districts(id),
    state VARCHAR(128),
    population INTEGER,
    households INTEGER,
    area_ha FLOAT,
    geom GEOMETRY(POINT, 4326),
    boundary GEOMETRY(POLYGON, 4326),
    data_status VARCHAR(32) DEFAULT 'DEMO',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Hazard assessments
CREATE TABLE IF NOT EXISTS hazard_assessments (
    id SERIAL PRIMARY KEY,
    habitation_id VARCHAR(64) REFERENCES habitations(id),
    hazard_type VARCHAR(64) NOT NULL,
    intensity FLOAT NOT NULL CHECK (intensity >= 0 AND intensity <= 100),
    data_type VARCHAR(32) NOT NULL,
    source TEXT,
    description TEXT,
    assessed_at TIMESTAMPTZ DEFAULT NOW(),
    data_status VARCHAR(32) DEFAULT 'DEMO'
);

-- Risk scores
-- Each dynamic liquidity recompute inserts a NEW row (ledger): baseline_score is
-- retained per row so recompute history is an auditable timeline of risk deltas.
CREATE TABLE IF NOT EXISTS risk_scores (
    id SERIAL PRIMARY KEY,
    habitation_id VARCHAR(64) REFERENCES habitations(id),
    current_score FLOAT NOT NULL CHECK (current_score >= 0 AND current_score <= 100),
    baseline_score FLOAT NOT NULL CHECK (baseline_score >= 0 AND baseline_score <= 100),
    hazard_component FLOAT,
    exposure_component FLOAT,
    vulnerability_component FLOAT,
    interaction_component FLOAT,
    event_escalation_component FLOAT,       -- Slice 3: live escalation term
    live_inputs JSONB,                      -- Slice 3: inputs that fed the recompute
    data_type VARCHAR(32) DEFAULT 'DERIVED',
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    data_status VARCHAR(32) DEFAULT 'DEMO'
);
ALTER TABLE risk_scores
    ADD COLUMN IF NOT EXISTS event_escalation_component FLOAT;
ALTER TABLE risk_scores
    ADD COLUMN IF NOT EXISTS live_inputs JSONB;
CREATE INDEX IF NOT EXISTS idx_risk_scores_computed ON risk_scores(habitation_id, computed_at DESC);

-- Vulnerability assessments
CREATE TABLE IF NOT EXISTS vulnerability_assessments (
    id SERIAL PRIMARY KEY,
    habitation_id VARCHAR(64) REFERENCES habitations(id),
    overall_score FLOAT NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),
    demographic_score FLOAT,
    socioeconomic_score FLOAT,
    infrastructure_score FLOAT,
    accessibility_score FLOAT,
    data_type VARCHAR(32) DEFAULT 'DERIVED',
    assessed_at TIMESTAMPTZ DEFAULT NOW(),
    data_status VARCHAR(32) DEFAULT 'DEMO'
);

-- Relocation priorities
CREATE TABLE IF NOT EXISTS relocation_priorities (
    id SERIAL PRIMARY KEY,
    habitation_id VARCHAR(64) REFERENCES habitations(id),
    priority VARCHAR(32) NOT NULL,
    rpi_score FLOAT NOT NULL CHECK (rpi_score >= 0 AND rpi_score <= 100),
    risk_component FLOAT,
    vulnerability_component FLOAT,
    exposed_population_component FLOAT,
    historical_impact_component FLOAT,
    urgency_component FLOAT,
    data_type VARCHAR(32) DEFAULT 'RECOMMENDATION',
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    data_status VARCHAR(32) DEFAULT 'DEMO'
);

-- Candidate relocation sites
CREATE TABLE IF NOT EXISTS candidate_sites (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(256) NOT NULL,
    district_id VARCHAR(64) REFERENCES districts(id),
    geom GEOMETRY(POINT, 4326),
    boundary GEOMETRY(POLYGON, 4326),
    suitability_score FLOAT CHECK (suitability_score >= 0 AND suitability_score <= 100),
    safe_capacity INTEGER CHECK (safe_capacity >= 0),
    safety_score FLOAT,
    infrastructure_score FLOAT,
    accessibility_score FLOAT,
    water_score FLOAT,
    healthcare_score FLOAT,
    education_score FLOAT,
    hard_constraints_passed BOOLEAN DEFAULT TRUE,
    data_type VARCHAR(32) DEFAULT 'DERIVED',
    data_status VARCHAR(32) DEFAULT 'DEMO',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Carrying capacity assessments
CREATE TABLE IF NOT EXISTS capacity_assessments (
    id SERIAL PRIMARY KEY,
    site_id VARCHAR(64) REFERENCES candidate_sites(id),
    land_capacity INTEGER,
    water_capacity INTEGER,
    healthcare_capacity INTEGER,
    education_capacity INTEGER,
    infrastructure_capacity INTEGER,
    environment_capacity INTEGER,
    c_safe INTEGER,
    bottleneck VARCHAR(64),
    data_type VARCHAR(32) DEFAULT 'DERIVED',
    assessed_at TIMESTAMPTZ DEFAULT NOW(),
    data_status VARCHAR(32) DEFAULT 'DEMO'
);

-- Optimization results (stored for audit trail)
CREATE TABLE IF NOT EXISTS optimization_results (
    id SERIAL PRIMARY KEY,
    habitation_id VARCHAR(64) REFERENCES habitations(id),
    status VARCHAR(32) NOT NULL,
    total_demand INTEGER,
    total_allocated INTEGER,
    unallocated INTEGER,
    objective_value FLOAT,
    solver_note TEXT,
    data_type VARCHAR(32) DEFAULT 'RECOMMENDATION',
    data_status VARCHAR(32) DEFAULT 'DEMO',
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────────────────────
-- Real-time weather (WeatherAPI.com) — Slice 1 (P0)
-- data_status on ingest rows is always OBSERVED (as-served by the provider);
-- the 72h-rolling rainfall aggregates carry data_type DERIVED.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS weather_observations (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(64) NOT NULL,          -- e.g. munnar (region key + place)
    region VARCHAR(32) NOT NULL,              -- kerala | vizag | assam
    observed_at TIMESTAMPTZ NOT NULL,
    temp_c FLOAT,
    humidity_pct FLOAT,
    wind_kph FLOAT,
    gust_kph FLOAT,
    precip_mm_1h FLOAT,
    totalprecip_mm_24h FLOAT,                 -- provider's rolling 24h gauge
    rainfall_mm_24h FLOAT,                    -- derived rolling window
    rainfall_mm_72h FLOAT,                    -- DERIVED rolling 72h window
    condition_text VARCHAR(128),
    source VARCHAR(64) DEFAULT 'weatherapi',
    data_type VARCHAR(32) DEFAULT 'OBSERVED',
    data_status VARCHAR(32) DEFAULT 'OBSERVED',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (station_id, observed_at)
);

CREATE TABLE IF NOT EXISTS weather_forecasts (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(64) NOT NULL,
    region VARCHAR(32) NOT NULL,
    forecast_for TIMESTAMPTZ NOT NULL,        -- period start (date at 00:00 IST)
    rainfall_mm_expected FLOAT,               -- totalprecip_mm for the day
    max_temp_c FLOAT,
    min_temp_c FLOAT,
    avg_humidity_pct FLOAT,
    chance_of_rain_pct FLOAT,
    condition_text VARCHAR(128),
    source VARCHAR(64) DEFAULT 'weatherapi',
    data_type VARCHAR(32) DEFAULT 'OBSERVED',
    data_status VARCHAR(32) DEFAULT 'OBSERVED',
    issued_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (station_id, forecast_for)
);

-- Historical + current earthquakes (USGS catalog, India subset) — Slice 1
-- USGS as-served fields kept raw; geom is the authoritative point geometry.
CREATE TABLE IF NOT EXISTS earthquake_events (
    usgs_id VARCHAR(128) PRIMARY KEY,         -- USGS event id (unique)
    occurred_at TIMESTAMPTZ NOT NULL,
    magnitude FLOAT,
    mag_type VARCHAR(16),
    depth_km FLOAT,
    place TEXT,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    geom GEOMETRY(POINT, 4326),
    nst INTEGER,
    gap FLOAT,
    dmin FLOAT,
    rms FLOAT,
    horizontal_error FLOAT,
    depth_error FLOAT,
    mag_error FLOAT,
    mag_nst INTEGER,
    status VARCHAR(32),
    location_source VARCHAR(32),
    mag_source VARCHAR(32),
    reviewed BOOLEAN,
    source VARCHAR(32) DEFAULT 'usgs',
    data_type VARCHAR(32) DEFAULT 'OBSERVED',
    data_status VARCHAR(32) DEFAULT 'OBSERVED',
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Spatial indexes
CREATE INDEX IF NOT EXISTS idx_habitations_geom ON habitations USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_habitations_district ON habitations(district_id);
CREATE INDEX IF NOT EXISTS idx_candidate_sites_geom ON candidate_sites USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_risk_scores_habitation ON risk_scores(habitation_id);
CREATE INDEX IF NOT EXISTS idx_hazard_assessments_habitation ON hazard_assessments(habitation_id);
CREATE INDEX IF NOT EXISTS idx_vuln_habitation ON vulnerability_assessments(habitation_id);
CREATE INDEX IF NOT EXISTS idx_rp_habitation ON relocation_priorities(habitation_id);
CREATE INDEX IF NOT EXISTS idx_weather_obs_station_time ON weather_observations(station_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_weather_fc_station_time ON weather_forecasts(station_id, forecast_for);
CREATE INDEX IF NOT EXISTS idx_earthquake_time ON earthquake_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_earthquake_mag ON earthquake_events(magnitude);
CREATE INDEX IF NOT EXISTS idx_earthquake_geom ON earthquake_events USING GIST(geom);

-- Active hazard events (Slice 2) — the "current operational picture". Events
-- are activated from LIVE sources only: rainfall exceedance (DERIVED from live
-- weather observations) and recent earthquakes at/above the alert magnitude
-- (OBSERVED). event_id is deterministic (rain-{station}-{ts}, quake-{usgs_id})
-- so recomputes upsert in place. Severity ladder + formulas are defined in
-- app/services/hazard_service.py. geom is a circular buffer polygon (WGS84)
-- whose radius grows with severity; it represents estimated exposure reach,
-- NOT a surveyed footprint.
CREATE TABLE IF NOT EXISTS hazard_events (
    event_id VARCHAR(64) PRIMARY KEY,
    hazard_type VARCHAR(64) NOT NULL,
    severity_level VARCHAR(32) NOT NULL,
    severity_score FLOAT NOT NULL CHECK (severity_score >= 0 AND severity_score <= 100),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    geom GEOMETRY(POLYGON, 4326),
    centroid_lat FLOAT NOT NULL,
    centroid_lon FLOAT NOT NULL,
    buffer_radius_km FLOAT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    last_confirmed_at TIMESTAMPTZ DEFAULT NOW(),
    source TEXT,
    data_type VARCHAR(32) NOT NULL DEFAULT 'DERIVED',
    data_status VARCHAR(32) DEFAULT 'LIVE',
    event_meta JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_hazard_events_active ON hazard_events(active);
CREATE INDEX IF NOT EXISTS idx_hazard_events_geom ON hazard_events USING GIST(geom);

-- Safe-zone candidates (Slice 4) — dynamically discovered + scored candidate
-- sites for relocation, produced by the safe-zone engine over real spatial
-- tables (district point, earthquake_events, hazard_events, candidate_sites).
-- source distinguishes pre-screened demo sites ('existing') from grid-
-- discovered candidates ('discovered'). hard_constraints records the
-- per-constraint pass/fail evidence; constraint_pass is the conjunction.
CREATE TABLE IF NOT EXISTS safe_zone_candidates (
    id VARCHAR(64) PRIMARY KEY,
    district_id VARCHAR(64) REFERENCES districts(id),
    name VARCHAR(256),
    source VARCHAR(32) NOT NULL DEFAULT 'discovered'
        CHECK (source IN ('existing', 'discovered')),
    geom GEOMETRY(POINT, 4326),
    suitability_score FLOAT CHECK (suitability_score >= 0 AND suitability_score <= 100),
    safety_score FLOAT CHECK (safety_score >= 0 AND safety_score <= 100),
    estimated_capacity INTEGER CHECK (estimated_capacity >= 0),
    hard_constraints JSONB,
    constraint_pass BOOLEAN NOT NULL DEFAULT TRUE,
    constraint_evidence TEXT,
    base_site_id VARCHAR(64),
    data_type VARCHAR(32) NOT NULL DEFAULT 'DERIVED',
    data_status VARCHAR(32) NOT NULL DEFAULT 'DEMO',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_safe_zone_candidates_district ON safe_zone_candidates(district_id);
CREATE INDEX IF NOT EXISTS idx_safe_zone_candidates_geom ON safe_zone_candidates USING GIST(geom);

-- Relocation plan lifecycle (Slice 5)
CREATE TABLE IF NOT EXISTS relocation_plans (
    id SERIAL PRIMARY KEY,
    district_id VARCHAR(64) REFERENCES districts(id),
    name VARCHAR(256) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved', 'executing', 'completed', 'cancelled')),
    description TEXT,
    total_demand INTEGER,
    total_allocated INTEGER,
    unallocated INTEGER,
    optimizer_status VARCHAR(32),
    created_by VARCHAR(64),
    approved_by VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    data_status VARCHAR(32) DEFAULT 'DEMO',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_relocation_plans_district ON relocation_plans(district_id);
CREATE INDEX IF NOT EXISTS idx_relocation_plans_status ON relocation_plans(status);

CREATE TABLE IF NOT EXISTS relocation_assignments (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER REFERENCES relocation_plans(id) ON DELETE CASCADE,
    habitation_id VARCHAR(64) REFERENCES habitations(id),
    site_id VARCHAR(64) REFERENCES candidate_sites(id),
    allocated_population INTEGER,
    distance_km FLOAT,
    utilization_pct FLOAT,
    surplus_after INTEGER,
    status VARCHAR(32) DEFAULT 'assigned'
        CHECK (status IN ('assigned', 'moved', 'completed', 'cancelled')),
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    moved_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    data_status VARCHAR(32) DEFAULT 'RECOMMENDATION'
);
CREATE INDEX IF NOT EXISTS idx_relocation_assignments_plan ON relocation_assignments(plan_id);
CREATE INDEX IF NOT EXISTS idx_relocation_assignments_habitation ON relocation_assignments(habitation_id);

-- ────────────────────────────────────────────────────────────────────────
-- Apply schema changes to PostGIS (idempotent). Run once per environment.
-- ────────────────────────────────────────────────────────────────────────
