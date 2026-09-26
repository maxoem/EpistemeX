import React, { useState } from "react";
import { Play, Sparkles, X, CheckCircle2, AlertCircle } from "lucide-react";
import { api } from "../../../api/client";
import { useEvaluationStore } from "../../../store/evaluationStore";
import { useLeaderboardStore } from "../../../store/leaderboardStore";
import { useRunsStore } from "../../../store/runsStore";
import type { EvaluateRunRequest } from "../../../api/types";

interface FastEvaluateModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultBenchmarkId?: string;
  onSuccess?: (evalId: string) => void;
}

export const FastEvaluateModal: React.FC<FastEvaluateModalProps> = ({
  isOpen,
  onClose,
  defaultBenchmarkId,
  onSuccess,
}) => {
  const { benchmarks, fetchReports, setActiveReportId, setActiveMode } = useEvaluationStore();
  const { fetchLeaderboard } = useLeaderboardStore();
  const { runs } = useRunsStore();

  const [selectedRunId, setSelectedRunId] = useState<string>(runs[0]?.run_id || "");
  const [selectedBenchmarkId, setSelectedBenchmarkId] = useState<string>(
    defaultBenchmarkId || benchmarks[0]?.id || ""
  );
  const [strategy, setStrategy] = useState<string>("structuralist_poset");
  const [simThreshold, setSimThreshold] = useState<number>(0.85);

  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRunId.trim()) {
      setError("Please select or enter a pipeline run ID.");
      return;
    }

    setIsEvaluating(true);
    setError(null);

    try {
      const payload: EvaluateRunRequest = {
        run_id: selectedRunId.trim(),
        benchmark_id: selectedBenchmarkId || undefined,
        strategy,
        sim_threshold: simThreshold,
        persist: true,
      };

      const report = await api.evaluateRun(payload);

      await fetchReports();
      await fetchLeaderboard({ benchmark_id: selectedBenchmarkId });

      setActiveReportId(report.evaluation_id);
      onSuccess?.(report.evaluation_id);
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to evaluate pipeline run");
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs select-none p-4">
      <div className="w-full max-w-md bg-app-surface border border-app-border rounded-lg shadow-2xl flex flex-col overflow-hidden text-app-text animate-in zoom-in-95 duration-150 font-sans">
        {/* Header */}
        <div className="h-12 px-4 border-b border-app-border flex items-center justify-between shrink-0 bg-app-bg/50">
          <div className="flex items-center gap-2">
            <div className="p-1 rounded bg-blue-500/10 text-blue-500 border border-blue-500/30">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-xs font-semibold text-app-heading">
                Fast Post-Hoc Run Evaluation
              </h2>
              <p className="text-[10px] text-app-muted">
                Evaluate existing cached run artifacts against reference benchmarks in seconds
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleEvaluate} className="p-4 space-y-3.5 text-xs">
          {error && (
            <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs">
              {error}
            </div>
          )}

          {/* Select Run */}
          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Select Pipeline Run *
            </label>
            {runs.length > 0 ? (
              <select
                value={selectedRunId}
                onChange={(e) => setSelectedRunId(e.target.value)}
                className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden font-mono"
              >
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id} ({Object.values(r.models || {})[0] || "Default Model"}) — {r.status}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={selectedRunId}
                onChange={(e) => setSelectedRunId(e.target.value)}
                placeholder="Enter run ID, e.g. run-2026-09-082"
                className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden font-mono"
                required
              />
            )}
          </div>

          {/* Select Target Benchmark */}
          <div>
            <label className="block text-[11px] font-medium text-app-muted mb-1">
              Reference Benchmark Dataset
            </label>
            <select
              value={selectedBenchmarkId}
              onChange={(e) => setSelectedBenchmarkId(e.target.value)}
              className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden"
            >
              {benchmarks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.id})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            {/* Strategy */}
            <div>
              <label className="block text-[11px] font-medium text-app-muted mb-1">
                Evaluation Strategy
              </label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="w-full bg-app-bg text-app-text px-2.5 py-1.5 rounded border border-app-border text-xs focus:border-blue-500 focus:outline-hidden"
              >
                <option value="structuralist_poset">Bourbaki Poset DAG</option>
                <option value="triple_alignment">Soft Triple Alignment</option>
                <option value="strict_isomorphism">Strict Graph Isomorphism</option>
              </select>
            </div>

            {/* Sim Threshold */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-[11px] font-medium text-app-muted">Alignment Threshold (τ)</label>
                <span className="font-mono text-[10px] text-app-text font-semibold">
                  {simThreshold.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min="0.5"
                max="0.99"
                step="0.01"
                value={simThreshold}
                onChange={(e) => setSimThreshold(parseFloat(e.target.value))}
                className="w-full accent-blue-600"
              />
            </div>
          </div>

          {/* Notice */}
          <div className="p-2.5 rounded bg-app-subtle border border-app-border text-app-muted text-[11px] leading-tight">
            Executes full in-memory epistemic validation: Bourbaki completeness, poset acyclicity, and ECE without re-invoking LLM API calls.
          </div>

          {/* Footer Actions */}
          <div className="pt-2 border-t border-app-border flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded text-xs font-medium text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isEvaluating || !selectedRunId}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 transition-colors shadow-xs"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{isEvaluating ? "Evaluating..." : "Run Post-Hoc Evaluation"}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
