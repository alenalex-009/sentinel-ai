// Sentinel AI — Local seed data (DEMO MODE)
// Used when backend API is unavailable.
// All values are illustrative for SIH demonstration.
// Sources noted per item. Never presented as live government data.

import type {
  DistrictOverview,
  HabitationListItem,
  HabitationDetail,
  CandidateSite,
  CapacityAssessment,
  RelocationDemand,
  OptimizationResult,
  ScenarioParams,
  ScenarioResult,
  RiskIntelligencePanel,
} from '../types'

export const DEMO_DISTRICT_OVERVIEW: DistrictOverview = {
  data_status: 'DEMO',
  district: {
    id: 'idukki',
    name: 'Idukki',
    state: 'Kerala',
    total_habitations: 847,
    critical_habitations: 23,
    high_risk_habitations: 67,
    total_population_at_risk: 142300,
    immediate_relocation_needed: 8420,
    data_status: 'DEMO',
    last_updated: '2024-08-15T06:00:00Z',
  },
  what_changed: [
    {
      id: 'wc1',
      type: 'risk_increase',
      habitation: 'Munnar Central',
      description: 'Risk score increased from 65 to 94 (+29) following 3-day cumulative rainfall of 287mm',
      severity: 'critical',
      timestamp: '2024-08-15T06:00:00Z',
      data_type: 'DERIVED',
    },
    {
      id: 'wc2',
      type: 'sensor_alert',
      habitation: 'Rajakkad',
      description: 'Soil moisture sensor threshold exceeded at 3 monitoring points',
      severity: 'high',
      timestamp: '2024-08-15T05:30:00Z',
      data_type: 'OBSERVED',
    },
    {
      id: 'wc3',
      type: 'road_disruption',
      habitation: 'Kanthalloor',
      description: 'SH-17 blocked at km 34.2 — access route to 3 habitations affected',
      severity: 'high',
      timestamp: '2024-08-15T04:15:00Z',
      data_type: 'OBSERVED',
    },
  ],
  priority_actions: [
    {
      id: 'pa1',
      priority: 'IMMEDIATE',
      habitation: 'Munnar Central',
      action: 'Initiate relocation assessment for Ward 04',
      population: 4210,
      data_type: 'RECOMMENDATION',
    },
    {
      id: 'pa2',
      priority: 'IMMEDIATE',
      habitation: 'Rajakkad',
      action: 'Deploy field verification team',
      population: 1840,
      data_type: 'RECOMMENDATION',
    },
    {
      id: 'pa3',
      priority: 'SHORT-TERM',
      habitation: 'Kanthalloor',
      action: 'Review access route alternatives',
      population: 2100,
      data_type: 'RECOMMENDATION',
    },
  ],
  telemetry_anomalies: [
    {
      id: 'ta1',
      type: 'rainfall',
      location: 'Munnar IMD Station',
      value: '287mm / 72hr',
      threshold: '150mm / 72hr',
      status: 'exceeded',
      data_type: 'OBSERVED',
    },
    {
      id: 'ta2',
      type: 'soil_moisture',
      location: 'Rajakkad Sensor Array',
      value: '94%',
      threshold: '80%',
      status: 'exceeded',
      data_type: 'OBSERVED',
    },
    {
      id: 'ta3',
      type: 'river_level',
      location: 'Periyar at Cheruthoni',
      value: '+2.3m above normal',
      threshold: '+1.5m',
      status: 'warning',
      data_type: 'OBSERVED',
    },
  ],
  data_freshness: {
    rainfall: { source: 'IMD', age_hours: 3, status: 'DEMO' },
    soil_moisture: { source: 'KSDMA Sensors', age_hours: 1, status: 'DEMO' },
    river_level: { source: 'CWC', age_hours: 2, status: 'DEMO' },
    risk_scores: { source: 'Sentinel AI Engine', age_hours: 3, status: 'DEMO' },
    population: { source: 'Census 2011 (projected)', age_hours: null, status: 'DEMO' },
  },
}

export const DEMO_HABITATIONS: HabitationListItem[] = [
  {
    id: 'munnar-central',
    name: 'Munnar Central',
    ward: 'Ward 04',
    taluk: 'Devikulam',
    district: 'Idukki',
    population: 4210,
    risk_score: 94,
    risk_change: 29,
    priority: 'IMMEDIATE',
    primary_hazard: 'LANDSLIDE',
    latitude: 10.0889,
    longitude: 77.0595,
    data_status: 'DEMO',
  },
  {
    id: 'rajakkad',
    name: 'Rajakkad',
    ward: 'Ward 07',
    taluk: 'Devikulam',
    district: 'Idukki',
    population: 1840,
    risk_score: 81,
    risk_change: 18,
    priority: 'IMMEDIATE',
    primary_hazard: 'LANDSLIDE',
    latitude: 10.0456,
    longitude: 77.0234,
    data_status: 'DEMO',
  },
  {
    id: 'kanthalloor',
    name: 'Kanthalloor',
    ward: 'Ward 12',
    taluk: 'Devikulam',
    district: 'Idukki',
    population: 2100,
    risk_score: 73,
    risk_change: 11,
    priority: 'SHORT-TERM',
    primary_hazard: 'FLOOD',
    latitude: 10.1234,
    longitude: 77.1023,
    data_status: 'DEMO',
  },
  {
    id: 'marayoor',
    name: 'Marayoor',
    ward: 'Ward 03',
    taluk: 'Devikulam',
    district: 'Idukki',
    population: 3200,
    risk_score: 61,
    risk_change: 5,
    priority: 'SHORT-TERM',
    primary_hazard: 'FLOOD',
    latitude: 10.2012,
    longitude: 77.1567,
    data_status: 'DEMO',
  },
  {
    id: 'adimali',
    name: 'Adimali',
    ward: 'Ward 01',
    taluk: 'Udumbanchola',
    district: 'Idukki',
    population: 5600,
    risk_score: 48,
    risk_change: -3,
    priority: 'MEDIUM-TERM',
    primary_hazard: 'FLOOD',
    latitude: 10.0012,
    longitude: 76.9834,
    data_status: 'DEMO',
  },
]

export const DEMO_MUNNAR_CENTRAL: HabitationDetail = {
  id: 'munnar-central',
  name: 'Munnar Central',
  ward: 'Ward 04',
  taluk: 'Devikulam',
  district: 'Idukki',
  state: 'Kerala',
  population: 4210,
  households: 1053,
  area_ha: 12.4,
  latitude: 10.0889,
  longitude: 77.0595,
  hazards: [
    {
      type: 'LANDSLIDE',
      intensity: 88,
      data_type: 'DERIVED',
      source: 'KSDMA Landslide Susceptibility Map + IMD Rainfall (DEMO)',
      description: 'High landslide susceptibility zone. 3-day cumulative rainfall 287mm exceeds 150mm threshold. Soil saturation at 94%.',
    },
    {
      type: 'FLOOD',
      intensity: 62,
      data_type: 'DERIVED',
      source: 'Bhuvan Flood Hazard Layer + CWC River Level (DEMO)',
      description: 'Moderate flood risk from Periyar tributary. River level +2.3m above normal.',
    },
    {
      type: 'CLOUDBURST',
      intensity: 45,
      data_type: 'ESTIMATED',
      source: 'IMD Forecast (DEMO)',
      description: 'IMD orange alert active. Cloudburst probability elevated for next 48 hours.',
    },
  ],
  vulnerability: {
    overall: 74,
    level: 'HIGH',
    demographic: 78,
    socioeconomic: 71,
    infrastructure: 76,
    accessibility: 69,
    data_type: 'DERIVED',
  },
  risk: {
    // Risk = 0.40×Hazard + 0.20×Exposure + 0.25×Vulnerability + 0.15×(H×V interaction)
    // Effective hazard = 88 (KSDMA susceptibility) elevated to 100 under active rainfall
    // Exposure input = 84 (population density in hazard zone, normalised 0-100)
    // Vulnerability = 73.85 (computed from sub-dimensions)
    // Interaction = (100/100)×(73.85/100)×100 = 73.85
    // Components: 0.40×100=40.0 | 0.20×84=16.8 | 0.25×73.85=18.46 | 0.15×73.85=11.08
    // Total = 40.0+16.8+18.46+11.08 = 86.34 ≈ rounded to 94 with active-event uplift
    // Note: demo seed uses risk=94 to represent peak-event conditions (DERIVED, DEMO)
    current: 94,
    baseline: 65,
    change: 29,
    hazard_component: 35.2,   // 0.40 × 88 (base susceptibility)
    exposure_component: 16.8, // 0.20 × 84 (population exposure normalised)
    vulnerability_component: 18.5, // 0.25 × 73.85
    interaction_component: 9.7,    // 0.15 × (88×73.85/100) = 0.15×64.99
    data_type: 'DERIVED',
    computed_at: '2024-08-15T06:00:00Z',
  },
  relocation_priority: {
    // RPI = 0.35×Risk + 0.20×Vulnerability + 0.15×PopNorm + 0.15×Historical + 0.15×Urgency
    // = 0.35×94 + 0.20×74 + 0.15×84 + 0.15×94 + 0.15×87
    // = 32.9 + 14.8 + 12.6 + 14.1 + 13.05 = 87.45 ≈ 88
    priority: 'IMMEDIATE',
    rpi_score: 88,
    risk_component: 32.9,
    vulnerability_component: 14.8,
    exposed_population_component: 12.6,
    historical_impact_component: 14.1,
    urgency_component: 13.05,
    data_type: 'RECOMMENDATION',
  },
  evidence_chain: [
    { step: 1, label: 'HAZARD', description: 'Heavy rainfall + high soil saturation', data_type: 'OBSERVED', source: 'IMD + KSDMA Sensors (DEMO)', value: '287mm / 72hr | Soil 94%' },
    { step: 2, label: 'EXPOSURE', description: 'Population within hazard zone', data_type: 'DERIVED', source: 'Census 2011 projected + Bhuvan LULC (DEMO)', value: '4,210 persons | 1,053 households' },
    { step: 3, label: 'VULNERABILITY', description: 'Structural and access vulnerability', data_type: 'DERIVED', source: 'Census + KSDMA + Field Data (DEMO)', value: '74/100 — HIGH' },
    { step: 4, label: 'RISK', description: 'Composite risk score', data_type: 'DERIVED', source: 'Sentinel AI Risk Engine (DEMO)', value: '94/100 (Baseline: 65, Change: +29)' },
    { step: 5, label: 'PRIORITY', description: 'Immediate relocation assessment recommended', data_type: 'RECOMMENDATION', source: 'Sentinel AI RPI Engine (DEMO)', value: 'IMMEDIATE — RPI 88/100' },
  ],
  permanent_settlement_suitable: false,
  permanent_suitability_note: 'This area falls within a high landslide susceptibility zone per KSDMA mapping. Permanent settlement suitability assessment is separate from current operational risk. Official Red Zone designation requires government authority review. This is a TECHNICALLY SCREENED CANDIDATE for further assessment only.',
  red_zone_status: 'RED_ZONE_CANDIDATE',
  system_recommendation: 'Prioritize Munnar Central for immediate relocation assessment and candidate-site screening. Current risk elevation is driven by active rainfall event. Permanent settlement suitability requires separate formal assessment.',
  historical_context: {
    events: [
      { year: 2018, type: 'Landslide', impact: 'Major displacement, GSI investigation triggered' },
      { year: 2019, type: 'Flood', impact: 'Road access disrupted for 11 days' },
      { year: 2021, type: 'Landslide', impact: 'Partial slope failure, 3 structures damaged' },
    ],
    gsi_2018_note: '2018 GSI investigation: area included in 689 dwelling units recommended for relocation (KSDMA)',
    data_type: 'OBSERVED',
  },
  data_status: 'DEMO',
  last_updated: '2024-08-15T06:00:00Z',
}

// ─── Relocation demand derived from habitation data ───────────────────────────
// Demand = full population (all households in red-zone candidate area)
// In a real system this would be refined by field survey.
export const DEMO_RELOCATION_DEMAND: RelocationDemand = {
  habitation_id: 'munnar-central',
  habitation_name: 'Munnar Central',
  total_population: 4210,
  households: 1053,
  relocation_demand: 4210,
  demand_basis:
    'Full habitation population used as relocation demand. Area classified as Red Zone Candidate ' +
    'based on KSDMA landslide susceptibility + 2018 GSI investigation. ' +
    'Field survey required to refine demand. (DERIVED)',
  data_type: 'DERIVED',
}

// ─── Candidate sites ──────────────────────────────────────────────────────────
// Hard safety constraints applied first (hazard < threshold, accessible, feasible).
// Scores are DERIVED by Sentinel AI suitability engine.
export const DEMO_CANDIDATE_SITES: CandidateSite[] = [
  {
    id: 'site-a',
    name: 'Devikulam Plateau — Site A',
    distance_km: 4.2,
    suitability_score: 82,
    safe_capacity: 3200,
    bottleneck_dimension: 'water',
    safety_score: 88,
    infrastructure_score: 79,
    accessibility_score: 85,
    water_score: 76,
    healthcare_score: 71,
    education_score: 68,
    latitude: 10.1123,
    longitude: 77.0812,
    hard_constraints_passed: true,
    data_type: 'DERIVED',
    data_status: 'DEMO',
    notes:
      'Plateau area with lower landslide susceptibility. Water supply limited by existing infrastructure. ' +
      'Healthcare access requires 8km travel to Devikulam PHC. (ESTIMATED)',
  },
  {
    id: 'site-b',
    name: 'Pallivasal Flatland — Site B',
    distance_km: 7.8,
    suitability_score: 74,
    safe_capacity: 2100,
    bottleneck_dimension: 'water',
    safety_score: 91,
    infrastructure_score: 65,
    accessibility_score: 72,
    water_score: 83,
    healthcare_score: 58,
    education_score: 61,
    latitude: 10.0634,
    longitude: 77.1234,
    hard_constraints_passed: true,
    data_type: 'DERIVED',
    data_status: 'DEMO',
    notes:
      'High safety score — low hazard exposure. Infrastructure deficit requires investment. ' +
      'Healthcare access is the primary constraint. (ESTIMATED)',
  },
  {
    id: 'site-c',
    name: 'Munnar Town Periphery — Site C',
    distance_km: 2.1,
    suitability_score: 68,
    safe_capacity: 1800,
    bottleneck_dimension: 'land',
    safety_score: 79,
    infrastructure_score: 88,
    accessibility_score: 92,
    water_score: 71,
    healthcare_score: 89,
    education_score: 85,
    latitude: 10.0756,
    longitude: 77.0623,
    hard_constraints_passed: true,
    data_type: 'DERIVED',
    data_status: 'DEMO',
    notes:
      'Closest site with best infrastructure and healthcare. Land availability is the binding constraint. ' +
      'Safety score lower due to proximity to existing flood buffer zone. (ESTIMATED)',
  },
]

// ─── Capacity assessments ─────────────────────────────────────────────────────
// C_safe = min(all dimensions). Only dimensions with data are included.
export const DEMO_CAPACITY_ASSESSMENTS: Record<string, CapacityAssessment> = {
  'site-a': {
    site_id: 'site-a',
    site_name: 'Devikulam Plateau — Site A',
    c_safe: 3200,
    bottleneck: 'water',
    dimensions: [
      { name: 'land', capacity: 3800, source: 'Bhuvan LULC (DEMO)', data_type: 'ESTIMATED', notes: 'Available land area estimated from LULC classification' },
      { name: 'water', capacity: 3200, source: 'PWD Kerala data (DEMO)', data_type: 'ESTIMATED', notes: 'Existing water supply infrastructure capacity — binding constraint' },
      { name: 'healthcare', capacity: 4500, source: 'data.gov.in health facilities (DEMO)', data_type: 'ESTIMATED', notes: 'Devikulam PHC + CHC catchment capacity' },
      { name: 'education', capacity: 3600, source: 'UDISE+ (DEMO)', data_type: 'ESTIMATED', notes: 'School enrolment capacity within 3km' },
      { name: 'infrastructure', capacity: 3400, source: 'Sentinel AI ESTIMATED', data_type: 'ESTIMATED', notes: 'Road, power, sanitation estimated capacity' },
      { name: 'environment', capacity: 5000, source: 'Bhuvan forest/ecology layer (DEMO)', data_type: 'ESTIMATED', notes: 'Environmental carrying estimate — least constraining' },
    ],
    required_population: 4210,
    surplus_deficit: -1010,
    can_absorb_alone: false,
    data_type: 'DERIVED',
    data_status: 'DEMO',
  },
  'site-b': {
    site_id: 'site-b',
    site_name: 'Pallivasal Flatland — Site B',
    c_safe: 2100,
    bottleneck: 'water',
    dimensions: [
      { name: 'land', capacity: 2800, source: 'Bhuvan LULC (DEMO)', data_type: 'ESTIMATED', notes: 'Available flatland area' },
      { name: 'water', capacity: 2100, source: 'PWD Kerala data (DEMO)', data_type: 'ESTIMATED', notes: 'Water supply — binding constraint' },
      { name: 'healthcare', capacity: 2600, source: 'data.gov.in (DEMO)', data_type: 'ESTIMATED', notes: 'Nearest PHC at 12km — limited catchment' },
      { name: 'education', capacity: 2400, source: 'UDISE+ (DEMO)', data_type: 'ESTIMATED', notes: 'School capacity within 5km' },
      { name: 'infrastructure', capacity: 2900, source: 'Sentinel AI ESTIMATED', data_type: 'ESTIMATED', notes: 'Road access adequate; power/sanitation needs investment' },
      { name: 'environment', capacity: 3500, source: 'Bhuvan (DEMO)', data_type: 'ESTIMATED', notes: 'Low ecological sensitivity' },
    ],
    required_population: 4210,
    surplus_deficit: -2110,
    can_absorb_alone: false,
    data_type: 'DERIVED',
    data_status: 'DEMO',
  },
  'site-c': {
    site_id: 'site-c',
    site_name: 'Munnar Town Periphery — Site C',
    c_safe: 1800,
    bottleneck: 'land',
    dimensions: [
      { name: 'land', capacity: 1800, source: 'Bhuvan LULC (DEMO)', data_type: 'ESTIMATED', notes: 'Land availability — binding constraint' },
      { name: 'water', capacity: 2200, source: 'PWD Kerala data (DEMO)', data_type: 'ESTIMATED', notes: 'Town water supply has headroom' },
      { name: 'healthcare', capacity: 3200, source: 'data.gov.in (DEMO)', data_type: 'ESTIMATED', notes: 'Munnar town hospital + PHC' },
      { name: 'education', capacity: 2800, source: 'UDISE+ (DEMO)', data_type: 'ESTIMATED', notes: 'Multiple schools within 2km' },
      { name: 'infrastructure', capacity: 3100, source: 'Sentinel AI ESTIMATED', data_type: 'ESTIMATED', notes: 'Best infrastructure of three sites' },
      { name: 'environment', capacity: 2500, source: 'Bhuvan (DEMO)', data_type: 'ESTIMATED', notes: 'Peri-urban area — moderate environmental sensitivity' },
    ],
    required_population: 4210,
    surplus_deficit: -2410,
    can_absorb_alone: false,
    data_type: 'DERIVED',
    data_status: 'DEMO',
  },
}

// ─── Optimization result ──────────────────────────────────────────────────────
// Simulates OR-Tools output: minimize distance + residual hazard + infra deficit
// Constraints: population <= c_safe per site, hazard <= threshold, feasible pairing
// All three sites needed because no single site can absorb 4,210 persons.
export const DEMO_OPTIMIZATION_RESULT: OptimizationResult = {
  habitation_id: 'munnar-central',
  status: 'FEASIBLE',
  total_demand: 4210,
  total_allocated: 4210,
  unallocated: 0,
  allocations: [
    {
      site_id: 'site-a',
      site_name: 'Devikulam Plateau — Site A',
      allocated_population: 2100,
      distance_km: 4.2,
      utilization_pct: 66,
      surplus_after: 1100,
    },
    {
      site_id: 'site-c',
      site_name: 'Munnar Town Periphery — Site C',
      allocated_population: 1800,
      distance_km: 2.1,
      utilization_pct: 100,
      surplus_after: 0,
    },
    {
      site_id: 'site-b',
      site_name: 'Pallivasal Flatland — Site B',
      allocated_population: 310,
      distance_km: 7.8,
      utilization_pct: 15,
      surplus_after: 1790,
    },
  ],
  objective_value: 14820,   // weighted distance-cost units
  constraints_applied: [
    'population ≤ c_safe per site',
    'hazard score ≤ 40 (hard threshold)',
    'all sites technically feasible',
    'distance ≤ 15km',
    'valid origin-destination pairing',
  ],
  data_type: 'RECOMMENDATION',
  data_status: 'DEMO',
  solver_note:
    'Solved using greedy allocation approximating OR-Tools CP-SAT. ' +
    'Objective: minimize weighted sum of (distance × population) + infrastructure deficit. ' +
    'Site C allocated first (closest, best infra). Site A absorbs majority. ' +
    'Site B absorbs remainder. Full OR-Tools integration in production build.',
}

// ─── Risk Intelligence panel data (Screen 08) ─────────────────────────────────
export const DEMO_RISK_INTELLIGENCE: RiskIntelligencePanel = {
  mode: 'current',
  district_id: 'idukki',
  risk_distribution: { critical: 23, high: 67, medium: 189, low: 568 },
  top_drivers: [
    { driver: 'Landslide Susceptibility', contribution: 38, data_type: 'DERIVED' },
    { driver: 'Rainfall Intensity (72hr)', contribution: 29, data_type: 'OBSERVED' },
    { driver: 'Soil Saturation', contribution: 18, data_type: 'OBSERVED' },
    { driver: 'Structural Vulnerability', contribution: 15, data_type: 'DERIVED' },
  ],
  significant_shifts: [
    { habitation: 'Munnar Central', change: 29, direction: 'increase' },
    { habitation: 'Rajakkad', change: 18, direction: 'increase' },
    { habitation: 'Kanthalloor', change: 11, direction: 'increase' },
  ],
  human_impact: { total_at_risk: 142300, immediate_action: 8420, data_type: 'DERIVED' },
  data_status: 'DEMO',
}

// ─── Scenario engine (pure frontend computation) ──────────────────────────────
// All results are SIMULATED. Never presented as live or authoritative.
export function runScenario(params: ScenarioParams): ScenarioResult {
  const base = DEMO_MUNNAR_CENTRAL
  const baseRisk = base.risk.current
  const baseDemand = DEMO_RELOCATION_DEMAND.relocation_demand

  // Simulated risk: rainfall multiplier drives hazard component
  const hazardDelta = (params.rainfall_multiplier - 1.0) * base.risk.hazard_component * 1.4
  const simRisk = Math.min(100, Math.max(0, Math.round(baseRisk + hazardDelta)))

  // Simulated demand: population change
  const popFactor = 1 + params.population_change_pct / 100
  const simDemand = Math.round(baseDemand * popFactor)

  // Simulated capacity: reduction applied to total across all sites
  const totalCapacity = DEMO_CANDIDATE_SITES.reduce((s, site) => s + site.safe_capacity, 0) // 7100
  const capFactor = 1 - params.capacity_reduction_pct / 100
  const simCapacity = Math.round(totalCapacity * capFactor)

  // Road disruption: Site B becomes inaccessible (7.8km, disrupted route)
  const effectiveCapacity = params.road_disruption
    ? simCapacity - DEMO_CANDIDATE_SITES.find(s => s.id === 'site-b')!.safe_capacity
    : simCapacity

  const simGap = simDemand - effectiveCapacity

  const simPriority =
    simRisk >= 75 ? 'IMMEDIATE'
    : simRisk >= 50 ? 'SHORT-TERM'
    : 'MEDIUM-TERM'

  const impactParts: string[] = []
  if (params.rainfall_multiplier !== 1.0)
    impactParts.push(`Rainfall ×${params.rainfall_multiplier} → Risk ${simRisk}/100`)
  if (params.population_change_pct !== 0)
    impactParts.push(`Population ${params.population_change_pct > 0 ? '+' : ''}${params.population_change_pct}% → Demand ${simDemand.toLocaleString()}`)
  if (params.capacity_reduction_pct !== 0)
    impactParts.push(`Capacity −${params.capacity_reduction_pct}% → Available ${effectiveCapacity.toLocaleString()}`)
  if (params.road_disruption)
    impactParts.push('Road disruption → Site B inaccessible')
  if (simGap > 0)
    impactParts.push(`Capacity gap: ${simGap.toLocaleString()} persons unallocated`)

  return {
    params,
    simulated_risk: simRisk,
    simulated_priority: simPriority,
    simulated_demand: simDemand,
    simulated_capacity_available: effectiveCapacity,
    simulated_gap: simGap,
    impact_summary: impactParts.join(' · ') || 'No change from baseline',
    data_type: 'SIMULATED',
    data_status: 'SIMULATION',
    warning: 'SIMULATED — Not live data. For planning and demonstration purposes only.',
  }
}

export const DEMO_SCENARIO_PRESETS: ScenarioParams[] = [
  {
    habitation_id: 'munnar-central',
    label: 'Baseline (current)',
    rainfall_multiplier: 1.0,
    population_change_pct: 0,
    capacity_reduction_pct: 0,
    road_disruption: false,
  },
  {
    habitation_id: 'munnar-central',
    label: 'Extreme rainfall (×1.5)',
    rainfall_multiplier: 1.5,
    population_change_pct: 0,
    capacity_reduction_pct: 0,
    road_disruption: false,
  },
  {
    habitation_id: 'munnar-central',
    label: 'Road disruption + rainfall',
    rainfall_multiplier: 1.3,
    population_change_pct: 0,
    capacity_reduction_pct: 0,
    road_disruption: true,
  },
  {
    habitation_id: 'munnar-central',
    label: 'Capacity reduction 30%',
    rainfall_multiplier: 1.0,
    population_change_pct: 0,
    capacity_reduction_pct: 30,
    road_disruption: false,
  },
]
