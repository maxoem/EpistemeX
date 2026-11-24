# [ISSUE-073] Formal & Conceptual Evaluation: Explanatory Breadth (`explanatory_breadth.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-073` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 3: Empirical Power |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **High** (contains topological circularity in Leiden-based $REB_{\text{CLUSTER}}$, unbounded $\theta_{\text{effective}} > 1$ breaking ECHO dynamics, and missing edge-orientation/tacking guards) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-075`](../ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-009`](../../03-epistemic-metrics/ISSUE-009-global-qbaf-solvers-and-thagardian-harmony.md), [`ISSUE-066`](../../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **Partially (Vulnerable to Gaming)** | $REB_{\text{NODE}}$ accurately captures the proportion of domain evidence nodes covered by $T$. However, $REB_{\text{CLUSTER}}$ is vulnerable to both **single-node cluster gaming** (explaining 1 node in each cluster gives $1.0$) and **topological circularity** (if Leiden is run on the full graph including $T$'s own support edges, $T$ creates the very clusters it is evaluated against). Furthermore, without an axiomatic normalization or homogeneity check, $REB$ is vulnerable to the Tacking Paradox. |
| **2. Formally & Mathematically Correct?** | **Mostly, except $\theta_{\text{effective}}$** | Set-theoretic formulas for $Cons(H)$, $REB_{\text{NODE}}$, $UER$, $ECR$, and $REB_{\text{net}}$ are well-typed (assuming $V_E \neq \emptyset$). However, the **Dynamic Skepticism Penalty** $\theta_{\text{effective}} = \theta_{\text{base}}(1 + \gamma_{\text{unexp}} UER + \gamma_{\text{att}} ECR)$ is **not bounded in $(0, 1)$** and can exceed $1.0$, which breaks the LPG-ECHO decay equation $a_j(t) = a_j(0)(1-\theta)^t$ and causes sign-flipping oscillation or $\ln(1-\theta)$ domain errors. |
| **3. Free of Semantic Shifts?** | **Contains 3 Notable Shifts** | (1) Shifts between **Out-Set** (heading L44) and **In-Degree** (`index.md` L94 & L46) due to inverted edge direction $E \to H$ vs. `H -[:EXPLAINS]-> E`; (2) shifts from static graph metric to a dynamic solver parameter ($\theta_{\text{effective}}$) inside LPG-ECHO; (3) shifts from Whewellian *topical/domain* diversity to *topological* Leiden communities. |
| **4. Valid & Scientifically Significant?** | **Yes (Core Metric)** | Consilience (Whewell 1840; Thagard 1978, 1989; Schurz 2014) is a foundational criterion of scientific theory evaluation. Once the cluster partitioning and $\theta_{\text{effective}}$ bounding are fixed, this is one of the cleanest, most directly computable metrics in `epistemetrics`. |

---

## 1. Does the Metric Capture What It Claims It Does?

### EB-01 · Topological Circularity and Single-Node Gaming in $REB_{\text{CLUSTER}}$ — **Critical**

**Where.** [`explanatory_breadth.md#L57-L69`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L57-L69).

**Finding.**
To capture Whewellian qualitative consilience across distinct empirical fields, $REB_{\text{CLUSTER}}(T)$ partitions $V_E$ into communities $\mathcal{C} = \{C_1, \dots, C_k\}$ via a clustering algorithm (Leiden modularity optimization) and computes:
$$REB_{\text{CLUSTER}}(T) = \frac{|\{ C_i \in \mathcal{C} \mid C_i \cap V_E^{\text{exp}}(T) \neq \emptyset \}|}{|\mathcal{C}|}$$

This formulation has three structural vulnerabilities:
1. **Topological Circularity (Endogenous Partitioning):** In a bipartite or layered theory graph, evidence nodes $E \in V_E$ are primarily connected *through* the hypotheses $H \in V_H$ that explain them. If Leiden modularity optimization is run on the graph $G$ containing $R_{\text{sup}}$, then all evidence nodes explained by $T$ will be grouped into **the same topological community** because they share common neighbors in $V_H(T)$! Consequently, a broadly unifying theory $T$ that connects previously disparate evidence will **merge** their topological communities, paradoxically *reducing* the number of communities it spans! Conversely, if $V_E$ has no direct $V_E \times V_E$ edges, topological clustering on $V_E$ alone produces $|\mathcal{C}| = |V_E|$ singleton clusters, making $REB_{\text{CLUSTER}}(T) \equiv REB_{\text{NODE}}(T)$.
2. **Existential Threshold Gaming ($C_i \cap V_E^{\text{exp}}(T) \neq \emptyset$):** Requiring only *at least one* explained node per cluster ($|C_i \cap V_E^{\text{exp}}(T)| \ge 1$) means that if there are 5 clusters of 100 evidence nodes each ($|V_E| = 500$), a theory that explains just **5 nodes** (1 per cluster, i.e. $1\%$ of the data) achieves a **perfect** $REB_{\text{CLUSTER}}(T) = 1.0$! Even the suggested geometric mean $\sqrt{REB_{\text{NODE}} \cdot REB_{\text{CLUSTER}}} = \sqrt{0.01 \times 1.0} = 0.10$ inflates its score $10\times$.
3. **Granularity Sensitivity to Leiden Resolution $\gamma$:** Changing the Leiden resolution parameter $\gamma$ arbitrarily changes $|\mathcal{C}|$ and thus $REB_{\text{CLUSTER}}(T)$.

**Fix.**
1. **Exogenous / Theory-Independent Partitioning of $V_E$:** Specify that $\mathcal{C}$ must be computed **independently of $R_{\text{sup}}$ and $V_H$**—specifically, by clustering $V_E$ using L1/L2 semantic embeddings, document/discipline metadata, or the L2 entity-co-occurrence projection graph.
2. **Entropy-Based or Coverage-Weighted Cluster Consilience:** Instead of a binary indicator $\mathbb{I}(C_i \cap V_E^{\text{exp}}(T) \neq \emptyset)$, compute either:
   - the **macro-averaged cluster coverage**:
     $$REB_{\text{CLUSTER}}(T) = \frac{1}{|\mathcal{C}|} \sum_{i=1}^{k} \frac{|C_i \cap V_E^{\text{exp}}(T)|}{|C_i|},$$
   - or the **normalized Shannon entropy / Simpson diversity** (or Guimerà–Amaral participation coefficient) of $V_E^{\text{exp}}(T)$ across clusters $\mathcal{C}$, multiplied by $REB_{\text{NODE}}(T)$.

---

### EB-02 · Vulnerability to the Tacking Paradox Without Homogeneity / Unification Pairing — **Major**

**Where.** [`explanatory_breadth.md#L52-L55`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L52-L55).

**Finding.**
Because $REB_{\text{NODE}}(T)$ takes the union $\bigcup_{H \in V_H(T)} \{E \in V_E \mid (E, H) \in R_{\text{sup}}\}$ over all hypotheses in $V_H(T)$ without penalizing $|V_H(T)|$ or checking axiomatic connectedness:
- Conjoining two unrelated theories $T_1 \cup T_2$ (or adding 100 ad-hoc single-fact hypotheses $H_1, \dots, H_{100}$) monotonically increases $REB_{\text{NODE}}$ and $REB_{\text{CLUSTER}}$ while reducing $UER$ to $0$.
- While `docs/concepts/theory/metrics/index.md` (L137) notes this distinction when discussing Unification, `explanatory_breadth.md` itself cites Schurz (2024, sec. 3.12, 5.3 & 6.4) on "tacking paradoxes" (L126–127) without including any relevance or homogeneity constraint in the mathematical specification.

**Fix.**
Require that $V_H(T)$ is restricted to a single connected/homogeneous theory component (`Semantic & Axiomatic Homogeneity` $> 0$), or explicitly state in `explanatory_breadth.md` that $REB(T)$ must be evaluated jointly with `Unification` ($U_{\text{ratio}} = |V_E^{\text{exp}}(T)| / |B(T)|$) to prevent tacking inflation.

---

### EB-03 · Ambiguous Scope of the Denominator $|V_E|$ — **Major**

**Where.** [`explanatory_breadth.md#L30`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L30), [`#L55`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L55), [`#L77-L82`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L77-L82).

**Finding.**
L30 defines $V_E$ as *"the set of established evidence nodes within the empirical domain scope"*.
In a multi-theory property graph (e.g., containing both biological and astronomical literature, or ethics and epistemology), what defines the "empirical domain scope" of $T$?
- If $V_E$ is the **global** set of all evidence nodes in the database/run, then a specialized theory (e.g., Hooke's law of elasticity) will have $REB_{\text{NODE}} \to 0$ and $UER \to 1.0$, and will be falsely penalized as *"Isolated / Cherry-Picking"* (L114) simply because the corpus also contains unrelated documents!
- Conversely, if $V_E$ is defined as only the evidence nodes **connected to $T$**, then $V_E = V_E^{\text{exp}}(T) \cup V_E^{\text{att}}(T)$, so any theory without active refutations automatically gets $REB_{\text{NODE}}(T) = 1.0$ and $UER(T) = 0.0$, rendering $UER$ trivial!

**Fix.**
Formally define the **Scoped Empirical Domain $V_E(D_T)$** of a theory $T$: e.g., the union of evidence nodes belonging to the same Leiden meso-community / topical domain $D_T$ (or linked to the same intended application classes $I$ across rival theories $T_1, \dots, T_m$ competing in that domain).

---

## 2. Is the Metric Formally & Mathematically Correct?

### EB-04 · Dynamic Skepticism Penalty $\theta_{\text{effective}}$ Can Exceed $1.0$, Breaking LPG-ECHO — **Critical**

**Where.** [`explanatory_breadth.md#L91-L103`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L91-L103) vs. [`adapted_echo_algorithm.md#L44-L56`](../../../docs/concepts/theory/metrics/adapted_echo_algorithm.md#L44-L56).

**Finding.**
In [`adapted_echo_algorithm.md`](../../../docs/concepts/theory/metrics/adapted_echo_algorithm.md#L44), the decay parameter $\theta$ must strictly lie in $(0, 1)$, governing exponential decay:
$$a_j(t) = a_j(0) \cdot (1 - \theta)^t, \qquad t_{1/2} = \frac{\ln(0.5)}{\ln(1 - \theta)}.$$
In `explanatory_breadth.md` (L96), $\theta_{\text{effective}}$ is defined as:
$$\theta_{\text{effective}} = \theta_{\text{base}} \cdot \left(1 + \gamma_{\text{unexp}} \cdot UER(T) + \gamma_{\text{att}} \cdot ECR(T)\right)$$
with defaults $\gamma_{\text{unexp}} = 1.0$ and $\gamma_{\text{att}} = 3.0$ (and $\gamma_{\text{att}} \gg \gamma_{\text{unexp}}$).
With $UER(T) \in [0, 1]$ and $ECR(T) \in [0, 1]$, the multiplier $(1 + \gamma_{\text{unexp}} UER + \gamma_{\text{att}} ECR)$ reaches **$5.0$** under default weights (and even higher since $\gamma_{\text{att}} \gg \gamma_{\text{unexp}}$ is unconstrained).
If $\theta_{\text{base}} = 0.20$ (or if $\gamma_{\text{att}}$ is set to $20$ at $\theta_{\text{base}} = 0.05$), then **$\theta_{\text{effective}} \ge 1.0$**:
- At $\theta_{\text{effective}} = 1.0$, $\ln(1 - \theta_{\text{effective}})$ is **undefined ($\ln 0 = -\infty$)**;
- At $\theta_{\text{effective}} > 1.0$, $(1 - \theta_{\text{effective}})^t$ **alternates signs every iteration**, causing catastrophic numerical oscillation in LPG-ECHO and undefined complex logarithms in $t_{1/2}$!

Furthermore, in LPG-ECHO, $\theta$ is a **node/system parameter** applied per relaxation step, whereas $UER(T)$ and $ECR(T)$ are **macro theory-level** scores. Worse, active refutations ($ECR$) are **already** modeled in LPG-ECHO as inhibitory edges ($w_{ij} < 0$) from evidence nodes to hypothesis nodes—penalizing $\theta_{\text{effective}}$ by $ECR(T)$ **double-counts** active refutations!

**Fix.**
1. Bound $\theta_{\text{effective}}$ strictly within $(0, 1)$, e.g. via a saturating map:
   $$\theta_{\text{effective}}(T) = 1 - (1 - \theta_{\text{base}})^{1 + \gamma_{\text{unexp}} UER(T) + \gamma_{\text{att}} ECR(T)} \in (\theta_{\text{base}}, 1).$$
2. Clarify whether $\gamma_{\text{att}}$ should be set to $0$ when running LPG-ECHO with explicit inhibitory attack edges $R_{\text{att}}$ to avoid double-counting refutations.

---

### EB-05 · Undefined Edge Cases ($|V_E| = 0$) and Unbounded $REB_{\text{net}} \in [-\alpha, 1]$ — **Minor**

**Where.** [`explanatory_breadth.md#L55`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L55), [`#L66`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L66), [`#L87`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L87).

**Finding.**
1. If $|V_E| = 0$ (e.g., a purely formal or normative philosophical text before empirical evidence extraction), $REB_{\text{NODE}}$, $REB_{\text{CLUSTER}}$, $UER$, and $ECR$ all divide by zero.
2. Note that an evidence node $E \in V_E$ can simultaneously support one hypothesis $H_1 \in V_H(T)$ and attack another hypothesis $H_2 \in V_H(T)$ within the same theory $T$. Thus $V_E^{\text{exp}}(T)$ and $V_E^{\text{att}}(T)$ are **not necessarily disjoint**, and $REB_{\text{NODE}}(T) + ECR(T)$ can exceed $1.0$.
3. $REB_{\text{net}}(T) = REB_{\text{NODE}}(T) - \alpha \cdot ECR(T)$ lies in $[-\alpha, 1.0]$, whereas the diagnostic table on L110–114 only lists positive thresholds for "$REB(T)$ Score" without specifying whether the table refers to $REB_{\text{NODE}}$, $REB_{\text{CLUSTER}}$, or $REB_{\text{net}}$.

**Fix.**
Define $REB_{\text{NODE}}(T) := 0, UER(T) := 1, ECR(T) := 0$ when $V_E = \emptyset$, and specify explicitly which $REB$ variant ($REB_{\text{NODE}}$ vs. $REB_{\text{net}}$) drives the diagnostic table on L110.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### EB-06 · Edge Orientation Shift: "Out-Set" vs. Incoming Support Edges ($E \to H$ vs. $H \to E$) — **Major**

**Where.** [`explanatory_breadth.md#L31-L34`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L31-L34), [`#L44-L48`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L44-L48) vs. [`index.md#L94`](../../../docs/concepts/theory/metrics/index.md#L94) vs. `epistemetrics/core/models.py`.

**Finding.**
- On L44, the heading calls $Cons(H)$ the **"Consilience Out-Set $Cons$**"**, while L46 immediately says *"consilience is defined set-theoretically over **incoming** support edges: $Cons(H) = |\{E \in V_E \mid (E, H) \in R_{\text{sup}}\}|$"* (which is an **in-degree**, not an out-set!).
- Meanwhile, in `epistemetrics` (`RelationType.EXPLAINS`, `RelationType.PREDICTS`), explanatory edges are directed from the hypothesis to the evidence: **`H -[:EXPLAINS]-> E`** (so $E$ is in the **out-set** of $H$), whereas argumentative support edges (`RelationType.SUPPORTS`, `RelationType.EVIDENCED_BY`) are directed **`E -[:SUPPORTS]-> H`** or **`H -[:EVIDENCED_BY]-> E`**!
- If an implementation queries incoming edges $(E, H)$ for `:EXPLAINS`, or outgoing edges $(H, E)$ for `:SUPPORTS`, $Cons(H)$ and $REB(T)$ will evaluate to **$0.0$ across the entire graph**.

**Fix.**
Rename L44 to *"Consilience Support Set $Cons(H)$"* and define the explanatory coverage relation canonically across both edge conventions:
$$(E, H) \in R_{\text{sup}} \iff (E \xrightarrow{\text{SUPPORTS}} H) \lor (H \xrightarrow{\text{EXPLAINS} \mid \text{PREDICTS} \mid \text{EVIDENCED\_BY}} E).$$

---

## 4. Is the Metric Valid and Scientifically Significant?

### EB-07 · Empty Implementation Section (`## Measurement & Graph Implementation`) — **Major**

**Where.** [`explanatory_breadth.md#L104-L106`](../../../docs/concepts/theory/metrics/empirical_power/explanatory_breadth.md#L104-L106).

**Finding.**
Line 104 contains the heading `## Measurement & Graph Implementation` followed immediately by `---` with **zero content**. Unlike `empirical_adequacy.md` and `theoretical_achievements.md`, the algorithm and Cypher/NetworkX implementation steps were left blank.

**Fix.**
Populate `## Measurement & Graph Implementation` with the concrete graph traversal steps:
1. Domain scope resolution for $V_E(D_T)$.
2. Computation of $V_E^{\text{exp}}(T)$ and $V_E^{\text{att}}(T)$ across `SUPPORTS`, `EXPLAINS`, `PREDICTS`, and `ATTACKS`/`CONTRADICTS`/`REFUTES` edges.
3. Exogenous community detection on $V_E$ for $REB_{\text{CLUSTER}}(T)$.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Corrupted LaTeX Delimiters Throughout the File (L27–38, L50–69, L89–103):**
   Almost every inline math expression has mismatched or stray parentheses inside/outside `$`:
   - L27: `Let $(G = (V_H \cup V_E, R_{\text{sup}} \cup \mathcal{R}_{\text{att}}))$`
   - L31–34: `$E \to H)$ indicating evidence $(E)$ supports or is explained by $(H$.`
   - L61: `Let $(\mathcal{C} = \{C_1, C_2, \dots, C_k\})$`
   - L89: `where $(\alpha \ge 1.0)$`
   - L93–94: `$(\theta_\n{\text{effective}})$` (broken across newline!)
   - L101–102: `(default = $(1.0$.` and `(default = $(3.0$.`
   This appears to be a regex conversion artifact from `\(...\)` to `$(...)$` where `\(` was replaced by `$(` and `\)` by `)$` (or partially stripped).
2. **Font Mismatch for Support vs. Attack Relations (L27, L31, L34):** Uses plain $R_{\text{sup}}$ alongside calligraphic $\mathcal{R}_{\text{att}}$. Use either $R_{\text{sup}}, R_{\text{att}}$ or $\mathcal{R}_{\text{sup}}, \mathcal{R}_{\text{att}}$ consistently.
3. **Diagnostic Table Partition Gap (L110–114):** The table covers $REB > 0.6$, $0.2 \le REB \le 0.6$, and $REB < 0.1$, leaving the interval **$0.1 \le REB < 0.2$** ($0.8 < UER \le 0.9$) completely undefined!
