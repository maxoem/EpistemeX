---
status: needs_verification
tags:
  - Metrics
---

# Tree / Hierarchical Conformity

## Definition & Conceptual Goal

The **Hierarchical Conformity** metric (or *Theory-Tree Conformity*) evaluates whether a directed specialization graph strictly conforms to a single-rooted hierarchical branching structure ([Balzer et al., 1987, p. 175](../../../references.md#balzer-1987)).

In the structuralist architecture of scientific theories, a mature and well-founded scientific theory does not have multiple conflicting foundational cores; rather, it is anchored in a unique, fundamental root theory-element ($T_0$) from which all further domain-specific laws branch out via successive specializations. This metric measures the macroscopic structural integrity of this deductive specialization hierarchy.

---

## Theoretical Grounding, Graph Granularity & The Nature of $T_0$

A critical distinction must be made regarding the granularity of the graph. A theory-net is not a single atomic proposition or isolated equation. It is a macro-logical **Theory-Element** defined as $T = \langle K, I \rangle$, where $K$ is the theoretical core and $I$ represents the intended applications.

The core ($K = \langle M_p, M, M_{pp}, C, L \rangle$) encapsulates a set of interdependent fundamental laws (which jointly define the actual models $M$). Internally, these fundamental laws are non-hierarchical; they combine via logical conjunction and mutually presuppose one another.

Consequently, the root element $T_0$ is inherently a clustered group of cooperating axioms (e.g., Newton's laws of motion, absolute space, and universal gravitation operating together as a unified paradigmatic core). If this metric is applied to a micro-level knowledge graph where individual axioms are modeled as separate nodes, applying the hierarchy metric directly is epistemically invalid. Foundational cooperating axioms must first be aggregated into a single macro-node $T_0$.

---

## Prerequisites for $T_0$: Micro-Cohesion & Validity

To prevent the artificial grouping of disjoint axioms into a "fake" $T_0$ merely to achieve a perfect hierarchy score, the micro-cohesion of the foundational set must be validated before the macro-metric is applied.

For a set of individual laws or axioms to be legitimately grouped into the root core $K_0$, they must satisfy strict internal coherence criteria evaluated by separate micro-level graph metrics:

1. **Logical Consistency:** The elements must not contradict one another.
2. **Mutual Constraint (Cross-Binding):** The axioms must share theoretical terms and jointly constrain the intended applications. In a directed dependency graph, they should form a Strongly Connected Component (SCC) of mutual presupposition.
3. **High Internal Density:** The propositions within $T_0$ must exhibit dense horizontal relations (e.g., `PRESUPPOSES`, `SHARES_VARIABLE`, `CONSTRAINS`).

If a proposed root cluster fails these micro-cohesion checks, it cannot be legitimately grouped into a single $T_0$. The theory is technically fragmented, and the root count $\vert{}B(N)\vert{}$ must reflect multiple independent cores.

---

## Mathematical Specification & Graph Formulation

Let $G = (V, E)$ be the Directed Acyclic Graph (DAG) of specialization relations where directed edges $(u, v) \in E$ indicate $u \text{ specializes } v$ (or in parent-child representation, $(v, u) \in E_{spec}$ where $v$ is generalized into child $u$). It is assumed that $G$ is a proper theory-net where valid foundational clusters have been condensed into macroscopic theory-elements.

We define the set of **top-elements** (or minimal elements with respect to generalization, i.e., root elements) as $B(N)$:

$$B(N) = \{T_i \in T \mid \forall T_j \in T \, (T_j \alpha T_i \implies T_j = T_i)\}$$

A connected theory-net $N$ is a **Theory-Tree** (*Theorie-Baum*) if and only if:

1. $B(N)$ is a **singleton**: $\vert{}B(N)\vert{} = 1$, denoted as $B(N) = \{T_0\}$.
2. The transitive reduction of $\alpha$ forms an out-tree (arborescence) rooted at $T_0$, meaning every non-root node $T_k \in T \setminus \{T_0\}$ has exactly one immediate predecessor in the specialization hierarchy.

### Tree Conformity Score

We define the metric score $S_{tree}(G) \in [0, 1]$ as:

$$S_{tree}(G) = \begin{cases} 1 & \text{if } \vert{}B(N)\vert{} = 1 \land \forall u \in V \setminus \{T_0\}, \, \text{in-deg}_{spec}(u) = 1 \\ \frac{1}{\vert{}B(N)\vert{}} \cdot \left(1 - \frac{\sum_{u \in V} \max(0, \text{in-deg}_{spec}(u) - 1)}{\vert{}E\vert{}} \right) & \text{otherwise} \end{cases}$$

Where:

* $\vert{}B(N)\vert{}$ is the number of root macro-nodes (nodes with 0 in-degree in parent-to-child orientation).
* $\text{in-deg}_{spec}(u)$ is the number of immediate generalizing parents for node $u$.

---

## Measurement & Graph Implementation

1. **Micro-Cohesion Validation & Graph Condensation**: If operating on a micro-level proposition graph, verify the mutual constraint of foundational axioms. Collapse valid, strongly connected foundational components (SCCs) into a single macro-node $T_0$.
2. **Root Identification**: Compute the in-degree in parent-to-child orientation for all nodes in the theory-net subgraph. Filter nodes with in-degree equal to 0 to establish $B(N)$.
3. **Branching Factor & Multiple Inheritance**: Count the number of nodes that have multiple parent specializations. In property graphs, multiple parents indicate either poly-specialization (legitimate cross-specialization from two cores) or structural ambiguity requiring consolidation.
4. **Neo4j Cypher Check (Macro-Level)**:
```cypher
MATCH (t:TheoryElement {theory_id: $theory_id})
WHERE NOT (t)-[:SPECIALIZES]->(:TheoryElement {theory_id: $theory_id})
RETURN count(t) AS root_count

```

---

## Diagnostic & Metascientific Value

| Root Count $\vert{}B(N)\vert{}$ | Structure | Metascientific Diagnostic |
| --- | --- | --- |
| $\vert{}B(N)\vert{} = 1$ | Pure Theory-Tree | Paradigmatic normal science. The core $K_0$ successfully and uniquely anchors all branching laws. |
| $\vert{}B(N)\vert{} > 1$ | Multi-Root Forest | Conceptual fracture. Conflation of multiple independent paradigms, unvalidated $T_0$ grouping, or missing unifying axiom. |
| Multiple Parents | Poly-Net / Lattice | Synthesis of distinct theoretical streams within one program, indicating cross-pollination of specific laws. |

---

## Grounding References

* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science*. Reidel Publishing, pp. 172–176.
* **[Stegmüller, 1976]** Stegmüller, W. (1976). *The Structure and Dynamics of Theories*. Springer-Verlag, pp. 169–171.