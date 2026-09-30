import React, { useState } from "react";
import {
  Activity,
  AlertCircle,
  Ban,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  ExternalLink,
  Layers,
  Network,
  RotateCcw,
  Sliders,
  Sparkles,
  Terminal,
} from "lucide-react";
import type { EvaluationJobStatus, StudioEvent } from "../../../api/types";

export interface JobProgressStepperProps {
  jobId: string;
  status: EvaluationJobStatus;
  progress: number;
  currentStage: string;
  events: StudioEvent[];
  error?: string | null;
  reportId?: string | null;
  isCancelling?: boolean;
  onCancel?: () => void;
  onOpenReport?: (reportId: string) => void;
  onOpenCanvas?: (reportId: string) => void;
  onOpenAdjudication?: (reportId: string) => void;
  onClose?: () => void;
}

const STAGES = [
  { id: "load", label: "Envelope & Artifact Loading", icon: Layers },
  { id: "align", label: "Hungarian GM-GBS Alignment", icon: Network },
  { id: "tenability", label: "Structuralist Poset Verification", icon: Sparkles },
  { id: "retrieval", label: "Extrinsic Competency Retrieval", icon: Activity },
  { id: "report", label: "Report Synthesis & Materialization", icon: CheckCircle2 },
];

export const JobProgressStepper: React.FC<JobProgressStepperProps> = ({
  jobId,
  status,
  progress,
  currentStage,
  events,
  error,
  reportId,
  isCancelling,
  onCancel,
  onOpenReport,
  onOpenCanvas,
  onOpenAdjudication,
  onClose,
}) => {
  const [showLogs, setShowLogs] = useState(false);

  const getStageStatus = (stageIdx: number) => {
    if (status === "completed") return "completed";
    if (status === "failed" || status === "aborted") {
      const activeIdx = Math.min(Math.floor((progress / 100) * STAGES.length), STAGES.length - 1);
      if (stageIdx < activeIdx) return "completed";
      if (stageIdx === activeIdx) return status;
      return "upcoming";
    }
    const currentActiveIdx = Math.min(Math.floor((progress / 100) * STAGES.length), STAGES.length - 1);
    if (stageIdx < currentActiveIdx) return "completed";
    if (stageIdx === currentActiveIdx) return "active";
    return "upcoming";
  };

  const renderStatusBadge = () => {
    switch (status) {
      case "pending":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-500/10 text-amber-500 border border-amber-500/30">
            <Clock className="w-3.5 h-3.5 animate-spin" />
            PENDING
          </span>
        );
      case "running":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-500 border border-blue-500/30">
            <Activity className="w-3.5 h-3.5 animate-pulse" />
            RUNNING
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-500 border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5" />
            COMPLETED
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-rose-500/10 text-rose-500 border border-rose-500/30">
            <AlertCircle className="w-3.5 h-3.5" />
            FAILED
          </span>
        );
      case "aborted":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-zinc-500/10 text-zinc-400 border border-zinc-500/30">
            <Ban className="w-3.5 h-3.5" />
            ABORTED
          </span>
        );
    }
  };

  return (
    <div className="border border-app-border rounded-md overflow-hidden bg-app-bg divide-y divide-app-border">
      {/* Top Header Card */}
        <div className="flex items-center justify-between p-3">
        <div className="flex items-center gap-3">
          <Sparkles className="w-5 h-5 text-blue-500" />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold text-app-text">{jobId}</span>
              {renderStatusBadge()}
            </div>
            <p className="text-xs text-app-muted mt-0.5">{currentStage}</p>
          </div>
        </div>

        <div className="text-right">
          <span className="font-mono text-sm font-bold text-app-text">{Math.round(progress)}%</span>
          <p className="text-[10px] text-app-muted">Progress</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="px-3 py-2.5">
        <div className="w-full bg-app-subtle rounded-full h-2 overflow-hidden border border-app-border">
          <div
            className={`h-full transition-all duration-300 ${
              status === "failed"
                ? "bg-rose-500"
                : status === "aborted"
                ? "bg-zinc-500"
                : status === "completed"
                ? "bg-emerald-500"
                : "bg-blue-600"
            }`}
            style={{ width: `${Math.max(5, progress)}%` }}
          />
        </div>
      </div>

      {/* Multi-Stage Visual Stepper */}
      <div className="divide-y divide-app-border">
        {STAGES.map((s, idx) => {
          const stageState = getStageStatus(idx);
          const Icon = s.icon;
          return (
            <div
              key={s.id}
              className={`flex items-center gap-3 px-3 py-2 text-xs transition-colors ${
                stageState === "active"
                  ? "bg-blue-500/10 text-blue-500 dark:text-blue-400 font-medium border-l-2 border-blue-500"
                  : stageState === "completed"
                  ? "bg-transparent text-app-text border-l-2 border-emerald-500/60"
                  : stageState === "failed"
                  ? "bg-rose-500/10 text-rose-500 font-medium border-l-2 border-rose-500"
                  : stageState === "aborted"
                  ? "bg-zinc-500/5 text-app-muted border-l-2 border-zinc-500"
                  : "bg-transparent text-app-muted opacity-60 border-l-2 border-transparent"
              }`}
            >
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 text-[10px] font-semibold ${
                  stageState === "active"
                    ? "bg-blue-500 text-white"
                    : stageState === "completed"
                    ? "bg-emerald-500 text-white"
                    : stageState === "failed"
                    ? "bg-rose-500 text-white"
                    : stageState === "aborted"
                    ? "bg-zinc-600 text-white"
                    : "bg-app-subtle border border-app-border text-app-muted"
                }`}
              >
                {stageState === "completed" ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : (
                  <span>{idx + 1}</span>
                )}
              </div>

              <div className="flex-1 min-w-0">
                <span className="truncate">{s.label}</span>
              </div>

              <Icon className="w-3.5 h-3.5 shrink-0 opacity-80" />
            </div>
          );
        })}
      </div>

      {/* Error / Aborted Banner */}
      {error && (
        <div className="p-3 rounded bg-rose-500/10 border border-rose-500/30 text-rose-500 text-xs">
          <div className="font-semibold flex items-center gap-1.5 mb-1">
            <AlertCircle className="w-4 h-4" />
            Evaluation Failed
          </div>
          <p className="font-mono text-[11px] opacity-90 break-words">{error}</p>
        </div>
      )}

      {status === "aborted" && !error && (
        <div className="p-3 rounded bg-zinc-500/10 border border-zinc-500/30 text-app-muted text-xs">
          <div className="font-semibold flex items-center gap-1.5 mb-1 text-app-text">
            <Ban className="w-4 h-4 text-zinc-400" />
            Job Aborted
          </div>
          <p className="text-[11px]">The evaluation run was cancelled before completion.</p>
        </div>
      )}

      {/* Telemetry Stream Collapsible Log */}
      <div>
        <button
          type="button"
          onClick={() => setShowLogs(!showLogs)}
          className="w-full px-3 py-2 text-xs flex items-center justify-between text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
        >
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5" />
            <span>Telemetry Event Log ({events.length} events)</span>
          </div>
          {showLogs ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>

        {showLogs && (
          <div className="p-2.5 max-h-48 overflow-y-auto font-mono text-[11px] space-y-1.5 bg-app-bg text-app-muted select-text">
            {events.length === 0 ? (
              <span className="text-app-muted/60 italic">Awaiting telemetry stream...</span>
            ) : (
              events.map((ev, i) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-app-muted/60 shrink-0">#{ev.seq}</span>
                  <span
                    className={
                      ev.level === "error"
                        ? "text-rose-400"
                        : ev.level === "warning"
                        ? "text-amber-400"
                        : "text-blue-400"
                    }
                  >
                    [{ev.kind}]
                  </span>
                  <span className="truncate">{ev.message}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="px-3 py-3 flex items-center justify-between">
        {(status === "running" || status === "pending") && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={isCancelling}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border border-rose-500/30 transition-colors disabled:opacity-50"
          >
            <Ban className="w-3.5 h-3.5" />
            <span>{isCancelling ? "Cancelling..." : "Cancel Job"}</span>
          </button>
        )}

        {status === "completed" && reportId && (
          <div className="flex items-center gap-2 flex-wrap">
            {onOpenReport && (
              <button
                type="button"
                onClick={() => onOpenReport(reportId)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>View Full Report</span>
              </button>
            )}
            {onOpenCanvas && (
              <button
                type="button"
                onClick={() => onOpenCanvas(reportId)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-app-subtle hover:bg-app-subtle/80 text-app-text border border-app-border transition-colors"
              >
                <Network className="w-3.5 h-3.5 text-blue-500" />
                <span>Open Canvas Overlay</span>
              </button>
            )}
            {onOpenAdjudication && (
              <button
                type="button"
                onClick={() => onOpenAdjudication(reportId)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-app-subtle hover:bg-app-subtle/80 text-app-text border border-app-border transition-colors"
              >
                <Sliders className="w-3.5 h-3.5 text-amber-500" />
                <span>Adjudication Queue</span>
              </button>
            )}
          </div>
        )}

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="ml-auto px-3 py-1.5 rounded text-xs font-medium bg-app-subtle hover:bg-app-subtle/80 text-app-text border border-app-border transition-colors"
          >
            Close
          </button>
        )}
      </div>
    </div>
  );
};
