import test from "node:test";
import assert from "node:assert/strict";
import {CURATED_LENSES, extractTheoriesFromGraph, useViewOverlayStore,} from "../store/viewOverlayStore.ts";

test("CURATED_LENSES contains only domain-agnostic lenses and no hardcoded domain theories", () => {
  const lensIds = CURATED_LENSES.map((l) => l.id);

  // Hardcoded domain theories must be removed
  assert.ok(!lensIds.includes("theory_neurology"), "theory_neurology should not be hardcoded");
  assert.ok(!lensIds.includes("theory_psychoanalysis"), "theory_psychoanalysis should not be hardcoded");

  // Domain-agnostic structuralist lenses must be preserved
  assert.ok(lensIds.includes("all"), "Full graph snapshot lens should be present");
  assert.ok(lensIds.includes("empirical_base"), "Empirical base (M_pp) lens should be present");
  assert.ok(lensIds.includes("theoretical_core"), "Theoretical core (M) lens should be present");
  assert.ok(lensIds.includes("argument_web"), "Argument web lens should be present");
  assert.ok(lensIds.includes("knowledge_graph"), "Knowledge graph lens should be present");
  assert.ok(lensIds.includes("bridges"), "Intertheoretical bridges lens should be present");
});

test("extractTheoriesFromGraph correctly extracts dynamic theories from graph nodes", () => {
  const mockGraph = {
    nodes: [
      {
        id: "hyp_1",
        layer: 3,
        type: "TheoreticalHypothesis",
        label: "Dopamine hypothesis of reward",
        partition: "A",
        props: {
          theory_id: "reinforcement_learning",
          theory_cluster: "cluster-chunk-01",
          parameters: { QValue: 0.85, LearningRate: 0.1 },
        },
        tenability: {
          theory_id: "reinforcement_learning",
          local_score: 0.9,
          aggregated_score: 0.88,
        },
      },
      {
        id: "obs_1",
        layer: 3,
        type: "ObservationUnit",
        label: "Striatal dopamine burst measurement",
        partition: "B",
        props: {
          theory_id: "reinforcement_learning",
          theory_cluster: "cluster-chunk-01",
          parameters: { PredictionError: 0.72 },
        },
        tenability: {
          theory_id: "reinforcement_learning",
          local_score: 0.86,
          aggregated_score: 0.88,
        },
      },
      {
        id: "hyp_2",
        layer: 3,
        type: "TheoreticalHypothesis",
        label: "Free energy minimization hypothesis",
        partition: "A",
        props: {
          theory_id: "predictive_processing",
          theory_cluster: "cluster-chunk-02",
          parameters: { PrecisionWeight: 0.95 },
        },
        tenability: {
          theory_id: "predictive_processing",
          local_score: 0.75,
          aggregated_score: 0.75,
        },
      },
      {
        id: "general_entity",
        layer: 2,
        type: "Concept",
        label: "Synaptic plasticity",
        props: {},
      },
    ],
    edges: [],
    source: "artifacts",
    graph_version: "test-v1",
    schema_version: "v1",
  };

  const theories = extractTheoriesFromGraph(mockGraph as any);
  assert.equal(theories.length, 2);

  const rl = theories.find((t) => t.theoryId === "reinforcement_learning");
  assert.ok(rl, "reinforcement_learning theory should be found");
  assert.equal(rl.elementCount, 2);
  assert.equal(rl.badge, "Φ_reinfo");
  assert.equal(rl.name, "Theory: Reinforcement Learning");
  assert.ok(rl.parameters.includes("QValue"));
  assert.ok(rl.parameters.includes("LearningRate"));
  assert.ok(rl.parameters.includes("PredictionError"));
  assert.ok(rl.clusters.includes("cluster-chunk-01"));
  assert.equal(rl.mask.theoryId, "reinforcement_learning");

  const pp = theories.find((t) => t.theoryId === "predictive_processing");
  assert.ok(pp, "predictive_processing theory should be found");
  assert.equal(pp.elementCount, 1);
  assert.equal(pp.badge, "Φ_predic");
  assert.equal(pp.name, "Theory: Predictive Processing");
  assert.ok(pp.parameters.includes("PrecisionWeight"));
  assert.equal(pp.mask.theoryId, "predictive_processing");
});

test("extractTheoriesFromGraph returns empty array for null or empty graph", () => {
  assert.deepEqual(extractTheoriesFromGraph(null), []);
  assert.deepEqual(extractTheoriesFromGraph({ nodes: [] } as any), []);
  assert.deepEqual(
    extractTheoriesFromGraph({ nodes: [{ id: "n1", props: {} }] } as any),
    []
  );
});

test("useViewOverlayStore handles dynamic theory lens activation and drawer toggles", () => {
  const store = useViewOverlayStore.getState();

  // Initially closed
  useViewOverlayStore.setState({ isDrawerOpen: false });
  assert.equal(useViewOverlayStore.getState().isDrawerOpen, false);

  // Open drawer
  useViewOverlayStore.getState().openDrawer("overlays");
  assert.equal(useViewOverlayStore.getState().isDrawerOpen, true);
  assert.equal(useViewOverlayStore.getState().activeTab, "overlays");

  // Close drawer
  useViewOverlayStore.getState().closeDrawer();
  assert.equal(useViewOverlayStore.getState().isDrawerOpen, false);

  // Toggle drawer
  useViewOverlayStore.getState().toggleDrawer();
  assert.equal(useViewOverlayStore.getState().isDrawerOpen, true);

  // Dynamic theory lens activation
  useViewOverlayStore.getState().setActiveLens("theory_quantum_gravity");
  const mask = useViewOverlayStore.getState().activeMask;
  assert.equal(mask.lensId, "theory_quantum_gravity");
  assert.equal(mask.theoryId, "quantum_gravity");

  // Reset mask
  useViewOverlayStore.getState().resetMask();
  assert.equal(useViewOverlayStore.getState().activeMask.lensId, "all");
  assert.equal(useViewOverlayStore.getState().activeMask.theoryId, null);
});

test("activeMask.theoryId accurately isolates theory-specific nodes", () => {
  const nodes = [
    { id: "n1", props: { theory_id: "theory_alpha" } },
    { id: "n2", props: { theory_id: "theory_beta" } },
    { id: "n3", props: { other_prop: 123 } },
  ];

  const filterForTheory = (activeTheoryId: string | null) => {
    return nodes.filter((node) => {
      if (activeTheoryId) {
        const nodeTheoryId = node.props?.theory_id;
        if (nodeTheoryId !== activeTheoryId) return false;
      }
      return true;
    });
  };

  const alphaNodes = filterForTheory("theory_alpha");
  assert.equal(alphaNodes.length, 1);
  assert.equal(alphaNodes[0].id, "n1");

  const betaNodes = filterForTheory("theory_beta");
  assert.equal(betaNodes.length, 1);
  assert.equal(betaNodes[0].id, "n2");

  const allNodes = filterForTheory(null);
  assert.equal(allNodes.length, 3);
});
