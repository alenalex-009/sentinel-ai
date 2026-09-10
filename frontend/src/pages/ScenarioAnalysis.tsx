import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, RefreshCw, ChevronRight, Info } from "lucide-react";
import { DataTypeBadge } from "../components/ui/DataTypeBadge";
import { FreshnessBadge } from "../components/ui/FreshnessBadge";
import { PriorityBadge } from "../components/ui/PriorityBadge";
import { RiskBadge } from "../components/ui/RiskBadge";
import {
  DEMO_MUNNAR_CENTRAL,
  DEMO_CANDIDATE_SITES,
  DEMO_SCENARIO_PRESETS,
  runScenario,
} from "../data/idukki-seed";
import { api } from "../api/client";
import type { ScenarioParams, ScenarioResult } from "../types";
import clsx from "clsx";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";

const BASELINE_RISK = DEMO_MUNNAR_CENTRAL.risk.current;
const BASELINE_DEMAND = DEMO_MUNNAR_CENTRAL.population;
const TOTAL_CAPACITY = DEMO_CANDIDATE_SITES.reduce(
  (s, site) => s + site.safe_capacity,
  0,
);

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
  disabled = false,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400">{label}</span>
        <span
          className={clsx(
            "text-xs font-mono font-semibold",
            disabled ? "text-slate-600" : "text-slate-200",
          )}
        >
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className={clsx(
          "w-full h-1.5 rounded-full appearance-none cursor-pointer",
          "bg-slate-800 [&::-webkit-slider-thumb]:appearance-none",
          "[&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:w-3.5",
          "[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500",
          disabled && "opacity-40 cursor-not-allowed",
        )}
      />
    </div>
  );
}

function ImpactMetric({
  label,
  baseline,
  simulated,
  unit = "",
  higherIsBad = true,
}: {
  label: string;
  baseline: number;
  simulated: number;
  unit?: string;
  higherIsBad?: boolean;
}) {
  const delta = simulated - baseline;
  const changed = delta !== 0;
  const worse = higherIsBad ? delta > 0 : delta < 0;
  return (
    <div className="rounded border border-slate-800 bg-slate-900 p-2.5">
      <div className="text-2xs text-slate-500 mb-1">{label}</div>
      <div className="flex items-baseline gap-2">
        <span
          className={clsx(
            "text-lg font-bold font-mono",
            !changed
              ? "text-slate-300"
              : worse
                ? "text-red-400"
                : "text-green-400",
          )}
        >
          {simulated.toLocaleString()}
          {unit}
        </span>
        {changed && (
          <span
            className={clsx(
              "text-xs font-mono",
              worse ? "text-red-400" : "text-green-400",
            )}
          >
            {delta > 0 ? "+" : ""}
            {delta.toLocaleString()}
            {unit}
          </span>
        )}
      </div>
      <div className="text-2xs text-slate-600">
        Baseline: {baseline.toLocaleString()}
        {unit}
      </div>
    </div>
  );
}

export function ScenarioAnalysis() {
  const navigate = useNavigate();
  const h = DEMO_MUNNAR_CENTRAL;

  const [params, setParams] = useState<ScenarioParams>(
    DEMO_SCENARIO_PRESETS[0],
  );
  const [result, setResult] = useState<ScenarioResult>(() =>
    runScenario(DEMO_SCENARIO_PRESETS[0]),
  );

  async function runAndSet(next: ScenarioParams) {
    setParams(next);
    try {
      const apiResult = (await api.runScenario({
        habitation_id: next.habitation_id,
        label: next.label,
        rainfall_multiplier: next.rainfall_multiplier,
        population_change_pct: next.population_change_pct,
        capacity_reduction_pct: next.capacity_reduction_pct,
        road_disruption: next.road_disruption,
      })) as ScenarioResult;
      // API returns SIMULATED — use it directly
      if (apiResult?.data_type === "SIMULATED") {
        setResult(apiResult);
        return;
      }
    } catch {
      // API unavailable — fall back to frontend engine (also SIMULATED)
    }
    setResult(runScenario(next));
  }

  function update(patch: Partial<ScenarioParams>) {
    const next = { ...params, ...patch };
    runAndSet(next);
  }

  function applyPreset(preset: ScenarioParams) {
    runAndSet(preset);
  }

  const gapData = [
    { name: "Demand", value: result.simulated_demand, fill: "#ef4444" },
    {
      name: "Capacity",
      value: result.simulated_capacity_available,
      fill: "#14b8a6",
    },
  ];

  return (
    <div className="flex h-full overflow-hidden">
      {/* LEFT — controls */}
      <div className="flex w-72 flex-shrink-0 flex-col gap-4 overflow-y-auto border-r border-slate-800 bg-slate-950 p-4">
        {/* SIMULATION warning */}
        <div className="rounded border border-cyan-500/30 bg-cyan-500/10 px-3 py-2">
          <div className="flex items-center gap-2 mb-1">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
            <span className="text-xs font-semibold text-cyan-400">
              SIMULATION MODE
            </span>
          </div>
          <p className="text-2xs text-cyan-400/70 leading-relaxed">
            All results are SIMULATED. Not live data. For planning and
            demonstration purposes only.
          </p>
        </div>

        {/* Source habitation */}
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div className="text-2xs text-slate-500 mb-1">
            Scenario Habitation
          </div>
          <div className="text-sm font-bold text-slate-200">{h.name}</div>
          <div className="text-2xs text-slate-500">
            {h.ward} · {h.taluk}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <RiskBadge score={h.risk.current} size="sm" />
            <span className="text-2xs text-slate-500">Baseline risk</span>
          </div>
        </div>

        {/* Presets */}
        <div>
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
            Presets
          </div>
          <div className="flex flex-col gap-1.5">
            {DEMO_SCENARIO_PRESETS.map((preset) => (
              <button
                key={preset.label}
                onClick={() => applyPreset(preset)}
                className={clsx(
                  "rounded border px-2.5 py-2 text-left text-xs transition-colors",
                  params.label === preset.label
                    ? "border-blue-500/50 bg-blue-600/15 text-blue-300"
                    : "border-slate-800 bg-slate-900 text-slate-400 hover:text-slate-300",
                )}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Manual controls */}
        <div>
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
            Manual Controls
          </div>
          <div className="flex flex-col gap-4">
            <SliderRow
              label="Rainfall multiplier"
              value={params.rainfall_multiplier}
              min={0.5}
              max={3.0}
              step={0.1}
              unit="×"
              onChange={(v) =>
                update({ rainfall_multiplier: v, label: "Custom" })
              }
            />
            <SliderRow
              label="Population change"
              value={params.population_change_pct}
              min={-20}
              max={50}
              step={5}
              unit="%"
              onChange={(v) =>
                update({ population_change_pct: v, label: "Custom" })
              }
            />
            <SliderRow
              label="Capacity reduction"
              value={params.capacity_reduction_pct}
              min={0}
              max={60}
              step={5}
              unit="%"
              onChange={(v) =>
                update({ capacity_reduction_pct: v, label: "Custom" })
              }
            />

            {/* Road disruption toggle */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">
                Road disruption (Site B)
              </span>
              <button
                onClick={() =>
                  update({
                    road_disruption: !params.road_disruption,
                    label: "Custom",
                  })
                }
                className={clsx(
                  "relative h-5 w-9 rounded-full transition-colors",
                  params.road_disruption ? "bg-red-500" : "bg-slate-700",
                )}
              >
                <span
                  className={clsx(
                    "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
                    params.road_disruption
                      ? "translate-x-4"
                      : "translate-x-0.5",
                  )}
                />
              </button>
            </div>
          </div>
        </div>

        <button
          onClick={() => applyPreset(DEMO_SCENARIO_PRESETS[0])}
          className="flex items-center gap-2 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-400 hover:text-slate-300 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Reset to baseline
        </button>

        <FreshnessBadge status="SIMULATION" />
      </div>

      {/* RIGHT — results */}
      <div className="flex flex-1 flex-col overflow-y-auto gap-4 p-4">
        {/* SIMULATED banner */}
        <div className="rounded border border-cyan-500/40 bg-cyan-500/10 px-4 py-3">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <DataTypeBadge type="SIMULATED" />
                <span className="text-xs font-semibold text-cyan-300">
                  {params.label}
                </span>
              </div>
              <p className="text-xs text-cyan-400/80 leading-relaxed">
                {result.warning}
              </p>
            </div>
            <FreshnessBadge status="SIMULATION" />
          </div>
          {result.impact_summary && (
            <div className="mt-2 rounded border border-cyan-500/20 bg-cyan-500/5 px-2.5 py-1.5">
              <p className="text-xs text-cyan-300 font-mono">
                {result.impact_summary}
              </p>
            </div>
          )}
        </div>

        {/* Key metrics */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <ImpactMetric
            label="Simulated Risk"
            baseline={BASELINE_RISK}
            simulated={result.simulated_risk}
          />
          <ImpactMetric
            label="Relocation Demand"
            baseline={BASELINE_DEMAND}
            simulated={result.simulated_demand}
            unit=" persons"
          />
          <ImpactMetric
            label="Available Capacity"
            baseline={TOTAL_CAPACITY}
            simulated={result.simulated_capacity_available}
            unit=" persons"
            higherIsBad={false}
          />
          <div className="rounded border border-slate-800 bg-slate-900 p-2.5">
            <div className="text-2xs text-slate-500 mb-1">Capacity Gap</div>
            <div
              className={clsx(
                "text-lg font-bold font-mono",
                result.simulated_gap > 0 ? "text-red-400" : "text-green-400",
              )}
            >
              {result.simulated_gap > 0 ? "+" : ""}
              {result.simulated_gap.toLocaleString()}
            </div>
            <div className="text-2xs text-slate-600">
              {result.simulated_gap > 0
                ? "persons unallocated"
                : "surplus capacity"}
            </div>
          </div>
        </div>

        {/* Priority change */}
        <div className="flex items-center gap-4 rounded-lg border border-slate-800 bg-slate-900 p-3">
          <div>
            <div className="text-2xs text-slate-500 mb-1">
              Baseline Priority
            </div>
            <PriorityBadge
              priority={h.relocation_priority.priority}
              size="lg"
            />
          </div>
          <ChevronRight className="h-4 w-4 text-slate-600" />
          <div>
            <div className="text-2xs text-slate-500 mb-1">
              Simulated Priority
            </div>
            <PriorityBadge priority={result.simulated_priority} size="lg" />
          </div>
          <div className="ml-auto">
            <DataTypeBadge type="SIMULATED" />
          </div>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-2 gap-4">
          {/* Demand vs Capacity */}
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-400">
                Demand vs Capacity
              </span>
              <DataTypeBadge type="SIMULATED" />
            </div>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={gapData} barSize={40}>
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: "#64748b" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: "#64748b" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: 4,
                    fontSize: 11,
                  }}
                  formatter={(v: number) => [v.toLocaleString(), "persons"]}
                />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {gapData.map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} opacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {result.simulated_gap > 0 && (
              <div className="mt-2 flex items-center gap-2 rounded border border-red-500/30 bg-red-500/10 px-2 py-1.5">
                <AlertTriangle className="h-3.5 w-3.5 text-red-400 flex-shrink-0" />
                <span className="text-2xs text-red-400">
                  {result.simulated_gap.toLocaleString()} persons cannot be
                  allocated under this scenario
                </span>
              </div>
            )}
          </div>

          {/* Risk comparison */}
          <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-slate-400">
                Risk: Baseline vs Simulated
              </span>
              <DataTypeBadge type="SIMULATED" />
            </div>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart
                data={[
                  { name: "Baseline", value: BASELINE_RISK, fill: "#475569" },
                  {
                    name: "Simulated",
                    value: result.simulated_risk,
                    fill:
                      result.simulated_risk >= 80
                        ? "#ef4444"
                        : result.simulated_risk >= 60
                          ? "#f97316"
                          : "#eab308",
                  },
                ]}
                barSize={40}
              >
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 10, fill: "#64748b" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 9, fill: "#64748b" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: 4,
                    fontSize: 11,
                  }}
                />
                <ReferenceLine
                  y={80}
                  stroke="#ef4444"
                  strokeDasharray="3 2"
                  strokeWidth={1}
                />
                <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                  {[
                    { name: "Baseline", fill: "#475569" },
                    {
                      name: "Simulated",
                      fill: result.simulated_risk >= 80 ? "#ef4444" : "#f97316",
                    },
                  ].map((entry) => (
                    <Cell key={entry.name} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Trust note */}
        <div className="rounded border border-slate-800 bg-slate-900/50 p-3">
          <div className="flex items-start gap-2">
            <Info className="h-3.5 w-3.5 text-slate-600 flex-shrink-0 mt-0.5" />
            <p className="text-2xs text-slate-600 leading-relaxed">
              Scenario results are SIMULATED using the Sentinel AI risk and
              capacity models with the parameters above. They are not live
              forecasts. Rainfall multiplier affects the hazard component of the
              risk model. Capacity reduction applies uniformly across all sites.
              Road disruption removes Site B from the available pool. All
              results require human authority review before any planning
              decision.
            </p>
          </div>
        </div>

        {/* CTA */}
        <button
          onClick={() => navigate("/relocation")}
          className="flex items-center justify-between rounded border border-blue-500/30 bg-blue-600/10 px-4 py-2.5 text-xs font-semibold text-blue-400 hover:bg-blue-600/20 transition-colors"
        >
          Return to Relocation Intelligence
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
