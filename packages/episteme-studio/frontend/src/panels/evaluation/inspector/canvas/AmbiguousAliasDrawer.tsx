import React, { useState, useMemo } from "react";
import {
  Check,
  CheckCheck,
  ExternalLink,
  Layers,
  Sparkles,
  Users,
  X,
  XCircle,
  HelpCircle,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import { ActionableHookPill } from "../../components/ActionableHookPill";
import type { EvaluationNodeOverlay } from "../../../../api/types";

export interface AmbiguousEntityCandidate {
  id: string;
  predicted_id: string;
  predicted_label: string;
  candidate_gold_id: string;
  candidate_gold_label: string;
  similarity_score: number;
  class_name?: string;
  evidence_snippet?: string;
  decision?: "approved" | "rejected" | null;
}

export interface AmbiguousAliasDrawerProps {
  candidates?: AmbiguousEntityCandidate[];
}

export const AmbiguousAliasDrawer: React.FC<AmbiguousAliasDrawerProps> = ({
  candidates: customCandidates,
}) => {
  const {
    isAmbiguousDrawerOpen,
    setIsAmbiguousDrawerOpen,
    graphOverlay,
    stageAdjudication,
  } = useEvaluationStore();

  // Synthesize or derive borderline candidates if not supplied
  const initialCandidates: AmbiguousEntityCandidate[] = useMemo(() => {
    if (customCandidates && customCandidates.length > 0) {
      return customCandidates;
    }

    const derived: AmbiguousEntityCandidate[] = [];
    const nodes = graphOverlay?.nodes || [];

    // Find borderline nodes or nodes with intermediate similarity
    for (const node of nodes) {
      if (
        node.alignment_status === "borderline" ||
        (node.similarity_score >= 0.75 && node.similarity_score <= 0.88 && !node.is_ghost)
      ) {
        derived.push({
          id: `cand_${node.id}`,
          predicted_id: node.id,
          predicted_label: node.label,
          candidate_gold_id: node.gold_id || "gold:Constitutional_Basis",
          candidate_gold_label: node.gold_id
            ? node.gold_id.split(":").pop()?.replace(/_/g, " ") || node.gold_id
            : "Constitutional Epistemic Basis",
          similarity_score: node.similarity_score,
          class_name: node.class_name || "actual_models",
          evidence_snippet: `Predicted concept "${node.label}" shares dense embedding neighborhood with reference schema entity.`,
          decision: null,
        });
      }
    }

    // Default fallback realistic mock candidates for Bourbaki / Carnap evaluation if none in overlay
    if (derived.length === 0) {
      return [
        {
          id: "amb_01",
          predicted_id: "pred:Elementary_Experiences",
          predicted_label: "Elementary Experiences (Elementarerlebnisse)",
          candidate_gold_id: "gold:Elementary_Experience_Basis",
          candidate_gold_label: "Elementary Experience Basis",
          similarity_score: 0.862,
          class_name: "actual_models",
          evidence_snippet:
            "Aufbau §67: 'The basic elements of the constitution system are the elementary experiences of a single person.'",
          decision: null,
        },
        {
          id: "amb_02",
          predicted_id: "pred:Qualia_Constitution",
          predicted_label: "Qualia Constitution",
          candidate_gold_id: "gold:Sensory_Qualia_Class",
          candidate_gold_label: "Sensory Qualia Class",
          similarity_score: 0.814,
          class_name: "potential_models",
          evidence_snippet:
            "Aufbau §72: 'The construction of qualities proceeds from the relation of recollected similarity between experiences.'",
          decision: null,
        },
        {
          id: "amb_03",
          predicted_id: "pred:Quasi_Analysis_Method",
          predicted_label: "Quasi-Analysis Method",
          candidate_gold_id: "gold:Quasi_Analysis_Procedure",
          candidate_gold_label: "Quasi-Analysis Procedure",
          similarity_score: 0.873,
          class_name: "constraints",
          evidence_snippet:
            "Aufbau §71: 'Quasi-analysis serves to construct fictitious components of unpartitioned experiences.'",
          decision: null,
        },
        {
          id: "amb_04",
          predicted_id: "pred:Intersubjective_Domain",
          predicted_label: "Intersubjective Domain",
          candidate_gold_id: "gold:Intersubjective_World",
          candidate_gold_label: "Intersubjective Physical World",
          similarity_score: 0.785,
          class_name: "intended_applications",
          evidence_snippet:
            "Aufbau §146: 'The intersubjective world is constituted through the structural assignment of qualities to spacetime coordinates.'",
          decision: null,
        },
      ];
    }

    return derived;
  }, [customCandidates, graphOverlay]);

  const [items, setItems] = useState<AmbiguousEntityCandidate[]>(initialCandidates);

  // Sync state if initial candidates change
  React.useEffect(() => {
    setItems(initialCandidates);
  }, [initialCandidates]);

  if (!isAmbiguousDrawerOpen) return null;

  const pendingCount = items.filter((i) => !i.decision).length;

  const handleDecision = (id: string, decision: "approved" | "rejected") => {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, decision } : item))
    );

    const item = items.find((i) => i.id === id);
    if (item) {
      stageAdjudication(item.id, {
        adjudication_id: `adj_${item.id}`,
        predicted_edge: {
          source: item.predicted_id,
          predicate: decision === "approved" ? "IS_SCHEMA_ALIAS_OF" : "DISTINCT_FROM",
          target: item.candidate_gold_id,
        },
        decision: decision === "approved" ? "schema_alias" : "false_positive",
        similarity_score: item.similarity_score,
        alias_target: decision === "approved" ? item.candidate_gold_id : undefined,
        rationale: `Reconciled from Ambiguous Alias Drawer: ${decision.toUpperCase()}`,
      });
    }
  };

  const handleApproveHighConfidence = () => {
    setItems((prev) =>
      prev.map((item) => {
        if (!item.decision && item.similarity_score >= 0.85) {
          handleDecision(item.id, "approved");
          return { ...item, decision: "approved" };
        }
        return item;
      })
    );
  };

  return (
    <div className="absolute right-0 top-0 bottom-0 w-[420px] bg-app-surface/98 backdrop-blur-md border-l border-app-border z-30 flex flex-col select-none animate-in slide-in-from-right duration-200">
      {/* Drawer Header */}
      <div className="h-12 px-4 border-b border-app-border flex items-center justify-between bg-app-surface shrink-0">
        <div className="flex items-center gap-2">
          <Users className="w-4 h-4 text-violet-500" />
          <h3 className="text-xs font-semibold text-app-heading uppercase tracking-wider">
            Ambiguous Entity Reconciliation
          </h3>
          <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/30">
            {pendingCount} Pending
          </span>
        </div>
        <button
          onClick={() => setIsAmbiguousDrawerOpen(false)}
          className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer"
          title="Close drawer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Description & Bulk Actions Toolbar */}
      <div className="p-3 border-b border-app-border bg-app-bg/50 space-y-2 shrink-0">
        <p className="text-[11px] text-app-muted leading-relaxed">
          Borderline entity merges (&tau; &isin; [0.75, 0.88]). Reconcile synonyms and alias mappings
          to prevent spurious error propagation down Bourbaki structuralist models.
        </p>
        <div className="flex items-center justify-between pt-1">
          <span className="text-[10px] text-app-muted font-mono">
            {items.length} total candidates
          </span>
          <button
            onClick={handleApproveHighConfidence}
            disabled={pendingCount === 0}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium bg-violet-600 hover:bg-violet-700 text-white transition-colors disabled:opacity-50 cursor-pointer"
          >
            <CheckCheck className="w-3.5 h-3.5" />
            <span>Approve All High-Conf (&ge; 0.85)</span>
          </button>
        </div>
      </div>

      {/* Candidate List */}
      <div className="flex-1 overflow-y-auto divide-y divide-app-border">
        {items.map((cand) => (
          <div
            key={cand.id}
            className={`p-4 transition-colors space-y-2.5 ${
              cand.decision === "approved"
                ? "bg-emerald-500/5 border-l-2 border-emerald-500"
                : cand.decision === "rejected"
                ? "bg-rose-500/5 border-l-2 border-rose-500"
                : "bg-app-surface/30 hover:bg-app-subtle/50 border-l-2 border-transparent"
            }`}
          >
            {/* Top row: Status and Similarity Pill */}
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono text-[10px] text-app-muted px-1.5 py-0.2 rounded bg-app-subtle">
                {cand.class_name}
              </span>
              <span className="font-mono text-[11px] tabular-nums font-semibold px-2 py-0.5 rounded bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20">
                &tau; {cand.similarity_score.toFixed(3)}
              </span>
            </div>

            {/* Candidate Entities Alignment */}
            <div className="space-y-1.5 font-mono text-[11px]">
              <div>
                <span className="text-[10px] text-app-muted uppercase block font-sans">
                  Predicted Entity
                </span>
                <span className="font-semibold text-app-heading">{cand.predicted_label}</span>
              </div>
              <div>
                <span className="text-[10px] text-app-muted uppercase block font-sans">
                  Candidate Gold Target
                </span>
                <span className="font-semibold text-violet-600 dark:text-violet-400">
                  {cand.candidate_gold_label}
                </span>
              </div>
            </div>

            {/* Evidence quote */}
            {cand.evidence_snippet && (
              <blockquote className="p-2 rounded bg-app-surface text-[10px] italic text-app-muted leading-relaxed font-serif border-l-2 border-violet-400">
                "{cand.evidence_snippet}"
              </blockquote>
            )}

            {/* Decision Status or Action Buttons */}
            <div className="pt-1 flex items-center justify-end gap-2">
              {cand.decision === "approved" ? (
                <div className="flex items-center gap-1 text-[11px] text-emerald-600 font-semibold">
                  <Check className="w-3.5 h-3.5" />
                  <span>Approved as Alias (True Positive)</span>
                </div>
              ) : cand.decision === "rejected" ? (
                <div className="flex items-center gap-1 text-[11px] text-rose-600 font-semibold">
                  <XCircle className="w-3.5 h-3.5" />
                  <span>Rejected (Marked Distinct / False Positive)</span>
                </div>
              ) : (
                <>
                  <ActionableHookPill
                    type="schema_drift"
                    predicate={cand.predicted_label}
                    label="Map in Engine"
                  />
                  <button
                    onClick={() => handleDecision(cand.id, "rejected")}
                    className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium text-rose-600 hover:bg-rose-500/10 border border-rose-500/20 transition-colors"
                  >
                    <X className="w-3 h-3" />
                    <span>Reject</span>
                  </button>
                  <button
                    onClick={() => handleDecision(cand.id, "approved")}
                    className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium bg-emerald-600 hover:bg-emerald-700 text-white transition-colors cursor-pointer"
                  >
                    <Check className="w-3 h-3" />
                    <span>Accept Merge</span>
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
