# Conformal Prediction Calibration & Distribution-Free Confidence

This document details the mathematical theory, architectural integration, and runtime triage mechanics of **Split Conformal Prediction** within the Episteme pipeline.

*For runtime usage in theory fusion, see [Phase 5: Alignment & Theory Fusion](../workflow/5_inter_document_argument_web/index.md). For entity consolidation, see [Phase 3b: Latent Graph Consolidation](../workflow/3b_consolidation/index.md). For ADR decisions, see [ADR 0005](../adr/0005-two-pass-fusion-strategy.md).*

---

## 1. Problem Statement: The Fallacy of Rigid Scalar Thresholds

In traditional Neuro-Symbolic knowledge graphs, automated decisions—such as whether to merge two theoretical entities or fuse two argument clusters across distinct corpora—rely on arbitrary, fixed scalar heuristics (e.g., $\text{cosine\_similarity} \ge 0.85$ or $\hat{P} \ge 0.80$).

This introduces severe epistemic vulnerabilities:
1. **Uncalibrated Model Confidence**: Softmax probabilities produced by neural models are notorious for overconfidence under distribution shift (e.g., historical German philosophy vs. contemporary analytic logic).
2. **Point Estimate Brittleness**: A fixed scalar cutoff cannot distinguish between a high-certainty decision and a high-entropy borderline case.
3. **Catastrophic Epistemic Conflation**: Merging competing philosophical frameworks into single macro-clusters in long-term Neo4j storage based on heuristic point cutoffs damages downstream QBAF gradual semantics and TheoryNet consistency.

To establish rigorous scientific validity, Episteme replaces rigid scalar thresholds with **Distribution-Free Split Conformal Prediction** (Vovk et al., 2005; Angelopoulos & Bates, 2021).

---

## 2. Mathematical Foundation

Split Conformal Prediction guarantees finite-sample marginal coverage without making parametric distributional assumptions regarding the underlying data distribution, requiring only the assumption of exchangeability.

### 2.1 Non-Conformity Scoring

Given a held-out calibration set $\mathcal{D}_{\text{cal}} = \{(x_1, y_1), \dots, (x_n, y_n)\}$, where $x_i$ represents candidate features and $y_i \in \mathcal{Y}$ represents the ground-truth classification label:

We compute non-conformity scores $s_i$ assessing how unusual the true label $y_i$ is under the model's predictive distribution $\hat{P}(Y = y \mid X = x)$:

$$s_i = 1 - \hat{P}(y_i \mid x_i)$$

Higher scores indicate greater non-conformity between the model prediction and empirical reality.

### 2.2 Empirical Quantile Calibration

For a user-selected significance level $\alpha \in (0, 1)$ (typically $\alpha = 0.05$ for $95\%$ statistical coverage), we compute the empirical $(1 - \alpha)$-quantile $\hat{q}$ over sorted non-conformity scores $\{s_1, \dots, s_n\}$:

$$\hat{q} = \text{Quantile}\left(\frac{\lceil (n + 1)(1 - \alpha) \rceil}{n}, \{s_1, \dots, s_n\}\right)$$

### 2.3 Finite-Sample Coverage Guarantee

For any new test instance $X_{n+1}$, the conformal prediction set $C(X_{n+1})$ is constructed by collecting all labels whose non-conformity score does not exceed the calibrated quantile $\hat{q}$:

$$C(X_{n+1}) = \{y \in \mathcal{Y} \mid 1 - \hat{P}(y \mid X_{n+1}) \le \hat{q}\} = \{y \in \mathcal{Y} \mid \hat{P}(y \mid X_{n+1}) \ge 1 - \hat{q}\}$$

Under exchangeability, the coverage theorem guarantees:

$$P(Y_{n+1} \in C(X_{n+1})) \ge 1 - \alpha$$

---

## 3. Dual-Process Triage Engine

Episteme integrates [`ConformalCalibrator`](file:///Users/max.oehmichen/PycharmProjects/episteme/packages/episteme-pipeline/episteme_pipeline/decision/conformal.py) into the System 1 / System 2 decision routing pipeline:

```mermaid
flowchart TD
    A[Candidate Decision Input X] --> B[TypeSafe Jev System 1 Scoring]
    B --> C[ConformalCalibrator<br>Compute Prediction Set C_X]
    C --> D{Cardinality of C_X}
    D -->||C_X| = 1| E[Provably Unambiguous<br>Fast-Exit System 1]
    D -->||C_X| > 1| F[Epistemic Ambiguity<br>Escalate to System 2 / Active Learning]
    D -->||C_X| = 0| G[Out-of-Distribution Anomaly<br>Flag for Expert Review]
    E --> H{Stochastic Audit?<br>p = 0.02}
    H -->|Yes| F
    H -->|No| I[Commit Deterministic Action]
```

### 3.1 Triage Rules

1. **Singleton Prediction Set ($|C(X)| = 1$) $\implies$ Fast-Exit**:
   - The decision is provably unambiguous at the $(1 - \alpha)$ confidence level.
   - The system executes the single candidate action immediately in $<150\text{ms}$ without consuming generative LLM tokens.
2. **Multi-Class Prediction Set ($|C(X)| > 1$) $\implies$ System 2 Escalation**:
   - The instance exhibits high epistemic entropy (e.g. subtle distinction between `IDENTICAL_MERGE` and `HIERARCHICAL_SUBSUMPTION`).
   - The decision is escalated to deep generative reasoning (System 2) or tagged with `active_learning: True` for human-in-the-loop expert adjudication.
3. **Empty Prediction Set ($|C(X)| = 0$) $\implies$ Out-of-Distribution Anomaly**:
   - None of the candidate labels fit the observed state under the calibrated confidence threshold.
   - The item is flagged as an out-of-distribution anomaly, preventing silent failure.
4. **Stochastic False-Negative Auditing ($p = 0.02$)**:
   - A random $2\%$ sample of fast-exit singletons is routed to System 2 to continuously monitor calibration drift, detect concept drift across documents, and guard against premature consolidation.

---

## 4. Pipeline Integration Points

### 4.1 Phase 3b: Latent Graph Consolidation

In [`Phase3bLatentConsolidationRunner`](file:///Users/max.oehmichen/PycharmProjects/episteme/packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/runner.py), candidate entity pairs in the borderline cosine similarity band ($[0.75, 0.88)$) are evaluated via [`verify_borderline_pair`](file:///Users/max.oehmichen/PycharmProjects/episteme/packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/clustering.py):
- **Options**: `["IDENTICAL_MERGE", "HIERARCHICAL_SUBSUMPTION", "DISTINCT_SEPARATE"]`.
- **Conformal Guard**: Merging in the Union-Find structure is strictly restricted to cases where $C(X) = \{\text{"IDENTICAL\_MERGE"}\}$ (or empirical accuracy $\ge \tau_{\text{merge}}$). If the prediction set contains multiple alternatives, merging is aborted to preserve conceptual hierarchy.

### 4.2 Phase 5: Global Theory Fusion

In [`Phase5ArgumentWebRunner`](file:///Users/max.oehmichen/PycharmProjects/episteme/packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_web.py), cross-document community partitions and argument clusters are evaluated via [`verify_inter_document_cluster`](file:///Users/max.oehmichen/PycharmProjects/episteme/packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_clustering.py):
- **Options**: `["EQUIVALENT_FUSION", "COMPETING_THEORIES", "DISTINCT_APPLICATIONS"]`.
- **Conformal Guard**: Fusion into the global theory graph is only committed when `EQUIVALENT_FUSION` $\in C(X)$ (or empirical accuracy $\ge \tau_{\text{fusion}}$).
- **Active Learning**: Multi-class ambiguous clusters emit domain events with `active_learning: True` for dataset curation and Langfuse telemetry.

---

## 5. References

- Angelopoulos, A. N., & Bates, S. (2021). *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification*. arXiv:2107.07511.
- Vovk, V., Gammerman, A., & Shafer, G. (2005). *Algorithmic Learning in a Random World*. Springer.
- [ADR 0005: Two-Pass Fusion Strategy](../adr/0005-two-pass-fusion-strategy.md)
