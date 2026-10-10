import React, {useMemo} from "react";
import {PhaseStatus} from "../api/types";
import {ChevronRight, Layers, RotateCcw,} from "lucide-react";
import {getPhaseLifecycleGroup, getShortStageLabel, LIFECYCLE_GROUPS, PipelineLifecycleGroup,} from "./stageModel";
import {resolvePhaseKey} from "./phaseConfig/phaseConfigResolver";

export interface RunTimelineProps {
  phaseRecords: PhaseStatus[];
  selectedPhaseKey?: string | null;
  onSelectPhase?: (phaseKey: string | null) => void;
  /** Legacy support for selecting by ordinal */
  selectedPhaseOrdinal?: number | null;
  onInspectConfig?: (phase: PhaseStatus) => void;
  showOverviewOption?: boolean;
}

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return "";
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}h ${rm}m`;
};

export const RunTimeline: React.FC<RunTimelineProps> = ({
  phaseRecords,
  selectedPhaseKey,
  onSelectPhase,
  selectedPhaseOrdinal,
  onInspectConfig,
  showOverviewOption = true,
}) => {
  // Group phase records into dynamic lifecycle phases: Ingest, Extraction & Inference, Synthesis, Post-processing
  const groupedPhases = useMemo(() => {
    const groups: {
      group: PipelineLifecycleGroup;
      meta: (typeof LIFECYCLE_GROUPS)[PipelineLifecycleGroup];
      stages: {
        phase: PhaseStatus;
        key: string;
        shortLabel: string;
      }[];
    }[] = [
      { group: "ingest", meta: LIFECYCLE_GROUPS.ingest, stages: [] },
      { group: "extraction", meta: LIFECYCLE_GROUPS.extraction, stages: [] },
      { group: "synthesis", meta: LIFECYCLE_GROUPS.synthesis, stages: [] },
      { group: "post", meta: LIFECYCLE_GROUPS.post, stages: [] },
    ];

    (phaseRecords || []).forEach((phase) => {
      const g = getPhaseLifecycleGroup(phase);
      const key = resolvePhaseKey(phase);
      const target = groups.find((grp) => grp.group === g);
      if (target) {
        target.stages.push({
          phase,
          key,
          shortLabel: getShortStageLabel(phase.phase_name, phase.phase_ordinal),
        });
      }
    });

    return groups.filter((g) => g.stages.length > 0);
  }, [phaseRecords]);

  if (!phaseRecords || phaseRecords.length === 0) {
    return (
      <div className="p-3 text-xs text-app-muted text-center bg-app-surface rounded-lg border border-app-border">
        No phase records available for this run.
      </div>
    );
  }

  const handleStageClick = (key: string, phase: PhaseStatus) => {
    if (onSelectPhase) {
      onSelectPhase(key);
    }
    if (onInspectConfig) {
      onInspectConfig(phase);
    }
  };

  const handleOverviewClick = () => {
    if (onSelectPhase) {
      onSelectPhase(null);
    }
  };

  const isOverviewSelected = !selectedPhaseKey && (selectedPhaseOrdinal === null || selectedPhaseOrdinal === undefined || selectedPhaseOrdinal === 0);

  return (
    <div className="flex flex-col space-y-2 p-2.5 bg-app-surface rounded-lg border border-app-border text-xs shadow-xs">
      <div className="flex items-center justify-between pb-1.5 border-b border-app-border/60">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-app-heading text-[11px] uppercase tracking-wider">
            Pipeline Lifecycle Flow
          </span>
          <span className="text-[11px] text-app-muted font-mono">
            {phaseRecords.length} dynamic stages across {groupedPhases.length} phases
          </span>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-app-muted">
          {showOverviewOption && (
            <button
              type="button"
              onClick={handleOverviewClick}
              className={`px-2 py-0.5 rounded text-[11px] font-medium transition-all cursor-pointer flex items-center gap-1.5 ${
                isOverviewSelected
                  ? "bg-blue-600 text-white shadow-xs font-semibold"
                  : "bg-app-subtle hover:bg-app-subtle/80 text-app-heading border border-app-border"
              }`}
              title="View full run overview, global cumulative yield (L1–L4), and overall graph metrics"
            >
              <Layers className="w-3 h-3" />
              <span>Run Overview (L1–L4)</span>
            </button>
          )}
          <span className="hidden md:inline text-app-muted">
            Click any stage chip to isolate its provenance & artifacts
          </span>
        </div>
      </div>

      {/* Grouped Dynamic Pipeline Rail */}
      <div className="flex items-center gap-2 overflow-x-auto py-1 scrollbar-none">
        {groupedPhases.map((grp, groupIdx) => {
          const groupTotalYield = grp.stages.reduce((acc, s) => acc + (s.phase.artifact_count || 0), 0);
          const hasRunning = grp.stages.some((s) => s.phase.status === "running");
          const allCompleted = grp.stages.every((s) => s.phase.status === "completed");

          return (
            <React.Fragment key={grp.group}>
              {/* Group Container Box */}
              <div
                className={`flex flex-col gap-1 p-1.5 rounded-lg border transition-all ${
                  hasRunning
                    ? "bg-blue-500/5 border-blue-500/30"
                    : "bg-app-subtle/40 border-app-border/80"
                }`}
              >
                {/* Group Header Badge */}
                <div className="flex items-center justify-between gap-2 px-1 text-[10px]">
                  <span className={`font-semibold tracking-wide ${grp.meta.color}`}>
                    {grp.meta.badgeLabel} ({grp.stages.length})
                  </span>
                  <span className="font-mono text-app-muted text-[9px]">
                    {groupTotalYield} items
                  </span>
                </div>

                {/* Sub-steps / Dynamic Stage Chips */}
                <div className="flex items-center gap-1">
                  {grp.stages.map((stg) => {
                    const isSelected =
                      selectedPhaseKey === stg.key ||
                      (selectedPhaseOrdinal !== null &&
                        selectedPhaseOrdinal !== undefined &&
                        selectedPhaseOrdinal === stg.phase.phase_ordinal);
                    const isZeroYield =
                      stg.phase.status === "completed" && stg.phase.artifact_count === 0;
                    const durationStr = formatDuration(stg.phase.duration_seconds);

                    return (
                      <button
                        key={stg.key}
                        type="button"
                        onClick={() => handleStageClick(stg.key, stg.phase)}
                        title={`${stg.phase.phase_name}\nStatus: ${stg.phase.status}\nDuration: ${durationStr || "—"}\nYield: ${stg.phase.artifact_count} artifacts${stg.phase.reused ? " (Reused)" : ""}`}
                        className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-all cursor-pointer whitespace-nowrap border ${
                          isSelected
                            ? "bg-blue-600 text-white border-blue-600 shadow-xs font-semibold ring-1 ring-blue-500/40"
                            : isZeroYield
                            ? "bg-app-bg text-app-muted border-app-border hover:border-app-muted"
                            : stg.phase.status === "completed"
                            ? "bg-app-bg text-app-heading border-app-border hover:border-blue-400 hover:bg-app-subtle/60"
                            : stg.phase.status === "running"
                            ? "bg-blue-500/10 text-blue-500 border-blue-500/30 animate-pulse"
                            : stg.phase.status === "failed"
                            ? "bg-red-500/10 text-red-500 border-red-500/30"
                            : "bg-app-bg text-app-muted border-app-border"
                        }`}
                      >
                        {/* Status Icon or Ordinal Indicator */}
                        <span
                          className={`flex items-center justify-center w-4 h-4 rounded text-[9px] font-mono font-bold shrink-0 ${
                            isSelected
                              ? "bg-white/20 text-white"
                              : stg.phase.status === "completed"
                              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                              : stg.phase.status === "running"
                              ? "bg-blue-500 text-white"
                              : stg.phase.status === "failed"
                              ? "bg-red-500 text-white"
                              : "bg-app-subtle text-app-muted"
                          }`}
                        >
                          {stg.phase.phase_ordinal}
                        </span>

                        <span className="truncate max-w-[130px] sm:max-w-[150px]">
                          {stg.shortLabel}
                        </span>

                        {/* Artifact Count / Duration pill */}
                        <div className="flex items-center gap-1 font-mono text-[9px] opacity-80 shrink-0">
                          <span>{stg.phase.artifact_count}</span>
                          {stg.phase.reused && (
                            <span title="Reused from cache" className="inline-flex">
                              <RotateCcw
                                className={`w-2.5 h-2.5 shrink-0 ${
                                  isSelected ? "text-cyan-200" : "text-cyan-500"
                                }`}
                              />
                            </span>
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Connecting Inter-group Arrow */}
              {groupIdx < groupedPhases.length - 1 && (
                <div className="flex items-center text-app-muted/50 shrink-0 px-0.5">
                  <ChevronRight className="w-4 h-4" />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
