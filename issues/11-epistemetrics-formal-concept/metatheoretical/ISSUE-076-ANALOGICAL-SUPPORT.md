# [ISSUE-076] Formal & Conceptual Evaluation: Analogical Support (`analogical_support.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-076` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 5: Metatheoretical Framework |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/metatheoretical/analogical_support.md`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (computes $k$-step random-walk reachability instead of regular equivalence, evaluates to $0$ on disconnected cross-domain subgraphs, divides by zero on sink nodes, and violates its claimed $[0, 1)$ range) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-082`](../ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md), [`ISSUE-009`](../../03-epistemic-metrics/ISSUE-009-global-qbaf-solvers-and-thagardian-harmony.md), [`ISSUE-067`](../../10-formal-conceptual-docs/ISSUE-067-mathematical-errors-in-formalisms.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Inverted)** | Claims to measure cross-domain **regular equivalence** (structural role isomorphism between hypotheses in separate domains that share no neighbors or direct paths). Instead, $\text{Sim}_{\text{reg}}^{(k)}(H_1, H_2) = \sum_{r=1}^k \alpha^r ((\mathbf{D}^{-1}\mathbf{A})^r)_{H_1, H_2}$ computes **$k$-step random-walk transition probability from $H_1$ to $H_2$**. For two hypotheses in separate domain subgraphs with no path of length $\le k=3$ between them, the score is identically $0$. |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) $\mathbf{D}^{-1}$ is **singular** (division by zero) whenever any node has out-degree $0$ ($D_{ii} = 0$, e.g. leaf claims or evidence sinks); (2) $LAB_{\text{norm}}(H_1)$ lies in $(-1, 1)$, not $[0, 1)$, because $a_{H_2}(t) \in [-1, 1]$ can be negative; (3) $\text{Sim}_{\text{reg}}^{(k)}(H_1, H_2) \neq \text{Sim}_{\text{reg}}^{(k)}(H_2, H_1)$ is asymmetric, breaking ECHO weight symmetry. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Shifts from (a) **role isomorphism** between non-adjacent subgraphs (L34–46) to (b) **Markov random-walk proximity** on a connected graph (L63–73), and from (c) an **excitatory-only boost** (L105–107) to (d) a **signed activation sum** that inhibits $H_1$ whenever a cross-domain neighbor has $a_{H_2}(t) < 0$ (L121). |
| **4. Valid & Scientifically Significant?** | **Conceptually Valid, Formally Broken** | Analogical transfer (Thagard 1989, Principle E3; Gentner 1983) is scientifically significant, but requires structural role similarity (e.g., RoleSim, Struct2Vec, or relational motif isomorphism) rather than $k$-hop walk reachability between $H_1$ and $H_2$. |

---

## 1. Does the Metric Capture What It Claims It Does?

### AS-01 · $\text{Sim}_{\text{reg}}^{(k)}(H_1, H_2)$ Computes $k$-Step Random-Walk Reachability Between $H_1$ and $H_2$, Not Regular Equivalence — **Critical**

**Where.** [`analogical_support.md#L34-L46`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L34-L46) vs. [`#L61-L73`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L61-L73).

**Finding.**
In §Graph-Theoretical Foundations (L34–46), the document correctly characterizes scientific analogy and regular equivalence:
> *"Genuine scientific analogies are characterized by the fact that two hypotheses from different fields share hardly any common technical terms or direct connecting edges, but occupy **the same relational roles** in their respective subnetworks... Two nodes $H_1$ and $H_2$ are similar if they have neighbor nodes that are themselves similarly structured – even if $H_1$ and $H_2$ do not share a single common neighbor."*

However, in Step 1 (L73), "Bounded Regular Equivalence" is defined as:
$$\text{Sim}_{\text{reg}}^{(k)}(H_1, H_2) = \sum_{r=1}^{k} \alpha^r \cdot \left( (\mathbf{D}^{-1}\mathbf{A})^r \right)_{H_1, H_2}$$
with default $k = 3$.

**Why this mathematically contradicts regular equivalence.**
Let $\mathbf{P} = \mathbf{D}^{-1}\mathbf{A}$ be the row-normalized random-walk transition matrix. The $(H_1, H_2)$-entry of $\mathbf{P}^r$ is the probability that a directed walk starting at node $H_1$ arrives at node $H_2$ in **exactly $r$ steps**:
$$\left((\mathbf{D}^{-1}\mathbf{A})^r\right)_{H_1, H_2} > 0 \iff \text{there exists a directed path } H_1 \to v_1 \to \dots \to H_2 \text{ of length } r \le k.$$
This causes two fatal inversions of the construct:
1. **Zero Score on Genuine Cross-Domain Analogies:** Consider the document's own canonical example (L12–13): $H_1$ is the acoustic wave equation in domain $D_1$ (acoustics) and $H_2$ is the water wave equation in domain $D_2$ (hydrodynamics). Each sits at the center of an isomorphic derivation subgraph within its own discipline, with **no direct edges or $\le 3$-hop paths connecting $H_1$ to $H_2$**. Because $\text{dist}_G(H_1, H_2) > 3$ (or $\infty$), $\left((\mathbf{D}^{-1}\mathbf{A})^r\right)_{H_1, H_2} = 0$ for all $r \in \{1, 2, 3\}$, yielding:
   $$\text{Sim}_{\text{reg}}^{(3)}(H_1, H_2) = 0 \implies w_{\text{analogy}}(H_1, H_2) = 0 \implies LAB_{\text{norm}}(H_1) = 0.$$
2. **Maximum Score on Direct Cross-Domain Edges ($r = 1$):** Conversely, $\text{Sim}_{\text{reg}}^{(k)}(H_1, H_2)$ is **maximized** when $H_1$ has a direct $1$-hop outgoing edge to $H_2$ ($A_{H_1, H_2} > 0$), even if $H_1$ is a leaf claim and $H_2$ is a root axiom with completely opposite structural roles! Thus the formula measures **local random-walk proximity**, the exact opposite of role equivalence.

**Fix.**
Replace path-reachability between $H_1$ and $H_2$ with a genuine **bounded regular equivalence / structural role similarity** metric:
- **Option A (Iterative Regular Equivalence — Leicht, Holme & Newman 2006 / Newman 2018, §7.12):**
  Compute the $k$-step iterative role similarity matrix $\mathbf{\Sigma}^{(k)}$ where two nodes are similar if their neighbors are similar:
  $$\mathbf{\Sigma}^{(0)} = \mathbf{I}, \qquad \mathbf{\Sigma}^{(r)} = \alpha \, \mathbf{D}^{-1} \mathbf{A} \, \mathbf{\Sigma}^{(r-1)} \, (\mathbf{D}^{-1} \mathbf{A})^\top + \mathbf{I}$$
  (or via RoleSim / Cooper & Barahona 2010 signature vectors).
- **Option B ($k$-Hop Typed Role Profile Cosine Similarity):**
  For each node $H$, construct its $k$-hop typed structural role vector $\boldsymbol{\psi}^{(k)}(H) \in \mathbb{R}^{d}$ (recording at each hop $r \in \{1, \dots, k\}$ the $\alpha^r$-damped distribution of incoming/outgoing edge types `EXPLAINS`, `SUPPORTS`, `ATTACKS`, `SPECIALIZES`, `CONSTRAINS` and degree quartiles), and define:
  $$\text{Sim}_{\text{reg}}^{(k)}(H_1, H_2) = \frac{\boldsymbol{\psi}^{(k)}(H_1) \cdot \boldsymbol{\psi}^{(k)}(H_2)}{\|\boldsymbol{\psi}^{(k)}(H_1)\|_2 \, \|\boldsymbol{\psi}^{(k)}(H_2)\|_2} \in [0, 1].$$
  This is symmetric, bounded in $[0, 1]$, requires no path between $H_1$ and $H_2$, and runs in $O(k|E|)$ time.

---

### AS-02 · Collapse of Multi-Relational Edge Types & Omission of Thagard's Relational Pair Matching — **Major**

**Where.** [`analogical_support.md#L17`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L17), [`#L63-L73`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L63-L73), [`#L132`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L132).

**Finding.**
1. **Loss of Edge Polarity and Relation Types:** The adjacency matrix $\mathbf{A}$ is defined as an untyped non-negative matrix $A_{ij} \ge 0$ (L132). In `TheoryGraph` (`epistemetrics/core/models.py`), edges carry distinct semantic types and polarities (`EXPLAINS` $+1$, `SUPPORTS` $+1$, `ATTACKS` $-1$, `SPECIALIZES` $0$, `CONSTRAINS` $0$). Collapsing them into a single scalar matrix $\mathbf{A}$ means a hypothesis $H_1$ that **attacks** 4 propositions has the exact same transition structure as a hypothesis $H_2$ that **explains** 4 empirical phenomena.
2. **Deviation from Thagard's Principle E3 (Analogy):** In Thagard (1989, p. 437), analogy is defined over **pairs of explanatory relations**: if $P_1$ explains $Q_1$ and $P_2$ explains $Q_2$, and $P_1 \sim P_2$ while $Q_1 \sim Q_2$, then excitatory analogy links connect $P_1 \leftrightarrow P_2$ and $Q_1 \leftrightarrow Q_2$. Evaluating node degrees in isolation ignores whether the explananda $Q_1, Q_2$ also occupy analogous positions.

**Fix.**
Restrict the structural role comparison to the **explanatory/deductive subgraph** ($E_{\text{exp}} \cup E_{\text{sup}}$) or stratify the role profile $\boldsymbol{\psi}^{(k)}(H)$ by `RelationType` and polarity so that explanatory hubs are only matched with explanatory hubs.

---

## 2. Is the Metric Formally & Mathematically Correct?

### AS-03 · Range Error in $LAB_{\text{norm}}(H_1)$ and Violation of Non-Inhibitory Guarantee When $a_{H_2}(t) < 0$ — **Critical**

**Where.** [`analogical_support.md#L105-L107`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L105-L107), [`#L115-L121`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L115-L121), [`#L135-L136`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L135-L136).

**Finding.**
In Step 3 (L115–121), the specification defines:
$$LAB_{\text{norm}}(H_1) = \tanh \left( \sum_{H_2 \in V \setminus \{H_1\}} w_{\text{analogy}}(H_1, H_2) \cdot a_{H_2}(t) \right)$$
where $a_{H_2}(t) \in [-1, 1]$ (L115, L135), and claims:
- L106–107: *"This guarantees that analogies always form excitatory (supporting) connections and never falsely generate inhibitory (contradictory) edges."*
- L117: *"the hyperbolic tangent ($\tanh$) is applied as a saturation function mapping the input onto the interval $[0, 1)$"*
- L136: *"$LAB_{\text{norm}}(H_1)$ | Real number in the interval $[0, 1)$"*

**Why this is mathematically false.**
Because $w_{\text{analogy}}(H_1, H_2) \ge 0$ and $a_{H_2}(t) \in [-1, 1]$, any disconfirmed or rejected cross-domain hypothesis with $a_{H_2}(t) < 0$ contributes a **negative** term $w_{\text{analogy}}(H_1, H_2) a_{H_2}(t) < 0$.
1. When the weighted sum is negative, $\tanh(\cdot) < 0$, so the range of $LAB_{\text{norm}}(H_1)$ is $(-1, 1)$, **not** $[0, 1)$!
2. Epistemologically, a negative term means that if an analogous hypothesis $H_2$ in another domain is refuted ($a_{H_2} < 0$), $H_1$ receives **inhibitory disconfirmation** ("guilt by structural analogy"), directly violating L106–107 and Thagard (1989, p. 437), who explicitly restricts analogy to positive excitation rather than inhibition.

**Fix.**
Rectify the source activation via $\max(0, a_{H_2}(t))$ (ReLU) so that only corroborated hypotheses ($a_{H_2}(t) > 0$) transmit positive analogical support:
$$LAB_{\text{norm}}(H_1) = \tanh \left( \sum_{H_2 \in V \setminus \{H_1\}} w_{\text{analogy}}(H_1, H_2) \cdot \max\big(0, a_{H_2}(t)\big) \right) \in [0, 1).$$

---

### AS-04 · Singular Degree Matrix $\mathbf{D}^{-1}$ (Division by Zero on Sink Nodes) — **Critical**

**Where.** [`analogical_support.md#L63-L66`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L63-L66), [`#L73`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L73), [`#L133`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L133).

**Finding.**
L64–65 defines $\mathbf{D}$ as the diagonal out-degree matrix $D_{ii} = \sum_j A_{ij}$ ("the total number or sum of weights of all outgoing edges from node $i$") and multiplies by $\mathbf{D}^{-1}$ in $(\mathbf{D}^{-1}\mathbf{A})^r$.
In any directed `TheoryGraph` (and in every DAG!), sink nodes have no outgoing edges, so $D_{ii} = 0$. Therefore $\det(\mathbf{D}) = 0$ and $\mathbf{D}^{-1}$ **does not exist**.

**Fix.**
Replace $\mathbf{D}^{-1}$ with the Moore–Penrose pseudoinverse $\mathbf{D}^+$:
$$D^+_{ii} = \begin{cases} D_{ii}^{-1} & \text{if } D_{ii} > 0 \\ 0 & \text{if } D_{ii} = 0 \end{cases}$$
and state this explicitly in the parameter table (L133).

---

### AS-05 · Asymmetry of $w_{\text{analogy}}(H_1, H_2) \neq w_{\text{analogy}}(H_2, H_1)$ Breaks ECHO Lyapunov Convergence — **Major**

**Where.** [`analogical_support.md#L73`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L73), [`#L96`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L96).

**Finding.**
Even if the underlying graph $\mathbf{A}$ is undirected ($A_{ij} = A_{ji}$), the row-normalized random-walk matrix $\mathbf{P} = \mathbf{D}^+\mathbf{A}$ is **asymmetric** whenever node degrees differ ($P_{ij} = A_{ij}/D_{ii} \neq A_{ji}/D_{jj}$). On a directed graph, $(\mathbf{D}^+\mathbf{A})^r$ is even more asymmetric.
Consequently:
$$w_{\text{analogy}}(H_1, H_2) \neq w_{\text{analogy}}(H_2, H_1).$$
However, Thagard's ECHO model (`adapted_echo_algorithm.md`, `system_coherence.md`, Principle E1 Symmetry) requires symmetric constraint weights $w_{ij} = w_{ji}$ so that the global Harmony function $H(t) = \sum_{i,j} w_{ij} a_i(t) a_j(t)$ acts as a strict Lyapunov function guaranteeing convergence to a fixed point rather than limit-cycle oscillations.

**Fix.**
Use a symmetric similarity kernel (such as cosine similarity over role vectors $\boldsymbol{\psi}^{(k)}$ in AS-01, or symmetric normalization $\mathbf{D}^{-1/2}\mathbf{A}\mathbf{D}^{-1/2}$ if comparing spectral profiles), ensuring $w_{\text{analogy}}(H_1, H_2) = w_{\text{analogy}}(H_2, H_1)$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### AS-06 · Semantic Shift Between Disjoint Role Isomorphism and Local Walk Reachability — **Major**

**Where.** [`analogical_support.md#L34-L53`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L34-L53) $\to$ [`#L63-L88`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L63-L88).

**Finding.**
- In §Graph-Theoretical Foundations (L44–53), the "$k$-hop neighborhood" is introduced as the local radius around $H_1$ and the local radius around $H_2$ within which each node's **relational role** is inspected (*"even if $H_1$ and $H_2$ do not share a single common neighbor"*).
- In §Mathematical Formulation (L67–73), the "$k$-hop neighborhood" silently shifts meaning to paths of length $r \le k$ **connecting $H_1$ directly to $H_2$**.
- This conflict becomes acute when combined with the domain filter $\phi_{\text{domain}}(H_1, H_2)$ (L101): if domains $\text{Dom}(H)$ are identified via Leiden community detection (Phase 5 Fusion), communities are precisely dense subgraphs separated by sparse inter-community cuts. Thus, pairs with $\phi_{\text{domain}}(H_1, H_2) = 1$ ($\text{Dom}(H_1) \neq \text{Dom}(H_2)$) are systematically those with the lowest walk probability $((\mathbf{D}^{-1}\mathbf{A})^r)_{H_1, H_2}$!

**Fix.**
Keep the $k$-hop neighborhood strictly as the radius used to extract each node's local structural signature $\boldsymbol{\psi}^{(k)}(H_i)$ within its own domain $\text{Dom}(H_i)$, and then compare $\boldsymbol{\psi}^{(k)}(H_1)$ with $\boldsymbol{\psi}^{(k)}(H_2)$ across domains.

---

### AS-07 · Semantic Shift Between Post-Hoc Metric and Intra-Loop ECHO Relaxation Term — **Major**

**Where.** [`analogical_support.md#L113-L121`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L113-L121), [`adapted_echo_algorithm.md#L104-L105`](../../../docs/concepts/theory/metrics/adapted_echo_algorithm.md#L104-L105).

**Finding.**
L117–121 states that $\tanh$ is applied to $LAB_{\text{norm}}(H_1)$ to *"prevent the target hypothesis from accumulating infinitely high activation values... and ensure mathematical stability and convergence during network relaxation."*
This conflates two distinct architectural roles:
1. **Intra-Loop Edge Weight ($w_{\text{analogy}}(H_1, H_2)$):** Inside the LPG-ECHO relaxation loop (`adapted_echo_algorithm.md` L27), activation updates already bound $a_j(t+1) \in [-1, 1]$ via the damping factor $(a_{\max} - a_j(t))$ using raw linear net input $\text{net}_j(t) = \sum_i w_{ij} a_i(t)$. Injecting a pre-squashed $\tanh$ term inside $\text{net}_j(t)$ alters the fixed-point equations and invalidates the quadratic Harmony function $H(t)$.
2. **Post-Convergence Diagnostic Metric ($LAB_{\text{norm}}(H_1)$):** When reported to the user as a standalone metatheoretical metric after solver convergence, $a_{H_2}(t)$ must be the converged equilibrium activation $a_{H_2}^*$ (or calibrated D-QBAF justification degree $\tau^*(H_2)$ from `qbaf.py`).

**Fix.**
Explicitly distinguish the **static cross-domain analogy weight** $w_{\text{analogy}}(H_1, H_2)$ (which enters the ECHO/QBAF adjacency matrix linearly) from the **post-convergence diagnostic score** $LAB_{\text{norm}}(H_1)$ evaluated at equilibrium $a_{H_2}^*$.

---

## 4. Is the Metric Valid and Scientifically Significant?

### AS-08 · Misattributed Grounding References & Missing Network Role-Equivalence Citations — **Major**

**Where.** [`analogical_support.md#L140-L147`](../../../docs/concepts/theory/metrics/metatheoretical/analogical_support.md#L140-L147).

**Finding.**
The reference list cites Balzer, Moulines & Sneed (1987) and Stegmüller (1976), neither of whom formulates regular equivalence, Katz damping, or connectionist analogical boost. Meanwhile, the foundational papers for regular equivalence in networks (White & Reitz 1983; Leicht, Holme & Newman 2006) and structure-mapping in scientific analogy (Gentner 1983) are omitted.

**Fix.**
Cite White & Reitz (1983), Leicht, Holme & Newman (2006), and Gentner (1983) alongside Thagard (1989, p. 437) and Newman (2018, §7.12).

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Undefined Domain Function $\text{Dom}(H)$ in `TheoryGraph` (L27, L101):** `TheoryNode` in `packages/epistemetrics/src/epistemetrics/core/models.py` has no `domain` attribute. Specify how $\text{Dom}(H)$ is resolved (e.g., `node.attributes.get("domain")` or `theory_net_id` / Leiden partition index from `PartitionResult`).
2. **Typo in Step 1 Prose (L63, L67):** `"Let A $\mathbf{A}$ be the adjacency matrix"` (duplicate `A`) and `"where he $r$-th power"` (`he` $\to$ `the`).
3. **Unmatched Parenthesis in Step 2 (L98–107):** Opens a parenthesis on L98 `(Where $\phi_{\text{domain}}...` and closes it 9 lines later at the end of a bullet point on L107 `...inhibitory (contradictory) edges).`.
4. **Template Divergence:** Unlike the other 5 files in `metatheoretical/`, `analogical_support.md` lacks an H1 title (`# Analogical Support`) and uses custom section headers (`Introduction & Epistemological Purpose`, `Graph-Theoretical Foundations`, etc.) instead of the standard 6-section metric template.
