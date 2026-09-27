import React, { useState, useMemo } from "react";
import { useRunsStore } from "../store/runsStore";
import { LogConsole } from "../console/LogConsole";
import {
  resolvePhaseConfig,
  getAvailablePhaseTabs,
  resolvePhaseKey,
} from "./phaseConfig/phaseConfigResolver";
import {
  AlertCircle,
  Clock,
  Cpu,
  Layers,
  CheckCircle2,
  PlayCircle,
  XCircle,
  FileText,
  RotateCcw,
  ExternalLink,
  Copy,
  Check,
  Calendar,
  GitFork,
  Sliders,
  Database,
  GitCompare,
  Network,
  ChevronDown,
  ChevronUp,
  Square,
  Play,
  Sparkles,
  Terminal,
  Loader2,
  Brain,
  MoreHorizontal,
  Download,
} from "lucide-react";
import { RunStatus, GraphView } from "../api/types";
import { api } from "../api/client";
import { useDiffStore } from "../store/diffStore";
import { useNavigationStore } from "../store/navigationStore";
import { useEvaluationStore } from "../store/evaluationStore";
import { RunCompareModal } from "./RunCompareModal";
import { ExecuteEvaluationModal } from "./evaluation/components/ExecuteEvaluationModal";
import { useViewOverlayStore } from "../store/viewOverlayStore";
import { resolveStageArtifacts } from "./stageModel";
import {
  StageArtifactsView,
  StageTripleItem,
  INITIAL_STAGE_TRIPLES,
} from "./StageArtifactsView";
import { transformGraphToTriples } from "./assertionTransformer";
import { StageProvenancePane } from "./StageProvenancePane";
import { RunOverviewView, type PredicateSchemaRow } from "./RunOverviewView";
import { ResizablePanel } from "./ResizablePanel";
import { RunDiagnosticInspectorRail } from "./RunDiagnosticInspectorRail";
import { useProjectSettingsStore } from "../store/projectSettingsStore";
import { Coins } from "lucide-react";

const GenerationCostsView = React.lazy(() =>
  import("./GenerationCostsView").then((m) => ({ default: m.GenerationCostsView }))
);

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return "";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}h ${rm}m`;
};

const getStatusBadge = (status: RunStatus) => {
  switch (status) {
    case "completed":
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 whitespace-nowrap">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
          Completed
        </span>
      );
    case "running":
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-blue-600 dark:text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20 whitespace-nowrap">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping shrink-0" />
          Running
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-rose-600 dark:text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20 whitespace-nowrap">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
          Failed
        </span>
      );
    case "aborted":
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-amber-600 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20 whitespace-nowrap">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
          Aborted
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-app-muted bg-app-subtle px-2 py-0.5 rounded-full border border-app-border whitespace-nowrap capitalize">
          <span className="w-1.5 h-1.5 rounded-full bg-app-muted shrink-0" />
          {status}
        </span>
      );
  }
};

export interface RunDetailViewProps {
  onNavigateToConfig?: () => void;
  onNavigateToGraph?: () => void;
}

export const RunDetailView: React.FC<RunDetailViewProps> = ({
  onNavigateToConfig,
  onNavigateToGraph,
}) => {
  const {
    selectedRunDetail,
    isLoadingDetail,
    events,
    cancelCurrentRun,
    refreshActiveRun,
    liveProgress,
    subtasks,
    isCancellingRun,
    cancelError,
    forkRun,
    selectedPhaseKey,
    setSelectedPhaseKey,
  } = useRunsStore();
  const { setIsCompareModalOpen } = useDiffStore();
  const { setActiveTab } = useNavigationStore();
  const { setActiveMode, setTargetRunId } = useEvaluationStore();
  const { setActiveLens } = useViewOverlayStore();
  const { stageRefreshIntervalSeconds, openProjectSettings } = useProjectSettingsStore();
  const [copiedId, setCopiedId] = useState(false);
  const [isOverflowOpen, setIsOverflowOpen] = useState(false);
  const [isRunConfigOpen, setIsRunConfigOpen] = useState(false);
  const [isEvaluateModalOpen, setIsEvaluateModalOpen] = useState(false);
  const [phaseViewMode, setPhaseViewMode] = useState<"artifacts" | "config">("artifacts");

  // State for fetched run graph data
  const [graphData, setGraphData] = useState<GraphView | null>(null);
  const [isLoadingGraph, setIsLoadingGraph] = useState(false);

  // Fetch real GraphView whenever selectedRunDetail.run_id changes
  React.useEffect(() => {
    const runId = selectedRunDetail?.run_id;
    if (!runId) {
      setGraphData(null);
      return;
    }
    let cancelled = false;
    setIsLoadingGraph(true);
    api
      .getRunGraph(runId, 1000, false)
      .then((data) => {
        if (!cancelled) {
          setGraphData(data);
          setIsLoadingGraph(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.warn("Could not load run graph:", err);
          setGraphData(null);
          setIsLoadingGraph(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedRunDetail?.run_id]);

  // Derived real triples across the entire run
  const allTriples = useMemo(() => {
    const converted = transformGraphToTriples(graphData);
    return converted.length > 0 ? converted : INITIAL_STAGE_TRIPLES;
  }, [graphData]);

  // Track status overrides so manual triage updates state
  const [statusOverrides, setStatusOverrides] = useState<Record<string, "valid" | "flagged" | "quarantine">>({});

  const triplesWithOverrides = useMemo(() => {
    return allTriples.map((t) => {
      if (statusOverrides[t.id]) {
        return { ...t, status: statusOverrides[t.id] };
      }
      return t;
    });
  }, [allTriples, statusOverrides]);

  // Filter triples by active phase for StageArtifactsView
  const phaseTriples = useMemo(() => {
    if (!selectedPhaseKey) return triplesWithOverrides;
    const pKey = selectedPhaseKey.toLowerCase();
    const phaseFiltered = triplesWithOverrides.filter((t) => t.phaseKey === pKey);
    if (phaseFiltered.length > 0) return phaseFiltered;
    // If graph has real triples but none for this stage, return empty array rather than fallback
    if (graphData && graphData.edges && graphData.edges.length > 0) {
      return [];
    }
    return triplesWithOverrides;
  }, [selectedPhaseKey, triplesWithOverrides, graphData]);

  // State for active stage triple inspection synchronized across center canvas and right inspector
  const [activeTriple, setActiveTriple] = useState<StageTripleItem | null>(null);
  const [selectedPredicate, setSelectedPredicate] = useState<PredicateSchemaRow | null>(null);
  const [selectionNonce, setSelectionNonce] = useState<number>(0);
  const [inspectorRailTab, setInspectorRailTab] = useState<"assertion" | "predicate" | "invariants" | "telemetry">(
    "assertion"
  );

  const handleSelectPredicate = (pred: PredicateSchemaRow) => {
    setSelectedPredicate(pred);
    setInspectorRailTab("predicate");
    setSelectionNonce((n) => n + 1);
  };

  const handleSelectTriple = (triple: StageTripleItem) => {
    setActiveTriple(triple);
    setSelectedPredicate(null);
    setInspectorRailTab("assertion");
    setSelectionNonce((n) => n + 1);
  };

  React.useEffect(() => {
    const sourceList = selectedPhaseKey ? phaseTriples : triplesWithOverrides;
    if (sourceList.length > 0) {
      if (!activeTriple || !sourceList.some((t) => t.id === activeTriple.id)) {
        setActiveTriple(sourceList[0]);
      }
    } else {
      setActiveTriple(null);
    }
  }, [selectedPhaseKey, phaseTriples, triplesWithOverrides]);

  const handleUpdateTripleStatus = (tripleId: string, nextStatus: "valid" | "flagged" | "quarantine") => {
    setStatusOverrides((prev) => ({ ...prev, [tripleId]: nextStatus }));
    if (activeTriple?.id === tripleId) {
      setActiveTriple((prev) => (prev ? { ...prev, status: nextStatus } : null));
    }
  };

  const handleUpdatePredicateStatus = (predicateName: string, status: "Valid" | "Flagged" | "Quarantined") => {
    if (selectedPredicate && selectedPredicate.predicate === predicateName) {
      setSelectedPredicate((prev) => (prev ? { ...prev, status } : null));
    }
  };

  const isRunActive = selectedRunDetail?.status === "running";

  // Derive active running phase key from live progress or running phase record
  const liveRunningPhaseKey = useMemo(() => {
    if (liveProgress?.phaseName) {
      return resolvePhaseKey({ phase_name: liveProgress.phaseName });
    }
    const runningRec = (selectedRunDetail?.phase_records || []).find((p) => p.status === "running");
    if (runningRec) {
      return resolvePhaseKey(runningRec);
    }
    return null;
  }, [liveProgress?.phaseName, selectedRunDetail?.phase_records]);

  // When a run starts or is loaded in running state, align selected stage with the active running stage
  React.useEffect(() => {
    if (isRunActive && liveRunningPhaseKey) {
      if (selectedPhaseKey === "phase2") {
        const p2 = selectedRunDetail?.phase_records?.find((p) => resolvePhaseKey(p) === "phase2");
        if (p2?.status !== "running") {
          setSelectedPhaseKey(liveRunningPhaseKey);
        }
      }
    }
  }, [isRunActive, liveRunningPhaseKey]);

  // Auto-refresh stage statistics and yields at configurable interval during live execution
  React.useEffect(() => {
    if (!isRunActive) return;
    const intervalMs = Math.max(5, stageRefreshIntervalSeconds || 30) * 1000;
    const timer = setInterval(() => {
      refreshActiveRun();
    }, intervalMs);
    return () => clearInterval(timer);
  }, [isRunActive, stageRefreshIntervalSeconds, refreshActiveRun]);

  const [inspectorTab, setInspectorTab] = useState<"params" | "prompts" | "raw" | "validation">("params");

  // Available phase tabs from config snapshot & records
  const availablePhaseTabs = useMemo(() => {
    return getAvailablePhaseTabs(
      selectedRunDetail?.config_snapshot || {},
      selectedRunDetail?.phase_records || []
    );
  }, [selectedRunDetail?.config_snapshot, selectedRunDetail?.phase_records]);

  // Active phase record for selected stage
  const activePhaseRecord = useMemo(() => {
    if (!selectedPhaseKey) return undefined;
    return selectedRunDetail?.phase_records?.find(
      (p) => resolvePhaseKey(p) === selectedPhaseKey
    );
  }, [selectedPhaseKey, selectedRunDetail?.phase_records]);

  // Selected phase descriptor for inspector
  const activePhaseDescriptor = useMemo(() => {
    if (!selectedPhaseKey) return null;
    const targetRecord = activePhaseRecord;
    const target = targetRecord || {
      phase_name: availablePhaseTabs.find((t) => t.key === selectedPhaseKey)?.label || selectedPhaseKey,
      phase_ordinal: availablePhaseTabs.find((t) => t.key === selectedPhaseKey)?.ordinal || 1,
      key: selectedPhaseKey,
    };
    return resolvePhaseConfig(target, selectedRunDetail?.config_snapshot || {});
  }, [selectedPhaseKey, activePhaseRecord, selectedRunDetail?.config_snapshot, availablePhaseTabs]);

  // Resolved stage artifacts report for selected stage
  const stageArtifactsReport = useMemo(() => {
    if (!selectedPhaseKey) return null;
    return resolveStageArtifacts(
      selectedPhaseKey,
      activePhaseRecord,
      selectedRunDetail?.artifact_counts_by_kind,
      selectedRunDetail?.status
    );
  }, [selectedPhaseKey, activePhaseRecord, selectedRunDetail?.artifact_counts_by_kind, selectedRunDetail?.status]);

  const cleanStageName = useMemo(() => {
    if (!stageArtifactsReport?.stageName) return "";
    return stageArtifactsReport.stageName.replace(/^Phase\s*\d+\s*[:\-–]\s*/i, "");
  }, [stageArtifactsReport?.stageName]);

  // Count errors and warnings in events for Dynamic Telemetry Drawer
  // Automatically open drawer if errors or warnings > 0, otherwise auto-hide
  const { errorCount, warnCount } = useMemo(() => {
    let errs = 0;
    let warns = 0;
    for (const ev of events) {
      if (ev.level === "error") errs++;
      else if (ev.level === "warning") warns++;
    }
    return { errorCount: errs, warnCount: warns };
  }, [events]);

  const [isLogDrawerOpen, setIsLogDrawerOpen] = useState<boolean>(errorCount > 0 || warnCount > 0);

  if (isLoadingDetail) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs text-app-muted">
        Loading run manifest...
      </div>
    );
  }

  if (!selectedRunDetail) {
    return (
      <div className="flex-1 flex items-center justify-center text-xs text-app-muted">
        Select a pipeline run from the left panel to inspect execution diagnostics and telemetry.
      </div>
    );
  }

  const failure = selectedRunDetail.failure;
  const durationStr = formatDuration(selectedRunDetail.duration_seconds);
  const reusedCount = selectedRunDetail.reused_phase_count ?? 0;
  const totalCount = selectedRunDetail.total_phase_count || 8;
  const reusePercent = totalCount > 0 ? Math.round((reusedCount / totalCount) * 100) : 0;

  const inputFiles = (selectedRunDetail.input_sources || []).map((src) => {
    const parts = src.split(/[/\\]/);
    return { name: parts[parts.length - 1] || src, path: src };
  });

  const llmModel = selectedRunDetail.models?.llm_model || "openai/gpt-4o-mini";
  const embModel = selectedRunDetail.models?.embedding_model || "sentence-transformers/all-MiniLM-L6-v2";
  const rrkModel = selectedRunDetail.models?.reranker_model || "Alibaba-NLP/gte-reranker-modernbert-base";

  const handleDrilldownToGraph = (lensId: string) => {
    setActiveLens(lensId);
    if (onNavigateToGraph) {
      onNavigateToGraph();
    }
  };

  const handleCopyRunId = () => {
    if (!selectedRunDetail) return;
    navigator.clipboard.writeText(selectedRunDetail.run_id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 1800);
  };

  const handleExportManifest = () => {
    if (!selectedRunDetail) return;
    const jsonStr = JSON.stringify(selectedRunDetail, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `run_${selectedRunDetail.run_id.slice(0, 8)}_manifest.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const createdDateStr = selectedRunDetail.created_at
    ? new Date(selectedRunDetail.created_at).toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  // Derive L1-L4 rollups for the persistent metric strip
  const counts = selectedRunDetail.artifact_counts_by_kind || {};
  const l1Total = (counts["document"] || 0) + (counts["chunk"] || 0);
  const l2Total =
    (counts["linked_entity"] || 0) +
    (counts["entity"] || 0) +
    (counts["mature_entity"] || 0) +
    (counts["entity_mention"] || 0) +
    (counts["local_relation"] || 0) +
    (counts["global_relation"] || 0) +
    (counts["canonicalization"] || 0);
  const l3Total =
    (counts["theory_atom"] || 0) +
    (counts["argument_component"] || 0) +
    (counts["theory_relation"] || 0) +
    (counts["argument_relation"] || 0);
  const l4Total = (counts["fusion_decision"] || 0) + (counts["fusion_cluster"] || 0);
  const totalArtifactCount = l1Total + l2Total + l3Total + l4Total;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg">
      {/* 1. Strict 44px Scientific Header Bar */}
      <div className="h-[44px] min-h-[44px] px-4 border-b border-app-border bg-app-surface dark:bg-app-bg flex items-center justify-between gap-3 text-xs shrink-0 select-none font-sans">
        {/* Left: Breadcrumb Context Anchor (Document Title + Status + Run Hash + Stage) */}
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {/* Document Title Anchor */}
          <div className="flex items-center gap-1.5 min-w-0 shrink-0">
            <FileText className="w-3.5 h-3.5 text-blue-500 shrink-0" />
            <span
              className="font-semibold text-app-heading text-[13px] tracking-tight truncate max-w-[200px] sm:max-w-[280px]"
              title={inputFiles[0]?.path || selectedRunDetail.primary_input || ""}
            >
              {inputFiles[0]?.name || selectedRunDetail.primary_input || "Corpus Document"}
            </span>
          </div>

          {/* Calm Dot Status Badge */}
          <div className="shrink-0">{getStatusBadge(selectedRunDetail.status)}</div>

          {/* Interactive Hash Chip with integrated Copy Feedback */}
          <button
            type="button"
            onClick={handleCopyRunId}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded font-mono text-[11px] text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer shrink-0 border border-transparent hover:border-app-border"
            title={`Click to copy full Run ID: ${selectedRunDetail.run_id}`}
          >
            <span>#{selectedRunDetail.run_id.slice(0, 8)}</span>
            {copiedId ? (
              <Check className="w-2.5 h-2.5 text-emerald-500 shrink-0" />
            ) : (
              <Copy className="w-2.5 h-2.5 opacity-50 shrink-0" />
            )}
          </button>

          {/* Subdued Stage Breadcrumb */}
          <div className="hidden md:flex items-center gap-1.5 text-[11px] text-app-muted min-w-0 truncate">
            <span className="text-app-border-subtle select-none">/</span>
            {selectedPhaseKey === "generations" ? (
              <span className="font-medium text-app-heading truncate">Generation & Costs</span>
            ) : selectedPhaseKey && stageArtifactsReport ? (
              <span className="font-medium text-app-heading truncate">
                P{stageArtifactsReport.stageOrdinal} · {cleanStageName}
                {phaseViewMode === "config" && (
                  <span className="text-app-muted font-normal"> / Spec</span>
                )}
              </span>
            ) : (
              <span className="font-medium text-app-heading truncate">Cumulative Overview</span>
            )}
          </div>
        </div>

        {/* Center/Right Telemetry (Quiet, tabular numerals, no heavy boxes) */}
        <div className="hidden lg:flex items-center gap-2.5 font-mono text-[11px] text-app-muted shrink-0">
          {!selectedPhaseKey && (
            <span className="tabular-nums">
              {(selectedRunDetail.artifact_count || totalArtifactCount).toLocaleString()} artifacts
            </span>
          )}

          {durationStr && (
            <span className="tabular-nums" title={`Total duration: ${durationStr}`}>
              {durationStr}
            </span>
          )}

          {selectedRunDetail.parent_run_id && (
            <span
              className="flex items-center gap-1"
              title={`Resumed from checkpoint: ${selectedRunDetail.parent_run_id}`}
            >
              <GitFork className="w-3 h-3 text-app-muted shrink-0" />
              <span>#{selectedRunDetail.parent_run_id.slice(0, 8)}</span>
            </span>
          )}
        </div>

        {/* Right: Consolidated Action Controls */}
        <div className="flex items-center gap-1.5 shrink-0 relative">
          {/* Run Config Popover Button (Quiet Icon Button) */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsRunConfigOpen(!isRunConfigOpen)}
              className={`h-7 w-7 flex items-center justify-center rounded border transition-colors cursor-pointer ${
                isRunConfigOpen
                  ? "bg-app-subtle text-app-heading border-app-border"
                  : "bg-app-surface border-app-border text-app-muted hover:text-app-heading hover:bg-app-subtle"
              }`}
              title="View Run Configuration & Inference Models"
            >
              <Cpu className="w-3.5 h-3.5 text-blue-500" />
            </button>

            {isRunConfigOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setIsRunConfigOpen(false)}
                />
                <div className="absolute right-0 top-full mt-1 w-80 p-3 rounded-md bg-app-surface border border-app-border shadow-lg z-50 text-xs animate-in fade-in zoom-in-95 duration-100 space-y-3">
                  <div className="flex items-center justify-between pb-1.5 border-b border-app-border">
                    <div className="flex items-center gap-1.5 font-semibold text-app-heading">
                      <Cpu className="w-3.5 h-3.5 text-blue-500" />
                      <span>Runtime Inference Models</span>
                    </div>
                    <span className="text-[10px] font-mono text-app-muted">Config Spec</span>
                  </div>

                  <div className="space-y-2 text-xs font-sans">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-app-muted shrink-0">Primary LLM:</span>
                      <span className="font-mono text-[11px] text-app-heading font-medium truncate text-right" title={llmModel}>
                        {llmModel}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-app-muted shrink-0">Embedding:</span>
                      <span className="font-mono text-[11px] text-app-muted truncate text-right" title={embModel}>
                        {embModel}
                      </span>
                    </div>
                    {rrkModel && (
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-app-muted shrink-0">Reranker:</span>
                        <span className="font-mono text-[11px] text-app-muted truncate text-right" title={rrkModel}>
                          {rrkModel}
                        </span>
                      </div>
                    )}
                    {selectedRunDetail.models?.thinking_level && (
                      <div className="flex items-center justify-between">
                        <span className="text-app-muted">Thinking Level:</span>
                        <span className="font-mono text-[10px] px-1.5 py-0.2 rounded bg-app-subtle border border-app-border text-app-heading font-semibold">
                          {selectedRunDetail.models.thinking_level}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="pt-2 border-t border-app-border/60 flex items-center justify-between text-[11px]">
                    <span className="text-app-muted font-mono">Run: {selectedRunDetail.run_id.slice(0, 8)}</span>
                    {onNavigateToConfig && (
                      <button
                        type="button"
                        onClick={() => {
                          setIsRunConfigOpen(false);
                          onNavigateToConfig();
                        }}
                        className="text-blue-600 dark:text-blue-400 hover:underline font-medium cursor-pointer"
                      >
                        Edit in Config Editor →
                      </button>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Export Manifest Quiet Icon Action */}
          <button
            type="button"
            onClick={handleExportManifest}
            className="h-7 w-7 flex items-center justify-center rounded border border-app-border bg-app-surface text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
            title="Export full run manifest telemetry JSON"
          >
            <Download className="w-3.5 h-3.5" />
          </button>

          {/* Secondary CTA: Open in Graph Explorer (Icon button) */}
          {onNavigateToGraph && (
            <button
              type="button"
              onClick={onNavigateToGraph}
              className="h-7 w-7 flex items-center justify-center rounded border border-app-border bg-app-surface text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="Open active run in Graph Explorer ↗"
            >
              <Network className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Primary Run Action: High-emphasis Accent Button for Run Pipeline or Cancel Run */}
          {selectedRunDetail.status === "running" || selectedRunDetail.status === "planned" ? (
            <button
              type="button"
              disabled={isCancellingRun}
              onClick={() => cancelCurrentRun()}
              className={`inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-white font-medium text-xs shadow-xs transition-all ${
                isCancellingRun
                  ? "bg-rose-800 opacity-70 cursor-not-allowed"
                  : "bg-rose-600 hover:bg-rose-500 cursor-pointer"
              }`}
              title="Cancel Current Pipeline Run"
            >
              {isCancellingRun ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Square className="w-3.5 h-3.5 fill-current" />
              )}
              <span>{isCancellingRun ? "Cancelling..." : "Cancel Run"}</span>
            </button>
          ) : (
            <>
              {selectedRunDetail.status === "completed" && (
                <button
                  type="button"
                  onClick={() => {
                    setTargetRunId(selectedRunDetail.run_id);
                    setActiveMode("execute");
                    setActiveTab("evaluation");
                  }}
                  className="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-md bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/30 text-xs font-semibold shadow-2xs transition-all cursor-pointer"
                  title="Evaluate this completed run in On-Demand Evaluation Studio"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Evaluate Run</span>
                </button>
              )}
              {onNavigateToConfig && (
                <button
                  type="button"
                  onClick={onNavigateToConfig}
                  className="inline-flex items-center gap-1.5 h-7 px-3 rounded-md bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-semibold text-xs shadow-sm transition-all cursor-pointer"
                  title="Configure and launch a new pipeline execution run"
                >
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Run Pipeline</span>
                </button>
              )}
            </>
          )}

          {/* Overflow Menu Button */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsOverflowOpen(!isOverflowOpen)}
              className="h-7 w-7 flex items-center justify-center rounded border border-app-border text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
              title="More Actions"
            >
              <MoreHorizontal className="w-3.5 h-3.5" />
            </button>

            {/* Overflow Dropdown Popover */}
            {isOverflowOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setIsOverflowOpen(false)}
                />
                <div className="absolute right-0 top-full mt-1 w-48 py-1 rounded-md bg-app-surface border border-app-border shadow-lg z-50 text-xs animate-in fade-in zoom-in-95 duration-100">
                  <button
                    type="button"
                    onClick={() => {
                      setIsOverflowOpen(false);
                      setTargetRunId(selectedRunDetail.run_id);
                      setActiveMode("execute");
                      setActiveTab("evaluation");
                    }}
                    className="w-full px-3 py-1.5 text-left text-app-text hover:text-app-heading hover:bg-app-subtle flex items-center gap-2 cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-blue-500" />
                    <span>Evaluate Run...</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setIsOverflowOpen(false);
                      setIsCompareModalOpen(true);
                    }}
                    className="w-full px-3 py-1.5 text-left text-app-text hover:text-app-heading hover:bg-app-subtle flex items-center gap-2 cursor-pointer"
                  >
                    <GitCompare className="w-3.5 h-3.5 text-purple-500" />
                    <span>Compare Runs...</span>
                  </button>

                  {onNavigateToConfig && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsOverflowOpen(false);
                        if (selectedRunDetail) {
                          forkRun(selectedRunDetail);
                        }
                        onNavigateToConfig();
                      }}
                      className="w-full px-3 py-1.5 text-left text-app-text hover:text-app-heading hover:bg-app-subtle flex items-center gap-2 cursor-pointer"
                    >
                      <Sliders className="w-3.5 h-3.5 text-blue-500" />
                      <span>Fork for New Run</span>
                    </button>
                  )}

                  {selectedRunDetail.langfuse_url && (
                    <a
                      href={selectedRunDetail.langfuse_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={() => setIsOverflowOpen(false)}
                      className="w-full px-3 py-1.5 text-left text-app-text hover:text-app-heading hover:bg-app-subtle flex items-center gap-2 cursor-pointer"
                    >
                      <ExternalLink className="w-3.5 h-3.5 text-amber-500" />
                      <span>Inspect in Langfuse ↗</span>
                    </a>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Failure Diagnostic Alert Box if Run Failed */}
      {failure && (
        <div className="p-3 border-b border-red-500/30 bg-red-500/10 text-xs flex flex-col space-y-1.5 shrink-0">
          <div className="flex items-center space-x-2 text-red-500 dark:text-red-400 font-semibold">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>
              {failure.title} ({failure.type})
            </span>
          </div>
          {failure.detail && <p className="text-app-text">{failure.detail}</p>}
        </div>
      )}

      {cancelError && (
        <div className="p-3 border-b border-red-500/30 bg-red-500/10 text-xs flex items-center space-x-2 text-red-500 dark:text-red-400 shrink-0">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{cancelError}</span>
        </div>
      )}

      {/* 2. Fluid Center Canvas + Docked Right Diagnostic Inspector Rail (340px) */}
      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* Fluid Center Canvas (100% of remaining width) */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-app-bg">
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-app-bg">
            {selectedPhaseKey === "generations" ? (
              <React.Suspense
                fallback={
                  <div className="flex items-center justify-center h-full text-xs text-app-muted">
                    Loading Generation Costs...
                  </div>
                }
              >
                <GenerationCostsView
                  runId={selectedRunDetail.run_id}
                  langfuseUrl={selectedRunDetail.langfuse_url}
                  fallbackLlmModel={llmModel}
                  onOpenSettings={openProjectSettings}
                />
              </React.Suspense>
            ) : selectedPhaseKey && (stageArtifactsReport || activePhaseDescriptor) ? (
              phaseViewMode === "config" ? (
                activePhaseDescriptor ? (
                  <StageProvenancePane
                    descriptor={activePhaseDescriptor}
                    phaseRecord={activePhaseRecord}
                    inspectorTab={inspectorTab}
                    onTabChange={setInspectorTab}
                    llmModel={llmModel}
                    embModel={embModel}
                    rrkModel={rrkModel}
                    phaseViewMode={phaseViewMode}
                    onPhaseViewModeChange={setPhaseViewMode}
                    lensId={stageArtifactsReport?.lensId}
                    lensName={stageArtifactsReport?.lensName}
                    onDrilldownToGraph={handleDrilldownToGraph}
                  />
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-xs text-app-muted">
                    <Sliders className="w-8 h-8 opacity-30 mb-2" />
                    <span className="font-semibold text-app-heading text-sm">Run Configuration Spec</span>
                    <p className="max-w-xs text-[11px] mt-1">
                      No configuration spec available for this stage.
                    </p>
                  </div>
                )
              ) : stageArtifactsReport ? (
                <StageArtifactsView
                  report={stageArtifactsReport}
                  onDrilldownToGraph={handleDrilldownToGraph}
                  primaryInputName={inputFiles[0]?.name || selectedRunDetail.primary_input || undefined}
                  isRunActive={isRunActive}
                  isStageRunning={
                    isRunActive &&
                    (liveRunningPhaseKey === selectedPhaseKey || activePhaseRecord?.status === "running")
                  }
                  refreshIntervalSeconds={stageRefreshIntervalSeconds}
                  onManualRefresh={() => refreshActiveRun()}
                  phaseViewMode={phaseViewMode}
                  onPhaseViewModeChange={setPhaseViewMode}
                  selectedTripleId={activeTriple?.id}
                  onSelectTripleId={(id) => {
                    const match = (phaseTriples.length > 0 ? phaseTriples : triplesWithOverrides).find((t) => t.id === id);
                    if (match) {
                      setActiveTriple(match);
                      setSelectedPredicate(null);
                      setInspectorRailTab("assertion");
                      setSelectionNonce((n) => n + 1);
                    }
                  }}
                  onActiveTripleChange={(triple) => setActiveTriple(triple)}
                  triples={phaseTriples}
                  onUpdateStatus={handleUpdateTripleStatus}
                  graphData={graphData}
                />
              ) : null
            ) : (
              <RunOverviewView
                artifactCountsByKind={selectedRunDetail.artifact_counts_by_kind}
                totalArtifactCount={selectedRunDetail.artifact_count}
                sizeBytes={selectedRunDetail.size_bytes}
                durationSeconds={selectedRunDetail.duration_seconds}
                onDrilldownToGraph={handleDrilldownToGraph}
                onSelectPhase={(key) => setSelectedPhaseKey(key)}
                llmModel={llmModel}
                embModel={embModel}
                primaryInput={inputFiles[0]?.name || selectedRunDetail.primary_input || undefined}
                graphData={graphData}
                triples={triplesWithOverrides}
                activeTriple={activeTriple}
                selectedPredicate={selectedPredicate}
                onSelectPredicate={handleSelectPredicate}
                onSelectTriple={handleSelectTriple}
                onUpdateTripleStatus={handleUpdateTripleStatus}
              />
            )}
          </div>
        </div>

        {/* Docked Right Rail: RunDiagnosticInspectorRail (360px default) */}
        <ResizablePanel
          side="right"
          storageKey="glp-studio-run-inspector-rail-width"
          defaultWidth={360}
          minWidth={320}
          maxWidth={520}
          collapsible={true}
          collapseThreshold={120}
          className="!bg-app-surface dark:!bg-app-rail !border-l !border-app-border z-10"
        >
          <RunDiagnosticInspectorRail
            selectedRunDetail={selectedRunDetail}
            selectedPhaseKey={selectedPhaseKey}
            activePhaseRecord={activePhaseRecord}
            stageReport={stageArtifactsReport}
            totalArtifactCount={selectedRunDetail.artifact_count}
            sizeBytes={selectedRunDetail.size_bytes}
            durationSeconds={selectedRunDetail.duration_seconds}
            reusedCount={reusedCount}
            totalPhaseCount={totalCount}
            reusePercent={reusePercent}
            llmModel={llmModel}
            embModel={embModel}
            rrkModel={rrkModel}
            thinkingLevel={selectedRunDetail.models?.thinking_level}
            liveProgress={liveProgress}
            subtasks={subtasks}
            isRunActive={isRunActive}
            onSelectPhase={(phaseKey) => setSelectedPhaseKey(phaseKey)}
            activeTriple={activeTriple}
            selectedPredicate={selectedPredicate}
            selectionNonce={selectionNonce}
            onUpdateTripleStatus={handleUpdateTripleStatus}
            onUpdatePredicateStatus={handleUpdatePredicateStatus}
            primaryInputName={inputFiles[0]?.name || selectedRunDetail.primary_input || undefined}
            onDrilldownToGraph={handleDrilldownToGraph}
            activeTab={inspectorRailTab}
            onActiveTabChange={setInspectorRailTab}
          />
        </ResizablePanel>
      </div>

      {/* 3. Dynamic Telemetry Drawer: Full-width docked bar at bottom */}
      <div className="border-t border-app-border shrink-0 transition-all bg-app-bg">
        <button
          type="button"
          onClick={() => setIsLogDrawerOpen(!isLogDrawerOpen)}
          className={`w-full px-4 py-2 flex items-center justify-between transition-colors cursor-pointer text-xs ${
            errorCount > 0
              ? "bg-red-500/10 text-red-500"
              : warnCount > 0
              ? "bg-amber-500/10 text-amber-500"
              : "bg-transparent hover:bg-app-subtle/50"
          }`}
        >
          <div className="flex items-center gap-2 min-w-0">
            <Terminal className="w-3.5 h-3.5 text-app-muted shrink-0" />
            <span className="font-medium text-app-heading">
              Execution Logs & Diagnostics
            </span>
            <span className="text-[11px] text-app-muted font-mono">
              ({errorCount} error{errorCount === 1 ? "" : "s"}, {warnCount} warning{warnCount === 1 ? "" : "s"})
            </span>
            {errorCount === 0 && warnCount === 0 && (
              <span className="text-[10px] text-emerald-500 font-mono">(Clean Run)</span>
            )}
          </div>

          <div className="flex items-center gap-1 text-app-muted">
            <span className="text-[11px]">{isLogDrawerOpen ? "Collapse" : "Expand"}</span>
            {isLogDrawerOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </div>
        </button>

        {isLogDrawerOpen && (
          <div className="border-t border-app-border">
            <LogConsole resizable={true} />
          </div>
        )}
      </div>

      {/* Run Comparison Modal */}
      <RunCompareModal onNavigateToGraph={onNavigateToGraph} />

      {/* On-Demand Evaluation Modal */}
      <ExecuteEvaluationModal
        isOpen={isEvaluateModalOpen}
        onClose={() => setIsEvaluateModalOpen(false)}
        defaultRunId={selectedRunDetail.run_id}
      />
    </div>
  );
};
