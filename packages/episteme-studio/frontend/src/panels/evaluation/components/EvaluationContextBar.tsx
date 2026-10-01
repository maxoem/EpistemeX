import React, { useState, useMemo } from "react";
import {
  ChevronDown,
  Download,
  Eye,
  EyeOff,
  Play,
  RefreshCw,
  Wrench,
  CheckCircle2,
  XCircle,
  TriangleAlert,
  Clock,
  Award,
  Plus,
  Search,
  Copy,
  FileCode,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { WorkspaceContextBar, BreadcrumbItem } from "../../../shell/navigation";
import { ExportReportModal } from "./ExportReportModal";
import { ExecuteEvaluationModal } from "./ExecuteEvaluationModal";
import { PromoteToGoldModal } from "../catalog/PromoteToGoldModal";
import { RegisterBenchmarkModal } from "../catalog/RegisterBenchmarkModal";
import { openPhasePromptInExecution } from "./ActionableHookPill";
import type { EvaluationOutcome } from "../../../api/types";

export interface EvaluationContextBarProps {
  isSidebarCollapsed: boolean;
  onExpandSidebar: () => void;
  onOpenConfigEditor?: () => void;
}

const SUB_TAB_TITLES: Record<string, string> = {
  canvas: "Topological Canvas",
  epistemics: "Epistemic TheoryNet",
  adjudication: "Adjudication Workspace",
  calibration: "Calibration Lab",
  grounding: "Document Grounding",
  retrieval: "Retrieval & Stress",
};

const MODE_TITLES: Record<string, string> = {
  catalog: "Benchmark Catalog",
  leaderboard: "Leaderboard Studio",
  inspector: "Run Inspector",
  longitudinal: "Longitudinal Studio",
  execute: "Execute Evaluation",
};

export const EvaluationContextBar: React.FC<EvaluationContextBarProps> = ({
  isSidebarCollapsed,
  onExpandSidebar,
  onOpenConfigEditor,
}) => {
  const {
    activeMode,
    setActiveMode,
    activeSubTab,
    reports,
    activeReportId,
    activeReport,
    setActiveReportId,
    benchmarks,
    selectedBenchmarkId,
    setSelectedBenchmarkId,
    fetchReports,
    fetchBenchmarks,
    stagedAdjudications,
    optimisticScalarDeltas,
    setTargetRunId,
    isLoading,
    catalogViewMode,
    setCatalogViewMode,
    catalogSearchQuery,
    setCatalogSearchQuery,
    catalogTaskFilter,
    setCatalogTaskFilter,
    isPromoteModalOpen,
    setIsPromoteModalOpen,
    isRegisterModalOpen,
    setIsRegisterModalOpen,
    isLinterRailOpen,
    setIsLinterRailOpen,
  } = useEvaluationStore();

  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isExecuteModalOpen, setIsExecuteModalOpen] = useState(false);
  const [copyCodeFeedback, setCopyCodeFeedback] = useState(false);

  const activeBenchmark = useMemo(() => {
    if (!benchmarks.length) return undefined;
    if (!selectedBenchmarkId) return benchmarks[0];
    return benchmarks.find((b) => b.id === selectedBenchmarkId) || benchmarks[0];
  }, [benchmarks, selectedBenchmarkId]);

  const handleCopyCli = (benchmarkId: string) => {
    navigator.clipboard.writeText(`episteme eval --benchmark ${benchmarkId}`);
    setCopyCodeFeedback(true);
    setTimeout(() => setCopyCodeFeedback(false), 2000);
  };

  const [showKpiStrip, setShowKpiStrip] = useState(() => {
    try {
      return localStorage.getItem("episteme-header-kpi-visible") !== "false";
    } catch {
      return true;
    }
  });

  const toggleKpiStrip = () => {
    setShowKpiStrip((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("episteme-header-kpi-visible", String(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  const METRIC_LABELS: Record<string, string> = {
    f1: "F₁",
    macro_f1: "Macro F₁",
    delta_star: "δ*",
    tenability: "Tenability",
    ece: "ECE",
    mrr: "MRR",
    mcc: "MCC",
    pfs: "PFS",
    ag_iou: "IoU",
    edge_fidelity: "Fidelity",
    poset_f1: "Hierarchy F₁",
    poset_reachability_f1: "Reach F₁",
    polarity_accuracy: "Polarity",
    precision: "Prec",
    recall: "Rec",
  };

  const stagedCount = stagedAdjudications.size;

  const displayMetrics = useMemo(() => {
    if (!activeReport?.key_metrics) return [];
    const km = activeReport.key_metrics;

    const preferredOrder = [
      "f1",
      "macro_f1",
      "pfs",
      "mcc",
      "delta_star",
      "tenability",
      "ag_iou",
      "edge_fidelity",
      "poset_f1",
    ];

    const selectedKeys: string[] = [];
    for (const key of preferredOrder) {
      if (km[key] !== undefined && km[key] !== null) {
        if (!selectedKeys.includes(key)) {
          selectedKeys.push(key);
        }
      }
      if (selectedKeys.length >= 3) break;
    }

    if (selectedKeys.length < 3) {
      for (const [key, val] of Object.entries(km)) {
        if (!selectedKeys.includes(key) && typeof val === "number") {
          selectedKeys.push(key);
        }
        if (selectedKeys.length >= 3) break;
      }
    }

    return selectedKeys.map((k) => ({
      key: k,
      label: METRIC_LABELS[k] || k.replace(/_/g, " ").toUpperCase(),
      value: km[k],
      delta: k === "f1" || k === "macro_f1" ? optimisticScalarDeltas.f1 : 0,
    }));
  }, [activeReport?.key_metrics, optimisticScalarDeltas.f1]);

  const renderOutcomeBadge = (outcome: EvaluationOutcome | string) => {
    switch (outcome.toLowerCase()) {
      case "pass":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400 border border-emerald-500/25">
            <CheckCircle2 className="w-3 h-3" />
            PASS
          </span>
        );
      case "fail":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/10 text-rose-500/90 dark:bg-rose-500/15 dark:text-rose-400/90 border border-rose-500/25">
            <XCircle className="w-3 h-3" />
            FAIL
          </span>
        );
      case "warning":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400 border border-amber-500/25">
            <TriangleAlert className="w-3 h-3" />
            WARN
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-500/10 text-zinc-500 dark:bg-zinc-400 border border-zinc-500/25">
            <Clock className="w-3 h-3" />
            {outcome.toUpperCase()}
          </span>
        );
    }
  };

  // Breadcrumbs based on activeMode, catalogViewMode, and activeSubTab
  const breadcrumbs: BreadcrumbItem[] = useMemo(() => {
    const crumbs: BreadcrumbItem[] = [
      {
        label: "Evaluation",
        onClick: () => {
          setActiveMode("catalog");
          setCatalogViewMode("table");
        },
      },
    ];

    if (activeMode === "catalog") {
      if (catalogViewMode === "detail" && activeBenchmark) {
        crumbs.push({
          label: "Benchmark Catalog",
          onClick: () => setCatalogViewMode("table"),
        });
        crumbs.push({
          label: activeBenchmark.name,
          active: true,
        });
      } else {
        crumbs.push({
          label: "Benchmark Catalog",
          active: true,
        });
      }
      return crumbs;
    }

    crumbs.push({
      label: MODE_TITLES[activeMode] || "Workspace",
      onClick:
        activeMode === "inspector"
          ? () => setActiveMode("inspector")
          : undefined,
    });

    if (activeMode === "inspector" && activeSubTab) {
      crumbs.push({
        label: SUB_TAB_TITLES[activeSubTab] || activeSubTab,
      });
    }

    return crumbs;
  }, [
    activeMode,
    activeSubTab,
    catalogViewMode,
    activeBenchmark,
    setActiveMode,
    setCatalogViewMode,
  ]);

  // Context Selector: Controls what dataset/run is being queried
  const contextSelector = useMemo(() => {
    if (activeMode === "inspector") {
      if (reports.length === 0) return null;
      return (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-app-muted font-medium shrink-0">
            Evaluation Run:
          </span>
          <div className="relative flex items-center">
            <select
              value={activeReportId || ""}
              onChange={(e) => setActiveReportId(e.target.value)}
              className="h-7 pl-2.5 pr-7 py-0.5 rounded bg-app-bg border border-app-border text-xs font-medium text-app-heading focus:outline-none focus:border-blue-500 cursor-pointer appearance-none max-w-[260px] truncate"
              title="Switch Active Evaluation Run"
            >
              {reports.map((r) => {
                const f1 = r.key_metrics?.f1 ?? r.key_metrics?.macro_f1;
                return (
                  <option key={r.evaluation_id} value={r.evaluation_id}>
                    {r.evaluation_id} ({r.outcome.toUpperCase()}
                    {f1 !== undefined ? ` · F₁ ${f1.toFixed(3)}` : ""})
                  </option>
                );
              })}
            </select>
            <ChevronDown className="w-3.5 h-3.5 absolute right-2 text-app-muted pointer-events-none" />
          </div>
          {activeReport && renderOutcomeBadge(activeReport.outcome)}
        </div>
      );
    }

    if (activeMode === "catalog") {
      if (catalogViewMode === "table") {
        return (
          <div className="flex items-center gap-2.5 font-sans">
            <span className="hidden sm:inline-flex px-2 py-0.5 rounded text-[11px] font-sans font-medium tabular-nums bg-app-subtle border border-app-border text-app-muted">
              {benchmarks.length} registered
            </span>

            {/* Fast Search Input */}
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-app-muted pointer-events-none" />
              <input
                type="text"
                placeholder="Filter benchmarks..."
                value={catalogSearchQuery}
                onChange={(e) => setCatalogSearchQuery(e.target.value)}
                className="w-36 sm:w-48 lg:w-56 pl-8 pr-2.5 py-1 text-xs font-sans rounded bg-app-bg border border-app-border text-app-text placeholder:text-app-muted/60 focus:outline-hidden focus:border-blue-500"
              />
            </div>

            {/* Task Category Filter */}
            <div className="hidden md:flex items-center border border-app-border rounded overflow-hidden text-xs font-sans bg-app-bg">
              {[
                { id: "all", label: "All" },
                { id: "structuralist", label: "TheoryNet" },
                { id: "retrieval", label: "Retrieval" },
                { id: "extraction", label: "Extraction" },
              ].map((tab, idx) => (
                <button
                  key={tab.id}
                  onClick={() => setCatalogTaskFilter(tab.id)}
                  className={`px-2.5 py-1 transition-colors cursor-pointer ${
                    idx > 0 ? "border-l border-app-border" : ""
                  } ${
                    catalogTaskFilter === tab.id
                      ? "bg-app-subtle text-app-heading font-medium"
                      : "text-app-muted hover:text-app-text"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        );
      }

      if (activeBenchmark) {
        return (
          <div className="hidden sm:flex items-center gap-2 text-xs font-sans text-app-muted">
            <span className="font-mono text-[11px] text-app-muted">id: {activeBenchmark.id}</span>
            <span>·</span>
            <span className="capitalize">{activeBenchmark.task_type} Task</span>
            <span>·</span>
            <span>Level {activeBenchmark.level || (activeBenchmark.task_type === "structuralist" ? 4 : 2)}</span>
          </div>
        );
      }

      return null;
    }

    return null;
  }, [
    activeMode,
    catalogViewMode,
    benchmarks,
    catalogSearchQuery,
    catalogTaskFilter,
    activeBenchmark,
    setCatalogSearchQuery,
    setCatalogTaskFilter,
    reports,
    activeReportId,
    activeReport,
    setActiveReportId,
  ]);

  // Metrics KPI Strip
  const metricsStrip = useMemo(() => {
    if (activeMode !== "inspector" || !activeReport || displayMetrics.length === 0) {
      return null;
    }

    return (
      <div className="flex items-center gap-3">
        {stagedCount > 0 && (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] bg-amber-500/10 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400 border border-amber-500/30">
            <span className="font-medium">{stagedCount}</span>
            <span>Staged (⌘⏎ commit)</span>
            {optimisticScalarDeltas.f1 !== 0 && (
              <span className="tabular-nums text-[10px]">
                ({optimisticScalarDeltas.f1 > 0 ? "+" : ""}
                {optimisticScalarDeltas.f1.toFixed(3)} F₁)
              </span>
            )}
          </div>
        )}

        {showKpiStrip && (
          <div className="flex items-center gap-3 text-xs tabular-nums">
            {displayMetrics.map((m, idx) => (
              <div key={m.key} className="flex items-center gap-1.5">
                {idx > 0 && <span className="text-app-border">·</span>}
                <span className="text-[10px] uppercase text-app-muted font-sans font-medium">
                  {m.label}:
                </span>
                <span className="font-medium text-app-text">
                  {m.value.toFixed(3)}
                  {m.delta !== 0 && (
                    <span className="ml-1 text-[10px] font-normal text-emerald-500">
                      ({m.delta > 0 ? "+" : ""}
                      {m.delta.toFixed(3)})
                    </span>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={toggleKpiStrip}
          className={`p-1 rounded text-xs border transition-colors cursor-pointer ${
            showKpiStrip
              ? "bg-app-bg text-app-muted hover:text-app-text border-app-border"
              : "bg-blue-500/10 text-blue-500 border-blue-500/30"
          }`}
          title={showKpiStrip ? "Hide Header KPIs" : "Show Header KPIs"}
        >
          {showKpiStrip ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
        </button>
      </div>
    );
  }, [
    activeMode,
    activeReport,
    displayMetrics,
    stagedCount,
    optimisticScalarDeltas.f1,
    showKpiStrip,
  ]);

  // Actions Toolbar
  const actionToolbar = useMemo(() => {
    return (
      <div className="flex items-center gap-1.5">
        {activeMode === "inspector" && (
          <>
            <button
              type="button"
              onClick={() => {
                if (activeReport?.run_ids?.[0]) {
                  setTargetRunId(activeReport.run_ids[0]);
                }
                setActiveMode("execute");
              }}
              className="flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors cursor-pointer"
              title="Navigate to dedicated On-Demand Evaluation Studio"
            >
              <Play className="w-3 h-3 fill-current" />
              <span>Run</span>
            </button>

            {activeReport && (
              <>
                <button
                  type="button"
                  onClick={() => setIsExportModalOpen(true)}
                  className="p-1 rounded bg-app-bg hover:bg-app-subtle text-app-text border border-app-border transition-colors cursor-pointer"
                  title="Export Report"
                >
                  <Download className="w-3.5 h-3.5 text-blue-500" />
                </button>

                <button
                  type="button"
                  onClick={() => {
                    if (onOpenConfigEditor) {
                      onOpenConfigEditor();
                    } else {
                      openPhasePromptInExecution({
                        phaseKey: "phase2",
                        promptKey: "entity_extraction",
                      });
                    }
                  }}
                  className="p-1 rounded bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text border border-app-border transition-colors cursor-pointer"
                  title="Tune Prompt in ConfigEditor"
                >
                  <Wrench className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </>
        )}

        {activeMode === "catalog" && catalogViewMode === "table" && (
          <>
            <button
              type="button"
              onClick={() => setIsPromoteModalOpen(true)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-sans font-medium bg-app-surface text-app-text border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
              title="Promote verified pipeline run to gold benchmark"
            >
              <Award className="w-3.5 h-3.5 text-app-muted" />
              <span>Promote from Run</span>
            </button>
            <button
              type="button"
              onClick={() => setIsRegisterModalOpen(true)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-sans font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer"
              title="Register new benchmark specification"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Register Benchmark</span>
            </button>
          </>
        )}

        {activeMode === "catalog" && catalogViewMode === "detail" && activeBenchmark && (
          <>
            <button
              type="button"
              onClick={() => handleCopyCli(activeBenchmark.id)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-sans font-medium bg-app-surface text-app-text border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
              title="Copy CLI evaluation command"
            >
              <Copy className="w-3.5 h-3.5 text-app-muted" />
              <span>{copyCodeFeedback ? "Copied" : "CLI Snippet"}</span>
            </button>

            <button
              type="button"
              onClick={() => setIsPromoteModalOpen(true)}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-sans font-medium bg-app-surface text-app-text border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
              title="Promote verified pipeline run to gold benchmark"
            >
              <Award className="w-3.5 h-3.5 text-app-muted" />
              <span>Promote Run</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setSelectedBenchmarkId(activeBenchmark.id);
                setTargetRunId(activeBenchmark.id);
                setActiveMode("execute");
              }}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-sans font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer"
              title="Evaluate run against benchmark"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Evaluate Run</span>
            </button>

            <button
              type="button"
              onClick={() => setIsLinterRailOpen(!isLinterRailOpen)}
              className={`p-1 rounded text-xs border transition-colors cursor-pointer ${
                isLinterRailOpen
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-app-surface text-app-muted hover:text-app-text border-app-border hover:bg-app-subtle"
              }`}
              title={isLinterRailOpen ? "Close Pre-Flight Linter Rail" : "Open Pre-Flight Linter Rail"}
            >
              <FileCode className="w-3.5 h-3.5" />
            </button>
          </>
        )}

        <button
          type="button"
          onClick={() => {
            fetchReports();
            fetchBenchmarks();
          }}
          disabled={isLoading}
          className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors disabled:opacity-50 cursor-pointer"
          title="Refresh Evaluation Data"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`}
          />
        </button>
      </div>
    );
  }, [
    activeMode,
    catalogViewMode,
    activeBenchmark,
    copyCodeFeedback,
    isLinterRailOpen,
    setIsPromoteModalOpen,
    setIsRegisterModalOpen,
    setSelectedBenchmarkId,
    setTargetRunId,
    setActiveMode,
    setIsLinterRailOpen,
    activeReport,
    onOpenConfigEditor,
    fetchReports,
    fetchBenchmarks,
    isLoading,
  ]);

  return (
    <>
      <WorkspaceContextBar
        breadcrumbs={breadcrumbs}
        isSidebarCollapsed={isSidebarCollapsed}
        onExpandSidebar={onExpandSidebar}
        showExpandButton={false}
        contextSelector={contextSelector}
        metrics={metricsStrip}
        actions={actionToolbar}
      />

      {/* Action Modals */}
      <ExportReportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        report={activeReport}
      />

      <ExecuteEvaluationModal
        isOpen={isExecuteModalOpen}
        onClose={() => setIsExecuteModalOpen(false)}
        defaultRunId={activeReport?.run_ids?.[0] || ""}
      />

      <PromoteToGoldModal
        isOpen={isPromoteModalOpen}
        onClose={() => setIsPromoteModalOpen(false)}
      />

      <RegisterBenchmarkModal
        isOpen={isRegisterModalOpen}
        onClose={() => setIsRegisterModalOpen(false)}
      />
    </>
  );
};
