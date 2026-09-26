import test from "node:test";
import assert from "node:assert/strict";
import { useEvaluationStore } from "./evaluationStore.ts";
import type { EdgeAdjudicationItem, EvaluationReportDetail } from "../api/types.ts";

test("evaluationStore: initial state adheres to Phase 0 contracts", () => {
  const store = useEvaluationStore.getState();
  store.resetStore();

  const state = useEvaluationStore.getState();
  assert.equal(state.activeMode, "inspector");
  assert.equal(state.activeSubTab, "canvas");
  assert.equal(state.activeReport, null);
  assert.equal(state.activeReportId, null);
  assert.equal(state.stagedAdjudications.size, 0);
  assert.deepEqual(state.optimisticScalarDeltas, { f1: 0, precision: 0, recall: 0 });
  assert.equal(state.isCommittingBatch, false);
});

test("evaluationStore: navigation and sub-tab state updates", () => {
  const store = useEvaluationStore.getState();
  store.setActiveMode("catalog");
  assert.equal(useEvaluationStore.getState().activeMode, "catalog");

  store.setActiveSubTab("adjudication");
  assert.equal(useEvaluationStore.getState().activeSubTab, "adjudication");

  const mockReport: EvaluationReportDetail = {
    evaluation_id: "eval-001",
    run_ids: ["run-001"],
    dataset_ref: "gold-standard-1928",
    dataset_type: "gold",
    outcome: "pass",
    created_at: new Date().toISOString(),
    key_metrics: { f1: 0.92, delta_star: 0.95, ece: 0.03, mrr: 0.88 },
    has_markdown: true,
    has_baseline: false,
    results_by_level: {},
    model_decomposition: [],
    comparative_deltas: [],
    summary_markdown: "# Summary",
    omitted_components: [],
    violations: [],
  };

  store.setActiveReport(mockReport);
  assert.equal(useEvaluationStore.getState().activeReportId, "eval-001");
  assert.deepEqual(useEvaluationStore.getState().activeReport, mockReport);
});

test("evaluationStore: HITL staging buffer stages, unstages, and tracks optimistic deltas", () => {
  const store = useEvaluationStore.getState();
  store.clearStagedAdjudications();

  const item1: EdgeAdjudicationItem = {
    adjudication_id: "adj-1",
    predicted_edge: { source: "A", predicate: "SUPPORTS", target: "B" },
    decision: "true_positive",
    similarity_score: 0.91,
  };

  store.stageAdjudication("cand-1", item1);
  const stateAfter1 = useEvaluationStore.getState();
  assert.equal(stateAfter1.stagedAdjudications.size, 1);
  assert.equal(stateAfter1.stagedAdjudications.get("cand-1")?.decision, "true_positive");
  assert.ok(stateAfter1.optimisticScalarDeltas.f1 > 0);

  const item2: EdgeAdjudicationItem = {
    adjudication_id: "adj-2",
    predicted_edge: { source: "X", predicate: "ATTACKS", target: "Y" },
    decision: "false_positive",
    similarity_score: 0.42,
  };

  store.stageAdjudication("cand-2", item2);
  const stateAfter2 = useEvaluationStore.getState();
  assert.equal(stateAfter2.stagedAdjudications.size, 2);

  store.unstageAdjudication("cand-1");
  const stateAfterUnstage = useEvaluationStore.getState();
  assert.equal(stateAfterUnstage.stagedAdjudications.size, 1);
  assert.equal(stateAfterUnstage.stagedAdjudications.has("cand-1"), false);
  assert.equal(stateAfterUnstage.stagedAdjudications.has("cand-2"), true);

  store.clearStagedAdjudications();
  const stateAfterClear = useEvaluationStore.getState();
  assert.equal(stateAfterClear.stagedAdjudications.size, 0);
  assert.deepEqual(stateAfterClear.optimisticScalarDeltas, { f1: 0, precision: 0, recall: 0 });
});

test("evaluationStore: Phase 2 graph overlay, filters, opacity, and selection state updates", () => {
  const store = useEvaluationStore.getState();
  store.resetStore();

  // Test alignment filter toggles
  assert.equal(useEvaluationStore.getState().alignmentFilters.fn, true);
  store.toggleAlignmentFilter("fn");
  assert.equal(useEvaluationStore.getState().alignmentFilters.fn, false);
  store.toggleAlignmentFilter("fn");
  assert.equal(useEvaluationStore.getState().alignmentFilters.fn, true);

  // Test ghost opacity clamping
  store.setGhostOpacity(0.65);
  assert.equal(useEvaluationStore.getState().ghostOpacity, 0.65);
  store.setGhostOpacity(2.0); // should clamp to 1.0
  assert.equal(useEvaluationStore.getState().ghostOpacity, 1.0);
  store.setGhostOpacity(-0.5); // should clamp to 0.1
  assert.equal(useEvaluationStore.getState().ghostOpacity, 0.1);

  // Test selected overlay item
  const sampleNode = {
    id: "str:CPM_Axiom_1_Inertia",
    label: "Law of Inertia",
    class_name: "actual_models",
    symbol: "M",
    alignment_status: "true_positive" as const,
    similarity_score: 1.0,
    is_ghost: false,
  };
  store.setSelectedOverlayItem({ type: "node", item: sampleNode });
  assert.deepEqual(useEvaluationStore.getState().selectedOverlayItem, {
    type: "node",
    item: sampleNode,
  });

  store.setSelectedOverlayItem(null);
  assert.equal(useEvaluationStore.getState().selectedOverlayItem, null);

  // Test Bourbaki hull and class filters
  assert.equal(useEvaluationStore.getState().bourbakiHullEnabled, false);
  store.setBourbakiHullEnabled(true);
  assert.equal(useEvaluationStore.getState().bourbakiHullEnabled, true);

  assert.equal(useEvaluationStore.getState().selectedBourbakiClasses.has("Mp"), true);
  store.toggleBourbakiClass("Mp");
  assert.equal(useEvaluationStore.getState().selectedBourbakiClasses.has("Mp"), false);

  // Test ambiguous drawer toggle and cycle isolation
  store.setIsAmbiguousDrawerOpen(true);
  assert.equal(useEvaluationStore.getState().isAmbiguousDrawerOpen, true);

  store.setCycleHighlightNodeIds(["node-a", "node-b", "node-a"]);
  assert.deepEqual(useEvaluationStore.getState().cycleHighlightNodeIds, [
    "node-a",
    "node-b",
    "node-a",
  ]);
  store.setCycleHighlightNodeIds(null);
  assert.equal(useEvaluationStore.getState().cycleHighlightNodeIds, null);
});
