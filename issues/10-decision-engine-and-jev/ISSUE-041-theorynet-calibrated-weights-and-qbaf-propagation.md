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

### Crucial Theoretical Distinction: Epistemic Confidence vs. Logical Modality
A foundational theoretical vulnerability in automated theory graph construction is conflating the model's **epistemic extraction confidence** with the author's **propositional modal strength**:
- **Extraction Confidence** ($P(\text{correct})$): The probability that the model correctly extracted the author's statement from text.
- **Modal Strength** ($M(\phi) \in [0, 1]$): The formal modal status asserted by the author (e.g., $1.0$ for deductive necessity / axiom; $0.75$ for assertoric factual claim; $0.30$ for tentative hypothesis / epistemic possibility).

If an author writes *"It is conceivable that space is an illusion,"* the model may be $99\%$ confident of the extraction ($P=0.99$), but the proposition itself is an epistemic possibility ($M=0.30$). Squaring uncertainty or setting $w = 0.99$ causes QBAF solvers to treat contingent conjectures as unassailable axioms.

This issue addresses properly decoupling extraction confidence from modal strength and propagating calibrated edge weights into Neo4j and `epistemetrics`.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Calibrated & Modal Edge Attributes in TheoryNet Contracts (`pipeline/contracts/domain.py`)**:
   - Ensure `TheoryRelation` preserves:
     - `class_probability: float` (Softmax probability $P(\text{stance})$)
     - `empirical_accuracy: float` (Laya `action.act_probability` expected accuracy)
     - `modal_strength: float = 1.0` (Propositional modality score in $[0, 1]$)
     - `effective_weight: float` (Decoupled mathematical edge weight)
     - `decision_engine_provider: str | None`
2. **QBAF Decoupled Weight Formulation (`pipeline/phases/phase6_theorynet/`, `packages/epistemetrics`)**:
   - Calculate effective edge weight $w$ without double-penalizing uncertainty:
     $$w = M(\text{modal\_strength}) \times P(\text{stance})$$
   - Use `empirical_accuracy` as an admissibility gate: if $\text{empirical\_accuracy} < \tau_{\text{admissibility}}$, the edge is either pruned or flagged with low epistemic tenability.
3. **Projection Property Mapping (`pipeline/projection/theorynet_projector.py`, `pipeline/phases/phase6_theorynet/`)**:
   - Update Cypher projection templates to persist `class_probability`, `empirical_accuracy`, `modal_strength`, `weight_support`, and `weight_attack` onto `:SUPPORTS` and `:ATTACKS` relationships in the Neo4j Projection Graph.
4. **QBAF Solver Weight Ingestion (`packages/epistemetrics`)**:
   - Ensure `epistemetrics` gradual semantics solvers ingest continuous edge weights directly from Neo4j projection graphs or artifact envelopes.
   - Add a normalization mode in `epistemetrics` comparing gradual equilibrium convergence under uncalibrated binary weights vs. calibrated modal weights.

### What to Change
1. **`Phase6Runner`**:
   - Verify that theory graph projection ingests the enriched attributes emitted by Phase 4b (`ISSUE-039`) rather than discarding probability metadata or conflating modality with confidence.
2. **Evaluation Metrics**:
   - Incorporate calibration metrics (Brier Score, Expected Calibration Error - ECE) into `EvaluationRun` reports when evaluating TheoryNet edges.

### What to Remove
- Remove the naive $w = P(\text{stance}) \times \text{confidence}$ formulation and arbitrary fallbacks that assign uncalibrated float confidences to theoretical relations.

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
