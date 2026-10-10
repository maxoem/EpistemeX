# Phase 5: Alignment & Theory Fusion

## Overview

Phase 5 (Theory Fusion & Argument Clustering) runs after Phase 4b Argument Mining in the pipeline sequence:

```
Phase 1 → Phase 2 → Phase 3 → Phase 3b → Phase 4 (Maturation) → Phase 4b (Argument Mining) → Phase 5 → Phase 6
```

While pre-Phase 4 entity consolidation is handled mathematically by **Phase 3b: Latent Graph Consolidation**
(`Phase3bLatentConsolidationRunner`), **Phase 5** (`Phase5ArgumentWebRunner` in
`pipeline/phases/phase5_fusion/argument_web.py`) operates on the extracted Layer 3 theory argument structures.

It groups semantically equivalent argument components across documents and performs theory-level graph clustering,
enabling cross-document argument analysis and Theoriennetz (TF) community detection.

## Goals

- Cluster semantically equivalent `ArgumentComponent` nodes using embedding cosine similarity.
- Identify representative argument components per cluster for Key Point Analysis.
- Apply community detection over the global Theory Graph using hierarchical Leiden clustering
  (`LeidenTheoryClustering`).

## Steps

1. **Component Loading**: All `ArgumentComponent` nodes are loaded from the graph via `get_argument_components()`.
2. **Embedding**: Component texts are embedded concurrently via `embed_model.aget_text_embedding_batch()`.
3. **Cosine Similarity**: A normalised similarity matrix is computed over all component pairs (numpy dot product on
   L2-normalised embeddings).
4. **Connected Components (`_union_find_components`)**: Pairs above `Phase5Config.fusion_similarity_threshold` (default
   0.85) are merged via union-find. Only clusters of size $\ge 2$ are retained.
5. **Cluster Output & Representative Election**: Each cluster is returned as a list of component IDs. The component with
   the highest mean similarity to cluster peers is elected as the cluster representative.
6. **Calibrated Fusion Gating (`InterDocumentClusterVerifier`)**: When `Phase5Config.gating.enabled = True`, candidate
   macro-clusters are evaluated by `InterDocumentClusterVerifier` using `ConformalCalibrator`. Distribution-free conformal
   prediction sets $C(X)$ guarantee $P(Y \in C(X)) \ge 1 - \alpha$ (95% coverage at $\alpha=0.05$). Singleton sets
   `{"EQUIVALENT_FUSION"}` fast-exit in sub-second inference; multi-class sets are rejected from merging and queued for
   active learning review in Langfuse.
7. **Theory-Level Fusion (Optional)**: `LeidenTheoryClustering` builds a global NetworkX graph of entities and
   relations, applies modularity optimization via Hierarchical Leiden, and writes community assignments back to the
   graph store. When fusion gating is enabled, Leiden community candidates must also pass `cluster_verifier` approval before
   being committed to the graph. Activation requires `Phase5Config.theory_fusion_enabled = True`.

## Phase Data Flow

- **Input:** `Phase4ArtifactsView` (cumulative collection of theory atoms and relations).
- **Output:** Phase 5 cluster and fusion-decision artifacts.
- **Graph updates:**
    - `Community` nodes representing theoretical communities/clusters.
    - `IN_COMMUNITY` edges linking entities and argument components to their community nodes.

## Pluggability

- **Argument Clustering**: Implement `ArgumentClustering(ABC)` and inject via
  `Phase5ArgumentWebRunner(clustering=MyClustering())`.
- **Theory Fusion**: Implement `TheoryFusion(ABC)` and inject via `Phase5ArgumentWebRunner(theory_fusion=MyFusion())`.
  Requires `Phase5Config.theory_fusion_enabled = True`.
- **Similarity Threshold**: Configured via `Phase5Config.fusion_similarity_threshold` (default: 0.85).
- **Embedding Model**: Any LlamaIndex `BaseEmbedding` or `EmbeddingModel` protocol; injected via
  `Pipeline.for_task(embedding_model=...)`.

## ADR References

- [ADR 0003: Coreference Absorbed into Fusion](../../adr/0003-coreference-absorbed-into-fusion.md)
- [ADR 0005: Two-Pass Fusion Strategy](../../adr/0005-two-pass-fusion-strategy.md)
- [ADR 0007: TF Structural Correspondence](../../adr/0007-tf-structural-correspondence.md)

## Implementation

- `pipeline/phases/phase5_fusion/argument_web.py` — `Phase5ArgumentWebRunner`
- `pipeline/phases/phase5_fusion/argument_clustering.py` — `EmbeddingArgumentClustering`
- `pipeline/phases/phase5_fusion/leiden_clustering.py` — `LeidenTheoryClustering`
- `pipeline/phases/phase5_fusion/models.py` — `EntitySamenessOutput`
- `pipeline/protocols/fusion.py` — `ArgumentClustering(ABC)`, `TheoryFusion(ABC)`
