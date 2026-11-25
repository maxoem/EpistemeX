---
status: needs_verification
tags:
  - Metrics
---

# Structural Homogeneity

## Definition & Conceptual Goal

The **Structural Homogeneity** metric assesses the degree of structural balance and topological uniformity across a
theory-net or theory-holon ([Schurz, 2014, sec. 5.1](../../../references.md#schurz-2014)).

It determines whether empirical indicators and specialization branches are uniformly integrated across the graph or
whether the topology exhibits pathological skewness (e.g., hyper-concentrated hub bottlenecks or severely
under-specified peripheral components).

!!! note "Composite Index Context"
    This is a foundational metric. In our taxonomy, the presence of pathological hubs (low Homogeneity) is combined with
    their collapse threshold ($k$-connectivity) and impact (Refutability) to form the overall
    **[Bottleneck Fragility Profile](bottleneck_fragility.md)**.

!!! info "Scope & Theoretical Boundaries"

    * **Single-Mode Projection**: To satisfy the structuralist requirement of "type-homogeneity" (Balzer et al., 1987), this
    topological metric is ideally calculated on a specific, unified projection of the property graph (e.g., restricting to
    a  single node type and relation class like `SPECIALIZES`). 
    * **Factorizability**: The question of whether a theory
    factorizes into disconnected components (Schurz, 2013) is conceptually related but measured separately in our pipeline
    via **[Connectedness & Cohesion](connectedness.md)**.

---

## Theoretical Grounding & Model Formulation

A theoretically robust graph displays balanced structural branching where theoretical concepts maintain consistent
explanatory obligations. Pathological topological asymmetry often signals incomplete relation extraction, unbalanced
text coverage, or ungrounded conceptual leaps.

---

## Mathematical Specification & Graph Formulation

Let $G = (V, E, \lambda_v, \lambda_e)$ be the full heterogeneous theory graph. To ensure type-homogeneity and eliminate
structural noise from auxiliary relationships (e.g., provenance or logical metadata), we calculate the metric on a
strict **Single-Mode Projection** $G' = (V', E')$ where:

$$
V' = \{v \in V \mid \lambda_v (v) \in T_{\text{target}}\}
$$

$$
E' = \{e= (u,v) \in E \mid u,v \in V' \land \lambda_e (e) \in R_{\text{target}}\}
$$

*(where $T_{\text{target}}$ and $R_{\text{target}}$ are the sets of structurally relevant node and edge types, e.g.,
$\small\mathsf{CONCEPT}$ and $\small\mathsf{SPECIALIZES}$).*

Let the projected graph $G'$ have the degree sequence $K = \{k_1, k_2, \dots, k_n\}$
where $k_i = \text{deg}_{G'} (v_i)$.

### Node Degree Entropy ($H_{\text{node}}$)

Let $p_i$ be the relative degree centrality of a node $v_i \in V$, representing its share of the graph's total
connections:

$$p_i = \frac{\text{deg} (v_i)}{\sum_{j=1}^{|V|} \text{deg} (v_j)}$$

The structural entropy of the network is given by the Shannon entropy of this node distribution:

$$H_{\text{node}} (G) = -\sum_{i=1}^{|V|} p_i \log_2 p_i$$

Normalized structural homogeneity score (where $\log_2 |V|$ is the maximum possible entropy, achieved when all nodes
have the exact same degree):

$$\text{Homogeneity}_{\text{struct}} (G) = \frac{H_{\text{node}} (G)}{\log_2 |V|}$$

### Degree Variance & Gini Coefficient

The variance of node degree:

$$\sigma^2_{\text{deg}} = \frac{1}{|V|} \sum_{v \in V} (\text{deg} (v) - \mu_{\text{deg}})^2$$

A lower degree Gini coefficient corresponds to higher structural uniformity across theory elements.

---

## Measurement & Graph Implementation

1. **Degree Distribution Extraction**: Extract in-degree, out-degree, and total degree histograms across all theory
   element nodes.
2. **Entropy Calculation**: Compute Shannon entropy of the degree distribution.
3. **Outlier Identification**: Identify nodes with degree deviating by $> 3\sigma$ from the mean.

---

## Diagnostic & Metascientific Value

| Metric Value                           | Topology                  | Diagnostic Finding                                                           |
|:---------------------------------------|:--------------------------|:-----------------------------------------------------------------------------|
| High Homogeneity ($\approx 0.8 - 1.0$) | Balanced Tree/Mesh        | Uniformly articulated scientific framework with balanced empirical coverage. |
| Very Low Homogeneity ($< 0.3$)         | Extreme Star / Bottleneck | Fragile theoretical architecture or heavily biased textual extraction.       |

---

## Grounding References

* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, sec. 5.1.
* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science*. Reidel
  Publishing, p. 224.
