import test from "node:test";
import assert from "node:assert/strict";
import type {
  CompetencyQueryDiagnosticItem,
  PerturbationSweepPoint,
  NoiseRobustnessReportDetail,
} from "../../../../api/types.ts";

test("retrieval: MRR and Hits@K metric calculation adheres to Information Retrieval invariants", () => {
  const queries: CompetencyQueryDiagnosticItem[] = [
    {
      query_id: "q1",
      query_text: "What is Kepler's 3rd Law?",
      expected_gold_nodes: ["kepler_law_3"],
      retrieved_candidates: [],
      first_hit_rank: 1,
      reciprocal_rank: 1.0,
      hits_at_1: true,
      hits_at_3: true,
      hits_at_10: true,
    },
    {
      query_id: "q2",
      query_text: "Which axiom proves momentum conservation?",
      expected_gold_nodes: ["axiom_momentum"],
      retrieved_candidates: [],
      first_hit_rank: 2,
      reciprocal_rank: 0.5,
      hits_at_1: false,
      hits_at_3: true,
      hits_at_10: true,
    },
    {
      query_id: "q3",
      query_text: "How does Newton define absolute space?",
      expected_gold_nodes: ["space_absolute"],
      retrieved_candidates: [],
      first_hit_rank: 4,
      reciprocal_rank: 0.25,
      hits_at_1: false,
      hits_at_3: false,
      hits_at_10: true,
    },
    {
      query_id: "q4",
      query_text: "What refutes solipsism?",
      expected_gold_nodes: ["other_minds"],
      retrieved_candidates: [],
      first_hit_rank: 20,
      reciprocal_rank: 0.05,
      hits_at_1: false,
      hits_at_3: false,
      hits_at_10: false,
    },
  ];

  const total = queries.length;
  assert.equal(total, 4);

  // MRR = (1.0 + 0.5 + 0.25 + 0.05) / 4 = 1.80 / 4 = 0.45
  const mrr = queries.reduce((acc, q) => acc + q.reciprocal_rank, 0) / total;
  assert.equal(mrr, 0.45);

  // Hits@1 = 1 / 4 = 25%
  const hits1 = queries.filter((q) => q.hits_at_1).length / total;
  assert.equal(hits1, 0.25);

  // Hits@3 = 2 / 4 = 50%
  const hits3 = queries.filter((q) => q.hits_at_3).length / total;
  assert.equal(hits3, 0.5);

  // Hits@10 = 3 / 4 = 75%
  const hits10 = queries.filter((q) => q.hits_at_10).length / total;
  assert.equal(hits10, 0.75);
});

test("noiseRobustness: Robustness Degradation Factor (RDF) and resilience classification", () => {
  const baselineF1 = 0.92;
  const worstCaseF1 = 0.81;

  // RDF = 1 - (worst_case / baseline)
  const rdf = Math.round((1.0 - worstCaseF1 / baselineF1) * 1000) / 1000;
  // 1 - 0.81 / 0.92 = 1 - 0.88043... = 0.11956... -> 0.120
  assert.ok(Math.abs(rdf - 0.12) < 0.005);

  // Resilience condition: RDF < 0.20 => resilient
  const isResilient = rdf < 0.20;
  assert.equal(isResilient, true);

  // Catastrophic noise degradation scenario
  const vulnerableWorstCase = 0.60;
  const vulnerableRDF = 1.0 - vulnerableWorstCase / baselineF1;
  // 1 - 0.60 / 0.92 = 0.3478
  assert.ok(vulnerableRDF >= 0.20);
});

test("noiseRobustness: Perturbation sweep series monotonically increases degradation", () => {
  const sweep: PerturbationSweepPoint[] = [
    { noise_level: 0.0, f1_score: 0.92, mcc_score: 0.95, poset_dag_valid: true, rdf_delta: 0.0 },
    { noise_level: 0.05, f1_score: 0.88, mcc_score: 0.91, poset_dag_valid: true, rdf_delta: 0.043 },
    { noise_level: 0.10, f1_score: 0.82, mcc_score: 0.84, poset_dag_valid: true, rdf_delta: 0.109 },
    { noise_level: 0.20, f1_score: 0.71, mcc_score: 0.70, poset_dag_valid: false, rdf_delta: 0.228 },
  ];

  // Increasing noise level strictly decreases F1 score
  for (let i = 1; i < sweep.length; i++) {
    assert.ok(sweep[i].f1_score < sweep[i - 1].f1_score);
    assert.ok(sweep[i].rdf_delta > sweep[i - 1].rdf_delta);
  }

  // Extreme noise level breaks poset DAG acyclicity
  assert.equal(sweep[0].poset_dag_valid, true);
  assert.equal(sweep[3].poset_dag_valid, false);
});
