// Sentinel AI — API client
// All calls throw on non-2xx so useApiWithFallback can catch and use demo data.

import type { HistoricalPeriodsResponse, ScreeningZonesResponse } from '../types'

// Same-origin by default: dev uses the vite proxy (vite.config.ts),
// production rewrites /api/* to the Render backend (vercel.json).
// Set VITE_API_URL to point the browser straight at another origin.
const BASE_URL = import.meta.env.VITE_API_URL || ''

async function fetchJSON<T>(path: string): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 8000) // 8s timeout
  try {
    const res = await fetch(`${BASE_URL}${path}`, { signal: controller.signal })
    if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
    return res.json() as Promise<T>
  } finally {
    clearTimeout(timeout)
  }
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
    return res.json() as Promise<T>
  } finally {
    clearTimeout(timeout)
  }
}

export const api = {
  // Health
  health: () => fetchJSON<{ status: string; database: string }>('/health'),
  dataSourceHealth: () => fetchJSON('/api/v1/data-sources/health'),

  // Districts
  getDistrictOverview: (districtId: string) =>
    fetchJSON(`/api/v1/districts/${districtId}/overview`),

  // Habitations
  getHabitations: (districtId = 'idukki', search?: string) => {
    const params = new URLSearchParams({ district_id: districtId })
    if (search) params.set('search', search)
    return fetchJSON(`/api/v1/habitations/?${params}`)
  },

  getHabitationDetail: (habitationId: string) =>
    fetchJSON(`/api/v1/habitations/${habitationId}`),

  getHabitationsGeoJSON: (districtId = 'idukki') =>
    fetchJSON(`/api/v1/habitations/geojson/district/${districtId}`),

  getCandidateSitesGeoJSON: (districtId = 'idukki') =>
    fetchJSON(`/api/v1/relocation/sites/geojson?district_id=${districtId}`),

  getSpatialDistance: (habitationId: string, siteId: string) =>
    fetchJSON(`/api/v1/spatial/distance/${habitationId}/${siteId}`),

  getSpatialProximity: (habitationId: string, radiusM?: number) =>
    fetchJSON(
      `/api/v1/spatial/proximity/${habitationId}${radiusM ? `?radius_m=${radiusM}` : ''}`,
    ),

  // Risk
  getRiskIntelligence: (districtId = 'idukki', mode = 'current') =>
    fetchJSON(`/api/v1/risk/intelligence?district_id=${districtId}&mode=${mode}`),

  getRiskDrivers: (habitationId: string) =>
    fetchJSON(`/api/v1/risk/drivers/${habitationId}`),

  getDecisionTrace: (habitationId: string) =>
    fetchJSON(`/api/v1/risk/decision-trace/${habitationId}`),

  getRiskPriorities: (districtId = 'idukki') =>
    fetchJSON(`/api/v1/risk/priorities?district_id=${districtId}`),

  // Relocation
  getCandidateSites: (habitationId: string) =>
    fetchJSON(`/api/v1/relocation/candidates?habitation_id=${habitationId}`),

  getCapacityAssessment: (siteId: string) =>
    fetchJSON(`/api/v1/relocation/capacity/${siteId}`),

  getRelocationDemand: (habitationId: string) =>
    fetchJSON(`/api/v1/relocation/demand/${habitationId}`),

  getOptimization: (habitationId: string) =>
    fetchJSON(`/api/v1/relocation/optimization/${habitationId}`),

  // Scenarios
  runScenario: (params: Record<string, unknown>) =>
    postJSON('/api/v1/scenarios/run', params),

  // Multi-engine road routing (Phase 5C — all engines consume OSM data)
  getRoutingEngines: (region = 'kerala') =>
    fetchJSON(`/api/v1/routing/engines?region=${region}`),

  getRoute: (habitationId: string, siteId: string, engine = 'graphhopper') =>
    fetchJSON(
      `/api/v1/routing/route/${habitationId}/${siteId}?engine=${engine}`,
    ),

  // Validation (audit trail)
  validateAll: () => fetchJSON('/api/v1/validate/all'),

  // Data sources
  getDataSources: () => fetchJSON('/api/v1/data-sources/'),

  // Phase 5B — screening zones + historical periods
  getScreeningZones: (districtId = 'idukki'): Promise<ScreeningZonesResponse> =>
    fetchJSON(`/api/v1/spatial/zones?district_id=${districtId}`),

  getHistoricalPeriods: (region = 'kerala'): Promise<HistoricalPeriodsResponse> =>
    fetchJSON(`/api/v1/spatial/history/${region}`),
}
