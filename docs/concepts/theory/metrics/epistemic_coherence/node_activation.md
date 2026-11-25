---
status: needs_verification
tags:
  - Metrics
---

# Node Activation (Acceptability)

## Definition & Conceptual Goal

The **Node Activation (Acceptability)** metric represents the final, equilibrium epistemic status—acceptance, rejection,
or neutrality—of an individual proposition or hypothesis after global network relaxation. Here, "final" means the steady
state reached when the network converges, defined mathematically as $a_i^* = \lim_{t \to \infty} a_i (t)$
([Thagard, 1989, p. 439](../../../references.md#thagard-1989); [Schurz, 2014, sec. 5.3](../../../references.md#schurz-2014)).

Rather than evaluating hypotheses in isolation, node activation models how empirical data cascades through explanatory,
analogical, and contradictory links until each node settles into a continuous equilibrium value $a_i^* \in [-1, 1]$.

---

## Theoretical Grounding & Model Formulation

In the connectionist ECHO model, each node $j$ updates its activation $a_j (t)$ at each discrete time step. The
state $a_j (t)$ represents the current continuous degree of acceptability or confidence of the node. The update is based
on:

1. Decay parameter ($\theta$).
2. Total incoming input ($\text{net}_j (t)$) from neighboring nodes $i$.
3. Ceiling and floor bounds ($a_{\max} = 1.0, a_{\min} = -1.0, a_{\text{decay}} = 0.0$).

---

## Mathematical Specification & Graph Formulation

Let the net input to node $j$ at time $t$ be defined as the aggregate function of connected neighbors:

$$\text{net}_j (t) = \sum_{i=1}^N w_{ij} a_i (t)$$

Here, $a_i (t)$ is the continuous activation (confidence/acceptability) of the neighbor node $i$ at time $t$.
At $t=0$, $a_i (0)$ is initialized using the prior plausibility function $\tau (a_i)$ (as defined in the underlying
TheoryNet Quantitative Bipolar Argumentation Framework).

The connection weights $w_{ij}$ map directly to the edge labeling function $\lambda_e (e)$ and the continuous weight
function $\phi (a_i, a_j)$ from TheoryNet. Specifically, this metric operates on the following edge types:

* **Supportive relations ($\mathcal{R}_{sup}$):** Mapped to positive weights $w_{ij} > 0$.
* **Attacking/Undermining relations ($\mathcal{R}_{att}$):** Mapped to negative weights $w_{ij} < 0$.

By aggregating the node plausibility ($\tau$) and the edge confidence/weight ($\phi$), the total update function allows
local empirical evidence to propagate globally. This continuous summation correlates directly with the structural
coherence of the graph: propositions strongly supported by evidence and aligned with other accepted claims mutually
reinforce each other, while contradictory claims suppress each other, dynamically resolving theoretical conflicts.

The activation update rule is:

$$a_j (t+1) = \begin{cases} a_j (t)(1 - \theta) + \text{net}_j (t)(a_{\max} - a_j (t)) & \text{if } \text{net}_j (t) > 0 \\ a_j (t)(1 - \theta) + \text{net}_j (t)(a_j (t) - a_{\min}) & \text{if } \text{net}_j (t) \le 0 \end{cases}$$

Where:

* $\theta \in (0, 1)$ is the decay rate (typically $\theta = 0.05$).
* $a_{\max} = 1.0$, $a_{\min} = -1.0$.

### Epistemic Status Classification

At equilibrium convergence $a_j^* = \lim_{t \to \infty} a_j (t)$:

$$\text{Status} (j) = \begin{cases} \text{Accepted} & \text{if } a_j^* \ge \tau_{\text{accept}} \quad (\text{e.g., } \tau \ge 0.20) \\ \text{Rejected} & \text{if } a_j^* \le -\tau_{\text{reject}} \quad (\text{e.g., } \le -0.20) \\ \text{Neutral / Undetermined} & \text{otherwise} \end{cases}$$

---

## Measurement & Graph Implementation

1. **ECHO Solver Run**: Execute the connectionist relaxation loop until convergence.
2. **Graph Property Update**: Store final `equilibrium_activation` on each proposition node in Neo4j.
3. **Hypothesis Selection**: Filter accepted hypotheses ($a_j^* > 0.2$) for theory graph synthesis.

---

## Diagnostic & Metascientific Value

| Equilibrium Activation $a_j^*$ | Epistemic Decision   | Metascientific Outcome                                                |
|:-------------------------------|:---------------------|:----------------------------------------------------------------------|
| $a_j^* \approx +1.0$           | Firmly Accepted      | Validated paradigm law; strongly supported by evidence and coherence. |
| $a_j^* \approx 0.0$            | Epistemic Suspension | Insufficient evidence or evenly balanced competing explanations.      |
| $a_j^* \approx -1.0$           | Decisively Rejected  | Defeated hypothesis; outcompeted by superior alternative paradigm.    |

---

## Grounding References

* **[Thagard, 1989]** Thagard, P. (1989). Explanatory Coherence. *Behavioral and Brain Sciences*, 12 (3), pp. 435–467.
* **[Schurz, 2024]** Schurz, G. (2024). *Philosophy of Science: A Unified Approach*. Routledge, sec. 5.3.
