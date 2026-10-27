# [ISSUE-095] Cross-Cutting Evaluation: Pillar 2 Epistemic Coherence & Parsimony Metrics (`epistemic_coherence/*`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-095` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Cross-Cutting (Pillar 2: Epistemic Coherence & Parsimony) |
| **Evaluated Docs** | [`conservatism.md`](../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md), [`consistency.md`](../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md), [`elegance_and_economy.md`](../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md), [`node_activation.md`](../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md), [`simplicity.md`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md), [`system_coherence.md`](../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md), [`tenability.md`](../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md), [`adapted_echo_algorithm.md`](../../docs/concepts/theory/metrics/adapted_echo_algorithm.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/epistemic/qbaf.py`), `episteme-pipeline` (`post_processing/theoretical_enrichment/`) |
| **Priority** | **Critical** (intra-pillar schism between undirected $[-1, 1]$ ECHO and directed $[0, 1]$ D-QBAF, contradictory edge directions between explanatory modeling $A \to B$ and evidential propagation $B \to A$, mutually contradictory parsimony assumptions in `simplicity.md` vs. `elegance_and_economy.md`, and complete absence of 6 of 7 evaluators in `epistemetrics`) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-088`](epistemic_coherence/ISSUE-088-CONSERVATISM.md), [`ISSUE-089`](epistemic_coherence/ISSUE-089-CONSISTENCY.md), [`ISSUE-090`](epistemic_coherence/ISSUE-090-ELEGANCE-AND-ECONOMY.md), [`ISSUE-091`](epistemic_coherence/ISSUE-091-NODE-ACTIVATION.md), [`ISSUE-092`](epistemic_coherence/ISSUE-092-SIMPLICITY.md), [`ISSUE-093`](epistemic_coherence/ISSUE-093-SYSTEM-COHERENCE.md), [`ISSUE-094`](epistemic_coherence/ISSUE-094-TENABILITY.md), [`ISSUE-075`](ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-082`](ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md), [`ISSUE-087`](ISSUE-087-THEORY-DYNAMICS-CROSS-CUTTING.md), [`ISSUE-050`](../09-architecture-workflow-domain/ISSUE-050-ontological-schism-tf-vs-dqbaf-vs-structuralist-tenability-feedback.md) |

Severity legend: **Critical** = invalidates the metric suite's architectural/mathematical coherence · **Major** = significant cross-file conflict, redundancy, or domain mismatch · **Minor** = notation, alignment, or presentation issue.

---

## 1. Intra-Pillar Solver Schism: Undirected Symmetric ECHO ($[-1, 1]$) vs. Directed Asymmetric D-QBAF ($[0, 1]$) — **Critical**

**Where.** [`node_activation.md`](../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md), [`system_coherence.md`](../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md), [`adapted_echo_algorithm.md`](../../docs/concepts/theory/metrics/adapted_echo_algorithm.md) vs. [`simplicity.md`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md), [`elegance_and_economy.md`](../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md), [`formal_graph_model.md#L168-L245`](../../docs/concepts/formal_graph_model.md#L168-L245), and [`packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py`](../../packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py).

**Finding.**
Within Pillar 2 (`epistemic_coherence/`), the seven specifications are split across **two mutually incompatible relaxation engines**:

| Dimension | Group A (`node_activation.md`, `system_coherence.md`, `adapted_echo_algorithm.md`) | Group B (`simplicity.md`, `elegance_and_economy.md`, `formal_graph_model.md`, `qbaf.py`) |
| :--- | :--- | :--- |
| **Mathematical Engine** | Thagard's (1989) Connectionist **LPG-ECHO** | Potyka's (2018) **D-QBAF Gradual Semantics** (`WeightedQuadraticEnergySolver`) |
| **State Space & Neutral Point** | Bipolar $a_i(t) \in [-1, 1]$, neutrality at $0.0$ | Unipolar $\rho(a_i), \tau^*(a_i) \in [0, 1]$, neutrality at $0.5$ (or prior $\tau_0(a_i)$) |
| **Graph Symmetry & Edge Weights** | Undirected symmetric matrix $W = W^\top$ with signed scalar weights $w_{ij} \in \mathbb{R}$ | Directed asymmetric graphs $G_{\text{supp}}, G_{\text{att}}$ with unsigned weights $\phi, W_{ji} \in [0, 1]$ |
| **Decay Target** | Decays toward $a_{\text{decay}} = 0.0$ at rate $\theta$ (collapsing all DAGs to $0$ without clamping; [`ISSUE-091` NA-01](epistemic_coherence/ISSUE-091-NODE-ACTIVATION.md)) | Relaxes toward node's intrinsic base score $\tau_0(a_i) \in [0, 1]$ (`qbaf.py` L283) |
| **Codebase Implementation Status** | **Not implemented** in `epistemetrics` or `episteme-pipeline` | **Implemented** in `epistemetrics/epistemic/qbaf.py` (but without `simplicity.md`'s MDL weight scaling or $APS$ initialization) |

Worse, `node_activation.md` (L40–47) attempts to glue the two engines together without coordinate conversion—initializing bipolar ECHO activations $a_i(0) \in [-1, 1]$ directly from unipolar QBAF priors $\tau(a_i) \in [0, 1]$ and plugging QBAF weights $\phi \in [0, 1]$ into an unclipped linear shunting equation that diverges when $|\text{net}_j(t)| > 1$ ([`ISSUE-091` NA-03, NA-04](epistemic_coherence/ISSUE-091-NODE-ACTIVATION.md)).

**Fix.**
1. Establish **D-QBAF (`epistemetrics/epistemic/qbaf.py`)** as the single normative acceptability engine across Pillar 2 (`node_activation.md`, `simplicity.md`, `elegance_and_economy.md`), matching `formal_graph_model.md`.
2. Provide an explicit, self-contained **Bipolar Transformation & Symmetrization Adapter** in `epistemetrics/epistemic/qbaf.py` (or `thagard_echo.py`) for metrics requiring bipolar activations or symmetric constraint matrices (`system_coherence.md`):
   - Bipolar centered activation: $a_i^* = 2\tau^*(a_i) - 1 \in [-1, 1]$ (or prior-centered), with positive acceptance $a_i^+ = \max(0, a_i^*)$ used in $SCS(G)$ ([`ISSUE-093` SC-01](epistemic_coherence/ISSUE-093-SYSTEM-COHERENCE.md)).
   - Symmetric constraint weight: $w_{ij} = \frac{1}{2} \sum_{e \in E(i, j) \cup E(j, i)} \text{pol}(e) W(e)$.

---

## 2. Inverted Edge Orientations Between Explanatory Modeling ($A \to B$) and Evidential Propagation ($B \to A$) — **Critical**

**Where.** [`conservatism.md#L29-L37`](../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L29-L37), [`elegance_and_economy.md#L78-L80`](../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L78-L80), [`simplicity.md#L88-L92`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L88-L92), [`#L147-L148`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L147-L148), [`#L172-L174`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L172-L174), [`node_activation.md#L37`](../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L37), and [`packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py#L560-L567`](../../packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py#L560-L567).

**Finding.**
Across `epistemic_coherence/` and `epistemetrics`, the orientation of edges between **Theoretical Antecedents ($A$)** and **Empirical Observations ($B$)** is inverted depending on whether the author is thinking about *deductive explanation* or *evidential justification*:
1. **Explanatory / Deductive Orientation ($A \to B$):**
   - `RelationType.EXPLAINS` in `epistemetrics/core/models.py` (L405): *"Deductive or explanatory relation from explanans to explanandum"* ($A \to B$).
   - `simplicity.md` (L88–91, L147–148) & `elegance_and_economy.md` (L79): Mapping laws $Z(a, b)$ and weights $\phi(a_i, b)$ are directed from $a_i \in A$ to $b \in B$ ($A \to B$).
2. **Evidential / Justification Orientation ($B \to A$):**
   - `conservatism.md` (L30, L86): Paths run from `Empirical Sentences (Source)` $v_1 \in B$ to `Conclusion (Target)` $v_{|p|} \in A$ ($B \to A$).
   - `node_activation.md` (L16, L49–50) & `simplicity.md` (L172–174, L199): Assume that during QBAF/ECHO relaxation, confirmed empirical observations $b \in B$ propagate positive support energy **into** hypotheses $a_i \in A$ ($B \to A$).

**Why this breaks `epistemetrics/epistemic/qbaf.py`.**
In `qbaf.py` (`_resolve_polarity` L1074 and `solve` L559–567), `RelationType.EXPLAINS` has `default_polarity = +1`, and energy flows strictly from `edge.source` to `edge.target`.
Therefore, when a hypothesis $a \in A$ explains an empirical observation $b \in B$ via `(a)-[:EXPLAINS]->(b)`:
- `qbaf.py` propagates energy **from the hypothesis $a$ to the observation $b$**,
- and the hypothesis $a$ receives **zero corroboration** from the empirical observation $b$ it explains!
Meanwhile, if `conservatism.md` queries for paths `B -> ... -> A`, it misses all `A -[:EXPLAINS]-> B` edges!

**Fix.**
Standardize edge orientation and solver semantics across `epistemetrics` and all Pillar 2 specs:
- **In Storage (`TheoryGraph`):**
  - `RelationType.EXPLAINS` points from explanans to explanandum ($A \to B$).
  - `RelationType.SUPPORTS` points from evidentiary/inferential premise to supported claim ($B \to A$ or $A_1 \to A_2$).
- **In Evidential Propagation (`qbaf.py` & `conservatism.md` Safety):**
  When computing upward empirical justification of hypotheses $a \in A$ from confirmed observations $b \in B$, treat `(a)-[:EXPLAINS]->(b)` (where $b \in B$ is confirmed evidence) as an upward evidential corroboration channel $b \to a$ (modulated by `simplicity.md`'s co-antecedent MDL factor $1/\sum c(a_j)$).

---

## 3. Contradiction Within the Paired Parsimony Suite (`simplicity.md` vs. `elegance_and_economy.md`) — **Major**

**Where.** [`simplicity.md#L27-L30`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L27-L30), [`#L39-L62`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L39-L62), [`#L167-L168`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L167-L168), [`#L180-L201`](../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L180-L201) vs. [`elegance_and_economy.md#L49-L74`](../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L49-L74).

**Finding.**
`docs/concepts/theory/metrics/index.md` (L166) and `simplicity.md` (L189–201) pair `simplicity.md` and `elegance_and_economy.md` as a single multi-scale parsimony suite ("Paired (S&E)"), where `elegance_and_economy.md` computes macro $APS(T)$ and passes it to `simplicity.md` as the QBAF prior $\tau(a_i)$.
However, the two specifications directly contradict each other in two ways:
1. **MDL Content-Element Invariance vs. Raw Node Counting:**
   - `simplicity.md` (L39–62) proves that counting raw nodes $|A|$ is broken by Hempel's Conjunction Problem ($a^* = a_1 \land a_2 \land a_3$) and mandates weighting every node by $c(a_i) = \max(1.0, |Ce(a_i)|)$.
   - `elegance_and_economy.md` (L54, L72) defines $APS(T)$ and $L(M) = w_n |A_{\text{core}}| + w_e |R_{\text{core}}|$ using **unweighted node counts** $|Ax(T)|$ and $|A_{\text{core}}|$ ([`ISSUE-090` EE-02](epistemic_coherence/ISSUE-090-ELEGANCE-AND-ECONOMY.md)).
2. **Algebraically Impossible Thresholds Across Both Diagnostic Tables:**
   - `elegance_and_economy.md` (L98) requires $APS > 0.7$ for "High $APS$", and `simplicity.md` (L182–183) requires $APS \ge 0.8$ for "High Macro Elegance".
   - Yet for any non-empty theory ($|Ax(T)| \ge 1$), the formula $APS(T) = \frac{1}{1 + \log_2(1 + |Ax(T)|) + \log_2(1 + |\Theta(T)|)}$ cannot exceed $0.50$ ([`ISSUE-090` EE-01](epistemic_coherence/ISSUE-090-ELEGANCE-AND-ECONOMY.md), [`ISSUE-092` SM-04](epistemic_coherence/ISSUE-092-SIMPLICITY.md)).

**Fix.**
Define $C_{\text{core}}(T) = \sum_{a \in Ax(T)} c(a)$ using the shared MDL content-element complexity $c(a) = |Ce(a)|$ across both files, and recalibrate $APS(T)$ so that a non-empty minimal core ($C_{\text{core}} = 1, |\Theta| = 0$) scores $APS = 1.0$.

---

## 4. Missing Logical Consistency Metric in Pillar 2 & Package Boundary Split (`epistemetrics` vs. `episteme-pipeline`) — **Major**

**Where.** All 7 files in `docs/concepts/theory/metrics/epistemic_coherence/`, `packages/epistemetrics/`, and `packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/`.

**Finding.**
1. **No Metric in Pillar 2 Actually Measures Logical Consistency of a Theory:**
   - `consistency.md` measures **L2 entity mention embedding similarity** $S_{\text{embed}}(t)$ (which is blind to logical negation and penalizes cross-domain unification; [`ISSUE-089` CN-01](epistemic_coherence/ISSUE-089-CONSISTENCY.md)).
   - `system_coherence.md` measures quadratic Hopfield harmony $w_{ij} a_i^* a_j^*$ (which scores $+1.0$ when all hypotheses of a theory are rejected; [`ISSUE-093` SC-01](epistemic_coherence/ISSUE-093-SYSTEM-COHERENCE.md)).
   - Thus, if a reconstructed theory $T$ contains direct internal contradictions ($(a_1, a_2) \in \mathcal{R}_{att}$ between two of its own core axioms $a_1, a_2 \in Ax(T)$), **no metric in Pillar 2 directly measures its internal logical consistency**!
2. **Package Boundary Split Between `epistemetrics` and `episteme-pipeline`:**
   - Out of the 7 Pillar 2 metrics, **zero** are implemented as metric evaluators in `packages/epistemetrics/` (where `qbaf.py` only computes node justification degrees $\tau^*(a)$ without `conservatism`, `consistency`, `elegance_and_economy`, `simplicity`, `system_coherence`, or `tenability`).
   - Meanwhile, `tenability.md` is implemented inside `packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py`, making `TenabilitySolver` unavailable to standalone `epistemetrics` evaluations unless extracted or bridged.

**Fix.**
1. Move or expose the pure mathematical `TenabilitySolver` and `SafeFormulaEvaluator` in `packages/epistemetrics/src/epistemetrics/epistemic/` (keeping LLM induction/projection in `episteme-pipeline`), and implement the remaining Pillar 2 evaluators in `epistemetrics`.
2. Add an explicit **Internal Logical / Dialectical Consistency** score in `consistency.md` measuring the absence of active internal attack edges $\mathcal{R}_{att}$ within $A(T)$ and between $A(T)$ and $B(T)$.

---

## 5. Non-Threatening Cross-File Inconsistencies & Notation Misalignments

| Issue | Locations | Details & Recommended Standardization |
| :--- | :--- | :--- |
| **1. Five-Way Symbol Collision on $c$ Across Pillar 2** | `conservatism.md` L86 ($c(v_{\text{source}}) \in [0, 1]$: source node confidence)<br>`elegance_and_economy.md` L81 ($c(b \mid A_{\text{core}}) \in [0, 1]$: residual data codelength cost)<br>`simplicity.md` L84 ($c(a_i) \in [1, \infty)$: MDL content-element complexity)<br>`formal_graph_model.md` L96 ($c_m \in C$: document chunk)<br>`formal_graph_model.md` L372 ($c(A \land B)$: fuzzy composite confidence) | Reserve $c(a_i) = \|Ce(a_i)\| \ge 1$ for MDL content-element complexity, $\tau_0(v_{\text{source}})$ for source base plausibility, and $\ell(b \mid A_{\text{core}}) \in [0, 1]$ for residual data description cost. |
| **2. Symbol Collision on $H$ Across Pillar 2** | `conservatism.md` L63 & `simplicity.md` L23, L104 ($H = (V_H, E_H)$: hypothesis subgraph)<br>`simplicity.md` L197–199 ($H_i, H_j$: individual hypothesis nodes)<br>`system_coherence.md` L25, L41 ($H(t)$: global Harmony function) | Use $G_H = (V_H, E_H)$ for a hypothesis subgraph, $h_i \in V_H$ (or $a_i \in A$) for individual hypothesis nodes, and $\mathcal{H}(t)$ for global Thagardian Harmony. |
| **3. Symbol Collision on $E$ Across Pillar 2** | `conservatism.md` L63 & `simplicity.md` L68 ($E, E_H$: edge sets)<br>`consistency.md` L34 ($E_t = \{e_1, \dots, e_k\}$: entity mention set)<br>`simplicity.md` L25, L115 ($E(H), E(G)$: Shannon cluster association entropy)<br>`simplicity.md` L199 ($E$: confirmed evidence node)<br>`tenability.md` L178 ($E_{GC}$: constraint edge set) | Reserve $E$ for edge sets ($E_H, E_{GC}$), use $\mathrm{Ent}_{\text{topic}}(G)$ for Shannon topic entropy, $M(\tau)$ for entity mentions of term $\tau$, and $b \in B$ (or $e \in V_E$) for empirical evidence nodes. |
| **4. Symbol Collision on $\delta$ Across Pillar 2** | `conservatism.md` L72, L75 ($\delta(u, v) \in [0, \infty)$: Euclidean distance between weighted adjacency vectors)<br>`tenability.md` L84, L130 ($\delta, \delta_C \in [0, 1]$: uniform-space blur inaccuracy parameter) | Use $d_{\text{ctx}}(u, v)$ for context/embedding distance in `conservatism.md` and reserve $\delta \in [0, 1]$ for admissible blur tolerances in `tenability.md`. |
| **5. Broken Desktop Zotero Links & Misassigned Key `24SNSW2B`** | `consistency.md` (L13)<br>`elegance_and_economy.md` (L12)<br>`node_activation.md` (L14)<br>`system_coherence.md` (L13)<br>`tenability.md` (30+ occurrences)<br>`docs/reference/theoretical_enrichment.md` (L5) | Replace local `zotero://select/library/items/...` URIs with standard bibliographic links/DOIs. Fix `consistency.md` L13, `elegance_and_economy.md` L12, `tenability.md` L53, and `theoretical_enrichment.md` L5 where `[Balzer et al., 1987]` is linked to `24SNSW2B` (the Zotero key for **Schurz 2024**). |
| **6. Unmapped Numeric Citations & Missing H1 in `simplicity.md`, Missing Implementation Section in `elegance_and_economy.md`** | `simplicity.md` (L1–201)<br>`elegance_and_economy.md` (L90–100)<br>`system_coherence.md` (L7) | Add `# Simplicity (Einfachheit)` H1 and map raw bracket numbers (`[7, 18]`, `[84, 150]`, `[424]`) to author-year references in `simplicity.md`; add `## Measurement & Graph Implementation` to `elegance_and_economy.md`; normalize header casing in `system_coherence.md`. |
