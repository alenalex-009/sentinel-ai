import { ExternalLink, Database, AlertTriangle } from 'lucide-react'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { ApiStatusBanner } from '../components/ui/ApiStatusBanner'
import { useApiWithFallback } from '../hooks/useApiWithFallback'
import { api } from '../api/client'
import clsx from 'clsx'

type SourceStatus = 'LIVE' | 'DEMO' | 'UNAVAILABLE' | 'STALE'
type SourceDataType = 'OBSERVED' | 'DERIVED' | 'ESTIMATED'

interface DatasetEntry {
  id: string
  name: string
  organization: string
  url: string
  data_types: string[]
  used_for: string
  year_reference: string
  update_frequency: string
  data_type_label: SourceDataType
  status: SourceStatus
  limitations: string
  model_version?: string
}

// Shape of one entry in the backend data-source registry (single source of
// truth when the API is reachable). Only Bhuvan WMS availability is probed at
// runtime; every other source is DEMO because no live integration exists.
interface RegistrySource {
  id: string
  name: string
  organization: string
  url: string
  data_type: string
  data_types?: string[]
  used_for: string
  year_reference: string
  update_frequency: string
  availability: string
  last_checked?: string | null
  last_successful?: string | null
  age_hours?: number | null
  limitations?: string
  model_version?: string | null
  error_message?: string | null
}

function normalizeStatus(value: string): SourceStatus {
  return (['LIVE', 'DEMO', 'UNAVAILABLE', 'STALE'] as SourceStatus[]).includes(value as SourceStatus)
    ? (value as SourceStatus)
    : 'DEMO'
}

function normalizeDataType(value: string): SourceDataType {
  return (['OBSERVED', 'DERIVED', 'ESTIMATED'] as SourceDataType[]).includes(value as SourceDataType)
    ? (value as SourceDataType)
    : 'DERIVED'
}

function adaptRegistry(registry: RegistrySource[]): DatasetEntry[] {
  return registry.map((s) => ({
    id: s.id,
    name: s.name,
    organization: s.organization,
    url: s.url,
    data_types: s.data_types && s.data_types.length > 0 ? s.data_types : [s.data_type],
    used_for: s.used_for,
    year_reference: s.year_reference,
    update_frequency: s.update_frequency,
    data_type_label: normalizeDataType(s.data_type),
    status: normalizeStatus(s.availability),
    limitations: s.limitations || '',
    model_version: s.model_version || undefined,
  }))
}

// ─── Offline snapshot (used only when the backend API is unreachable) ────────
// Content is intentionally aligned with the backend registry. When the API is
// up, this page renders the live registry instead of this copy.
const FALLBACK_DATASETS: DatasetEntry[] = [
  {
    id: 'ksdma-landslide',
    name: 'Landslide Susceptibility Map',
    organization: 'KSDMA (Kerala State Disaster Management Authority)',
    url: 'https://sdma.kerala.gov.in',
    data_types: ['Raster', 'Vector'],
    used_for: 'Hazard intensity — landslide component of risk model',
    year_reference: '2019',
    update_frequency: 'Periodic (post-event)',
    data_type_label: 'OBSERVED',
    status: 'DEMO',
    limitations: 'Static susceptibility map. Does not reflect real-time soil saturation or rainfall. 2019 vintage — may not reflect post-2021 terrain changes.',
    model_version: 'KSDMA 2019 investigation dataset',
  },
  {
    id: 'imd-rainfall',
    name: 'Rainfall Observations & Forecasts',
    organization: 'India Meteorological Department (IMD)',
    url: 'https://mausam.imd.gov.in',
    data_types: ['Station data', 'Gridded', 'Forecast'],
    used_for: 'Rainfall intensity input to hazard model. Threshold: 150mm/72hr for landslide trigger.',
    year_reference: 'Real-time (DEMO: 2024-08-15)',
    update_frequency: 'Hourly (live); DEMO uses static snapshot',
    data_type_label: 'OBSERVED',
    status: 'DEMO',
    limitations: 'Live IMD API not connected in demo. Static snapshot used. Munnar station data used as proxy for Ward 04.',
  },
  {
    id: 'bhuvan-lulc',
    name: 'Land Use / Land Cover (LULC)',
    organization: 'ISRO / NRSC — Bhuvan',
    url: 'https://bhuvan.nrsc.gov.in',
    data_types: ['Raster', 'WMS'],
    used_for: 'Exposure mapping, candidate site land availability estimation',
    year_reference: '2022-23',
    update_frequency: 'Annual',
    data_type_label: 'OBSERVED',
    status: 'DEMO',
    limitations: 'WMS layer may be unavailable in demo environment. Local GeoJSON fallback used. 56m resolution — sub-parcel accuracy not guaranteed.',
  },
  {
    id: 'bhuvan-flood',
    name: 'Kerala Disaster Event Layers (Bhuvan WMS)',
    organization: 'ISRO / NRSC — Bhuvan (Bhuvan is the ISRO/NRSC geospatial platform)',
    url: 'https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms',
    data_types: ['Raster', 'WMS'],
    used_for: 'Visual map overlay of historical Kerala disaster events (Kerala 2019 event; Oct 2021 landslides). Overlay-only — NOT a numeric input to the risk engine.',
    year_reference: '2019 & 2021 historical events',
    update_frequency: 'Periodic (historical product)',
    data_type_label: 'OBSERVED',
    status: 'DEMO',
    limitations: 'Historical event layers only — no live hazard feed. Service can be slow; tiles may lag or fail when the network is unavailable. Reachability is probed at request time.',
  },
  {
    id: 'census-2011',
    name: 'Census of India 2011 — Village/Ward Data',
    organization: 'Office of the Registrar General & Census Commissioner',
    url: 'https://censusindia.gov.in',
    data_types: ['Tabular', 'Shapefile'],
    used_for: 'Population, households, demographic vulnerability indicators',
    year_reference: '2011 (projected to 2024)',
    update_frequency: 'Decennial. 2021 census pending.',
    data_type_label: 'OBSERVED',
    status: 'DEMO',
    limitations: 'Census 2011 is the most recent available. Population figures are projected estimates — not current counts. Ward-level granularity varies.',
  },
  {
    id: 'cwc-river',
    name: 'River Level & Flood Forecasting',
    organization: 'Central Water Commission (CWC)',
    url: 'https://cwc.gov.in',
    data_types: ['Station data', 'Forecast'],
    used_for: 'Flood hazard input. River level anomaly detection.',
    year_reference: 'Real-time (DEMO: 2024-08-15)',
    update_frequency: 'Hourly (live); DEMO uses static snapshot',
    data_type_label: 'OBSERVED',
    status: 'DEMO',
    limitations: 'Live CWC API not connected in demo. Periyar at Cheruthoni gauge used as proxy.',
  },
  {
    id: 'data-gov-health',
    name: 'Health Facility Data',
    organization: 'data.gov.in / NHM Kerala',
    url: 'https://data.gov.in',
    data_types: ['Tabular', 'GeoJSON'],
    used_for: 'Healthcare carrying capacity dimension for candidate sites',
    year_reference: '2022',
    update_frequency: 'Annual',
    data_type_label: 'ESTIMATED',
    status: 'DEMO',
    limitations: 'Catchment capacity estimated from facility type and bed count. Actual surge capacity not available.',
  },
  {
    id: 'udise-schools',
    name: 'UDISE+ School Infrastructure',
    organization: 'Ministry of Education — UDISE+',
    url: 'https://udiseplus.gov.in',
    data_types: ['Tabular'],
    used_for: 'Education carrying capacity dimension for candidate sites',
    year_reference: '2022-23',
    update_frequency: 'Annual',
    data_type_label: 'ESTIMATED',
    status: 'DEMO',
    limitations: 'Enrolment capacity estimated from school count and average capacity. Actual available seats not verified.',
  },
  {
    id: 'sentinel-risk-engine',
    name: 'Sentinel AI Risk Engine',
    organization: 'Sentinel AI (SIH PS 26191)',
    url: '#',
    data_types: ['Computed'],
    used_for: 'Risk scores, RPI, vulnerability composite, carrying capacity C_safe',
    year_reference: 'v0.1.0',
    update_frequency: 'On data refresh',
    data_type_label: 'DERIVED',
    status: 'DEMO',
    limitations:
      'Weights are configurable project baselines — not official government formulas. ' +
      'Risk = 0.40×Hazard + 0.20×Exposure + 0.25×Vulnerability + 0.15×Interaction, ' +
      'plus a deterministic event-escalation term for current operational risk. ' +
      'All outputs are DERIVED and require human authority review.',
    model_version: 'v0.1.0 — SIH demo build',
  },
  {
    id: 'ortools-optimizer',
    name: 'OR-Tools CP-SAT Optimizer',
    organization: 'Google OR-Tools (open source)',
    url: 'https://developers.google.com/optimization',
    data_types: ['Computed'],
    used_for: 'Multi-site relocation allocation optimization',
    year_reference: 'v9.10',
    update_frequency: 'On demand',
    data_type_label: 'DERIVED',
    status: 'DEMO',
    limitations:
      'Optimization results are RECOMMENDATION only and are computed from demo inputs. ' +
      'Requires human authority review before any relocation action.',
    model_version: 'OR-Tools 9.10 CP-SAT',
  },
  {
    id: 'graphhopper-routing',
    name: 'OpenStreetMap Road Network Routing (GraphHopper)',
    organization: 'OpenStreetMap (ODbL) / GraphHopper (self-hosted)',
    url: 'http://localhost:8989',
    data_types: ['Road network', 'Route'],
    used_for: 'Road-network distance and travel time between habitations and candidate sites (region-aware: kerala / vizag / assam)',
    year_reference:
      'OSM via Overpass API 2026-09-04. Loaded: Kerala (Idukki pilot region — covers all Kerala prototype habitations), Vizag (Visakhapatnam urban pilot), Assam (Guwahati urban pilot). Prototype-area coverage only, not full-state.',
    update_frequency: 'On demand (cached 5 min)',
    data_type_label: 'DERIVED',
    status: 'UNAVAILABLE',
    limitations:
      'Probed at request time. LIVE only when every region GraphHopper service answered. ' +
      'Road distance is not a geodesic or demo estimate; travel time is an estimate, not ' +
      'official emergency travel time. Datasets are prototype-area extracts (Idukki / ' +
      'Vizag city / Guwahati), not full-state coverage.',
    model_version: 'GraphHopper 8.0 (profile: car)',
  },
]

const STATUS_COLORS: Record<SourceStatus, string> = {
  LIVE: 'border-green-500/30 bg-green-500/10 text-green-400',
  DEMO: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  UNAVAILABLE: 'border-red-500/30 bg-red-500/10 text-red-400',
  STALE: 'border-orange-500/30 bg-orange-500/10 text-orange-400',
}

export function DataSources() {
  const { data: liveDatasets, error, source } = useApiWithFallback<DatasetEntry[]>(
    () =>
      api
        .getDataSources()
        .then((res) => adaptRegistry((res as { sources: RegistrySource[] }).sources)),
    FALLBACK_DATASETS,
  )
  const datasets = liveDatasets ?? FALLBACK_DATASETS

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-slate-800 bg-slate-950 px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-sm font-semibold text-slate-200">Data & Sources</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Dataset registry — provenance, vintage, limitations, and data type for every input used by Sentinel AI.
              {source === 'api'
                ? ' Showing the live backend registry.'
                : source === 'demo_fallback'
                ? ' API unreachable — showing the offline registry snapshot.'
                : ''}
            </p>
          </div>
          <FreshnessBadge status="DEMO" />
        </div>
        {error && <ApiStatusBanner source={source} error={error} className="mt-2" />}
      </div>

      {/* Trust banner */}
      <div className="border-b border-slate-800 bg-slate-950 px-4 py-2">
        <div className="flex items-center gap-2 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
          <p className="text-xs text-amber-400/80">
            No live IMD / CWC / KSDMA feeds are connected — those entries are DEMO (static snapshot).
            The Bhuvan WMS overlay (ISRO/NRSC Kerala disaster event layers) is probed at request time;
            a LIVE status means the service answered a tile request, not that live data is ingested.
            Sentinel AI never fabricates live government data.
          </p>
        </div>
      </div>

      {/* Dataset table */}
      <div className="flex-1 overflow-auto p-4">
        <div className="flex flex-col gap-3">
          {datasets.map(ds => (
            <div
              key={ds.id}
              className="rounded-lg border border-slate-800 bg-slate-900 p-4"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex items-start gap-3">
                  <Database className="h-4 w-4 text-slate-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-slate-200">{ds.name}</span>
                      <DataTypeBadge type={ds.data_type_label} />
                      <span className={clsx(
                        'inline-flex items-center rounded border px-1.5 py-0.5 text-2xs font-semibold uppercase tracking-wide',
                        STATUS_COLORS[ds.status]
                      )}>
                        {ds.status}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">{ds.organization}</div>
                  </div>
                </div>
                {ds.url !== '#' && (
                  <a
                    href={ds.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-2xs text-blue-400 hover:text-blue-300 flex-shrink-0"
                    onClick={e => e.stopPropagation()}
                  >
                    <ExternalLink className="h-3 w-3" />
                    Source
                  </a>
                )}
              </div>

              <div className="grid grid-cols-2 gap-x-6 gap-y-2 mb-3 lg:grid-cols-4">
                <div>
                  <div className="text-2xs text-slate-600 uppercase tracking-wide">Used for</div>
                  <div className="text-xs text-slate-400 mt-0.5">{ds.used_for}</div>
                </div>
                <div>
                  <div className="text-2xs text-slate-600 uppercase tracking-wide">Reference year</div>
                  <div className="text-xs text-slate-400 mt-0.5">{ds.year_reference}</div>
                </div>
                <div>
                  <div className="text-2xs text-slate-600 uppercase tracking-wide">Update frequency</div>
                  <div className="text-xs text-slate-400 mt-0.5">{ds.update_frequency}</div>
                </div>
                <div>
                  <div className="text-2xs text-slate-600 uppercase tracking-wide">Data types</div>
                  <div className="text-xs text-slate-400 mt-0.5">{ds.data_types.join(', ')}</div>
                </div>
              </div>

              {ds.model_version && (
                <div className="mb-2">
                  <span className="text-2xs text-slate-600">Model/version: </span>
                  <span className="text-2xs font-mono text-slate-500">{ds.model_version}</span>
                </div>
              )}

              <div className="rounded border border-slate-800 bg-slate-950 px-2.5 py-2">
                <div className="text-2xs text-slate-600 uppercase tracking-wide mb-0.5">Limitations</div>
                <p className="text-xs text-slate-500 leading-relaxed">{ds.limitations}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
