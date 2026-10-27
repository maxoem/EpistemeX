# [ISSUE-100] Formal & Conceptual Evaluation: Non-Cyclic Form / DAG Property (`dag_property.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-100` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 1: Structural & Topological Metrics (Logical Integrity Constraints) |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/structural_topology/dag_property.md`](../../../docs/concepts/theory/metrics/structural_topology/dag_property.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/epistemic/poset_evaluation.py`, `analysis.py`), `episteme-pipeline` |
| **Priority** | **Critical** (Directly contradicts `hierarchical_conformity.md` which requires foundational axioms in $T_0$ to form a Strongly Connected Component $|SCC| > 1$ of mutual presupposition, contradicts `theory_nets_and_topologies.md` which defines $\alpha$ as a *reflexive* partial order, and conflicts with `analysis.py` which runs `nx.is_directed_acyclic_graph` on the entire unfiltered graph including symmetric/cyclic coherence and attack edges) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-101`](ISSUE-101-HIERARCHICAL-CONFORMITY.md), [`ISSUE-107`](../ISSUE-107-STRUCTURAL-TOPOLOGY-CROSS-CUTTING.md), [`ISSUE-066`](../../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core, yields inverted diagnostics, or is mathematically uncomputable as written · **Major** = significant formal flaw, semantic shift, gaming vulnerability, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **Partially (Broken by Cross-Edge Orientation Collisions & Uncondensed $T_0$ SCCs)** | Claims to detect logical circularity (*petitio principii*) in intra-theory specialization and derivation hierarchies. However, (1) `hierarchical_conformity.md` (L34, L69) explicitly states that valid micro-level foundational axioms in $T_0$ **must** form a Strongly Connected Component ($\|SCC\| > 1$) of mutual presupposition before macro-condensation—so running `dag_property.md` on an uncondensed micro-graph flags valid cooperating core axioms as a "fatal logical fallacy"; (2) Pooling `specializes`, `derives_from`, and `explains` into a single subgraph creates artificial cycles because `derives_from` ($B \xrightarrow{\text{derives\_from}} A$: child to parent) has the **opposite edge direction** of `explains` ($A \xrightarrow{\text{explains}} B$: parent to child)! |
| **2. Formally & Mathematically Correct?** | **Mostly Correct, with Edge-Orientation & Empty-Graph Bugs** | (1) $\text{CircularityPenalty}(G) = \frac{\|V_{\text{cyclic}}\|}{\|V\|}$ divides by $0$ when $\|V\| = 0$; (2) Pooling converse relation types (`explains` $A \to B$ vs. `derives_from` $B \to A$ or inconsistent `specializes` directions) creates false 2-cycles $A \rightleftarrows B$ even when the hierarchy is strictly acyclic; (3) Contradicts `theory_nets_and_topologies.md` (L53), which defines $\alpha$ as a **reflexive** partial order ($T_i \alpha T_i$), whereas `dag_property.md` (L24) defines $\alpha$ as **irreflexive** ($\neg(T_i \alpha T_i)$). |
| **3. Free of Semantic Shifts?** | **No (Major Shifts)** | Shifts between macro-level **Theory-Elements** $T_i = \langle K_i, I_i \rangle$ ordered by model-theoretic specialization $\alpha$ (L22–28) and micro-level **Propositions / Claims** connected by `specializes`, `derives_from`, `explains` (L34), while `epistemetrics/analysis.py` (L145) evaluates `is_dag` on the **entire unfiltered property graph** (including mutual attacks $\mathcal{R}_{\text{att}}$ and symmetric `COHERES_WITH` edges). |
| **4. Valid & Scientifically Significant?** | **Yes (Core Structuralist & Deductive Prerequisite)** | Acyclicity of the strict specialization relation ($\prec_\sigma$) and of deductive derivations is a foundational mathematical requirement of structuralist theory-nets (Balzer et al. 1987, pp. 172–173). |

---

## 1. Does the Metric Capture What It Claims It Does?

### DP-01 · Artificial 2-Cycles Created by Pooling Converse Edge Types (`explains` $A \to B$ vs. `derives_from` $B \to A$) in the Target Subgraph — **Critical**

**Where.** [`dag_property.md#L34`](../../../docs/concepts/theory/metrics/structural_topology/dag_property.md#L34) vs. [`unification.md#L64-L69`](../../../docs/concepts/theory/metrics/metatheoretical/unification.md#L64-L69), [`hierarchical_conformity.md#L43`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L43), and [`packages/epistemetrics/src/epistemetrics/core/models.py#L404-L454`](../../../packages/epistemetrics/src/epistemetrics/core/models.py#L404-L454).

**Finding.**
L34 specifies that acyclicity is evaluated on the subgraph restricted to:
$$\lambda_e(e) \in \{\mathsf{specializes}, \mathsf{derives\_from}, \mathsf{explains}\}.$$
Consider the edge directions of these three relations across the documentation and codebase:
1. **`explains` (`RelationType.EXPLAINS`):** Points from **general premise / explanans $A$ to derived conclusion / explanandum $B$** ($A \to B$).
2. **`derives_from`:** Linguistically and semantically, "$B$ derives from $A$" points from **derived conclusion $B$ to general premise $A$** ($B \to A$). (Moreover, `derives_from` is not even a valid enum member in `epistemetrics.RelationType`!).
3. **`specializes` (`RelationType.SPECIALIZES`):** In `hierarchical_conformity.md` (L43: *"directed edges $(u, v) \in E$ indicate $u \text{ specializes } v$"* and L75: `(t)-[:SPECIALIZES]->(:TheoryElement)`), `specializes` points from **specialized child $B$ to general parent $A$** ($B \to A$), whereas in `poset_evaluation.py` (L177) and `schema.md` (L90) it points from **parent $A$ to child $B$** ($A \to B$)!

**Consequence:**
If a general law $A$ explains a specialized law $B$ (`(A)-[:EXPLAINS]->(B)`) AND $B$ is marked as deriving from or specializing $A$ (`(B)-[:DERIVES_FROM]->(A)` or `(B)-[:SPECIALIZES]->(A)`), then pooling these edges into one directed graph without orientation normalization creates the directed 2-cycle:
$$A \xrightarrow{\text{explains}} B \xrightarrow{\text{derives\_from / specializes}} A!$$
`IsDAG(G)` immediately returns $0$ and `CircularityPenalty(G)` flags $\{A, B\}$ as a "fatal logical fallacy (petitio principii)", when in fact both edges express the **exact same valid asymmetric hierarchy** ($A$ is more general than $B$)!

**Fix.**
1. Replace unregistered `derives_from` with canonical `epistemetrics.RelationType` members (`SPECIALIZES`, `EXPLAINS`, `SUPPORTS` / `DEDUCES`).
2. Explicitly normalize all hierarchical edges into a **single canonical parent-to-child orientation** (general/premise $\to$ specialized/derived) before running cycle detection.

---

### DP-02 · Direct Contradiction with `hierarchical_conformity.md` on Cooperating Foundational Axioms in $T_0$ ($|SCC| > 1$) and Unfiltered `analysis.py` (`is_dag`) — **Critical**

**Where.** [`dag_property.md#L14-L17`](../../../docs/concepts/theory/metrics/structural_topology/dag_property.md#L14-L17), [`#L44-L46`](../../../docs/concepts/theory/metrics/structural_topology/dag_property.md#L44-L46) vs. [`hierarchical_conformity.md#L21-L36`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L21-L36), [`#L69`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L69), and [`packages/epistemetrics/src/epistemetrics/analysis.py#L142-L147`](../../../packages/epistemetrics/src/epistemetrics/analysis.py#L142-L147).

**Finding.**
1. **Conflict with `hierarchical_conformity.md` over Micro-Level Cooperating Axioms ($T_0$):**
   In `hierarchical_conformity.md` (L21–23, L34, L69):
   > *"Internally, these fundamental laws are non-hierarchical; they combine via logical conjunction and mutually presuppose one another... In a directed dependency graph, they should form a Strongly Connected Component (SCC) of mutual presupposition... Collapse valid, strongly connected foundational components (SCCs) into a single macro-node $T_0$."*
   If `dag_property.md` is run on the micro-level proposition graph *before* valid mutually presupposing axiom clusters $K_0$ are condensed into macro-elements $T_i$, every cooperating axiom core with $|SCC(v)| > 1$ is penalized by $\text{CircularityPenalty}(G)$ and submitted to conflict resolution (L56–57) to delete one of its edges!
2. **Codebase Bug in `epistemetrics/analysis.py` (L142–147) vs. `poset_evaluation.py` (L161–171):**
   - In [`epistemetrics/analysis.py`](../../../packages/epistemetrics/src/epistemetrics/analysis.py#L142-L147), `analyze_theory_graph` computes `is_dag = nx.is_directed_acyclic_graph(g)` on the **entire unfiltered `TheoryGraph`** `g`! Because `TheoryGraph` contains mutual dialectical attacks ($a_1 \rightleftarrows a_2 \in \mathcal{R}_{\text{att}}$) and symmetric coherence edges (`COHERES_WITH`, `EQUIVALENT_TO`), `EpistemicReport.is_dag` evaluates to `False` on valid theories that have dialectical debates or equivalence links!
   - Conversely, [`epistemetrics/epistemic/poset_evaluation.py`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L161-L221) filters *only* `NodeType.THEORY_ELEMENT` and `RelationType.SPECIALIZES` (ignoring proposition-level `EXPLAINS` / `SUPPORTS` and missing `CircularityPenalty(G)`).

**Fix.**
1. Specify the execution order between micro-core condensation and DAG verification:
   - **Macro-Poset DAG Check (`poset_evaluation.py`):** Evaluated over condensed `TheoryElement` nodes and `SPECIALIZES` edges ($N = \langle T, \alpha \rangle$).
   - **Micro-Derivation DAG Check:** Evaluated over non-equivalent deductive derivation edges after quotienting out explicit logical equivalences (`EQUIVALENT_TO`) and mutually presupposing co-axioms within the same `TheoryElement` core $K_i$.
2. Fix `epistemetrics/analysis.py` (L145) to evaluate `is_dag` on the hierarchical specialization/derivation projection rather than the unfiltered bipolar graph.

---

## 2. Is the Metric Formally & Mathematically Correct?

### DP-03 · Reflexive Partial Order ($\le$) in `theory_nets_and_topologies.md` vs. Strict Partial Order ($<$) in `dag_property.md`, and Division by Zero When $|V| = 0$ — **Major**

**Where.** [`dag_property.md#L22-L28`](../../../docs/concepts/theory/metrics/structural_topology/dag_property.md#L22-L28), [`#L44-L46`](../../../docs/concepts/theory/metrics/structural_topology/dag_property.md#L44-L46) vs. [`theory_nets_and_topologies.md#L51-L56`](../../../docs/concepts/theory_nets_and_topologies.md#L51-L56) and [`hierarchical_conformity.md#L47`](../../../docs/concepts/theory/metrics/structural_topology/hierarchical_conformity.md#L47).

**Finding.**
1. **Reflexive vs. Irreflexive Definition of $\alpha$ Across Docs:**
   - `theory_nets_and_topologies.md` (L53–55) defines $\alpha$ as a **weak (reflexive) partial order**:
     1. Reflexivity: $T_i \, \alpha \, T_i$
     2. Antisymmetry: $T_i \, \alpha \, T_j \land T_j \, \alpha \, T_i \implies T_i = T_j$
     3. Transitivity.
   - `hierarchical_conformity.md` (L47) also assumes $\alpha$ is reflexive: $B(N) = \{T_i \in T \mid \forall T_j \in T \, (T_j \, \alpha \, T_i \implies T_j = T_i)\}$ (if $\alpha$ were irreflexive, $T_j = T_i$ would never satisfy $T_j \, \alpha \, T_i$, which is fine, or if reflexive it requires $T_j = T_i$).
   - `dag_property.md` (L22–26) defines the exact same symbol $\alpha$ as a **strict (irreflexive) partial order**: $\forall T_i \in T, \neg(T_i \, \alpha \, T_i)$, and L46 penalizes self-loops $(v, v) \in E$ as cycles!
   As noted in [`ISSUE-067` B-30](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md#b-30--poset--dag-antisymmetry-is-about-cycles-not-definitions--minor), a reflexive relation has a self-loop at every node, so its graph has $\text{CircularityPenalty}(G) = 1.0$ and $\text{IsDAG}(G) = 0$! Only the **strict part** $\prec_\alpha$ (or Hasse diagram / transitive reduction) is a DAG.
2. **Division by Zero in $\text{CircularityPenalty}(G)$ When $|V| = 0$ (L44):**
   $$\text{CircularityPenalty}(G) = \frac{|V_{\text{cyclic}}|}{|V|}$$
   When $|V| = 0$ (e.g. when `extract_specialization_subgraph` finds 0 `THEORY_ELEMENT` nodes in a proposition-only graph), $|V| = 0$ causes a `ZeroDivisionError`.

**Fix.**
1. Standardize notation across all documents: use $\preceq_\sigma$ (or $\alpha$) for the weak reflexive specialization poset in order theory, and explicitly state that graph edges $E_{\text{spec}}$ store the **strict specialization relation** $\prec_\sigma$ (irreflexive, asymmetric) or its Hasse diagram (transitive reduction).
2. Guard $|V| = 0$ in $\text{CircularityPenalty}(G)$ by returning $0.0$ when $|V| = 0$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### DP-04 · Silent Shift Between Global Vertex Set $V$ and Hierarchical Subgraph $V_{\text{hier}}$ in $\text{CircularityPenalty}(G)$ — **Minor**

**Where.** [`dag_property.md#L33-L46`](../../../docs/concepts/theory/metrics/structural_topology/dag_property.md#L33-L46).

**Finding.**
L33–34 restricts evaluation to hierarchical edge types $\lambda_e(e) \in \{\mathsf{specializes}, \dots\}$, but L44 divides $|V_{\text{cyclic}}|$ by $|V|$ (the global vertex count of $G$, which includes L1 chunks, L2 entities `Person`/`Work`, and isolated observation units that cannot participate in specialization cycles). Including non-hierarchical nodes in the denominator $|V|$ artificially dilutes $\text{CircularityPenalty}(G)$.

**Fix.**
Define the denominator of $\text{CircularityPenalty}(G_{\text{hier}})$ over the active hierarchical vertex set $V_{\text{hier}}$ (nodes of target theoretical types or incident to $E_{\text{hier}}$).

---

## 4. Is the Metric Valid and Scientifically Significant?

### DP-05 · Missing `CircularityPenalty` Field on `PosetEvaluationResult` in `epistemetrics` — **Minor**

**Where.** [`packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L26-L115`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L26-L115).

**Finding.**
`PosetEvaluationResult` in `poset_evaluation.py` computes `is_dag: bool`, `is_strict_partial_order: bool`, and `cycles: list[list[str]]`, but does not compute or expose `circularity_penalty: float` ($|V_{\text{cyclic}}| / |V_{\text{hier}}|$ via Tarjan's SCCs + self-loops, which runs in $O(|V| + |E|)$ time compared to `nx.simple_cycles` which can be exponential $O((|V| + |E|)(c + 1))$ in graphs with many overlapping cycles!).

**Fix.**
Compute $V_{\text{cyclic}}$ via `nx.strongly_connected_components(graph)` and `nx.nodes_with_selfloops(graph)` in $O(|V| + |E|)$ time in `poset_evaluation.py` and expose `circularity_penalty: float` on `PosetEvaluationResult`.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Header Casing Typo (L7):** `# Non-CYCLIC Form (Dag Property)` mixes ALL-CAPS `CYCLIC` with Title-Case `Dag`. Change to `# Non-Cyclic Form (DAG Property)`.
2. **Broken Desktop Zotero Link & Wrong Key `24SNSW2B` for Balzer et al. (1987) (L12):** `[Balzer et al., 1987, pp. 172–173](zotero://select/library/items/24SNSW2B)` links Balzer et al. (1987) to Schurz's Zotero key `24SNSW2B`.
