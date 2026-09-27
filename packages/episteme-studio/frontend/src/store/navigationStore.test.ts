import test from "node:test";
import assert from "node:assert/strict";
import { useNavigationStore } from "./navigationStore.ts";
import { useEngineSettingsStore } from "./engineSettingsStore.ts";
import { useEvaluationStore } from "./evaluationStore.ts";
import {
  openPredicateInEngine,
  openArgRelationInEngine,
  openPhasePromptInExecution,
  isolateCycleInCanvas,
} from "../panels/evaluation/components/actionableHooks.ts";

test("navigationStore: manages global workspace activeTab and promptTuningTarget", () => {
  const store = useNavigationStore.getState();
  store.resetNavigation();

  assert.equal(useNavigationStore.getState().activeTab, "runs");
  assert.equal(useNavigationStore.getState().promptTuningTarget, null);

  store.setActiveTab("evaluation");
  assert.equal(useNavigationStore.getState().activeTab, "evaluation");

  store.setPromptTuningTarget({
    phaseKey: "phase2",
    promptKey: "entity_extraction",
    sourceText: "Test source paragraph",
  });
  assert.deepEqual(useNavigationStore.getState().promptTuningTarget, {
    phaseKey: "phase2",
    promptKey: "entity_extraction",
    sourceText: "Test source paragraph",
  });
});

test("ActionableHookPill: openPredicateInEngine dispatches category unmapped and navigates to engine", () => {
  useNavigationStore.getState().setActiveTab("evaluation");

  openPredicateInEngine("has_constituent_part");

  assert.equal(useNavigationStore.getState().activeTab, "engine");
  assert.equal(useEngineSettingsStore.getState().activeCategory, "unmapped");
  assert.equal(useEngineSettingsStore.getState().unmappedSubTab, "discovered");
  assert.ok(useEngineSettingsStore.getState().selectedUnmapped.has("has_constituent_part"));
});

test("ActionableHookPill: openArgRelationInEngine dispatches ontology arg_relations and navigates to engine", () => {
  useNavigationStore.getState().setActiveTab("evaluation");

  openArgRelationInEngine("SUPPORTS");

  assert.equal(useNavigationStore.getState().activeTab, "engine");
  assert.equal(useEngineSettingsStore.getState().activeCategory, "ontology");
  assert.equal(useEngineSettingsStore.getState().ontologySubTab, "arg_relations");
  assert.deepEqual(useEngineSettingsStore.getState().selectedItem, {
    type: "arg_relation",
    id: "SUPPORTS",
  });
});

test("ActionableHookPill: openPhasePromptInExecution stages prompt tuning target and navigates to config", () => {
  useNavigationStore.getState().setActiveTab("evaluation");

  openPhasePromptInExecution({
    phaseKey: "phase3",
    promptKey: "relation_extraction",
    sourceText: "Phenomenal state grounding text",
    assertionId: "triple_0492",
  });

  assert.equal(useNavigationStore.getState().activeTab, "config");
  assert.deepEqual(useNavigationStore.getState().promptTuningTarget, {
    phaseKey: "phase3",
    promptKey: "relation_extraction",
    sourceText: "Phenomenal state grounding text",
    assertionId: "triple_0492",
  });
});

test("ActionableHookPill: isolateCycleInCanvas sets cycle node IDs and switches to canvas", () => {
  useEvaluationStore.getState().setActiveSubTab("epistemics");
  useEvaluationStore.getState().setCycleHighlightNodeIds(null);

  isolateCycleInCanvas(["Hyp_04", "Lem_12", "Ax_01", "Hyp_04"]);

  assert.equal(useEvaluationStore.getState().activeSubTab, "canvas");
  assert.deepEqual(useEvaluationStore.getState().cycleHighlightNodeIds, [
    "Hyp_04",
    "Lem_12",
    "Ax_01",
  ]);
});
