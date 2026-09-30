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
  Eye,
  EyeOff,
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

  const METRIC_LABELS: Record<string, string> = {
    f1: "Macro F₁",
    macro_f1: "Macro F₁",
    delta_star: "Tenability δ*",
    tenability: "Tenability δ*",
    ece: "ECE",
    mrr: "MRR",
    mcc: "Coverage (MCC)",
    pfs: "Fidelity (PFS)",
    ag_iou: "Align IoU",
    edge_fidelity: "Edge Fidelity",
    poset_f1: "Hierarchy F₁",
    poset_reachability_f1: "Reachability F₁",
    polarity_accuracy: "Polarity Acc",
    polarity_conflict_rate: "Polarity Conflict",
    precision: "Precision",
    recall: "Recall",
  };

  const stagedCount = stagedAdjudications.size;

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

  // Dynamically resolve metrics to display based on report key_metrics
  const displayMetrics = React.useMemo(() => {
    if (!activeReport?.key_metrics) return [];
    const km = activeReport.key_metrics;

    // Preferred key order: prioritized canonical metrics if present
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
      "ece",
      "mrr",
    ];

    const selectedKeys: string[] = [];
    for (const key of preferredOrder) {
      if (km[key] !== undefined && km[key] !== null) {
        if (!selectedKeys.includes(key)) {
          selectedKeys.push(key);
        }
      }
      if (selectedKeys.length >= 4) break;
    }

    // Fall back to other available numeric metrics if fewer than 4 found
    if (selectedKeys.length < 4) {
      for (const [key, val] of Object.entries(km)) {
        if (!selectedKeys.includes(key) && typeof val === "number") {
          selectedKeys.push(key);
        }
        if (selectedKeys.length >= 4) break;
      }
    }

    return selectedKeys.map((k) => ({
      key: k,
      label: METRIC_LABELS[k] || k.replace(/_/g, " ").toUpperCase(),
      value: km[k],
      delta: k === "f1" || k === "macro_f1" ? optimisticScalarDeltas.f1 : 0,
    }));
  }, [activeReport?.key_metrics, optimisticScalarDeltas.f1]);

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
                  <span
                    className="text-xs font-mono text-app-muted truncate max-w-[140px]"
                    title={activeReport.dataset_ref}
                  >
                    {activeReport.dataset_ref.split("/").pop() || activeReport.dataset_ref}
                  </span>
                  <span className="text-app-muted">/</span>
                </>
              )}
              <h1
                className="text-xs font-mono font-semibold text-app-heading truncate max-w-sm"
                title={activeReport ? activeReport.evaluation_id : ""}
              >
                {activeReport ? activeReport.evaluation_id : "Select an Evaluation Run"}
              </h1>
            </div>
          </div>

          {/* Center-Right: Dynamic KPI Strip with Tabular Numerals */}
          {activeReport && displayMetrics.length > 0 && showKpiStrip && (
            <div className="hidden md:flex items-center gap-4 text-xs font-mono tabular-nums animate-in fade-in duration-100">
              {displayMetrics.map((m, idx) => (
                <React.Fragment key={m.key}>
                  {idx > 0 && <div className="h-5 w-px bg-app-border" />}
                  <div className="flex flex-col items-end">
                    <span className="text-[10px] uppercase text-app-muted font-sans font-semibold">
                      {m.label}
                    </span>
                    <span className="text-xs font-semibold text-app-text">
                      {m.value.toFixed(3)}
                      {m.delta !== 0 && (
                        <span className="ml-1 text-[10px] font-normal text-emerald-500">
                          ({m.delta > 0 ? "+" : ""}
                          {m.delta.toFixed(3)})
                        </span>
                      )}
                    </span>
                  </div>
                </React.Fragment>
              ))}
            </div>
          )}

          {/* Action Bar */}
          <div className="flex items-center gap-2 pl-2">
            {activeReport && displayMetrics.length > 0 && (
              <button
                onClick={toggleKpiStrip}
                className={`p-1.5 rounded text-xs font-medium border transition-colors cursor-pointer ${
                  showKpiStrip
                    ? "bg-app-bg text-app-muted hover:text-app-text border-app-border"
                    : "bg-blue-500/10 text-blue-500 border-blue-500/30"
                }`}
                title={showKpiStrip ? "Hide Header KPIs to reduce distraction" : "Show Header KPIs"}
              >
                {showKpiStrip ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            )}

            <button
              onClick={() => {
                if (activeReport?.run_ids?.[0]) {
                  setTargetRunId(activeReport.run_ids[0]);
                }
                setActiveMode("execute");
              }}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors cursor-pointer"
              title="Navigate to dedicated On-Demand Evaluation Studio"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Evaluation</span>
            </button>

            {activeReport && (
              <>
                <button
                  onClick={() => setIsExportModalOpen(true)}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-app-bg hover:bg-app-subtle text-app-text border border-app-border transition-colors cursor-pointer"
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
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text border border-app-border transition-colors cursor-pointer"
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
              const badge =
                tab.id === "adjudication" && stagedCount > 0
                  ? stagedCount
                  : null;

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
                  {badge && (
                    <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono font-semibold bg-amber-500/20 text-amber-500">
                      {badge}
                    </span>
                  )}
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
