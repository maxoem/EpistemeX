---
status: needs_verification
tags:
  - Metrics
---

# Explanatory Breadth (Consilience & Evidence Coverage)

## Definition & Conceptual Goal

The **Explanatory Breadth (Consilience & Evidence Coverage)** metric favors hypotheses and theories that explain a
broader spectrum and larger volume of distinct empirical evidence
([Thagard, 1989, pp. 437, 442](../../../references.md#thagard-1989); [Schurz, 2014, sec. 5.3](../../../references.md#schurz-2014)).

Originally emphasized by William Whewell and formalized computationally in Thagard's Theory of Explanatory Coherence
(TEC), consilience operates on the principle that a hypothesis gains epistemic credibility in proportion to the
diversity and quantity of independent empirical facts it successfully accounts for.

Conversely, this metric directly incorporates the **Unexplained Evidence Ratio (UER)**: penalizing theoretical networks
that achieve artificial internal harmony merely by cherry-picking a tiny subset of data while leaving the majority of
established empirical observations unexplained.

---

## Theoretical Grounding & Model Formulation

Let $(G = (V_H \cup V_E, R_{\text{sup}} \cup \mathcal{R}_{\text{att}}))$ be a directed knowledge/coherence graph, where:

* $(V_H)$ is the set of hypothesis nodes representing theoretical claims.
* $(V_E)$ is the set of established evidence nodes within the empirical domain scope.
* $(R_{\text{sup}} \subseteq V_E \times V_H)$ is the set of **directed support relations** $E \to H)$ indicating
  evidence $(E)$ supports or is explained by $(H$.
* $(\mathcal{R}_{\text{att}} \subseteq V_E \times V_H)$ is the set of **directed attack/refutation relations**
  $E \to H)$ indicating evidence $(E)$ directly contradicts or refutes $(H$.

While Thagard's ECHO connectionist relaxation model required symmetric edge weights $w_{ij} = w_{ji}$ for Lyapunov
energy convergence, structural graph metrics operate on directed edges to accurately model explanatory asymmetry without
numeric oscillation.

---

## Mathematical Specification

### Consilience Out-Set $Cons$

For an individual hypothesis $(H \in V_H)$, consilience is defined set-theoretically over incoming support edges:

$$Cons (H) = |\{ E \in V_E \mid (E, H) \in R_{\text{sup}} \}|$$

### Relative Node Coverage $REB_{\text{NODE}}$

For a theory $(T)$ composed of hypothesis nodes $(V_H (T) \subseteq V_H)$, relative node coverage is computed over the
**union** of explained evidence to prevent double-counting shared facts:

$$REB_{\text{NODE}} (T) = \frac{\left| \bigcup_{H \in V_H (T)} \{ E \in V_E \mid (E, H) \in R_{\text{sup}} \} \right|}{|V_E|} = \frac{|V_E^{\text{exp}} (T)|}{|V_E|}$$

### Domain-Clustered Explanatory Breadth $REB_{\text{CLUSTER}}$

To capture Whewellian qualitative consilience across distinct empirical fields:

1. Let $(\mathcal{C} = \{C_1, C_2, \dots, C_k\})$ be the partition of evidence nodes $(V_E)$ into topological/topical
   communities identified by a clustering algorithm (e.g., Leiden modularity optimization).
2. Domain coverage ratio $(REB_{\text{CLUSTER}} (T))$ evaluates the proportion of empirical clusters containing at least
   one evidence node explained by theory $(T)$:

$$REB_{\text{CLUSTER}} (T) = \frac{|\{ C_i \in \mathcal{C} \mid C_i \cap V_E^{\text{exp}} (T) \neq \emptyset \}|}{|\mathcal{C}|}$$

*Note: In evaluation pipelines, $(REB_{\text{NODE}} (T))$ and $(REB_{\text{CLUSTER}} (T))$ can be combined via geometric
mean or presented as complementary metrics.*

### Unexplained Evidence Ratio $UER$ & Empirical Conflict Ratio $ECR$

We separate passive evidence omission from active empirical falsification:

1. **Unexplained Evidence Ratio (Passive Gap)**:
$$
UER (T) = \frac{|V_E \setminus V_E^{\text{exp}} (T)|}{|V_E|} = 1 - REB_{\text{NODE}} (T)
$$

2. **Empirical Conflict Ratio (Active Refutation)**:
$$
ECR (T) = \frac{\left| \bigcup_{H \in V_H (T)} \{ E \in V_E \mid (E, H) \in \mathcal{R}_{\text{att}} \} \right|}{|V_E|}
$$

3. **Net Explanatory Coverage $REB_{\text{net}}$**:
$$
REB_{\text{net}} (T) = REB_{\text{NODE}} (T) - \alpha \cdot ECR (T)
$$
   where $(\alpha \ge 1.0)$ is the falsification severity multiplier.

### Dynamic Skepticism Penalty

To penalize theories that cherry-pick data or ignore active refutations, the systemic decay/skepticism rate $(\theta_
{\text{effective}})$ is scaled by both omission and conflict ratios:

$$\theta_{\text{effective}} = \theta_{\text{base}} \cdot \left (1 + \gamma_{\text{unexp}} \cdot UER (T) + \gamma_{\text{att}} \cdot ECR (T) \right)$$

where:

* $(\theta_{\text{base}})$ is the baseline network decay rate.
* $(\gamma_{\text{unexp}} \ge 1.0)$ is the evidence omission penalty weight (default = $(1.0$.
* $(\gamma_{\text{att}} \gg \gamma_{\text{unexp}})$ is the active refutation penalty weight (default = $(3.0$.

## Measurement & Graph Implementation

---

## Diagnostic & Metascientific Value

| $REB(T)$ Score        | $UER(T)$ Score        | Epistemic Status          | Metascientific Interpretation                                                        |
|:----------------------|:----------------------|:--------------------------|:-------------------------------------------------------------------------------------|
| $REB > 0.6$           | $UER < 0.4$           | Broadly Consilient        | Strong explanatory coverage; accounts for diverse phenomena across scope.            |
| $0.2 \le REB \le 0.6$ | $0.4 \le UER \le 0.8$ | Partial Scope             | Moderate coverage with notable unaddressed observational pockets.                    |
| $REB < 0.1$           | $UER > 0.9$           | Isolated / Cherry-Picking | Explains only isolated observations; high decay penalty applied due to omitted data. |

---

## Grounding References

* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. *An Architectonic for Science*. Reidel, Ch. VIII
  (Directed intertheoretical links and theory-holons).
* **[Newman, 2018]** Newman, M. *Networks*. Oxford University Press, Ch. 14 (Community structure and modularity
  algorithms).
* **[Nováček et al., 2015]** Nováček, V. et al. *Formalising Hypothesis Virtues for Knowledge Graphs*. arXiv:
  1503.09137v2 (Metric constellations and modesty/simplicity measures).
* **[Schurz, 2024]** Schurz, G. *Philosophy of Science: A Unified Approach*. Routledge, sec. 3.12, 5.3 & 6.4 (Content
  elements, tacking paradoxes, and unification).
* **[Thagard, 1989]** Thagard, P. Explanatory Coherence. *Behavioral and Brain Sciences*, 12 (3), pp. 435–467.
