# [ISSUE-074] Formal & Conceptual Evaluation: Theoretical Achievements (`theoretical_achievements.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-074` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 3: Empirical Power |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (contains division-by-zero when $m < 2$, Asymmetric Ordered-Pair vs. Unordered-Pair mismatch in $PPM$, $\infty/\infty$ cardinality ratio over $M_{pp}$, and fabricated citation page numbers) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-075`](../ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-005`](../../02-structuralist-engine/ISSUE-005-sneedian-theoreticity-and-ramseyification.md), [`ISSUE-070`](../../10-formal-conceptual-docs/ISSUE-070-bibliography-and-attribution-audit.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **Partially (Conflates Laws & Constraints in $EFI$)** | Correctly identifies the two classical justifications for $T$-theoretical terms (Sneed 1971; Stegmüller 1976; Schurz 2014): (1) Empirical Focus (state-space restriction) and (2) Prognostic Power (cross-domain prediction via constraints). However, $EFI(\tau)$ fails to isolate the restriction due to $\tau$'s cross-application constraints $GC$ from the restriction due to intra-application laws $M$, and the graph implementation reduces both to simple bridge-edge counting. |
| **2. Formally & Mathematically Correct?** | **No (4 Critical/Major Flaws)** | (1) $PPM(\tau)$ divides by $\binom{m}{2} = 0$ whenever $\tau$ appears in $m \le 1$ domains (which is the exact case of an "idle wheel" $TAS \approx 0$!); (2) $PPM(\tau)$ sums over $1 \le i < j \le m$ ($\binom{m}{2}$ unordered pairs) an **asymmetric** quantity $\frac{|Pred(\tau, D_j \mid D_i)|}{|Obs(D_j)|}$ that depends on index order and ignores $D_i \mid D_j$; (3) $|\text{PermissibleStates}(M_{pp})|$ is infinite for continuous/first-order domains and completely undefined on a property graph; (4) $C(x, a, R, p)$ on L29 introduces four completely undefined symbols. |
| **3. Free of Semantic Shifts?** | **No (Severe Shift)** | Shifts abruptly from model-theoretic state-space cardinalities ($|\text{PermissibleStates}(M_{pp} \mid \tau)|$) and conditional domain prediction sets ($Pred(\tau, D_j \mid D_i)$) in §Mathematical Specification to simple topological bridge-edge counting in §Measurement & Graph Implementation (L55–59), with no mathematical bridge between the two. |
| **4. Valid & Scientifically Significant?** | **Yes (Crucial for Ramsey-Sneed Justification)** | Evaluating whether a theoretical construct $\tau$ performs genuine cross-application work (Ramsey-Sneed non-redundancy / Schurz's creativity of theoretical terms) vs. acting as an "idle wheel" is essential for theory evaluation. However, the mathematical formulas must be rewritten in terms of well-defined graph/constraint quantities. |

---

## 1. Does the Metric Capture What It Claims It Does?

### TA-01 · $EFI(\tau)$ Fails to Isolate Term $\tau$'s Constraint Contribution from Law $M$ — **Major**

**Where.** [`theoretical_achievements.md#L24-L26`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L24-L26), [`#L37-L39`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L37-L39).

**Finding.**
In structuralism (Stegmüller 1976, pp. 65–74; BMS 1987, pp. 125–139), a single application $y \in M_{pp}$ can often be trivially enriched with a theoretical function $\tau$ to satisfy a law $M$ if $\tau$ is allowed to vary freely from one application to the next (e.g., choosing whatever force or mass makes $F = ma$ true in a single isolated measurement). The genuine **Empirical Focus** of a theoretical term $\tau$ arises only when:
1. $\tau$ is governed by **both** special laws $M$ **and** cross-application constraints $GC_\tau$ (requiring $\tau(x)$ to take identical or linked values across overlapping applications $A_1, \dots, A_m$), or
2. Comparing the empirical content $\operatorname{Cn}(K)$ **with** $\tau$ (and its constraints $GC_\tau$) against the core $K \setminus \{\tau\}$ without $\tau$.

However, L39 writes:
$$EFI(\tau) = 1 - \frac{|\text{PermissibleStates}(M_{pp} \mid \tau)|}{|\text{PermissibleStates}(M_{pp})|}$$
1. By conditioning on a single symbol "$\mid \tau$" rather than on the theory core's laws $M$ and constraints $GC_\tau$ involving $\tau$, the notation is ill-typed ($\tau$ is a term/concept node, not a proposition or constraint).
2. In the baseline denominator $|\text{PermissibleStates}(M_{pp})|$, *all* partial potential models in $M_{pp}$ are permissible by definition ($\text{PermissibleStates}(M_{pp}) = M_{pp}$). If the numerator conditions on the entire theory $K$, then every theoretical term $\tau_1, \tau_2 \in K$ would receive the exact same $EFI$ score! To evaluate a specific term $\tau$, one must measure the **marginal restriction** contributed by $\tau$ and its constraints $GC_\tau$.

**Fix.**
Define $EFI(\tau)$ as the marginal reduction in permissible empirical configurations (or increase in constraint degrees of freedom / overdetermination) attributable specifically to the laws $M(\tau)$ and constraints $GC(\tau)$ referencing $\tau$.

---

## 2. Is the Metric Formally & Mathematically Correct?

### TA-02 · Division by Zero in $PPM(\tau)$ When $m < 2$ and Order-Dependent Asymmetry — **Critical**

**Where.** [`theoretical_achievements.md#L34-L35`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L34-L35), [`#L41-L46`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L41-L46), [`#L58`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L58).

**Finding.**
Let $\tau$ be linked across $m$ application subgraphs $D_1, \dots, D_m$. The Prognostic Power Metric is defined as:
$$PPM(\tau) = \frac{1}{\binom{m}{2}} \sum_{1 \le i < j \le m} \frac{|Pred(\tau, D_j \mid D_i)|}{|Obs(D_j)|}$$

This equation contains **three mathematical errors**:
1. **Division by Zero for $m = 0$ and $m = 1$:** When a theoretical term $\tau$ is an "idle wheel" defined in only $m = 1$ domain (or $m = 0$ empirical domains), $\binom{m}{2} = 0$, so $\frac{1}{\binom{m}{2}}$ **divides by zero**! Yet L58 explicitly claims: *"Nodes with $TAS \approx 0$ represent ungrounded 'idle wheels'"*. Those very nodes crash the formula with a `ZeroDivisionError`.
2. **Asymmetric Summand over Unordered Index Pairs ($1 \le i < j \le m$):** The sum runs only over $i < j$ ($\binom{m}{2}$ terms), evaluating only predictions from $D_i \to D_j$ ($\frac{|Pred(\tau, D_j \mid D_i)|}{|Obs(D_j)|}$) and **completely ignoring** predictions from $D_j \to D_i$ ($\frac{|Pred(\tau, D_i \mid D_j)|}{|Obs(D_i)|}$)!
   *Counter-example:* Suppose $\tau$ is measured in $D_2$ and predicts all observations in $D_1$ ($|Pred(\tau, D_1 \mid D_2)| = |Obs(D_1)|$), while $D_1$ does not uniquely determine $\tau$ so $|Pred(\tau, D_2 \mid D_1)| = 0$.
   - Under indexing $(D_1, D_2)$, $PPM(\tau) = 0.0$.
   - Under swapped indexing $(D_2, D_1)$, $PPM(\tau) = 1.0$.
   A graph metric **must be invariant under arbitrary permutation of domain indices** $\{1, \dots, m\}$!
3. **Division by Zero When $|Obs(D_j)| = 0$:** L28–29 states: *"Measurement of theoretical term $\tau$ in domain $D_1$ directly constrains and predicts observable values in **unmeasured** domain $D_2$"*. If $D_2$ is an *unmeasured* domain, then the set of existing observations $|Obs(D_2)| = 0$, causing $\frac{|Pred(\tau, D_2 \mid D_1)|}{|Obs(D_2)|}$ to divide by zero! Furthermore, if $Pred(\tau, D_j \mid D_i)$ contains *novel predictions* not in $Obs(D_j)$, the ratio can exceed $1.0$.

**Fix.**
1. Handle $m < 2$ explicitly by setting $PPM(\tau) := 0.0$ when $m < 2$.
2. Sum over all **ordered pairs** $(i, j)$ with $i \neq j$, normalizing by $m(m - 1) = 2\binom{m}{2}$:
   $$PPM(\tau) = \begin{cases} \dfrac{1}{m(m - 1)} \displaystyle\sum_{i=1}^{m} \sum_{\substack{j=1 \\ j \neq i}}^{m} \frac{|Pred(\tau, D_j \mid D_i) \cap Obs(D_j)|}{|Obs(D_j)|} & \text{if } m \ge 2 \\[10pt] 0.0 & \text{if } m < 2 \end{cases}$$
   (with terms where $|Obs(D_j)| = 0$ either excluded from the average or replaced by the total potential observable nodes $|V_E(D_j)|$ in domain $D_j$).

---

### TA-03 · Ill-Defined Infinite Cardinality Ratio in $EFI(\tau)$ — **Critical**

**Where.** [`theoretical_achievements.md#L39`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L39).

**Finding.**
$$EFI(\tau) = 1 - \frac{|\text{PermissibleStates}(M_{pp} \mid \tau)|}{|\text{PermissibleStates}(M_{pp})|}$$
1. **In Model Theory ($\infty / \infty$):** In standard structuralist applications (and in `ADR 0015`, where parameters live in $\mathbb{R}^+$), the class of partial potential models $M_{pp}$ (and $\mathcal{P}(M_{pp})$) is **infinite** (often uncountably infinite). The naive cardinality ratio $\frac{|\infty|}{|\infty|}$ is undefined without a probability/Lebesgue measure $\mu$ on $M_{pp}$ (which structuralism explicitly avoids because $M_{pp}$ is only a uniform space, not a measure space).
2. **In the Property Graph:** Neither `PermissibleStates(M_pp)` nor `PermissibleStates(M_pp | tau)` is defined in terms of graph vertices, edges, or attributes. How is $|\text{PermissibleStates}(M_{pp} \mid \tau)|$ calculated from a `TheoryGraph`?

**Fix.**
Replace the uncomputable set-cardinality ratio with a concrete **Graph / Constraint Overdetermination Formula**:
- In **symbolic/parametric mode (ADR 0015):** Define $EFI(\tau)$ via the degree of overdetermination (or dimensionality reduction / codimension) induced by $\tau$: if determining $\tau$ requires $k_{\text{est}}$ observations in $I$ and $\tau$ constrains $k_{\text{constrained}}(\tau)$ independent empirical observations across $I$, then:
  $$EFI(\tau) = \max\left(0, \; 1 - \frac{k_{\text{est}}(\tau)}{k_{\text{constrained}}(\tau)}\right) \in [0, 1)$$
  (which directly operationalizes Schurz's (2014, sec. 5.2) criterion that a theoretical term is creative iff the number of independent empirical measurements it links strictly exceeds the number of measurements needed to fix its value!).
- In **topological graph mode:** If $\tau$ connects to $d_{\text{emp}}(\tau)$ independent empirical claims/domains and requires 1 definitional/operationalization anchor, $EFI(\tau) = \max(0, 1 - 1 / d_{\text{emp}}(\tau))$ for $d_{\text{emp}}(\tau) \ge 1$ (and $0$ for $d_{\text{emp}}(\tau) \le 1$). Notice how cleanly this gives $EFI(\tau) = 0$ when $\tau$ is an "idle wheel" used in only 1 empirical claim ($d_{\text{emp}} = 1$, i.e., an ad-hoc post-factum parameter)!

---

### TA-04 · Undefined 4-Argument Notation $C(x, a, R, p)$ — **Minor**

**Where.** [`theoretical_achievements.md#L29`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L29).

**Finding.**
Line 29 writes: *"through theoretical constraints $C(x, a, R, p)$"*.
None of the four arguments $x, a, R, p$ is defined anywhere in `theoretical_achievements.md`, `glossary.md`, or `index.md`. In structuralism, a global constraint is simply $GC \subseteq \mathcal{P}(M_p)$ (or $C \subseteq \mathcal{P}(M_p)$).

**Fix.**
Replace $C(x, a, R, p)$ with standard project notation $GC$ (or $C \subseteq \mathcal{P}(M_p)$) and define any tuple components if needed.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### TA-05 · Complete Disconnect Between §Mathematical Specification and §Measurement & Graph Implementation — **Major**

**Where.** [`theoretical_achievements.md#L33-L51`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L33-L51) vs. [`#L53-L60`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L53-L60).

**Finding.**
In §Mathematical Specification (L33–51), $EFI(\tau)$ and $PPM(\tau)$ are defined via model-theoretic state spaces `PermissibleStates(M_pp)` and conditional domain prediction sets `Pred(tau, D_j | D_i)`.
In §Measurement & Graph Implementation (L55–59), the implementation is described solely as:
> 1. **Constraint Graph Traversal**: Identify theoretical entity nodes that bridge multiple disconnected empirical observation subgraphs.
> 2. **Predictive Dependency Tracking**: Count cross-domain dependency edges originating from the shared theoretical node.

Counting cross-domain edges originating from $\tau$ neither computes $|\text{PermissibleStates}(M_{pp} \mid \tau)|$ nor normalizes by $\binom{m}{2}$ and $|Obs(D_j)|$. If an engineer implements §Measurement literally, the resulting code will not match the formulas in §Mathematical Specification.

**Fix.**
Unify §Mathematical Specification and §Measurement & Graph Implementation around the overdetermination / cross-domain constraint-bridging formulation (see Fix in TA-02 and TA-03).

---

## 4. Is the Metric Valid and Scientifically Significant?

### TA-06 · Erroneous Citation to Thagard (1989, pp. 280–287) — **Major**

**Where.** [`theoretical_achievements.md#L13`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L13), [`#L72`](../../../docs/concepts/theory/metrics/empirical_power/theoretical_achievements.md#L72), and [`docs/concepts/theory/metrics/index.md#L95`](../../../docs/concepts/theory/metrics/index.md#L95).

**Finding.**
The document cites:
> `[Thagard, 1989, pp. 280–287]` — *Thagard, P. (1989). Explanatory Coherence. Behavioral and Brain Sciences, 12(3), pp. 280–287.*

1. **Wrong Page Range:** Thagard's (1989) paper in *Behavioral and Brain Sciences* 12(3) spans **pp. 435–467** (as correctly cited in `index.md` L186 and `explanatory_breadth.md` L128)—pages 280–287 are in a completely different issue of *BBS*!
2. **Wrong Attribution:** The concepts of **Empirical Focus (*Empirischer Fokus*)**, **Prognostic Power (*Prognostische Leistung*)**, and **Theoretical Achievements (*Theoretische Leistungen*)** of $T$-theoretical terms via cross-application constraints $C$ originate in **Stegmüller (1976, pp. 65–74, 125–139)**, **Sneed (1971)**, and **Schurz (2014/2024, sec. 5.2)**—not in Thagard (1989). (Pages 280–287 likely come from a German textbook or Stegmüller/Schurz page range that was accidentally pasted onto the Thagard Zotero key `8F6MW586`.)

**Fix.**
Remove the erroneous `pp. 280–287` from Thagard (1989) and attribute Empirical Focus and Prognostic Power directly to Stegmüller (1976), Balzer et al. (1987, pp. 125–139), and Schurz (2024, sec. 5.2).

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Status Tag (`status: in_progress`):** `theoretical_achievements.md` has `status: in_progress` in its YAML frontmatter (L2), whereas the other three files in `empirical_power/` have `status: needs_verification`.
2. **Symbol Collision on $\tau$:** Uses $\tau$ for a **theoretical concept node** ($\tau \in V_T$), which matches `t_theoreticity.md` ($\tau$), but collides with QBAF equilibrium justification degree $\tau(a) \in [0, 1]$ and prior plausibility $\tau_0$ in `epistemetrics/epistemic/qbaf.py` and `formal_graph_model.md` (see `ISSUE-066` A-03).
3. **Diagnostic Table Gap (L64–67):** Only specifies `High TAS (> 0.7)` and `Low TAS (< 0.2)`, leaving the middle range **$0.2 \le TAS(\tau) \le 0.7$** (Moderate Theoretical Utility / Single-Domain Construct) uncharacterized.
