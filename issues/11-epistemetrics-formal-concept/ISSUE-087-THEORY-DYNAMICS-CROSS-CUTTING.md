# [ISSUE-087] Cross-Cutting Evaluation: Pillar 4 Theory Dynamics Metrics (`theory_dynamics/*`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-087` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Cross-Cutting (Pillar 4: Theory Dynamics) |
| **Evaluated Docs** | [`degeneration_index.md`](../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md), [`paradigm_guidance.md`](../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md), [`progressiveness.md`](../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md), [`foundations/cognitive_weight.md`](../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/epistemic/dynamics.py`, `poset_evaluation.py`), `episteme-pipeline` |
| **Priority** | **Critical** (four incompatible representations of diachronic evolution across files and code, three mutually contradictory definitions of a "Progressive Research Programme", duplicate and incompatible hard-core invariance predicates, and unlinked duplication between `cognitive_weight.md` and `empirical_content.md`) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-083`](theory_dynamics/ISSUE-083-DEGENERATION-INDEX.md), [`ISSUE-084`](theory_dynamics/ISSUE-084-PARADIGM-GUIDANCE.md), [`ISSUE-085`](theory_dynamics/ISSUE-085-PROGRESSIVENESS.md), [`ISSUE-086`](theory_dynamics/ISSUE-086-COGNITIVE-WEIGHT.md), [`ISSUE-075`](ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-082`](ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md), [`ISSUE-010`](../04-diachronic-dynamics/ISSUE-010-theory-reduction-and-kuhn-loss-tracking.md), [`ISSUE-011`](../04-diachronic-dynamics/ISSUE-011-diachronic-timeline-and-terminology-drift.md) |

Severity legend: **Critical** = invalidates the metric suite's architectural/mathematical coherence · **Major** = significant cross-file conflict, redundancy, or domain mismatch · **Minor** = notation, alignment, or presentation issue.

---

## 1. Four Incompatible Representations of Diachronic Time and Theory Snapshots — **Critical**

**Where.** Across all four files in `docs/concepts/theory/metrics/theory_dynamics/` and [`packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py`](../../packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py).

**Finding.**
Although all four documents in `theory_dynamics/` and `epistemetrics/epistemic/dynamics.py` evaluate the same diachronic evolution $\mathcal{E}$ of a theory over time, each invents a different temporal container, graph schema, and indexing convention:

| Component | Temporal Sequence Notation | Snapshot Object Model | Assumed Neo4j / `TheoryGraph` Schema |
| :--- | :--- | :--- | :--- |
| **`degeneration_index.md`** | $K_i \to K_{i+1}$, $E_{i+1} = \langle K_{i+1}, I_{i+1} \rangle$, and $V_1, \dots, V_m$ | Version node $V_j$ with incident success/failure nodes | `(:TheoryVersion)-[:HAS_SUCCESS\|:HAS_FAILURE_A\|:HAS_FAILURE_B]->(:Success\|:FailureTypA\|:FailureTypB)` + `:RESOLVES_ANOMALY`, `:PREDICTS_NOVEL`, `:AdHocImmunization` |
| **`paradigm_guidance.md`** | $\langle N_1, \dots, N_k \rangle$ and $G_1, \dots, G_k$ at revision stage $t \in \{1, \dots, k\}$ | Directed specialization graph $G_t = (V(G_t), E(G_t))$ with root $T_0 \in V(G_1)$ | `(:TheoryElement {is_paradigm_core: true, theory_id: $theory_id})-[:SPECIALIZES*]->(:TheoryElement)` (no temporal property in Cypher) |
| **`progressiveness.md`** | $\mathcal{E} = \langle N_1, \dots, N_k \rangle$ at $t_1 < \dots < t_k$ (switching to $\langle N_0, \dots, N_k \rangle$ at $t_0 \dots t_k$ on L165) | Theory-nets $N_t = \langle T_t, \alpha_t \rangle$ with $I(t_i) = F(I_i) \uplus A(I_i)$ and $E_e(\cdot)$ | None specified (no `## Measurement & Graph Implementation` section) |
| **`epistemetrics/epistemic/dynamics.py`** | `snapshots: Sequence[Any]` indexed $0, \dots, m-1$ (`T_0 -> T_1`) | Edge-blind 4-tuple `(core_axioms, auxiliary_hypotheses, anomalies, empirical_content)` | `TheoryGraph` nodes partitioned solely by `NodeType` and `EpistemicStatus` (ignores all edges!) |

**Why this blocks unified execution in `epistemetrics`.**
1. In `epistemetrics/epistemic/dynamics.py` (`_extract_snapshot_components`, L137–213), all edges of `TheoryGraph` are ignored! The extractor merely loops over `snapshot.nodes.items()` and classifies nodes by `node_type` and `epistemic_status`.
2. Because `dynamics.py` never inspects edges, it cannot tell:
   - Whether a new auxiliary hypothesis $h$ actually resolves a prior anomaly (`:RESOLVES_ANOMALY` / `EXPLAINS`) or predicts a novel observation (`:PREDICTS_NOVEL` / `EXPLAINS`) (`degeneration_index.md`),
   - Whether a new `TheoryElement` descends from the root $T_0$ via `RelationType.SPECIALIZES` (`paradigm_guidance.md`), or
   - Whether an empirical application node $y \in I(t)$ is confirmed ($F(I(t))$) vs. unconfirmed conjecture ($A(I(t))$) and what its tenability blur $\delta^*(y) = 1 - TS_{\text{local}}(y)$ is (`progressiveness.md`).

**Fix.**
Standardize on a single canonical diachronic input representation across all Pillar 4 metrics and `epistemetrics/epistemic/dynamics.py`:
- An ordered sequence of `TheoryGraph` snapshots $\mathcal{E} = \langle G_0, G_1, \dots, G_k \rangle$ (0-indexed from inception $t_0$ to $t_k$, matching Python indexing in `dynamics.py` and $N_0, \dots, N_k$ in `EPR_{Cn}`).
- Within each `TheoryGraph` $G_t$, extract both vertex strata (`NodeType`, `EpistemicStatus`, `confidence`, `attributes["tenability_blur"]`, `attributes["cognitive_weight"]`) **and** typed directed edges (`RelationType.SPECIALIZES`, `EXPLAINS`, `SUPPORTS`, `ATTACKS`, `HAS_ACTUAL_MODEL`, `HAS_CONSTRAINT`, `HAS_PARADIGM`, `HAS_INTENDED_APPLICATION`).

---

## 2. Three Mutually Contradictory Definitions of a "Progressive Research Programme" — **Critical**

**Where.** [`degeneration_index.md#L51-L61`](../../docs/concepts/theory/metrics/theory_dynamics/degeneration_index.md#L51-L61), [`progressiveness.md#L51-L53`](../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L51-L53), [`#L79-L80`](../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L79-L80), [`#L145`](../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L145), [`#L185`](../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L185), and [`packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py#L381-L385`](../../packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py#L381-L385).

**Finding.**
Within Pillar 4, three different components define whether a research programme $\mathcal{E}$ is a **"Progressive Research Programme"** vs. **"Degenerating / Regressive Programme"**, and their criteria directly contradict one another:
1. **`degeneration_index.md` (L52, L61, L84):**
   - Uses **unweighted raw node cardinalities**: $D(V_j) = \frac{|F_{\text{Typ b}}(V_j)|}{|S(V_j)| + |F_{\text{Typ a}}(V_j)|}$.
   - Declares a programme **Progressive** if $\Delta D \le 0$ and $D < 0.3$—ignoring content retention $RR_{Cn}$, cognitive weights $w(P)$, precision tightening $PTM$, and hard-core invariance, and treating an increase in direct falsifications $|F_{\text{Typ a}}|$ as *improving* (lowering) $D(V_j)$ ([`ISSUE-083` DI-01](theory_dynamics/ISSUE-083-DEGENERATION-INDEX.md)).
2. **`progressiveness.md` (L51–53, L79, L145, L185):**
   - Explicitly rejects unweighted node counting (*"In accordance with Lakatos and Schurz, scientific progress cannot be measured by raw node cardinality"*, L79).
   - Declares a programme **Progressive** if $\Pi_{\text{empirical}} > 0.2 \land \delta_{\text{retention}} \approx 1.0$, using cognitive weights $w(P)$ over $E_e(F(I(t)))$ and precision tightening $PTM$—while **completely ignoring Type-b ad-hoc immunizations ($F_{\text{Typ b}}$) and auxiliary hypothesis bloat**! Under `progressiveness.md`, a theory that adds 100 ad-hoc auxiliary patches to accommodate anomalies and gains a modest increase in $F(I(t))$ is diagnosed as a **Progressive Programme**!
3. **`epistemetrics/epistemic/dynamics.py` (L381–385):**
   - Declares `is_progressive = (overall_di < 1.0) and core_invariant`, where `overall_di = (total_delta_aux + final_anomalies) / (total_delta_emp + epsilon)` penalizes **all** added auxiliary hypotheses regardless of whether they are progressive specializations or ad-hoc patches ([`ISSUE-083` DI-02](theory_dynamics/ISSUE-083-DEGENERATION-INDEX.md)).

**Fix.**
Unify the normative criterion for a **Lakatos-Stegmüller-Schurz Progressive Research Programme** across `degeneration_index.md`, `paradigm_guidance.md`, `progressiveness.md`, and `dynamics.py` as a conjunction of three orthogonal conditions:
1. **Paradigm Guidance & Core Stability (`paradigm_guidance.md`):** $\text{CoreStable} = 1 \land PGI_t \ge 0.5$.
2. **Positive Content-Weighted Empirical Growth (`progressiveness.md`):** $\Pi_{\text{empirical}}(t_{j-1}, t_j) > 0$ (new confirmed content outweighs lost content and precision does not collapse).
3. **Non-Degenerating Protective Belt (`degeneration_index.md`):** $D(V_j) < 0.3 \land \Delta D \le 0$ (ad-hoc Type-b immunizations do not accumulate faster than genuine empirical successes).

---

## 3. Duplicate and Incompatible Hard-Core Invariance Checkers Across `paradigm_guidance.md` and `dynamics.py` — **Major**

**Where.** [`paradigm_guidance.md#L76-L81`](../../docs/concepts/theory/metrics/theory_dynamics/paradigm_guidance.md#L76-L81) vs. [`packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py#L216-L270`](../../packages/epistemetrics/src/epistemetrics/epistemic/dynamics.py#L216-L270).

**Finding.**
Both `paradigm_guidance.md` (§D $\text{CoreStable}$) and `dynamics.py` (`verify_hard_core_invariance`) check whether the foundational paradigm core remains invariant over time, yet they test different node sets with different equivalence criteria:
1. `paradigm_guidance.md` (L80) tests $\left|\bigcap_{t=1}^k M_0(t)\right| = |M_0(1)|$ and $\left|\bigcap_{t=1}^k GC_0(t)\right| = |GC_0(1)|$ on the root element $T_0$, which allows arbitrary additions to $M_0(t)$ and ignores $M_p, M_{pp}, GL$ ([`ISSUE-084` PG-01](theory_dynamics/ISSUE-084-PARADIGM-GUIDANCE.md)).
2. `dynamics.py` (L183, L216–270) collects **all** nodes with `EpistemicStatus.HARD_CORE` or `NodeType in {AXIOM, ACTUAL_MODEL}` in snapshot $0$ (including specialized peripheral laws $M_i$ that belong to outer theory-elements $T_i \neq T_0$!), ignores `NodeType.CONSTRAINT` ($GC_0$), and requires exact string identity `f0.strip() != f_t.strip()` (which fails under benign terminology drift tracked in [`ISSUE-011`](../04-diachronic-dynamics/ISSUE-011-diachronic-timeline-and-terminology-drift.md)).

**Fix.**
Align `verify_hard_core_invariance` in `dynamics.py` with the corrected $\text{CoreStable}$ specification (`ISSUE-084` PG-01): scope invariance to the root paradigm core $T_0$ (or nodes explicitly marked `EpistemicStatus.HARD_CORE`), include global constraints $GC_0$ (`NodeType.CONSTRAINT`), check exact set equality of canonical core IDs ($K_0(t) = K_0(0)$), and support semantic/canonical equivalence in addition to raw string equality.

---

## 4. Uncoordinated Duplication Between Pillar 4 Cognitive Weight $w(P)$ and Pillar 3 Epistemic Weight $w(v)$ — **Major**

**Where.** [`docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md`](../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md) vs. [`docs/concepts/theory/metrics/empirical_power/empirical_content.md#L40-L85`](../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L40-L85) and [`docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L33-L41`](../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L33-L41).

**Finding.**
- In Pillar 4, `foundations/cognitive_weight.md` defines $w(P)$ for content elements $P \in E_e(H)$ via syntactic quantifier scope (Approach A) and model-theoretic state-space restriction $1 - |M(P)|/|M_{pp}|$ (Approach D), without providing closed-form equations ([`ISSUE-086`](theory_dynamics/ISSUE-086-COGNITIVE-WEIGHT.md)).
- In Pillar 3, `empirical_content.md` defines $w(v) = S_v \cdot e^{-\beta d_v}$ using syntactic quantifier classes ($S_{\text{univ}}, S_{\text{cond}}, S_{\text{sing}}, S_{\text{exist}}$) grounded in Carnapian state-space restriction $1 - P(h)$ ([`ISSUE-072`](../empirical_power/ISSUE-072-EMPIRICAL-CONTENT.md)), and `theoretical_achievements.md` defines $EFI(\tau) = 1 - \frac{|\text{PermissibleStates}(M_{pp} \mid \tau)|}{|\text{PermissibleStates}(M_{pp})|}$ ([`ISSUE-074`](../empirical_power/ISSUE-074-THEORETICAL-ACHIEVEMENTS.md)).
- In Pillar 4, `degeneration_index.md` ignores $w(P)$ altogether and uses unweighted cardinalities $|S(V_j)|, |F_{\text{Typ a}}(V_j)|, |F_{\text{Typ b}}(V_j)|$even though `progressiveness.md` (L79) states that unweighted cardinality violates Schurz's framework!

**Fix.**
Unify `cognitive_weight.md` ($w(P)$) and `empirical_content.md` ($w(v)$) into a single shared foundation specification, and optionally allow $D(V_j)$ in `degeneration_index.md` to use the same content weights $w(P)$ over $S(V_j), F_{\text{Typ a}}(V_j), F_{\text{Typ b}}(V_j)$ for consistency with `progressiveness.md`.

---

## 5. Non-Threatening Cross-File Inconsistencies & Notation Misalignments

| Issue | Locations | Details & Recommended Standardization |
| :--- | :--- | :--- |
| **1. Symbol Collision on $A$ Across Pillar 4 and Core Docs** | `progressiveness.md` L20, L44 ($A_1, A_2, A_j, A_k$: admissible blurs)<br>`progressiveness.md` L22, L34, L115 ($A(I_i)$: assumed/conjectured applications)<br>`formal_graph_model.md` L45 ($A$: theoretical antecedents in $\Delta = (B, A)$) | Use calligraphic $\mathcal{A}$ for admissible blurs (matching `formal_graph_model.md` L324 and `tenability.md` L52), $I_{\text{conj}}(t)$ (or $A(I_t)$) for conjectured applications, and $A$ for theoretical antecedents. |
| **2. Symbol Collision on $V$ Across Pillar 4** | `degeneration_index.md` L22, L50 ($V_j$: historical theory version)<br>`degeneration_index.md` L46 ($V_{\text{progressive}}, V_{\text{immunizing}}$: vertex sets)<br>`paradigm_guidance.md` L40 ($V(G_t)$: vertex set of $G_t$)<br>`progressiveness.md` L68 ($V(F(I(t)))$: total cognitive value function) | Reserve $V(G_t)$ for vertex sets, use $N_t$ (or $G_t$) for historical theory-net versions, and use $\mathcal{W}(F(I(t)))$ for total cognitive weight. |
| **3. Symbol Collision on $E$ Across Pillar 4** | `degeneration_index.md` L28 ($E_{i+1} = \langle K_{i+1}, I_{i+1} \rangle$: theory-element)<br>`degeneration_index.md` L44 & `progressiveness.md` L29 ($\mathcal{E}$: theory-evolution sequence)<br>`paradigm_guidance.md` L40 ($E(G_t)$: edge set)<br>`progressiveness.md` L58–61 ($E(S), E_e(S)$: empirical content operators)<br>`epistemology.md` L65, L188 ($E$: empirical successes, German *Erfolg*) | Use $T_i = \langle K_i, I_i \rangle$ for theory-elements, $\mathcal{E}$ for theory-evolution sequences, $E(G_t)$ for graph edge sets, $E_e(\cdot)$ for Schurz's relevant empirical content operator, and $S(N_t)$ for empirical successes. |
| **4. Formula Discrepancy for $EPR_{Cn}(\mathcal{E})$ Between `index.md` and `progressiveness.md`** | `docs/concepts/theory/metrics/index.md` (L105) vs. `progressiveness.md` (L168) | `index.md` L105 writes $P \in A(I, t_0) \cap F(I, t_k)$ (omitting $E_e(\cdot)$), whereas `progressiveness.md` L168 writes $P \in E_e(A(I, t_0)) \cap E_e(F(I, t_k))$. Synchronize both formulas. |
| **5. Broken Zotero Links & Misassigned Key `24SNSW2B`** | `degeneration_index.md` (L11)<br>`paradigm_guidance.md` (L13) | Both files link `[Balzer et al., 1987]` to `zotero://select/library/items/24SNSW2B`, which is the Zotero key for **Schurz (2024)**. Replace desktop `zotero://` URIs with standard bibliographic links/DOIs. |
| **6. Dangling Document Reference `"Structuralist Foundations of Episteme"`** | `progressiveness.md` (L176) | L176 tells readers to see `"Tenability" and "Structuralist Foundations of Episteme"`, instead of linking to [`tenability.md`](../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md), [`formal_graph_model.md`](../../docs/concepts/formal_graph_model.md#structuralist-model-theoretic-foundations), and [`theory_nets_and_topologies.md`](../../docs/concepts/theory_nets_and_topologies.md). |
