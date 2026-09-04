import { ExternalLink, Database, AlertTriangle, RefreshCw } from 'lucide-react'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { ApiStatusBanner } from '../components/ui/ApiStatusBanner'
import { useApiWithFallback } from '../hooks/useApiWithFallback'
import { api } from '../api/client'
import clsx from 'clsx'

interface DatasetEntry {
  id: string
  name: string
  organization: string
  url: string
  data_types: string[]
  used_for: string
  year_reference: string
  update_frequency: string
  data_type_label: 'OBSERVED' | 'DERIVED' | 'ESTIMATED'
  status: 'DEMO' | 'UNAVAILABLE' | 'STALE'
  limitations: string
  model_version?: string
}

const DATASETS: DatasetEntry[] = [
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
    name: 'Flood Hazard Layer',
    organization: 'ISRO / NRSC — Bhuvan',
    url: 'https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms',
    data_types: ['Raster', 'WMS'],
    used_for: 'Flood hazard component of risk model. Map overlay in GIS workspace.',
    year_reference: '2021',
    update_frequency: 'Periodic',
    data_type_label: 'OBSERVED',
    status: 'DEMO',
    limitations: 'Bhuvan WMS may be unreachable from demo environment. Layer shown as DEMO/UNAVAILABLE when offline.',
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
      'Risk = 0.40×Hazard + 0.20×Exposure + 0.25×Vulnerability + 0.15×Interaction. ' +
      'All outputs are DERIVED and require human authority review.',
    model_version: 'v0.1.0 — SIH demo build',
  },
]

const STATUS_COLORS = {
  DEMO: 'border-amber-500/30 bg-amber-500/8 text-amber-400',
  UNAVAILABLE: 'border-red-500/30 bg-red-500/8 text-red-400',
  STALE: 'border-orange-500/30 bg-orange-500/8 text-orange-400',
}

export function DataSources() {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-slate-800 bg-slate-950 px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-sm font-semibold text-slate-200">Data & Sources</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Dataset registry — provenance, vintage, limitations, and data type for every input used by Sentinel AI.
            </p>
          </div>
          <FreshnessBadge status="DEMO" />
        </div>
      </div>

      {/* Trust banner */}
      <div className="border-b border-slate-800 bg-slate-950 px-4 py-2">
        <div className="flex items-center gap-2 rounded border border-amber-500/30 bg-amber-500/8 px-3 py-2">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
          <p className="text-xs text-amber-400/80">
            All data in this demo is labelled DEMO. Live connections to IMD, CWC, Bhuvan and KSDMA are not active.
            Sentinel AI never fabricates live government data. When external sources are unavailable, data is shown as DEMO or UNAVAILABLE.
          </p>
        </div>
      </div>

      {/* Dataset table */}
      <div className="flex-1 overflow-auto p-4">
        <div className="flex flex-col gap-3">
          {DATASETS.map(ds => (
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
