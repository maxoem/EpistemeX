---
status: in_progress
tags:
  - Metrics
---

# Unification

## Definition & Conceptual Goal

The **Unification** metric favors theoretical frameworks that repeatedly use a compact, unified set of core hypotheses
and argument patterns to explain a large volume of diverse phenomena
([Schurz, 2014, pp. 6, 317–320](../../../references.md#schurz-2014); [Thagard, 1989, p. 441](../../../references.md#thagard-1989)).

In Kitcher's and Schurz's models of scientific explanation, explanatory unification maximizes the ratio of derived
explanatory conclusions to the number of fundamental un-derived basic assumptions (axioms and initial facts).

---
## Theoretical Grounding & Model Formulation

Let an explanatory belief system $S$ have a set of relevant content elements $Ce (S)$. The content elements are
partitioned into:

* **Basic Elements ($B$)**: Non-derivable core axioms, fundamental laws, and brute initial facts.
* **Derived Elements ($D$)**: Theorems, empirical predictions, and explained observational facts derived deductively or
  probabilistically from $B$.

$$Ce (S) = B \cup D \quad \text{where} \quad B \cap D = \emptyset$$

---
## Mathematical Specification & Graph Formulation

On the deductive derivation DAG $G = (V, E_{\text{derive}})$:

### Schurz Unification Ratio ($U_{\text{ratio}}$)

$$U_{\text{ratio}} (S) = \frac{|D|}{|B|} = \frac{|Ce (S) \setminus B|}{|B|}$$

### Global Unification Index ($GUI$)

Normalized against total system content size:

$$GUI (S) = \frac{|D|}{|B| + |D|} = \frac{|D|}{|Ce (S)|} \in [0, 1)$$

* $GUI \to 1$: Highly unified theory (a tiny set of axioms derives vast empirical consequences).
* $GUI = 0$: Completely un-unified theory (no derivations; every fact is treated as a separate brute assumption).

---
## Measurement & Graph Implementation

1. **Partition Graph Nodes**: Classify graph nodes with 0 in-degree in derivation chains as $B$ (`:BasicAxiom` /
   `:InitialFact`).
2. **Count Derived Nodes**: Identify nodes with in-degree $> 0$ along valid inference paths as $D$ (`:DerivedTheorem` /
   `:ExplainedFact`).
3. **Cypher Query**:
   ```cypher
   MATCH (t:Theory {id: $id})-[:CONTAINS]->(n:Proposition)
   WITH count(n) AS total_nodes
   MATCH (t)-[:CONTAINS]->(b:Proposition)
   WHERE NOT (b)<-[:DERIVED_FROM]-(:Proposition)
   WITH total_nodes, count(b) AS basic_count
   RETURN (total_nodes - basic_count) * 1.0 / basic_count AS unification_ratio
   ```

---
## Diagnostic & Metascientific Value

| Unification Ratio $|D|/|B|$ | Unification Level | Metascientific Significance | | :--- | :--- | :--- | | $\gg 5.0$ |
High Unification | Exemplary scientific theory (e.g., Maxwell's equations, general relativity). | | $\approx 1.0$ |
Moderate Unification | Specialized model with equal proportion of assumptions to conclusions. | | $< 0.2$ | Fragmented /
Ad-Hoc | Epistemically weak system; excessive arbitrary assumptions. |

---
## Grounding References

* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, pp. 6, 317–320.
* **[Thagard, 1989]** Thagard, P. (1989). Explanatory Coherence. *Behavioral and Brain Sciences*, 12 (3), p. 441.
