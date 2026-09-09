// Sentinel AI — Command Overview Screen (Redesigned)
// Modern Emergency Operations Center dashboard: live API-driven figures,
// honest system statuses, unified risk palette with the map layer, and
// accessible interactive rows. Falls back to the labelled demo seed offline.

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Users,
  MapPin,
  Activity,
  Droplets,
  Mountain,
  Wind,
  RefreshCw,
  Bell,
  Settings,
  Share2,
  LayoutGrid,
  TrendingUp,
  TrendingDown,
  Waves,
} from "lucide-react";
import { MapContainer } from "../components/map/MapContainer";
import { PriorityBadge } from "../components/ui/PriorityBadge";
import { DEMO_DISTRICT_OVERVIEW, DEMO_HABITATIONS } from "../data/idukki-seed";
import { RedZoneDetectionService } from "../services/redZoneDetectionService";
import { api } from "../api/client";
import type { DistrictOverview, HabitationListItem } from "../types";
import clsx from "clsx";

// ── Unified risk palette — identical thresholds/colors as MapContainer ──────
const RISK = {
  critical: '#ef4444', // 80+
  high: '#f97316',     // 60-79
  medium: '#eab308',   // 40-59
  low: '#22c55e',      // <40
} as const;

const riskColor = (score: number): string =>
  score >= 80 ? RISK.critical
  : score >= 60 ? RISK.high
  : score >= 40 ? RISK.medium
  : RISK.low;

interface OverviewStats {
  criticalHabitations: number;
  highRiskHabitations: number;
  totalHabitations: number;
  totalPopulationAtRisk: number;
  immediateRelocationNeeded: number;
  lastUpdate: string;
}

interface TelemetryItem {
  id: string;
  type: 'rainfall' | 'soil_moisture' | 'river_level' | 'cloudburst' | 'wind' | 'temperature';
  location: string;
  value: string;
  status: 'normal' | 'warning' | 'exceeded' | 'critical';
  threshold: string;
  dataType: string;
}

interface WhatChangedItem {
  id: string;
  type: string;
  habitation: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
  dataType: string;
}

interface PriorityAction {
  id: string;
  priority: 'IMMEDIATE' | 'SHORT-TERM' | 'MEDIUM-TERM';
  habitation: string;
  action: string;
  population: number;
  dataType: string;
}

type OverviewSource = 'api' | 'demo_fallback';

/**
 * OverviewService — single source of truth for the Command Overview.
 * API first (validated risk engine), versioned demo seed as labelled fallback.
 */
class OverviewService {
  private static instance: OverviewService;
  private redZoneService: RedZoneDetectionService;
  private overview: DistrictOverview = DEMO_DISTRICT_OVERVIEW;
  private source: OverviewSource = 'demo_fallback';

  private constructor() {
    this.redZoneService = RedZoneDetectionService.getInstance();
  }

  public static getInstance(): OverviewService {
    if (!OverviewService.instance) {
      OverviewService.instance = new OverviewService();
    }
    return OverviewService.instance;
  }

  startMonitoring(): void {
    this.redZoneService.startMonitoring('idukki', 2); // every 2 min (demo cadence)
  }

  stopMonitoring(): void {
    this.redZoneService.stopMonitoring();
  }

  async loadOverview(): Promise<OverviewSource> {
    try {
      this.overview = await api.getDistrictOverview('idukki') as DistrictOverview;
      this.source = 'api';
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'API unavailable';
      console.warn(`[Sentinel AI] Overview API unavailable, using demo seed: ${msg}`);
      this.overview = DEMO_DISTRICT_OVERVIEW;
      this.source = 'demo_fallback';
    }
    return this.source;
  }

  getSource(): OverviewSource {
    return this.source;
  }

  getOverviewStats(): OverviewStats {
    const d = this.overview.district;
    return {
      criticalHabitations: d.critical_habitations,
      highRiskHabitations: d.high_risk_habitations,
      totalHabitations: d.total_habitations,
      totalPopulationAtRisk: d.total_population_at_risk,
      immediateRelocationNeeded: d.immediate_relocation_needed,
      lastUpdate: d.last_updated,
    };
  }

  getTelemetryData(): TelemetryItem[] {
    const typeMap: Record<string, TelemetryItem['type']> = {
      rainfall: 'rainfall',
      soil_moisture: 'soil_moisture',
      river_level: 'river_level',
      cloudburst: 'cloudburst',
      wind: 'wind',
      temperature: 'temperature',
    };
    return this.overview.telemetry_anomalies.map(a => ({
      id: a.id,
      type: typeMap[a.type] ?? 'rainfall',
      location: a.location,
      value: a.value,
      status: (['normal', 'warning', 'exceeded', 'critical'].includes(a.status)
        ? a.status : 'warning') as TelemetryItem['status'],
      threshold: a.threshold,
      dataType: a.data_type,
    }));
  }

  getWhatChanged(): WhatChangedItem[] {
    return this.overview.what_changed.map(change => ({
      id: change.id,
      type: change.type,
      habitation: change.habitation,
      description: change.description,
      severity: change.severity as WhatChangedItem['severity'],
      dataType: change.data_type,
      timestamp: change.timestamp,
    }));
  }

  getPriorityActions(): PriorityAction[] {
    return this.overview.priority_actions
      .filter(action => action.priority !== 'MONITOR' && action.priority !== 'NONE')
      .map(action => ({
        id: action.id,
        priority: action.priority as PriorityAction['priority'],
        habitation: action.habitation,
        action: action.action,
        population: action.population,
        dataType: action.data_type,
      }));
  }
}

const getStatusColor = (status: string): string => {
  switch (status.toLowerCase()) {
    case 'normal': return RISK.low;
    case 'warning': return RISK.high;
    case 'exceeded':
    case 'critical': return RISK.critical;
    default: return '#33b5e5';
  }
};

const formatTimeAgo = (timestamp: string): string => {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);

  if (diffMinutes < 1) return 'just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
};

export function Overview() {
  const navigate = useNavigate();
  const [overviewStats, setOverviewStats] = useState<OverviewStats | null>(null);
  const [telemetryData, setTelemetryData] = useState<TelemetryItem[]>([]);
  const [whatChanged, setWhatChanged] = useState<WhatChangedItem[]>([]);
  const [priorityActions, setPriorityActions] = useState<PriorityAction[]>([]);
  const [redZoneAlerts, setRedZoneAlerts] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>("munnar-central");
  const [showHazardLayer, setShowHazardLayer] = useState(false);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [dataSource, setDataSource] = useState<OverviewSource | null>(null);

  const overviewService = OverviewService.getInstance();
  const redZoneService = RedZoneDetectionService.getInstance();

  const refreshAll = useCallback(async () => {
    const source = await overviewService.loadOverview();
    setDataSource(source);
    setOverviewStats(overviewService.getOverviewStats());
    setTelemetryData(overviewService.getTelemetryData());
    setWhatChanged(overviewService.getWhatChanged());
    setPriorityActions(overviewService.getPriorityActions());
    setRedZoneAlerts(redZoneService.getActiveAlerts());
  }, [overviewService, redZoneService]);

  useEffect(() => {
    setIsMonitoring(true);
    overviewService.startMonitoring();
    refreshAll();
    return () => {
      overviewService.stopMonitoring();
      setIsMonitoring(false);
    };
  }, [overviewService, redZoneService, refreshAll]);

  useEffect(() => {
    if (!isMonitoring) return;
    const interval = setInterval(() => {
      refreshAll().catch(error =>
        console.error('Error refreshing overview data:', error)
      );
    }, 45000);
    return () => clearInterval(interval);
  }, [isMonitoring, refreshAll]);

  const selectedHabitation: HabitationListItem =
    DEMO_HABITATIONS.find((h) => h.id === selectedId) ?? DEMO_HABITATIONS[0];

  return (
    <div className="flex h-full overflow-hidden bg-slate-950 text-white">
      {/* LEFT PANEL — situation overview & controls */}
      <aside className="w-72 flex-shrink-0 overflow-y-auto border-r border-slate-800 bg-slate-900 p-4">
        <div className="mb-4 flex items-center gap-3">
          <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-slate-950/20 border border-slate-800/30">
            <LayoutGrid className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wide">Sentinel AI Command</h1>
            <p className="text-xs text-slate-400">Emergency Operations Center</p>
          </div>
        </div>

        {/* Quick Stats — counts, not trends; no fake ▲/▼ on static figures */}
        <div className="space-y-3">
          <OverviewStatCard
            title="Critical Zones"
            value={`${overviewStats?.criticalHabitations ?? '—'}`}
            icon={<MapPin className="h-4 w-4" style={{ color: RISK.critical }} />}
          />
          <OverviewStatCard
            title="High-Risk Zones"
            value={`${overviewStats?.highRiskHabitations ?? '—'}`}
            icon={<AlertTriangle className="h-4 w-4" style={{ color: RISK.high }} />}
          />
          <OverviewStatCard
            title="At Risk Pop."
            value={(overviewStats?.totalPopulationAtRisk ?? 0).toLocaleString()}
            icon={<Users className="h-4 w-4" />}
          />
          <OverviewStatCard
            title="Immediate Action"
            value={`${overviewStats?.immediateRelocationNeeded?.toLocaleString() ?? '—'}`}
            icon={<Users className="h-4 w-4" style={{ color: RISK.critical }} />}
          />
        </div>

        {/* Data provenance */}
        <div
          className={clsx(
            'mt-4 rounded border px-2.5 py-1.5 text-2xs font-mono uppercase tracking-wider',
            dataSource === 'api'
              ? 'border-cyan-500/30 bg-cyan-500/5 text-cyan-300'
              : 'border-amber-500/30 bg-amber-500/5 text-amber-300'
          )}
          title={dataSource === 'api'
            ? 'Figures served by the Sentinel AI API (validated risk engine)'
            : 'API unreachable — showing the versioned demo seed. All figures are illustrative.'}
        >
          {dataSource === 'api'
            ? `● API · updated ${overviewStats?.lastUpdate.slice(11, 16) ?? ''} UTC`
            : '● DEMO SEED · not live data'}
        </div>

        {/* System Status — every line reflects real state; nothing hardcoded */}
        <div className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide">System Status</h2>
          <div className="space-y-2">
            <StatusIndicator
              label="Data Source"
              status={dataSource === 'api' ? 'active' : 'warning'}
              details={dataSource === 'api' ? 'API engine' : 'demo seed (API down)'}
            />
            <StatusIndicator
              label="Red-Zone Monitor"
              status={isMonitoring ? 'active' : 'inactive'}
              details={isMonitoring ? 'polling every 2 min' : 'stopped'}
            />
            <StatusIndicator
              label="Alert System"
              status={redZoneAlerts.length > 0 ? 'warning' : 'active'}
              details={redZoneAlerts.length > 0
                ? `${redZoneAlerts.length} active alert${redZoneAlerts.length > 1 ? 's' : ''}`
                : 'No alerts'}
            />
          </div>
        </div>

        {/* Navigation — one control per destination (was duplicated) */}
        <div className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide">Navigate</h2>
          <div className="space-y-2">
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/risk')}
              icon={<Activity className="h-4 w-4" />}
              label="Risk Intelligence"
            />
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/habitations')}
              icon={<Users className="h-4 w-4" />}
              label="Habitations"
            />
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/relocation')}
              icon={<MapPin className="h-4 w-4" />}
              label="Relocation & Routing"
            />
            <ButtonVariant
              variant="outline"
              onClick={() => setShowHazardLayer(!showHazardLayer)}
              icon={<RefreshCw className="h-4 w-4" />}
              label={showHazardLayer ? 'Hide Hazard Overlay' : 'Show Hazard Overlay'}
              aria-pressed={showHazardLayer}
            />
            <ButtonVariant
              variant="outline"
              onClick={() => navigate('/scenarios')}
              icon={<TrendingUp className="h-4 w-4" />}
              label="Scenario Planning"
            />
            <ButtonVariant
              variant="outline"
              onClick={() => navigate('/data')}
              icon={<Share2 className="h-4 w-4" />}
              label="Data Sources"
            />
          </div>
        </div>

        {/* Priority focus */}
        <div className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide">Priority Focus</h2>
          <ButtonVariant
            variant="success"
            onClick={() => navigate('/habitations/munnar-central')}
            icon={<AlertTriangle className="h-4 w-4" />}
            label="Investigate Munnar Central"
          />
        </div>
      </aside>

      {/* MAIN CONTENT — map, telemetry, changes, actions */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header Bar */}
        <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900/50 px-4">
          <div className="flex items-center gap-3">
            <Activity className="h-4 w-4 text-cyan-400" />
            <div>
              <h1 className="text-sm font-bold tracking-wide">District Overview</h1>
              <p className="text-xs text-slate-400">Idukki, Kerala · live monitoring</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <div
              className="flex items-center gap-1.5"
              title={redZoneAlerts.length > 0 ? `${redZoneAlerts.length} active red-zone alerts` : 'No active alerts'}
            >
              <Bell className={clsx(
                'h-3.5 w-3.5',
                redZoneAlerts.length > 0 ? 'animate-pulse text-red-500' : 'text-slate-500'
              )} />
              <span className="font-mono">{redZoneAlerts.length}</span>
            </div>
          </div>
        </header>

        {/* Content grid — map first (EOC primary surface), panels below */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Map */}
            <section className="lg:col-span-2" aria-label="Live situation map">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-semibold tracking-wide">Live Situation Map</h2>
                <div className="flex items-center gap-3 text-2xs">
                  <span className="flex items-center gap-1 text-slate-500">
                    <span className={clsx('h-2 w-2 rounded-full', showHazardLayer ? 'bg-teal-400' : 'bg-slate-600')} />
                    {showHazardLayer ? 'Hazard overlay ON (Bhuvan WMS)' : 'Hazard overlay off'}
                  </span>
                  <span className="flex items-center gap-1 text-slate-500">
                    <span className="h-2 w-2 rounded-full bg-green-500" />
                    Habitations live
                  </span>
                </div>
              </div>
              <MapContainer
                habitations={DEMO_HABITATIONS}
                selectedHabitationId={selectedId}
                onHabitationSelect={setSelectedId}
                showHazardLayer={showHazardLayer}
                className="h-[380px] w-full rounded-lg border border-slate-800"
              />
              {/* Legend uses the exact map palette */}
              <div className="mt-2 flex flex-wrap items-center gap-4 rounded-lg border border-slate-800/20 bg-slate-900/50 px-3 py-2">
                {[
                  { label: 'Critical (80+)', color: RISK.critical },
                  { label: 'High (60–79)', color: RISK.high },
                  { label: 'Medium (40–59)', color: RISK.medium },
                  { label: 'Low (<40)', color: RISK.low },
                ].map(({ label, color }) => (
                  <span key={label} className="flex items-center gap-1.5 text-2xs text-slate-400">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
                    {label}
                  </span>
                ))}
              </div>
            </section>

            {/* Telemetry */}
            <TelemetryPanel
              telemetry={telemetryData}
              onItemClick={() => navigate('/risk')}
            />

            {/* What changed */}
            <RecentChangesPanel
              changes={whatChanged}
              onItemClick={() => navigate('/habitations')}
            />

            {/* Priority actions */}
            <section className="lg:col-span-2">
              <PriorityActionsPanel
                actions={priorityActions}
                onActionClick={() => navigate('/relocation')}
              />
            </section>
          </div>
        </div>
      </main>

      {/* RIGHT PANEL — focused habitation & alerts (wide screens only;
          below xl the map deserves the space) */}
      <aside className="hidden xl:block w-72 flex-shrink-0 overflow-y-auto border-l border-slate-800 bg-slate-900 p-4">
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide">Focused Habitation</h2>
          <HabitationFocusCard
            habitation={selectedHabitation}
            onInvestigate={() => selectedId && navigate(`/habitations/${selectedId}`)}
            redZoneAlerts={redZoneAlerts.filter((a: any) => a.habitationId === selectedId)}
          />
        </section>

        <section className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide">
            Active Alerts
            <span className="rounded bg-slate-950/60 px-1.5 py-0.5 font-mono text-2xs text-slate-400">
              {redZoneAlerts.length}
            </span>
          </h2>
          {redZoneAlerts.length > 0 ? (
            <div className="space-y-3">
              {redZoneAlerts.map((alert: any) => (
                <RedZoneAlertCard
                  key={alert.id}
                  alert={alert}
                  onClick={() => navigate(`/habitations/${alert.habitationId}`)}
                />
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center rounded-lg border border-slate-800/40 bg-slate-900/30 py-8 text-center text-slate-500">
              <div>
                <Activity className="mx-auto mb-2 h-6 w-6 text-slate-600" aria-hidden />
                <p className="text-xs">All systems normal</p>
                <p className="text-2xs">No active alerts</p>
              </div>
            </div>
          )}
        </section>
      </aside>
    </div>
  );
}

// Component: Overview stat card (count — no trend decoration)
function OverviewStatCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between p-3 bg-slate-900/30 rounded-lg border border-slate-800">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-950/20">
          {icon}
        </div>
        <div className="flex-1">
          <p className="text-xs text-slate-400">{title}</p>
          <p className="text-lg font-bold font-mono">{value}</p>
        </div>
      </div>
    </div>
  );
}

// Component: Button Variant
function ButtonVariant({
  variant,
  onClick,
  icon,
  label,
  ariaPressed,
}: {
  variant: 'primary' | 'secondary' | 'success' | 'warning' | 'outline';
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  ariaPressed?: boolean;
}) {
  const variants: Record<string, { bg: string; text: string }> = {
    primary: { bg: '#00b4d8', text: '#0a0a0a' },
    secondary: { bg: '#1a1a1a', text: '#ffffff' },
    success: { bg: '#00c853', text: '#0a0a0a' },
    warning: { bg: '#ffbb33', text: '#0a0a0a' },
    outline: { bg: 'transparent', text: '#ffffff' },
  };
  const variantStyle = variants[variant] || variants.outline;
  return (
    <button
      onClick={onClick}
      aria-pressed={ariaPressed}
      style={{ backgroundColor: variantStyle.bg, color: variantStyle.text }}
      className="flex w-full items-center justify-start gap-3 px-3 py-2 text-left text-sm font-medium transition-all rounded-md hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

// Component: Status Indicator
function StatusIndicator({
  label,
  status,
  details,
}: {
  label: string;
  status: 'active' | 'warning' | 'error' | 'inactive';
  details: string;
}) {
  const statusColors: Record<string, string> = {
    active: RISK.low,
    warning: '#ffbb33',
    error: RISK.critical,
    inactive: '#64748b',
  };
  return (
    <div className="flex items-center justify-between p-2 bg-slate-900/20 rounded border border-slate-800">
      <div className="flex items-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: statusColors[status] }} />
        <span className="text-xs">{label}</span>
      </div>
      <div className="text-xs text-slate-400">{details}</div>
    </div>
  );
}

// Component: Telemetry Panel
function TelemetryPanel({ telemetry, onItemClick }: { telemetry: TelemetryItem[]; onItemClick: () => void }) {
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-4">
      <div className="mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide">Live Telemetry Feed</h2>
        <p className="text-xs text-slate-500">Sensor anomalies from the monitoring network</p>
      </div>
      <div className="space-y-2">
        {telemetry.length === 0 && (
          <p className="text-xs text-slate-500">No anomalies reported.</p>
        )}
        {telemetry.map(item => (
          <TelemetryItemRow key={item.id} item={item} onClick={onItemClick} />
        ))}
      </div>
    </div>
  );
}

// Component: Telemetry row — button semantics + keyboard support
function TelemetryItemRow({ item, onClick }: { item: TelemetryItem; onClick: () => void }) {
  const statusColor = getStatusColor(item.status);
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-between rounded border border-slate-800/20 p-3 text-left cursor-pointer transition-colors hover:bg-slate-900/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
    >
      <div className="flex flex-1 items-center gap-2.5">
        <div className="w-6 h-6 flex flex-shrink-0 items-center justify-center rounded bg-slate-950/40">
          {item.type === 'rainfall' && <Droplets className="h-3.5 w-3.5 text-cyan-400" />}
          {item.type === 'soil_moisture' && <Mountain className="h-3.5 w-3.5 text-amber-500" />}
          {item.type === 'river_level' && <Waves className="h-3.5 w-3.5 text-blue-400" />}
          {item.type === 'wind' && <Wind className="h-3.5 w-3.5 text-slate-300" />}
          {item.type === 'temperature' && <Activity className="h-3.5 w-3.5 text-red-400" />}
        </div>
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">{item.location}</p>
          <p className="text-2xs uppercase tracking-wide text-slate-500">
            {item.type.replace('_', ' ')} · threshold {item.threshold}
          </p>
        </div>
      </div>
      <div className="flex flex-shrink-0 items-center gap-2.5">
        <span className="font-mono text-sm font-bold">{item.value}</span>
        <span className="flex items-center gap-1.5 text-2xs capitalize text-slate-400">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: statusColor }} />
          {item.status}
        </span>
      </div>
    </button>
  );
}

// Component: Recent Changes Panel
function RecentChangesPanel({ changes, onItemClick }: { changes: WhatChangedItem[]; onItemClick: () => void }) {
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-4">
      <div className="mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide">Recent Changes</h2>
        <p className="text-xs text-slate-500">Latest situation updates</p>
      </div>
      <div className="space-y-2">
        {changes.map(change => (
          <ChangeItemRow key={change.id} change={change} onClick={onItemClick} />
        ))}
      </div>
    </div>
  );
}

// Component: Change row — severity from the record; time computed client-side
function ChangeItemRow({ change, onClick }: { change: WhatChangedItem; onClick: () => void }) {
  const severityColors: Record<string, string> = {
    low: '#33b5e5',
    medium: '#ffbb33',
    high: RISK.high,
    critical: RISK.critical,
  };
  const typeIcon = (() => {
    if (change.type === 'risk_increase') return <TrendingUp className="h-3.5 w-3.5" />;
    if (change.type === 'risk_decrease') return <TrendingDown className="h-3.5 w-3.5" />;
    if (change.type === 'new_hazard') return <AlertTriangle className="h-3.5 w-3.5" />;
    if (change.type === 'sensor_alert') return <Bell className="h-3.5 w-3.5" />;
    if (change.type === 'infrastructure_change') return <Settings className="h-3.5 w-3.5" />;
    return <Activity className="h-3.5 w-3.5" />;
  })();

  return (
    <button
      onClick={onClick}
      className="flex w-full items-start justify-between rounded border border-slate-800/20 p-3 text-left cursor-pointer transition-colors hover:bg-slate-900/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
    >
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="w-5 h-5 flex flex-shrink-0 items-center justify-center rounded bg-slate-950/40 text-slate-300">
            {typeIcon}
          </span>
          <span className="text-xs font-medium">{change.habitation}</span>
          <span className="text-2xs uppercase tracking-wide text-slate-500">
            {change.type.replace(/_/g, ' ')}
          </span>
        </div>
        <p className="line-clamp-2 text-xs text-slate-400">{change.description}</p>
        <div className="mt-1.5 flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-2xs capitalize text-slate-500">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: severityColors[change.severity] }} />
            {change.severity}
          </span>
          <span className="text-2xs text-slate-500">{formatTimeAgo(change.timestamp)}</span>
        </div>
      </div>
    </button>
  );
}

// Component: Priority Actions Panel
function PriorityActionsPanel({ actions, onActionClick }: { actions: PriorityAction[]; onActionClick: () => void }) {
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-4">
      <div className="mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide">Priority Actions</h2>
        <p className="text-xs text-slate-500">Current operational priorities</p>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {actions.map(action => (
          <ActionItemRow key={action.id} action={action} onClick={onActionClick} />
        ))}
      </div>
    </div>
  );
}

// Component: Action row — PriorityBadge carries the color; no duplicate dot
function ActionItemRow({ action, onClick }: { action: PriorityAction; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-start justify-between gap-2 rounded border border-slate-800/20 p-3 text-left cursor-pointer transition-colors hover:bg-slate-900/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
    >
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <PriorityBadge priority={action.priority} size="sm" />
          <span className="text-xs font-medium">{action.habitation}</span>
        </div>
        <p className="text-xs text-slate-400">{action.action}</p>
      </div>
      <span className="flex-shrink-0 text-right">
        <span className="block font-mono text-sm font-bold">{action.population.toLocaleString()}</span>
        <span className="block text-2xs text-slate-500">persons</span>
      </span>
    </button>
  );
}

// Component: Habitation focus card — palette aligned with the map
function HabitationFocusCard({
  habitation,
  onInvestigate,
  redZoneAlerts,
}: {
  habitation: HabitationListItem;
  onInvestigate: () => void;
  redZoneAlerts: any[];
}) {
  const color = riskColor(habitation.risk_score);
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800 p-4">
      <div className="mb-3 flex items-start justify-between">
        <div className="min-w-0">
          <div className="text-2xs text-slate-400">{habitation.ward} · {habitation.taluk}</div>
          <h3 className="truncate text-sm font-bold">{habitation.name}</h3>
        </div>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
          <span className="font-mono text-sm font-bold">{habitation.risk_score}</span>
        </span>
      </div>

      {/* Risk bar */}
      <div className="mb-3">
        <div className="h-2 w-full overflow-hidden rounded bg-slate-950/60">
          <div
            className="h-2 rounded transition-all"
            style={{ width: `${habitation.risk_score}%`, backgroundColor: color }}
          />
        </div>
        <div className="mt-1 flex items-center justify-between text-2xs text-slate-500">
          <span>risk score</span>
          <span className="font-mono">{habitation.risk_score}/100</span>
        </div>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2">
        <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
          <div className="text-2xs text-slate-500">Population</div>
          <div className="font-mono text-sm font-bold">{habitation.population.toLocaleString()}</div>
        </div>
        <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
          <div className="text-2xs text-slate-500">Primary hazard</div>
          <div className="text-xs font-semibold capitalize">
            {habitation.primary_hazard.replace('_', ' ').toLowerCase()}
          </div>
        </div>
      </div>

      {redZoneAlerts.length > 0 && (
        <div className="mb-3 border-t border-slate-800/20 pt-2">
          {redZoneAlerts.map((alert: any) => (
            <div key={alert.id} className="rounded border border-red-500/30 bg-red-500/5 p-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-red-400">{alert.redZoneStatus}</span>
                <span className="font-mono text-2xs text-slate-400">{alert.riskScore}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-2xs text-slate-400">
                {alert.triggers.join(', ')}
              </p>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onInvestigate}
        className="w-full rounded-lg bg-cyan-500/20 px-4 py-2 text-sm font-medium text-cyan-300 transition-colors hover:bg-cyan-500/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
      >
        <span className="flex items-center justify-center gap-2">
          <Users className="h-4 w-4" />
          Investigate Habitation
        </span>
      </button>
    </div>
  );
}

// Component: Red Zone Alert Card
function RedZoneAlertCard({ alert, onClick }: { alert: any; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-start justify-between rounded border border-slate-800 p-3 text-left cursor-pointer transition-all hover:border-slate-600 hover:bg-slate-900/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400"
    >
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-500" />
          <span className="truncate text-xs font-medium">{alert.habitationName}</span>
        </div>
        <p className="text-2xs uppercase tracking-wide text-red-400/90">{alert.redZoneStatus}</p>
        <div className="mt-1.5 flex items-center gap-3 text-2xs text-slate-500">
          <span><span className="font-mono text-slate-300">{alert.riskScore}</span> risk</span>
          <span>conf <span className="font-mono text-slate-300">{alert.confidence.toFixed(2)}</span></span>
          <span>{formatTimeAgo(alert.detectedAt)}</span>
        </div>
        <p className="mt-1.5 line-clamp-2 text-2xs text-slate-400">
          {alert.triggers.slice(0, 3).join(' · ')}
        </p>
      </div>
    </button>
  );
}
