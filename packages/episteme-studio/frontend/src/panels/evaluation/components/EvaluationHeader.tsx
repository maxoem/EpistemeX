import React, { useState } from "react";
import {
  BookOpen,
  CheckCircle2,
  Clock,
  Download,
  Filter,
  Layers,
  Network,
  Play,
  Sliders,
  Sparkles,
  TriangleAlert,
  XCircle,
  Wrench,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { ExportReportModal } from "./ExportReportModal";
import { ExecuteEvaluationModal } from "./ExecuteEvaluationModal";
import { openPhasePromptInExecution } from "./ActionableHookPill";
import type { EvaluationOutcome, EvaluationSubTab } from "../../../api/types";

export interface EvaluationHeaderProps {
  onOpenConfigEditor?: () => void;
}

const SUB_TABS: Array<{ id: EvaluationSubTab; label: string; icon: React.ElementType }> = [
  { id: "canvas", label: "Topological Canvas", icon: Network },
  { id: "epistemics", label: "Epistemic TheoryNet", icon: Layers },
  { id: "adjudication", label: "Adjudication Queue", icon: Sliders },
  { id: "calibration", label: "Calibration Lab", icon: Sparkles },
  { id: "grounding", label: "Document Grounding", icon: BookOpen },
  { id: "retrieval", label: "Retrieval & Stress", icon: Filter },
];

export const EvaluationHeader: React.FC<EvaluationHeaderProps> = ({ onOpenConfigEditor }) => {
  const {
    activeReport,
    activeSubTab,
    setActiveSubTab,
    stagedAdjudications,
    optimisticScalarDeltas,
    setActiveMode,
    setTargetRunId,
  } = useEvaluationStore();

  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isExecuteModalOpen, setIsExecuteModalOpen] = useState(false);

  const renderOutcomeBadge = (outcome: EvaluationOutcome | string) => {
    switch (outcome?.toLowerCase()) {
      case "pass":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            PASS
          </span>
        );
      case "fail":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/30">
            <XCircle className="w-3.5 h-3.5 text-rose-500" />
            FAIL
          </span>
        );
      case "warning":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
            <TriangleAlert className="w-3.5 h-3.5 text-amber-500" />
            WARN
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-500/10 text-zinc-500 dark:text-zinc-400 border border-zinc-500/30">
            <Clock className="w-3.5 h-3.5 text-zinc-400" />
            {outcome ? outcome.toUpperCase() : "UNKNOWN"}
          </span>
        );
    }
  };

  const stagedCount = stagedAdjudications.size;

  const f1Score = activeReport?.key_metrics?.f1 ?? activeReport?.key_metrics?.macro_f1 ?? 0;
  const tenability =
    activeReport?.key_metrics?.delta_star ?? activeReport?.key_metrics?.tenability ?? 0;
  const ece = activeReport?.key_metrics?.ece ?? 0;
  const mrr = activeReport?.key_metrics?.mrr ?? 0;

  return (
    <>
      <div className="shrink-0 border-b border-app-border bg-app-surface select-none">
        {/* Row 1: Fixed 48px Header */}
        <div className="h-12 px-4 flex items-center justify-between border-b border-app-border/60">
          {/* Breadcrumbs & Outcome Pill */}
          <div className="flex items-center gap-3 min-w-0">
            {activeReport ? (
              renderOutcomeBadge(activeReport.outcome)
            ) : (
              <span className="text-xs text-app-muted">No Run Selected</span>
            )}

            <div className="flex items-center gap-2 truncate">
              <span className="font-mono text-xs text-app-muted">Evaluation</span>
              <span className="text-app-muted">/</span>
              {activeReport?.dataset_ref && (
                <>
                  <span className="text-xs font-medium text-app-text truncate">
                    {activeReport.dataset_ref}
                  </span>
                  <span className="text-app-muted">/</span>
                </>
              )}
              <h1 className="text-xs font-mono font-semibold text-app-heading truncate">
                {activeReport ? activeReport.evaluation_id : "Select an Evaluation Run"}
              </h1>
            </div>
          </div>

          {/* Center-Right: Persistent KPI Strip with Tabular Numerals */}
          {activeReport && (
            <div className="flex items-center gap-4 text-xs font-mono tabular-nums">
              <div className="flex flex-col items-end">
                <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                  Macro F₁
                </span>
                <span className="text-xs font-semibold text-app-text">
                  {f1Score.toFixed(3)}
                  {optimisticScalarDeltas.f1 !== 0 && (
                    <span className="ml-1 text-[10px] font-normal text-emerald-500">
                      ({optimisticScalarDeltas.f1 > 0 ? "+" : ""}
                      {optimisticScalarDeltas.f1.toFixed(3)})
                    </span>
                  )}
                </span>
              </div>
              <div className="h-5 w-px bg-app-border" />
              <div className="flex flex-col items-end">
                <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                  Tenability δ*
                </span>
                <span className="text-xs font-semibold text-app-text">
                  {tenability.toFixed(3)}
                </span>
              </div>
              <div className="h-5 w-px bg-app-border" />
              <div className="flex flex-col items-end">
                <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                  ECE
                </span>
                <span className="text-xs font-semibold text-app-text">{ece.toFixed(3)}</span>
              </div>
              <div className="h-5 w-px bg-app-border" />
              <div className="flex flex-col items-end">
                <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                  MRR
                </span>
                <span className="text-xs font-semibold text-app-text">{mrr.toFixed(3)}</span>
              </div>
            </div>
          )}

          {/* Action Bar */}
          <div className="flex items-center gap-2 pl-2">
            <button
              onClick={() => {
                if (activeReport?.run_ids?.[0]) {
                  setTargetRunId(activeReport.run_ids[0]);
                }
                setActiveMode("execute");
              }}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-2xs cursor-pointer"
              title="Navigate to dedicated On-Demand Evaluation Studio"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Evaluation</span>
            </button>

            {activeReport && (
              <>
                <button
                  onClick={() => setIsExportModalOpen(true)}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-app-bg hover:bg-app-subtle text-app-text border border-app-border transition-colors shadow-2xs"
                  title="Export report in LaTeX, JSON-LD, or Markdown"
                >
                  <Download className="w-3.5 h-3.5 text-blue-500" />
                  <span className="hidden sm:inline">Export Report</span>
                </button>

                <button
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
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text border border-app-border transition-colors shadow-2xs cursor-pointer"
                  title="Tune prompts or parameters in ConfigEditor"
                >
                  <Wrench className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">Tune Prompt</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* Row 2: Fixed 40px Zero-Box Segmented Sub-Nav */}
        <div className="h-10 px-4 flex items-center justify-between border-t border-app-border/40 overflow-x-auto">
          <div className="flex items-center gap-1">
            {SUB_TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeSubTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveSubTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors whitespace-nowrap ${
                    isActive
                      ? "bg-blue-600/10 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400 font-semibold shadow-2xs"
                      : "text-app-muted hover:text-app-text hover:bg-app-subtle"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Staged Adjudications Indicator if any */}
          {stagedCount > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30 animate-pulse font-mono">
              <span className="font-semibold">{stagedCount}</span>
              <span>Staged for Commit (⌘⏎)</span>
            </div>
          )}
        </div>
      </div>

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
    </>
  );
};
