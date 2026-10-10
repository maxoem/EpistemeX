import React, {useState} from "react";
import {useRunsStore} from "../store/runsStore";
import {useDiffStore} from "../store/diffStore";
import {AlertTriangle, ArrowRight, CheckCircle2, GitCompare, X} from "lucide-react";

interface RunCompareModalProps {
  onNavigateToGraph?: () => void;
}

export const RunCompareModal: React.FC<RunCompareModalProps> = ({ onNavigateToGraph }) => {
  const { runs, selectedRunId } = useRunsStore();
  const { isCompareModalOpen, setIsCompareModalOpen, startDiff } = useDiffStore();

  const [baseRunId, setBaseRunId] = useState<string>(selectedRunId || (runs[0]?.run_id ?? ""));
  const [candidateRunId, setCandidateRunId] = useState<string>(
    runs.find((r) => r.run_id !== baseRunId)?.run_id ?? ""
  );

  if (!isCompareModalOpen) return null;

  const baseRun = runs.find((r) => r.run_id === baseRunId);
  const candidateRun = runs.find((r) => r.run_id === candidateRunId);

  const baseSource = baseRun?.primary_input || baseRun?.input_sources?.[0] || "";
  const candidateSource = candidateRun?.primary_input || candidateRun?.input_sources?.[0] || "";
  const sourcesMatch = Boolean(baseSource && candidateSource && baseSource === candidateSource);

  const handleStartComparison = async () => {
    if (!baseRunId || !candidateRunId || baseRunId === candidateRunId) return;
    setIsCompareModalOpen(false);
    await startDiff(baseRunId, candidateRunId);
    if (onNavigateToGraph) {
      onNavigateToGraph();
    }
  };

  const renderRunSelector = (
    runId: string,
    setRunId: (v: string) => void,
    label: string,
    namespace: string,
    accent: string,
    run: typeof baseRun,
    source: string
  ) => (
    <div className="space-y-2">
      <div className="flex items-center justify-between border-b border-app-border pb-2">
        <span className={`text-[11px] font-semibold uppercase tracking-wider ${accent}`}>{label}</span>
        <span className="font-mono text-[10px] text-app-muted">{namespace}</span>
      </div>

      <select
        value={runId}
        onChange={(e) => setRunId(e.target.value)}
        className="w-full h-8 px-2.5 rounded bg-app-bg text-app-heading border border-app-border text-xs font-mono focus:outline-none focus:border-blue-500"
      >
        {runs.map((r) => (
          <option key={r.run_id} value={r.run_id}>
            {r.run_id} ({r.models?.llm_model?.split("/").pop() || "LLM"})
          </option>
        ))}
      </select>

      <div className="pt-0.5 divide-y divide-app-border-subtle">
        <div className="flex items-center justify-between gap-3 py-1.5">
          <span className="text-[11px] text-app-muted shrink-0">Model</span>
          <span className="font-mono text-[11px] text-app-heading truncate text-right">
            {run?.models?.llm_model || "unknown model"}
            {run?.models?.thinking_level ? ` · ${run.models.thinking_level}` : ""}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3 py-1.5">
          <span className="text-[11px] text-app-muted shrink-0">Source</span>
          <span className="font-mono text-[11px] text-app-heading truncate text-right">
            {source || "No source recorded"}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3 py-1.5">
          <span className="text-[11px] text-app-muted shrink-0">Artifacts</span>
          <span className="font-mono text-[11px] text-app-heading">{run?.artifact_count ?? "—"}</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150 select-none">
      <div className="bg-app-surface border border-app-border rounded-xl shadow-2xl max-w-2xl w-full flex flex-col overflow-hidden text-xs">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-app-border bg-app-surface">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-blue-500/10 text-blue-500 border border-blue-500/20">
              <GitCompare className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-app-heading">Compare Pipeline Runs</h2>
              <p className="text-[11px] text-app-muted">
                Audit progression, degenerations, polarity shifts, and argument structure deltas.
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsCompareModalOpen(false)}
            className="p-1 rounded-md text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-5">
          {/* Compare Matrix */}
          <div className="grid grid-cols-1 sm:grid-cols-2 sm:gap-5">
            <div>
              {renderRunSelector(
                baseRunId,
                setBaseRunId,
                "Baseline",
                "run_a",
                "text-blue-600 dark:text-blue-400",
                baseRun,
                baseSource
              )}
            </div>
            <div className="sm:border-l sm:border-app-border sm:pl-5 mt-4 sm:mt-0">
              {renderRunSelector(
                candidateRunId,
                setCandidateRunId,
                "Candidate",
                "run_b",
                "text-emerald-600 dark:text-emerald-400",
                candidateRun,
                candidateSource
              )}
            </div>
          </div>

          {/* Compatibility Status */}
          {baseRunId && candidateRunId && (
            <div
              className={`flex items-start gap-2.5 border-l-2 py-1 pl-3 ${
                sourcesMatch ? "border-emerald-500" : "border-amber-500"
              }`}
            >
              {sourcesMatch ? (
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-500" />
              ) : (
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-500" />
              )}
              <div className="text-[11px] leading-relaxed text-app-muted">
                {sourcesMatch ? (
                  <>
                    <strong className="font-semibold text-app-heading">Ideal Comparison Scenario (D-18):</strong>{" "}
                    Both runs operated over identical input documents. Deterministic entity hashes
                    will match 1:1, allowing exact discovery and polarity shift auditing.
                  </>
                ) : (
                  <>
                    <strong className="font-semibold text-app-heading">Corpus Disparity Warning:</strong> The
                    selected runs appear to originate from different source documents or inputs.
                    Entities and argument components may not share identical content hashes.
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-app-border bg-app-subtle/50">
          <span className="text-[11px] text-app-muted">
            {baseRunId === candidateRunId
              ? "Select two distinct runs to compare."
              : "Union topology will be visualized in the Graph Explorer."}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsCompareModalOpen(false)}
              className="h-8 px-3 rounded border border-app-border bg-app-surface hover:bg-app-subtle text-app-heading transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleStartComparison}
              disabled={!baseRunId || !candidateRunId || baseRunId === candidateRunId}
              className="h-8 px-3.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shadow-xs"
            >
              <span>Launch Comparison</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
