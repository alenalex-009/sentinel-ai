// Sentinel AI — Phase 5B demo fallback data (DEMO MODE)
// Mirrors the backend derivation in app/services/screening.py so the map works
// when the API is unavailable. Zones are DERIVED screening ranges — never
// official hazard boundaries or government land approvals.

import type {
  HistoricalPeriodsResponse,
  ScreeningZoneFeature,
  ScreeningZonesResponse,
} from '../types'
import {
  DEMO_CANDIDATE_SITES,
  DEMO_CAPACITY_ASSESSMENTS,
} from './idukki-seed'

// Same deterministic rule as the backend: bottleneck is a capacity constraint
// (kept in `basis`), not a suitability failure.
export function zoneStatus(suitability: number, safety: number, hardPassed: boolean): 'red' | 'yellow' | 'green' {
  if (!hardPassed || suitability < 50 || safety < 40) return 'red'
  if (suitability < 70) return 'yellow'
  return 'green'
}

export function zoneRadiusKm(cSafe: number, maxCSafe: number): number {
  if (!maxCSafe) return 0.75
  return Math.min(2.5, Math.max(0.75, 0.75 + 1.25 * (cSafe / maxCSafe)))
}

// Approximate geodesic buffer ring (equirectangular) — DEMO fallback only.
function bufferRing(lat: number, lon: number, radiusKm: number): number[][] {
  const mPerDegLat = 111320
  const mPerDegLon = 111320 * Math.max(Math.cos((lat * Math.PI) / 180), 0.01)
  const radiusM = radiusKm * 1000
  const cx = lon * mPerDegLon
  const cy = lat * mPerDegLat
  const pts: number[][] = []
  const SEGMENTS = 48
  for (let i = 0; i <= SEGMENTS; i++) {
    const a = (i / SEGMENTS) * 2 * Math.PI
    pts.push([
      (cx + radiusM * Math.cos(a)) / mPerDegLon,
      (cy + radiusM * Math.sin(a)) / mPerDegLat,
    ])
  }
  return pts
}

const ZONE_MEANING_NOTE =
  "DERIVED SCREENING RANGE — a geodesic buffer around a technically screened candidate site, sized from the site's assessed safe capacity and colored from its suitability/safety scores. This is NOT an official danger zone, hazard boundary, or government land approval."

export const DEMO_SCREENING_ZONES: ScreeningZonesResponse = (() => {
  const maxC = Math.max(...DEMO_CANDIDATE_SITES.map((s) => s.safe_capacity))
  const features: ScreeningZoneFeature[] = DEMO_CANDIDATE_SITES.map((s) => {
    const status = zoneStatus(s.suitability_score, s.safety_score, s.hard_constraints_passed)
    const radiusKm = zoneRadiusKm(s.safe_capacity, maxC)
    return {
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [bufferRing(s.latitude, s.longitude, radiusKm)] },
      properties: {
        site_id: s.id,
        site_name: s.name,
        status,
        label:
          status === 'red' ? 'Exclusion / High Risk'
          : status === 'yellow' ? 'Caution / Limited Suitability'
          : 'Technically Suitable',
        classification: 'DERIVED',
        derived: true,
        authoritative: false,
        method: 'shapely buffer on demo coordinates (DEMO fallback)',
        radius_km: radiusKm,
        basis: {
          suitability_score: s.suitability_score,
          safety_score: s.safety_score,
          bottleneck: DEMO_CAPACITY_ASSESSMENTS[s.id]?.bottleneck ?? null,
          c_safe: DEMO_CAPACITY_ASSESSMENTS[s.id]?.c_safe ?? s.safe_capacity,
        },
        data_status: 'DEMO',
        _source: 'demo_fallback',
      },
    }
  })
  return {
    type: 'FeatureCollection',
    features,
    data_status: 'DEMO',
    classification: 'DERIVED',
    _source: 'demo_fallback',
    geometry_type: 'Polygon',
    srid: 4326,
    status_counts: {
      red: features.filter((f) => f.properties.status === 'red').length,
      yellow: features.filter((f) => f.properties.status === 'yellow').length,
      green: features.filter((f) => f.properties.status === 'green').length,
    },
    zone_meaning_note: ZONE_MEANING_NOTE,
  }
})()

const BHUVAN_KERALA_2019_WMS =
  'https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=disaster:Kerala_2019_Event&STYLES=&FORMAT=image/png&TRANSPARENT=true&SRS=EPSG:3857&WIDTH=256&HEIGHT=256&BBOX={bbox-epsg-3857}'

export const DEMO_HISTORICAL_PERIODS: Record<string, HistoricalPeriodsResponse> = {
  kerala: {
    region: 'kerala',
    status: 'AVAILABLE',
    periods: [
      {
        period: 'current',
        label: 'Current (operational)',
        availability: 'current',
        classification: 'DERIVED',
        spatial_layer: null,
        note: 'Operational risk and suitability from the current data pipeline. Not a historical event.',
      },
      {
        period: '2018',
        label: '2018 — Kerala floods & landslides',
        availability: 'context_only',
        classification: 'OBSERVED',
        source: 'KSDMA / GSI investigation records (documented in habitation history)',
        spatial_layer: null,
        note: 'No machine-readable spatial layer for 2018 exists in the project dataset. Event context (major displacement; GSI investigation; 689 dwelling units recommended for relocation) is documented in habitation records as DEMO narrative only.',
      },
      {
        period: '2019',
        label: '2019 — Kerala flood event',
        availability: 'live_overlay',
        classification: 'OBSERVED',
        source: 'Bhuvan / ISRO-NRSC',
        spatial_layer: {
          type: 'wms',
          layer: 'disaster:Kerala_2019_Event',
          url: BHUVAN_KERALA_2019_WMS,
          attribution: 'Bhuvan / ISRO-NRSC — Kerala 2019 event layer',
        },
        note: 'Real ISRO/NRSC historical event WMS overlay (verified reachable). Visual context only — never a numeric input to the risk engine.',
      },
      {
        period: '2021',
        label: '2021 — October landslides',
        availability: 'context_only',
        classification: 'OBSERVED',
        source: 'KSDMA records (documented in habitation history)',
        spatial_layer: null,
        note: 'No machine-readable spatial layer for 2021 in the project dataset. Event context (partial slope failure, 3 structures damaged) is documented as DEMO narrative only.',
      },
    ],
  },
  vizag: {
    region: 'vizag',
    status: 'UNAVAILABLE',
    periods: [],
    reason: 'No historical hazard/event layer is registered for the Vizag prototype region in the project data sources. Current operational data only.',
  },
  assam: {
    region: 'assam',
    status: 'UNAVAILABLE',
    periods: [],
    reason: 'No historical hazard/event layer is registered for the Assam prototype region in the project data sources. Current operational data only.',
  },
}


// Candidate-site points for the map (DEMO fallback — mirrors the API geojson).
export const DEMO_SITES_GEOJSON = {
  type: 'FeatureCollection' as const,
  features: DEMO_CANDIDATE_SITES.map((s) => ({
    type: 'Feature' as const,
    geometry: { type: 'Point' as const, coordinates: [s.longitude, s.latitude] },
    properties: {
      id: s.id,
      name: s.name,
      suitability_score: s.suitability_score,
      safety_score: s.safety_score,
      c_safe: DEMO_CAPACITY_ASSESSMENTS[s.id]?.c_safe ?? s.safe_capacity,
      bottleneck: DEMO_CAPACITY_ASSESSMENTS[s.id]?.bottleneck ?? null,
    },
  })),
}
