import test from "node:test";
import assert from "node:assert/strict";
import {computeEdgeStyle} from "./edgeStyling.ts";
import {computeNodeStyle} from "./nodeStyling.ts";
import type {EdgeStyleContext, NodeStyleContext} from "./types.ts";
import type {StudioEdge, StudioNode} from "../../api/types.ts";

const BASE_GRAPH_SETTINGS = {
  nodeSizeMultiplier: 1.0,
  edgeThicknessMultiplier: 1.0,
  labelFontSize: 11,
  labelMaxLength: 24,
  showEdgeLabels: true,
  autoAdaptLabels: false,
  linkDistance: 120,
  nodeRepulsion: -300,
  hierarchicalRankSep: 80,
  forceLayoutAnimated: true,
  forceIterations: 300,
};

test("computeEdgeStyle resolves dynamic polarity via schema and open-vocabulary aliases", () => {
  const edge: StudioEdge = {
    id: "e1",
    source: "n1",
    target: "n2",
    type: "WIDERSPRICHT",
    layer: 3,
    polarity: null, // Raw backend has no precomputed polarity
    weight: 0.8,
    target_kind: "node",
    props: {},
  };

  const contextWithAlias: EdgeStyleContext = {
    isDark: true,
    activeOverlay: null,
    activeMetricResult: null,
    isDiffActive: false,
    diffData: null,
    graphSettings: BASE_GRAPH_SETTINGS,
    getPolarity: (type: string) => (type === "WIDERSPRICHT" ? -1 : null),
  };

  const styleWithAlias = computeEdgeStyle(edge, contextWithAlias);
  assert.equal(styleWithAlias.stroke, "#ef4444", "Should resolve to red attack (-1) via schema alias");
  assert.equal(styleWithAlias.lineDash, undefined, "Mapped predicate should be solid line");

  // When unmapped in schema, fallback to unmapped dashed
  const contextUnmapped: EdgeStyleContext = {
    ...contextWithAlias,
    getPolarity: () => null,
  };
  const styleUnmapped = computeEdgeStyle(edge, contextUnmapped);
  assert.equal(styleUnmapped.stroke, "#64748b", "Unmapped predicate should render with neutral/muted stroke");
  assert.deepEqual(styleUnmapped.lineDash, [4, 4], "Unmapped predicate should render as dashed line");
});

test("computeEdgeStyle preserves pre-calculated edge polarity as fallback", () => {
  const edge: StudioEdge = {
    id: "e2",
    source: "n1",
    target: "n2",
    type: "SUPPORTS",
    layer: 3,
    polarity: 1, // Precomputed on edge payload
    weight: 0.9,
    target_kind: "node",
    props: {},
  };

  const ctx: EdgeStyleContext = {
    isDark: false,
    activeOverlay: null,
    activeMetricResult: null,
    isDiffActive: false,
    diffData: null,
    graphSettings: BASE_GRAPH_SETTINGS,
    getPolarity: () => null, // Schema has no override
  };

  const style = computeEdgeStyle(edge, ctx);
  assert.equal(style.stroke, "#10b981", "Should use precomputed support (+1) emerald color");
});

test("computeNodeStyle applies layer colors, synthetic, and unresolved flags", () => {
  const nodeL1: StudioNode = {
    id: "c1",
    label: "Chunk 1",
    layer: 1,
    type: "Chunk",
    resolved: true,
    synthetic: false,
    props: {},
  };

  const nodeL3: StudioNode = {
    id: "h1",
    label: "Theoretical Hypothesis",
    layer: 3,
    type: "TheoreticalHypothesis",
    resolved: true,
    synthetic: false,
    props: {},
  };

  const nodeUnresolved: StudioNode = {
    id: "u1",
    label: "Missing Concept",
    layer: 2,
    type: "Concept",
    resolved: false,
    synthetic: false,
    props: {},
  };

  const ctx: NodeStyleContext = {
    isDark: true,
    activeOverlay: null,
    activeMetricResult: null,
    isDiffActive: false,
    diffData: null,
    graphSettings: BASE_GRAPH_SETTINGS,
    getPartition: () => null,
  };

  const styleL1 = computeNodeStyle(nodeL1, ctx);
  assert.equal(styleL1.fill, "#3b82f6", "L1 chunk should be blue");

  const styleL3 = computeNodeStyle(nodeL3, ctx);
  assert.equal(styleL3.fill, "#059669", "L3 TheoryNet should be emerald");

  const styleUnres = computeNodeStyle(nodeUnresolved, ctx);
  assert.equal(styleUnres.stroke, "#f59e0b", "Unresolved node should have amber stroke");
  assert.deepEqual(styleUnres.lineDash, [4, 4], "Unresolved node should have dashed border");
});

test("computeNodeStyle handles diff additions and deletions", () => {
  const node: StudioNode = {
    id: "n_diff",
    label: "Modified Node",
    layer: 2,
    type: "Concept",
    resolved: true,
    synthetic: false,
    props: {},
  };

  const gainedCtx: NodeStyleContext = {
    isDark: true,
    activeOverlay: null,
    activeMetricResult: null,
    isDiffActive: true,
    diffData: {
      run_a_id: "a",
      run_b_id: "b",
      node_diff: { n_diff: "gained" },
      edge_diff: {},
      rho_deltas: {},
      polarity_inversions: [],
      union_graph: { nodes: [], edges: [], layer_counts: { 1: 0, 2: 0, 3: 0 } },
    } as any,
    graphSettings: BASE_GRAPH_SETTINGS,
    getPartition: () => null,
  };

  const gainedStyle = computeNodeStyle(node, gainedCtx);
  assert.equal(gainedStyle.stroke, "#10b981", "Gained node should have emerald border");
  assert.ok(gainedStyle.labelText.startsWith("[+]"), "Gained node label should be prefixed with [+]");
});
