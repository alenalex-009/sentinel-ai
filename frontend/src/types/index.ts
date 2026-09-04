// Sentinel AI — Core TypeScript types

export type DataType = 'OBSERVED' | 'DERIVED' | 'ESTIMATED' | 'SIMULATED' | 'RECOMMENDATION'
export type DataStatus = 'LIVE' | 'DEMO' | 'SIMULATION' | 'UNAVAILABLE' | 'STALE'
export type Priority = 'IMMEDIATE' | 'SHORT-TERM' | 'MEDIUM-TERM' | 'MONITOR' | 'NONE'
export type HazardType = 'LANDSLIDE' | 'FLOOD' | 'CLOUDBURST' | 'EROSION' | 'MULTI_HAZARD'
export type VulnerabilityLevel = 'VERY HIGH' | 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY LOW'

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

export interface CandidateSite {
  id: string
  name: string
  distance_km: number
  suitability_score: number
  safe_capacity: number
  safety_score: number
  infrastructure_score: number
  accessibility_score: number
  water_score: number
  healthcare_score: number
  education_score: number
  latitude: number
  longitude: number
  data_type: DataType
}

export interface CapacityAssessment {
  site_id: string
  c_safe: number
  bottleneck: string
  dimensions: Record<string, number>
  required_population: number
  surplus_deficit: number
  data_type: DataType
  data_status: DataStatus
}

export interface DecisionTraceStep {
  step: number
  node: string
  value: string
  data_type: DataType
}
