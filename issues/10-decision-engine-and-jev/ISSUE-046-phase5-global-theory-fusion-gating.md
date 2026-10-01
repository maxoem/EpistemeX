# [ISSUE-046] Phase 5 Global Theory Fusion Gating & Conformal Prediction Calibration

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-046` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/phases/phase5_fusion/argument_web.py`, `pipeline/phases/phase5_fusion/argument_clustering.py`, `pipeline/config.py`, `pipeline/decision/conformal.py`) |
| **Roadmap Horizon** | **Horizon 2** (Global Theory Fusion & Distribution-Free Calibration) |
| **Priority** | High |
| **Status** | Open |
| **Source Ref** | `docs/workflow/5_theory_fusion/index.md`, `pipeline/protocols/fusion.py`, ADR 0005 |

---

## 1. Problem Statement & Motivation
Phase 5 (Inter-Document Argument Web & Theory Fusion) aggregates arguments and entities across disparate scientific treatises into a cohesive global knowledge graph. Currently, [`Phase5ArgumentWebRunner`](file:///Users/max.oehmichen/PycharmProjects/episteme/packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_web.py) relies solely on mathematical embedding similarity (`similarity_threshold: 0.85`) and graph topological partitioning (`LeidenTheoryClustering`).

This introduces two severe vulnerabilities:
1. **Unverified Inter-Document Theory Merges in Long-Term Memory**:
   - Merging theoretical constructs across different authors or centuries based purely on dense embedding cosine distance and Leiden modularity causes catastrophic epistemic conflation. Distinct or competing philosophical frameworks that use overlapping vocabulary are falsely collapsed into single macro-clusters in long-term Neo4j storage without semantic verification.
2. **Brittle Rigid Scalar Thresholds across Heterogeneous Corpora**:
   - Fixed scalar cutoffs ($\tau = 0.85$) do not account for distribution shift between modern analytic philosophy, historical German texts, or interdisciplinary treatises.
   - Point estimates lack statistical guarantees, leading to uncontrolled error rates when generalizing across corpora.

By integrating the **Decision Engine** into Phase 5 and introducing **Conformal Prediction**, Episteme provides:
- A semantic gate to verify inter-document theory cluster coherence and equivalence before committing `:FUSED_INTO` edges.
- Distribution-free finite-sample coverage guarantees ($1 - \alpha = 0.95$), replacing rigid scalar thresholds with adaptive prediction sets.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Conformal Prediction Engine (`pipeline/decision/conformal.py`)**:
   - `class ConformalCalibrator`:
     - Implements Split Conformal Prediction for classification over calibrated probability distributions.
     - Calibrates non-conformity scores $s_i = 1 - \hat{P}(y_i \mid x_i)$ on a small held-out calibration split.
     - Computes the empirical quantile $\hat{q} = \text{Quantile}\left(\frac{\lceil (n+1)(1-\alpha) \rceil}{n}\right)$.
     - Method `predict_set(score: DecisionScore, alpha: float = 0.05) -> list[str]`:
       - Emits the prediction set $C(x) = \{y \in \mathcal{Y} \mid \hat{P}(y \mid x) \ge 1 - \hat{q}\}$.
       - Guarantees $P(Y \in C(X)) \ge 1 - \alpha$.
   - **Triage Decision Logic**:
     - If $|C(x)| = 1$: Provably unambiguous decision $\rightarrow$ **Fast-Exit**.
     - If $|C(x)| > 1$ or $|C(x)| = 0$: Ambiguous or out-of-distribution $\rightarrow$ **Escalate to System 2**.
2. **Phase 5 Theory Fusion Semantic Gate (`pipeline/phases/phase5_fusion/argument_clustering.py`)**:
   - Add `async def verify_inter_document_cluster(cluster_nodes: list[TheoryAtom | L2Entity], decision_engine: DecisionEngine, prompt_bundle: StructuredPromptBundle | None = None) -> tuple[bool, float]`:
     - Formulates a state summarizing the core claims, authorial contexts, and relational neighborhoods of the cluster members.
     - Asks Jev `Choice`:
       - `options`: `["EQUIVALENT_FUSION", "COMPETING_THEORIES", "DISTINCT_APPLICATIONS"]`.
     - Confirms fusion into long-term memory only if `EQUIVALENT_FUSION` is contained in the conformal prediction set (or $\text{empirical\_accuracy} \ge \tau_{\text{fusion}}$).
3. **Phase 5 Configuration Controls (`pipeline/config.py`)**:
   - Extend [`Phase5Config`](file:///Users/max.oehmichen/PycharmProjects/episteme/packages/episteme-pipeline/episteme_pipeline/config.py) with:
     - `enable_fusion_gating: bool = False` (defaults to False for zero regression)
     - `conformal_alpha: float = 0.05` (95% coverage guarantee)
     - `fusion_confidence_threshold: float = 0.85`
     - `stochastic_audit_rate: float = 0.02` (2% audit to System 2 / Langfuse)
4. **Active Learning Queue Hook for High-Entropy Merges**:
   - When $|C(x)| > 1$ during Phase 5 cross-document evaluation, tag the event with `active_learning: true` and push the borderline cluster to a Langfuse Dataset for domain expert review.

### What to Change
1. **`Phase5ArgumentWebRunner` (`pipeline/phases/phase5_fusion/argument_web.py`)**:
   - Inject `decision_engine: DecisionEngine | None = None`.
   - Before executing `theory_fusion.fuse(self.graph_store)`, run cluster verification on candidate community partitions.
2. **Composition Root (`pipeline/pipeline.py`)**:
   - In `Pipeline.for_task`, pass `decision_engine` into `Phase5ArgumentWebRunner`.

### What to Remove
- Remove blind acceptance of Leiden community partitions without semantic validation.

---

## 3. Acceptance Criteria
- [ ] `ConformalCalibrator` computes distribution-free prediction sets with $1 - \alpha$ coverage.
- [ ] Singleton prediction sets ($|C(x)| = 1$) trigger fast-exit; multi-class sets escalate to System 2 or active learning.
- [ ] Phase 5 filters out spurious inter-document merges between competing or distinct philosophical frameworks.
- [ ] 2% stochastic audit samples are emitted to Langfuse to detect false negative theory splits.
- [ ] Unit tests with `MockJevDecisionEngine` verify cluster gating and conformal prediction set generation.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/decision/conformal.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_web.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_clustering.py`
- `packages/episteme-pipeline/episteme_pipeline/config.py`
- `packages/episteme-pipeline/episteme_pipeline/pipeline.py`
- `packages/episteme-pipeline/tests/test_phase5_fusion_gating.py`

---

## 5. Documentation Updates Required
- Update Phase 5 Inter-Document Argument Web workflow documentation (`docs/workflow/5_theory_fusion/`).
- Document Conformal Prediction mathematical guarantees in `docs/architecture/conformal_prediction.md`.
- Update ADR 0005 (Two-Pass Fusion Strategy) to include semantic theory fusion gating.
