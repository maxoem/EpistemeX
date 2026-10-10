import test from "node:test";
import assert from "node:assert/strict";
import {
    extractPromptVariables,
    getAvailablePhaseTabs,
    resolvePhaseConfig,
    resolvePhaseKey,
} from "./phaseConfigResolver.ts";

const SAMPLE_CONFIG_SNAPSHOT = {
  phase1: {
    chunk_size: 1024,
    chunk_overlap: 128,
    provenance_enabled: true,
  },
  phase2: {
    top_k_linking_candidates: 10,
    linking_confidence_threshold: 0.85,
    ner_confidence_threshold: 0.0,
    local_relation_confidence_threshold: 0.0,
    batch_size: 10,
    ner_prompts: {
      direct_template: "You are an expert. Extract entities from:\n{chunk_text}\nLabels: {entity_types}",
      reasoning_template: null,
      format_template: null,
      gleaning_template: null,
    },
    ner_decoding_strategy: "nl_to_format",
    entity_linking_prompt_template: "Linking mention {mention_a_text} to {candidate_name} in {mention_a_context}",
    max_gleanings: 2,
  },
  phase3: {
    global_relation_confidence_threshold: 0.7,
    max_candidates_per_entity_pair: 200,
    subgraph_depth: 2,
    global_relation_prompts: {
      direct_template: "Analyze relation between {entity_a_name} and {entity_b_name} with envelope {subgraph_envelope}",
      reasoning_template: "Step by step reasoning for {entity_a_id} and {entity_b_id}",
      format_template: "Extract {relation_types} from {reasoning_text}",
      gleaning_template: null,
    },
    global_relation_decoding_strategy: "nl_to_format",
    dense_similarity_threshold: 0.8,
    reranker_threshold: 0.6,
    trace_dense_retrieval: true,
  },
  phase3b: {
    enabled: true,
    dense_similarity_threshold: 0.8,
    relation_overlap_threshold: 0.8,
  },
  phase4_maturation: {
    maturation_top_k: 5,
    batch_size: 10,
    entity_synthesis_prompts: {
      direct_template: "Synthesize {entity_name} with envelopes {envelopes}",
    },
    entity_synthesis_decoding_strategy: "direct_constrained",
  },
  phase4: {
    adu_segmentation_prompt_template: "Identify ADUs in {chunk_text}",
    acc_confidence_threshold: 0.0,
    batch_size: 10,
    acc_prompts: {
      direct_template: "Classify ADUs in {tagged_text} with {chunk_entities}",
      reasoning_template: "Reason about {component_types} and {argument_relation_types}",
      format_template: "Format reasoning {reasoning_text}",
    },
    acc_decoding_strategy: "nl_to_format",
    arc_prompts: {
      direct_template: "Relate {component_a_text} and {component_b_text}",
    },
    arc_decoding_strategy: "nl_to_format",
    arc_confidence_threshold: 0.65,
    arc_subgraph_depth: 2,
    arc_max_candidates_per_component: 10,
    arc_use_priority_rank: false,
    adu_markup_open: "<AC",
    adu_markup_close: ">",
  },
  phase5: {
    argument_clustering_enabled: true,
    theory_fusion_enabled: true,
    fusion_similarity_threshold: 0.85,
    cluster_layer: "both",
  },
  phase6: {
    enabled: true,
  },
  execution: {
    persist_run_manifests: true,
    persist_phase1_artifacts: true,
    persist_phase2_artifacts: true,
    persist_phase3_artifacts: true,
    persist_phase3b_artifacts: true,
    persist_phase4_maturation_artifacts: true,
    persist_phase4_artifacts: true,
    persist_phase5_artifacts: true,
    persist_phase6_artifacts: true,
    project_artifacts_to_graph: true,
    allow_phase_reuse: true,
    allow_artifact_hydration: true,
    runs_dir: ".pipeline_runs",
    artifacts_dir: ".pipeline_artifacts",
  },
};

test("resolvePhaseKey maps phase names and ordinals correctly", () => {
  assert.equal(resolvePhaseKey({ phase_name: "Phase 1: Data Foundation", phase_ordinal: 1 }), "phase1");
  assert.equal(resolvePhaseKey({ phase_name: "Phase 2: Entity & Local Relation Discovery", phase_ordinal: 2 }), "phase2");
  assert.equal(resolvePhaseKey({ phase_name: "Phase 3: Global Relation Extraction", phase_ordinal: 3 }), "phase3");
  assert.equal(resolvePhaseKey({ phase_name: "Phase 3b: Latent Graph Consolidation", phase_ordinal: 4 }), "phase3b");
  assert.equal(resolvePhaseKey({ phase_name: "Phase 4: Entity Maturation (Batch Epistemic Synthesis)", phase_ordinal: 5 }), "phase4_maturation");
  assert.equal(resolvePhaseKey({ phase_name: "Phase 4: Argument Mining", phase_ordinal: 6 }), "phase4");
  assert.equal(resolvePhaseKey({ phase_name: "Phase 5: Inter-Document Argument Web", phase_ordinal: 7 }), "phase5");
  assert.equal(resolvePhaseKey({ phase_name: "Phase 6: Epistemic Consolidation", phase_ordinal: 8 }), "phase6");
  assert.equal(resolvePhaseKey({ phase_ordinal: 9 }), "execution");
});

test("extractPromptVariables extracts all curly variable tags", () => {
  const vars = extractPromptVariables("Hello {user}, welcome to {place}! Also {user} again.");
  assert.deepEqual(vars.sort(), ["place", "user"]);
});

test("resolvePhaseConfig extracts Phase 2 parameters and prompts", () => {
  const desc = resolvePhaseConfig(
    { phase_name: "Phase 2: Entity & Local Relation Discovery", phase_ordinal: 2 },
    SAMPLE_CONFIG_SNAPSHOT
  );

  assert.equal(desc.phaseKey, "phase2");
  assert.equal(desc.phaseOrdinal, 2);
  assert.equal(desc.category, "L2 Knowledge Graph");

  // Check scalar parameters
  const paramKeys = desc.parameters.map((p) => p.key);
  assert.ok(paramKeys.includes("top_k_linking_candidates"));
  assert.ok(paramKeys.includes("linking_confidence_threshold"));
  assert.ok(paramKeys.includes("ner_decoding_strategy"));

  // Check linking threshold value
  const linkingThresh = desc.parameters.find((p) => p.key === "linking_confidence_threshold");
  assert.equal(linkingThresh?.value, 0.85);

  // Check prompts extracted
  assert.ok(desc.prompts.length >= 2);
  const nerDirect = desc.prompts.find((p) => p.id === "ner_prompts.direct_template");
  assert.ok(nerDirect);
  assert.ok(nerDirect.variables.includes("chunk_text"));
  assert.ok(nerDirect.variables.includes("entity_types"));

  const linkingPrompt = desc.prompts.find((p) => p.id === "entity_linking_prompt_template");
  assert.ok(linkingPrompt);
  assert.ok(linkingPrompt.variables.includes("mention_a_text"));

  // Check execution settings
  const execKeys = desc.executionSettings.map((e) => e.key);
  assert.ok(execKeys.includes("persist_phase2_artifacts"));
});

test("resolvePhaseConfig extracts Phase 3 multiple prompt templates", () => {
  const desc = resolvePhaseConfig(
    { phase_name: "Phase 3: Global Relation Extraction", phase_ordinal: 3 },
    SAMPLE_CONFIG_SNAPSHOT
  );

  assert.equal(desc.phaseKey, "phase3");
  assert.equal(desc.prompts.length, 3); // direct, reasoning, format
  const roles = desc.prompts.map((p) => p.role);
  assert.ok(roles.includes("direct"));
  assert.ok(roles.includes("reasoning"));
  assert.ok(roles.includes("format"));
});

test("resolvePhaseConfig extracts Phase 4 ADU and ARC prompts", () => {
  const desc = resolvePhaseConfig(
    { phase_name: "Phase 4: Argument Mining", phase_ordinal: 6 },
    SAMPLE_CONFIG_SNAPSHOT
  );

  assert.equal(desc.phaseKey, "phase4");
  const promptIds = desc.prompts.map((p) => p.id);
  assert.ok(promptIds.includes("adu_segmentation_prompt_template"));
  assert.ok(promptIds.includes("acc_prompts.direct_template"));
  assert.ok(promptIds.includes("arc_prompts.direct_template"));
});

test("getAvailablePhaseTabs returns ordered phase tabs", () => {
  const tabs = getAvailablePhaseTabs(SAMPLE_CONFIG_SNAPSHOT);
  assert.ok(tabs.length >= 8);
  assert.equal(tabs[0].key, "phase1");
  assert.equal(tabs[1].key, "phase2");
  assert.equal(tabs[2].key, "phase3");
  assert.equal(tabs[3].key, "phase3b");
  assert.equal(tabs[4].key, "phase4_maturation");
  assert.equal(tabs[5].key, "phase4");
  assert.equal(tabs[6].key, "phase5");
  assert.equal(tabs[7].key, "phase6");

  // Verify prompts indicator
  assert.equal(tabs[0].hasPrompts, false);
  assert.equal(tabs[1].hasPrompts, true);
  assert.equal(tabs[2].hasPrompts, true);
});
