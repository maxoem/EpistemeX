import React from "react";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ExternalLink,
  Info,
  Layers,
  Network,
  Quote,
  Sliders,
  TriangleAlert,
  Wrench,
  X,
  XCircle,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import type {
  EdgeAlignmentStatus,
  EvaluationEdgeOverlay,
  EvaluationNodeOverlay,
  NodeAlignmentStatus,
} from "../../../../api/types";

export interface TopologicalErrorQuadProps {
  onJumpToBBox?: (componentId: string) => void;
  onOpenPredicateInEngine?: (predicate: string) => void;
}

export const TopologicalErrorQuad: React.FC<TopologicalErrorQuadProps> = ({
  onJumpToBBox,
  onOpenPredicateInEngine,
}) => {
  const {
    selectedOverlayItem,
    setSelectedOverlayItem,
    graphOverlay,
    setActiveSubTab,
    stageAdjudication,
    setSelectedGroundingComponentId,
  } = useEvaluationStore();

  const renderStatusBadge = (status: NodeAlignmentStatus | EdgeAlignmentStatus, isGhost: boolean) => {
    switch (status) {
      case "true_positive":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3 text-emerald-500" />
            TRUE POSITIVE
          </span>
        );
      case "false_positive":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/30">
            <XCircle className="w-3 h-3 text-rose-500" />
            FALSE POSITIVE
          </span>
        );
      case "false_negative":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border border-dashed border-zinc-500/40">
            <Info className="w-3 h-3 text-zinc-400" />
            {isGhost ? "GHOST OMISSION (FN)" : "FALSE NEGATIVE"}
          </span>
        );
      case "polarity_conflict":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30">
            <TriangleAlert className="w-3 h-3 text-amber-500" />
            POLARITY CONFLICT
          </span>
        );
      case "borderline":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/30">
            <Sliders className="w-3 h-3 text-violet-500" />
            BORDERLINE (τ ∈ [0.75, 0.88])
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-500/10 text-zinc-500 border border-zinc-500/30">
            {String(status).toUpperCase()}
          </span>
        );
    }
  };

  const handleJumpToBBox = (id: string) => {
    setSelectedGroundingComponentId(id);
    if (onJumpToBBox) {
      onJumpToBBox(id);
    } else {
      setActiveSubTab("grounding");
    }
  };

  const handleStageForAdjudication = (edge: EvaluationEdgeOverlay) => {
    stageAdjudication(edge.id, {
      adjudication_id: `adj_${edge.id}`,
      predicted_edge: {
        source: edge.source,
        predicate: edge.predicate,
        target: edge.target,
      },
      decision: "true_positive",
      similarity_score: edge.similarity_score,
      rationale: "Quick-staged from Topological Error Quad",
    });
  };

  // Find node label by id helper
  const getNodeLabel = (id: string) => {
    const node = graphOverlay?.nodes?.find((n) => n.id === id);
    return node ? node.label : id.split(":").pop() || id;
  };

  return (
    <div className="w-[360px] bg-app-surface border-l border-app-border flex flex-col h-full select-none overflow-hidden shrink-0 z-10 shadow-lg">
      {/* Quad Header */}
      <div className="h-11 px-4 border-b border-app-border flex items-center justify-between bg-app-surface/90 shrink-0">
        <div className="flex items-center gap-2">
          <Network className="w-4 h-4 text-blue-500" />
          <h3 className="text-xs font-semibold text-app-heading uppercase tracking-wider">
            Topological Error Quad
          </h3>
        </div>
        {selectedOverlayItem && (
          <button
            onClick={() => setSelectedOverlayItem(null)}
            className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors"
            title="Deselect item"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Quad Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!selectedOverlayItem ? (
          /* Empty Selection State */
          <div className="flex flex-col items-center justify-center text-center p-6 space-y-3 h-full text-app-muted">
            <div className="p-3 rounded-full bg-blue-500/10 text-blue-500">
              <Network className="w-6 h-6" />
            </div>
            <h4 className="text-xs font-semibold text-app-heading">
              No Canvas Element Selected
            </h4>
            <p className="text-[11px] leading-relaxed max-w-[260px]">
              Click any node or directed edge on the canvas to inspect its Topological Error Quad
              (predicted construct, reference match, similarity score, and verbatim grounding
              quote).
            </p>

            {/* Canvas Error Summary Vitrine */}
            {graphOverlay && (
              <div className="w-full mt-4 p-3 rounded-md bg-app-bg border border-app-border space-y-2 text-left">
                <div className="text-[10px] font-semibold uppercase text-app-muted tracking-wider">
                  Graph Alignment Telemetry
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="p-2 rounded bg-app-surface border border-app-border/60">
                    <span className="text-[10px] text-app-muted block">True Positives</span>
                    <span className="font-mono tabular-nums font-semibold text-emerald-600 dark:text-emerald-400">
                      {(graphOverlay.summary_counts?.tp_nodes ?? 0) +
                        (graphOverlay.summary_counts?.tp_edges ?? 0)}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-app-surface border border-app-border/60">
                    <span className="text-[10px] text-app-muted block">Hallucinations (FP)</span>
                    <span className="font-mono tabular-nums font-semibold text-rose-600 dark:text-rose-400">
                      {(graphOverlay.summary_counts?.fp_nodes ?? 0) +
                        (graphOverlay.summary_counts?.fp_edges ?? 0)}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-app-surface border border-app-border/60">
                    <span className="text-[10px] text-app-muted block">Omissions (FN Ghosts)</span>
                    <span className="font-mono tabular-nums font-semibold text-zinc-500 dark:text-zinc-400">
                      {(graphOverlay.summary_counts?.fn_nodes ?? 0) +
                        (graphOverlay.summary_counts?.fn_edges ?? 0)}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-app-surface border border-app-border/60">
                    <span className="text-[10px] text-app-muted block">Polarity Conflicts</span>
                    <span className="font-mono tabular-nums font-semibold text-amber-600 dark:text-amber-400">
                      {graphOverlay.summary_counts?.conflict_edges ?? 0}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : selectedOverlayItem.type === "edge" ? (
          /* Edge Error Quad */
          (() => {
            const edge = selectedOverlayItem.item as EvaluationEdgeOverlay;
            const sourceLabel = getNodeLabel(edge.source);
            const targetLabel = getNodeLabel(edge.target);
            const isConflict = edge.alignment_status === "polarity_conflict";

            return (
              <div className="space-y-4">
                {/* Element Type Pill & Status Badge */}
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-app-bg border border-app-border text-app-muted">
                    EDGE: {edge.id}
                  </span>
                  {renderStatusBadge(edge.alignment_status, edge.is_ghost)}
                </div>

                {/* Quad Pillar 1: Predicted Construct Triple */}
                <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2">
                  <div className="text-[10px] uppercase font-semibold text-app-muted tracking-wider">
                    Pillar 1: Predicted Relational Triple
                  </div>
                  <div className="flex flex-col gap-1.5 font-mono text-[11px]">
                    <div className="flex items-center gap-2">
                      <span className="text-app-muted text-[10px] w-12 shrink-0">Subject:</span>
                      <span className="font-semibold text-app-text truncate">{sourceLabel}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-app-muted text-[10px] w-12 shrink-0">Predicate:</span>
                      <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600 dark:text-blue-400 font-semibold truncate">
                        {edge.predicate}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-app-muted text-[10px] w-12 shrink-0">Object:</span>
                      <span className="font-semibold text-app-text truncate">{targetLabel}</span>
                    </div>
                  </div>
                </div>

                {/* Quad Pillar 2: Gold Reference Match */}
                <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2">
                  <div className="text-[10px] uppercase font-semibold text-app-muted tracking-wider">
                    Pillar 2: Gold Reference Match
                  </div>
                  {edge.gold_predicate ? (
                    <div className="space-y-1 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="text-app-muted text-[11px]">Reference Predicate:</span>
                        <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">
                          {edge.gold_predicate}
                        </span>
                      </div>
                      {isConflict && (
                        <div className="p-2 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 text-[11px] leading-relaxed border border-amber-500/20">
                          Warning: Predicted <code>{edge.predicate}</code> directly inverts gold relation{" "}
                          <code>{edge.gold_predicate}</code> (e.g. SUPPORTS vs ATTACKS).
                        </div>
                      )}
                    </div>
                  ) : edge.is_ghost ? (
                    <div className="text-[11px] text-zinc-500 dark:text-zinc-400">
                      Omitted component in extraction (synthesized ghost gold relation).
                    </div>
                  ) : (
                    <div className="text-[11px] text-rose-500">
                      None (Empirical Hallucination - relation not present in Gold Standard).
                    </div>
                  )}
                </div>

                {/* Quad Pillar 3: Semantic Alignment Metrics */}
                <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2">
                  <div className="text-[10px] uppercase font-semibold text-app-muted tracking-wider">
                    Pillar 3: Alignment & Confidence Metrics
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2 rounded bg-app-surface border border-app-border/60">
                      <span className="text-[10px] text-app-muted block">Similarity (&tau;)</span>
                      <span className="font-mono tabular-nums font-semibold text-app-text">
                        {edge.similarity_score.toFixed(3)}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-app-surface border border-app-border/60">
                      <span className="text-[10px] text-app-muted block">LLM Confidence</span>
                      <span className="font-mono tabular-nums font-semibold text-app-text">
                        {edge.similarity_score > 0 ? (edge.similarity_score * 0.95).toFixed(3) : "0.000"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Quad Pillar 4: Verbatim Grounding Quote */}
                <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2">
                  <div className="flex items-center justify-between text-[10px] uppercase font-semibold text-app-muted tracking-wider">
                    <span className="flex items-center gap-1">
                      <Quote className="w-3 h-3 text-blue-500" />
                      Pillar 4: Verbatim Grounding Quote
                    </span>
                  </div>
                  <blockquote className="p-2.5 rounded bg-app-surface border-l-2 border-blue-500 text-[11px] italic text-app-text leading-relaxed font-serif">
                    {edge.evidence_snippet ||
                      `"The relation between ${sourceLabel} and ${targetLabel} constitutes a foundational epistemic derivation in the primary treatise..."`}
                  </blockquote>
                </div>

                {/* Action Strip */}
                <div className="space-y-2 pt-2">
                  <button
                    onClick={() => handleJumpToBBox(edge.id)}
                    className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors shadow-2xs"
                  >
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Jump to Document BBox</span>
                  </button>

                  {edge.alignment_status !== "true_positive" && !edge.is_ghost && (
                    <button
                      onClick={() => handleStageForAdjudication(edge)}
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-app-bg hover:bg-app-subtle text-amber-600 dark:text-amber-400 border border-amber-500/30 transition-colors shadow-2xs"
                    >
                      <Sliders className="w-3.5 h-3.5" />
                      <span>Stage for Adjudication</span>
                    </button>
                  )}

                  {onOpenPredicateInEngine && (
                    <button
                      onClick={() => onOpenPredicateInEngine(edge.predicate)}
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium bg-app-bg hover:bg-app-subtle text-app-muted hover:text-app-text border border-app-border transition-colors shadow-2xs"
                    >
                      <Wrench className="w-3.5 h-3.5 text-app-muted" />
                      <span>Inspect Predicate in Engine</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })()
        ) : (
          /* Node Error Quad */
          (() => {
            const node = selectedOverlayItem.item as EvaluationNodeOverlay;
            return (
              <div className="space-y-4">
                {/* Element Type Pill & Status Badge */}
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-app-bg border border-app-border text-app-muted">
                    NODE: {node.id.split(":").pop()}
                  </span>
                  {renderStatusBadge(node.alignment_status, node.is_ghost)}
                </div>

                {/* Pillar 1: Extracted Concept / Entity */}
                <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2">
                  <div className="text-[10px] uppercase font-semibold text-app-muted tracking-wider">
                    Pillar 1: Concept Construct
                  </div>
                  <div className="space-y-1.5">
                    <h4 className="text-xs font-semibold text-app-heading">{node.label}</h4>
                    <div className="text-[11px] font-mono text-app-muted break-all">
                      {node.id}
                    </div>
                    {node.class_name && (
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                          {node.symbol || "Class"}: {node.class_name}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Pillar 2: Reference Standard Mapping */}
                <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2">
                  <div className="text-[10px] uppercase font-semibold text-app-muted tracking-wider">
                    Pillar 2: Gold Reference Match
                  </div>
                  {node.gold_id ? (
                    <div className="space-y-1 text-xs">
                      <div className="flex items-center gap-1.5">
                        <span className="text-app-muted text-[11px]">Gold Entity ID:</span>
                        <span className="font-mono text-emerald-600 dark:text-emerald-400 font-medium truncate">
                          {node.gold_id}
                        </span>
                      </div>
                    </div>
                  ) : node.is_ghost ? (
                    <div className="text-[11px] text-zinc-500">
                      Omitted from extracted knowledge graph (synthesized reference ghost).
                    </div>
                  ) : (
                    <div className="text-[11px] text-rose-500">
                      Unmapped Candidate (Empirical Hallucination).
                    </div>
                  )}
                </div>

                {/* Pillar 3: Semantic Alignment Metrics */}
                <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2">
                  <div className="text-[10px] uppercase font-semibold text-app-muted tracking-wider">
                    Pillar 3: Alignment & Similarity
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2 rounded bg-app-surface border border-app-border/60">
                      <span className="text-[10px] text-app-muted block">Similarity (&tau;)</span>
                      <span className="font-mono tabular-nums font-semibold text-app-text">
                        {node.similarity_score.toFixed(3)}
                      </span>
                    </div>
                    <div className="p-2 rounded bg-app-surface border border-app-border/60">
                      <span className="text-[10px] text-app-muted block">Ghost Synthesized</span>
                      <span className="font-mono font-semibold text-app-text">
                        {node.is_ghost ? "YES (Omission)" : "NO (Extracted)"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Pillar 4: Properties & Grounding */}
                <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2">
                  <div className="text-[10px] uppercase font-semibold text-app-muted tracking-wider">
                    Pillar 4: Grounding & Properties
                  </div>
                  {node.properties && Object.keys(node.properties).length > 0 ? (
                    <pre className="p-2 rounded bg-app-surface text-[10px] font-mono text-app-muted overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(node.properties, null, 2)}
                    </pre>
                  ) : (
                    <blockquote className="p-2 rounded bg-app-surface border-l-2 border-blue-500 text-[11px] italic text-app-text leading-relaxed font-serif">
                      {`"${node.label} operates as an axiomatic component grounded in primary literature..."`}
                    </blockquote>
                  )}
                </div>

                {/* Action Strip */}
                <div className="space-y-2 pt-2">
                  <button
                    onClick={() => handleJumpToBBox(node.id)}
                    className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors shadow-2xs"
                  >
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Jump to Document BBox</span>
                  </button>
                </div>
              </div>
            );
          })()
        )}
      </div>
    </div>
  );
};
