import React, { useState } from "react";
import {
  ArrowLeft,
  Award,
  BookOpen,
  Copy,
  FileCode,
  Network,
  Play,
  Table as TableIcon,
} from "lucide-react";
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
  onBackToRegistry: () => void;
  onEvaluateBenchmark: (benchmark: BenchmarkDescriptor) => void;
  onPromoteClick: () => void;
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
  const [isLinterRailOpen, setIsLinterRailOpen] = useState<boolean>(false);
  const [copyCodeFeedback, setCopyCodeFeedback] = useState<boolean>(false);

  const handleCopyCli = () => {
    navigator.clipboard.writeText(`episteme eval --benchmark ${benchmark.id}`);
    setCopyCodeFeedback(true);
    setTimeout(() => setCopyCodeFeedback(false), 2000);
  };

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
        {/* 1. Contextual Action Header Strip                                 */}
        {/* ───────────────────────────────────────────────────────────────── */}
        <div className="px-6 py-3.5 border-b border-app-border bg-app-surface shrink-0 flex flex-col gap-2.5 select-none font-sans">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onBackToRegistry}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium text-app-muted hover:text-app-text hover:bg-app-subtle border border-app-border transition-colors cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Registry</span>
              </button>

              {/* Title in Manrope (design.md font-display) without inline gold badge */}
              <h1 className="font-display text-lg font-semibold text-app-heading tracking-tight">
                {benchmark.name}
              </h1>
            </div>

            {/* Action Buttons Toolbar: Neutral styling */}
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleCopyCli}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-app-surface text-app-text border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
                title="Copy CLI evaluation command"
              >
                <Copy className="w-3.5 h-3.5 text-app-muted" />
                <span>{copyCodeFeedback ? "Copied" : "CLI Snippet"}</span>
              </button>

              <button
                type="button"
                onClick={onPromoteClick}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-app-surface text-app-text border border-app-border hover:bg-app-subtle transition-colors cursor-pointer"
              >
                <Award className="w-3.5 h-3.5 text-app-muted" />
                <span>Promote Run</span>
              </button>

              <button
                type="button"
                onClick={() => onEvaluateBenchmark(benchmark)}
                className="flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Evaluate Run</span>
              </button>

              <button
                type="button"
                onClick={() => setIsLinterRailOpen((prev) => !prev)}
                className={`p-1.5 rounded text-xs border transition-colors cursor-pointer ${
                  isLinterRailOpen
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-app-surface text-app-muted hover:text-app-text border-app-border hover:bg-app-subtle"
                }`}
                title={isLinterRailOpen ? "Close Pre-Flight Linter Rail" : "Open Pre-Flight Linter Rail"}
              >
                <FileCode className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Subline Metadata: only machine ID is mono, rest is clean Inter */}
          <div className="flex items-center gap-2 text-xs text-app-muted font-sans">
            <span className="font-mono text-[11px] text-app-muted">id: {benchmark.id}</span>
            <span>·</span>
            <span className="capitalize">{benchmark.task_type} Task</span>
            <span>·</span>
            <span>{benchmark.domain || "General Science"}</span>
            <span>·</span>
            <span>Level {benchmark.level || (benchmark.task_type === "structuralist" ? 4 : 2)}</span>
          </div>

          {/* ─────────────────────────────────────────────────────────────── */}
          {/* Zero-Box Segmented Sub-Tabs (design.md §4)                      */}
          {/* Dataset Card & Provenance is FIRST tab                          */}
          {/* ─────────────────────────────────────────────────────────────── */}
          <div className="flex items-center gap-1 pt-1 border-t border-app-border/60 text-xs font-sans">
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

            {/* Tab 4: Evaluation Runs */}
            <button
              onClick={() => setActiveTab("runs")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium transition-colors cursor-pointer ${
                activeTab === "runs"
                  ? "bg-app-subtle text-app-heading border border-app-border"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle/40 border border-transparent"
              }`}
            >
              <Award className="w-3.5 h-3.5" />
              <span>Evaluation Runs</span>
            </button>
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
