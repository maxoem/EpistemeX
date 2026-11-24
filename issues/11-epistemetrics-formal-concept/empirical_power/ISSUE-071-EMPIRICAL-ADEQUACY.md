# [ISSUE-071] Formal & Conceptual Evaluation: Empirical Adequacy & Grounding (`empirical_adequacy.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-071` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 3: Empirical Power |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (contains unbound variables, symmetric vs. asymmetric Hausdorff collapse, and complete overlap with Tenability) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-075`](../ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-025`](../../03-epistemic-metrics/ISSUE-025-model-theoretic-plausibility-score.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **Partially / No** | Claims to measure structuralist approximative empirical adequacy ($I \approx_{\mathcal{A}} X$) and true partial empirical claims ($I_0 \in \operatorname{Cn}(K)$). In execution, $GR(T)$ collapses to a provenance/dataset-coverage ratio, and $AS$/$BMCR$ drop the reverse Hausdorff clause—allowing theories that posit arbitrary uninstantiated models to achieve a perfect score. |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) $X$ is an **unbound (free) variable** in $BMCR(I, K)$; (2) $\mathcal{A}$ is simultaneously treated as a family of relations and a single relation; (3) $I_0 \in \operatorname{Cn}(K)$ vs. $I_{\text{confirmed}} \subseteq \operatorname{Cn}(K)$ commits a set-level type error; (4) Cypher query `count(DISTINCT d) / count(DISTINCT i)` is not bounded in $[0, 1]$ and does not compute $GR(T)$. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts across three incompatible meanings of $d(i, x)$ and $I$: (a) continuous metric residuals in $M_{pp} \times M_{pp}$, (b) LLM semantic plausibility $1 - p(i, x)$ between an observation and a law statement, and (c) binary database existence of a `:Dataset` node (`:EVIDENCED_BY`). |
| **4. Valid & Scientifically Significant?** | **Redundant as Stated** | The model-theoretic approximation concept is scientifically significant (BMS 1987), but **already formalized more rigorously in [`tenability.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md)** (ADR 0015). Having two nearly identical uniform-space blur metrics with inverted framing creates an architectural split-brain. |

---

## 1. Does the Metric Capture What It Claims It Does?

### EA-01 · Loss of the Reverse Hausdorff Clause in $AS$ and $BMCR$ — **Critical**

**Where.** [`empirical_adequacy.md#L28-L30`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L28-L30) vs. [`#L55-L61`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L55-L61).

**Finding.**
In §Theoretical Grounding (L30), the document correctly defines the induced Hausdorff-style blur equivalence $I \approx_{\mathcal{A}} X$ over subsets of $M_{pp}$ using **both** directions:
1. **Forward (Empirical Coverage):** $\forall i \in I \, \exists x \in X \, ((i, x) \in u)$ — every intended application is approximated by some model in the constrained model set $X$.
2. **Backward (Model Instantiation / Soundness):** $\forall x \in X \, \exists i \in I \, ((i, x) \in u)$ — every model in $X$ corresponds to some intended application in $I$.

However, both the **Adequacy Score ($AS$)** (L55):
$$\text{Adequacy}(I, K) = \max_{X \in \operatorname{Cn}(K)} \left[ 1 - \frac{1}{|I|} \sum_{i \in I} \min_{x \in X} d(i, x) \right]$$
and the **Blur Margin Compliance Ratio ($BMCR$)** (L61) evaluate **only the forward direction** ($\forall i \in I \min_{x \in X} d(i, x)$).

**Why this breaks the metric.**
In structuralism, $\operatorname{Cn}(K) = \bar{r}(\mathcal{P}(M) \cap GC \cap GL)$ is closed under enlargement as long as constraints $GC$ are not violated. If a theory is completely unconstrained ($GC = \mathcal{P}(M_p)$) or permissive ($M = M_p$), then $X = M_{pp} \in \operatorname{Cn}(K)$. Choosing $X = M_{pp}$ gives $\min_{x \in X} d(i, x) = d(i, i) = 0$ for all $i \in I$, yielding $\text{Adequacy}(I, K) = 1.0$ and $BMCR = 1.0$ for a **completely vacuous theory** that predicts every logically possible state! Even when $X$ is chosen as a massive superset containing wild, unobserved theoretical models alongside the actual data $I$, the one-sided formula ignores the uninstantiated models in $X \setminus I$.

**Fix.**
Either:
1. Define $X$ not as an arbitrary set in $\operatorname{Cn}(K)$, but as the **enrichment image** $X = \bar{r}(\Phi(I))$ of the specific application set $I$ (matching [`tenability.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md)), where $|X| = |I|$ and each $i \in I$ is paired with its enriched model $\Phi(i) \in M \cap GC$; or
2. Use the symmetric Hausdorff distance / Chamfer distance between $I$ and $X$:
   $$d_{\text{sym}}(I, X) = \frac{1}{2|I|} \sum_{i \in I} \min_{x \in X} d(i, x) + \frac{1}{2|X|} \sum_{x \in X} \min_{i \in I} d(i, x).$$

---

### EA-02 · `ClaimStatus(T)` Conflates Evidentiary Support with Model-Theoretic Subsumption — **Major**

**Where.** [`empirical_adequacy.md#L15`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L15), [`#L45-L51`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L45-L51).

**Finding.**
The metric claims to verify the "True Partial Empirical Claim" ($I_0 \neq \emptyset \land I_0 \in \operatorname{Cn}(K)$), where $I_0 \subseteq I$ is the set of paradigm applications (Stegmüller 1976).
However, `ClaimStatus(T)` (L49–51) defines $I_{\text{confirmed}}$ as the set of `:EmpiricalApplication` nodes with `:EVIDENCED_BY` / `:SUPPORTED_BY` edges from a `:Dataset`, and then writes:
$$\text{ClaimStatus}(T) = 1 \iff |I_{\text{confirmed}}| > 0 \land I_{\text{confirmed}} \subseteq \operatorname{Cn}(K).$$
First, having a `:Dataset` attached to an `:Application` node only means *data exists* for that application domain (e.g., planetary orbits have astronomical tables); it does **not** mean the theory's laws $M$ and constraints $GC$ hold on that data ($I_0 \in \operatorname{Cn}(K)$). Second, in the diagnostic table (L79–84), `ClaimStatus(T)` disappears entirely and is replaced by $GR(T) > 0$. Thus, a theory with 1 dataset that **completely refutes** the theory ($BMCR = 0.0$) still satisfies $GR(T) > 0$!

**Fix.**
Define $I_{\text{confirmed}} := \{ i \in I \mid \min_{x \in X^*} d(i, x) \le \epsilon_{\text{blur}} \}$ (applications that actually pass the blur test under a constraint-satisfying model set $X^*$), or separate **Data Availability Ratio** (has dataset) from **Empirical Grounding Ratio** (paradigm applications $I_0$ that satisfy $K$ within $\epsilon_{\text{blur}}$).

---

## 2. Is the Metric Formally & Mathematically Correct?

### EA-03 · Unbound (Free) Variable $X$ in $BMCR(I, K)$ — **Critical**

**Where.** [`empirical_adequacy.md#L59-L61`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L59-L61).

**Finding.**
The Blur Margin Compliance Ratio is written as:
$$BMCR(I, K) = \frac{|\{i \in I \mid \min_{x \in X} d(i, x) \le \epsilon_{\text{blur}}\}|}{|I|}$$
Here, **$X$ is a free variable**—it does not appear on the left-hand side $BMCR(I, K)$ and has no quantifier ($\max_{X \in \operatorname{Cn}(K)}$ or $\sup_{X \in \operatorname{Cn}(K)}$) on the right-hand side. As written, the formula cannot be evaluated.

Moreover, optimizing $X$ independently for $AS$ (mean residual) vs. $BMCR$ (threshold count) can select **different** model sets $X_1 \neq X_2 \in \operatorname{Cn}(K)$ unless $X^*$ is fixed across both.

**Fix.**
Quantify over $X \in \operatorname{Cn}(K)$ explicitly:
$$BMCR(I, K) = \max_{X \in \operatorname{Cn}(K)} \frac{|\{i \in I \mid \min_{x \in X} d(i, x) \le \epsilon_{\text{blur}}\}|}{|I|}$$
or define $X^* = \arg\max_{X \in \operatorname{Cn}(K)} \text{Adequacy}(I, X)$ and evaluate $BMCR(I, X^*)$ on that same witness $X^*$.

---

### EA-04 · Type Error: $\in \operatorname{Cn}(K)$ vs. $\subseteq \operatorname{Cn}(K)$ — **Major**

**Where.** [`empirical_adequacy.md#L15`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L15), [`#L28`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L28) vs. [`#L49`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L49).

**Finding.**
In structuralism (BMS 1987, p. 91), the theoretical content $\operatorname{Cn}(K) \subseteq \mathcal{P}(M_{pp})$ is a **class of sets** of partial potential models:
$$\operatorname{Cn}(K) := \{ Y \subseteq M_{pp} \mid \exists X \subseteq M : X \in GC \land X \in GL \land \bar{r}(X) = Y \}.$$
Because $I_{\text{confirmed}} \subseteq I \subseteq M_{pp}$ is a *set* of partial potential models, $I_{\text{confirmed}}$ is an **element** of $\operatorname{Cn}(K)$ ($I_{\text{confirmed}} \in \operatorname{Cn}(K)$), as correctly written on L15 and L28.
On L49, however, the formula writes:
$$I_{\text{confirmed}} \subseteq \operatorname{Cn}(K)$$
which is a Russellian type error (asserting that individual applications $i \in I_{\text{confirmed}}$ are themselves sets of partial potential models).

**Fix.**
Replace $I_{\text{confirmed}} \subseteq \operatorname{Cn}(K)$ on L49 with $I_{\text{confirmed}} \in \operatorname{Cn}(K)$.

---

### EA-05 · Type Collision in Admissible Blurs $\mathcal{A}$ — **Major**

**Where.** [`empirical_adequacy.md#L26-L30`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L26-L30).

**Finding.**
On L26, $\mathcal{A}$ is defined as a **family** of blur relations:
$$\mathcal{A} \subseteq \mathcal{P}(M_{pp} \times M_{pp})$$
(i.e. each element $u \in \mathcal{A}$ is a binary relation $u \subseteq M_{pp} \times M_{pp}$, which is an entourage of the uniformity $\mathcal{U}$).
Three lines later (L30), the definition writes:
$$(i, x) \in \mathcal{A}$$
treating $\mathcal{A}$ as a **single binary relation** $\mathcal{A} \subseteq M_{pp} \times M_{pp}$ rather than a family of relations!

**Fix.**
Follow BMS (1987, Ch. VII, p. 331): Let $\mathcal{A} \subseteq \mathcal{U}$ be a family of admissible entourages (blurs) on $M_{pp}$. Then $I \approx_{\mathcal{A}} X$ iff:
$$\exists u \in \mathcal{A} \quad \text{such that} \quad (\forall i \in I \, \exists x \in X : (i, x) \in u) \land (\forall x \in X \, \exists i \in I : (i, x) \in u).$$

---

### EA-06 · Cypher Implementation Does Not Compute $GR(T)$ and Violates $GR(T) \in [0, 1]$ — **Major**

**Where.** [`empirical_adequacy.md#L47`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L47) vs. [`#L66-L71`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L66-L71).

**Finding.**
$GR(T)$ is defined on L47 as $\frac{|I_{\text{confirmed}}|}{|I_{\text{total}}|}$, which is a proportion in $[0, 1]$ where $I_{\text{confirmed}} \subseteq I_{\text{total}}$ is a subset of applications.
The Cypher query on L67–71 instead computes:
```cypher
MATCH (t:TheoryElement {id: $id})-[:INTENDED_APPLICATION]->(i:Application)
OPTIONAL MATCH (i)<-[:EVIDENCED_BY]-(d:Dataset)
RETURN count(DISTINCT i) AS total_i, count(DISTINCT d) AS evidenced_count
```
1. If a single `:Application` node $i_1$ is evidenced by 5 `:Dataset` nodes ($d_1, \dots, d_5$) while $i_2, i_3$ have 0 datasets, `count(DISTINCT d)` is $5$ and `count(DISTINCT i)` is $3$, giving $GR = 5/3 = 1.67 > 1.0$, while 2 of 3 applications are completely ungrounded!
2. Conversely, if 1 `:Dataset` node $d_1$ evidences all 3 `:Application` nodes, `count(DISTINCT d)` is $1$, giving $GR = 1/3$ even though $100\%$ of intended applications are evidenced.
3. Division by zero occurs whenever `total_i == 0`.

**Fix.**
Count the distinct **applications** `i` that have at least one supporting dataset/observation, not the distinct datasets `d`:
```cypher
MATCH (t:TheoryElement {id: $id})-[:INTENDED_APPLICATION]->(i:Application)
OPTIONAL MATCH (i)<-[:EVIDENCED_BY]-(d:Dataset)
WITH count(DISTINCT i) AS total_i,
     count(DISTINCT CASE WHEN d IS NOT NULL THEN i END) AS confirmed_i
RETURN CASE WHEN total_i = 0 THEN 0.0 ELSE toFloat(confirmed_i) / total_i END AS grounding_ratio
```

---

### EA-07 · Unbounded Distance $d(i, x)$ Breaks Adequacy Score Range $[0, 1]$ — **Minor**

**Where.** [`empirical_adequacy.md#L35-L41`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L35-L41), [`#L55`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L55).

**Finding.**
L35 states "Let $d(i, x)$ be the normalized distance metric", and L39 states "The distance function $d(i, x)$ is defined abstractly to allow for domain-specific physical or statistical residuals." Physical or statistical residuals (e.g., $\ell_2$ norm, Mahalanobis distance, $\chi^2$ residual) lie in $[0, \infty)$, not $[0, 1]$. If $d(i, x) > 1$, then $\text{Adequacy}(I, K) = 1 - \frac{1}{|I|}\sum d(i, x)$ becomes **negative** and cannot be compared with the LLM proxy $d(i, x) = 1 - p(i, x) \in [0, 1]$.

**Fix.**
Explicitly specify a bounded normalization transform for physical residuals, e.g. $d_{\text{norm}}(i, x) = \frac{d_{\text{raw}}(i, x)}{1 + d_{\text{raw}}(i, x)} \in [0, 1)$ or $\min(1, d_{\text{raw}}(i, x) / d_{\max})$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### EA-08 · Triple Semantic Shift in the Meaning of $i, x$, and $d(i, x)$ — **Critical**

**Where.** [`empirical_adequacy.md#L24-L30`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L24-L30) $\to$ [`#L39-L41`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L39-L41) $\to$ [`#L66-L74`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L66-L74).

**Finding.**
Across 50 lines, the mathematical objects $i \in I$, $x \in X$, and $d(i, x)$ undergo three incompatible semantic shifts:

1. **Structuralist Model Space (L24–30):** $i \in I \subseteq M_{pp}$ and $x \in X \subseteq M_{pp}$ are *partial potential models* (set-theoretic structures of identical signature), and $(i, x) \in u$ measures observational measurement imprecision within the same non-theoretical vocabulary.
2. **LLM Hermeneutic Proxy (L37–41 & `ISSUE-025`):** $i$ is a natural-language observation statement and $x$ is a natural-language theoretical hypothesis/law, and $p(i, x) \in [0, 1]$ is an LLM-estimated *semantic plausibility score* that "$i$ is a valid instantiation of $x$". Here, $i$ and $x$ are no longer in the same space $M_{pp}$—one is an observation statement ($B$) and one is a law statement ($A$). Furthermore, in a text corpus (especially philosophy or qualitative science), an LLM scoring $p(i, x)$ measures **textual/semantic entailment or topical relevance**, not empirical measurement error within admissible instrumental blurs!
3. **Property-Graph Node Attribute Diff (L72–74):** In §Measurement & Graph Implementation, $x$ becomes "predicted node attributes" on `:TheoryCore`, $i$ becomes "observed empirical node values in `:EmpiricalData`", and $\mathcal{A}$ becomes "declared tolerance intervals stored on `:ErrorMargin` edges". None of these labels (`:TheoryCore`, `:EmpiricalData`, `:ErrorMargin`, `:Dataset`) exist in the Episteme / `epistemetrics` schema (`NodeType`, `RelationType`).

**Impact.**
Because of this shift, the formula $\max_{X \in \operatorname{Cn}(K)}$ is completely vacuous in the LLM proxy regime: when $p(i, x)$ is an edge property on existing graph edges `(i)-[:INSTANTIATES]->(x)`, there is no optimization over candidate model sets $X \in \operatorname{Cn}(K)$ at all.

**Fix.**
Separate the **model-theoretic residual regime** (handled by `TheoreticalEnrichmentRunner` in ADR 0015) from the **text/argumentation regime** (where `p(i, x)` is an edge weight on `:INSTANTIATES` / `:EVIDENCED_BY` between $B$-nodes and $A$-nodes). Write the exact graph formula for the edge-weight regime without pretending it maximizes over $\operatorname{Cn}(K)$.

---

## 4. Is the Metric Valid and Scientifically Significant?

### EA-09 · Complete Conceptual and Mathematical Duplication with `tenability.md` — **Major**

**Where.** [`empirical_adequacy.md#L18-L19`](../../../docs/concepts/theory/metrics/empirical_power/empirical_adequacy.md#L18-L19) vs. [`tenability.md#L20-L28`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L20-L28).

**Finding.**
Both `empirical_adequacy.md` and `tenability.md` formalize the **exact same structuralist concept**: whether $I \in \operatorname{Cn}(K)$ holds approximately under admissible blurs $\mathcal{A}$ in a uniform space $(M_p, \mathcal{U})$, citing the exact same pages of Stegmüller (1976, pp. 40–45, 75–121) and Balzer, Moulines & Sneed (1987, pp. 93, 209–217).

Worse, their attempts to distinguish themselves **directly contradict each other**:
- `empirical_adequacy.md` (L18–19) claims: *"While **Tenability** ensures the qualitative semantic precondition that empirical observation nodes can be conceptually typed and theoretically enriched into the non-theoretical vocabulary of the theory ($I \subseteq M_{pp}$...), **Empirical Adequacy** assesses whether the resulting enriched models ($M$) match empirical observations within admissible blur margins ($\mathcal{A}$)."* (Note: "theoretically enriched into the non-theoretical vocabulary" is also a contradiction in terms—enrichment adds *theoretical* terms $M_{pp} \to M_p$; restriction drops them $M_p \to M_{pp}$.)
- `tenability.md` (L20–28 & L130–180) actually computes the continuous blur optimization $TS_{\text{local}}(y, M) = \sup\{1 - \delta \mid \exists x^* \in M : (\Phi(y), x^*) \in u_\delta\}$ and $TS_{\text{edge}}(e)$ over global constraints $GC$!
- Furthermore, in `tenability.md` (L75–86) and ADR 0015, the project explicitly **rejected** using a single metric distance $d(i, x)$ because heterogeneous physical quantities lack a natural metric, adopting Bourbaki uniformities $u_\delta$ instead—whereas `empirical_adequacy.md` (L24, L35) reverts to a metric space $(\mathcal{M}_{pp}, d)$.

**Fix.**
Consolidate or strictly orthogonalize the two metrics:
- **Option A (Consolidate):** Merge `empirical_adequacy.md` and `tenability.md` into a single structuralist empirical fit suite (comprising Baseline Grounding $GR$, Local Law Tenability $TS_{\text{local}}$, Global Constraint Tenability $TS_{\text{edge}}$, and Blur Margin Compliance Ratio $BMCR = \frac{1}{|I|}|\{y \in I \mid TS_{\text{local}}(y, M) \ge 1 - \epsilon_{\text{blur}}\}|$).
- **Option B (Orthogonalize by Layer):** Keep `Tenability` for the post-processing model-theoretic enrichment solver ($\Phi_{\text{spec}}$, ADR 0015), and restrict `Empirical Adequacy & Grounding` to the **Layer 3 dialectical/evidentiary graph** ($GR$ + plausibility-weighted support coverage of intended applications), removing the duplicate $\operatorname{Cn}(K)$ optimization from `empirical_adequacy.md`.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Unregistered Neo4j Labels & Edge Types (L51, L68–74):** Uses `:TheoryElement`, `:INTENDED_APPLICATION`, `:Application`, `:EVIDENCED_BY`, `:Dataset`, `:TheoryCore`, `:EmpiricalData`, and `:ErrorMargin`. In `epistemetrics/core/models.py`, the canonical enums are `NodeType.THEORY_ELEMENT`, `NodeType.PARADIGM`, `NodeType.EVIDENCE`, and `RelationType.HAS_INTENDED_APPLICATION`, `RelationType.SUPPORTS`.
2. **Broken Sentence in Callout Note (L39):** *"To satisfy the Adequacy Score ($AS$) formula. In text-based graph environments..."* is a sentence fragment.
3. **Glossary Link Target (L16):** Links to `../../../glossary.md#starke-idealisierte-empirische-adaquatheit-newmans-problem`. In `glossary.md` (L201), the anchor exists, though "Newman's problem" is never explained in either file.
