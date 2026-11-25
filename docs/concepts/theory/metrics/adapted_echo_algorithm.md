---
status: in_progress
tags:
  - Algorithms
  - Metrics
---

# The Symmetrized LPG-ECHO Lens

## Overview & Role in Episteme

The **Symmetrized LPG-ECHO Lens** (*ECHO for Large Property Graphs*) is a **secondary analytical coherence lens** complementing Episteme's primary directed **Continuous D-QBAF** engine ([Formal Graph Schema & Argumentation Semantics](../../formal_graph_model.md#3-uncertainty-ontology-and-d-qbaf-gradual-semantics)). Grounded in Paul Thagard's Theory of Explanatory Coherence ([Thagard, 1989](../../references.md#thagard-1989); [Thagard, 1992](../../references.md#thagard-1992)), it evaluates global explanatory constraint satisfaction via parallel activation relaxation over an explicitly symmetrized projection of the Layer 3 Dialectical Argument Graph ($\mathcal{D}$).

## Explicit Symmetrization Map ($\mathcal{D} \to \text{ECHO}$)

Because Episteme's Layer 3 graph $\mathcal{D}$ is directed and bipartite (carrying conjunctive premise warrants $w_k \in \mathcal{W}$), projecting into ECHO applies a deterministic symmetrization map (`epistemetrics.epistemic.lenses.project_to_echo_network`):

- **Explanatory Support with Co-Hypothesis Dilution (TEC Principle E2):** Each supporting warrant with $m = |\operatorname{Prem}(w_k)|$ conjunctive premises explaining conclusion $q$ creates symmetric excitatory weights $w_{pq}^{\text{echo}} = (\epsilon^+ / m) W_{w_k}$ between each premise $p \in \operatorname{Prem}(w_k)$ and $q$, and between every pair of co-hypotheses $(p, p')$.
- **Dialectical Contradiction / Attack (TEC Principle E5):** Each attacking warrant contributes symmetric inhibitory weight $w_{pq}^{\text{echo}} = -\epsilon^- W_{w_k}$.
- **Defeasible Data Priority (TEC Principle E4):** Evidential base atoms (`ObservationUnit` / `EMPIRICAL`) receive excitatory input from a fixed special evidence unit clamped at $+1.0$ (rather than hard-clamping observation nodes themselves, preserving defeasibility under overwhelming contradiction).
- **Structural Exclusions:** Polarity-`0` structural relations (including `ALTERNATIVE_READING_OF`) are excluded from the signed ECHO matrix.

---

## Relaxation Dynamics & Global Harmony

In the symmetrized ECHO network:

* **Nodes (Units)**: Represent propositions, hypotheses, axioms, and evidential base units with continuous activation $a_j^{\text{echo}}(t) \in [-1, 1]$.
* **Edges (Symmetric Weights)**: Undirected excitatory ($w_{ij}^{\text{echo}} > 0$) and inhibitory ($w_{ij}^{\text{echo}} < 0$) weights with $w_{ij}^{\text{echo}} = w_{ji}^{\text{echo}}$.
* **Bounded Synchronous Update**: At each iteration $t$, with $\text{net}_j(t) = \sum_i w_{ij}^{\text{echo}} a_i^{\text{echo}}(t)$:
  $$a_j^{\text{echo}}(t+1) = a_j^{\text{echo}}(t)(1 - \theta) + \begin{cases} \text{net}_j(t)\,(1 - a_j^{\text{echo}}(t)) & \text{if } \text{net}_j(t) > 0 \\ \text{net}_j(t)\,(a_j^{\text{echo}}(t) + 1) & \text{if } \text{net}_j(t) \le 0 \end{cases}$$
* **Global Harmony ($\mathcal{H}_{\text{echo}}$)**: At convergence $t^*$, the Hopfield-type global coherence score is $\mathcal{H}_{\text{echo}}(t^*) = \sum_{i,j} w_{ij}^{\text{echo}} a_i^{\text{echo}}(t^*) a_j^{\text{echo}}(t^*)$.

---

## System Skepticism & Decay Dynamics

The resistance of the network to ungrounded or speculative hypotheses is governed by the **System Skepticism / Decay Parameter** ($\theta \in (0, 1)$), originally formalized by Thagard (1989, p. 443).

### Intrinsic Decay Dynamics

In the absence of net positive input from evidentiary nodes ($\text{net}_j (t) \le 0$), a hypothesis node's activation decays exponentially back toward neutrality:

$$a_j (t) = a_j (0) \cdot (1 - \theta)^t$$

### Half-Life of Unsupported Beliefs ($t_{1/2}$)

The half-life of an unsupported proposition (the number of relaxation cycles before initial confidence is halved) is:

$$t_{1/2} = \frac{\ln (0.5)}{\ln (1 - \theta)}$$

For the canonical standard setting $\theta = 0.05$:
$$t_{1/2} \approx \frac{-0.693}{-0.0513} \approx 13.5 \text{ iterations}$$

### Epistemic Diagnostic Profile

| Skepticism Parameter $\theta$ | Epistemic Stance            | Solver Behavior                                                                      |
|:------------------------------|:----------------------------|:-------------------------------------------------------------------------------------|
| $\theta < 0.02$               | Credulous / Gullible        | Speculative auxiliary hypotheses survive without solid data support.                 |
| $\theta \approx 0.05$         | Normative Epistemic Balance | Standard scientific skepticism; requires continuous evidentiary backing.             |
| $\theta > 0.15$               | Hyper-Skeptical             | Even well-grounded theories struggle to propagate activation to higher-level axioms. |

Propositions whose activation collapses to $< 0.01$ under normative decay are formally diagnosed as **unsupported speculation ("ghost nodes")**.

---

## Implicitly Collected Metrics

The true power of the LPG-ECHO algorithm is that its convergence state mathematically synthesizes multiple distinct
metrics. By running this single algorithm, we implicitly collect or account for the following theoretical properties:

### A. Epistemic Coherence Metrics

1. **Node Activation (Acceptability)**: Directly calculated. The final equilibrium state $a_j^*$ determines if a
   hypothesis is accepted, rejected, or neutral.
2. **System Coherence (Harmony, $H$)**: The global energy state of the network at convergence directly measures the
   overall consistency and lack of contradictions across the paradigm.
3. **Simplicity / Elegance**: Implicitly captured. Complex explanations (those requiring many auxiliary co-hypotheses)
   suffer from excitation dilution. Simpler explanations automatically channel higher, undistiluted excitation to their
   conclusions, naturally favoring Occam's Razor.
4. **Conservatism / Tenability**: Implicitly captured by the temporal persistence of node activations. Established
   paradigm nodes resist deactivation from minor anomalies unless overwhelmed by a highly coherent alternative theory.

### B. Empirical Power Metrics

5. **Explanatory Breadth**: Implicitly captured. A theory node that explains many distinct empirical evidence nodes
   receives excitatory feedback from all of them, naturally driving its activation toward $+1.0$.
6. **Construct Validity / Empirical Adequacy**: Evidence nodes are hard-clamped to $+1.0$. The flow of this empirical
   certainty upward into the theoretical layers intrinsically measures how well grounded the theory is in observation.
7. **Ratio of Axioms vs. Observations (Unification)**: While we explicitly measure this via the Schurz Unification
   Ratio, ECHO implicitly models it. A theory with too few observations and too many ungrounded axioms will suffer from
   baseline decay, as the clamped empirical activation is insufficient to keep the vast theoretical network "alive."

### C. Metatheoretical Metrics

8. **Higher-Level Warrant**: Implicitly captured by adding vertical excitatory channels from higher-level paradigm nodes
   down to specific theory nodes.
9. **Analogical Support**: Modeled by excitatory horizontal links between distinct but structurally similar domains,
   allowing them to mutually boost each other's activation.

---

## Grounding References

* **[Thagard, 1989]** [Thagard, P. (1989)](../../references.md#thagard-1989). Explanatory Coherence. *Behavioral and Brain Sciences*, 12(3), 435–467.
* **[Thagard, 1992]** [Thagard, P. (1992)](../../references.md#thagard-1992). *Conceptual Revolutions*. Princeton University Press.
* **[Schurz, 2014]** [Schurz, G. (2014)](../../references.md#schurz-2014). *Philosophy of Science: A Unified Approach*. Routledge.
