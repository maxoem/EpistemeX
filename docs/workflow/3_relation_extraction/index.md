# Phase 3: Global Relation Extraction

## Overview

Phase 3 discovers semantic relationships between entity pairs across different documents and chunks, moving beyond
intra-chunk co-occurrences to establish the global network structure of the theory graph.

## Purpose

While Phase 2 extracts local relations within individual chunks, Phase 3 connects entities across document boundaries.
It identifies conceptual dependencies, historical lineages, and argumentative tensions that span across the corpus.

## Theoretical Foundation

See [Epistemic Grounding & Dense Alignment](../../concepts/dense_alignment.md)
and [ADR 0002](../../adr/0002-tag-reranker-global-relation-extraction.md):

- Global candidate generation via dense MIPS retrieval
- Contextual isomorphism and Text-Attributed Graph (TAG) subgraph envelopes
- Relational reranking using Cross-Encoders
- Constrained LLM relation classification

## Components

### 1. Global Candidate Retrieval (The Prior)

- **Dense MIPS Retrieval**: Computes dense vector similarities between entity embeddings across the entire corpus,
  breaking document and chunk boundaries.
- **Structural Candidate Blocking**: Optionally filters or groups candidates to avoid $O (N^2)$ explosion, capping
  partner candidates at `max_candidates_per_entity_pair`.

### 2. Contextual Subgraph Envelopes

- **TAG Envelope Retrieval**: For each candidate pair $(e_A, e_B)$, queries the graph store for up to `subgraph_depth`
  hops of contextual neighborhood (adjacent chunk nodes and connected entities).
- **Context Synthesis**: Merges and deduplicates envelopes for $e_A$ and $e_B$ into a compact textual representation.

### 3. Cross-Encoder / System 1 Precision Reranking & Pair Gating

- **System 1 Binary Pair Gating (`use_jev_pair_gating`)**: Optionally filters candidate pairs via calibrated Jev `Noul` gating (`pair_gating_threshold`, `pair_gating_audit_rate`) before retrieving heavy graph envelopes.
- **Joint-Attention Scoring (`RelationReranker` Strategy)**: Evaluates candidate pairs and their contextual envelopes through `CrossEncoder` or `JevRelationReranker` (`use_jev_reranker`), allowing deep cross-referencing between concept contexts.
- **Threshold Filtering**: Only candidate pairs scoring above `reranker_threshold` proceed to LLM decoding.

### 4. LLM Relation Decoding & Within-Phase Checkpointing (`ADR-0016`)

- **Constrained Classification**: Structured prediction (`astructured_predict`) against `GlobalRelationOutput`.
- **Schema & Confidence Validation**: Validates extracted predicates against `SchemaConfig.relation_types` and `global_relation_confidence_threshold`.
- **Atomic Batch Checkpointing (`PhaseCheckpointStore`)**: Candidate pairs are filtered via `filter_unprocessed_items` (`:PhaseItem`) and committed atomically per batch via `commit_phase_batch`, enabling crash-safe mid-phase resumption.

## Workflow

```mermaid
flowchart TD
    A[Layer 2 Entities] --> B[DenseRetrievalGlobalRelationExtractor<br>MIPS Vector Similarity + Optional Jev Pair Gate]
    B --> B2[Filter Unprocessed Pairs<br>PhaseCheckpointStore :PhaseItem]
    B2 --> C[Retrieve TAG Subgraph Envelopes<br>depth = subgraph_depth]
    C --> D[RelationReranker<br>Cross-Encoder / Jev Reranker]
    D --> E{Reranker Score >= reranker_threshold?}
    E -->|Yes| F[LLM Structured Triple Decoding]
    E -->|No| H[Discard Pair]
    F --> G{Predicate in SchemaConfig &<br>Confidence >= Threshold?}
    G -->|Yes| J[Atomic Batch Commit<br>Global Triple + :PhaseItem Checkpoint]
    G -->|No| H
```

## Implementation Details

- [`pipeline_explanation.md`](pipeline_explanation.md) - Detailed implementation walkthrough
- [Design Patterns, Clean Code & Architectural Standards](../../architecture/design_patterns_and_standards.md) - Unit-of-Work batch checkpointing and Calibrated Cascade standards

## Configuration

Configuration is managed via `Phase3Config` in `episteme_pipeline/config.py`:

| Parameter                              | Type                         | Default        | Description                                                                  |
|:---------------------------------------|:-----------------------------|:---------------|:-----------------------------------------------------------------------------|
| `batch_size`                           | `int`                        | `50`           | Number of candidate pairs processed per checkpointed batch.                  |
| `dense_similarity_threshold`           | `float`                      | `0.5`          | Minimum cosine similarity between entity embeddings to form candidate pairs. |
| `reranker_threshold`                   | `float`                      | `0.6`          | Minimum reranker score required to pass candidates to LLM decoding.          |
| `global_relation_confidence_threshold` | `float`                      | `0.7`          | Minimum confidence score required for committed global relations.            |
| `max_candidates_per_entity_pair`       | `int`                        | `200`          | Maximum candidate partners permitted per entity hub.                         |
| `subgraph_depth`                       | `int`                        | `2`            | Hops of TAG neighborhood context retrieved per entity envelope.              |
| `global_relation_decoding_strategy`    | `StructuredDecodingStrategy` | `NL_TO_FORMAT` | Structured decoding strategy.                                                |
| `trace_dense_retrieval`                | `bool`                       | `True`         | Whether to emit telemetry events for candidate generation and reranking.     |
| `use_jev_reranker`                     | `bool`                       | `False`        | Whether to use calibrated Jev System 1 reranking instead of Cross-Encoder.   |
| `use_jev_pair_gating`                  | `bool`                       | `False`        | Whether to pre-filter candidate pairs with Jev binary `Noul` gating.         |
| `pair_gating_threshold`                | `float`                      | `0.75`         | Empirical accuracy threshold for Jev pair gating.                            |
| `pair_gating_audit_rate`               | `float`                      | `0.02`         | Stochastic audit rate for false-negative pair gating evaluation.             |

## Phase Contract

**Inputs:**

- Layer 2 entities from Phase 2 (from graph store or `Phase2ArtifactsView`).
- `SchemaConfig`: Taxonomy of valid global relation types.

**Outputs:**

- Phase 3 `ArtifactCollection` containing global relation envelopes.
- Global relation edges in Neo4j (`SchemaConfig.relation_types`) with properties:
    - `confidence`: float
    - `scope: "global"`
    - `source_chunk_id: None`

**Invariants:**

- Global relations connect entities with `scope="global"` to distinguish them from Phase 2 within-chunk triples.
- Unrecognized relation types outside `SchemaConfig` are discarded.

## Related

- **Theory**: [Epistemic Grounding & Dense Alignment](../../concepts/dense_alignment.md)
- **ADRs**: [ADR 0002: TAG Reranker Global Relation Extraction](../../adr/0002-tag-reranker-global-relation-extraction.md) | [ADR 0016: Phase 3 Within-Phase Checkpointing](../../adr/0016-phase-3-within-phase-checkpointing-and-atomicity.md)
- **Next Phase**: [Phase 3b: Latent Graph Consolidation](../3b_consolidation/)
