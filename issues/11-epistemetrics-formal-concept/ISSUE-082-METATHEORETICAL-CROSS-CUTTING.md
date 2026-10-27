# [ISSUE-082] Cross-Cutting Evaluation: Pillar 5 Metatheoretical Metrics (`metatheoretical/*`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-082` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Cross-Cutting (Pillar 5: Metatheoretical Framework) |
| **Evaluated Docs** | [`analogical_support.md`](../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md), [`higher_level_warrant.md`](../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md), [`reduction_capacity.md`](../../docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md), [`semantic_homogeneity.md`](../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md), [`t_theoreticity.md`](../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md), [`unification.md`](../../docs/concepts/theory/metrics/metatheoretical/unification.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (six incompatible graph models and edge vocabularies, inverted edge directions across files, split between unimplemented `LPG-ECHO` $[-1, 1]$ and implemented `D-QBAF` $[0, 1]$, and collapse of conjunctive hyperedges into simple binary paths) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-076`](metatheoretical/ISSUE-076-ANALOGICAL-SUPPORT.md), [`ISSUE-077`](metatheoretical/ISSUE-077-HIGHER-LEVEL-WARRANT.md), [`ISSUE-078`](metatheoretical/ISSUE-078-REDUCTION-CAPACITY.md), [`ISSUE-079`](metatheoretical/ISSUE-079-SEMANTIC-HOMOGENEITY.md), [`ISSUE-080`](metatheoretical/ISSUE-080-T-THEORETICITY.md), [`ISSUE-081`](metatheoretical/ISSUE-081-UNIFICATION.md), [`ISSUE-075`](ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-050`](../09-architecture-workflow-domain/ISSUE-050-ontological-schism-tf-vs-dqbaf-vs-structuralist-tenability-feedback.md), [`ISSUE-055`](../09-architecture-workflow-domain/ISSUE-055-bipartite-inference-hypergraph-conjunctive-premises-and-undercutters.md) |

Severity legend: **Critical** = invalidates the metric suite's architectural/mathematical coherence · **Major** = significant cross-file conflict, redundancy, or domain mismatch · **Minor** = notation, alignment, or presentation issue.

---

## 1. Six Metrics, Six Incompatible Graph Formalisms & Unregistered Edge Vocabularies — **Critical**

**Where.** Across all six files in `docs/concepts/theory/metrics/metatheoretical/`.

**Finding.**
Although all six metrics reside in `docs/concepts/theory/metrics/metatheoretical/` and are intended to evaluate the `TheoryGraph` constructed by `episteme-pipeline` and analyzed by `epistemetrics`, each specification invents its own ad-hoc graph schema, node labels, and edge types—none of which matches `epistemetrics.core.models.NodeType` and `RelationType`:

| Metric Document | Assumed Graph Formalism | Assumed Node Labels / Types | Assumed Edge Labels / Types |
| :--- | :--- | :--- | :--- |
| **`analogical_support.md`** | Untyped weighted adjacency matrix $\mathbf{A} \in \mathbb{R}_{\ge 0}^{N \times N}$ with domain map $\text{Dom}(H)$ | Hypotheses $H \in V$ with $\text{Dom}(H)$ and $a_H(t) \in [-1, 1]$ | Untyped scalar edges $A_{ij} \ge 0$ |
| **`higher_level_warrant.md`** | Vertical hierarchical digraph $(V, E_{\text{warrant}})$ | `V_H`, superordinate theory-element nodes $T \in \text{Sup}(H)$, `:PossessesHigherWarrant` | `:EXPLAINS`, `:JUSTIFIES` (top-down: `T -> H`) |
| **`reduction_capacity.md`** | Pair of theory graphs $G_{T_1}, G_{T_2}$ with vertex morphism $\phi: V(G_{T_1}) \to V(G_{T_2})$ | `:TheoryNet`, intended applications $I(T_1), I(T_2)$ | `:REDUCES_TO`, `:SUBSUMES` with `limit` property |
| **`semantic_homogeneity.md`** | Logical inference graph $G_T = (V_{Ax}, E_{\text{inf}})$ | `:Theory`, axioms/premises/theorems $V_{Ax}$, shared state variables | $E_{\text{inf}}$ (claimed as direct edges between $A_1, A_2$) |
| **`t_theoreticity.md`** | Intra-theory core $T$ + global theory-holon $H$ dependency graph | `:TheoryCore`, term node $\tau$, law nodes $\text{Laws}(G)$ | `:MEASURED_BY`, `:DETERMINED_BY`, `:MEASURED_VIA`, `:LINKED_TO` |
| **`unification.md`** | Deductive derivation DAG $G = (V, E_{\text{derive}})$ | `:Theory`, `:Proposition`, `:BasicAxiom`, `:InitialFact`, `:DerivedTheorem`, `:ExplainedFact` | `:CONTAINS`, `:DERIVED_FROM` |

**Why this blocks execution in `epistemetrics`.**
1. Out of the 17 Neo4j labels and edge types used across these six files, **only 1 (`:EXPLAINS` / `:REDUCES_TO`) exists in `epistemetrics.core.models.RelationType`**!
2. Even the **orientation of deductive/explanatory edges is contradictory across files**:
   - In `higher_level_warrant.md` (L33, L51), derivation/explanation edges run **from premise/theory to conclusion** (`T -[:EXPLAINS]-> H`), so root axioms have **in-degree $0$**.
   - In `unification.md` (L50 vs. L60), the prose states that basic axioms have **in-degree $0$**, while the Cypher query writes `WHERE NOT (b)<-[:DERIVED_FROM]-(:Proposition)`—which on a `:DERIVED_FROM` edge (`conclusion -[:DERIVED_FROM]-> premise`) selects nodes with **no derived conclusions** (leaf theorems)!
   - In `reduction_capacity.md` (L51), `:REDUCES_TO` (`predecessor -> successor`) and `:SUBSUMES` (`successor -> predecessor`) are treated as synonymous despite having opposite orientations.
3. Currently, **none of the six Pillar 5 metrics is implemented as an intrinsic evaluator in `packages/epistemetrics/`** (note that `epistemetrics/epistemic/reduction_evaluation.py` only computes extrinsic Precision/Recall/F1 of predicted `:REDUCES_TO` and `:PRESUPPOSES` links against a gold reference graph, not $SPR$, $ECI$, or $RS$).

**Fix.**
Define a single canonical mapping from `epistemetrics.TheoryGraph` (`NodeType`, `RelationType`, `EpistemicStatus`) to all six Pillar 5 metrics, and standardize edge orientation so that all deductive/explanatory relations (`RelationType.EXPLAINS`, `SUPPORTS`) point **from premise/explanans to conclusion/explanandum**, while `RelationType.REDUCES_TO` points **from predecessor $T_{\text{old}}$ to successor $T_{\text{new}}$**.

---

## 2. Split-Brain Between Unimplemented `LPG-ECHO` ($a_i(t) \in [-1, 1]$) and Implemented `D-QBAF` ($\tau(a) \in [0, 1]$) — **Critical**

**Where.** [`analogical_support.md#L115-L121`](../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L115-L121), [`higher_level_warrant.md#L37-L40`](../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L37-L40), [`adapted_echo_algorithm.md`](../../docs/concepts/theory/metrics/adapted_echo_algorithm.md) vs. [`packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py`](../../packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py) (cf. [`ISSUE-050`](../09-architecture-workflow-domain/ISSUE-050-ontological-schism-tf-vs-dqbaf-vs-structuralist-tenability-feedback.md), [`ISSUE-068` C-10](../10-formal-conceptual-docs/ISSUE-068-conceptual-and-domain-errors.md)).

**Finding.**
Both `analogical_support.md` ($LAB_{\text{norm}}$) and `higher_level_warrant.md` ($HLW$) are parameterized by time-dependent node activations $a_i(t) \in [-1, 1]$ from Thagard's connectionist ECHO algorithm (`adapted_echo_algorithm.md`).
However:
1. **In `packages/epistemetrics/`, `LPG-ECHO` is not implemented.** Instead, `epistemetrics/epistemic/qbaf.py` implements **Quantitative Bipolar Argumentation Framework (D-QBAF)** gradual semantics (`WeightedQuadraticEnergySolver` and `QBAFGradualSemanticsSolver`), which outputs equilibrium justification degrees $\tau^*(a) \in [0, 1]$ around a neutral prior $\tau_0(a) \in [0, 1]$ (default $0.6$).
2. **Incompatible Sign Conventions Break Both Metrics:**
   - If ECHO activations $a_i(t) \in [-1, 1]$ are plugged into $LAB_{\text{norm}}$ and $HLW$ as written, rejected nodes ($a_i < 0$) make $LAB_{\text{norm}} < 0$ (violating its claimed $[0, 1)$ range and non-inhibitory guarantee; see [`ISSUE-076` AS-03](metatheoretical/ISSUE-076-ANALOGICAL-SUPPORT.md)) and make $HLW < 0$ (committing the fallacy of Denying the Antecedent; see [`ISSUE-077` HLW-01](metatheoretical/ISSUE-077-HIGHER-LEVEL-WARRANT.md)).
   - Conversely, if D-QBAF justification degrees $\tau^*(a) \in [0, 1]$ are plugged directly in place of $a_i(t)$ without centering/rectifying, even a **strongly refuted** hypothesis with $\tau^*(a) = 0.05 > 0$ (far below its prior $\tau_0 = 0.6$) contributes a **positive** analogical boost and a **positive** higher-level warrant!

**Fix.**
Define a canonical **Positive Corroboration Activation Adapter** $\alpha^+(u) \in [0, 1]$ that works consistently across both solvers:
- **Under LPG-ECHO ($a_u^* \in [-1, 1]$):** $\alpha^+(u) = \max(0, a_u^*)$.
- **Under D-QBAF ($\tau^*(u) \in [0, 1]$ with prior $\tau_0(u) \in (0, 1)$):**
  $$\alpha^+(u) = \max\!\left(0, \, \frac{\tau^*(u) - \tau_0(u)}{1 - \tau_0(u)}\right) \in [0, 1] \quad \text{(or } \max(0, 2\tau^*(u) - 1)\text{)}.$$
Use $\alpha^+(u) \in [0, 1]$ in both $LAB_{\text{norm}}$ and $HLW$.

---

## 3. Loss of Conjunctive Multi-Premise Structure (AND vs. OR Collapse) Across `semantic_homogeneity.md`, `t_theoreticity.md`, and `unification.md` — **Major**

**Where.** [`semantic_homogeneity.md#L46`](../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L46), [`t_theoreticity.md#L55-L61`](../../docs/concepts/theory/metrics/metatheoretical/t_theoreticity.md#L55-L61), [`unification.md#L50-L63`](../../docs/concepts/theory/metrics/metatheoretical/unification.md#L50-L63) (cf. [`ISSUE-055`](../09-architecture-workflow-domain/ISSUE-055-bipartite-inference-hypergraph-conjunctive-premises-and-undercutters.md), [`ISSUE-068` C-05](../10-formal-conceptual-docs/ISSUE-068-conceptual-and-domain-errors.md)).

**Finding.**
A fundamental theorem of philosophy of science (Duhem 1906; Sneed 1971; Schurz 2014) is that scientific derivations and measurements are **conjunctive (linked multi-premise hyperedges)**:
- A law $l_1$ and an auxiliary law $l_2$ **jointly entail** an empirical prediction $e$: $\{l_1, l_2\} \vdash e$.
- A measurement method $m$ **conjunctively presupposes** both a pre-theoretical optical law $l^*$ and a fundamental mechanical law $l \in \text{Laws}(T)$ to determine $\tau$: $\{l^*, l\} \to m \to \tau$.
- A universal law $l \in Ax(T)$ and a singular initial condition $c_i$ **jointly derive** an observation $d_i$: $\{l, c_i\} \vdash d_i$.

Because `semantic_homogeneity.md`, `t_theoreticity.md`, and `unification.md` attempt to express these multi-premise relationships on a **simple binary graph $(V, E)$ without inference/method mediator nodes**:
1. **`semantic_homogeneity.md`** cannot distinguish whether two axioms $a_1, a_2$ **jointly** derive $e$ ($\{a_1, a_2\} \vdash e$, genuine non-factorizable unity) or whether $a_1 \vdash e$ and $a_2 \vdash e$ **independently** (factorizable redundancy), and worse, looks for direct edges $(a_1, a_2) \in E_{\text{inf}}$ between axioms ([`ISSUE-079` SH-01](metatheoretical/ISSUE-079-SEMANTIC-HOMOGENEITY.md)).
2. **`t_theoreticity.md`** splits a single conjunctive measurement procedure requiring $\{l^*, l\}$ into two separate graph paths $p_1 = (l^* \to \tau)$ and $p_2 = (l \to \tau)$, and then sees $p_1$ as an "independent measurement pathway", misclassifying every $T$-theoretical term as $T$-non-theoretical ([`ISSUE-080` TT-02](metatheoretical/ISSUE-080-T-THEORETICITY.md)).
3. **`unification.md`** lumps singular initial conditions $c_i$ and universal laws $l$ together as in-degree-$0$ nodes in $B$, capping $|D|/|B| < 1.0$ whenever each prediction requires an initial condition ([`ISSUE-081` UN-02](metatheoretical/ISSUE-081-UNIFICATION.md)).

**Fix.**
Represent multi-premise inferences and measurement methods in `TheoryGraph` via **bipartite inference/application nodes** (or hyperedges $e = (\text{Premises}(e), \text{Conclusion}(e))$, aligning with [`ISSUE-055`](../09-architecture-workflow-domain/ISSUE-055-bipartite-inference-hypergraph-conjunctive-premises-and-undercutters.md)):
- In `semantic_homogeneity.md`, two axioms $a_1, a_2$ are co-derivation neighbors iff they belong to the premise set $\text{Premises}(e)$ of a common inference step $e$ leading to $L_E$.
- In `t_theoreticity.md`, a measurement method $m \in M(\tau)$ is an inference/determination node whose prerequisite law set is $\text{Presupposes}(m) = \text{Premises}(m) \cap \text{Laws}(G)$.
- In `unification.md`, $B_{\text{ax}}$ counts only universal axioms (`NodeType.AXIOM` / `HYPOTHESIS`), or counts reusable inference schemas across applications.

---

## 4. Unreconciled Statement-View vs. Non-Statement-View Split Across Pillar 5 — **Major**

**Where.** All six files in `docs/concepts/theory/metrics/metatheoretical/` (cf. [`ISSUE-069` D-04](../10-formal-conceptual-docs/ISSUE-069-philosophical-errors.md)).

**Finding.**
Pillar 5 combines three distinct metatheoretical traditions without a formal bridge between their domain objects:
1. **Statement-View (Syntactic / Proof-Theoretic):** `semantic_homogeneity.md` ($Ax, \operatorname{Cn}(E(Ax_1) \cup E(Ax_2))$), `unification.md` ($Ce(S) = B \cup D$), and `higher_level_warrant.md` ($T \to H$).
2. **Non-Statement-View (Structuralist Model-Theoretic):** `t_theoreticity.md` ($M_p, M_{pp}, M$) and `reduction_capacity.md` ($p: M_p(T') \to M_p(T), I(T_1)$).
3. **Network-Theoretic / Connectionist:** `analogical_support.md` ($\mathbf{D}^{-1}\mathbf{A}, a_{H_2}(t)$).

Because the documents do not specify how a structuralist `TheoryElement` ($T = \langle K, I \rangle$) in `t_theoreticity.md` and `reduction_capacity.md` links to its statement-view axiom set $Ax(T)$ in `semantic_homogeneity.md` and `unification.md`, each metric queries a disjoint set of non-existent node labels (`:TheoryElement` vs. `:TheoryNet` vs. `:TheoryCore` vs. `:Theory`).

**Fix.**
Use `NodeType.THEORY_ELEMENT` as the single canonical theory container in `TheoryGraph`, with:
- Statement-level axioms/laws linked via `NodeType.AXIOM` / `ACTUAL_MODEL` ($Ax(T)$),
- Concept vocabulary linked via `NodeType.CONCEPT` ($\text{Voc}_T(K)$ vs. $\text{Voc}_{NT}(K)$ according to $TI(\tau, T)$),
- Intended applications linked via `RelationType.HAS_INTENDED_APPLICATION` to `NodeType.PARADIGM` ($I(T)$).

---

## 5. Non-Threatening Cross-File Inconsistencies & Notation Misalignments

| Issue | Locations | Details & Recommended Standardization |
| :--- | :--- | :--- |
| **1. Symbol Collision on $H$ Across Pillar 5** | `analogical_support.md` ($H_1, H_2 \in V$: hypothesis nodes)<br>`higher_level_warrant.md` ($H \in V_H$: target hypothesis)<br>`semantic_homogeneity.md` ($H_{\text{axiomatic}}(T)$: homogeneity factor)<br>`t_theoreticity.md` ($H$: global theory-holon) | Reserve $H$ (or $h \in V_H$) for hypotheses, $\mathcal{H}$ for the global Theory-Holon, and $\text{Hom}_{\text{ax}}(T)$ for Axiomatic Homogeneity (avoiding collision with Harmony $H(t)$ in `system_coherence.md` and Hypergraph $H$ in `empirical_content.md`). |
| **2. Symbol Collision on $T$ Across Pillar 5** | `higher_level_warrant.md` ($T \in \text{Sup}(H)$: superordinate theory node)<br>`reduction_capacity.md` ($T, T'$ then $T_1, T_2$: theory-nets)<br>`semantic_homogeneity.md`, `t_theoreticity.md` ($T$: single theory / theory core) | Use $T = \langle K, I \rangle$ for a single Theory-Element, $\mathcal{N}$ (or $TN$) for a Theory-Net, and $T_{\text{old}}, T_{\text{new}}$ for predecessor/successor reduction pairs. |
| **3. Broken Desktop Zotero Links & Misassigned Key `24SNSW2B`** | `higher_level_warrant.md` (L13)<br>`reduction_capacity.md` (L13)<br>`semantic_homogeneity.md` (L13)<br>`unification.md` (L13) | Replace `zotero://select/library/items/...` URIs with standard Markdown reference links or DOIs. Note that in `reduction_capacity.md` (L13), `[Balzer et al., 1987, p. 372]` is linked to `zotero://select/library/items/24SNSW2B`, which is the Zotero item key for **Schurz (2024)** in all other files. |
| **4. Pillar 4 vs. Pillar 5 Placement of `reduction_capacity.md`** | `docs/concepts/theory/metrics/index.md` (L108) vs. `docs/concepts/theory/metrics/metatheoretical/reduction_capacity.md` | `index.md` lists `reduction_capacity.md` under **Pillar 4: Theory Dynamics**, whereas the file resides in `metatheoretical/` (Pillar 5). Synchronize directory location and table placement. |
| **5. Corrupted Markdown Table in `unification.md` & Template Divergence in `analogical_support.md`** | `unification.md` (L68–71)<br>`analogical_support.md` (L1–147) | Fix the collapsed single-line Markdown table in `unification.md` (L68–71) and align `analogical_support.md` with the standard 6-section metric documentation template. |
