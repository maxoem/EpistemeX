---
status: needs_verification
tags:
  - Metrics
---

# System COHERENCE (HARMONY, $H$)

## Definition & Conceptual Goal

The **System Coherence (Harmony, $H$)** metric measures the global explanatory stability and constraint-satisfaction
state of the entire epistemological network
([Thagard, 1989, p. 443](../../../references.md#thagard-1989); [Schurz, 2014, sec. 5.3](../../../references.md#schurz-2014)).

It quantifies how well the competing and supporting hypotheses satisfy mutual constraints: maximizing simultaneous
activation of mutually supportive (excitatory) propositions while minimizing simultaneous activation of contradictory
(inhibitory) claims.

---
## Theoretical Grounding & Model Formulation

In Thagard's connectionist architecture (ECHO), explanatory coherence is framed as a **parallel constraint satisfaction
problem** analogous to Hopfield neural networks or Boltzmann machines.

The global state of the network at iteration $t$ is evaluated by a **Harmony Function ($H (t)$)**. As node activations
update over successive iterations, the network relaxes toward a state of maximum harmony, resolving conflicts and
selecting the globally coherent theory.

---
## Mathematical Specification & Graph Formulation

Let $V = \{1, 2, \dots, N\}$ be the set of all proposition nodes (hypotheses and evidence units). Let $w_{ij}$ be the
symmetric connection weight between node $i$ and node $j$:

* $w_{ij} > 0$ for positive explanatory / coherence links (excitatory constraints).
* $w_{ij} < 0$ for contradiction / incompatibility links (inhibitory constraints).
* $a_i (t) \in [-1, 1]$ be the continuous activation of node $i$ at iteration step $t$.

### Global Harmony Function

$$H (t) = \sum_{i=1}^{N} \sum_{j=1}^{N} w_{ij} a_i (t) a_j (t)$$

### Normalized System Coherence Score ($SCS$)

$$SCS (G) = \frac{H (t^*)}{\sum_{i=1}^N \sum_{j=1}^N |w_{ij}|}$$

where $t^*$ is the convergence iteration where $\Delta H (t^*) < \epsilon_{\text{tol}}$.

---
## Measurement & Graph Implementation

1. **Network Initialization**: Construct symmetric adjacency matrix $W$ with excitatory ($w > 0$) and inhibitory
   ($w < 0$) weights.
2. **Synchronous Relaxation Loop**: Update node activations until $\|\mathbf{a} (t+1) - \mathbf{a} (t)\| < 10^{-4}$.
3. **Harmony Calculation**: Compute quadratic form $\mathbf{a}^T W \mathbf{a}$ at equilibrium.

---
## Diagnostic & Metascientific Value

| $SCS(G)$ Score       | Epistemic Coherence State       | Metascientific Diagnostic                                                                |
|:---------------------|:--------------------------------|:-----------------------------------------------------------------------------------------|
| High $SCS$ ($> 0.7$) | Highly Harmonious & Coherent    | Hypotheses and evidence mutually reinforce without unresolved contradictions.            |
| Low $SCS$ ($< 0.2$)  | Fractured / Conflicted Paradigm | Intense internal contradictions and un-reconciled anomalies across competing hypotheses. |

---
## Grounding References

* **[Thagard, 1989]** Thagard, P. (1989). Explanatory Coherence. *Behavioral and Brain Sciences*, 12 (3), pp. 435–467.
* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, sec. 5.3.
