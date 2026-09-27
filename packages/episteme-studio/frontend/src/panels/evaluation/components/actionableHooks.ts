import { useNavigationStore } from "../../../store/navigationStore.ts";
import { useEngineSettingsStore } from "../../../store/engineSettingsStore.ts";
import { useEvaluationStore } from "../../../store/evaluationStore.ts";

export type EpistemicHookType =
  | "schema_drift"
  | "argument_polarity"
  | "overconfidence"
  | "dag_cycle";

/**
 * Routes to EngineSettingsPage to map an unmapped predicate or alias.
 */
export function openPredicateInEngine(predicate: string): void {
  useEngineSettingsStore.getState().setActiveCategory("unmapped");
  useEngineSettingsStore.getState().setUnmappedSubTab("discovered");
  useEngineSettingsStore.getState().setSelectedUnmapped(new Set([predicate]));
  useNavigationStore.getState().setActiveTab("engine");
}

/**
 * Routes to EngineSettingsPage to inspect or adjust dialectical criteria for an argument relation.
 */
export function openArgRelationInEngine(relationId: string): void {
  useEngineSettingsStore.getState().setActiveCategory("ontology");
  useEngineSettingsStore.getState().setOntologySubTab("arg_relations");
  useEngineSettingsStore.getState().setSelectedItem({
    type: "arg_relation",
    id: relationId,
  });
  useNavigationStore.getState().setActiveTab("engine");
}

/**
 * Routes to ConfigEditor pre-loading the offending text in the phase prompt tester.
 */
export function openPhasePromptInExecution(params: {
  phaseKey?: string;
  promptKey?: string;
  sourceText?: string;
  assertionId?: string;
}): void {
  useNavigationStore.getState().setPromptTuningTarget({
    phaseKey: params.phaseKey || "phase2",
    promptKey: params.promptKey || "entity_extraction",
    sourceText: params.sourceText,
    assertionId: params.assertionId,
  });
  useNavigationStore.getState().setActiveTab("config");
}

/**
 * Switches to Sub-View 3.1 and isolates cycle node IDs on the G6 canvas.
 */
export function isolateCycleInCanvas(cycleNodes: string[]): void {
  const uniqueNodes = Array.from(new Set(cycleNodes));
  useEvaluationStore.getState().setCycleHighlightNodeIds(uniqueNodes);
  useEvaluationStore.getState().setActiveSubTab("canvas");
}
