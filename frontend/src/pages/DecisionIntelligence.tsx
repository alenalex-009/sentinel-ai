// Sentinel AI — Decision Intelligence Screen (Redesigned)
// Emergency Operations Center Dashboard with Explainable AI Decision Traces

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowDown,
  Activity,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  LayoutGrid,
  MapPin,
  BarChart2,
  Zap,
  Route,
  ExternalLink,
} from "lucide-react";
import { DataTypeBadge } from "../components/ui/DataTypeBadge";
import { PriorityBadge } from "../components/ui/PriorityBadge";
import { RiskBadge } from "../components/ui/RiskBadge";
import { DEMO_MUNNAR_CENTRAL, DEMO_OPTIMIZATION_RESULT } from "../data/idukki-seed";
import { api } from "../api/client";
import { useApiWithFallback } from "../hooks/useApiWithFallback";
import type { EngineRouteResult, RoutingEngine, RoutingEnginesStatus } from "../types";
import clsx from "clsx";

// EOC status colors (shared by badges and indicators)
const EOC_COLORS = {
  accent: '#00b4d8',
  success: '#00c853',
  warning: '#ffbb33',
  danger: '#ff4444',
  info: '#33b5e5',
  textSecondary: '#b0b0b0'
} as const;
void EOC_COLORS;

// Decision trace — values consistent with validated risk model
const TRACE_STEPS = [
  { step: 1, node: 'OBSERVED HAZARDS', value: 'Landslide 88 | Flood 62 | Cloudburst 45 (KSDMA + IMD + CWC)', data_type: 'OBSERVED' as const, color: '#33b5e5' },
  { step: 2, node: 'EXPOSURE', value: '4,210 persons in hazard zone | 1,053 households | Exposure index 84/100', data_type: 'DERIVED' as const, color: '#8b5cf6' },
  { step: 3, node: 'VULNERABILITY', value: '73.85/100 ≈ 74 — HIGH | Demo 78 · Socio 71 · Infra 76 · Access 69', data_type: 'DERIVED' as const, color: '#8b5cf6' },
  { step: 4, node: 'OPERATIONAL RISK', value: '94/100 (Baseline 65, Change +29) | Base risk 80.21 + event escalation 13.65 = 93.86 ≈ 94', data_type: 'DERIVED' as const, color: '#f97316' },
  { step: 5, node: 'RELOCATION PRIORITY', value: 'IMMEDIATE — RPI 88/100 | 0.35×94 + 0.20×74 + 0.15×84 + 0.15×94 + 0.15×87', data_type: 'RECOMMENDATION' as const, color: '#ef4444' },
  { step: 6, node: 'SITE / CAPACITY CHECK', value: '3 candidate sites screened | C_safe: A=3,200 B=2,100 C=1,800 | Total=7,100 | Demand=4,210', data_type: 'DERIVED' as const, color: '#8b5cf6' },
  { step: 7, node: 'SYSTEM RECOMMENDATION', value: 'Initiate relocation assessment for Ward 04, Munnar Central. Multi-site allocation required.', data_type: 'RECOMMENDATION' as const, color: '#10b981' },
];

const TOP_DRIVERS: RiskDriversResponse['drivers'] = [
  { rank: 1, name: 'Landslide Susceptibility (KSDMA)', score: 88, weight: 0.40, contribution: 35.2, data_type: 'DERIVED' },
  { rank: 2, name: 'Soil Saturation (KSDMA Sensors)', score: 94, weight: 0.25, contribution: 23.5, data_type: 'OBSERVED' },
  { rank: 3, name: 'Structural Vulnerability', score: 76, weight: 0.25, contribution: 19.0, data_type: 'DERIVED' },
  { rank: 4, name: 'Access Route Risk', score: 69, weight: 0.15, contribution: 10.4, data_type: 'DERIVED' },
];

// Helper function to get trend icon and color
const getTrendIndicator = (trend: 'up' | 'down' | 'stable') => {
  switch (trend) {
    case 'up':
      return { icon: <TrendingUp className="h-4 w-4" />, color: '#ff4444' };
    case 'down':
      return { icon: <TrendingDown className="h-4 w-4" />, color: '#00c853' };
    default:
      return { icon: <Activity className="h-4 w-4" />, color: '#33b5e5' };
  }
};

// Shape of the backend /risk/drivers response (explanations block)
interface ExplanationEntry {
  feature: string;
  value: number;
  weight: number;
  contribution: number;
  percentage: number;
  data_type: 'OBSERVED' | 'DERIVED' | 'ESTIMATED' | 'SIMULATED' | 'RECOMMENDATION';
}
interface RiskDriversResponse {
  data_status: string;
  habitation_id: string;
  note?: string;
  drivers: Array<{ rank: number; name: string; score: number; weight: number; contribution: number; data_type: 'OBSERVED' | 'DERIVED' | 'ESTIMATED' | 'SIMULATED' | 'RECOMMENDATION' }>;
  explanations?: { hazard: ExplanationEntry[]; vulnerability: ExplanationEntry[] };
}
interface DecisionTraceResponse {
  data_status: string;
  habitation_id: string;
  trace: Array<{ step: number; node: string; value: string; data_type: 'OBSERVED' | 'DERIVED' | 'ESTIMATED' | 'SIMULATED' | 'RECOMMENDATION' }>;
  data_type?: string;
}

// Seed fallbacks — mirror the backend's canonical demo data so the page still
// renders coherently when the API is unreachable (labelled DEMO by the hook).
const FALLBACK_DRIVERS: RiskDriversResponse = {
  data_status: 'DEMO',
  habitation_id: 'munnar-central',
  note: 'Demo seed fallback — deterministic risk-engine baseline weights.',
  drivers: [
    { rank: 1, name: 'Landslide Susceptibility', score: 88, weight: 0.40, contribution: 35.2, data_type: 'DERIVED' },
    { rank: 2, name: 'Soil Saturation', score: 94, weight: 0.25, contribution: 23.5, data_type: 'OBSERVED' },
    { rank: 3, name: 'Structural Vulnerability', score: 76, weight: 0.25, contribution: 19.0, data_type: 'DERIVED' },
    { rank: 4, name: 'Access Route Risk', score: 69, weight: 0.15, contribution: 10.4, data_type: 'DERIVED' },
  ],
  explanations: {
    hazard: [
      { feature: 'Landslide Susceptibility', value: 88, weight: 0.40, contribution: 35.2, percentage: 49, data_type: 'DERIVED' },
      { feature: 'Soil Saturation (KSDMA Sensors)', value: 94, weight: 0.25, contribution: 23.5, percentage: 33, data_type: 'OBSERVED' },
      { feature: 'Rainfall Intensity (72hr)', value: 87, weight: 0.15, contribution: 13.05, percentage: 18, data_type: 'OBSERVED' },
    ],
    vulnerability: [
      { feature: 'Demographic Factors', value: 78, weight: 0.30, contribution: 23.4, percentage: 32, data_type: 'DERIVED' },
      { feature: 'Socioeconomic Factors', value: 68, weight: 0.20, contribution: 13.6, percentage: 18, data_type: 'DERIVED' },
      { feature: 'Infrastructure Score', value: 76, weight: 0.25, contribution: 19.0, percentage: 26, data_type: 'DERIVED' },
      { feature: 'Accessibility Score', value: 72, weight: 0.25, contribution: 18.0, percentage: 24, data_type: 'DERIVED' },
    ],
  },
};

export function DecisionIntelligence() {
  const navigate = useNavigate();
  const h = DEMO_MUNNAR_CENTRAL;
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<string>("");

  // Backend decision trace — the validated engine output, not a client-side model.
  const { data: traceData, source: traceSource } = useApiWithFallback<DecisionTraceResponse>(
    () => api.getDecisionTrace('munnar-central') as Promise<DecisionTraceResponse>,
    { data_status: 'DEMO', habitation_id: 'munnar-central', trace: TRACE_STEPS.map(s => ({ step: s.step, node: s.node, value: s.value, data_type: s.data_type })) },
    [],
  );

  // Backend risk drivers + engine-derived explanations (replaces the old
  // client-side mlPredictionService, whose weights disagreed with the engine).
  const { data: driversData, source: driversSource } = useApiWithFallback<RiskDriversResponse>(
    () => api.getRiskDrivers('munnar-central') as Promise<RiskDriversResponse>,
    FALLBACK_DRIVERS,
    [],
  );

  const mlExplanations = driversData?.explanations ?? null;
  const usingApi = traceSource === 'api' && driversSource === 'api';

  // ── Road-route citation (Phase 5C) ──────────────────────────────────
  // The relocation recommendation cites the ACTUAL road route to the primary
  // allocated site (largest allocation), fetched from the first online
  // routing engine. All engines route the same OSM network, so the first
  // online one is canonical here; provenance is shown with the figure.
  const primaryAllocation = [...DEMO_OPTIMIZATION_RESULT.allocations]
    .sort((a, b) => b.allocated_population - a.allocated_population)[0];
  const [routeResult, setRouteResult] = useState<EngineRouteResult | null>(null);
  const [routeState, setRouteState] = useState<'loading' | 'ok' | 'unavailable' | 'idle'>('idle');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const st = await api.getRoutingEngines('kerala') as RoutingEnginesStatus;
        if (cancelled) return;
        const order: RoutingEngine[] = ['osrm', 'graphhopper', 'valhalla'];
        const online = order.find(e => st.engines?.[e]?.ok);
        if (!online) {
          setRouteState('unavailable');
          return;
        }
        const r = await api.getRoute('munnar-central', primaryAllocation.site_id, online) as EngineRouteResult;
        if (cancelled) return;
        setRouteResult(r);
        setRouteState(r.status === 'OK' ? 'ok' : 'unavailable');
      } catch (err) {
        if (!cancelled) {
          console.warn('[Sentinel AI] route citation fetch failed:', err);
          setRouteState('unavailable');
        }
      }
    })();
    return () => { cancelled = true; };
  }, [primaryAllocation.site_id]);

  useEffect(() => {
    if (traceSource !== 'loading' && driversSource !== 'loading') {
      setIsMonitoring(true);
      setLastRefresh(new Date().toLocaleTimeString());
    }
  }, [traceSource, driversSource]);

  return (
    <div className="flex h-full overflow-hidden bg-slate-950 text-white">
      {/* LEFT PANEL - Controls & Status */}
      <aside className="w-72 flex-shrink-0 flex flex-col gap-4 border-r border-slate-800 bg-slate-900 p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-slate-950/20 border border-slate-800/30">
              <LayoutGrid className="h-5 w-5" />
           </div>
            <div>
              <h1 className="text-sm font-bold tracking-wide">Decision Intelligence</h1>
              <p className="text-xs text-slate-400">Explainable AI Trace</p>
           </div>
         </div>
          <div className="flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-2.5 h-2.5 rounded-full" style={{
                backgroundColor: isMonitoring ? '#00c853' : '#b0b0b0'
              }} />
              <span>{isMonitoring ? 'Live' : 'Static'}</span>
           </div>
            <span className="font-mono">{lastRefresh}</span>
         </div>
       </div>

        {/* Quick Stats */}
        <div className="space-y-3">
          <OverviewStatCard
            title="Decision Steps"
            value="7"
            icon={<Activity className="h-4 w-4" />}
            color={'#00b4d8'}
            trend="stable"
          />
          <OverviewStatCard
            title="Top Drivers"
            value="4"
            icon={<BarChart2 className="h-4 w-4" />}
            color={'#33b5e5'}
            trend="stable"
          />
          <OverviewStatCard
            title="Risk Score"
            value={`${h.risk.current}/100`}
            icon={<AlertTriangle className="h-4 w-4" />}
            color={h.risk.current >= 80 ? '#ff4444' : '#ffbb33'}
            trend={h.risk.change > 0 ? 'up' : 'down'}
          />
          <OverviewStatCard
            title="Priority"
            value={h.relocation_priority.priority}
            icon={<Zap className="h-4 w-4" />}
            color={'#ff4444'}
            trend="up"
          />
       </div>

        {/* Navigation */}
        <div className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">Navigation</h2>
          <div className="space-y-2">
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate(`/habitations/${h.id}`)}
              icon={<ArrowLeft className="h-4 w-4" />}
              label="Back to Investigation"
            />
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/')}
              icon={<LayoutGrid className="h-4 w-4" />}
              label="Command Overview"
            />
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/risk')}
              icon={<Activity className="h-4 w-4" />}
              label="Risk Intelligence"
            />
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/relocation')}
              icon={<MapPin className="h-4 w-4" />}
              label="Relocation Planning"
            />
         </div>
       </div>

        {/* System Status */}
        <div className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">System Status</h2>
          <div className="space-y-2">
            <StatusIndicator
              label="AI Engine"
              status="active"
              details="Models operational"
            />
            <StatusIndicator
              label="Decision Trace"
              status="active"
              details="7 steps available"
            />
            <StatusIndicator
              label="SHAP Explanations"
              status={mlExplanations ? 'active' : 'warning'}
              details={mlExplanations ? (usingApi ? 'Generated (API)' : 'Demo seed') : 'Calculating'}
            />
         </div>
       </div>
     </aside>

      {/* MAIN CONTENT - Decision Trace & Analysis */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header Bar */}
        <header className="flex h-16 items-center justify-between border-b border-slate-800 bg-slate-900/50 px-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-950/20">
                <Activity className="h-4 w-4" />
             </div>
              <div>
                <h1 className="text-sm font-bold tracking-wide">Decision Intelligence</h1>
                <p className="text-xs text-slate-400">
                  {h.ward} · {h.taluk} · {h.district}
               </p>
             </div>
           </div>
         </div>
       </header>

        {/* Main Content Area */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid gap-4 p-4">
            {/* Decision Trace Panel */}
            <div className="col-span-1 lg:col-span-2">
              <DecisionTracePanel steps={traceData?.trace ?? TRACE_STEPS} />
           </div>

            {/* Top Drivers Panel */}
            <div className="col-span-1 lg:col-span-2">
              <TopDriversPanel drivers={driversData?.drivers ?? TOP_DRIVERS} />
           </div>

            {/* Risk Score Breakdown */}
            <div className="col-span-1 lg:col-span-4">
              <RiskScoreBreakdownPanel habitation={h} />
           </div>

            {/* ML Explanations Panel */}
            {mlExplanations && (
              <div className="col-span-1 lg:col-span-4">
                <MLExplanationsPanel explanations={mlExplanations} />
             </div>
            )}
         </div>
       </div>
     </main>

      {/* RIGHT PANEL - System Recommendation & Trust Notes */}
      <aside className="w-72 flex-shrink-0 flex flex-col gap-4 border-l border-slate-800 bg-slate-900 p-4">        {/* System Recommendation */}
        <section>
          <div className="mb-4">
            <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">System Recommendation</h2>
         </div>
          <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold text-green-500">RECOMMENDATION</span>
              <DataTypeBadge type="RECOMMENDATION" />
           </div>
            <p className="text-sm text-slate-400 leading-relaxed mb-3">
              {h.system_recommendation}
           </p>
            <PriorityBadge priority={h.relocation_priority.priority} size="lg" />
         </div>

          {/* Road-route citation — real OSM route to the primary site */}
          {primaryAllocation && (
            <div className="mt-3 rounded-lg border border-cyan-500/25 bg-cyan-500/5 p-3">
              <div className="flex items-center justify-between mb-2">
                <h3 className="flex items-center gap-1.5 text-2xs font-semibold uppercase tracking-wide text-cyan-300">
                  <Route className="h-3.5 w-3.5" />
                  Route to primary site
                </h3>
                <span className="text-2xs text-slate-500" title="Largest allocation in the CP-SAT plan">
                  {Math.round((primaryAllocation.allocated_population / DEMO_OPTIMIZATION_RESULT.total_demand) * 100)}% of demand
                </span>
              </div>
              <p className="text-xs font-medium text-slate-200 mb-2">
                {primaryAllocation.site_name}
              </p>
              {routeState === 'loading' || routeState === 'idle' ? (
                <p className="text-2xs text-slate-500">Resolving road route…</p>
              ) : routeState === 'ok' && routeResult?.route ? (
                <>
                  <div className="mb-2 grid grid-cols-2 gap-2">
                    <div className="rounded border border-slate-800 bg-slate-950/50 p-2">
                      <div className="text-2xs text-slate-500">Road distance</div>
                      <div className="text-base font-bold font-mono text-white">
                        {routeResult.route.distance_km}
                        <span className="ml-1 text-2xs text-slate-400">km</span>
                      </div>
                    </div>
                    <div className="rounded border border-slate-800 bg-slate-950/50 p-2">
                      <div className="text-2xs text-slate-500">Travel time</div>
                      <div className="text-base font-bold font-mono text-white">
                        {routeResult.route.duration_min}
                        <span className="ml-1 text-2xs text-slate-400">min</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-2xs text-slate-500">
                    <span title={routeResult.route.method}>
                      via <span className="uppercase text-cyan-400">{routeResult.engine}</span> · OpenStreetMap
                    </span>
                    <button
                      onClick={() => navigate('/relocation')}
                      className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors"
                      title="Open Relocation & Routing workspace"
                    >
                      Plan route <ExternalLink className="h-3 w-3" />
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <p className="text-2xs text-amber-400/90 mb-1">
                    Road route unavailable — plan cites the DEMO/ESTIMATED seed distance of{' '}
                    <span className="font-mono">{primaryAllocation.distance_km} km</span>.
                  </p>
                  <p className="text-2xs text-slate-500">
                    No routing engine is reachable. Straight-line figures are never
                    relabelled as road routes — start OSRM/GraphHopper/Valhalla to cite
                    the real network distance.
                  </p>
                </>
              )}
            </div>
          )}
        </section>

        {/* Trust Notes */}
        <section className="mt-4 pt-3 border-t border-slate-800/20">
          <div className="mb-4">
            <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">About This Decision</h2>
         </div>
          <div className="space-y-2">                {[
              usingApi
                ? 'Scores and explanations served by the Sentinel AI API (validated deterministic engine).'
                : 'API unreachable — showing the demo seed; values mirror the validated engine.',
              routeState === 'ok' && routeResult?.route
                ? `Road route to ${primaryAllocation?.site_name.split(' — ')[1] ?? 'primary site'} measured on the OSM network via ${routeResult.engine.toUpperCase()} (not an estimate).`
                : 'Road-route figures fall back to the DEMO/ESTIMATED seed distance when no routing engine is reachable — never a relabelled straight line.',
              'Deterministic GIS and risk engines produce all scores — AI provides explanation only.',
              'Risk weights are configurable project baselines, not official government formulas.',
              'Operational risk is separate from permanent settlement suitability.',
              'All recommendations require human authority review before any action.',
              'Data labelled DEMO — not live government data.',
            ].map(note => (
              <div key={note} className="flex items-start gap-2 text-xs text-slate-400">
                <span className="mt-1 h-1 w-1 rounded-full bg-[#00b4d8] flex-shrink-0" />
                {note}
             </div>
            ))}
         </div>
       </section>
     </aside>
   </div>
  );
}

// Component: Overview Stat Card
function OverviewStatCard({
  title,
  value,
  icon,
  trend
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
  color?: string;
  trend: 'up' | 'down' | 'stable'
}) {
  const { icon: trendIcon, color: trendColor } = getTrendIndicator(trend);

  return (
    <div className="flex items-center justify-between p-3 bg-slate-900/30 rounded-lg border border-slate-800/20">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-950/20">
          {icon}
       </div>
        <div className="flex-1">
          <p className="text-xs text-slate-400">{title}</p>
          <p className="text-lg font-bold font-mono">{value}</p>
       </div>
     </div>
      <div className="flex items-center gap-2 text-xs">
        {trendIcon}
        <span className={clsx("font-mono", trendColor)}>{trend === 'up' ? '▲' : trend === 'down' ? '▼' : '●'}</span>
     </div>
   </div>
  );
}

// Component: Button Variant
function ButtonVariant({
  variant,
  onClick,
  icon,
  label
}: {
  variant: 'primary' | 'secondary' | 'success' | 'warning' | 'outline';
  onClick: () => void;
  icon: React.ReactNode;
  label: string
}) {
  const variants: Record<string, { bg: string; text: string; hover: string }> = {
    primary: { bg: '#00b4d8', text: '#0a0a0a', hover: '#00b4d8' },
    secondary: { bg: '#1a1a1a', text: '#ffffff', hover: '#2a2a2a' },
    success: { bg: '#00c853', text: '#0a0a0a', hover: '#00c853' },
    warning: { bg: '#ffbb33', text: '#0a0a0a', hover: '#ffbb33' },
    outline: { bg: 'transparent', text: '#ffffff', hover: '#2a2a2a' }
  };

  const variantStyle = variants[variant] || variants.outline;

  return (
    <button
      onClick={onClick}
      style={{ backgroundColor: variantStyle.bg }}
      className="flex w-full items-center justify-start gap-3 px-3 py-2 text-left text-sm font-medium transition-all rounded-md text-white hover:opacity-90"
    >
      {icon}
      <span>{label}</span>
   </button>
  );
}

// Component: Status Indicator
function StatusIndicator({ label, status, details }: { label: string; status: 'active' | 'warning' | 'error'; details: string }) {
  const statusColors: Record<string, string> = {
    active: '#00c853',
    warning: '#ffbb33',
    error: '#ff4444'
  };

  return (
    <div className="flex items-center justify-between p-2 bg-slate-900/20 rounded border border-slate-800/20">
      <div className="flex items-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: statusColors[status] }} />
        <span className="text-xs">{label}</span>
     </div>
      <div className="text-xs text-slate-400">{details}</div>
   </div>
  );
}

// Node color for trace steps — API steps carry no color, so derive a stable
// one from the data type (same palette the badges use).
const DATA_TYPE_COLOR: Record<string, string> = {
  OBSERVED: '#33b5e5',
  DERIVED: '#8b5cf6',
  ESTIMATED: '#f59e0b',
  SIMULATED: '#06b6d4',
  RECOMMENDATION: '#10b981',
};

// Component: Decision Trace Panel
function DecisionTracePanel({ steps }: { steps: DecisionTraceResponse['trace'] }) {
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 p-4">
      <div className="mb-3">
        <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">Decision Trace</h2>
        <p className="text-xs text-slate-400">Step-by-step decision logic</p>
     </div>
      <div className="space-y-2">
        {steps.map((step, idx) => (
          <div key={step.step} className="w-full">
            <div
              className="rounded border p-3"
              style={{
                borderColor: `${DATA_TYPE_COLOR[step.data_type] ?? '#8b5cf6'}40`,
                backgroundColor: `${DATA_TYPE_COLOR[step.data_type] ?? '#8b5cf6'}15`,
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold tracking-wide" style={{ color: DATA_TYPE_COLOR[step.data_type] ?? '#8b5cf6' }}>
                  {step.node}
               </span>
                <DataTypeBadge type={step.data_type} />
             </div>
              <p className="text-xs text-slate-400 font-mono">{step.value}</p>
           </div>
            {idx < steps.length - 1 && (
              <div className="flex justify-center py-1">
                <ArrowDown className="h-4 w-4 text-slate-400" />
             </div>
            )}
         </div>
        ))}
     </div>
   </div>
  );
}

// Component: Top Drivers Panel
function TopDriversPanel({ drivers }: { drivers: RiskDriversResponse['drivers'] }) {
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 p-4">
      <div className="mb-3">
        <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">Top Risk Drivers</h2>
        <p className="text-xs text-slate-400">Factors with highest contribution to risk</p>
     </div>
      <div className="space-y-3">
        {drivers.map(d => (
          <div key={d.rank} className="flex items-center gap-3">
            <span className="w-5 text-xs font-mono text-slate-400">#{d.rank}</span>
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-white">{d.name}</span>
                <div className="flex items-center gap-2">
                  <DataTypeBadge type={d.data_type} />
                  <span className="text-xs font-mono text-slate-400">w={Math.round(d.weight * 100)}%</span>
               </div>
             </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-slate-800">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${d.score}%`, backgroundColor: '#00b4d8' }}
                  />
               </div>
                <span className="text-xs font-mono text-slate-400 w-8 text-right">{d.score}</span>
                <span className="text-xs font-mono text-slate-400 w-10 text-right">+{d.contribution}</span>
             </div>
           </div>
         </div>
        ))}
     </div>
   </div>
  );
}

// Component: Risk Score Breakdown Panel
function RiskScoreBreakdownPanel({ habitation }: { habitation: any }) {
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 p-4">
      <div className="mb-3">
        <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">Risk Score Breakdown</h2>
        <p className="text-xs text-slate-400">Component-wise risk calculation</p>
     </div>
      <div className="flex items-center gap-4 mb-3">
        <RiskBadge score={habitation.risk.current} size="xl" />
        <div>
          <div className="text-xs text-slate-400">Baseline: <span className="font-mono text-white">{habitation.risk.baseline}</span></div>
          <div className="text-xs text-red-500">Change: <span className="font-mono">+{habitation.risk.change}</span></div>
          <DataTypeBadge type={habitation.risk.data_type} />
       </div>
     </div>
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: 'Hazard (40%)', value: habitation.risk.hazard_component, note: '0.40 × 88' },
          { label: 'Exposure (20%)', value: habitation.risk.exposure_component, note: '0.20 × 84' },
          { label: 'Vulnerability (25%)', value: habitation.risk.vulnerability_component, note: '0.25 × 73.85' },
          { label: 'Interaction (15%)', value: habitation.risk.interaction_component, note: '0.15 × (H×V)' },
          ...(habitation.risk.event_escalation_component != null
            ? [{
                label: 'Event Escalation',
                value: habitation.risk.event_escalation_component,
                note: '0.05×(287−150) + 0.40×(94−80) + 1.50×(2.3−1.5) = 13.65',
              }]
            : []),
        ].map(({ label, value, note }) => (
          <div key={label} className="rounded border border-slate-800 bg-slate-900 p-2">
            <div className="text-2xs text-slate-400">{label}</div>
            <div className="text-sm font-bold font-mono text-white">{value}</div>
            <div className="text-2xs text-slate-400 font-mono">{note}</div>
         </div>
        ))}
     </div>
      <p className="text-2xs text-slate-400 mt-2">
        Base risk = 35.2 + 16.8 + 18.46 + 9.75 = 80.21 (deterministic model). Current operational
        risk = base 80.21 + event escalation 13.65 = 93.86 ≈ 94 — escalation reflects active
        rainfall/saturation/river triggers above documented thresholds.
     </p>
</div>
  );
}

// Component: ML Explanations Panel
function MLExplanationsPanel({ explanations }: { explanations: any }) {
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 p-4">
      <div className="mb-3">
        <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">SHAP-Like Explanations</h2>
        <p className="text-xs text-slate-400">ML model feature contributions</p>
     </div>
      <div className="grid gap-4">
        <div>
          <h3 className="text-xs font-semibold mb-2">Hazard Prediction Drivers</h3>
          <div className="space-y-1">
            {explanations.hazard.slice(0, 5).map((e: any, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="w-32 text-slate-400">{e.feature}</span>
                <div className="flex-1 h-1 rounded-full bg-slate-800">
                  <div className="h-full rounded-full" style={{ width: `${e.percentage}%`, backgroundColor: '#00b4d8' }} />
               </div>
                <span className="font-mono text-white w-10 text-right">{e.percentage}%</span>
             </div>
            ))}
         </div>
       </div>
        <div>
          <h3 className="text-xs font-semibold mb-2">Vulnerability Prediction Drivers</h3>
          <div className="space-y-1">
            {explanations.vulnerability.slice(0, 5).map((e: any, i: number) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="w-32 text-slate-400">{e.feature}</span>
                <div className="flex-1 h-1 rounded-full bg-slate-800">
                  <div className="h-full rounded-full" style={{ width: `${e.percentage}%`, backgroundColor: '#33b5e5' }} />
               </div>
                <span className="font-mono text-white w-10 text-right">{e.percentage}%</span>
             </div>
            ))}
         </div>
       </div>
     </div>
   </div>
  );
}
