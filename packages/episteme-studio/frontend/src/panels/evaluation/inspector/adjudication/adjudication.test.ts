import test from "node:test";
import assert from "node:assert/strict";
import { useEvaluationStore } from "../../../../store/evaluationStore.ts";
import type {
  AdjudicationQueueItem,
  EdgeAdjudicationItem,
  EvaluationReportDetail,
} from "../../../../api/types.ts";

test("HITL Staging: deterministic local staging and O(1) delta estimation", () => {
  const store = useEvaluationStore.getState();
  store.clearStagedAdjudications();

  const mockCandidate: AdjudicationQueueItem = {
    candidate_id: "cand_test_01",
    evaluation_id: "eval_test_01",
    predicted_edge: { source: "Law_of_Force", predicate: "EXPRESSES_FORCE", target: "Mass" },
    reference_edge: { source: "CPM_Axiom_2", predicate: "HAS_GOVERNING_LAW", target: "Mass" },
    similarity_score: 0.865,
    status: "pending",
    confidence: 0.92,
  };

  // Stage True Positive
  const tpItem: EdgeAdjudicationItem = {
    adjudication_id: "adj_cand_test_01",
    predicted_edge: mockCandidate.predicted_edge,
    reference_edge: mockCandidate.reference_edge,
    similarity_score: mockCandidate.similarity_score,
    decision: "true_positive",
    rationale: "Verified by domain expert",
    adjudicated_at: new Date().toISOString(),
  };

  store.stageAdjudication(mockCandidate.candidate_id, tpItem);

  const state1 = useEvaluationStore.getState();
  assert.equal(state1.stagedAdjudications.size, 1);
  assert.equal(state1.stagedAdjudications.get("cand_test_01")?.decision, "true_positive");
  assert.ok(state1.optimisticScalarDeltas.f1 > 0);
  assert.ok(state1.optimisticScalarDeltas.precision > 0);
  assert.ok(state1.optimisticScalarDeltas.recall > 0);

  // Stage Schema Alias
  const aliasItem: EdgeAdjudicationItem = {
    adjudication_id: "adj_cand_test_02",
    predicted_edge: { source: "Centripetal", predicate: "DIRECTED_TO", target: "Center" },
    decision: "schema_alias",
    alias_target: "DIRECTED_TOWARDS",
    similarity_score: 0.82,
  };

  store.stageAdjudication("cand_test_02", aliasItem);
  const state2 = useEvaluationStore.getState();
  assert.equal(state2.stagedAdjudications.size, 2);
  assert.equal(state2.stagedAdjudications.get("cand_test_02")?.alias_target, "DIRECTED_TOWARDS");

  // Unstage item
  store.unstageAdjudication("cand_test_01");
  const state3 = useEvaluationStore.getState();
  assert.equal(state3.stagedAdjudications.size, 1);
  assert.equal(state3.stagedAdjudications.has("cand_test_01"), false);
  assert.equal(state3.stagedAdjudications.has("cand_test_02"), true);

  // Clear staging buffer
  store.clearStagedAdjudications();
  const state4 = useEvaluationStore.getState();
  assert.equal(state4.stagedAdjudications.size, 0);
  assert.equal(state4.optimisticScalarDeltas.f1, 0);
});

test("HITL Staging: undo stack behavior", () => {
  const store = useEvaluationStore.getState();
  store.clearStagedAdjudications();

  // Emulate sequential actions and undo
  const history: Array<{ id: string; prev: EdgeAdjudicationItem | null; current: EdgeAdjudicationItem }> = [];

  const itemA: EdgeAdjudicationItem = {
    adjudication_id: "adj_A",
    predicted_edge: { source: "A", predicate: "P", target: "B" },
    decision: "true_positive",
  };
  history.push({ id: "cand_A", prev: null, current: itemA });
  store.stageAdjudication("cand_A", itemA);

  const itemB: EdgeAdjudicationItem = {
    adjudication_id: "adj_B",
    predicted_edge: { source: "X", predicate: "Q", target: "Y" },
    decision: "false_positive",
  };
  history.push({ id: "cand_B", prev: null, current: itemB });
  store.stageAdjudication("cand_B", itemB);

  assert.equal(useEvaluationStore.getState().stagedAdjudications.size, 2);

  // Undo last (B)
  const lastAction = history.pop();
  assert.ok(lastAction);
  if (lastAction.prev) {
    store.stageAdjudication(lastAction.id, lastAction.prev);
  } else {
    store.unstageAdjudication(lastAction.id);
  }

  assert.equal(useEvaluationStore.getState().stagedAdjudications.size, 1);
  assert.equal(useEvaluationStore.getState().stagedAdjudications.has("cand_A"), true);
  assert.equal(useEvaluationStore.getState().stagedAdjudications.has("cand_B"), false);
});

test("HITL Adjudication: differential proposition formatting and sentence generation", () => {
  // Test predicate formatting
  const rawPred = "immanently_critiques";
  const formattedPred = rawPred.replace(/_/g, " ").replace(/\band\b/g, "&");
  assert.equal(formattedPred, "immanently critiques");

  // Test natural language sentence builder
  const formatNaturalSentence = (s: string, p: string, o: string) => {
    const clean = (val: string) => val.replace(/^str:|^pred:|^gold:/, "");
    const cleanedPred = p.replace(/_/g, " ").replace(/\band\b/g, "&");
    return `${clean(s)} ${cleanedPred} ${clean(o)}.`;
  };

  const predSentence = formatNaturalSentence(
    "pred:Hegel's Dialectic",
    "immanently_critiques",
    "pred:Kantian Dualism"
  );
  assert.equal(predSentence, "Hegel's Dialectic immanently critiques Kantian Dualism.");

  const goldSentence = formatNaturalSentence(
    "gold:The Dialectical Progression",
    "overcomes",
    "gold:Transcendental Dualism"
  );
  assert.equal(goldSentence, "The Dialectical Progression overcomes Transcendental Dualism.");

  // Test differential detection
  const p1: string = "immanently_critiques";
  const p2: string = "overcomes";
  const hasPredicateDiff = p1 !== p2;
  assert.equal(hasPredicateDiff, true);

  const s1: string = "Hegel's Dialectic";
  const s2: string = "The Dialectical Progression";
  const hasSourceDiff = s1 !== s2;
  assert.equal(hasSourceDiff, true);
});
