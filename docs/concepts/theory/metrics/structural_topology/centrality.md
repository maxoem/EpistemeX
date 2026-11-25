---
status: needs_verification
tags:
  - Metrics
---

# Centrality & Argumentative Discrepancy

## Definition & Conceptual Goal

The **Centrality & Argumentative Discrepancy** metric evaluates the systemic epistemic importance of hypotheses within a
theory-net and compares this structural prominence against textual emphasis
([Schurz, 2014, p. 119](../../../references.md#schurz-2014)).

A key phenomenon in theory reconstruction is **Argumentative Discrepancy**
(*[Argumentative Diskrepanz](../../../glossary.md#argumentative-diskrepanz)*): structurally vital, foundational axioms (such as
core conservation laws) are often rarely debated in literature because they are tacitly taken for granted, whereas
peripheral, controversial hypotheses receive heavy textual discourse. Comparing structural centrality with textual
discourse prominence exposes differences between the **context of discovery** and the **context of justification**.

---

## Theoretical Grounding & Graph Projections

Because the pipeline extracts both logical dependencies (Layer 2) and rhetorical/argumentative structures (Layer 3) into
a single unified property graph $G = (V, E)$, calculating centrality directly on $G$ conflates logical necessity with
rhetorical popularity.

To maintain mathematical cleanliness, $G$ must be projected into two distinct subgraphs:

1. **Logical-Structural Subgraph ($G_{\text{struct}}$)**: Contains only edges representing theoretical taxonomy,
   structural dependencies, and specializations (e.g., `DEPENDS_ON`, `SPECIALIZES`). This isolates the
   **Non-Statement-View** (how many models collapse if a node is removed).
2. **Argumentative-Discourse Subgraph ($G_{\text{disc}}$)**: Contains edges representing rhetoric and textual grounding
   (e.g., `SUPPORTS`, `REFUTES`, `MENTIONED_IN`). This isolates the **Statement-View** (how prominently a proposition is
   debated verbally in the source corpus).

---

## Mathematical Specification

Let $G = (V, E)$ be the global theory graph. We define projections $G_{\text{struct}} = (V, E_{\text{struct}})$
and $G_{\text{disc}} = (V, E_{\text{disc}})$.

### Structural Centrality ($C_{\text{struct}}$)

Evaluated strictly over $G_{\text{struct}}$.

1. **Out-Degree Centrality** on derivation/specialization edges:

$$
C_{\text{deg}} (v) = \frac{\text{deg}_{\text{out}} (v, G_{\text{struct}})}{|V| - 1}
$$

2. **Eigenvector Centrality**:
3.

$$
C_{\text{eigen}} (v) = \frac{1}{\lambda} \sum_{u \in \mathcal{N}_{\text{struct}} (v)} A_{uv}^{\text{struct}} x_u
$$

### Discourse Prominence Score ($S_{\text{disc}}$)

Evaluated over $G_{\text{disc}}$ and Layer 1 source mappings. $S_{\text{disc}} (v)$ can be formulated as a composite
score or as a network centrality on the rhetorical graph:

$$
S_{\text{disc}} (v) = \alpha \cdot \text{PR} (v, G_{\text{disc}}) + \beta \cdot \text{freq} (v)
$$

Where:

* $\text{PR} (v, G_{\text{disc}})$ is the PageRank or weighted In-Degree of node $v$ within the argumentative
  support/attack network (Layer 3).
* $\text{freq} (v)$ is the normalized count of `MENTIONED_IN` edges linking $v$ to source documents (Layer 1).
* $\alpha, \beta$ are weighting coefficients for rhetorical embeddedness vs. raw text volume.

### Argumentative Discrepancy Score ($AD$)

For each node $v \in V$:

$$
AD (v) = \hat{C}_{\text{struct}} (v) - \hat{S}_{\text{disc}} (v)
$$

Where $\hat{C}_{\text{struct}}$ and $\hat{S}_{\text{disc}}$ are min-max normalized to $[0, 1]$.

---

## Measurement & Graph Implementation

1. **Graph Projections**: Query the graph database (e.g., Neo4j) to create in-memory projections of $G_{\text{struct}}$
   and $G_{\text{disc}}$ using edge-type filtering.
2. **Graph Metric**: Compute PageRank or Eigenvector Centrality over $G_{\text{struct}}$.
3. **Discourse Metric**: Compute PageRank over $G_{\text{disc}}$ and aggregate with `MENTIONED_IN` frequency.
4. **Discrepancy Matrix**: Scatter plot $\hat{C}_{\text{struct}}$ vs. $\hat{S}_{\text{disc}}$ to isolate
   high-discrepancy nodes.

---

## Diagnostic & Metascientific Value

| Structural Centrality ($C_{\text{struct}}$) | Low Discourse Prominence ($S_{\text{disc}}$)                           | High Discourse Prominence ($S_{\text{disc}}$)                              |
|:--------------------------------------------|:-----------------------------------------------------------------------|:---------------------------------------------------------------------------|
| **High**                                    | **Tacit Paradigm Core** <br>*(Implicit foundation, taken for granted)* | **Explicit Core Law** <br>*(Major structural impact & heavily debated)*    |
| **Low**                                     | **Peripheral Assumption** <br>*(Minor detail, low importance)*         | **Fringe Controversy** <br>*(Heavy textual debate, low structural impact)* |

* **High Structural + Low Discourse**: Implicit foundational presupposition (hard core).
* **Low Structural + High Discourse**: Transient controversy / rhetorical emphasis without fundamental theoretical
  disruption.

---

## Grounding References

* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, p. 119, sec. 5.1.
* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science*. Reidel
  Publishing, p. xxix.
