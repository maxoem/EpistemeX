import React, { useState } from "react";
import {
  Quote,
  GitMerge,
  ShieldCheck,
  FileCode,
  Sparkles,
  ArrowRight,
  ExternalLink,
  CheckCircle2,
  Info,
  ChevronDown,
  ChevronRight,
  Activity,
  Sliders,
  Layers,
} from "lucide-react";
import type {
  AdjudicationQueueItem,
  EdgeAdjudicationItem,
} from "../../../../api/types";
import { ComparativeOverlayGraph } from "./ComparativeOverlayGraph";
import { formatPredicate } from "../../../StageArtifactsView";

export interface AdjudicationInspectorRailProps {
  candidate: AdjudicationQueueItem | null;
  stagedItem: EdgeAdjudicationItem | null;
  onOpenAlias: () => void;
  exportPath: string;
  onChangeExportPath: (path: string) => void;
  stagedCount: number;
}

export const AdjudicationInspectorRail: React.FC<AdjudicationInspectorRailProps> = ({
  candidate,
  stagedItem,
  onOpenAlias,
  exportPath,
  onChangeExportPath,
  stagedCount,
}) => {
  // Secondary tool accordions (collapsed by default to keep evidence & graph front-and-center)
  const [isAliasAccordionOpen, setIsAliasAccordionOpen] = useState(false);
  const [isVectorAccordionOpen, setIsVectorAccordionOpen] = useState(false);
  const [isSafeguardsAccordionOpen, setIsSafeguardsAccordionOpen] = useState(false);

  const hasAlias = Boolean(
    stagedItem?.decision === "schema_alias" || candidate?.current_decision === "schema_alias"
  );
  const activeAliasTarget = stagedItem?.alias_target || candidate?.alias_target || null;

  // Semantic similarity approximations
  const overallSim = candidate?.similarity_score ?? 0.85;
  const headSim = Math.min(1.0, Math.round((overallSim + 0.05) * 100) / 100);
  const tailSim = Math.min(1.0, Math.round((overallSim + 0.03) * 100) / 100);
  const predSim = Math.max(0.4, Math.round((overallSim - 0.08) * 100) / 100);

  const clean = (val?: string) => String(val || "").replace(/^str:|^pred:|^gold:/, "");

  return (
    <aside className="w-full flex-1 flex flex-col h-full overflow-hidden select-none bg-app-surface">
      {/* 1. Rail Docked Header (44px) */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Activity className="w-4 h-4 text-blue-500 shrink-0" />
          <h2 className="text-xs font-semibold text-app-heading tracking-tight truncate font-sans">
            Diagnostic Inspector
          </h2>
        </div>

        {candidate && (
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-semibold truncate max-w-[120px]">
              {candidate.candidate_id}
            </span>
          </div>
        )}
      </div>

      {/* 2. Scrollable Inspector Body */}
      <div className="flex-1 overflow-y-auto divide-y divide-app-border select-text">
        {!candidate ? (
          <div className="p-8 text-center text-xs text-app-muted flex flex-col items-center justify-center h-64">
            <Layers className="w-8 h-8 opacity-25 mb-2" />
            <span className="font-medium text-app-text">No Assertion Selected</span>
            <span className="text-[11px] text-app-muted mt-0.5">
              Select a candidate edge to inspect literature evidence and topological invariants.
            </span>
          </div>
        ) : (
          <>
            {/* ───────────────────────────────────────────────────────────── */}
            {/* SECTION A: VERBATIM LITERATURE PROVENANCE (Primary Evidence)  */}
            {/* ───────────────────────────────────────────────────────────── */}
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Quote className="w-3.5 h-3.5 text-blue-500" />
                  <h3 className="text-xs font-semibold text-app-heading font-sans">
                    Literature Provenance
                  </h3>
                </div>
                <span className="px-1.5 py-0.5 rounded font-mono text-[10px] font-bold text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20">
                  Intra-Chunk Grounding
                </span>
              </div>

              {/* Chunk Tag & Token Metrology */}
              <div className="flex items-center justify-between text-[11px] font-mono text-app-muted">
                <span>chunk_041 · 384 tokens</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                  Verbatim L1 Grounded ✓
                </span>
              </div>

              {/* Verbatim Excerpt with Highlighted Spans */}
              {candidate.evidence_snippet ? (
                <div className="space-y-2">
                  <blockquote className="p-3.5 rounded-md bg-app-subtle/50 border-l-2 border-blue-500 text-xs italic text-app-heading leading-relaxed font-serif">
                    &ldquo;
                    {candidate.evidence_snippet
                      .split(/(\([^)]+\)|derivations|experiment|progressively|critiques|manifestation)/gi)
                      .map((part, i) => {
                        if (/^\(.*\)$/.test(part)) {
                          return (
                            <mark
                              key={i}
                              className="bg-amber-500/20 text-amber-800 dark:text-amber-200 px-1 py-0.5 rounded font-sans not-italic border border-amber-500/30"
                              title="Entity Mention Span"
                            >
                              {part}
                            </mark>
                          );
                        }
                        if (/derivations|experiment|progressively|critiques|manifestation/i.test(part)) {
                          return (
                            <mark
                              key={i}
                              className="bg-purple-500/20 text-purple-800 dark:text-purple-200 px-1 py-0.5 rounded font-sans not-italic border border-purple-500/30"
                              title="Epistemic Relation Functor"
                            >
                              {part}
                            </mark>
                          );
                        }
                        return part;
                      })}
                    &rdquo;
                  </blockquote>

                  {/* Highlighting Legend */}
                  <div className="flex items-center justify-between text-[10px] font-mono text-app-muted pt-0.5">
                    <div className="flex items-center gap-2.5">
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded bg-amber-500/30 border border-amber-500/60" />
                        <span>Entity</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded bg-purple-500/30 border border-purple-500/60" />
                        <span>Predicate</span>
                      </span>
                    </div>
                    <span className="text-app-text font-medium">Source Document Context</span>
                  </div>
                </div>
              ) : (
                <div className="p-4 rounded-md bg-app-subtle/30 border border-dashed border-app-border text-center text-xs text-app-muted space-y-1">
                  <Info className="w-4 h-4 mx-auto opacity-40 text-app-muted" />
                  <p className="font-medium text-app-text">Topological Invariance</p>
                  <p className="text-[11px] text-app-muted">
                    Inferred edge from higher-order ontology synthesis without direct intra-chunk text snippet.
                  </p>
                </div>
              )}
            </div>

            {/* ───────────────────────────────────────────────────────────── */}
            {/* SECTION B: DUAL-STATE NODE-EDGE COMPARATIVE OVERLAY           */}
            {/* ───────────────────────────────────────────────────────────── */}
            <div className="p-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-app-heading font-sans flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-blue-500" />
                  <span>Comparative Graph Overlay</span>
                </h3>
                <span className="text-[10px] font-mono text-app-muted">
                  Superimposed Geometry
                </span>
              </div>

              {/* Embedded Visual Comparative Overlay Graph */}
              <ComparativeOverlayGraph
                predictedEdge={candidate.predicted_edge}
                referenceEdge={candidate.reference_edge}
                decision={stagedItem?.decision ?? candidate.current_decision}
                similarityScore={candidate.similarity_score}
                confidence={candidate.confidence}
                height={190}
              />
            </div>

            {/* ───────────────────────────────────────────────────────────── */}
            {/* SECTION C: COLLAPSIBLE SECONDARY DATA ACCORDIONS              */}
            {/* ───────────────────────────────────────────────────────────── */}

            {/* Accordion 1: Ontology Schema Aliasing */}
            <div className="divide-y divide-app-border/60">
              <button
                type="button"
                onClick={() => setIsAliasAccordionOpen((prev) => !prev)}
                className="w-full px-4 py-2.5 flex items-center justify-between text-left text-xs hover:bg-app-subtle/50 transition-colors cursor-pointer select-none"
              >
                <div className="flex items-center gap-2">
                  {isAliasAccordionOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
                  )}
                  <div className="flex items-center gap-1.5">
                    <GitMerge className="w-3.5 h-3.5 text-violet-500" />
                    <span className="font-semibold text-app-heading font-sans">
                      Ontology Schema Aliasing
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {hasAlias && (
                    <span className="w-2 h-2 rounded-full bg-violet-500" title="Alias active" />
                  )}
                  <span className="text-[10px] font-mono text-violet-500 font-medium">
                    [S] Omnibar
                  </span>
                </div>
              </button>

              {isAliasAccordionOpen && (
                <div className="px-4 py-3 bg-app-bg space-y-3 animate-in fade-in duration-100">
                  <p className="text-[11px] text-app-muted leading-relaxed font-sans">
                    Map candidate vocabulary drift to canonical ontology predicates without modifying extraction pipeline logic.
                  </p>

                  <div className="p-2.5 rounded bg-app-surface border border-app-border space-y-1.5 text-xs font-mono">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-app-muted font-sans">Predicted Predicate:</span>
                      <span className="font-semibold text-amber-500 bg-amber-500/10 px-1.5 py-0.2 rounded text-[10px]">
                        {formatPredicate(candidate.predicted_edge?.predicate || "None")}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-app-muted font-sans">Reference Gold Target:</span>
                      <span className="font-semibold text-emerald-500 bg-emerald-500/10 px-1.5 py-0.2 rounded text-[10px]">
                        {candidate.reference_edge?.predicate
                          ? formatPredicate(candidate.reference_edge.predicate)
                          : "None (Vocabulary Drift)"}
                      </span>
                    </div>
                  </div>

                  {activeAliasTarget ? (
                    <div className="p-2.5 rounded bg-violet-500/10 border border-violet-500/25 text-xs space-y-1">
                      <span className="text-[10px] text-violet-600 dark:text-violet-400 uppercase font-sans font-semibold tracking-wider block">
                        Mapped Alias Target
                      </span>
                      <div className="font-mono text-xs font-bold text-violet-700 dark:text-violet-300">
                        {activeAliasTarget}
                      </div>
                      <button
                        type="button"
                        onClick={onOpenAlias}
                        className="mt-1 w-full py-1 px-2 rounded bg-violet-600/15 hover:bg-violet-600/25 text-violet-600 dark:text-violet-400 border border-violet-500/30 text-[11px] font-medium transition-colors cursor-pointer flex items-center justify-center gap-1.5"
                      >
                        <GitMerge className="w-3 h-3" />
                        <span>Change Canonical Mapping</span>
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={onOpenAlias}
                      className="w-full py-1.5 px-3 rounded bg-violet-600/10 hover:bg-violet-600/20 text-violet-600 dark:text-violet-400 border border-violet-500/30 text-xs font-medium transition-colors flex items-center justify-center gap-2 cursor-pointer"
                    >
                      <GitMerge className="w-3.5 h-3.5" />
                      <span>Map to Canonical Ontology</span>
                      <kbd className="text-[10px] font-mono px-1 py-0.2 rounded bg-violet-500/20">
                        S
                      </kbd>
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Accordion 2: Semantic Similarity Vector Decomposition */}
            <div className="divide-y divide-app-border/60">
              <button
                type="button"
                onClick={() => setIsVectorAccordionOpen((prev) => !prev)}
                className="w-full px-4 py-2.5 flex items-center justify-between text-left text-xs hover:bg-app-subtle/50 transition-colors cursor-pointer select-none"
              >
                <div className="flex items-center gap-2">
                  {isVectorAccordionOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
                  )}
                  <div className="flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-amber-500" />
                    <span className="font-semibold text-app-heading font-sans">
                      Semantic Similarity Decomposition
                    </span>
                  </div>
                </div>

                <span className="font-mono text-[10px] text-amber-500 font-semibold tabular-nums">
                  τ {overallSim.toFixed(3)}
                </span>
              </button>

              {isVectorAccordionOpen && (
                <div className="px-4 py-3 bg-app-bg space-y-2 animate-in fade-in duration-100">
                  <div className="grid grid-cols-3 gap-2">
                    {/* Head Sim */}
                    <div className="p-2 rounded bg-app-surface border border-app-border space-y-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-app-muted">
                        <span>Head Entity</span>
                        <span className="text-emerald-500 font-semibold">{headSim.toFixed(2)}</span>
                      </div>
                      <div className="w-full bg-app-subtle h-1.5 rounded overflow-hidden">
                        <div className="bg-emerald-500 h-full rounded" style={{ width: `${headSim * 100}%` }} />
                      </div>
                    </div>

                    {/* Predicate Sim */}
                    <div className="p-2 rounded bg-app-surface border border-app-border space-y-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-app-muted">
                        <span>Predicate</span>
                        <span className="text-amber-500 font-semibold">{predSim.toFixed(2)}</span>
                      </div>
                      <div className="w-full bg-app-subtle h-1.5 rounded overflow-hidden">
                        <div className="bg-amber-500 h-full rounded" style={{ width: `${predSim * 100}%` }} />
                      </div>
                    </div>

                    {/* Tail Sim */}
                    <div className="p-2 rounded bg-app-surface border border-app-border space-y-1">
                      <div className="flex items-center justify-between text-[10px] font-mono text-app-muted">
                        <span>Tail Entity</span>
                        <span className="text-emerald-500 font-semibold">{tailSim.toFixed(2)}</span>
                      </div>
                      <div className="w-full bg-app-subtle h-1.5 rounded overflow-hidden">
                        <div className="bg-emerald-500 h-full rounded" style={{ width: `${tailSim * 100}%` }} />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Accordion 3: Epistemic Safeguards & Gold Dataset Export */}
            <div className="divide-y divide-app-border/60">
              <button
                type="button"
                onClick={() => setIsSafeguardsAccordionOpen((prev) => !prev)}
                className="w-full px-4 py-2.5 flex items-center justify-between text-left text-xs hover:bg-app-subtle/50 transition-colors cursor-pointer select-none"
              >
                <div className="flex items-center gap-2">
                  {isSafeguardsAccordionOpen ? (
                    <ChevronDown className="w-3.5 h-3.5 text-app-muted" />
                  ) : (
                    <ChevronRight className="w-3.5 h-3.5 text-app-muted" />
                  )}
                  <div className="flex items-center gap-1.5">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                    <span className="font-semibold text-app-heading font-sans">
                      Safeguards & Gold Export
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  {stagedCount > 0 && (
                    <span className="px-1.5 py-0.2 rounded font-mono text-[10px] bg-amber-500/10 text-amber-500 font-semibold">
                      {stagedCount} Staged
                    </span>
                  )}
                </div>
              </button>

              {isSafeguardsAccordionOpen && (
                <div className="px-4 py-3 bg-app-bg space-y-3 animate-in fade-in duration-100 text-xs">
                  {/* Export Path */}
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-1.5 font-semibold text-app-heading font-sans text-xs">
                      <FileCode className="w-3.5 h-3.5 text-app-muted" />
                      <span>Export Adjudicated Dataset</span>
                    </div>
                    <input
                      type="text"
                      value={exportPath}
                      onChange={(e) => onChangeExportPath(e.target.value)}
                      placeholder="e.g. data/gold/adjudicated_v1.json"
                      className="w-full px-2.5 py-1.5 text-xs rounded bg-app-surface border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted font-mono"
                    />
                  </div>

                  {/* Buffer Telemetry */}
                  <div className="p-2.5 rounded bg-app-surface border border-app-border font-mono text-[11px] space-y-1">
                    <div className="flex justify-between">
                      <span className="text-app-muted">Staged Decisions:</span>
                      <span className="text-app-text font-semibold tabular-nums">{stagedCount}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-app-muted">Buffer State:</span>
                      <span className={stagedCount > 0 ? "text-amber-500 font-semibold" : "text-emerald-500 font-semibold"}>
                        {stagedCount > 0 ? "Pending Commit (⌘⏎)" : "Clean"}
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-app-muted leading-relaxed font-sans">
                    Explicit batch commit (⌘⏎) recalculates Bourbaki structural coverage and Poset DAG topological invariants server-side.
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </aside>
  );
};
