// Sentinel AI — API client

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${path}`)
  }
  return res.json() as Promise<T>
}

export const api = {
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

  // Risk
  getRiskIntelligence: (districtId = 'idukki', mode = 'current') =>
    fetchJSON(`/api/v1/risk/intelligence?district_id=${districtId}&mode=${mode}`),

  getRiskDrivers: (habitationId: string) =>
    fetchJSON(`/api/v1/risk/drivers/${habitationId}`),

  getDecisionTrace: (habitationId: string) =>
    fetchJSON(`/api/v1/risk/decision-trace/${habitationId}`),

  // Relocation
  getCandidateSites: (habitationId: string) =>
    fetchJSON(`/api/v1/relocation/candidates?habitation_id=${habitationId}`),

  getCapacityAssessment: (siteId: string) =>
    fetchJSON(`/api/v1/relocation/capacity/${siteId}`),

  // Scenarios
  runScenario: (params: Record<string, unknown>) =>
    fetch(`${BASE_URL}/api/v1/scenarios/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    }).then(r => r.json()),
}
