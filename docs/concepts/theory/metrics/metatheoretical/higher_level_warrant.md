---
status: in_progress
tags:
  - Metrics
---

# Higher-Level Warrant

## Definition & Conceptual Goal

The **Higher-Level Warrant** metric models how scientific hypotheses gain indirect credibility and justification when
they are themselves explained by deeper, higher-level fundamental theories
([Thagard, 1989, p. 441](../../../references.md#thagard-1989); [Schurz, 2014, sec. 5.3](../../../references.md#schurz-2014)).

An empirical hypothesis (such as Kepler's laws of planetary motion) does not solely rely on direct observational data;
its epistemic warrant is substantially amplified once it is deductively derived from or explained by a superordinate
fundamental theory (such as Newton's gravitational mechanics).

---
## Theoretical Grounding & Model Formulation

In Thagard's Principle of Higher-Level Coherence:

* If higher-level theory $T_{\text{high}}$ explains intermediate hypothesis $H_{\text{mid}}$, an excitatory
  link $(T_{\text{high}}, H_{\text{mid}})$ is established with weight $w_{\text{warrant}} > 0$.
* Activation cascades downward: confidence in well-established foundational paradigms reinforces the acceptability of
  intermediate empirical generalizations.

---
## Mathematical Specification & Graph Formulation

Let $H \in V_H$ be a target hypothesis. Let $\text{Sup} (H) = \{T_1, T_2, \dots, T_k\}$ be the set of higher-level
theory nodes possessing directed explanatory links $(T_i, H) \in E_{\text{warrant}}$.

### Higher-Level Warrant Score ($HLW$)

$$HLW (H) = \sum_{T \in \text{Sup} (H)} w (T, H) \cdot a_T (t)$$

where $a_T (t)$ is the current activation level of the higher-level theory node $T$, and $w (T, H)$ is the positive
warrant weight.

### Depth of Justification ($DoJ$)

$$DoJ (H) = \max_{p \in \text{Paths}_{\text{root}} (H)} \text{length} (p)$$

representing the maximum depth of vertical deductive grounding leading to $H$.

---
## Measurement & Graph Implementation

1. **Vertical Hierarchy Detection**: Identify incoming directed `:EXPLAINS` or `:JUSTIFIES` edges originating from
   superordinate theory-element nodes.
2. **Activation Propagation**: In the ECHO relaxation pass, include vertical excitatory channels.
3. **Property Graph Labeling**: Nodes with $HLW > 0$ are marked with `:PossessesHigherWarrant`.

---
## Diagnostic & Metascientific Value

| $DoJ(H)$ Depth | Epistemic Justification     | Metascientific Status                                                    |
|:---------------|:----------------------------|:-------------------------------------------------------------------------|
| $DoJ \ge 2$    | Deeply Grounded             | Multi-tier theoretical justification (embedded in scientific hierarchy). |
| $DoJ = 1$      | Directly Grounded           | Explained by a single immediate law.                                     |
| $DoJ = 0$      | Phenomenological / Isolated | Pure empirical rule lacking higher theoretical explanation.              |

---
## Grounding References

* **[Thagard, 1989]** Thagard, P. (1989). Explanatory Coherence. *Behavioral and Brain Sciences*, 12 (3), p. 441.
* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, sec. 5.3.
