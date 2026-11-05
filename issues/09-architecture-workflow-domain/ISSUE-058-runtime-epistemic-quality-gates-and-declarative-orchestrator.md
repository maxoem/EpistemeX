# [ISSUE-058] Active Runtime Epistemic Quality Gates & Declarative Dataflow Orchestration

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-058` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Orchestrator Architecture, Runtime Quality Gates, Workflow Composition) |
| **Target Package(s)** | `packages/episteme-pipeline`, `packages/epistemetrics` (`pipeline.py`, `runtime/`, `protocols/`) |
| **Priority** | **Medium** |
| **Status** | `In Progress (Post-Audit Architectural Remediation)` |
| **Evaluated Docs & ADRs** | [`docs/architecture/overview.md`](../../docs/architecture/overview.md), [`docs/architecture/pipeline_architecture.md`](../../docs/architecture/pipeline_architecture.md), [`ADR-0007`](../../docs/adr/0007-tf-structural-correspondence.md), [`ADR-0011`](../../docs/adr/0011-declarative-graph-metrics-and-qbaf-semantics.md), [`ADR-0016`](../../docs/adr/0016-phase-3-within-phase-checkpointing-and-atomicity.md) |

---

## 1. Current State

1. **Evaluation Restricted to Passive Post-Construction Analytics**:
   - Per [`ADR-0007 §4`](../../docs/adr/0007-tf-structural-correspondence.md) and [`ADR-0011`](../../docs/adr/0011-declarative-graph-metrics-and-qbaf-semantics.md), topological and epistemic metrics (`epistemetrics`) operate exclusively *after* pipeline completion. During execution, the only automated safety check is [`ADR-0016 §4`](../../docs/adr/0016-phase-3-within-phase-checkpointing-and-atomicity.md)'s check for a 100% exception rate in Batch 0 of Phase 3.
2. **Monolithic `Pipeline` Class Fusing 5 Architectural Roles**:
   - [`Pipeline`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py) currently combines: (a) Composition Root (`for_task`), (b) Workflow Topology (`_SUPPORTED_TASKS = {"knowledge_graph"}`), (c) Cache/Invalidation Policy (`_choose_reuse_source`), (d) Artifact/Manifest/Projection Storage I/O, and (e) Telemetry Scoping (`_execute`).

---

## 2. Why This Causes Problems

### A. Researcher & Operational Reliability Perspective
1. **Open-Loop Blindness to Structural & Calibration Pathologies**:
   - If a misconfigured prompt, embedding model mismatch, or distribution shift causes:
     - **Ontological Collapse in Phase 2** (e.g., $>90\%$ of extracted entities assigned to a single fallback label),
     - **Giant-Component Percolation in Phase 3b** (e.g., a permissive similarity threshold merging $>50\%$ of all entities into a single connected component), or
     - **Conformal OOD Collapse in Phase 3/4** (e.g., $>70\%$ of System 1 predictions yielding empty sets $|C(X)| = 0$ or multi-class escalation $|C(X)| > 1$),
     the pipeline has no **Inter-Phase Epistemic Quality Gate** to detect the pathology and halt or adapt before burning hours of downstream LLM compute.

### B. Software Engineering & Extensibility Perspective
2. **Inability to Compose Non-Linear Research Workflows**:
   - Because `Pipeline` couples DI wiring, storage, and invalidation to a single sequential phase list (`task="knowledge_graph"`), researchers cannot declaratively define multi-branch workflows such as **Comparative Theory Alignment** (running two corpora through Phases 1–4 independently and joining them in Phase 5/6) or **Query-Driven Subgraph Expansion** without duplicating orchestrator internals.

---

## 3. Proposed Solution & Architectural Explanation

### Step 1: Inter-Phase `EpistemicQualityGate` Protocol (Homeostatic Circuit Breakers)
- Introduce a lightweight `EpistemicQualityGate` hook evaluated between phases on the emitted `ArtifactCollection`:
  - **Ontology Entropy Gate (Post-Phase 2)**: Verifies Shannon entropy $H(\text{entity\_types}) \ge H_{\min}$ and checks that non-empty chunks yield a non-zero entity density.
  - **Percolation / Cluster Diameter Gate (Post-Phase 3b & Phase 5)**: Verifies that the largest merged equivalence class does not exceed $\rho_{\max} \cdot |E|$ (preventing giant-component collapse).
  - **Conformal Calibration Health Gate (Post-Phase 3 & 4)**: Monitors the empirical rate of empty ($|C(X)| = 0$) and ambiguous ($|C(X)| > 1$) prediction sets, emitting a `QualityGateWarning` or halting (`QualityGateViolationError`) if OOD rates exceed configured bounds.

### Step 2: Decouple `WorkflowTopology`, `PipelineFactory`, and `ArtifactExecutionEngine`
Refactor [`pipeline.py`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py) into three clean, single-responsibility collaborators while keeping `Pipeline.for_task()` as a convenient facade:
1. **`PipelineFactory` (Composition Root)**: Wires LLMs, embedders, rerankers, `DecisionEngine`, and `ModalStrengthResolver` from `PipelineConfig`.
2. **`WorkflowDAG` (Declarative Topology)**: Defines phase nodes, data dependencies (`reads_kinds`/`writes_kinds`), and attached `EpistemicQualityGate`s.
3. **`ArtifactExecutionEngine` (Runtime)**: Executes any `WorkflowDAG` with manifest fingerprinting, DAG-based cache hydration (`ISSUE-048`), batched graph projection (`ISSUE-046`), and symmetric event lifecycle management (`ISSUE-052`).

---

## 4. Post-Implementation Architectural Audit & Zero-Legacy Remediation Scope

Following review of commit `2982acd`, the macro-level separation into `PipelineFactory`, `WorkflowDAG`, `ArtifactExecutionEngine`, and `EpistemicQualityGate` is sound, but six architectural and domain defects must be remediated under our zero-legacy standard:

1. **True Topological DAG Execution & Branch-Scoped Dataflow (`WorkflowDAG` + `ArtifactExecutionEngine`)**:
   - `WorkflowDAG` must validate acyclicity eagerly on construction, resolve dependencies across all nodes (not only backward slice `[:i]`), and `ArtifactExecutionEngine.execute()` must iterate in `workflow.topological_order()`.
   - Each node's input `ArtifactCollection` and `lineage_fingerprint` must be scoped to its transitive upstream DAG dependencies (`transitive_dependencies(phase_key)`) rather than a single global flat `previous` collection, isolating parallel multi-branch workflows (e.g., Comparative Theory Alignment).
   - Quality gate fingerprints must be included in `phase_config_fingerprints` / invalidation checks so modifying a gate's thresholds invalidates and re-evaluates the gated phase.
2. **Centralized Quality Gate Event & Violation Lifecycle (OCP/DIP)**:
   - Quality gates must be pure domain evaluators returning `QualityGateResult` without side-effecting on the event bus or raising exceptions directly. `ArtifactExecutionEngine.evaluate_phase_quality_gates()` must uniformly emit `QualityGateEvaluated`, record manifest notes, emit `QualityGateWarning`, or raise `QualityGateViolationError` for both built-in and custom gates.
3. **Phase-Scoped Conformal Prediction Tracking & Active Calibrator Wiring (`ObservableDecisionEngine` + `ConformalCalibrationGate`)**:
   - `ObservableDecisionEngine` must apply `self.calibrator.predict_set(result)` when `self.calibrator` is configured and `result.prediction_set is None`, instrument `evaluate_batch()` via `evaluate_questions_sequentially` (or record per-item sets/events), and scope recorded prediction sets by active phase (`clear_prediction_sets()` at phase start or phase-keyed buffer) so Phase 2/3b sets never contaminate Phase 3/4 gates.
   - `ConformalCalibrationGate` must also support Phase 2 / 3b / 5 conformal evaluations and inspect typed `DecisionEvaluationCompleted` / phase-scoped sets cleanly.
4. **Domain Fixes in `OntologyEntropyGate` and `PercolationQualityGate`**:
   - `OntologyEntropyGate`: `require_nonzero_density` must default to `True` in `build_default_quality_gates()` (catching 0-entity extraction on non-empty chunks by default) and account for schema entity-type cardinality ($|T| \le 1 \implies H_{\min} = 0$).
   - `PercolationQualityGate`: Separate L2 (`LinkedEntityArtifact` + `CanonicalizationArtifact` / L2 `FusionDecisionArtifact`) and L3 (`TheoryAtomArtifact` + L3 `FusionDecisionArtifact`) populations so `cluster_layer="both"` in Phase 5 does not conflate L2 and L3 denominators.
5. **Eliminate Disguised `getattr` (`try/except AttributeError`) & Enforce Strict `PhaseRunner` Protocol**:
   - Remove the 14 `try ... except AttributeError` blocks in `WorkflowDAG` and `ArtifactExecutionEngine` in favor of strict `PhaseRunner` attributes (`phase_key`, `name`, `input_view`, `reads_kinds`, `writes_kinds`, `dependencies`, `checkpoint_store`) and public `EpistemicStateView.allowed_kinds`.
6. **Zero-Legacy `Pipeline` Facade & Unified Engine Entrypoints**:
   - Move `run_from_phase()` and `resume_from_run()` into `ArtifactExecutionEngine`, eliminate duplicated `run()` logic, and shrink `Pipeline` to a thin facade without private `_phase_entries` / `_custom_phase_entries` mutation shims.

---

## 5. Acceptance Criteria

- [ ] `EpistemicQualityGate` protocol is evaluated purely after each phase in `ArtifactExecutionEngine`, with centralized `QualityGateEvaluated` emission, warning/halt policy enforcement, and gate fingerprint invalidation.
- [ ] `OntologyEntropyGate`, `PercolationQualityGate`, and `ConformalCalibrationGate` accurately evaluate phase-scoped artifacts and calibrated `ObservableDecisionEngine` prediction sets without cross-phase buffer contamination or L2/L3 denominator mixing.
- [ ] `WorkflowDAG` validates acyclicity eagerly and `ArtifactExecutionEngine` executes in topological order with branch-isolated upstream `ArtifactCollection` and `lineage_fingerprint` scoping.
- [ ] `Pipeline` is a thin, zero-legacy facade delegating `run`, `run_from_phase`, `resume_from_run`, `get_run_report`, `get_run_artifacts`, and `diff_artifacts` to `ArtifactExecutionEngine`, with zero `try/except AttributeError` duck-typing in `WorkflowDAG`.
