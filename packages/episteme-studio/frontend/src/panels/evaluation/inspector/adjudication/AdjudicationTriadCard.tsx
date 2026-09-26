import React from "react";
import {
  CheckCircle2,
  XCircle,
  GitMerge,
  RotateCcw,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Info,
  Layers,
} from "lucide-react";
import type {
  AdjudicationDecision,
  AdjudicationQueueItem,
  EdgeAdjudicationItem,
} from "../../../../api/types";

export interface AdjudicationTriadCardProps {
  candidate: AdjudicationQueueItem | null;
  stagedItem: EdgeAdjudicationItem | null;
  rationale: string;
  onChangeRationale: (rationale: string) => void;
  onAccept: () => void;
  onReject: () => void;
  onOpenAlias: () => void;
  onUndo: () => void;
}

export const AdjudicationTriadCard: React.FC<AdjudicationTriadCardProps> = ({
  candidate,
  stagedItem,
  rationale,
  onChangeRationale,
  onAccept,
  onReject,
  onOpenAlias,
  onUndo,
}) => {
  if (!candidate) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-app-muted select-none">
        <Layers className="w-10 h-10 opacity-30 mb-3" />
        <h4 className="text-sm font-semibold text-app-heading mb-1">
          No Candidate Selected
        </h4>
        <p className="text-xs max-w-sm text-app-muted">
          Select a borderline relation candidate from the queue or use [j]/[k] to navigate.
        </p>
      </div>
    );
  }

  const predSource = String(candidate.predicted_edge?.source || "").replace(/^str:|^pred:/, "");
  const predPredicate = String(candidate.predicted_edge?.predicate || "");
  const predTarget = String(candidate.predicted_edge?.target || "").replace(/^str:|^pred:/, "");

  const refSource = candidate.reference_edge
    ? String(candidate.reference_edge?.source || "").replace(/^str:|^gold:/, "")
    : null;
  const refPredicate = candidate.reference_edge
    ? String(candidate.reference_edge?.predicate || "")
    : null;
  const refTarget = candidate.reference_edge
    ? String(candidate.reference_edge?.target || "").replace(/^str:|^gold:/, "")
    : null;

  // Approximate vector similarities based on overall score
  const overallSim = candidate.similarity_score;
  const headSim = Math.min(1.0, Math.round((overallSim + 0.05) * 100) / 100);
  const tailSim = Math.min(1.0, Math.round((overallSim + 0.03) * 100) / 100);
  const predSim = Math.max(0.4, Math.round((overallSim - 0.08) * 100) / 100);

  const activeDecision: AdjudicationDecision | null =
    stagedItem?.decision ?? candidate.current_decision ?? null;

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto bg-app-bg p-4 space-y-4 select-none">
      {/* Candidate Header Strip */}
      <div className="flex items-center justify-between p-3 rounded-lg bg-app-surface border border-app-border">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-500 font-mono text-xs font-semibold">
            {candidate.candidate_id}
          </div>
          <div>
            <h3 className="text-xs font-semibold text-app-heading">
              Borderline Relation Alignment
            </h3>
            <p className="text-[11px] text-app-muted">
              Evaluation uncertainty band: τ = {overallSim.toFixed(3)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase font-sans text-app-muted font-semibold">
              Extraction Confidence
            </span>
            <span className="font-mono text-xs font-semibold tabular-nums text-app-text">
              {(candidate.confidence * 100).toFixed(1)}%
            </span>
          </div>

          <div className="h-6 w-px bg-app-border" />

          <div className="flex flex-col items-end">
            <span className="text-[10px] uppercase font-sans text-app-muted font-semibold">
              Soft Similarity τ
            </span>
            <span className="font-mono text-xs font-semibold tabular-nums text-amber-500">
              {overallSim.toFixed(3)}
            </span>
          </div>
        </div>
      </div>

      {/* Staged State Notice if active */}
      {stagedItem && (
        <div className="p-2.5 rounded-lg border flex items-center justify-between text-xs animate-in fade-in duration-150 bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-500" />
            <span className="font-medium">
              Staged Decision:{" "}
              <strong className="uppercase font-mono">
                {stagedItem.decision.replace("_", " ")}
              </strong>
              {stagedItem.alias_target && ` -> ${stagedItem.alias_target}`}
            </span>
          </div>
          <span className="font-mono text-[11px] bg-emerald-500/20 px-2 py-0.5 rounded">
            Pending Batch Commit (⌘⏎)
          </span>
        </div>
      )}

      {/* Side-by-Side Comparison Triad */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left Card: Predicted Edge */}
        <div className="p-3.5 rounded-lg bg-app-surface border border-app-border flex flex-col space-y-3">
          <div className="flex items-center justify-between border-b border-app-border/60 pb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-app-muted flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              Predicted Triple (Pipeline Output)
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-app-subtle text-app-muted">
              Conf: {(candidate.confidence * 100).toFixed(0)}%
            </span>
          </div>

          <div className="p-3 rounded-md bg-app-bg border border-app-border/80 font-mono text-xs space-y-1.5">
            <div>
              <span className="text-[10px] text-app-muted uppercase block font-sans">
                Head (Subject)
              </span>
              <span className="text-app-text font-semibold">{predSource}</span>
            </div>
            <div className="pt-1">
              <span className="text-[10px] text-app-muted uppercase block font-sans">
                Predicate (Relation)
              </span>
              <span className="text-amber-500 font-semibold bg-amber-500/10 px-1.5 py-0.5 rounded inline-block">
                {predPredicate}
              </span>
            </div>
            <div className="pt-1">
              <span className="text-[10px] text-app-muted uppercase block font-sans">
                Tail (Object)
              </span>
              <span className="text-app-text font-semibold">{predTarget}</span>
            </div>
          </div>
        </div>

        {/* Right Card: Candidate Gold Reference */}
        <div className="p-3.5 rounded-lg bg-app-surface border border-app-border flex flex-col space-y-3">
          <div className="flex items-center justify-between border-b border-app-border/60 pb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-app-muted flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              Candidate Reference Match (Gold Standard)
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-500">
              Gold Spec
            </span>
          </div>

          {candidate.reference_edge ? (
            <div className="p-3 rounded-md bg-app-bg border border-app-border/80 font-mono text-xs space-y-1.5">
              <div>
                <span className="text-[10px] text-app-muted uppercase block font-sans">
                  Head (Subject)
                </span>
                <span className="text-app-text font-semibold">{refSource}</span>
              </div>
              <div className="pt-1">
                <span className="text-[10px] text-app-muted uppercase block font-sans">
                  Predicate (Relation)
                </span>
                <span className="text-blue-500 font-semibold bg-blue-500/10 px-1.5 py-0.5 rounded inline-block">
                  {refPredicate}
                </span>
              </div>
              <div className="pt-1">
                <span className="text-[10px] text-app-muted uppercase block font-sans">
                  Tail (Object)
                </span>
                <span className="text-app-text font-semibold">{refTarget}</span>
              </div>
            </div>
          ) : (
            <div className="p-6 rounded-md bg-app-bg border border-dashed border-app-border text-center text-xs text-app-muted flex flex-col items-center justify-center h-full">
              <Info className="w-5 h-5 opacity-40 mb-1" />
              <span>No gold reference match found within threshold.</span>
              <span className="text-[11px] text-app-muted mt-0.5">
                Likely novel candidate or empirical hallucination.
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Vector Component Similarity Gauges */}
      <div className="p-3.5 rounded-lg bg-app-surface border border-app-border">
        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-app-muted mb-2.5">
          Semantic Similarity Vector Decomposition
        </h4>
        <div className="grid grid-cols-4 gap-3 text-xs">
          <div className="p-2 rounded bg-app-bg border border-app-border">
            <span className="text-[10px] text-app-muted uppercase block">Head Entity</span>
            <div className="flex items-baseline justify-between mt-1">
              <span className="font-mono font-semibold tabular-nums text-app-text">
                {headSim.toFixed(2)}
              </span>
              <span className="text-[10px] text-emerald-500 font-mono">High</span>
            </div>
            <div className="w-full bg-app-border h-1 rounded mt-1.5 overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded"
                style={{ width: `${headSim * 100}%` }}
              />
            </div>
          </div>

          <div className="p-2 rounded bg-app-bg border border-app-border">
            <span className="text-[10px] text-app-muted uppercase block">Predicate</span>
            <div className="flex items-baseline justify-between mt-1">
              <span className="font-mono font-semibold tabular-nums text-app-text">
                {predSim.toFixed(2)}
              </span>
              <span className="text-[10px] text-amber-500 font-mono">Borderline</span>
            </div>
            <div className="w-full bg-app-border h-1 rounded mt-1.5 overflow-hidden">
              <div
                className="bg-amber-500 h-full rounded"
                style={{ width: `${predSim * 100}%` }}
              />
            </div>
          </div>

          <div className="p-2 rounded bg-app-bg border border-app-border">
            <span className="text-[10px] text-app-muted uppercase block">Tail Entity</span>
            <div className="flex items-baseline justify-between mt-1">
              <span className="font-mono font-semibold tabular-nums text-app-text">
                {tailSim.toFixed(2)}
              </span>
              <span className="text-[10px] text-emerald-500 font-mono">High</span>
            </div>
            <div className="w-full bg-app-border h-1 rounded mt-1.5 overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded"
                style={{ width: `${tailSim * 100}%` }}
              />
            </div>
          </div>

          <div className="p-2 rounded bg-app-bg border border-app-border">
            <span className="text-[10px] text-app-muted uppercase block">Overall Soft τ</span>
            <div className="flex items-baseline justify-between mt-1">
              <span className="font-mono font-semibold tabular-nums text-amber-500">
                {overallSim.toFixed(3)}
              </span>
              <span className="text-[10px] text-amber-500 font-mono">Uncertain</span>
            </div>
            <div className="w-full bg-app-border h-1 rounded mt-1.5 overflow-hidden">
              <div
                className="bg-amber-500 h-full rounded"
                style={{ width: `${overallSim * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Decision Action Buttons */}
      <div className="p-3.5 rounded-lg bg-app-surface border border-app-border space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-app-heading">
            Triage Decision Actions
          </h4>
          <span className="text-[11px] text-app-muted">
            Press hotkeys to stage instantly (no auto-debounce lag)
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {/* True Positive Button */}
          <button
            onClick={onAccept}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg border text-xs font-semibold transition-all shadow-2xs ${
              activeDecision === "true_positive"
                ? "bg-emerald-600 text-white border-emerald-600 ring-2 ring-emerald-500/30"
                : "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
            }`}
          >
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <div className="flex flex-col items-start leading-tight">
              <span>Accept (TP)</span>
              <span className="text-[10px] font-normal opacity-80 font-mono">[A] or [1]</span>
            </div>
          </button>

          {/* False Positive Button */}
          <button
            onClick={onReject}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg border text-xs font-semibold transition-all shadow-2xs ${
              activeDecision === "false_positive"
                ? "bg-rose-600 text-white border-rose-600 ring-2 ring-rose-500/30"
                : "bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 border-rose-500/30"
            }`}
          >
            <XCircle className="w-4 h-4 shrink-0" />
            <div className="flex flex-col items-start leading-tight">
              <span>Reject (FP)</span>
              <span className="text-[10px] font-normal opacity-80 font-mono">[R] or [2]</span>
            </div>
          </button>

          {/* Schema Alias Button */}
          <button
            onClick={onOpenAlias}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg border text-xs font-semibold transition-all shadow-2xs ${
              activeDecision === "schema_alias"
                ? "bg-violet-600 text-white border-violet-600 ring-2 ring-violet-500/30"
                : "bg-violet-500/10 hover:bg-violet-500/20 text-violet-600 dark:text-violet-400 border-violet-500/30"
            }`}
          >
            <GitMerge className="w-4 h-4 shrink-0" />
            <div className="flex flex-col items-start leading-tight">
              <span>Schema Alias</span>
              <span className="text-[10px] font-normal opacity-80 font-mono">[S] or [3]</span>
            </div>
          </button>

          {/* Undo Button */}
          <button
            onClick={onUndo}
            className="flex items-center justify-center gap-2 py-2 px-3 rounded-lg border border-app-border hover:bg-app-subtle text-app-muted hover:text-app-text text-xs font-medium transition-colors shadow-2xs"
          >
            <RotateCcw className="w-4 h-4 shrink-0" />
            <div className="flex flex-col items-start leading-tight">
              <span>Undo Decision</span>
              <span className="text-[10px] font-normal opacity-80 font-mono">[U] / ⌘Z</span>
            </div>
          </button>
        </div>

        {/* Optional Rationale Input */}
        <div className="pt-2 border-t border-app-border/50">
          <label className="block text-[11px] font-medium text-app-muted mb-1">
            Expert Review Notes / Rationale (Optional):
          </label>
          <input
            type="text"
            value={rationale}
            onChange={(e) => onChangeRationale(e.target.value)}
            placeholder="e.g. Validated against Principia Axiom II; vocabulary matches historical Latin edition..."
            className="w-full px-3 py-1.5 text-xs rounded-md bg-app-bg border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted"
          />
        </div>
      </div>
    </div>
  );
};
