# [ISSUE-084] Formal & Conceptual Evaluation: Kuhnian / Paradigm-Guidance (`paradigm_guidance.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-084` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 4: Theory Dynamics |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/epistemic/poset_evaluation.py`, `dynamics.py`), `episteme-pipeline` |
| **Priority** | **Critical** ($\text{CoreStable}$ uses subset-cardinality equality $|\bigcap_{t=1}^k M_0(t)| = |M_0(1)|$ which fails to detect additions to the root core or weakening of actual models, omits $M_p, M_{pp}, GL$, and operates on infinite model classes; $\Delta PAR_t$ is defined to fix historical masking but omitted from $PGI_t$; and $DCI$ ignores whether paradigm applications $I_0$ are empirically falsified) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-087`](../ISSUE-087-THEORY-DYNAMICS-CROSS-CUTTING.md), [`ISSUE-010`](../../04-diachronic-dynamics/ISSUE-010-theory-reduction-and-kuhn-loss-tracking.md), [`ISSUE-011`](../../04-diachronic-dynamics/ISSUE-011-diachronic-timeline-and-terminology-drift.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or yields inverted diagnostics · **Major** = significant formal flaw, semantic shift, or implementation divergence · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **Partially (Broken Edge & Core Guards)** | Claims to evaluate Kuhnian/Stegmüllerian normal science via core invariance, specialization lineage from $T_0$, and conservation of paradigm applications $I_0$. However: (1) $\Delta PAR_t$ is introduced in §B specifically to prevent historical nodes from masking unguided additions, yet §E omits $\Delta PAR_t$ from $PGI_t$; (2) $DCI(I(t), I_0)$ checks only whether $i \in I_0$ remains listed in $I(t)$, not whether $i$ has been empirically refuted (contradicting L96 *"or fundamental applications fail"*); and (3) $PAR$ checks only syntactic `:SPECIALIZES` reachability without verifying poset acyclicity or model subsumption ($M(T_j) \subseteq M(T_i)$). |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaw in $\text{CoreStable}$)** | (1) $\text{CoreStable}$ (L80) checks $\|\bigcap_{t=1}^k M_0(t)\| = \|M_0(1)\|$ and $\|\bigcap_{t=1}^k GC_0(t)\| = \|GC_0(1)\|$, which only tests $M_0(1) \subseteq M_0(t)$ ($t \ge 1$) and **fails to detect arbitrary additions** $M_0(t) \supsetneq M_0(1)$ to the root core (and is $\infty = \infty$ under the structuralist definition of $M_0$ as an infinite model class); (2) $\text{CoreStable}$ omits $M_p, M_{pp}, GL$ despite defining $K_0(t) = (M_p, M_{pp}, M, GC, GL)_0$ on L78; (3) $\Delta PAR_t$ returns $1.0$ when $\Delta V_t = \emptyset$ even if specialization edges were deleted at step $t$; (4) $PAR$ and $DCI$ lack division-by-zero guards when $\|V(G_t)\| = 0$ or $\|I_0\| = 0$. |
| **3. Free of Semantic Shifts?** | **No (Model Class vs. Axiom Set Shift)** | Shifts $K_0(t) = (M_p, M_{pp}, M, GC, GL)_0$ from Bourbaki set-theoretic model classes (where $M_0(t)$ is the infinite class of actual models satisfying the laws of $T_0$) to finite sets of syntactic axiom nodes in L80, and then to a single Cypher node `(:TheoryElement {is_paradigm_core: true})` with no temporal revision index $t$ in L105–114. |
| **4. Valid & Scientifically Significant?** | **Yes (Core Structuralist Concept)** | Stegmüller's (1976, pp. 169–171, 194) and Balzer, Moulines, & Sneed's (1987, pp. 175–176) formalization of Kuhnian normal science as a paradigm-guided sequence of theory-trees is a cornerstone of structuralist theory dynamics. |

---

## 1. Does the Metric Capture What It Claims It Does?

### PG-01 · $\text{CoreStable}(G_1, \dots, G_k)$ Fails to Detect Root Core Expansion ($M_0(1) \subsetneq M_0(t)$), Is Ill-Defined on Infinite Model Classes, and Ignores $M_p, M_{pp}, GL$ — **Critical**

**Where.** [`paradigm_guidance.md#L76-L81`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L76-L81).

**Finding.**
Section D defines the Core Stability Predicate for $K_0(t) = (M_p, M_{pp}, M, GC, GL)_0$ as:
$$\text{CoreStable} (G_1, \dots, G_k) = \begin{cases} 1 & \text{if } \big|\bigcap_{t=1}^k M_0 (t)\big| = \lvert M_0 (1) \rvert \text{ and } \big|\bigcap_{t=1}^k GC_0 (t)\big| = \lvert GC_0 (1) \rvert \\ 0 & \text{otherwise} \end{cases}$$

This equation has three critical flaws:
1. **Asymmetric Subset Trap ($M_0(1) \subsetneq M_0(t)$ Passes as "Invariant"):**
   For finite sets, $\left|\bigcap_{t=1}^k M_0(t)\right| = |M_0(1)|$ holds if and only if $M_0(1) \subseteq M_0(t)$ for all $t \in \{1, \dots, k\}$. It does **not** enforce $M_0(t) = M_0(1)$!
   - **Under the Syntactic / Graph Reading ($M_0(t)$ = set of law nodes attached to root $T_0$):** If an author mutates the foundational root $T_0$ at $t = 2$ by cramming 10 new ad-hoc laws directly into $M_0(2)$ alongside the original law in $M_0(1)$ ($|M_0(1)| = 1, |M_0(2)| = 11$), then $|M_0(1) \cap M_0(2)| = 1 = |M_0(1)|$, so $\text{CoreStable} = 1$ even though the root core $K_0$ was directly altered instead of remaining an immutable paradigm core with outer specializations!
   - **Under the Model-Theoretic Reading ($M_0(t)$ = class of actual models satisfying the laws of $T_0$):** In structuralism (BMS 1987), $M_0(t)$ is the class of mathematical structures satisfying the laws of $T_0$. First, $M_0(1)$ is **infinite** ($|M_0(1)| = \infty$), so comparing cardinalities $|\bigcap M_0(t)| = |M_0(1)|$ is mathematically undefined on infinite sets. Second, even on a finite universe of candidate structures, weakening a fundamental law of $T_0$ at $t = 2$ **enlarges** the set of allowed models ($M_0(1) \subsetneq M_0(2)$), which again satisfies $|M_0(1) \cap M_0(2)| = |M_0(1)|$ and falsely scores $\text{CoreStable} = 1$!
2. **Omission of $M_p$, $M_{pp}$, and $GL$:**
   L78 explicitly declares the five-component core tuple $K_0(t) = (M_p, M_{pp}, M, GC, GL)_0$, yet L80 only checks $M_0$ and $GC_0$. If a historical revision alters the conceptual/theoretical vocabulary $M_{p,0}(t)$ (a classic Kuhnian conceptual shift!), alters the empirical base $M_{pp,0}(t)$, or severs the inter-theoretical links $GL_0(t)$, $\text{CoreStable}$ still evaluates to $1$.
3. **Inconsistency with `verify_hard_core_invariance` in `dynamics.py`:**
   In `packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py` (L216–270), hard-core invariance checks only `AXIOM` / `ACTUAL_MODEL` / `HARD_CORE` nodes across the entire snapshot (not specifically $T_0$, and ignoring `CONSTRAINT` nodes $GC_0$ entirely).

**Fix.**
Require exact set equality across all core components of the root element $T_0$:
$$\text{CoreStable}(G_1, \dots, G_k) = \mathbb{I}\!\left(\forall t \in \{1, \dots, k\}: K_0(t) = K_0(1)\right)$$
where on a finite `TheoryGraph`, $K_0(t) = \big(V_{M_p}(T_0, t), V_{M_{pp}}(T_0, t), V_M(T_0, t), V_{GC}(T_0, t), E_{GL}(T_0, t)\big)$, i.e., for each component $X \in \{M_p, M_{pp}, M, GC, GL\}$, $X_0(t) = X_0(1)$ (equivalently, $|X_0(t) \cap X_0(1)| = |X_0(1)| = |X_0(t)|$).

---

### PG-02 · Incremental Paradigm Adherence ($\Delta PAR_t$) Is Defined to Prevent Historical Masking, But Omitted from $PGI_t$ and Blind to Edge Deletions — **Major**

**Where.** [`paradigm_guidance.md#L56-L62`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L56-L62) vs. [`#L82-L87`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L82-L87).

**Finding.**
1. **$\Delta PAR_t$ Is Orphaned from the Composite Score $PGI_t$:**
   Section B (L58–61) introduces $\Delta PAR_t(G_t, T_0)$ with the explicit rationale:
   > *"To prevent historical nodes from masking recent unguided additions, we define the adherence ratio specifically for newly added nodes $\Delta V_t = V(G_t) \setminus V(G_{t-1})$."*
   Yet Section E (L86) defines the Composite Paradigm Guidance Index $PGI(G_t, T_0)$ using only cumulative $PAR(G_t, T_0)$:
   $$PGI (G_t, T_0) = \text{CoreStable} (G_1, \dots, G_t) \cdot \left[ w_1 \cdot PAR (G_t, T_0) + w_2 \cdot DCI (I (t), I_0) \right].$$
   Because $\Delta PAR_t$ never enters $PGI$, a large historical theory-net with $|V(G_{t-1})| = 100$ guided nodes that adds $5$ completely disconnected, ad-hoc theory-elements at step $t$ ($\Delta PAR_t = 0.0$) still achieves $PAR(G_t, T_0) = 100/105 = 0.952$ and $PGI_t = 0.976$—failing to detect the onset of paradigm fragmentation!
2. **Blindness of $\Delta PAR_t$ to Specialization Edge Deletions and Subtree Detachments:**
   In $\Delta PAR_t$ (L61), when no new vertices are added at step $t$ ($|\Delta V_t| = |V(G_t) \setminus V(G_{t-1})| = 0$), the piecewise formula unconditionally returns $\Delta PAR_t = 1.0$—even if specialization edges in $E_\alpha(t)$ were deleted at step $t$ so that previously guided nodes in $V(G_{t-1})$ lost their path from $T_0$!

**Fix.**
1. Incorporate $\Delta PAR_t$ into $PGI_t$ (e.g., $w_1 \cdot PAR(G_t, T_0) + w_2 \cdot \Delta PAR_t(G_t, T_0) + w_3 \cdot DCI(I(t), I_0)$ with $w_1 + w_2 + w_3 = 1$, or use the geometric mean $\sqrt{PAR(G_t, T_0) \cdot \Delta PAR_t(G_t, T_0)}$ for structural adherence).
2. When $|\Delta V_t| = 0$, define $\Delta PAR_t(G_t, T_0) = \min(1.0, \, 1.0 + PAR(G_t, T_0) - PAR(G_{t-1}, T_0))$ so that edge deletions reducing reachability at step $t$ are penalized.

---

### PG-03 · $DCI(I(t), I_0)$ Ignores Empirical Falsification / Tenability of Paradigm Applications, Contradicting the Diagnostic Scale — **Major**

**Where.** [`paradigm_guidance.md#L63-L74`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L63-L74) vs. [`#L96`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L96).

**Finding.**
1. **Claimed vs. Tenable Paradigm Applications:**
   On L71, the Domain Conservation Index is defined as:
   $$DCI (I (t), I_0) = \frac{\lvert I_0 \cap I (t) \rvert}{\lvert I_0 \rvert}$$
   where $I(t)$ is *"the total set of intended applications claimed by the theory-net at revision $t$"* (L66).
   However, the Diagnostic Scale on L96 states that $PGI < 0.5$ (**Paradigm Crisis**) occurs when:
   > *"newly introduced models bypass $T_0$ or **fundamental applications fail**."*
   If a foundational paradigm application $i_0 \in I_0$ remains attached to the theory-net in $I(t)$ at time $t$ **but empirically fails** (i.e. becomes an unresolved Type-a anomaly $i_0 \in F_{\text{Typ a}}(t)$ with `EpistemicStatus.ANOMALOUS`, or fails Tenability $TS_{\text{local}}(i_0, M) < 0.5$), $i_0$ is still an element of $I_0 \cap I(t)$, so $DCI(I(t), I_0) = 1.0$!
2. **Structuralist Specialization Constraint on $I(T_j)$:**
   Furthermore, in structuralism (BMS 1987, p. 171), each specialized theory-element $T_j = \langle K_j, I_j \rangle$ restricts the intended application domain ($I_j \subseteq I_i$ for $T_j \alpha T_i$). If $I(t) = \bigcup_{T_j \in V(G_t)} I_j$ is simply the union over all vertices, then as long as the root node $T_0 = \langle K_0, I_0 \rangle$ remains in $V(G_t)$, $I_0 \subseteq I(t)$ is trivially $1.0$ unless $I_0$ is intersected with the **confirmed / tenable** applications $F(I(t))$!

**Fix.**
Define $DCI$ over the **tenable / non-anomalous** intended applications $I_{\text{tenable}}(t) = \{i \in I(t) \mid \text{status}(i) \neq \text{ANOMALOUS} \land TS_{\text{local}}(i) \ge \tau_{\text{ten}}\}$:
$$DCI(I_{\text{tenable}}(t), I_0) = \begin{cases} \frac{|I_0 \cap I_{\text{tenable}}(t)|}{|I_0|} & \text{if } |I_0| > 0 \\ 1.0 & \text{if } |I_0| = 0 \end{cases}$$

---

### PG-04 · $PAR(G_t, T_0)$ Checks Only Syntactic `:SPECIALIZES` Reachability Without Verifying Poset Acyclicity or Model Subsumption — **Major**

**Where.** [`paradigm_guidance.md#L44-L54`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L44-L54) vs. [`packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L260-L291`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L260-L291), [`#L421-L542`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py#L421-L542).

**Finding.**
In §Theoretical Grounding (L26–27), Core Specialization requires that all new elements are **formal core specializations** ($K_i(t) \alpha K_0$). In BMS (1987, pp. 169–175), $(V(G_t), E_\alpha)$ must be a **strict partial order (DAG)** where each specialization edge $(T_i, T_j) \in E_\alpha$ satisfies model subsumption ($M_p(T_j) = M_p(T_i)$, $M(T_j) \subseteq M(T_i)$, $GC(T_j) \subseteq GC(T_i)$).
However, $PAR(G_t, T_0)$ on L51 and the Cypher query on L105–114 treat *any* edge labeled `:SPECIALIZES` as valid, without checking:
1. Whether $E_\alpha$ contains directed cycles (violating the poset condition; cf. `verify_strict_partial_order` in `poset_evaluation.py`).
2. Whether $(T_i, T_j) \in E_\alpha$ satisfies hierarchical model subsumption (`check_hierarchical_subsumption` in `poset_evaluation.py`).

**Fix.**
Restrict $E_\alpha^{\text{valid}}$ to specialization edges that pass `check_hierarchical_subsumption` on a cycle-free specialization DAG, or weight $PAR(G_t, T_0)$ by `hierarchical_subsumption_score` from `poset_evaluation.py`.

---

## 2. Is the Metric Formally & Mathematically Correct?

### PG-05 · Cypher Query Lacks Revision Index $t$, Miscounts Under Multiple/Missing Roots, and Does Not Compute $PAR$ or $PGI$ — **Major**

**Where.** [`paradigm_guidance.md#L100-L114`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L100-L114).

**Finding.**
```cypher
MATCH (root:TheoryElement {is_paradigm_core: true, theory_id: $theory_id})
MATCH (t:TheoryElement {theory_id: $theory_id})
WHERE t <> root 
  AND NOT (root)-[:SPECIALIZES*]->(t)
RETURN 
  count(t) AS unguided_node_count,
  collect(t.id) AS unguided_node_ids;
```
1. **Missing Temporal Filter ($t$):** Every equation in §Formal Specification ($PAR(G_t, T_0)$, $\Delta PAR_t$, $DCI(I(t), I_0)$, $\text{CoreStable}(G_1, \dots, G_t)$, $PGI(G_t, T_0)$) is a function of revision stage $t$, yet the Cypher query has no revision/epoch filter (`t.epoch <= $t` or `version_id`), collapsing all historical epochs together.
2. **Missing Root / Multiple Root Bug:** If no node has the unregistered attribute `is_paradigm_core: true` (in `poset_evaluation.py` L228, the root $T_0$ is identified topologically via `find_poset_roots` as the unique in-degree-$0$ node, not via `is_paradigm_core: true`!), the first `MATCH` produces 0 rows and `count(t)` returns `0`—falsely reporting `0` unguided nodes when there is no paradigm root at all! Conversely, if two nodes have `is_paradigm_core: true`, `MATCH (root)... MATCH (t)...` forms a Cartesian product and double-counts `t`.
3. **Division by Zero in $PAR(G_t, T_0)$ and $DCI(I(t), I_0)$:** Neither L51 ($PAR$) nor L71 ($DCI$) guards against $|V(G_t)| = 0$ or $|I_0| = 0$ (unlike $\Delta PAR_t$ on L61, which explicitly guards $|\Delta V_t| = 0$).

**Fix.**
Guard $|V(G_t)| = 0$ and $|I_0| = 0$ in the mathematical specification, and update the Cypher query to filter by epoch/version, match `$root_id` (or topological root), and return `par_score` alongside `unguided_node_ids`.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### PG-06 · Shift Between Bourbaki Core Quintuple $K_0 = (M_p, M_{pp}, M, GC, GL)_0$ and Flat Property-Graph `:TheoryElement` Nodes — **Major**

**Where.** [`paradigm_guidance.md#L25-L29`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L25-L29), [`#L78-L80`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L78-L80) vs. [`#L105-L114`](../../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L105-L114).

**Finding.**
1. On L26, specialization is written between cores: $K_i(t) \alpha K_0$. On L45–47, specialization is written between theory-elements: $T_0 \xrightarrow{\alpha, *} T$ (note: in BMS 1987, p. 171, specialization $\alpha$ is a relation between *theory-elements* $T_j \alpha T_i$, where $T_i = \langle K_i, I_i \rangle$).
2. On L78–80, $\text{CoreStable}$ accesses the internal sets $M_0(t)$ and $GC_0(t)$ of $T_0$, whereas the Cypher implementation on L105–114 treats `:TheoryElement` as an atomic vertex without showing how $M_0(t)$, $GC_0(t)$, or $I(t)$ are traversed via `HAS_ACTUAL_MODEL`, `HAS_CONSTRAINT`, and `HAS_INTENDED_APPLICATION` / `HAS_PARADIGM` (the canonical relations in `epistemetrics/core/models.py` L481–486).

**Fix.**
Explicitly specify the graph traversal from `T_0: NodeType.THEORY_ELEMENT` to its component sets via `RelationType.HAS_ACTUAL_MODEL` ($M_0$), `HAS_POTENTIAL_MODEL` ($M_{p,0}$), `HAS_PARTIAL_POTENTIAL_MODEL` ($M_{pp,0}$), `HAS_CONSTRAINT` ($GC_0$), `HAS_PARADIGM` ($I_0$), and `HAS_INTENDED_APPLICATION` ($I(t)$).

---

## 4. Is the Metric Valid and Scientifically Significant?

### PG-07 · Missing Implementation of $PAR$, $\Delta PAR_t$, $DCI$, and $PGI$ in `epistemetrics` — **Major**

**Where.** [`packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py`](../../../packages/epistemetrics/src/epistemetrics/epistemic/poset_evaluation.py) and [`dynamics.py`](../../../packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py).

**Finding.**
While `poset_evaluation.py` implements static poset checks (`is_dag`, `has_unique_root`, `hierarchical_subsumption_score`) and `dynamics.py` implements `verify_hard_core_invariance`, neither module computes $PAR(G_t, T_0)$, $\Delta PAR_t(G_t, T_0)$, $DCI(I(t), I_0)$, or the composite $PGI(G_t, T_0)$ across a sequence of snapshots $\langle G_1, \dots, G_k \rangle$. Adding `evaluate_paradigm_guidance(snapshots)` to `epistemetrics/epistemic/dynamics.py` will directly unite `poset_evaluation.py` and `dynamics.py`.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Duplicate Section Heading (L118–120):** Line 118 has an empty `## Grounding References` heading immediately followed on Line 120 by `## References & Theoretical Grounding`.
2. **Misassigned Zotero Key (L13):** Links `[Balzer et al., 1987, pp. 175–176]` to `zotero://select/library/items/24SNSW2B` (the Zotero key for Schurz 2024).
3. **Direction of $\alpha$ Notation (L27 vs. L45–47):** L27 writes $K_i(t) \alpha K_0$ (child $\alpha$ parent), whereas L45–47 defines $(T_i, T_j) \in E_\alpha$ and $T_0 \xrightarrow{\alpha, *} T$ from parent to child ($T_0 \to T$). While `poset_evaluation.py` L177 also uses parent $\to$ child (`T_i -> T_j` where $T_j$ specializes $T_i$), this convention should be explicitly noted so $T_j \alpha T_i$ and $T_i \xrightarrow{\alpha} T_j$ are not confused.
