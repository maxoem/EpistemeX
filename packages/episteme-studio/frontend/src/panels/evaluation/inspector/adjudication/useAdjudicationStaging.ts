import { useState, useCallback, useRef } from "react";
import { useEvaluationStore } from "../../../../store/evaluationStore";
import type {
  AdjudicateAndRecalculateResponse,
  AdjudicationDecision,
  AdjudicationQueueItem,
  EdgeAdjudicationItem,
} from "../../../../api/types";

export interface StagingActionHistoryItem {
  candidateId: string;
  previousDecision: EdgeAdjudicationItem | null;
  newDecision: EdgeAdjudicationItem;
}

export function useAdjudicationStaging(evaluationId: string) {
  const {
    stagedAdjudications,
    stageAdjudication,
    unstageAdjudication,
    clearStagedAdjudications,
    optimisticScalarDeltas,
    commitStagedAdjudications,
    isCommittingBatch,
    error: storeError,
  } = useEvaluationStore();

  const undoStackRef = useRef<StagingActionHistoryItem[]>([]);
  const [localMessage, setLocalMessage] = useState<string | null>(null);

  /**
   * Stage an adjudication decision locally without debounced network RPC.
   * Immediately re-computes an O(1) optimistic delta.
   */
  const stageDecision = useCallback(
    (
      candidate: AdjudicationQueueItem,
      decision: AdjudicationDecision,
      aliasTarget?: string | null,
      rationale?: string | null
    ) => {
      const candidateId = candidate.candidate_id;
      const prevDecision = stagedAdjudications.get(candidateId) || null;

      const item: EdgeAdjudicationItem = {
        adjudication_id: `adj_${candidateId}`,
        predicted_edge: candidate.predicted_edge,
        reference_edge: candidate.reference_edge,
        similarity_score: candidate.similarity_score,
        decision,
        alias_target: aliasTarget ?? null,
        rationale: rationale ?? (decision === "schema_alias" ? `Mapped alias: ${aliasTarget}` : undefined),
        adjudicated_at: new Date().toISOString(),
      };

      // Record in undo stack
      undoStackRef.current.push({
        candidateId,
        previousDecision: prevDecision,
        newDecision: item,
      });

      stageAdjudication(candidateId, item);
      setLocalMessage(
        decision === "true_positive"
          ? "Staged as True Positive (TP)"
          : decision === "false_positive"
          ? "Staged as False Positive (FP)"
          : `Staged as Schema Alias (${aliasTarget || "Mapped"})`
      );
    },
    [stagedAdjudications, stageAdjudication]
  );

  /**
   * Revert the most recently staged adjudication decision.
   */
  const undoLastDecision = useCallback(() => {
    const lastAction = undoStackRef.current.pop();
    if (!lastAction) {
      setLocalMessage("No staged actions to undo");
      return;
    }

    if (lastAction.previousDecision) {
      stageAdjudication(lastAction.candidateId, lastAction.previousDecision);
      setLocalMessage(`Reverted to previous staged state`);
    } else {
      unstageAdjudication(lastAction.candidateId);
      setLocalMessage(`Removed staged decision for candidate`);
    }
  }, [stageAdjudication, unstageAdjudication]);

  /**
   * Explicitly commit all staged adjudications to the backend.
   * Calls POST /reports/{id}/adjudicate-and-recalculate.
   */
  const commitBatch = useCallback(
    async (exportDatasetPath?: string | null): Promise<AdjudicateAndRecalculateResponse | null> => {
      if (stagedAdjudications.size === 0) return null;

      const res = await commitStagedAdjudications(evaluationId, exportDatasetPath);
      if (res) {
        undoStackRef.current = [];
        setLocalMessage(`Successfully committed ${res.adjudicated_count} decisions!`);
      }
      return res;
    },
    [evaluationId, stagedAdjudications.size, commitStagedAdjudications]
  );

  return {
    stagedAdjudications,
    stagedCount: stagedAdjudications.size,
    optimisticScalarDeltas,
    isCommittingBatch,
    localMessage,
    error: storeError,
    stageDecision,
    undoLastDecision,
    commitBatch,
    clearStagedAdjudications,
  };
}
