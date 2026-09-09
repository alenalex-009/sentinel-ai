// Sentinel AI — Habitation Investigation Screen (Redesigned)
// Emergency Operations Center Dashboard with Detailed Habitation Analysis

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Users,
  Shield,
  Activity,
  RefreshCw,
  LayoutGrid,
  MapPin,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
} from "lucide-react";
import { LoadingSpinner } from "../components/ui/LoadingSpinner";
import { EmptyState } from "../components/ui/EmptyState";
import { MapContainer } from "../components/map/MapContainer";
import { DEMO_MUNNAR_CENTRAL, DEMO_HABITATIONS } from "../data/idukki-seed";
import { useApiWithFallback } from "../hooks/useApiWithFallback";
import { api } from "../api/client";
import { RedZoneDetectionService } from "../services/redZoneDetectionService";
import type { HabitationDetail } from "../types";
import clsx from "clsx";

// Helper function to format timestamp
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

class HabitationInvestigationService {
  private static instance: HabitationInvestigationService;
  private redZoneService: RedZoneDetectionService;
  private refreshInterval: ReturnType<typeof setInterval> | null = null;

  private constructor() {
    this.redZoneService = RedZoneDetectionService.getInstance();
  }

  public static getInstance(): HabitationInvestigationService {
    if (!HabitationInvestigationService.instance) {
      HabitationInvestigationService.instance = new HabitationInvestigationService();
    }
    return HabitationInvestigationService.instance;
  }

  startMonitoring(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
    this.refreshInterval = setInterval(() => this.refreshData(), 30000);
    console.log('Habitation investigation monitoring started');
  }

  stopMonitoring(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
    }
    console.log('Habitation investigation monitoring stopped');
  }

  async refreshData(): Promise<void> {
    // Red-zone monitoring runs on its own cadence; page data refreshes are
    // driven by the component polling the backend-backed hooks.
  }

  async getRedZoneAlertsForHabitation(habitationId: string) {
    const alerts = this.redZoneService.getActiveAlerts();
    return alerts.filter(alert => alert.habitationId === habitationId);
  }
}

export function HabitationInvestigation() {
  const { id = 'munnar-central' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<string>("");
  const [redZoneAlerts, setRedZoneAlerts] = useState<any[]>([]);
  const [showHazardLayer, setShowHazardLayer] = useState(true);

  const investigationService = HabitationInvestigationService.getInstance();
  // Determine fallback: use Munnar Central detail for munnar-central, minimal for others
  const fallback = id === 'munnar-central' ? DEMO_MUNNAR_CENTRAL : buildFallbackDetail(id);

  const { data: h, loading, refetch } = useApiWithFallback<HabitationDetail>(
    () => api.getHabitationDetail(id) as Promise<HabitationDetail>,
    fallback,
    [id],
  );

  // Risk drivers + engine-derived explanations from the backend — replaces the
  // old client-side mlPredictionService whose weights diverged from the engine.
  const { data: driversData, source: driversSource, refetch: refetchDrivers } = useApiWithFallback<
    ReturnType<typeof api.getRiskDrivers> extends Promise<infer T> ? T : never
  >(
    () => api.getRiskDrivers(id) as Promise<ReturnType<typeof api.getRiskDrivers> extends Promise<infer T> ? T : never>,
    { data_status: 'DEMO', habitation_id: id, drivers: [] },
    [id],
  );

  const explanations = (driversData as { explanations?: { hazard: unknown[]; vulnerability: unknown[] } } | null)?.explanations ?? null;
  const mlPredictions = explanations; // status indicator: predictions available?

  // Initialize data on mount
  useEffect(() => {
    const loadInitialData = async () => {
      setIsMonitoring(true);
      investigationService.startMonitoring();
      setRedZoneAlerts(await investigationService.getRedZoneAlertsForHabitation(id));
      setLastRefresh(new Date().toLocaleTimeString());
    };

    loadInitialData();

    return () => {
      investigationService.stopMonitoring();
      setIsMonitoring(false);
    };
  }, [id, investigationService]);

  // Refresh data periodically — re-poll backend drivers + local red-zone alerts
  useEffect(() => {
    if (!isMonitoring || !h) return;

    const interval = setInterval(async () => {
      try {
        const [alerts] = await Promise.all([
          investigationService.getRedZoneAlertsForHabitation(id),
          refetchDrivers(),
        ]);

        setRedZoneAlerts(alerts);
        setLastRefresh(new Date().toLocaleTimeString());
      } catch (error) {
        console.error('Error refreshing investigation data:', error);
      }
    }, 45000);

    return () => clearInterval(interval);
  }, [isMonitoring, h, id, investigationService, refetchDrivers]);

  if (loading) {
    return (
      <div className={`flex h-full items-center justify-center bg-slate-950`}>
        <LoadingSpinner label="Loading habitation data..." />
      </div>
    );
  }

  if (!h) {
    return (
      <div className={`flex h-full items-center justify-center p-8 bg-slate-950`}>
        <EmptyState variant="no-data" detail={`Habitation '${id}' not found.`} onRetry={refetch} />
      </div>
    );
  }

  const selectedHabitation = DEMO_HABITATIONS.find(x => x.id === id);

  return (
    <div className="flex h-full overflow-hidden bg-slate-950 text-white">
      {/* LEFT PANEL - Investigation Controls & Metrics */}
      <aside className="w-72 flex-shrink-0 flex flex-col gap-4 border-r border-slate-800 bg-slate-900 p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-slate-950/20 border border-slate-800/30">
              <LayoutGrid className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-wide">Habitation Investigation</h1>
              <p className="text-xs text-slate-400">Detailed Analysis</p>
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
            title="Current Risk"
            value={`${h.risk.current}/100`}
            icon={<Activity className="h-4 w-4" />}
            color={h.risk.current >= 80 ? '#ff4444' : h.risk.current >= 60 ? '#ffbb33' : '#33b5e5'}
            trend={h.risk.change > 0 ? 'up' : h.risk.change < 0 ? 'down' : 'stable'}
          />
          <OverviewStatCard
            title="Population"
            value={`${h.population.toLocaleString()}`}
            icon={<Users className="h-4 w-4" />}
            color={'#33b5e5'}
            trend="stable"
          />
          <OverviewStatCard
            title="Vulnerability"
            value={`${h.vulnerability.overall}`}
            icon={<Shield className="h-4 w-4" />}
            color={h.vulnerability.overall >= 70 ? '#ff4444' : h.vulnerability.overall >= 50 ? '#ffbb33' : '#33b5e5'}
            trend="stable"
          />
          <OverviewStatCard
            title="Red Zone"
            value={redZoneAlerts.length > 0 ? 'ACTIVE' : 'MONITOR'}
            icon={<AlertTriangle className="h-4 w-4" />}
            color={redZoneAlerts.length > 0 ? '#ff4444' : '#00c853'}
            trend="stable"
          />
        </div>

        {/* Navigation */}
        <div className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">Navigation</h2>
          <div className="space-y-2">
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/')}
              icon={<ArrowLeft className="h-4 w-4" />}
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
            <ButtonVariant
              variant="outline"
              onClick={() => setShowHazardLayer(!showHazardLayer)}
              icon={<Activity className="h-4 w-4" />}
              label={showHazardLayer ? 'Hide Hazards' : 'Show Hazards'}
            />
          </div>
        </div>

        {/* System Status */}
        <div className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">System Status</h2>
          <div className="space-y-2">
            <StatusIndicator
              label="Data Sources"
              status="active"
              details="All systems nominal"
            />
            <StatusIndicator
              label="Risk Explanations"
              status={mlPredictions ? 'active' : 'warning'}
              details={mlPredictions ? (driversSource === 'api' ? 'API engine' : 'Demo fallback') : 'Calculating'}
            />
            <StatusIndicator
              label="Red Zone Alerts"
              status={redZoneAlerts.length > 0 ? 'warning' : 'active'}
              details={redZoneAlerts.length > 0
                ? `${redZoneAlerts.length} active alerts`
                : "No alerts"
              }
            />
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT - Map & Investigation Details */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header Bar */}
        <header className="flex h-16 items-center justify-between border-b border-slate-800 bg-slate-900/50 px-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-950/20">
                <MapPin className="h-4 w-4" />
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-wide">{h.name}</h1>
                <p className="text-xs text-slate-400">
                  {h.ward} · {h.taluk} · {h.district}
                </p>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <div className="flex-1 overflow-hidden">
          <div className="grid gap-4 p-4 h-full">
            {/* Map Panel - Full width on lg+ */}
            <div className="col-span-1 lg:col-span-4">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold tracking-wide">Live Situation Map</h2>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="flex items-center gap-1">
                      <MapStatusIndicator
                        source={showHazardLayer ? 'Hazards ON' : 'Base Map'}
                        status={showHazardLayer ? 'active' : 'inactive'}
                      />
                      <span className="flex items-center gap-1">
                        <MapStatusIndicator
                          source="Habitations"
                          status="active"
                        />
                      </span>
                    </span>
                  </div>
                </div>

                <MapContainer
                  habitations={selectedHabitation ? [selectedHabitation] : DEMO_HABITATIONS}
                  selectedHabitationId={id}
                  showHazardLayer={showHazardLayer}
                  className="h-96 w-full rounded-lg border border-slate-800/20"
                />
              </div>
            </div>

            {/* Investigation Details */}
            <div className="col-span-1 lg:col-span-4">
              <HabitationInvestigationDetails habitation={h} />
            </div>
          </div>
        </div>
      </main>

      {/* RIGHT PANEL - Focused Analysis & Alerts */}
      <aside className="w-72 flex-shrink-0 flex flex-col gap-4 border-l border-slate-800 bg-slate-900 p-4">
        {/* Red Zone Alerts */}
        <section>
          <div className="mb-4">
            <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">
              Red Zone Alerts
              <span className="text-xs">{redZoneAlerts.length}</span>
            </h2>
          </div>
          {redZoneAlerts.length > 0 ? (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {redZoneAlerts.map(alert => (
                <RedZoneAlertCard key={alert.id} alert={alert} />
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center py-8">
              <div className="text-center text-slate-400">
                <Activity className="h-6 w-6 text-slate-400/50 mb-2" />
                <p className="text-sm">No active alerts</p>
              </div>
            </div>
          )}
        </section>

        {/* Quick Actions */}
        <section className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">Quick Actions</h2>
          <div className="space-y-2">
            <ButtonVariant
              variant="success"
              onClick={() => navigate('/relocation')}
              icon={<MapPin className="h-4 w-4" />}
              label="Review Candidate Sites"
            />
            <ButtonVariant
              variant="warning"
              onClick={() => navigate(`/habitations/${h.id}/decision`)}
              icon={<Shield className="h-4 w-4" />}
              label="Explain This Risk"
            />
            <ButtonVariant
              variant="outline"
              onClick={() => navigate('/data')}
              icon={<RefreshCw className="h-4 w-4" />}
              label="Data Sources"
            />
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

// Component: Map Status Indicator
function MapStatusIndicator({ source, status }: { source: string; status: 'active' | 'inactive' }) {
  return (
    <div className="flex items-center gap-1 text-xs">
      <div className="w-2 h-2 rounded-full" style={{
        backgroundColor: status === 'active' ? '#00c853' : '#b0b0b0'
      }} />
      <span>{source}</span>
    </div>
  );
}

// Component: Habitation Investigation Details
function HabitationInvestigationDetails({
  habitation
}: {
  habitation: HabitationDetail;
}) {
  return (
    <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 p-4">
      <div className="mb-4">
        <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">Habitation Investigation Details</h2>
        <p className="text-xs text-slate-400">Comprehensive risk assessment and analysis</p>
      </div>

      <div className="space-y-4">
        {/* Risk Assessment */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold">Risk Assessment</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-slate-900/20 rounded border border-slate-800/20">
              <p className="text-xs text-slate-400 mb-1">Current Risk</p>
              <p className="text-xl font-bold font-mono">{habitation.risk.current}/100</p>
              <p className="text-xs text-slate-400 mt-1">
                {habitation.risk.change > 0 ? '+' : ''}{habitation.risk.change} from baseline
              </p>
            </div>
            <div className="p-3 bg-slate-900/20 rounded border border-slate-800/20">
              <p className="text-xs text-slate-400 mb-1">Baseline Risk</p>
              <p className="text-xl font-bold font-mono">{habitation.risk.baseline}/100</p>
              <p className="text-xs text-slate-400 mt-1">Historical average</p>
            </div>
          </div>
        </div>

        {/* Vulnerability Breakdown */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold">Vulnerability Breakdown</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-slate-900/20 rounded border border-slate-800/20">
              <p className="text-xs text-slate-400 mb-1">Overall</p>
              <p className="text-lg font-bold font-mono">{habitation.vulnerability.overall}</p>
              <p className="text-xs text-slate-400 mt-1">{habitation.vulnerability.level}</p>
            </div>
            <div className="p-3 bg-slate-900/20 rounded border border-slate-800/20">
              <p className="text-xs text-slate-400 mb-1">Demographic</p>
              <p className="text-lg font-bold font-mono">{habitation.vulnerability.demographic}</p>
            </div>
          </div>
        </div>

        {/* Active Hazards */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold">Active Hazards</h3>
          <div className="space-y-2">
            {habitation.hazards.map(hazard => (
              <div key={hazard.type} className="p-3 bg-slate-900/20 rounded border border-slate-800/20">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-semibold">{hazard.type}</p>
                  <p className="text-xs font-mono">{hazard.intensity}</p>
                </div>
                <p className="text-xs text-slate-400">{hazard.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* System Recommendation */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold">System Recommendation</h3>
          <div className="p-3 bg-slate-900/20 rounded border border-slate-800/20">
            <p className="text-xs text-slate-400 mb-2">RECOMMENDATION</p>
            <p className="text-sm">{habitation.system_recommendation}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Component: Red Zone Alert Card
function RedZoneAlertCard({ alert }: { alert: any }) {
  return (
    <div
      className={clsx(
        "flex items-center justify-between p-4 rounded border border-slate-800/20 cursor-pointer hover:bg-slate-900/20 hover:border-slate-800",
        "transition-all"
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-3 h-3 flex items-center justify-center">
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </div>
          <div>
            <p className="text-xs font-medium">{alert.habitationName}</p>
            <p className="text-xs text-slate-400">{alert.redZoneStatus}</p>
          </div>
        </div>
        <div className="space-y-1 text-xs">
          <div className="flex items-center gap-1">
            <span className="font-mono">{alert.riskScore}</span>
            <span className="text-slate-400">risk score</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-slate-400 capitalize">
              {alert.confidence.toFixed(2)}
            </span>
            <span className="text-slate-400">confidence</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-slate-400">
              {formatTimeAgo(alert.detectedAt)}
            </span>
            <span className="text-slate-400">ago</span>
          </div>
        </div>
        <p className="text-xs text-slate-400 line-clamp-2 mt-2">
          {alert.triggers.slice(0, 3).join(', ')}{alert.triggers.length > 3 ? '...' : ''}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{
          backgroundColor: '#ff4444'
        }} />
        <span className="text-xs text-slate-400">
          ALERT
        </span>
      </div>
    </div>
  );
}

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

// Canonical derived values for non-Munnar demo habitations
const FALLBACK_RPI: Record<string, number> = {
  'rajakkad': 78, 'kanthalloor': 61, 'marayoor': 52, 'adimali': 38,
};
const FALLBACK_VULNERABILITY: Record<string, number> = {
  'rajakkad': 68, 'kanthalloor': 59, 'marayoor': 51, 'adimali': 42,
};
const FALLBACK_HISTORICAL: Record<string, number> = {
  'rajakkad': 71, 'kanthalloor': 55, 'marayoor': 48, 'adimali': 31,
};
const FALLBACK_URGENCY: Record<string, number> = {
  'rajakkad': 76, 'kanthalloor': 63, 'marayoor': 54, 'adimali': 35,
};
const FALLBACK_RISK_COMPONENTS: Record<string, [number, number, number, number]> = {
  'rajakkad': [31.2, 14.4, 16.8, 8.1],
  'kanthalloor': [27.4, 13.2, 15.6, 7.2],
  'marayoor': [22.8, 11.6, 13.4, 6.1],
  'adimali': [18.2, 9.8, 11.2, 5.1],
};
const FALLBACK_RECOMMENDATION: Record<string, string> = {
  'rajakkad': 'Prioritize Rajakkad for field verification and relocation-assessment screening.',
  'kanthalloor': 'Review access-route alternatives for Kanthalloor and monitor flood hazard.',
  'marayoor': 'Monitor Marayoor flood risk; include in near-term screening.',
  'adimali': 'No immediate relocation indication for Adimali; continue routine monitoring.',
};

function fallbackVulnLevel(score: number): 'VERY HIGH' | 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY LOW' {
  if (score >= 80) return 'VERY HIGH';
  if (score >= 60) return 'HIGH';
  if (score >= 40) return 'MEDIUM';
  if (score >= 20) return 'LOW';
  return 'VERY LOW';
}

function buildFallbackDetail(id: string): HabitationDetail {
  const listItem = DEMO_HABITATIONS.find(h => h.id === id);
  if (!listItem) return DEMO_MUNNAR_CENTRAL;
  const population = listItem.population;
  const households = Math.round(population / 4);
  const vuln = FALLBACK_VULNERABILITY[id];
  const level = fallbackVulnLevel(vuln);
  const baseline = listItem.risk_score - listItem.risk_change;
  const comps = FALLBACK_RISK_COMPONENTS[id];
  const hazardLabel = listItem.primary_hazard.replace('_', ' ').toLowerCase();
  const hazardTitle = hazardLabel.charAt(0).toUpperCase() + hazardLabel.slice(1);
  const sourceText = listItem.primary_hazard === 'LANDSLIDE'
    ? 'KSDMA Landslide Susceptibility Map + IMD Rainfall (DEMO)'
    : 'Bhuvan/ISRO Kerala 2019 flood-event overlay + CWC River Level (DEMO)';
  const riskComp = Math.round(0.35 * listItem.risk_score * 100) / 100;
  const vulnComp = Math.round(0.2 * vuln * 100) / 100;
  const histComp = Math.round(0.15 * FALLBACK_HISTORICAL[id] * 100) / 100;
  const urgComp = Math.round(0.15 * FALLBACK_URGENCY[id] * 100) / 100;
  const popComp = Math.round((FALLBACK_RPI[id] - riskComp - vulnComp - histComp - urgComp) * 100) / 100;

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
  };
}
