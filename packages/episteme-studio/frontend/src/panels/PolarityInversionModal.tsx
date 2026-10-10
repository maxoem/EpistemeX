import React from "react";
import {useDiffStore} from "../store/diffStore";
import {useRunsStore} from "../store/runsStore";
import {PolarityInversion} from "../api/types";
import {ArrowRight, CheckCircle, Crosshair, X, Zap} from "lucide-react";

interface PolarityInversionModalProps {
  onFocusEndpoints?: (sourceId: string, targetId: string) => void;
}

export const PolarityInversionModal: React.FC<PolarityInversionModalProps> = ({
  onFocusEndpoints,
}) => {
  const { isPolarityModalOpen, setIsPolarityModalOpen, diffData, baseRunId, targetRunId } =
    useDiffStore();
  const { setFocusedNodeId } = useRunsStore();

  if (!isPolarityModalOpen || !diffData) return null;

  const inversions = diffData.polarity_inversions;

  const handleZoomToPair = (inv: PolarityInversion) => {
    if (onFocusEndpoints) {
      onFocusEndpoints(inv.source, inv.target);
    } else {
      setFocusedNodeId(inv.source);
    }
    setIsPolarityModalOpen(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150 select-none">
      <div className="bg-app-surface border border-app-border rounded-xl shadow-2xl max-w-3xl w-full flex flex-col overflow-hidden text-xs max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-app-border bg-app-surface">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-500 border border-amber-500/20">
              <Zap className="w-4 h-4 fill-current" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-app-heading flex items-center gap-2">
                Polarity Inversions & Argumentative Divergences
                <span className="text-[11px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-500 font-mono font-medium border border-amber-500/20">
                  {inversions.length} detected
                </span>
              </h2>
              <p className="text-[11px] text-app-muted">
                Relations between identical concepts where reasoning polarities directly conflicted.
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsPolarityModalOpen(false)}
            className="p-1 rounded-md text-app-muted hover:text-app-heading hover:bg-app-subtle transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Inversions List */}
        <div className="p-5 overflow-y-auto space-y-3.5 flex-1">
          {inversions.length === 0 ? (
            <div className="text-center py-10 text-app-muted space-y-2">
              <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto opacity-80" />
              <p className="text-xs">No direct polarity inversions detected between these runs.</p>
              <p className="text-[11px]">All shared claim relations maintained compatible polarity directions.</p>
            </div>
          ) : (
            inversions.map((inv, idx) => (
              <div
                key={inv.edge_id || idx}
                className="p-3.5 rounded-lg border border-app-border bg-app-bg space-y-3 hover:border-amber-500/40 transition-colors"
              >
                {/* Concept Pair Header */}
                <div className="flex items-center justify-between gap-2 border-b border-app-border-subtle pb-2">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="font-semibold text-app-heading truncate text-[12px]" title={inv.source_label}>
                      {inv.source_label}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-app-muted shrink-0" />
                    <span className="font-semibold text-app-heading truncate text-[12px]" title={inv.target_label}>
                      {inv.target_label}
                    </span>
                  </div>

                  <button
                    onClick={() => handleZoomToPair(inv)}
                    className="inline-flex items-center gap-1 px-2 py-1 rounded bg-app-subtle hover:bg-app-hover text-app-heading text-[11px] font-medium transition-colors cursor-pointer shrink-0"
                    title="Center and highlight these endpoints on canvas"
                  >
                    <Crosshair className="w-3 h-3 text-blue-400" />
                    <span>Focus on Canvas</span>
                  </button>
                </div>

                {/* Side-by-Side Model Inversion Breakdown */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Run A */}
                  <div className="p-2.5 rounded-md bg-app-surface border border-app-border/80 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-500">
                        Baseline (Run A)
                      </span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[10px] font-semibold border ${
                          (inv.polarity_a ?? 0) > 0
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                            : (inv.polarity_a ?? 0) < 0
                            ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30"
                            : "bg-app-subtle text-app-muted border-app-border"
                        }`}
                      >
                        {(inv.polarity_a ?? 0) > 0 ? "SUPPORT (+1)" : (inv.polarity_a ?? 0) < 0 ? "ATTACK (-1)" : "NEUTRAL (0)"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-app-muted">Predicate:</span>
                      <span className="font-mono font-medium text-app-heading">{inv.predicate_a}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-app-muted">Weight / Conf:</span>
                      <span className="font-mono text-app-heading">
                        {inv.weight_a !== null && inv.weight_a !== undefined ? inv.weight_a.toFixed(3) : "—"}
                      </span>
                    </div>
                  </div>

                  {/* Run B */}
                  <div className="p-2.5 rounded-md bg-app-surface border border-app-border/80 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-500">
                        Candidate (Run B)
                      </span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[10px] font-semibold border ${
                          (inv.polarity_b ?? 0) > 0
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30"
                            : (inv.polarity_b ?? 0) < 0
                            ? "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30"
                            : "bg-app-subtle text-app-muted border-app-border"
                        }`}
                      >
                        {(inv.polarity_b ?? 0) > 0 ? "SUPPORT (+1)" : (inv.polarity_b ?? 0) < 0 ? "ATTACK (-1)" : "NEUTRAL (0)"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-app-muted">Predicate:</span>
                      <span className="font-mono font-medium text-app-heading">{inv.predicate_b}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-app-muted">Weight / Conf:</span>
                      <span className="font-mono text-app-heading">
                        {inv.weight_b !== null && inv.weight_b !== undefined ? inv.weight_b.toFixed(3) : "—"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-5 py-3 border-t border-app-border bg-app-subtle/50">
          <button
            onClick={() => setIsPolarityModalOpen(false)}
            className="px-3.5 py-1.5 rounded-md bg-app-surface border border-app-border hover:bg-app-hover text-app-heading transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
