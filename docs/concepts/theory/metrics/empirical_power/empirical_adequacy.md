---
status: needs_verification
tags:
  - Metrics
---

# Empirical Adequacy & Empirical Grounding (Adäquatheit)

## Definition & Conceptual Goal

The **Empirical Adequacy & Grounding** metric quantifies the degree of agreement between empirical observation data ($I$) and theoretical models ($M$), taking into account inevitable measurement errors, experimental approximations, and idealized boundary conditions ([Balzer et al., 1987, pp. 93, 215, 217](../../../references.md#balzer-1987); [Stegmüller, 1976, pp. 40–45, 120](../../../references.md#stegmuller-1976)).

It integrates two fundamental levels of empirical validation:

1. **Baseline Empirical Grounding (True Partial Empirical Claim)**: Verifying that the theory is not a vacuous mathematical exercise, but possesses a non-empty set of historically validated paradigm applications ($I_0 \neq \emptyset$) where the central empirical claim holds ($I_0 \in \operatorname{Cn}(K)$).
2. **Approximative Empirical Adequacy**: Verifying that empirical deviations across the full intended domain remain strictly within a class of **[admissible blurs $\mathcal{A}$](../../../glossary.md#zulassige-unscharfen-admissible-blurs-a)** ($\exists X \in \operatorname{Cn}(K) \text{ s.t. } I \approx_\mathcal{A} X$), avoiding both unachievable idealized exactness ([Strong Adequacy](../../../glossary.md#starke-idealisierte-empirische-adaquatheit-newmans-problem)) and ad-hoc immunization.

!!! note "Relationship to Tenability"
    While **[Tenability](../epistemic_coherence/tenability.md)** ensures the qualitative semantic precondition that empirical observation nodes can be conceptually typed and theoretically enriched into the non-theoretical vocabulary of the theory ($I \subseteq M_{pp}$, governed by [ADR 0015](../../../../adr/0015-theoretical-enrichment-and-tenability-evaluation.md)), **Empirical Adequacy** assesses whether the resulting enriched models ($M$) match empirical observations within admissible blur margins ($\mathcal{A}$).

---
## Theoretical Grounding & Model Formulation

In structuralism, every theory-element $T = \langle K, I \rangle$ asserts the empirical claim $I \in \operatorname{Cn}(K)$. In real empirical science, continuous laws never match observations without experimental imprecision. Balzer, Moulines, and Sneed formalized this using a uniform topology / metric space $(\mathcal{M}_{pp}, d)$ over partial potential models.

Let $\mathcal{A} \subseteq \mathcal{P}(M_{pp} \times M_{pp})$ be a family of **admissible blur relations** representing acceptable error margins (surrounding a uniform space). A theory-element $T = \langle K, I \rangle$ is **approximatively empirically adequate** with respect to $\mathcal{A}$ if and only if:

$$\exists X \in \operatorname{Cn} (K) \quad \text{such that} \quad I \approx_\mathcal{A} X$$

where $I \approx_\mathcal{A} X \iff \forall i \in I \, \exists x \in X \, ((i, x) \in \mathcal{A}) \land \forall x \in X \, \exists i \in I \, ((i, x) \in \mathcal{A})$.

---
## Mathematical Specification & Graph Formulation

Let $d (i, x)$ be the normalized distance metric in the feature space of observation $i$ vs. theoretical model $x$.

!!! note "Distance Metric $d(i,x)$ & LLM Proxy"

    The distance function $d(i,x)$ is defined abstractly to allow for domain-specific physical or statistical residuals. To satisfy the Adequacy Score ($AS$) formula. In text-based graph environments where raw data is unavailable, we substitute physical residuals with an LLM-derived **Plausibility Score** $p(i,x) \in [0, 1]$. Because structural distance and semantic plausibility are inversely related, the score must be inverted before calculation:

    $$d(i,x) = 1 - p(i,x)$$

### Grounding Ratio ($GR$ - Baseline Existence)

A theory must first satisfy the **True Partial Empirical Claim** criterion:

$$GR (T) = \frac{|I_{\text{confirmed}}|}{|I_{\text{total}}|}$$

$$\text{ClaimStatus} (T) = \begin{cases} 1 & \text{if } |I_{\text{confirmed}}| > 0 \land I_{\text{confirmed}} \subseteq \operatorname{Cn} (K) \\ 0 & \text{otherwise} \end{cases}$$

Where $I_{\text{confirmed}}$ is the set of `:EmpiricalApplication` nodes with validated evidentiary support edges (`:EVIDENCED_BY` / `:SUPPORTED_BY`).

### Adequacy Score ($AS$)

$$\text{Adequacy} (I, K) = \max_{X \in \operatorname{Cn} (K)} \left[ 1 - \frac{1}{|I|} \sum_{i \in I} \min_{x \in X} d (i, x) \right]$$

### Blur Margin Compliance Ratio ($BMCR$)

Given a maximum allowable blur threshold $\epsilon_{\text{blur}}$:

$$BMCR (I, K) = \frac{|\{i \in I \mid \min_{x \in X} d (i, x) \le \epsilon_{\text{blur}}\}|}{|I|}$$

---
## Measurement & Graph Implementation

1. **Verify Baseline Grounding ($GR$)**:
   ```cypher
   MATCH (t:TheoryElement {id: $id})-[:INTENDED_APPLICATION]->(i:Application)
   OPTIONAL MATCH (i)<-[:EVIDENCED_BY]-(d:Dataset)
   RETURN count(DISTINCT i) AS total_i, count(DISTINCT d) AS evidenced_count
   ```
2. **Model Prediction Extraction**: Retrieve quantitative or qualitative assertions predicted by `:TheoryCore`.
3. **Observation Edge Residuals**: Compute the difference between predicted node attributes and observed empirical node values in `:EmpiricalData`.
4. **Blur Evaluation**: Check if residual errors fall within declared tolerance intervals stored on `:ErrorMargin` edges.

---
## Diagnostic & Metascientific Value

| $GR(T)$ | $BMCR$ Score         | Epistemic Status             | Metascientific Interpretation                                                                          |
|:--------|:---------------------|:-----------------------------|:-------------------------------------------------------------------------------------------------------|
| $GR = 0$| —                    | Pure Formal Speculation      | Mathematical formalism lacking any verified empirical instantiation.                                  |
| $GR > 0$| $BMCR = 1.0$         | Approximatively Adequate     | All empirical applications match theoretical predictions within tolerated blur limits.                 |
| $GR > 0$| $0.5 \le BMCR < 1.0$ | Partial Anomalies            | Certain applications exhibit systematic deviations; candidates for specialization or anomaly tracking. |
| $GR > 0$| $BMCR < 0.5$         | Empirical Crisis / Refuted   | Major empirical failure; theory core predictions persistently fall outside acceptable error margins.   |

---
## Grounding References

* **[Balzer et al., 1987]** Balzer, W., Moulines, C. U., & Sneed, J. D. (1987). *An Architectonic for Science*. Reidel Publishing, pp. 93, 209–217.
* **[Stegmüller, 1976]** Stegmüller, W. (1976). *The Structure and Dynamics of Theories*. Springer-Verlag, pp. 40–45, 120, 215–220.
