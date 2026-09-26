import test from "node:test";
import assert from "node:assert/strict";
import type {
  EvaluationEdgeOverlay,
  EvaluationNodeOverlay,
  EvaluationGraphOverlay,
} from "../../../../api/types.ts";

test("topologicalCanvas: classification and alignment status invariants", () => {
  const tpNode: EvaluationNodeOverlay = {
    id: "str:Newtonian_Particle_Mechanics",
    label: "Newtonian Particle Mechanics",
    class_name: "potential_models",
    symbol: "Mp",
    alignment_status: "true_positive",
    gold_id: "str:Newtonian_Particle_Mechanics",
    similarity_score: 1.0,
    is_ghost: false,
  };

  const fnGhostNode: EvaluationNodeOverlay = {
    id: "str:CPM_Axiom_3_ActionReaction",
    label: "Action-Reaction Law [Omitted]",
    class_name: "actual_models",
    symbol: "M",
    alignment_status: "false_negative",
    gold_id: "str:CPM_Axiom_3_ActionReaction",
    similarity_score: 0.0,
    is_ghost: true,
  };

  const fpHallucinationNode: EvaluationNodeOverlay = {
    id: "pred:Unverified_Kinematic_Claim",
    label: "Unverified Kinematic Claim",
    class_name: "potential_models",
    symbol: "Mp",
    alignment_status: "false_positive",
    similarity_score: 0.15,
    is_ghost: false,
  };

  const conflictEdge: EvaluationEdgeOverlay = {
    id: "edge_conflict_01",
    source: "str:Newtonian_Particle_Mechanics",
    target: "pred:Unverified_Kinematic_Claim",
    predicate: "SUPPORTS",
    gold_predicate: "ATTACKS",
    alignment_status: "polarity_conflict",
    similarity_score: 0.65,
    is_ghost: false,
  };

  assert.equal(tpNode.alignment_status, "true_positive");
  assert.equal(tpNode.is_ghost, false);

  assert.equal(fnGhostNode.alignment_status, "false_negative");
  assert.equal(fnGhostNode.is_ghost, true);

  assert.equal(fpHallucinationNode.alignment_status, "false_positive");
  assert.equal(fpHallucinationNode.similarity_score, 0.15);

  assert.equal(conflictEdge.alignment_status, "polarity_conflict");
  assert.equal(conflictEdge.predicate, "SUPPORTS");
  assert.equal(conflictEdge.gold_predicate, "ATTACKS");
});

test("topologicalCanvas: summary counts and overlay integrity", () => {
  const mockOverlay: EvaluationGraphOverlay = {
    evaluation_id: "eval-carnap-001",
    run_id: "run-001",
    benchmark_id: "carnap-1928-aufbau",
    nodes: [
      {
        id: "n1",
        label: "Qualia",
        alignment_status: "true_positive",
        similarity_score: 1.0,
        is_ghost: false,
      },
      {
        id: "n2",
        label: "Elementary Experience",
        alignment_status: "false_negative",
        similarity_score: 0.0,
        is_ghost: true,
      },
    ],
    edges: [
      {
        id: "e1",
        source: "n1",
        target: "n2",
        predicate: "has_constituent",
        alignment_status: "false_negative",
        similarity_score: 0.0,
        is_ghost: true,
      },
    ],
    summary_counts: {
      tp_nodes: 1,
      fp_nodes: 0,
      fn_nodes: 1,
      tp_edges: 0,
      fp_edges: 0,
      fn_edges: 1,
      conflict_edges: 0,
    },
  };

  assert.equal(mockOverlay.nodes.length, 2);
  assert.equal(mockOverlay.edges.length, 1);
  assert.equal(mockOverlay.summary_counts.fn_nodes, 1);
  assert.equal(mockOverlay.summary_counts.tp_nodes, 1);
});
