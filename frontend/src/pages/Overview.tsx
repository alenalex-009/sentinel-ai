import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, Users, MapPin, ArrowUpRight,
  ArrowDownRight, Minus, Activity, Clock, ChevronRight,
  Droplets, Mountain, Wind,
} from 'lucide-react'
import { MapContainer } from '../components/map/MapContainer'
import { RiskBadge } from '../components/ui/RiskBadge'
import { PriorityBadge } from '../components/ui/PriorityBadge'
import { DataTypeBadge } from '../components/ui/DataTypeBadge'
import { FreshnessBadge } from '../components/ui/FreshnessBadge'
import { DEMO_DISTRICT_OVERVIEW, DEMO_HABITATIONS } from '../data/idukki-seed'
import type { HabitationListItem } from '../types'
import clsx from 'clsx'

const overview = DEMO_DISTRICT_OVERVIEW
const d = overview.district

const HAZARD_ICONS: Record<string, React.ReactNode> = {
  rainfall: <Droplets className="h-3.5 w-3.5" />,
  soil_moisture: <Mountain className="h-3.5 w-3.5" />,
  river_level: <Activity className="h-3.5 w-3.5" />,
  cloudburst: <Wind className="h-3.5 w-3.5" />,
}

function KPICard({
  label, value, sub, color = 'text-slate-200', icon,
}: {
  label: string
  value: string | number
  sub?: string
  color?: string
  icon?: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-slate-800 bg-slate-900 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500 uppercase tracking-wide">{label}</span>
        {icon && <span className="text-slate-600">{icon}</span>}
      </div>
      <span className={clsx('text-2xl font-bold font-mono', color)}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </span>
      {sub && <span className="text-xs text-slate-500">{sub}</span>}
    </div>
  )
}

function WhatChangedItem({ item }: { item: typeof overview.what_changed[0] }) {
  const severityColor = {
    critical: 'border-l-red-500 bg-red-500/5',
    high: 'border-l-orange-500 bg-orange-500/5',
    medium: 'border-l-yellow-500 bg-yellow-500/5',
  }[item.severity] || 'border-l-slate-600 bg-slate-800'

  return (
    <div className={clsx('border-l-2 pl-3 py-2 rounded-r', severityColor)}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="text-xs font-semibold text-slate-300">{item.habitation}</span>
          <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{item.description}</p>
        </div>
        <DataTypeBadge type={item.data_type} />
      </div>
    </div>
  )
}

function PriorityActionItem({ item }: { item: typeof overview.priority_actions[0] }) {
  return (
    <div className="flex items-start gap-3 rounded border border-slate-800 bg-slate-900 p-2.5">
      <PriorityBadge priority={item.priority} size="sm" />
      <div className="flex-1 min-w-0">
        <div className="text-xs font-semibold text-slate-300">{item.habitation}</div>
        <div className="text-xs text-slate-400 mt-0.5">{item.action}</div>
        <div className="text-2xs text-slate-500 mt-1">{item.population.toLocaleString()} persons</div>
      </div>
      <ChevronRight className="h-3.5 w-3.5 text-slate-600 flex-shrink-0 mt-0.5" />
    </div>
  )
}

function TelemetryItem({ item }: { item: typeof overview.telemetry_anomalies[0] }) {
  const isExceeded = item.status === 'exceeded'
  return (
    <div className={clsx(
      'flex items-center justify-between rounded border p-2',
      isExceeded ? 'border-red-500/30 bg-red-500/5' : 'border-orange-500/30 bg-orange-500/5'
    )}>
      <div className="flex items-center gap-2">
        <span className={clsx('text-slate-500', isExceeded ? 'text-red-400' : 'text-orange-400')}>
          {HAZARD_ICONS[item.type] || <Activity className="h-3.5 w-3.5" />}
        </span>
        <div>
          <div className="text-xs font-medium text-slate-300">{item.location}</div>
          <div className="text-2xs text-slate-500">
            {item.value} <span className="text-slate-600">(threshold: {item.threshold})</span>
          </div>
        </div>
      </div>
      <span className={clsx(
        'text-2xs font-semibold uppercase tracking-wide',
        isExceeded ? 'text-red-400' : 'text-orange-400'
      )}>
        {item.status}
      </span>
    </div>
  )
}

function HabitationListRow({
  h, selected, onSelect,
}: {
  h: HabitationListItem
  selected: boolean
  onSelect: (id: string) => void
}) {
  const changeIcon = h.risk_change > 0
    ? <ArrowUpRight className="h-3 w-3 text-red-400" />
    : h.risk_change < 0
    ? <ArrowDownRight className="h-3 w-3 text-green-400" />
    : <Minus className="h-3 w-3 text-slate-500" />

  return (
    <button
      onClick={() => onSelect(h.id)}
      className={clsx(
        'w-full flex items-center gap-2 px-2 py-2 rounded text-left transition-colors',
        selected ? 'bg-blue-600/15 border border-blue-500/30' : 'hover:bg-slate-800 border border-transparent'
      )}
    >
      <RiskBadge score={h.risk_score} size="sm" />
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium text-slate-200 truncate">{h.name}</div>
        <div className="text-2xs text-slate-500">{h.ward} · {h.taluk}</div>
      </div>
      <div className="flex items-center gap-1 text-2xs font-mono">
        {changeIcon}
        <span className={h.risk_change > 0 ? 'text-red-400' : h.risk_change < 0 ? 'text-green-400' : 'text-slate-500'}>
          {h.risk_change > 0 ? '+' : ''}{h.risk_change}
        </span>
      </div>
      <PriorityBadge priority={h.priority} size="sm" />
    </button>
  )
}

export function Overview() {
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState<string | null>('munnar-central')
  const [showHazard, setShowHazard] = useState(false)

  const handleSelect = (id: string) => {
    setSelectedId(id)
  }

  const handleInvestigate = () => {
    if (selectedId) navigate(`/habitations/${selectedId}`)
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* LEFT PANEL — situational data */}
      <div className="flex w-72 flex-shrink-0 flex-col gap-3 overflow-y-auto border-r border-slate-800 bg-slate-950 p-3">
        {/* District header */}
        <div>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-sm font-semibold text-slate-200">Idukki District</h1>
              <p className="text-xs text-slate-500">Kerala · Pilot Region</p>
            </div>
            <FreshnessBadge status="DEMO" ageHours={3} />
          </div>
        </div>

        {/* KPI grid */}
        <div className="grid grid-cols-2 gap-2">
          <KPICard
            label="Critical"
            value={d.critical_habitations}
            sub="habitations"
            color="text-red-400"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
          />
          <KPICard
            label="High Risk"
            value={d.high_risk_habitations}
            sub="habitations"
            color="text-orange-400"
            icon={<MapPin className="h-3.5 w-3.5" />}
          />
          <KPICard
            label="At Risk"
            value={d.total_population_at_risk}
            sub="population"
            color="text-yellow-400"
            icon={<Users className="h-3.5 w-3.5" />}
          />
          <KPICard
            label="Immediate"
            value={d.immediate_relocation_needed}
            sub="need relocation"
            color="text-red-400"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
          />
        </div>

        {/* What Changed */}
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">What Changed</h2>
          <div className="flex flex-col gap-2">
            {overview.what_changed.map(item => (
              <WhatChangedItem key={item.id} item={item} />
            ))}
          </div>
        </div>

        {/* Telemetry Anomalies */}
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Telemetry Anomalies</h2>
          <div className="flex flex-col gap-1.5">
            {overview.telemetry_anomalies.map(item => (
              <TelemetryItem key={item.id} item={item} />
            ))}
          </div>
        </div>

        {/* Data freshness */}
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Data Freshness</h2>
          <div className="flex flex-col gap-1">
            {Object.entries(overview.data_freshness).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between">
                <span className="text-xs text-slate-500 capitalize">{key.replace('_', ' ')}</span>
                <FreshnessBadge status={val.status} ageHours={val.age_hours} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CENTER — GIS map (main element) */}
      <div className="relative flex-1">
        <MapContainer
          habitations={DEMO_HABITATIONS}
          selectedHabitationId={selectedId}
          onHabitationSelect={handleSelect}
          showHazardLayer={showHazard}
          className="h-full w-full"
        />

        {/* Map controls overlay */}
        <div className="absolute left-3 top-3 flex flex-col gap-2">
          <button
            onClick={() => setShowHazard(v => !v)}
            className={clsx(
              'rounded border px-2.5 py-1.5 text-xs font-medium transition-colors',
              showHazard
                ? 'border-blue-500/50 bg-blue-600/20 text-blue-400'
                : 'border-slate-700 bg-slate-900/90 text-slate-400 hover:text-slate-300'
            )}
          >
            {showHazard ? 'Hide' : 'Show'} Hazard Layer
          </button>
          <div className="rounded border border-slate-700 bg-slate-900/90 px-2.5 py-1.5">
            <div className="text-2xs text-slate-500 mb-1">Risk Legend</div>
            {[
              { label: 'Critical (80+)', color: 'bg-red-500' },
              { label: 'High (60-79)', color: 'bg-orange-500' },
              { label: 'Medium (40-59)', color: 'bg-yellow-500' },
              { label: 'Low (<40)', color: 'bg-green-500' },
            ].map(({ label, color }) => (
              <div key={label} className="flex items-center gap-1.5 mb-0.5">
                <span className={clsx('h-2 w-2 rounded-full', color)} />
                <span className="text-2xs text-slate-400">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* RIGHT PANEL — habitation list + priority actions */}
      <div className="flex w-64 flex-shrink-0 flex-col gap-3 overflow-y-auto border-l border-slate-800 bg-slate-950 p-3">
        {/* Habitation list */}
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Habitations</h2>
          <div className="flex flex-col gap-1">
            {DEMO_HABITATIONS.map(h => (
              <HabitationListRow
                key={h.id}
                h={h}
                selected={selectedId === h.id}
                onSelect={handleSelect}
              />
            ))}
          </div>
        </div>

        {/* Selected habitation quick view */}
        {selectedId && (() => {
          const h = DEMO_HABITATIONS.find(x => x.id === selectedId)
          if (!h) return null
          return (
            <div className="rounded-lg border border-slate-700 bg-slate-900 p-3">
              <div className="text-2xs text-slate-500 mb-1">{h.ward} · {h.taluk}</div>
              <div className="text-sm font-semibold text-slate-200 mb-2">{h.name}</div>
              <div className="flex items-center gap-3 mb-3">
                <div>
                  <div className="text-2xs text-slate-500">RISK</div>
                  <RiskBadge score={h.risk_score} size="lg" />
                </div>
                <div>
                  <div className="text-2xs text-slate-500">POPULATION</div>
                  <div className="text-sm font-semibold text-slate-200">{h.population.toLocaleString()}</div>
                </div>
              </div>
              <div className="flex items-center gap-2 mb-3">
                <PriorityBadge priority={h.priority} />
                <span className="text-xs text-slate-500">{h.primary_hazard}</span>
              </div>
              <button
                onClick={handleInvestigate}
                className="w-full rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 transition-colors"
              >
                Investigate →
              </button>
            </div>
          )
        })()}

        {/* Priority Actions */}
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Priority Actions</h2>
          <div className="flex flex-col gap-2">
            {overview.priority_actions.map(item => (
              <PriorityActionItem key={item.id} item={item} />
            ))}
          </div>
        </div>

        {/* System note */}
        <div className="rounded border border-slate-800 bg-slate-900/50 p-2.5">
          <div className="flex items-start gap-2">
            <Clock className="h-3.5 w-3.5 text-slate-600 flex-shrink-0 mt-0.5" />
            <p className="text-2xs text-slate-500 leading-relaxed">
              Sentinel AI is decision support only. All recommendations require human authority review before action.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
