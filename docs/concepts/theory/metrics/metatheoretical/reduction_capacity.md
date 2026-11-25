---
status: in_progress
tags:
  - Metrics
---

# Reduction Capacity

## Definition & Conceptual Goal

The **Reduction Capacity** metric formalizes the rational mechanism by which a successor theory-net ($T'$) supersedes,
subsumes, and replaces an older predecessor theory-net ($T$)
([Balzer et al., 1987, p. 372](../../../references.md#balzer-1987); [Stegmüller, 1976, pp. 131, 277–278](../../../references.md#stegmuller-1976)).

Rather than falsifying and obliterating the predecessor, inter-theoretic reduction explains why the older theory worked
within its limited observational domain while translating its core functions and preserving its empirical claims under
suitable limit conditions (e.g., relativistic mechanics reducing to Newtonian mechanics as $v/c \to 0$).

---
## Theoretical Grounding & Model Formulation

Structuralism distinguishes two fundamental types of theoretical reduction:

1. **Strict Reduction ($\text{RED} (p, E, E')$)**: A translation function $p: M_p (T') \to M_p (T)$ such that actual
   models map onto actual models ($p (M (T')) \subseteq M (T)$) and the empirical claim of $T$ is deductively preserved.
2. **Approximative Direct Reduction (Type $w_1$, Formula $DVII\text{-}22$)**: Relaxing strict identity into a
   topological approximation where $p (M (T')) \approx_A M (T)$ within admissible blur boundaries.

---
## Mathematical Specification & Graph Formulation

Let $G_{T_1}$ and $G_{T_2}$ be two theory graphs with translation morphism $\phi: V (G_{T_1}) \to V (G_{T_2})$:

### Structural Preservation Ratio ($SPR$)

$$SPR (T_1, T_2) = \frac{|\{ (u, v) \in E (G_{T_1}) \mid (\phi (u), \phi (v)) \in E (G_{T_2})\}|}{|E (G_{T_1})|}$$

### Empirical Claim Invariance ($ECI$)

Let $I (T_1)$ be the intended applications of the predecessor theory:

$$ECI (T_1, T_2) = \frac{|I (T_1) \cap I (T_2)|}{|I (T_1)|}$$

### Reduction Score ($RS$)

$$RS (T_1, T_2) = \frac{1}{2} \left (SPR (T_1, T_2) + ECI (T_1, T_2) \right)$$

---
## Measurement & Graph Implementation

1. **Reduction Edge Detection**: Identify inter-theoretic `:REDUCES_TO` and `:SUBSUMES` relations between distinct
   `:TheoryNet` containers.
2. **Limit Condition Tracking**: Verify properties on reduction edges specifying the mathematical approximation limit
   parameter (e.g., `limit: "c -> infinity"`).
3. **Application Preservation Check**: Ensure the empirical domain of the predecessor is covered by the successor.

---
## Diagnostic & Metascientific Value

| $RS(T_1, T_2)$ Score | Reduction Status                    | Metascientific Diagnostic                                                                     |
|:---------------------|:------------------------------------|:----------------------------------------------------------------------------------------------|
| $RS \ge 0.8$         | Genuine Intersubjective Reduction   | Successful scientific revolution with full cumulative retention of prior empirical successes. |
| $RS < 0.4$           | Incommensurability / Paradigm Break | Predecessor concepts cannot be translated into successor without radical semantic loss.       |

---
## Grounding References

* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science*. Reidel
  Publishing, p. 372.
* **[Stegmüller, 1976]** Stegmüller, W. (1976). *The Structure and Dynamics of Theories*. Springer-Verlag, pp. 131,
  277–278.
