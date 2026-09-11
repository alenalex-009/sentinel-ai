// Sentinel AI — Core TypeScript types
// Phase 2: extended for full pipeline

export type DataType = 'OBSERVED' | 'DERIVED' | 'ESTIMATED' | 'SIMULATED' | 'RECOMMENDATION'
export type DataStatus = 'LIVE' | 'DEMO' | 'SIMULATION' | 'UNAVAILABLE' | 'STALE' | 'EMPTY'
export type Priority = 'IMMEDIATE' | 'SHORT-TERM' | 'MEDIUM-TERM' | 'MONITOR' | 'NONE'
export type HazardType = 'LANDSLIDE' | 'FLOOD' | 'CLOUDBURST' | 'EROSION' | 'MULTI_HAZARD' | 'EARTHQUAKE'
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
  // Deterministic event-escalation term: current = base components (sum of the
  // four above) + event_escalation_component, rounded. Only present on the
  // event-adjusted demo score (Munnar Central).
  event_escalation_component?: number
  risk_model_note?: string
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

// ─── Relocation plan lifecycle (Slice 5) ──────────────────────────────────────

export type RelocationPlanStatus =
  | 'draft'
  | 'approved'
  | 'executing'
  | 'completed'
  | 'cancelled'

export interface DistrictRelocationDemand {
  data_status: DataStatus
  district_id?: string
  total_demand: number
  demand_habitations?: number
  habitations: Array<{
    habitation_id: string
    name: string
    population: number
    current_score: number
    relocation_demand: number
  }>
  note?: string
}

export interface RelocationAssignment {
  id?: number
  plan_id?: number
  habitation_id: string | null
  site_id: string
  allocated_population: number
  distance_km: number
  utilization_pct: number
  surplus_after: number
  data_status?: DataStatus
}

export interface RelocationPlan {
  data_status: DataStatus
  plan_id?: number
  district_id?: string
  name?: string
  status: RelocationPlanStatus
  total_demand: number
  total_allocated: number
  unallocated: number
  optimizer_status?: string
  assignments: RelocationAssignment[]
  constraints_applied?: string[]
  solver_note?: string
  reason?: string
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

// ─── GIS / Spatial (Phase 3 — PostGIS geometry) ───────────────────────────────

export interface GeoJsonPointGeometry {
  type: 'Point'
  coordinates: [number, number] // [lon, lat], EPSG:4326
}

export interface GeoJsonPointFeature {
  type: 'Feature'
  geometry: GeoJsonPointGeometry
  properties: {
    id: string
    name?: string | null
    ward?: string | null
    taluk?: string | null
    population?: number | null
    households?: number | null
    risk_score?: number | null
    risk_change?: number | null
    priority?: string | null
    data_status?: string
    // candidate-site properties (when the feature is a site)
    suitability_score?: number | null
    safe_capacity?: number | null
    c_safe?: number | null
    bottleneck?: string | null
    hard_constraints_passed?: boolean | null
  }
}

export interface GeoJsonFeatureCollection {
  type: 'FeatureCollection'
  features: GeoJsonPointFeature[]
  data_status?: DataStatus
  district_id?: string
  _source?: string
  geometry_source?: string
  geometry_type?: string
  srid?: number
  note?: string
  approval_status_note?: string
}

// ── Active hazard events (Slice 2) ─────────────────────────────────────────

export type HazardSeverityLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE'

export interface HazardEventSourceBasis {
  data_status?: string
  reason?: string
  observations?: number
  recorded?: number
}

export interface HazardEvent {
  event_id: string
  hazard_type: HazardType
  severity_level: HazardSeverityLevel
  severity_label: string
  severity_score: number
  active: boolean
  started_at: string
  source: string
  data_type: DataType
  centroid_lat: number
  centroid_lon: number
  buffer_radius_km: number
  event_meta: Record<string, unknown>
}

export interface CurrentHazardsResponse {
  data_status: DataStatus
  reason?: string
  generated_at: string
  region: string
  ttl_seconds: number
  persisted?: boolean
  summary?: string
  source_basis?: {
    weather: HazardEventSourceBasis
    earthquakes: HazardEventSourceBasis
  }
  events: HazardEvent[]
  feature_collection: GeoJSON.FeatureCollection
}

export interface HazardDetailResponse {
  data_status: DataStatus
  reason?: string
  event: HazardEvent | null
  affected_habitations: {
    habitation_id: string
    name: string
    region: string
    latitude: number
    longitude: number
    exposure_intensity: number
    distance_km: number
    basis: { distance_decay: string; habitation_at_risk: boolean }
  }[]
  basis_note?: string
}

// ── Dynamic current risk (Slice 3) ────────────────────────────────────────

export interface RiskSourceBasis {
  data_status?: string
  reason?: string
  observations?: number
  events_considered?: number
}

export interface CurrentRiskBasis {
  weather: RiskSourceBasis
  hazard_events: RiskSourceBasis
  soil_saturation: RiskSourceBasis
  river_level: RiskSourceBasis
}

export interface DynamicRiskLiveInputs {
  station_id: string
  station_place?: string
  rainfall_mm_72h: number | null
  soil_saturation_pct: number | null
  river_level_anomaly_m: number | null
  hazard_intensity: number
  covering_event_ids: string[]
}

export interface CurrentRiskHabitation {
  id: string
  name: string
  population: number
  latitude: number
  longitude: number
  priority: Priority
  primary_hazard: HazardType
  baseline_score: number
  event_escalation: number
  escalation_weather: number | null
  escalation_hazard: number | null
  current_score: number
  current_score_rounded: number
  data_status: DataStatus
  data_type: DataType
  live_inputs: DynamicRiskLiveInputs | null
  equation?: string
}

export interface CurrentRiskResponse {
  data_status: DataStatus
  reason?: string
  district_id: string
  computed_at: string
  mode: string
  basis: CurrentRiskBasis
  note?: string
  persisted?: boolean
  live_habitations?: number
  habitations: CurrentRiskHabitation[]
}

export interface RiskDeltaPoint {
  computed_at: string
  current_score: number
  baseline_score: number
  event_escalation: number | null
}

export interface RiskTimelineResponse {
  data_status: DataStatus
  reason?: string
  habitation_id?: string
  points: RiskDeltaPoint[]
}

export interface SpatialDistance {
  habitation_id: string
  site_id: string
  distance_m: number
  distance_km: number
  unit: 'm'
  classification: DataType
  method: string
  distance_type: string
  source_geometry: string
  note: string
  data_status: DataStatus
  _source: string
}

export interface ProximateSiteResult {
  site_id: string
  site_name: string
  distance_m: number
  distance_km: number
  c_safe?: number | null
  bottleneck?: string | null
  within_radius: boolean
}

export interface SpatialProximity {
  habitation_id: string
  radius_m: number
  method: string
  threshold_note: string
  results: ProximateSiteResult[]
  data_status: DataStatus
  _source: string
}


// ─── Multi-engine road routing (Phase 5C) ─────────────────────────────

export type RoutingEngine = 'osrm' | 'graphhopper' | 'valhalla'

export interface EngineStatus {
  tier: 'fast' | 'balanced' | 'advanced'
  ok: boolean
  detail: string
  url: string | null
}

export interface RoutingEnginesStatus {
  region: string
  engines: Record<RoutingEngine, EngineStatus>
  note: string
  checked_at: string
}

export interface RouteInfo {
  distance_m: number
  distance_km: number
  duration_min: number
  duration_s: number
  unit: string
  time_unit: string
  classification: DataType
  source: string
  method: string
  cache: boolean
  computed_at: string
  points_count: number
}

export interface EngineRouteResult {
  habitation_id: string
  site_id: string
  engine: RoutingEngine
  engine_tier: 'fast' | 'balanced' | 'advanced'
  status: 'OK' | 'UNAVAILABLE'
  route: RouteInfo | null
  route_geojson: GeoJSON.Feature | null
  reason?: string
  classification: DataType
  source: string
  method: string
  region: {
    key: string | null
    display: string | null
    dataset_status: string | null
    dataset: string | null
  }
  note: string
  computed_at: string
  _source: string
}

// ─── Phase 5B — Derived screening zones + historical periods ────────────────

export type ScreeningZoneStatus = 'red' | 'yellow' | 'green'

export interface ScreeningZoneFeature {
  type: 'Feature'
  geometry: GeoJSON.Polygon
  properties: {
    site_id: string
    site_name: string
    status: ScreeningZoneStatus
    label: string
    classification: DataType
    derived: boolean
    authoritative: boolean
    method: string
    radius_km: number
    basis: {
      suitability_score?: number | null
      safety_score?: number | null
      bottleneck?: string | null
      c_safe?: number | null
    }
    data_status?: string
    _source?: string
  }
}

export interface ScreeningZonesResponse {
  type: 'FeatureCollection'
  features: ScreeningZoneFeature[]
  district_id?: string
  data_status?: DataStatus
  classification?: DataType
  _source?: string
  geometry_source?: string
  geometry_type?: string
  srid?: number
  status_counts: { red: number; yellow: number; green: number }
  zone_meaning_note?: string
  note?: string
}

export interface HistoricalSpatialLayer {
  type: 'wms'
  layer: string
  url: string
  attribution: string
}

export interface HistoricalPeriod {
  period: string
  label: string
  availability: 'current' | 'live_overlay' | 'context_only'
  classification: DataType
  source?: string
  spatial_layer: HistoricalSpatialLayer | null
  note: string
}

export interface HistoricalPeriodsResponse {
  region: string
  status: 'AVAILABLE' | 'UNAVAILABLE'
  periods: HistoricalPeriod[]
  reason?: string
  note?: string
}

// ─── Safe-zone candidates (Slice 4) ─────────────────────────────────────────

export type SafeZoneStatus = 'green' | 'yellow' | 'red'

export interface SafeZoneCandidate {
  id: string
  district_id: string
  lat: number
  lon: number
  source: 'discovered' | 'existing'
  status: SafeZoneStatus
  suitability_score: number | null
  safety_score: number | null
  estimated_capacity?: number | null
  constraint_pass: boolean
  fault_km: number | null
  nearest_hazard_km: number | null
  hazard_id: string | null
  slope_pct: number | null
  land_use: string | null
  water_km: number | null
  hazard_intensity: number
  max_intensity: number
  data_status: DataStatus
}

export interface SafeZoneDiscoveryRequest {
  district_id: string
  dry_run?: boolean
}

export interface SafeZoneDiscoveryResponse {
  data_status: DataStatus
  district_id: string
  geometry_source: string
  generated_at: string
  constraint_note: string
  sources_used: string[]
  thresholds: Record<string, number>
  grid_notes: string[]
  candidates: SafeZoneCandidate[]
  candidates_count: number
  persisted: boolean
}

export interface SafeZoneCandidateFeature {
  type: 'Feature'
  geometry: GeoJSON.Point
  properties: SafeZoneCandidate & {
    name?: string | null
    color: string
  }
}

export interface SafeZonesResponse {
  type: 'FeatureCollection'
  features: SafeZoneCandidateFeature[]
  district_id?: string
  data_status?: DataStatus
  geometry_source?: string
  geometry_type?: string
  time_to_live_s?: number
  empty_reason?: string
  status_counts: { green: number; yellow: number; red: number }
  note?: string
}

// ── OpenStreetMap layers (Phase 6 — Overpass provider) ──────────────────────
export type OSMFeatureCategory = 'roads' | 'buildings' | 'facilities' | 'water'

export interface OSMFeatureProperties {
  osm_type: string
  osm_id: number
  name?: string | null
  kind?: string
  category?: OSMFeatureCategory
  highway?: string
  building?: string
  amenity?: string
  [key: string]: unknown
}

export interface OSMFeature {
  type: 'Feature'
  geometry: GeoJSON.Geometry
  properties: OSMFeatureProperties
}

export interface OSMLayerResponse {
  type: 'FeatureCollection'
  features: OSMFeature[]
  category?: OSMFeatureCategory
  bbox?: number[]
  source?: string
  fetched_at?: string
  cache?: boolean
  data_status?: DataStatus
  count?: number
  persisted?: boolean
  region?: { key?: string | null; display?: string | null }
  feature_collection?: { type: 'FeatureCollection'; features: OSMFeature[] }
  empty_reason?: string
}

export interface OSMStatusResponse {
  provider: string
  url: string
  reachable: boolean
  detail: string
  cache_entries: number
  cache_ttl_s: number
  checked_at: string
}

// ── Hazard-aware routing + alternatives / isochrones / matrix (Phase 6) ─────
export interface HazardExposure {
  event_id: string
  hazard_type: string
  severity_level: string
  severity_score: number
  buffer_radius_km: number
  inside_km: number
  fraction: number
  weight: number
  contribution: number
}

export interface HazardAnalysis {
  route_risk_score: number | null
  risk_label: string | null
  method: string
  exposures: HazardExposure[]
  events_evaluated?: number
  hazard_empty?: boolean
  reason?: string
}

export interface HazardAwareRouteResponse {
  habitation_id: string
  site_id: string
  engine: string
  engine_tier: string
  status: 'OK' | 'UNAVAILABLE'
  route: {
    distance_km?: number
    distance_m?: number
    duration_min?: number
    source?: string
    [key: string]: unknown
  } | null
  route_geojson: GeoJSON.Feature | null
  hazard_analysis: HazardAnalysis
  avoidance?: {
    enabled: boolean
    avoided: boolean
    note: string
    candidates_count?: number
  }
  region?: Record<string, unknown>
  note?: string
  computed_at?: string
  reason?: string
}

export interface IsochronesResponse {
  data_status: DataStatus
  reason?: string
  source?: string
  region?: string
  computed_at?: string
  feature_collection: GeoJSON.FeatureCollection
}

export interface MatrixResponse {
  data_status: DataStatus
  reason?: string
  source?: string
  region?: string
  rows: string[]
  columns: string[]
  distances_km?: number[][]
  durations_min?: number[][]
  computed_at?: string
}

export interface HabitationsResponse {
  data_status: DataStatus
  _source?: string
  district_id: string
  total: number
  habitations: HabitationListItem[]
}

// ── Automatic evacuation options (GET /api/v1/routing/options) ────────────
export interface EvacuationOptionOrigin {
  id: string
  name: string
  latitude?: number
  longitude?: number
  relocation_demand?: number
}

export interface EvacuationOptionDestination {
  id: string
  name: string
  latitude?: number | null
  longitude?: number | null
  capacity: number
  suitability_score?: number | null
  safety_score?: number | null
  status?: boolean
}

export interface EvacuationRouteOption {
  status: 'OK' | 'UNAVAILABLE' | 'REJECTED' | 'NOT_EVALUATED'
  site_id: string
  route_site_id?: string
  origin?: EvacuationOptionOrigin
  destination: EvacuationOptionDestination
  capacity_available: number
  capacity_sufficient?: boolean
  distance_km?: number | null
  duration_min?: number | null
  eta_min?: number | null
  risk_score?: number | null
  risk_label?: string | null
  hazard_exposure?: {
    events: Array<string | null>
    inside_km_total?: number
    events_evaluated?: number
  }
  engine?: string | null
  served_by?: string | null
  fallback_used?: boolean
  engine_requested?: string | null
  route_geojson?: GeoJSON.Feature | null
  avoidance?: { enabled: boolean; avoided: boolean; note?: string } | null
  recommendation_rank?: number
  recommendation_reason?: string
  reason?: string | null
}

export interface EvacuationCapacitySummary {
  data_status: string
  origin_demand: number
  district_total_demand: number
  total_capacity: number
  capacity_gap: number
  capacity_gap_formula: string
  unallocated_demand: number
  note: string
}

export interface EvacuationOptionsResponse {
  data_status: DataStatus
  district_id: string
  habitation_id?: string
  generated_at: string
  origin: EvacuationOptionOrigin & { events_near_origin?: Array<string> } | null
  policy: string
  engine_policy?: string
  engine?: string | null
  engine_unavailable_reason?: string | null
  hazards?: { data_status: string; active_events: number }
  recommended_route: EvacuationRouteOption | null
  alternative_routes: EvacuationRouteOption[]
  rejected_options: EvacuationRouteOption[]
  evaluated_sites?: number
  routed_sites?: number
  capacity_summary: EvacuationCapacitySummary | null
  ranking_rule?: string
  note?: string
  provenance?: { source: string; generated_at: string }
  reason?: string
}
