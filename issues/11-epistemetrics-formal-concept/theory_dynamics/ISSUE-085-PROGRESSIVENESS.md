# [ISSUE-085] Formal & Conceptual Evaluation: Progressiveness & Evolution Perfectness (`progressiveness.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-085` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 4: Theory Dynamics |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/theory_dynamics/progressiveness.md`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/epistemic/dynamics.py`), `episteme-pipeline` |
| **Priority** | **Critical** (contains frozen time-index bug $\operatorname{CC}(I_{t_i}) = E_e(F(I(t_1)))$ forcing $RR_{Cn} \equiv 1.0$, unbounded negative $PTM \in (-\infty, 1]$ where losing empirical content attenuates precision penalties via $\delta_{\text{retention}} \cdot PTM$, and a $TEI_{Cn}$ formula that rewards demoting confirmed applications back into unconfirmed conjectures as "Lakatosian Boldness") |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-086`](ISSUE-086-COGNITIVE-WEIGHT.md), [`ISSUE-087`](../ISSUE-087-THEORY-DYNAMICS-CROSS-CUTTING.md), [`ISSUE-083`](ISSUE-083-DEGENERATION-INDEX.md), [`ISSUE-071`](../empirical_power/ISSUE-071-EMPIRICAL-ADEQUACY.md), [`ISSUE-066`](../../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or yields inverted diagnostics · **Major** = significant formal flaw, semantic shift, or implementation divergence · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Inverted in 3 Regimes)** | Claims to measure content-weighted empirical progress ($\Pi_{\text{empirical}}$), Lakatosian theoretical boldness ($\Pi_{\text{theoretical}}$), and conjecture-to-confirmation efficiency ($EPR_{Cn}$). However: (1) in $TEI_{Cn}$, **demoting a confirmed application** $P \in F(I(t_1))$ back into an unconfirmed conjecture $A(I(t_2))$ puts $P \in E_e(A(I(t_2))) \setminus E_e(A(I(t_1)))$, rewarding empirical retraction as "Lakatosian Boldness"; (2) when $PTM < 0$, multiplying by $\delta_{\text{retention}} \in [0, 1]$ means **losing confirmed content ($\delta_{\text{retention}} \to 0$) shrinks the negative penalty** and pulls $\Pi_{\text{empirical}}$ up toward $0$; (3) despite claiming to implement Schurz's net-success rule (L96), $\Pi_{\text{empirical}} > 0$ even when $99\%$ of confirmed content is lost and only $1\%$ new content is added. |
| **2. Formally & Mathematically Correct?** | **No (4 Critical/Major Flaws)** | (1) L84 defines $\operatorname{CC}(I_{t_i}) = E_e(F(I(t_1)))$ with a hardcoded $t_1$ on the RHS, making $\operatorname{CC}(I_{t_1}) = \operatorname{CC}(I_{t_2})$ and $RR_{Cn}(t_1, t_2) \equiv 1.0$; (2) $PTM(t_1, t_2) = \frac{\bar{\epsilon}(t_1) - \bar{\epsilon}(t_2)}{\bar{\epsilon}(t_1)}$ is unbounded below in $(-\infty, 1]$ while $\sigma(AGR_{Cn}) \in [0, 1)$, and divides by zero when $\bar{\epsilon}(t_1) = 0$; (3) $TEI_{Cn}$ and $EPR_{Cn}$ divide by zero whenever a theory has no unconfirmed conjectures at $t_1$ or $t_0$ ($A(I) = \emptyset$); (4) $\forall u_j \in \text{Bound}(A_j) \, \exists u_k \in \text{Bound}(A_k) : u_k \subseteq u_j$ (L44) is trivially satisfied if $\text{Bound}(A_k)$ contains a single tight blur alongside arbitrarily loose blurs. |
| **3. Free of Semantic Shifts?** | **No (Severe Shift & Missing Implementation)** | Shifts from structuralist model-theoretic intended applications $I(t) \subseteq M_{pp}$ and uniform-space entourages $u \in \text{Bound}(\mathcal{A})$ (L29–45) to Gerhard Schurz's first-order statement-view relevant consequence operator $E_e(\cdot)$ applied directly to $F(I(t))$ (L58–120), while completely omitting any `## Measurement & Graph Implementation` section. |
| **4. Valid & Scientifically Significant?** | **Conceptually Strong, Unimplemented** | Decoupling empirical progress from theoretical boldness and gating by content retention is an insightful synthesis of Stegmüller (1976, pp. 180–195), Balzer et al. (1987, pp. 222, 363–364), and Schurz (2014), but none of its equations is currently operationalized in `epistemetrics`. |

---

## 1. Does the Metric Capture What It Claims It Does?

### PR-01 · $TEI_{Cn}(t_1, t_2)$ Rewards Demoting Confirmed Applications Into Unconfirmed Conjectures as "Lakatosian Boldness" and Misses Immediately Confirmed Predictions — **Critical**

**Where.** [`progressiveness.md#L33-L35`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L33-L35), [`#L113-L120`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L113-L120), [`#L150-L156`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L150-L156).

**Finding.**
On L33–34, the intended applications $I_i = I(t_i)$ at epoch $t_i$ are partitioned into:
- **Firm / Confirmed Applications:** $F(I_i)$
- **Assumed / Conjectured Applications:** $A(I_i) = I_i \setminus F(I_i)$.

On L119, the **Theoretical Excess Content Index ($TEI_{Cn}$) — Lakatosian Boldness** is defined as:
$$TEI_{Cn} (t_1, t_2) = \frac{\sum_{P \in E_e (A (I (t_2))) \setminus E_e (A (I (t_1)))} w (P)}{\sum_{Q \in E_e (A (I (t_1)))} w (Q)}$$
with $\Pi_{\text{theoretical}}(t_1, t_2) = \sigma(TEI_{Cn})$.

This formulation fails in three fundamental ways:
1. **Empirical Regression Masquerades as Lakatosian Boldness ($F(I(t_1)) \to A(I(t_2))$):**
   Suppose at $t_1$, an application $P \in E_e(F(I(t_1)))$ was **empirically confirmed**. Because $A(I_1) = I_1 \setminus F(I_1)$, $P \notin E_e(A(I(t_1)))$.
   At $t_2$, the theory's explanation of $P$ breaks down (e.g. a measurement or derivation fails), so $P$ loses its confirmed status and drops back into the unconfirmed set $A(I(t_2)) = I(t_2) \setminus F(I(t_2))$.
   Then:
   $$P \in E_e(A(I(t_2))) \setminus E_e(A(I(t_1)))!$$
   Thus, **losing empirical confirmation of an existing application $P$** is counted in the numerator of $TEI_{Cn}(t_1, t_2)$ as positive "Theoretical Excess Content / Lakatosian Boldness"!
2. **Immediate Confirmation Paradox ($P \notin E_e(I(t_1))$ Confirmed at $t_2$):**
   Conversely, suppose a scientist introduces a genuinely bold novel prediction $P \notin E_e(I(t_1))$ at $t_2$ and **immediately confirms it experimentally** in the same publication/epoch $t_2$, so $P \in E_e(F(I(t_2)))$ and $P \notin E_e(A(I(t_2)))$. Because $TEI_{Cn}$ only inspects $A(I(t_2)) = I(t_2) \setminus F(I(t_2))$, $P$ contributes **$0$** to $TEI_{Cn}$ ($\Pi_{\text{theoretical}} = 0$)!
3. **Division by Zero When $A(I(t_1)) = \emptyset$:**
   If a theory at $t_1$ has confirmed all of its existing intended applications ($F(I(t_1)) = I(t_1)$, so $A(I(t_1)) = \emptyset$), then the denominator $\sum_{Q \in E_e(A(I(t_1)))} w(Q) = 0$, causing $TEI_{Cn}(t_1, t_2)$ to **divide by zero** at the exact moment the theory introduces new conjectures at $t_2$!

**Fix.**
1. To measure genuinely **novel** unconfirmed conjectures introduced at $t_2$, subtract the **entire** prior content $E_e(I(t_1)) = E_e(F(I(t_1))) \cup E_e(A(I(t_1)))$ in the numerator, not just $E_e(A(I(t_1)))$!
2. Normalize the denominator by the total content of $I(t_1)$ (i.e. $\sum_{Q \in E_e(I(t_1))} w(Q)$), which is non-zero for any non-empty theory at $t_1$ even when $A(I(t_1)) = \emptyset$:
   $$TEI_{Cn}(t_1, t_2) = \frac{\sum_{P \in E_e(A(I(t_2))) \setminus E_e(I(t_1))} w(P)}{\sum_{Q \in E_e(I(t_1))} w(Q)}.$$

---

### PR-02 · Multiplicative Gating $\delta_{\text{retention}} \cdot [\dots]$ Attenuates Negative Precision Penalties ($PTM < 0$) and Violates Schurz's Net-Success Rule — **Critical**

**Where.** [`progressiveness.md#L93-L101`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L93-L101), [`#L122-L148`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L122-L148), [`#L180-L188`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L180-L188).

**Finding.**
Look at Equation L145 for Empirical Progressiveness:
$$\Pi_{\text{empirical}} (t_1, t_2) = \delta_{\text{retention}} (t_1, t_2) \cdot \left[ w_1 \cdot \sigma (AGR_{Cn}) + w_2 \cdot PTM (t_1, t_2) \right]$$
where $\delta_{\text{retention}}(t_1, t_2) = (RR_{Cn}(t_1, t_2))^\gamma \in [0, 1]$, $\sigma(AGR_{Cn}) = \frac{AGR_{Cn}}{1 + AGR_{Cn}} \in [0, 1)$, and $PTM(t_1, t_2) = \frac{\bar{\epsilon}(t_1) - \bar{\epsilon}(t_2)}{\bar{\epsilon}(t_1)} \in (-\infty, 1]$.

This creates three severe mathematical pathologies:
1. **Sign-Inversion of the Retention Penalty When $PTM < 0$:**
   On L131–132, the document explicitly notes that $PTM$ can be negative:
   > *"Unlike the legacy metric, $PTM$ is not clamped at $0.0$, allowing precision losses to correctly yield a negative signal."*
   Suppose $AGR_{Cn} = 0$ and precision worsens so $w_2 \cdot PTM(t_1, t_2) = -0.60 < 0$.
   - If Theory A **retains $100\%$ of its confirmed content** ($RR_{Cn} = 1.0 \implies \delta_{\text{retention}} = 1.0$), it receives $\Pi_{\text{empirical}}(A) = 1.0 \times (-0.60) = -0.60$.
   - If Theory B **loses $90\%$ of its confirmed content** ($RR_{Cn} = 0.1 \implies \delta_{\text{retention}} = 0.1^2 = 0.01$), it receives $\Pi_{\text{empirical}}(B) = 0.01 \times (-0.60) = -0.006 \gg -0.60$!
   Because a negative number is multiplied by $\delta_{\text{retention}} \in [0, 1]$, **discarding confirmed empirical content improves $\Pi_{\text{empirical}}$ whenever the bracket is negative**!
2. **Asymmetric Unboundedness of $PTM \in (-\infty, 1]$ vs. Bounded $\sigma(AGR_{Cn}) \in [0, 1)$:**
   While $AGR_{Cn} \in [0, \infty)$ is compressed into $[0, 1)$ via $\sigma(x) = \frac{x}{1+x}$, $PTM(t_1, t_2) = 1 - \frac{\bar{\epsilon}(t_2)}{\bar{\epsilon}(t_1)}$ is **unbounded below** as $\bar{\epsilon}(t_2) / \bar{\epsilon}(t_1)$ grows (e.g., if error blur increases $5\times$, $PTM = -4.0$, overwhelming $w_1 \sigma(AGR_{Cn}) < 1$), and **divides by zero** if $\bar{\epsilon}(t_1) = 0$.
3. **Failure to Implement Claimed "Schurz's Net-Success Rule" (L96–97):**
   L96–97 claims to enforce *"Schurz's net-success rule (where progress remains positive if new successes strictly outweigh lost content)"*.
   Yet under Equation L145, if a theory at $t_2$ **loses $80\%$ of its confirmed content** ($RR_{Cn} = 0.20$, lost weight $= 0.80 V_1$) and adds only **$5\%$ new confirmed content** ($AGR_{Cn} = 0.05$, gained weight $= 0.05 V_1 \ll 0.80 V_1$) with $PTM = 0$, net content change is $-0.75 V_1 < 0$ (severe regression), yet Equation L145 outputs:
   $$\Pi_{\text{empirical}} = (0.20)^2 \cdot w_1 \frac{0.05}{1.05} > 0 \quad (\text{strictly positive!}).$$
   In fact, Equation L145 **never** yields a negative value for content loss when $PTM \ge 0$!

**Fix.**
1. Symmetrize and bound $PTM(t_1, t_2) \in [-1, 1]$ so it cannot divide by zero or diverge to $-\infty$:
   $$PTM_{\text{sym}}(t_1, t_2) = \frac{\bar{\epsilon}(t_1) - \bar{\epsilon}(t_2)}{\bar{\epsilon}(t_1) + \bar{\epsilon}(t_2) + \epsilon_0} \in (-1, 1).$$
2. Directly incorporate **net content balance** ($AGR_{Cn} - (1 - RR_{Cn})$) or apply $\delta_{\text{retention}}$ only to the positive growth term while subtracting content loss $(1 - RR_{Cn})$:
   $$\Pi_{\text{empirical}}(t_1, t_2) = w_1 \cdot \Big(\delta_{\text{retention}} \cdot \sigma(AGR_{Cn}) - (1 - RR_{Cn})\Big) + w_2 \cdot PTM_{\text{sym}}(t_1, t_2) \in [-1, 1].$$
   Under this formulation:
   - Losing content does not attenuate a negative $PTM_{\text{sym}}$; it makes $\Pi_{\text{empirical}}$ strictly more negative.
   - When lost content $(1 - RR_{Cn})$ exceeds $\delta_{\text{retention}} \sigma(AGR_{Cn})$, the first term becomes strictly negative, faithfully implementing Schurz's net-success rule!

---

## 2. Is the Metric Formally & Mathematically Correct?

### PR-03 · Hardcoded $t_1$ Typo in $\operatorname{CC}(I_{t_i}) = E_e(F(I(t_1)))$ Forces $RR_{Cn}(t_1, t_2) \equiv 1.0$ — **Critical**

**Where.** [`progressiveness.md#L81-L91`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L81-L91).

**Finding.**
Lines 81–91 state:
> *"Let the relevant empirical content, of a confirmed application at time/version $t_i$ be*
> *$$\operatorname{CC} (I_{t_i}) = E_e (F (I (t_1)))$$"*
> *"We define the **Content Retention Rate ($RR_{Cn}$)**:*
> *$$RR_{Cn} (t_1, t_2) = \frac{\sum_{P \in \operatorname{CC} (I_{t_1}) \cap \operatorname{CC} (I_{t_2})} w (P)}{\sum_{Q \in \operatorname{CC} (I_{t_1})} w (Q)}$$"*

Because the right-hand side of L84 hardcodes $t_1$ (`E_e(F(I(t_1)))`) instead of $t_i$ (`E_e(F(I(t_i)))`), $\operatorname{CC}(I_{t_2}) = E_e(F(I(t_1))) = \operatorname{CC}(I_{t_1})$, so $\operatorname{CC}(I_{t_1}) \cap \operatorname{CC}(I_{t_2}) = \operatorname{CC}(I_{t_1})$ and $RR_{Cn}(t_1, t_2) = 1.0$ identically for all $t_1, t_2$!

**Fix.**
Change L84 to:
$$\operatorname{CC}(I_{t_i}) = E_e(F(I(t_i))).$$

---

### PR-04 · Quantifier Order Error in Precision Tightening Condition ($\forall u_j \exists u_k$) and Incomplete Scope of $EPR_{Cn}(\mathcal{E})$ — **Major**

**Where.** [`progressiveness.md#L39-L45`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L39-L45), [`#L160-L172`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L160-L172).

**Finding.**
1. **Quantifier Direction in Blur Tightening (L44):**
   L44 writes the precision refinement condition as:
   $$\forall u_j \in \text{Bound} (A_j), \, \exists u_k \in \text{Bound} (A_k) \quad \text{s.t.} \quad u_k \subseteq u_j.$$
   In structuralism (BMS 1987, p. 214, 363; `formal_graph_model.md` L325), $\mathcal{A}_j \subseteq \mathcal{U}$ is a collection of **admissible blurs** (tolerances that are deemed acceptable). If $\mathcal{A}_k$ contains *one* very tight blur $u_{\text{tight}} \subseteq u_j$ (for instance, the diagonal $\Delta(M_p)$) **plus** arbitrarily huge, permissive blurs $u_{\text{huge}} \supsetneq u_j$, then $\forall u_j \exists u_k (u_k \subseteq u_j)$ is trivially true by picking $u_k = u_{\text{tight}}$, even though $T_k$ now permits much looser approximations $u_{\text{huge}} \in \mathcal{A}_k$!
   To ensure that every admissible blur in the successor $T_k$ is at least as sharp as an admissible blur in the predecessor $T_j$ (i.e. tightening the upper bound of admissible error), the quantifier order must be:
   $$\forall u_k \in \mathcal{A}_k, \, \exists u_j \in \mathcal{A}_j \quad \text{s.t.} \quad u_k \subseteq u_j \quad (\text{with } \exists u_k \in \mathcal{A}_k \, \forall u_j \in \mathcal{A}_j : u_k \subsetneq u_j).$$
2. **$EPR_{Cn}(\mathcal{E})$ Evaluates Only Epoch-$t_0$ Conjectures and Divides by Zero When $A(I, t_0) = \emptyset$ (L165–172):**
   $$EPR_{Cn} (\mathcal{E}) = \frac{\sum_{P \in E_e (A (I, t_0)) \cap E_e (F (I, t_k))} w (P)}{\sum_{Q \in E_e (A (I, t_0))} w (Q)}$$
   - First, L29–30 indexes the sequence as $\mathcal{E} = \langle N_1, \dots, N_k \rangle$ ($t_1 < \dots < t_k$) and writes $A(I(t_1))$, whereas L165–168 shifts to $\langle N_0, \dots, N_k \rangle$ and writes $A(I, t_0)$.
   - Second, if $A(I, t_0) = \emptyset$, the denominator is $0$.
   - Third, $EPR_{Cn}(\mathcal{E})$ ignores all conjectures introduced at intermediate epochs $t_1, \dots, t_{k-1}$! Yet L153–155 explicitly states that excess content generated by $\Pi_{\text{theoretical}}(t_i, t_{i+1})$ at any step must be converted into confirmed applications in subsequent steps.
   To measure cumulative conjecture-conversion efficiency across $\mathcal{E}$, $EPR_{Cn}(\mathcal{E})$ should track the union of conjectures generated across $t_0, \dots, t_{k-1}$:
   $$A_{\text{cum}}(\mathcal{E}) = \bigcup_{i=0}^{k-1} E_e(A(I(t_i))), \qquad EPR_{Cn}(\mathcal{E}) = \frac{\sum_{P \in A_{\text{cum}}(\mathcal{E}) \cap E_e(F(I(t_k)))} w(P)}{\sum_{Q \in A_{\text{cum}}(\mathcal{E})} w(Q)}.$$

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### PR-05 · Semantic Shift Between Structuralist Intended Applications $I(t) \subseteq M_{pp}$ and Statement-View Relevant Consequences $E_e(H)$, Plus Missing Graph Implementation — **Critical**

**Where.** [`progressiveness.md#L29-L46`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L29-L46) vs. [`#L49-L76`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L49-L76) vs. [`#L174-L176`](../../../docs/concepts/theory/metrics/theory_dynamics/progressiveness.md#L174-L176).

**Finding.**
1. **Applying $E_e(\cdot)$ to Intended Applications $F(I(t))$ Instead of Theory Hypotheses $H$:**
   - In §Theoretical Grounding (L29–35), $I(t_i) \subseteq M_{pp}$ is the structuralist set of **intended applications** (partial potential models), partitioned into $F(I_i)$ and $A(I_i)$.
   - In §Mathematical Specification (L51–75), the document invokes Gerhard Schurz's relevant empirical content operator $E_e(\cdot)$—which in Schurz (1991, 2014; see [`cognitive_weight.md`](../../../docs/concepts/theory/metrics/theory_dynamics/foundations/cognitive_weight.md#L15)) is defined on a **theoretical hypothesis/axiom system $H$** ($E_e(H)$ = irreducible non-analytic empirical consequences derived from $H$)—and applies it instead to $F(I(t))$: $E_e(F(I(t)))$.
   - As analyzed in [`ISSUE-086` CW-02](ISSUE-086-COGNITIVE-WEIGHT.md), if $F(I(t))$ consists of singular empirical applications/observations, then every element $P \in E_e(F(I(t)))$ is a singular empirical statement, which under `cognitive_weight.md` Approach A receives a flat weight $w(P) = 1$, rendering the entire cognitive-weighting machinery trivial unless $E_e(\cdot)$ includes general empirical laws $\forall x (Fx \to Gx)$ derived from $K(t)$ and confirmed by $F(I(t))$!
2. **Missing `## Measurement & Graph Implementation` Section:**
   Unlike `degeneration_index.md` and `paradigm_guidance.md`, `progressiveness.md` has **no implementation section**, no Cypher queries, and no mapping to `epistemetrics.TheoryGraph`. Furthermore, the note on L174–176 refers the reader to `"Structuralist Foundations of Episteme"`, a document title that does not exist in `docs/`.

**Fix.**
Add a `## Measurement & Graph Implementation` section defining how $F(I(t))$, $A(I(t))$, $E_e(\cdot)$, $w(P)$, and $\bar{\epsilon}(t)$ map to `epistemetrics.TheoryGraph`:
- Confirmed empirical claims/applications $F(I(t))$: empirical nodes (`NodeType.PARADIGM`, `PHENOMENON`, `EVIDENCE`, `CLAIM`) explained by $N_t$ (`RelationType.EXPLAINS` / `SUPPORTS`) with tenability $TS_{\text{local}}(y) \ge \tau_{\text{ten}}$ (and mean blur $\bar{\epsilon}(t) = \frac{1}{|F(I(t))|} \sum_{y \in F(I(t))} (1 - TS_{\text{local}}(y))$ from `tenability.md`!).
- Conjectured applications $A(I(t))$: intended application or predicted claim nodes attached to $N_t$ that lack empirical verification ($E_{\text{total}} = 0$ or unverified status).

---

## 4. Is the Metric Valid and Scientifically Significant?

### PR-06 · Strong Conceptual Architecture, Needs Direct Integration with `tenability.md` ($\bar{\epsilon} = 1 - \overline{TS}_{\text{local}}$) and `dynamics.py` — **Major**

**Finding.**
Notice how naturally $PTM(t_1, t_2)$ connects to `tenability.md` (`ADR 0015`): in `tenability.md` (L130), each application $y \in I$ has optimal blur $\delta^*(y) = 1 - TS_{\text{local}}(y, M)$. Setting $\bar{\epsilon}(t) = \frac{1}{|F(I(t))|} \sum_{y \in F(I(t))} \delta^*(y) = 1 - \overline{TS}_{\text{local}}(t)$ makes $PTM(t_1, t_2)$ directly computable from the Tenability post-processing pass! Currently this bridge is missing in both `progressiveness.md` and `epistemetrics/epistemic/dynamics.py`.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Internal Symbol Collision on $A$ (L20, L44 vs. L22, L34, L115):** On L20 and L44, $A_1, A_2, A_j, A_k$ denote **admissible blur families** ($\text{Bound}(A_j)$), whereas on L22, L34, L115, L119, and L168 of the same document, $A(I_i)$ denotes **Assumed / Conjectured Applications**. Use calligraphic $\mathcal{A}_j$ for admissible blurs (matching `formal_graph_model.md` L324 and `tenability.md` L52) and $A(I_i)$ (or $I_{\text{conj}}(t_i)$) for conjectured applications.
2. **Inconsistent Start Index ($N_1, t_1$ vs. $N_0, t_0$) and Argument Syntax ($A(I(t_1))$ vs. $A(I, t_0)$):** L29–120 indexes the sequence from $t_1$ and writes $A(I(t_1)), F(I(t_1))$; L165–168 indexes from $t_0$ and writes $A(I, t_0), F(I, t_k)$.
3. **Typos (L73, L81, L124):** L73 `irreduceable` $\to$ `irreducible`; L81 `content, of` $\to$ `content of`; L124 `(see glossar)` $\to$ `([see glossary](../../../glossary.md#zulassige-unscharfen-admissible-blurs-a))`.
