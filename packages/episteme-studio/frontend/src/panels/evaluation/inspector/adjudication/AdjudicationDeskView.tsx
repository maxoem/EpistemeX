import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import { api } from "../../../../api/client";
import type {
  AdjudicationQueueItem,
  AdjudicationQueueResponse,
} from "../../../../api/types";
import { useAdjudicationStaging } from "./useAdjudicationStaging";
import { useEvaluationHotkeys } from "./useEvaluationHotkeys";
import { AdjudicationTableView } from "./AdjudicationTableView";
import { AdjudicationInspectorRail } from "./AdjudicationInspectorRail";
import { SchemaAliasOmnibar } from "./SchemaAliasOmnibar";
import { ResizablePanel } from "../../../ResizablePanel";

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
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  // Schema Alias Omnibar state & Export settings
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

  // Toggle row accordion expansion (keystroke-triggered or click)
  const handleToggleExpand = useCallback(() => {
    if (!activeCandidate) return;
    setExpandedRowId((prev) =>
      prev === activeCandidate.candidate_id ? null : activeCandidate.candidate_id
    );
  }, [activeCandidate]);

  const handleToggleExpandRow = useCallback((id: string) => {
    setExpandedRowId((prev) => (prev === id ? null : id));
  }, []);

  // Action handlers (with automatic advance to the next candidate edge)
  const handleAccept = useCallback(() => {
    if (!activeCandidate) return;
    const rat = candidateRationale[activeCandidate.candidate_id];
    stageDecision(activeCandidate, "true_positive", null, rat);
    // Auto advance focus to the next candidate edge for rapid keyboard triage
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
      fetchQueue();
    }
  }, [stagedCount, isCommittingBatch, commitBatch, exportPath, fetchQueue]);

  // Wire Hotkeys: [A], [R], [S], [U], [j], [k], [Space], [⌘⏎]
  useEvaluationHotkeys({
    onAccept: handleAccept,
    onReject: handleReject,
    onOpenAlias: handleOpenAlias,
    onUndo: undoLastDecision,
    onNext: handleNext,
    onPrev: handlePrev,
    onCommit: handleCommit,
    onToggleExpand: handleToggleExpand,
    enabled: !isAliasModalOpen,
  });

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-app-bg select-none">
      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* Main Horizontally Integrated Workspace (2-Column Architecture)     */}
      {/* Pane 1: Continuous Proposition Table with Consolidated Action Bar   */}
      {/* Pane 2: Cursor Draggable Resizable Right Diagnostic Inspector       */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">
        {/* Pane 1: Center Fluid Adjudication Table with Integrated Header Toolbar */}
        <AdjudicationTableView
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
          minSim={minSim}
          maxSim={maxSim}
          rationaleMap={candidateRationale}
          onChangeRationale={(id, val) =>
            setCandidateRationale((prev) => ({ ...prev, [id]: val }))
          }
          onAccept={handleAccept}
          onReject={handleReject}
          onOpenAlias={handleOpenAlias}
          onUndo={undoLastDecision}
          expandedRowId={expandedRowId}
          onToggleExpandRow={handleToggleExpandRow}
          stagedCount={stagedCount}
          optimisticF1Delta={optimisticScalarDeltas.f1}
          isCommittingBatch={isCommittingBatch}
          onCommitBatch={handleCommit}
          onRefresh={fetchQueue}
          isLoading={isLoading}
          localMessage={localMessage}
        />

        {/* Pane 2: Draggable Resizable Right Diagnostic Inspector Rail */}
        <ResizablePanel
          side="right"
          storageKey="episteme-adjudication-inspector-width"
          defaultWidth={420}
          minWidth={320}
          maxWidth={850}
          collapsible={false}
          className="h-full !bg-app-surface"
        >
          <AdjudicationInspectorRail
            candidate={activeCandidate}
            stagedItem={currentStagedItem}
            onOpenAlias={handleOpenAlias}
            exportPath={exportPath}
            onChangeExportPath={setExportPath}
            stagedCount={stagedCount}
          />
        </ResizablePanel>
      </div>

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
