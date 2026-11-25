---
status: completed
tags:
  - Metrics
---

# Degeneration Index & Immunization Tracking

## Definition & Conceptual Goal

The **Degeneration Index & Immunization Tracking** metric suite evaluates Lakatosian research-programme degeneration across chronological theory-net snapshots $T^{(0)}, \dots, T^{(m)}$ and detects ad-hoc$_1$ immunizing stratagems ([Balzer et al., 1987, pp. 333–338](../../../references.md#balzer-1987); [Stegmüller, 1976, p. 184](../../../references.md#stegmuller-1976); [Schurz, 2014](../../../references.md#schurz-2014); [Lakatos, 1978](../../../references.md#lakatos-1978)). See [Epistemology & Philosophy of Science](../../../epistemology.md#42-bounded-degeneration-proxy-episteme-operationalization) and [Canonical Notation](../../../notation.md) for the formal epistemological grounding and domain-scope constraints (empirical scientific theories).

It diagnoses two interconnected levels of non-progressive evolution:

1. **Micro-Level (Node Immunization $II$)**: Identifies newly added auxiliary hypotheses ($K_{i+1}$) that resolve an empirical anomaly without generating independent novel empirical content ($\operatorname{Cn}_{\text{str}}(K_{i+1}) \setminus \{a\} \subseteq \operatorname{Cn}_{\text{str}}(K_i)$).
2. **Macro-Level (Bounded Degeneration Proxy $D_{\text{deg}}$ & Empirical Failure Rate $R_{\text{fail}}$)**: Quantifies the share of ad-hoc$_1$ immunizations relative to corroborated novel predictions ($D_{\text{deg}} \in [0, 1]$), paired with the overall failure share ($R_{\text{fail}} \in [0, 1]$).

---

## Theoretical Grounding & Partitioning

For each historical epoch $T^{(j)}$ of an empirical research programme, empirical outcomes are partitioned into four disjoint sets:

* **$\mathsf{Succ}^{\text{nov}}(T^{(j)})$ (Corroborated Novel Predictions)**: Empirically confirmed predictions not already used to construct or calibrate the auxiliary modification (Worrall/Zahar use-novelty).
* **$\mathsf{Succ}^{\text{acc}}(T^{(j)})$ (Accommodated Explanations)**: Retrodictions or post-hoc fits of already known phenomena; tracked separately so they do not inflate novel progress.
* **$\mathsf{Fail}_a(T^{(j)})$ ([Direct Refutations / Failure Type a](../../../glossary.md#misserfolg-typ-a-direkter-widerspruch))**: Open empirical anomalies contradicting $T^{(j)}$ without ad-hoc shielding.
* **$\mathsf{Fail}_b(T^{(j)})$ ([Ad-Hoc$_1$ Immunizations / Failure Type b](../../../glossary.md#misserfolg-typ-b-immunisierter-misserfolg-scheinbarer-erfolg))**: Auxiliary adjustments that absorb prior anomalies while producing zero independent corroborated excess empirical content.

---

## Mathematical Specification

### Node-Level Immunization Index ($II$)

For an auxiliary modification resolving $\Delta_{\text{anom}}$ anomalies while yielding $\Delta_{\text{content}} = \Delta |\mathsf{Succ}^{\text{nov}}|$ corroborated novel predictions:

$$II(K_i, K_{i+1}) = \begin{cases} 1.0 & \text{if } \Delta_{\text{anom}} > 0 \land \Delta_{\text{content}} = 0 \\ \dfrac{\Delta_{\text{anom}}}{\Delta_{\text{anom}} + \Delta_{\text{content}}} & \text{otherwise} \end{cases}$$

### Ratio of Progressive to Immunizing Nodes ($RPI$)

Across an evolution sequence $\mathcal{E}$:

$$RPI(\mathcal{E}) = \frac{|V_{\text{progressive}}|}{|V_{\text{progressive}}| + |V_{\text{immunizing}}|}$$

### Bounded Degeneration Proxy ($D_{\text{deg}}$) & Empirical Failure Rate ($R_{\text{fail}}$)

Implemented in `epistemetrics.epistemic.dynamics.compute_bounded_degeneration_proxy`:

$$D_{\text{deg}}(T^{(j)}) = \frac{|\mathsf{Fail}_b(T^{(j)})|}{|\mathsf{Succ}^{\text{nov}}(T^{(j)})| + |\mathsf{Fail}_b(T^{(j)})|} \in [0, 1]$$

$$R_{\text{fail}}(T^{(j)}) = \frac{|\mathsf{Fail}_a(T^{(j)})| + |\mathsf{Fail}_b(T^{(j)})|}{|\mathsf{Succ}^{\text{nov}}(T^{(j)})| + |\mathsf{Fail}_a(T^{(j)})| + |\mathsf{Fail}_b(T^{(j)})|} \in [0, 1]$$

Both ratios return $0.0$ when their denominator is zero. Separating $D_{\text{deg}}$ from $R_{\text{fail}}$ ensures exact monotonicity:
- $\partial D_{\text{deg}} / \partial |\mathsf{Fail}_b| > 0$ (ad-hoc immunizations strictly increase degeneration),
- $\partial D_{\text{deg}} / \partial |\mathsf{Succ}^{\text{nov}}| < 0$ (novel empirical successes strictly decrease degeneration),
- $\partial D_{\text{deg}} / \partial |\mathsf{Fail}_a| = 0$ (direct unresolved refutations increase $R_{\text{fail}}$ without artificially lowering $D_{\text{deg}}$).

### Programme Trajectory Trend ($\Delta D_{\text{deg}}$)

Over a chronological sequence $T^{(0)}, T^{(1)}, \dots, T^{(m)}$:

$$\Delta D_{\text{deg}} = D_{\text{deg}}(T^{(m)}) - D_{\text{deg}}(T^{(0)})$$

* $\Delta D_{\text{deg}} > 0$: Increasing ad-hoc immunization burden across epochs.
* $\Delta D_{\text{deg}} \le 0$: Stable or improving ratio of novel predictions to ad-hoc adjustments.

---

## Measurement & Graph Implementation

1. **Detect Ad-Hoc$_1$ Nodes**:
   - Identify newly added auxiliary hypotheses carrying `:RESOLVES_ANOMALY` links but zero outgoing `:PREDICTS_NOVEL` links (`is_adhoc` / `failure_type = "b"`).
2. **Compute Bounded Degeneration Proxy & Failure Rate**:
   ```cypher
   MATCH (v:TheoryVersion {id: $version_id})
   OPTIONAL MATCH (v)-[:HAS_NOVEL_SUCCESS]->(s:Success)
   OPTIONAL MATCH (v)-[:HAS_FAILURE_A]->(fa:FailureTypA)
   OPTIONAL MATCH (v)-[:HAS_FAILURE_B]->(fb:FailureTypB)
   WITH count(DISTINCT s) AS n_nov, count(DISTINCT fa) AS n_fa, count(DISTINCT fb) AS n_fb
   RETURN
     CASE WHEN (n_nov + n_fb) = 0 THEN 0.0 ELSE toFloat(n_fb) / (n_nov + n_fb) END AS d_deg,
     CASE WHEN (n_nov + n_fa + n_fb) = 0 THEN 0.0 ELSE toFloat(n_fa + n_fb) / (n_nov + n_fa + n_fb) END AS r_fail
   ```

---

## Diagnostic & Metascientific Value

| Measurement Indicator | Programme Dynamic | Metascientific Interpretation |
| :--- | :--- | :--- |
| Hard core invariant, $D_{\text{deg}} < 0.3$, $R_{\text{fail}} < 0.5$ | Progressive Programme | Corroborated novel predictions dominate; auxiliary adjustments remain content-increasing. |
| Hard core invariant, $0.3 \le D_{\text{deg}} < 0.5$ | Transitional / Contested | Novel predictions still outnumber ad-hoc patches, but defensive adjustments are rising. |
| $D_{\text{deg}} \ge 0.5$ or $R_{\text{fail}} \ge 0.5$ | Degenerating Programme | Ad-hoc immunizations or unresolved refutations equal or exceed corroborated novel predictions. |
| Hard core mutated | Programme Rupture | Foundational core laws were altered or dropped; continuity of the research programme is broken. |
| $II = 1.0$ (Node Level) | Pure Immunizing Patch | Auxiliary node absorbs an anomaly without generating independent novel empirical content. |

---

## Grounding References

* **[Lakatos, 1978]** [Lakatos, I. (1978)](../../../references.md#lakatos-1978). *The Methodology of Scientific Research Programmes: Philosophical Papers, Volume 1*. Cambridge University Press.
* **[Schurz, 2014]** [Schurz, G. (2014)](../../../references.md#schurz-2014). *Philosophy of Science: A Unified Approach*. Routledge.
* **[Balzer et al., 1987]** [Balzer, W., Moulines, C. U., & Sneed, J. D. (1987)](../../../references.md#balzer-1987). *An Architectonic for Science*. Reidel Publishing, pp. 333–338.
* **[Stegmüller, 1976]** [Stegmüller, W. (1976)](../../../references.md#stegmuller-1976). *The Structure and Dynamics of Theories*. Springer-Verlag, p. 184.
