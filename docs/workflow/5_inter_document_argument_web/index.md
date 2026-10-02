# Phase 5: Alignment & Theory Fusion

## Overview

Phase 5 groups semantically equivalent argument components across documents and performs theory-level graph clustering.
It operates on the extracted Layer 3 argument structures to assemble the cross-document argument web and discover
theoretical communities.

## Purpose

While Phase 4b extracts argument components within documents and connects pairs across chunks, Phase 5 performs
macro-level synthesis: it clusters similar claims across distinct authors and texts, elects representative key points,
and applies hierarchical community detection to detect theoretical paradigms.

## Theoretical Foundation

See [Formal Graph Schema (TheoryNet)](../../concepts/formal_graph_model.md)
and [ADR 0005: Two-Pass Fusion Strategy](../../adr/0005-two-pass-fusion-strategy.md):

- Argument component clustering via dense vector cosine similarity
- Representative argument election for Key Point Analysis
- Hierarchical Leiden community detection over the global Theory Graph

## Components

### 1. Argument Component Clustering

- **Batch Embedding**: Argument component texts are embedded concurrently via `embed_model.aget_text_embedding_batch()`.
- **Cosine Similarity Matrix**: Normalised dot product matrix is computed over all component pairs.
- **Union-Find Clustering**: Component pairs exceeding `fusion_similarity_threshold` (default: 0.85) are merged into
  clusters.
- **Representative Election**: The component with the highest mean cosine similarity to peers is elected as the cluster
  representative.

### 2. Theory-Level Fusion & Community Detection
 
- **Leiden Graph Clustering (`LeidenTheoryClustering`)**: Builds a global graph of entities, argument components, and
  relations.
- **Modularity Optimization**: Applies hierarchical Leiden community detection to discover cohesive theoretical
  sub-networks.
- **Graph Updates**: Writes `Community` nodes and `IN_COMMUNITY` edges back to the graph store when
  `theory_fusion_enabled = True`.

### 3. Semantic Theory Fusion Gate & Conformal Calibration

- **Semantic Gate (`verify_inter_document_cluster`)**: When `enable_fusion_gating = True`, candidate clusters and community
  partitions are validated via Jev `Choice` over `["EQUIVALENT_FUSION", "COMPETING_THEORIES", "DISTINCT_APPLICATIONS"]`.
  Clusters are only approved if `EQUIVALENT_FUSION` is contained in the calibrated conformal prediction set or if empirical
  accuracy meets `fusion_confidence_threshold`.
- **Conformal Prediction Guard (`ConformalCalibrator`)**: Replaces rigid scalar cutoffs with distribution-free prediction sets
  $C(X)$ guaranteeing $1 - \alpha$ (95%) coverage. Singleton sets ($|C(X)| = 1$) trigger fast-exit; multi-class or empty sets
  escalate to System 2 or human review.
- **Active Learning Queue**: High-entropy clusters producing ambiguous conformal sets ($|C(X)| > 1$) are tagged with
  `active_learning: True` and emitted to domain event streams for expert review and dataset curation.
- **Stochastic False-Negative Audit**: A configurable fraction of fast-exit clusters (`stochastic_audit_rate`, default 2%)
  is routed to System 2 to monitor against catastrophic epistemic conflation and detect calibration drift.

## Workflow

```mermaid
flowchart TD
    A[Layer 3 Argument Components] --> B[Concurrent Text Embedding]
    B --> C[Compute Pairwise Cosine Similarity]
    C --> D[Union-Find Clustering<br>threshold = fusion_similarity_threshold]
    D --> E[Elect Representative Component<br>Highest Mean Centroid Similarity]
    E --> F{theory_fusion_enabled = True?}
    F -->|Yes| G[LeidenTheoryClustering<br>Hierarchical Community Detection]
    F -->|No| H[Skip Community Commit]
    G --> I[Graph Commit:<br>Community Nodes, IN_COMMUNITY Edges]
    H --> J[Emit Phase 5 Artifacts]
    I --> J
```

## Implementation Details

- [`pipeline_explanation.md`](pipeline_explanation.md) - Detailed step-by-step implementation walkthrough

## Configuration

Configuration is managed via `Phase5Config` in `pipeline/config.py`:

| Parameter                     | Type                 | Default          | Description                                                      |
|:------------------------------|:---------------------|:-----------------|:-----------------------------------------------------------------|
| `argument_clustering_enabled` | `bool`               | `True`           | Whether to cluster semantically equivalent argument components.  |
| `theory_fusion_enabled`       | `bool`               | `False`          | Whether to execute hierarchical Leiden community detection.      |
| `fusion_similarity_threshold` | `float`              | `0.85`           | Minimum cosine similarity required to merge argument components. |
| `cluster_layer`               | `str`                | `"theory_atoms"` | Layer to cluster (`"theory_atoms"`, `"l2_entities"`, `"both"`).  |
| `gating`                      | `FusionGatingConfig` | `default`        | Encapsulated configuration for calibrated theory fusion gating.  |
| `gating.enabled`              | `bool`               | `False`          | Whether to verify candidate theory clusters using Jev decision engine. |
| `gating.conformal_alpha`      | `float`              | `0.05`           | Conformal significance level defining error rate ($\alpha=0.05 \implies 95\%$ coverage). |
| `gating.confidence_threshold` | `float`              | `0.85`           | Fallback empirical accuracy threshold for approving inter-document fusion. |
| `gating.audit_rate`           | `float`              | `0.02`           | Probability (2%) of routing fast-exit decisions to System 2 / Langfuse. |

## Phase Contract

**Inputs:**

- `Phase4ArtifactsView`: Cumulative collection of `TheoryAtom` and `TheoryRelation` artifacts.

**Outputs:**

- Phase 5 `ArtifactCollection` containing cluster envelopes and fusion decisions.
- Graph updates (when enabled):
    - `Community` nodes
    - `IN_COMMUNITY` relationships: `TheoryAtom / Entity -> Community`

**Invariants:**

- Clusters must have a minimum size of 2 components.
- The elected representative component is strictly the member with highest mean similarity to cluster peers.

## Related

- **Theory**: [Formal Graph Schema (TheoryNet)](../../concepts/formal_graph_model.md)
- **Previous Phase**: [Phase 4b: Argument Mining](../4_argument_mining/)
- **Next Phase**: [Phase 6: TheoryNet Projection](../6_theorynet/)
