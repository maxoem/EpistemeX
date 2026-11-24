# [ISSUE-101] Formal & Conceptual Evaluation: Tree / Hierarchical Conformity (`hierarchical_conformity.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-101` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 1: Structural & Topological Metrics (Logical Integrity Constraints) |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/epistemic/poset_evaluation.py`), `episteme-pipeline` |
| **Priority** | **Critical** (Inverts thespecialization order $\alpha$ in $B(N)$ so that $B(N)$ selects **terminal leaf specializations** instead of the root $T_0$; evaluates $\text{in-deg}_{\text{spec}}(u)$ on the raw DAG $G$ instead of its transitive reduction $G_{\text{TR}}$, penalizing every transitive specialization edge as multiple inheritance; divides by zero when $|B(N)| = 0$ or $|E| = 0$; and contradicts its own Cypher query on `:SPECIALIZES` edge direction) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-100`](ISSUE-100-DAG-PROPERTY.md), [`ISSUE-107`](../ISSUE-107-STRUCTURAL-TOPOLOGY-CROSS-CUTTING.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core, yields inverted diagnostics, or is mathematically uncomputable as written · **Major** = significant formal flaw, semantic shift, gaming vulnerability, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Inverts Root vs. Leaf in $B(N)$ and Penalizes Transitive Poset Edges as Poly-Specialization)** | Claims to verify whether a theory-net $N = \langle T, \alpha \rangle$ is a single-rooted **Theory-Tree** anchored at $T_0$. However, (1) under the standard structuralist convention $T_j \, \alpha \, T_i \equiv \text{"}T_j \text{ specializes } T_i\text{"}$ (`theory_nets_and_topologies.md` L44), the formula $B(N) = \{T_i \in T \mid \forall T_j \in T \, (T_j \, \alpha \, T_i \implies T_j = T_i)\}$ selects elements that **have no specializations**—i.e. the **terminal leaf applications**, NOT the foundational root $T_0$! (2) Even worse, while L52 states that the *transitive reduction* of $\alpha$ must be an arborescence, the formula $S_{\text{tree}}(G)$ on L58 evaluates $\text{in-deg}_{\text{spec}}(u)$ on $G = (V, E)$ directly without taking the transitive reduction—so any valid poset containing transitive edges $(T_0 \to T_1, T_1 \to T_2, T_0 \to T_2)$ has $\text{in-deg}_{\text{spec}}(T_2) = 2$ and fails the tree test! |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) $S_{\text{tree}}(G)$ divides by $0$ when $\|B(N)\| = 0$ (cyclic graph or empty graph) or when $\|E\| = 0$ (edgeless graph with $\|B(N)\| > 1$); (2) Contradictory edge orientations inside the same document: L43 & L75 define `(u)-[:SPECIALIZES]->(v)` as child $u \to$ parent $v$ (so roots have **out-degree 0**), whereas L58, L60, and L70 define roots as nodes with **in-degree 0** (parent $v \to$ child $u$); (3) In `epistemetrics/epistemic/poset_evaluation.py` (L252–255), `find_poset_roots` filters out isolated root nodes (`out_degree == 0`) whenever *any* edge exists elsewhere in the graph, hiding disconnected root paradigms! |
| **3. Free of Semantic Shifts?** | **No (Major Shifts)** | Shifts between a **micro-level proposition graph** where core axioms must form a **Strongly Connected Component (SCC)** of mutual presupposition (L34, L69—violating `dag_property.md`!) and a **macro-level TheoryElement poset** where each node is a tuple $T_i = \langle K_i, I_i \rangle$, without any SCC-condensation algorithm implemented in the pipeline or `epistemetrics`. |
| **4. Valid & Scientifically Significant?** | **Yes (Core Structuralist Benchmark Metric)** | Single-rooted Theory-Tree conformity ($B(N) = \{T_0\}$) and arborescence evaluation on the Hasse diagram (transitive reduction) are foundational to Balzer, Moulines, & Sneed (1987, pp. 172–176) and Task 2 of the project's Structuralist Theory-Net Benchmark (STNB). |

---

## 1. Does the Metric Capture What It Claims It Does?

### HC-01 · Inverted Quantifier Order in $B(N)$ Selects Terminal Leaves Instead of the Root $T_0$, and Internal Contradiction on `:SPECIALIZES` Direction — **Critical**

**Where.** [`hierarchical_conformity.md#L43-L53`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L43-L53), [`#L60-L63`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L60-L63), [`#L70-L78`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L70-L78) vs. [`theory_nets_and_topologies.md#L42-L65`](../../../docs/concepts/theory_nets_and_topologies.md#L42-L65) and [`poset_evaluation.py#L174-L178`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L174-L178).

**Finding.**
1. **Order-Theoretic Inversion in $B(N)$ (L47):**
   In `theory_nets_and_topologies.md` (L44) and Balzer, Moulines, & Sneed (1987, p. 171), the specialization relation is written:
   $$T_j \, \alpha \, T_i \quad \Longleftrightarrow \quad T_j \text{ is a specialization of } T_i.$$
   Under this definition, every element $T_j$ in a Theory-Tree is a specialization of the root $T_0$ ($T_j \, \alpha \, T_0$).
   Now examine the set $B(N)$ defined on L47 of `hierarchical_conformity.md`:
   $$B(N) = \{T_i \in T \mid \forall T_j \in T \, (T_j \, \alpha \, T_i \implies T_j = T_i)\}.$$
   Read literally: $T_i \in B(N)$ iff the only element $T_j$ that specializes $T_i$ is $T_i$ itself—meaning **nothing specializes $T_i$**!
   Those are the **most specialized terminal leaf elements** at the bottom of the tree, NOT the foundational root $T_0$!
   For the foundational root $T_0$ (which generalizes all other elements and is specialized by nothing), the condition must be:
   $$B(N) = \{T_i \in T \mid \forall T_j \in T \, (T_i \, \alpha \, T_j \implies T_j = T_i)\}$$
   (i.e. $T_i$ is not a proper specialization of any $T_j$; see also [`ISSUE-067` B-29](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md#b-29--root-is-called-minimal-unique-root-does-not-make-a-tree--major)).

2. **Self-Contradictory Edge Orientation Between L43/L75 (`child -> parent`) and L58/L60/L70 (`parent -> child`):**
   Inside `hierarchical_conformity.md` itself, the direction of `:SPECIALIZES` flips three times:
   - **L43 (Child $\to$ Parent):** *"directed edges $(u, v) \in E$ indicate $u \text{ specializes } v$ (or in parent-child representation, $(v, u) \in E_{\text{spec}}$ where $v$ is generalized into child $u$)."*
   - **L58, L60, L62, L70 (Parent $\to$ Child):** Defines roots as nodes with **0 in-degree** and $\text{in-deg}_{\text{spec}}(u)$ as *"the number of immediate generalizing parents for node $u$"*. This holds **only** when edges point from **general parent $v$ to specialized child $u$** ($v \to u$).
   - **L73–77 Cypher Query (Child $\to$ Parent):**
     ```cypher
     MATCH (t:TheoryElement {theory_id: $theory_id})
     WHERE NOT (t)-[:SPECIALIZES]->(:TheoryElement {theory_id: $theory_id})
     RETURN count(t) AS root_count
     ```
     This Cypher query checks `NOT (t)-[:SPECIALIZES]->(...)` (i.e. **out-degree = 0**)!
     Yet in [`poset_evaluation.py`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L177) (`Preserves parent -> child orientation (T_i -> T_j where T_j specializes T_i)`) and [`docs/reference/schema.md`](../../../docs/reference/schema.md#L90) (`RootCore -->|"SPECIALIZES (α)"| SpecHyp`), `:SPECIALIZES` edges are stored in the **parent $\to$ child** direction ($T_0 \to T_1$)!
     Therefore, running L74–76's Cypher query on the project's graph counts the **leaf nodes** (which have no outgoing `:SPECIALIZES` edges) instead of the root $T_0$!

**Fix.**
1. Correct the order-theoretic definition of $B(N)$ on L47 to:
   $$B(N) = \{T_i \in T \mid \neg \exists T_j \in T \setminus \{T_i\} : T_i \text{ specializes } T_j\}.$$
2. Standardize `:SPECIALIZES` edge orientation across all docs and Cypher queries to match `poset_evaluation.py` and `schema.md` (**parent $\to$ child**: `(parent:TheoryElement)-[:SPECIALIZES]->(child:TheoryElement)`, where roots have `in_degree == 0`), and fix the Cypher query on L75 to:
   ```cypher
   MATCH (t:TheoryElement {theory_id: $theory_id})
   WHERE NOT (:TheoryElement {theory_id: $theory_id})-[:SPECIALIZES]->(t)
   RETURN count(t) AS root_count
   ```

---

### HC-02 · Evaluating $\text{in-deg}_{\text{spec}}(u)$ on $G$ Instead of Its Transitive Reduction $G_{\text{TR}}$ Penalizes Valid Transitive Posets as "Multiple Inheritance" — **Critical**

**Where.** [`hierarchical_conformity.md#L52-L63`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L52-L63).

**Finding.**
1. L52 rightly states the structuralist definition of a **Theory-Tree** (Balzer et al. 1987, p. 175):
   > *"2. The **transitive reduction** of $\alpha$ forms an out-tree (arborescence) rooted at $T_0$, meaning every non-root node $T_k \in T \setminus \{T_0\}$ has exactly one immediate predecessor in the specialization hierarchy."*
2. However, the mathematical formula for $S_{\text{tree}}(G)$ on L58:
   $$S_{\text{tree}}(G) = \begin{cases} 1 & \text{if } |B(N)| = 1 \land \forall u \in V \setminus \{T_0\}, \, \text{in-deg}_{\text{spec}}(u) = 1 \\ \frac{1}{|B(N)|} \cdot \left(1 - \frac{\sum_{u \in V} \max(0, \text{in-deg}_{\text{spec}}(u) - 1)}{|E|} \right) & \text{otherwise} \end{cases}$$
   evaluates $\text{in-deg}_{\text{spec}}(u)$ and $|E|$ on $G = (V, E)$ rather than on the **Hasse diagram / transitive reduction** $G_{\text{TR}} = \operatorname{TR}(G) = (V, E_{\text{TR}})$!
3. Because $\alpha$ is a **transitive** partial order (`dag_property.md` L26: $T_0 \to T_1 \land T_1 \to T_2 \implies T_0 \to T_2$), any chain of length $\ge 2$ where transitive edges are explicitly extracted has $\text{in-deg}_G(T_2) = 2$ (from $T_0$ and $T_1$) even though $T_2$ has only **one immediate predecessor** ($T_1$) in the Hasse diagram $G_{\text{TR}}$!
   On a pure chain $T_0 \to T_1 \to \dots \to T_{n-1}$ with transitive closure edges, every node $T_k$ ($k \ge 2$) has $\text{in-deg}_G(T_k) = k > 1$, so L58 penalizes a pure linear chain as failing tree conformity!

**Fix.**
Explicitly compute the **transitive reduction** $G_{\text{TR}} = \operatorname{TR}(G) = (V, E_{\text{TR}})$ first (assuming $\text{IsDAG}(G) = 1$), and define $\text{in-deg}_{\text{TR}}(u)$ and $|E_{\text{TR}}|$ over $G_{\text{TR}}$:
$$S_{\text{tree}}(G) = \frac{1}{|B(N)|} \cdot \left(1 - \frac{\sum_{u \in V} \max\big(0, \text{in-deg}_{\text{TR}}(u) - 1\big)}{|E_{\text{TR}}|} \right)$$
(which automatically equals $1$ when $|B(N)| = 1$ and $\forall u \in V \setminus \{T_0\}, \text{in-deg}_{\text{TR}}(u) = 1$, eliminating the redundant piecewise branch!).

---

## 2. Is the Metric Formally & Mathematically Correct?

### HC-03 · Division by Zero When $|B(N)| = 0$ or $|E| = 0$, and Disconnected Root Filtering Bug in `poset_evaluation.py` (`find_poset_roots`) — **Critical**

**Where.** [`hierarchical_conformity.md#L58`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L58) and [`packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L228-L258`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L228-L258), [`#L576-L597`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L576-L597).

**Finding.**
1. **Division by Zero in $S_{\text{tree}}(G)$ (L58):**
   - **Case 1 ($|B(N)| = 0$):** If $G$ is empty ($V = \emptyset$) or if every node has $\text{in-deg}_{\text{spec}}(u) \ge 1$ (e.g. a directed cycle $T_1 \to T_2 \to T_1$), then $|B(N)| = 0$, and $\frac{1}{|B(N)|}$ divides by zero!
   - **Case 2 ($|E| = 0$ and $|V| \ge 2$):** If a graph has $k \ge 2$ isolated theory-elements and $0$ specialization edges ($|E| = 0$), then $|B(N)| = k > 1$ (so it enters the `otherwise` branch) and $\frac{\sum \max(0, \text{in-deg}(u) - 1)}{|E|} = \frac{0}{0}$ divides by zero!
2. **Critical Bug in `epistemetrics/epistemic/poset_evaluation.py` (`find_poset_roots` L252–256):**
   Look at how `find_poset_roots(dag)` is implemented in `poset_evaluation.py` (L247–257):
   ```python
   zero_in = [n for n, deg in dag.in_degree() if deg == 0]
   if not zero_in:
       return []

   # If edges exist, prioritize nodes that actually reach other nodes
   if dag.number_of_edges() > 0:
       branching_roots = [n for n in zero_in if dag.out_degree(n) > 0]
       if branching_roots:
           return branching_roots

   return zero_in
   ```
   **Why this is a critical bug:**
   Suppose a fragmented theory graph has **two disconnected components**:
   - Component 1: $T_0 \to T_1$ (`out_degree(T_0) = 1 > 0`), and
   - Component 2: an isolated unintegrated root theory-element $T_2$ (`in_degree(T_2) = 0, out_degree(T_2) = 0`).
   Here, $B(N) = \{T_0, T_2\}$ has **2 roots** ($|B(N)| = 2$, a disconnected multi-root forest!).
   Yet because `dag.number_of_edges() > 0`, `find_poset_roots` **discards $T_2$** (`out_degree == 0`), returns `branching_roots = [T_0]` (length 1), and sets `has_unique_root = True` and `root_conformity = True`!
    Furthermore, even if Component 1 is a single root $T_0$ branching into $T_1$ AND Component 2 is a second root $T'_0$ branching into $T'_1$ (disconnected forest of 2 trees), `poset_evaluation.py` checks `has_unique_root` ($|B(N)| = 1$) but **never checks whether the arborescence condition ($\text{in-deg}_{\text{TR}}(u) = 1$) holds** or computes $S_{\text{tree}}(G)$!

**Fix.**
1. Guard $S_{\text{tree}}(G)$ against $|B(N)| = 0$, $|V| \le 1$, and $|E_{\text{TR}}| = 0$:
   $$S_{\text{tree}}(G) = \begin{cases} 0.0 & \text{if } |V| = 0 \lor |B(N)| = 0 \lor \neg\text{IsDAG}(G) \\ 1.0 & \text{if } |V| = 1 \\ \dfrac{1}{|B(N)|} & \text{if } |V| \ge 2 \land |E_{\text{TR}}| = 0 \\ \dfrac{1}{|B(N)|} \left(1 - \dfrac{\sum_{u \in V} \max(0, \text{in-deg}_{\text{TR}}(u) - 1)}{|E_{\text{TR}}|}\right) & \text{otherwise.} \end{cases}$$
2. Fix `find_poset_roots` in `poset_evaluation.py` so that **all** nodes with `in_degree == 0` in the specialization poset are returned as roots (do not silently drop isolated `THEORY_ELEMENT` nodes when other edges exist!), and add `tree_conformity_score: float` ($S_{\text{tree}}(G)$) and `is_arborescence: bool` to `PosetEvaluationResult`.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### HC-04 · Unspecified & Unimplemented Micro-to-Macro SCC Condensation Algorithm for $T_0$ — **Major**

**Where.** [`hierarchical_conformity.md#L19-L38`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L19-L38), [`#L69`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L69).

**Finding.**
L23–38 and L69 state that on a micro-level proposition graph, individual axioms must first be validated for:
1. Logical Consistency,
2. Mutual Constraint (forming an SCC of mutual presupposition), and
3. High Internal Density (`PRESUPPOSES`, `SHARES_VARIABLE`, `CONSTRAINS`),
and then condensed into a single macro-node $T_0$ before computing $B(N)$ and $S_{\text{tree}}(G)$.

However:
- Neither `hierarchical_conformity.md` nor `poset_evaluation.py` defines the quantitative thresholds for "High Internal Density" or specifies which edge types form the SCC of mutual presupposition vs. the DAG of specialization.
- `SHARES_VARIABLE` is not a registered `RelationType` in `epistemetrics` or `schema.md`.
- If `PRESUPPOSES` forms cycles (SCCs) inside $T_0$, any algorithm that pools `PRESUPPOSES` with `SPECIALIZES` will fail `dag_property.md` unless condensation is executed first.

**Fix.**
Formalize the two-stage **Condensation & Poset Projection** algorithm explicitly:
1. **Stage 1 (Equivalence & Co-Axiom Condensation):** On the subgraph of horizontal co-axiom relations (`PRESUPPOSES`, `EQUIVALENT_TO`, `CONSTRAINS`), compute Tarjan's Strongly Connected Components $C_1, \dots, C_m$ (verifying absence of internal `ATTACKS` edges, i.e., $\forall u, v \in C_r, (u, v) \notin \mathcal{R}_{\text{att}}$) and contract each valid SCC into a macro-node $T_r = \text{condense}(C_r)$.
2. **Stage 2 (Vertical Specialization Arborescence):** Project the strict vertical `:SPECIALIZES` edges between macro-nodes $T_r$, verify `IsDAG`, compute the transitive reduction $G_{\text{TR}}$, and evaluate $B(N)$ and $S_{\text{tree}}(G_{\text{TR}})$.

---

## 4. Is the Metric Valid and Scientifically Significant?

### HC-05 · High Metascientific Validity (Balzer et al. 1987, p. 175) — Needs `S_tree` Integration in `poset_evaluation.py` — **Minor**

**Where.** [`packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py).

**Finding.**
The distinction between a **Pure Theory-Tree** ($|B(N)| = 1, S_{\text{tree}} = 1$), a **Poly-Net / Lattice** ($|B(N)| = 1, S_{\text{tree}} < 1$ where a child law cross-specializes two parent branches, e.g., electro-magnetism or thermo-elasticity), and a **Multi-Root Forest** ($|B(N)| > 1$) is scientifically rigorous and faithful to Balzer, Moulines, & Sneed (1987, pp. 172–176). Adding `S_tree` and distinguishing lattices from forests in `poset_evaluation.py` will complete the STNB Task 2 implementation.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Corrupted Google Search Zotero URL (L11):** `[Balzer et al., 1987, p. 175](https://www.google.com/search?q=zotero://select/library/items/24SNSW2B)` wraps a broken desktop Zotero URI (for Schurz 2024!) inside a Google Search query string.
2. **Core Quintuple Notation Drift (L21):** Writes $K = \langle M_p, M, M_{pp}, C, L \rangle$ whereas `metrics/index.md` L181 and `ISSUE-068` C-11 use $K = \langle M_p, M, M_{pp}, GC, GL \rangle$.
3. **Symbol Collision on $B(N)$:** As noted in `ISSUE-066` A-03, $B(N)$ (base/root elements of net $N$) collides with $B$ (empirical observation base in $\Delta = (B, A)$). Suggest $\operatorname{Roots}(N)$ or $B_{\text{root}}(N)$.
