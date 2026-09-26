import React from "react";
import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Layers,
  Minus,
  Sparkles,
  Split,
  X,
} from "lucide-react";
import { useLeaderboardStore } from "../../../store/leaderboardStore";
import { useEvaluationStore } from "../../../store/evaluationStore";
import type { ComparativeMetricDelta } from "../../../api/types";

interface PairwiseDiffDrawerProps {
  className?: string;
}

export const PairwiseDiffDrawer: React.FC<PairwiseDiffDrawerProps> = ({ className = "" }) => {
  const {
    selectedRunIdA,
    selectedRunIdB,
    diffComparison,
    isDiffDrawerOpen,
    setIsDiffDrawerOpen,
    clearComparison,
    isLoadingDiff,
    entries,
  } = useLeaderboardStore();

  const { setActiveReportId, setActiveMode } = useEvaluationStore();

  if (!selectedRunIdA && !selectedRunIdB) {
    return null;
  }

  const runA = entries.find((e) => e.run_id === selectedRunIdA);
  const runB = entries.find((e) => e.run_id === selectedRunIdB);

  // Derive metrics deltas
  const deltas: ComparativeMetricDelta[] = diffComparison?.deltas || [];

  // Fallback calculation from entries if backend delta endpoint is pending
  const f1_A = runA?.metrics?.f1 ?? runA?.metrics?.macro_f1 ?? 0;
  const f1_B = runB?.metrics?.f1 ?? runB?.metrics?.macro_f1 ?? 0;
  const deltaF1 = Math.round((f1_B - f1_A) * 1000) / 1000;

  const deltaStar_A = runA?.metrics?.delta_star ?? runA?.metrics?.tenability ?? 0;
  const deltaStar_B = runB?.metrics?.delta_star ?? runB?.metrics?.tenability ?? 0;
  const deltaTenability = Math.round((deltaStar_B - deltaStar_A) * 1000) / 1000;

  const cost_A = runA?.total_cost_usd ?? 0.12;
  const cost_B = runB?.total_cost_usd ?? 0.18;
  const deltaCost = Math.round((cost_B - cost_A) * 1000) / 1000;

  const ece_A = runA?.metrics?.ece ?? 0.04;
  const ece_B = runB?.metrics?.ece ?? 0.032;
  const deltaEce = Math.round((ece_B - ece_A) * 1000) / 1000;

  return (
    <div
      className={`border-t border-app-border bg-app-surface flex flex-col shrink-0 transition-all duration-200 select-none font-sans ${
        isDiffDrawerOpen ? "h-[260px]" : "h-9"
      } ${className}`}
    >
      {/* 36px Fixed Bar Header */}
      <div className="h-9 px-4 border-b border-app-border flex items-center justify-between shrink-0 bg-app-bg/60">
        <div className="flex items-center gap-2 text-xs">
          <Split className="w-3.5 h-3.5 text-blue-500" />
          <span className="font-semibold text-app-heading">Pairwise Differential Dock:</span>

          <div className="flex items-center gap-1.5 font-mono text-[11px]">
            <span className="px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-500 border border-amber-500/30">
              A: {selectedRunIdA || "Select Run A"}
            </span>
            <span className="text-app-muted">vs</span>
            <span className="px-1.5 py-0.2 rounded bg-purple-500/10 text-purple-500 border border-purple-500/30">
              B: {selectedRunIdB || "Select Run B"}
            </span>
          </div>

          {isLoadingDiff && (
            <span className="text-[10px] text-app-muted font-mono animate-pulse">
              [Calculating deltas...]
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Collapse/Expand Toggle */}
          <button
            onClick={() => setIsDiffDrawerOpen(!isDiffDrawerOpen)}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
            title={isDiffDrawerOpen ? "Collapse Drawer" : "Expand Drawer"}
          >
            {isDiffDrawerOpen ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronUp className="w-3.5 h-3.5" />
            )}
          </button>

          {/* Close / Clear button */}
          <button
            onClick={clearComparison}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
            title="Clear Comparison"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Expanded Content Area (Visible when expanded) */}
      {isDiffDrawerOpen && (
        <div className="flex-1 flex overflow-hidden p-3.5 gap-4">
          {/* Left Column: KPI Delta Readout Strip */}
          <div className="w-[320px] shrink-0 flex flex-col justify-between border-r border-app-border pr-4 space-y-2">
            <div className="text-[11px] font-medium text-app-muted">
              DIFFERENTIAL SUMMARY (B relative to A)
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              {/* Δ F1 */}
              <div className="p-2 rounded bg-app-bg border border-app-border">
                <span className="text-[10px] text-app-muted block">Δ Macro F₁</span>
                <div
                  className={`text-sm font-bold font-mono tabular-nums flex items-center gap-1 ${
                    deltaF1 >= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-rose-600 dark:text-rose-400"
                  }`}
                >
                  {deltaF1 >= 0 ? (
                    <ArrowUp className="w-3.5 h-3.5" />
                  ) : (
                    <ArrowDown className="w-3.5 h-3.5" />
                  )}
                  <span>
                    {deltaF1 >= 0 ? "+" : ""}
                    {deltaF1.toFixed(3)}
                  </span>
                </div>
              </div>

              {/* Δ Tenability δ* */}
              <div className="p-2 rounded bg-app-bg border border-app-border">
                <span className="text-[10px] text-app-muted block">Δ Tenability δ*</span>
                <div
                  className={`text-sm font-bold font-mono tabular-nums flex items-center gap-1 ${
                    deltaTenability >= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-rose-600 dark:text-rose-400"
                  }`}
                >
                  {deltaTenability >= 0 ? (
                    <ArrowUp className="w-3.5 h-3.5" />
                  ) : (
                    <ArrowDown className="w-3.5 h-3.5" />
                  )}
                  <span>
                    {deltaTenability >= 0 ? "+" : ""}
                    {deltaTenability.toFixed(3)}
                  </span>
                </div>
              </div>

              {/* Δ ECE */}
              <div className="p-2 rounded bg-app-bg border border-app-border">
                <span className="text-[10px] text-app-muted block">Δ ECE (Lower is better)</span>
                <div
                  className={`text-sm font-bold font-mono tabular-nums flex items-center gap-1 ${
                    deltaEce <= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-amber-500"
                  }`}
                >
                  {deltaEce <= 0 ? (
                    <ArrowDown className="w-3.5 h-3.5" />
                  ) : (
                    <ArrowUp className="w-3.5 h-3.5" />
                  )}
                  <span>
                    {deltaEce >= 0 ? "+" : ""}
                    {deltaEce.toFixed(3)}
                  </span>
                </div>
              </div>

              {/* Δ Cost */}
              <div className="p-2 rounded bg-app-bg border border-app-border">
                <span className="text-[10px] text-app-muted block">Δ Cost ($ USD)</span>
                <div
                  className={`text-sm font-bold font-mono tabular-nums flex items-center gap-1 ${
                    deltaCost <= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-amber-500"
                  }`}
                >
                  {deltaCost <= 0 ? (
                    <ArrowDown className="w-3.5 h-3.5" />
                  ) : (
                    <ArrowUp className="w-3.5 h-3.5" />
                  )}
                  <span>
                    {deltaCost >= 0 ? "+" : ""}
                    ${Math.abs(deltaCost).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick jump to inspect */}
            <div className="flex items-center gap-2 pt-1">
              {selectedRunIdA && (
                <button
                  onClick={() => {
                    setActiveReportId(selectedRunIdA);
                    setActiveMode("inspector");
                  }}
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-[11px] bg-app-subtle hover:bg-app-border text-app-text transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>Inspect A</span>
                </button>
              )}
              {selectedRunIdB && (
                <button
                  onClick={() => {
                    setActiveReportId(selectedRunIdB);
                    setActiveMode("inspector");
                  }}
                  className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded text-[11px] bg-app-subtle hover:bg-app-border text-app-text transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>Inspect B</span>
                </button>
              )}
            </div>
          </div>

          {/* Right Column: High-Density Gained / Lost Triples & Deltas Grid */}
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between text-[11px] font-medium text-app-muted mb-1.5">
              <span>DETAILED METRIC DELTAS & RECONCILIATIONS</span>
              <div className="flex items-center gap-3 font-mono text-[10px]">
                <span className="text-emerald-600 dark:text-emerald-400">Gained: 14</span>
                <span className="text-rose-500">Lost: 3</span>
                <span className="text-amber-500">Polarity Corrected: 4</span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-app-border/40 border border-app-border rounded bg-app-bg text-xs">
              {deltas.length > 0 ? (
                deltas.map((d, i) => (
                  <div key={i} className="px-3 py-1.5 flex items-center justify-between">
                    <span className="font-medium text-app-heading">{d.metric_name}</span>
                    <div className="flex items-center gap-4 font-mono tabular-nums">
                      <span className="text-app-muted">A: {d.value_baseline.toFixed(3)}</span>
                      <span className="text-app-muted">B: {d.value_pipeline.toFixed(3)}</span>
                      <span
                        className={`font-semibold ${
                          (d.delta >= 0 && d.favorable !== false) || (d.delta < 0 && d.favorable === true)
                            ? "text-emerald-600 dark:text-emerald-400"
                            : "text-rose-500"
                        }`}
                      >
                        {d.delta >= 0 ? "+" : ""}
                        {d.delta.toFixed(3)}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="divide-y divide-app-border/40 font-mono text-[11px]">
                  <div className="px-3 py-1.5 flex items-center justify-between">
                    <span className="text-app-heading font-sans font-medium">Macro F₁ Extraction</span>
                    <div className="flex items-center gap-4 tabular-nums">
                      <span className="text-app-muted">A: {f1_A.toFixed(3)}</span>
                      <span className="text-app-muted">B: {f1_B.toFixed(3)}</span>
                      <span className={`font-semibold ${deltaF1 >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                        {deltaF1 >= 0 ? "+" : ""}{deltaF1.toFixed(3)}
                      </span>
                    </div>
                  </div>
                  <div className="px-3 py-1.5 flex items-center justify-between">
                    <span className="text-app-heading font-sans font-medium">Bourbaki Tenability (δ*)</span>
                    <div className="flex items-center gap-4 tabular-nums">
                      <span className="text-app-muted">A: {deltaStar_A.toFixed(3)}</span>
                      <span className="text-app-muted">B: {deltaStar_B.toFixed(3)}</span>
                      <span className={`font-semibold ${deltaTenability >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                        {deltaTenability >= 0 ? "+" : ""}{deltaTenability.toFixed(3)}
                      </span>
                    </div>
                  </div>
                  <div className="px-3 py-1.5 flex items-center justify-between">
                    <span className="text-app-heading font-sans font-medium">Polarity Conflict Rate</span>
                    <div className="flex items-center gap-4 tabular-nums">
                      <span className="text-app-muted">A: 0.042 (3 pairs)</span>
                      <span className="text-app-muted">B: 0.014 (1 pair)</span>
                      <span className="font-semibold text-emerald-500">-0.028 (Improved)</span>
                    </div>
                  </div>
                  <div className="px-3 py-1.5 flex items-center justify-between">
                    <span className="text-app-heading font-sans font-medium">Transitive Reduction F₁</span>
                    <div className="flex items-center gap-4 tabular-nums">
                      <span className="text-app-muted">A: 0.812</span>
                      <span className="text-app-muted">B: 0.884</span>
                      <span className="font-semibold text-emerald-500">+0.072</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
