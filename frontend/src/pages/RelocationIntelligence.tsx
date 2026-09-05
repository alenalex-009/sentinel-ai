import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
   Users, AlertTriangle, CheckCircle, XCircle,
  ChevronRight, Info, ArrowRight,
} from 'lucide-react'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { SiteScreeningMap } from '../components/map/SiteScreeningMap'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { RiskBadge } from '../components/ui/RiskBadge'
import {
  DEMO_MUNNAR_CENTRAL,
  DEMO_RELOCATION_DEMAND,
  DEMO_CANDIDATE_SITES,
  DEMO_CAPACITY_ASSESSMENTS,
  DEMO_OPTIMIZATION_RESULT,
} from '../data/idukki-seed'
import type { CandidateSite, CapacityAssessment } from '../types'
import clsx from 'clsx'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, Cell, ReferenceLine,
} from 'recharts'

type Tab = 'sites' | 'suitability' | 'capacity' | 'allocation'

const TAB_LABELS: Record<Tab, string> = {
  sites: 'Candidate Sites',
  suitability: 'Suitability',
  capacity: 'Capacity',
  allocation: 'Allocation',
}

function SuitabilityBar({ label, value, max = 100 }: { label: string; value: number; max?: number }) {
  const pct = (value / max) * 100
  const color =
    value >= 80 ? 'bg-green-500'
    : value >= 60 ? 'bg-teal-500'
    : value >= 40 ? 'bg-yellow-500'
    : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <span className="w-28 text-xs text-slate-400 flex-shrink-0 truncate">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-slate-800">
        <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-7 text-right text-xs font-mono text-slate-300">{value}</span>
    </div>
  )
}

function SiteCard({
  site, selected, onSelect,
}: {
  site: CandidateSite
  selected: boolean
  onSelect: () => void
}) {
  const cap = DEMO_CAPACITY_ASSESSMENTS[site.id]
  const canAbsorb = cap.can_absorb_alone
  return (
    <button
      onClick={onSelect}
      className={clsx(
        'w-full rounded-lg border p-3 text-left transition-colors',
        selected
          ? 'border-blue-500/50 bg-blue-600/10'
          : 'border-slate-800 bg-slate-900 hover:border-slate-700'
      )}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <div className="text-xs font-semibold text-slate-200">{site.name}</div>
          <div className="text-2xs text-slate-500 mt-0.5">DEMO/ESTIMATED distance — {site.distance_km} km (seed input, not a measured road distance)</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="text-lg font-bold font-mono text-teal-400">{site.suitability_score}</span>
          <DataTypeBadge type={site.data_type} />
        </div>
      </div>
      <div className="flex items-center gap-3 mb-2">
        <div>
          <div className="text-2xs text-slate-500">C_safe</div>
          <div className="text-sm font-bold font-mono text-slate-200">{cap.c_safe.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-2xs text-slate-500">Bottleneck</div>
          <div className="text-xs font-semibold text-amber-400 uppercase">{cap.bottleneck}</div>
        </div>
        <div className="ml-auto">
          {canAbsorb
            ? <span className="flex items-center gap-1 text-2xs text-green-400"><CheckCircle className="h-3 w-3" /> Can absorb alone</span>
            : <span className="flex items-center gap-1 text-2xs text-orange-400"><XCircle className="h-3 w-3" /> Needs multi-site</span>
          }
        </div>
      </div>
      <div className="text-2xs text-slate-600 leading-relaxed line-clamp-2">{site.notes}</div>
    </button>
  )
}

function CapacityPanel({ cap }: { cap: CapacityAssessment }) {
  const demand = cap.required_population
  const chartData = cap.dimensions.map(d => ({
    name: d.name.charAt(0).toUpperCase() + d.name.slice(1),
    capacity: d.capacity,
    demand,
    isBottleneck: d.name === cap.bottleneck,
  }))

  return (
    <div className="flex flex-col gap-3">
      {/* C_safe summary */}
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded border border-slate-800 bg-slate-900 p-2.5 text-center">
          <div className="text-2xs text-slate-500">C_safe</div>
          <div className="text-xl font-bold font-mono text-teal-400">{cap.c_safe.toLocaleString()}</div>
          <div className="text-2xs text-slate-500">persons</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-2.5 text-center">
          <div className="text-2xs text-slate-500">Demand</div>
          <div className="text-xl font-bold font-mono text-slate-200">{demand.toLocaleString()}</div>
          <div className="text-2xs text-slate-500">persons</div>
        </div>
        <div className={clsx(
          'rounded border p-2.5 text-center',
          cap.surplus_deficit >= 0
            ? 'border-green-500/30 bg-green-500/8'
            : 'border-red-500/30 bg-red-500/8'
        )}>
          <div className="text-2xs text-slate-500">Gap / Surplus</div>
          <div className={clsx(
            'text-xl font-bold font-mono',
            cap.surplus_deficit >= 0 ? 'text-green-400' : 'text-red-400'
          )}>
            {cap.surplus_deficit >= 0 ? '+' : ''}{cap.surplus_deficit.toLocaleString()}
          </div>
          <div className="text-2xs text-slate-500">persons</div>
        </div>
      </div>

      {/* Bottleneck callout */}
      <div className="rounded border border-amber-500/30 bg-amber-500/8 px-3 py-2">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
          <span className="text-xs text-amber-300">
            Binding constraint: <strong className="uppercase">{cap.bottleneck}</strong> — limits capacity to {cap.c_safe.toLocaleString()} persons
          </span>
        </div>
      </div>

      {/* Dimension bars */}
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400">Capacity by Dimension</span>
          <DataTypeBadge type="ESTIMATED" />
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <BarChart data={chartData} barSize={18} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 9, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 4, fontSize: 11 }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <ReferenceLine y={demand} stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1.5} label={{ value: 'Demand', fill: '#ef4444', fontSize: 9 }} />
            <Bar dataKey="capacity" radius={[2, 2, 0, 0]}>
              {chartData.map(entry => (
                <Cell
                  key={entry.name}
                  fill={entry.isBottleneck ? '#f59e0b' : '#14b8a6'}
                  opacity={entry.isBottleneck ? 1 : 0.7}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Dimension detail */}
      <div className="flex flex-col gap-1.5">
        {cap.dimensions.map(d => (
          <div
            key={d.name}
            className={clsx(
              'rounded border px-2.5 py-2',
              d.name === cap.bottleneck
                ? 'border-amber-500/30 bg-amber-500/8'
                : 'border-slate-800 bg-slate-900'
            )}
          >
            <div className="flex items-center justify-between mb-0.5">
              <div className="flex items-center gap-2">
                <span className={clsx(
                  'text-xs font-semibold uppercase',
                  d.name === cap.bottleneck ? 'text-amber-400' : 'text-slate-300'
                )}>
                  {d.name}
                  {d.name === cap.bottleneck && ' ← bottleneck'}
                </span>
                <DataTypeBadge type={d.data_type} />
              </div>
              <span className="text-xs font-mono font-bold text-slate-200">{d.capacity.toLocaleString()}</span>
            </div>
            <div className="text-2xs text-slate-500">{d.notes}</div>
            <div className="text-2xs text-slate-600 mt-0.5">Source: {d.source}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function AllocationPanel() {
  const opt = DEMO_OPTIMIZATION_RESULT
  const demand = opt.total_demand

  return (
    <div className="flex flex-col gap-3">
      {/* Status banner */}
      <div className={clsx(
        'rounded border px-3 py-2.5',
        opt.status === 'FEASIBLE'
          ? 'border-green-500/30 bg-green-500/8'
          : opt.status === 'PARTIAL'
          ? 'border-orange-500/30 bg-orange-500/8'
          : 'border-red-500/30 bg-red-500/8'
      )}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {opt.status === 'FEASIBLE'
              ? <CheckCircle className="h-4 w-4 text-green-400" />
              : <XCircle className="h-4 w-4 text-red-400" />}
            <span className={clsx(
              'text-sm font-bold',
              opt.status === 'FEASIBLE' ? 'text-green-400' : 'text-red-400'
            )}>
              {opt.status}
            </span>
          </div>
          <DataTypeBadge type={opt.data_type} />
        </div>
        <div className="mt-1 text-xs text-slate-400">
          {opt.total_allocated.toLocaleString()} / {demand.toLocaleString()} persons allocated
          {opt.unallocated > 0 && (
            <span className="text-red-400 ml-2">· {opt.unallocated.toLocaleString()} unallocated</span>
          )}
        </div>
      </div>

      {/* Allocation table */}
      <div className="rounded-lg border border-slate-800 bg-slate-900 overflow-hidden">
        <div className="px-3 py-2 border-b border-slate-800">
          <span className="text-xs font-semibold text-slate-400">Recommended Allocation</span>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-800">
              {['Site', 'Allocated', 'Dist. (est. input)', 'Utilisation', 'Surplus'].map(h => (
                <th key={h} className="px-3 py-1.5 text-left text-2xs font-semibold uppercase tracking-wide text-slate-600">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {opt.allocations.map(a => (
              <tr key={a.site_id} className="border-b border-slate-800/50">
                <td className="px-3 py-2">
                  <div className="text-xs font-medium text-slate-300">{a.site_name.split(' — ')[1] || a.site_name}</div>
                  <div className="text-2xs text-slate-600">{a.site_name.split(' — ')[0]}</div>
                </td>
                <td className="px-3 py-2 text-xs font-mono text-slate-200">{a.allocated_population.toLocaleString()}</td>
                <td className="px-3 py-2 text-xs font-mono text-slate-400">{a.distance_km} km</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1.5 rounded-full bg-slate-800">
                      <div
                        className={clsx('h-full rounded-full', a.utilization_pct >= 90 ? 'bg-orange-500' : 'bg-teal-500')}
                        style={{ width: `${a.utilization_pct}%` }}
                      />
                    </div>
                    <span className="text-2xs font-mono text-slate-400">{a.utilization_pct}%</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-xs font-mono text-slate-400">{a.surplus_after.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Constraints applied */}
      <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
        <div className="text-2xs text-slate-500 mb-2">Constraints Applied</div>
        <div className="flex flex-col gap-1">
          {opt.constraints_applied.map(c => (
            <div key={c} className="flex items-start gap-2">
              <CheckCircle className="h-3 w-3 text-teal-500 flex-shrink-0 mt-0.5" />
              <span className="text-xs text-slate-400">{c}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Solver note */}
      <div className="rounded border border-slate-800 bg-slate-900/50 p-2.5">
        <div className="flex items-start gap-2">
          <Info className="h-3.5 w-3.5 text-slate-600 flex-shrink-0 mt-0.5" />
          <p className="text-2xs text-slate-600 leading-relaxed">{opt.solver_note}</p>
        </div>
      </div>
    </div>
  )
}

export function RelocationIntelligence() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<Tab>('sites')
  const [selectedSiteId, setSelectedSiteId] = useState<string>('site-a')

  const h = DEMO_MUNNAR_CENTRAL
  const demand = DEMO_RELOCATION_DEMAND
  const selectedSite = DEMO_CANDIDATE_SITES.find(s => s.id === selectedSiteId)!
  const selectedCap = DEMO_CAPACITY_ASSESSMENTS[selectedSiteId]

  const totalCapacity = DEMO_CANDIDATE_SITES.reduce((s, site) => s + site.safe_capacity, 0)
  const capacityGap = demand.relocation_demand - totalCapacity

  const radarData = [
    { subject: 'Safety', A: selectedSite.safety_score },
    { subject: 'Infrastructure', A: selectedSite.infrastructure_score },
    { subject: 'Accessibility', A: selectedSite.accessibility_score },
    { subject: 'Water', A: selectedSite.water_score },
    { subject: 'Healthcare', A: selectedSite.healthcare_score },
    { subject: 'Education', A: selectedSite.education_score },
  ]

  return (
    <div className="flex h-full overflow-hidden">
      {/* LEFT — habitation context + demand */}
      <div className="flex w-64 flex-shrink-0 flex-col gap-3 overflow-y-auto border-r border-slate-800 bg-slate-950 p-3">
        {/* Source habitation */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500 mb-1">Source Habitation</div>
          <div className="text-sm font-bold text-slate-200 mb-1">{h.name}</div>
          <div className="text-2xs text-slate-500 mb-2">{h.ward} · {h.taluk} · {h.district}</div>
          <div className="flex items-center gap-2 mb-2">
            <RiskBadge score={h.risk.current} size="sm" />
            <PriorityBadge priority={h.relocation_priority.priority} size="sm" />
          </div>
          <button
            onClick={() => navigate('/habitations/munnar-central')}
            className="text-2xs text-blue-400 hover:text-blue-300"
          >
            View investigation →
          </button>
        </div>

        {/* Relocation demand */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-2xs text-slate-500">Relocation Demand</div>
            <DataTypeBadge type={demand.data_type} />
          </div>
          <div className="flex items-center gap-2 mb-1">
            <Users className="h-3.5 w-3.5 text-slate-500" />
            <span className="text-xl font-bold font-mono text-slate-200">
              {demand.relocation_demand.toLocaleString()}
            </span>
            <span className="text-xs text-slate-500">persons</span>
          </div>
          <div className="text-2xs text-slate-500 mb-2">{demand.households.toLocaleString()} households</div>
          <div className="rounded border border-slate-800 bg-slate-950 p-2">
            <p className="text-2xs text-slate-600 leading-relaxed">{demand.demand_basis}</p>
          </div>
        </div>

        {/* Capacity summary across all sites */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500 mb-2">Total Available Capacity</div>
          <div className="text-xl font-bold font-mono text-teal-400 mb-1">
            {totalCapacity.toLocaleString()}
          </div>
          <div className="text-2xs text-slate-500 mb-2">across {DEMO_CANDIDATE_SITES.length} candidate sites</div>
          <div className={clsx(
            'rounded border px-2 py-1.5',
            capacityGap >= 0
              ? 'border-green-500/30 bg-green-500/8'
              : 'border-orange-500/30 bg-orange-500/8'
          )}>
            <div className="text-2xs text-slate-500">Combined gap / surplus</div>
            <div className={clsx(
              'text-sm font-bold font-mono',
              capacityGap >= 0 ? 'text-green-400' : 'text-orange-400'
            )}>
              {capacityGap >= 0 ? '+' : ''}{(totalCapacity - demand.relocation_demand).toLocaleString()}
            </div>
          </div>
          <p className="mt-2 text-2xs text-slate-600">
            No single site can absorb full demand. Multi-site allocation required.
          </p>
        </div>

        {/* Pipeline CTA */}
        <button
          onClick={() => setActiveTab('allocation')}
          className="flex items-center justify-between rounded border border-emerald-500/30 bg-emerald-500/8 px-3 py-2 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/15 transition-colors"
        >
          View Optimized Allocation
          <ArrowRight className="h-3.5 w-3.5" />
        </button>

        <button
          onClick={() => navigate('/scenarios')}
          className="flex items-center justify-between rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800 transition-colors"
        >
          Run Scenario Analysis
          <ChevronRight className="h-3.5 w-3.5" />
        </button>

        <FreshnessBadge status="DEMO" />
      </div>

      {/* RIGHT — tabbed intelligence panels */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b border-slate-800 bg-slate-950 px-4">
          {(Object.keys(TAB_LABELS) as Tab[]).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={clsx(
                'px-4 py-3 text-xs font-semibold transition-colors border-b-2 -mb-px',
                activeTab === tab
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300'
              )}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {/* TAB: Candidate Sites */}
          {activeTab === 'sites' && (
            <div className="flex flex-col gap-3">
              <div>
                <h2 className="text-sm font-semibold text-slate-200">Screening Range Map</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Zones are DERIVED screening ranges around technically screened candidates — sized from assessed
                  safe capacity, colored from suitability/safety scores. Not official hazard boundaries. Click a site
                  point to open its assessment; click a zone for its evidence.
                </p>
              </div>
              <SiteScreeningMap
                region="kerala"
                selectedSiteId={selectedSiteId}
                onSiteSelect={(id) => { setSelectedSiteId(id); setActiveTab('suitability') }}
              />
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-200">Technically Screened Candidates</h2>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Hard safety constraints applied first. Scores are DERIVED by Sentinel AI suitability engine.
                    Official approval required before relocation.
                  </p>
                </div>
                <DataTypeBadge type="DERIVED" />
              </div>
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                {DEMO_CANDIDATE_SITES.map(site => (
                  <SiteCard
                    key={site.id}
                    site={site}
                    selected={selectedSiteId === site.id}
                    onSelect={() => { setSelectedSiteId(site.id); setActiveTab('suitability') }}
                  />
                ))}
              </div>
              <div className="rounded border border-slate-800 bg-slate-900/50 p-2.5">
                <div className="flex items-start gap-2">
                  <Info className="h-3.5 w-3.5 text-slate-600 flex-shrink-0 mt-0.5" />
                  <p className="text-2xs text-slate-600 leading-relaxed">
                    These are Technically Screened Candidates only. Official government approval is required before any relocation. Suitability scores are DERIVED by Sentinel AI and are not official assessments.
                    Distance figures are DEMO/ESTIMATED inputs — they are neither geodesic nor road-network measurements.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB: Suitability */}
          {activeTab === 'suitability' && (
            <div className="flex flex-col gap-4">
              {/* Site selector */}
              <div className="flex gap-2">
                {DEMO_CANDIDATE_SITES.map(site => (
                  <button
                    key={site.id}
                    onClick={() => setSelectedSiteId(site.id)}
                    className={clsx(
                      'rounded border px-3 py-1.5 text-xs font-medium transition-colors',
                      selectedSiteId === site.id
                        ? 'border-blue-500/50 bg-blue-600/20 text-blue-300'
                        : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-300'
                    )}
                  >
                    {site.name.split(' — ')[1]}
                  </button>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-4">
                {/* Radar chart */}
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-xs font-semibold text-slate-300">{selectedSite.name}</div>
                      <div className="text-2xs text-slate-500">{selectedSite.distance_km} km · Suitability {selectedSite.suitability_score}/100</div>
                    </div>
                    <DataTypeBadge type={selectedSite.data_type} />
                  </div>
                  <ResponsiveContainer width="100%" height={200}>
                    <RadarChart data={radarData}>
                      <PolarGrid stroke="#334155" />
                      <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10, fill: '#64748b' }} />
                      <Radar
                        name={selectedSite.name}
                        dataKey="A"
                        stroke="#14b8a6"
                        fill="#14b8a6"
                        fillOpacity={0.25}
                        strokeWidth={1.5}
                      />
                      <Tooltip
                        contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 4, fontSize: 11 }}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                {/* Score breakdown */}
                <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
                  <div className="text-xs font-semibold text-slate-400 mb-3">Score Breakdown (weights)</div>
                  <div className="flex flex-col gap-2.5">
                    <SuitabilityBar label="Safety (30%)" value={selectedSite.safety_score} />
                    <SuitabilityBar label="Infrastructure (20%)" value={selectedSite.infrastructure_score} />
                    <SuitabilityBar label="Accessibility (15%)" value={selectedSite.accessibility_score} />
                    <SuitabilityBar label="Water (10%)" value={selectedSite.water_score} />
                    <SuitabilityBar label="Healthcare (15%)" value={selectedSite.healthcare_score} />
                    <SuitabilityBar label="Education (10%)" value={selectedSite.education_score} />
                  </div>
                  <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-between">
                    <span className="text-xs text-slate-500">Overall Suitability</span>
                    <span className="text-lg font-bold font-mono text-teal-400">{selectedSite.suitability_score}/100</span>
                  </div>
                  <div className="mt-2">
                    <DataTypeBadge type="DERIVED" />
                  </div>
                </div>
              </div>

              {/* Notes */}
              <div className="rounded border border-slate-800 bg-slate-900 p-3">
                <div className="text-2xs text-slate-500 mb-1">Assessment Notes</div>
                <p className="text-xs text-slate-400 leading-relaxed">{selectedSite.notes}</p>
              </div>
            </div>
          )}

          {/* TAB: Capacity */}
          {activeTab === 'capacity' && (
            <div className="flex flex-col gap-4">
              <div className="flex gap-2">
                {DEMO_CANDIDATE_SITES.map(site => (
                  <button
                    key={site.id}
                    onClick={() => setSelectedSiteId(site.id)}
                    className={clsx(
                      'rounded border px-3 py-1.5 text-xs font-medium transition-colors',
                      selectedSiteId === site.id
                        ? 'border-blue-500/50 bg-blue-600/20 text-blue-300'
                        : 'border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-300'
                    )}
                  >
                    {site.name.split(' — ')[1]}
                  </button>
                ))}
              </div>
              <CapacityPanel cap={selectedCap} />
            </div>
          )}

          {/* TAB: Allocation */}
          {activeTab === 'allocation' && (
            <div className="flex flex-col gap-4">
              <div>
                <h2 className="text-sm font-semibold text-slate-200">Optimized Multi-Site Allocation</h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Objective: minimize weighted distance + residual hazard exposure + infrastructure deficit.
                  All results are RECOMMENDATION — require human authority review.
                </p>
              </div>
              <AllocationPanel />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
