import React, { useState } from "react";
import {
  BookOpen,
  Network,
  Play,
  Table as TableIcon,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { BenchmarkDataViewer } from "./BenchmarkDataViewer";
import { BenchmarkCardTab } from "./BenchmarkCardTab";
import { StructuralistSpecializationTab } from "./StructuralistSpecializationTab";
import { RetrievalSpecializationTab } from "./RetrievalSpecializationTab";
import { ExtractionSpecializationTab } from "./ExtractionSpecializationTab";
import { BenchmarkRunsTab } from "./BenchmarkRunsTab";
import { PreFlightLinterRail } from "./PreFlightLinterRail";
import type { BenchmarkDescriptor } from "../../../api/types";

interface BenchmarkDetailViewProps {
  benchmark: BenchmarkDescriptor;
  onBackToRegistry?: () => void;
  onEvaluateBenchmark?: (benchmark: BenchmarkDescriptor) => void;
  onPromoteClick?: () => void;
}

type DetailSubTab = "card" | "viewer" | "specialization" | "runs";

export const BenchmarkDetailView: React.FC<BenchmarkDetailViewProps> = ({
  benchmark,
  onBackToRegistry,
  onEvaluateBenchmark,
  onPromoteClick,
}) => {
  // Dataset card & provenance is the first active tab
  const [activeTab, setActiveTab] = useState<DetailSubTab>("card");
  const { isLinterRailOpen } = useEvaluationStore();

  const specializationLabel =
    benchmark.task_type === "structuralist"
      ? "TheoryNet Invariants"
      : benchmark.task_type === "retrieval"
      ? "Competency Queries"
      : benchmark.task_type === "extraction"
      ? "Entity Taxonomy"
      : "Domain Specialization";

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-app-bg text-app-text font-sans">
      {/* Center Fluid: Workbench Canvas */}
      <div className="flex-1 flex flex-col h-full overflow-hidden border-r border-app-border">
        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Zero-Box Segmented Sub-Tabs Bar (design.md §4)                    */}
        {/* Dataset Card & Provenance is FIRST tab                            */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="h-10 px-6 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between select-none font-sans">
          <div className="flex items-center gap-1 text-xs font-sans">
            {/* Tab 1: Dataset Card & Provenance */}
            <button
              onClick={() => setActiveTab("card")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors cursor-pointer ${
                activeTab === "card"
                  ? "bg-app-subtle text-app-heading border border-app-border"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle/40 border border-transparent"
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Dataset Card & Provenance</span>
            </button>

            {/* Tab 2: Data Viewer */}
            <button
              onClick={() => setActiveTab("viewer")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors cursor-pointer ${
                activeTab === "viewer"
                  ? "bg-app-subtle text-app-heading border border-app-border"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle/40 border border-transparent"
              }`}
            >
              <TableIcon className="w-3.5 h-3.5" />
              <span>Data Viewer</span>
            </button>

            {/* Tab 3: Specialized Domain View */}
            <button
              onClick={() => setActiveTab("specialization")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors cursor-pointer ${
                activeTab === "specialization"
                  ? "bg-app-subtle text-app-heading border border-app-border"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle/40 border border-transparent"
              }`}
            >
              <Network className="w-3.5 h-3.5" />
              <span>{specializationLabel}</span>
            </button>

            {/* Tab 4: Evaluation Runs Baseline */}
            <button
              onClick={() => setActiveTab("runs")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors cursor-pointer ${
                activeTab === "runs"
                  ? "bg-app-subtle text-app-heading border border-app-border"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle/40 border border-transparent"
              }`}
            >
              <Play className="w-3.5 h-3.5" />
              <span>Evaluation Runs</span>
            </button>
          </div>

          {/* Quick info tag on the right */}
          <div className="hidden lg:flex items-center gap-2 text-xs text-app-muted font-sans">
            <span>Domain: <strong className="font-medium text-app-heading">{benchmark.domain || "General"}</strong></span>
            <span>·</span>
            <span>Format: <strong className="font-mono text-[11px] text-app-muted">JSON-LD</strong></span>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────────── */}
        {/* Dynamic Tab Body                                                  */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col h-full overflow-hidden">
          {activeTab === "card" ? (
            <BenchmarkCardTab benchmark={benchmark} />
          ) : activeTab === "viewer" ? (
            <BenchmarkDataViewer benchmark={benchmark} />
          ) : activeTab === "specialization" ? (
            benchmark.task_type === "structuralist" ? (
              <StructuralistSpecializationTab benchmark={benchmark} />
            ) : benchmark.task_type === "retrieval" ? (
              <RetrievalSpecializationTab benchmark={benchmark} />
            ) : (
              <ExtractionSpecializationTab benchmark={benchmark} />
            )
          ) : (
            <BenchmarkRunsTab
              benchmark={benchmark}
              onEvaluateBenchmark={onEvaluateBenchmark}
            />
          )}
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────────── */}
      {/* Right Dock: Pre-Flight Linter Rail (Collapsible)                  */}
      {/* ───────────────────────────────────────────────────────────────── */}
      {isLinterRailOpen && (
        <PreFlightLinterRail
          benchmarkName={benchmark.name}
          className="shrink-0 animate-in slide-in-from-right duration-150"
        />
      )}
    </div>
  );
};
