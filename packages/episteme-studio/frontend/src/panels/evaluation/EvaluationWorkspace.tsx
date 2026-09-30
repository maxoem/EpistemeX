import React, { useEffect, useState, useMemo } from "react";
import {
  Activity,
  Award,
  BarChart2,
  BookOpen,
  CheckCircle2,
  Clock,
  ExternalLink,
  Filter,
  Layers,
  Network,
  Play,
  Plus,
  RefreshCw,
  Search,
  Sliders,
  Sparkles,
  TrendingUp,
  TriangleAlert,
  XCircle,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { useEvaluationStore } from "../../store/evaluationStore";
import { ResizablePanel } from "../ResizablePanel";
import { BenchmarkCatalogPage } from "./catalog/BenchmarkCatalogPage";
import { PromoteToGoldModal } from "./catalog/PromoteToGoldModal";
import { RegisterBenchmarkModal } from "./catalog/RegisterBenchmarkModal";
import { LeaderboardPage } from "./leaderboard/LeaderboardPage";
import { RunEvaluationInspector } from "./inspector/RunEvaluationInspector";
import { LongitudinalTrajectoryStudio } from "./longitudinal/LongitudinalTrajectoryStudio";
import { ExecuteEvaluationPage } from "./execution/ExecuteEvaluationPage";
import type { EvaluationOutcome } from "../../api/types";

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
  const [isPromoteModalOpen, setIsPromoteModalOpen] = useState(false);
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("episteme-eval-left-sidebar-width-collapsed") === "true";
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("episteme-eval-left-sidebar-width-collapsed", String(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

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
        <div className="flex items-center gap-2">
          {activeMode !== "leaderboard" &&
            activeMode !== "longitudinal" &&
            activeMode !== "execute" && (
            <button
              onClick={toggleSidebar}
              className={`p-1.5 rounded-md border transition-colors cursor-pointer ${
                isSidebarCollapsed
                  ? "bg-blue-500/10 border-blue-500/30 text-blue-500 hover:bg-blue-500/20"
                  : "bg-app-bg border-app-border text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
              title={isSidebarCollapsed ? "Expand Runs Sidebar" : "Collapse Runs Sidebar to Focus"}
              aria-label="Toggle sidebar"
            >
              {isSidebarCollapsed ? <PanelLeftOpen className="w-3.5 h-3.5" /> : <PanelLeftClose className="w-3.5 h-3.5" />}
            </button>
          )}

          {/* Mode Selector Tabs */}
          <div className="flex items-center gap-1 bg-app-bg dark:bg-[#111827] p-0.5 rounded-md border border-app-border">
            <button
              onClick={() => setActiveMode("catalog")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                activeMode === "catalog"
                  ? "bg-app-surface text-app-heading border border-app-border/80 font-semibold"
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
                  ? "bg-app-surface text-app-heading border border-app-border/80 font-semibold"
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
                  ? "bg-app-surface text-app-heading border border-app-border/80 font-semibold"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Run Inspector</span>
            </button>
            <button
              onClick={() => setActiveMode("longitudinal")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                activeMode === "longitudinal"
                  ? "bg-app-surface text-app-heading border border-app-border/80 font-semibold"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
            >
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Longitudinal Studio</span>
            </button>
            <button
              onClick={() => setActiveMode("execute")}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                activeMode === "execute"
                  ? "bg-app-surface text-app-heading border border-app-border/80 font-semibold"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle"
              }`}
            >
              <Play className="w-3.5 h-3.5" />
              <span>Execute Evaluation</span>
            </button>
          </div>
        </div>

        {/* Center / Run Context */}
        <div className="flex items-center gap-2 text-app-muted truncate max-w-md">
          {activeMode === "inspector" && activeReport ? (
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-app-muted">Active Run:</span>
              <span className="font-mono font-semibold text-app-text truncate">{activeReport.evaluation_id}</span>
            </div>
          ) : (
            <span className="text-xs text-app-muted font-medium">Evaluation Workbench</span>
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
        {activeMode !== "leaderboard" &&
          activeMode !== "longitudinal" &&
          activeMode !== "execute" && (
          <ResizablePanel
            side="left"
            storageKey="episteme-eval-left-sidebar-width"
            defaultWidth={300}
            minWidth={260}
            maxWidth={460}
            collapsible={true}
            collapseThreshold={120}
            showFooter={false}
            collapsed={isSidebarCollapsed}
            onToggleCollapse={toggleSidebar}
            className="!bg-[#F8FAFC] dark:!bg-app-rail !border-r !border-[#E2E8F0] dark:!border-app-border flex flex-col"
          >
            <div className="flex flex-col h-full overflow-hidden">
              {/* Search & Filter Header */}
            <div className="p-2.5 border-b border-app-border space-y-2 shrink-0">
              <div className="flex items-center gap-1.5">
                <div className="relative flex-1">
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
                <button
                  onClick={toggleSidebar}
                  className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer"
                  title="Collapse sidebar"
                  aria-label="Collapse sidebar"
                >
                  <PanelLeftClose className="w-3.5 h-3.5" />
                </button>
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
                        className={`p-2.5 cursor-pointer transition-colors border-l-2 ${
                          isSelected
                            ? "bg-app-subtle border-blue-600 text-app-heading font-medium"
                            : "border-transparent hover:bg-app-subtle text-app-text"
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
                      className={`p-2.5 cursor-pointer transition-colors border-l-2 ${
                        isSelected
                          ? "bg-app-subtle border-blue-600 text-app-heading font-medium"
                          : "border-transparent hover:bg-app-subtle text-app-text"
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

            {/* Catalog Action Buttons at bottom of Left Rail */}
            {activeMode === "catalog" && (
              <div className="p-2 border-t border-app-border space-y-1.5 shrink-0 bg-app-surface/60">
                <button
                  onClick={() => setIsPromoteModalOpen(true)}
                  className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium bg-amber-600 hover:bg-amber-700 text-white transition-colors cursor-pointer"
                >
                  <Award className="w-3.5 h-3.5" />
                  <span>+ Promote from Run</span>
                </button>
                <button
                  onClick={() => setIsRegisterModalOpen(true)}
                  className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium bg-app-surface hover:bg-app-subtle text-app-text border border-app-border transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 text-app-muted" />
                  <span>+ Register Benchmark</span>
                </button>
              </div>
            )}
          </div>
        </ResizablePanel>
        )}

        {/* Center Fluid Workspace */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg">
          {activeMode === "catalog" ? (
            /* Page 1: Benchmark Catalog (Phase 1) */
            <BenchmarkCatalogPage />
          ) : activeMode === "leaderboard" ? (
            /* Page 2: Benchmark Leaderboard Matrix & Pareto Studio (Phase 1) */
            <LeaderboardPage />
          ) : activeMode === "longitudinal" ? (
            /* Sub-View 3.4 / Diachronic Studio: Lakatosian Longitudinal Trajectory (Phase 3) */
            <LongitudinalTrajectoryStudio />
          ) : activeMode === "execute" ? (
            /* Page 4: On-Demand Evaluation Execution Studio */
            <ExecuteEvaluationPage />
          ) : (
            /* Page 3: Deep Single-Run Evaluation Inspector (Phase 2 & 3) */
            <RunEvaluationInspector />
          )}
        </div>
      </div>

      {/* Global Promotion & Benchmark Registration Modals */}
      <PromoteToGoldModal
        isOpen={isPromoteModalOpen}
        onClose={() => setIsPromoteModalOpen(false)}
      />
      <RegisterBenchmarkModal
        isOpen={isRegisterModalOpen}
        onClose={() => setIsRegisterModalOpen(false)}
      />
    </div>
  );
};
