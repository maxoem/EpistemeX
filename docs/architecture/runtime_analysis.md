# Pipeline Runtime Analysis

This document provides an asymptotic runtime analysis of the Episteme pipeline. It details the computational complexity
of each phase with respect to the size of the input document corpus and analyzes real-world runtime behavior.

---

## Complexity Variables

* **$N$**: Total number of pages or raw input size.
* **$C$**: Total number of text chunks (directly proportional to $N$, i.e., $C \propto N$).
* **$E$**: Total number of extracted L2 entities. Generally, $E \propto C$.
* **$A$**: Total number of extracted theory atoms (argument components). Generally, $A \propto C$.
* **$R$**: Total number of extracted theory relations (argumentative edges between atoms).
* **$|\mathcal{C}|$**: Total number of empirical clusters identified for theoretical enrichment.
* **$|\mathcal{T}|$**: Total number of registered theory elements ($M_p, M_{pp}$).
* **$K$**: A constant bounding parameter (e.g., `max_candidates_per_entity_pair`, `arc_max_candidates_per_component`, `top_k_linking_candidates`).
* **$\boldsymbol{\mu}_e$**: Geometric centroid embedding of entity $e$ across its textual mention envelopes.
* **$T_{\text{ODE}}$**: Adaptive integration step count (`RK45`/`Radau`) for cyclic strongly connected components (SCCs) in continuous D-QBAF gradual semantics (whereas acyclic DAG components execute in a single closed-form topological pass).

---

## Phase-by-Phase Asymptotic Complexity

### Complexity Summary Table

| Phase | Dominant Operation | Asymptotic Complexity | Bottleneck Resource | Bounding Parameter |
|:---|:---|:---|:---|:---|
| **Phase 1: Foundation** | Chunking & Embedding | $O(N)$ | Embedding API | `chunk_size` |
| **Phase 2: Entity Discovery** | NER & Entity Linking | $O(C) + O(E \log E)$ | LLM Structured Output | `top_k_linking_candidates` ($K=10$) |
| **Phase 3: Global Relations** | Dense Cosine + Cross-Encoder | $O(E^2) + O(E \cdot K)$ | Cross-Encoder GPU / LLM | `max_candidates_per_entity_pair` ($K=200$) |
| **Phase 3b: Consolidation** | Entity Cosine Similarity | $O(E^2)$ | In-memory Vector Math | `dense_similarity_threshold` ($0.85$) |
| **Phase 4: Argument Mining** | ADU / ACC (Local) + ARC (Global) | $O(C) + O(A \cdot K)$ | LLM Structured Output | `arc_max_candidates_per_component` ($K=10$) |
| **Phase 4: Maturation** | Centroid Text Synthesis | $O(E)$ | LLM Structured Output | `maturation_top_k` ($5$) |
| **Phase 5: Fusion** | Community Leiden Detection | $O(V \log V)$ | Neo4j GDS / In-Memory Graph | Resolution parameters |
| **Phase 6: TheoryNet** | Continuous D-QBAF Equilibrium | $O(\vert A\vert + \vert R\vert)$ (DAG) / $O(T_{\text{ODE}} \cdot (\vert A_{\text{cyc}}\vert + \vert R_{\text{cyc}}\vert))$ (Cyclic) | Closed-Form DAG / Adaptive ODE Solver | `rtol`, `atol`, `max_time` |
| **Post-Processing** | Theoretical Enrichment & Coupled Re-Convergence | $O(\vert\mathcal{C}\vert \cdot \vert\mathcal{T}\vert) + O(\vert A\vert + \vert R\vert)$ | LLM Structured Output + D-QBAF Re-Convergence | Number of Theories $\mathcal{T}$ |

---

### Detailed Phase Breakdown

#### Phase 1: Foundation (Chunking & Embedding)

* **Text Chunking**: $O(N)$
* **Chunk Embedding**: $O(C)$ dense embedding calls.
* **Overall Complexity**: **$O(N)$**

#### Phase 2: Entity & Local Relation Discovery

* **NER Extraction**: One LLM structured prediction call per chunk. $O(C)$ LLM calls.
* **Entity Linking**: For each entity, a dense similarity search against the existing graph, returning top-$K$
  candidates, followed by cross-encoder reranking. Retrieval is $O(\log E)$ or $O(E)$ (depending on the vector index),
  and reranking is $O(K)$. Over $E$ entities, this takes $O(E \log E)$ or $O(E^2)$.
* **Overall Complexity**: **$O(C)$** LLM calls + **$O(E \log E)$** linking overhead.

#### Phase 3: Global Relation Extraction

This phase identifies relationships between entities globally across chunk boundaries using dense retrieval,
cross-encoder reranking, and LLM decoding.

* **Dense Candidate Generation**: Computes embeddings for all $E$ entities and calculates an $E \times E$ cosine
  similarity matrix. $O(E^2)$ similarity computations.
* **Candidate Filtering**: Selects the top $K$ (`max_candidates_per_entity_pair`) similar partners per entity. Generates
  bounded candidate pairs: $O(E \cdot K)$.
* **Reranking**: A cross-encoder model evaluates each candidate pair. $O(E \cdot K)$ cross-encoder inferences.
* **LLM Extraction**: Pairs scoring above `reranker_threshold` are sent to the LLM. Bounded by $O(E \cdot K)$ but
  typically $O(E)$ in practice due to thresholding.
* **Overall Complexity**: **$O(E^2)$** similarity + **$O(E \cdot K)$** cross-encoder/LLM calls.

#### Phase 3b: Latent Consolidation

* **Similarity Matrix**: Computes $O(E^2)$ cosine similarities between all entities.
* **Overall Complexity**: **$O(E^2)$** vector comparisons.

#### Phase 4: Argument Mining

* **ADU Segmentation & ACC Classification**: Local to each chunk. $O(C)$ LLM calls.
* **ARC (Global Argument Relations)**:
    * Similar to Phase 3, computes dense similarities for all $A$ theory atoms: $O(A^2)$.
    * Selects top $K$ (`arc_max_candidates_per_component`) partners per theory atom, yielding $O(A \cdot K)$ candidate pairs.
    * Uses LLM structured prediction on *all* generated candidate pairs (no cross-encoder filter step). $O(A \cdot K)$ LLM calls.
* **Overall Complexity**: **$O(C)$** local LLM calls + **$O(A \cdot K)$** global ARC LLM calls + $O(A^2)$ similarity checks.

#### Phase 4: Entity Maturation

* Synthesizes canonical descriptions for mature entities via geometric centroid calculation $\boldsymbol{\mu}_e$ across textual envelopes.
* **Overall Complexity**: **$O(E)$** LLM calls.

#### Phase 5: Fusion (Clustering & Canonicalization)

* **Clustering**: Modularity-based community detection algorithms (e.g., Hierarchical Leiden) over the graph structure. Complexity is
  roughly $O(V \log V)$ or $O(V + \mathcal{E})$ where $V$ is nodes and $\mathcal{E}$ is edges.
* **Overall Complexity**: **$O(E \log E)$** or near-linear in graph size.

#### Phase 6: TheoryNet Construction & Continuous D-QBAF Gradual Semantics

* Maps Phase 4/5 canonical theory atoms and relations into the formal $\mathcal{G}_{\text{TheoryNet}}$ model ([ADR-0011 Addendum 2](../adr/0011-declarative-graph-metrics-and-qbaf-semantics.md), [ADR-0022](../adr/0022-unified-stratified-epistemic-metamodel.md)).
* **Acyclic Graphs (DAGs)**: Solves equilibrium justification degrees $\tau^*(a)$ in a single exact closed-form topological pass via Kahn's algorithm in **$O(|A| + |R|)$** time with zero iteration overhead.
* **Cyclic Graphs**: Integrates the continuous dynamical system $\frac{ds_i(t)}{dt} = -s_i(t) + \sigma(\text{logit}(\tilde{\tau}_0(a_i)) + E_i(s(t)))$ over cyclic subgraphs using adaptive Runge-Kutta (`RK45`) or implicit `Radau` ODE integration with terminal root-finding (`||ds/dt||_\infty < 10^{-5}`), scaling as **$O(T_{\text{ODE}} \cdot (|A_{\text{cyc}}| + |R_{\text{cyc}}|))$**.
* **Overall Complexity**: **$O(|A| + |R|)$** for DAGs; **$O(T_{\text{ODE}} \cdot (|A_{\text{cyc}}| + |R_{\text{cyc}}|))$** for cyclic components.

#### Post-Processing: Theoretical Enrichment & Coupled D-QBAF Re-Convergence

* Projects empirical clusters $\mathcal{C}$ into theoretical parametric spaces ($M_p$) across registered theory elements $\mathcal{T}$.
* Evaluates local tenability ($TS_{\text{local}}$) and intertheoretical edge tenability ($TS_{\text{edge}}$) via bounded blur constraints: $O(|\mathcal{C}| \cdot |\mathcal{T}|)$ structured LLM/optimization calls.
* Executes an incremental D-QBAF re-convergence pass over tenability-modulated node priors $\tilde{\tau}_0(a) = \tau_0(a) \cdot TS_{\text{local}}(a)$ and edge weights $W_{ji} \cdot TS_{\text{edge}}(e)$ in $O(|A| + |R|)$ time.
* **Overall Complexity**: **$O(|\mathcal{C}| \cdot |\mathcal{T}|) + O(|A| + |R|)$**.

---

## Intended vs. Observed Behavior

### The Intended Runtime Complexity

The pipeline was architected to avoid the catastrophic **$O(N^2)$** LLM scaling typically associated with global
all-to-all relation extraction over large corpora. By utilizing vector similarity to generate a bounded set of
candidates (top $K$), the heavy operations (Cross-Encoder inference and LLM decoding) are capped at **$O(N \cdot K)$**.
For large document sets ($N \gg K$), this ensures the pipeline scales linearly with the input size rather than
quadratically.

### The "Small Input" Overhead (e.g., One-Page Documents)

For extremely small inputs (e.g., a single page or short excerpt), users may observe disproportionately long runtimes. This occurs
because when $N$ is small, the number of entities $E$ and atoms $A$ is typically smaller than the $K$ bounding
parameters (e.g., $K=200$ for Phase 3, $K=10$ for ARC).

When $E < K$, the bounds do not prune the search space. The pipeline falls back to evaluating *every possible pair*
($O(N^2)$). While $O(N^2)$ on small $N$ is theoretically trivial, the **constant factor** is extremely high:

1. **Phase 3 Reranker**: An $O(E^2)$ pair evaluation means making hundreds of sequential or batched cross-encoder
   inferences.
2. **Phase 4 ARC**: Evaluates all $O(A^2)$ theory atom pairs directly using the LLM (since there is no reranker
   filter). For just 15 theory atoms, this triggers ~100 LLM calls.

Additionally, the dense similarity threshold (`dense_similarity_threshold: 0.5`) in Phase 3 is overly permissive for
models like `all-MiniLM-L6-v2`, where cosine similarities are often naturally clustered above 0.5. As a result, almost
all pairs bypass the dense filter, overwhelming the cross-encoder and LLM.

**Conclusion**: The pipeline is highly optimized for asymptotic scaling on large datasets ($O(N \cdot K)$) but incurs notable
constant-factor overheads on small texts due to unpruned all-to-all evaluations. Tuning $K$ dynamically based on corpus size mitigates this effect.

---

## 4. Related Documentation

- **System Architecture**: [Pipeline Architecture](pipeline_architecture.md)
- **Artifact and Run Model**: [Artifact and Run Model](artifact_run_model.md)
- **Invalidation & Resume**: [Invalidation and Resume](invalidation_and_resume.md)
- **Dense Alignment**: [Dense Alignment & Grounding](../concepts/dense_alignment.md)
- **Configuration Tuning**: [Configuration Reference](../reference/config.md)

