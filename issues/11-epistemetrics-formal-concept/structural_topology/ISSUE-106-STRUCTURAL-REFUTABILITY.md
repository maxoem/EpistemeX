# [ISSUE-106] Formal & Conceptual Evaluation: Structural Refutability (`structural_refutability.md`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-106` |
| **Domain / Category** | `11-Epistemetrics Formal Concept` — Pillar 1: Structural & Topological Metrics (Micro-Topology Foundation) |
| **Evaluated Doc** | [`docs/concepts/theory/metrics/structural_topology/structural_refutability.md`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md) |
| **Target Package(s)** | `epistemetrics` (`src/epistemetrics/graph/algorithms/`), `episteme-studio` |
| **Priority** | **Critical** (Contradiction between the formula $\sum_{i=1}^k |\Pi(H / R(i))|$ which removes each node $R(i)$ *independently* from $H$ and the implementation step L70 which removes the top-$k$ nodes *iteratively/cumulatively*; non-monotonicity of geodesic path multiplicity $|\Pi(H)|$ where removing a shortcut hub can *increase* the number of shortest paths; $k$-dependent range $[\frac{1}{1+k}, 1]$ that shrinks as $k$ increases; and zero-betweenness degeneracy of root axioms $T_0$ and leaf evidence $B$ in directed DAGs) |
| **Status** | `Open` |
| **Related Issues** | [`ISSUE-096`](ISSUE-096-BOTTLENECK-FRAGILITY.md), [`ISSUE-099`](ISSUE-099-CONNECTEDNESS.md), [`ISSUE-107`](../ISSUE-107-STRUCTURAL-TOPOLOGY-CROSS-CUTTING.md), [`ISSUE-006`](../../03-epistemic-metrics/ISSUE-006-novacek-hypothesis-virtues-suite.md) |

Severity legend: **Critical** = invalidates the metric's mathematical/conceptual core, yields inverted diagnostics, or is mathematically uncomputable as written · **Major** = significant formal flaw, semantic shift, gaming vulnerability, or literature misattribution · **Minor** = notation, alignment, or presentation issue.

---

## Executive Summary across the 4 Evaluation Dimensions

| Evaluation Dimension | Verdict | Core Assessment |
| :--- | :--- | :--- |
| **1. Captures Claimed Construct?** | **No (Directed Betweenness Assigns $C_B(T_0) = 0$ to Every Foundational Root Axiom, and Independent Ablation Fails on $k \ge 2$ Cuts)** | Claims to measure how easily the claim volume of a theory graph collapses if its "most structurally vital concepts" are falsified, ranking nodes by **Betweenness Centrality** $C_B(v)$. However: (1) In any directed specialization or derivation DAG (`dag_property.md`), every foundational root axiom $T_0 \in B(N)$ has **in-degree $0$** (no shortest path can *enter* $T_0$), so **its Betweenness Centrality is identically $C_B(T_0) = 0.0$**! Thus $T_0$ is ranked **dead last** and is never selected for removal by Top-$k$ Refutability! (2) Even if undirected betweenness is used, the formula $\frac{\|\Pi(H)\|}{\|\Pi(H)\| + \sum_{i=1}^k \|\Pi(H / R(i))\|}$ removes each node $R(i)$ *individually* from the original graph $H$ rather than removing $\{R(1), \dots, R(k)\}$ together—so for any graph with vertex connectivity $\kappa(H) = k \ge 2$, removing $1$ node leaves all pairs connected and scores low refutability ($\approx \frac{1}{1+k}$) even when $k = \kappa(H)$! |
| **2. Formally & Mathematically Correct?** | **No (Critical Flaws)** | (1) Direct contradiction between L54/L60 ($H / R(i)$ removes only the single $i$-th vertex from $H$) and L70 (*"Iteratively 'remove' the top $k$ nodes"*); (2) Counting shortest paths $\|\Pi(H)\|$ (geodesic multiplicity $\sum_{s \neq t} \sigma_{st}$) is **not monotonic** under vertex removal: deleting a unique 2-hop shortcut bridge that masks $m$ parallel 3-hop paths increases $\sigma_{st}$ from $1$ to $m$, driving $\text{Refutability}_1(H) < 0.50$; (3) Unnormalized range $[\frac{1}{1+k}, 1]$ shrinks toward $0$ as $k$ increases; (4) Divides by $0$ when $\|\Pi(H)\| = 0$ (edgeless graph). |
| **3. Free of Semantic Shifts?** | **No (Major Shifts)** | Uses graph-contraction / quotient notation $H / R(i)$ (L54, L60) to mean **vertex deletion** $H \setminus \{R(i)\}$ (whereas `bottleneck_fragility.md` L51 writes $G \setminus \{v_i\}$ and `metrics/index.md` L51 writes $H \setminus \{v_i\}$), and oscillates between Popperian **Hard Falsifiability** (a positive scientific virtue; L16, L80) and **Fragility** (a structural weakness; L11, L72). |
| **4. Valid & Scientifically Significant?** | **Yes (Once Repaired to Cumulative Pair-Reachability Drop & Root/Intermediate Aware)** | Targeted node-ablation percolation (Albert, Jeong, & Barabási 2000; Nováček 2015) is a classic network robustness/vulnerability method, provided it uses cumulative ablation $H \setminus \{R(1), \dots, R(k)\}$, reachable vertex-pair count (or global efficiency), and accounts for source/root axioms alongside intermediate bridges. |

---

## 1. Does the Metric Capture What It Claims It Does?

### SR-01 · Zero-Betweenness Blind Spot: Foundational Root Axioms ($T_0$) Have $C_B(T_0) = 0$ on Directed Theory Graphs and Are Never Tested for Refutability — **Critical**

**Where.** [`structural_refutability.md#L48-L55`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L48-L55), [`#L69-L70`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L69-L70), and [`packages/epistemetrics/src/epistemetrics/graph/algorithms/betweenness.py#L60-L65`](../../../packages/epistemetrics/src/epistemetrics/graph/algorithms/betweenness.py#L60-L65).

**Finding.**
1. L48–49 specifies:
   > *"To measure the real-world impact of targeted falsification, we rank the vertices $v \in V_H$ by their **Betweenness Centrality**. Let $R(i)$ be the $i$-th ranked vertex."*
2. In `epistemetrics`, `TheoryGraph.nx_graph` is a **directed graph** (`nx.MultiDiGraph`), and `networkx_betweenness` (`betweenness.py` L61) computes **directed** shortest-path betweenness centrality:
   $$C_B(v) = \sum_{s \neq v \neq t \in V} \frac{\sigma_{st}(v)}{\sigma_{st}}$$
   where a path $s \to \dots \to v \to \dots \to t$ requires at least one incoming edge into $v$ and at least one outgoing edge from $v$.
3. **What happens to the foundational root axiom $T_0$ (e.g., Newton's Second Law $\vec{F} = m\vec{a}$) in any directed Theory-Tree or DAG?**
   - Because $T_0$ is a root element, $\text{deg}_{\text{in}}(T_0) = 0$: **zero directed paths from any $s \neq T_0$ can ever pass through $T_0$**!
   - Therefore, for **every foundational root axiom $T_0$ in any directed theory graph**:
     $$C_B(T_0) = \mathbf{0.0}!$$
   - Even in a **Pure Directed Star** $T_0 \to \{T_1, T_2, \dots, T_{n-1}\}$ (where $T_0$ is the sole central hub and removing $T_0$ destroys $100\%$ of the edges in the entire graph!), **every single node in the graph has directed betweenness centrality $C_B(v) = 0.0$**!
   - In a 3-tier tree $T_0 \to \{T_1, T_2\}$ where $T_1 \to \{T_{11}, T_{12}\}$, the intermediate node $T_1$ has $C_B(T_1) = 0$ as well (because only paths starting at $T_0$ pass through $T_1$, and $T_0$ has only 1 path to $T_{11}, T_{12}$); if $T_0$ is a single root, $T_1$ has $\sigma_{T_0, T_{11}}(T_1) = 1$, while the root $T_0$ itself still has **$C_B(T_0) = 0.0$**!
   - Thus, on any directed theory graph, ranking nodes by directed Betweenness Centrality places the foundational root axioms $T_0$ at the **very bottom of the ranking ($C_B = 0$)**, so Top-$k$ Refutability **never tests falsifying the foundational axioms of the theory**!

**Fix.**
Specify explicitly:
1. When evaluating **Undirected Topological Bottlenecks** (structural articulation points), compute Betweenness Centrality and shortest paths on the **undirected skeleton** $H_{\text{undir}}$ (where the root $T_0$ bridging multiple branches has maximal betweenness $C_B(T_0)$).
2. When evaluating **Directed Deductive / Evidential Falsification** on the directed graph $H_{\text{dir}}$, rank candidate nodes by **Total Path Participation** (nodes $v$ maximizing the number of directed pairs $(s, t)$ whose paths originate at OR pass through $v$, i.e. $|\{(s, t) \mid s \neq t, \, v \in P_{st}\}|$, which includes both root axioms $s = v$ and intermediate bridges $s \neq v \neq t$).

---

### SR-02 · Contradiction Between Independent Single-Node Removal ($H / R(i)$ in Formula L54) and Iterative Multi-Node Removal (Step 3 in L70), Plus Failure on $\kappa(H) \ge 2$ — **Critical**

**Where.** [`structural_refutability.md#L32-L33`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L32-L33), [`#L54-L60`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L54-L60) vs. [`#L70`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L70).

**Finding.**
1. **Direct Contradiction Between L54/L60 and L70:**
   - L54 & L60 define the formula using **independent single-vertex removals** from the original graph $H$:
     $$\text{Refutability}_k(H) = \frac{|\Pi(H)|}{|\Pi(H)| + \sum_{i=1}^k |\Pi(H / R(i))|}$$
     where L60 states: *"$H / R(i)$ is the graph after removing the $i$-th most central vertex."*
   - L70 (Measurement & Graph Implementation, Step 3) states the exact opposite:
     > *"3. **Node Removal Simulation**: **Iteratively** 'remove' the top $k$ nodes (often $k=1$ is sufficient)."*
2. **Why Independent Removal ($H \setminus \{R(i)\}$) Breaks the $\kappa$-Connectivity Guarantee (L32–33):**
   L32–33 states:
   > *"This concept is strictly bounded by **$k$-connectivity**: a theory with a vertex connectivity of $k$ requires the falsification of at least $k$ distinct core concepts to shatter."*
   As proven in [`ISSUE-096` BF-03](ISSUE-096-BOTTLENECK-FRAGILITY.md#bf-03--independent-single-node-ablation-in-sum_i1k-pig-setminus-v_i-fails-to-measure-multi-node-k--1-bottleneck-collapse-and-shrinks-r_kg-as-k-grows--critical): if $\kappa(H) = 2$ (two parallel bridge nodes $R(1), R(2)$ connecting two components), removing $R(1)$ alone leaves $H \setminus \{R(1)\}$ 100% connected via $R(2)$, and removing $R(2)$ alone leaves $H \setminus \{R(2)\}$ 100% connected via $R(1)$.
   Only **joint/cumulative removal** $H^{(i)} = H \setminus \{R(1), \dots, R(i)\}$ (where at $i = 2$, *both* $R(1)$ and $R(2)$ have been removed!) shatters the $\kappa = 2$ graph!
3. **Unnormalized Range $[\frac{1}{1+k}, 1]$ Shrinks with $k$:**
   In L54, when node removal destroys $0\%$ of paths ($|\Pi(H^{(i)})| = |\Pi(H)|$), $\text{Refutability}_k(H) = \frac{1}{1+k}$ (which is $0.50$ for $k=1$, $0.25$ for $k=3$, and $0.09$ for $k=10$). Even if step $i = k$ completely shatters the graph ($|\Pi(H^{(k)})| = 0$), the earlier terms $i = 1, \dots, k-1$ in the denominator prevent $\text{Refutability}_k(H)$ from ever reaching $1.0$ for $k \ge 2$!

**Fix.**
Define Top-$k$ Refutability via **joint removal** of the top-$k$ set $S_k = \{R(1), \dots, R(k)\}$ as the direct **Path Destruction Ratio** in $[0, 1]$:
$$\text{Refutability}_k(H) = 1 - \frac{|\Pi(H \setminus \{R(1), \dots, R(k)\})|}{|\Pi(H)|} \in [0, 1]$$
(and optionally report the **Cumulative Ablation Curve** $\text{AUC}_{\text{refut}}(H, K) = \frac{1}{K} \sum_{k=1}^K \left(1 - \frac{|\Pi(H \setminus \{R(1), \dots, R(k)\})|}{|\Pi(H)|}\right) \in [0, 1]$).
Under this definition:
- Destroying $0\%$ of connected pairs yields $\text{Refutability}_k(H) = 0.0$ for *every* $k$.
- Destroying $100\%$ of connected pairs yields $\text{Refutability}_k(H) = 1.0$ for *every* $k$.
- Removing $k = \kappa(H)$ minimum-cut vertices strictly disconnects the graph and increases $\text{Refutability}_k(H)$ monotonically with $k$!

---

## 2. Is the Metric Formally & Mathematically Correct?

### SR-03 · Non-Monotonicity of Shortest-Path Multiplicity $|\Pi(H)|$ Under Vertex Deletion & $0/0$ Division by Zero — **Major**

**Where.** [`structural_refutability.md#L54-L61`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L54-L61), [`#L71-L72`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L71-L72).

**Finding.**
1. **Shortcut Removal Can Increase the Number of Shortest Paths:**
   L59 defines $|\Pi(H)|$ as *"the number of shortest paths (claims) in the original graph."*
   In graph theory, if $|\Pi(H)| = \sum_{s \neq t} \sigma_{st}(H)$ counts the **number of shortest paths** between all pairs $(s, t)$, then deleting a central node $R(1)$ can **increase** $|\Pi(H \setminus \{R(1)\})| > |\Pi(H)|$!
   - *Concrete counter-example:* Let $s$ and $t$ have one 2-hop path $s - R(1) - t$ through hub $R(1)$ (length $2$, so $\sigma_{st}(H) = 1$) and $m = 5$ parallel 3-hop paths $s - u_r - w_r - t$ ($r = 1, \dots, 5$, length $3$, which are *not* shortest paths in $H$ because $3 > 2$).
   - When $R(1)$ is deleted, the distance between $s$ and $t$ increases from $2$ to $3$, and all $5$ paths of length $3$ now become **shortest paths** in $H \setminus \{R(1)\}$, so $\sigma_{st}(H \setminus \{R(1)\}) = 5 > 1 = \sigma_{st}(H)$!
   - Thus, deleting the central hub $R(1)$ **increased** $|\Pi|$ instead of decreasing it!
2. **Division by Zero When $|\Pi(H)| = 0$:**
   If $H$ has no edges ($E_H = \emptyset$) or $|V_H| \le 1$, $|\Pi(H)| = 0$ and $|\Pi(H \setminus S_k)| = 0$, causing $\frac{0}{0 + 0}$ (`ZeroDivisionError`).

**Fix.**
Define $|\Pi(H)|$ explicitly as the **number of reachable ordered vertex pairs** (connectivity volume):
$$|\Pi(H)| = \big|\{(s, t) \in V_H \times V_H \mid s \neq t \text{ and } d_H(s, t) < \infty\}\big|$$
(or **Harmonic Global Efficiency** $\mathcal{E}(H) = \sum_{s \neq t \in V_H} \frac{1}{d_H(s, t)}$ where $1/\infty := 0$), both of which are **strictly non-increasing** ($|\Pi(H \setminus S)| \le |\Pi(H)|$ and $\mathcal{E}(H \setminus S) \le \mathcal{E}(H)$) for every vertex removal $S \subseteq V_H$! Guard $|\Pi(H)| = 0$ by returning $1.0$.

---

## 3. Does It Contain Semantic Shifts That Threaten Metric Integrity?

### SR-04 · Quotient/Contraction Notation $H / R(i)$ Used for Vertex Deletion $H \setminus \{R(i)\}$ — **Minor**

**Where.** [`structural_refutability.md#L54`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L54), [`#L60`](../../../docs/concepts/theory/metrics/structural_topology/structural_refutability.md#L60) vs. [`bottleneck_fragility.md#L51`](../../../docs/concepts/theory/metrics/structural_topology/bottleneck_fragility.md#L51) and [`docs/concepts/theory/metrics/index.md#L51`](../../../docs/concepts/theory/metrics/index.md#L51).

**Finding.**
In standard graph theory, $H / S$ denotes **graph quotient / contraction** (collapsing $S$ into a super-vertex while preserving incident edges, which *increases* connectivity!), whereas **vertex deletion** (removing $R(i)$ and all incident edges) is written $H \setminus \{R(i)\}$ or $H - R(i)$. Note that `bottleneck_fragility.md` (L51) and `metrics/index.md` (L51) already corrected this to $G \setminus \{v_i\}$ and $H \setminus \{v_i\}$, while `structural_refutability.md` (L54, L60) still retains $H / R(i)$.

**Fix.**
Replace $H / R(i)$ with $H \setminus \{v_1, \dots, v_k\}$ in `structural_refutability.md` L54 and L60.

---

## 4. Is the Metric Valid and Scientifically Significant?

### SR-05 · Missing Implementation in `epistemetrics` — **Major**

**Where.** `packages/epistemetrics/src/epistemetrics/graph/algorithms/`.

**Finding.**
`compute_structural_refutability` is not implemented in `packages/epistemetrics/`.

**Fix.**
Implement `compute_structural_refutability` in `packages/epistemetrics/src/epistemetrics/graph/algorithms/` supporting both joint top-$k$ ablation $R_k(H) \in [0, 1]$ and vertex connectivity $\kappa(H)$.
