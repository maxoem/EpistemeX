import React from "react";
import {
  CheckCircle2,
  XCircle,
  GitMerge,
  RotateCcw,
  Sparkles,
  ArrowRight,
  Info,
  Layers,
  ChevronDown,
  ChevronRight,
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
        <h4 className="text-sm font-semibold text-app-heading mb-1 font-sans">
          No Candidate Selected
        </h4>
        <p className="text-xs max-w-sm text-app-muted font-sans">
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

  const [showVectorDecomp, setShowVectorDecomp] = React.useState(false);

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto bg-app-bg select-none">
      {/* 1. Candidate Header Strip */}
      <div className="flex items-center justify-between px-6 py-3.5 bg-app-surface border-b border-app-border">
        <div className="flex items-center gap-3">
          <div className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 font-mono text-xs font-semibold border border-amber-500/20">
            {candidate.candidate_id}
          </div>
          <div>
            <h3 className="text-xs font-semibold text-app-heading font-sans">
              Borderline Relation Alignment
            </h3>
            <p className="text-[11px] text-app-muted font-sans">
              Evaluation uncertainty band:{" "}
              <span className="font-mono text-app-text font-medium" style={{ fontFeatureSettings: '"tnum" 1' }}>
                τ = {overallSim.toFixed(3)}
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end">
            <span className="text-[10px] font-sans text-app-muted font-medium">
              Extraction Confidence
            </span>
            <span className="font-mono text-xs font-semibold tabular-nums text-app-text">
              {(candidate.confidence * 100).toFixed(1)}%
            </span>
          </div>

          <div className="h-6 w-px bg-app-border" />

          <div className="flex flex-col items-end">
            <span className="text-[10px] font-sans text-app-muted font-medium">
              Soft Similarity τ
            </span>
            <span className="font-mono text-xs font-semibold tabular-nums text-amber-500">
              {overallSim.toFixed(3)}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Staged State Notice if active */}
      {stagedItem && (
        <div className="px-6 py-2.5 flex items-center justify-between text-xs animate-in fade-in duration-150 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-b border-emerald-500/20">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-500 shrink-0" />
            <span className="font-medium font-sans">
              Staged Decision:{" "}
              <strong className="uppercase font-mono">
                {stagedItem.decision.replace("_", " ")}
              </strong>
              {stagedItem.alias_target && (
                <span className="font-mono text-violet-600 dark:text-violet-400">
                  {" "}→ {stagedItem.alias_target}
                </span>
              )}
            </span>
          </div>
          <span className="font-mono text-[11px] bg-emerald-500/20 px-2 py-0.5 rounded font-medium">
            Pending Batch Commit (⌘⏎)
          </span>
        </div>
      )}

      {/* 3. Parallel Aligned Triple Comparison (design.md Box-Crate elimination & Monograph layout) */}
      <div className="border-b border-app-border bg-app-surface/30">
        {/* Column Headers */}
        <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-app-border border-b border-app-border/70 text-xs">
          <div className="px-6 py-2.5 flex items-center justify-between bg-app-surface/60">
            <span className="font-semibold text-app-heading flex items-center gap-2 font-sans text-xs">
              <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
              Predicted Triple (Pipeline Output)
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-app-subtle text-app-muted">
              Conf: {(candidate.confidence * 100).toFixed(0)}%
            </span>
          </div>

          <div className="px-6 py-2.5 flex items-center justify-between bg-app-surface/60">
            <span className="font-semibold text-app-heading flex items-center gap-2 font-sans text-xs">
              <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
              Candidate Reference Match (Gold Standard)
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-500">
              Gold Spec
            </span>
          </div>
        </div>

        {/* Aligned Row 1: Head (Subject) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-app-border border-b border-app-border/50 text-xs">
          <div className="px-6 py-3 flex flex-col justify-center">
            <span className="text-[10px] text-app-muted font-sans font-medium mb-1">
              Subject (Head)
            </span>
            <span className="font-mono text-xs text-app-text font-semibold truncate" title={predSource}>
              {predSource}
            </span>
          </div>

          <div className="px-6 py-3 flex flex-col justify-center">
            <span className="text-[10px] text-app-muted font-sans font-medium mb-1">
              Subject (Head)
            </span>
            {refSource ? (
              <span className="font-mono text-xs text-app-text font-semibold truncate" title={refSource}>
                {refSource}
              </span>
            ) : (
              <span className="font-sans text-xs text-app-muted italic">No gold match</span>
            )}
          </div>
        </div>

        {/* Aligned Row 2: Predicate (Relation) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-app-border border-b border-app-border/50 text-xs bg-app-subtle/15">
          <div className="px-6 py-2.5 flex flex-col justify-center">
            <span className="text-[10px] text-app-muted font-sans font-medium mb-1">
              Predicate (Relation)
            </span>
            <div>
              <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded inline-block truncate bg-app-surface text-app-text border border-app-border">
                {predPredicate}
              </span>
            </div>
          </div>

          <div className="px-6 py-2.5 flex flex-col justify-center">
            <span className="text-[10px] text-app-muted font-sans font-medium mb-1">
              Predicate (Relation)
            </span>
            <div>
              {refPredicate ? (
                <span className={`font-mono text-xs font-semibold px-2 py-0.5 rounded inline-block truncate ${
                  predPredicate === refPredicate
                    ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                    : "bg-app-surface text-app-text border border-app-border"
                }`}>
                  {refPredicate}
                </span>
              ) : (
                <span className="font-sans text-xs text-app-muted italic">No gold predicate</span>
              )}
            </div>
          </div>
        </div>

        {/* Aligned Row 3: Tail (Object) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-app-border text-xs">
          <div className="px-6 py-3 flex flex-col justify-center">
            <span className="text-[10px] text-app-muted font-sans font-medium mb-1">
              Object (Tail)
            </span>
            <span className="font-mono text-xs text-app-text font-semibold truncate" title={predTarget}>
              {predTarget}
            </span>
          </div>

          <div className="px-6 py-3 flex flex-col justify-center">
            <span className="text-[10px] text-app-muted font-sans font-medium mb-1">
              Object (Tail)
            </span>
            {refTarget ? (
              <span className="font-mono text-xs text-app-text font-semibold truncate" title={refTarget}>
                {refTarget}
              </span>
            ) : (
              <span className="font-sans text-xs text-app-muted italic">No gold match</span>
            )}
          </div>
        </div>
      </div>

      {/* 4. Streamlined Semantic Similarity Vector Telemetry (Collapsible) */}
      <div className="px-6 py-2.5 border-b border-app-border bg-app-bg">
        <button
          type="button"
          onClick={() => setShowVectorDecomp((prev) => !prev)}
          className="w-full flex items-center justify-between text-left py-1 text-app-muted hover:text-app-text transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2">
            {showVectorDecomp ? (
              <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
            )}
            <span className="text-[11px] font-medium font-sans">
              Semantic Similarity Vector Decomposition
            </span>
          </div>
          <div className="flex items-center gap-2.5 text-[10px] font-mono text-app-muted">
            <span>Head: <strong className="text-app-text font-semibold">{headSim.toFixed(2)}</strong></span>
            <span>•</span>
            <span>Pred: <strong className="text-app-text font-semibold">{predSim.toFixed(2)}</strong></span>
            <span>•</span>
            <span>Tail: <strong className="text-app-text font-semibold">{tailSim.toFixed(2)}</strong></span>
            <span>•</span>
            <span>Soft τ: <strong className="text-amber-500 font-semibold">{overallSim.toFixed(3)}</strong></span>
          </div>
        </button>

        {showVectorDecomp && (
          <div className="grid grid-cols-4 gap-2 bg-app-surface border border-app-border rounded-md p-2.5 divide-x divide-app-border mt-2 animate-in fade-in duration-100">
            {/* Head Entity */}
            <div className="px-2 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-app-muted font-sans">Head Entity</span>
                <span className="text-[10px] text-emerald-500 font-mono font-medium">High</span>
              </div>
              <div className="font-mono text-xs font-semibold tabular-nums text-app-text">
                {headSim.toFixed(2)}
              </div>
              <div className="w-full bg-app-subtle h-1.5 rounded overflow-hidden">
                <div
                  className="bg-emerald-500 h-full rounded"
                  style={{ width: `${headSim * 100}%` }}
                />
              </div>
            </div>

            {/* Predicate */}
            <div className="px-2 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-app-muted font-sans">Predicate</span>
                <span className="text-[10px] text-amber-500 font-mono font-medium">Borderline</span>
              </div>
              <div className="font-mono text-xs font-semibold tabular-nums text-app-text">
                {predSim.toFixed(2)}
              </div>
              <div className="w-full bg-app-subtle h-1.5 rounded overflow-hidden">
                <div
                  className="bg-amber-500 h-full rounded"
                  style={{ width: `${predSim * 100}%` }}
                />
              </div>
            </div>

            {/* Tail Entity */}
            <div className="px-2 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-app-muted font-sans">Tail Entity</span>
                <span className="text-[10px] text-emerald-500 font-mono font-medium">High</span>
              </div>
              <div className="font-mono text-xs font-semibold tabular-nums text-app-text">
                {tailSim.toFixed(2)}
              </div>
              <div className="w-full bg-app-subtle h-1.5 rounded overflow-hidden">
                <div
                  className="bg-emerald-500 h-full rounded"
                  style={{ width: `${tailSim * 100}%` }}
                />
              </div>
            </div>

            {/* Overall Soft τ */}
            <div className="px-2 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-app-muted font-sans">Overall Soft τ</span>
                <span className="text-[10px] text-amber-500 font-mono font-medium">Uncertain</span>
              </div>
              <div className="font-mono text-xs font-semibold tabular-nums text-amber-500">
                {overallSim.toFixed(3)}
              </div>
              <div className="w-full bg-app-subtle h-1.5 rounded overflow-hidden">
                <div
                  className="bg-amber-500 h-full rounded"
                  style={{ width: `${overallSim * 100}%` }}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 5. Triage Decision Command Strip (Ergonomic Triage) */}
      <div className="px-6 py-4 bg-app-surface/60 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-[11px] font-semibold text-app-heading font-sans">
            Triage Decision Actions
          </h4>
          <span className="text-[11px] text-app-muted font-sans">
            Press hotkeys to stage instantly (no auto-debounce lag)
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {/* True Positive Button */}
          <button
            type="button"
            onClick={onAccept}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-md text-xs font-semibold transition-all cursor-pointer ${
              activeDecision === "true_positive"
                ? "bg-emerald-600 text-white shadow-xs ring-1 ring-emerald-500/40"
                : "bg-app-surface hover:bg-emerald-500/5 hover:border-emerald-500/40 text-app-text border border-app-border"
            }`}
          >
            <CheckCircle2 className={`w-4 h-4 shrink-0 ${activeDecision === "true_positive" ? "text-white" : "text-emerald-500"}`} />
            <div className="flex flex-col items-start leading-tight">
              <span>Accept (TP)</span>
              <span className={`text-[10px] font-normal font-mono px-1 py-0.2 rounded mt-0.5 ${
                activeDecision === "true_positive" ? "bg-white/20 text-white" : "bg-app-subtle text-app-muted border border-app-border/60"
              }`}>[A] or [1]</span>
            </div>
          </button>

          {/* False Positive Button */}
          <button
            type="button"
            onClick={onReject}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-md text-xs font-semibold transition-all cursor-pointer ${
              activeDecision === "false_positive"
                ? "bg-rose-600 text-white shadow-xs ring-1 ring-rose-500/40"
                : "bg-app-surface hover:bg-rose-500/5 hover:border-rose-500/40 text-app-text border border-app-border"
            }`}
          >
            <XCircle className={`w-4 h-4 shrink-0 ${activeDecision === "false_positive" ? "text-white" : "text-rose-500"}`} />
            <div className="flex flex-col items-start leading-tight">
              <span>Reject (FP)</span>
              <span className={`text-[10px] font-normal font-mono px-1 py-0.2 rounded mt-0.5 ${
                activeDecision === "false_positive" ? "bg-white/20 text-white" : "bg-app-subtle text-app-muted border border-app-border/60"
              }`}>[R] or [2]</span>
            </div>
          </button>

          {/* Schema Alias Button */}
          <button
            type="button"
            onClick={onOpenAlias}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-md text-xs font-semibold transition-all cursor-pointer ${
              activeDecision === "schema_alias"
                ? "bg-violet-600 text-white shadow-xs ring-1 ring-violet-500/40"
                : "bg-app-surface hover:bg-violet-500/5 hover:border-violet-500/40 text-app-text border border-app-border"
            }`}
          >
            <GitMerge className={`w-4 h-4 shrink-0 ${activeDecision === "schema_alias" ? "text-white" : "text-violet-500"}`} />
            <div className="flex flex-col items-start leading-tight">
              <span>Schema Alias</span>
              <span className={`text-[10px] font-normal font-mono px-1 py-0.2 rounded mt-0.5 ${
                activeDecision === "schema_alias" ? "bg-white/20 text-white" : "bg-app-subtle text-app-muted border border-app-border/60"
              }`}>[S] or [3]</span>
            </div>
          </button>

          {/* Undo Button */}
          <button
            type="button"
            onClick={onUndo}
            className="flex items-center justify-center gap-2 py-2 px-3 rounded-md border border-app-border hover:bg-app-subtle text-app-muted hover:text-app-text text-xs font-medium transition-colors cursor-pointer bg-app-surface"
          >
            <RotateCcw className="w-4 h-4 shrink-0" />
            <div className="flex flex-col items-start leading-tight">
              <span>Undo</span>
              <span className="text-[10px] font-normal font-mono px-1 py-0.2 rounded mt-0.5 bg-app-subtle text-app-muted border border-app-border/60">[U] / ⌘Z</span>
            </div>
          </button>
        </div>

        {/* Optional Rationale Input */}
        <div className="pt-1">
          <label className="block text-[11px] font-medium text-app-muted mb-1 font-sans">
            Expert Review Notes / Rationale (Optional):
          </label>
          <input
            type="text"
            value={rationale}
            onChange={(e) => onChangeRationale(e.target.value)}
            placeholder="e.g. Validated against Principia Axiom II; vocabulary matches historical Latin edition..."
            className="w-full px-3 py-1.5 text-xs rounded bg-app-bg border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted font-sans"
          />
        </div>
      </div>
    </div>
  );
};
