# [ISSUE-072] Formal & Conceptual Evaluation: Effective Empirical Content (`empirical_content.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-072` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 3: Empirical Power |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/empirical_power/empirical_content.md`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (contains non-equivalence relation used for quotient sets, disjoint numerator/denominator in $\Gamma_{\text{relative}}$, and reversed Lakatos Delta under anomaly accommodation) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-075`](../ISSUE-075-EMPIRICAL-POWER-CROSS-CUTTING.md), [`ISSUE-055`](../../09-architecture-workflow-domain/ISSUE-055-bipartite-inference-hypergraph-conjunctive-premises-and-undercutters.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Inverted in Key Regimes)** | Claims to measure Popperian/Carnapian empirical content (what a theory *forbids*) regularized by parsimony and immunized against tacking and ad-hoc patches. However, (1) positive empirical observations $M_w$ increase EEC even when the theory neither explains nor predicts them; (2) accommodating a falsifying anomaly *increases* $M_w$ and can make the Lakatos Delta $\Delta_{\text{EEC}} < 0$ (diagnosing ad-hoc immunization as progressive!); (3) geometric mean across hyperedge nodes violates the "weakest link" principle it claims to preserve. |
| **2. Formally & Mathematically Correct?** | **No (5 Critical/Major Flaws)** | (1) $\sim_{\text{eq}}$ is **not an equivalence relation** (probabilistic dependence / lack of $d$-separation is intransitive, and disjunctive union with structural equivalence is intransitive), so the quotient set $V_O / {\sim_{\text{eq}}}$ does not exist; (2) $E_{\text{forbidden}} \not\subseteq E_{\text{local}}$, so $\Gamma_{\text{relative}}(K)$ can exceed $1.0$ or divide by zero; (3) $0 < \text{EEC} \le 1$ is violated when $E_{\text{forbidden}} = \emptyset$ ($\text{EEC}=0$) or $E_{\text{forbidden}} \not\subseteq E_{\text{local}}$ ($\text{EEC}>1$); (4) $\rho_e$ (mutual information) is undefined on deductively excluded edges where $P(e \mid K) = 0$. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts from (a) hypergraph $H=(V, E, P)$ where $V_O$ are empirical propositions/sentences with quantifier classes ($S_{\text{univ}}, S_{\text{exist}}$), to (b) causal Bayesian network variables for $d$-separation, to (c) property-graph entities where $k_T = |V_T|$ counts theoretical *constructs/nodes* rather than independent axioms, to (d) LPG-ECHO node activations. |
| **4. Valid & Scientifically Significant?** | **Conceptually Ambitious, Computationally Unoperationalized** | The synthesis of Schurz's relevant content, Carnapian logical probability, Goldman's reliabilist inferential distance, and MDL/parsimony regularization is theoretically rich, but the hypergraph $H$, forbidden power-set $E_{\text{forbidden}}$, and $d$-separation quotient have **zero mapping** to Episteme's actual `TheoryGraph` data structures. |

---

## 1. Does the Metric Capture What It Claims It Does?

### EEC-01 · Geometric Mean Violates the Claimed "Weakest Link" Principle of Conjunctions — **Major**

**Where.** [`empirical_content.md#L104-L112`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L104-L112).

**Finding.**
In §The Relative Restriction Grammar (L104–106), the document states:
> *"To preserve the epistemological integrity of logical conjunctions (the 'weakest link' principle of falsificationism) while preventing the mathematical collapse of higher-order multi-node edges, the aggregation utilizes a normalized geometric mean: $\left(\prod_{v \in e} w(v)\right)^{1/|e|}$."*

Logically and mathematically, this is self-contradictory:
1. **What a forbidden hyperedge represents:** If $e = \{v_1, \dots, v_k\} \in E_{\text{forbidden}}$ means the theory forbids the simultaneous occurrence (conjunction) $v_1 \land \dots \land v_k$, i.e. $K \vdash \neg(v_1 \land \dots \land v_k)$, then to empirically test/falsify $K$ via $e$, one must jointly establish **all** $v_1, \dots, v_k$.
2. **Failure of the weakest link:** Under the geometric mean, if $v_1$ is a highly robust universal law ($w(v_1) = 1.0$) and $v_2$ is a nearly unmeasurable existential claim ($w(v_2) = 0.01$), the 2-node hyperedge $e = \{v_1, v_2\}$ receives weight $\sqrt{1.0 \times 0.01} = 0.10$—which is **$10\times$ higher** than the weakest link $\min_{v \in e} w(v) = 0.01$! Worse, conjoining a low-weight node $v_2$ with $m$ high-weight nodes $v_1, \dots, v_m$ drives $\left(\prod w(v)\right)^{1/(m+1)} \to 1.0$ as $m \to \infty$, **completely masking the untestable component**.
3. **Conversely, if $K \vdash \neg e$ is read conjunctively:** If $K$ forbids *each* $v \in e$ individually ($K \vdash \neg v_1 \land \dots \land \neg v_k$), then $e$ is not a hyperedge at all, just a set of 1-ary exclusions.

**Fix.**
If $e = \{v_1, \dots, v_k\}$ represents a forbidden state conjunction $K \vdash \neg\bigwedge_{v \in e} v$, testing $e$ requires observing every $v \in e$, so the epistemic reliability $R_e$ is bounded by the weakest link $\min_{v \in e} R_v$ (Gödel t-norm) or product $\prod_{v \in e} R_v$, while the syntactic improbability $S_e$ is governed by the joint prior $1 - P(\bigwedge_{v \in e} v)$. Separate $R_e = \min_{v \in e} R_v$ from $S_e$ rather than taking the geometric mean of $w(v)$.

---

### EEC-02 · Unexplained/Irrelevant Observations Inflate $M_w$ and $\text{EEC}(K)$ — **Major**

**Where.** [`empirical_content.md#L114-L140`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L114-L140), [`#L160`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L160).

**Finding.**
The parsimony regularizer is defined as:
$$\text{DoF}_w = \exp\left(-\lambda \frac{k_T}{M_w}\right), \quad \text{where} \quad M_w = \sum_{[v] \in V_O / {\sim_{\text{eq}}}} w([v]).$$
Notice that $M_w$ sums over **all empirical nodes $V_O$ in the graph**, regardless of whether theory $K$ explains, predicts, or even connects to them!
If a document or corpus contains 1,000 independent empirical observation statements ($M_w \gg k_T$) that theory $K$ says almost nothing about (except forbidding one trivial configuration in its tiny local neighborhood so $\Gamma_{\text{relative}}(K) = 1$), then $\exp(-\lambda k_T / M_w) \to 1.0$ and $\text{EEC}(K) \to 1.0$.
Thus, adding completely unrelated empirical observations to the graph artificially inflates $M_w$ and boosts $\text{EEC}(K)$.

**Fix.**
Restrict $M_w(K)$ to the **empirically covered/constrained domain of $K$**, i.e., equivalence classes of empirical nodes that participate in relevant derivations or forbidden configurations of $K$:
$$V_O(K) := \bigcup \{ e \in E_{\text{forbidden}}(K) \cup E_{\text{explained}}(K) \mid \rho_e(K) > 0 \}.$$

---

### EEC-03 · Lakatos Delta ($\Delta_{\text{EEC}}$) Can Become Negative Under Ad-Hoc Immunization — **Critical**

**Where.** [`empirical_content.md#L141-L152`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L141-L152).

**Finding.**
The Lakatos Delta is defined as:
$$\Delta_{\text{EEC}} = \text{EEC}(K_{\text{core}}) - \text{EEC}(K_{\text{core}} \cup \{B'\})$$
with the diagnostic claim (L149–151):
> *"A degenerative research program reveals itself when $B'$ shrinks the set of forbidden empirical states while simultaneously increasing theoretical parameters ($k_T$). This yields a positive $\Delta_{\text{EEC}}$, meaning the theory has lost effective empirical content."*

There are two critical flaws here:
1. **Classical Monotonicity of $\vdash$:** In classical logic, adding an auxiliary hypothesis $B'$ via conjunction $K_{\text{core}} \cup \{B'\}$ **never shrinks** the deductive consequences $\operatorname{Cn}(K_{\text{core}} \cup \{B'\}) \supseteq \operatorname{Cn}(K_{\text{core}})$! An ad-hoc immunization does not *conjoin* $B'$ to an unchanged $K_{\text{core}}$; it **replaces/weakens** a core or belt law $L \in K$ with a hedged version $L' = (L \lor \text{Exception})$ (an AGM contraction followed by expansion, see `ISSUE-067` B-04). Writing $K_{\text{core}} \cup \{B'\}$ is logically incompatible with "shrinking the set of forbidden empirical states".
2. **Sign Reversal when $B'$ adds an ad-hoc empirical exception:** Suppose $B'$ is formulated using observational vocabulary (e.g. "except at spacetime region $x_0$"), or introduces new empirical boundary nodes into $V_O$ while keeping $k_T = |V_T|$ fixed, or adds a specialized restriction in a small local neighborhood. If $\Gamma_{\text{relative}}$ increases locally or $M_w$ increases, $\text{EEC}(K') > \text{EEC}(K)$, yielding $\Delta_{\text{EEC}} < 0$ (falsely classifying an ad-hoc adjustment as progressive).

**Fix.**
1. Write the modified theory as $K' = (K \setminus \{L\}) \cup \{L'\}$ (belt revision) rather than monotonic union $K_{\text{core}} \cup \{B'\}$.
2. Evaluate $\Gamma_{\text{relative}}$ over a **fixed reference domain** $E_{\text{ref}}$ across both $K$ and $K'$ so the denominator does not shift between versions.

---

## 2. Is the Metric Formally & Mathematically Correct?

### EEC-04 · $\sim_{\text{eq}}$ Is Not an Equivalence Relation; Quotient $V_O / {\sim_{\text{eq}}}$ Is Ill-Defined — **Critical**

**Where.** [`empirical_content.md#L117-L131`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L117-L131).

**Finding.**
The document partitions $V_O$ into equivalence classes $V_O / {\sim_{\text{eq}}}$ by defining (L120–124):
> *"Two empirical nodes $v_i$ and $v_j$ are equivalent ($v_i \sim_{\text{eq}} v_j$) if they fail the criterion of strict probabilistic independence (e.g., they are not $d$-separated within the underlying theoretical causal network) or if they occupy structurally equivalent positions within the hypergraph topology (sharing identical hyperedge neighborhoods $N(v_i) = N(v_j)$)."*

**Mathematical Proof of Invalidity:**
A relation $\sim$ forms a valid partition $V_O / {\sim}$ **if and only if** it is reflexive, symmetric, and **transitive**.
1. **Probabilistic dependence (lack of $d$-separation) is NOT transitive:** Let $X_1 \to Y \leftarrow X_2$ be a collider, or let $X_1$ and $X_2$ be independent coin flips and $Y = X_1 + X_2$. Then $X_1$ and $Y$ are probabilistically dependent ($X_1 \sim Y$), and $Y$ and $X_2$ are probabilistically dependent ($Y \sim X_2$), **but $X_1$ and $X_2$ are strictly independent ($X_1 \not\sim X_2$)**!
2. **Union of two relations is NOT transitive:** Even if relation $\sim_1$ and relation $\sim_2$ were both equivalence relations, their disjunction ($\sim_1 \lor \sim_2$) is **not** transitive ($v_1 \sim_1 v_2$ and $v_2 \sim_2 v_3 \not\implies v_1 \sim_1 v_3 \lor v_1 \sim_2 v_3$).
3. **Neighborhood equality $N(v_i) = N(v_j)$ fails for adjacent nodes unless self-loops are handled:** In a hypergraph, if $N(v)$ is the set of incident hyperedges $\{e \in E \mid v \in e\}$, then $N(v_i) = N(v_j)$ means $v_i$ and $v_j$ belong to the exact same hyperedges (twins). That part is an equivalence relation, but its disjunction with probabilistic dependence is not.

Because $\sim_{\text{eq}}$ is not transitive, the equivalence classes $[v]$ overlap, and the sum $M_w = \sum_{[v] \in V_O / {\sim_{\text{eq}}}} w([v])$ is **mathematically undefined**.

**Fix.**
Either:
1. Take the **transitive closure** $\sim_{\text{eq}}^*$ of the dependence/twin relation (which corresponds to connected components in the dependence graph, though note this may collapse large chains via single hubs); or
2. Replace hard quotienting with a **continuous effective sample size / diversity weighting** (e.g., discounting each node $v_i$ by its total similarity/mutual information with other nodes: $M_w = \sum_{v_i \in V_O} \frac{w(v_i)}{1 + \sum_{j \neq i} \text{Sim}(v_i, v_j)}$, as in Solow–Polasky species diversity or effective sample size $N_{\text{eff}}$).

---

### EEC-05 · Numerator and Denominator of $\Gamma_{\text{relative}}(K)$ Sum Over Incommensurable Sets — **Critical**

**Where.** [`empirical_content.md#L96`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L96), [`#L108-L112`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L108-L112), [`#L157`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L157).

**Finding.**
The Relative Restriction Grammar is defined as:
$$\Gamma_{\text{relative}}(K) = \frac{\sum_{e \in E_{\text{forbidden}}} \rho_e \left(\prod_{v \in e} w(v)\right)^{\frac{1}{|e|}}}{\sum_{e \in E_{\text{local}}} \left(\prod_{v \in e} w(v)\right)^{\frac{1}{|e|}}}$$
where:
- $E_{\text{forbidden}} \subseteq \{ e \in \mathcal{P}(V_O) \mid K \vdash \neg e \}$ is the set of **theoretically forbidden (counterfactual/excluded)** states (which therefore *do not occur* as positive empirical facts in the observed graph);
- $E_{\text{local}}$ is described as *"computed locally per node over its local hyperedge neighborhood ($E_{\text{local}}$)"* (L109).

This creates three mathematical failures:
1. **Unbounded Ratio ($\Gamma_{\text{relative}} > 1$):** Because $E_{\text{forbidden}}$ is not defined as a subset of $E_{\text{local}}$ ($E_{\text{forbidden}} \not\subseteq E_{\text{local}}$), the numerator can easily exceed the denominator, violating the claimed bound $0 < \text{EEC} \le 1$ on L157!
2. **Scope Mismatch ("per node" vs. global $K$):** L109 says $\Gamma_{\text{relative}}$ is computed *"locally per node over its local hyperedge neighborhood ($E_{\text{local}}$)"*, yet the left-hand side $\Gamma_{\text{relative}}(K)$ is a function of the **entire theory core $K$**, not a node $v$. Which node's neighborhood is $E_{\text{local}}$?
3. **Zero Boundary ($E_{\text{forbidden}} = \emptyset$ or $E_{\text{local}} = \emptyset$):** L157 states $0 < \text{EEC} \le 1$ (strict inequality $0 < \text{EEC}$), yet if $E_{\text{forbidden}} = \emptyset$ (a non-falsifiable theory, as discussed on L166), $\Gamma_{\text{relative}}(K) = 0 \implies \text{EEC}(K) = 0$. Conversely, if $E_{\text{local}} = \emptyset$, division by zero occurs.

**Fix.**
Define a single finite candidate space of empirical configurations $E_{\text{cand}}(K) \subseteq \mathcal{P}(V_O)$ (e.g., all evaluated empirical hyperedges in the domain of $K$, partitioned into $E_{\text{cand}}(K) = E_{\text{permitted}}(K) \uplus E_{\text{forbidden}}(K)$), with $E_{\text{forbidden}}(K) \subseteq E_{\text{cand}}(K)$:
$$\Gamma_{\text{relative}}(K) = \frac{\sum_{e \in E_{\text{forbidden}}(K)} \rho_e \cdot W(e)}{\sum_{e \in E_{\text{cand}}(K)} W(e)} \in [0, 1]$$
with $\Gamma_{\text{relative}}(K) := 0$ when $E_{\text{cand}}(K) = \emptyset$, and change the range on L157 to $0 \le \text{EEC} \le 1$.

---

### EEC-06 · Syntactic Content Class $S_v$ Commits a Measurement-Theoretic Category Error — **Major**

**Where.** [`empirical_content.md#L49-L66`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L49-L66).

**Finding.**
L51–54 claims:
> *"To mathematically justify continuous metric operations as a valid ratio scale, $S_v$ is formally grounded in Carnapian logical probability ($1 - P(h)$)... Rather than assigning arbitrary scalars, $S_v$ is defined via the following boundary conditions derived from the property set $P(v)$: $S_{\text{univ}} \to 1.0$, $S_{\text{cond}} = 1 - P(h \mid \text{antecedent})$, $S_{\text{sing}} < S_{\text{cond}}$, $S_{\text{exist}} \to 0.0$."*

1. **Ordinal inequalities do not define a ratio scale:** Specifying two limits ($\to 1.0, \to 0.0$) and one ordinal inequality ($S_{\text{sing}} < S_{\text{cond}}$) does **not** define a function $S_v \in (0, 1]$, nor does it establish a ratio scale (which in Representational Measurement Theory requires an empirical concatenation operation or invariant unit up to similarity transformation $x \mapsto \alpha x$; Krantz et al. 1971). An implementer has no formula to compute $S_v$ for any node!
2. **Wrong formula for conditional statement content ($S_{\text{cond}}$):** In Carnapian inductive logic and Popperian content theory, the logical content of a conditional $A \to H$ is $1 - P(A \to H) = P(A \land \neg H) = P(A) \cdot (1 - P(H \mid A))$, **not** $1 - P(H \mid A)$! Using $1 - P(H \mid A)$ ignores the probability of the antecedent $P(A)$: a conditional law with an impossible or ultra-rare antecedent ($P(A) \to 0$) is almost unfalsifiable (vacuously true almost everywhere), yet $1 - P(H \mid A)$ assigns it maximum content near $1.0$!
3. **Boundary Violation $S_{\text{exist}} \to 0.0$ vs. $w(v) \in (0, 1]$:** If $S_{\text{exist}} = 0$, then any hyperedge $e$ containing even one existential node has geometric mean $\left(\prod_{v \in e} w(v)\right)^{1/|e|} = 0$, annihilating the entire hyperedge weight.

**Fix.**
1. Correct the conditional content formula to $S_{\text{cond}} = P(\text{antecedent}) \cdot (1 - P(h \mid \text{antecedent})) = P(\text{antecedent} \land \neg h)$.
2. Provide explicit, deterministic reference values or a closed-form mapping from the node's syntactic quantifier type in $P(v)$ to $(0, 1]$ (and acknowledge that discrete syntactic classes form an ordinal/interval proxy, not a physical ratio scale).

---

### EEC-07 · Semantic Relevance Weight $\rho_e$ ("Mutual Information") Is Undefined for Deductively Excluded Edges — **Major**

**Where.** [`empirical_content.md#L90-L100`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L90-L100).

**Finding.**
L90–92 defines $\rho_e \in (0, 1]$ as:
> *"This factor quantifies the semantic and deductive cohesion (mutual information) between the theoretical postulates and the specific empirical configuration."*

1. **Classical Mutual Information Collapse:** For any deductively excluded hyperedge $e \in E_{\text{forbidden}}$, $K \vdash \neg e$, so $P(e \mid K) = 0$. Furthermore, under any fixed theory $K$, $K$ is a deterministic proposition, not a random variable with a marginal distribution, unless a prior measure over theories/models is specified. Even in Carnapian state-description space, if $K$ is tacked with an irrelevant law $H$ ($K' = K \land H$), a configuration $e_H$ forbidden solely by $H$ still has $P(e_H \mid K \land H) = 0$, so raw probabilistic dependence between $K'$ and $e_H$ is high—which is **why** Hempel's and Popper's probabilistic content measures fail the tacking paradox in the first place (Schurz 1991, 2014)!
2. **Schurz's Relevance Criterion is Proof-Theoretic, Not Mutual Information:** Schurz resolves the tacking paradox via **relevant deduction** (a conclusion is relevant iff no predicate in it is replaceable by an arbitrary predicate salvâ validitate, and every axiom in the core participates in unified derivations; see `semantic_homogeneity.md`), not via Shannon mutual information.

**Fix.**
Define $\rho_e(K) \in (0, 1]$ explicitly in graph/proof-theoretic or embedding terms: e.g., the fraction of minimal axiom subsets $Ax_0 \subseteq K$ entailing $\neg e$ that are connected to the core derivation component of $K$ (proof-theoretic relevance), or the cosine similarity between $e$ and the core axioms of $K$ in embedding space (semantic relevance proxy).

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### EEC-08 · Semantic Shift Between Statement-View Propositions ($V_O$) and Entity/Variable Nodes ($V_T, V_O$) — **Critical**

**Where.** [`empirical_content.md#L37-L66`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L37-L66) vs. [`#L120-L124`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L120-L124) vs. [`#L136`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L136).

**Finding.**
The document shifts between three incompatible ontological meanings of a "node" $v \in V$:
1. **In §The Syntactic Content Class (L49–65):** Nodes $v \in V_O$ are **propositions/sentences** classified as Universal ($\forall x (F(x) \to G(x))$), Conditional, Singular, or Existential ($\exists x F(x)$). Wait: in philosophy of science (Popper, Carnap, Schurz), a universal nomological law $\forall x (F(x) \to G(x))$ is a **theoretical/general hypothesis**, not an empirical observation node in $V_O$! And if $v \in V_O$ is already a full proposition, what is a hyperedge $e \subseteq V_O$?
2. **In §Formal Hypergraph Architecture (L34–38):** The hypergraph is introduced *"To preserve the full deductive expressiveness of predicate logic (including multi-place predicates and nested quantifiers)"*, where nodes $V_T, V_O$ are **terms/concepts/entities** and hyperedges $E$ are **multi-place predicates/propositions** connecting them!
3. **In §Epistemically Independent Mass & Parsimony (L120–136):** Nodes $v_i, v_j \in V_O$ are **random variables** in a causal Bayesian network (subject to $d$-separation), while $k_T = |V_T|$ is called *"the number of independent theoretical postulates ($k_T = |V_T|$)"* (L136)—shifting $V_T$ from "theoretical constructs" (L37, i.e. terms/concepts) to "independent theoretical postulates" (L136, i.e. axioms)!

**Impact.**
This three-way ontological shift makes it impossible to map a `TheoryGraph` onto $H = (V, E, P)$: are $V_O$ and $V_T$ `L2Entity` concepts (terms) connected by propositional hyperedges, or are $V_O$ and $V_T$ `TheoryAtom` propositions ($B$ and $A$) connected by inference hyperedges?

**Fix.**
Align strictly with Episteme's Layer 3 / Bipartite Inference Graph architecture (`ISSUE-055`):
- **Propositional nodes ($V = V_B \uplus V_A$):** $V_B$ are empirical/observation propositions (carrying $S_v$ and $R_v$), $V_A$ are theoretical axioms/postulates ($k_T = |V_A^{\text{axiom}}|$).
- **Hyperedges ($E$):** Joint inference / conflict / constraint hyperedges over $V_B \cup V_A$.

---

### EEC-09 · Semantic Shift to "LPG-ECHO Algorithm" for Combinatorial Power-Set Synthesis — **Major**

**Where.** [`empirical_content.md#L108-L110`](../../../docs/concepts/theory/metrics/empirical_power/empirical_content.md#L108-L110).

**Finding.**
L108–110 states:
> *"Furthermore, to bypass the combinatorial explosion inherent to full power-set evaluation over $V_O$, the restrictive power is currently computed locally per node over its local hyperedge neighborhood ($E_{\text{local}}$), pending global synthesis via the LPG-ECHO algorithm."*

The LPG-ECHO algorithm ([`adapted_echo_algorithm.md`](../../../docs/concepts/theory/metrics/adapted_echo_algorithm.md)) is a connectionist Hopfield relaxation algorithm over existing positive and negative binary edges that outputs node activations $a_i^* \in [-1, 1]$. It does **not** enumerate, synthesize, or approximate the power set $\mathcal{P}(V_O)$ of deductively forbidden hyperedges $\{e \in \mathcal{P}(V_O) \mid K \vdash \neg e\}$. Invoking LPG-ECHO as a pending solver for power-set deductive exclusion is a conceptual non-sequitur.

**Fix.**
Remove the claim that LPG-ECHO computes power-set deductive exclusion. Instead, state explicitly that in graph implementations, $E_{\text{forbidden}}(K)$ is approximated by the set of explicit negative/inhibitory/conflict edges (`CONTRADICTS`, `REFUTES`, `EXCLUDES`) and falsifier nodes attached to $K$ in the extracted graph.

---

## 4. Is the Metric Valid and Scientifically Significant?

### EEC-10 · Scientific Significance vs. Operational Tractability in Text-Extracted Graphs — **Major**

**Finding.**
From a philosophy of science standpoint, combining Popperian falsifiability (forbidden states), Carnapian syntactic generality ($S_v$), Goldman/Quinean reliabilist inferential distance ($R_v = e^{-\beta d_v}$), Schurz's relevance filter ($\rho_e$), diversity-discounted empirical mass ($M_w$), and a parsimony regularizer ($\exp(-\lambda k_T / M_w)$) is a genuinely thoughtful, multi-factor conceptualization of *effective* empirical content.

However, as an **executable metric in `epistemetrics`**, it suffers from a severe operationalization gap:
1. **No hypergraph in `epistemetrics`:** `TheoryGraph` (`packages/epistemetrics/src/epistemetrics/graph/theory_graph.py`) is a directed multigraph of binary `TheoryEdge` objects, not an attributed hypergraph $H = (V, E, P)$.
2. **Forbidden states are rarely stated in prose:** Scientific and philosophical authors almost always state what their theory *asserts* or *explains* ($K \vdash e$), not the exponential list of counterfactual empirical configurations it *forbids* ($K \vdash \neg e$). Unless the pipeline actively generates or extracts falsifiers (potential falsifiers in Popper's sense) or treats incompatible rival observations in $V_O$ as $E_{\text{forbidden}}$, $E_{\text{forbidden}}$ will be empty ($\text{EEC} = 0$) for most extracted graphs.

**Fix.**
Provide a concrete **Graph Operationalization Section** (currently missing from `empirical_content.md`, unlike the other three files!) specifying:
1. How $d_v$ (inferential path length to basal measurement) is computed on `TheoryGraph` (e.g., shortest path length from $v$ to a grounded `EVIDENCE` / `DATAPOINT` node, or LLM proxy).
2. How $E_{\text{forbidden}}(K)$ and $E_{\text{cand}}(K)$ are extracted from binary/bipartite graph edges (e.g., rival observation nodes attacked by $K$, or explicit falsification conditions).
3. Default hyperparameter values for $\beta > 0$ (in $R_v = e^{-\beta d_v}$) and $\lambda > 0$ (in $\text{DoF}_w = \exp(-\lambda k_T / M_w)$), without which $\text{EEC}(K)$ is uncalibrated.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Missing Standard Sections:** Unlike `empirical_adequacy.md`, `explanatory_breadth.md`, and `theoretical_achievements.md`, `empirical_content.md` does **not** follow the standard template (`## Definition & Conceptual Goal`, `## Theoretical Grounding & Model Formulation`, `## Mathematical Specification & Graph Formulation`, `## Measurement & Graph Implementation`, `## Diagnostic & Metascientific Value`, `## Grounding References`). In particular, it has **no `## Measurement & Graph Implementation` section** and **no `## Grounding References` section** (references to Carnap, Schurz, Popper, Lakatos, Quine, Goldman, Sneed are made in-line without bibliographic entries).
2. **Dangling Bullet Point & Missing Period (L66, L77):** Line 66 contains an empty bullet `*`, and Line 77 ends mid-sentence without a period (`...ensuring valid continuous metric operations downstream`).
3. **Version Header Artifact (L9):** Contains `**(Hypergraph-Theoretic & Reliabilist Framework – Version 2.1)**`, which looks like an internal prompt/draft artifact rather than canonical documentation style.
