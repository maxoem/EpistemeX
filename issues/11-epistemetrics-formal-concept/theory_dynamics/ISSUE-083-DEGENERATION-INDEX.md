# [ISSUE-083] Formal & Conceptual Evaluation: Degeneration Index & Immunization Tracking (`degeneration_index.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-083` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 4: Theory Dynamics |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/epistemic/dynamics.py`), `episteme-pipeline` |
| **Priority** | **Critical** (contains contradictory definitions of excess empirical content $\Delta_{\text{content}}$, inverted inclusion direction for structuralist $\operatorname{Cn}(K)$, perverse diagnostic incentive where accumulating direct refutations $F_{\text{Typ a}}$ lowers $D(V_j)$ and diagnoses a refuted theory as "Progressive", and a complete formula split-brain with `dynamics.py`) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-087`](../ISSUE-087-THEORY-DYNAMICS-CROSS-CUTTING.md), [`ISSUE-072`](../empirical_power/ISSUE-072-EMPIRICAL-CONTENT.md), [`ISSUE-075`](../ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-066`](../../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or yields inverted diagnostics · **Major** = significant formal flaw, semantic shift, or implementation divergence · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Inverted Under Direct Refutation)** | Claims to diagnose Lakatosian degeneration and distinguish progressive from degenerating research programmes. However, because direct empirical refutations $|F_{\text{Typ a}}(V_j)|$ sit in the **denominator** of $D(V_j) = \frac{\|F_{\text{Typ b}}\|}{\|S\| + \|F_{\text{Typ a}}\|}$, a theory that gains **zero** new successes and suffers **massive new direct falsifications** ($|F_{\text{Typ a}}| \uparrow$) sees $D(V_j) \to 0$ and $\Delta D < 0$, which the diagnostic table (L61, L84) falsely classifies as a **"Progressive Research Programme (genuine successes outpace anomalies)"**. |
| **2. Formally & Mathematically Correct?** | **No (4 Critical/Major Flaws)** | (1) L30 defines $\Delta_{\text{content}} = \|\operatorname{Cn}(K_{i+1}) \setminus \operatorname{Cn}(K_i)\| = 0$, omitting the $\setminus \{a\}$ exclusion from L15 so that accommodating anomaly $a$ makes $\Delta_{\text{content}} \ge 1$ (or $\infty$ under deductive closure); (2) in structuralist model theory, specialization *shrinks* $\operatorname{Cn}(K_{i+1}) \subseteq \operatorname{Cn}(K_i)$ while domain restriction *expands* it; (3) $\Delta_{\text{anom}}$, $V_{\text{progressive}}$, and $V_{\text{immunizing}}$ are never formally defined, and $II(K_i, K_{i+1})$, $RPI(\mathcal{E})$, $D(V_j)$, and $\Delta D$ all lack division-by-zero guards; (4) `dynamics.py` implements a completely different formula $DI = \frac{\Delta\|\text{Aux}\| + \|\text{Anom}\|}{\Delta\|\text{Emp}\| + \epsilon}$ and clamps `anom_resolved = max(1, ...)` when 0 anomalies exist. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts across four incompatible representations: (a) structuralist theory-elements $E_{i+1} = \langle K_{i+1}, I_{i+1} \rangle$ with $a \in I \subseteq M_{pp}$, (b) Tarskian deductive sentence sets $\operatorname{Cn}(K)$, (c) two disconnected Neo4j schemas within the same file (`:RESOLVES_ANOMALY` / `:PREDICTS_NOVEL` / `:AdHocImmunization` in Step 1 vs. `:TheoryVersion` / `:HAS_FAILURE_B` / `:FailureTypB` in Step 2), and (d) edge-blind node-type counting in `epistemetrics/epistemic/dynamics.py`. |
| **4. Valid & Scientifically Significant?** | **Yes (Core Concept)** | Lakatos's (1978) methodology of scientific research programmes and Schurz's (2014, §2.5.3; 2024, pp. 51, 59–61) distinction between direct refutations (Type-a) and ad-hoc immunizations (Type-b) are foundational to diachronic theory evaluation (STNB Task 5), provided the immunization ratio is paired with an empirical net-success condition. |

---

## 1. Does the Metric Capture What It Claims It Does?

### DI-01 · Accumulating Direct Empirical Refutations ($|F_{\text{Typ a}}| \uparrow$) Drives $D(V_j) \to 0$ and $\Delta D < 0$, Falsely Diagnosing a Refuted Programme as "Progressive" — **Critical**

**Where.** [`degeneration_index.md#L50-L61`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L50-L61), [`#L82-L87`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L82-L87).

**Finding.**
On L52–61, the document defines Schurz's Degeneration Index and Trajectory Trend as:
$$D (V_j) = \frac{|F_{\text{Typ b}} (V_j)|}{|S (V_j)| + |F_{\text{Typ a}} (V_j)|}, \qquad \Delta D = \frac{D (V_m) - D (V_1)}{m - 1}$$
and states the diagnostic rule (L60–61, L84):
- $\Delta D \le 0$: **Progressive Research Programme** (*"genuine successes outpace anomalies"*).
- $\Delta D \le 0, D < 0.3$: **Progressive Programme** (*"Healthy Lakatosian growth; true empirical successes dominate"*).

**Mathematical Counterexample:**
Suppose at version $V_1$, a theory has $1$ genuine success ($|S(V_1)| = 1$), $0$ direct failures ($|F_{\text{Typ a}}(V_1)| = 0$), and $1$ immunized failure ($|F_{\text{Typ b}}(V_1)| = 1$). Then:
$$D(V_1) = \frac{1}{1 + 0} = 1.0.$$
At version $V_2$, the theory achieves **zero new empirical successes** ($|S(V_2)| = 1$), keeps its $1$ immunized failure ($|F_{\text{Typ b}}(V_2)| = 1$), and suffers **$9$ new direct empirical refutations** ($|F_{\text{Typ a}}(V_2)| = 9$). Then:
$$D(V_2) = \frac{1}{1 + 9} = 0.10 < 0.3, \qquad \Delta D = \frac{0.10 - 1.0}{2 - 1} = -0.90 < 0.$$
Because $|F_{\text{Typ a}}(V_j)|$ is in the **denominator** of $D(V_j)$, the influx of $9$ direct empirical contradictions drives $D(V_j)$ down from $1.0$ to $0.10$ and makes $\Delta D = -0.90 \le 0$, causing the specification on L61 and L84 to classify a catastrophically falsified theory with zero new successes as a **"Progressive Research Programme (genuine successes outpace anomalies)"**!

**Why this happens.**
In Schurz's formal epistemology (Schurz 2014, §2.5.3; cf. `docs/concepts/epistemology.md` L65), comparative theory progress requires **two complementary conditions**:
1. **Empirical Net-Success / Comparative Superiority:** Verified successes $S$ must expand and outweigh total failures ($F_{\text{Typ a}} \cup F_{\text{Typ b}}$), e.g., $S(V_{j}) \supset S(V_{j-1})$ and $F_{\text{Typ a}}(V_j) \subseteq F_{\text{Typ a}}(V_{j-1})$.
2. **Low Immunization Ratio ($D$):** Among empirical contacts, the theory must not merely convert direct Type-a refutations into Type-b ad-hoc immunizations. $D(V_j)$ measures the ratio of *immunized* failures to *non-immunized* empirical contacts ($S \cup F_{\text{Typ a}}$); it is an **immunization ratio**, not a standalone sufficiency test for empirical progress!

**Fix.**
1. Require **both** positive empirical net growth ($\Delta |S| > \Delta |F_{\text{Typ a}}| + \Delta |F_{\text{Typ b}}|$ or $|S(V_j)| > |F_{\text{Typ a}}(V_j)| + |F_{\text{Typ b}}(V_j)|$) **and** $\Delta D \le 0, D < 0.3$ before diagnosing a **Progressive Programme**.
2. Alternatively, define the **Total Failure Ratio** alongside the **Immunization Index**:
   $$F_{\text{ratio}}(V_j) = \frac{|F_{\text{Typ a}}(V_j)| + |F_{\text{Typ b}}(V_j)|}{|S(V_j)| + |F_{\text{Typ a}}(V_j)| + |F_{\text{Typ b}}(V_j)|}, \qquad D_{\text{imm}}(V_j) = \frac{|F_{\text{Typ b}}(V_j)|}{|S(V_j)| + |F_{\text{Typ b}}(V_j)|}.$$

---

### DI-02 · Complete Formula Split-Brain Between `degeneration_index.md` and `epistemetrics/epistemic/dynamics.py` — **Critical**

**Where.** [`degeneration_index.md#L38-L58`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L38-L58) vs. [`packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py#L4-L5`](../../../packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py#L4-L5), [`#L355-L384`](../../../packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py#L355-L384).

**Finding.**
Although `docs/research/structuralist_theory_benchmark.md` (L287–288) states that STNB Task 5 (`dynamics.py`) implements `degeneration_index.md`, the Python implementation in `packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py` computes a **completely different mathematical formula** that contradicts `degeneration_index.md` in three ways:

| Aspect | `degeneration_index.md` (Spec) | `epistemetrics/epistemic/dynamics.py` (Code) |
| :--- | :--- | :--- |
| **Degeneration Formula** | $D(V_j) = \frac{\|F_{\text{Typ b}}(V_j)\|}{\|S(V_j)\| + \|F_{\text{Typ a}}(V_j)\|}$ (L52) | $DI = \frac{\Delta \|\text{Auxiliary Hypotheses}\| + \|\text{Anomalies}\|}{\Delta \|\text{Empirical Content}\| + \epsilon}$ (L355, L381) |
| **Treatment of Progressive Auxiliary Hypotheses** | Only **ad-hoc** auxiliaries lacking novel predictions ($\Delta_{\text{content}} = 0$) count toward $F_{\text{Typ b}}$ in the numerator. | **Every** added auxiliary hypothesis ($\Delta \|\text{Aux}\|$) is added to the numerator as a penalty, even when it is a progressive specialization (e.g. Hooke's law in `test_dynamics.py` L34)! |
| **Treatment of Direct Anomalies ($F_{\text{Typ a}}$)** | Placed in the **denominator** ($\|S\| + \|F_{\text{Typ a}}\|$). | Placed in the **numerator** ($+ \|\text{Anomalies}\|$). |
| **Node-Level Immunization $II$** | Per-node ratio of anomalies resolved by that node to novel content predicted by that node (L38–40, L66–68). | Assigns the **same global transition ratio** to every `aux_node in added_aux`, and fabricates `anom_resolved = max(1, len(anom_prev - anom_curr))` (L364)! |

Look closely at `dynamics.py` L360–367:
```python
for aux_node in added_aux:
    if delta_emp == 0:
        node_immunization[aux_node] = 1.0
    else:
        anom_resolved = max(1, len(anom_prev - anom_curr))
        node_immunization[aux_node] = float(anom_resolved) / float(
            anom_resolved + delta_emp
        )
```
Because `anom_resolved = max(1, len(anom_prev - anom_curr))` clamps `anom_resolved` to at least `1`, **even when zero anomalies existed in `anom_prev` (`len(anom_prev) == 0`)**, `dynamics.py` invents $1$ resolved anomaly out of thin air! Thus, in a completely anomaly-free progressive theory that adds $1$ auxiliary law explaining $1$ new empirical phenomenon (`delta_emp = 1`), `dynamics.py` assigns `II = 1 / (1 + 1) = 0.50`, and if `delta_emp = 0` with `0` anomalies, it assigns `II = 1.0` ("Ad-Hoc Immunization ❌") when there was no anomaly to immunize against!

**Fix.**
1. In `dynamics.py`, remove the fabricated `max(1, ...)` clamp on `anom_resolved`: when `anom_resolved == 0` and `delta_emp > 0`, `II = 0.0` (pure progressive expansion); when `anom_resolved == 0` and `delta_emp == 0`, `II = 0.0` (or `0.5` neutral/untested conjecture, not `1.0` ad-hoc anomaly immunization).
2. Compute per-node $\Delta_{\text{anom}}(h)$ and $\Delta_{\text{content}}(h)$ using each auxiliary node $h$'s incident edges in `TheoryGraph` (with fallback to snapshot-level deltas only when snapshot inputs are edge-free dictionaries).
3. Unify the macro formula between `degeneration_index.md` and `dynamics.py` so that only **immunizing** auxiliary patches (where $II(h) \ge \tau_{\text{adhoc}}$ or $\Delta_{\text{content}}(h) = 0$) count as $F_{\text{Typ b}}$, rather than penalizing all auxiliary hypotheses indiscriminately.

---

## 2. Is the Metric Formally & Mathematically Correct?

### DI-03 · Contradiction Between L15 and L30 in Defining $\Delta_{\text{content}}$, and Inverted Structuralist Inclusion Direction for $\operatorname{Cn}(K)$ — **Critical**

**Where.** [`degeneration_index.md#L15`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L15) vs. [`#L28-L31`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L28-L31).

**Finding.**
1. **Omission of $\setminus \{a\}$ on L30:**
   - L15 defines zero excess empirical content as:
     $$\operatorname{Cn}(K_{i+1}) \setminus \{a\} \subseteq \operatorname{Cn}(K_i)$$
     where $a \in I$ is the absorbed anomaly.
   - Yet L30 defines the mathematical condition for ad-hoc immunization as:
     $$\Delta_{\text{anom}} > 0 \quad \text{and} \quad \Delta_{\text{content}} = |\operatorname{Cn}(K_{i+1}) \setminus \operatorname{Cn}(K_i)| = 0.$$
   - Notice that L30 **drops $\setminus \{a\}$** (or $\setminus A_{\text{resolved}}$)! If $K_{i+1}$ accommodates the previously anomalous phenomenon $a$ so that $a \in \operatorname{Cn}(K_{i+1})$ whereas $a \notin \operatorname{Cn}(K_i)$, then $a \in \operatorname{Cn}(K_{i+1}) \setminus \operatorname{Cn}(K_i)$, which means $|\operatorname{Cn}(K_{i+1}) \setminus \operatorname{Cn}(K_i)| \ge |\{a\}| \ge 1 \neq 0$!
   - Furthermore, under classical Tarskian deductive consequence $\operatorname{Cn}(\cdot)$, if $a \in \operatorname{Cn}(K_{i+1}) \setminus \operatorname{Cn}(K_i)$, then infinitely many trivial disjunctions $a \lor \psi$ and conjunctions $a \land \varphi$ also belong to $\operatorname{Cn}(K_{i+1}) \setminus \operatorname{Cn}(K_i)$, making $|\operatorname{Cn}(K_{i+1}) \setminus \operatorname{Cn}(K_i)| = \infty$ (the classic Tarskian cardinality trap; see `progressiveness.md` L51–58, which replaces $\operatorname{Cn}$ with Schurz's finite/irreducible relevant empirical content $E_e$!).
2. **Inverted Inclusion Direction of $\operatorname{Cn}(K)$ in Structuralist Model Theory:**
   - L15 and L28 write $E_{i+1} = \langle K_{i+1}, I_{i+1} \rangle$ and $a \in I$, citing Balzer et al. (1987, pp. 333–338) and Stegmüller (1976, p. 184).
   - In the structuralist Non-Statement View (see `tenability.md` L43–46 and `glossary.md` L202), $\operatorname{Cn}(K) = r(\mathcal{P}(M) \cap GC \cap GL) \subseteq \mathcal{P}(M_{pp})$ is the class of **permissible sets of partial potential models**.
   - In model theory, adding a stronger law (specialization $K_{i+1} \alpha K_i$) **restricts** the permissible models, so $\operatorname{Cn}(K_{i+1}) \subseteq \operatorname{Cn}(K_i)$ (and therefore $\operatorname{Cn}(K_{i+1}) \setminus \operatorname{Cn}(K_i) = \emptyset$ for every genuine specialization!). Conversely, relaxing/weakening a law to accommodate an anomaly **enlarges** the class of allowed models: $\operatorname{Cn}(K_{i+1}) \supset \operatorname{Cn}(K_i)$!
   - Moreover, since $\operatorname{Cn}(K) \subseteq \mathcal{P}(M_{pp})$ is a class of *sets* of partial potential models while $a \in I \subseteq M_{pp}$ is an *element* (a single partial potential model), writing $\operatorname{Cn}(K_{i+1}) \setminus \{a\}$ is a set-theoretic type error ($\mathcal{P}(M_{pp})$ vs. $M_{pp}$).

**Fix.**
Express excess empirical content using Schurz's irreducible relevant empirical content operator $E_e(\cdot)$ (aligning with `progressiveness.md` L58) or confirmed novel applications $S_{\text{novel}}(K_{i+1})$, explicitly subtracting the accommodated anomaly set $A_{\text{res}}(K_i, K_{i+1})$:
$$\Delta_{\text{anom}}(K_i, K_{i+1}) = |A_{\text{res}}(K_i, K_{i+1})|, \qquad \Delta_{\text{content}}(K_i, K_{i+1}) = \big|\big(E_e(K_{i+1}) \setminus E_e(K_i)\big) \setminus A_{\text{res}}(K_i, K_{i+1})\big|.$$

---

### DI-04 · Undefined Variables ($\Delta_{\text{anom}}, V_{\text{progressive}}, V_{\text{immunizing}}$), Redundant Piecewise Split in $II$, and Multiple Division-by-Zero Traps — **Major**

**Where.** [`degeneration_index.md#L30`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L30), [`#L40`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L40), [`#L46`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L46), [`#L52`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L52), [`#L58`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L58).

**Finding.**
1. **Unbound / Undefined Symbols:**
   - $\Delta_{\text{anom}}$ (L30, L40) is never defined by an equation. Is it $|F_{\text{Typ a}}(V_i) \setminus F_{\text{Typ a}}(V_{i+1})|$ (resolved anomalies) or $|F_{\text{Typ a}}(V_{i+1})| - |F_{\text{Typ a}}(V_i)|$ (net change in anomalies, which can be negative)?
   - $V_{\text{progressive}}$ and $V_{\text{immunizing}}$ in $RPI(\mathcal{E})$ (L46) are never defined. Are they auxiliary nodes $h$ classified by $II(h) = 0$ vs. $II(h) = 1$, or $II(h) < 0.8$ vs. $II(h) \ge 0.8$ (as in `dynamics.py` L125)?
2. **Redundant Case Split in $II(K_i, K_{i+1})$ That Misses the Actual $0/0$ Singularity (L40):**
   $$II (K_i, K_{i+1}) = \begin{cases} 1.0 & \text{if } \Delta_{\text{anom}} > 0 \land \Delta_{\text{content}} = 0 \\ \frac{\Delta_{\text{anom}}}{\Delta_{\text{anom}} + \Delta_{\text{content}}} & \text{otherwise} \end{cases}$$
   When $\Delta_{\text{anom}} > 0$ and $\Delta_{\text{content}} = 0$, the second branch $\frac{\Delta_{\text{anom}}}{\Delta_{\text{anom}} + 0} = 1.0$ **already evaluates to $1.0$**! Meanwhile, when $\Delta_{\text{anom}} = 0$ and $\Delta_{\text{content}} = 0$ (an auxiliary modification that neither resolves an existing anomaly nor adds new empirical content), the "otherwise" branch computes $\frac{0}{0 + 0} = \text{NaN}$!
3. **Unguarded Denominators in $RPI(\mathcal{E})$, $D(V_j)$, and $\Delta D$:**
   - In $RPI(\mathcal{E})$ (L46): divides by $0$ when $|V_{\text{progressive}}| + |V_{\text{immunizing}}| = 0$.
   - In $D(V_j)$ (L52): the mathematical formula has no guard when $|S(V_j)| + |F_{\text{Typ a}}(V_j)| = 0$ (though the Cypher query on L76 adds `+ 1e-6`).
   - In $\Delta D = \frac{D(V_m) - D(V_1)}{m - 1}$ (L58): divides by $0$ when $m = 1$, and ignores all intermediate versions $V_2, \dots, V_{m-1}$ (a theory can drop from $D(V_1)=0.9$ to $D(V_2)=0.1$ and then degenerate monotonically from $V_2$ to $V_{10}$ up to $D(V_{10})=0.85$, yet $\Delta D = (0.85 - 0.90)/9 < 0$ diagnoses it as "Progressive").

**Fix.**
1. Define $\Delta_{\text{anom}}(h) = |\{a \in F_{\text{Typ a}}(V_i) \mid h \text{ resolves } a\}| \ge 0$ and $\Delta_{\text{content}}(h) = |\{e \in S(V_{i+1}) \setminus S(V_i) \mid h \text{ predicts } e\}| \ge 0$.
2. Fix the case split in $II(h)$ so the guarded case is $\Delta_{\text{anom}}(h) + \Delta_{\text{content}}(h) = 0$:
   $$II(h) = \begin{cases} 0.0 & \text{if } \Delta_{\text{anom}}(h) = 0 \land \Delta_{\text{content}}(h) = 0 \\ \frac{\Delta_{\text{anom}}(h)}{\Delta_{\text{anom}}(h) + \Delta_{\text{content}}(h)} & \text{otherwise} \end{cases}$$
3. Define $V_{\text{progressive}} = \{h \in V_{\text{aux}} \mid \Delta_{\text{content}}(h) > 0 \land II(h) \le 0.5\}$ and $V_{\text{immunizing}} = \{h \in V_{\text{aux}} \mid \Delta_{\text{anom}}(h) > 0 \land II(h) > 0.5\}$.
4. Replace the two-point secant $\Delta D = \frac{D(V_m) - D(V_1)}{m - 1}$ (for $m \ge 2$, else $0.0$) with OLS linear regression slope or recency-weighted step differences $\Delta D_j = D(V_j) - D(V_{j-1})$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### DI-05 · Internal Graph Schema Split Between Step 1 and Step 2 & Unregistered Labels — **Major**

**Where.** [`degeneration_index.md#L66-L77`](../../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L66-L77).

**Finding.**
Within `## Measurement & Graph Implementation`, Step 1 and Step 2 assume two disconnected graph schemas that neither match each other nor exist in `epistemetrics`:
1. **Step 1 (L66–68):** Assumes auxiliary hypothesis nodes have incoming `:RESOLVES_ANOMALY` edges and outgoing `:PREDICTS_NOVEL` edges, and assigns them the node label `:AdHocImmunization`.
2. **Step 2 (L69–77):** Queries `(:TheoryVersion {id: $version_id})` connected via `:HAS_SUCCESS`, `:HAS_FAILURE_A`, and `:HAS_FAILURE_B` to `(:Success)`, `(:FailureTypA)`, and `(:FailureTypB)`—never referencing `:AdHocImmunization`, `:RESOLVES_ANOMALY`, or `:PREDICTS_NOVEL` from Step 1!
3. **Codebase Mismatch:** None of the 10 labels/edges (`:TheoryVersion`, `:Success`, `:FailureTypA`, `:FailureTypB`, `:AdHocImmunization`, `:RESOLVES_ANOMALY`, `:PREDICTS_NOVEL`, `:HAS_SUCCESS`, `:HAS_FAILURE_A`, `:HAS_FAILURE_B`) exists in `epistemetrics.core.models.NodeType` or `RelationType`.

**Fix.**
Map the implementation onto canonical `epistemetrics` types:
- Auxiliary hypotheses: `NodeType.HYPOTHESIS` with `EpistemicStatus.PROTECTIVE_BELT`.
- Direct failures ($F_{\text{Typ a}}$): empirical nodes (`NodeType.EVIDENCE` / `PHENOMENON` / `PARADIGM`) with `EpistemicStatus.ANOMALOUS` or connected via `RelationType.ATTACKS`.
- Successes ($S$): empirical nodes explained via `RelationType.EXPLAINS` / `SUPPORTS` with non-anomalous status.
- Immunized failures ($F_{\text{Typ b}}$): anomalies from $t-1$ linked only to protective-belt hypotheses with $II(h) = 1.0$.

---

## 4. Is the Metric Valid and Scientifically Significant?

### DI-06 · High Metascientific Value, Subject to Overlap Resolution with `empirical_content.md` ($\Delta_{\text{EEC}}$) and `progressiveness.md` — **Minor**

**Finding.**
Tracking ad-hoc immunizations (Lakatos 1978; Schurz 2014) is indispensable for distinguishing genuine explanatory progress from degenerative protective-belt patching. However, as noted in [`ISSUE-075`](../ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), `empirical_content.md` (L141–152) defines a separate "Lakatos Delta ($\Delta_{\text{EEC}}$)" for the exact same construct, while `progressiveness.md` defines "Progressive vs. Regressive Programme" without referencing $D(V_j)$ or $II(h)$. These three specifications should be formally linked.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Symbol Collision on $V$ Within the Same Document (L22, L46, L50):** $V_j$ denotes a *historical theory version* on L22 and L50, whereas $V_{\text{progressive}}$ and $V_{\text{immunizing}}$ denote *sets of graph vertices* on L46. Use $\mathcal{V}_j$ or $N_j$ for theory versions and $V_{\text{prog}}, V_{\text{imm}}$ for vertex subsets.
2. **Symbol Collision on $E_{i+1}$ (L28):** Uses $E_{i+1} = \langle K_{i+1}, I_{i+1} \rangle$ for a theory-element, whereas `paradigm_guidance.md` and `progressiveness.md` use $T_i = \langle K_i, I_i \rangle$ and reserve $\mathcal{E}$ for the evolution sequence and $E(G)$ for edges.
3. **Misassigned Zotero Key (L11):** Links both `[Balzer et al., 1987, pp. 333–338]` and `[Schurz, 2024, pp. 51, 59, 61, 265]` to the identical Zotero URI `zotero://select/library/items/24SNSW2B`.
