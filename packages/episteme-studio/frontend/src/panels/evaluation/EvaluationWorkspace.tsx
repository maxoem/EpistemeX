import React, { useEffect, useState, useMemo } from "react";
import {
  Activity,
  Award,
  BarChart2,
  BookOpen,
  Filter,
  Layers,
  Network,
  Play,
  Plus,
  Sliders,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { useEvaluationStore } from "../../store/evaluationStore";
import { ResizablePanel } from "../ResizablePanel";
import { LocalNavSidebar, NavSectionDef } from "../../shell/navigation";
import { EvaluationContextBar } from "./components/EvaluationContextBar";
import { BenchmarkCatalogPage } from "./catalog/BenchmarkCatalogPage";
import { LeaderboardPage } from "./leaderboard/LeaderboardPage";
import { RunEvaluationInspector } from "./inspector/RunEvaluationInspector";
import { LongitudinalTrajectoryStudio } from "./longitudinal/LongitudinalTrajectoryStudio";
import { ExecuteEvaluationPage } from "./execution/ExecuteEvaluationPage";
import { PromoteToGoldModal } from "./catalog/PromoteToGoldModal";
import { RegisterBenchmarkModal } from "./catalog/RegisterBenchmarkModal";

export const EvaluationWorkspace: React.FC = () => {
  const {
    activeMode,
    setActiveMode,
    activeSubTab,
    setActiveSubTab,
    reports,
    activeReportId,
    setActiveReportId,
    fetchReports,
    fetchBenchmarks,
    stagedAdjudications,
  } = useEvaluationStore();

  const [isPromoteModalOpen, setIsPromoteModalOpen] = useState(false);
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);

  // Expanded sidebar by default to present robust L-shaped spatial hierarchy
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem("episteme-eval-nav-sidebar-collapsed");
      if (stored !== null) return stored === "true";
      return false; // Default expanded
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("episteme-eval-nav-sidebar-collapsed", String(next));
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

  // Auto-select first report if none active and reports are present
  useEffect(() => {
    if (!activeReportId && reports.length > 0) {
      setActiveReportId(reports[0].evaluation_id);
    }
  }, [activeReportId, reports, setActiveReportId]);

  const stagedCount = stagedAdjudications.size;

  // Declarative navigation schema for the local navigation sidebar (SOLID / Open-Closed Principle)
  const navSections: NavSectionDef[] = useMemo(() => {
    return [
      {
        id: "eval-primary-navigation",
        entries: [
          {
            type: "item",
            item: {
              id: "catalog",
              label: "Benchmark Catalog",
              icon: BookOpen,
              active: activeMode === "catalog",
              onClick: () => setActiveMode("catalog"),
            },
          },
          {
            type: "item",
            item: {
              id: "leaderboard",
              label: "Leaderboard Studio",
              icon: BarChart2,
              active: activeMode === "leaderboard",
              onClick: () => setActiveMode("leaderboard"),
            },
          },
          {
            type: "group",
            group: {
              id: "inspector",
              label: "Run Inspector",
              icon: Activity,
              active: activeMode === "inspector",
              collapsible: true,
              defaultExpanded: true,
              badge: reports.length > 0 ? reports.length : undefined,
              onTitleClick: () => {
                if (activeMode !== "inspector") {
                  setActiveMode("inspector");
                }
              },
              children: [
                {
                  id: "canvas",
                  label: "Topological Canvas",
                  icon: Network,
                  active: activeMode === "inspector" && activeSubTab === "canvas",
                  onClick: () => {
                    setActiveMode("inspector");
                    setActiveSubTab("canvas");
                  },
                },
                {
                  id: "epistemics",
                  label: "Epistemic TheoryNet",
                  icon: Layers,
                  active: activeMode === "inspector" && activeSubTab === "epistemics",
                  onClick: () => {
                    setActiveMode("inspector");
                    setActiveSubTab("epistemics");
                  },
                },
                {
                  id: "adjudication",
                  label: "Adjudication Workspace",
                  icon: Sliders,
                  badge: stagedCount > 0 ? stagedCount : undefined,
                  badgeVariant: "warning",
                  active: activeMode === "inspector" && activeSubTab === "adjudication",
                  onClick: () => {
                    setActiveMode("inspector");
                    setActiveSubTab("adjudication");
                  },
                },
                {
                  id: "calibration",
                  label: "Calibration Lab",
                  icon: Sparkles,
                  active: activeMode === "inspector" && activeSubTab === "calibration",
                  onClick: () => {
                    setActiveMode("inspector");
                    setActiveSubTab("calibration");
                  },
                },
                {
                  id: "grounding",
                  label: "Document Grounding",
                  icon: BookOpen,
                  active: activeMode === "inspector" && activeSubTab === "grounding",
                  onClick: () => {
                    setActiveMode("inspector");
                    setActiveSubTab("grounding");
                  },
                },
                {
                  id: "retrieval",
                  label: "Retrieval & Stress",
                  icon: Filter,
                  active: activeMode === "inspector" && activeSubTab === "retrieval",
                  onClick: () => {
                    setActiveMode("inspector");
                    setActiveSubTab("retrieval");
                  },
                },
              ],
            },
          },
          {
            type: "item",
            item: {
              id: "longitudinal",
              label: "Longitudinal Studio",
              icon: TrendingUp,
              active: activeMode === "longitudinal",
              onClick: () => setActiveMode("longitudinal"),
            },
          },
          {
            type: "item",
            item: {
              id: "execute",
              label: "Execute Evaluation",
              icon: Play,
              active: activeMode === "execute",
              onClick: () => setActiveMode("execute"),
            },
          },
        ],
      },
    ];
  }, [activeMode, activeSubTab, reports.length, stagedCount, setActiveMode, setActiveSubTab]);

  return (
    <div className="flex flex-1 h-full w-full bg-app-bg text-app-text select-none overflow-hidden font-sans">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 1. Local Navigation (Left Sidebar) - L-Shaped Spatial Hierarchy    */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <ResizablePanel
        side="left"
        storageKey="episteme-eval-nav-sidebar-width"
        defaultWidth={250}
        minWidth={220}
        maxWidth={360}
        collapsible={true}
        collapseThreshold={110}
        collapsedWidth={48}
        showFooter={false}
        collapsed={isSidebarCollapsed}
        onCollapseChange={setIsSidebarCollapsed}
        collapsedContent={
          <LocalNavSidebar
            title="EVALUATION"
            sections={navSections}
            collapsed={true}
            onToggleCollapse={toggleSidebar}
          />
        }
        className="!bg-app-surface !border-r !border-app-border flex flex-col"
      >
        <LocalNavSidebar
          title="EVALUATION"
          sections={navSections}
          collapsed={false}
          onToggleCollapse={toggleSidebar}
          footerContent={
            activeMode === "catalog" ? (
              <div className="space-y-1.5">
                <button
                  type="button"
                  onClick={() => setIsPromoteModalOpen(true)}
                  className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium bg-amber-600 hover:bg-amber-700 text-white transition-colors cursor-pointer"
                >
                  <Award className="w-3.5 h-3.5" />
                  <span>+ Promote from Run</span>
                </button>
                <button
                  type="button"
                  onClick={() => setIsRegisterModalOpen(true)}
                  className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium bg-app-surface hover:bg-app-subtle text-app-text border border-app-border transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5 text-app-muted" />
                  <span>+ Register Benchmark</span>
                </button>
              </div>
            ) : undefined
          }
        />
      </ResizablePanel>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 2. Main Data Canvas: Decoupled State Context Bar + Fluid Workspace */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg">
        {/* Single Consolidated Context / Utility Bar (Height: 40px) */}
        <EvaluationContextBar
          isSidebarCollapsed={isSidebarCollapsed}
          onExpandSidebar={toggleSidebar}
        />

        {/* Dynamic Fluid Canvas Content */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg">
          {activeMode === "catalog" ? (
            <BenchmarkCatalogPage />
          ) : activeMode === "leaderboard" ? (
            <LeaderboardPage />
          ) : activeMode === "longitudinal" ? (
            <LongitudinalTrajectoryStudio />
          ) : activeMode === "execute" ? (
            <ExecuteEvaluationPage />
          ) : (
            <RunEvaluationInspector />
          )}
        </div>
      </div>

      {/* Auxiliary Modals for Promotion / Registration */}
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
