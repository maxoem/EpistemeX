import React, { useState } from "react";
import {
  BookOpen,
  Download,
  Filter,
  Layers,
  Network,
  Play,
  Sliders,
  Sparkles,
  Wrench,
  Eye,
  EyeOff,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { ExportReportModal } from "./ExportReportModal";
import { ExecuteEvaluationModal } from "./ExecuteEvaluationModal";
import { openPhasePromptInExecution } from "./ActionableHookPill";
import type { EvaluationSubTab } from "../../../api/types";

export interface EvaluationHeaderProps {
  onOpenConfigEditor?: () => void;
}

const SUB_TABS: Array<{ id: EvaluationSubTab; label: string; icon: React.ElementType }> = [
  { id: "canvas", label: "Topological Canvas", icon: Network },
  { id: "epistemics", label: "Epistemic TheoryNet", icon: Layers },
  { id: "adjudication", label: "Adjudication Workspace", icon: Sliders },
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

  return (
    <>
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Single Consolidated Sub-Nav & Metrology Header (Clean 38px)         */}
      {/* Eliminated redundant breadcrumb bar repeating run name & status      */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-10 px-3 border-b border-app-border bg-app-surface flex items-center justify-between gap-3 shrink-0 select-none overflow-x-auto text-xs">
        {/* Left: Sub-Nav Tab Group */}
        <div className="flex items-center gap-1 shrink-0">
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
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors whitespace-nowrap cursor-pointer ${
                  isActive
                    ? "bg-blue-600/10 text-blue-600 dark:bg-blue-500/15 dark:text-blue-400 font-medium"
                    : "text-app-muted hover:text-app-text hover:bg-app-subtle"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
                {badge && (
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] tabular-nums font-medium bg-amber-500/20 text-amber-500">
                    {badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Right: Consolidated KPIs & Quick Actions */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Dynamic KPI Strip */}
          {activeReport && displayMetrics.length > 0 && showKpiStrip && (
            <div className="hidden lg:flex items-center gap-3 text-xs tabular-nums">
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
                        ({m.delta > 0 ? "+" : ""}{m.delta.toFixed(3)})
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* KPI toggle */}
          {activeReport && displayMetrics.length > 0 && (
            <button
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
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-1.5">
            <button
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
                  onClick={() => setIsExportModalOpen(true)}
                  className="p-1 rounded bg-app-bg hover:bg-app-subtle text-app-text border border-app-border transition-colors cursor-pointer"
                  title="Export Report"
                >
                  <Download className="w-3.5 h-3.5 text-blue-500" />
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
                  className="p-1 rounded bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text border border-app-border transition-colors cursor-pointer"
                  title="Tune Prompt in ConfigEditor"
                >
                  <Wrench className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </div>
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
