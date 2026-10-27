# [ISSUE-107] Cross-Cutting Evaluation: Pillar 1 Structural & Topological Metrics (`structural_topology/*`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-107` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Cross-Cutting (Pillar 1: Structural & Topological Metrics) |
| **Evaluated Docs** | [`index.md`](../../docs/concepts/theory/metrics/structural_topology/index.md), [`bottleneck_fragility.md`](../../docs/concepts/theory/metrics/structural_topology/bottleneck_fragility.md), [`centrality.md`](../../docs/concepts/theory/metrics/structural_topology/centrality.md), [`community_bridges.md`](../../docs/concepts/theory/metrics/structural_topology/community_bridges.md), [`connectedness.md`](../../docs/concepts/theory/metrics/structural_topology/connectedness.md), [`dag_property.md`](../../docs/concepts/theory/metrics/structural_topology/dag_property.md), [`hierarchical_conformity.md`](../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md), [`modesty.md`](../../docs/concepts/theory/metrics/structural_topology/modesty.md), [`modularity_clustering.md`](../../docs/concepts/theory/metrics/structural_topology/modularity_clustering.md), [`structural_elegance.md`](../../docs/concepts/theory/metrics/structural_topology/structural_elegance.md), [`structural_homogeneity.md`](../../docs/concepts/theory/metrics/structural_topology/structural_homogeneity.md), [`structural_refutability.md`](../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md), [`metrics/index.md`](../../docs/concepts/theory/metrics/index.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/graph/algorithms/`, `epistemic/poset_evaluation.py`, `analysis.py`), `episteme-pipeline` (`phases/phase5_fusion/leiden_clustering.py`) |
| **Priority** | **Critical** (Fundamental normative contradiction where Logical Integrity Prerequisites require a rooted DAG/Theory-Tree with $\kappa=1$ while Macro/Micro-Topology metrics demand cyclic biconnected regular graphs with $\kappa \ge 2$ and $\lambda_{\max} > 0$; contradictory `:SPECIALIZES` edge directions across files; architectural split-brain where Phase 5 Leiden lives in `episteme-pipeline` instead of `epistemetrics`; and complete absence of 9 of 11 composite/metric evaluators in `epistemetrics`) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-096`](structural_topology/ISSUE-096-BOTTLENECK-FRAGILITY.md)–[`ISSUE-106`](structural_topology/ISSUE-106-STRUCTURAL-REFUTABILITY.md), [`ISSUE-075`](ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-082`](ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md), [`ISSUE-087`](ISSUE-087-THEORY-DYNAMICS-CROSS-CUTTING.md), [`ISSUE-095`](ISSUE-095-EPISTEMIC-COHERENCE-CROSS-CUTTING.md), [`ISSUE-066`](../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md), [`ISSUE-067`](../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric suite's architectural/mathematical coherence · **Major** = significant cross-file conflict, redundancy, or domain mismatch · **Minor** = notation, alignment, or presentation issue.

---

## 1. Fundamental Intra-Pillar Topological Contradiction: Structuralist Theory-Tree Prerequisites ($\text{IsDAG} = 1, S_{\text{tree}} = 1 \implies \kappa = 1, \lambda_{\max} = 0$) vs. Network-Science Resilience & Centrality Ideals ($\kappa \ge 2, H_{\text{deg}} \to 1, C_{\text{eigen}} > 0$) — **Critical**

**Where.** [`structural_topology/index.md#L13-L45`](../../docs/concepts/theory/metrics/structural_topology/index.md#L13-L45), [`dag_property.md`](../../docs/concepts/theory/metrics/structural_topology/dag_property.md), [`hierarchical_conformity.md`](../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md) vs. [`bottleneck_fragility.md`](../../docs/concepts/theory/metrics/structural_topology/bottleneck_fragility.md), [`connectedness.md`](../../docs/concepts/theory/metrics/structural_topology/connectedness.md), [`structural_homogeneity.md`](../../docs/concepts/theory/metrics/structural_topology/structural_homogeneity.md), [`structural_refutability.md`](../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md), and [`centrality.md`](../../docs/concepts/theory/metrics/structural_topology/centrality.md).

**Finding.**
`structural_topology/index.md` (L33–38) establishes [`dag_property.md`](../../docs/concepts/theory/metrics/structural_topology/dag_property.md) and [`hierarchical_conformity.md`](../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md) as **mandatory Logical Integrity Prerequisites**:
> *"Prerequisite Checks: A theory must pass these before structural virtues (like Elegance or Fragility) can be meaningfully evaluated."*

However, a graph $G$ that passes both prerequisites ($\text{IsDAG}(G) = 1$ and $S_{\text{tree}}(G) = 1$, i.e. a single-rooted **Theory-Tree** anchored at $T_0$) **mathematically violates** the normative ideals of almost every other metric in `structural_topology/` if evaluated on the same graph:

| Metric | Normative Ideal Claimed in Spec | Mathematical Value on a Perfect Theory-Tree ($\text{IsDAG}=1, S_{\text{tree}}=1, \|V\| \ge 3$) | Resulting Contradiction |
| :--- | :--- | :--- | :--- |
| **`connectedness.md` & `bottleneck_fragility.md` ($\kappa, \lambda$)** | High $\kappa(G) \ge 2$, High $\lambda(G) \ge 2$ ("Highly Resilient / Classical Mechanics") | **$\kappa(G) = \lambda(G) = \delta(G) = 1$** (every tree has leaf nodes of degree $1$ and cut-vertex $T_0$) | Any graph with $\kappa(G) \ge 2$ is **2-vertex-connected (contains cycles)**, so it **cannot be a tree** ($S_{\text{tree}} < 1$)! |
| **`structural_homogeneity.md` & `bottleneck_fragility.md` ($H_{\text{node}}$)** | $H_{\text{node}}(G)/\log_2\|V\| \to 1.0$ (Regular mesh; no hubs) | Branching root $T_0$ ($\text{deg} \ge 2$) and leaves ($\text{deg} = 1$) force non-regular degree sequence | Only a $d$-regular graph achieves $1.0$; for $d \ge 2$, every $d$-regular graph is **cyclic** (cannot be a tree)! |
| **`structural_refutability.md` ($C_B(v), R_k$)** | Low $R_k$ ("Highly Resilient"); ranks nodes by Betweenness $C_B(v)$ | Root $T_0$ has **directed $C_B(T_0) = 0.0$** (in-degree $0$, never tested!) and **undirected $C_B(T_0) = \max$** (removing $T_0$ shatters the tree, giving maximal $R_1$!) | Directed betweenness is blind to $T_0$; undirected betweenness condemns $T_0$ as a "Dogmatic Bottleneck"! |
| **`centrality.md` ($C_{\text{eigen}}(v)$)** | High $C_{\text{eigen}}(T_0)$ on $G_{\text{struct}}$ ("Tacit Paradigm Core") | On any DAG ($\text{IsDAG}=1$), $A^{\text{struct}}$ is nilpotent ($\lambda_{\max} = 0$), so **$C_{\text{eigen}}(v)$ is $0/0$ undefined or identically zero**! | Passing `dag_property.md` ($\text{IsDAG}=1$) makes `centrality.md`'s Eigenvector Centrality **mathematically degenerate**! |
| **`dag_property.md` vs. `hierarchical_conformity.md` ($T_0$ SCCs)** | `dag_property.md`: $\|SCC(v)\| = 1$ everywhere ($\text{IsDAG}=1$) | `hierarchical_conformity.md` L34: Cooperating axioms in $T_0$ **must** form an SCC ($\|SCC\| > 1$) of mutual presupposition! | Uncondensed cooperating axioms pass `hierarchical_conformity.md` only by **violating `dag_property.md`**! |
| **`connectedness.md` ($\lambda_2$) vs. `modularity_clustering.md` ($h(G)$)** | `connectedness.md` & `structural_elegance.md`: **High $\lambda_2$** (which implies High $h(G) \ge \lambda_2/2$) is "Bulletproof / Elegant" | `modularity_clustering.md` L156–157: **Low $h(G)$** is "Differentiated research program", while **High $h(G)$** is "Unspecialized / Monolithic"! | Opposite normative interpretations of the exact same spectral bottleneck constant ($\lambda_2 \leftrightarrow h(G)$)! |

**Fix.**
Stratify Pillar 1 metrics across **three explicit, mathematically distinct graph projections** of `TheoryGraph`:
1. **Projection 1 — Vertical Specialization Poset ($G_{\text{spec}} = (V_{\text{TE}}, E_{\text{spec}})$, Directed DAG):**
   - Evaluates **Logical Integrity Prerequisites**: `dag_property.md` ($\text{IsDAG} = 1$, $\text{CircularityPenalty} = 0$) and `hierarchical_conformity.md` ($|B(N)| = 1$, $S_{\text{tree}}(\operatorname{TR}(G_{\text{spec}}))$), after condensing horizontal mutual-presupposition SCCs into macro `TheoryElement` nodes.
   - Evaluates **Structural Centrality ($C_{\text{struct}}$)** in `centrality.md` via **Transitive Descendant Reachability / Katz Centrality** (never Eigenvector Centrality!).
2. **Projection 2 — Multi-Relational Theoretical Coherence & Constraint Web ($G_{\text{coh}} = (V_{\text{L3}}, E_{\text{spec}} \cup E_{\text{constr}} \cup E_{\text{sup}})$, Undirected / Directed Support):**
   - Because horizontal constraints (`CONSTRAINS`), co-explanatory links (`COHERES_WITH`), and convergent empirical justifications (`SUPPORTS`, `EXPLAINS`) cross-link distinct specialization branches, $G_{\text{coh}}$ is **not** restricted to a tree.
   - Evaluates **Macro-Topology** (`connectedness.md` $\tilde{\lambda}_2(\mathcal{L}_{\text{norm}})$, `modesty.md` $M_{\text{norm}}$, `structural_elegance.md` $E_{\text{struct}}$) and **Micro-Topology** (`bottleneck_fragility.md`, `structural_homogeneity.md`, `structural_refutability.md`) over the **non-leaf 2-core or evidential justification paths**.
3. **Projection 3 — Global Multi-Paradigm Holon ($G_{\text{holon}}$, Signed / Community-Partitioned):**
   - Evaluates **Meso-Topology**: `modularity_clustering.md` (Signed Leiden / Modularity $Q$ and intra-cluster vs. inter-cluster conductance) and `community_bridges.md` (weighted $\operatorname{BCIR}$ over inter-community links $\Lambda_{\text{formal}}$).

---

## 2. Contradictory Edge Directions & Unregistered Relation Types Across Pillar 1 Specifications and Code — **Critical**

**Where.** [`dag_property.md#L34`](../../docs/concepts/theory/metrics/structural_topology/dag_property.md#L34), [`community_bridges.md#L35`](../../docs/concepts/theory/metrics/structural_topology/community_bridges.md#L35), [`centrality.md#L32-L35`](../../docs/concepts/theory/metrics/structural_topology/centrality.md#L32-L35), [`hierarchical_conformity.md#L35`](../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L35), [`#L43`](../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L43), [`#L58-L77`](../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L58-L77) vs. [`packages/epistemetrics/src/epistemetrics/core/models.py#L438-L454`](../../packages/epistemetrics/src/epistemetrics/core/models.py#L438-L454) and [`packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L174-L178`](../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L174-L178).

**Finding.**
1. **Opposite Directions of `:SPECIALIZES` and Hierarchical Edges Across Files:**
   - **Parent $\to$ Child ($T_{\text{general}} \to T_{\text{specific}}$, root has `in_degree == 0` and high `out_degree`):**
     - `epistemetrics/epistemic/poset_evaluation.py` (L177, L247): `T_i -> T_j where T_j specializes T_i`; roots have `in_degree == 0`.
     - `docs/reference/schema.md` (L90): `RootCore -->|"SPECIALIZES (α)"| SpecHyp`.
     - `centrality.md` (L49–52): Out-degree centrality $C_{\text{deg}}(v) = \frac{\text{deg}_{\text{out}}(v, G_{\text{struct}})}{|V|-1}$ identifies foundational cores.
     - `hierarchical_conformity.md` (L58, L60, L70): Roots $B(N)$ have `in-deg_spec == 0`.
   - **Child $\to$ Parent ($T_{\text{specific}} \to T_{\text{general}}$, root has `out_degree == 0` and high `in_degree`):**
     - `hierarchical_conformity.md` (L43 & Cypher query L75): `directed edges (u, v) in E indicate u specializes v`; `WHERE NOT (t)-[:SPECIALIZES]->(:TheoryElement)`!
     - `centrality.md` (L32): Includes `DEPENDS_ON` ($u \xrightarrow{\text{DEPENDS\_ON}} T_0$) in $G_{\text{struct}}$ alongside `SPECIALIZES`!
     - `dag_property.md` (L34) & `community_bridges.md` (L35): Pool `derives_from` ($u \xrightarrow{\text{derives\_from}} T_0$) with `explains` ($T_0 \xrightarrow{\text{explains}} u$), creating artificial 2-cycles $T_0 \rightleftarrows u$ ([`ISSUE-100` DP-01](structural_topology/ISSUE-100-DAG-PROPERTY.md))!
2. **Unregistered Edge Types Used Across Pillar 1 Docs:**
   Pillar 1 specifications filter on five edge types that **do not exist** in `epistemetrics.RelationType` (`models.py` L438–454):
   - `derives_from` (`dag_property.md` L34, `community_bridges.md` L35)
   - `DEPENDS_ON` (`centrality.md` L32)
   - `MENTIONED_IN` (`centrality.md` L35, L75)
   - `REFUTES` (`centrality.md` L35 — aliased to `ATTACKS` in `RelationType.from_str`)
   - `SHARES_VARIABLE` (`hierarchical_conformity.md` L35)

**Fix.**
1. Enforce the **Parent $\to$ Child** storage convention (`(general)-[:SPECIALIZES]->(specific)` and `(premise)-[:EXPLAINS]->(conclusion)`) across all 11 Pillar 1 documents and Cypher queries. If an alias like `derives_from` or `depends_on` is ingested via `RelationType.from_str`, invert its endpoints $(u, v) \mapsto (v, u)$ upon ingestion so all hierarchical edges share a single consistent orientation.
2. Replace unregistered edge labels in the specifications with canonical `epistemetrics.RelationType` enum values.

---

## 3. Architectural Split-Brain Between `episteme-pipeline` and `epistemetrics` (Phase 5 Leiden & Missing Evaluators) — **Critical**

**Where.** [`packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/leiden_clustering.py`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/leiden_clustering.py), [`packages/epistemetrics/src/epistemetrics/graph/algorithms/`](../../packages/epistemetrics/src/epistemetrics/graph/algorithms/), [`packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py`](../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py), and [`packages/epistemetrics/src/epistemetrics/analysis.py`](../../packages/epistemetrics/src/epistemetrics/analysis.py).

**Finding.**
The project architecture specifies that `epistemetrics` provides the topological algorithms and metric evaluators used both:
1. **During construction** (e.g., Phase 5 Theory Fusion via Leiden clustering), and
2. **After construction for evaluation** (computing the Pillar 1–5 metrics).

A systematic audit of `packages/epistemetrics/` and `packages/episteme-pipeline/` against the 11 specifications in `docs/concepts/theory/metrics/structural_topology/` reveals major gaps and package-boundary violations:

| Pillar 1 Document | Specified Mathematical Quantities | Status in `epistemetrics` | Discrepancies & Bugs in Existing Code |
| :--- | :--- | :--- | :--- |
| **1. `bottleneck_fragility.md`** | $(H_{\text{node}}, \kappa(G), R_k(G))$ | **Not implemented** | None of its 3 sub-metrics is implemented as a metric evaluator. |
| **2. `centrality.md`** | $C_{\text{deg}}$, $C_{\text{eigen}}$, $S_{\text{disc}}$, $AD(v)$ | **Partial** (`pagerank.py`, `eigenvector.py` only) | No $G_{\text{struct}} / G_{\text{disc}}$ projection or $AD(v)$ calculation; `eigenvector.py` fails/degenerates on DAGs. |
| **3. `community_bridges.md`** | Edge Betweenness $C_B(e)$, $\operatorname{BCIR}(G)$ | **Not implemented** | `betweenness.py` only computes *node* betweenness (and GDS has no edge betweenness); $\operatorname{BCIR}(G)$ is absent. |
| **4. `connectedness.md`** | WCC $|\pi_0(G)|$, $\kappa(G)$, $\lambda(G)$, $\lambda_2(G)$ | **Partial** (`wcc.py` only) | Vertex connectivity $\kappa(G)$, edge connectivity $\lambda(G)$, and Fiedler value $\lambda_2(G)$ are completely absent. |
| **5. `dag_property.md`** | $\text{IsDAG}(G)$, $\text{CircularityPenalty}(G)$ | **Partial** (`poset_evaluation.py`, `analysis.py`) | `analysis.py` L145 runs `is_directed_acyclic_graph` on the **unfiltered** graph (failing on any mutual attack/coherence edge); `CircularityPenalty` is unimplemented. |
| **6. `hierarchical_conformity.md`** | $B(N)$, $S_{\text{tree}}(G)$, $T_0$ SCC condensation | **Partial** (`poset_evaluation.py`) | `find_poset_roots` (L252) **drops isolated roots (`out_degree == 0`)** when other edges exist; $S_{\text{tree}}(G)$ and $T_0$ SCC condensation are unimplemented. |
| **7. `modesty.md`** | $M(H) = \frac{\|V_H\|(\|V_H\|-1)}{2\|E_H\|}$ | **Not implemented** | `analysis.py` L140 computes directed $\rho = \frac{\|E\|}{\|V\|(\|V\|-1)}$ (differing by $2\times$ from `modesty.md`); $M(H)$ is absent. |
| **8. `modularity_clustering.md`** | Leiden, Louvain, Modularity $Q$, 1-Laplacian $\mu_2 = h(G)$, Assortativity $r$, Permutation $p$-value | **Split-Brain** (`louvain.py` in `epistemetrics`; `leiden_clustering.py` in `episteme-pipeline`) | **Leiden is in `episteme-pipeline` (calling `graspologic` directly) and missing from `epistemetrics`!** Both ignore negative `:ATTACKS` polarity; `PartitionResult` omits $Q$; $h(G)$, $r$, and permutation tests are unimplemented. |
| **9. `structural_elegance.md`** | $E(G) = \lambda_2(G) - \alpha \rho(G)$ | **Not implemented** | Absent from `epistemetrics`. |
| **10. `structural_homogeneity.md`** | $H_{\text{node}}$, $\text{Homogeneity}_{\text{struct}}$, $\sigma^2_{\text{deg}}$, Gini | **Not implemented** | Absent from `epistemetrics`. |
| **11. `structural_refutability.md`** | $\kappa(H)$, $\text{Refutability}_k(H)$ | **Not implemented** | Absent from `epistemetrics`. |

**Fix.**
1. Move/consolidate **Hierarchical Leiden & Signed Leiden Community Detection** into `packages/epistemetrics/src/epistemetrics/graph/algorithms/leiden.py` (with `GraphAlgorithmsEngine` protocol support and `modularity: float` on `PartitionResult`), and have `episteme_pipeline/phases/phase5_fusion/leiden_clustering.py` invoke `epistemetrics`.
2. Implement a cohesive `epistemetrics.epistemic.topology_evaluation` (or `epistemetrics.graph.metrics`) module providing all 11 corrected Pillar 1 evaluators with deterministic unit tests.

---

## 4. Systematic Algebraic Scaling & Normalization Defects Across Pillar 1 Formulas — **Major**

**Where.** [`structural_elegance.md#L55`](../../docs/concepts/theory/metrics/structural_topology/structural_elegance.md#L55), [`structural_homogeneity.md#L76`](../../docs/concepts/theory/metrics/structural_topology/structural_homogeneity.md#L76), [`structural_refutability.md#L54`](../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L54), [`modesty.md#L50`](../../docs/concepts/theory/metrics/structural_topology/modesty.md#L50), and [`hierarchical_conformity.md#L58`](../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L58).

**Finding.**
Across Pillar 1, five formulas exhibit severe algebraic scaling or boundary defects that falsify their own diagnostic tables:
1. **Complete-Graph Inversion in `structural_elegance.md` ([`ISSUE-104` SE-01](structural_topology/ISSUE-104-STRUCTURAL-ELEGANCE.md)):**
   Because unnormalized $\lambda_2(G) \le (|V|-1)\rho(G)$, $E(G) = \lambda_2(G) - \alpha \rho(G)$ is **globally maximized by the complete hairball $K_n$** ($E(K_n) = n - \alpha$) whenever $n > \alpha$, and globally maximized by the edgeless graph $\emptyset$ whenever $\alpha \ge n$.
2. **Unreachable Star Threshold in `structural_homogeneity.md` ([`ISSUE-105` SHM-01](structural_topology/ISSUE-105-STRUCTURAL-HOMOGENEITY.md)):**
   Because the hub of a star $K_{1, n-1}$ holds at most $50\%$ of total degree sum ($p_{\text{hub}} = 1/2$), $\text{Homogeneity}_{\text{struct}}(K_{1, n-1}) = \frac{1 + \frac{1}{2}\log_2(n-1)}{\log_2 n} > 0.50$ for **all** $n \ge 2$ (and $> 0.80$ for $n \le 8$), making the diagnostic category "$< 0.3$ = Extreme Star / Bottleneck" **mathematically impossible for any connected graph**!
3. **Histogram vs. Node-Share Entropy Inversion Between `metrics/index.md` L50 and `structural_homogeneity.md` L76 ([`ISSUE-105` SHM-02](structural_topology/ISSUE-105-STRUCTURAL-HOMOGENEITY.md)):**
   `metrics/index.md` L50 writes $H_{\text{deg}} = -\frac{1}{\ln |V|} \sum p(k) \ln p(k)$ over the degree histogram $p(k)$, which scores **$0.0$ on a perfectly homogeneous regular graph** (the exact opposite of `structural_homogeneity.md` L76, which scores $1.0$!).
4. **Independent vs. Cumulative Ablation & $k$-Shrinking Range in `structural_refutability.md` & `bottleneck_fragility.md` ([`ISSUE-096` BF-03](structural_topology/ISSUE-096-BOTTLENECK-FRAGILITY.md), [`ISSUE-106` SR-02](structural_topology/ISSUE-106-STRUCTURAL-REFUTABILITY.md)):**
   Summing $|\Pi(G \setminus \{v_i\})|$ over independent single-node removals fails to disconnect any graph with $\kappa(G) \ge 2$ and shrinks the baseline $\frac{1}{1+k} \to 0$ as $k$ increases.
5. **Linear Graph-Size Scaling in `modesty.md` ([`ISSUE-102` MD-01](structural_topology/ISSUE-102-MODESTY.md)):**
   On any tree, $M(\text{Tree}_n) = \frac{n}{2}$ grows linearly with node count $n = |V_H|$ rather than measuring size-invariant sparsity.

**Fix.**
Adopt bounded, size-invariant $[0, 1]$ normalizations across all five metrics:
- **Normalized Algebraic Connectivity:** $\tilde{\lambda}_2(\mathcal{L}_{\text{norm}}) \in [0, 1]$ (or $\frac{n-1}{n}\tilde{\lambda}_2 \in [0, 1]$).
- **Spanning-Tree Normalized Modesty:** $M_{\text{norm}}(H) = 1 - \frac{|E_{\text{simple}}| - (|V_H| - |\pi_0(H)|)}{\binom{|V_H|}{2} - (|V_H| - |\pi_0(H)|)} \in [0, 1]$.
- **Structural Elegance Index:** $\operatorname{SE}(G) = \tilde{\lambda}_2(\mathcal{L}_{\text{norm}}) \cdot M_{\text{norm}}(G)^\alpha \in [0, 1]$.
- **Star-Normalized Homogeneity / Gini Equality:** $\text{Homogeneity}_{\text{star-norm}}(G') = \frac{H_{\text{node}}(G') - H_{\text{node}}(K_{1, n-1})}{\log_2 n - H_{\text{node}}(K_{1, n-1})} \in [0, 1]$ and $1 - G_{\text{Gini}}^{\text{norm}}(G') \in [0, 1]$.
- **Cumulative Pair-Reachability Drop Refutability:** $R_k(H) = 1 - \frac{|\Pi_{\text{pairs}}(H \setminus \{v_1, \dots, v_k\})|}{|\Pi_{\text{pairs}}(H)|} \in [0, 1]$.

---

## 5. Non-Threatening Cross-File Inconsistencies & Notation Misalignments

| Issue | Locations | Details & Recommended Standardization |
| :--- | :--- | :--- |
| **1. Six-Way Symbol Collision on $\lambda$ Across Pillar 1** | `connectedness.md` L66 ($\lambda(G) \in \mathbb{N}_0$: edge connectivity)<br>`connectedness.md` L73 & `structural_elegance.md` L50 ($\lambda_2(G) \in \mathbb{R}_{\ge 0}$: Fiedler Laplacian eigenvalue)<br>`centrality.md` L59 ($\lambda$: principal adjacency eigenvalue)<br>`community_bridges.md` L23 ($\lambda \subseteq M_p(T_1) \times M_p(T_2)$: inter-theoretical link)<br>`community_bridges.md` L35, L50 & `structural_homogeneity.md` L44 ($\lambda_v, \lambda_e$: vertex/edge type labeling)<br>`modularity_clustering.md` L121 ($\lambda^k$: Cell Descent iterate) | Reserve $\lambda_v, \lambda_e$ for graph type labelings, $\lambda_2(L)$ (and $\tilde{\lambda}_2(\mathcal{L}_{\text{norm}})$) for the Fiedler Laplacian eigenvalue, $\rho_{\text{spec}}(A)$ for the adjacency spectral radius, $\kappa_e(G)$ for edge connectivity, and $GL$ for inter-theoretical link classes. |
| **2. Four-Way Symbol Collision on $\alpha$ Across Pillar 1** | `connectedness.md` L30, `dag_property.md` L14, L22, `hierarchical_conformity.md` L47 ($\alpha$: specialization relation on $T$)<br>`centrality.md` L68 ($\alpha \in \mathbb{R}_{\ge 0}$: PageRank weight in $S_{\text{disc}}$)<br>`structural_elegance.md` L55 ($\alpha \in \mathbb{R}_{\ge 0}$: density penalty hyperparameter in $E(G)$)<br>` epst/pagerank.py` L76 (`alpha`: PageRank damping factor $d$) | Use $\sigma$ (BMS standard) or $\preceq_{\text{spec}}$ for the specialization poset relation, $w_{\text{pr}}, w_{\text{freq}}$ in `centrality.md`, and $\gamma_{\text{mod}}$ in `structural_elegance.md`. |
| **3. Four-Way Symbol Collision on $\Pi$ / $\pi$ Across Pillar 1** | `bottleneck_fragility.md` L51, `modesty.md` L30, `structural_refutability.md` L54 ($\Pi(G)$: set of shortest/simple paths)<br>`connectedness.md` L56 ($|\pi_0(G)|$: 0-th Betti number / connected component count)<br>`modularity_clustering.md` L72 ($\pi$: feasible manifold for 1-Laplacian minimization)<br>`formal_graph_model.md` L99 ($\pi: C \to \text{Text}$: chunk substring projection) | Use $\Pi_{\text{pairs}}(G)$ for reachable vertex pairs, $b_0(G)$ (or $c(G)$) for connected component count, and $\mathcal{M}_1$ for the 1-Laplacian feasible manifold. |
| **4. Symbol Collision on $E(G)$ and $H$ Across Pillar 1** | `structural_elegance.md` L48 ($E$: edge set of $G$) vs. L55 ($E(G)$: Structural Elegance Index)<br>`modesty.md` L43 & `structural_refutability.md` L40 ($H = (V_H, E_H)$: hypothesis subgraph) vs. `structural_homogeneity.md` L70 ($H_{\text{node}}(G)$: Shannon degree entropy) | Use $\operatorname{SE}(G)$ for Structural Elegance Index and $G_H = (V_H, E_H)$ for the hypothesis subgraph. |
| **5. Broken Desktop Zotero Links & Misassigned Key `24SNSW2B`** | `bottleneck_fragility.md` L29<br>`centrality.md` L13<br>`community_bridges.md` L13 (links Balzer et al. 1987 to Schurz key `24SNSW2B`!)<br>`connectedness.md` L13 (links Balzer et al. 1987 to `24SNSW2B`!)<br>`dag_property.md` L12 (links Balzer et al. 1987 to `24SNSW2B`!)<br>`hierarchical_conformity.md` L11 (`https://www.google.com/search?q=zotero://select/library/items/24SNSW2B` for Balzer et al. 1987!)<br>`structural_elegance.md` L30 (links Balzer et al. 1987 to `24SNSW2B`!)<br>`structural_homogeneity.md` L12 | Remove local `zotero://` URIs and the broken Google Search wrapper in `hierarchical_conformity.md` L11; link citations to the shared bibliography. |
| **6. Taxonomy Count Mismatch in `structural_topology/index.md` vs. `metrics/index.md`** | `structural_topology/index.md` L11 (`## The Three Dimensions of Structural Topology`, followed by `## Dimension 4: Socio-Epistemic Alignment` on L40!) vs. `metrics/index.md` L35 (`Four-Dimensional Taxonomy`) | Change `structural_topology/index.md` L11 heading to `## The Four Dimensions of Structural Topology` to match Dimension 4 on L40 and `metrics/index.md` L35. |
| **7. Header Casing Typos in `dag_property.md` and `community_bridges.md`** | `dag_property.md` L7 (`# Non-CYCLIC Form (Dag Property)`)<br>`community_bridges.md` L7 (`# Community-bridges (Inter-Theoretical Links)`) | Normalize to `# Non-Cyclic Form (DAG Property)` and `# Community-Bridges (Inter-Theoretical Links)`. |
