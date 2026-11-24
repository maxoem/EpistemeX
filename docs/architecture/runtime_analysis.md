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
| **Phase 3: Global Relations** | CSLS + Adaptive $K_{\text{eff}}(E)$ + Cross-Encoder | $O(E^2) + O(E \cdot K_{\text{eff}}(E))$ | Cross-Encoder GPU / LLM | $K_{\text{eff}}(E) = \min(K_{\max}, \max(K_{\min}, \lceil \gamma\sqrt{E}\rceil))$ |
| **Phase 3b: Consolidation** | CSLS Similarity + Adaptive $K_{\text{eff}}(E)$ | $O(E^2) + O(E \cdot K_{\text{eff}}(E))$ | In-memory Vector Math / Jev Verifier | `use_csls=True`, `z_score_threshold`, $K_{\text{eff}}(E)$ |
| **Phase 4: Argument Mining** | ADU / ACC (Local) + ARC (Global) | $O(C) + O(A \cdot K_{\text{eff}}(A))$ | System 1 Jev Triage + LLM Fallback | $K_{\text{eff}}(A)$ (`arc_max_candidates_per_component`) |
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

This phase identifies relationships between entities globally across chunk boundaries using Cross-Domain Similarity Local Scaling (CSLS), adaptive candidate degree bounding $K_{\text{eff}}(E)$, cross-encoder / System 1 reranking, and LLM decoding.

* **CSLS Candidate Generation**: Computes embeddings for all $E$ entities and calculates an $E \times E$ CSLS similarity matrix $\text{CSLS}(\mathbf{u}, \mathbf{v}) = 2\cos(\mathbf{u}, \mathbf{v}) - r_T(\mathbf{u}) - r_T(\mathbf{v})$, penalizing hub nodes and correcting for embedding anisotropy ($O(E^2)$ vectorized matrix operations).
* **Adaptive Candidate Filtering ($K_{\text{eff}}(E)$ & Z-Score)**: Bounds the per-entity candidate degree to $K_{\text{eff}}(E) = \min(K_{\max}, \max(K_{\min}, \lceil \gamma\sqrt{E}\rceil))$ and optionally applies standardized z-score filtering (`z_score_threshold`), generating $O(E \cdot K_{\text{eff}}(E))$ candidate pairs.
* **Reranking**: A cross-encoder or calibrated System 1 `JevRelationReranker` evaluates each candidate pair in $O(E \cdot K_{\text{eff}}(E))$ inferences.
* **LLM Extraction**: Pairs scoring above `reranker_threshold` are sent to the LLM. Bounded by $O(E \cdot K_{\text{eff}}(E))$ and typically $O(E)$ in practice.
* **Overall Complexity**: **$O(E^2)$** vectorized CSLS + **$O(E \cdot K_{\text{eff}}(E))$** cross-encoder/LLM calls.

#### Phase 3b: Latent Consolidation

* **CSLS & Z-Score Similarity Matrix**: Computes $O(E^2)$ CSLS similarities (`use_csls=True`) and optional standardized z-scores (`z_score_normalize`) across all entities.
* **Adaptive $K_{\text{eff}}(E)$ Candidate Pruning**: Evaluates 1-hop relation Jaccard overlap and borderline System 1 verification on at most $K_{\text{eff}}(E)$ top-ranked same-label partners per entity ($O(E \cdot K_{\text{eff}}(E))$), followed by clique-constrained connected components (`min_internal_similarity`, `max_diameter`).
* **Overall Complexity**: **$O(E^2)$** vectorized similarity + **$O(E \cdot K_{\text{eff}}(E))$** structural/verifier checks.

#### Phase 4: Argument Mining

* **ADU Segmentation & ACC Classification**: Local to each chunk. $O(C)$ LLM / System 1 cascade calls.
* **ARC (Global Argument Relations)**:
    * Computes CSLS similarities (`arc_use_csls=True`) for all $A$ theory atoms in $O(A^2)$ vectorized operations.
    * Bounds candidate partners per atom using $K_{\text{eff}}(A) = \min(K_{\max}, \max(K_{\min}, \lceil \gamma\sqrt{A}\rceil))$ (`arc_use_adaptive_k=True`) and optional `arc_z_score_threshold`, yielding $O(A \cdot K_{\text{eff}}(A))$ candidate pairs.
    * Routes candidate pairs through `CascadingARCClassifier` (System 1 `JevARCClassifier` conformal triage $\to$ System 2 `TAGARCClassifier` LLM fallback only for ambiguous or audited pairs).
* **Overall Complexity**: **$O(C)$** local calls + **$O(A \cdot K_{\text{eff}}(A))$** global ARC evaluations + $O(A^2)$ vectorized similarity checks.

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

### Mitigating Small-Input Overhead & Embedding Anisotropy (`ISSUE-051`)

Historically, fixed degree caps (e.g., $K=200$ in Phase 3, $K=10$ in Phase 4 ARC) and raw cosine cutoffs (`0.5` or `0.85`) suffered from two pathologies:
1. When $E < K$ or $A < K$ on small texts, static top-$K$ caps failed to prune the search space, degenerating into all-to-all $O(E^2)$ / $O(A^2)$ pair evaluations.
2. High-dimensional transformer embeddings (`all-MiniLM-L6-v2`, `bge-m3`, `text-embedding-3-large`) exhibit narrow anisotropic cones and hubness, causing raw cosine similarities to cluster above fixed scalar thresholds.

Episteme resolves both pathologies across **Phase 3, Phase 3b, and Phase 4 ARC** (`TAGARCClassifier` and `JevARCClassifier`):
1. **Cross-Domain Similarity Local Scaling (CSLS)**: Subtracts each node's mean $T$-nearest-neighbor cosine similarity $r_T(\mathbf{u})$, removing model-specific baseline anisotropy and penalizing hub vectors.
2. **Dynamic Sub-Linear Candidate Degree $K_{\text{eff}}(n)$**: Scales the per-node candidate cap sub-linearly with population size $n \in \{E, A\}$:
   $$K_{\text{eff}}(n) = \min\big(K_{\max},\; \max(K_{\min},\; \lceil \gamma \sqrt{n} \rceil)\big)$$
   ensuring small excerpts evaluate $O(n^{1.5})$ candidates rather than all $O(n^2)$ pairs while large corpora remain capped at $O(n \cdot K_{\max})$.
3. **Standardized Z-Score Pruning (`z_score_normalize`)**: Optional `z_score_threshold` filters candidate pairs against the empirical off-diagonal mean and standard deviation ($\mu + \tau_z \sigma$) of the similarity matrix.

---

## 4. Related Documentation

- **System Architecture**: [Pipeline Architecture](pipeline_architecture.md)
- **Artifact and Run Model**: [Artifact and Run Model](artifact_run_model.md)
- **Invalidation & Resume**: [Invalidation and Resume](invalidation_and_resume.md)
- **Dense Alignment**: [Dense Alignment & Grounding](../concepts/dense_alignment.md)
- **Configuration Tuning**: [Configuration Reference](../reference/config.md)

