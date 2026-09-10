import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  FileText, Download, AlertTriangle, CheckCircle,
  XCircle, Info, ChevronRight, Clock,
} from 'lucide-react'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { RiskBadge } from '../components/ui/RiskBadge'
import {
  DEMO_DISTRICT_OVERVIEW,
  DEMO_MUNNAR_CENTRAL,
  DEMO_CANDIDATE_SITES,
  DEMO_CAPACITY_ASSESSMENTS,
  DEMO_OPTIMIZATION_RESULT,
  DEMO_RELOCATION_DEMAND,
  DEMO_SCENARIO_PRESETS,
  runScenario,
} from '../data/idukki-seed'
import clsx from 'clsx'

type ReportSection =
  | 'district'
  | 'habitation'
  | 'relocation'
  | 'capacity'
  | 'scenario'
  | 'provenance'

const SECTIONS: Array<{ id: ReportSection; label: string; description: string }> = [
  { id: 'district', label: 'District Risk Summary', description: 'Idukki district situational overview' },
  { id: 'habitation', label: 'Habitation Investigation', description: 'Munnar Central — Ward 04' },
  { id: 'relocation', label: 'Relocation Assessment', description: 'Candidate sites & allocation plan' },
  { id: 'capacity', label: 'Capacity Gap Analysis', description: 'C_safe per site vs demand' },
  { id: 'scenario', label: 'Scenario Results', description: 'Extreme rainfall scenario' },
  { id: 'provenance', label: 'Data & Provenance', description: 'Sources, vintage, limitations' },
]

const GENERATED_AT = '2024-08-15T06:00:00Z'

function ReportHeader() {
  return (
    <div className="border-b border-slate-700 pb-4 mb-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-blue-400 font-mono">SENTINEL AI</span>
            <span className="text-xs text-slate-500">— Decision Support Report</span>
          </div>
          <h1 className="text-lg font-bold text-slate-100">Idukki District — Hazard Risk & Relocation Assessment</h1>
          <p className="text-xs text-slate-500 mt-0.5">SIH PS 26191 · Ministry of Home Affairs · NDRF, DM Division</p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <FreshnessBadge status="DEMO" />
          <div className="text-2xs text-slate-600">
            Generated: {new Date(GENERATED_AT).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST
          </div>
        </div>
      </div>
      <div className="mt-3 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2">
        <div className="flex items-start gap-2">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-400/90 leading-relaxed">
            <strong>DECISION SUPPORT ONLY.</strong> This report is produced by Sentinel AI for situational awareness and planning.
            It does not constitute an official government order, evacuation directive, or legal Red Zone declaration.
            All recommendations require human authority review before any action.
            Data labelled DEMO — not live government data.
          </p>
        </div>
      </div>
    </div>
  )
}

function SectionLabel({ label, type }: { label: string; type: 'OBSERVED' | 'DERIVED' | 'ESTIMATED' | 'SIMULATED' | 'RECOMMENDATION' }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <h2 className="text-sm font-bold text-slate-200">{label}</h2>
      <DataTypeBadge type={type} />
    </div>
  )
}

function Divider() {
  return <div className="my-5 border-t border-slate-800" />
}

function DistrictSection() {
  const d = DEMO_DISTRICT_OVERVIEW.district
  return (
    <div>
      <SectionLabel label="1. District Risk Summary" type="DERIVED" />
      <div className="grid grid-cols-2 gap-3 mb-4 lg:grid-cols-4">
        {[
          { label: 'Total Habitations', value: d.total_habitations.toLocaleString(), color: 'text-slate-200' },
          { label: 'Critical Risk', value: d.critical_habitations, color: 'text-red-400' },
          { label: 'High Risk', value: d.high_risk_habitations, color: 'text-orange-400' },
          { label: 'Population at Risk', value: d.total_population_at_risk.toLocaleString(), color: 'text-yellow-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="rounded border border-slate-800 bg-slate-900 p-3">
            <div className="text-2xs text-slate-500 uppercase tracking-wide">{label}</div>
            <div className={clsx('text-xl font-bold font-mono mt-1', color)}>{value}</div>
          </div>
        ))}
      </div>
      <div className="rounded border border-slate-800 bg-slate-900 p-3 mb-3">
        <div className="text-2xs text-slate-500 mb-2">Significant Changes (last 72 hours)</div>
        {DEMO_DISTRICT_OVERVIEW.what_changed.map(wc => (
          <div key={wc.id} className="flex items-start gap-2 mb-2">
            <span className={clsx(
              'mt-0.5 h-1.5 w-1.5 rounded-full flex-shrink-0',
              wc.severity === 'critical' ? 'bg-red-500' : 'bg-orange-500'
            )} />
            <div>
              <span className="text-xs font-semibold text-slate-300">{wc.habitation}: </span>
              <span className="text-xs text-slate-400">{wc.description}</span>
              <DataTypeBadge type={wc.data_type} />
            </div>
          </div>
        ))}
      </div>
      <div className="text-2xs text-slate-600">
        Source: Sentinel AI Risk Engine (DERIVED) · IMD, KSDMA, CWC (OBSERVED) · Census 2011 projected (ESTIMATED)
      </div>
    </div>
  )
}

function HabitationSection() {
  const h = DEMO_MUNNAR_CENTRAL
  return (
    <div>
      <SectionLabel label="2. Habitation Investigation — Munnar Central" type="DERIVED" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="rounded border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500">Risk Score</div>
          <RiskBadge score={h.risk.current} size="lg" />
          <div className="text-2xs text-slate-500 mt-1">Baseline: {h.risk.baseline} · Change: +{h.risk.change}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500">Priority</div>
          <PriorityBadge priority={h.relocation_priority.priority} size="lg" />
          <div className="text-2xs text-slate-500 mt-1">RPI: {h.relocation_priority.rpi_score}/100</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500">Population</div>
          <div className="text-xl font-bold font-mono text-slate-200">{h.population.toLocaleString()}</div>
          <div className="text-2xs text-slate-500">{h.households.toLocaleString()} households</div>
        </div>
      </div>

      <div className="mb-3">
        <div className="text-xs font-semibold text-slate-400 mb-2">Evidence Chain</div>
        {h.evidence_chain.map(ev => (
          <div key={ev.step} className="flex items-start gap-3 mb-2">
            <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border border-slate-700 text-2xs font-bold text-slate-500">{ev.step}</span>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-300">{ev.label}</span>
                <DataTypeBadge type={ev.data_type} />
              </div>
              <div className="text-xs text-slate-400">{ev.description}</div>
              {ev.value && <div className="text-xs font-mono text-slate-500">{ev.value}</div>}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded border border-slate-800 bg-slate-900 p-3 mb-3">
        <div className="text-2xs text-slate-500 mb-1">Active Hazards</div>
        {h.hazards.map(hz => (
          <div key={hz.type} className="flex items-center gap-3 mb-1">
            <span className="text-xs font-semibold text-orange-400 w-24">{hz.type}</span>
            <div className="flex-1 h-1.5 rounded-full bg-slate-800">
              <div className="h-full rounded-full bg-orange-500" style={{ width: `${hz.intensity}%` }} />
            </div>
            <span className="text-xs font-mono text-slate-400 w-8 text-right">{hz.intensity}</span>
            <DataTypeBadge type={hz.data_type} />
          </div>
        ))}
      </div>

      <div className="rounded border border-red-500/20 bg-red-500/5 p-3">
        <div className="text-2xs text-slate-500 mb-1">Permanent Settlement Suitability</div>
        <div className="flex items-center gap-2 mb-1">
          <XCircle className="h-3.5 w-3.5 text-red-400" />
          <span className="text-xs font-semibold text-red-400">NOT SUITABLE (Red Zone Candidate)</span>
        </div>
        <p className="text-2xs text-slate-500 leading-relaxed">{h.permanent_suitability_note}</p>
      </div>
    </div>
  )
}

function RelocationSection() {
  const opt = DEMO_OPTIMIZATION_RESULT
  const demand = DEMO_RELOCATION_DEMAND
  return (
    <div>
      <SectionLabel label="3. Relocation Assessment" type="RECOMMENDATION" />
      <div className="rounded border border-slate-800 bg-slate-900 p-3 mb-3">
        <div className="text-2xs text-slate-500 mb-2">Relocation Demand</div>
        <div className="flex items-center gap-4">
          <div>
            <div className="text-xl font-bold font-mono text-slate-200">{demand.relocation_demand.toLocaleString()}</div>
            <div className="text-2xs text-slate-500">persons · {demand.households.toLocaleString()} households</div>
          </div>
          <DataTypeBadge type={demand.data_type} />
        </div>
        <p className="text-2xs text-slate-600 mt-2 leading-relaxed">{demand.demand_basis}</p>
      </div>

      <div className="mb-3">
        <div className="text-xs font-semibold text-slate-400 mb-2">Candidate Sites (Technically Screened)</div>
        {DEMO_CANDIDATE_SITES.map(site => (
          <div key={site.id} className="rounded border border-slate-800 bg-slate-900 p-3 mb-2">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-slate-300">{site.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-teal-400">{site.suitability_score}/100</span>
                <DataTypeBadge type={site.data_type} />
              </div>
            </div>
            <div className="flex items-center gap-4 text-2xs text-slate-500">
              <span>C_safe: <strong className="text-slate-300">{DEMO_CAPACITY_ASSESSMENTS[site.id].c_safe.toLocaleString()}</strong></span>
              <span>Bottleneck: <strong className="text-amber-400 uppercase">{DEMO_CAPACITY_ASSESSMENTS[site.id].bottleneck}</strong></span>
              <span>Distance: {site.distance_km} km</span>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded border border-emerald-500/20 bg-emerald-500/5 p-3">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
          <span className="text-xs font-semibold text-emerald-400">Optimized Allocation — {opt.status}</span>
          <DataTypeBadge type={opt.data_type} />
        </div>
        <div className="flex flex-col gap-1.5">
          {opt.allocations.map(a => (
            <div key={a.site_id} className="flex items-center gap-3">
              <span className="text-xs text-slate-400 flex-1">{a.site_name.split(' — ')[1] || a.site_name}</span>
              <span className="text-xs font-mono text-slate-200">{a.allocated_population.toLocaleString()} persons</span>
              <span className="text-2xs text-slate-500">{a.distance_km} km</span>
              <span className="text-2xs text-slate-500">{a.utilization_pct}% utilisation</span>
            </div>
          ))}
        </div>
        <p className="mt-2 text-2xs text-slate-600 leading-relaxed">{opt.solver_note}</p>
      </div>
    </div>
  )
}

function CapacitySection() {
  const totalCapacity = DEMO_CANDIDATE_SITES.reduce((s, site) => s + DEMO_CAPACITY_ASSESSMENTS[site.id].c_safe, 0)
  const demand = DEMO_RELOCATION_DEMAND.relocation_demand
  const gap = totalCapacity - demand
  return (
    <div>
      <SectionLabel label="4. Capacity Gap Analysis" type="DERIVED" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="rounded border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500">Total C_safe (3 sites)</div>
          <div className="text-xl font-bold font-mono text-teal-400">{totalCapacity.toLocaleString()}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500">Relocation Demand</div>
          <div className="text-xl font-bold font-mono text-slate-200">{demand.toLocaleString()}</div>
        </div>
        <div className={clsx(
          'rounded border p-3',
          gap >= 0 ? 'border-green-500/30 bg-green-500/10' : 'border-red-500/30 bg-red-500/10'
        )}>
          <div className="text-2xs text-slate-500">Combined Gap / Surplus</div>
          <div className={clsx('text-xl font-bold font-mono', gap >= 0 ? 'text-green-400' : 'text-red-400')}>
            {gap >= 0 ? '+' : ''}{gap.toLocaleString()}
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {DEMO_CANDIDATE_SITES.map(site => {
          const cap = DEMO_CAPACITY_ASSESSMENTS[site.id]
          return (
            <div key={site.id} className="rounded border border-slate-800 bg-slate-900 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-300">{site.name}</span>
                <span className={clsx(
                  'text-xs font-mono font-bold',
                  cap.surplus_deficit >= 0 ? 'text-green-400' : 'text-red-400'
                )}>
                  {cap.surplus_deficit >= 0 ? '+' : ''}{cap.surplus_deficit.toLocaleString()}
                </span>
              </div>
              <div className="flex items-center gap-4 text-2xs text-slate-500">
                <span>C_safe: <strong className="text-teal-400">{cap.c_safe.toLocaleString()}</strong></span>
                <span>Bottleneck: <strong className="text-amber-400 uppercase">{cap.bottleneck}</strong></span>
                <span>Can absorb alone: <strong className={cap.can_absorb_alone ? 'text-green-400' : 'text-red-400'}>{cap.can_absorb_alone ? 'Yes' : 'No'}</strong></span>
              </div>
            </div>
          )
        })}
      </div>
      <p className="mt-3 text-2xs text-slate-600">
        C_safe = min(land, water, healthcare, education, infrastructure, environment). Only dimensions with available data included.
        All capacity figures are ESTIMATED from secondary sources. Field verification required.
      </p>
    </div>
  )
}

function ScenarioSection() {
  const preset = DEMO_SCENARIO_PRESETS[1] // Extreme rainfall ×1.5
  const result = runScenario(preset)
  return (
    <div>
      <SectionLabel label="5. Scenario Results" type="SIMULATED" />
      <div className="rounded border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 mb-4">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
          <span className="text-xs font-semibold text-cyan-400">SIMULATION MODE</span>
          <span className="text-2xs text-cyan-400/70">— {result.warning}</span>
        </div>
      </div>
      <div className="rounded border border-slate-800 bg-slate-900 p-3 mb-3">
        <div className="text-xs font-semibold text-slate-400 mb-2">Scenario: {preset.label}</div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            { label: 'Simulated Risk', value: result.simulated_risk, color: 'text-red-400' },
            { label: 'Simulated Demand', value: result.simulated_demand.toLocaleString(), color: 'text-slate-200' },
            { label: 'Available Capacity', value: result.simulated_capacity_available.toLocaleString(), color: 'text-teal-400' },
            { label: 'Capacity Gap', value: result.simulated_gap > 0 ? `+${result.simulated_gap.toLocaleString()}` : result.simulated_gap.toLocaleString(), color: result.simulated_gap > 0 ? 'text-red-400' : 'text-green-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded border border-slate-800 bg-slate-950 p-2">
              <div className="text-2xs text-slate-500">{label}</div>
              <div className={clsx('text-lg font-bold font-mono', color)}>{value}</div>
            </div>
          ))}
        </div>
        <div className="mt-2">
          <span className="text-2xs text-slate-500">Simulated priority: </span>
          <PriorityBadge priority={result.simulated_priority} size="sm" />
        </div>
      </div>
      <p className="text-2xs text-slate-600 leading-relaxed">
        Scenario computed using Sentinel AI risk and capacity models. Rainfall multiplier ×{preset.rainfall_multiplier} applied to hazard component.
        Results are SIMULATED and must not be used as operational forecasts.
      </p>
    </div>
  )
}

function ProvenanceSection() {
  const sources = [
    { name: 'KSDMA Landslide Susceptibility', type: 'OBSERVED' as const, year: '2019', status: 'DEMO' },
    { name: 'IMD Rainfall (Munnar Station)', type: 'OBSERVED' as const, year: '2024-08-15 snapshot', status: 'DEMO' },
    { name: 'Bhuvan LULC / Kerala disaster-event WMS (historical)', type: 'OBSERVED' as const, year: '2019/2021 events', status: 'DEMO' },
    { name: 'Census of India 2011 (projected)', type: 'ESTIMATED' as const, year: '2011', status: 'DEMO' },
    { name: 'CWC River Level (Periyar)', type: 'OBSERVED' as const, year: '2024-08-15 snapshot', status: 'DEMO' },
    { name: 'data.gov.in Health Facilities', type: 'ESTIMATED' as const, year: '2022', status: 'DEMO' },
    { name: 'UDISE+ School Infrastructure', type: 'ESTIMATED' as const, year: '2022-23', status: 'DEMO' },
    { name: 'Sentinel AI Risk Engine v0.1.0', type: 'DERIVED' as const, year: 'SIH demo build', status: 'DEMO' },
    { name: 'OR-Tools CP-SAT Optimizer v9.10', type: 'DERIVED' as const, year: 'v9.10', status: 'DEMO' },
  ]
  return (
    <div>
      <SectionLabel label="6. Data & Provenance" type="OBSERVED" />
      <div className="flex flex-col gap-1.5">
        {sources.map(s => (
          <div key={s.name} className="flex items-center gap-3 rounded border border-slate-800 bg-slate-900 px-3 py-2">
            <DataTypeBadge type={s.type} />
            <span className="text-xs text-slate-300 flex-1">{s.name}</span>
            <span className="text-2xs text-slate-500">{s.year}</span>
            <FreshnessBadge status="DEMO" />
          </div>
        ))}
      </div>
      <div className="mt-3 rounded border border-slate-800 bg-slate-900/50 p-3">
        <div className="flex items-start gap-2">
          <Info className="h-3.5 w-3.5 text-slate-600 flex-shrink-0 mt-0.5" />
          <p className="text-2xs text-slate-600 leading-relaxed">
            All data in this report is labelled DEMO. Live connections to IMD, CWC, Bhuvan and KSDMA are not active in this build.
            Risk model weights are configurable project baselines — not official government formulas.
            Candidate sites are technically screened candidates only — official approval required before relocation.
            This report does not constitute a government order or legal declaration.
          </p>
        </div>
      </div>
    </div>
  )
}

export function Reports() {
  const navigate = useNavigate()
  const [activeSection, setActiveSection] = useState<ReportSection>('district')
  const [printMode, setPrintMode] = useState(false)

  const renderSection = () => {
    switch (activeSection) {
      case 'district': return <DistrictSection />
      case 'habitation': return <HabitationSection />
      case 'relocation': return <RelocationSection />
      case 'capacity': return <CapacitySection />
      case 'scenario': return <ScenarioSection />
      case 'provenance': return <ProvenanceSection />
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* LEFT — section nav */}
      {!printMode && (
        <div className="flex w-56 flex-shrink-0 flex-col gap-2 overflow-y-auto border-r border-slate-800 bg-slate-950 p-3">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Report Sections</div>
          {SECTIONS.map(s => (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              className={clsx(
                'rounded border px-2.5 py-2 text-left transition-colors',
                activeSection === s.id
                  ? 'border-blue-500/50 bg-blue-600/15'
                  : 'border-slate-800 bg-slate-900 hover:border-slate-700'
              )}
            >
              <div className={clsx(
                'text-xs font-semibold',
                activeSection === s.id ? 'text-blue-300' : 'text-slate-300'
              )}>{s.label}</div>
              <div className="text-2xs text-slate-500 mt-0.5">{s.description}</div>
            </button>
          ))}

          <div className="mt-auto pt-3 border-t border-slate-800">
            <button
              onClick={() => setPrintMode(true)}
              className="flex w-full items-center gap-2 rounded border border-slate-700 bg-slate-900 px-2.5 py-2 text-xs text-slate-400 hover:text-slate-300 transition-colors"
            >
              <FileText className="h-3.5 w-3.5" />
              Full Report View
            </button>
          </div>

          <div className="flex flex-col gap-1">
            <button
              onClick={() => navigate('/relocation')}
              className="flex items-center gap-1.5 text-2xs text-blue-400 hover:text-blue-300"
            >
              <ChevronRight className="h-3 w-3" /> Relocation Intelligence
            </button>
            <button
              onClick={() => navigate('/scenarios')}
              className="flex items-center gap-1.5 text-2xs text-blue-400 hover:text-blue-300"
            >
              <ChevronRight className="h-3 w-3" /> Scenario Analysis
            </button>
          </div>

          <div className="flex items-center gap-1.5">
            <Clock className="h-3 w-3 text-slate-600" />
            <span className="text-2xs text-slate-600">DEMO · 2024-08-15</span>
          </div>
        </div>
      )}

      {/* RIGHT — report content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {printMode && (
          <div className="flex items-center gap-3 border-b border-slate-800 bg-slate-950 px-4 py-2">
            <button
              onClick={() => setPrintMode(false)}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              ← Back to sections
            </button>
            <span className="text-xs text-slate-500">Full report view</span>
            <button
              onClick={() => window.print()}
              className="ml-auto flex items-center gap-1.5 rounded border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs text-slate-400 hover:text-slate-300"
            >
              <Download className="h-3.5 w-3.5" /> Print / Export
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            <ReportHeader />

            {printMode ? (
              // Full report: all sections
              <div className="flex flex-col gap-0">
                <DistrictSection /><Divider />
                <HabitationSection /><Divider />
                <RelocationSection /><Divider />
                <CapacitySection /><Divider />
                <ScenarioSection /><Divider />
                <ProvenanceSection />
              </div>
            ) : (
              renderSection()
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
