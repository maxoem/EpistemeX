---
status: needs_verification
tags:
  - Metrics
---

# Kuhnian / Paradigm-Guidance

## Definition & Conceptual Goal

The **Kuhnian / Paradigm-Guidance** metric evaluates whether the historical evolution of a theory-net represents
coherent "normal science" or erratic, ad-hoc shifts
([Balzer et al., 1987, pp. 175–176](../../../references.md#balzer-1987); [Stegmüller, 1976, pp. 169–171, 194](../../../references.md#stegmuller-1976)).

In Kuhn's philosophy of science (as formalized structurally by Stegmüller), normal scientific research proceeds by
developing specialized laws in the outer branches of a theory-net that strictly descend from an immutable paradigmatic
core ($K_0$), while leaving the core laws protected and stable.

---

## Theoretical Grounding & Model Formulation

A historical sequence of theory-nets $\langle N_1, N_2, \dots, N_k \rangle$ is **paradigm-guided** iff:

1. **Core Invariance**: There exists a fundamental paradigm core $K_0$ present in every net $N_t$.
2. **Core Specialization**: All newly introduced theory-elements $K_i (t)$ at subsequent times are formal core
   specializations ($K_i (t) \alpha K_0$) of the root paradigm $K_0$.
3. **Domain Conservation**: The fundamental paradigm applications $I_0$ remain continuously embedded in the intended
   application set ($I_0 \subseteq I (t)$).

---

## Formal Specification

The formal framework addresses limitations in basic graph coverage models by explicitly tracking specialization
filtering, incremental dynamics, and domain conservation.

### A. Refined Paradigm Adherence Ratio ($PAR$)

Let $G_t = (V (G_t), E (G_t))$ be the directed graph representing the theory-net at revision stage $t$, where
vertices $V (G_t)$ denote the set of all active theory-elements. Let $T_0 \in V (G_1)$ denote the foundational paradigm
root node established at inception.

To ensure nodes correctly align with the paradigm, we restrict paths to directed specialization
edges $E_\alpha \subseteq V (G_t) \times V (G_t)$, where $(T_i, T_j) \in E_\alpha$ signifies that $T_j$ is a direct
formal specialization of $T_i$. We denote the existence of a directed specialization path from $T_0$ to $T$ via the
reflexive-transitive closure over $E_\alpha$, written as $T_0 \xrightarrow{\alpha, *} T$.

The Paradigm Adherence Ratio is then defined as:

$$PAR (G_t, T_0) = \frac{\big\lvert \{ T \in V (G_t) \mid T_0 \xrightarrow{\alpha, *} T \} \big\rvert}{\lvert V (G_t) \rvert}$$

* **Interpretation**: $PAR \in [0.0, 1.0]$. A value of $1.0$ indicates that every node in $G_t$ strictly descends
  from $T_0$ through a chain of formal specializations.

### B. Incremental Paradigm Adherence Ratio ($\Delta PAR_t$)

To prevent historical nodes from masking recent unguided additions, we define the adherence ratio specifically for newly
added nodes $\Delta V_t = V (G_t) \setminus V (G_{t-1})$:

$$\Delta PAR_t (G_t, T_0) = \begin{cases} \frac{\big\lvert \{ T \in \Delta V_t \mid T_0 \xrightarrow{\alpha, *} T \} \big\rvert}{\lvert \Delta V_t \rvert} & \text{if } \lvert \Delta V_t \rvert > 0 \\ 1.0 & \text{if } \lvert \Delta V_t \rvert = 0 \end{cases}$$

### C. Domain Conservation Index ($DCI_t$)

Let $I_0 \subseteq M_{pp}$ be the initial paradigmatic intended applications established by the founders, and
let $I (t) \subseteq M_{pp}$ denote the total set of intended applications claimed by the theory-net at revision $t$.

To operationalize Kuhn's condition that original paradigm applications ($I_0$) must not be discarded during revisions,
we define:

$$DCI (I (t), I_0) = \frac{\lvert I_0 \cap I (t) \rvert}{\lvert I_0 \rvert}$$

* **Interpretation**: $DCI = 1.0$ iff $I_0 \subseteq I (t)$ (full conservation). If $DCI < 1.0$, intended paradigm
  applications are being abandoned, signaling an anomaly or domain shift.

### D. Core Stability Predicate ($\text{CoreStable}$)

Let $K_0 (t) = (M_p, M_{pp}, M, GC, GL)_0$ be the core tuple of $T_0$ at time step $t$:

$$\text{CoreStable} (G_1, \dots, G_k) = \begin{cases} 1 & \text{if } \big|\bigcap_{t=1}^k M_0 (t)\big| = \lvert M_0 (1) \rvert \text{ and } \big|\bigcap_{t=1}^k GC_0 (t)\big| = \lvert GC_0 (1) \rvert \\ 0 & \text{otherwise} \end{cases}$$

### E. Composite Paradigm Guidance Index ($PGI_t$)

Combining structural core adherence and empirical domain conservation into a single score ($w_1 + w_2 = 1$):

$$PGI (G_t, T_0) = \text{CoreStable} (G_1, \dots, G_t) \cdot \left[ w_1 \cdot PAR (G_t, T_0) + w_2 \cdot DCI (I (t), I_0) \right]$$

---

## Refinement Diagnostic Scale

| $PGI$ Score             | Research Dynamic             | Metascientific Interpretation                                                                |
|:------------------------|:-----------------------------|:---------------------------------------------------------------------------------------------|
| **$PGI = 1.0$**         | **Pure Normal Science**      | All theoretical nodes descend from $T_0$ and all original applications $I_0$ are preserved.  |
| **$0.5 \le PGI < 1.0$** | **Auxiliary Shifts / Drift** | Emergence of semi-independent models or minor loss of original application domain.           |
| **$PGI < 0.5$**         | **Paradigm Crisis**          | Severe fragmentation; newly introduced models bypass $T_0$ or fundamental applications fail. |

---

## Updated Graph Implementation (Cypher)

To match the refined mathematical specification $T_0 \xrightarrow{\alpha, *} T$, the database query must explicitly
specify the relationship type `:SPECIALIZES`:

```cypher
// Query to identify unguided nodes (nodes not reachable via specialization from paradigm root)
MATCH (root:TheoryElement {is_paradigm_core: true, theory_id: $theory_id})
MATCH (t:TheoryElement {theory_id: $theory_id})
WHERE t <> root 
  AND NOT (root)-[:SPECIALIZES*]->(t)
RETURN 
  count(t) AS unguided_node_count,
  collect(t.id) AS unguided_node_ids;
```

---

## Grounding References

## References & Theoretical Grounding

* **Balzer, W., Moulines, C. U., & Sneed, J. D. (1987).** *An Architectonic for Science*. D. Reidel Publishing Company.

* **Stegmüller, W. (1976).** *The Structure and Dynamics of Theories*. Springer-Verlag.

* **Schurz, G. (2014).** *Philosophy of Science: A Unified Approach*. Routledge.

* **Newman, M. (2018).** *Networks* (2nd ed.). Oxford University Press.

* **Nováček, V. (2015).** Formalising Hypothesis Virtues in Knowledge Graphs: A General Theoretical Framework and its
  Validation in Literature-Based Discovery Experiments. *arXiv:1503.09137*.