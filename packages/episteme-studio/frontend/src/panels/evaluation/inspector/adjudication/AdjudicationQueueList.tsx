import React, { useMemo } from "react";
import {
  CheckCircle2,
  XCircle,
  GitMerge,
  Clock,
  ArrowRight,
  Search,
  Filter,
} from "lucide-react";
import type {
  AdjudicationDecision,
  AdjudicationQueueItem,
  EdgeAdjudicationItem,
} from "../../../../api/types";

export interface AdjudicationQueueListProps {
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
}

export const AdjudicationQueueList: React.FC<AdjudicationQueueListProps> = ({
  candidates,
  selectedIndex,
  onSelectIndex,
  stagedMap,
  filterStatus,
  onChangeFilterStatus,
  searchQuery,
  onChangeSearchQuery,
  counts,
}) => {
  const getDecisionBadge = (decision: AdjudicationDecision | null | undefined, isStaged: boolean) => {
    if (!decision) return null;

    if (decision === "true_positive") {
      return (
        <span
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
            isStaged
              ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
              : "bg-emerald-500/10 text-emerald-500"
          }`}
        >
          <CheckCircle2 className="w-2.5 h-2.5" />
          <span>{isStaged ? "TP [Staged]" : "TP"}</span>
        </span>
      );
    }
    if (decision === "false_positive") {
      return (
        <span
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
            isStaged
              ? "bg-rose-500/15 text-rose-600 dark:text-rose-400 border border-rose-500/30"
              : "bg-rose-500/10 text-rose-500"
          }`}
        >
          <XCircle className="w-2.5 h-2.5" />
          <span>{isStaged ? "FP [Staged]" : "FP"}</span>
        </span>
      );
    }
    if (decision === "schema_alias") {
      return (
        <span
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium ${
            isStaged
              ? "bg-violet-500/15 text-violet-600 dark:text-violet-400 border border-violet-500/30"
              : "bg-violet-500/10 text-violet-500"
          }`}
        >
          <GitMerge className="w-2.5 h-2.5" />
          <span>{isStaged ? "Alias [Staged]" : "Alias"}</span>
        </span>
      );
    }
    return null;
  };

  return (
    <aside className="w-[300px] shrink-0 border-r border-app-border bg-app-surface/60 flex flex-col h-full overflow-hidden select-none">
      {/* Search & Filter Header */}
      <div className="p-2.5 border-b border-app-border space-y-2 bg-app-surface">
        {/* Status Filters */}
        <div className="grid grid-cols-3 gap-1 p-0.5 rounded-lg bg-app-bg border border-app-border text-[11px] font-medium text-center">
          <button
            onClick={() => onChangeFilterStatus("pending")}
            className={`py-1 rounded-md transition-colors cursor-pointer ${
              filterStatus === "pending"
                ? "bg-app-surface text-app-text font-semibold border border-app-border/80"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
            }`}
          >
            Pending ({counts.pending})
          </button>
          <button
            onClick={() => onChangeFilterStatus("adjudicated")}
            className={`py-1 rounded-md transition-colors cursor-pointer ${
              filterStatus === "adjudicated"
                ? "bg-app-surface text-app-text font-semibold border border-app-border/80"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
            }`}
          >
            Adjudicated ({counts.adjudicated})
          </button>
          <button
            onClick={() => onChangeFilterStatus("all")}
            className={`py-1 rounded-md transition-colors cursor-pointer ${
              filterStatus === "all"
                ? "bg-app-surface text-app-text font-semibold border border-app-border/80"
                : "text-app-muted hover:text-app-text hover:bg-app-subtle/50"
            }`}
          >
            All ({counts.all})
          </button>
        </div>

        {/* Search Input */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-app-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onChangeSearchQuery(e.target.value)}
            placeholder="Search candidate edges..."
            className="w-full pl-8 pr-2.5 py-1 text-xs rounded-md bg-app-bg border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted font-sans"
          />
        </div>
      </div>

      {/* Candidate Items List */}
      <div className="flex-1 overflow-y-auto divide-y divide-app-border/40">
        {candidates.length === 0 ? (
          <div className="p-6 text-center text-app-muted text-xs flex flex-col items-center justify-center h-48">
            <Filter className="w-8 h-8 opacity-30 mb-2" />
            <p className="font-medium text-app-text">No Candidates Found</p>
            <p className="text-[11px] text-app-muted mt-0.5">
              Try adjusting the filter status or similarity range.
            </p>
          </div>
        ) : (
          candidates.map((candidate, idx) => {
            const isSelected = idx === selectedIndex;
            const staged = stagedMap.get(candidate.candidate_id);
            const activeDecision = staged?.decision ?? candidate.current_decision;
            const isStaged = Boolean(staged);

            const predSource = String(candidate.predicted_edge?.source || "").replace(/^str:|^pred:/, "");
            const predPred = String(candidate.predicted_edge?.predicate || "");
            const predTarget = String(candidate.predicted_edge?.target || "").replace(/^str:|^pred:/, "");

            return (
              <div
                key={candidate.candidate_id}
                onClick={() => onSelectIndex(idx)}
                className={`p-2.5 cursor-pointer transition-colors relative border-l-2 text-xs ${
                  isSelected
                    ? "bg-app-subtle border-blue-600 text-app-heading font-medium"
                    : "border-transparent hover:bg-app-subtle/70 text-app-muted hover:text-app-text"
                }`}
              >
                {/* Row 1: ID, Sim Badge & Staged/Decision Status */}
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="font-mono text-[10px] text-app-muted truncate">
                    {candidate.candidate_id}
                  </span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span
                      className="px-1.5 py-0.2 rounded text-[10px] font-mono tabular-nums font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/25"
                      title="Semantic similarity τ"
                    >
                      τ: {candidate.similarity_score.toFixed(3)}
                    </span>
                    {getDecisionBadge(activeDecision, isStaged)}
                  </div>
                </div>

                {/* Row 2: Triple Representation */}
                <div className="space-y-0.5 font-mono text-[11px] leading-tight">
                  <div className="text-app-text font-medium truncate">{predSource}</div>
                  <div className={`font-semibold truncate flex items-center gap-1 pl-1 ${
                    /undermine|attack|refute|disprove|oppose/i.test(predPred)
                      ? "text-rose-600 dark:text-rose-400"
                      : /validate|support|prove|corroborat|entail/i.test(predPred)
                      ? "text-blue-600 dark:text-blue-400"
                      : "text-app-text font-medium"
                  }`}>
                    <ArrowRight className="w-2.5 h-2.5 shrink-0 opacity-60" />
                    <span>{predPred}</span>
                  </div>
                  <div className="text-app-muted truncate pl-2">{predTarget}</div>
                </div>

                {/* Staged Alias Target indicator */}
                {activeDecision === "schema_alias" && (staged?.alias_target || candidate.alias_target) && (
                  <div className="mt-1 text-[10px] font-mono text-violet-500 flex items-center gap-1 truncate">
                    <GitMerge className="w-2.5 h-2.5 shrink-0" />
                    <span>Alias: {staged?.alias_target || candidate.alias_target}</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer Navigation Note */}
      <div className="p-2 border-t border-app-border bg-app-surface text-[10px] text-app-muted font-mono flex items-center justify-between">
        <span>[j] / [k] navigate</span>
        <span className="tabular-nums">
          {candidates.length > 0 ? `${selectedIndex + 1} of ${candidates.length}` : "0"}
        </span>
      </div>
    </aside>
  );
};
