-- Sentinel AI — Seed Data (DEMO MODE)
-- Pilot: Idukki, Kerala
-- All data is illustrative for SIH demonstration purposes.
-- Sources: Census 2011, KSDMA, publicly available information.

-- District
INSERT INTO districts (id, name, state) VALUES
    ('idukki', 'Idukki', 'Kerala')
ON CONFLICT (id) DO NOTHING;

-- Habitations
INSERT INTO habitations (id, name, ward, taluk, district_id, state, population, households, area_ha, geom, data_status) VALUES
    ('munnar-central', 'Munnar Central', 'Ward 04', 'Devikulam', 'idukki', 'Kerala', 4210, 1053, 12.4,
     ST_SetSRID(ST_MakePoint(77.0595, 10.0889), 4326), 'DEMO'),
    ('rajakkad', 'Rajakkad', 'Ward 07', 'Devikulam', 'idukki', 'Kerala', 1840, 460, 6.8,
     ST_SetSRID(ST_MakePoint(77.0234, 10.0456), 4326), 'DEMO'),
    ('kanthalloor', 'Kanthalloor', 'Ward 12', 'Devikulam', 'idukki', 'Kerala', 2100, 525, 8.2,
     ST_SetSRID(ST_MakePoint(77.1023, 10.1234), 4326), 'DEMO'),
    ('marayoor', 'Marayoor', 'Ward 03', 'Devikulam', 'idukki', 'Kerala', 3200, 800, 15.6,
     ST_SetSRID(ST_MakePoint(77.1567, 10.2012), 4326), 'DEMO'),
    ('adimali', 'Adimali', 'Ward 01', 'Udumbanchola', 'idukki', 'Kerala', 5600, 1400, 22.1,
     ST_SetSRID(ST_MakePoint(76.9834, 10.0012), 4326), 'DEMO')
ON CONFLICT (id) DO NOTHING;

-- Risk scores
INSERT INTO risk_scores (habitation_id, current_score, baseline_score, hazard_component, exposure_component, vulnerability_component, interaction_component, data_status) VALUES
    ('munnar-central', 94, 65, 35.2, 16.8, 18.46, 9.75, 'DEMO'),
    ('rajakkad', 81, 63, 31.2, 14.4, 16.8, 8.1, 'DEMO'),
    ('kanthalloor', 73, 62, 27.4, 13.2, 15.6, 7.2, 'DEMO'),
    ('marayoor', 61, 56, 22.8, 11.6, 13.4, 6.1, 'DEMO'),
    ('adimali', 48, 51, 18.2, 9.8, 11.2, 5.1, 'DEMO')
ON CONFLICT DO NOTHING;

-- Candidate sites
INSERT INTO candidate_sites (id, name, district_id, geom, suitability_score, safe_capacity, safety_score, infrastructure_score, accessibility_score, water_score, healthcare_score, education_score, data_status) VALUES
    ('site-a', 'Devikulam Plateau Site A', 'idukki',
     ST_SetSRID(ST_MakePoint(77.0812, 10.1123), 4326),
     82, 3200, 88, 79, 85, 76, 71, 68, 'DEMO'),
    ('site-b', 'Pallivasal Flatland Site B', 'idukki',
     ST_SetSRID(ST_MakePoint(77.1234, 10.0634), 4326),
     74, 2100, 91, 65, 72, 83, 58, 61, 'DEMO'),
    ('site-c', 'Munnar Town Periphery Site C', 'idukki',
     ST_SetSRID(ST_MakePoint(77.0623, 10.0756), 4326),
     68, 1800, 79, 88, 92, 71, 89, 85, 'DEMO')
ON CONFLICT (id) DO NOTHING;

-- Capacity assessments
INSERT INTO capacity_assessments (site_id, land_capacity, water_capacity, healthcare_capacity, education_capacity, infrastructure_capacity, environment_capacity, c_safe, bottleneck, data_status) VALUES
    ('site-a', 3800, 3200, 4500, 3600, 3400, 5000, 3200, 'water', 'DEMO'),
    ('site-b', 2800, 2100, 2600, 2400, 2900, 3500, 2100, 'water', 'DEMO'),
    ('site-c', 1800, 2200, 3200, 2800, 3100, 2500, 1800, 'land', 'DEMO')
ON CONFLICT DO NOTHING;
