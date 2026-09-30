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
} from "lucide-react";
import type {
  AdjudicationQueueItem,
  EdgeAdjudicationItem,
} from "../../../../api/types";

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
  const [activeTab, setActiveTab] = useState<"evidence" | "alias" | "safeguards">("evidence");

  const hasAlias = Boolean(
    stagedItem?.decision === "schema_alias" || candidate?.current_decision === "schema_alias"
  );
  const activeAliasTarget = stagedItem?.alias_target || candidate?.alias_target || null;

  return (
    <aside className="w-[340px] shrink-0 border-l border-app-border bg-app-surface flex flex-col h-full overflow-hidden select-none">
      {/* Zero-Box Segmented Sub-Tabs (design.md Anti-Pattern 4 & Cockpit Nav) */}
      <div className="h-11 px-3 border-b border-app-border bg-app-surface flex items-center justify-between gap-1 shrink-0">
        <div className="inline-flex items-center p-0.5 rounded-md bg-app-bg border border-app-border text-[11px] w-full">
          <button
            type="button"
            onClick={() => setActiveTab("evidence")}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded font-sans transition-colors cursor-pointer ${
              activeTab === "evidence"
                ? "bg-app-surface text-app-heading font-medium border border-app-border/80 shadow-2xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
            }`}
          >
            <Quote className="w-3 h-3 text-blue-500" />
            <span>Evidence</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("alias")}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded font-sans transition-colors cursor-pointer relative ${
              activeTab === "alias"
                ? "bg-app-surface text-app-heading font-medium border border-app-border/80 shadow-2xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
            }`}
          >
            <GitMerge className="w-3 h-3 text-violet-500" />
            <span>Schema Alias</span>
            {hasAlias && (
              <span className="w-1.5 h-1.5 rounded-full bg-violet-500 shrink-0" title="Alias active" />
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("safeguards")}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1 px-2 rounded font-sans transition-colors cursor-pointer relative ${
              activeTab === "safeguards"
                ? "bg-app-surface text-app-heading font-medium border border-app-border/80 shadow-2xs"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
            }`}
          >
            <ShieldCheck className="w-3 h-3 text-emerald-500" />
            <span>Safeguards</span>
            {(exportPath.trim().length > 0 || stagedCount > 0) && (
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" title="Configured / Staged" />
            )}
          </button>
        </div>
      </div>

      {/* Tab Panels */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 select-text">
        {/* TAB 1: Primary Source Evidence */}
        {activeTab === "evidence" && (
          <div className="space-y-4 animate-in fade-in duration-100">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-app-heading font-sans flex items-center gap-1.5">
                  <Quote className="w-3.5 h-3.5 text-blue-500" />
                  <span>Primary Source Evidence</span>
                </h3>
                <span className="text-[10px] font-mono text-emerald-500 font-semibold bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                  High Acuity (L1)
                </span>
              </div>
              <p className="text-[11px] text-app-muted font-sans leading-relaxed">
                Verbatim textual context extracted from source literature to verify candidate relation.
              </p>
            </div>

            {/* Evidence Vitrine Quote with Entity Span Highlighting */}
            {candidate?.evidence_snippet ? (
              <div className="space-y-2">
                <blockquote className="p-3.5 rounded-md bg-app-subtle/40 border-l-2 border-blue-500 text-xs italic text-app-text leading-relaxed font-serif">
                  &ldquo;
                  {candidate.evidence_snippet.split(/(\([^)]+\)|derivations|experiment)/gi).map((part, i) => {
                    if (/^\(.*\)$/.test(part)) {
                      return (
                        <mark
                          key={i}
                          className="bg-amber-500/20 text-amber-700 dark:text-amber-300 px-1 py-0.5 rounded font-sans not-italic border border-amber-500/30"
                          title="Entity Mention Span (Condition / Target)"
                        >
                          {part}
                        </mark>
                      );
                    }
                    if (/derivations|experiment/i.test(part)) {
                      return (
                        <mark
                          key={i}
                          className="bg-blue-500/20 text-blue-700 dark:text-blue-300 px-1 py-0.5 rounded font-sans not-italic border border-blue-500/30"
                          title="Grounding Anchor"
                        >
                          {part}
                        </mark>
                      );
                    }
                    return part;
                  })}
                  &rdquo;
                </blockquote>

                <div className="flex items-center justify-between text-[10px] font-mono text-app-muted pt-0.5">
                  <div className="flex items-center gap-2.5">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded bg-blue-500/30 border border-blue-500/50" />
                      <span>Anchor</span>
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded bg-amber-500/30 border border-amber-500/50" />
                      <span>Span</span>
                    </span>
                  </div>
                  <span className="text-app-text font-medium">Verbatim L1 Grounded</span>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-md bg-app-subtle/20 border border-dashed border-app-border text-center text-xs text-app-muted space-y-1">
                <Info className="w-4 h-4 mx-auto opacity-40 text-app-muted" />
                <p className="font-medium text-app-text">No snippet attached</p>
                <p className="text-[11px] text-app-muted">
                  This candidate edge was inferred topographically without a dedicated text passage span.
                </p>
              </div>
            )}

            {/* Candidate Context Telemetry - Compact Footnote */}
            {candidate && (
              <div className="pt-2 border-t border-app-border/70 flex items-center justify-between text-[11px] font-mono text-app-muted">
                <span className="truncate max-w-[140px]" title={candidate.candidate_id}>
                  ID: <span className="text-app-text">{candidate.candidate_id}</span>
                </span>
                <span>
                  Conf: <span className="text-app-text font-semibold">{(candidate.confidence * 100).toFixed(1)}%</span>
                </span>
              </div>
            )}

            {/* Quick alias notice if already mapped */}
            {hasAlias && activeAliasTarget && (
              <div className="p-2.5 rounded bg-violet-500/10 border border-violet-500/25 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-violet-600 dark:text-violet-400 font-sans font-medium uppercase tracking-wider">
                    Mapped Schema Alias
                  </span>
                  <button
                    type="button"
                    onClick={() => setActiveTab("alias")}
                    className="text-[10px] text-violet-500 hover:underline cursor-pointer"
                  >
                    View Details →
                  </button>
                </div>
                <div className="font-mono text-xs font-semibold text-violet-700 dark:text-violet-300">
                  {activeAliasTarget}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Schema Aliasing */}
        {activeTab === "alias" && (
          <div className="space-y-4 animate-in fade-in duration-100">
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-app-heading font-sans flex items-center gap-1.5">
                  <GitMerge className="w-3.5 h-3.5 text-violet-500" />
                  <span>Ontology Schema Aliasing</span>
                </h3>
                <button
                  type="button"
                  onClick={onOpenAlias}
                  className="text-[11px] font-mono text-violet-500 hover:text-violet-400 font-medium cursor-pointer"
                  title="Open Omnibar (Hotkey: S)"
                >
                  [S] Omnibar
                </button>
              </div>
              <p className="text-[11px] text-app-muted font-sans leading-relaxed">
                Map candidate vocabulary drift to canonical ontology predicates without modifying extraction pipeline logic.
              </p>
            </div>

            {/* Predicate Comparison */}
            <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-app-muted font-sans">Predicted Predicate</span>
                <span className="font-mono font-semibold text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded text-[11px]">
                  {candidate?.predicted_edge?.predicate || "None"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-app-muted font-sans">Reference Gold Target</span>
                <span className="font-mono font-semibold text-blue-500 bg-blue-500/10 px-1.5 py-0.5 rounded text-[11px]">
                  {candidate?.reference_edge?.predicate || "None (Vocabulary Drift)"}
                </span>
              </div>
            </div>

            {/* Active Target Banner */}
            {activeAliasTarget ? (
              <div className="p-3 rounded-md bg-violet-500/10 border border-violet-500/30 text-xs space-y-1.5">
                <span className="text-[10px] text-app-muted uppercase font-sans font-semibold tracking-wider block">
                  Active Alias Target
                </span>
                <div className="font-mono text-xs font-bold text-violet-600 dark:text-violet-400">
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
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={onOpenAlias}
                  className="w-full py-2 px-3 rounded bg-violet-600/10 hover:bg-violet-600/20 text-violet-600 dark:text-violet-400 border border-violet-500/30 text-xs font-medium transition-colors flex items-center justify-center gap-2 cursor-pointer"
                >
                  <GitMerge className="w-3.5 h-3.5" />
                  <span>Map to Canonical Ontology</span>
                  <kbd className="text-[10px] font-mono px-1 py-0.2 rounded bg-violet-500/20">
                    S
                  </kbd>
                </button>
                <p className="text-[10px] text-app-muted text-center font-sans">
                  Pressing [S] opens the canonical schema predicate selector.
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: Safeguards & Export */}
        {activeTab === "safeguards" && (
          <div className="space-y-4 animate-in fade-in duration-100">
            {/* Section A: Gold Standard Export */}
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-app-heading font-sans">
                <FileCode className="w-3.5 h-3.5 text-app-muted" />
                <span>Export Adjudicated Dataset</span>
              </div>
              <p className="text-[11px] text-app-muted font-sans leading-relaxed">
                Optionally persist approved edge annotations to an immutable gold standard file for future regression testing.
              </p>
              <input
                type="text"
                value={exportPath}
                onChange={(e) => onChangeExportPath(e.target.value)}
                placeholder="e.g. data/gold/adjudicated_v1.json"
                className="w-full px-2.5 py-1.5 text-xs rounded bg-app-bg border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted font-mono"
              />
            </div>

            {/* Section B: Formal Epistemic Safeguards */}
            <div className="space-y-2 pt-2 border-t border-app-border/70">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-app-heading font-sans">
                <ShieldCheck className="w-3.5 h-3.5 text-blue-500" />
                <span>Formal Epistemic Safeguards</span>
              </div>
              <div className="p-3 rounded-md bg-app-subtle/30 border border-app-border/70 text-[11px] text-app-muted space-y-2 font-sans leading-relaxed">
                <p>
                  Adjudications are held in a deterministic client buffer. Decisions staged via [A], [R], or [S] apply local previews without sending uncommitted network requests.
                </p>
                <p>
                  Explicit commit (⌘⏎) triggers server-side recalculation of Poset DAG integrity and Bourbaki structural coverage.
                </p>
              </div>
            </div>

            {/* Section C: Buffer Telemetry */}
            <div className="pt-2 border-t border-app-border/70 space-y-1.5">
              <span className="text-[11px] font-semibold text-app-heading font-sans block">
                Buffer Telemetry
              </span>
              <div className="p-2.5 rounded bg-app-bg border border-app-border font-mono text-[11px] space-y-1">
                <div className="flex justify-between">
                  <span className="text-app-muted">Staged Decisions:</span>
                  <span className="text-app-text font-semibold tabular-nums">{stagedCount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-app-muted">Buffer State:</span>
                  <span className={stagedCount > 0 ? "text-amber-500 font-semibold" : "text-emerald-500 font-semibold"}>
                    {stagedCount > 0 ? "Pending Commit" : "Clean"}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
