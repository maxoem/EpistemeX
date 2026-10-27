# [ISSUE-097] Formal & Conceptual Evaluation: Centrality & Argumentative Discrepancy (`centrality.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-097` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 1: Structural & Topological Metrics (Socio-Epistemic Alignment) |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/structural_topology/centrality.md`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/graph/algorithms/eigenvector.py`, `pagerank.py`), `episteme-pipeline` |
| **Priority** | **Critical** (Eigenvector centrality $C_{\text{eigen}}(v)$ is mathematically zero/degenerate on the acyclic structural poset $G_{\text{struct}}$, out-degree centrality $C_{\text{deg}}(v)$ is inverted when edges are typed as `DEPENDS_ON` or `SPECIALIZES` from child to parent, and min-max normalization $\hat{C}_{\text{struct}}, \hat{S}_{\text{disc}}$ divides by zero on uniform graphs) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-100`](ISSUE-100-DAG-PROPERTY.md), [`ISSUE-101`](ISSUE-101-HIERARCHICAL-CONFORMITY.md), [`ISSUE-107`](../ISSUE-107-STRUCTURAL-TOPOLOGY-CROSS-CUTTING.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md), [`ISSUE-068`](../../10-formal-conceptual-docs/ISSUE-068-conceptual-and-domain-errors.md), [`ISSUE-008`](../../03-epistemic-metrics/ISSUE-008-extended-newman-centrality-metrics.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core, yields inverted diagnostics, or is mathematically uncomputable as written · **Major** = significant formal flaw, semantic shift, gaming vulnerability, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Degenerates on DAGs & Inverts Root vs. Leaf Under `DEPENDS_ON` / `SPECIALIZES`)** | Claims to isolate foundational paradigm cores ($T_0$) via high $C_{\text{struct}}(v)$ on $G_{\text{struct}}$ and compare them to textual discourse $S_{\text{disc}}(v)$. However, (1) on any acyclic hierarchy $G_{\text{struct}}$ (`dag_property.md`), the adjacency matrix is nilpotent ($\lambda_{\max} = 0$), so **Eigenvector Centrality $C_{\text{eigen}}(v)$ is identically zero or fails to converge (`AlgorithmConvergenceError`)**; (2) `DEPENDS_ON` and `SPECIALIZES` (in `hierarchical_conformity.md` L43, L75) point from *specialized child to foundational parent* ($u \to T_0$), under which the foundational root $T_0$ has **$\text{deg}_{\text{out}}(T_0) = 0$** and scores $C_{\text{deg}}(T_0) = 0.0$ ("Peripheral Assumption") while leaf applications score high! |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) $C_{\text{eigen}}(v) = \frac{1}{\lambda} \sum_{u \in \mathcal{N}_{\text{struct}}(v)} A_{uv}^{\text{struct}} x_u$ divides by $\lambda = 0$ on DAGs and mixes $C_{\text{eigen}}(v)$ on the LHS with $x_u$ on the RHS without specifying in-neighbors vs. out-neighbors; (2) Min-max normalization $\hat{X}(v) = \frac{X(v) - \min X}{\max X - \min X}$ divides by zero when all nodes have equal centrality or equal mention frequency; (3) In $S_{\text{disc}}(v) = \alpha \cdot \text{PR}(v, G_{\text{disc}}) + \beta \cdot \text{freq}(v)$, $\text{PR}$ sums to $1$ across $V$ (so $\text{PR}(v) \sim 1/\|V\|$) while $\text{freq}(v)$ has unspecified normalization, making $\alpha, \beta$ scale-dependent on $\|V\|$; (4) `MENTIONED_IN` edges $(v \to c_m \in L1)$ included in $G_{\text{disc}}$ turn document chunks into PageRank sinks unless projected out. |
| **3. Free of Semantic Shifts?** | **No (Major Shifts)** | Conflates Sneed/Stegmüller's **Non-Statement-View vs. Statement-View** (set-theoretic model classes $M_p, M, M_{pp}$ vs. syntactic sentences) with **Structural Dependency Edges vs. Rhetorical/Provenance Edges** within a single propositional graph $V$, and uses unregistered relation types (`DEPENDS_ON`, `MENTIONED_IN`) absent from `epistemetrics.RelationType`. |
| **4. Valid & Scientifically Significant?** | **Yes (High Metascientific Value Once Repaired)** | Detecting **Argumentative Discrepancy** (tacit foundational axioms taken for granted vs. heavily debated peripheral controversies) is a genuine, high-value insight for automated corpus analysis and scientometrics. Replacing Eigenvector Centrality on DAGs with **Descendant Reach / Reverse PageRank (or Katz Centrality)** makes it mathematically sound. |

---

## 1. Does the Metric Capture What It Claims It Does?

### CD-01 · Nilpotent Adjacency Collapse of Eigenvector Centrality $C_{\text{eigen}}(v)$ on Acyclic Structural Graphs $G_{\text{struct}}$ — **Critical**

**Where.** [`centrality.md#L30-L33`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L30-L33), [`#L55-L60`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L55-L60), [`#L94`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L94), and [`packages/epistemetrics/src/epistemetrics/graph/algorithms/eigenvector.py`](../../../packages/epistemetrics/src/epistemetrics/graph/algorithms/eigenvector.py).

**Finding.**
`centrality.md` mandates computing **Eigenvector Centrality** $C_{\text{eigen}}(v)$ strictly over the Logical-Structural Subgraph $G_{\text{struct}} = (V, E_{\text{struct}})$ consisting of specialization and dependency edges:
$$C_{\text{eigen}}(v) = \frac{1}{\lambda} \sum_{u \in \mathcal{N}_{\text{struct}}(v)} A_{uv}^{\text{struct}} x_u.$$
However, by [`dag_property.md`](../../../docs/concepts/theory/metrics/structural_topology/dag_property.md) (a mandatory Logical Integrity Prerequisite in `structural_topology/index.md` L33–36), $G_{\text{struct}}$ **must be a Directed Acyclic Graph (DAG)**.
- On any finite DAG, the adjacency matrix $A^{\text{struct}}$ can be topologically ordered into a strictly triangular matrix with zeros on the diagonal.
- Therefore, $A^{\text{struct}}$ is **nilpotent** ($(A^{\text{struct}})^{|V|} = 0$), and **every eigenvalue of $A^{\text{struct}}$ is identically $\lambda = 0$**!
- Division by $\lambda = 0$ in L59 is mathematically undefined. Any eigenvector satisfying $A^{\text{struct}} x = 0 \cdot x = 0$ is non-zero only on sink/source nodes with 0 out/in-edges (yielding $0$ for all internal hierarchy nodes), and in [`epistemetrics/graph/algorithms/eigenvector.py`](../../../packages/epistemetrics/src/epistemetrics/graph/algorithms/eigenvector.py#L76-L98), `nx.eigenvector_centrality` fails power iteration on DAGs or returns degenerate zero vectors! (See also [`ISSUE-067` B-32](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md#b-32--eigenvector-centrality-is-degenerate-on-dags-and-signed-graphs--major)).

**Fix.**
Replace Eigenvector Centrality on the directed acyclic hierarchy $G_{\text{struct}}$ with **Katz Centrality** (attenuated walk count with $\alpha > 0$, which stays well-defined when $\lambda_{\max} = 0$ because $(I - \alpha A)^{-1} = \sum_{k=0}^{|V|-1} \alpha^k A^k$) or **Reverse PageRank / Transitive Descendant Coverage**:
$$C_{\text{reach}}(v) = \frac{|\operatorname{Desc}(v, G_{\text{struct}})|}{|V| - 1} \in [0, 1]$$
which directly measures *"how many downstream specializations/models collapse if node $v$ is removed"* (matching L33's stated conceptual goal!).

---

### CD-02 · Opposite Edge Orientations Between `DEPENDS_ON` / `SPECIALIZES` ($u \to T_0$) and Out-Degree Centrality $C_{\text{deg}}(v)$ Assign $0.0$ to Foundational Roots — **Critical**

**Where.** [`centrality.md#L30-L33`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L30-L33), [`#L49-L53`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L49-L53) vs. [`hierarchical_conformity.md#L43`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L43), [`#L73-L77`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L73-L77).

**Finding.**
1. L31 defines $G_{\text{struct}}$ as containing `DEPENDS_ON` and `SPECIALIZES` edges, and L49–53 defines Structural Centrality as **Out-Degree Centrality**:
   $$C_{\text{deg}}(v) = \frac{\text{deg}_{\text{out}}(v, G_{\text{struct}})}{|V| - 1}.$$
2. However:
   - In `DEPENDS_ON`: if specialized law $u$ depends on foundational axiom $T_0$ ($u \xrightarrow{\text{DEPENDS\_ON}} T_0$), the edge points from $u$ **to** $T_0$. The foundational axiom $T_0$ depends on nothing, so $\text{deg}_{\text{out}}(T_0) = 0$ and $\text{deg}_{\text{in}}(T_0)$ is high!
   - In `hierarchical_conformity.md` (L43 and Cypher query L74–76: `WHERE NOT (t)-[:SPECIALIZES]->(:TheoryElement)`), `(u)-[:SPECIALIZES]->(v)` also points from specialized child $u$ **to** general parent $v$ ($T_0$), so $T_0$ again has **out-degree $0$**!
   - Conversely, in `poset_evaluation.py` (L177) and `schema.md` (L90), `SPECIALIZES` points from parent $T_0$ **to** child $T_1$ ($T_0 \to T_1$).
3. Thus, under `DEPENDS_ON` (and `hierarchical_conformity.md`'s `SPECIALIZES` convention), $C_{\text{deg}}(T_0) = 0.0$ for every foundational axiom $T_0$, causing $AD(T_0) = 0 - \hat{S}_{\text{disc}}(T_0) \le 0$ and misclassifying the foundational core as a **"Peripheral Assumption"** or **"Fringe Controversy"**!
4. Furthermore, even under parent-to-child orientation ($T_0 \to T_1 \to T_{11}$), 1-hop out-degree $\text{deg}_{\text{out}}(T_0)$ only counts *immediate* children of $T_0$, ignoring deep multi-level specialization trees where $T_0$ has 2 immediate children that subsequently branch into 100 applications.

**Fix.**
1. Enforce a single canonical orientation for $G_{\text{struct}}$ (parent/foundation $\to$ child/dependent: $T_0 \to T_1$, reversing `DEPENDS_ON` edges if present).
2. Replace 1-hop $\text{deg}_{\text{out}}(v)$ with **Transitive Descendant Reachability** $\frac{|\operatorname{Desc}(v, G_{\text{struct}})|}{|V| - 1}$ (or attenuated Katz descendant centrality $\sum_{k=1}^{\infty} \gamma^k ((A^{\text{struct}})^k)_{v, u}$), so that foundational roots supporting deep specialization trees receive high $C_{\text{struct}}(v)$ regardless of whether their branching occurs at depth 1 or depth $d$.

---

## 2. Is the Metric Formally & Mathematically Correct?

### CD-03 · Division by Zero in Min-Max Normalization $\hat{C}_{\text{struct}}, \hat{S}_{\text{disc}}$, Scale Incommensurability in $S_{\text{disc}}$, and Sink Distortion from `MENTIONED_IN` — **Major**

**Where.** [`centrality.md#L34-L36`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L34-L36), [`#L52`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L52), [`#L67-L87`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L67-L87).

**Finding.**
1. **Division by Zero in Min-Max Normalization (L86) and $|V| = 1$ (L52):**
   L86 defines $\hat{C}_{\text{struct}}(v)$ and $\hat{S}_{\text{disc}}(v)$ as min-max normalized to $[0, 1]$:
   $$\hat{X}(v) = \frac{X(v) - \min_{u \in V} X(u)}{\max_{u \in V} X(u) - \min_{u \in V} X(u)}.$$
   When $\max_{u \in V} X(u) = \min_{u \in V} X(u)$ (e.g., when $E_{\text{struct}} = \emptyset$, or all nodes are mentioned once in single-pass extraction, or $|V| \le 1$), the denominator $\max X - \min X = 0$, causing a division by zero. Moreover, when $\max X - \min X = \epsilon \ll 1$ (tiny numerical jitter on an almost uniform graph), min-max normalization stretches negligible noise across the full $[0, 1]$ interval, fabricating maximal discrepancy scores $AD(v) = \pm 1.0$!
2. **Scale Incommensurability and Unconstrained Weights $\alpha, \beta$ in $S_{\text{disc}}(v)$ (L68):**
   $$S_{\text{disc}}(v) = \alpha \cdot \text{PR}(v, G_{\text{disc}}) + \beta \cdot \text{freq}(v)$$
   - Standard PageRank is a probability distribution over $V$: $\sum_{v \in V} \text{PR}(v) = 1$, so the mean PageRank is $1/|V|$ (which shrinks as $O(1/|V|)$ in large graphs).
   - Meanwhile, the normalization of $\text{freq}(v)$ (L75: *"normalized count of `MENTIONED_IN` edges"*) is never specified: is it divided by $\max_u \text{count}(u)$ (lying in $[0, 1]$), or by $\sum_u \text{count}(u)$ (lying in $[0, 1]$ with mean $1/|V|$), or by total chunks $|C|$? If $\text{freq}(v) \in [0, 1]$ is max-normalized while $\text{PR}(v) \sim 1/|V|$, then for $|V| = 1000$, $\text{freq}(v)$ dominates $\text{PR}(v)$ by $1000\times$ for fixed $\alpha, \beta$!
   - Nor is $\alpha + \beta = 1$ ($\alpha, \beta \ge 0$) specified.
3. **Bipartite Sink Distortion if `MENTIONED_IN` Edges Are Included in $G_{\text{disc}}$ (L35 vs. L68–75):**
   L35 states that $G_{\text{disc}}$ *"Contains edges representing rhetoric and textual grounding (e.g., `SUPPORTS`, `REFUTES`, `MENTIONED_IN`)"*.
   However, `MENTIONED_IN` edges point from Layer 2/3 nodes $v$ to **Layer 1 document chunks $c \in C$** ($v \xrightarrow{\text{MENTIONED\_IN}} c$). If `MENTIONED_IN` edges are included inside $G_{\text{disc}}$ when computing $\text{PR}(v, G_{\text{disc}})$, all PageRank mass flows *out* of propositions $v$ into L1 document chunk sinks $c \in C$ (and is already counted a second time in $\beta \cdot \text{freq}(v)$)!
4. **Ignore Polarity in $\text{PR}(v, G_{\text{disc}})$:**
   Computing standard unsigned PageRank over `SUPPORTS` and `REFUTES` combined (L73–74) treats being heavily *supported* and being heavily *attacked* identically as "rhetorical prominence". That is acceptable for measuring raw *discourse attention*, but in standard PageRank $(u \xrightarrow{\text{SUPPORTS}} v)$ means supporter $u$ transfers prestige to $v$, whereas $(u \xrightarrow{\text{REFUTES}} v)$ transfers prestige from attacker $u$ to target $v$ only if edge direction is preserved as $u \to v$.

**Fix.**
1. Restrict $G_{\text{disc}} = (V_{\text{L3}}, E_{\text{arg}})$ strictly to Layer 3 argumentative edges ($E_{\text{arg}} = \mathcal{R}_{sup} \cup \mathcal{R}_{att}$) when computing $\text{PR}(v, G_{\text{disc}})$, keeping `MENTIONED_IN` strictly in the provenance frequency term $\text{freq}(v)$.
2. Pre-normalize both $\text{PR}(v, G_{\text{disc}})$ and $\text{freq}(v)$ to $[0, 1]$ (or probability simplex $\sum_v p(v) = 1$) **before** taking the convex combination with $\alpha + \beta = 1, \alpha, \beta \ge 0$.
3. Guard min-max normalization with an explicit constant/epsilon check:
   $$\hat{X}(v) = \begin{cases} \frac{X(v) - \min X}{\max X - \min X} & \text{if } \max X - \min X > \epsilon \\ 0.0 & \text{otherwise.} \end{cases}$$

---

### CD-04 · Formula Contradiction Between Signed $AD(v) \in [-1, 1]$ (`centrality.md` L83) and Unsigned $\Delta_{\text{disc}} = |C_{\text{structural}} - C_{\text{textual}}|$ (`metrics/index.md` L59) — **Major**

**Where.** [`centrality.md#L83`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L83) vs. [`docs/concepts/theory/metrics/index.md#L59`](../../../docs/concepts/theory/metrics/index.md#L59).

**Finding.**
- In `centrality.md` (L83), Argumentative Discrepancy is a **signed difference** in $[-1, 1]$:
  $$AD(v) = \hat{C}_{\text{struct}}(v) - \hat{S}_{\text{disc}}(v) \in [-1, 1]$$
  where $AD(v) \gg 0$ identifies a **Tacit Paradigm Core** ($\hat{C}_{\text{struct}} \gg \hat{S}_{\text{disc}}$) and $AD(v) \ll 0$ identifies a **Fringe Controversy** ($\hat{C}_{\text{struct}} \ll \hat{S}_{\text{disc}}$).
- In `docs/concepts/theory/metrics/index.md` (L59), the formula is written with **absolute value bars**:
  $$\Delta_{\text{disc}} = |C_{\text{structural}} - C_{\text{textual}}| \in [0, 1]$$
  which collapses the sign and makes a **Tacit Paradigm Core** ($+0.9$) mathematically indistinguishable from a **Fringe Controversy** ($-0.9$)!

**Fix.**
Keep the signed definition $AD(v) = \hat{C}_{\text{struct}}(v) - \hat{S}_{\text{disc}}(v) \in [-1, 1]$ in both files so that the sign distinguishes tacit foundations ($AD > 0$) from fringe controversies ($AD < 0$).

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### CD-05 · Conflation of Non-Statement-View vs. Statement-View with Structural vs. Rhetorical Subgraph Projections & Unregistered Edge Types — **Major**

**Where.** [`centrality.md#L25-L37`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L25-L37) vs. [`formal_graph_model.md#L54-L134`](../../../docs/concepts/formal_graph_model.md#L54-L134) and [`packages/epistemetrics/src/epistemetrics/core/models.py#L399-L454`](../../../packages/epistemetrics/src/epistemetrics/core/models.py#L399-L454).

**Finding.**
1. **Mischaracterization of Layer 2 vs. Layer 3 (L25–26):**
   L25 states: *"Because the pipeline extracts both logical dependencies (Layer 2) and rhetorical/argumentative structures (Layer 3) into a single unified property graph..."*
   In [`formal_graph_model.md`](../../../docs/concepts/formal_graph_model.md#L101-L134), **Layer 2** is the entity-relational ontology (`Person`, `Work`, `Concept`), whereas **Layer 3** contains both deductive/specialization structures and argumentative structures.
2. **Misuse of "Non-Statement-View" vs. "Statement-View" (L32–36):**
   In philosophy of science (Stegmüller 1976; Balzer et al. 1987), the **Non-Statement-View** represents theories as classes of set-theoretic models $\langle M_p, M, M_{pp}, GC, GL \rangle$, whereas the **Statement-View** represents theories as sets of linguistic propositions/axioms. Both $G_{\text{struct}}$ and $G_{\text{disc}}$ in `centrality.md` share the **exact same vertex set $V$** (L42–43). Projecting edges into deductive/taxonomic edges vs. rhetorical/provenance edges separates **epistemic justification structure** from **pragmatic/rhetorical discourse prominence**, not Non-Statement-View from Statement-View.
3. **Unregistered Edge Types (`DEPENDS_ON`, `MENTIONED_IN`, `REFUTES`):**
   L32 and L35 filter on `DEPENDS_ON`, `SPECIALIZES`, `SUPPORTS`, `REFUTES`, `MENTIONED_IN`. In `epistemetrics.RelationType` (`models.py` L438–454), neither `DEPENDS_ON` nor `MENTIONED_IN` exists (provenance is stored as `node.provenance: list[str]`, and `PRESUPPOSES` / `EXPLAINS` / `SPECIALIZES` are the canonical structural types).

**Fix.**
1. Align the edge-type sets with `epistemetrics.RelationType` and `TheoryNode.provenance`:
   - $E_{\text{struct}}$: `{RelationType.SPECIALIZES, RelationType.PRESUPPOSES, RelationType.EXPLAINS, RelationType.CONSTRAINS}` (with unified parent-to-child orientation).
   - $E_{\text{disc}}$: `{RelationType.SUPPORTS, RelationType.ATTACKS, RelationType.COHERES_WITH}` plus `len(node.provenance)` for document chunk mention frequency $\text{freq}(v)$.
2. Frame the contrast accurately as **Epistemic-Structural Necessity vs. Textual-Rhetorical Prominence** (context of justification vs. context of discourse/discovery).

---

## 4. Is the Metric Valid and Scientifically Significant?

### CD-06 · Formatting Typo (Empty List Item `3.`) and Missing `AD(v)` Orchestrator in `epistemetrics` — **Minor**

**Where.** [`centrality.md#L55-L60`](../../../docs/concepts/theory/metrics/structural_topology/centrality.md#L55-L60).

**Finding.**
1. L55–57 contains a broken numbered list with an empty item `3.` before the equation for item `2. Eigenvector Centrality`.
2. While `epistemetrics` implements `page_rank` and `eigenvector_centrality`, it does not yet implement the dual-projection `compute_argumentative_discrepancy(graph)` evaluator.

**Fix.**
Remove the stray `3.` on L56 and implement `compute_argumentative_discrepancy` in `epistemetrics`.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Broken Desktop Zotero URI (L13):** `[Schurz, 2024, p. 119](zotero://select/library/items/24SNSW2B)` uses a local desktop link.
2. **Symbol Collision on $\alpha, \beta$ (L68 vs. `formal_graph_model.md` L366–367 and `theory_nets_and_topologies.md` L42):** Here $\alpha, \beta$ are scalar linear combination weights in $S_{\text{disc}}(v)$, whereas $\alpha$ denotes the specialization relation in `theory_nets_and_topologies.md` and $\beta$ denotes subjective-logic belief in `formal_graph_model.md`. Use $w_{\text{pr}}, w_{\text{freq}}$ with $w_{\text{pr}} + w_{\text{freq}} = 1$.
