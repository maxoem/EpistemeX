# [ISSUE-093] Formal & Conceptual Evaluation: System Coherence / Harmony (`system_coherence.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-093` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 2: Epistemic Coherence & Parsimony |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md) |
| **Target Package(s)** | `epistemetrics`, `episteme-pipeline` |
| **Priority** | **Critical** (quadratic product $w_{ij} a_i^* a_j^*$ treats two mutually rejected hypotheses $(-1) \times (-1) = +1$ as identical to two mutually accepted hypotheses $(+1) \times (+1) = +1$, allowing a completely falsified theory to score $SCS(G) = +1.0$, while synchronous updates on symmetric matrices admit period-2 limit cycles) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-091`](ISSUE-091-NODE-ACTIVATION.md), [`ISSUE-095`](../ISSUE-095-EPISTEMIC-COHERENCE-CROSS-CUTTING.md), [`ISSUE-009`](../../03-epistemic-metrics/ISSUE-009-global-qbaf-solvers-and-thagardian-harmony.md), [`ISSUE-066`](../../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md), [`ISSUE-068`](../../10-formal-conceptual-docs/ISSUE-068-conceptual-and-domain-errors.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Sign-Flip Symmetry Trap)** | Claims to quantify *"maximizing simultaneous activation of mutually supportive (excitatory) propositions while minimizing simultaneous activation of contradictory (inhibitory) claims"*. However, because $a_i(t) \in [-1, 1]$, the product $a_i a_j$ is invariant under sign inversion: two mutually supporting hypotheses that are **both decisively rejected** ($a_i^* = -1, a_j^* = -1$) yield $w_{ij}(-1)(-1) = +w_{ij} > 0$, so a completely refuted theory scores $SCS(G) = +1.0$ ("Highly Harmonious & Coherent")! |
| **2. Formally & Mathematically Correct?** | **No (Critical/Major Flaws)** | (1) Division by zero in $SCS(G)$ when the graph has no edges ($\sum \|w_{ij}\| = 0$); (2) Omits Thagard's $\frac{1}{2}$ factor in $H(t)$, double-counting every undirected constraint edge; (3) Step 2 specifies a **synchronous** relaxation loop on $W = W^\top$, which is known in Hopfield/Ising dynamics to admit period-2 oscillations where $\Delta H = 0$ while $\|\mathbf{a}(t+1) - \mathbf{a}(t)\| \not\to 0$; (4) Quadratic scaling $SCS \propto (\bar{a}^*)^2$ makes the $SCS > 0.7$ threshold unreachable under standard $\theta = 0.05$ ECHO equilibria. |
| **3. Free of Semantic Shifts?** | **No (Major Shifts)** | Conflates **global constraint-satisfaction energy of a multi-rival debate network** (where rejecting a rival theory increases network harmony $H$) with **internal epistemic coherence of a target theory** (whether the theory's own hypotheses and evidence mutually reinforce). Also assumes symmetric undirected weights $w_{ij} = w_{ji}$ while `TheoryGraph` and `qbaf.py` are directed and asymmetric. |
| **4. Valid & Scientifically Significant?** | **Valid with Rectification & Symmetrization** | Thagard's (1989) Harmony / constraint-satisfaction coherence is a classic model in cognitive philosophy of science, but must distinguish accepted-support satisfaction from rejected-support satisfaction when evaluating a single theory, and needs an explicit bridge to Episteme's directed D-QBAF (`qbaf.py`). |

---

## 1. Does the Metric Capture What It Claims It Does?

### SC-01 · Sign-Inversion Symmetry $(-1) \times (-1) = +1$ Awards Maximal Coherence $SCS(G) = 1.0$ to Completely Falsified Theories — **Critical**

**Where.** [`system_coherence.md#L15-L17`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L15-L17), [`#L39-L47`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L39-L47), [`#L60-L63`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L60-L63).

**Finding.**
L15–17 defines the conceptual goal of System Coherence as:
> *"maximizing simultaneous activation of mutually supportive (excitatory) propositions while minimizing simultaneous activation of contradictory (inhibitory) claims."*

And L41–45 defines:
$$H(t) = \sum_{i=1}^N \sum_{j=1}^N w_{ij} a_i(t) a_j(t), \qquad SCS(G) = \frac{H(t^*)}{\sum_{i=1}^N \sum_{j=1}^N |w_{ij}|}$$
with $a_i(t) \in [-1, 1]$, $w_{ij} > 0$ for excitatory (support/explanatory) links, and $w_{ij} < 0$ for inhibitory (contradiction) links.

**Counterexample (Total Theory Refutation Yields $SCS(G) = +1.0$):**
Consider a theory consisting of mutually supporting hypotheses $H_1, \dots, H_k$ connected by positive explanatory links ($w_{ij} > 0$), all of which are contradicted ($w_{iE} < 0$) by clamped empirical evidence $E$ ($a_E^* = +1.0$) so that at equilibrium every hypothesis of the theory is decisively rejected:
$$a_1^* = -1.0, \; a_2^* = -1.0, \; \dots, \; a_k^* = -1.0.$$
Evaluate each term in $H(t^*)$:
1. On every supportive link $w_{ij} > 0$ between rejected hypotheses $H_i$ and $H_j$:
   $$w_{ij} a_i^* a_j^* = w_{ij} (-1.0)(-1.0) = +w_{ij} = |w_{ij}| > 0!$$
2. On every inhibitory falsification link $w_{iE} < 0$ between rejected hypothesis $H_i$ and accepted evidence $E$:
   $$w_{iE} a_i^* a_E^* = (-|w_{iE}|)(-1.0)(+1.0) = +|w_{iE}| > 0!$$
Summing over all edges gives $H(t^*) = \sum_{i,j} |w_{ij}|$, and therefore:
$$SCS(G) = \frac{\sum_{i,j} |w_{ij}|}{\sum_{i,j} |w_{ij}|} = +1.0 > 0.70!$$
The Diagnostic Table (L61) classifies this completely falsified theory as:
> **"High $SCS$ ($> 0.7$): Highly Harmonious & Coherent — Hypotheses and evidence mutually reinforce without unresolved contradictions."**

**Why this happens.**
In Hopfield (1982) spin-glass networks and Thagard (1989, p. 443), the quadratic form $\mathbf{a}^\top W \mathbf{a}$ measures **global constraint satisfaction of a bipolar assignment** (where setting two positively linked propositions to the same truth value—including both `False` $(-1, -1)$—satisfies the material biconditional $P \leftrightarrow Q$). While $H(t)$ is a valid Lyapunov objective for the relaxation solver when deciding *which* rival theory to reject, reporting $SCS(G) = \frac{\mathbf{a}^{*\top} W \mathbf{a}^*}{\sum |w_{ij}|}$ as the epistemic coherence of a theory conflates **"all hypotheses of the theory are jointly accepted"** ($(+1)(+1) = +1$) with **"all hypotheses of the theory are jointly rejected"** ($(-1)(-1) = +1$)!

**Fix.**
Separate the **Solver Lyapunov Energy $H_{\text{ECHO}}(t)$** from the **Theory System Coherence Score $SCS(G)$**:
1. **For Solver Convergence Telemetry ($H_{\text{ECHO}}$):** Keep $H(t) = \frac{1}{2} \sum_{i,j} w_{ij} a_i(t) a_j(t)$ as the internal constraint-satisfaction energy of the bipolar solver.
2. **For Theory Epistemic Coherence Evaluation ($SCS(G)$):** Use **positive acceptance activations** $a_i^+ = \max(0, a_i^*) \in [0, 1]$ (or D-QBAF justification degrees $s_i^* \in [0, 1]$ from `qbaf.py`) so that only *accepted* mutually supporting claims contribute positive coherence and simultaneously accepted contradictory claims subtract coherence:
   $$SCS(G) = \frac{\sum_{(i,j) \in \mathcal{R}_{sup}} w_{ij}^+ \, a_i^+ a_j^+ - \sum_{(i,j) \in \mathcal{R}_{att}} |w_{ij}^-| \, a_i^+ a_j^+}{\sum_{i,j} |w_{ij}|} \in [-1, 1].$$
   Under this formulation, a refuted theory ($a_i^* \le 0 \implies a_i^+ = 0$) scores $SCS = 0.0$ rather than $+1.0$, and any unresolved contradiction between two simultaneously accepted claims ($a_i^+ > 0, a_j^+ > 0$ with $(i, j) \in \mathcal{R}_{att}$) strictly penalizes $SCS(G)$.

---

## 2. Is the Metric Formally & Mathematically Correct?

### SC-02 · Synchronous Relaxation on Symmetric $W$ Admits Period-2 Limit Cycles & Contradictory Stopping Criteria — **Major**

**Where.** [`system_coherence.md#L47`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L47) vs. [`#L53-L55`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L53-L55).

**Finding.**
1. **Two Inconsistent Convergence Criteria (L47 vs. L54):**
   - L47 defines $t^*$ as the iteration where the scalar Harmony change satisfies $\Delta H(t^*) = |H(t^*) - H(t^*-1)| < \epsilon_{\text{tol}}$.
   - L54 defines convergence as the vector state change satisfying $\|\mathbf{a}(t+1) - \mathbf{a}(t)\| < 10^{-4}$.
2. **Period-2 Limit Cycles Under Synchronous Updates:**
   Step 2 (L54) specifies a **Synchronous Relaxation Loop** on a symmetric matrix $W = W^\top$. By a classic theorem on symmetric discrete-time dynamical networks (Goles, Fogelman-Soulie & Pellegrin 1985), while *asynchronous* updates strictly increase $H(t)$ and converge to fixed points, *synchronous* updates on a symmetric matrix $W = W^\top$ can converge to **period-2 limit cycles** ($\mathbf{a}(t+2) = \mathbf{a}(t)$ with $\mathbf{a}(t+1) \neq \mathbf{a}(t)$).
   On a period-2 cycle:
   - $H(t+1) = H(t)$, so $\Delta H(t) = 0 < \epsilon_{\text{tol}}$ triggers immediately on L47 even though the network is oscillating between two opposite states!
   - Meanwhile, $\|\mathbf{a}(t+1) - \mathbf{a}(t)\| \gg 10^{-4}$ on L54 never terminates!

**Fix.**
Use **asynchronous** (or damped / continuous ODE) updates and define convergence strictly on the state vector norm $\|\mathbf{a}(t+1) - \mathbf{a}(t)\|_\infty < \epsilon_{\text{tol}}$ with a maximum iteration guard $T_{\max}$.

---

### SC-03 · Division by Zero on Edgeless Graphs & Missing $\frac{1}{2}$ Prefactor in $H(t)$ — **Major**

**Where.** [`system_coherence.md#L41-L45`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L41-L45).

**Finding.**
1. **Division by Zero when $E = \emptyset$:**
   In $SCS(G) = \frac{H(t^*)}{\sum_{i=1}^N \sum_{j=1}^N |w_{ij}|}$ (L45), if a theory subgraph has no edges ($\sum_{i,j} |w_{ij}| = 0$), the denominator is $0$.
2. **Missing $\frac{1}{2}$ Factor vs. Thagard (1989, p. 443):**
   Because $w_{ij} = w_{ji}$ is symmetric (L32–33), summing $\sum_{i=1}^N \sum_{j=1}^N w_{ij} a_i(t) a_j(t)$ counts every undirected constraint $\{i, j\}$ twice. Thagard (1989, p. 443, Eq. 2) writes $H = \frac{1}{2} \sum_i \sum_j w_{ij} a_i a_j$ (or $\sum_{i < j} w_{ij} a_i a_j$) with $w_{ii} = 0$.

**Fix.**
Write $H(t) = \frac{1}{2} \sum_{i=1}^N \sum_{j \neq i} w_{ij} a_i(t) a_j(t)$ and define $SCS(G) := 0.0$ when $\sum_{i \neq j} |w_{ij}| = 0$.

---

### SC-04 · Quadratic Attenuation $(\bar{a}^*)^2$ Makes Diagnostic Threshold $SCS > 0.7$ Unreachable Under Standard Decay $\theta = 0.05$ — **Major**

**Where.** [`system_coherence.md#L45`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L45), [`#L60-L63`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L60-L63).

**Finding.**
In $SCS(G) = \frac{\sum_{i,j} w_{ij} a_i^* a_j^*}{\sum_{i,j} |w_{ij}|}$, the denominator sums $|w_{ij}|$ (which assumes $a_i^* a_j^* = 1.0$), whereas the numerator multiplies two equilibrium activations $a_i^* \cdot a_j^*$.
Under standard ECHO parameters ($\theta = 0.05$, `node_activation.md` L60, where acceptance is $a_i^* \ge 0.20$), non-clamped hypotheses in a completely contradiction-free network ($w_{ij} \ge 0$ everywhere) typically converge to $a_i^* \in [0.45, 0.75]$.
- If every hypothesis in a contradiction-free theory converges to a strong acceptability of $a_i^* = 0.70$, then $a_i^* a_j^* = 0.70 \times 0.70 = 0.49$, so $SCS(G) = 0.49 \ll 0.70$!
- If every hypothesis converges to $a_i^* = 0.44$ (well above the acceptance threshold $\tau_{\text{accept}} = 0.20$), then $SCS(G) = 0.44^2 = 0.1936 < 0.20$, which the Diagnostic Table (L62) classifies as:
  > **"Low $SCS$ ($< 0.2$): Fractured / Conflicted Paradigm — Intense internal contradictions and un-reconciled anomalies across competing hypotheses"**
  even when the graph has **zero contradictions ($w_{ij} < 0$) and zero anomalies**!

**Fix.**
Either:
1. Normalize $SCS(G)$ by the **active weight mass** $\sum_{i \neq j} |w_{ij}| \, |a_i^*| \, |a_j^*|$ (measuring the pure sign-alignment / frustration-free ratio in $[-1, 1]$, where $+1.0$ means zero active contradictions regardless of decay magnitude $\theta$), or
2. Recalibrate the diagnostic thresholds for the unnormalized quadratic product (e.g., High Coherence $SCS \ge 0.35$, Moderate $0.0 \le SCS < 0.35$, Conflicted/Fractured $SCS < 0.0$).

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### SC-05 · Unspecified Symmetrization Mapping Between Directed `TheoryGraph` / D-QBAF and Symmetric Matrix $W$ — **Major**

**Where.** [`system_coherence.md#L32-L36`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L32-L36), [`#L52-L53`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L52-L53) (cf. [`ISSUE-066` A-12](../../10-formal-conceptual-docs/ISSUE-066-cross-document-inconsistencies-and-notation.md#a-12--echo-coherence-links-do-not-fit-the-qbaf-typing--major)).

**Finding.**
`system_coherence.md` requires a **symmetric** adjacency matrix $W = W^\top$ ($w_{ij} = w_{ji}$).
However, `TheoryGraph` (`epistemetrics/core/models.py`) and Layer 3 D-QBAF (`formal_graph_model.md`, `qbaf.py`) store **directed** edges $(u, v) \in E$ with asymmetric weights $W_{uv} \neq W_{vu}$ (and potentially opposing polarities, e.g., $u$ supports $v$ while $v$ attacks $u$, or multiple parallel edges in the multigraph).
Step 1 (L52: *"Construct symmetric adjacency matrix $W$ with excitatory ($w > 0$) and inhibitory ($w < 0$) weights"*) never specifies how directed multigraph edges between $i$ and $j$ are aggregated and symmetrized into $w_{ij} = w_{ji}$.

**Fix.**
Define the canonical symmetrization projection from `TheoryGraph` to $W = W^\top$:
$$w_{ij} = w_{ji} = \frac{1}{2} \sum_{e \in E(i, j) \cup E(j, i)} \text{pol}(e) \cdot W(e), \qquad w_{ii} = 0$$
where $\text{pol}(e) \in \{+1, -1\}$ is the edge polarity (`RelationType.default_polarity`), ignoring structural containment edges with $\text{pol}(e) = 0$.

---

## 4. Is the Metric Valid and Scientifically Significant?

### SC-06 · Relationship to Frustration Index in Signed Networks — **Minor**

**Where.** [`system_coherence.md#L20-L27`](../../../docs/concepts/theory/metrics/epistemic_coherence/system_coherence.md#L20-L27).

**Finding.**
In signed network theory (Harary 1953; Traag & Bruggeman 2009) and constraint-satisfaction complexity (Thagard & Verbeurgt 1998), normalized Harmony over active nodes is dual to the **signed network frustration index** (the fraction of edge weight that violates structural balance). Grounding $SCS(G)$ in Thagard & Verbeurgt (1998) alongside Thagard (1989) strengthens its theoretical justification.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Inconsistent Header Capitalization (L7):** `# System COHERENCE (HARMONY, $H$)` uses mixed ALL-CAPS (`COHERENCE (HARMONY, $H$)`), unlike `# Node Activation (Acceptability)` or `# Consistency`.
2. **Broken Desktop Zotero Links (L13):** `[Thagard, 1989, p. 443](zotero://select/library/items/8F6MW586)` and `[Schurz, 2024, sec. 5.3](zotero://select/library/items/24SNSW2B)` use local desktop Zotero URIs.
3. **Symbol Collision on $H$:** $H(t)$ denotes the scalar Harmony function here, whereas $H = (V_H, E_H)$ denotes a hypothesis subgraph in `conservatism.md` and `simplicity.md`.
