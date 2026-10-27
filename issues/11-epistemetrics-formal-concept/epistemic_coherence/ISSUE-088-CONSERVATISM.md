# [ISSUE-088] Formal & Conceptual Evaluation: Conservatism & Epistemic Safety (`conservatism.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-088` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 2: Epistemic Coherence & Parsimony |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/epistemic_coherence/conservatism.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (computes Euclidean straightness ratio $\delta(v_1, v_{|p|}) / \sum \delta(v_i, v_{i+1})$ which scores $1.0$ on any single-step radical jump and $0.0$ when source and conclusion share a paradigm, contains unbound variables in $\text{Safety}(v_{\text{target}})$, and inverts deductive path topology) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-095`](../ISSUE-095-EPISTEMIC-COHERENCE-CROSS-CUTTING.md), [`ISSUE-006`](../../03-epistemic-metrics/ISSUE-006-novacek-hypothesis-virtues-suite.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Inverted on Core Cases)** | Claims that high $C(H)$ means the theory *"stays strictly within established conceptual boundaries"* while low $C(H)$ means it *"bridges distant, disconnected concepts"*. In reality, $C(p) = \frac{\delta(v_1, v_{|p|})}{\sum \delta(v_i, v_{i+1})}$ is the **geometric straightness index (inverse tortuosity)**: any direct 1-hop leap between two maximally distant concepts scores $C(p) = 1.0$, whereas a multi-step argument whose conclusion remains close to the conceptual neighborhood of its premise ($\delta(v_1, v_{|p|}) \to 0$) scores $C(p) \to 0.0$. Meanwhile, Epistemic Safety ignores all attacking edges $\mathcal{R}_{att}$. |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) Division by zero in $C(H)$ when $\pi_s(H, \delta) = \emptyset$ or when path vertices share identical adjacency vectors ($\sum \delta(v_i, v_{i+1}) = 0$); (2) $v_{\text{source}}$ is an **unbound variable** placed outside the $\max$ operator in $\text{Safety}(v_{\text{target}})$, breaking the Dijkstra $-\log w(e)$ reduction when multiple sources have differing priors $c(v_{\text{source}})$; (3) $-\log w(e)$ is undefined when $w(e) \le 0$. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts $\delta(u, v)$ from *"semantic distance between premises and conclusions"* across topics (L13, L48) to Euclidean distance between *"weighted adjacency vectors"* on the graph (L50, L75), which on sparse chains collapses to a purely topological function of hop count $1/(|p|-1)$. Also shifts the inferential topology to `Empirical Sentences -> Hypothesis -> Premises -> Assignment Laws -> Conclusion`, inverting the logical order of premises, hypotheses, and mapping laws. |
| **4. Valid & Scientifically Significant?** | **Conceptually Valid, Formally Flawed** | Distinguishing incremental vs. radical conceptual steps (Nováček 2015; Quine & Ullian 1978) and path-level evidential attenuation are scientifically meaningful, but require separating **endpoint conceptual leap** $\delta(v_1, v_{|p|})$ from **path straightness**, and conditioning Epistemic Safety on undefeated nodes and conjunctive premises. |

---

## 1. Does the Metric Capture What It Claims It Does?

### CS-01 · Straightness Ratio $C(H)$ Scores $1.0$ on Direct Radical Leaps and $0.0$ on Intra-Paradigm Conclusions — **Critical**

**Where.** [`conservatism.md#L13-L15`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L13-L15), [`#L48-L52`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L48-L52), [`#L71-L77`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L71-L77), [`#L110-L112`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L110-L112).

**Finding.**
The document defines Conservatism $C(H)$ for a hypothesis graph $H$ as (L72):
$$C(H) = \frac{1}{|\pi_s(H, \delta)|} \sum_{p \in \pi_s(H, \delta)} \frac{\delta(v_1, v_{|p|})}{\sum_{i=1}^{|p|-1} \delta(v_i, v_{i+1})}$$
where $\delta(u, v) = \|\mathbf{x}(u) - \mathbf{x}(v)\|_2$ is the Euclidean distance between node vectors, and claims:
- L13–15: *"A conservative theory introduces incremental semantic steps that stay closely anchored to known paradigms, whereas radical hypotheses make large conceptual leaps across disparate topics."*
- L48–49: *"It assesses whether the semantic 'distance' between the premises and the conclusions is minimized."*
- L112: High Value = *"Incremental: Stays strictly within established conceptual boundaries"*; Low Value = *"Radical: Revolutionary or highly speculative; bridges distant, disconnected concepts."*

**Why the formula contradicts the conceptual claim and diagnostic table.**
In Euclidean geometry, the quotient $\frac{\|\mathbf{x}(v_1) - \mathbf{x}(v_{|p|})\|_2}{\sum_{i=1}^{|p|-1} \|\mathbf{x}(v_i) - \mathbf{x}(v_{i+1})\|_2} \in [0, 1]$ does **not** measure whether the distance $\delta(v_1, v_{|p|})$ or the step sizes $\delta(v_i, v_{i+1})$ are small; it measures the **geometric straightness (collinearity / inverse tortuosity)** of the polygonal chain $(\mathbf{x}(v_1), \dots, \mathbf{x}(v_{|p|}))$:
1. **Single-Hop Radical Jump Collapse ($|p| = 2 \implies C(p) \equiv 1.0$):**
   For any 1-edge path $p = (v_1, v_2)$ ($|p| = 2$) with $\delta(v_1, v_2) > 0$:
   $$\frac{\delta(v_1, v_2)}{\sum_{i=1}^{1} \delta(v_i, v_{i+1})} = \frac{\delta(v_1, v_2)}{\delta(v_1, v_2)} \equiv 1.0.$$
   Thus, a wild speculative hypothesis that jumps directly from an empirical observation $v_1$ in quantum mechanics to a conclusion $v_2$ in psychoanalysis ($\delta(v_1, v_2) \gg 0$) with no intermediate reasoning steps achieves the **maximum possible Conservatism score $C = 1.0$ ("Incremental: Stays strictly within established conceptual boundaries")**! Even for $|p| > 2$, any path taking enormous steps along a straight line in vector space scores $C(p) = 1.0$.
2. **Intra-Paradigm Conclusion Inversion ($\delta(v_1, v_{|p|}) \to 0 \implies C(p) \to 0.0$):**
   Because the endpoint distance $\delta(v_1, v_{|p|})$ sits in the **numerator**, if the empirical premise $v_1$ and the theoretical conclusion $v_{|p|}$ belong to the **exact same conceptual paradigm/neighborhood** so that $\delta(v_1, v_{|p|}) \approx 0$ while the derivation traverses distinct intermediate helper lemmas $v_2, \dots, v_{|p|-1}$ ($\sum \delta(v_i, v_{i+1}) > 0$), the ratio evaluates to:
   $$C(p) = \frac{\delta(v_1, v_{|p|})}{\sum_{i=1}^{|p|-1} \delta(v_i, v_{i+1})} \to 0.0,$$
   falsely diagnosing an intra-paradigm deduction whose conclusion stays right next to its premise as **"Radical: bridges distant, disconnected concepts"**!

**Fix.**
Decompose path evaluation into two orthogonal, well-typed quantities over normalized semantic/context embeddings $\hat{\mathbf{x}}(v)$ ($\|\hat{\mathbf{x}}(v)\|_2 = 1$, where $\delta_{\cos}(u, v) = \frac{1}{2}\|\hat{\mathbf{x}}(u) - \hat{\mathbf{x}}(v)\|_2^2 = 1 - \cos(\hat{\mathbf{x}}(u), \hat{\mathbf{x}}(v)) \in [0, 1]$):
1. **Stepwise Conceptual Conservatism (Incrementalism):** Penalizes large individual semantic leaps along the inferential chain:
   $$C_{\text{step}}(H) = 1 - \frac{1}{|\Pi(H)|} \sum_{p \in \Pi(H)} \max_{1 \le i < |p|} \delta_{\cos}(v_i, v_{i+1}) \in [0, 1] \quad \text{(or arithmetic mean } 1 - \overline{\delta_{\cos}}\text{)}.$$
2. **Inferential Directness (Non-Detour / Straightness, for $|p| \ge 3$):** Measures whether intermediate premises stay on the geodesic between $v_1$ and $v_{|p|}$ without unnecessary conceptual detours, explicitly guarded against $\delta(v_1, v_{|p|}) = 0$:
   $$\text{Directness}(p) = \frac{\delta(v_1, v_{|p|})}{\sum_{i=1}^{|p|-1} \delta(v_i, v_{i+1})}.$$

---

### CS-02 · Epistemic Safety Ignores Dialectical Attacks ($\mathcal{R}_{att}$) and Conjunctive Multi-Premise Dependencies — **Major**

**Where.** [`conservatism.md#L54-L58`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L54-L58), [`#L79-L87`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L79-L87).

**Finding.**
1. **Blindness to Active Refutations ($\mathcal{R}_{att}$):**
   $\text{Safety}(v_{\text{target}})$ (L86) maximizes $\prod_{e \in p} w(e) \times c(v_{\text{source}})$ over supportive paths $p$. It completely ignores whether $v_{\text{target}}$ or an intermediate node $v_i \in p$ is the target of a decisive **attack/falsification edge** $(u, v_i) \in \mathcal{R}_{att}$. Consequently, a hypothesis that has one short support chain ($w = 0.9$) and ten fatal empirical counterexamples ($w_{\text{att}} = 1.0$) scores $\text{Safety}(v_{\text{target}}) = 0.90$ (**"Secure"**).
2. **OR-Maximization vs. AND-Conjunction of Co-Premises:**
   By taking $\max_{p \in \text{paths}}$ over simple paths, the formula treats every incoming edge as an independent sufficient warrant (convergent OR-argument). When a conclusion requires a **conjunctive law + initial condition** ($a_1 \land a_2 \to v_{\text{target}}$; see [`ISSUE-068` C-05](../../10-formal-conceptual-docs/ISSUE-068-conceptual-and-domain-errors.md)), the safety of the deduction is bounded by the *minimum* (or product) of the required co-premises, not the *maximum* of the single strongest premise.

**Fix.**
1. Restrict valid safety paths $p \in \Pi_{\text{sup}}(B \to v_{\text{target}})$ to edges in $\mathcal{R}_{sup}$ and weight each intermediate node $v_i \in p$ by a local non-refutation factor (or restrict paths to nodes accepted under D-QBAF / grounded semantics, $\tau^*(v_i) \ge \tau_{\text{accept}}$).
2. On bipartite inference hypergraphs (`ISSUE-055`), aggregate conjunctive premises of an inference step via product or Gödel t-norm ($\min$) and alternative derivations of the same claim via $\max$.

---

## 2. Is the Metric Formally & Mathematically Correct?

### CS-03 · Unbound Variable $v_{\text{source}}$ Outside the $\max$ Operator Breaks $\text{Safety}(v_{\text{target}})$ and Its Dijkstra Reduction — **Critical**

**Where.** [`conservatism.md#L81-L87`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L81-L87), [`#L101-L104`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L101-L104).

**Finding.**
1. **Unbound $v_{\text{source}}$ Outside $\max_{p \in \text{paths}}$:**
   Line 86 writes:
   $$\text{Safety}(v_{\text{target}}) = \max_{p \in \text{paths}} \left( \prod_{e \in p} w(e) \right) \times c(v_{\text{source}})$$
   Here, $v_{\text{source}}$ is not an argument of $\text{Safety}(v_{\text{target}})$, and $c(v_{\text{source}})$ is placed **outside** the $\max_{p \in \text{paths}}$ operator! Because a path $p = (v_1, \dots, v_{|p|})$ originates at $v_1 \in B$, different candidate paths $p$ supporting $v_{\text{target}}$ can originate at **different empirical source nodes** $v_1(p) \in B$ with different initial confidences $c(v_1(p))$.
2. **Broken Dijkstra Reduction (L101–104):**
   L101–104 states that Safety is computed by running Dijkstra's shortest-path algorithm with edge costs $\text{cost}(e) = -\log(w(e))$.
   - If Dijkstra is run solely with edge costs $-\log(w(e))$ without initializing the source distance queue at $\text{dist}[v_{\text{source}}] = -\log c(v_{\text{source}})$ (or adding a virtual super-source $s_0$ with edge weight $w(s_0, v_{\text{source}}) = c(v_{\text{source}})$), Dijkstra finds the path maximizing $\prod_{e \in p} w(e)$ rather than $c(v_1(p)) \prod_{e \in p} w(e)$!
   - Furthermore, if $w(e) = 0$ (e.g. an inadmissible edge gated out by D-QBAF Mode 1, `formal_graph_model.md` L216) or $c(v_{\text{source}}) = 0$, $-\log(0)$ is undefined ($+\infty$).

**Fix.**
Move $c(v_1(p))$ inside the maximization over all simple support paths $p = (v_1, e_1, \dots, e_k, v_{\text{target}})$ with $v_1 \in B$:
$$\text{Safety}(v_{\text{target}}) = \max_{p \in \Pi_{\text{sup}}(B \to v_{\text{target}})} \left( c(v_1(p)) \cdot \prod_{e \in p} w(e) \right)$$
with $\text{Safety}(v_{\text{target}}) := 0$ if $\Pi_{\text{sup}}(B \to v_{\text{target}}) = \emptyset$. For the multi-source Dijkstra implementation, initialize the priority queue with $\text{cost}(v_s) = -\log \max(\epsilon, c(v_s))$ for all $v_s \in B$ with $c(v_s) > 0$ and restrict traversal to edges $e \in \mathcal{R}_{sup}$ with $w(e) > 0$.

---

### CS-04 · Division-by-Zero Traps and Ambiguous Path Set $\pi_s(H, \delta)$ in $C(H)$ — **Critical**

**Where.** [`conservatism.md#L63-L73`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L63-L73).

**Finding.**
1. **Empty Path Set Division by Zero ($|\pi_s(H, \delta)| = 0$):**
   If $H$ contains no directed paths matching the required source-to-conclusion topology (L29–37), $|\pi_s(H, \delta)| = 0$ and the prefactor $\frac{1}{|\pi_s(H, \delta)|}$ divides by zero.
2. **Zero Step-Distance Division by Zero ($\sum_{i=1}^{|p|-1} \delta(v_i, v_{i+1}) = 0$):**
   If all vertices on a path $p$ have identical weighted adjacency vectors (e.g., $\mathbf{x}(v_i) = \mathbf{x}(v_{i+1})$, or $\delta(v_i, v_{i+1}) = 0$), the denominator $\sum_{i=1}^{|p|-1} \delta(v_i, v_{i+1}) = 0$, causing a $0/0$ NaN error.
3. **Contradictory Definition of $\pi_s(H, \delta)$:**
   - L63–64 defines paths $p$ as running *"from an empirical source $v_1$ to a conclusion $v_{|p|}$"*.
   - L69 defines $\pi_s(H, \delta)$ as *"all shortest paths $p \in \pi_s(H, \delta)$ within that graph"* weighted by $\delta$.
   - If edge weights for shortest-path routing are defined as $\delta(v_i, v_{i+1}) = \|\mathbf{x}(v_i) - \mathbf{x}(v_{i+1})\|_2$, and $\delta(v_i, v_{i+1}) = 0$ is possible, shortest paths can degenerate; moreover, the specification never states whether $\pi_s(H, \delta)$ ranges over all ordered vertex pairs $(u, v) \in V_H \times V_H$ with $|p| \ge 3$ or only source-target pairs $(v_s, v_t) \in B_H \times A_{\text{concl}}(H)$.

**Fix.**
Define $\Pi_s(H)$ explicitly as the set of $\delta$-shortest paths between empirical source nodes $v_s \in B_H$ and target conclusions $v_t \in A_{\text{concl}}(H)$ of length $|p| \ge 3$ (at least 2 edges, since 1-edge paths trivially have straightness $1$), guard $\sum_{i=1}^{|p|-1} \delta(v_i, v_{i+1}) = 0$ by returning $1.0$, and return $0.0$ (or `None`) when $\Pi_s(H) = \emptyset$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### CS-05 · Inverted Logical Path Topology (`Empirical Sentences -> Hypothesis -> Premises -> Assignment Laws -> Conclusion`) — **Critical**

**Where.** [`conservatism.md#L27-L40`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L27-L40).

**Finding.**
In §Topological Preconditions (L29–37), the required path structure is specified as:
$$\text{Empirical Sentences } (\text{Source}) \to \text{Hypothesis} \to \text{Premises} \to \text{Assignment Laws} \to \text{Conclusion } (\text{Target}).$$
This sequence commits three foundational inversions of scientific logic and of Episteme's own Layer 3 schema ([`formal_graph_model.md`](../../../docs/concepts/formal_graph_model.md)):
1. **`Hypothesis -> Premises` Inverts Premise-Conclusion Order:** By definition, premises are the reasons/assumptions from which a hypothesis or conclusion is derived (`Premises -> Hypothesis`), not downstream consequences of a hypothesis.
2. **Misplacement of Assignment Laws (*Zuordnungsgesetze*):** In Schurz (2014) and `formal_graph_model.md` (L83, L267–270) as well as `simplicity.md` (L75–77), *Zuordnungsgesetze* $Z(a, b)$ bridge **Theoretical Antecedents ($A$)** and **Empirical Observation Sentences ($B$)**. Placing `Assignment Laws` between `Premises` and `Conclusion` at the far theoretical end of the chain while `Empirical Sentences` sit at the opposite end disconnects `Assignment Laws` from `Empirical Sentences`!
3. **Deductive vs. Evidential Orientation Conflict:**
   - In deductive/explanatory order (Hempel–Oppenheim / Schurz): $\text{Core Axioms / Hypotheses } (A) + \text{Auxiliaries / Assignment Laws } (Z) \to \text{Empirical Predictions } (B)$.
   - In upward evidential justification order: $\text{Empirical Observations } (B) \xrightarrow{Z} \text{Empirical Generalizations / Premises} \xrightarrow{\mathcal{R}_{sup}} \text{Theoretical Hypotheses / Conclusions } (A)$.
   Mixing both orders into `Empirical Sentences -> Hypothesis -> Premises -> Assignment Laws -> Conclusion` produces a path pattern that **matches zero paths** in any valid `TheoryGraph` (`epistemetrics/core/models.py` has no `AssignmentLaw` or `Conclusion` `NodeType` either).

**Fix.**
Align the path topology with `epistemetrics.core.models.NodeType` and `RelationType`:
- **Upward Evidential Justification Path (for Epistemic Safety):**
  $$v_1 \in V_E \; (\text{EVIDENCE / OBSERVATION}) \xrightarrow{\text{SUPPORTS}} \dots \xrightarrow{\text{SUPPORTS}} v_k \in V_H \; (\text{CLAIM / HYPOTHESIS / AXIOM}).$$
- **Downward Explanatory / Deductive Path:**
  $$v_1 \in V_H \; (\text{AXIOM / HYPOTHESIS}) \xrightarrow{\text{EXPLAINS / SUPPORTS}} \dots \xrightarrow{\text{EXPLAINS}} v_k \in V_E \; (\text{PHENOMENON / EVIDENCE}).$$

---

### CS-06 · Semantic Shift Between "Semantic Distance Across Topics" and Sparse "Weighted Adjacency Vectors" — **Major**

**Where.** [`conservatism.md#L13-L15`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L13-L15), [`#L48-L52`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L48-L52), [`#L75`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L75), and [`ISSUE-006`](../../03-epistemic-metrics/ISSUE-006-novacek-hypothesis-virtues-suite.md#L31).

**Finding.**
1. The document motivates $\delta(u, v)$ as the **semantic distance across topics** between premises and conclusions (L13–15, L48), and [`ISSUE-006`](../../03-epistemic-metrics/ISSUE-006-novacek-hypothesis-virtues-suite.md#L31) specifies `conservatism.py` as *"Shortest-path semantic embedding divergence between premise anchors and conclusion leaves"*.
2. However, L50–51 and L75 define $\delta(u, v)$ as the Euclidean distance between the **weighted adjacency vectors** $\mathbf{x}(u), \mathbf{x}(v) \in \mathbb{R}^{|V|}$ of the vertices in the graph.
3. On a directed Layer 3 argument graph (`TheoryGraph`), using raw adjacency vectors $\mathbf{x}(v)$ fails both mathematically and semantically:
   - Whether $\mathbf{x}(v)$ is the outgoing row $A_{v,:}$, incoming column $A_{:,v}$, or symmetrized adjacency $A_{v,:} + A_{:,v}^\top$ is left unspecified (if outgoing, every terminal conclusion $v_{|p|}$ has $\mathbf{x}(v_{|p|}) = \mathbf{0}$).
   - Along a sparse deductive chain $v_1 \to v_2 \to \dots \to v_k$, vertices $v_i$ and $v_j$ ($|i - j| \ge 2$) rarely share 1-hop neighbors in $V$, so their adjacency vectors have disjoint support ($\mathbf{x}(v_i) \perp \mathbf{x}(v_j)$). If each node has unit-normalized adjacency weight $\|\mathbf{x}(v_i)\|_2 = 1$, then $\delta(v_i, v_j) = \sqrt{2}$ for **every** pair of non-sharing nodes, collapsing $C(p)$ to:
     $$C(p) = \frac{\sqrt{2}}{(|p|-1)\sqrt{2}} = \frac{1}{|p|-1},$$
     which is merely the **reciprocal of path length** and contains zero semantic or topic information!

**Fix.**
Define $\mathbf{x}(v) \in \mathbb{R}^d$ explicitly as the L2-normalized **contextual semantic embedding** of proposition $v$ (or the L2-concept TF-IDF / community profile vector over L2 entities mentioned in $v$, matching Nováček 2015's corpus co-occurrence context vectors), rather than the sparse L3 1-hop adjacency row.

---

## 4. Is the Metric Valid and Scientifically Significant?

### CS-07 · Metascientific Framing of Conservatism vs. Lakatosian Boldness — **Minor**

**Where.** [`conservatism.md#L110-L113`](../../../docs/concepts/theory/metrics/epistemic_coherence/conservatism.md#L110-L113).

**Finding.**
While Quine & Ullian (1978) and Nováček (2015) treat Conservatism as a plausibility virtue (minimizing perturbation of established belief), Popper (1959) and Lakatos (1970) prize **theoretical boldness** (bridging previously unconnected domains to generate novel predictions, evaluated in `progressiveness.md` and `theoretical_achievements.md`). The diagnostic table (L112) appropriately notes both interpretations ("Incremental" vs. "Radical: Revolutionary or highly speculative"), which is good practice, provided $C(H)$ is not combined into a composite score that unconditionally penalizes revolutionary cross-domain unification.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Inconsistent Author Spelling (`Novacek` vs. `Nováček`):** Spelled `Novacek` without diacritics throughout `conservatism.md` (L15, L47, L49, L66, L69, L119), whereas `simplicity.md` (L22, L210) and `index.md` (L188) spell it `Nováček`.
2. **Incomplete Bibliographic Entry (L119):** `Novacek, V. (2015). Formalising Hypothesis Virtues in Knowledge Graphs.` omits co-authors, venue, and arXiv identifier (`arXiv:1503.09137v2`; cf. `index.md` L188–189).
3. **Symbol Collision on $\delta$ and $c$:** $\delta(u, v)$ denotes Euclidean distance between node vectors here, whereas $\delta$ denotes uniform-space blur in `tenability.md` and L2 edge certainty in `formal_graph_model.md`; $c(v_{\text{source}}) \in [0, 1]$ denotes node confidence here, whereas $c(a_i) \in [1, \infty)$ denotes MDL content-element count in `simplicity.md` and $c(b \mid A_{\text{core}})$ denotes residual data cost in `elegance_and_economy.md`.
