# [ISSUE-091] Formal & Conceptual Evaluation: Node Activation / Acceptability (`node_activation.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-091` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 2: Epistemic Coherence & Parsimony |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/epistemic_coherence/node_activation.md`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/epistemic/qbaf.py`), `episteme-pipeline` |
| **Priority** | **Critical** (complete split-brain with the implemented D-QBAF solver in `qbaf.py`, omits evidence clamping so every node in any DAG decays to $a_j^* = 0.0$, lacks bounds clamping when $\|\text{net}_j(t)\| > 1$ causing divergent oscillation, and initializes $[-1, 1]$ activations with $[0, 1]$ priors) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-093`](ISSUE-093-SYSTEM-COHERENCE.md), [`ISSUE-095`](../ISSUE-095-EPISTEMIC-COHERENCE-CROSS-CUTTING.md), [`ISSUE-009`](../../03-epistemic-metrics/ISSUE-009-global-qbaf-solvers-and-thagardian-harmony.md), [`ISSUE-050`](../../09-architecture-workflow-domain/ISSUE-050-ontological-schism-tf-vs-dqbaf-vs-structuralist-tenability-feedback.md), [`ISSUE-082`](../ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core or makes it uncomputable · **Major** = significant formal flaw, semantic shift, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Zero-Decay Collapse on DAGs)** | Claims to model how empirical data cascades through explanatory and contradictory links until each proposition settles into an equilibrium acceptability $a_j^* \in [-1, 1]$. However, because the mathematical specification (L37, L56) omits evidence clamping / persistent source input, root empirical nodes with no incoming edges decay exponentially via $a_i(t) = a_i(0)(1-\theta)^t \to 0$, dragging **every node in any DAG down to $a_j^* = 0.0$ ("Neutral / Undetermined")** at equilibrium! |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) **Unbounded divergence when $\|\text{net}_j(t)\| > 1$:** With QBAF weights $\phi \in [0, 1]$ and no $[\,a_{\min}, a_{\max}\,]$ clipping in L56, $\text{net}_j(t) > 1$ pushes $a_j(t+1) > 1$, flipping the sign of $(a_{\max} - a_j)$ and causing exponential blow-up when $\|\text{net}_j\| > 2 - \theta$; (2) **Prior scale mismatch:** Initializes $a_i(0) \in [-1, 1]$ directly from $\tau(a_i) \in [0, 1]$, where $\tau = 0.6$ already exceeds $\tau_{\text{accept}} = 0.20$ and $\tau = 0.0$ is neutral instead of rejected; (3) **Non-convergence on directed cycles:** $a_j^* = \lim_{t \to \infty} a_j(t)$ does not exist on asymmetric inhibitory cycles. |
| **3. Free of Semantic Shifts?** | **No (Severe Shifts)** | Conflates **Thagard's undirected symmetric ECHO model** ($a_j \in [-1, 1]$, decay toward $0$, small symmetric weights $w_{ij} = w_{ji} \approx 0.05$) with **TheoryNet's directed D-QBAF model** ($\tau(a) \in [0, 1]$, decay toward prior $\tau_0(a)$, directed weights $\phi(a_i, a_j) \in [0, 1]$). |
| **4. Valid & Scientifically Significant?** | **Split-Brain with `qbaf.py`** | Global acceptability relaxation is central to Episteme, and **`epistemetrics/epistemic/qbaf.py` already implements a mathematically rigorous continuous/discrete D-QBAF solver** (`WeightedQuadraticEnergySolver` & `QBAFGradualSemanticsSolver`), which `node_activation.md` completely ignores. |

---

## 1. Does the Metric Capture What It Claims It Does?

### NA-01 · Omission of Evidence Clamping / Anchor Input Forces Every Node in Any DAG to Decay to $a_j^* = 0.0$ — **Critical**

**Where.** [`node_activation.md#L34-L62`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L34-L62).

**Finding.**
In §Mathematical Specification (L37 & L56), the net input and update rule for **every** node $j \in \{1, \dots, N\}$ are defined as:
$$\text{net}_j(t) = \sum_{i=1}^N w_{ij} a_i(t)$$
$$a_j(t+1) = \begin{cases} a_j(t)(1 - \theta) + \text{net}_j(t)(a_{\max} - a_j(t)) & \text{if } \text{net}_j(t) > 0 \\ a_j(t)(1 - \theta) + \text{net}_j(t)(a_j(t) - a_{\min}) & \text{if } \text{net}_j(t) \le 0 \end{cases}$$
initialized at $a_i(0) = \tau(a_i)$ with decay rate $\theta \in (0, 1)$ (typically $\theta = 0.05$).

**Proof of total collapse on any DAG (and any weakly coupled graph):**
1. Unlike Thagard (1989, p. 439)—where data units $e \in B$ receive a permanent excitatory link $w_{0e} > 0$ from a clamped **special evidence unit $E_0 \equiv 1.0$** (or are themselves clamped to $a_e(t) \equiv 1.0$ for all $t \ge 0$)—the specification in `node_activation.md` applies L56 to all nodes using only $a_i(0) = \tau(a_i)$ at $t = 0$.
2. Suppose the directed support graph is a DAG (e.g. empirical source $e \in B \to$ premise $p \to$ hypothesis $h$).
   - Root empirical source nodes $e \in B$ have in-degree $0$, so $\text{net}_e(t) = 0$ for all $t \ge 0$.
   - By L56, $a_e(t+1) = (1 - \theta) a_e(t)$, so:
     $$\lim_{t \to \infty} a_e(t) = \lim_{t \to \infty} \tau(e)(1 - \theta)^t = 0.$$
   - By induction along the topological order of the DAG, once all predecessors $i$ of node $j$ satisfy $\lim_{t \to \infty} a_i(t) = 0$, we have $\lim_{t \to \infty} \text{net}_j(t) = 0$, and because $0 < 1 - \theta < 1$, node $j$ also satisfies:
     $$a_j^* = \lim_{t \to \infty} a_j(t) = 0.0!$$
3. Therefore, on **every directed acyclic graph**, the equilibrium activation of **every single node** is identically $a_j^* = 0.0$, classifying $100\%$ of propositions as **"Neutral / Undetermined"** regardless of how strong their prior plausibility $\tau(a_i)$ or edge weights $\phi(a_i, a_j)$ are!
4. Even on an undirected graph, if the spectral radius of $W$ satisfies $\rho(W) < \theta$, the unique stable fixed point in the absence of clamped nodes is the zero vector $\mathbf{a}^* = \mathbf{0}$.

**Fix.**
Either:
1. **In D-QBAF (implemented in `epistemetrics/epistemic/qbaf.py`):** Decay pulls $s_i(t)$ back toward the node's **intrinsic base score $w(i) = \tau_0(a_i)$** rather than $0$:
   $$\frac{ds_i}{dt} = \underbrace{\big(\tau_0(a_i) - s_i(t)\big)}_{\text{relaxation to prior } \tau_0} + (1 - \tau_0(a_i)) h(E_i(t)) - \tau_0(a_i) h(-E_i(t)),$$
   so root nodes retain $s_i^* = \tau_0(a_i)$ and propagate activation downstream without vanishing!
2. **In Thagardian ECHO (`adapted_echo_algorithm.md`):** Explicitly specify in the mathematical formula of `node_activation.md` that empirical observation nodes $b \in B$ are either **clamped** at $a_b(t) \equiv \tau_{\text{clamp}}(b) \in (0, 1]$ for all $t \ge 0$, or receive a constant external anchor input $w_{0b} \cdot 1.0$ from a clamped meta-source $a_0(t) \equiv 1.0$ (Thagard 1989, p. 439).

---

### NA-02 · Complete Architectural Split-Brain with `formal_graph_model.md` and `epistemetrics/epistemic/qbaf.py` — **Critical**

**Where.** [`node_activation.md#L23-L68`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L23-L68) vs. [`formal_graph_model.md#L168-L245`](../../../docs/concepts/formal_graph_model.md#L168-L245) and [`packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py`](../../../packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py).

**Finding.**
`formal_graph_model.md` (§Continuous State Computation & Gradual Semantics, L168–245) and `packages/epistemetrics/src/epistemetrics/epistemic/qbaf.py` define and implement node acceptability using **Potyka's (2018) Weighted Quadratic Energy D-QBAF model** (plus Euler, Categorizer, and Linear gradual semantics):
- State space: $s_i(t) \in [0, 1]$ (with equilibrium $\tau^*(a_i) \in [0, 1]$).
- Impact function: $h(x) = \frac{\max(x, 0)^2}{1 + \max(x, 0)^2} \in [0, 1)$.
- Solver: Closed-form topological evaluation in $O(|V| + |E|)$ on DAGs (`_solve_dag_closed_form`) and adaptive `solve_ivp` RK45/Radau ODE integration on cyclic graphs (`WeightedQuadraticEnergySolver`).

In contrast, `node_activation.md` defines node acceptability exclusively via Thagard's 1989 discrete linear-shunting update in $[-1, 1]$, which is **not implemented anywhere in `packages/epistemetrics/`** and contradicts `formal_graph_model.md` L170 ($\rho: A \to [0, 1]$).

**Fix.**
Update `node_activation.md` to document the **implemented D-QBAF gradual semantics solver** (`WeightedQuadraticEnergySolver` in `qbaf.py`, $\tau^*(a_i) \in [0, 1]$) as the primary normative acceptability engine (consistent with `formal_graph_model.md` L180–245), and present the signed $[-1, 1]$ Thagardian ECHO relaxation as an optional symmetric coherence lens (with explicit mapping $a_i^* = 2\tau^*(a_i) - 1 \in [-1, 1]$ or centered $\frac{\tau^*(a_i) - \tau_0(a_i)}{1 - \tau_0(a_i)}$; see [`ISSUE-082`](../ISSUE-082-METATHEORETICAL-CROSS-CUTTING.md#2-split-brain-between-unimplemented-lpg-echo-a_it-in--1-1-and-implemented-d-qbaf-taua-in-0-1--critical)).

---

## 2. Is the Metric Formally & Mathematically Correct?

### NA-03 · Missing Bounds Clipping Causes $a_j(t+1)$ to Escape $[-1, 1]$ and Diverge Exponentially When $|\text{net}_j(t)| > 1$ — **Critical**

**Where.** [`node_activation.md#L37-L62`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L37-L62).

**Finding.**
L43–47 maps connection weights $w_{ij}$ directly to QBAF edge weights $\phi(a_i, a_j) \in [0, 1]$ (which in `TheoryEdge`, `models.py` L673–679, default to `weight = 1.0` or `active_weight = 0.75`), and L56 defines:
$$a_j(t+1) = a_j(t)(1 - \theta) + \text{net}_j(t)(1 - a_j(t)) \quad \text{for } \text{net}_j(t) > 0.$$
Notice what happens when $\text{net}_j(t) > 1.0$ (for example, node $j$ has $a_j(t) = 0$ and is supported by 3 neighbors with $w_{ij} = 0.8$ and $a_i(t) = 0.8$, so $\text{net}_j(t) = 3 \times 0.64 = 1.92 > 1.0$):
1. **Escape from $[-1, 1]$ in 1 Step:**
   $$a_j(t+1) = 0 + 1.92(1 - 0) = 1.92 \notin [-1, 1]!$$
2. **Sign Inversion of the Shunting Factor $(a_{\max} - a_j(t))$:**
   Once $a_j(t+1) = 1.92 > a_{\max} = 1.0$, the shunting factor $(a_{\max} - a_j(t+1)) = 1.0 - 1.92 = -0.92$ becomes **negative**! Thus, continued positive support $\text{net}_j > 0$ drives $a_j$ **downward**.
3. **Exponential Divergence to $\pm\infty$:**
   Writing L56 as an affine recurrence in $a_j(t)$ for constant $\text{net}_j > 0$:
   $$a_j(t+1) = \big(1 - \theta - \text{net}_j\big) a_j(t) + \text{net}_j.$$
   The multiplier $\lambda = 1 - \theta - \text{net}_j$ satisfies $|\lambda| < 1 \iff \text{net}_j < 2 - \theta$. Whenever a node receives weighted support $\text{net}_j > 2 - \theta \approx 1.95$ (e.g. a hub supported by 3 nodes with weight $0.8$ and activation $0.85$), $|\lambda| > 1$ and $\lambda < -1$, so $a_j(t)$ **oscillates with alternating signs and diverges to $\pm\infty$**!
   (In Thagard 1989, p. 439 & 464, weights are $w_{ij} \approx 0.04$ and $a_j(t+1)$ is explicitly clamped via $\max(a_{\min}, \min(a_{\max}, a_j(t+1)))$.)

**Fix.**
If the discrete ECHO update (L56) is used:
1. Either apply a bounded saturating nonlinearity to $\text{net}_j(t)$ (e.g. $\widetilde{\text{net}}_j(t) = \tanh(\text{net}_j(t)) \in (-1, 1)$, or the continuous ODE form $\dot{a}_j = -\theta a_j + \max(\text{net}_j, 0)(1 - a_j) + \min(\text{net}_j, 0)(a_j + 1)$ which is forward-invariant on $[-1, 1]$ by Nagumo's theorem), **and**
2. Explicitly clamp each discrete step to $[a_{\min}, a_{\max}] = [-1, 1]$.

---

### NA-04 · Scale Mismatch Between Initialization $a_i(0) = \tau(a_i) \in [0, 1]$ and Bipolar State Space $a_i(t) \in [-1, 1]$ — **Major**

**Where.** [`node_activation.md#L17`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L17), [`#L40-L41`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L40-L41), [`#L67`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L67).

**Finding.**
- L40–41 states: *"At $t=0$, $a_i(0)$ is initialized using the prior plausibility function $\tau(a_i)$ (as defined in the underlying TheoryNet Quantitative Bipolar Argumentation Framework)."*
- In TheoryNet (`formal_graph_model.md` L131, L188 and `TheoryNode.base_score` in `models.py` L584), $\tau: A \to [0, 1]$ is unsigned: $\tau(a_i) = 0.5$ (or $0.6$) represents epistemic neutrality/default plausibility, and $\tau(a_i) \in (0, 0.3)$ represents low plausibility.
- In `node_activation.md` (L17, L29, L67), however, the state space is $a_i(t) \in [-1, 1]$ with neutrality at $a_{\text{decay}} = 0.0$, Acceptance at $a_j^* \ge +0.20$, and Rejection at $a_j^* \le -0.20$.
- Consequently, setting $a_i(0) = \tau(a_i) \in [0, 1]$ without an affine transformation:
  1. Initializes a strongly implausible claim with $\tau(a_i) = 0.25$ as **already Accepted** ($0.25 \ge \tau_{\text{accept}} = 0.20$)!
  2. Never initializes any node in $[-1, 0)$, even if $\tau(a_i) = 0.0$!

**Fix.**
When mapping a QBAF prior $\tau_0(a_i) \in [0, 1]$ into the bipolar ECHO interval $[-1, 1]$, apply the canonical centering bijection:
$$a_i(0) = 2\tau_0(a_i) - 1 \in [-1, 1] \quad \text{(or initialize } a_i(0) = 0.0 \text{ for all } a_i \in A \text{ and clamp } a_b(t) = \tau_0(b) \text{ for } b \in B\text{, matching Thagard 1989)}.$$

---

### NA-05 · Non-Existence of Equilibrium Limit $\lim_{t \to \infty} a_j(t)$ on Directed/Asymmetric Cyclic Graphs — **Major**

**Where.** [`node_activation.md#L13`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L13), [`#L65`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L65).

**Finding.**
L13 and L65 define equilibrium acceptability via the limit $a_j^* = \lim_{t \to \infty} a_j(t)$.
Because `node_activation.md` maps $w_{ij}$ to directed QBAF edges $\phi(a_i, a_j)$ ($w_{ij} \neq w_{ji}$) and uses synchronous discrete updates, networks containing directed odd attack cycles ($a_1 \xrightarrow{-} a_2 \xrightarrow{-} a_3 \xrightarrow{-} a_1$) or symmetric mutual attacks updated synchronously can enter persistent limit cycles where $\lim_{t \to \infty} a_j(t)$ **does not exist**. No max-iteration bound, damping schedule, or non-convergence fallback is specified.

**Fix.**
Specify a stopping tolerance $\|\mathbf{a}(t+1) - \mathbf{a}(t)\|_\infty < \epsilon_{\text{tol}}$ with a maximum iteration cap $T_{\max}$ (or use the adaptive ODE solver `WeightedQuadraticEnergySolver` in `qbaf.py` which explicitly reports `converged: bool` and `final_delta: float`).

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### NA-06 · Inverted Explanatory Edge Direction ($H \to E$ vs. $E \to H$) Prevents Evidence from Activating Hypotheses — **Major**

**Where.** [`node_activation.md#L37`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L37), [`#L43-L52`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L43-L52).

**Finding.**
L16–17 and L49–50 state that *"empirical data cascades through explanatory, analogical, and contradictory links"* so that *"local empirical evidence [propagates] globally"* to hypotheses.
In `TheoryGraph` (`epistemetrics/core/models.py` L405) and `simplicity.md` (L147–148), explanatory links `RelationType.EXPLAINS` are directed **from explanans (hypothesis $H \in A$) to explanandum (evidence $E \in B$)** ($H \to E$).
If $\text{net}_j(t) = \sum_{i=1}^N w_{ij} a_i(t)$ sums over incoming directed edges $i \to j$, then along an `EXPLAINS` edge $H \to E$, activation flows from **hypothesis $H$ to evidence $E$**, and **hypothesis $H$ receives zero incoming input from the evidence $E$ it explains**!
(In Thagard's ECHO, explanatory coherence links are **undirected / bidirectional** $w_{HE} = w_{EH} > 0$ so that clamped evidence $E$ excites hypothesis $H$.)

**Fix.**
Explicitly specify edge-orientation handling for acceptability propagation:
- For `RelationType.SUPPORTS`: activation flows along edge direction `source -> target` ($E \to H$).
- For `RelationType.EXPLAINS` ($H \to E$): either reverse edge direction during upward evidential corroboration ($E \to H$) in directed D-QBAF, or symmetrize $w_{HE} = w_{EH}$ in undirected ECHO.

---

## 4. Is the Metric Valid and Scientifically Significant?

### NA-07 · Missing Orthogonal Weight-of-Evidence & Volatility Dimensions in Status Classification — **Minor**

**Where.** [`node_activation.md#L63-L68`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L63-L68), [`#L79-L86`](../../../docs/concepts/theory/metrics/epistemic_coherence/node_activation.md#L79-L86).

**Finding.**
In §Epistemic Status Classification (L67) and the Diagnostic Table (L84), $a_j^* \approx 0.0$ is diagnosed as:
> *"Epistemic Suspension: Insufficient evidence or evenly balanced competing explanations."*

As documented in `formal_graph_model.md` (L246–253) and implemented in `epistemetrics/epistemic/qbaf.py` (L406–419, L592–601), a single scalar activation cannot distinguish between **total absence of evidence** ($E_{\text{total}} = 0$) and **intense dialectical controversy** ($E_{\text{supp}} \gg 0, E_{\text{att}} \gg 0$ with $E_{\text{supp}} \approx E_{\text{att}}$). `qbaf.py` already computes `total_weight_of_evidence` and `volatility_index` for this exact purpose, which should be referenced in `node_activation.md` to split the `Neutral / Undetermined` status into `Unevidenced / Open` vs. `Contested / Volatile`.

---

## 5. Non-Threatening Inconsistencies & Misalignments with Project Framework

1. **Broken Desktop Zotero Links (L14):** `[Thagard, 1989, p. 439](zotero://select/library/items/8F6MW586)` and `[Schurz, 2024, sec. 5.3](zotero://select/library/items/24SNSW2B)` use local desktop Zotero URIs.
2. **Symbol Collision on $\tau$ (L40 vs. L67):** Uses $\tau(a_i)$ for the prior plausibility function on L40 and $\tau_{\text{accept}}, \tau_{\text{reject}}$ (and bare $\tau \ge 0.20$) for classification thresholds on L67.
