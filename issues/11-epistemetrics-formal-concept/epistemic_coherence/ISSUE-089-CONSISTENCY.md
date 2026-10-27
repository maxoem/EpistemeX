# [ISSUE-089] Formal & Conceptual Evaluation: Consistency (`consistency.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-089` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 2: Epistemic Coherence & Parsimony |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/epistemic_coherence/consistency.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (measures lexical/topical context similarity via embedding cosine rather than logical or axiomatic consistency, is completely blind to direct negation/contradiction, penalizes cross-domain unifying concepts, and divides by zero when $k < 2$) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-095`](../ISSUE-095-EPISTEMIC-COHERENCE-CROSS-CUTTING.md), [`ISSUE-045`](../../10-decision-engine-and-jev/ISSUE-045-phase3b-consolidation-merge-verification.md), [`ISSUE-054`](../../09-architecture-workflow-domain/ISSUE-054-intensional-perspectival-scoping-and-conception-stratification.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Construct Mismatch)** | Claims to measure structuralist **logical and axiomatic consistency** (whether a theory avoids mutually conflicting axiomatizations and satisfies cross-application constraints $C(\tau)$). Instead, $S_{\text{embed}}(t)$ computes average pairwise cosine similarity of contextual embeddings across mentions of a term $t$. Standard dense embeddings assign $> 0.90$ cosine similarity to direct logical contradictions ($P(t)$ vs. $\neg P(t)$) in the same domain while assigning low similarity to legitimate applications of the same concept across heterogeneous domains. |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) Division by zero in $\frac{1}{\binom{k}{2}}$ whenever a concept has $k \le 1$ mentions; (2) Symbol collision on $k$ (used both as mention count $k = \|E_t\|$ and as cluster count in "$k$-means"); (3) Silhouette score $S_{\text{sil}}(t)$ is undefined for $\|E_t\| < 3$ and for $C = 1$ cluster, and its cluster count parameter is never specified; (4) Structuralist constraint equation $C(\tau) \subseteq \mathcal{P}(M_p(T_1) \times M_p(T_2))$ is mistyped. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts across three distinct constructs: (a) **structuralist cross-application constraints** $C(\tau)$ in model space (L22–26), (b) **logical consistency / non-contradiction** of axiomatizations (L11, L16), and (c) **lexical monosemy / entity disambiguation hygiene** over L2 concept mentions (L34–58). |
| **4. Valid & Scientifically Significant?** | **Misplaced Layer / Misnamed** | Detecting polysemous entity over-merging is a useful **Layer 2 entity-consolidation hygiene check** (Phase 3b), and tracking conceptual drift across authors/eras relates to diachronic dynamics (`ISSUE-011`, `ISSUE-054`), but calling contextual embedding similarity "Consistency" leaves actual **Layer 3 logical/dialectical consistency** ($\Sigma \cup B \nvdash \perp$) unmeasured. |

---

## 1. Does the Metric Capture What It Claims It Does?

### CN-01 · Embedding Cosine Similarity $S_{\text{embed}}(t)$ Is Blind to Logical Contradiction and Penalizes Cross-Domain Unification — **Critical**

**Where.** [`consistency.md#L11-L17`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L11-L17), [`#L39-L42`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L39-L42), [`#L63-L66`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L63-L66).

**Finding.**
The document states that Consistency ensures a theoretical term *"does not implicitly switch definitions or adopt mutually conflicting axiomatizations within the same reconstructed theory"* (L16–17), and measures it via the mean pairwise cosine similarity of contextual embeddings $\mathbf{v}(e_i)$ of mentions $E_t = \{e_1, \dots, e_k\}$ (L42):
$$S_{\text{embed}}(t) = \frac{1}{\binom{k}{2}} \sum_{1 \le i < j \le k} \frac{\mathbf{v}(e_i) \cdot \mathbf{v}(e_j)}{\|\mathbf{v}(e_i)\| \|\mathbf{v}(e_j)\|}.$$

**Why this fails in both directions:**
1. **False Positive on Direct Logical Contradictions (Negation Blindness):**
   In transformer-based contextual token and sentence embeddings, two mutually contradictory axioms about the same term $t$ in the same domain share almost identical vocabulary, syntax, and topical neighborhood:
   - $e_1$: *"In isolated thermodynamic systems, entropy $S$ monotonically increases ($\Delta S \ge 0$)."*
   - $e_2$: *"In isolated thermodynamic systems, entropy $S$ monotonically decreases ($\Delta S < 0$)."*
   Because $\mathbf{v}(e_1)$ and $\mathbf{v}(e_2)$ have cosine similarity $\ge 0.90$, a blatantly self-contradictory axiomatization achieves $S_{\text{embed}}(\text{"entropy"}) \ge 0.85$, which the diagnostic table (L65) classifies as **"Rigorous conceptual precision throughout corpus"**!
2. **False Negative on Cross-Domain Theoretical Unification:**
   In structuralism (Balzer, Moulines & Sneed 1987) and Schurz (2014), a core achievement of a theoretical concept $t$ (e.g., *"mass"*, *"energy"*, *"utility"*, *"entropy"*) is that the **same** formal concept bridges heterogeneous empirical domains (e.g., "entropy" applied to steam engines in thermodynamics, spin lattices in statistical mechanics, and channel capacity in information theory; or "mass" applied to planetary orbits vs. laboratory springs). Because the surrounding textual contexts (astronomy vs. laboratory mechanics) differ in domain vocabulary, contextual embeddings $\mathbf{v}(e_i)$ form domain-specific clusters with lower cross-domain cosine similarity ($S_{\text{embed}} < 0.60$) and high silhouette score $S_{\text{sil}}$, causing the metric to flag the unifying theoretical concept for **"automated entity splitting"** (L58, L66)—destroying the theory's cross-domain unification!

**Fix.**
Separate the two distinct constructs that are conflated here:
1. **Logical / Dialectical Theory Consistency (Pillar 2 Epistemic Coherence, Layer 3):**
   Measure whether the accepted or core propositions $A(T)$ of theory $T$ are free of internal attack/contradiction relations (`RelationType.ATTACKS` / NLI contradiction) and free of joint inconsistency on shared empirical applications $I(T)$:
   $$\text{Consistency}_{\text{logical}}(T) = 1 - \frac{\sum_{(a_i, a_j) \in \mathcal{R}_{att} \cap (A(T) \times A(T))} W_{ij} \, \tau^*(a_i) \, \tau^*(a_j)}{\max\big(1, \, |A(T)|(|A(T)| - 1)/2\big)} \in [0, 1]$$
   (combined with constraint tenability $TS_{\text{edge}}$ across $GC$ in `tenability.md`).
2. **Lexical Monosemy / Concept Equivocation Score (Layer 2 Entity Hygiene):**
   Rename $S_{\text{embed}}(t)$ and $S_{\text{sil}}(t)$ to **Conceptual Monosemy / Terminological Stability**, and evaluate it using **definitional/intensional embeddings** (or NLI mutual entailment over extracted definitions of $t$, see [`ISSUE-054`](../../09-architecture-workflow-domain/ISSUE-054-intensional-perspectival-scoping-and-conception-stratification.md)) rather than raw surface-context window embeddings that merely reflect topical domain shifts.

---

## 2. Is the Metric Formally & Mathematically Correct?

### CN-02 · Division by Zero for $k < 2$, Symbol Collision on $k$, and Undefined Silhouette Score $S_{\text{sil}}(t)$ — **Critical**

**Where.** [`consistency.md#L34-L50`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L34-L50).

**Finding.**
1. **Division by Zero when $k \le 1$ (L42):**
   Let $k = |E_t|$ be the number of mentions of concept node $t \in V$. For any concept mentioned once ($k = 1$) or zero times ($k = 0$), $\binom{k}{2} = \frac{k(k-1)}{2} = 0$, so:
   $$S_{\text{embed}}(t) = \frac{1}{\binom{k}{2}} \sum_{1 \le i < j \le k} \dots$$
   divides by zero ($0/0$). In long-tail scientific and philosophical corpora, a large fraction of extracted concepts have $k = 1$.
2. **Symbol Collision on $k$ within 12 Lines (L34 vs. L46):**
   - L34 defines $k$ as the **cardinality of the mention set**: $E_t = \{e_1, e_2, \dots, e_k\}$.
   - L46–47 writes: *"evaluated via silhouette score $S_{\text{sil}}$ over $k$-means"*, using the same symbol $k$ for the **number of clusters**! (If $k$-means is literally run with $k = |E_t|$ clusters on $k$ points, every point is a singleton cluster of size $1$, for which the intra-cluster distance $a(i)$ and silhouette score are undefined!)
3. **Ill-Defined Silhouette Score $S_{\text{sil}}(t)$ (L46–49):**
   - The standard Rousseeuw (1987) silhouette coefficient $S_{\text{sil}}$ for a partition into $C$ clusters is defined **only** when $2 \le C \le |E_t| - 1$ (requiring $|E_t| \ge 3$ and at least one cluster of size $\ge 2$).
   - The specification never states how the cluster count $C$ is chosen. Worse, if $C \ge 2$ is forced on a completely monosemous concept whose embeddings form a single isotropic Gaussian cluster in $\mathbb{R}^d$, $k$-means will partition the sphere into $C$ Voronoi sectors and report a strictly positive silhouette score $S_{\text{sil}}(t) > 0$, falsely indicating polysemy when the true number of semantic clusters is $C = 1$!

**Fix.**
1. Define $S_{\text{embed}}(t) := 1.0$ when $|E_t| \le 1$.
2. Denote mention count by $m = |E_t|$ and candidate cluster count by $C \in \{2, \dots, \min(C_{\max}, m - 1)\}$ (for $m \ge 3$, returning $\text{PolysemyDrift}(t) := 0.0$ when $m < 3$).
3. Gate multi-modal cluster detection with a unimodality test (e.g., Bayesian Information Criterion $\Delta\text{BIC}(C=1 \to C^*) > 0$ or gap statistic) or define drift via angular dispersion $1 - S_{\text{embed}}(t)$ modulated by $\max_{2 \le C \le C_{\max}} S_{\text{sil}}(t; C)$ so that unimodal clusters are not forcibly split.

---

### CN-03 · Type Error in Structuralist Constraint Formula $C(\tau) \subseteq \mathcal{P}(M_p(T_1) \times M_p(T_2))$ — **Major**

**Where.** [`consistency.md#L22-L26`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L22-L26).

**Finding.**
L22–26 states:
> *"In structuralist philosophy, a concept's formal meaning is bound by its potential model class $M_p$ and cross-application constraints $C$. If term $\tau$ appears in multiple theory-elements $T_1, T_2$, its semantic interpretation must satisfy relational compatibility:*
> $$C(\tau) \subseteq \mathcal{P}(M_p(T_1) \times M_p(T_2))\text{"}$$

This conflates **intra-theoretical global constraints ($GC$)** with **inter-theoretical links ($GL$)** and mistypes both (Balzer, Moulines & Sneed 1987, Ch. II & Ch. VIII):
1. A **global constraint** $GC(T) \subseteq \mathcal{P}(M_p(T))$ is a family of subsets of a *single* theory-element's potential models $M_p(T)$ (e.g., an equality constraint requiring that for any set of models $X \in GC(T)$, the function $\tau$ takes the same value on identical objects across all $x, x' \in X$).
2. An **intertheoretical link** $GL(T_1, T_2) \subseteq M_p(T_1) \times M_p(T_2)$ between two theory-elements $T_1, T_2$ is a subset of the Cartesian product $M_p(T_1) \times M_p(T_2)$ (i.e., $GL \in \mathcal{P}(M_p(T_1) \times M_p(T_2))$, not $\subseteq \mathcal{P}(M_p(T_1) \times M_p(T_2))$).
3. Furthermore, this structuralist formula is completely disconnected from the rest of `consistency.md`: cross-application constraint satisfaction in $M_p$ is evaluated by $TS_{\text{edge}}(e)$ in [`tenability.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md#L157-L165), not by token embeddings!

**Fix.**
Write the intra-element global constraint as $GC_\tau \subseteq \mathcal{P}(M_p(T))$ and the inter-element link as $GL_\tau \subseteq M_p(T_1) \times M_p(T_2)$, and explicitly cross-reference [`tenability.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/tenability.md) for the quantitative evaluation of $GC$ and $GL$.

---

### CN-04 · Incomplete Diagnostic Table & Missing Range/Thresholds for $\text{PolysemyDrift}(t)$ — **Minor**

**Where.** [`consistency.md#L44-L50`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L44-L50), [`#L62-L67`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L62-L67).

**Finding.**
1. The diagnostic table (L63–66) defines rows only for $S_{\text{embed}} \ge 0.85$ and $S_{\text{embed}} < 0.60$, leaving the interval $0.60 \le S_{\text{embed}} < 0.85$ undefined.
2. Although §Mathematical Specification defines a second metric $\text{PolysemyDrift}(t) = S_{\text{sil}}(t) \in [-1, 1]$ (L49), the Measurement section (L57) and Diagnostic table (L63–66) never mention $S_{\text{sil}}(t)$ or specify its flagging threshold $\theta_{\text{sil}}$.

**Fix.**
Add the intermediate diagnostic band $0.60 \le S_{\text{embed}} < 0.85$ (*"Contextual Variation / Cross-Domain Application — Verify whether clusters reflect legitimate domain specialization or polysemy via $S_{\text{sil}}$"*) and specify the decision rule combining $S_{\text{embed}} < \theta_{\text{sim}}$ and $S_{\text{sil}} > \theta_{\text{sil}}$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### CN-05 · Three-Way Semantic Shift:Axiomatic Consistency $\to$ Structuralist Constraints $\to$ L2 Entity Linking Disambiguation — **Major**

**Where.** [`consistency.md#L11-L29`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L11-L29) $\to$ [`#L34-L58`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L34-L58).

**Finding.**
The specification shifts silently across three distinct layers of the Episteme architecture:
1. **Layer 3 Axiomatic Non-Contradiction (L11–17):** Whether a theory adopts *"mutually conflicting axiomatizations"* (a property of sets of propositions $Ax(T)$ in Layer 3).
2. **Model-Theoretic Constraint Satisfaction (L22–26):** Whether $C(\tau)$ holds across $M_p(T_1) \times M_p(T_2)$ (a property of numerical/structural parameter assignments in Theoretical Enrichment).
3. **Layer 1 $\to$ Layer 2 Entity Mention Clustering (L34–58):** Whether text mentions $e_1, \dots, e_k$ mapped to a concept node $t \in \mathcal{V}_{L2}$ have similar contextual embeddings or should undergo *"automated entity splitting"* (which is Phase 2 / Phase 3b entity consolidation in `episteme-pipeline`, see `ISSUE-045`).

**Impact.**
Because `consistency.md` is placed in **Pillar 2: Epistemic Coherence** as the sole "Consistency" metric of a theory, any downstream evaluation harness (`epistemetrics`) looking for a measure of whether a theory is **logically consistent** (free of self-contradiction) instead gets an L2 lexical clustering score on entity mentions, while a theory containing explicit `ATTACKS` / `CONTRADICTS` edges between its own axioms goes undetected!

**Fix.**
Clarify the scope of `consistency.md` by splitting it into (1) **Terminological / Intensional Consistency ($S_{\text{embed}}, S_{\text{sil}}$)** over L2 concept definitions and (2) **Axiomatic / Dialectical Consistency** over L3 proposition subgraphs.

---

## 4. Is the Metric Valid and Scientifically Significant?

### CN-06 · Philosophical Grounding of Equivocation Detection vs. Formal Consistency — **Minor**

**Where.** [`consistency.md#L11-L18`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L11-L18), [`#L69-L73`](../../../docs/concepts/theory/metrics/epistemic_coherence/consistency.md#L69-L73).

**Finding.**
Detecting the **fallacy of equivocation** (using the same lexical term $t$ with two incompatible meanings across premises of an argument, e.g. in philosophical prose) is genuinely valuable for GER/ENG scientific and philosophical corpora (and connects directly to [`ISSUE-054: Intensional & Perspectival Scoping`](../../09-architecture-workflow-domain/ISSUE-054-intensional-perspectival-scoping-and-conception-stratification.md)). However, Balzer, Moulines & Sneed (1987, p. xviii) and Schurz (2024, sec. 5.2) discuss **formal/logical consistency of a theory**, not contextual word embeddings or $k$-means silhouette scores. Cite computational lexical semantics / word-sense induction literature (e.g., Navigli 2009; Rousseeuw 1987) for the embedding clustering method alongside philosophical references on equivocation and conceptual drift.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Broken Desktop Zotero Links & Duplicate Key `24SNSW2B` (L13):** Both `[Balzer et al., 1987, p. xviii]` and `[Schurz, 2024, sec. 5.2]` link to the exact same local Zotero URI `zotero://select/library/items/24SNSW2B`. Replace with standard Markdown reference links or DOIs.
2. **Symbol Collision on $t$ and $E_t$:** Uses $t \in V$ for a concept node (whereas $t$ denotes discrete iteration time in `node_activation.md` and `system_coherence.md`, and $\tau$ is used for the same term on L23 of `consistency.md`!) and $E_t$ for the set of entity mentions (colliding with edge set $E$ and cluster entropy $E(\cdot)$). Use $\tau \in \mathcal{V}_{L2}$ for the concept node and $M(\tau) = \{m_1, \dots, m_n\}$ for its mention set.
3. **Unstored Mention Embeddings in `TheoryGraph`:** `TheoryNode` in `packages/epistemetrics/src/epistemetrics/core/models.py` stores `provenance: list[str]` (chunk IDs), not per-mention contextual embedding vectors $\mathbf{v}(e_i) \in \mathbb{R}^d$. To make $S_{\text{embed}}$ computable in `epistemetrics`, Phase 3b (`phase3b_consolidation`) must persist either the pre-computed mention dispersion score or the mention embeddings on the consolidated `L2Entity` / `TheoryNode.attributes`.
