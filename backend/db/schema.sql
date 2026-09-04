-- Sentinel AI — PostGIS Schema
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
    hazard_type VARCHAR(64) NOT NULL,  -- LANDSLIDE, FLOOD, CLOUDBURST, EROSION
    intensity FLOAT NOT NULL,           -- 0-100
    data_type VARCHAR(32) NOT NULL,     -- OBSERVED, DERIVED, ESTIMATED
    source TEXT,
    description TEXT,
    assessed_at TIMESTAMPTZ DEFAULT NOW(),
    data_status VARCHAR(32) DEFAULT 'DEMO'
);

-- Risk scores
CREATE TABLE IF NOT EXISTS risk_scores (
    id SERIAL PRIMARY KEY,
    habitation_id VARCHAR(64) REFERENCES habitations(id),
    current_score FLOAT NOT NULL,
    baseline_score FLOAT NOT NULL,
    hazard_component FLOAT,
    exposure_component FLOAT,
    vulnerability_component FLOAT,
    interaction_component FLOAT,
    data_type VARCHAR(32) DEFAULT 'DERIVED',
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    data_status VARCHAR(32) DEFAULT 'DEMO'
);

-- Vulnerability assessments
CREATE TABLE IF NOT EXISTS vulnerability_assessments (
    id SERIAL PRIMARY KEY,
    habitation_id VARCHAR(64) REFERENCES habitations(id),
    overall_score FLOAT NOT NULL,
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
    priority VARCHAR(32) NOT NULL,  -- IMMEDIATE, SHORT-TERM, MEDIUM-TERM
    rpi_score FLOAT NOT NULL,
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
    suitability_score FLOAT,
    safe_capacity INTEGER,
    safety_score FLOAT,
    infrastructure_score FLOAT,
    accessibility_score FLOAT,
    water_score FLOAT,
    healthcare_score FLOAT,
    education_score FLOAT,
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
    c_safe INTEGER,  -- min of all dimensions
    bottleneck VARCHAR(64),
    data_type VARCHAR(32) DEFAULT 'DERIVED',
    assessed_at TIMESTAMPTZ DEFAULT NOW(),
    data_status VARCHAR(32) DEFAULT 'DEMO'
);

-- Spatial indexes
CREATE INDEX IF NOT EXISTS idx_habitations_geom ON habitations USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_habitations_district ON habitations(district_id);
CREATE INDEX IF NOT EXISTS idx_candidate_sites_geom ON candidate_sites USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_risk_scores_habitation ON risk_scores(habitation_id);
CREATE INDEX IF NOT EXISTS idx_hazard_assessments_habitation ON hazard_assessments(habitation_id);
