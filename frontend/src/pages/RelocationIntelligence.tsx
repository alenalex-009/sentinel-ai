// Sentinel AI — Relocation Intelligence Screen (Redesigned, Phase 5C)
// Map-first planning workspace: candidate sites, capacity, allocation, and
// real road-network routing with an engine selector (OSRM fast / GraphHopper
// balanced / Valhalla advanced) — every route rendered on the basemap with
// per-engine provenance. Falls back to the labelled demo seed offline.

import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Users,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  Activity,
  TrendingDown,
  TrendingUp,
  MapPin,
  BarChart2,
  Zap,
  Route,
  RefreshCw,
  Gauge,
  Brain,
  Rocket,
} from "lucide-react";
import { MapContainer } from "../components/map/MapContainer";
import { DataTypeBadge } from "../components/ui/DataTypeBadge";
import { useApiWithFallback } from "../hooks/useApiWithFallback";
import {
  DEMO_MUNNAR_CENTRAL,
  DEMO_RELOCATION_DEMAND,
  DEMO_CANDIDATE_SITES,
  DEMO_CAPACITY_ASSESSMENTS,
  DEMO_OPTIMIZATION_RESULT,
  DEMO_HABITATIONS,
} from "../data/idukki-seed";
import { RedZoneDetectionService } from "../services/redZoneDetectionService";
import { api } from "../api/client";
import type {
  CandidateSite,
  CapacityAssessment,
  RoutingEngine,
  RoutingEnginesStatus,
  EngineRouteResult,
  SafeZonesResponse,
  DistrictRelocationDemand,
  RelocationPlan,
  RelocationPlanStatus,
  SafeZoneCandidate,
  DataStatus,
} from "../types";
import clsx from "clsx";

type Tab = 'sites' | 'capacity' | 'allocation';

const TAB_LABELS: Record<Tab, string> = {
  sites: 'Candidate Sites',
  capacity: 'Capacity',
  allocation: 'Allocation',
};

// Engine selector metadata — tier names drive ordering and badges.
const ENGINES: Array<{ key: RoutingEngine; label: string; tier: string }> = [
  { key: 'osrm', label: 'OSRM', tier: 'FAST' },
  { key: 'graphhopper', label: 'GraphHopper', tier: 'BALANCED' },
  { key: 'valhalla', label: 'Valhalla', tier: 'ADVANCED' },
];

export function RelocationIntelligence() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<Tab>('sites');
  const [selectedSiteId, setSelectedSiteId] = useState<string>('site-a');
  const [alertCount, setAlertCount] = useState(0);

  // ── Multi-engine routing state ──────────────────────────────────────────
  const [engine, setEngine] = useState<RoutingEngine>('osrm');
  const [enginesStatus, setEnginesStatus] = useState<RoutingEnginesStatus | null>(null);
  const [routeResult, setRouteResult] = useState<EngineRouteResult | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);

  // ── Live Slice 5 data (district demand + safe-zone candidates + plan) ──
  const { data: apiDemand, source: demandSource } =
    useApiWithFallback<DistrictRelocationDemand>(
      () => api.getDistrictRelocationDemand('idukki') as Promise<DistrictRelocationDemand>,
      { data_status: 'DEMO', total_demand: DEMO_RELOCATION_DEMAND.relocation_demand, habitations: [] },
    );
  const { data: apiSafeZones, source: safeZonesSource } =
    useApiWithFallback<SafeZonesResponse>(
      () => api.getSafeZones('idukki') as Promise<SafeZonesResponse>,
      { type: 'FeatureCollection', features: [], status_counts: { green: 0, yellow: 0, red: 0 } },
    );

  const safeZoneCandidates = (apiSafeZones?.features ?? [])
    .map(f => f.properties as SafeZoneCandidate & { name?: string | null })
    .filter(p => !!p?.id && p.constraint_pass !== false);

  // Live candidate sites derived from Slice 4 discovered grid points.
  const liveSites: CandidateSite[] = safeZoneCandidates.map(c => ({
    id: c.id,
    name: c.name || c.id,
    distance_km: 0,
    suitability_score: c.suitability_score ?? 0,
    safe_capacity: c.estimated_capacity ?? 0,
    bottleneck_dimension: '',
    safety_score: c.safety_score ?? 0,
    infrastructure_score: 0,
    accessibility_score: 0,
    water_score: 0,
    healthcare_score: 0,
    education_score: 0,
    latitude: c.lat,
    longitude: c.lon,
    hard_constraints_passed: c.constraint_pass,
    data_type: 'DERIVED',
    data_status: c.data_status,
    notes: c.constraint_pass ? 'Discovered safe-zone candidate (Slice 4)' : 'Excluded candidate',
  }));

  const candidateSites = liveSites.length > 0 ? liveSites : DEMO_CANDIDATE_SITES;
  const demandTotal = apiDemand?.total_demand ?? DEMO_RELOCATION_DEMAND.relocation_demand;

  // Live relocation plan lifecycle state (Slice 5).
  const [plan, setPlan] = useState<RelocationPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planNotify, setPlanNotify] = useState<string | null>(null);

  const loadPlan = useCallback(async (planId: number) => {
    setPlanLoading(true);
    try {
      const p = await api.getRelocationPlan(planId) as RelocationPlan;
      setPlan(p);
      setPlanError(null);
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : 'plan fetch failed');
      setPlan(null);
    } finally {
      setPlanLoading(false);
    }
  }, []);

  const createPlan = useCallback(async () => {
    setPlanLoading(true);
    setPlanError(null);
    setPlanNotify(null);
    try {
      const p = await api.createRelocationPlan({
        district_id: 'idukki',
        name: `Idukki relocation plan — ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`,
        created_by: 'authority-web',
      }) as RelocationPlan;
      setPlan(p);
      setPlanNotify(`Plan #${p.plan_id} created (${p.data_status})`);
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : 'plan creation failed');
    } finally {
      setPlanLoading(false);
    }
  }, []);

  const transitionPlan = useCallback(async (newStatus: RelocationPlanStatus) => {
    if (!plan?.plan_id) return;
    setPlanLoading(true);
    setPlanError(null);
    setPlanNotify(null);
    try {
      const next = await api.updateRelocationPlanStatus(plan.plan_id, newStatus, 'authority-web');
      if (next?.data_status === 'ERROR') {
        setPlanError(next.reason ?? 'invalid transition');
      } else {
        await loadPlan(plan.plan_id);
        setPlanNotify(`Plan → ${newStatus}`);
      }
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : 'status update failed');
    } finally {
      setPlanLoading(false);
    }
  }, [plan, loadPlan]);

  const h = DEMO_MUNNAR_CENTRAL;
  const selectedSite: CandidateSite =
    candidateSites.find(s => s.id === selectedSiteId) ?? candidateSites[0];
  const selectedCap: CapacityAssessment =
    DEMO_CAPACITY_ASSESSMENTS[selectedSite.id] ?? {
      site_id: selectedSite.id,
      site_name: selectedSite.name,
      c_safe: selectedSite.safe_capacity,
      bottleneck: 'capacity unavailable',
      dimensions: [],
      required_population: demandTotal,
      surplus_deficit: 0,
      can_absorb_alone: false,
      data_type: 'DERIVED',
      data_status: selectedSite.data_status,
    };

  const totalCapacity = candidateSites.reduce((s, site) => s + site.safe_capacity, 0);
  const capacityGap = totalCapacity - demandTotal;

  // Probe per-engine availability once (drives the selector's status dots).
  const loadEngines = useCallback(async () => {
    try {
      const st = await api.getRoutingEngines('kerala');
      setEnginesStatus(st as RoutingEnginesStatus);
    } catch (err) {
      console.warn('[Sentinel AI] engines status unavailable:', err);
      setEnginesStatus(null);
    }
  }, []);

  // Fetch a real road route for the selected site via the selected engine.
  const loadRoute = useCallback(async (engineKey: RoutingEngine, siteId: string) => {
    setRouteLoading(true);
    try {
      const r = await api.getRoute('munnar-central', siteId, engineKey);
      setRouteResult(r as EngineRouteResult);
    } catch (err) {
      // 404 (unknown pair) → surface as UNAVAILABLE with no route.
      setRouteResult(null);
      console.warn('[Sentinel AI] route fetch failed:', err);
    } finally {
      setRouteLoading(false);
    }
  }, []);

  useEffect(() => {
    loadEngines();
    const redZoneService = RedZoneDetectionService.getInstance();
    setAlertCount(redZoneService.getActiveAlerts().length);
    const interval = setInterval(() => {
      setAlertCount(redZoneService.getActiveAlerts().length);
    }, 30000);
    return () => clearInterval(interval);
  }, [loadEngines]);

  // Re-route when the selected site or engine changes. Only seeded demo sites
  // have OSM paths — discovered grid sites have no route, so skip the fetch.
  const routeableSiteIds = useMemo(() => DEMO_CANDIDATE_SITES.map(s => s.id), []);
  useEffect(() => {
    if (!routeableSiteIds.includes(selectedSite.id)) return;
    loadRoute(engine, selectedSite.id);
  }, [engine, selectedSite.id, loadRoute, routeableSiteIds]);

  // Derive the map overlay + legend label from the current route result.
  // engineLabel is guarded: GraphHopper-era payloads can lack `engine`.
  const engineLabel = routeResult?.engine ?? 'graphhopper';
  const routeFeature = routeResult?.status === 'OK' ? routeResult.route_geojson : null;
  const routeLabel = routeResult?.status === 'OK' && routeResult.route
    ? `${engineLabel.toUpperCase()} · ${routeResult.route.distance_km} km · ${routeResult.route.duration_min} min`
    : null;
  const engineOnline = enginesStatus?.engines?.[engine]?.ok ?? null;

  return (
    <div className="flex h-full overflow-hidden bg-slate-950 text-white">
      {/* LEFT PANEL — demand, capacity, engine selector */}
      <aside className="w-72 flex-shrink-0 flex flex-col gap-4 overflow-y-auto border-r border-slate-800 bg-slate-900 p-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-slate-950/20 border border-slate-800/30">
            <MapPin className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-wide">Relocation Intelligence</h1>
            <p className="text-xs text-slate-400">Sites · Capacity · Routing</p>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex gap-1">
              <DataTypeBadge type={(apiDemand?.data_status as string) === 'DERIVED' ? 'DERIVED' : 'SIMULATED'} />
              <span className="text-2xs text-slate-500">{demandSource === 'api' ? 'live' : 'demo'}</span>
            </div>
          </div>
          <OverviewStatCard
            title="Relocation Demand"
            value={demandTotal.toLocaleString()}
            icon={<Users className="h-4 w-4" />}
            trend="stable"
          />
          <OverviewStatCard
            title="Total Capacity"
            value={totalCapacity.toLocaleString()}
            icon={<MapPin className="h-4 w-4" />}
            trend="stable"
          />
          <OverviewStatCard
            title="Capacity Gap"
            value={capacityGap >= 0 ? `+${capacityGap.toLocaleString()}` : capacityGap.toLocaleString()}
            icon={<AlertTriangle className="h-4 w-4" />}
            trend={capacityGap >= 0 ? 'stable' : 'up'}
          />
          <OverviewStatCard
            title="Sites Available"
            value={candidateSites.length.toString()}
            icon={<BarChart2 className="h-4 w-4" />}
            trend="stable"
          />
        </div>

        {/* ── Routing engine selector ──────────────────────────────────── */}
        <div className="mt-2 pt-3 border-t border-slate-800/20">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold tracking-wide uppercase">
              Routing Engine
            </h2>
            <button
              onClick={loadEngines}
              title="Re-probe engine availability"
              className="text-slate-500 hover:text-cyan-400 transition-colors"
            >
              <RefreshCw className="h-3 w-3" />
            </button>
          </div>
          <div className="space-y-1.5" role="radiogroup" aria-label="Routing engine">
            {ENGINES.map(e => {
              const st = enginesStatus?.engines?.[e.key];
              const online = st?.ok ?? null;
              return (
                <button
                  key={e.key}
                  role="radio"
                  aria-checked={engine === e.key}
                  onClick={() => setEngine(e.key)}
                  className={clsx(
                    'w-full flex items-center justify-between rounded border px-2.5 py-2 text-left transition-colors',
                    engine === e.key
                      ? 'border-cyan-500/50 bg-cyan-500/10'
                      : 'border-slate-800 bg-slate-900 hover:border-slate-700'
                  )}
                >
                  <span className="flex items-center gap-2">
                    <span
                      className={clsx(
                        'h-2 w-2 rounded-full',
                        online === true && 'bg-green-500',
                        online === false && 'bg-red-500',
                        online === null && 'bg-slate-600',
                      )}
                      title={st?.detail ?? 'status unknown'}
                    />
                    <span className={clsx(
                      'text-xs font-semibold',
                      engine === e.key ? 'text-cyan-300' : 'text-slate-300'
                    )}>
                      {e.label}
                    </span>
                  </span>
                  <span className={clsx(
                    'text-2xs font-mono uppercase tracking-wider',
                    e.key === 'osrm' && 'text-green-500/80',
                    e.key === 'graphhopper' && 'text-blue-400/80',
                    e.key === 'valhalla' && 'text-violet-400/80',
                  )}>
                    {e.tier}
                  </span>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-2xs leading-relaxed text-slate-500">
            All engines route on OpenStreetMap data. OSRM pre-bakes its graph
            (fastest queries); Valhalla costs edges at request time (runtime
            flexibility, isochrones-capable); GraphHopper is the pre-existing
            integration.
          </p>
        </div>

        {/* System Status */}
        <div className="mt-2 pt-3 border-t border-slate-800/20">
          <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">System Status</h2>
          <div className="space-y-2">
            <StatusIndicator
              label="Optimization Engine"
              status="active"
              details="CP-SAT solver"
            />
            <StatusIndicator
              label="Site Database"
              status={safeZonesSource === 'api' ? 'active' : 'warning'}
              details={safeZonesSource === 'api'
                ? `${candidateSites.length} candidates (live)`
                : `${candidateSites.length} sites loaded (demo)`}
            />
            <StatusIndicator
              label="Routing Engine"
              status={engineOnline === true ? 'active' : engineOnline === false ? 'error' : 'warning'}
              details={
                engineOnline === true ? `${engine.toUpperCase()} online`
                : engineOnline === false ? `${engine.toUpperCase()} unreachable`
                : 'probing…'
              }
            />
            <StatusIndicator
              label="Red Zone Alerts"
              status={alertCount > 0 ? 'warning' : 'active'}
              details={alertCount > 0 ? `${alertCount} active alerts` : 'No alerts'}
            />
          </div>
        </div>

        {/* Navigation */}
        <div className="pt-3 border-t border-slate-800/20">
          <h2 className="text-xs font-semibold tracking-wide uppercase mb-2">Navigation</h2>
          <div className="space-y-2">
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/habitations/munnar-central')}
              icon={<MapPin className="h-4 w-4" />}
              label="View Source Habitation"
            />
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/risk')}
              icon={<Activity className="h-4 w-4" />}
              label="Risk Intelligence"
            />
            <ButtonVariant
              variant="secondary"
              onClick={() => navigate('/scenarios')}
              icon={<Zap className="h-4 w-4" />}
              label="Run Scenario"
            />
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT — map + tabs */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="flex h-16 flex-shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900/50 px-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-950/20">
              <Route className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-wide">Evacuation Route Planning</h1>
              <p className="text-xs text-slate-400">
                {h.name} → {selectedSite.name.split(' — ')[1] || selectedSite.name}
              </p>
            </div>
          </div>
          {/* Route provenance chip */}
          <div className="flex items-center gap-2 text-xs">
            {routeLoading ? (
              <span className="flex items-center gap-1.5 rounded border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-slate-400">
                <RefreshCw className="h-3 w-3 animate-spin" /> routing…
              </span>
            ) : routeResult?.status === 'OK' && routeResult.route ? (
              <span
                className="flex items-center gap-2 rounded border border-cyan-500/40 bg-cyan-500/5 px-2.5 py-1.5"
                title={routeResult.route.method}
              >
                <span className="font-mono font-bold text-cyan-300">
                  {routeResult.route.distance_km} km
                </span>
                <span className="text-slate-500">/</span>
                <span className="font-mono text-slate-300">
                  {routeResult.route.duration_min} min
                </span>
                <span className="text-2xs uppercase tracking-wider text-slate-500">
                  via {engineLabel}
                </span>
              </span>
            ) : (
              <span
                className="flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/5 px-2.5 py-1.5 text-amber-400"
                title={routeResult?.reason}
              >
                <AlertTriangle className="h-3.5 w-3.5" />
                <span className="text-2xs uppercase tracking-wide">
                  {engine} unavailable
                </span>
              </span>
            )}
          </div>
        </header>

        {/* Map — the centerpiece */}
        <div className="relative flex-1 min-h-0">
          <MapContainer
            habitations={DEMO_HABITATIONS}
            selectedHabitationId={null}
            showHazardLayer={false}
            routeFeature={routeFeature}
            routeLabel={routeLabel}
            clickPopup={false}
            safeZonesGeoJSON={apiSafeZones?.features?.length ? apiSafeZones : null}
            showSafeZonesLayer={safeZonesSource === 'api'}
            className="h-full w-full"
          />
        </div>

        {/* Tabs */}
        <div className="flex flex-shrink-0 border-b border-slate-800/20 bg-slate-900/30 px-4">
          {(Object.keys(TAB_LABELS) as Tab[]).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={clsx(
                'px-4 py-2 text-xs font-semibold transition-colors',
                activeTab === tab
                  ? 'border-b-2 border-cyan-500 text-cyan-400'
                  : 'border-b-2 border-transparent text-slate-400 hover:text-white'
              )}
            >
              {TAB_LABELS[tab]}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="h-64 flex-shrink-0 overflow-y-auto">
          <div className="p-4">
            {activeTab === 'sites' && (
              <SitesTab
                sites={candidateSites}
                capacities={DEMO_CAPACITY_ASSESSMENTS}
                selectedSiteId={selectedSite.id}
                onSelectSite={setSelectedSiteId}
                activeDistance={routeResult?.status === 'OK' ? routeResult.route?.distance_km ?? null : null}
                activeDuration={routeResult?.status === 'OK' ? routeResult.route?.duration_min ?? null : null}
                engineLabel={routeResult?.status === 'OK' ? engineLabel : null}
              />
            )}
            {activeTab === 'capacity' && <CapacityTab cap={selectedCap} />}
            {activeTab === 'allocation' && (
              <AllocationTab
                plan={plan}
                planLoading={planLoading}
                planError={planError}
                planNotify={planNotify}
                onCreatePlan={createPlan}
                onTransition={transitionPlan}
              />
            )}
          </div>
        </div>
      </main>

      {/* RIGHT PANEL — selected site + actions (wide screens only) */}
      <aside className="hidden xl:block w-72 flex-shrink-0 overflow-y-auto border-l border-slate-800 bg-slate-900 p-4">
        {/* Route detail card */}
        <section>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide">Route Detail</h2>
          <div className="rounded-lg border border-slate-800/20 bg-slate-900/30 p-3">
            {routeResult?.status === 'OK' && routeResult.route ? (
              <>
                <div className="mb-2 flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-cyan-300">
                    {engineLabel === 'osrm' && <Rocket className="h-3.5 w-3.5" />}
                    {engineLabel === 'valhalla' && <Brain className="h-3.5 w-3.5" />}
                    {engineLabel === 'graphhopper' && <Gauge className="h-3.5 w-3.5" />}
                    {engineLabel.toUpperCase()}
                  </span>
                  <span className="rounded bg-slate-950/60 px-1.5 py-0.5 text-2xs uppercase tracking-wider text-slate-500">
                    {routeResult.engine_tier ?? 'balanced'}
                  </span>
                </div>
                <div className="mb-2 grid grid-cols-2 gap-2">
                  <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
                    <div className="text-2xs text-slate-500">Road distance</div>
                    <div className="text-lg font-bold font-mono text-white">
                      {routeResult.route.distance_km} <span className="text-2xs text-slate-400">km</span>
                    </div>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
                    <div className="text-2xs text-slate-500">Travel time</div>
                    <div className="text-lg font-bold font-mono text-white">
                      {routeResult.route.duration_min} <span className="text-2xs text-slate-400">min</span>
                    </div>
                  </div>
                </div>
                <p className="text-2xs leading-relaxed text-slate-500">
                  {routeResult.route.method}. Cache hit:{' '}
                  {routeResult.route.cache ? 'yes' : 'no'} ·{' '}
                  {routeResult.route.points_count} geometry points.
                </p>
              </>
            ) : routeResult ? (
              <>
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" /> {engineLabel.toUpperCase()} unavailable
                </div>
                <p className="text-2xs leading-relaxed text-slate-400">
                  {routeResult.reason}
                </p>
                <p className="mt-2 text-2xs leading-relaxed text-slate-500">
                  No road distance is shown — a straight-line estimate is never
                  relabelled as a road route. Start the engine (docker compose
                  up osm-convert osrm-prep osrm-kerala valhalla-kerala) or pick
                  another engine.
                </p>
              </>
            ) : (
              <p className="text-2xs text-slate-500">Select a site to route…</p>
            )}
          </div>
        </section>

        {/* Selected Site Details */}
        <section className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide">Selected Site</h2>
          <div className="rounded-lg border border-slate-800/20 bg-slate-900/30 p-4">
            <div className="mb-3">
              <p className="mb-1 text-xs text-slate-400">{selectedSite.name.split(' — ')[0]}</p>
              <p className="text-sm font-bold text-white">
                {selectedSite.name.split(' — ')[1] || selectedSite.name}
              </p>
            </div>
            <div className="mb-3 grid grid-cols-2 gap-2">
              <div>
                <p className="text-2xs text-slate-400">Suitability</p>
                <p className="text-sm font-bold font-mono text-white">{selectedSite.suitability_score}</p>
              </div>
              <div>
                <p className="text-2xs text-slate-400">Capacity</p>
                <p className="text-sm font-bold font-mono text-white">{selectedCap.c_safe.toLocaleString()}</p>
              </div>
            </div>
            <p className="text-2xs leading-relaxed text-slate-400">{selectedSite.notes}</p>
          </div>
        </section>

        {/* Quick Actions */}
        <section className="mt-4 pt-3 border-t border-slate-800/20">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide">Quick Actions</h2>
          <div className="space-y-2">
            <ButtonVariant
              variant="success"
              onClick={() => navigate('/scenarios')}
              icon={<Zap className="h-4 w-4" />}
              label="Run Scenario"
            />
            <ButtonVariant
              variant="warning"
              onClick={() => navigate('/habitations/munnar-central/decision')}
              icon={<Activity className="h-4 w-4" />}
              label="Explain Decision"
            />
            <ButtonVariant
              variant="outline"
              onClick={() => navigate('/data')}
              icon={<Info className="h-4 w-4" />}
              label="View Data Sources"
            />
          </div>
        </section>
      </aside>
    </div>
  );
}

// Component: Overview Stat Card
function OverviewStatCard({ title, value, icon, trend }: { title: string; value: string; icon: React.ReactNode; color?: string; trend: 'up' | 'down' | 'stable' }) {
  const { icon: trendIcon, color: trendColor } = getTrendIndicator(trend);
  return (
    <div className="flex items-center justify-between p-3 bg-slate-900/30 rounded-lg border border-slate-800/20">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 flex items-center justify-center rounded-lg bg-slate-950/20">{icon}</div>
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

// Helper: trend icon + color
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

// Component: Button Variant
function ButtonVariant({ variant, onClick, icon, label, disabled = false }: { variant: 'primary' | 'secondary' | 'success' | 'warning' | 'outline'; onClick: () => void; icon: React.ReactNode; label: string; disabled?: boolean }) {
  const variants: Record<string, { bg: string; text: string; hover: string }> = {
    primary: { bg: '#00b4d8', text: '#0a0a0a', hover: '#00b4d8' },
    secondary: { bg: '#1a1a1a', text: '#ffffff', hover: '#2a2a2a' },
    success: { bg: '#00c853', text: '#0a0a0a', hover: '#00c853' },
    warning: { bg: '#ffbb33', text: '#0a0a0a', hover: '#ffbb33' },
    outline: { bg: 'transparent', text: '#ffffff', hover: '#2a2a2a' }
  };
  const variantStyle = variants[variant] || variants.outline;
  return (
    <button onClick={onClick} disabled={disabled} style={{ backgroundColor: variantStyle.bg }}
      className={clsx(
        'flex w-full items-center justify-start gap-3 px-3 py-2 text-left text-sm font-medium transition-all rounded-md text-white hover:opacity-90',
        disabled && 'opacity-40 hover:opacity-40 cursor-not-allowed'
      )}>
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

// Tab: Sites — with live road distance from the selected engine
function SitesTab({
  sites,
  capacities,
  selectedSiteId,
  onSelectSite,
  activeDistance,
  activeDuration,
  engineLabel,
}: {
  sites: CandidateSite[];
  capacities: Record<string, CapacityAssessment>;
  selectedSiteId: string;
  onSelectSite: (id: string) => void;
  activeDistance: number | null;
  activeDuration: number | null;
  engineLabel: string | null;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold tracking-wide">Candidate Sites</h2>
        <p className="text-2xs text-slate-500">
          {engineLabel && activeDistance !== null
            ? `Road figures: ${engineLabel.toUpperCase()} (real OSM route)`
            : 'Distances: DEMO/ESTIMATED seed values (engine unavailable)'}
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {sites.map(site => {
          const cap = capacities[site.id];
          const selected = site.id === selectedSiteId;
          const isActive = selected && activeDistance !== null;
          const cSafe = cap?.c_safe ?? site.safe_capacity;
          const bottleneck = cap?.bottleneck ?? 'capacity unassessed';
          const canAbsorb = cap?.can_absorb_alone ?? false;
          return (
            <button
              key={site.id}
              onClick={() => onSelectSite(site.id)}
              className={clsx(
                'w-full rounded-lg border p-3 text-left transition-colors',
                selected
                  ? 'border-cyan-500/60 bg-cyan-500/10'
                  : 'border-slate-800 bg-slate-900/30 hover:border-slate-700'
              )}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <div className="text-sm font-semibold text-white">{site.name}</div>
                  <div className="mt-0.5 text-2xs text-slate-400">
                    {isActive ? (
                      <span className="text-cyan-300">
                        ⤳ {activeDistance} km road · {activeDuration} min ({engineLabel?.toUpperCase()})
                      </span>
                    ) : (
                      <span>Est. {site.distance_km} km{selected ? ' · route unavailable' : ''}</span>
                    )}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="text-lg font-bold font-mono text-cyan-400">{site.suitability_score}</span>
                  <DataTypeBadge type={site.data_type} />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <div className="text-2xs text-slate-400">C_safe</div>
                  <div className="text-sm font-bold font-mono text-white">{cSafe.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-2xs text-slate-400">Bottleneck</div>
                  <div className="text-xs font-semibold uppercase text-amber-500">{bottleneck}</div>
                </div>
                <div>
                  {canAbsorb ? (
                    <span className="flex items-center gap-1 text-2xs text-green-500"><CheckCircle className="h-3 w-3" /> Can absorb</span>
                  ) : (
                    <span className="flex items-center gap-1 text-2xs text-amber-500"><XCircle className="h-3 w-3" /> Multi-site</span>
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// Tab: Capacity
function CapacityTab({ cap }: { cap: CapacityAssessment }) {
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-bold tracking-wide">Capacity Assessment</h2>
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 p-3 text-center">
          <div className="text-2xs text-slate-400">C_safe</div>
          <div className="text-xl font-bold font-mono text-cyan-400">{cap.c_safe.toLocaleString()}</div>
          <div className="text-2xs text-slate-400">persons</div>
        </div>
        <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 p-3 text-center">
          <div className="text-2xs text-slate-400">Demand</div>
          <div className="text-xl font-bold font-mono text-white">{cap.required_population.toLocaleString()}</div>
          <div className="text-2xs text-slate-400">persons</div>
        </div>
        <div className={clsx('rounded-lg border p-3 text-center',
          cap.surplus_deficit >= 0
            ? 'border-green-500/30 bg-green-500/10'
            : 'border-red-500/30 bg-red-500/10'
        )}>
          <div className="text-2xs text-slate-400">Gap/Surplus</div>
          <div className={clsx('text-xl font-bold font-mono', cap.surplus_deficit >= 0 ? 'text-green-500' : 'text-red-500')}>
            {cap.surplus_deficit >= 0 ? '+' : ''}{cap.surplus_deficit.toLocaleString()}
          </div>
        </div>
      </div>
      <div className="bg-slate-900/30 rounded-lg border border-amber-500/30 p-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <span className="text-xs text-amber-500">
            Binding constraint: <strong className="uppercase">{cap.bottleneck}</strong>
          </span>
        </div>
      </div>
      <div className="space-y-2">
        {cap.dimensions.map(d => (
          <div key={d.name} className={clsx('rounded border p-3',
            d.name === cap.bottleneck
              ? 'border-amber-500/30 bg-amber-500/10'
              : 'border-slate-800 bg-slate-900/30'
          )}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className={clsx('text-xs font-semibold uppercase',
                  d.name === cap.bottleneck ? 'text-amber-500' : 'text-white'
                )}>
                  {d.name}{d.name === cap.bottleneck && ' ← bottleneck'}
                </span>
                <DataTypeBadge type={d.data_type} />
              </div>
              <span className="text-sm font-mono font-bold text-white">{d.capacity.toLocaleString()}</span>
            </div>
            <p className="text-2xs text-slate-400">{d.notes}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// Tab: Allocation — live relocation plan lifecycle + allocation table.
// Falls back to the labeled demo optimization seed when the API is down.
function AllocationTab({
  plan,
  planLoading,
  planError,
  planNotify,
  onCreatePlan,
  onTransition,
}: {
  plan: RelocationPlan | null;
  planLoading: boolean;
  planError: string | null;
  planNotify: string | null;
  onCreatePlan: () => void;
  onTransition: (s: RelocationPlanStatus) => void;
}) {
  // Fallback is the labeled demo optimization result (never relabeled).
  const demoTotals = DEMO_OPTIMIZATION_RESULT;
  const totalDemand = plan ? plan.total_demand : demoTotals.total_demand;
  const totalAllocated = plan ? plan.total_allocated : demoTotals.total_allocated;
  const status = plan?.status ?? (demoTotals.status === 'FEASIBLE' ? 'draft' : undefined);
  const allocations: Array<{
    site_id: string;
    site_name?: string;
    allocated_population: number;
    distance_km: number;
    utilization_pct: number;
    surplus_after: number;
  }> = plan?.assignments?.length
    ? plan.assignments
        .filter(a => a.site_id)
        .map(a => ({
          site_id: a.site_id,
          allocated_population: a.allocated_population,
          distance_km: a.distance_km,
          utilization_pct: a.utilization_pct,
          surplus_after: a.surplus_after,
        }))
    : demoTotals.allocations.map(a => ({
        site_id: a.site_id,
        site_name: a.site_name,
        allocated_population: a.allocated_population,
        distance_km: a.distance_km,
        utilization_pct: a.utilization_pct,
        surplus_after: a.surplus_after,
      }));
  const feasible = plan ? plan.optimizer_status === 'FEASIBLE' || plan.status !== 'cancelled' : demoTotals.status === 'FEASIBLE';
  const dataStatus = ((plan?.data_status as string) ?? (plan ? 'LIVE' : 'DEMO')) as DataStatus;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold tracking-wide">Relocation Plan & Allocation</h2>
        <DataTypeBadge type={plan ? ((plan.data_status as string) === 'DERIVED' ? 'DERIVED' : 'RECOMMENDATION') : 'SIMULATED'} />
      </div>

      {planNotify && (
        <div className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-300">
          {planNotify}
        </div>
      )}
      {planError && (
        <div className="flex items-center gap-2 rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          <AlertTriangle className="h-3.5 w-3.5" /> {planError}
        </div>
      )}

      {/* Plan creation / lifecycle actions */}
      {!plan ? (
        <div className="rounded-lg border border-slate-800/20 bg-slate-900/30 p-3">
          <p className="mb-2 text-2xs text-slate-400">
            No live plan loaded. Create one from live demand (Slice 3 risk) and
            Slice 4 safe-zone candidates — the OR-Tools optimizer allocates each
            habitation's demand to candidate sites.
          </p>
          <ButtonVariant
            variant="success"
            disabled={planLoading}
            onClick={onCreatePlan}
            icon={<Rocket className="h-4 w-4" />}
            label={planLoading ? 'Creating plan…' : 'Create Relocation Plan'}
          />
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className={clsx(
              'rounded border px-2.5 py-1 text-2xs font-mono uppercase tracking-wider',
              status === 'completed' && 'border-green-500/40 bg-green-500/10 text-green-400',
              status === 'cancelled' && 'border-red-500/40 bg-red-500/10 text-red-400',
              (status === 'approved' || status === 'executing') && 'border-amber-500/40 bg-amber-500/10 text-amber-400',
              status === 'draft' && 'border-slate-600 bg-slate-800/40 text-slate-300',
            )}>
              Plan #{plan.plan_id} · {status}
            </span>
            <span className="text-2xs text-slate-500">{plan.optimizer_status ?? '—'}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {status === 'draft' && (
              <>
                <ButtonVariant variant="success" disabled={planLoading} onClick={() => onTransition('approved')} icon={<CheckCircle className="h-4 w-4" />} label="Approve" />
                <ButtonVariant variant="outline" disabled={planLoading} onClick={() => onTransition('cancelled')} icon={<XCircle className="h-4 w-4" />} label="Cancel" />
              </>
            )}
            {status === 'approved' && (
              <>
                <ButtonVariant variant="warning" disabled={planLoading} onClick={() => onTransition('executing')} icon={<Zap className="h-4 w-4" />} label="Start Execution" />
                <ButtonVariant variant="outline" disabled={planLoading} onClick={() => onTransition('cancelled')} icon={<XCircle className="h-4 w-4" />} label="Cancel" />
              </>
            )}
            {status === 'executing' && (
              <>
                <ButtonVariant variant="success" disabled={planLoading} onClick={() => onTransition('completed')} icon={<CheckCircle className="h-4 w-4" />} label="Mark Completed" />
                <ButtonVariant variant="outline" disabled={planLoading} onClick={() => onTransition('cancelled')} icon={<XCircle className="h-4 w-4" />} label="Cancel" />
              </>
            )}
            {status === 'completed' && (
              <ButtonVariant variant="outline" disabled={planLoading} onClick={onCreatePlan} icon={<RefreshCw className="h-4 w-4" />} label="New Plan" />
            )}
          </div>
        </div>
      )}

      {/* Allocation summary */}
      <div className={clsx('rounded-lg border p-3',
        feasible
          ? 'border-green-500/30 bg-green-500/10'
          : 'border-red-500/30 bg-red-500/10'
      )}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-green-500" />
            <span className="text-sm font-bold text-green-500">{feasible ? 'FEASIBLE' : 'INFEASIBLE'}</span>
          </div>
          <DataTypeBadge type={dataStatus as 'DERIVED' | 'RECOMMENDATION' | 'SIMULATED'} />
        </div>
        <p className="text-xs text-slate-400">
          {totalAllocated.toLocaleString()} / {totalDemand.toLocaleString()} persons allocated
          {plan && plan.unallocated > 0 ? ` · ${plan.unallocated.toLocaleString()} unallocated` : ''}
        </p>
      </div>

      <div className="bg-slate-900/30 rounded-lg border border-slate-800/20 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-800">
              {['Site', 'Allocated', 'Distance', 'Utilization', 'Surplus'].map(h => (
                <th key={h} className="px-3 py-2 text-left text-2xs font-semibold uppercase tracking-wide text-slate-400">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(allocations.length > 0 ? allocations.slice(0, 12) : []) .map((a, i) => (
              <tr key={`${a.site_id}-${i}`} className="border-b border-slate-800/50">
                <td className="px-3 py-2">
                  <div className="text-xs font-medium text-white">{a.site_name?.split(' — ')[1] || a.site_id}</div>
                  <div className="text-2xs text-slate-400">{a.site_name?.split(' — ')[0]}</div>
                </td>
                <td className="px-3 py-2 text-xs font-mono text-white">{a.allocated_population.toLocaleString()}</td>
                <td className="px-3 py-2 text-xs font-mono text-slate-400">{a.distance_km} km</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1.5 rounded-full bg-slate-800">
                      <div className="h-full rounded-full" style={{ width: `${a.utilization_pct}%`, backgroundColor: a.utilization_pct >= 90 ? '#ffbb33' : '#00b4d8' }} />
                    </div>
                    <span className="text-2xs font-mono text-slate-400">{a.utilization_pct}%</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-xs font-mono text-slate-400">{a.surplus_after.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {allocations.length > 12 && (
          <p className="px-3 py-2 text-2xs text-slate-500">
            Showing first 12 of {allocations.length} allocations.
          </p>
        )}
      </div>
      <p className="text-2xs text-slate-500">
        {plan
          ? `Assignments are per-habitation; allocation from the CP-SAT optimizer.`
          : 'Showing labeled DEMO seed allocation (API unavailable).'}
      </p>
    </div>
  );
}
