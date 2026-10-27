# [ISSUE-079] Formal & Conceptual Evaluation: Semantic & Axiomatic Homogeneity (`semantic_homogeneity.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-079` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 5: Metatheoretical Framework |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** ($AID$ checks for direct inference edges between independent axioms, yielding $H_{\text{axiomatic}} = 0$ for every non-redundant axiomatization; minimization domain omits $A_1, A_2 \neq \emptyset$ and $A_1 \cap A_2 = \emptyset$, dividing by zero at $A_1 = \emptyset$) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-082`](../ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md), [`ISSUE-055`](../../09-architecture-workflow-domain/ISSUE-055-bipartite-inference-hypergraph-conjunctive-premises-and-undercutters.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Inverted on Axioms)** | Claims to operationalize Schurz's axiomatic non-factorizability criterion ($E(Ax) \neq \operatorname{Cn}(E(Ax_1) \cup E(Ax_2)) \cap L_E$) to detect the Tacking Paradox. However, $AID(A_1, A_2)$ counts **direct inference edges $(u, v) \in E_{\text{inf}}$ between $A_1$ and $A_2$**. Because irreducible natural axioms $Ax(T)$ do not derive *one another* (they **jointly derive** shared empirical consequences $a_1 \to e \leftarrow a_2$), there are zero direct edges between $A_1$ and $A_2$, causing every valid non-redundant axiomatic system to score $H_{\text{axiomatic}}(T) = 0$ ("Tacked-On Conjunction"). |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) $\min_{A_1 \cup A_2 = V_{Ax}} AID(A_1, A_2)$ omits $A_1 \neq \emptyset$, $A_2 \neq \emptyset$, and $A_1 \cap A_2 = \emptyset$, causing **division by zero** ($0/0$) at $A_1 = \emptyset$ and $\min \emptyset = +\infty$ when $\|V_{Ax}\| = 1$; (2) $E(Ax) = \operatorname{Cn}(E(Ax_1) \cup E(Ax_2))$ omits $\cap L_E$; (3) $AID$ scales as $O(1/\|V_{Ax}\|)$ on sparse connected graphs and requires $O(2^{\|V_{Ax}\|})$ NP-hard minimization. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts across three non-equivalent graph structures: (a) **joint empirical derivation** $E(Ax)$ (L28–31), (b) **direct inference edges** $(u, v) \in E_{\text{inf}}$ between axiom subsets (L46), and (c) **shared intermediate state variables/vocabulary** (L60–61). |
| **4. Valid & Scientifically Significant?** | **Yes (With Co-Derivation Graph)** | Preventing the Tacking Paradox via Schurz's factorization criterion (Schurz 1991; 2014, p. 73; Gemes 1993) is scientifically fundamental, but requires evaluating the **co-derivation hypergraph** over $Ax(T)$ rather than direct axiom-to-axiom edges. |

---

## 1. Does the Metric Capture What It Claims It Does?

### SH-01 · $AID(A_1, A_2)$ Checks for Direct Edges Between Axioms Instead of Joint Empirical Derivations, Scoring $0$ on Every Irreducible Axiom System — **Critical**

**Where.** [`semantic_homogeneity.md#L28-L31`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L28-L31) vs. [`#L39-L53`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L39-L53).

**Finding.**
In §Theoretical Grounding (L28–31), Schurz's Factorization Criterion is stated over the natural axiomatization $Ax$:
> An axiomatization $Ax$ is axiomatically homogeneous iff there exist no non-empty disjoint $Ax_1, Ax_2 \subset Ax$ such that $E(Ax) = \operatorname{Cn}(E(Ax_1) \cup E(Ax_2))$.

In §Mathematical Specification (L39–50), the graph formulation defines:
$$AID(A_1, A_2) = \frac{|\{(u, v) \in E_{\text{inf}} \mid (u \in A_1 \land v \in A_2) \lor (u \in A_2 \land v \in A_1)\}|}{|A_1| \cdot |A_2|}$$
$$H_{\text{axiomatic}}(T) = \min_{A_1 \cup A_2 = V_{Ax}} AID(A_1, A_2).$$

**Why this fails on both interpretations of $V_{Ax}$.**
1. **Interpretation 1 ($V_{Ax} = Ax(T)$, the set of axioms, as stated on L44 & L60):**
   By definition of a **natural axiomatization** $Ax(T)$ (`epistemology.md` L140; Schurz 2014, p. 73), the axioms in $Ax(T)$ are logically independent and non-redundant ($a_i \nvdash a_j$ for $i \neq j$). Therefore, **no axiom has a direct inference edge $(a_i, a_j) \in E_{\text{inf}}$ to another axiom**!
   Instead, axioms $a_1 \in A_1$ and $a_2 \in A_2$ interact by **jointly deriving** a common theorem or empirical prediction $c \in D$ (forming a V-structure / cospan $a_1 \to c \leftarrow a_2$ in the inference DAG, e.g. Newton's second law $\vec{F} = m\vec{a}$ and the law of gravitation $F_G = G m_1 m_2 / r^2$ jointly deriving Kepler's third law $c$).
   Because $(a_1, a_2) \notin E_{\text{inf}}$, the numerator of $AID(A_1, A_2)$ is **identically $0$** for every bipartition of $Ax(T)$, so **every irreducible axiomatic theory in science gets $H_{\text{axiomatic}}(T) = 0$ ("Tacked-On Conjunction")**!
2. **Interpretation 2 ($V_{Ax} = V(G_T)$, all axioms, premises, and derived theorems, as L39 suggests):**
   - Suppose $T = T_1 \land T_2$ is a genuinely heterogeneous tacked theory as defined by Schurz: $E(Ax) = \operatorname{Cn}(E(Ax_1) \cup E(Ax_2)) \cap L_E$ (its *empirical* consequences completely factorize), **but** $Ax_1$ and $Ax_2$ both entail a purely metaphysical or tautological statement $m \notin L_E$. Then $G_T$ is connected ($H_{\text{axiomatic}} > 0$), so $H_{\text{axiomatic}}$ fails to detect that the **empirical** content $E(Ax)$ is factorizable!
   - Conversely, on a binary graph $G_T = (V, E_{\text{inf}})$ without conjunctive hyperedges (`ISSUE-055`, `ISSUE-068` C-05), if $a_1 \vdash e$ independently and $a_2 \vdash e$ independently (redundant overdetermination of the same fact $e$, so $E(Ax_1 \cup Ax_2) = E(Ax_1) \cup E(Ax_2)$!), both $(a_1, e) \in E_{\text{inf}}$ and $(a_2, e) \in E_{\text{inf}}$ exist. Thus $G_T$ is connected and scores $H_{\text{axiomatic}} > 0$ even though $E(Ax) = \operatorname{Cn}(E(Ax_1) \cup E(Ax_2)) \cap L_E$ is **strictly factorizable**!

**Fix.**
Construct the **Axiom Co-Derivation Graph** $\mathcal{G}_{\text{co}} = (Ax(T), E_{\text{co}}, w_{\text{co}})$, where an undirected edge $\{a_i, a_j\} \in E_{\text{co}}$ exists between two axioms $a_i, a_j \in Ax(T)$ iff $a_i$ and $a_j$ **jointly participate in at least one minimal conjunctive derivation** of a relevant empirical consequence $e \in E_e(Ax)$ (i.e. $S \vdash e$ with $a_i, a_j \in S \subseteq Ax(T)$ and $S \setminus \{a_i\} \nvdash e$, $S \setminus \{a_j\} \nvdash e$):
$$w_{\text{co}}(a_i, a_j) = \big|\{e \in E_e(Ax) \mid \exists \text{ minimal } S \subseteq Ax(T) : \{a_i, a_j\} \subseteq S \land S \vdash e\}\big|.$$
Then evaluate $AID(A_1, A_2)$ (or the algebraic connectivity / Cheeger conductance) on $\mathcal{G}_{\text{co}}$, not on direct edges between axioms in $E_{\text{inf}}$.

---

## 2. Is the Metric Formally & Mathematically Correct?

### SH-02 · Ill-Defined Minimization Domain $\min_{A_1 \cup A_2 = V_{Ax}} AID(A_1, A_2)$ Causes Division by Zero and Single-Axiom Failure — **Critical**

**Where.** [`semantic_homogeneity.md#L44-L53`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L44-L53).

**Finding.**
On L50, the Homogeneity Factor is written as:
$$H_{\text{axiomatic}}(T) = \min_{A_1 \cup A_2 = V_{Ax}} AID(A_1, A_2)$$
where $AID(A_1, A_2)$ divides by $|A_1| \cdot |A_2|$.
1. **Missing Non-Emptiness ($A_1 \neq \emptyset, A_2 \neq \emptyset$):** The constraint $A_1 \cup A_2 = V_{Ax}$ is satisfied by $A_1 = \emptyset, A_2 = V_{Ax}$, for which the denominator $|A_1| \cdot |A_2| = 0 \cdot |V_{Ax}| = 0$, causing **division by zero ($0/0$)**!
2. **Missing Disjointness ($A_1 \cap A_2 = \emptyset$):** L29 requires $Ax_1 \cap Ax_2 = \emptyset$, but L44 and L50 omit $A_1 \cap A_2 = \emptyset$.
3. **Undefined for Single-Axiom Theories ($|V_{Ax}| = 1$):** If a theory consists of a single irreducible law ($|V_{Ax}| = 1$), there is **no** partition into two non-empty disjoint subsets $A_1, A_2$. Taking the minimum over an empty index set yields $\min \emptyset = +\infty$ (or `ValueError` in Python), whereas a 1-axiom theory is trivially non-factorizable ($H_{\text{axiomatic}} = 1.0$).

**Fix.**
Write the minimization domain explicitly and guard $|Ax(T)| \le 1$:
$$H_{\text{axiomatic}}(T) = \begin{cases} 1.0 & \text{if } |Ax(T)| = 1 \\[4pt] \displaystyle\min_{\substack{A_1 \uplus A_2 = Ax(T) \\ A_1 \neq \emptyset, \, A_2 \neq \emptyset}} AID_{\text{co}}(A_1, A_2) & \text{if } |Ax(T)| \ge 2 \\[12pt] 0.0 & \text{if } |Ax(T)| = 0. \end{cases}$$

---

### SH-03 · Size-Scaling Bias ($O(1/|Ax|)$ Decay) and NP-Hard $O(2^{|Ax|})$ Complexity of Uniform Cut Density — **Major**

**Where.** [`semantic_homogeneity.md#L46-L50`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L46-L50).

**Finding.**
1. **Hyperbolic Decay with Theory Size:** Because $AID(A_1, A_2)$ divides by $|A_1| \cdot |A_2|$, consider a connected chain or tree of $n = |Ax(T)|$ axioms where each adjacent pair jointly derives an empirical law. Choosing $A_1 = \{a_1\}$ (a leaf axiom of degree $1$) and $A_2 = Ax(T) \setminus \{a_1\}$ gives:
   $$AID(A_1, A_2) = \frac{1}{1 \cdot (n - 1)} = \frac{1}{n - 1} \xrightarrow{n \to \infty} 0.$$
   Thus, a 2-axiom theory gets $H_{\text{axiomatic}} = 1.0$, whereas a deeply unified 51-axiom theory gets $H_{\text{axiomatic}} = 0.02$, penalizing comprehensive theories simply for having more than 2 axioms!
2. **NP-Hardness of Sparsest Cut:** Minimizing $\frac{|E(A_1, A_2)|}{|A_1| \cdot |A_2|}$ over all $2^{n-1} - 1$ non-trivial bipartitions is the **Sparsest Cut problem**, which is NP-hard! Yet the Diagnostic Table (L68–71) only ever branches on whether $H_{\text{axiomatic}} > 0$ vs. $H_{\text{axiomatic}} = 0$, which is simply graph connectedness (solvable in $O(|V| + |E|)$ via BFS/WCC!).

**Fix.**
1. To test $H_{\text{axiomatic}} = 0$ vs. $> 0$, check whether the co-derivation graph $\mathcal{G}_{\text{co}}$ has a single connected component ($\text{WCC}(\mathcal{G}_{\text{co}}) = 1$) in $O(|Ax| + |E_{\text{co}}|)$ time.
2. For a continuous score in $[0, 1]$ that does not decay as $1/(n-1)$ or require $O(2^n)$ enumeration, use either the **Cheeger / Conductance bound** via the normalized Laplacian Fiedler value $\frac{1}{2}\lambda_2(\mathcal{L}_{\text{norm}}(\mathcal{G}_{\text{co}})) \in [0, 1]$ (aligning with `connectedness.md`) or the **Stoer–Wagner global minimum cut** normalized by minimum degree ($O(|V||E| + |V|^2 \log |V|)$).

---

### SH-04 · Missing Empirical Language Restriction ($\cap L_E$) in Schurz's Factorization Formula — **Major**

**Where.** [`semantic_homogeneity.md#L23-L31`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L23-L31) (cf. [`ISSUE-067` B-01, B-02](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md#b-02--the-homogeneity-non-factorizability-definition-is-degenerate--critical)).

**Finding.**
On L23, $E(Ax)$ is defined as *"the relevant deductive consequences of $Ax$"*, and on L31 the factorization criterion is written as:
$$E(Ax) = \operatorname{Cn}\big(E(Ax_1) \cup E(Ax_2)\big).$$
As shown in `ISSUE-067` (B-01 / B-02):
1. In Schurz (2014, p. 73), $E(Ax)$ is the set of **empirical** (or relevant empirical) consequences $\operatorname{Cn}_e(Ax) \cap L_E$.
2. Applying the unrestricted classical consequence operator $\operatorname{Cn}(\cdot)$ on the right-hand side generates arbitrary irrelevant disjunctions (e.g. $e_1 \lor t$ for $t \in L_T$) that are not in the relevant consequence set $E(Ax)$, so the left-hand side (relevant consequences) and right-hand side (all classical consequences) have different closure types!

**Fix.**
Write the criterion explicitly over the empirical sub-language $L_E$ (or relevant consequence elements $E_e$):
$$E(Ax) = \operatorname{Cn}\big(E(Ax_1) \cup E(Ax_2)\big) \cap L_E \qquad (\text{or } E_e(Ax) = E_e(Ax_1) \cup E_e(Ax_2)).$$

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### SH-05 · Triple Semantic Shift Between Joint Empirical Consequences, Direct Axiom Edges, and Shared Theoretical Vocabulary — **Major**

**Where.** [`semantic_homogeneity.md#L28-L31`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L28-L31) $\to$ [`#L44-L46`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L44-L46) $\to$ [`#L60-L61`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L60-L61).

**Finding.**
The document conflates three mathematically distinct properties under the single name "Semantic & Axiomatic Homogeneity":
1. **Deductive Empirical Non-Factorizability (L28–31):** $Ax$ cannot be split into $Ax_1 \uplus Ax_2$ without losing joint empirical consequences in $E(Ax)$.
2. **Direct Inference Graph Connectivity (L44–46):** Existence of direct edges $(u, v) \in E_{\text{inf}}$ between $A_1$ and $A_2$.
3. **Vocabulary / Variable Sharing (L60–61):** *"Validate whether theorems derived by axiom set $A_1$ share intermediate theoretical state variables with derivations from $A_2$."*

Sharing a theoretical variable or concept node in $L_T$ (**semantic/vocabulary overlap**) is a necessary precondition for joint deduction, but is **not sufficient** to prevent the Tacking Paradox! For example, conjoining $a_1 =$ *"Electrons have spin $\frac{1}{2}$"* with $a_2 =$ *"Electrons were named by G. J. Stoney in 1891"* shares the concept node `Electron`, yet $a_1$ and $a_2$ yield **zero joint empirical derivations** ($E(\{a_1, a_2\}) = \operatorname{Cn}(E(\{a_1\}) \cup E(\{a_2\})) \cap L_E$).

**Fix.**
Distinguish the two levels explicitly:
- **Level 1 — Vocabulary / Semantic Homogeneity ($H_{\text{vocab}}$):** Bipartite concept-sharing connectivity between axioms over $L_T$ terms (necessary condition).
- **Level 2 — Axiomatic / Deductive Homogeneity ($H_{\text{axiomatic}}$):** Connectivity of the co-derivation graph $\mathcal{G}_{\text{co}}$ where edges require joint participation in deriving an empirical consequence $e \in E_e(Ax)$ (sufficient condition resolving the Tacking Paradox).

---

## 4. Is the Metric Valid and Scientifically Significant?

### SH-06 · Undocumented Overlap with Pillar 1 `connectedness.md` — **Minor**

**Where.** [`semantic_homogeneity.md#L48-L63`](../../../docs/concepts/theory/metrics/metatheoretical/semantic_homogeneity.md#L48-L63) vs. [`docs/concepts/theory/metrics/structural_topology/connectedness.md`](../../../docs/concepts/theory/metrics/structural_topology/connectedness.md) and [`docs/concepts/theory/metrics/index.md#L159-L170`](../../../docs/concepts/theory/metrics/index.md#L159-L170).

**Finding.**
Both `connectedness.md` (Pillar 1) and `semantic_homogeneity.md` (Pillar 5) test whether a theory graph decomposes into disconnected components ($\text{WCC} > 1$ / $\lambda_2 = 0$), and both recommend alerting or splitting the `:Theory` container when disconnected components are found. Yet `docs/concepts/theory/metrics/index.md` (§Comprehensive Overlap & Redundancy Map) omits this pair entirely.

**Fix.**
Register the relationship in `docs/concepts/theory/metrics/index.md`: `connectedness.md` evaluates macro-topological connectivity on the specialization/argumentation graph, whereas `semantic_homogeneity.md` evaluates non-factorizability on the **axiom co-derivation projection** $\mathcal{G}_{\text{co}}$.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Unregistered Node Label `:Theory` (L58, L63):** Uses `:Theory` container nodes, whereas `epistemetrics/core/models.py` uses `NodeType.THEORY_ELEMENT`.
2. **Broken Local Zotero Link (L13):** Uses `zotero://select/library/items/24SNSW2B`.
