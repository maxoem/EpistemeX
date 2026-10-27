# [ISSUE-086] Formal & Conceptual Evaluation: Cognitive Weight $w(P)$ (`foundations/cognitive_weight.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-086` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 4: Theory Dynamics (Foundations) |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md`](../../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (contains zero closed-form equations despite being referenced by `progressiveness.md` for "exact calculation methods", falsely claims Approach A is implemented, and shifts the domain of $w(P)$ between leaf empirical content elements $P \in E_e(F(I(t)))$ and root theoretical laws $\vec{F} = m\vec{a}$, causing Approach B out-degree/downstream reach to evaluate to $0$ on all empirical leaves) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-085`](ISSUE-085-PROGRESSIVENESS.md), [`ISSUE-087`](../ISSUE-087-THEORY-DYNAMICS-CROSS-CUTTING.md), [`ISSUE-072`](../empirical_power/ISSUE-072-EMPIRICAL-CONTENT.md), [`ISSUE-074`](../empirical_power/ISSUE-074-THEORETICAL-ACHIEVEMENTS.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or implementation divergence · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Root-vs-Leaf Inversion in Approach B)** | Claims to define the cognitive weight $w(P) > 0$ summed over empirical content elements $P \in E_e(F(I(t)))$ in `progressiveness.md`. However, Approach B (L48–57) defines $w(P)$ via **out-degree / downstream reach to specializations and observation nodes** for a node sitting *"at the structural root of a theory tree"*. Because empirical content elements $P \in E_e(F(I(t)))$ sit at the **terminal leaves** of the derivation/specialization DAG, their downstream reach to specializations is **$0$**, making $w(P) = 0$ across `progressiveness.md`! |
| **2. Formally & Mathematically Correct?** | **No (Zero Closed-Form Equations)** | (1) Although `progressiveness.md` (L74) directs readers to `cognitive_weight.md` *"For a deeper dive into the exact calculation methods"*, Approaches A, B, and C contain **zero mathematical formulas**, and Approach D writes only an undefined proportionality $w(P) \propto 1 - \frac{\|M(P)\|}{\|M_{pp}\|}$; (2) in Approach D, $\|M(P)\| / \|M_{pp}\|$ is $\infty / \infty$ on infinite model spaces and yields $w(P) = 0$ on tautologies, violating $w(P) > 0$ (`progressiveness.md` L64). |
| **3. Free of Semantic Shifts?** | **No (Severe Ontological Shift in $P$)** | Shifts $P$ across three incompatible ontological levels: (a) an empirical consequence $P \in E_e(H)$ in observational vocabulary $L_E$ (L15, `progressiveness.md` L68), (b) a fundamental theoretical core law $\vec{F} = m\vec{a}$ in theoretical vocabulary $L_T$ sitting at the root of a theory-tree (L18, L30–31, L51–57), and (c) a structuralist model constraint restricting partial potential models $M(P) \subseteq M_{pp}$ (L70–74). |
| **4. Valid & Scientifically Significant?** | **Yes (Essential Foundation, Unimplemented)** | Weighting content elements by syntactic generality and systematization depth (Schurz & Lambert 1994; Schurz 2011, pp. 229–230; 2014) is essential to prevent trivial observation counting, but contrary to L46 (*"This syntactic approach, is highly feasible with our architecture and is implemented"*), **no implementation of $w(P)$ exists anywhere in `epistemetrics` or `episteme-pipeline`**. |

---

## 1. Does the Metric Capture What It Claims It Does?

### CW-01 · Ontological Shift Between Root Theoretical Laws ($\vec{F} = m\vec{a}$) and Leaf Empirical Content Elements ($P \in E_e(F(I(t)))$) Causes Approach B to Collapse to Zero — **Critical**

**Where.** [`cognitive_weight.md#L15-L20`](../../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md#L15-L20), [`#L30-L31`](../../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md#L30-L31), [`#L48-L57`](../../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md#L48-L57) vs. [`progressiveness.md#L68-L120`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L68-L120).

**Finding.**
Look at how $P$ is used in `progressiveness.md` versus how $P$ is described in `cognitive_weight.md`:
1. **In `progressiveness.md` (L68, L90, L110, L119, L168):**
   Every summation runs over $P \in E_e(F(I(t)))$ or $P \in E_e(A(I(t)))$—the **empirical content elements** of confirmed or conjectured applications. In a Theory Graph, empirical applications (`NodeType.PARADIGM`, `PHENOMENON`, `EVIDENCE`, `CLAIM` in $L_E$) are the **downstream targets (leaves)** of explanatory and specialization chains.
2. **In `cognitive_weight.md` (L18, L30–31, L48–57):**
   - L18 contrasts *"Observation #101 of pendulum A"* with *"discovering a single grand unifying law (e.g., $\vec{F} = m\vec{a}$)"*—treating $\vec{F} = m\vec{a}$ (a core theoretical axiom in $L_T$, **not** an empirical content element in $E_e(H) \subseteq L_E$!) as an element $P$.
   - L30–31 states: *"3. Unificatory / Systematization Value: A core hypothesis that logically entails or unifies multiple lower-level predictions carries higher weight."*
   - L51–57 (**Approach B: Graph-Theoretic Centrality & Entailment Dependency**) defines $w(P)$ as:
     - **Out-Degree / Downstream Reach:** *"proportional to the number of downstream specializations, empirical applications ($M_{pp}$), or observation nodes that logically depend on $P$."*
     - **Centrality Weighting:** *"a node $P$ that sits at the structural root of a theory tree—and whose removal would collapse multiple sub-branches—receives a high $w(P)$ score."*

**Why this breaks `progressiveness.md`:**
- If $P \in E_e(F(I(t)))$ is an empirical application/observation node at the **leaf** of the theory tree, it has **zero downstream specializations** and **zero downstream observation nodes** depending on it! Thus, under Approach B, $w(P) = 0$ (or baseline $\beta$) for every $P \in E_e(F(I(t)))$, while the root law $\vec{F} = m\vec{a}$ (which has high downstream reach) is a theoretical axiom in $K(t)$, not an element of $E_e(F(I(t)))$!
- Conversely, if one instead defines $w(P)$ on an empirical leaf $P$ by inheriting the out-degree of its ancestor laws, then an axiom $H$ that entails $N$ trivial observations $P_1, \dots, P_N$ gives each $P_i$ weight $w(P_i) \propto N$, so the sum $\sum_{i=1}^N w(P_i) \propto N^2$ scales **quadratically** in the number of trivial observations—**worsening** the exact trivial-observation inflation problem that `cognitive_weight.md` (L16–20) was created to solve!

**Fix.**
Strictly separate the role of **core law unification** from **empirical content element weighting**:
1. For an empirical content element / claim $P \in E_e(F(I(t)))$, $w(P)$ must measure the **intrinsic generality and epistemic robustness of $P$ itself** (e.g., an empirical law/generalization $\forall x (Fx \to Gx)$ vs. a singular observation $Fa \land Ga$), or **discount** redundant observations that share the same derivation pattern (dividing by cluster size rather than multiplying by ancestor out-degree!).
2. If evaluating the weight of a **theoretical hypothesis/law $H$** via downstream reach (Approach B), sum over distinct **empirical equivalence classes / clusters** explained by $H$ rather than raw observation node counts.

---

## 2. Is the Metric Formally & Mathematically Correct?

### CW-02 · Absence of Closed-Form Equations Across Approaches A–D and False Implementation Claim — **Critical**

**Where.** [`cognitive_weight.md#L34-L76`](../../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md#L34-L76) and [`progressiveness.md#L74-L75`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L74-L75).

**Finding.**
1. **No Closed-Form Specification:**
   `progressiveness.md` (L74–75) states:
   > *"For a deeper dive into the exact calculation methods, see the Cognitive Weight $w(P)$ foundation document."*
   Yet `cognitive_weight.md` contains **no exact calculation method or closed-form equation** in any of its four sections:
   - **Approach A (L38–46):** States that singular statements have $w(P) = 1$ and general laws *"receive higher weights scaled by quantifier depth, domain generality, and predicate complexity"*, without giving a formula.
   - **Approach B (L48–57):** States $w(P)$ is *"proportional to"* downstream reach or Katz/Betweenness centrality, without specifying edge direction, normalization, or how zero-centrality leaves avoid $w(P) = 0$.
   - **Approach C (L59–66):** Mentions Chaitin's algorithmic complexity and Bennett's logical depth (which is formally uncomputable due to the Halting Problem) and MDL, without a formula.
   - **Approach D (L68–76):** Writes only $w(P) \propto 1 - \frac{|M(P)|}{|M_{pp}|}$, where $|M(P)| / |M_{pp}|$ is $\infty / \infty$ for infinite model classes and $w(P) = 0$ for tautologies (violating $w(P) > 0$ in `progressiveness.md` L64).
2. **False Claim of Implementation (L46):**
   Line 46 states:
   > *"This syntactic approach, is highly feasible with our architecture and is implemented."*
   A full search of `packages/epistemetrics/` and `packages/episteme-pipeline/` confirms that **no function, class, or attribute implements `cognitive_weight` or quantifier-depth weighting**.

**Fix.**
Define an explicit, deterministic closed-form equation for $w(P) \in (0, 1]$ (or $[1, w_{\max}]$) on `TheoryGraph` nodes (aligning with `formal_graph_model.md` and `theory_nets_and_topologies.md` L89–98):
$$w(P) = w_{\text{scope}}(P) \cdot \tau^*(P)$$
where $w_{\text{scope}}(P)$ maps the sentence classification (`EssentialUniversal` $= 1.0$, `EmpiricalGeneralization` / `LocalizedUniversal` $= 0.6$, `SyntheticContingent` / `SingularObservation` $= 0.2$, `Existential` $= 0.1$) and $\tau^*(P) \in (0, 1]$ is the node's D-QBAF justification degree (or extraction/grounding reliability $R_P$). Update L46 to reflect actual implementation status.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### CW-03 · Misleading Cross-Reference to `tenability.md` for State-Space Cardinality Ratio $1 - |M(P)|/|M_{pp}|$ — **Major**

**Where.** [`cognitive_weight.md#L68-L76`](../../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md#L68-L76) vs. [`tenability.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md).

**Finding.**
In Approach D (L70–76), the document writes:
$$w(P) \propto 1 - \frac{|M(P)|}{|M_{pp}|}$$
and claims on L75–76:
> *"It directly reflects Popper's and Sneed's principle that empirical content equals the degree to which possible worlds are excluded. An approach to implementing this can be found in our 'Tenability Metric'"*

However, [`tenability.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md) (`ADR 0015`) does **not** compute state-space exclusion $1 - |M(P)|/|M_{pp}|$! Instead, `tenability.md` computes $TS_{\text{local}}(y, M) = \sup \{1 - \delta \mid \exists x^* \in M : (\Phi(y), x^*) \in u_\delta\}$, which measures the **inaccuracy blur $\delta$** needed for a specific observed data point $y \in I$ to be enriched into an actual model $x^* \in M$.
Meanwhile, the actual documents that attempt to formalize state-space exclusion $1 - |M(P)|/|M_{pp}|$ are [`empirical_content.md`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md) ($S_v = 1 - P(h)$ and $\Gamma_{\text{relative}}$; see [`ISSUE-072`](../empirical_power/ISSUE-072-EMPIRICAL-CONTENT.md)) and [`theoretical_achievements.md`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md) ($EFI(\tau)$; see [`ISSUE-074`](../empirical_power/ISSUE-074-THEORETICAL-ACHIEVEMENTS.md)).

**Fix.**
Replace the reference to `tenability.md` on L76 with a cross-reference to `empirical_content.md` ($w(v) = S_v \cdot R_v$) and `theoretical_achievements.md` ($EFI(\tau)$), and unify `cognitive_weight.md` ($w(P)$) with the node weight $w(v)$ in `empirical_content.md` so Episteme maintains a single canonical propositional weighting function.

---

## 4. Is the Metric Valid and Scientifically Significant?

### CW-04 · Uncoordinated Duplication with `empirical_content.md` Node Weight $w(v)$ — **Major**

**Where.** [`cognitive_weight.md`](../../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md) vs. [`empirical_content.md#L40-L85`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L40-L85).

**Finding.**
Both `cognitive_weight.md` ($w(P)$) and `empirical_content.md` ($w(v) = S_v \cdot e^{-\beta d_v}$) define a propositional weight to solve the exact same problem (preventing trivial observation statements from carrying the same weight as universal laws, grounded in Schurz and Carnap). Defining two separate, unlinked weighting functions (`w(P)` in Pillar 4 and `w(v)` in Pillar 3) duplicates foundational concepts and risks inconsistent weighting across static and diachronic metrics.

**Fix.**
Consolidate $w(P)$ (`cognitive_weight.md`) and $w(v)$ (`empirical_content.md`) into a single shared foundation specification used by both Pillar 3 (`empirical_content.md`) and Pillar 4 (`progressiveness.md`).

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Missing `## Grounding References` Section (L11, L18, L24, L38, L61):** The text cites `(Schurz, 2011, pp. 229–230)`, `Schurz and Lambert` (Schurz & Lambert 1994), `Chaitin`, `Bennett`, `Popper`, `Sneed`, and `Balzer et al.`, but omits the mandatory `## Grounding References` section at the end of the file.
2. **Typos & Punctuation Errors (L36, L46, L76):**
   - L36: `thorought` $\to$ `throughout`.
   - L46: `This syntactic approach, is` $\to$ `This syntactic approach is`.
   - L76: Missing period at the end of the file (`...in our "Tenability Metric"`).
