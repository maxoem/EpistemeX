import React, { useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Cpu,
  Layers,
  Network,
  Play,
  Sliders,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { apiClient } from "../../../api/client";
import { useEvaluationJob } from "../hooks/useEvaluationJob";
import { JobProgressStepper } from "./JobProgressStepper";
import type { EvaluateRunRequest } from "../../../api/types";

export interface ExecuteEvaluationModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultRunId?: string;
}

type EvalMode = "benchmark_alignment" | "structuralist" | "competency_retrieval" | "stress_test";

export const ExecuteEvaluationModal: React.FC<ExecuteEvaluationModalProps> = ({
  isOpen,
  onClose,
  defaultRunId = "",
}) => {
  const {
    benchmarks,
    setActiveReportId,
    setActiveMode,
    setActiveSubTab,
    fetchReports,
  } = useEvaluationStore();

  const [mode, setMode] = useState<EvalMode>("benchmark_alignment");
  const [runId, setRunId] = useState(defaultRunId);
  const [benchmarkId, setBenchmarkId] = useState(benchmarks[0]?.id || "stnb_cpm_pilot");
  const [strategy, setStrategy] = useState("structuralist");
  const [simThreshold, setSimThreshold] = useState(0.85);
  const [deltaStar, setDeltaStar] = useState(0.10);
  const [minMcc, setMinMcc] = useState(1.0);
  const [minPfs, setMinPfs] = useState(0.8);
  const [evaluateRetrieval, setEvaluateRetrieval] = useState(false);

  // Active Job State
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const jobHook = useEvaluationJob({
    jobId: activeJobId,
    onCompleted: (reportId) => {
      fetchReports();
    },
  });

  if (!isOpen) return null;

  const handleExecute = async () => {
    if (!runId.trim()) {
      setSubmitError("Please enter or select a valid Run ID.");
      return;
    }

    setSubmitError(null);
    setIsSubmitting(true);

    try {
      const payload: EvaluateRunRequest = {
        run_id: runId.trim(),
        benchmark_id: mode === "benchmark_alignment" ? benchmarkId : undefined,
        strategy: strategy,
        sim_threshold: simThreshold,
        delta_star: deltaStar,
        min_mcc: minMcc,
        min_pfs: minPfs,
        mode: mode,
        evaluate_retrieval: evaluateRetrieval,
        persist: true,
      };

      const descriptor = await apiClient.startRunEvaluationJob(payload);
      setActiveJobId(descriptor.job_id);
    } catch (e: any) {
      setSubmitError(e.message || "Failed to dispatch evaluation job.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetToNewJob = () => {
    setActiveJobId(null);
    setSubmitError(null);
  };

  const handleOpenReport = (reportId: string) => {
    setActiveReportId(reportId);
    setActiveMode("inspector");
    onClose();
  };

  const handleOpenCanvas = (reportId: string) => {
    setActiveReportId(reportId);
    setActiveMode("inspector");
    setActiveSubTab("canvas");
    onClose();
  };

  const handleOpenAdjudication = (reportId: string) => {
    setActiveReportId(reportId);
    setActiveMode("inspector");
    setActiveSubTab("adjudication");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
      <div className="bg-app-surface border border-app-border rounded-xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-5 py-3.5 border-b border-app-border flex items-center justify-between shrink-0 bg-app-subtle">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-app-text">Execute On-Demand Evaluation</h2>
              <p className="text-[11px] text-app-muted">
                Run structuralist alignment, intrinsic tenability, or competency suites
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-md text-app-muted hover:text-app-text hover:bg-app-surface transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {activeJobId ? (
            /* Active Job Progress View */
            <div className="space-y-4">
              <JobProgressStepper
                jobId={activeJobId}
                status={jobHook.status}
                progress={jobHook.progress}
                currentStage={jobHook.currentStage}
                events={jobHook.events}
                error={jobHook.error}
                reportId={jobHook.reportId}
                isCancelling={jobHook.isCancelling}
                onCancel={jobHook.cancelJob}
                onOpenReport={handleOpenReport}
                onOpenCanvas={handleOpenCanvas}
                onOpenAdjudication={handleOpenAdjudication}
                onClose={onClose}
              />

              {(jobHook.status === "failed" || jobHook.status === "aborted") && (
                <div className="pt-2 text-center">
                  <button
                    type="button"
                    onClick={handleResetToNewJob}
                    className="text-xs text-blue-500 hover:underline font-medium"
                  >
                    ← Configure and start another evaluation
                  </button>
                </div>
              )}
            </div>
          ) : (
            /* Configuration Wizard Form */
            <div className="space-y-4">
              {submitError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-500 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{submitError}</span>
                </div>
              )}

              {/* Mode Selection */}
              <div>
                <label className="block text-xs font-semibold text-app-text mb-2">
                  1. Evaluation Mode
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setMode("benchmark_alignment")}
                    className={`p-3 rounded-lg border text-left transition-all cursor-pointer ${
                      mode === "benchmark_alignment"
                        ? "bg-blue-500/10 border-blue-500/60 ring-1 ring-blue-500/20"
                        : "bg-app-subtle border-app-border hover:border-app-border/80"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-medium text-xs text-app-text">
                      <Network className="w-4 h-4 text-blue-500" />
                      <span>Benchmark Alignment</span>
                    </div>
                    <p className="text-[11px] text-app-muted mt-1">
                      Compare predicted graph against a gold standard using Hungarian GM-GBS.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setMode("structuralist")}
                    className={`p-3 rounded-lg border text-left transition-all cursor-pointer ${
                      mode === "structuralist"
                        ? "bg-blue-500/10 border-blue-500/60 ring-1 ring-blue-500/20"
                        : "bg-app-subtle border-app-border hover:border-app-border/80"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-medium text-xs text-app-text">
                      <Layers className="w-4 h-4 text-emerald-500" />
                      <span>Intrinsic Structuralist</span>
                    </div>
                    <p className="text-[11px] text-app-muted mt-1">
                      Verify Bourbaki quintuple decomposition and Sneedian tenability blur \(\delta^*\).
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setMode("competency_retrieval")}
                    className={`p-3 rounded-lg border text-left transition-all cursor-pointer ${
                      mode === "competency_retrieval"
                        ? "bg-blue-500/10 border-blue-500/60 ring-1 ring-blue-500/20"
                        : "bg-app-subtle border-app-border hover:border-app-border/80"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-medium text-xs text-app-text">
                      <Activity className="w-4 h-4 text-purple-500" />
                      <span>Competency Retrieval</span>
                    </div>
                    <p className="text-[11px] text-app-muted mt-1">
                      Execute domain query benchmark to score Mean Reciprocal Rank (MRR) & Hits@k.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setMode("stress_test")}
                    className={`p-3 rounded-lg border text-left transition-all cursor-pointer ${
                      mode === "stress_test"
                        ? "bg-blue-500/10 border-blue-500/60 ring-1 ring-blue-500/20"
                        : "bg-app-subtle border-app-border hover:border-app-border/80"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-medium text-xs text-app-text">
                      <Zap className="w-4 h-4 text-amber-500" />
                      <span>Adversarial Stress Test</span>
                    </div>
                    <p className="text-[11px] text-app-muted mt-1">
                      Simulate OCR typos, sentence permutations, and measure semantic drift factor.
                    </p>
                  </button>
                </div>
              </div>

              {/* Target Run ID */}
              <div>
                <label className="block text-xs font-semibold text-app-text mb-1">
                  2. Target Pipeline Run
                </label>
                <input
                  type="text"
                  value={runId}
                  onChange={(e) => setRunId(e.target.value)}
                  placeholder="e.g. run-kant-cpr-v1 or uuid..."
                  className="w-full px-3 py-1.5 text-xs font-mono rounded-md bg-app-subtle border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder:text-app-muted"
                />
              </div>

              {/* Gold Benchmark Dropdown */}
              {mode === "benchmark_alignment" && (
                <div>
                  <label className="block text-xs font-semibold text-app-text mb-1">
                    3. Gold Standard Benchmark
                  </label>
                  <select
                    value={benchmarkId}
                    onChange={(e) => setBenchmarkId(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded-md bg-app-subtle border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text"
                  >
                    {benchmarks.length === 0 ? (
                      <option value="stnb_cpm_pilot">STNB CPM Pilot Benchmark (stnb_cpm_pilot.jsonld)</option>
                    ) : (
                      benchmarks.map((bm) => (
                        <option key={bm.id} value={bm.id}>
                          {bm.name} ({bm.id}) — {bm.task_type}
                        </option>
                      ))
                    )}
                  </select>
                </div>
              )}

              {/* Hyperparameter Sliders */}
              <div className="p-3.5 rounded-lg bg-app-subtle border border-app-border space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-app-text">
                  <Sliders className="w-3.5 h-3.5 text-blue-500" />
                  <span>Evaluation Hyperparameters</span>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Soft Threshold tau */}
                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-app-muted">Alignment Threshold \(\tau\)</span>
                      <span className="font-mono font-semibold text-app-text">
                        {simThreshold.toFixed(2)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0.5}
                      max={1.0}
                      step={0.05}
                      value={simThreshold}
                      onChange={(e) => setSimThreshold(parseFloat(e.target.value))}
                      className="w-full accent-blue-600 h-1.5"
                    />
                  </div>

                  {/* Tenability Blur delta* */}
                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-app-muted">Tenability Blur \(\delta^*\)</span>
                      <span className="font-mono font-semibold text-app-text">
                        {deltaStar.toFixed(2)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0.0}
                      max={0.5}
                      step={0.02}
                      value={deltaStar}
                      onChange={(e) => setDeltaStar(parseFloat(e.target.value))}
                      className="w-full accent-emerald-600 h-1.5"
                    />
                  </div>

                  {/* Model Component Completeness (MCC) */}
                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-app-muted">Min Completeness (MCC)</span>
                      <span className="font-mono font-semibold text-app-text">
                        {minMcc.toFixed(2)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0.5}
                      max={1.0}
                      step={0.05}
                      value={minMcc}
                      onChange={(e) => setMinMcc(parseFloat(e.target.value))}
                      className="w-full accent-purple-600 h-1.5"
                    />
                  </div>

                  {/* Property Fidelity Score (PFS) */}
                  <div>
                    <div className="flex justify-between text-[11px] mb-1">
                      <span className="text-app-muted">Min Property Fidelity (PFS)</span>
                      <span className="font-mono font-semibold text-app-text">
                        {minPfs.toFixed(2)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0.5}
                      max={1.0}
                      step={0.05}
                      value={minPfs}
                      onChange={(e) => setMinPfs(parseFloat(e.target.value))}
                      className="w-full accent-amber-600 h-1.5"
                    />
                  </div>
                </div>

                <div className="pt-2 border-t border-app-border/60">
                  <label className="flex items-center gap-2 text-xs text-app-text cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={evaluateRetrieval}
                      onChange={(e) => setEvaluateRetrieval(e.target.checked)}
                      className="rounded border-app-border accent-blue-600"
                    />
                    <span>Enable downstream competency query retrieval scoring (MRR / nDCG)</span>
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        {!activeJobId && (
          <div className="px-5 py-3 border-t border-app-border flex items-center justify-between shrink-0 bg-app-subtle">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-md text-xs font-medium text-app-muted hover:text-app-text hover:bg-app-surface transition-colors"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleExecute}
              disabled={isSubmitting || !runId.trim()}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50 cursor-pointer"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isSubmitting ? "Dispatching..." : "Execute Evaluation"}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
