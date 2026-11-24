# Phase 2: Entity Discovery

## Overview

Phase 2 extracts named entities, resolves within-chunk coreference, disambiguates entity identities against existing
nodes, and extracts local (within-chunk) semantic triples to construct **Layer 2 (Deterministic Ontology)** of the
theory graph.

## Purpose

This phase populates the knowledge graph with domain-schema-typed entity nodes and local semantic relations, maintaining
rigorous provenance (`EXTRACTED_FROM`) back to Layer 1 chunks.

## Theoretical Foundation

See [Epistemic Grounding & Dense Alignment](../../concepts/dense_alignment.md)
and [Episodic Working Memory](../../concepts/episodic_working_memory.md) for the theoretical foundations:

- Symmetrical Textual Envelopes ($T_n$)
- Dual-Space Dense Alignment & Canonical Disambiguation
- [Episodic Working Memory](../../concepts/episodic_working_memory.md) (RAM-only state machine with Global Structural
  Anchors)
- [ADR 0003](../../adr/0003-coreference-absorbed-into-fusion.md) (Coreference resolution absorbed into prompt + Phase
  3b)

## Components

### 1. NER & Local Relation Extraction

- **Structured Prediction**: Structured LLM decoding (`astructured_predict`) guided by `SchemaConfig` entity and
  relation taxonomies.
- **Reasoning-First Chain-of-Thought**: CoT prompts prime the LLM to identify logical connectives before assigning
  entity labels and triples.
- **Iterative Gleaning & Actor-Critic Stopping Oracle**: When `gleaning.enabled` is active, gleaning is
  governed by `JevGleaningGate` (`episteme_pipeline/decision/gleaning.py`),
  decoupling the generative extraction *Actor* (LLM) from an objective non-generative *Critic* (TypeSafe Jev `Noul` evaluator).
  The gate budgets context to $\le 1024$ tokens / 3200 characters for ModernBERT compatibility, evaluates extraction completeness,
  and stops continuation as soon as $P(\text{unextracted}) < \tau_{\text{glean}}$ (eliminating redundant LLM tokens).
  A stochastic false-negative audit rate (default 2%) occasionally forces an additional pass to monitor stopping calibration.
  When disabled or when the decision engine is omitted, the loop falls back to fixed `gleaning.max_passes` bounds.
- **Deterministic ID Generation**: `_stable_entity_id(label, name)` generates deterministic SHA-256 hashes
  (`entity_<hash>`), ensuring identical names with identical labels map to the same node ID.

### 2. Episodic Working Memory (RAM-Only Context)

- **Global Structural Anchor (`GlobalStructuralAnchor`)**: Injects Table of Contents (ToC) or section outlines into
  prompts as an immutable global coordinate system.
- **Short-Term Memory State (`WorkingMemoryState`)**: Tracks short-lived variables (`active_entities`,
  `unresolved_references`, `current_argument_branch`) across sequential chunk iterations ($S_{i-1} \to S_i$) entirely in
  RAM (never committed to Neo4j).
- **Boundary-Based Eviction (`EpisodicEvictionHandler`)**: Automatically purges working memory on structural section
  boundaries or semantic triggers.

### 3. Entity Linking & Disambiguation (`EntityLinker` Strategy & Calibrated Cascade)

- **Pluggable Strategy Port (`EntityLinker`)**: Supports multiple disambiguation strategies (see [Design Patterns & Standards](../../architecture/design_patterns_and_standards.md)):
    - **`DenseEntityLinker`** (default when `embedding_model` is provided): Bi-encoder vector retrieval over symmetrical textual envelopes ($T_n$) paired with cross-encoder relational reranking.
    - **`JevEntityLinker` & `CascadingEntityLinker`**: System 1 calibrated `Choice` disambiguation with conformal prediction set gating ($C(X)$), escalating only multi-class ambiguous mentions ($|C(X)| > 1$) to `DenseEntityLinker`.
    - **`NameEntityLinker`**: Deterministic string containment and case-insensitive surface-form matching fallback when no embedding model is configured.
- **Canonical ID Redirection**: Matched entities have their IDs redirected to the canonical node, aggregating
  `source_chunk_ids` onto the canonical entity and updating local triples.
- **Cross-Chunk Deduplication Note**: Cross-chunk entity collision resolution is handled mathematically
  in [Phase 3b: Latent Graph Consolidation](../3b_consolidation/).

## Workflow

```mermaid
flowchart TD
    A[Layer 1 Chunk + Episodic State S_i-1] --> B[LLMNERExtractor<br>Structured CoT Extraction]
    B --> C[EntityLinker Strategy<br>Dense / Cascading Jev / Name]
    C --> D{Existing Match Found?}
    D -->|Yes| E[Redirect ID to Canonical Entity]
    D -->|No| F[Assign Stable Deterministic ID]
    E --> G[Update Triple Subject/Object IDs]
    F --> G
    G --> H[Graph Commit:<br>Entity Nodes, Local Triples, EXTRACTED_FROM]
    H --> I[EpisodicEvictionHandler<br>Update Working Memory State S_i]
```

## Implementation Details

- [`pipeline_explanation.md`](pipeline_explanation.md) - Step-by-step pipeline execution walkthrough
- [`prompting.md`](prompting.md) - LLM prompt templates and chain-of-thought strategy

## Configuration

Phase 2 behavior is configured via `Phase2Config` in `episteme_pipeline/config.py` (model selection is declared in
`ModelConfig`):

| Parameter                             | Type                         | Default        | Description                                                          |
|:--------------------------------------|:-----------------------------|:---------------|:---------------------------------------------------------------------|
| `batch_size`                          | `int`                        | `10`           | Number of chunks processed per batch.                                |
| `top_k_linking_candidates`            | `int`                        | `10`           | Maximum candidate entities considered during linking.                |
| `linking_confidence_threshold`        | `float`                      | `0.85`         | Minimum confidence score required to redirect to an existing entity. |
| `ner_confidence_threshold`            | `float`                      | `0.0`          | Minimum confidence threshold for entity acceptance.                  |
| `local_relation_confidence_threshold` | `float`                      | `0.0`          | Minimum confidence threshold for local triple acceptance.            |
| `ner_decoding_strategy`               | `StructuredDecodingStrategy` | `NL_TO_FORMAT` | Decoding strategy (`DIRECT`, `NL_TO_FORMAT`, `TRIGGER_TOKEN`).       |
| `gleaning`                            | `GleaningConfig`             | `default`      | Encapsulated gleaning config (`enabled`, `confidence_threshold`, `audit_rate`, `max_passes`). |

## Phase Contract

**Inputs:**

- Layer 1 chunks (from Phase 1 artifact view or `get_unprocessed_chunks("phase2")`).
- `SchemaConfig`: Domain entity types (`node_types`) and relation types (`relation_types`).

**Outputs:**

- Phase 2 `ArtifactCollection` containing extracted entities, local relations, and linking decisions.
- Layer 2 nodes and edges in Neo4j:
    - Entity nodes (`id`, `name`, `description`, `source_chunk_ids`)
    - Local relation edges (`confidence`, `scope: "local"`, `source_chunk_id`)
    - `EXTRACTED_FROM` relationships: Entity $\to$ Chunk (`confidence: 1.0`)
    - `Chunk.phase2_processed = true`

**Invariants:**

- Every entity has a deterministic ID based on its label and canonical name.
- Local relations only connect entities co-occurring in the same chunk.
- Unknown entity or relation labels outside `SchemaConfig` are dropped.

## Related

- **Theory**: [Epistemic Grounding & Dense Alignment](../../concepts/dense_alignment.md)
- **Architecture**: [ADR 0009: Episodic Working Memory](../../adr/0009-sota-dual-memory-episodic-working-memory.md)
- **Next Phase**: [Phase 3: Global Relation Extraction](../3_relation_extraction/)
- **Consolidation**: [Phase 3b: Latent Graph Consolidation](../3b_consolidation/)
