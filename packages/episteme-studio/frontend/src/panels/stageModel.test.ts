import test from "node:test";
import assert from "node:assert/strict";
import {getPhaseLifecycleGroup, getShortStageLabel, resolveStageArtifacts,} from "./stageModel.ts";

test("getPhaseLifecycleGroup correctly partitions phases into lifecycle stages", () => {
  // Ingest
  assert.equal(getPhaseLifecycleGroup({ phase_name: "Phase 1: Data Foundation", phase_ordinal: 1 }), "ingest");
  assert.equal(getPhaseLifecycleGroup({ key: "phase1" }), "ingest");

  // Extraction & Inference
  assert.equal(getPhaseLifecycleGroup({ phase_name: "Phase 2: Entity & Local Relation Discovery", phase_ordinal: 2 }), "extraction");
  assert.equal(getPhaseLifecycleGroup({ phase_name: "Phase 3: Global Relation Extraction", phase_ordinal: 3 }), "extraction");
  assert.equal(getPhaseLifecycleGroup({ phase_name: "Phase 3b: Latent Graph Consolidation", phase_ordinal: 4 }), "extraction");
  assert.equal(getPhaseLifecycleGroup({ phase_name: "Phase 4: Entity Maturation", phase_ordinal: 5 }), "extraction");
  assert.equal(getPhaseLifecycleGroup({ phase_name: "Phase 4: Argument Mining", phase_ordinal: 6 }), "extraction");

  // Synthesis & TheoryNet
  assert.equal(getPhaseLifecycleGroup({ phase_name: "Phase 5: Inter-Document Argument Web", phase_ordinal: 7 }), "synthesis");
  assert.equal(getPhaseLifecycleGroup({ phase_name: "Phase 6: Epistemic Consolidation (TheoryNet)", phase_ordinal: 8 }), "synthesis");

  // Post-processing & materialization
  assert.equal(getPhaseLifecycleGroup({ key: "phase7" }), "post");
  assert.equal(getPhaseLifecycleGroup({ key: "post" }), "post");
});

test("resolveStageArtifacts decomposes Phase 2 into entities, local relations, and confidence distribution", () => {
  const phaseRecord = {
    phase_name: "Phase 2: Entity & Local Relation Discovery",
    phase_ordinal: 2,
    status: "completed" as const,
    artifact_count: 168,
    reused: false,
    duration_seconds: 18.5,
    artifact_counts_by_kind: {
      entity: 123,
      local_relation: 45,
    },
  };

  const report = resolveStageArtifacts("phase2", phaseRecord, phaseRecord.artifact_counts_by_kind);

  assert.equal(report.stageKey, "phase2");
  assert.equal(report.totalYield, 168);
  assert.equal(report.reused, false);
  assert.equal(report.durationSeconds, 18.5);
  assert.equal(report.lensId, "knowledge_graph");
  assert.equal(report.lensName, "Knowledge Graph");

  assert.equal(report.items.length, 2);
  assert.equal(report.items[0].label, "Discovered Entities");
  assert.equal(report.items[0].count, 123);
  assert.equal(report.items[1].label, "Local Relations");
  assert.equal(report.items[1].count, 45);

  assert.ok(report.confidenceDistribution);
  assert.ok(report.confidenceDistribution.high > 0);
  assert.ok(report.confidenceDistribution.medium > 0);
});

test("resolveStageArtifacts handles Phase 4 Argument Mining components and relations", () => {
  const phaseRecord = {
    phase_name: "Phase 4: Argument Mining",
    phase_ordinal: 6,
    status: "completed" as const,
    artifact_count: 90,
    reused: true,
    duration_seconds: 0.2,
    artifact_counts_by_kind: {
      argument_component: 54,
      argument_relation: 36,
    },
  };

  const report = resolveStageArtifacts("phase4", phaseRecord);

  assert.equal(report.stageKey, "phase4");
  assert.equal(report.totalYield, 90);
  assert.equal(report.reused, true);
  assert.equal(report.lensId, "argument_web");
  assert.equal(report.lensName, "Argument Web");

  assert.equal(report.items.length, 2);
  assert.equal(report.items[0].label, "Argument Units (ADUs)");
  assert.equal(report.items[0].count, 54);
  assert.equal(report.items[1].label, "Argument Relations");
  assert.equal(report.items[1].count, 36);
});

test("getShortStageLabel provides crisp labels without clipping", () => {
  assert.equal(getShortStageLabel("Phase 1: Foundation", 1), "Ingest & Chunks");
  assert.equal(getShortStageLabel("Phase 2: Entity & Local Relation Discovery", 2), "Entities & Local Rels");
  assert.equal(getShortStageLabel("Phase 3: Global Relation Extraction", 3), "Global Relations");
  assert.equal(getShortStageLabel("Phase 4: Argument Mining", 6), "Argument Mining");
  assert.equal(getShortStageLabel("Phase 6: TheoryNet", 8), "TheoryNet & Bridges");
});
