// Sentinel AI — Core TypeScript types
// Phase 2: extended for full pipeline

export type DataType = 'OBSERVED' | 'DERIVED' | 'ESTIMATED' | 'SIMULATED' | 'RECOMMENDATION'
export type DataStatus = 'LIVE' | 'DEMO' | 'SIMULATION' | 'UNAVAILABLE' | 'STALE'
export type Priority = 'IMMEDIATE' | 'SHORT-TERM' | 'MEDIUM-TERM' | 'MONITOR' | 'NONE'
export type HazardType = 'LANDSLIDE' | 'FLOOD' | 'CLOUDBURST' | 'EROSION' | 'MULTI_HAZARD'
export type VulnerabilityLevel = 'VERY HIGH' | 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY LOW'
export type RedZoneStatus =
  | 'RED_ZONE_CANDIDATE'   // system-derived, not official
  | 'UNDER_ASSESSMENT'     // formal process initiated
  | 'NOT_RECOMMENDED'      // system does not flag
  | 'DATA_INSUFFICIENT'    // cannot determine

export interface HazardInfo {
  type: HazardType
  intensity: number
  data_type: DataType
  source: string
  description: string
}

export interface VulnerabilityBreakdown {
  overall: number
  level: VulnerabilityLevel
  demographic: number
  socioeconomic: number
  infrastructure: number
  accessibility: number
  data_type: DataType
}

export interface RiskScore {
  current: number
  baseline: number
  change: number
  hazard_component: number
  exposure_component: number
  vulnerability_component: number
  interaction_component: number
  data_type: DataType
  computed_at: string
}

export interface RelocationPriority {
  priority: Priority
  rpi_score: number
  risk_component: number
  vulnerability_component: number
  exposed_population_component: number
  historical_impact_component: number
  urgency_component: number
  data_type: DataType
}

export interface EvidenceItem {
  step: number
  label: string
  description: string
  data_type: DataType
  source?: string
  value?: string
}

export interface HabitationListItem {
  id: string
  name: string
  ward: string
  taluk: string
  district: string
  population: number
  risk_score: number
  risk_change: number
  priority: Priority
  primary_hazard: HazardType
  latitude: number
  longitude: number
  data_status: DataStatus
}

export interface HabitationDetail {
  id: string
  name: string
  ward: string
  taluk: string
  district: string
  state: string
  population: number
  households: number
  area_ha: number
  latitude: number
  longitude: number
  hazards: HazardInfo[]
  vulnerability: VulnerabilityBreakdown
  risk: RiskScore
  relocation_priority: RelocationPriority
  evidence_chain: EvidenceItem[]
  permanent_settlement_suitable: boolean
  permanent_suitability_note: string
  red_zone_status: RedZoneStatus
  system_recommendation: string
  historical_context: {
    events: Array<{ year: number; type: string; impact: string }>
    gsi_2018_note: string
    data_type: DataType
  }
  data_status: DataStatus
  last_updated: string
}

export interface DistrictOverview {
  data_status: DataStatus
  district: {
    id: string
    name: string
    state: string
    total_habitations: number
    critical_habitations: number
    high_risk_habitations: number
    total_population_at_risk: number
    immediate_relocation_needed: number
    data_status: DataStatus
    last_updated: string
  }
  what_changed: Array<{
    id: string
    type: string
    habitation: string
    description: string
    severity: string
    timestamp: string
    data_type: DataType
  }>
  priority_actions: Array<{
    id: string
    priority: Priority
    habitation: string
    action: string
    population: number
    data_type: DataType
  }>
  telemetry_anomalies: Array<{
    id: string
    type: string
    location: string
    value: string
    threshold: string
    status: string
    data_type: DataType
  }>
  data_freshness: Record<string, {
    source: string
    age_hours: number | null
    status: DataStatus
  }>
}

// ─── Candidate Sites & Capacity ───────────────────────────────────────────────

export interface CandidateSite {
  id: string
  name: string
  distance_km: number
  suitability_score: number       // 0-100, DERIVED
  safe_capacity: number           // C_safe = min(all dimensions)
  bottleneck_dimension: string    // which dimension limits capacity
  safety_score: number
  infrastructure_score: number
  accessibility_score: number
  water_score: number
  healthcare_score: number
  education_score: number
  latitude: number
  longitude: number
  hard_constraints_passed: boolean
  data_type: DataType
  data_status: DataStatus
  notes: string
}

export interface CapacityDimension {
  name: string
  capacity: number
  source: string
  data_type: DataType
  notes: string
}

export interface CapacityAssessment {
  site_id: string
  site_name: string
  c_safe: number                  // min of all dimensions
  bottleneck: string
  dimensions: CapacityDimension[]
  required_population: number
  surplus_deficit: number         // c_safe - required_population
  can_absorb_alone: boolean
  data_type: DataType
  data_status: DataStatus
}

// ─── Relocation Pipeline ──────────────────────────────────────────────────────

export interface RelocationDemand {
  habitation_id: string
  habitation_name: string
  total_population: number
  households: number
  relocation_demand: number       // population requiring relocation
  demand_basis: string            // explanation of how demand was derived
  data_type: DataType
}

export interface AllocationEntry {
  site_id: string
  site_name: string
  allocated_population: number
  distance_km: number
  utilization_pct: number         // allocated / c_safe
  surplus_after: number
}

export interface OptimizationResult {
  habitation_id: string
  status: 'FEASIBLE' | 'INFEASIBLE' | 'PARTIAL'
  total_demand: number
  total_allocated: number
  unallocated: number
  allocations: AllocationEntry[]
  objective_value: number         // minimized cost/distance
  constraints_applied: string[]
  data_type: DataType             // always RECOMMENDATION
  data_status: DataStatus         // always DEMO or SIMULATION
  solver_note: string
}

// ─── Scenarios ────────────────────────────────────────────────────────────────

export interface ScenarioParams {
  habitation_id: string
  label: string
  rainfall_multiplier: number     // 1.0 = baseline
  population_change_pct: number   // 0 = no change
  capacity_reduction_pct: number  // 0 = no reduction
  road_disruption: boolean
}

export interface ScenarioResult {
  params: ScenarioParams
  simulated_risk: number
  simulated_priority: Priority
  simulated_demand: number
  simulated_capacity_available: number
  simulated_gap: number
  impact_summary: string
  data_type: 'SIMULATED'
  data_status: 'SIMULATION'
  warning: string
}

// ─── Risk Intelligence (Screen 08) ────────────────────────────────────────────

export interface RiskIntelligencePanel {
  mode: 'current' | 'baseline' | 'change'
  district_id: string
  risk_distribution: { critical: number; high: number; medium: number; low: number }
  top_drivers: Array<{ driver: string; contribution: number; data_type: DataType }>
  significant_shifts: Array<{ habitation: string; change: number; direction: 'increase' | 'decrease' }>
  human_impact: { total_at_risk: number; immediate_action: number; data_type: DataType }
  data_status: DataStatus
}

export interface DecisionTraceStep {
  step: number
  node: string
  value: string
  data_type: DataType
}
