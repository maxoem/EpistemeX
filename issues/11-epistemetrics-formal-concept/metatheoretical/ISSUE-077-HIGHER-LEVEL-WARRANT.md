# [ISSUE-077] Formal & Conceptual Evaluation: Higher-Level Warrant (`higher_level_warrant.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-077` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 5: Metatheoretical Framework |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **High** (unbounded score with signed Denying-the-Antecedent penalty, topological depth $DoJ$ ignores truth/acceptability of ancestor theories, and circular ECHO double-counting) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-082`](../ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md), [`ISSUE-009`](../../03-epistemic-metrics/ISSUE-009-global-qbaf-solvers-and-thagardian-harmony.md), [`ISSUE-066`](../../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **Partially / Flawed** | Claims to quantify downward epistemic warrant from well-established fundamental theories ($T_{\text{high}} \to H$) and vertical depth of justification ($DoJ$). However, $HLW(H)$ penalizes $H$ when a superordinate theory is rejected ($a_T < 0$, committing the fallacy of Denying the Antecedent), while $DoJ(H)$ is purely syntactic—classifying a hypothesis derived via a 3-step chain from a refuted pseudoscientific theory as "Deeply Grounded" ($DoJ \ge 2$). |
| **2. Formally & Mathematically Correct?** | **No (Major Flaws)** | (1) $HLW(H)$ is unbounded in $(-\infty, +\infty)$; (2) $\text{Paths}_{\text{root}}(H)$ is never formally defined, is $-\infty$ on empty sets unless guarded, and is $+\infty$ / NP-hard if $E_{\text{warrant}}$ contains cycles; (3) $HLW(H)$ double-counts $H$'s own upward confirmation echoed back from $T$ in symmetric ECHO networks. |
| **3. Free of Semantic Shifts?** | **No** | Shifts the ontological type of $T \in \text{Sup}(H)$ between model-theoretic `:TheoryElement` containers (L32–33, L51) and propositional laws/axioms possessing activation $a_T(t)$ and `:EXPLAINS` edges (L15–17, L37). |
| **4. Valid & Scientifically Significant?** | **Yes (When Orthogonalized)** | Higher-level theoretical grounding (Thagard 1989, Principle E2/E4; Schurz 2014, §5.3) is a core metascientific virtue, provided it is decoupled from self-echoed bottom-up support and gated by ancestor acceptability. |

---

## 1. Does the Metric Capture What It Claims It Does?

### HLW-01 · Fallacy of Denying the Antecedent ($a_T(t) < 0$) and Unboundedness in $HLW(H)$ — **Critical**

**Where.** [`higher_level_warrant.md#L35-L40`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L35-L40), [`#L54`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L54).

**Finding.**
The Higher-Level Warrant Score is defined on L37 as:
$$HLW(H) = \sum_{T \in \text{Sup}(H)} w(T, H) \cdot a_T(t)$$
where $w(T, H) > 0$ and $a_T(t) \in [-1, 1]$ is the ECHO activation of the higher-level theory node $T$.

This formulation suffers from two severe defects:
1. **Signed Cancellation / Denying the Antecedent ($a_T(t) < 0$):**
   Suppose an empirical law $H$ (e.g., Snell's law of refraction or Boyle's gas law) was historically derived from a now-refuted superordinate theory $T_1$ ($a_{T_1}(t) = -0.9$, e.g., Descartes' ballistic corpuscular optics or caloric theory) and is also derived from an accepted theory $T_2$ ($a_{T_2}(t) = +0.8$, wave optics or kinetic theory).
   Under the linear sum on L37, the refuted parent $T_1$ contributes $-0.9 \cdot w(T_1, H) < 0$, **canceling out** the positive warrant from $T_2$ and yielding $HLW(H) < 0$!
   In deductive logic and philosophy of science, while truth transmits downward along valid deductions ($T \vdash H$ and $T$ warranted $\implies H$ warranted), **falsity does not transmit downward** ($T \vdash H$ and $\neg T \nvdash \neg H$; inferring $\neg H$ from $\neg T$ is the formal fallacy of *Denying the Antecedent*). A refuted theory simply provides *zero* warrant to $H$, not negative warrant!
2. **Unbounded Range and Threshold Fragility ($HLW > 0$):**
   Because $HLW(H)$ is an unnormalized sum, its range is $[0, |\text{Sup}(H)| \cdot w_{\max}]$ (or $(-\infty, +\infty)$ as written). On L54, every node with $HLW > 0$ is labeled `:PossessesHigherWarrant`. Thus, a node explained by a nearly neutral, uncorroborated speculation ($a_T = 0.001$) receives `:PossessesHigherWarrant`, while a node with 10 weak speculative parents ($a_{T_i} = 0.1$) outscores a node derived from a single highly corroborated fundamental law ($a_T = 0.9$).

**Fix.**
1. Gate parent activation by $\max(0, a_T^*)$ (in ECHO, where $a_T^* \in [-1, 1]$) or by net positive corroboration above baseline $\max(0, \tau^*(T) - \tau_0(T))$ (in D-QBAF, where $\tau^*(T) \in [0, 1]$).
2. Normalize $HLW(H)$ into $[0, 1)$ (e.g. via $\tanh$, noisy-OR $1 - \prod_{T \in \text{Sup}(H)} (1 - w(T, H)\max(0, a_T^*))$, or degree-normalized mean) and require a meaningful threshold $HLW(H) \ge \tau_{\text{warrant}}$ (e.g., $0.2$) before assigning `:PossessesHigherWarrant`.

---

### HLW-02 · Depth of Justification ($DoJ$) Ignores Epistemic Acceptability of Ancestor Theories and Is Gameable by Chain Subdivision — **Major**

**Where.** [`higher_level_warrant.md#L42-L46`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L42-L46), [`#L59-L63`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L59-L63).

**Finding.**
The Depth of Justification is defined on L44 as:
$$DoJ(H) = \max_{p \in \text{Paths}_{\text{root}}(H)} \text{length}(p)$$
and the Diagnostic Table (L59–63) classifies any node with $DoJ(H) \ge 2$ as **"Deeply Grounded — Multi-tier theoretical justification (embedded in scientific hierarchy)"**.

This fails construct validity in two ways:
1. **Blindness to Refuted Ancestors:** $DoJ(H)$ is purely topological and completely ignores $a_T(t)$ and edge admissibility! If $H$ is derived via a 2-step chain $T_{\text{root}} \to T_{\text{mid}} \to H$ where $T_{\text{root}}$ and $T_{\text{mid}}$ are completely falsified ($a_T^* \le -0.8$, or `EpistemicStatus.ANOMALOUS`), $DoJ(H)$ is still $2$, diagnosing $H$ as **"Deeply Grounded"**.
2. **Vulnerability to Syntactic Lemma Padding:** If an author breaks a single derivation step $T \to H$ into trivial intermediate restatements $T \to L_1 \to L_2 \to H$ within the same theoretical tier, $\text{length}(p)$ jumps from $1$ to $3$ without adding any deeper fundamental theory.

**Fix.**
1. Restrict $\text{Paths}_{\text{root}}(H)$ to **epistemically admissible warrant paths** where every ancestor node $u \in V(p) \setminus \{H\}$ is accepted ($a_u^* \ge \tau_{\text{accept}}$) and every edge $e \in E(p)$ passes the admissibility gate ($w(e) \ge \tau_{\text{edge}}$).
2. To prevent intra-level lemma inflation, define $DoJ(H)$ either over **distinct specialization/theory-element tiers** (counting transitions across distinct `TheoryElement` levels in the specialization poset) or weight path steps by reliability decay (aligning with `conservatism.md`).

---

## 2. Is the Metric Formally & Mathematically Correct?

### HLW-03 · Undefined Path Space $\text{Paths}_{\text{root}}(H)$, Empty-Set Trap ($\max \emptyset$), and Cycle Divergence — **Major**

**Where.** [`higher_level_warrant.md#L44`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L44).

**Finding.**
In $DoJ(H) = \max_{p \in \text{Paths}_{\text{root}}(H)} \text{length}(p)$:
1. **$\text{Paths}_{\text{root}}(H)$ is undefined:** The specification never defines what qualifies as a $\text{root}$ node (is it any node $r$ with in-degree $0$ in $E_{\text{warrant}}$, or only `NodeType.AXIOM` / `EpistemicStatus.HARD_CORE` nodes?).
2. **Empty-Set Trap on Isolated / Phenomenological Nodes:** On L63, the diagnostic table expects $DoJ(H) = 0$ for an isolated empirical rule with no incoming warrant edges. However, if $H$ has no incoming warrant paths from a root, $\text{Paths}_{\text{root}}(H) = \emptyset$, and in standard mathematics $\max_{p \in \emptyset} \text{length}(p) = -\infty$ (or raises `ValueError: max() arg is an empty sequence` in Python) unless explicitly guarded or unless trivial $0$-length paths $(H)$ are included.
3. **Cycle Divergence:** In an NLP-extracted property graph, `:EXPLAINS` / `:SUPPORTS` edges frequently contain cycles (`ISSUE-066` A-05). If $E_{\text{warrant}}$ is not DAG-projected before computing $DoJ(H)$, walk lengths are unbounded ($+\infty$) and Longest Simple Path on a cyclic digraph is NP-hard.

**Fix.**
Define the warrant DAG $G_{\text{warrant}} = \text{DAG}(V, E_{\text{warrant}})$, let $\text{Roots}(G_{\text{warrant}}) = \{r \in V \mid \text{deg}^-_{G_{\text{warrant}}}(r) = 0 \land a_r^* \ge \tau_{\text{accept}}\}$, and define:
$$DoJ(H) = \begin{cases} \max_{p \in \text{Paths}(\text{Roots} \to H)} |E(p)| & \text{if } \text{Paths}(\text{Roots} \to H) \neq \emptyset \\ 0 & \text{otherwise.} \end{cases}$$

---

### HLW-04 · Circular Self-Reinforcement Between $HLW(H)$ and Symmetric ECHO Propagation — **Major**

**Where.** [`higher_level_warrant.md#L24-L27`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L24-L27), [`#L37`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L37), [`#L52`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L52).

**Finding.**
In Thagard's ECHO (`adapted_echo_algorithm.md`), explanatory links $(T, H)$ are **symmetric** excitatory constraints ($w_{TH} = w_{HT} > 0$).
Suppose an empirical law $H$ is strongly supported by data $E$ ($a_H \approx 0.9$), and someone introduces a purely ad-hoc higher-level postulate $T$ that explains *only* $H$ and nothing else (no independent evidence or breadth).
During the ECHO relaxation pass (L52), activation flows **upward** from $H$ to $T$, driving $a_T^* > 0$.
If $HLW(H) = \sum_{T \in \text{Sup}(H)} w(T, H) a_T^*$ is then computed using the post-ECHO activation $a_T^*$, $H$ receives a positive Higher-Level Warrant score $HLW(H) > 0$ **generated entirely by its own upward echo into the ad-hoc postulate $T$**!
As Thagard (1989, p. 441) and Schurz (2014, §5.3) emphasize, a higher-level hypothesis $T$ only confers genuine *additional* warrant on $H$ if $T$ possesses **independent warrant** from explaining *other* phenomena ($V \setminus \{H\}$).

**Fix.**
Evaluate the warrant contributed by $T$ to $H$ using the **cavity (leave-one-out) activation** $a_{T \setminus H}^*$ (the activation of $T$ when the upward feedback from $H \to T$ is removed), or require $T$ to have explanatory out-degree $\text{deg}^+_{\text{exp}}(T) \ge 2$ before $T \in \text{Sup}(H)$ counts toward $HLW(H)$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### HLW-05 · Ontological Shift Between Structuralist `:TheoryElement` Containers and Propositional `:Axiom` / `:Hypothesis` Nodes — **Major**

**Where.** [`higher_level_warrant.md#L32-L33`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L32-L33), [`#L51`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L51).

**Finding.**
- On L15–17 and L24, $T_{\text{high}}$ is a fundamental law or theory (e.g., Newton's gravitational mechanics) explaining an empirical law $H_{\text{mid}}$ (Kepler's laws), and on L37 $T$ has a propositional activation $a_T(t)$.
- On L32–33 and L51, however, $T \in \text{Sup}(H)$ is described as *"superordinate theory-element nodes"* possessing directed `:EXPLAINS` or `:JUSTIFIES` edges to $H \in V_H$.
- In `epistemetrics/core/models.py`, `NodeType.THEORY_ELEMENT` represents a structuralist container $T = \langle K, I \rangle$ linked to other theory elements via `RelationType.SPECIALIZES` or `REDUCES_TO`, whereas `RelationType.EXPLAINS` and `SUPPORTS` connect propositional nodes (`NodeType.AXIOM`, `HYPOTHESIS`, `CLAIM`) and have QBAF/ECHO activations. Querying for `(t:TheoryElement)-[:EXPLAINS]->(h:Hypothesis)` mixes the non-statement container layer with the statement-view argumentation layer (`ISSUE-069` D-04).

**Fix.**
Define $\text{Sup}(H)$ on the statement-view argumentation graph as superordinate propositional laws $T \in V_{\text{Axiom}} \cup V_{\text{Hypothesis}}$ with $(T, H) \in E_{\text{explains}}$, or on the structuralist poset via specialization/reduction links $(T_{\text{high}}, T_{\text{low}}) \in E_{\text{specializes}} \cup E_{\text{reduces\_to}}$ where $H \in Ax(T_{\text{low}})$.

---

## 4. Is the Metric Valid and Scientifically Significant?

### HLW-06 · Edge-Direction Inversion Risk Across `EXPLAINS`, `SUPPORTS`, and `DERIVED_FROM` — **Minor**

**Where.** [`higher_level_warrant.md#L33`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L33), [`#L51`](../../../docs/concepts/theory/metrics/metatheoretical/higher_level_warrant.md#L51) vs. `epistemetrics/epistemic/qbaf.py`.

**Finding.**
In `higher_level_warrant.md`, warrant edges $(T_i, H) \in E_{\text{warrant}}$ point from the higher-level theory $T_i$ to the lower-level hypothesis $H$ (`T_i -[:EXPLAINS]-> H`).
In `epistemetrics/epistemic/qbaf.py` and `explanatory_breadth.md` (L32), however, `RelationType.SUPPORTS` edges point **bottom-up** from evidence $E$ to hypothesis $H$ (`E -[:SUPPORTS]-> H`). If an implementation traverses incoming positive edges without filtering strictly for top-down explanatory/deductive edges (`RelationType.EXPLAINS` from `AXIOM`/`HYPOTHESIS` nodes rather than `SUPPORTS` from `EVIDENCE` nodes), bottom-up empirical evidence will be miscounted as "Higher-Level Theoretical Warrant"!

**Fix.**
Explicitly restrict $E_{\text{warrant}}$ to edges $(u, v)$ with `relation_type == RelationType.EXPLAINS` (or `SUPPORTS` only when $\text{node\_type}(u) \in \{\text{AXIOM}, \text{HYPOTHESIS}\}$ and $\text{tier}(u) > \text{tier}(v)$).

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Unregistered Edge & Node Labels (L51, L54):** Uses `:JUSTIFIES` and `:PossessesHigherWarrant`, neither of which exists in `RelationType` or `NodeType` in `epistemetrics/core/models.py`.
2. **Broken Local Zotero URIs (L13):** Contains `zotero://select/library/items/8F6MW586` and `zotero://select/library/items/24SNSW2B`, which do not resolve outside the author's local desktop client.
