---
status: needs_verification
tags:
  - Metrics
---

# Semantic & Axiomatic Homogeneity

## Definition & Conceptual Goal

The **Semantic & Axiomatic Homogeneity** metric evaluates the logical unity of a theory, ensuring it cannot be
factorized into disjoint, non-interacting sub-theories
([Schurz, 2014, pp. 11, 73](../../../references.md#schurz-2014)).

It prevents the famous **[Tacking Paradox (Tacking-Paradoxie)](../../../glossary.md#tacking-paradoxie)** in philosophy of
science: the illegitimate conjunctive combination of two completely unrelated theories ($T_1 \land T_2$, e.g., Newtonian
gravitation conjoined with an arbitrary theological dogma) to falsely claim unified empirical confirmation for both.

---
## Theoretical Grounding & Model Formulation

In the statement-view / logical axiomatization of theories:
Let $Ax$ be the natural axiomatization of theory $T$, and let $E (Ax)$ denote the relevant deductive consequences
of $Ax$.

### Schurz's Factorization Criterion

An axiomatization $Ax$ is **axiomatically homogeneous** (indecomposable) if and only if there exist **no** non-empty
disjoint sub-axiomatizations $Ax_1, Ax_2 \subset Ax$ ($Ax_1 \cup Ax_2 = Ax, Ax_1 \cap Ax_2 = \emptyset$) such that:

$$E (Ax) = \operatorname{Cn} (E (Ax_1) \cup E (Ax_2))$$

If such a decomposition exists, $T$ is not a genuine single theory, but an arbitrary tacking together of two independent
systems.

---
## Mathematical Specification & Graph Formulation

Let $G_{T} = (V_{Ax}, E_{\text{inf}})$ be the logical inference graph between axioms, premises, and derived empirical
theorems.

### Axiom Interaction Density ($AID$)

Let $V_{Ax}$ be partitioned into two candidate subsets $A_1, A_2$. The cross-axiom mutual inference density is:

$$AID (A_1, A_2) = \frac{|\{ (u, v) \in E_{\text{inf}} \mid (u \in A_1 \land v \in A_2) \lor (u \in A_2 \land v \in A_1)\}|}{|A_1| \cdot |A_2|}$$

### Homogeneity Factor ($H_{\text{axiomatic}}$)

$$H_{\text{axiomatic}} (T) = \min_{A_1 \cup A_2 = V_{Ax}} AID (A_1, A_2)$$

* $H_{\text{axiomatic}} (T) > 0$: Indivisible, homogeneous theoretical system.
* $H_{\text{axiomatic}} (T) = 0$: Decomposable / tacked-on system.

---
## Measurement & Graph Implementation

1. **Bipartition Inference Scan**: Check for disconnected inference subgraphs within the asserted `:Theory` node
   container.
2. **Shared Intermediate Variables**: Validate whether theorems derived by axiom set $A_1$ share intermediate
   theoretical state variables with derivations from $A_2$.
3. **Graph Decomposition Alert**: If $H_{\text{axiomatic}} = 0$, automatically propose splitting the graph into two
   separate `:Theory` instances.

---
## Diagnostic & Metascientific Value

| $H_{\text{axiomatic}}$ | Logical Structure     | Metascientific Diagnostic                                          |
|:-----------------------|:----------------------|:-------------------------------------------------------------------|
| $> 0$                  | Unified Theory        | Genuine axiomatic unity; all laws contribute to joint derivations. |
| $= 0$                  | Tacked-On Conjunction | Tacking paradox detected. Arbitrary union of unrelated hypotheses. |

---
## Grounding References

* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, pp. 11, 73.
* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science*. Reidel
  Publishing, p. 11.
