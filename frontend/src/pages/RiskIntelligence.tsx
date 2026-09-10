import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, TrendingDown, Users, AlertTriangle, ChevronRight, Radio, Activity } from 'lucide-react'
import { MapContainer } from '../components/map/MapContainer'
import { RiskBadge } from '../components/ui/RiskBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import {
  DEMO_HABITATIONS,
  DEMO_RISK_INTELLIGENCE,
} from '../data/idukki-seed'
import type {
  CurrentHazardsResponse,
  CurrentRiskResponse,
  HabitationListItem,
  HazardEvent,
  RiskIntelligencePanel,
  RiskTimelineResponse,
  SafeZonesResponse,
} from '../types'
import { api } from '../api/client'
import { useApiWithFallback } from '../hooks/useApiWithFallback'
import clsx from 'clsx'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line,
} from 'recharts'

const EMPTY_HAZARDS: CurrentHazardsResponse = {
  data_status: 'DEMO',
  generated_at: '',
  region: 'all',
  ttl_seconds: 0,
  events: [],
  feature_collection: { type: 'FeatureCollection', features: [] },
}

const EMPTY_CURRENT_RISK: CurrentRiskResponse = {
  data_status: 'DEMO',
  district_id: 'idukki',
  computed_at: '',
  mode: 'current',
  basis: { weather: {}, hazard_events: {}, soil_saturation: {}, river_level: {} },
  note: '',
  habitations: [],
  persisted: false,
  live_habitations: 0,
}

const EMPTY_TIMELINE: RiskTimelineResponse = {
  data_status: 'EMPTY',
  points: [],
}

const EMPTY_SAFE_ZONES: SafeZonesResponse = {
  type: 'FeatureCollection',
  features: [],
  data_status: 'EMPTY',
  status_counts: { green: 0, yellow: 0, red: 0 },
}

const SEVERITY_COLORS: Record<string, string> = {
  SEVERE: '#ef4444',
  HIGH: '#f97316',
  MODERATE: '#eab308',
  LOW: '#3b82f6',
}

type RiskMode = 'current' | 'baseline' | 'change'

const MODE_LABELS: Record<RiskMode, string> = {
  current: 'CURRENT',
  baseline: 'BASELINE',
  change: 'CHANGE / DELTA',
}

// Derive display values per mode
function habitationDisplayScore(h: HabitationListItem, mode: RiskMode): number {
  if (mode === 'baseline') {
    // Baseline = current - change
    return h.risk_score - h.risk_change
  }
  if (mode === 'change') return Math.abs(h.risk_change)
  return h.risk_score
}

const RISK_DIST_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
}

export function RiskIntelligence() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<RiskMode>('current')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showHazard, setShowHazard] = useState(true)
  const [showSafeZones, setShowSafeZones] = useState(true)
  const [discovering, setDiscovering] = useState(false)

  // Live data: risk intelligence panel + habitation list (API-first, the
  // labelled demo seed is the automatic fallback).
  const { data: apiRi, source: riSource } = useApiWithFallback<RiskIntelligencePanel>(
    () => api.getRiskIntelligence('idukki', mode) as Promise<RiskIntelligencePanel>,
    DEMO_RISK_INTELLIGENCE as unknown as RiskIntelligencePanel,
    [mode],
  )
  const { data: apiHabitations, source: habSource } = useApiWithFallback<{
    habitations: HabitationListItem[]
  }>(
    () => api.getHabitations('idukki') as Promise<{ habitations: HabitationListItem[] }>,
    { habitations: DEMO_HABITATIONS as unknown as HabitationListItem[] },
    [],
  )

  const ri = apiRi ?? (DEMO_RISK_INTELLIGENCE as unknown as RiskIntelligencePanel)
  const habitations: HabitationListItem[] = apiHabitations?.habitations ?? DEMO_HABITATIONS

  // Live active hazard events (Slice 2). API-first; an empty operational
  // picture falls back to an empty feature set, never fabricated events.
  const { data: hazards } = useApiWithFallback<CurrentHazardsResponse>(
    () => api.getCurrentHazards() as Promise<CurrentHazardsResponse>,
    EMPTY_HAZARDS,
    [],
  )
  const activeEvents: HazardEvent[] = hazards?.events ?? []
  const hazardFeatures = (hazards?.feature_collection ?? EMPTY_HAZARDS.feature_collection) as GeoJSON.FeatureCollection

  // Safe-zone candidates (Slice 4) — persisted safe relocation pockets.
  const { data: safeZones, refetch: safeZonesRefetch } = useApiWithFallback<SafeZonesResponse>(
    () => api.getSafeZones('idukki') as Promise<SafeZonesResponse>,
    EMPTY_SAFE_ZONES,
    [],
  )
  const safeZoneFeatures = safeZones as unknown as GeoJSON.FeatureCollection

  // Dynamic current risk (Slice 3) — live escalation fed by weather/events.
  const { data: currentRisk } = useApiWithFallback<CurrentRiskResponse>(
    () => api.getCurrentRisk('idukki') as Promise<CurrentRiskResponse>,
    EMPTY_CURRENT_RISK,
    [],
  )
  const riskLive = currentRisk?.data_status === 'LIVE'

  // Recompute timeline for the selected habitation (risk deltas over time).
  const { data: timeline } = useApiWithFallback<RiskTimelineResponse>(
    selectedId
      ? () => api.getRiskTimeline(selectedId) as Promise<RiskTimelineResponse>
      : async () => EMPTY_TIMELINE,
    EMPTY_TIMELINE,
    [selectedId],
  )

  const distChartData = [
    { name: 'Critical', value: ri.risk_distribution.critical, key: 'critical' },
    { name: 'High', value: ri.risk_distribution.high, key: 'high' },
    { name: 'Medium', value: ri.risk_distribution.medium, key: 'medium' },
    { name: 'Low', value: ri.risk_distribution.low, key: 'low' },
  ]

  const sorted = [...habitations].sort((a, b) => {
    if (mode === 'change') return Math.abs(b.risk_change) - Math.abs(a.risk_change)
    if (mode === 'baseline') return (b.risk_score - b.risk_change) - (a.risk_score - a.risk_change)
    return b.risk_score - a.risk_score
  })

  const selected = selectedId ? habitations.find(h => h.id === selectedId) : null

  const runDiscovery = async () => {
    setDiscovering(true)
    try {
      await api.discoverSafeZones('idukki')
      safeZonesRefetch()
    } catch (err) {
      console.warn('[Sentinel AI] safe-zone discovery failed:', err)
    } finally {
      setDiscovering(false)
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* LEFT — layers & filters */}
      <div className="flex w-56 flex-shrink-0 flex-col gap-3 overflow-y-auto border-r border-slate-800 bg-slate-950 p-3">
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">View Mode</h2>
          <div className="flex flex-col gap-1">
            {(['current', 'baseline', 'change'] as RiskMode[]).map(m => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={clsx(
                  'rounded border px-2.5 py-1.5 text-left text-xs font-medium transition-colors',
                  mode === m
                    ? 'border-blue-500/50 bg-blue-600/20 text-blue-300'
                    : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-300'
                )}
              >
                {MODE_LABELS[m]}
              </button>
            ))}
          </div>
        </div>

        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Layers</h2>
          <div className="flex flex-col gap-1.5">
            {[
              { id: 'hazard', label: 'Hazard overlay', active: showHazard, toggle: () => setShowHazard(v => !v) },
              { id: 'safezones', label: 'Safe-zone candidates', active: showSafeZones, toggle: () => setShowSafeZones(v => !v) },
            ].map(layer => (
              <button
                key={layer.id}
                onClick={layer.toggle}
                className={clsx(
                  'flex items-center gap-2 rounded border px-2 py-1.5 text-xs transition-colors',
                  layer.active
                    ? 'border-teal-500/40 bg-teal-500/10 text-teal-400'
                    : 'border-slate-800 bg-slate-900 text-slate-500 hover:text-slate-400'
                )}
              >
                <span className={clsx('h-2 w-2 rounded-full', layer.active ? 'bg-teal-400' : 'bg-slate-700')} />
                {layer.label}
              </button>
            ))}
            <div className="rounded border border-slate-800 bg-slate-900 px-2 py-1.5">
              <div className="text-2xs text-slate-600 mb-1">Bhuvan WMS</div>
              <div className="text-2xs text-amber-600">DEMO — may be unavailable</div>
            </div>
          </div>
        </div>

        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Risk Legend</h2>
          {[
            { label: 'Critical (80+)', color: 'bg-red-500' },
            { label: 'High (60–79)', color: 'bg-orange-500' },
            { label: 'Medium (40–59)', color: 'bg-yellow-500' },
            { label: 'Low (<40)', color: 'bg-green-500' },
          ].map(({ label, color }) => (
            <div key={label} className="flex items-center gap-1.5 mb-1">
              <span className={clsx('h-2 w-2 rounded-full flex-shrink-0', color)} />
              <span className="text-2xs text-slate-400">{label}</span>
            </div>
          ))}
        </div>

        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Active Hazard Severity</h2>
          {(['SEVERE', 'HIGH', 'MODERATE', 'LOW'] as const).map(sev => (
            <div key={sev} className="flex items-center gap-1.5 mb-1">
              <span
                className="h-2 w-2 rounded-full flex-shrink-0"
                style={{ background: SEVERITY_COLORS[sev] }}
              />
              <span className="text-2xs text-slate-400">{sev}</span>
            </div>
          ))}
          <p className="text-2xs text-slate-600 leading-relaxed mt-1">
            Circular buffers are estimated exposure reach from live weather/quakes — not surveyed footprints.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Habitations</h2>
          <div className="flex flex-col gap-1">
            {sorted.map(h => {
              const displayScore = habitationDisplayScore(h, mode)
              return (
                <button
                  key={h.id}
                  onClick={() => setSelectedId(h.id)}
                  className={clsx(
                    'flex items-center gap-2 rounded border px-2 py-1.5 text-left transition-colors',
                    selectedId === h.id
                      ? 'border-blue-500/40 bg-blue-600/15'
                      : 'border-transparent hover:bg-slate-800'
                  )}
                >
                  <RiskBadge score={mode === 'change' ? h.risk_score : displayScore} size="sm" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-slate-300 truncate">{h.name}</div>
                    {mode === 'change' && (
                      <div className={clsx(
                        'text-2xs font-mono',
                        h.risk_change > 0 ? 'text-red-400' : 'text-green-400'
                      )}>
                        {h.risk_change > 0 ? '+' : ''}{h.risk_change}
                      </div>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* CENTER — GIS workspace */}
      <div className="relative flex-1">
        <MapContainer
          habitations={habitations}
          selectedHabitationId={selectedId}
          onHabitationSelect={setSelectedId}
          showHazardLayer={showHazard}
          hazardGeoJSON={hazardFeatures}
          safeZonesGeoJSON={safeZoneFeatures}
          showSafeZonesLayer={showSafeZones}
          // This page shows its own selected-habitation card; disable the
          // inline map popup so one click never produces two popups with the
          // same content.
          clickPopup={false}
          className="h-full w-full"
        />

        {/* Mode badge */}
        <div className="absolute left-3 top-3">
          <div className="rounded border border-blue-500/40 bg-slate-950/95 px-3 py-1.5">
            <span className="text-xs font-semibold text-blue-400">{MODE_LABELS[mode]}</span>
            <span className="ml-2 text-2xs text-slate-500">Idukki District</span>
          </div>
        </div>

        {/* Selected habitation popup */}
        {selected && (
          <div className="absolute right-3 top-3 w-60 rounded-xl border border-slate-500/70 bg-slate-900/95 p-3.5 shadow-2xl shadow-black/60">
            <div className="text-2xs font-semibold uppercase tracking-wide text-blue-300 mb-0.5">{selected.ward} · {selected.taluk}</div>
            <div className="text-[15px] font-bold text-white mb-2.5">{selected.name}</div>
            <div className="flex items-center gap-4 mb-2.5">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Risk</div>
                <RiskBadge score={selected.risk_score} size="md" />
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Change</div>
                <span className={clsx(
                  'text-lg font-bold font-mono',
                  selected.risk_change > 0 ? 'text-red-400' : 'text-green-400'
                )}>
                  {selected.risk_change > 0 ? '+' : ''}{selected.risk_change}
                </span>
              </div>
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">Population</div>
                <div className="text-sm font-bold text-slate-100 leading-tight">
                  {selected.population.toLocaleString()}
                  <span className="ml-1 text-[10px] font-medium text-slate-400">persons</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 mb-2.5">
              <PriorityBadge priority={selected.priority} size="sm" />
              <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-200">{selected.primary_hazard}</span>
            </div>
            <button
              onClick={() => navigate(`/habitations/${selected.id}`)}
              className="w-full rounded-md bg-blue-600 px-2 py-1.5 text-xs font-bold text-white shadow-md shadow-blue-950/50 hover:bg-blue-500 active:bg-blue-600 transition-colors"
            >
              Investigate →
            </button>
          </div>
        )}
      </div>

      {/* RIGHT — risk intelligence panel */}
      <div className="flex w-64 flex-shrink-0 flex-col gap-3 overflow-y-auto border-l border-slate-800 bg-slate-950 p-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risk Intelligence</h2>
          <FreshnessBadge status="DEMO" />
        </div>

        {/* Provenance line — panel + list sources differ per endpoint */}
        <div className="rounded border border-slate-800 bg-slate-900/50 px-2 py-1.5 text-2xs text-slate-500">
          Panel: {riSource === 'api' ? '● API engine' : '● demo seed'} ·
          List: {habSource === 'api' ? '● API' : '● seed'}
        </div>

        {/* Distribution chart */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500 mb-2">Risk Distribution — Idukki</div>
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={distChartData} barSize={20}>
              <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 4, fontSize: 11 }}
                labelStyle={{ color: '#94a3b8' }}
                itemStyle={{ color: '#cbd5e1' }}
              />
              <Bar dataKey="value" radius={[2, 2, 0, 0]}>
                {distChartData.map(entry => (
                  <Cell key={entry.key} fill={RISK_DIST_COLORS[entry.key]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div className="mt-1 grid grid-cols-2 gap-1">
            {distChartData.map(d => (
              <div key={d.key} className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: RISK_DIST_COLORS[d.key] }} />
                <span className="text-2xs text-slate-500">{d.name}: <span className="text-slate-300 font-mono">{d.value}</span></span>
              </div>
            ))}
          </div>
        </div>

        {/* Top drivers */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500 mb-2">Top Risk Drivers</div>
          <div className="flex flex-col gap-2">
            {ri.top_drivers.map((d, i) => (
              <div key={d.driver}>
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-xs text-slate-300">{d.driver}</span>
                  <DataTypeBadge type={d.data_type} />
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-blue-500"
                      style={{ width: `${d.contribution}%`, opacity: 1 - i * 0.15 }}
                    />
                  </div>
                  <span className="text-2xs font-mono text-slate-400 w-6 text-right">{d.contribution}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Significant shifts */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500 mb-2">Significant Shifts</div>
          <div className="flex flex-col gap-1.5">
            {ri.significant_shifts.map(s => (
              <div key={s.habitation} className="flex items-center justify-between">
                <button
                  onClick={() => {
                    const h = habitations.find(x => x.name === s.habitation)
                    if (h) setSelectedId(h.id)
                  }}
                  className="text-xs text-slate-300 hover:text-blue-400 text-left"
                >
                  {s.habitation}
                </button>
                <div className="flex items-center gap-1">
                  {s.direction === 'increase'
                    ? <TrendingUp className="h-3 w-3 text-red-400" />
                    : <TrendingDown className="h-3 w-3 text-green-400" />}
                  <span className={clsx(
                    'text-xs font-mono font-semibold',
                    s.direction === 'increase' ? 'text-red-400' : 'text-green-400'
                  )}>
                    {s.direction === 'increase' ? '+' : '-'}{s.change}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Live escalation — dynamic current risk fed by live weather/events (Slice 3) */}
        {riskLive && (
          <div className="rounded-lg border border-teal-500/30 bg-teal-500/5 p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5">
                <Activity className="h-3.5 w-3.5 text-teal-400" />
                <span className="text-2xs text-slate-400">Live Escalation</span>
              </div>
              <span className="rounded px-1.5 py-0.5 text-2xs font-mono font-semibold bg-teal-500/10 text-teal-400">
                {currentRisk?.data_status ?? 'LIVE'}
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              {[...(currentRisk?.habitations ?? [])]
                .sort((a, b) => b.current_score - a.current_score)
                .map(h => (
                  <div key={h.id} className="rounded border border-slate-800 bg-slate-950/60 p-2">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-slate-200 truncate">{h.name}</span>
                      <span className="text-xs font-mono font-bold text-teal-300">{h.current_score_rounded}</span>
                    </div>
                    <div className="mb-1 h-1 rounded-full bg-slate-800">
                      <div className="h-full rounded-full bg-teal-500" style={{ width: `${h.current_score}%` }} />
                    </div>
                    <div className="flex items-center justify-between text-2xs text-slate-500">
                      <span>base {h.baseline_score}</span>
                      <span className={clsx('font-mono', h.event_escalation > 0 ? 'text-amber-400' : 'text-slate-600')}>
                        {h.event_escalation > 0.004 ? `+${h.event_escalation.toFixed(1)} esc` : '+0.0'}
                      </span>
                      <span>now {h.current_score}</span>
                    </div>
                    <div className="mt-1 flex items-center gap-1 text-2xs text-slate-600">
                      <span>{h.live_inputs?.rainfall_mm_72h ?? '—'}mm/72h</span>
                      <span>·</span>
                      <span>haz {h.live_inputs?.hazard_intensity ?? 0}</span>
                      <span>·</span>
                      <span className="truncate">{h.live_inputs?.station_id}</span>
                    </div>
                  </div>
                ))}
            </div>
            <p className="text-2xs text-slate-600 leading-relaxed mt-2">
              Weather {currentRisk?.basis?.weather?.data_status ?? 'n/a'} · active
              events {currentRisk?.basis?.hazard_events?.events_considered ?? 0} · soil /
              river UNAVAILABLE (feed as 0)
            </p>
          </div>
        )}

        {/* Risk delta timeline (Slice 3) — recompute history for the selection */}
        {selectedId && riskLive && timeline && timeline.points.length > 0 && (
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xs text-slate-500">Risk Delta Timeline</span>
              <span className="text-2xs text-slate-500 truncate">{selected?.name}</span>
            </div>
            <ResponsiveContainer width="100%" height={90}>
              <LineChart data={[...timeline.points].reverse()}>
                <XAxis dataKey="computed_at" hide />
                <YAxis hide domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 4, fontSize: 11 }}
                  labelStyle={{ color: '#94a3b8' }}
                  itemStyle={{ color: '#cbd5e1' }}
                  labelFormatter={(v) => new Date(String(v)).toLocaleString()}
                />
                <Line type="monotone" dataKey="current_score" stroke="#2dd4bf" strokeWidth={1.5} dot={{ r: 2 }} />
                <Line type="monotone" dataKey="baseline_score" stroke="#64748b" strokeWidth={1} strokeDasharray="3 3" dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <div className="flex items-center gap-3 text-2xs text-slate-500 mt-1">
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-3 rounded bg-teal-500" /> current
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-3 rounded bg-slate-600" /> baseline
              </span>
            </div>
          </div>
        )}

        {/* Active hazards — live operational picture (Slice 2) */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Radio className={clsx('h-3.5 w-3.5', activeEvents.length ? 'text-red-400' : 'text-slate-600')} />
              <span className="text-2xs text-slate-500">Active Hazards</span>
            </div>
            <span className={clsx(
              'rounded px-1.5 py-0.5 text-2xs font-mono font-semibold',
              hazards?.data_status === 'LIVE'
                ? 'bg-green-500/10 text-green-400'
                : 'bg-slate-800 text-slate-500'
            )}>
              {hazards?.data_status ?? 'DEMO'}
            </span>
          </div>
          {activeEvents.length === 0 ? (
            <p className="text-2xs text-slate-500 leading-relaxed">
              No active hazard events — rainfall below trigger, no alert-level
              quakes in the monitoring window.
            </p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {activeEvents.map(ev => (
                <div key={ev.event_id} className="rounded border border-slate-800 bg-slate-950/60 p-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-slate-200">{ev.hazard_type}</span>
                    <span
                      className="rounded px-1.5 py-0.5 text-2xs font-mono font-bold text-slate-950"
                      style={{ background: SEVERITY_COLORS[ev.severity_level] ?? '#94a3b8' }}
                    >
                      {ev.severity_level} {ev.severity_score}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-2xs text-slate-500">
                      {new Date(ev.started_at).toLocaleDateString()}
                    </span>
                    <span className="text-2xs text-slate-500">
                      {ev.buffer_radius_km} km reach
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-1">
                    <DataTypeBadge type={ev.data_type} />
                    {ev.data_type === 'OBSERVED' && (
                      <span className="text-2xs text-slate-500 truncate">
                        {String(ev.event_meta?.place ?? ev.event_meta?.station_id ?? '')}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
          {hazards?.source_basis && (
            <p className="text-2xs text-slate-600 leading-relaxed mt-2">
              Sources: weather {hazards.source_basis.weather?.data_status ?? 'n/a'} ·
              quakes {hazards.source_basis.earthquakes?.data_status ?? 'n/a'}
            </p>
          )}
        </div>

        {/* Safe-zone candidates (Slice 4) — relocation pockets cleared of hard
            constraints (fault buffer, active hazard exclusion). */}
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <span className="text-2xs text-slate-400">Safe-Zone Candidates</span>
            </div>
            <button
              onClick={runDiscovery}
              disabled={discovering}
              className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-2xs font-semibold text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-colors"
            >
              {discovering ? 'Discovering…' : 'Rediscover'}
            </button>
          </div>

          <div className="flex items-center gap-3 mb-2">
            {(['green', 'yellow', 'red'] as const).map(status => (
              <div key={status} className="flex items-center gap-1">
                <span className={clsx(
                  'h-2 w-2 rounded-full',
                  status === 'green' ? 'bg-emerald-500' : status === 'yellow' ? 'bg-yellow-500' : 'bg-red-500'
                )} />
                <span className="text-2xs text-slate-400">{status}:</span>
                <span className="text-2xs font-mono font-semibold text-slate-200">
                  {safeZones?.status_counts?.[status] ?? 0}
                </span>
              </div>
            ))}
          </div>

          {safeZones && safeZones.features.length > 0 ? (
            <>
              <div className="flex flex-col gap-1">
                {[...safeZones.features]
                  .filter(f => f.properties.status === 'green')
                  .slice(0, 3)
                  .map(f => (
                    <div key={f.properties.id} className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/60 px-2 py-1.5">
                      <span className="text-2xs text-slate-300 truncate">
                        {f.properties.name ?? f.properties.id}
                      </span>
                      <span className="text-2xs font-mono text-slate-500">
                        {f.properties.suitability_score != null
                          ? `${f.properties.suitability_score.toFixed(0)} suit`
                          : '—'}
                      </span>
                    </div>
                  ))}
              </div>
              {safeZones.status_counts?.green === 0 && (
                <p className="text-2xs text-amber-500/90 leading-relaxed mt-1">
                  No green pockets — all grid cells fail a hard constraint or
                  score below threshold.
                </p>
              )}
            </>
          ) : (
            <p className="text-2xs text-slate-500 leading-relaxed">
              No persisted candidates yet — run Rediscover to map safe relocation pockets.
            </p>
          )}

          {safeZones?.geometry_source && (
            <p className="text-2xs text-slate-600 leading-relaxed mt-2">{safeZones.geometry_source}</p>
          )}
          {safeZones?.empty_reason && (
            <p className="text-2xs text-amber-500/80 leading-relaxed mt-1">{safeZones.empty_reason}</p>
          )}
        </div>

        {/* Human impact */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-2xs text-slate-500">Human Impact</div>
            <DataTypeBadge type={ri.human_impact.data_type} />
          </div>
          <div className="flex items-center gap-2 mb-1">
            <Users className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-xs text-slate-400">At risk:</span>
            <span className="text-sm font-bold font-mono text-yellow-400">
              {ri.human_impact.total_at_risk.toLocaleString()}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
            <span className="text-xs text-slate-400">Immediate:</span>
            <span className="text-sm font-bold font-mono text-red-400">
              {ri.human_impact.immediate_action.toLocaleString()}
            </span>
          </div>
        </div>

        {/* CTA — connects to relocation pipeline */}
        {selectedId && (
          <button
            onClick={() => navigate(`/habitations/${selectedId}`)}
            className="flex items-center justify-between rounded border border-blue-500/30 bg-blue-600/10 px-3 py-2 text-xs font-semibold text-blue-400 hover:bg-blue-600/20 transition-colors"
          >
            Investigate selected habitation
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        )}

        <div className="rounded border border-slate-800 bg-slate-900/50 p-2">
          <p className="text-2xs text-slate-600 leading-relaxed">
            Risk scores are DERIVED by Sentinel AI engine. Operational risk is separate from permanent settlement suitability. Data labelled DEMO.
          </p>
        </div>
      </div>
    </div>
  )
}
