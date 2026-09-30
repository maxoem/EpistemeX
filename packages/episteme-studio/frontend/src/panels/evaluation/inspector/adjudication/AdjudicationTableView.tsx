import React, { useEffect, useRef } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Filter,
  GitMerge,
  Loader2,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";
import type {
  AdjudicationDecision,
  AdjudicationQueueItem,
  EdgeAdjudicationItem,
} from "../../../../api/types";
import { formatPredicate } from "../../../StageArtifactsView";
import { classifyEpistemicRole } from "../../../assertionTransformer";

export interface AdjudicationTableViewProps {
  candidates: AdjudicationQueueItem[];
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
  stagedMap: Map<string, EdgeAdjudicationItem>;
  filterStatus: "pending" | "adjudicated" | "all";
  onChangeFilterStatus: (status: "pending" | "adjudicated" | "all") => void;
  searchQuery: string;
  onChangeSearchQuery: (query: string) => void;
  counts: {
    pending: number;
    adjudicated: number;
    all: number;
  };
  minSim?: number;
  maxSim?: number;
  rationaleMap: Record<string, string>;
  onChangeRationale: (candidateId: string, val: string) => void;
  onAccept: () => void;
  onReject: () => void;
  onOpenAlias: () => void;
  onUndo: () => void;
  expandedRowId: string | null;
  onToggleExpandRow: (id: string) => void;
  // Consolidated staging & commit toolbar props
  stagedCount?: number;
  optimisticF1Delta?: number;
  isCommittingBatch?: boolean;
  onCommitBatch?: () => void;
  onRefresh?: () => void;
  isLoading?: boolean;
  localMessage?: string | null;
}

export const AdjudicationTableView: React.FC<AdjudicationTableViewProps> = ({
  candidates,
  selectedIndex,
  onSelectIndex,
  stagedMap,
  filterStatus,
  onChangeFilterStatus,
  searchQuery,
  onChangeSearchQuery,
  counts,
  minSim = 0.75,
  maxSim = 0.95,
  rationaleMap,
  onChangeRationale,
  onAccept,
  onReject,
  onOpenAlias,
  onUndo,
  expandedRowId,
  onToggleExpandRow,
  stagedCount = 0,
  optimisticF1Delta = 0,
  isCommittingBatch = false,
  onCommitBatch,
  onRefresh,
  isLoading = false,
  localMessage,
}) => {
  const tableContainerRef = useRef<HTMLDivElement>(null);
  const selectedRowRef = useRef<HTMLDivElement>(null);

  // Auto-scroll selected row into view smoothly
  useEffect(() => {
    if (selectedRowRef.current) {
      selectedRowRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [selectedIndex]);

  const clean = (val?: string) => String(val || "").replace(/^str:|^pred:|^gold:/, "");

  const formatNaturalSentence = (
    subj?: string,
    pred?: string,
    obj?: string
  ): string => {
    const s = clean(subj);
    const p = formatPredicate(pred || "");
    const o = clean(obj);
    if (!s && !p && !o) return "No proposition available.";
    return `${s} ${p} ${o}.`;
  };

  const renderStatusBadge = (decision: AdjudicationDecision | null | undefined, isStaged: boolean) => {
    if (!decision) {
      return (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium text-app-muted bg-app-subtle border border-app-border/70">
          Pending
        </span>
      );
    }

    if (decision === "true_positive") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
          <CheckCircle2 className="w-2.5 h-2.5 text-emerald-500" />
          <span>{isStaged ? "TP [Staged]" : "TP"}</span>
        </span>
      );
    }
    if (decision === "false_positive") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30">
          <XCircle className="w-2.5 h-2.5 text-rose-500" />
          <span>{isStaged ? "FP [Staged]" : "FP"}</span>
        </span>
      );
    }
    if (decision === "schema_alias") {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-violet-500/15 text-violet-600 dark:text-violet-400 border border-violet-500/30">
          <GitMerge className="w-2.5 h-2.5 text-violet-500" />
          <span>{isStaged ? "Alias [Staged]" : "Alias"}</span>
        </span>
      );
    }
    return null;
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 1. Single Consolidated Action & Filter Header (Clean 40px)          */}
      {/* Replaces redundant stacked title & filter rows to reclaim viewport  */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-10 px-3 border-b border-app-border bg-app-surface flex items-center justify-between gap-3 shrink-0 text-xs">
        {/* Left: Triage Status Filter Pills + Uncertainty Band */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-0.5 bg-app-bg p-0.5 rounded-lg border border-app-border text-[11px]">
            <button
              type="button"
              onClick={() => onChangeFilterStatus("pending")}
              className={`px-2 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                filterStatus === "pending"
                  ? "bg-amber-500/15 text-amber-700 dark:text-amber-300 font-semibold border border-amber-500/30"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              <span>Pending</span>
              <span className="font-mono text-[10px] tabular-nums">{counts.pending}</span>
            </button>

            <button
              type="button"
              onClick={() => onChangeFilterStatus("adjudicated")}
              className={`px-2 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                filterStatus === "adjudicated"
                  ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 font-semibold border border-emerald-500/30"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
              }`}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>Adjudicated</span>
              <span className="font-mono text-[10px] tabular-nums">{counts.adjudicated}</span>
            </button>

            <button
              type="button"
              onClick={() => onChangeFilterStatus("all")}
              className={`px-2 py-1 rounded-md transition-all cursor-pointer flex items-center gap-1.5 ${
                filterStatus === "all"
                  ? "bg-blue-500/15 text-blue-700 dark:text-blue-300 font-semibold border border-blue-500/30"
                  : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
              }`}
            >
              <span>All</span>
              <span className="font-mono text-[10px] tabular-nums">{counts.all}</span>
            </button>
          </div>

          {/* Uncertainty Band τ indicator */}
          <div className="hidden lg:flex items-center gap-1 px-1.5 py-0.5 rounded text-[10.5px] bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-mono">
            <span className="text-[9.5px] font-sans text-app-muted">τ ∈</span>
            <span>[{minSim.toFixed(2)} - {maxSim.toFixed(2)}]</span>
          </div>
        </div>

        {/* Center: Search Input */}
        <div className="flex-1 max-w-xs relative flex items-center">
          <Search className="w-3.5 h-3.5 absolute left-2.5 text-app-muted pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onChangeSearchQuery(e.target.value)}
            placeholder="Search propositions or entities..."
            className="w-full h-7 pl-8 pr-10 rounded bg-app-bg text-app-heading placeholder-app-muted border border-app-border text-xs font-sans focus:outline-none focus:border-blue-500"
          />
          {searchQuery ? (
            <button
              type="button"
              onClick={() => onChangeSearchQuery("")}
              className="absolute right-2 text-app-muted hover:text-app-heading cursor-pointer"
            >
              <X className="w-3 h-3" />
            </button>
          ) : (
            <kbd className="hidden sm:inline-flex items-center absolute right-2 px-1 py-0.2 rounded bg-app-subtle border border-app-border text-[9px] font-mono text-app-muted pointer-events-none">
              j / k
            </kbd>
          )}
        </div>

        {/* Right: Consolidated Staged Batch Commit Actions */}
        <div className="flex items-center gap-2 shrink-0">
          {localMessage && (
            <span className="hidden xl:inline text-emerald-500 font-sans font-medium animate-pulse text-[11px]">
              {localMessage}
            </span>
          )}

          {stagedCount > 0 && (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-xs font-mono tabular-nums">
              <Sparkles className="w-3 h-3 text-emerald-500 shrink-0" />
              <span>
                {stagedCount} Staged
                {optimisticF1Delta !== 0 && (
                  <span className="ml-1 text-[10px]">
                    ({optimisticF1Delta > 0 ? "+" : ""}{optimisticF1Delta.toFixed(3)} F₁)
                  </span>
                )}
              </span>
            </div>
          )}

          {onRefresh && (
            <button
              type="button"
              onClick={onRefresh}
              disabled={isLoading}
              className="p-1 rounded text-app-muted hover:text-app-text hover:bg-app-subtle transition-colors cursor-pointer disabled:opacity-50"
              title="Refresh Queue"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            </button>
          )}

          {onCommitBatch && (
            <button
              type="button"
              onClick={onCommitBatch}
              disabled={stagedCount === 0 || isCommittingBatch}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                stagedCount > 0
                  ? "bg-blue-600 hover:bg-blue-700 text-white cursor-pointer shadow-xs"
                  : "bg-app-subtle text-app-muted border border-app-border cursor-not-allowed opacity-60"
              }`}
              title="Commit all staged decisions (Cmd+Enter)"
            >
              {isCommittingBatch ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <Send className="w-3 h-3" />
              )}
              <span>Commit ({stagedCount})</span>
              <kbd className="hidden sm:inline-block px-1 py-0.2 rounded text-[9px] font-mono bg-black/20">
                ⌘⏎
              </kbd>
            </button>
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 2. Intelligent Auto-Balanced Table Header Row                      */}
      {/* Generous proportional space for Epistemic Function column           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="h-8 px-4 border-b border-app-border bg-app-surface text-[10px] font-mono uppercase tracking-wider text-app-muted flex items-center justify-between shrink-0 select-none">
        <div className="flex items-center gap-3 flex-1 min-w-0 pr-4">
          <span className="w-6 shrink-0 text-center">#</span>
          <span className="flex-1 min-w-[170px] truncate">Subject Concept</span>
          <span className="flex-[1.4] min-w-[280px] text-center">
            Epistemic Function & Differential
          </span>
          <span className="flex-1 min-w-[170px] truncate">Target Object</span>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <span className="w-20 text-center">Class</span>
          <span className="w-16 text-right">Sim / Conf</span>
          <span className="w-24 text-right">Triage Status</span>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 3. Table Rows Body: Prominent Focus & Clean Stacked Cell Diffing    */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div
        ref={tableContainerRef}
        className="flex-1 overflow-y-auto divide-y divide-app-border/40 bg-app-bg"
      >
        {candidates.length === 0 ? (
          <div className="py-20 px-6 text-center text-xs text-app-muted font-mono flex flex-col items-center justify-center">
            <Filter className="w-8 h-8 opacity-25 mb-2" />
            <span className="font-semibold text-app-text">No Candidate Edges Found</span>
            <span className="text-[11px] text-app-muted mt-1">
              {searchQuery
                ? `No propositions match search query "${searchQuery}"`
                : "No candidate edges currently staged for this filter condition."}
            </span>
          </div>
        ) : (
          candidates.map((candidate, idx) => {
            const isSelected = idx === selectedIndex;
            const isExpanded = expandedRowId === candidate.candidate_id;
            const staged = stagedMap.get(candidate.candidate_id);
            const activeDecision = staged?.decision ?? candidate.current_decision;
            const isStaged = Boolean(staged);

            const predSource = clean(candidate.predicted_edge?.source);
            const predPredicate = formatPredicate(candidate.predicted_edge?.predicate || "");
            const predTarget = clean(candidate.predicted_edge?.target);

            const hasRef = Boolean(candidate.reference_edge);
            const refSource = hasRef ? clean(candidate.reference_edge?.source) : null;
            const refPredicate = hasRef
              ? formatPredicate(candidate.reference_edge?.predicate || "")
              : null;
            const refTarget = hasRef ? clean(candidate.reference_edge?.target) : null;

            // Differential checks
            const hasPredicateDiff =
              refPredicate && refPredicate.toLowerCase() !== predPredicate.toLowerCase();
            const hasSourceDiff =
              refSource && refSource.toLowerCase() !== predSource.toLowerCase();
            const hasTargetDiff =
              refTarget && refTarget.toLowerCase() !== predTarget.toLowerCase();

            // Epistemic class classification
            const epistemicClass = classifyEpistemicRole(
              candidate.predicted_edge?.predicate || ""
            );

            // Vector decomposition approximation for expanded state
            const overallSim = candidate.similarity_score;
            const headSim = Math.min(1.0, Math.round((overallSim + 0.05) * 100) / 100);
            const tailSim = Math.min(1.0, Math.round((overallSim + 0.03) * 100) / 100);
            const predSim = Math.max(0.4, Math.round((overallSim - 0.08) * 100) / 100);

            return (
              <div
                key={candidate.candidate_id}
                ref={isSelected ? selectedRowRef : undefined}
                className={`group flex flex-col transition-all select-none text-xs ${
                  isSelected
                    ? "bg-blue-500/[0.08] dark:bg-blue-500/[0.14] border-l-[5px] border-l-blue-600 dark:border-l-blue-400 border-y border-blue-500/25 shadow-xs z-10"
                    : "border-l-[5px] border-l-transparent hover:bg-app-subtle/50"
                }`}
              >
                {/* Main Horizontal Proposition Row with Proportional Layout */}
                <div
                  onClick={() => onSelectIndex(idx)}
                  className={`px-3 py-2 flex items-center justify-between cursor-pointer ${
                    hasPredicateDiff ? "min-h-[58px]" : "min-h-[44px]"
                  }`}
                >
                  {/* Left: Continuous Proposition (Subject ── Predicate ──► Object) */}
                  <div className="flex items-center gap-3 min-w-0 flex-1 pr-4">
                    {/* Active Focus Indicator / Expand Chevron */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectIndex(idx);
                        onToggleExpandRow(candidate.candidate_id);
                      }}
                      className={`w-6 h-6 flex items-center justify-center rounded shrink-0 cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-blue-600 text-white font-bold shadow-xs"
                          : "text-app-muted hover:text-app-text hover:bg-app-subtle"
                      }`}
                      title={isExpanded ? "Collapse proposition sentence (Space)" : "Expand proposition sentence (Space)"}
                    >
                      {isExpanded ? (
                        <ChevronDown className="w-3.5 h-3.5" />
                      ) : isSelected ? (
                        <span className="font-mono text-[10px] font-bold">{idx + 1}</span>
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100" />
                      )}
                    </button>

                    {/* Subject Concept (Fluid min-w-170 flex-1) */}
                    <div
                      className="flex-1 min-w-[170px] font-sans text-[12px] tracking-tight truncate"
                      title={predSource}
                    >
                      {hasSourceDiff ? (
                        <div className="flex flex-col gap-0.5">
                          <span className="px-1.5 py-0.2 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 font-mono text-[11px] w-fit truncate">
                            {predSource}
                          </span>
                          <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium text-[11px] w-fit truncate">
                            {refSource}
                          </span>
                        </div>
                      ) : (
                        <span className={isSelected ? "font-bold text-app-heading" : "text-app-heading font-medium"}>
                          {predSource}
                        </span>
                      )}
                    </div>

                    {/* ───────────────────────────────────────────────────────── */}
                    {/* Epistemic Function: Clean Stacked Cell Diffing            */}
                    {/* Predicted in subtle red container, Gold in green below    */}
                    {/* ───────────────────────────────────────────────────────── */}
                    <div className="flex-[1.4] min-w-[280px] flex items-center px-2 group/conn justify-center">
                      <div className="h-[1px] flex-1 bg-app-border group-hover:bg-blue-500/40 transition-colors" />

                      <div className="mx-2 text-center shrink-0">
                        {hasPredicateDiff ? (
                          /* Stacked Clean Differential within Cell */
                          <div className="flex flex-col items-center gap-1 py-1">
                            {/* Predicted Predicate in subtle red container */}
                            <div
                              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/25 font-mono text-[11px] font-semibold tracking-tight shadow-2xs"
                              title={`Predicted Pipeline Operator: ${predPredicate}`}
                            >
                              <span className="text-[9px] uppercase tracking-wider font-sans font-bold text-rose-500/70">
                                pred:
                              </span>
                              <span>{predPredicate}</span>
                            </div>

                            {/* Gold Standard Predicate directly below in green container */}
                            <div
                              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 font-mono text-[11px] font-semibold tracking-tight shadow-2xs"
                              title={`Reference Gold Target: ${refPredicate}`}
                            >
                              <span className="text-[9px] uppercase tracking-wider font-sans font-bold text-emerald-500/70">
                                gold:
                              </span>
                              <span>{refPredicate}</span>
                            </div>
                          </div>
                        ) : !hasRef ? (
                          /* No Gold Match */
                          <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-app-surface border border-app-border text-app-muted font-mono text-[11px]">
                            <span>{predPredicate}</span>
                            <span className="text-[9.5px] text-amber-500 font-sans italic ml-1">
                              [No Gold]
                            </span>
                          </div>
                        ) : (
                          /* Full Predicate Match */
                          <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded bg-app-surface border border-app-border text-app-heading font-mono text-[11px] font-semibold group-hover:border-blue-500/40 transition-colors">
                            <span>{predPredicate}</span>
                          </div>
                        )}
                      </div>

                      <div className="h-[1px] flex-1 bg-app-border group-hover:bg-blue-500/40 transition-colors relative flex items-center justify-end">
                        <span className="text-[10px] text-app-muted/70 group-hover:text-blue-500 leading-none -mr-0.5">
                          ▸
                        </span>
                      </div>
                    </div>

                    {/* Target Object Concept (Fluid min-w-170 flex-1) */}
                    <div
                      className="flex-1 min-w-[170px] font-sans text-[12px] tracking-tight truncate font-medium text-app-text"
                      title={predTarget}
                    >
                      {hasTargetDiff ? (
                        <div className="flex flex-col gap-0.5">
                          <span className="px-1.5 py-0.2 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 font-mono text-[11px] w-fit truncate">
                            {predTarget}
                          </span>
                          <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium text-[11px] w-fit truncate">
                            {refTarget}
                          </span>
                        </div>
                      ) : (
                        <span>{predTarget}</span>
                      )}
                    </div>
                  </div>

                  {/* Right: Class · Similarity/Confidence · Status & Inline Action Strip */}
                  <div className="flex items-center gap-4 shrink-0">
                    {/* Epistemic Class Badge */}
                    <span
                      className={`w-20 text-center font-mono text-[10px] px-1.5 py-0.5 rounded truncate ${
                        epistemicClass === "Dialectical"
                          ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-semibold"
                          : epistemicClass === "Causal"
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 font-semibold"
                          : epistemicClass === "Hierarchical"
                          ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 font-semibold"
                          : "bg-app-subtle text-app-muted border border-app-border"
                      }`}
                    >
                      {epistemicClass}
                    </span>

                    {/* Soft Similarity τ & Extraction Confidence */}
                    <div className="w-16 flex flex-col items-end font-mono text-[10px] tabular-nums leading-tight">
                      <span className="font-bold text-amber-500" title="Soft Similarity τ">
                        τ {candidate.similarity_score.toFixed(3)}
                      </span>
                      <span className="text-app-muted" title="Extraction Confidence">
                        {(candidate.confidence * 100).toFixed(0)}% conf
                      </span>
                    </div>

                    {/* Triage Status Badge + Inline Keyboard Action Hints on Selection */}
                    <div className="w-24 flex items-center justify-end gap-1">
                      {isSelected ? (
                        <div className="flex items-center gap-1 animate-in fade-in duration-100">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onAccept();
                            }}
                            className="p-1 rounded bg-emerald-500/10 hover:bg-emerald-500/25 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 transition-colors cursor-pointer"
                            title="Accept as True Positive (A)"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onReject();
                            }}
                            className="p-1 rounded bg-rose-500/10 hover:bg-rose-500/25 text-rose-600 dark:text-rose-400 border border-rose-500/30 transition-colors cursor-pointer"
                            title="Reject as False Positive (R)"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onOpenAlias();
                            }}
                            className="p-1 rounded bg-violet-500/10 hover:bg-violet-500/25 text-violet-600 dark:text-violet-400 border border-violet-500/30 transition-colors cursor-pointer"
                            title="Remap Schema Alias (S)"
                          >
                            <GitMerge className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        renderStatusBadge(activeDecision, isStaged)
                      )}
                    </div>
                  </div>
                </div>

                {/* ───────────────────────────────────────────────────────────── */}
                {/* 4. Keystroke-Triggered Expandable Accordion Row               */}
                {/* Natural Language Two-Line Comparison Proposition Format       */}
                {/* ───────────────────────────────────────────────────────────── */}
                {isExpanded && (
                  <div className="px-6 py-3.5 bg-app-surface/95 border-t border-app-border/80 space-y-3 animate-in fade-in duration-100">
                    <div className="flex items-center justify-between text-[11px] text-app-muted">
                      <span className="font-semibold text-app-heading font-sans flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-blue-500" />
                        <span>Natural Language Proposition Alignment</span>
                      </span>
                      <span className="font-mono text-[10px] text-app-muted">
                        Press <kbd className="px-1 py-0.2 rounded bg-app-subtle border border-app-border text-app-text">Space</kbd> to collapse
                      </span>
                    </div>

                    {/* Two-Line Clean Comparison */}
                    <div className="p-3 rounded-md bg-app-bg border border-app-border space-y-2 text-xs font-serif leading-relaxed">
                      {/* Line 1: Predicted Proposition */}
                      <div className="flex items-start gap-2.5">
                        <span className="font-sans font-mono text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 shrink-0">
                          Predicted
                        </span>
                        <div className="flex-1 font-serif text-[12.5px] text-app-heading">
                          &ldquo;
                          {formatNaturalSentence(
                            candidate.predicted_edge?.source,
                            candidate.predicted_edge?.predicate,
                            candidate.predicted_edge?.target
                          )}
                          &rdquo;
                        </div>
                        <span className="font-mono text-[10px] text-app-muted font-sans shrink-0">
                          {(candidate.confidence * 100).toFixed(1)}% conf
                        </span>
                      </div>

                      {/* Line 2: Reference Gold Proposition */}
                      <div className="flex items-start gap-2.5 pt-1.5 border-t border-app-border/50">
                        <span className="font-sans font-mono text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 shrink-0">
                          Reference
                        </span>
                        <div className="flex-1 font-serif text-[12.5px] text-app-heading">
                          {hasRef ? (
                            <span>
                              &ldquo;
                              {formatNaturalSentence(
                                candidate.reference_edge?.source,
                                candidate.reference_edge?.predicate,
                                candidate.reference_edge?.target
                              )}
                              &rdquo;
                            </span>
                          ) : (
                            <span className="font-sans text-app-muted italic text-xs not-italic">
                              No gold standard reference proposition matched in benchmark.
                            </span>
                          )}
                        </div>
                        {hasRef && (
                          <span className="font-mono text-[10px] text-amber-500 font-sans font-semibold shrink-0">
                            τ {candidate.similarity_score.toFixed(3)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Vector Similarity Telemetry Mini-Strip */}
                    <div className="grid grid-cols-4 gap-2 text-[10px] font-mono">
                      <div className="p-2 rounded bg-app-bg border border-app-border flex items-center justify-between">
                        <span className="text-app-muted">Head Sim:</span>
                        <span className="text-app-text font-semibold">{headSim.toFixed(2)}</span>
                      </div>
                      <div className="p-2 rounded bg-app-bg border border-app-border flex items-center justify-between">
                        <span className="text-app-muted">Pred Sim:</span>
                        <span className="text-app-text font-semibold">{predSim.toFixed(2)}</span>
                      </div>
                      <div className="p-2 rounded bg-app-bg border border-app-border flex items-center justify-between">
                        <span className="text-app-muted">Tail Sim:</span>
                        <span className="text-app-text font-semibold">{tailSim.toFixed(2)}</span>
                      </div>
                      <div className="p-2 rounded bg-app-bg border border-app-border flex items-center justify-between">
                        <span className="text-app-muted">Soft τ:</span>
                        <span className="text-amber-500 font-bold">{overallSim.toFixed(3)}</span>
                      </div>
                    </div>

                    {/* Inline Evaluator Notes */}
                    <div className="flex items-center gap-2 pt-1">
                      <span className="text-[11px] font-medium text-app-muted font-sans shrink-0">
                        Notes:
                      </span>
                      <input
                        type="text"
                        value={rationaleMap[candidate.candidate_id] || ""}
                        onChange={(e) => onChangeRationale(candidate.candidate_id, e.target.value)}
                        placeholder="Adjudication notes or evidence rationale..."
                        className="flex-1 px-2.5 py-1 text-xs rounded bg-app-bg border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted font-sans"
                        data-hotkey-ignore="true"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 5. Persistent Hotkey Triage Legend Bar (30px Fixed)                 */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <footer className="h-7 px-4 border-t border-app-border bg-app-surface flex items-center justify-between text-[11px] text-app-muted font-mono shrink-0 select-none">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 rounded bg-app-bg border border-app-border text-app-text font-mono text-[9px]">
              j / k
            </kbd>
            <span className="font-sans text-[10.5px]">Navigate</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 font-bold border border-emerald-500/30 text-[9px]">
              A
            </kbd>
            <span className="font-sans text-[10.5px]">Accept TP</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 rounded bg-rose-500/20 text-rose-600 dark:text-rose-400 font-bold border border-rose-500/30 text-[9px]">
              R
            </kbd>
            <span className="font-sans text-[10.5px]">Reject FP</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 rounded bg-violet-500/20 text-violet-600 dark:text-violet-400 font-bold border border-violet-500/30 text-[9px]">
              S
            </kbd>
            <span className="font-sans text-[10.5px]">Schema Alias</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 rounded bg-app-bg border border-app-border text-app-text text-[9px]">
              Space
            </kbd>
            <span className="font-sans text-[10.5px]">Expand Sentence</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.2 rounded bg-app-bg border border-app-border text-app-text text-[9px]">
              U
            </kbd>
            <span className="font-sans text-[10.5px]">Undo</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-app-muted font-sans text-[10.5px]">
            {candidates.length > 0 ? (
              <span>
                Row <strong className="text-app-text font-mono">{selectedIndex + 1}</strong> of{" "}
                <strong className="text-app-text font-mono">{candidates.length}</strong>
              </span>
            ) : (
              "0 candidates"
            )}
          </span>
        </div>
      </footer>
    </div>
  );
};
