---
status: needs_verification
tags:
  - Metrics
---

# Non-CYCLIC Form (Dag Property)

## Definition & Conceptual Goal

The **Non-Cyclic Form (DAG Property)** metric assesses whether the intra-theory specialization and derivation relations
strictly form a **Directed Acyclic Graph** ([Balzer et al., 1987, pp. 172–173](../../../references.md#balzer-1987)).

In formal philosophy of science and epistemology, specializations $\alpha$ and logical derivations must be asymmetric
and strictly irreflexive. Circular specialization ($T_1 \alpha T_2 \alpha \dots \alpha T_1$) represents a fatal logical
fallacy (petitio principii / vicious circle) where a fundamental law claims grounding in a specialization that
presupposes that very same fundamental law.

---
## Theoretical Grounding & Model Formulation

The specialization relation $\alpha$ on the set of theory-elements $T$ is defined as a strict partial order:

1. **Irreflexivity**: $\forall T_i \in T, \neg (T_i \alpha T_i)$
2. **Asymmetry**: $\forall T_i, T_j \in T, (T_i \alpha T_j \implies \neg (T_j \alpha T_i))$
3. **Transitivity**: $\forall T_i, T_j, T_k \in T, (T_i \alpha T_j \land T_j \alpha T_k \implies T_i \alpha T_k)$

Consequently, a valid theory-net graph $G = (V, E_{spec})$ is mathematically required to be a DAG.

---
## Mathematical Specification & Graph Formulation

Let $G$ be a theory graph as defined in the **[Formal Graph Schema & Argumentation Semantics](../../../formal_graph_model.md)**.
We evaluate acyclicity on the subgraph restricted to hierarchical edge types, i.e., where $\lambda_e(e) \in \{\mathsf{specializes}, \mathsf{derives\_from}, \mathsf{explains}\}$.

### Binary Acyclicity Check

$$\text{IsDAG} (G) = \begin{cases} 1 & \text{if } \text{Cycles} (G) = \emptyset \\ 0 & \text{if } |\text{Cycles} (G)| > 0 \end{cases}$$

### Cycle Contamination Metric

To measure the severity of circularity in extracted candidate graphs:

$$\text{CircularityPenalty} (G) = \frac{|V_{cyclic}|}{|V|}$$

where $V_{cyclic} = \{v \in V \mid |SCC(v)| > 1 \lor (v, v) \in E\}$ is the set of vertices participating in any structural cycle, derived via Strongly Connected Components (SCCs) and self-loops.

---
## Measurement & Graph Implementation

1. **Tarjan's / Kosaraju's Algorithm**: Partition graph $G$ into strongly connected components. If any component has
   size $> 1$ or contains a self-loop, cycle violation is detected.
2. **Topological Sort**: Compute Kahn's algorithm or DFS-based topological ordering. The presence of back-edges
   indicates circular dependencies.
3. **Automated Feedback in Pipeline**:
   When a cycle is detected during pipeline execution, the cycle path is extracted and submitted to the conflict
   resolution module to determine which edge was misclassified or inverted.

---
## Diagnostic & Metascientific Value

| Measurement        | Diagnostic Finding                                                                                                      |
|:-------------------|:------------------------------------------------------------------------------------------------------------------------|
| $\text{IsDAG} = 1$ | Valid foundational hierarchy. Epistemic justification flows strictly from core axioms to peripheral applications.       |
| $\text{IsDAG} = 0$ | Logical circularity error. Edge direction inversion during relation extraction or conceptual conflation in source text. |

---
## Grounding References

* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science*. Reidel
  Publishing, pp. 172–173.
* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, pp. 119–122.
