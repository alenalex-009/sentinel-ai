import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, TrendingUp, TrendingDown, Minus, ChevronRight, ArrowRight } from 'lucide-react'
import { RiskBadge } from '../components/ui/RiskBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { DEMO_HABITATIONS, DEMO_DISTRICT_OVERVIEW } from '../data/idukki-seed'
import type { Priority } from '../types'
import clsx from 'clsx'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'

// RPI scores derived from habitation data using the configured model
// RPI = 0.35×Risk + 0.20×Vulnerability + 0.15×ExposedPop + 0.15×Historical + 0.15×Urgency
// These are DERIVED values — not official government assessments
const RPI_DATA = [
  { id: 'munnar-central', rpi: 88, vulnerability: 74, historical: 94, urgency: 87 },
  { id: 'rajakkad',       rpi: 78, vulnerability: 68, historical: 71, urgency: 76 },
  { id: 'kanthalloor',   rpi: 61, vulnerability: 59, historical: 55, urgency: 63 },
  { id: 'marayoor',      rpi: 52, vulnerability: 51, historical: 48, urgency: 54 },
  { id: 'adimali',       rpi: 38, vulnerability: 42, historical: 31, urgency: 35 },
]

const PRIORITY_FILTER_OPTIONS: Array<Priority | 'ALL'> = [
  'ALL', 'IMMEDIATE', 'SHORT-TERM', 'MEDIUM-TERM', 'MONITOR',
]

const RISK_COLORS: Record<string, string> = {
  'munnar-central': '#ef4444',
  'rajakkad': '#ef4444',
  'kanthalloor': '#f97316',
  'marayoor': '#f97316',
  'adimali': '#eab308',
}

export function Priorities() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Priority | 'ALL'>('ALL')
  const d = DEMO_DISTRICT_OVERVIEW.district

  const enriched = DEMO_HABITATIONS.map(h => ({
    ...h,
    ...RPI_DATA.find(r => r.id === h.id)!,
  })).sort((a, b) => b.rpi - a.rpi)

  const filtered = filter === 'ALL'
    ? enriched
    : enriched.filter(h => h.priority === filter)

  const chartData = enriched.map(h => ({
    name: h.name.split(' ')[0],
    rpi: RPI_DATA.find(r => r.id === h.id)!.rpi,
    risk: h.risk_score,
  }))

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Top summary bar */}
      <div className="flex items-center gap-4 border-b border-slate-800 bg-slate-950 px-4 py-3">
        <div className="flex items-center gap-6">
          {[
            { label: 'IMMEDIATE', value: d.critical_habitations, color: 'text-red-400' },
            { label: 'HIGH RISK', value: d.high_risk_habitations, color: 'text-orange-400' },
            { label: 'POPULATION AT RISK', value: d.total_population_at_risk.toLocaleString(), color: 'text-yellow-400' },
            { label: 'NEED RELOCATION', value: d.immediate_relocation_needed.toLocaleString(), color: 'text-red-400' },
          ].map(({ label, value, color }) => (
            <div key={label}>
              <div className="text-2xs text-slate-600 uppercase tracking-wide">{label}</div>
              <div className={clsx('text-lg font-bold font-mono', color)}>{value}</div>
            </div>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-3">
          <DataTypeBadge type="DERIVED" />
          <FreshnessBadge status="DEMO" />
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* LEFT — chart + filters */}
        <div className="flex w-64 flex-shrink-0 flex-col gap-3 overflow-y-auto border-r border-slate-800 bg-slate-950 p-3">
          {/* RPI chart */}
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
            <div className="text-2xs text-slate-500 mb-2">RPI Score by Habitation</div>
            <ResponsiveContainer width="100%" height={120}>
              <BarChart data={chartData} barSize={16} layout="vertical" margin={{ left: -10 }}>
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 9, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 9, fill: '#64748b' }} axisLine={false} tickLine={false} width={50} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 4, fontSize: 11 }}
                />
                <Bar dataKey="rpi" radius={[0, 2, 2, 0]}>
                  {chartData.map(entry => (
                    <Cell key={entry.name} fill={RISK_COLORS[enriched.find(h => h.name.startsWith(entry.name))?.id || ''] || '#64748b'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Priority filter */}
          <div>
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Filter by Priority</div>
            <div className="flex flex-col gap-1">
              {PRIORITY_FILTER_OPTIONS.map(opt => (
                <button
                  key={opt}
                  onClick={() => setFilter(opt)}
                  className={clsx(
                    'rounded border px-2.5 py-1.5 text-left text-xs font-medium transition-colors',
                    filter === opt
                      ? 'border-blue-500/50 bg-blue-600/15 text-blue-300'
                      : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-300'
                  )}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/50 p-2.5">
            <p className="text-2xs text-slate-600 leading-relaxed">
              RPI = 0.35×Risk + 0.20×Vulnerability + 0.15×Population + 0.15×Historical + 0.15×Urgency.
              Configurable baseline weights — not official government formula.
            </p>
          </div>
        </div>

        {/* RIGHT — ranked table */}
        <div className="flex flex-1 flex-col overflow-hidden p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h1 className="text-sm font-semibold text-slate-200">Risk & Relocation Priorities — Idukki</h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Ranked by Relocation Priority Index (RPI). {filtered.length} habitations shown.
              </p>
            </div>
          </div>

          <div className="flex-1 overflow-auto rounded-lg border border-slate-800">
            <table className="w-full">
              <thead className="sticky top-0 bg-slate-900 z-10">
                <tr className="border-b border-slate-800">
                  {['Rank', 'Habitation', 'Population', 'Risk', 'Δ Change', 'Vulnerability', 'RPI', 'Priority', 'Action'].map(col => (
                    <th key={col} className="px-3 py-2.5 text-left text-2xs font-semibold uppercase tracking-wide text-slate-500">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((h, idx) => {
                  const changeIcon = h.risk_change > 0
                    ? <TrendingUp className="h-3 w-3 text-red-400" />
                    : h.risk_change < 0
                    ? <TrendingDown className="h-3 w-3 text-green-400" />
                    : <Minus className="h-3 w-3 text-slate-600" />

                  return (
                    <tr
                      key={h.id}
                      className="border-b border-slate-800/50 hover:bg-slate-900/60 cursor-pointer"
                      onClick={() => navigate(`/habitations/${h.id}`)}
                    >
                      <td className="px-3 py-3">
                        <span className="text-sm font-bold font-mono text-slate-500">#{idx + 1}</span>
                      </td>
                      <td className="px-3 py-3">
                        <div className="text-sm font-semibold text-slate-200">{h.name}</div>
                        <div className="text-2xs text-slate-500">{h.ward} · {h.taluk}</div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5">
                          <Users className="h-3 w-3 text-slate-600" />
                          <span className="text-xs font-mono text-slate-300">{h.population.toLocaleString()}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <RiskBadge score={h.risk_score} size="sm" />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1">
                          {changeIcon}
                          <span className={clsx(
                            'text-xs font-mono font-semibold',
                            h.risk_change > 0 ? 'text-red-400'
                            : h.risk_change < 0 ? 'text-green-400'
                            : 'text-slate-600'
                          )}>
                            {h.risk_change > 0 ? '+' : ''}{h.risk_change}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5">
                          <div className="w-16 h-1.5 rounded-full bg-slate-800">
                            <div
                              className="h-full rounded-full bg-orange-500"
                              style={{ width: `${h.vulnerability}%` }}
                            />
                          </div>
                          <span className="text-xs font-mono text-slate-400">{h.vulnerability}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-bold font-mono text-slate-200">{h.rpi}</span>
                          <DataTypeBadge type="DERIVED" />
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <PriorityBadge priority={h.priority} size="sm" />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={e => { e.stopPropagation(); navigate(`/habitations/${h.id}`) }}
                            className="flex items-center gap-1 text-2xs text-blue-400 hover:text-blue-300"
                          >
                            Investigate <ChevronRight className="h-3 w-3" />
                          </button>
                          {h.priority === 'IMMEDIATE' && (
                            <button
                              onClick={e => { e.stopPropagation(); navigate('/relocation') }}
                              className="flex items-center gap-1 text-2xs text-emerald-400 hover:text-emerald-300"
                            >
                              Relocate <ArrowRight className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
