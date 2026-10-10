import test from "node:test";
import assert from "node:assert/strict";
import {
    classifyEpistemicRole,
    computeCrossLayerHeatmap,
    computeDegreeDistribution,
    computePredicateRows,
    findPhraseSpan,
    findRelationSpan,
    formatMultiChunkProvenance,
    formatSingleChunkProvenance,
    inferPhaseForEdge,
    isCanonicalPredicate,
    transformGraphToTriples,
    truncateLeading,
    truncateMiddle,
    truncateTrailing,
} from "./assertionTransformer.ts";
import type {GraphView} from "../api/types.ts";

test("classifyEpistemicRole accurately categorizes predicates", () => {
  assert.equal(classifyEpistemicRole("part_of"), "Hierarchical");
  assert.equal(classifyEpistemicRole("SUBCLASS_OF"), "Hierarchical");
  assert.equal(classifyEpistemicRole("SUPPORTS"), "Dialectical");
  assert.equal(classifyEpistemicRole("CONTRADICTS"), "Dialectical");
  assert.equal(classifyEpistemicRole("IMPLIES"), "Causal");
  assert.equal(classifyEpistemicRole("CAUSES"), "Causal");
  assert.equal(classifyEpistemicRole("RELATED_TO"), "Associative");
  assert.equal(classifyEpistemicRole("COHERES_WITH"), "Associative");
  assert.equal(classifyEpistemicRole("custom_random_pred"), "Unmapped");
});

test("isCanonicalPredicate detects open-vocabulary drift vs schema", () => {
  assert.equal(isCanonicalPredicate("part_of"), true);
  assert.equal(isCanonicalPredicate("supports"), true);
  assert.equal(isCanonicalPredicate("unknown_drift_relation"), false);
});

test("inferPhaseForEdge routes edges to their appropriate pipeline stages", () => {
  assert.equal(
    inferPhaseForEdge({
      id: "e1",
      source: "n1",
      target: "n2",
      target_kind: "node",
      type: "RELATED_TO",
      layer: 2,
      props: { scope: "local" },
    }),
    "phase2"
  );
  assert.equal(
    inferPhaseForEdge({
      id: "e2",
      source: "n1",
      target: "n2",
      target_kind: "node",
      type: "IMPLIES",
      layer: 2,
      props: { scope: "global" },
    }),
    "phase3"
  );
  assert.equal(
    inferPhaseForEdge({
      id: "e3",
      source: "ac1",
      target: "ac2",
      target_kind: "node",
      type: "SUPPORTS_ARG",
      layer: 3,
      props: { scope: "local" },
    }),
    "phase4"
  );
});

test("transformGraphToTriples converts GraphView into StageTripleItem propositions", () => {
  const mockGraph: GraphView = {
    nodes: [
      {
        id: "kant",
        layer: 2,
        type: "Person",
        label: "Immanuel Kant",
        degree: 4,
        resolved: true,
        synthetic: false,
        props: { description: "Philosopher of transcendental idealism" },
      },
      {
        id: "hegel",
        layer: 2,
        type: "Person",
        label: "G.W.F. Hegel",
        degree: 3,
        resolved: true,
        synthetic: false,
        props: { description: "Philosopher of dialectics" },
      },
    ],
    edges: [
      {
        id: "rel_1",
        source: "kant",
        target: "hegel",
        target_kind: "node",
        type: "IMPLIES",
        layer: 2,
        confidence: 0.91,
        props: { scope: "global" },
      },
    ],
    source: "artifacts",
    run_id: "test-run-001",
    graph_version: "v1",
    schema_version: "v1",
    truncated: false,
    dropped_count: 0,
    unmapped_predicates: {},
    unresolved_count: 0,
    layer_counts: { 2: 2 },
  };

  const triples = transformGraphToTriples(mockGraph);
  assert.equal(triples.length, 1);
  const t = triples[0];
  assert.equal(t.id, "rel_1");
  assert.equal(t.subject, "Immanuel Kant");
  assert.equal(t.predicate, "IMPLIES");
  assert.equal(t.object, "G.W.F. Hegel");
  assert.equal(t.category, "Causal");
  assert.equal(t.confidence, 0.91);
  assert.equal(t.status, "valid");
  assert.equal(t.phaseKey, "phase3");
});

test("computePredicateRows calculates frequencies and ontology mapping", () => {
  const mockGraph: GraphView = {
    nodes: [],
    edges: [
      { id: "e1", source: "a", target: "b", target_kind: "node", type: "SUPPORTS", layer: 2, confidence: 0.9, props: {} },
      { id: "e2", source: "b", target: "c", target_kind: "node", type: "SUPPORTS", layer: 2, confidence: 0.8, props: {} },
      { id: "e3", source: "a", target: "c", target_kind: "node", type: "DRIFT_REL", layer: 2, confidence: 0.5, props: {} },
    ],
    source: "artifacts",
    run_id: "test-run-001",
    graph_version: "v1",
    schema_version: "v1",
    truncated: false,
    dropped_count: 0,
    unmapped_predicates: { UNKNOWN_CANON: 1 },
    unresolved_count: 0,
    layer_counts: {},
  };

  const rows = computePredicateRows(mockGraph);
  assert.equal(rows.length, 3);
  const supportsRow = rows.find((r) => r.predicate === "SUPPORTS");
  assert.ok(supportsRow);
  assert.equal(supportsRow.frequency, 2);
  assert.equal(supportsRow.ontologyMapping, "Canonical Schema");
  assert.equal(supportsRow.epistemicRole, "Dialectical");
  assert.equal(supportsRow.averageConfidence, 0.85);

  const driftRow = rows.find((r) => r.predicate === "DRIFT_REL");
  assert.ok(driftRow);
  assert.equal(driftRow.ontologyMapping, "Open-Vocabulary Drift");
  assert.equal(driftRow.epistemicRole, "Unmapped");
});

test("computeDegreeDistribution and computeCrossLayerHeatmap return valid structures", () => {
  const mockGraph: GraphView = {
    nodes: [
      { id: "n1", layer: 1, type: "Chunk", label: "C1", degree: 2, resolved: true, synthetic: false, props: {} },
      { id: "n2", layer: 2, type: "Entity", label: "E1", degree: 4, resolved: true, synthetic: false, props: {} },
    ],
    edges: [
      { id: "e1", source: "n1", target: "n2", target_kind: "node", type: "MENTIONS", layer: 2, props: {} },
    ],
    source: "artifacts",
    run_id: "test-run-001",
    graph_version: "v1",
    schema_version: "v1",
    truncated: false,
    dropped_count: 0,
    unmapped_predicates: {},
    unresolved_count: 0,
    layer_counts: {},
  };

  const deg = computeDegreeDistribution(mockGraph);
  assert.ok(deg.empiricalPoints.length >= 2);

  const heatmap = computeCrossLayerHeatmap(mockGraph);
  assert.equal(heatmap.length, 16); // 4x4
});

test("row click predicate-to-triple lookup accurately identifies representative assertions", () => {
  const mockGraph: GraphView = {
    nodes: [
      { id: "k1", layer: 2, type: "Entity", label: "Concept A", degree: 1, resolved: true, synthetic: false, props: {} },
      { id: "k2", layer: 2, type: "Entity", label: "Concept B", degree: 1, resolved: true, synthetic: false, props: {} },
    ],
    edges: [
      {
        id: "e100",
        source: "k1",
        target: "k2",
        target_kind: "node",
        type: "CRITIQUES",
        layer: 2,
        props: { confidence: 0.91, epistemic_role: "dialectical" },
      },
    ],
    source: "artifacts",
    run_id: "test-run-selection",
    graph_version: "v1",
    schema_version: "v1",
    truncated: false,
    dropped_count: 0,
    unmapped_predicates: {},
    unresolved_count: 0,
    layer_counts: {},
  };

  const triples = transformGraphToTriples(mockGraph);
  assert.equal(triples.length, 1);
  const rows = computePredicateRows(mockGraph);
  assert.equal(rows.length, 1);

  // Simulating user clicking row in predicate table
  const clickedRow = rows[0];
  const matchingTriple = triples.find(
    (t) => t.predicate.toLowerCase() === clickedRow.predicate.toLowerCase()
  );
  assert.ok(matchingTriple);
  assert.equal(matchingTriple.subject, "Concept A");
  assert.equal(matchingTriple.predicate, "CRITIQUES");
  assert.equal(matchingTriple.object, "Concept B");
  assert.equal(matchingTriple.confidence, 0.91);
});

test("truncateLeading, truncateTrailing, and truncateMiddle format excerpts cleanly", () => {
  const shortText = "Short discourse excerpt.";
  assert.equal(truncateLeading(shortText, 70), shortText);
  assert.equal(truncateTrailing(shortText, 70), shortText);

  const longLeading =
    "In classical German philosophy, particularly in the critical methodology developed by Immanuel Kant during the late eighteenth century Königsberg lectures, the transcendental deduction serves as";
  const trimmedLeading = truncateLeading(longLeading, 60);
  assert.ok(trimmedLeading.startsWith("… "));
  assert.ok(trimmedLeading.length < longLeading.length);

  const longTrailing =
    "serves as the cornerstone of epistemological justification, reframing traditional metaphysics into a systematic exploration of the synthetic a priori conditions of possible experience.";
  const trimmedTrailing = truncateTrailing(longTrailing, 60);
  assert.ok(trimmedTrailing.endsWith(" …"));
  assert.ok(trimmedTrailing.length < longTrailing.length);

  const shortMid = "transcendental deduction implies";
  const resShort = truncateMiddle(shortMid, 100);
  assert.equal(resShort.truncated, false);
  assert.equal(resShort.text, shortMid);

  const longMid =
    "transcendental deduction, which encompasses a dense exposition of the categories of the understanding and their legitimate application to sensible intuition rather than transcendent things in themselves, directly implies";
  const resLong = truncateMiddle(longMid, 70);
  assert.equal(resLong.truncated, true);
  assert.ok(resLong.text.includes("[...]"));
});

test("findPhraseSpan and findRelationSpan locate entities and predicates accurately", () => {
  const text = "Furthermore, Kantian Dualism is fundamentally challenged by dialectical progression.";
  const span1 = findPhraseSpan(text, "Kantian Dualism");
  assert.ok(span1);
  assert.equal(span1.matchedText, "Kantian Dualism");

  const span2 = findPhraseSpan(text, "dialectical progression");
  assert.ok(span2);
  assert.equal(span2.matchedText, "dialectical progression");

  // Case-insensitivity
  const spanCase = findPhraseSpan(text, "kantian dualism");
  assert.ok(spanCase);
  assert.equal(spanCase.matchedText, "Kantian Dualism");

  // Word fallback
  const spanFuzzy = findPhraseSpan(text, "Kantian Philosophy");
  assert.ok(spanFuzzy);
  assert.equal(spanFuzzy.matchedText, "Kantian");

  // Predicate stems
  const relSpan1 = findRelationSpan("which contradicts and invalidates", "CONTRADICTS");
  assert.ok(relSpan1);
  assert.equal(relSpan1.matchedText, "contradicts");

  const relSpan2 = findRelationSpan("which immanently critiques the premise", "IMMANENTLY_CRITIQUES");
  assert.ok(relSpan2);
  assert.ok(relSpan2.matchedText.includes("critique"));
});

test("formatSingleChunkProvenance formats intra-chunk verbatim excerpts with relationship and ellipsis", () => {
  const chunkText =
    "In the philosophy of psychoanalysis, clinical observation suggests that incest contradicts Oedipus complex within the early developmental phases of childhood neurosis.";

  const result = formatSingleChunkProvenance(
    chunkText,
    "incest",
    "Oedipus complex",
    "CONTRADICTS",
    "chunk_001",
    180,
    "freud_theory.md"
  );

  assert.equal(result.chunkId, "chunk_001");
  assert.equal(result.docId, "freud_theory.md");
  assert.equal(result.tokenCount, 180);
  assert.equal(result.highlightedText, "incest");
  assert.equal(result.highlightType, "subject");
  assert.equal(result.relationText, "contradicts");
  assert.equal(result.secondHighlightedText, "Oedipus complex");
  assert.equal(result.secondHighlightType, "object");
});

test("formatMultiChunkProvenance extracts and formats across Chunk A and Chunk B", () => {
  const chunkAText =
    "In the first Critique, Immanuel Kant articulates the synthetic a priori as the foundational ground for mathematical and physical judgments.";
  const chunkBText =
    "In the Science of Logic, Hegel rejects the synthetic a priori as an uncritical preservation of the Kantian Dualism between concept and intuition.";

  const results = formatMultiChunkProvenance(
    chunkAText,
    chunkBText,
    "synthetic a priori",
    "Kantian Dualism",
    "chunk_010",
    "chunk_025",
    140,
    160,
    "german_idealism.md"
  );

  assert.equal(results.length, 2);
  const [chunkA, chunkB] = results;

  assert.equal(chunkA.chunkId, "chunk_010");
  assert.equal(chunkA.highlightedText, "synthetic a priori");
  assert.equal(chunkA.highlightType, "subject");

  assert.equal(chunkB.chunkId, "chunk_025");
  assert.equal(chunkB.highlightedText, "Kantian Dualism");
  assert.equal(chunkB.highlightType, "object");
});

test("transformGraphToTriples populates single_chunk and multi_chunk provenance from real GraphView nodes", () => {
  const graph: GraphView = {
    nodes: [
      {
        id: "chunk_001",
        layer: 1,
        type: "Chunk",
        label: "chunk_001",
        resolved: true,
        synthetic: false,
        props: {
          text: "Introductory section asserts that concept alpha part_of framework beta, while concept gamma is introduced as a premise.",
          token_count: 120,
          source_doc_id: "doc_alpha",
        },
      },
      {
        id: "chunk_002",
        layer: 1,
        type: "Chunk",
        label: "chunk_002",
        resolved: true,
        synthetic: false,
        props: {
          text: "Later chapters demonstrate that concept gamma contradicts hypothesis delta under empirical testing.",
          token_count: 150,
          source_doc_id: "doc_gamma",
        },
      },
      {
        id: "doc_alpha",
        layer: 1,
        type: "Document",
        label: "Theoretical Foundations.md",
        resolved: true,
        synthetic: false,
        props: {},
      },
      {
        id: "c_alpha",
        layer: 2,
        type: "Concept",
        label: "concept alpha",
        resolved: true,
        synthetic: false,
        props: { source_chunk_ids: ["chunk_001"] },
      },
      {
        id: "c_beta",
        layer: 2,
        type: "Concept",
        label: "framework beta",
        resolved: true,
        synthetic: false,
        props: { source_chunk_ids: ["chunk_001"] },
      },
      {
        id: "c_gamma",
        layer: 2,
        type: "Concept",
        label: "concept gamma",
        resolved: true,
        synthetic: false,
        props: { source_chunk_ids: ["chunk_001"] },
      },
      {
        id: "c_delta",
        layer: 2,
        type: "Concept",
        label: "hypothesis delta",
        resolved: true,
        synthetic: false,
        props: { source_chunk_ids: ["chunk_002"] },
      },
    ],
    edges: [
      {
        id: "edge_local",
        source: "c_alpha",
        target: "c_beta",
        target_kind: "node",
        type: "part_of",
        layer: 2,
        confidence: 0.95,
        props: { scope: "local", source_chunk_id: "chunk_001" },
      },
      {
        id: "edge_global",
        source: "c_gamma",
        target: "c_delta",
        target_kind: "node",
        type: "CONTRADICTS",
        layer: 2,
        confidence: 0.88,
        props: {
          scope: "global",
          supporting_chunk_ids: ["chunk_001", "chunk_002"],
        },
      },
    ],
    source: "artifacts",
    run_id: "run-prov-test",
    graph_version: "v1",
    schema_version: "v1",
    truncated: false,
    dropped_count: 0,
    unmapped_predicates: {},
    unresolved_count: 0,
    layer_counts: { 1: 3, 2: 4 },
  };

  const triples = transformGraphToTriples(graph);
  assert.equal(triples.length, 2);

  // 1. Single Chunk Local Relation
  const localTriple = triples.find((t) => t.id === "edge_local")!;
  assert.ok(localTriple);
  assert.equal(localTriple.provenanceMode, "single_chunk");
  assert.equal(localTriple.sourceChunkId, "chunk_001");
  assert.equal(localTriple.documentName, "Theoretical Foundations.md");
  assert.equal(localTriple.scope, "local");
  assert.ok(localTriple.provenanceChunks && localTriple.provenanceChunks.length === 1);
  assert.equal(localTriple.provenanceChunks[0].highlightedText, "concept alpha");
  assert.equal(localTriple.provenanceChunks[0].secondHighlightedText, "framework beta");

  // 2. Multi-Chunk Global Relation
  const globalTriple = triples.find((t) => t.id === "edge_global")!;
  assert.ok(globalTriple);
  assert.equal(globalTriple.provenanceMode, "multi_chunk");
  assert.equal(globalTriple.scope, "global");
  assert.ok(globalTriple.provenanceChunks && globalTriple.provenanceChunks.length === 2);
  assert.equal(globalTriple.provenanceChunks[0].chunkId, "chunk_001");
  assert.equal(globalTriple.provenanceChunks[1].chunkId, "chunk_002");
  assert.equal(globalTriple.provenanceChunks[0].highlightedText, "concept gamma");
  assert.equal(globalTriple.provenanceChunks[1].highlightedText, "hypothesis delta");
});

