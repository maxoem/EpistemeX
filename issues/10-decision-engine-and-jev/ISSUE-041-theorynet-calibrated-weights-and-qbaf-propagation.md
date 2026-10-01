# [ISSUE-041] TheoryNet Projection & QBAF Calibrated Probability Propagation

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-041` |
| **Component(s)`** | `packages/episteme-pipeline` (`pipeline/phases/phase6_theorynet/`, `pipeline/projection/theorynet_projector.py`), `packages/epistemetrics` (`src/epistemetrics/`) |
| **Roadmap Horizon** | **Horizon 2** (Gradual Semantics & Dialectical Modeling) |
| **Priority** | High |
| **Status** | Open |
| **Source Ref** | `docs/roadmap.md` (§ Advanced Gradual Semantics Solvers, § JevClassifier), ADR 0006, ADR 0011 |

---

## 1. Problem Statement & Motivation
In Episteme, Layer 3 (TheoryNet) models dialectical structures as Quaternary Bipolar Argumentation Frameworks (QBAF), where iterative convergence algorithms solve for equilibrium justification degrees ($\tau$):
$$\tau(a) = f\left(\tau_0(a), \sum_{s \in \text{Supp}(a)} w_s \cdot \tau(s), \sum_{k \in \text{Att}(a)} w_k \cdot \tau(k)\right)$$

In standard generative LLM pipelines, the relation weights $w_s$ and $w_k$ are either uncalibrated heuristic scores (e.g. LLMs guessing `"confidence": 0.8`) or defaulted to $1.0$. Uncalibrated inputs distort gradual semantics solvers (Eulerian, quadratic energy, or categorization models) and degrade epistemic coherence calculations.

TypeSafe Jev emits empirically calibrated probability distributions and confidence scores. This issue addresses propagating Jev's calibrated probabilities through Phase 6 projection into Neo4j and into `epistemetrics` gradual semantics solvers.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Calibrated Edge Attributes in TheoryNet Contracts (`pipeline/contracts/domain.py`)**:
   - Ensure `TheoryRelation` and `TheoryAtom` contracts preserve:
     - `calibrated_confidence: float | None`
     - `system1_probabilities: dict[str, float] | None`
     - `decision_engine_provider: str | None`
2. **Projection Property Mapping (`pipeline/projection/theorynet_projector.py`, `pipeline/phases/phase6_theorynet/`)**:
   - Update Cypher projection templates to persist `calibrated_confidence`, `weight_support`, and `weight_attack` onto `:SUPPORTS` and `:ATTACKS` relationships in the Neo4j Projection Graph.
   - When Jev probabilities are present, set relationship weight directly:
     $$w = P(\text{stance}) \times \text{confidence}$$
3. **QBAF Solver Weight Ingestion (`packages/epistemetrics`)**:
   - Ensure `epistemetrics` gradual semantics solvers can ingest variable edge weights directly from Neo4j projection graphs or artifact envelopes.
   - Add a normalization mode in `epistemetrics` comparing gradual equilibrium convergence under uncalibrated binary weights vs. Jev calibrated weights.

### What to Change
1. **`Phase6Runner`**:
   - Verify that theory graph projection ingests the enriched attributes emitted by Phase 4b (`ISSUE-039`) rather than discarding probability metadata.
2. **Evaluation Metrics**:
   - Incorporate calibration metrics (Brier Score, Expected Calibration Error - ECE) into `EvaluationRun` reports when evaluating TheoryNet edges.

### What to Remove
- Remove arbitrary hardcoded fallbacks that assign uncalibrated float confidences to theoretical relations.

---

## 3. Acceptance Criteria
- [ ] `TheoryRelation` domain models serialize and preserve calibrated confidence and probability distributions.
- [ ] Neo4j projection writes `calibrated_confidence` and mathematical weights to graph edges.
- [ ] `epistemetrics` QBAF gradual semantics solvers execute with continuous, calibrated edge weights.
- [ ] Equilibrium justification degrees ($\tau$) converge deterministically without numerical instability under calibrated weights.
- [ ] Unit tests verify end-to-end propagation from Phase 4 classification artifacts through Phase 6 Neo4j projection.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/contracts/domain.py`
- `packages/episteme-pipeline/episteme_pipeline/projection/theorynet_projector.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase6_theorynet/runner.py`
- `packages/epistemetrics/src/epistemetrics/`
- `packages/episteme-pipeline/tests/test_theorynet_calibrated_projection.py`

---

## 5. Documentation Updates Required
- Update the TheoryNet and formal graph model documentation (`docs/concepts/formal_graph_model.md`, `docs/workflow/6_theorynet/`) to document calibrated edge weighting.
- Update Epistemetrics documentation regarding QBAF gradual semantics solver inputs and calibration properties.
- Update ADR 0011 (Declarative Graph Metrics and QBAF Semantics) to reflect the integration of calibrated System 1 priors.
