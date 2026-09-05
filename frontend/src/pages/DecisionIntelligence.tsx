import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowDown } from 'lucide-react'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { RiskBadge } from '../components/ui/RiskBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { DEMO_MUNNAR_CENTRAL } from '../data/idukki-seed'
import clsx from 'clsx'

// Decision trace — values consistent with validated risk model
// Risk = 0.40×Hazard + 0.20×Exposure + 0.25×Vulnerability + 0.15×Interaction
// Vulnerability = 0.30×78 + 0.20×71 + 0.25×76 + 0.25×69 = 73.85
const TRACE_STEPS = [
  { step: 1, node: 'OBSERVED HAZARDS', value: 'Landslide 88 | Flood 62 | Cloudburst 45 (KSDMA + IMD + CWC)', data_type: 'OBSERVED' as const, color: 'border-blue-500/40 bg-blue-500/8 text-blue-300' },
  { step: 2, node: 'EXPOSURE', value: '4,210 persons in hazard zone | 1,053 households | Exposure index 84/100', data_type: 'DERIVED' as const, color: 'border-violet-500/40 bg-violet-500/8 text-violet-300' },
  { step: 3, node: 'VULNERABILITY', value: '73.85/100 ≈ 74 — HIGH | Demo 78 · Socio 71 · Infra 76 · Access 69', data_type: 'DERIVED' as const, color: 'border-violet-500/40 bg-violet-500/8 text-violet-300' },
  { step: 4, node: 'OPERATIONAL RISK', value: '94/100 (Baseline 65, Change +29) | Base risk 80.21 + event escalation 13.65 = 93.86 ≈ 94', data_type: 'DERIVED' as const, color: 'border-orange-500/40 bg-orange-500/8 text-orange-300' },
  { step: 5, node: 'RELOCATION PRIORITY', value: 'IMMEDIATE — RPI 88/100 | 0.35×94 + 0.20×74 + 0.15×84 + 0.15×94 + 0.15×87', data_type: 'RECOMMENDATION' as const, color: 'border-red-500/40 bg-red-500/8 text-red-300' },
  { step: 6, node: 'SITE / CAPACITY CHECK', value: '3 candidate sites screened | C_safe: A=3,200 B=2,100 C=1,800 | Total=7,100 | Demand=4,210', data_type: 'DERIVED' as const, color: 'border-violet-500/40 bg-violet-500/8 text-violet-300' },
  { step: 7, node: 'SYSTEM RECOMMENDATION', value: 'Initiate relocation assessment for Ward 04, Munnar Central. Multi-site allocation required.', data_type: 'RECOMMENDATION' as const, color: 'border-emerald-500/40 bg-emerald-500/8 text-emerald-300' },
]

// Top drivers — contribution = weight × score
const TOP_DRIVERS = [
  { rank: 1, name: 'Landslide Susceptibility (KSDMA)', score: 88, weight: '40%', contribution: 35.2, data_type: 'DERIVED' as const },
  { rank: 2, name: 'Soil Saturation (KSDMA Sensors)', score: 94, weight: '25%', contribution: 23.5, data_type: 'OBSERVED' as const },
  { rank: 3, name: 'Structural Vulnerability', score: 76, weight: '25%', contribution: 19.0, data_type: 'DERIVED' as const },
  { rank: 4, name: 'Access Route Risk', score: 69, weight: '15%', contribution: 10.4, data_type: 'DERIVED' as const },
]

export function DecisionIntelligence() {
  const navigate = useNavigate()
  const h = DEMO_MUNNAR_CENTRAL

  return (
    <div className="flex h-full overflow-hidden">
      {/* LEFT — decision trace */}
      <div className="flex w-96 flex-shrink-0 flex-col overflow-y-auto border-r border-slate-800 bg-slate-950 p-4">
        <button
          onClick={() => navigate(`/habitations/${h.id}`)}
          className="mb-4 flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Investigation
        </button>

        <div className="mb-4">
          <div className="text-2xs text-slate-500 mb-1">{h.ward} · {h.taluk} · {h.district}</div>
          <h1 className="text-base font-bold text-slate-100">Decision Intelligence</h1>
          <p className="text-xs text-slate-500 mt-0.5">How Sentinel AI reached this recommendation</p>
        </div>

        <FreshnessBadge status="DEMO" />

        {/* Decision trace */}
        <div className="mt-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Decision Trace</h2>
          <div className="flex flex-col items-center">
            {TRACE_STEPS.map((step, idx) => (
              <div key={step.step} className="w-full">
                <div className={clsx('rounded border p-3', step.color)}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold tracking-wide">{step.node}</span>
                    <DataTypeBadge type={step.data_type} />
                  </div>
                  <p className="text-xs opacity-80 font-mono">{step.value}</p>
                </div>
                {idx < TRACE_STEPS.length - 1 && (
                  <div className="flex justify-center py-1">
                    <ArrowDown className="h-4 w-4 text-slate-700" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* RIGHT — supporting panels */}
      <div className="flex flex-1 flex-col overflow-y-auto gap-4 p-4">
        {/* Top risk drivers */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Top Risk Drivers</h2>
          <div className="flex flex-col gap-2">
            {TOP_DRIVERS.map(d => (
              <div key={d.rank} className="flex items-center gap-3">
                <span className="w-5 text-xs font-mono text-slate-600">#{d.rank}</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-slate-300">{d.name}</span>
                    <div className="flex items-center gap-2">
                      <DataTypeBadge type={d.data_type} />
                      <span className="text-xs font-mono text-slate-400">w={d.weight}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-slate-800">
                      <div
                        className="h-full rounded-full bg-blue-500"
                        style={{ width: `${d.score}%` }}
                      />
                    </div>
                    <span className="text-xs font-mono text-slate-400 w-8 text-right">{d.score}</span>
                    <span className="text-xs font-mono text-slate-500 w-10 text-right">+{d.contribution}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk component breakdown */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Risk Score Breakdown</h2>
          <div className="flex items-center gap-4 mb-3">
            <RiskBadge score={h.risk.current} size="xl" />
            <div>
              <div className="text-xs text-slate-500">Baseline: <span className="font-mono text-slate-400">{h.risk.baseline}</span></div>
              <div className="text-xs text-red-400">Change: <span className="font-mono">+{h.risk.change}</span></div>
              <DataTypeBadge type={h.risk.data_type} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'Hazard (40%)', value: h.risk.hazard_component, note: '0.40 × 88' },
              { label: 'Exposure (20%)', value: h.risk.exposure_component, note: '0.20 × 84' },
              { label: 'Vulnerability (25%)', value: h.risk.vulnerability_component, note: '0.25 × 73.85' },
              { label: 'Interaction (15%)', value: h.risk.interaction_component, note: '0.15 × (H×V)' },
              ...(h.risk.event_escalation_component != null
                ? [{
                  label: 'Event Escalation',
                  value: h.risk.event_escalation_component,
                  note: '0.05×(287−150) + 0.40×(94−80) + 1.50×(2.3−1.5) = 13.65 — active event triggers only',
                }]
                : []),
            ].map(({ label, value, note }) => (
              <div key={label} className="rounded border border-slate-800 bg-slate-950 p-2">
                <div className="text-2xs text-slate-500">{label}</div>
                <div className="text-sm font-bold font-mono text-slate-200">{value}</div>
                <div className="text-2xs text-slate-600 font-mono">{note}</div>
              </div>
            ))}
          </div>
          <p className="text-2xs text-slate-600 mt-1">
            Base risk = 35.2 + 16.8 + 18.46 + 9.75 = 80.21 (deterministic model). Current operational
            risk = base 80.21 + event escalation 13.65 = 93.86 ≈ 94 — escalation reflects active
            rainfall/saturation/river triggers above documented thresholds and never changes permanent
            settlement suitability. Weights and escalation coefficients are configurable Sentinel AI
            baselines — not official government formulas.
          </p>
        </div>

        {/* System recommendation */}
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/8 p-4">
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-emerald-500">System Recommendation</h2>
            <DataTypeBadge type="RECOMMENDATION" />
          </div>
          <p className="text-sm text-emerald-300 leading-relaxed mb-3">{h.system_recommendation}</p>
          <PriorityBadge priority={h.relocation_priority.priority} size="lg" />
        </div>

        {/* Trust note */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">About This Decision</h2>
          <ul className="flex flex-col gap-1.5">
            {[
              'Deterministic GIS and risk engines produce all scores — AI provides explanation only.',
              'Risk weights are configurable project baselines, not official government formulas.',
              'Operational risk is separate from permanent settlement suitability.',
              'All recommendations require human authority review before any action.',
              'Data labelled DEMO — not live government data.',
            ].map(note => (
              <li key={note} className="flex items-start gap-2 text-xs text-slate-500">
                <span className="mt-1 h-1 w-1 rounded-full bg-slate-700 flex-shrink-0" />
                {note}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
