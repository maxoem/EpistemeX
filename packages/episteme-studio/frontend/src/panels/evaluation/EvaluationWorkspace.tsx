import React, { useEffect, useState, useMemo } from "react";
import {
  Activity,
  BarChart2,
  BookOpen,
  CheckCircle2,
  Clock,
  ExternalLink,
  Filter,
  Layers,
  Network,
  RefreshCw,
  Search,
  Sliders,
  Sparkles,
  TriangleAlert,
  XCircle,
} from "lucide-react";
import { useEvaluationStore } from "../../store/evaluationStore";
import { ResizablePanel } from "../ResizablePanel";
import type { EvaluationMode, EvaluationSubTab, EvaluationOutcome } from "../../api/types";

const SUB_TABS: Array<{ id: EvaluationSubTab; label: string; icon: React.ElementType }> = [
  { id: "canvas", label: "Topological Canvas", icon: Network },
  { id: "epistemics", label: "Epistemic TheoryNet", icon: Layers },
  { id: "adjudication", label: "Adjudication Queue", icon: Sliders },
  { id: "calibration", label: "Calibration Lab", icon: Sparkles },
  { id: "grounding", label: "Document Grounding", icon: BookOpen },
  { id: "retrieval", label: "Retrieval & Stress", icon: Filter },
];

export const EvaluationWorkspace: React.FC = () => {
  const {
    activeMode,
    setActiveMode,
    activeSubTab,
    setActiveSubTab,
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
    isLoading,
    error,
  } = useEvaluationStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState<string>("all");

  useEffect(() => {
    fetchReports();
    fetchBenchmarks();
  }, [fetchReports, fetchBenchmarks]);

  // Filtered reports list
  const filteredReports = useMemo(() => {
    return reports.filter((r) => {
      const matchesSearch =
        searchQuery.trim() === "" ||
        r.evaluation_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (r.dataset_ref && r.dataset_ref.toLowerCase().includes(searchQuery.toLowerCase())) ||
        r.run_ids.some((id) => id.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesOutcome =
        outcomeFilter === "all" || r.outcome.toLowerCase() === outcomeFilter.toLowerCase();

      return matchesSearch && matchesOutcome;
    });
  }, [reports, searchQuery, outcomeFilter]);

  // Filtered benchmarks list
  const filteredBenchmarks = useMemo(() => {
    return benchmarks.filter((b) => {
      return (
        searchQuery.trim() === "" ||
        b.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        b.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        b.task_type.toLowerCase().includes(searchQuery.toLowerCase())
      );
    });
  }, [benchmarks, searchQuery]);

  const renderOutcomeBadge = (outcome: EvaluationOutcome | string) => {
    switch (outcome.toLowerCase()) {
      case "pass":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-500 dark:bg-emerald-500/20 dark:text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3" />
            PASS
          </span>
        );
      case "fail":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/10 text-rose-500 dark:bg-rose-500/20 dark:text-rose-400 border border-rose-500/30">
            <XCircle className="w-3 h-3" />
            FAIL
          </span>
        );
      case "warning":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-500 dark:bg-amber-500/20 dark:text-amber-400 border border-amber-500/30">
            <TriangleAlert className="w-3 h-3" />
            WARN
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-500/10 text-zinc-500 dark:bg-zinc-500/20 dark:text-zinc-400 border border-zinc-500/30">
            <Clock className="w-3 h-3" />
            {outcome.toUpperCase()}
          </span>
        );
    }
  };

  const stagedCount = stagedAdjudications.size;

  return (
    <div className="flex flex-col h-full w-full bg-app-bg text-app-text select-none overflow-hidden font-sans">
      {/* 44px Fixed Contextual Action Bar */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs">
        {/* Mode Selector Tabs */}
        <div className="flex items-center gap-1 bg-app-bg p-0.5 rounded-md border border-app-border">
          <button
            onClick={() => setActiveMode("catalog")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              activeMode === "catalog"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Benchmark Catalog</span>
          </button>
          <button
            onClick={() => setActiveMode("leaderboard")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              activeMode === "leaderboard"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle"
            }`}
          >
            <BarChart2 className="w-3.5 h-3.5" />
            <span>Leaderboard Studio</span>
          </button>
          <button
            onClick={() => setActiveMode("inspector")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              activeMode === "inspector"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle"
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Run Inspector</span>
          </button>
        </div>

        {/* Center / Breadcrumb info */}
        <div className="flex items-center gap-2 text-app-muted truncate max-w-md">
          <span className="font-mono text-[11px]">Evaluation</span>
          <span>/</span>
          <span className="truncate text-app-text font-medium text-[12px]">
            {activeReport?.dataset_ref || selectedBenchmarkId || "All Benchmarks"}
          </span>
          {activeReportId && (
            <>
              <span>/</span>
              <span className="font-mono text-[11px] text-blue-500 dark:text-blue-400 truncate">
                {activeReportId}
              </span>
            </>
          )}
        </div>

        {/* Right status & action tools */}
        <div className="flex items-center gap-2">
          {stagedCount > 0 && (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] bg-amber-500/10 text-amber-500 dark:bg-amber-500/20 dark:text-amber-400 border border-amber-500/30 animate-pulse">
              <span className="font-semibold">{stagedCount}</span>
              <span>Staged (⌘⏎ commit)</span>
              {optimisticScalarDeltas.f1 !== 0 && (
                <span className="font-mono tabular-nums text-[10px]">
                  ({optimisticScalarDeltas.f1 > 0 ? "+" : ""}
                  {optimisticScalarDeltas.f1.toFixed(3)} F₁)
                </span>
              )}
            </div>
          )}

          <button
            onClick={() => {
              fetchReports();
              fetchBenchmarks();
            }}
            disabled={isLoading}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors disabled:opacity-50"
            title="Refresh Evaluation Data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Main Split: Left Rail Controller + Center Fluid Workspace */}
      <div className="flex flex-1 w-full h-full overflow-hidden">
        {/* Left Primary Controller Rail (280px - 320px Resizable) */}
        <ResizablePanel
          side="left"
          storageKey="episteme-eval-left-sidebar-width"
          defaultWidth={300}
          minWidth={260}
          maxWidth={460}
          collapsible={true}
          collapseThreshold={120}
          showFooter={false}
          className="!bg-[#F8FAFC] dark:!bg-app-rail !border-r !border-[#E2E8F0] dark:!border-app-border flex flex-col"
        >
          <div className="flex flex-col h-full overflow-hidden">
            {/* Search & Filter Header */}
            <div className="p-2.5 border-b border-app-border space-y-2 shrink-0">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-app-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder={
                    activeMode === "catalog"
                      ? "Search benchmarks..."
                      : "Search evaluation runs..."
                  }
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-app-bg text-app-text pl-8 pr-2.5 py-1 text-xs rounded border border-app-border focus:border-blue-500 focus:outline-hidden"
                />
              </div>

              {activeMode !== "catalog" && (
                <div className="flex items-center gap-1 text-[11px]">
                  {["all", "pass", "fail", "warning"].map((outcome) => (
                    <button
                      key={outcome}
                      onClick={() => setOutcomeFilter(outcome)}
                      className={`px-2 py-0.5 rounded capitalize transition-colors ${
                        outcomeFilter === outcome
                          ? "bg-blue-600 text-white font-medium"
                          : "text-app-muted hover:text-app-text hover:bg-app-subtle"
                      }`}
                    >
                      {outcome}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* List Body */}
            <div className="flex-1 overflow-y-auto divide-y divide-app-border/40">
              {activeMode === "catalog" ? (
                filteredBenchmarks.length === 0 ? (
                  <div className="p-4 text-center text-xs text-app-muted">
                    {isLoading ? "Loading benchmarks..." : "No benchmarks found"}
                  </div>
                ) : (
                  filteredBenchmarks.map((b) => {
                    const isSelected = selectedBenchmarkId === b.id;
                    return (
                      <div
                        key={b.id}
                        onClick={() => setSelectedBenchmarkId(b.id)}
                        className={`p-2.5 cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-blue-600/10 dark:bg-blue-500/15 border-l-2 border-blue-600 text-app-heading"
                            : "hover:bg-app-subtle text-app-text"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className="font-semibold text-xs truncate">{b.name}</span>
                          <span className="text-[10px] font-mono px-1.5 py-0.2 bg-app-surface text-app-muted rounded border border-app-border">
                            {b.task_type}
                          </span>
                        </div>
                        <p className="text-[11px] text-app-muted line-clamp-2 leading-relaxed">
                          {b.description}
                        </p>
                      </div>
                    );
                  })
                )
              ) : filteredReports.length === 0 ? (
                <div className="p-4 text-center text-xs text-app-muted">
                  {isLoading ? "Loading evaluations..." : "No evaluation reports discovered"}
                </div>
              ) : (
                filteredReports.map((r) => {
                  const isSelected = activeReportId === r.evaluation_id;
                  const f1 = r.key_metrics?.f1 ?? r.key_metrics?.macro_f1;
                  return (
                    <div
                      key={r.evaluation_id}
                      onClick={() => {
                        setActiveReportId(r.evaluation_id);
                        if (activeMode !== "inspector") {
                          setActiveMode("inspector");
                        }
                      }}
                      className={`p-2.5 cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-blue-600/10 dark:bg-blue-500/15 border-l-2 border-blue-600 text-app-heading"
                          : "hover:bg-app-subtle text-app-text"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <span className="font-mono text-[11px] font-semibold truncate">
                          {r.evaluation_id}
                        </span>
                        {renderOutcomeBadge(r.outcome)}
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-app-muted mt-1">
                        <span className="truncate max-w-[150px]">
                          {r.dataset_ref || "Default Gold"}
                        </span>
                        {f1 !== undefined && (
                          <span className="font-mono tabular-nums text-app-text font-medium">
                            F₁ {f1.toFixed(3)}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </ResizablePanel>

        {/* Center Fluid Workspace */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg">
          {activeMode === "catalog" ? (
            /* Page 1: Benchmark Catalog (Phase 1 mount target) */
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-app-muted">
              <BookOpen className="w-12 h-12 text-blue-500 mb-3 opacity-60" />
              <h2 className="text-base font-semibold text-app-heading mb-1">
                Benchmark Catalog & Curation Vitrine
              </h2>
              <p className="text-xs max-w-md text-app-muted leading-relaxed mb-4">
                Gold-standard benchmark repository, pre-flight DAG acyclicity linters (ISSUE-033),
                and golden pathway pipeline promotions.
              </p>
              <div className="flex items-center gap-2 text-[11px] font-mono bg-app-surface px-3 py-1.5 rounded border border-app-border">
                <span>Phase 1 Mount Ready:</span>
                <span className="text-blue-500">BenchmarkCatalogPage.tsx</span>
              </div>
            </div>
          ) : activeMode === "leaderboard" ? (
            /* Page 2: Benchmark Leaderboard Matrix & Pareto Studio (Phase 1 mount target) */
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-app-muted">
              <BarChart2 className="w-12 h-12 text-blue-500 mb-3 opacity-60" />
              <h2 className="text-base font-semibold text-app-heading mb-1">
                Multi-Virtue Pareto Frontier & Leaderboard Studio
              </h2>
              <p className="text-xs max-w-md text-app-muted leading-relaxed mb-4">
                Multi-objective comparative analysis (F₁ vs. Bourbaki Tenability δ* vs.
                Cost/Latency, ISSUE-030) and pairwise diff inspection.
              </p>
              <div className="flex items-center gap-2 text-[11px] font-mono bg-app-surface px-3 py-1.5 rounded border border-app-border">
                <span>Phase 1 Mount Ready:</span>
                <span className="text-blue-500">LeaderboardPage.tsx</span>
              </div>
            </div>
          ) : (
            /* Page 3: Deep Single-Run Evaluation Inspector */
            <div className="flex-1 flex flex-col h-full overflow-hidden">
              {/* Header & Persistent KPI Strip (Row 1: 48px Fixed + Row 2: 40px Sub-Nav) */}
              <div className="shrink-0 border-b border-app-border bg-app-surface">
                {/* Row 1: Fixed 48px Header */}
                <div className="h-12 px-4 flex items-center justify-between border-b border-app-border/60">
                  <div className="flex items-center gap-3 min-w-0">
                    {activeReport ? (
                      renderOutcomeBadge(activeReport.outcome)
                    ) : (
                      <span className="text-xs text-app-muted">No Run Selected</span>
                    )}

                    <div className="flex items-center gap-2 truncate">
                      <h1 className="text-sm font-semibold text-app-heading truncate">
                        {activeReport ? activeReport.evaluation_id : "Select an Evaluation Run"}
                      </h1>
                      {activeReport?.dataset_ref && (
                        <span className="text-[11px] font-mono text-app-muted px-1.5 py-0.5 bg-app-bg rounded border border-app-border truncate">
                          {activeReport.dataset_ref}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Persistent KPI Strip with Tabular Numerals */}
                  {activeReport && (
                    <div className="flex items-center gap-4 text-xs font-mono tabular-nums">
                      <div className="flex flex-col items-end">
                        <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                          Macro F₁
                        </span>
                        <span className="text-xs font-semibold text-app-text">
                          {(activeReport.key_metrics?.f1 ?? activeReport.key_metrics?.macro_f1 ?? 0).toFixed(3)}
                        </span>
                      </div>
                      <div className="h-5 w-px bg-app-border" />
                      <div className="flex flex-col items-end">
                        <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                          Tenability δ*
                        </span>
                        <span className="text-xs font-semibold text-app-text">
                          {(activeReport.key_metrics?.delta_star ?? activeReport.key_metrics?.tenability ?? 0).toFixed(3)}
                        </span>
                      </div>
                      <div className="h-5 w-px bg-app-border" />
                      <div className="flex flex-col items-end">
                        <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                          ECE
                        </span>
                        <span className="text-xs font-semibold text-app-text">
                          {(activeReport.key_metrics?.ece ?? 0).toFixed(3)}
                        </span>
                      </div>
                      <div className="h-5 w-px bg-app-border" />
                      <div className="flex flex-col items-end">
                        <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                          MRR
                        </span>
                        <span className="text-xs font-semibold text-app-text">
                          {(activeReport.key_metrics?.mrr ?? 0).toFixed(3)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Row 2: Fixed 40px Zero-Box Segmented Sub-Nav */}
                <div className="h-10 px-4 flex items-center gap-1 overflow-x-auto">
                  {SUB_TABS.map((tab) => {
                    const Icon = tab.icon;
                    const isActive = activeSubTab === tab.id;
                    return (
                      <button
                        key={tab.id}
                        onClick={() => setActiveSubTab(tab.id)}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                          isActive
                            ? "bg-blue-600/10 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400 font-semibold"
                            : "text-app-muted hover:text-app-text hover:bg-app-subtle"
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        <span>{tab.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Sub-View Content Body */}
              <div className="flex-1 overflow-hidden relative">
                {!activeReport ? (
                  <div className="flex flex-col items-center justify-center h-full p-8 text-center text-app-muted">
                    <Activity className="w-10 h-10 text-app-muted/50 mb-2" />
                    <p className="text-xs">
                      Select an evaluation report from the left panel to inspect metrics and graph
                      alignments.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full p-8 text-center text-app-muted">
                    <div className="p-3 rounded-full bg-blue-500/10 text-blue-500 mb-3">
                      {React.createElement(
                        SUB_TABS.find((t) => t.id === activeSubTab)?.icon || Activity,
                        { className: "w-6 h-6" }
                      )}
                    </div>
                    <h3 className="text-sm font-semibold text-app-heading mb-1">
                      {SUB_TABS.find((t) => t.id === activeSubTab)?.label}
                    </h3>
                    <p className="text-xs max-w-md text-app-muted leading-relaxed mb-4">
                      Active Report: <span className="font-mono text-app-text">{activeReport.evaluation_id}</span>
                      <br />
                      Sub-view ready for vertical slice implementation according to roadmap.
                    </p>
                    <div className="text-[11px] font-mono bg-app-surface px-3 py-1.5 rounded border border-app-border text-app-muted">
                      Status: Phase 0 Foundations & Shell Wiring Complete
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
