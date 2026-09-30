import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Scale,
  Quote,
  Network,
  ShieldCheck,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import { ActionableHookPill } from "../../components/ActionableHookPill";
import type { PolarityConcordanceDetail } from "../../../../api/types";

export interface PolarityConflictItem {
  id: string;
  sourceNode: string;
  targetNode: string;
  predictedPredicate: "SUPPORTS" | "ATTACKS" | "PROVES" | "REFUTES" | "UNDERCUTS";
  goldPredicate: "SUPPORTS" | "ATTACKS" | "PROVES" | "REFUTES" | "UNDERCUTS";
  severity: "CRITICAL_INVERSION" | "MODERATE_POLARITY_MISALIGNMENT";
  similarity: number;
  sourceQuote: string;
  citation: string;
  edgeId?: string;
}

/**
 * Lens 3: Inferential Polarity Concordance (SUPPORTS vs ATTACKS Dialectics).
 *
 * Implements design.md §9 (Headless Linear Data Grid) & §11 (Keyboard Triage):
 * - Fixed 40px (h-10) data rows with 2px left border in primary blue (#2563EB)
 * - Docked Master-Detail: Fluid center data grid + Right diagnostic citation rail
 * - Instant j/k keyboard triage across dialectical conflicts
 */
export const PolarityConflictMatrix: React.FC = () => {
  const {
    activeReport,
    setActiveSubTab,
    setSelectedOverlayItem,
    graphOverlay,
  } = useEvaluationStore();

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const polarityDetail: PolarityConcordanceDetail = useMemo(() => {
    if (activeReport?.polarity_detail) {
      return activeReport.polarity_detail;
    }
    return {
      polarity_accuracy: 0.962,
      polarity_conflict_rate: 0.038,
      conflicting_pairs_count: 3,
      agreed_pairs_count: 76,
    };
  }, [activeReport]);

  const conflictItems: PolarityConflictItem[] = useMemo(() => {
    const overlayEdges = graphOverlay?.edges?.filter(
      (e) => e.alignment_status === "polarity_conflict"
    );

    if (overlayEdges && overlayEdges.length > 0) {
      return overlayEdges.map((e, idx) => ({
        id: `conf_${e.id || idx}`,
        edgeId: e.id,
        sourceNode: e.source,
        targetNode: e.target,
        predictedPredicate: (e.predicate.toUpperCase() as any) || "SUPPORTS",
        goldPredicate: (e.gold_predicate?.toUpperCase() as any) || "ATTACKS",
        severity: "CRITICAL_INVERSION",
        similarity: e.similarity_score || 0.45,
        sourceQuote:
          e.evidence_snippet ||
          "Historical commentary: The author explicitly refutes this thesis, whereas the model concluded deductive entailment.",
        citation: "Dialectical Inversion Evidence",
      }));
    }

    return [
      {
        id: "conf_01",
        sourceNode: "Axiom-04 (Machian Relativity)",
        targetNode: "Hypothesis-12 (Absolute Newtonian Space)",
        predictedPredicate: "SUPPORTS",
        goldPredicate: "ATTACKS",
        severity: "CRITICAL_INVERSION",
        similarity: 0.38,
        sourceQuote:
          "Mach rejects any ontological reality ascribed to absolute space, demonstrating its purely auxiliary and metaphysical character.",
        citation: "Mach (1883) Science of Mechanics, §2.6",
      },
      {
        id: "conf_02",
        sourceNode: "Rebuttal-02 (Duhem Underdetermination)",
        targetNode: "Claim-09 (Crucial Experiment Definitive Refutation)",
        predictedPredicate: "PROVES",
        goldPredicate: "REFUTES",
        severity: "CRITICAL_INVERSION",
        similarity: 0.42,
        sourceQuote:
          "An experiment in physics can never condemn an isolated hypothesis but only a whole theoretical group; an experimentum crucis is impossible.",
        citation: "Duhem (1906) Aim and Structure of Physical Theory, Part II, Ch. VI",
      },
      {
        id: "conf_03",
        sourceNode: "Lemma-07 (Auxiliary Elastic Adjustment)",
        targetNode: "Anomaly-03 (Anomalous Planetary Perihelion)",
        predictedPredicate: "REFUTES",
        goldPredicate: "UNDERCUTS",
        severity: "MODERATE_POLARITY_MISALIGNMENT",
        similarity: 0.64,
        sourceQuote:
          "The auxiliary hypothesis does not refute the observed perihelion discrepancy, but immunizes the core gravitation law by distributing error.",
        citation: "Lakatos (1970) Methodology of Scientific Research Programmes, §3",
      },
    ];
  }, [graphOverlay]);

  useEffect(() => {
    if (conflictItems.length > 0 && !selectedId) {
      setSelectedId(conflictItems[0].id);
    }
  }, [conflictItems, selectedId]);

  const selectedConflict = useMemo(() => {
    return conflictItems.find((c) => c.id === selectedId) || conflictItems[0] || null;
  }, [conflictItems, selectedId]);

  const activeIndex = useMemo(() => {
    if (!selectedId) return 0;
    const idx = conflictItems.findIndex((c) => c.id === selectedId);
    return idx >= 0 ? idx : 0;
  }, [conflictItems, selectedId]);

  // Keyboard Triage (§11)
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        if (activeIndex < conflictItems.length - 1) {
          setSelectedId(conflictItems[activeIndex + 1].id);
        }
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        if (activeIndex > 0) {
          setSelectedId(conflictItems[activeIndex - 1].id);
        }
      }
    },
    [activeIndex, conflictItems]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  const handleInspectOnCanvas = (conflict: PolarityConflictItem) => {
    if (graphOverlay?.edges) {
      const match = graphOverlay.edges.find(
        (e) =>
          e.id === conflict.edgeId ||
          (e.source.includes(conflict.sourceNode) && e.target.includes(conflict.targetNode))
      );
      if (match) {
        setSelectedOverlayItem({ type: "edge", item: match });
      }
    }
    setActiveSubTab("canvas");
  };

  const accuracyPct = Math.round(polarityDetail.polarity_accuracy * 1000) / 10;
  const conflictPct = Math.round(polarityDetail.polarity_conflict_rate * 1000) / 10;

  return (
    <div className="flex-1 flex flex-col h-full w-full overflow-hidden bg-app-bg text-app-text select-none font-sans">
      {/* 44px Action Bar */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface shrink-0 flex items-center justify-between text-xs gap-3">
        <div className="flex items-center gap-2">
          <Scale className="w-3.5 h-3.5 text-amber-500" />
          <h3 className="type-caption font-semibold text-app-heading uppercase tracking-wider">
            Inferential Polarity Concordance
          </h3>
          <span className="type-mono text-[11px] text-app-muted hidden sm:inline">
            (SUPPORTS vs. ATTACKS Dialectics)
          </span>
        </div>

        {/* Telemetry Strip */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs">
            <span className="type-caption text-app-muted">Concordance:</span>
            <span className="type-mono font-semibold tabular-nums text-emerald-500">
              {accuracyPct.toFixed(1)}%
            </span>
          </div>
          <span className="text-app-border">·</span>
          <div className="flex items-center gap-1.5 text-xs">
            <span className="type-caption text-app-muted">Conflict Rate:</span>
            <span className="type-mono font-semibold tabular-nums text-amber-500">
              {conflictPct.toFixed(1)}% ({polarityDetail.conflicting_pairs_count} pairs)
            </span>
          </div>
        </div>
      </div>

      {/* Main Split: Center Stage Grid + Right Diagnostic Rail */}
      <div className="flex-1 flex overflow-hidden">
        {/* Center Stage: Headless Linear Data Grid */}
        <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
          <div className="flex-1 overflow-y-auto min-h-0">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="sticky top-0 bg-app-surface border-b border-app-border text-[11px] text-app-muted font-semibold tracking-[0.05em] uppercase z-10">
                <tr className="h-9">
                  <th className="px-4 w-[28%]">Source Proposition</th>
                  <th className="px-4 w-[28%]">Target Proposition</th>
                  <th className="px-3 text-center w-[14%]">Predicted</th>
                  <th className="px-3 text-center w-[14%]">Gold Standard</th>
                  <th className="px-3 text-center w-[16%]">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-border font-sans text-xs">
                {conflictItems.map((conflict) => {
                  const isSelected = conflict.id === selectedId;

                  return (
                    <tr
                      key={conflict.id}
                      onClick={() => setSelectedId(conflict.id)}
                      className={`h-10 cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-app-subtle border-l-2 border-blue-600 text-app-heading font-medium"
                          : "border-l-2 border-transparent hover:bg-app-subtle/50 text-app-text"
                      }`}
                    >
                      <td className="px-4 truncate max-w-[200px] text-app-heading font-medium">
                        {conflict.sourceNode}
                      </td>
                      <td className="px-4 truncate max-w-[200px] text-app-heading font-medium">
                        {conflict.targetNode}
                      </td>
                      <td className="px-3 text-center type-mono text-[11px] font-semibold text-app-heading">
                        {conflict.predictedPredicate}
                      </td>
                      <td className="px-3 text-center type-mono text-[11px] font-semibold text-rose-500">
                        {conflict.goldPredicate}
                      </td>
                      <td className="px-3 text-center">
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] type-mono font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/25">
                          CRITICAL INVERSION
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Grid Footer */}
          <div className="h-8 px-4 border-t border-app-border bg-app-surface/60 shrink-0 flex items-center justify-between text-[11px] text-app-muted">
            <span>
              Showing <strong className="type-mono text-app-heading">{conflictItems.length}</strong> polarity conflicts
            </span>
            <span className="hidden sm:inline text-app-muted/70">
              Use <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-[10px] type-mono">j</kbd> /{" "}
              <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-[10px] type-mono">k</kbd> to step through conflicts
            </span>
          </div>
        </div>

        {/* Right Diagnostic Rail for Polarity Conflict */}
        <div className="w-[420px] border-l border-app-border bg-app-surface flex flex-col h-full shrink-0 overflow-y-auto">
          <div className="h-10 px-4 border-b border-app-border flex items-center justify-between text-[11px] text-app-muted uppercase font-semibold tracking-wider bg-app-surface/80">
            <span>Dialectical Inversion Diagnostic</span>
            {selectedConflict && (
              <span className="type-mono text-[11px] text-rose-500 font-semibold">
                Sim: {selectedConflict.similarity.toFixed(2)}
              </span>
            )}
          </div>

          {selectedConflict ? (
            <div className="p-4 space-y-4 text-xs font-sans">
              {/* Conflict Pair Description */}
              <div className="p-3 rounded bg-app-bg border border-app-border space-y-2">
                <div className="flex items-center justify-between">
                  <span className="type-caption text-[10px] uppercase font-semibold text-app-muted">
                    Dialectical Conflict Relation
                  </span>
                  <span className="type-mono text-[10px] text-rose-500 font-bold">
                    INVERTED
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-app-heading font-medium truncate max-w-[160px]">
                    {selectedConflict.sourceNode}
                  </span>
                  <ArrowRight className="w-3.5 h-3.5 text-app-muted shrink-0" />
                  <span className="text-app-heading font-medium truncate max-w-[160px]">
                    {selectedConflict.targetNode}
                  </span>
                </div>

                <div className="flex items-center gap-3 pt-1 text-xs border-t border-app-border/40">
                  <div>
                    <span className="type-caption text-[10px] text-app-muted block">Predicted:</span>
                    <span className="type-mono font-semibold text-app-heading">
                      {selectedConflict.predictedPredicate}
                    </span>
                  </div>
                  <span className="text-app-muted font-bold">≠</span>
                  <div>
                    <span className="type-caption text-[10px] text-app-muted block">Gold Standard:</span>
                    <span className="type-mono font-semibold text-rose-500">
                      {selectedConflict.goldPredicate}
                    </span>
                  </div>
                </div>
              </div>

              {/* Corpus Grounding Citation */}
              <div className="space-y-1">
                <span className="type-caption uppercase font-semibold text-app-muted text-[10px] block">
                  Grounding Evidence &amp; Citation
                </span>
                <blockquote className="italic text-xs text-app-heading leading-relaxed bg-app-bg p-3 rounded border-l-2 border-amber-500 font-serif">
                  &ldquo;{selectedConflict.sourceQuote}&rdquo;
                </blockquote>
                <span className="type-caption text-[10px] text-app-muted block text-right">
                  — {selectedConflict.citation}
                </span>
              </div>

              {/* Argumentative Impact Rationale */}
              <div className="p-3 rounded bg-rose-500/10 border-l-2 border-rose-500 space-y-1">
                <span className="type-caption font-semibold text-rose-600 dark:text-rose-400 text-[10px] uppercase block">
                  Dialectical Analysis
                </span>
                <p className="type-body text-[11px] text-rose-600 dark:text-rose-300 leading-relaxed">
                  Confusing supportive entailment with counter-argument inverts the dialectical polarity of the debate, producing an erroneous consensus.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-between gap-2 border-t border-app-border">
                <ActionableHookPill
                  type="argument_polarity"
                  relationId={selectedConflict.predictedPredicate}
                  sourceNode={selectedConflict.sourceNode}
                  targetNode={selectedConflict.targetNode}
                  label="Tuning Hook"
                />

                <button
                  type="button"
                  onClick={() => handleInspectOnCanvas(selectedConflict)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer"
                >
                  <Network className="w-3.5 h-3.5" />
                  <span>Inspect on Canvas</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-app-muted">
              <ShieldCheck className="w-8 h-8 text-emerald-500 opacity-80 mb-2" />
              <p className="type-body text-xs">No conflict selected.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
