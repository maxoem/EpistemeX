import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Sliders,
  CheckCircle2,
  XCircle,
  GitMerge,
  RotateCcw,
  Sparkles,
  Send,
  Loader2,
  BookOpen,
  Quote,
  ShieldCheck,
  FileCode,
  ArrowRight,
  ExternalLink,
} from "lucide-react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import { api } from "../../../../api/client";
import type {
  AdjudicationDecision,
  AdjudicationQueueItem,
  AdjudicationQueueResponse,
} from "../../../../api/types";
import { useAdjudicationStaging } from "./useAdjudicationStaging";
import { useEvaluationHotkeys } from "./useEvaluationHotkeys";
import { AdjudicationQueueList } from "./AdjudicationQueueList";
import { AdjudicationTriadCard } from "./AdjudicationTriadCard";
import { SchemaAliasOmnibar } from "./SchemaAliasOmnibar";

export const AdjudicationDeskView: React.FC = () => {
  const { activeReport } = useEvaluationStore();
  const evaluationId = activeReport?.evaluation_id || "";

  // Data state
  const [queueResponse, setQueueResponse] = useState<AdjudicationQueueResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<"pending" | "adjudicated" | "all">("pending");
  const [minSim, setMinSim] = useState(0.75);
  const [maxSim, setMaxSim] = useState(0.95);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Schema Alias Omnibar state
  const [isAliasModalOpen, setIsAliasModalOpen] = useState(false);
  const [candidateRationale, setCandidateRationale] = useState<Record<string, string>>({});
  const [exportPath, setExportPath] = useState("");

  // Staging hook
  const {
    stagedAdjudications,
    stagedCount,
    optimisticScalarDeltas,
    isCommittingBatch,
    localMessage,
    error,
    stageDecision,
    undoLastDecision,
    commitBatch,
  } = useAdjudicationStaging(evaluationId);

  // Fetch queue items
  const fetchQueue = useCallback(async () => {
    if (!evaluationId) return;
    setIsLoading(true);
    try {
      const data = await api.getAdjudicationQueue(evaluationId, {
        status: filterStatus,
        min_sim: minSim,
        max_sim: maxSim,
      });
      setQueueResponse(data);
    } catch (err) {
      console.error("Failed to fetch adjudication queue:", err);
    } finally {
      setIsLoading(false);
    }
  }, [evaluationId, filterStatus, minSim, maxSim]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  // Filter candidates by search query locally
  const filteredCandidates = useMemo(() => {
    if (!queueResponse?.candidates) return [];
    if (!searchQuery.trim()) return queueResponse.candidates;
    const q = searchQuery.toLowerCase();
    return queueResponse.candidates.filter((c) => {
      const p = c.predicted_edge;
      const src = String(p?.source || "").toLowerCase();
      const pred = String(p?.predicate || "").toLowerCase();
      const tgt = String(p?.target || "").toLowerCase();
      const id = c.candidate_id.toLowerCase();
      return src.includes(q) || pred.includes(q) || tgt.includes(q) || id.includes(q);
    });
  }, [queueResponse?.candidates, searchQuery]);

  // Clamp selected index
  useEffect(() => {
    if (selectedIndex >= filteredCandidates.length) {
      setSelectedIndex(Math.max(0, filteredCandidates.length - 1));
    }
  }, [filteredCandidates.length, selectedIndex]);

  const activeCandidate: AdjudicationQueueItem | null =
    filteredCandidates[selectedIndex] || null;

  const currentStagedItem = activeCandidate
    ? stagedAdjudications.get(activeCandidate.candidate_id) || null
    : null;

  // Navigation handlers
  const handleNext = useCallback(() => {
    setSelectedIndex((prev) => (prev < filteredCandidates.length - 1 ? prev + 1 : prev));
  }, [filteredCandidates.length]);

  const handlePrev = useCallback(() => {
    setSelectedIndex((prev) => (prev > 0 ? prev - 1 : 0));
  }, []);

  // Action handlers
  const handleAccept = useCallback(() => {
    if (!activeCandidate) return;
    const rat = candidateRationale[activeCandidate.candidate_id];
    stageDecision(activeCandidate, "true_positive", null, rat);
    // Auto advance to next candidate for rapid keyboard triage
    handleNext();
  }, [activeCandidate, candidateRationale, stageDecision, handleNext]);

  const handleReject = useCallback(() => {
    if (!activeCandidate) return;
    const rat = candidateRationale[activeCandidate.candidate_id];
    stageDecision(activeCandidate, "false_positive", null, rat);
    handleNext();
  }, [activeCandidate, candidateRationale, stageDecision, handleNext]);

  const handleOpenAlias = useCallback(() => {
    if (!activeCandidate) return;
    setIsAliasModalOpen(true);
  }, [activeCandidate]);

  const handleSelectAliasTarget = useCallback(
    (alias: string) => {
      if (!activeCandidate) return;
      const rat = candidateRationale[activeCandidate.candidate_id];
      stageDecision(activeCandidate, "schema_alias", alias, rat);
      handleNext();
    },
    [activeCandidate, candidateRationale, stageDecision, handleNext]
  );

  const handleCommit = useCallback(async () => {
    if (stagedCount === 0 || isCommittingBatch) return;
    const res = await commitBatch(exportPath ? exportPath : null);
    if (res) {
      // Refresh the queue after commit
      fetchQueue();
    }
  }, [stagedCount, isCommittingBatch, commitBatch, exportPath, fetchQueue]);

  // Wire Hotkeys
  useEvaluationHotkeys({
    onAccept: handleAccept,
    onReject: handleReject,
    onOpenAlias: handleOpenAlias,
    onUndo: undoLastDecision,
    onNext: handleNext,
    onPrev: handlePrev,
    onCommit: handleCommit,
    enabled: !isAliasModalOpen,
  });

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg select-none">
      {/* 44px Contextual Top Toolbar */}
      <div className="h-11 px-4 border-b border-app-border bg-app-surface flex items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-app-heading">
            <Sliders className="w-4 h-4 text-blue-500" />
            <span>HITL Adjudication Desk</span>
          </div>

          <div className="h-4 w-px bg-app-border" />

          {/* Uncertainty Band Slider */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-[11px] text-app-muted">Uncertainty Band τ:</span>
            <span className="font-mono text-xs font-medium text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded">
              [{minSim.toFixed(2)} - {maxSim.toFixed(2)}]
            </span>
          </div>
        </div>

        {/* Center / Right: Staging status & Commit Action */}
        <div className="flex items-center gap-3">
          {/* Optimistic Delta Preview */}
          {stagedCount > 0 && (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 text-xs font-mono tabular-nums">
              <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
              <span>
                {stagedCount} Staged ({optimisticScalarDeltas.f1 >= 0 ? "+" : ""}
                {optimisticScalarDeltas.f1.toFixed(3)} F₁)
              </span>
            </div>
          )}

          {/* Explicit Batch Commit Button */}
          <button
            onClick={handleCommit}
            disabled={stagedCount === 0 || isCommittingBatch}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-all shadow-2xs ${
              stagedCount > 0
                ? "bg-blue-600 hover:bg-blue-700 text-white cursor-pointer ring-2 ring-blue-500/20"
                : "bg-app-subtle text-app-muted border border-app-border cursor-not-allowed opacity-60"
            }`}
            title="Explicitly commit all staged adjudications and recompute metrics (Cmd+Enter)"
          >
            {isCommittingBatch ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
            <span>Commit Batch ({stagedCount})</span>
            <kbd className="hidden sm:inline-block px-1 py-0.2 rounded text-[10px] font-mono bg-black/20">
              ⌘⏎
            </kbd>
          </button>
        </div>
      </div>

      {/* Main 3-Pane Body */}
      <div className="flex-1 flex overflow-hidden">
        {/* Pane 1: Queue List (300px) */}
        <AdjudicationQueueList
          candidates={filteredCandidates}
          selectedIndex={selectedIndex}
          onSelectIndex={setSelectedIndex}
          stagedMap={stagedAdjudications}
          filterStatus={filterStatus}
          onChangeFilterStatus={setFilterStatus}
          searchQuery={searchQuery}
          onChangeSearchQuery={setSearchQuery}
          counts={{
            pending: queueResponse?.pending_count ?? 0,
            adjudicated: queueResponse?.adjudicated_count ?? 0,
            all: queueResponse?.total_candidates ?? 0,
          }}
        />

        {/* Pane 2: Adjudication Triad View (Fluid) */}
        <AdjudicationTriadCard
          candidate={activeCandidate}
          stagedItem={currentStagedItem}
          rationale={activeCandidate ? candidateRationale[activeCandidate.candidate_id] || "" : ""}
          onChangeRationale={(val) => {
            if (activeCandidate) {
              setCandidateRationale((prev) => ({
                ...prev,
                [activeCandidate.candidate_id]: val,
              }));
            }
          }}
          onAccept={handleAccept}
          onReject={handleReject}
          onOpenAlias={handleOpenAlias}
          onUndo={undoLastDecision}
        />

        {/* Pane 3: Evidence & Schema Aliasing Pane (360px) */}
        <aside className="w-[360px] shrink-0 border-l border-app-border bg-app-surface flex flex-col h-full overflow-y-auto p-4 space-y-4 select-none">
          {/* Section 1: Primary Source Text Evidence */}
          <div className="p-3.5 rounded-lg bg-app-bg border border-app-border space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-app-heading">
              <Quote className="w-4 h-4 text-blue-500" />
              <span>Primary Source Evidence</span>
            </div>

            {activeCandidate?.evidence_snippet ? (
              <div className="p-2.5 rounded bg-app-surface border border-app-border/70 text-xs italic text-app-text leading-relaxed font-serif">
                &ldquo;{activeCandidate.evidence_snippet}&rdquo;
              </div>
            ) : (
              <div className="p-3 rounded bg-app-surface border border-dashed border-app-border text-center text-xs text-app-muted font-sans">
                No verbatim text snippet attached for this candidate relation.
              </div>
            )}

            <div className="flex items-center justify-between text-[11px] text-app-muted font-mono pt-1">
              <span>Grounding Quality:</span>
              <span className="text-emerald-500 font-semibold">High Acuity (L1)</span>
            </div>
          </div>

          {/* Section 2: Schema Aliasing Quick Tool */}
          <div className="p-3.5 rounded-lg bg-app-bg border border-app-border space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-app-heading">
                <GitMerge className="w-4 h-4 text-violet-500" />
                <span>Ontology Schema Aliasing</span>
              </div>
              <button
                onClick={handleOpenAlias}
                className="text-[11px] font-mono text-violet-500 hover:text-violet-400 font-medium"
              >
                [S] Omnibar
              </button>
            </div>

            <p className="text-[11px] text-app-muted leading-relaxed">
              If the predicted relation expresses a valid scientific relationship with minor
              vocabulary divergence, map it to a canonical ontology predicate to accept as TP.
            </p>

            {currentStagedItem?.decision === "schema_alias" && currentStagedItem.alias_target ? (
              <div className="p-2.5 rounded bg-violet-500/10 border border-violet-500/30 text-xs font-mono space-y-1">
                <span className="text-[10px] text-app-muted uppercase font-sans block">
                  Active Alias Target:
                </span>
                <span className="font-semibold text-violet-600 dark:text-violet-400 block truncate">
                  {currentStagedItem.alias_target}
                </span>
              </div>
            ) : (
              <button
                onClick={handleOpenAlias}
                className="w-full py-1.5 px-3 rounded-md bg-violet-600/10 hover:bg-violet-600/20 text-violet-600 dark:text-violet-400 border border-violet-500/30 text-xs font-medium transition-colors flex items-center justify-center gap-2"
              >
                <GitMerge className="w-3.5 h-3.5" />
                <span>Map to Canonical Ontology</span>
              </button>
            )}
          </div>

          {/* Section 3: Gold Standard Export Options */}
          <div className="p-3.5 rounded-lg bg-app-bg border border-app-border space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-app-heading">
              <FileCode className="w-4 h-4 text-app-muted" />
              <span>Export Adjudicated Dataset</span>
            </div>

            <p className="text-[11px] text-app-muted leading-relaxed">
              Optionally persist approved edge annotations to an immutable gold standard file for
              future regression testing.
            </p>

            <input
              type="text"
              value={exportPath}
              onChange={(e) => setExportPath(e.target.value)}
              placeholder="e.g. data/gold/adjudicated_v1.json"
              className="w-full px-2.5 py-1.5 text-xs rounded bg-app-surface border border-app-border focus:border-blue-500 focus:outline-hidden text-app-text placeholder-app-muted font-mono"
            />
          </div>

          {/* Section 4: Telemetry & Safety Invariants */}
          <div className="p-3 rounded-lg bg-app-subtle/50 border border-app-border text-[11px] space-y-1.5 text-app-muted">
            <div className="flex items-center gap-1.5 text-app-text font-semibold">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-500" />
              <span>Formal Epistemic Safeguards</span>
            </div>
            <p className="leading-relaxed">
              Adjudications are held in a deterministic client buffer. Pressing [A], [R], or [S]
              applies local previews without sending uncommitted network requests. Explicit commit
              (⌘⏎) triggers server-side recalculation of Poset DAG integrity and Bourbaki coverage.
            </p>
          </div>
        </aside>
      </div>

      {/* Bottom Hotkey Helper Bar (Fixed 32px) */}
      <footer className="h-8 px-4 border-t border-app-border bg-app-surface flex items-center justify-between text-[11px] text-app-muted font-mono shrink-0">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-app-text">
              j
            </kbd>
            <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-app-text">
              k
            </kbd>
            <span>Navigate</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-emerald-500/20 text-emerald-500 font-bold border border-emerald-500/30">
              A
            </kbd>
            <span>True Positive</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-rose-500/20 text-rose-500 font-bold border border-rose-500/30">
              R
            </kbd>
            <span>False Positive</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-violet-500/20 text-violet-500 font-bold border border-violet-500/30">
              S
            </kbd>
            <span>Schema Alias</span>
          </span>
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-app-bg border border-app-border text-app-text">
              U
            </kbd>
            <span>Undo</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          {localMessage && (
            <span className="text-emerald-500 font-sans font-medium animate-pulse">
              {localMessage}
            </span>
          )}
          <span className="flex items-center gap-1">
            <kbd className="px-1 py-0.5 rounded bg-blue-500/20 text-blue-500 font-bold border border-blue-500/30">
              ⌘⏎
            </kbd>
            <span>Commit Batch</span>
          </span>
        </div>
      </footer>

      {/* Schema Alias cmdk Omnibar Modal */}
      <SchemaAliasOmnibar
        isOpen={isAliasModalOpen}
        onClose={() => setIsAliasModalOpen(false)}
        predictedPredicate={String(activeCandidate?.predicted_edge?.predicate || "")}
        referencePredicate={
          activeCandidate?.reference_edge
            ? String(activeCandidate.reference_edge?.predicate || "")
            : null
        }
        onSelectAlias={handleSelectAliasTarget}
      />
    </div>
  );
};
