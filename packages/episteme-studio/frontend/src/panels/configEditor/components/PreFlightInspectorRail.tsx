import React from "react";
import {
  Activity,
  Play,
  RefreshCw,
  AlertTriangle,
  Clock,
  DollarSign,
  Terminal,
  ChevronDown,
  ChevronRight,
  Check,
  Copy,
  Database,
  ShieldCheck,
  ArrowRight,
  Layers,
  Loader2,
  Zap,
} from "lucide-react";
import { GlobalStructuralAnchor, InvalidationPreview, DecisionEngineSettings } from "../../../api/types";
import { PhaseExecutionStatusMap } from "../phaseExecution";

interface PreFlightInspectorRailProps {
  hasRunBaseline: boolean;
  phaseExecutionStatus: PhaseExecutionStatusMap;
  effectiveInvalidationPreview: InvalidationPreview;
  isLaunching: boolean;
  handleLaunchRun: () => void;
  isPreviewLoading: boolean;
  errorMessage: string | null;
  corePhaseKeys: string[];
  selectedProfile: string;
  effectiveSourcePaths: string[];
  selectedBibPaths: string[];
  effectiveMetadata: Record<string, string>;
  effectiveAnchor: GlobalStructuralAnchor | null;
  executionMode: "single" | "corpus";
  simulationMode: boolean;
  setSimulationMode: (val: boolean) => void;
  isCliExportExpanded: boolean;
  setIsCliExportExpanded: (val: boolean) => void;
  cliCommand: string;
  copiedCli: boolean;
  handleCopyCli: () => void;
  decisionEngineSettings?: DecisionEngineSettings;
  hasDecisionOverrides?: boolean;
}

export const PreFlightInspectorRail: React.FC<PreFlightInspectorRailProps> = ({
  hasRunBaseline,
  effectiveInvalidationPreview,
  isLaunching,
  handleLaunchRun,
  isPreviewLoading,
  errorMessage,
  corePhaseKeys,
  selectedProfile,
  effectiveSourcePaths,
  executionMode,
  simulationMode,
  setSimulationMode,
  isCliExportExpanded,
  setIsCliExportExpanded,
  cliCommand,
  copiedCli,
  handleCopyCli,
  decisionEngineSettings,
  hasDecisionOverrides,
}) => {
  // Derived diagnostic metrics
  const totalPhases = Math.max(1, corePhaseKeys.length);
  const invalidatedCount = effectiveInvalidationPreview?.invalidated_phases?.length || 0;
  const reusedCount = effectiveInvalidationPreview?.reused_phases?.length || 0;

  const isAllCached = hasRunBaseline && invalidatedCount === 0;
  const isPartialInvalidation = hasRunBaseline && invalidatedCount > 0;
  const isFreshRun = !hasRunBaseline;

  // Cache hit ratio calculation
  const cacheHitRatio = isFreshRun
    ? 0
    : isAllCached
    ? 100
    : Math.round((reusedCount / Math.max(1, reusedCount + invalidatedCount)) * 100);

  // Compute estimates based on dirty stages
  const estRuntimeSeconds = isFreshRun
    ? totalPhases * 8
    : isAllCached
    ? 0
    : Math.max(2, invalidatedCount * 6);

  const estCostDollars = isFreshRun
    ? (totalPhases * 0.0006).toFixed(4)
    : isAllCached
    ? "0.0000"
    : (invalidatedCount * 0.0006).toFixed(4);

  // Target label formatting
  const targetDocName = effectiveSourcePaths.length > 0
    ? effectiveSourcePaths[0].split("/").pop() || "Document"
    : "No document";

  return (
    <div className="w-full h-full flex flex-col bg-app-surface border-l border-app-border overflow-hidden select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 1. RAIL HEADER & LIVE OPERATIONAL BEACON                           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-12 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Activity className="w-4 h-4 text-app-heading shrink-0" />
          <div className="min-w-0">
            <h2 className="text-xs font-semibold text-app-heading tracking-tight truncate font-display">
              Pre-Flight Diagnostics
            </h2>
            <span className="text-[11px] text-app-muted block truncate font-sans">
              Execution readiness & telemetry
            </span>
          </div>
        </div>

        {/* Operational Status Pill */}
        {isFreshRun ? (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-blue-500/10 text-blue-500 dark:text-blue-400 border border-blue-500/20 font-medium inline-flex items-center gap-1.5 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
            <span>Fresh Run</span>
          </span>
        ) : isAllCached ? (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-medium inline-flex items-center gap-1.5 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
            <span>Hydrated</span>
          </span>
        ) : (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-medium inline-flex items-center gap-1.5 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
            <span>{invalidatedCount} Dirty</span>
          </span>
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* SCROLLABLE DIAGNOSTIC COCKPIT                                      */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto select-text">
        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 2. EXECUTION COMMAND POST (Primary Action & Engine Scope)         */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="p-4 border-b border-app-border space-y-3">
          {/* Primary CTA Launch Button */}
          <button
            type="button"
            onClick={handleLaunchRun}
            disabled={isLaunching}
            className="w-full h-9 rounded bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold text-xs transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 tracking-wide border border-blue-400/20"
          >
            {isLaunching ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Launching Run...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Launch Pipeline Run</span>
              </>
            )}
          </button>

          {/* Engine Selector & Run Scope Row */}
          <div className="flex items-center justify-between gap-2 pt-0.5">
            <span className="text-[11px] text-app-muted font-sans font-medium">
              Run Engine
            </span>

            {/* Segmented Pill Track */}
            <div className="p-0.5 inline-flex items-center bg-app-subtle rounded border border-app-border/60 gap-0.5 text-[11px]">
              <button
                type="button"
                onClick={() => setSimulationMode(false)}
                className={`h-5.5 px-2.5 rounded text-[11px] transition-all cursor-pointer font-medium ${
                  !simulationMode
                    ? "bg-app-surface text-app-heading font-semibold border border-app-border/80"
                    : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
                }`}
                title="Execute against live Neo4j store and LLM providers"
              >
                Real
              </button>
              <button
                type="button"
                onClick={() => setSimulationMode(true)}
                className={`h-5.5 px-2.5 rounded text-[11px] transition-all cursor-pointer font-medium ${
                  simulationMode
                    ? "bg-app-surface text-app-heading font-semibold border border-app-border/80"
                    : "text-app-muted hover:text-app-heading hover:bg-app-hover/50"
                }`}
                title="Dry simulation mode without invoking external APIs or Neo4j"
              >
                Simulation
              </button>
            </div>
          </div>

          {/* Target Verification Breadcrumb */}
          <div className="pt-2 border-t border-app-border/60 flex items-center justify-between text-[11px] text-app-muted">
            <span className="truncate max-w-[180px] font-mono text-[10px]" title={targetDocName}>
              {targetDocName}
            </span>
            <span className="shrink-0 text-app-muted/80 font-sans text-[11px]">
              {executionMode === "single" ? "Single Doc" : "Corpus"} · {selectedProfile}
            </span>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 3. CACHE IMPACT (Unboxed, Highly Readable)                        */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="p-4 border-b border-app-border space-y-2.5">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-app-heading tracking-tight font-display">
              Cache Impact
            </h3>
            {isPreviewLoading && (
              <RefreshCw className="w-3 h-3 animate-spin text-app-muted" />
            )}
          </div>

          {errorMessage && (
            <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="leading-snug">{errorMessage}</span>
            </div>
          )}

          {/* Open, unboxed diagnosis layout */}
          <div className="space-y-2 text-xs">
            {/* Headline with state beacon */}
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full shrink-0 ${
                isAllCached ? "bg-emerald-500" : isPartialInvalidation ? "bg-amber-500" : "bg-blue-500"
              }`} />
              <span className="font-medium text-app-heading">
                {isAllCached
                  ? "Store Hydration Complete"
                  : isPartialInvalidation
                  ? "Partial Recomputation"
                  : "Fresh Execution"}
              </span>
            </div>

            {/* Clear, natural explanation */}
            <p className="text-[12px] text-app-muted leading-relaxed">
              {isAllCached
                ? "All pipeline stages will resume directly from the artifact store without recomputing."
                : isPartialInvalidation
                ? `${invalidatedCount} stages invalidated downstream, while ${reusedCount} stages will be reused from store.`
                : "Initial pipeline run. All stages will execute from scratch."}
            </p>

            {/* Trigger Reason (Clean, fully readable sentence) */}
            {effectiveInvalidationPreview?.reason && (
              <div className="text-[11px] leading-relaxed text-app-muted pt-1 border-t border-app-border/40">
                <span className="text-app-text font-medium">Trigger:</span>{" "}
                <span>{effectiveInvalidationPreview.reason}</span>
              </div>
            )}

            {/* Partial Invalidation Cutoff */}
            {isPartialInvalidation && (
              <div className="flex items-center gap-2 text-[11px] font-mono pt-1">
                <span className="text-emerald-500 font-medium">
                  {reusedCount} stages intact
                </span>
                <ArrowRight className="w-3 h-3 text-app-muted shrink-0" />
                <span className="text-amber-500 font-medium">
                  {invalidatedCount} to recompute
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 4. RESOURCE ESTIMATION (Unboxed, High-Density Stat Grid)          */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="p-4 border-b border-app-border space-y-3">
          <h3 className="text-xs font-semibold text-app-heading tracking-tight font-display">
            Resource Estimation
          </h3>

          {/* Clean, unboxed 2x2 stat grid */}
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            {/* Stat 1: Est. Runtime */}
            <div>
              <div className="text-[11px] text-app-muted font-sans flex items-center gap-1">
                <Clock className="w-3 h-3 text-app-muted shrink-0" />
                <span>Est. Duration</span>
              </div>
              <div
                className="text-base font-semibold text-app-heading font-mono tracking-tight mt-0.5"
                style={{ fontFeatureSettings: '"tnum" 1' }}
              >
                {estRuntimeSeconds === 0 ? "< 1s" : `~${estRuntimeSeconds}s`}
              </div>
            </div>

            {/* Stat 2: Est. Compute Cost */}
            <div>
              <div className="text-[11px] text-app-muted font-sans flex items-center gap-1">
                <DollarSign className="w-3 h-3 text-app-muted shrink-0" />
                <span>Est. LLM Cost</span>
              </div>
              <div
                className="text-base font-semibold text-app-heading font-mono tracking-tight mt-0.5"
                style={{ fontFeatureSettings: '"tnum" 1' }}
              >
                ~${estCostDollars}
              </div>
            </div>

            {/* Stat 3: Cache Hit Ratio */}
            <div>
              <div className="text-[11px] text-app-muted font-sans flex items-center gap-1">
                <Database className="w-3 h-3 text-app-muted shrink-0" />
                <span>Store Hit Rate</span>
              </div>
              <div
                className={`text-base font-semibold font-mono tracking-tight mt-0.5 ${
                  cacheHitRatio === 100
                    ? "text-emerald-500"
                    : cacheHitRatio > 0
                    ? "text-amber-500"
                    : "text-blue-500"
                }`}
                style={{ fontFeatureSettings: '"tnum" 1' }}
              >
                {cacheHitRatio}%
              </div>
            </div>

            {/* Stat 4: Artifact Delta */}
            <div>
              <div className="text-[11px] text-app-muted font-sans flex items-center gap-1">
                <Layers className="w-3 h-3 text-app-muted shrink-0" />
                <span>Artifact Delta</span>
              </div>
              <div
                className="text-base font-semibold text-app-heading font-mono tracking-tight mt-0.5"
                style={{ fontFeatureSettings: '"tnum" 1' }}
              >
                {effectiveInvalidationPreview?.estimated_artifact_loss === 0
                  ? "0 lost"
                  : `~${effectiveInvalidationPreview?.estimated_artifact_loss || 0} dirty`}
              </div>
            </div>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 5. DECISION ENGINE (JEV) ROUTING                                 */}
        {/* ───────────────────────────────────────────────────────────────── */}
        {decisionEngineSettings && (
          <div className="p-4 border-b border-app-border space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                <h3 className="text-xs font-semibold text-app-heading tracking-tight font-display">
                  Decision Engine Routing
                </h3>
              </div>
              {hasDecisionOverrides && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-500 border border-blue-500/20 font-medium">
                  Overridden
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-xs">
              <div>
                <span className="text-[11px] text-app-muted font-sans block">Provider · Device</span>
                <span className="text-xs font-semibold text-app-heading font-mono">
                  {decisionEngineSettings.provider.toUpperCase()} · {decisionEngineSettings.device.toUpperCase()}
                </span>
              </div>
              <div>
                <span className="text-[11px] text-app-muted font-sans block">Fast-Exit Threshold</span>
                <span className="text-xs font-semibold text-app-heading font-mono" style={{ fontFeatureSettings: '"tnum" 1' }}>
                  {Math.round(decisionEngineSettings.fast_exit_threshold * 100)}%
                </span>
              </div>
              <div>
                <span className="text-[11px] text-app-muted font-sans block">Active Phase Gates</span>
                <span className="text-xs font-semibold text-app-heading font-mono">
                  {Object.values(decisionEngineSettings.phase_gates || {}).filter(Boolean).length}/6 Active
                </span>
              </div>
              <div>
                <span className="text-[11px] text-app-muted font-sans block">Audit Rate</span>
                <span className="text-xs font-semibold text-app-heading font-mono" style={{ fontFeatureSettings: '"tnum" 1' }}>
                  {Math.round(decisionEngineSettings.stochastic_audit_rate * 100)}%
                </span>
              </div>
            </div>
          </div>
        )}

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 6. ARCHITECTURAL INVARIANTS                                       */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="p-4 border-b border-app-border space-y-2.5">
          <h3 className="text-xs font-semibold text-app-heading tracking-tight font-display">
            Architectural Invariants
          </h3>

          <div className="space-y-2 text-xs">
            <div className="flex items-start gap-2">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-500 shrink-0 mt-0.5" />
              <div className="text-[11px] leading-relaxed text-app-muted font-sans">
                <span className="text-app-heading font-medium">Decision D-14:</span> Swapping{" "}
                <code className="text-app-text font-mono text-[10px]">models.*</code> updates manifest
                provenance without invalidating cached DAG artifacts.
              </div>
            </div>

            <div className="flex items-start gap-2">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
              <div className="text-[11px] leading-relaxed text-app-muted font-sans">
                <span className="text-app-heading font-medium">Dual-Graph Neo4j Store:</span> Active
                workspace isolated from background analytical projections.
              </div>
            </div>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* 6. REPRODUCIBLE CLI TERMINAL BRIDGE                               */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="p-4 space-y-2">
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setIsCliExportExpanded(!isCliExportExpanded)}
              className="flex items-center gap-1.5 text-xs font-semibold text-app-heading hover:text-blue-500 transition-colors cursor-pointer font-display"
            >
              {isCliExportExpanded ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronRight className="w-3.5 h-3.5" />
              )}
              <Terminal className="w-3.5 h-3.5" />
              <span>Reproducible CLI</span>
            </button>

            <button
              type="button"
              onClick={handleCopyCli}
              className="h-6 px-2 rounded border border-app-border bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-heading text-[10px] font-mono transition-colors cursor-pointer inline-flex items-center gap-1"
              title="Copy terminal command to clipboard"
            >
              {copiedCli ? (
                <>
                  <Check className="w-3 h-3 text-emerald-500" />
                  <span className="text-emerald-500 font-medium">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>

          {isCliExportExpanded && (
            <div className="relative mt-1">
              <pre className="p-2.5 rounded bg-app-bg border border-app-border font-mono text-[10px] text-app-muted whitespace-pre-wrap select-all leading-relaxed break-all">
                <span className="text-cyan-500 select-none">$ </span>
                {cliCommand}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
