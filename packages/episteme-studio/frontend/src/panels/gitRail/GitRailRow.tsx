import React from "react";
import { GitRailNode } from "./types";
import { EPISTEMIC_TAXONOMY } from "../epistemicTheme";
import { getShortStageLabel } from "../stageModel";
import { ChevronDown, ChevronRight, Boxes, Zap } from "lucide-react";
import { useRunsStore } from "../../store/runsStore";

interface GitRailRowProps {
  node: GitRailNode;
  isSelected: boolean;
  isParent: boolean;
  isChild: boolean;
  isDimmed: boolean;
  isLiveRunning: boolean;
  onSelect: (key: string) => void;
  onToggleFold?: (branchId: string, e: React.MouseEvent) => void;
  isFolded?: boolean;
  nodeRef?: (el: HTMLDivElement | null) => void;
  liveProgress?: {
    step?: number | null;
    totalSteps?: number | null;
    percentage?: number | null;
    description?: string | null;
  } | null;
}

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
};

/**
 * High-density 32px flush row with hairline border, micro-typography,
 * tabular monospace statistics, and epistemic delta metrics.
 */
export const GitRailRow: React.FC<GitRailRowProps> = ({
  node,
  isSelected,
  isParent,
  isChild,
  isDimmed,
  isLiveRunning,
  onSelect,
  onToggleFold,
  isFolded,
  nodeRef,
  liveProgress,
}) => {
  const epistemic = EPISTEMIC_TAXONOMY[node.layerId];
  const duration =
    node.phaseRecord?.duration_seconds || node.totalDurationSeconds || 0;
  const durationStr = formatDuration(duration);
  const yieldCount =
    node.phaseRecord?.artifact_count ?? node.aggregateArtifactCount ?? 0;

  const selectedRunDetail = useRunsStore((s) => s.selectedRunDetail);
  const phaseDecision = selectedRunDetail?.decision_metrics?.by_phase?.[node.key.toLowerCase()];

  const shortTitle = node.isCompound
    ? node.phaseName
    : getShortStageLabel(node.phaseName, node.ordinal);

  // Micro prefix: e.g. L2·P3
  const microPrefix = node.isCompound
    ? `${node.layerId}·P2-5`
    : `${node.layerId}·P${node.ordinal}`;

  const isExecuted =
    node.phaseRecord?.status === "completed" ||
    (node.phaseRecord?.status === "running") ||
    node.cacheHit ||
    yieldCount > 0 ||
    duration > 0;

  const displayDuration = isLiveRunning ? (
    <span className="text-blue-600 dark:text-blue-400 font-semibold animate-pulse">
      live
    </span>
  ) : isExecuted ? (
    durationStr
  ) : (
    <span className="text-app-muted/50 text-[10px] font-mono">
      —
    </span>
  );

  return (
    <div
      ref={nodeRef}
      onClick={() => onSelect(node.key)}
      className={`group relative h-8 px-2 flex items-center justify-between border-b border-app-border/80 cursor-pointer transition-colors select-none text-xs ${
        isDimmed ? "opacity-70 hover:opacity-100" : "opacity-100"
      } ${
        isSelected
          ? "bg-app-subtle/90 text-app-heading font-medium"
          : isParent
          ? "bg-sky-50/50 dark:bg-sky-950/20 hover:bg-sky-50/80 dark:hover:bg-sky-950/30"
          : isChild
          ? "bg-purple-50/50 dark:bg-purple-950/20 hover:bg-purple-50/80 dark:hover:bg-purple-950/30"
          : "hover:bg-app-subtle/60 text-app-text"
      }`}
      title={`${node.phaseName} (${node.layerId} - ${epistemic.name})`}
    >
      {/* Active selection bridge seam: 2px hairline extending on left & right edge */}
      {isSelected && (
        <>
          <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-blue-600 dark:bg-blue-500" />
          <div className="absolute right-0 top-0 bottom-0 w-[2px] bg-blue-600 dark:bg-blue-500 shadow-sm" />
        </>
      )}

      {/* Left Column: Ontological micro-tag + Stage Name */}
      <div className="flex items-center gap-1.5 min-w-0 flex-1 pr-2">
        {/* Ontological Micro Prefix: neutral slate muted monospace micro-badge */}
        <span
          className="font-mono text-[9px] font-medium px-1 py-0.2 rounded shrink-0 tracking-tight text-app-muted bg-app-subtle border border-app-border"
        >
          {microPrefix}
        </span>

        {/* Phase Name: Elevated to medium-contrast zinc-600 when not selected */}
        <span
          className={`truncate min-w-0 text-[11px] font-sans ${
            isSelected
              ? "font-semibold text-app-heading"
              : "font-medium text-app-text"
          }`}
        >
          {shortTitle}
        </span>

        {/* Dual-Process System 1 Triage Badge */}
        {phaseDecision && phaseDecision.total_decisions > 0 && (
          <span
            className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded text-[9px] font-mono font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 shrink-0"
            title={`${phaseDecision.fast_exit_count} Fast-Exits, ${phaseDecision.llm_escalation_count} LLM Escalations (${Math.round((phaseDecision.fast_exit_count / Math.max(phaseDecision.total_decisions, 1)) * 100)}% S1)`}
          >
            <Zap className="w-2 h-2 text-emerald-500" />
            <span>{Math.round((phaseDecision.fast_exit_count / Math.max(phaseDecision.total_decisions, 1)) * 100)}% S1</span>
          </span>
        )}

        {/* Epistemic Delta / Yield delta in micro-typography strictly reserved for secondary deltas */}
        {node.deltaLabel && (
          <span className="hidden xl:inline text-[10px] font-mono text-app-muted truncate">
            {node.deltaLabel}
          </span>
        )}

        {/* Cached Glyph: Stack/Diamond with hover footprint */}
        {node.cacheHit && (
          <span
            className="inline-flex items-center text-[10px] font-mono text-cyan-700 dark:text-cyan-400 px-1 py-0.2 rounded bg-cyan-500/10 border border-cyan-500/20 shrink-0"
            title="Artifact cached from upstream / hydrated run"
          >
            ⟐
          </span>
        )}

        {/* Compound branch toggle button */}
        {(node.key === "phase2" || node.isCompound) && onToggleFold && (
          <button
            type="button"
            onClick={(e) => onToggleFold("kg", e)}
            className="p-0.5 text-app-muted hover:text-app-heading cursor-pointer shrink-0"
            title={isFolded ? "Expand KG sub-DAG" : "Collapse into KG super-node"}
          >
            {isFolded ? (
              <ChevronRight className="w-3 h-3" />
            ) : (
              <ChevronDown className="w-3 h-3" />
            )}
          </button>
        )}
      </div>

      {/* Right Column: Tabular Metrics Column (Yield + Duration) in medium-contrast zinc-600 */}
      <div className="flex items-center gap-2 shrink-0 font-mono text-[11px] tabular-nums text-app-muted font-medium">
        {node.confidencePct !== undefined && (
          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold hidden 2xl:inline">
            {node.confidencePct.toFixed(1)}%
          </span>
        )}

        <span className="text-[10px] tracking-tight">
          n={yieldCount.toLocaleString()}
        </span>

        <span className="w-16 text-right text-app-muted text-[10px]">
          {displayDuration}
        </span>
      </div>

      {/* Live execution mini-progress bar along bottom edge */}
      {isLiveRunning && (
        <div className="absolute bottom-0 left-0 right-0 h-[1.5px] bg-blue-100 dark:bg-blue-950 overflow-hidden">
          <div
            className="h-full bg-blue-600 transition-all duration-300"
            style={{
              width: `${Math.max(10, liveProgress?.percentage ?? 15)}%`,
            }}
          />
        </div>
      )}
    </div>
  );
};
