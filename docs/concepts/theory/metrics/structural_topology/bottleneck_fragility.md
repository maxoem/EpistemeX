---
status: needs_verification
tags:
  - Metrics
  - Composite Index
---

# Bottleneck Fragility Profile

## Definition & Conceptual Goal

The **Bottleneck Fragility Profile** is a *Micro-Topological Composite Index* that evaluates whether a theory graph is
overly reliant on a few centralized dogmas or hubs, and quantifies the structural damage if those hubs are falsified.

It unifies three related properties to form a complete fragility diagnostic:

1. **[Structural Homogeneity](structural_homogeneity.md)** (The Presence of Hubs): Do extremely central bottleneck nodes
   exist?
2. **[$k$-connectivity](connectedness.md)** (The Collapse Threshold): What is the absolute minimum number of nodes that
   must be falsified to shatter the theory?
3. **[Structural Refutability](structural_refutability.md)** (The Damage Impact): If the top-$k$ most central
   bottlenecks are removed, how much of the theory's explanatory power (shortest paths) is destroyed?

---

## Theoretical Grounding & Model Formulation

A robust scientific theory should distribute its explanatory burden. According
to [Schurz (2014)](../../../references.md#schurz-2014), a theory-holon should possess structural homogeneity,
avoiding pathological skewness.

When Homogeneity is very low, the theory structure resembles a "star network" heavily reliant on a single central hub.
In such cases, the theory becomes highly structurally refutable ([Novacek, 2015]), as the falsification of that single
hub causes a massive drop in logical claim paths, splitting the theory into heterogeneous, disconnected parts.

By unifying these metrics, the Bottleneck Fragility Profile transitions from merely identifying a hub (Homogeneity) to
proving its vulnerability ($k$-connectivity) and quantifying the actual consequence of its failure (Refutability).

---

## Mathematical Specification

Let $G = (V, E)$ be the theory graph. The Fragility Profile is a composite report combining:

1. **Homogeneity ($H_{\text{node}}$)**: The normalized Shannon entropy of the node degree centralities. Low entropy indicates
   severe bottlenecks.
2. **Absolute Threshold ($\kappa$)**: The vertex connectivity. Defines exactly how many core concepts must fall to
   disconnect the graph.
3. **Impact Score ($R_k$)**: The Top-$k$ Refutability score.

$$ R_k (G) = \frac{|\Pi (G)|}{|\Pi (G)| + \sum_{i=1}^k |\Pi (G \setminus \{v_i\})|} $$
*(Where $\Pi (G)$ is the number of shortest paths and $v_i$ are the nodes with the highest Betweenness Centrality).*

---

## Diagnostic & Metascientific Value

| Profile Diagnosis                  | $H_{\text{deg}}$ (Homogeneity) | $\kappa$ (Threshold)   | $R_k$ (Impact) | Interpretation                                                                                                  |
|:-----------------------------------|:-------------------------------|:-----------------------|:---------------|:----------------------------------------------------------------------------------------------------------------|
| **Highly Resilient (Quinean Web)** | High                           | High                   | Low            | The theory is structurally redundant. No single node acts as a critical point of failure.                       |
| **Fragile Bottleneck (Dogmatic)**  | Low                            | Low (often $\kappa=1$) | High           | The theory relies entirely on a central dogma. Falsifying it shatters the framework.                            |
| **Modular but Resilient**          | Moderate                       | Moderate               | Moderate       | The theory has clear structural centers, but with enough crossover pathways to survive isolated falsifications. |

---

## Sub-Metric Drill Down

To understand the mathematical components driving the Fragility Profile, inspect the standalone metrics:

* **[Structural Homogeneity](structural_homogeneity.md)**: For node degree entropy and Gini coefficient calculations.
* **[Structural Refutability](structural_refutability.md)**: For shortest-path drop calculations based on Betweenness
  Centrality.
* **[Connectedness & Cohesion](connectedness.md)**: For the foundational $k$-connectivity bounds.

## Grounding References

* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, sec. 5.1.
* **[Novacek, 2015]** Novacek, V. (2015). Formalising Hypothesis Virtues in Knowledge Graphs.
