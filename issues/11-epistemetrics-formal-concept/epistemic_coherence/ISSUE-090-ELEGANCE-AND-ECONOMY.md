# [ISSUE-090] Formal & Conceptual Evaluation: Elegance and Economy (`elegance_and_economy.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-090` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 2: Epistemic Coherence & Parsimony |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (Axiom Parsimony Score $APS(T)$ cannot exceed $0.50$ for any non-empty theory—making the diagnostic threshold $APS > 0.7$ mathematically unreachable except for an empty theory $|Ax|=0$—leaves $c(b \mid A_{\text{core}})$ without a closed-form equation, and is vulnerable to Hempel's Conjunction Problem that `simplicity.md` explicitly forbids) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-092`](ISSUE-092-SIMPLICITY.md), [`ISSUE-095`](../ISSUE-095-EPISTEMIC-COHERENCE-CROSS-CUTTING.md), [`ISSUE-072`](../empirical_power/ISSUE-072-EMPIRICAL-CONTENT.md), [`ISSUE-081`](../metatheoretical/ISSUE-081-UNIFICATION.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Rewards Empty Theories & Fails on All Real Theories)** | Claims to measure Ockham's Razor ("minimizing unnecessary mathematical baggage while maximizing descriptive power"). However, $APS(T) = \frac{1}{1 + \log_2(1 + \|Ax(T)\|) + \log_2(1 + \|\Theta(T)\|)}$ ignores descriptive/explanatory power completely: an empty theory ($\|Ax\| = \|\Theta\| = 0$) scores $APS = 1.0$, while **every non-empty theory** ($\|Ax\| \ge 1$) is bounded by $APS \le 0.50$ (and $\le 0.333$ if $\|\Theta\| \ge 1$), making the "Elegant & Parsimonious" regime ($APS > 0.7$) mathematically impossible for any actual theory! |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) $c(b \mid A_{\text{core}}) \in [0, 1]$ in $L(D \mid M)$ has **no closed-form mathematical equation** (only two qualitative limit arrows $c \to 0$ and $c \to 1$); (2) $L(M) = w_n \|A_{\text{core}}\| + w_e \|R_{\text{core}}\|$ and $L(D \mid M) \in [0, \|B\|]$ have incommensurable units and unspecified weights $w_n, w_e$; (3) $APS(T)$ range and diagnostic thresholds ($> 0.7$ vs. $< 0.3$) are algebraically inconsistent with integer cardinalities $\|Ax(T)\|, \|\Theta(T)\| \in \mathbb{N}$. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts from (a) algorithmic Kolmogorov/MDL codelength in bits (L17–41) to (b) structuralist axiom and parameter counts $\|Ax(T)\|, \|\Theta(T)\|$ (L47–54) to (c) unweighted QBAF node and edge counts $\|A_{\text{core}}\|, \|R_{\text{core}}\|$ including internal attacks $\mathcal{R}_{att}$ (L62–72) to (d) structural isomorphism $Z_2$ (L88–89). |
| **4. Valid & Scientifically Significant?** | **Conceptually Valid, Formally Uncomputable** | Two-part MDL (Rissanen 1978; Grünwald 2005) is a premier formalization of parsimony, but requires a well-defined codelength formula for both model complexity (using MDL content elements $c(a)$ from `simplicity.md` rather than raw node counts) and residual data description length. |

---

## 1. Does the Metric Capture What It Claims It Does?

### EE-01 · Algebraic Impossibility of $APS(T) > 0.7$ for Any Non-Empty Theory & Vacuous-Theory Optimization Trap — **Critical**

**Where.** [`elegance_and_economy.md#L49-L55`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L49-L55), [`#L94-L100`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L94-L100), and [`simplicity.md#L167-L168`](../../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L167-L168), [`#L180-L185`](../../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L180-L185).

**Finding.**
The **Axiom Parsimony Score ($APS$)** is defined on L54 as:
$$APS(T) = \frac{1}{1 + \log_2(1 + |Ax(T)|) + \log_2(1 + |\Theta(T)|)}$$
and interpreted in the Diagnostic Table (L97–99) as:
- **High $APS$ ($> 0.7$):** *"Elegant & Parsimonious — Compact mathematical core deriving rich empirical theorems."*
- **Low $APS$ ($< 0.3$):** *"Bloated / Complex — Redundant or unpruned formal definitions with excess conceptual overhead."*
(And in `simplicity.md` L182–183, the "Epistemic Ideal" requires **$APS \ge 0.8$**!)

**Why this formula fails mathematically and conceptually:**
1. **No Non-Empty Theory Can Ever Achieve $APS > 0.50$ (Let Alone $> 0.70$ or $\ge 0.80$):**
   Because $|Ax(T)| \in \{0, 1, 2, \dots\}$ and $|\Theta(T)| \in \{0, 1, 2, \dots\}$ are set cardinalities (non-negative integers):
   - For the **minimal possible non-empty theory** with $|Ax(T)| = 1$ axiom and $|\Theta(T)| = 0$ parameters:
     $$APS(T) = \frac{1}{1 + \log_2(1 + 1) + \log_2(1 + 0)} = \frac{1}{1 + 1 + 0} = 0.50.$$
   - For a minimal parametric theory with $|Ax(T)| = 1$ axiom and $|\Theta(T)| = 1$ parameter:
     $$APS(T) = \frac{1}{1 + \log_2(2) + \log_2(2)} = \frac{1}{3} \approx 0.333.$$
   - For **Newtonian Mechanics** with $|Ax(T)| = 3$ axioms (Newton's 3 laws) and $|\Theta(T)| = 1$ universal constant ($G$):
     $$APS(T) = \frac{1}{1 + \log_2(4) + \log_2(2)} = \frac{1}{1 + 2 + 1} = 0.25 < 0.30!$$
   Thus:
   - The diagnostic category **High $APS$ ($> 0.7$)** (and $APS \ge 0.8$ in `simplicity.md`) is **mathematically unreachable for every non-empty theory in existence**!
   - The **only** object that satisfies $APS > 0.7$ is the **empty theory** $|Ax(T)| = 0, |\Theta(T)| = 0$ ($APS = 1.0$), which explains zero phenomena yet is diagnosed as *"Compact mathematical core deriving rich empirical theorems"*!
   - Conversely, every theory with $\ge 3$ axioms and $\ge 1$ parameter (or $\ge 2$ axioms and $\ge 2$ parameters, where $APS = \frac{1}{1 + 2\log_2 3} = 0.239 < 0.30$) is unconditionally classified as **"Bloated / Complex ($< 0.3$)"**!
2. **$APS(T)$ Ignores Explanatory Yield ("Deriving Rich Empirical Theorems"):**
   $APS(T)$ is a monotonically decreasing function of $|Ax(T)|$ and $|\Theta(T)|$ alone; it does not divide or normalize by the number of explained empirical applications $|I|$ or derived theorems $|D|$. A 1-axiom trivial claim that explains 0 observations gets $APS = 0.50$, whereas a 3-axiom grand unified theory that explains 1,000 observations gets $APS = 0.25$.
3. **Destructive Downstream Coupling in `simplicity.md` (L167–168):**
   `simplicity.md` (L167–168) imports $APS(T)$ as the baseline prior plausibility $\tau(a_i)$ for QBAF initialization. Because $APS(T) \le 0.333$ for any parametric theory, this initializes all axioms in QBAF well below the neutral prior $0.50$ (in the disbelieved regime)!

**Fix.**
Either:
1. **Normalize Axiom/Parameter Complexity by Empirical Scope (Compression Ratio):**
   Let $C_{\text{core}}(T) = \sum_{a \in Ax(T)} c(a) + |\Theta(T)|$ be the MDL core complexity and $|I_{\text{exp}}(T)|$ (or $M_w$) be the confirmed empirical scope. Define $APS(T)$ so that a 1-axiom, 0-parameter core ($C_{\text{core}} = 1$) starts at $1.0$ (or scales relative to explained scope):
   $$APS(T) = \frac{1}{1 + \alpha \log_2\big(1 + \max(0, C_{\text{core}}(T) - 1)\big)} \quad \text{or} \quad APS(T) = \frac{|I_{\text{exp}}(T)|}{|I_{\text{exp}}(T)| + C_{\text{core}}(T)} \in [0, 1].$$
2. If $APS(T)$ is kept as a pure intrinsic core-size prior (independent of $|I|$), shift the argument by $-1$ so a 1-axiom core achieves $APS = 1.0$ (with $APS(\emptyset) := 0$) and lower the logarithmic slope (e.g. $\frac{1}{1 + 0.25 \log_2(|Ax(T)| + |\Theta(T)|)}$), or recalibrate the diagnostic thresholds to match the actual algebraic range.

---

### EE-02 · Syntactic Node-Packing Vulnerability in $L(M)$ and $APS(T)$ Directly Contradicts `simplicity.md` — **Major**

**Where.** [`elegance_and_economy.md#L54`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L54), [`#L72`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L72) vs. [`simplicity.md#L39-L62`](../../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L39-L62).

**Finding.**
In [`simplicity.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/simplicity.md#L39-L62) (§Resolution of Hempel's Conjunction Problem via MDL), the documentation proves that any metric counting raw nodes $|A|$ can be trivially gamed by conjoining $k$ independent axioms $a_1, \dots, a_k$ into a single composite axiom node $a^* = (a_1 \land \dots \land a_k)$, artificially reducing the node count from $k$ to $1$. `simplicity.md` solves this by weighting each node $a_i$ by its irreducible content-element count $c(a_i) = \max(1.0, |Ce(a_i)|)$.

However, `elegance_and_economy.md` (which `simplicity.md` L191 calls its macro partner sharing *"the same information-theoretic compression engine"*) ignores $c(a_i)$ completely:
- L54 uses raw axiom cardinality $|Ax(T)|$ in $APS(T)$.
- L72 defines theory description length as raw node and edge cardinality:
  $$L(M) = w_n \cdot |A_{\text{core}}| + w_e \cdot |R_{\text{core}}|.$$
Under L54 and L72, packing 10 independent axioms into 1 conjunctive node $a^*$ slashes $L(M)$ by $90\%$ and boosts $APS(T)$!

**Fix.**
Replace raw node cardinality $|A_{\text{core}}|$ in $L(M)$ and $|Ax(T)|$ in $APS(T)$ with the sum of irreducible content-element complexities $\sum_{a \in A_{\text{core}}} c(a) = \sum_{a \in A_{\text{core}}} |Ce(a)|$ defined in `simplicity.md`.

---

## 2. Is the Metric Formally & Mathematically Correct?

### EE-03 · Missing Closed-Form Equation for $c(b \mid A_{\text{core}})$ and Incommensurable Scaling in $MDL(T) = L(M) + L(D \mid M)$ — **Critical**

**Where.** [`elegance_and_economy.md#L58-L92`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L58-L92).

**Finding.**
1. **No Mathematical Formula for $c(b \mid A_{\text{core}})$:**
   L81 defines Data Description Length as:
   $$L(D \mid M) = \sum_{b \in B} c(b \mid A_{\text{core}})$$
   and L83–90 describes $c(b \mid A_{\text{core}}) \in [0, 1]$ only via two qualitative prose bullets ($c \to 0$ for strong $\mathcal{R}_{sup}$ with high $\phi$; $c \to 1$ for $\mathcal{R}_{att}$ or absence of structural isomorphism).
   There is **no equation** specifying how $c(b \mid A_{\text{core}})$ is computed from the graph's edge weights $\phi(a, b)$ or how multiple incoming support and attack edges from $A_{\text{core}}$ to $b$ are aggregated! As written, $L(D \mid M)$ and $MDL(T)$ cannot be implemented.
2. **Incommensurable Units & Unspecified Free Weights $w_n, w_e$:**
   In Grünwald (2005), $L(M)$ and $L(D \mid M)$ are both measured in **bits** ($-\log_2 P(M)$ and $-\log_2 P(D \mid M)$), so a $1$-bit increase in $L(M)$ trades off against a $1$-bit decrease in $L(D \mid M)$.
   Here:
   - $L(M) = w_n |A_{\text{core}}| + w_e |R_{\text{core}}|$ has arbitrary unspecified weights $w_n, w_e > 0$ (whose default values are never stated).
   - $L(D \mid M) \in [0, |B|]$ is bounded by $|B|$, where each explained observation reduces $L(D \mid M)$ by at most $1.0$.
   - If $w_n + w_e > 1.0$, introducing a new hypothesis $a$ with $1$ explanatory edge to explain $1$ observation $b$ *increases* $MDL(T)$ (worsening the score). Conversely, if $|B|$ is large vs. small across different runs, raw $MDL(T) \in [0, \infty)$ is not normalized by $|B|$ (i.e. $MDL(T) / MDL(\emptyset) = \frac{L(M) + L(D \mid M)}{|B|}$), and has no entry in the Diagnostic Table (L95–99, which only lists $APS$!).

**Fix.**
1. Provide an explicit closed-form equation for $c(b \mid A_{\text{core}}) \in [0, 1]$ over the admissible support and attack edges between $A_{\text{core}}$ and $b$, e.g.:
   $$c(b \mid A_{\text{core}}) = 1 - \max\left(0, \; \frac{S(b \mid A_{\text{core}})}{1 + S(b \mid A_{\text{core}})} - \frac{A(b \mid A_{\text{core}})}{1 + A(b \mid A_{\text{core}})}\right) \in [0, 1]$$
   where $S(b \mid A_{\text{core}}) = \sum_{a \in A_{\text{core}} : (a, b) \in \mathcal{R}_{sup}} \phi(a, b)$ and $A(b \mid A_{\text{core}}) = \sum_{a \in A_{\text{core}} : (a, b) \in \mathcal{R}_{att}} \phi(a, b)$ (or using the Shannon codelength $-\log_2 P(b \mid A_{\text{core}})$).
2. Specify canonical default values for $w_n, w_e$ and normalize total $MDL$ against the null/literal encoding cost $L(D \mid \emptyset) = |B|$ to yield the **MDL Compression Ratio**:
   $$\text{CR}_{\text{MDL}}(T) = \frac{L(M) + L(D \mid M)}{|B|} \quad (\text{where } \text{CR}_{\text{MDL}}(T) < 1.0 \iff T \text{ achieves net compression}).$$

---

### EE-04 · Inclusion of Attacking Edges $\mathcal{R}_{att}$ Inside the Theory Core $R_{\text{core}}$ — **Major**

**Where.** [`elegance_and_economy.md#L68-L72`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L68-L72).

**Finding.**
L68–70 defines the theory core subgraph as $G_{\text{core}} = (A_{\text{core}}, R_{\text{core}})$ where:
$$R_{\text{core}} \subseteq \mathcal{R}_{att} \cup \mathcal{R}_{sup}$$
are the logical relations connecting $A_{\text{core}}$.
1. A coherent theory core $G_{\text{core}}$ consists of axioms, definitions, and deductive/specialization links (`SPECIALIZES`, `CONSTRAINS`, `EXPLAINS`, `SUPPORTS`), **not internal self-attacks $\mathcal{R}_{att}$**! If a theory core contains internal attack edges $\mathcal{R}_{att}$ among its own core axioms, that is a logical inconsistency (Pillar 2 `consistency.md`), not mere description-length overhead.
2. Meanwhile, in L86–88, $\mathcal{R}_{sup}$ and $\mathcal{R}_{att}$ are used for the **mapping edges** between $A_{\text{core}}$ and $B$ ($A_{\text{core}} \times B$), which are external to $G_{\text{core}} = (A_{\text{core}}, R_{\text{core}})$ yet are not excluded from $R_{\text{core}}$.

**Fix.**
Define $R_{\text{core}} \subseteq (A_{\text{core}} \times A_{\text{core}}) \cap (\mathcal{R}_{sup} \cup \mathcal{R}_{\text{struct}})$ as the intra-core deductive and structural relations, and define $R_{\text{map}} \subseteq A_{\text{core}} \times B$ as the core-to-empirical mapping relations used in $L(D \mid M)$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### EE-05 · Three-Way Ontological Shift Between Structuralist Tuple $T = \langle K, I \rangle$, QBAF Subgraph $G_{\text{core}}$, and Mapping Isomorphism $Z(a, b)$ — **Major**

**Where.** [`elegance_and_economy.md#L47-L55`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L47-L55) $\to$ [`#L62-L74`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L62-L74) $\to$ [`#L78-L90`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L78-L90).

**Finding.**
1. **Structuralist Regime (L47–54):** Assumes $T = \langle K, I \rangle$ with an explicit axiom set $Ax(T)$ and parameter set $\Theta(T)$. Neither $Ax(T)$ nor $\Theta(T)$ exists as a field on `epistemetrics.TheoryGraph` (parameters are only induced optionally during post-processing in `episteme_pipeline/post_processing/theoretical_enrichment/`).
2. **QBAF Regime (L62–74):** Switches to $V = A \cup B$ and defines $G_{\text{core}} = (A_{\text{core}}, R_{\text{core}})$, without specifying how $A_{\text{core}} \subseteq A$ is selected from $A$ (is $A_{\text{core}}$ the set of nodes with `EpistemicStatus.HARD_CORE`, or `NodeType.AXIOM`, or all $A$?) or how $Ax(T)$ and $\Theta(T)$ relate to $A_{\text{core}}$ and $R_{\text{core}}$.
3. **Mapping Law Regime (L79–90):** Switches to mapping laws $Z(a, b)$ and "structural isomorphism" ($Z_2$), which in `formal_graph_model.md` (L280; see [`ISSUE-067` B-21](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md)) is an undefined function $\sigma(\kappa(a), \kappa(b))$.

**Fix.**
Unify the domain mapping on `TheoryGraph`:
- Define $A_{\text{core}}(T) \equiv Ax(T)$ as the set of core theoretical propositions (`NodeType.AXIOM` / `HYPOTHESIS` belonging to theory $T$), weighted by MDL content elements $c(a) = |Ce(a)|$.
- Define $\Theta(T)$ via `node.attributes.get("parameters", {})` (or Induced `TheoryElementDefinition.parameter_names` when Theoretical Enrichment is active, defaulting to $\emptyset$ in purely qualitative corpora).

---

## 4. Is the Metric Valid and Scientifically Significant?

### EE-06 · Missing Measurement & Graph Implementation Section and Overlap with `unification.md` & `empirical_content.md` — **Minor**

**Where.** [`elegance_and_economy.md#L90-L100`](../../../docs/concepts/theory/metrics/epistemic_coherence/elegance_and_economy.md#L90-L100).

**Finding.**
1. Unlike the other metric documents in `docs/concepts/theory/metrics/`, `elegance_and_economy.md` completely **omits the `## Measurement & Graph Implementation` section** between `## Mathematical Specification & Graph Formulation` and `## Diagnostic & Metascientific Value`.
2. As noted in [`ISSUE-075`](../ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md#2-unacknowledged-overlap-and-contradictions-between-pillar-3-metrics-and-other-pillars--major), the trade-off between core size $|A_{\text{core}}|$ and explained empirical base $|B|$ is also measured by the **Unification Ratio** $U_{\text{ratio}} = |D|/|B|$ (`unification.md`) and the **Degrees-of-Freedom regularizer** $\exp(-\lambda k_T / M_w)$ in `empirical_content.md`.

**Fix.**
Add the missing `## Measurement & Graph Implementation` section specifying how $A_{\text{core}}$, $R_{\text{core}}$, $\Theta(T)$, and $c(b \mid A_{\text{core}})$ are extracted from `TheoryGraph`, and add `MDL Compression Ratio` to the Diagnostic Table alongside `APS`.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Broken Desktop Zotero Links & Duplicate Key `24SNSW2B` (L12):** Both `[Balzer et al., 1987, p. xviii]` and `[Schurz, 2024, sec. 5.2]` link to `zotero://select/library/items/24SNSW2B`.
2. **Symbol Collision on $M$ (L60 vs. `tenability.md`):** In `MDL(T) = L(M) + L(D \mid M)` (L60), $M$ stands for the statistical "Model" (Grünwald 2005), whereas in structuralist metrics (`tenability.md` L35, `formal_graph_model.md` L309) $M \subseteq M_p$ stands for the class of **Actual Models** (fundamental laws). Use $L(H)$ and $L(D \mid H)$ (or $L(K)$ and $L(B \mid K)$) to avoid colliding with $M \subseteq M_p$.
