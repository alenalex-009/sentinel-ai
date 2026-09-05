import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Users, Home,
  ChevronRight, Info, History, Shield,
} from 'lucide-react'
import { RiskBadge } from '../components/ui/RiskBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { LoadingSpinner } from '../components/ui/LoadingSpinner'
import { EmptyState } from '../components/ui/EmptyState'
import { ApiStatusBanner } from '../components/ui/ApiStatusBanner'
import { MapContainer } from '../components/map/MapContainer'
import { DEMO_MUNNAR_CENTRAL, DEMO_HABITATIONS } from '../data/idukki-seed'
import { useApiWithFallback } from '../hooks/useApiWithFallback'
import { api } from '../api/client'
import type { HabitationDetail, HazardType } from '../types'
import clsx from 'clsx'

const HAZARD_COLORS: Record<HazardType, string> = {
  LANDSLIDE: 'text-orange-400 border-orange-500/30 bg-orange-500/8',
  FLOOD: 'text-blue-400 border-blue-500/30 bg-blue-500/8',
  CLOUDBURST: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/8',
  EROSION: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/8',
  MULTI_HAZARD: 'text-red-400 border-red-500/30 bg-red-500/8',
}

function HazardBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-24 text-xs text-slate-400 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-slate-800">
        <div className={clsx('h-full rounded-full', color)} style={{ width: `${value}%` }} />
      </div>
      <span className="w-8 text-right text-xs font-mono text-slate-300">{value}</span>
    </div>
  )
}

function EvidenceStep({ item }: { item: HabitationDetail['evidence_chain'][0] }) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-2xs font-bold text-slate-400">
          {item.step}
        </div>
        {item.step < 5 && <div className="mt-1 w-px flex-1 bg-slate-800" />}
      </div>
      <div className="pb-4 flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-slate-300">{item.label}</span>
          <DataTypeBadge type={item.data_type} />
        </div>
        <p className="text-xs text-slate-400 mb-1">{item.description}</p>
        {item.value && (
          <div className="rounded border border-slate-800 bg-slate-900 px-2 py-1 font-mono text-xs text-slate-300">
            {item.value}
          </div>
        )}
        {item.source && <p className="mt-1 text-2xs text-slate-600">Source: {item.source}</p>}
      </div>
    </div>
  )
}

// ─── Canonical derived values for non-Munnar demo habitations — parity with
// backend demo_data (RPI/vulnerability maps and per-habitation components).
const FALLBACK_RPI: Record<string, number> = {
  'rajakkad': 78, 'kanthalloor': 61, 'marayoor': 52, 'adimali': 38,
}
const FALLBACK_VULNERABILITY: Record<string, number> = {
  'rajakkad': 68, 'kanthalloor': 59, 'marayoor': 51, 'adimali': 42,
}
const FALLBACK_HISTORICAL: Record<string, number> = {
  'rajakkad': 71, 'kanthalloor': 55, 'marayoor': 48, 'adimali': 31,
}
const FALLBACK_URGENCY: Record<string, number> = {
  'rajakkad': 76, 'kanthalloor': 63, 'marayoor': 54, 'adimali': 35,
}
const FALLBACK_RISK_COMPONENTS: Record<string, [number, number, number, number]> = {
  'rajakkad': [31.2, 14.4, 16.8, 8.1],
  'kanthalloor': [27.4, 13.2, 15.6, 7.2],
  'marayoor': [22.8, 11.6, 13.4, 6.1],
  'adimali': [18.2, 9.8, 11.2, 5.1],
}
const FALLBACK_RECOMMENDATION: Record<string, string> = {
  'rajakkad': 'Prioritize Rajakkad for field verification and relocation-assessment screening.',
  'kanthalloor': 'Review access-route alternatives for Kanthalloor and monitor flood hazard.',
  'marayoor': 'Monitor Marayoor flood risk; include in near-term screening.',
  'adimali': 'No immediate relocation indication for Adimali; continue routine monitoring.',
}

function fallbackVulnLevel(score: number): 'VERY HIGH' | 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY LOW' {
  if (score >= 80) return 'VERY HIGH'
  if (score >= 60) return 'HIGH'
  if (score >= 40) return 'MEDIUM'
  if (score >= 20) return 'LOW'
  return 'VERY LOW'
}

// Build a complete, well-formed HabitationDetail from a list item for
// non-Munnar habitations (used only when the API is unreachable). Mirrors the
// backend contract: no Munnar history/suitability text is inherited.
function buildFallbackDetail(id: string): HabitationDetail {
  const listItem = DEMO_HABITATIONS.find(h => h.id === id)
  if (!listItem) return DEMO_MUNNAR_CENTRAL
  const population = listItem.population
  const households = Math.round(population / 4)
  const vuln = FALLBACK_VULNERABILITY[id]
  const level = fallbackVulnLevel(vuln)
  const baseline = listItem.risk_score - listItem.risk_change
  const comps = FALLBACK_RISK_COMPONENTS[id]
  const hazardLabel = listItem.primary_hazard.replace('_', ' ').toLowerCase()
  const hazardTitle = hazardLabel.charAt(0).toUpperCase() + hazardLabel.slice(1)
  const sourceText = listItem.primary_hazard === 'LANDSLIDE'
    ? 'KSDMA Landslide Susceptibility Map + IMD Rainfall (DEMO)'
    : 'Bhuvan/ISRO Kerala 2019 flood-event overlay + CWC River Level (DEMO)'
  const riskComp = Math.round(0.35 * listItem.risk_score * 100) / 100
  const vulnComp = Math.round(0.2 * vuln * 100) / 100
  const histComp = Math.round(0.15 * FALLBACK_HISTORICAL[id] * 100) / 100
  const urgComp = Math.round(0.15 * FALLBACK_URGENCY[id] * 100) / 100
  const popComp = Math.round((FALLBACK_RPI[id] - riskComp - vulnComp - histComp - urgComp) * 100) / 100

  return {
    id: listItem.id,
    name: listItem.name,
    ward: listItem.ward,
    taluk: listItem.taluk,
    district: listItem.district,
    state: 'Kerala',
    population,
    households,
    area_ha: Math.round(population / 340 * 10) / 10,
    latitude: listItem.latitude,
    longitude: listItem.longitude,
    hazards: [{
      type: listItem.primary_hazard,
      intensity: Math.round(comps[0] / 0.4 * 10) / 10,
      data_type: 'DERIVED',
      source: sourceText,
      description: `${hazardTitle} hazard exposure — risk elevated (DEMO).`,
    }],
    vulnerability: {
      overall: vuln,
      level,
      demographic: vuln + 4,
      socioeconomic: vuln - 6,
      infrastructure: vuln + 2,
      accessibility: vuln - 2,
      data_type: 'DERIVED',
    },
    risk: {
      current: listItem.risk_score,
      baseline,
      change: listItem.risk_change,
      hazard_component: comps[0],
      exposure_component: comps[1],
      vulnerability_component: comps[2],
      interaction_component: comps[3],
      data_type: 'DERIVED',
      computed_at: '2024-08-15T06:00:00Z',
    },
    relocation_priority: {
      priority: listItem.priority,
      rpi_score: FALLBACK_RPI[id],
      risk_component: riskComp,
      vulnerability_component: vulnComp,
      historical_impact_component: histComp,
      urgency_component: urgComp,
      exposed_population_component: popComp,
      data_type: 'RECOMMENDATION',
    },
    evidence_chain: [
      { step: 1, label: 'HAZARD', description: `${hazardTitle} hazard exposure active`, data_type: 'DERIVED', source: sourceText, value: `${listItem.primary_hazard} hazard — risk elevated` },
      { step: 2, label: 'EXPOSURE', description: 'Population within hazard zone', data_type: 'DERIVED', source: 'Census 2011 projected + Bhuvan LULC (DEMO)', value: `${population.toLocaleString()} persons | ${households.toLocaleString()} households` },
      { step: 3, label: 'VULNERABILITY', description: 'Structural and access vulnerability', data_type: 'DERIVED', source: 'Census + KSDMA + Field Data (DEMO)', value: `${vuln}/100 — ${level}` },
      { step: 4, label: 'RISK', description: 'Composite risk score', data_type: 'DERIVED', source: 'Sentinel AI Risk Engine (DEMO)', value: `${listItem.risk_score}/100 (Baseline: ${baseline}, Change: ${listItem.risk_change > 0 ? '+' : ''}${listItem.risk_change})` },
      { step: 5, label: 'PRIORITY', description: 'Relocation priority assessment', data_type: 'RECOMMENDATION', source: 'Sentinel AI RPI Engine (DEMO)', value: `${listItem.priority} — RPI ${FALLBACK_RPI[id]}/100` },
    ],
    red_zone_status: 'NOT_RECOMMENDED',
    permanent_settlement_suitable: true,
    permanent_suitability_note:
      `No permanent-unsuitability determination has been made for ${listItem.name}. ` +
      'Operational risk is elevated and is separate from permanent settlement suitability. ' +
      'Official assessment is required before any permanent suitability conclusion (DEMO — not an official designation).',
    system_recommendation: FALLBACK_RECOMMENDATION[id],
    historical_context: {
      events: [],
      gsi_2018_note:
        `No habitation-specific event record is verified for ${listItem.name} in this DEMO dataset. ` +
        'Historical-impact indicators are ESTIMATED from district-level records.',
      data_type: 'ESTIMATED',
    },
    data_status: 'DEMO',
    last_updated: '2024-08-15T06:00:00Z',
  }
}

export function HabitationInvestigation() {
  const { id = 'munnar-central' } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Determine fallback: use Munnar Central detail for munnar-central, minimal for others
  const fallback = id === 'munnar-central' ? DEMO_MUNNAR_CENTRAL : buildFallbackDetail(id)

  const { data: h, loading, error, source, refetch } = useApiWithFallback<HabitationDetail>(
    () => api.getHabitationDetail(id) as Promise<HabitationDetail>,
    fallback,
    [id],
  )

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <LoadingSpinner label="Loading habitation data..." />
      </div>
    )
  }

  if (!h) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <EmptyState variant="no-data" detail={`Habitation '${id}' not found.`} onRetry={refetch} />
      </div>
    )
  }

  const selectedHabitation = DEMO_HABITATIONS.find(x => x.id === id)

  return (
    <div className="flex h-full overflow-hidden">
      {/* LEFT — investigation panel */}
      <div className="flex w-80 flex-shrink-0 flex-col overflow-y-auto border-r border-slate-800 bg-slate-950">
        {/* Header */}
        <div className="border-b border-slate-800 p-3">
          <button
            onClick={() => navigate('/')}
            className="mb-3 flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Overview
          </button>

          {error && <ApiStatusBanner source={source} error={error} className="mb-2" />}

          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-2xs text-slate-500">{h.ward} · {h.taluk} · {h.district}</div>
              <h1 className="text-base font-bold text-slate-100">{h.name}</h1>
              <div className="text-xs text-slate-500">{h.state}</div>
            </div>
            <FreshnessBadge status={h.data_status} />
          </div>

          {/* Key metrics */}
          <div className="mt-3 grid grid-cols-3 gap-2">
            <div className="rounded border border-slate-800 bg-slate-900 p-2 text-center">
              <div className="text-2xs text-slate-500">RISK</div>
              <RiskBadge score={h.risk.current} size="lg" />
            </div>
            <div className="rounded border border-slate-800 bg-slate-900 p-2 text-center">
              <div className="text-2xs text-slate-500">BASELINE</div>
              <div className="text-lg font-bold font-mono text-slate-400">{h.risk.baseline}</div>
            </div>
            <div className="rounded border border-slate-800 bg-slate-900 p-2 text-center">
              <div className="text-2xs text-slate-500">CHANGE</div>
              <div className={clsx(
                'text-lg font-bold font-mono',
                h.risk.change > 0 ? 'text-red-400' : h.risk.change < 0 ? 'text-green-400' : 'text-slate-400'
              )}>
                {h.risk.change > 0 ? '+' : ''}{h.risk.change}
              </div>
            </div>
          </div>

          <div className="mt-2 flex items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Users className="h-3.5 w-3.5" />
              {h.population.toLocaleString()} persons
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Home className="h-3.5 w-3.5" />
              {h.households.toLocaleString()} HH
            </div>
          </div>

          <div className="mt-2 flex items-center gap-2">
            <PriorityBadge priority={h.relocation_priority.priority} />
            <span className="text-xs text-slate-500">Vulnerability: {h.vulnerability.level}</span>
          </div>
        </div>

        {/* Hazards */}
        <div className="border-b border-slate-800 p-3">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Active Hazards</h2>
          {h.hazards.length === 0 ? (
            <EmptyState variant="missing-hazard-layer" compact />
          ) : (
            <div className="flex flex-col gap-2">
              {h.hazards.map(hazard => (
                <div key={hazard.type} className={clsx('rounded border p-2.5', HAZARD_COLORS[hazard.type])}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold">{hazard.type}</span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-mono font-bold">{hazard.intensity}</span>
                      <DataTypeBadge type={hazard.data_type} />
                    </div>
                  </div>
                  <p className="text-2xs opacity-80 leading-relaxed">{hazard.description}</p>
                  <p className="mt-1 text-2xs opacity-50">Source: {hazard.source}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Vulnerability breakdown */}
        <div className="border-b border-slate-800 p-3">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Vulnerability</h2>
            <DataTypeBadge type={h.vulnerability.data_type} />
          </div>
          <div className="mb-3 flex items-center gap-2">
            <span className="text-2xl font-bold font-mono text-orange-400">{h.vulnerability.overall}</span>
            <span className="text-xs text-orange-400 font-semibold">{h.vulnerability.level}</span>
          </div>
          <div className="flex flex-col gap-2">
            <HazardBar label="Demographic" value={h.vulnerability.demographic} color="bg-orange-500" />
            <HazardBar label="Socioeconomic" value={h.vulnerability.socioeconomic} color="bg-orange-400" />
            <HazardBar label="Infrastructure" value={h.vulnerability.infrastructure} color="bg-orange-500" />
            <HazardBar label="Accessibility" value={h.vulnerability.accessibility} color="bg-orange-300" />
          </div>
          <p className="mt-2 text-2xs text-slate-600">
            Weights: Demographic 30% · Socioeconomic 20% · Infrastructure 25% · Accessibility 25%
          </p>
        </div>

        {/* Evidence chain */}
        <div className="border-b border-slate-800 p-3">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Evidence Chain</h2>
          <div>
            {h.evidence_chain.map(item => <EvidenceStep key={item.step} item={item} />)}
          </div>
        </div>

        {/* Historical context */}
        {'historical_context' in h && h.historical_context && (
          <div className="border-b border-slate-800 p-3">
            <div className="flex items-center gap-2 mb-2">
              <History className="h-3.5 w-3.5 text-slate-500" />
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Historical Context</h2>
              <DataTypeBadge type={h.historical_context.data_type} />
            </div>
            <div className="flex flex-col gap-1.5 mb-2">
              {h.historical_context.events.map(ev => (
                <div key={ev.year} className="flex gap-2 text-xs">
                  <span className="font-mono text-slate-500 flex-shrink-0">{ev.year}</span>
                  <span className="text-orange-400 flex-shrink-0">{ev.type}</span>
                  <span className="text-slate-400">{ev.impact}</span>
                </div>
              ))}
            </div>
            <div className="rounded border border-slate-800 bg-slate-900 p-2">
              <p className="text-2xs text-slate-500 leading-relaxed">{h.historical_context.gsi_2018_note}</p>
            </div>
          </div>
        )}

        {/* Permanent settlement suitability */}
        <div className="border-b border-slate-800 p-3">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="h-3.5 w-3.5 text-slate-500" />
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Permanent Settlement Suitability</h2>
          </div>
          <div className={clsx(
            'rounded border p-2.5 mb-2',
            h.permanent_settlement_suitable
              ? 'border-green-500/30 bg-green-500/8 text-green-400'
              : 'border-red-500/30 bg-red-500/8 text-red-400'
          )}>
            <span className="text-xs font-semibold">
              {h.permanent_settlement_suitable ? 'POTENTIALLY SUITABLE' : 'NOT SUITABLE — RED ZONE CANDIDATE'}
            </span>
          </div>
          <div className="flex items-start gap-2 rounded border border-slate-800 bg-slate-900 p-2">
            <Info className="h-3.5 w-3.5 text-slate-600 flex-shrink-0 mt-0.5" />
            <p className="text-2xs text-slate-500 leading-relaxed">{h.permanent_suitability_note}</p>
          </div>
        </div>

        {/* System recommendation */}
        <div className="p-3">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">System Recommendation</h2>
          <div className="rounded border border-emerald-500/30 bg-emerald-500/8 p-2.5 mb-3">
            <DataTypeBadge type="RECOMMENDATION" />
            <p className="mt-1.5 text-xs text-emerald-300 leading-relaxed">{h.system_recommendation}</p>
          </div>
          <div className="flex flex-col gap-2">
            <button
              onClick={() => navigate('/relocation')}
              className="flex items-center justify-between rounded border border-blue-500/30 bg-blue-600/10 px-3 py-2 text-xs font-semibold text-blue-400 hover:bg-blue-600/20 transition-colors"
            >
              Review Candidate Sites
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => navigate(`/habitations/${h.id}/decision`)}
              className="flex items-center justify-between rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800 transition-colors"
            >
              Explain This Risk
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* RIGHT — local GIS */}
      <div className="relative flex-1">
        <MapContainer
          habitations={selectedHabitation ? [selectedHabitation] : DEMO_HABITATIONS}
          selectedHabitationId={id}
          showHazardLayer={true}
          className="h-full w-full"
        />

        {/* Map layer legend — only layers actually rendered by the map */}
        <div className="absolute left-3 top-3 flex flex-col gap-1.5">
          <div className="rounded border border-slate-700 bg-slate-900/95 px-2.5 py-2">
            <div className="text-2xs text-slate-500 mb-1.5">Map Layers</div>
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="h-2 w-2 rounded-full bg-red-500 flex-shrink-0" />
              <span className="text-2xs text-slate-400">Habitation point (risk-graded)</span>
            </div>
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="h-2 w-2 rounded-sm bg-blue-500 flex-shrink-0" />
              <span className="text-2xs text-slate-400">Kerala 2019 flood event (Bhuvan/ISRO overlay)</span>
            </div>
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="h-2 w-2 rounded-sm bg-slate-500 flex-shrink-0" />
              <span className="text-2xs text-slate-400">Basemap: OpenStreetMap</span>
            </div>
            <p className="mt-1.5 text-2xs text-amber-500/70">Overlay is a historical event layer, not a live hazard feed; it renders only when the ISRO/NRSC WMS responds.</p>
          </div>
        </div>

        {/* Risk score overlay */}
        <div className="absolute right-3 top-3 rounded border border-slate-700 bg-slate-900/95 p-3">
          <div className="text-2xs text-slate-500 mb-1">{h.name}</div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-red-400">{h.risk.current}</span>
            <span className="text-xs text-slate-500">/100</span>
          </div>
          <div className={clsx(
            'text-xs font-mono',
            h.risk.change > 0 ? 'text-red-400' : 'text-green-400'
          )}>
            {h.risk.change > 0 ? '+' : ''}{h.risk.change} from baseline
          </div>
          <div className="mt-2">
            <PriorityBadge priority={h.relocation_priority.priority} size="lg" />
          </div>
        </div>
      </div>
    </div>
  )
}
