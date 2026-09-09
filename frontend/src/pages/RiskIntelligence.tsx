import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, TrendingDown, Users, AlertTriangle, ChevronRight } from 'lucide-react'
import { MapContainer } from '../components/map/MapContainer'
import { RiskBadge } from '../components/ui/RiskBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import {
  DEMO_HABITATIONS,
  DEMO_RISK_INTELLIGENCE,
} from '../data/idukki-seed'
import type { HabitationListItem, RiskIntelligencePanel } from '../types'
import { api } from '../api/client'
import { useApiWithFallback } from '../hooks/useApiWithFallback'
import clsx from 'clsx'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

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
          <FreshnessBadge status={riSource === 'api' ? 'DEMO' : 'DEMO'} />
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
