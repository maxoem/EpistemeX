# [ISSUE-110] Checkpointing Resilience, Neo4j Isolation & Workflow/Quality-Gate Hardening

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-110` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Checkpoint Isolation, Crash Recovery, WorkflowDAG, Epistemic Quality Gates, Observability) |
| **Originating Issues** | [`ISSUE-046`](ISSUE-046-split-brain-state-artifact-vs-neo4j-isolation.md), [`ISSUE-051`](ISSUE-051-episodic-memory-crash-amnesia-and-quadratic-retrieval-scaling.md), [`ISSUE-052`](ISSUE-052-event-bus-lifecycle-gaps-unflushed-spans-and-audit-completeness.md), [`ISSUE-058`](ISSUE-058-runtime-epistemic-quality-gates-and-declarative-orchestrator.md), [`ISSUE-059`](ISSUE-059-phase-runner-template-method-lifecycle-and-component-wiring.md), [`ISSUE-061`](ISSUE-061-reflection-antipatterns-getattr-hasattr-and-leaky-protocols.md), [`ISSUE-065`](ISSUE-065-dry-consolidation-of-vector-graph-and-pairing-primitives.md) |
| **Target Package(s)** | `../../../../packages/episteme-pipeline` (`runtime/`, `graph/`, `artifacts/`, `phases/`, `post_processing/`, `events/`, `decision/`, `evaluation/`, `tests/`) |
| **Priority** | **Medium** |
| **Status** | `Resolved` |
| **Evaluated Docs & ADRs** | [`../../../../docs/architecture/artifact_run_model.md`](../../../../docs/architecture/artifact_run_model.md), [`../../../../docs/architecture/runtime_analysis.md`](../../../../docs/architecture/runtime_analysis.md), [`../../../../docs/architecture/event-system.md`](../../../../docs/architecture/event-system.md), [`ADR-0016`](../../../../docs/adr/0016-phase-3-within-phase-checkpointing-and-atomicity.md), [`ADR-0017`](../../../../docs/adr/0017-explicit-batch-contracts-and-bulk-io.md) |

---

## 1. Current State & Audit Findings

While core abstractions for offline execution, checkpointed batching, DAG orchestration, and epistemic quality gates are in place, four clusters of runtime hardening, Neo4j isolation, and `ISSUE-058` completion gaps remain open:

1. **`Neo4jCheckpointStore` Lineage-Key Crash, Unscoped Clearing & Lossy Artifact Projection (`ISSUE-046`)**:
   - [`_cypher_identifier()`](../../../../packages/episteme-pipeline/episteme_pipeline/graph/neo4j_store.py#L71-L95) enforces `_IDENTIFIER_RE = r"^[A-Za-z_][A-Za-z0-9_]*$"`, rejecting `:` in lineage-scoped phase keys (e.g. `"phase2:<lineage_fp>"`). `_Neo4jCheckpointMixin` (`#L1130,L1166,L1186,L1262,L1288,L1299`) validates `phase` through `_cypher_identifier`, causing **`Neo4jCheckpointStore` to raise `ValueError` during Phase 2/3/4 execution**.
   - [`ArtifactExecutionEngine.execute()`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py#L1134) calls `await chk_store.clear_phase_checkpoints(entry.phase_key)` with unscoped `entry.phase_key` rather than `f"{entry.phase_key}:{lineage_fp}"`, leaving stale lineage-scoped checkpoints behind on forced re-runs (`run_from_phase` with unchanged config/input).
   - Lossy projection vs. documentation when `Phase1Runner` runs with `graph_store=None`: [`DocumentArtifact.project_to_graph()`](../../../../packages/episteme-pipeline/episteme_pipeline/artifacts/models.py#L221-L227) writes only `:Document`, dropping `:Chapter`, `(:Document)-[:CONTAINS]->(:Chapter)`, `(:Chapter)-[:CONTAINS]->(:Chunk)`, and `(:Chunk)-[:NEXT]->(:Chunk)` edges; `FusionDecisionArtifact.collect_for_projection` (`#L399-L401`) is a no-op; [`TheoreticalEnrichmentArtifact`](../../../../packages/episteme-pipeline/episteme_pipeline/projection/artifact_projector.py#L137-L150) patches `edge_tenability` without projecting `:Theory` / `:HAS_THEORY_ELEMENT` / `:GOVERNED_BY`; and `DocumentArtifact` / `TheoryInference` (`artifact_projector.py#L191-L219`) still issue per-node `upsert_node` calls rather than bulk `UNWIND`.
   - [`docs/architecture/artifact_run_model.md#L198`](../../../../docs/architecture/artifact_run_model.md#L198) still describes `FileSystemCheckpointStore` as an *"append-only JSONL Write-Ahead Log (WAL)"* rather than atomic `.json.tmp` rewrites, and lines `#L235,L244-L245` list edges currently dropped by projection.

2. **Unwired `CheckpointedBatchExecutor`, Incomplete STM Crash Recovery & Phase 3b Scaling (`ISSUE-051`)**:
   - 3 of 4 `CheckpointedBatchExecutor` targets are inactive or broken in `Pipeline.for_task()`:
     - **Phase 4 Maturation**: [`PipelineFactory.build_phases()`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L782-L787) passes `graph_store=None`, leaving `checkpoint_store=None` (`phase4_entity_maturation/__init__.py#L530-L534`) and `guard_systematic_failure=False` (`#L589`).
     - **Theoretical Enrichment**: [`PipelineFactory.resolve_components()`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L549) and `build_phases()` (`#L833`) pass `graph_store=None`, leaving `checkpoint_store=None` (`post_processing/theoretical_enrichment/runner.py#L317-L321`) and `guard_systematic_failure=False` (`#L393`).
     - **Phase 4 ARC**: [`Phase4Runner.run()`](../../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/__init__.py#L448-L454) passes `graph_store=active_reader` (`ArtifactSubgraphReader`, not a `PhaseCheckpointStore`), leaving `checkpoint_store=None` (`arc_classifier.py#L227-L229`). Furthermore, `phase_tag="phase4_arc"` (`#L244`) omits `lineage_fingerprint`, `guard_systematic_failure=False` (`#L248`), and `_classify_pair()` (`#L447-L454`) catches `Exception` and returns `None`, marking poison pills `"completed"` instead of quarantining them as `"failed"`.
   - **Phase 2 STM Crash-Recovery Gaps**:
     - [`EpisodicWorkingMemoryManager.snapshot_state()`](../../../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/working_memory.py#L465-L486) omits `EpisodicEvictionHandler` state (`_last_section_path`, `_last_parent_header`, `#L320-L322`).
     - [`CheckpointedStreamExecutor.execute()`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/batch_executor.py#L469-L475) marks chunks processed *before* saving the STM snapshot (non-atomic crash window).
     - On mid-phase crash recovery under `FileSystemCheckpointStore`, `Phase2Runner.run()` and `Phase4Runner.run()` skip previously processed chunks without recovering their already-extracted entities/triples/atoms, dropping pre-crash outputs from the returned `ArtifactCollection`.
     - The first chapter stream reuses `self.working_memory_manager` directly without forking (`phase2_entity_discovery/__init__.py#L236-L239`), risking state bleed on runner reuse.
     - No end-to-end mid-chapter crash-and-restart test exists for `Phase2Runner.run()` in `tests/test_issue_051_scalability_and_resilience.py`.
   - **Phase 3b Scaling & Stale Complexity Docs**:
     - [`LatentGraphConsolidation.fuse()`](../../../../packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/consolidation.py#L292-L353) and [`Phase3bConfig`](../../../../packages/episteme-pipeline/episteme_pipeline/config.py#L280-L288) implement `use_csls` only—lacking `z_score_normalize`/`z_score_threshold` and `dynamic_k_effective` ($K_{\text{eff}}(E)$) pruning (still iterating all $O(E^2)$ pairs), while `JevARCClassifier` (`classifiers.py#L919`) bypasses CSLS/adaptive $K$.
     - [`docs/architecture/runtime_analysis.md#L31-L33,L62-L83,L122-L141`](../../../../docs/architecture/runtime_analysis.md#L31-L33) still documents unmitigated raw cosine thresholding (`0.5`) and small-input $O(N^2)$ behavior.

3. **Unfinished `ISSUE-058` Remediation Scope (`WorkflowDAG` & Pure Quality Gates)**:
   - All 4 Acceptance Criteria boxes in [`ISSUE-058`](ISSUE-058-runtime-epistemic-quality-gates-and-declarative-orchestrator.md#L80-L83) remain unchecked because Section 4 items #1–#3 remain incomplete:
     - [`WorkflowDAG.__init__`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/workflow_dag.py#L86-L102) does not eagerly validate acyclicity on construction (cycle detection stays lazy via `topological_order()`).
     - [`WorkflowDAG.dependencies()`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/workflow_dag.py#L309-L312) resolves `reads_kinds & prev.writes_kinds` only over the backward slice `self._nodes[:i]` rather than across all nodes.
     - Built-in quality gates are not pure domain evaluators: [`_finalize_gate_evaluation()`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/quality_gates.py#L62-L126) still directly emits `QualityGateEvaluated` (`#L111`), emits `warnings.warn(..., QualityGateWarning)` (`#L125`), and raises `QualityGateViolationError` (`#L124`). Meanwhile, `execution_engine.py` duplicates `_GateEventSpy` at module level (`#L110-L171`) and inside `evaluate_phase_quality_gates()` (`#L816-L839`), and fails to emit `QualityGateWarning` when a custom pure gate returns `QualityGateResult(passed=False, severity="warn")` (`#L871-L890`).
     - [`ConformalCalibrationGate`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/quality_gates.py#L673,L909-L916) defaults to `target_phases = frozenset({"phase3", "phase4"})`, omitting Phase 2, Phase 3b, and Phase 5 conformal evaluations (while Phase 3 uses `evaluate_noul`, producing no prediction sets).
     - [`PercolationQualityGate._compute_l3_percolation()`](../../../../packages/episteme-pipeline/episteme_pipeline/runtime/quality_gates.py#L555) selects `l2_ratio > l3_ratio` without checking `min_population`, allowing a sub-threshold L3 population to mask a violating L2 population.

4. **Remaining Observability, Protocol & Hygiene Follow-Ups (`ISSUE-052`, `ISSUE-059`, `ISSUE-061`, `ISSUE-065`)**:
   - **Event Telemetry Persistence (`ISSUE-052`)**: `RunReport.observer_telemetry` is populated in memory (`execution_engine.py#L1249-L1251`) but not persisted in `RunManifest`, so `get_run_report(run_id)` (`#L2089-L2106`) reloads `{}`; `SimpleEventEmitter` delivery/error counters do not reset across runs on a shared emitter; post-runner `artifact_store.write_artifact` / `projector.project_collection` (`execution_engine.py#L1256-L1261`) sit outside the phase `try/except` failure-event boundary; `LangfuseObserver.on_event()` (`events/langfuse_observer.py#L122-L123`) swallows exceptions before `SimpleEventEmitter.observer_errors` can count them; and [`docs/architecture/event-system.md#L123`](../../../../docs/architecture/event-system.md#L123) references stale `_run_observability_scope`.
   - **Progress Guard & Docstrings (`ISSUE-059`)**: `DenseRetrievalGlobalRelationExtractor.extract()` (`dense_retrieval_extractor.py#L306,L319`) emits `ProgressStarted`/`ProgressCompleted` without `try...finally`; stale module docstrings in `ner_extractor.py#L8-L9` and `adu_segmenter.py#L5-L8` still mention returning `[]` on error.
   - **Protocol & Reflection Hygiene (`ISSUE-061`)**: `GleaningStoppingOracle` (`protocols/decision.py#L319`) and `TheoryRegistry` (`enrichment_models.py#L262`) should inherit `Fingerprintable`, eliminating the remaining `hasattr(..., "fingerprint")` checks in `decision/gleaning.py#L127` and `decision/jev_client.py#L1050`; `tests/test_dry_primitives.py#L254-L259` should scan all of `runtime/` instead of only `runtime/runner.py`.
   - **Norm Guard (`ISSUE-065`)**: `evaluation/scorers/gm_gbs.py#L39-L40` still normalizes via `a / np.linalg.norm(a, axis=1, keepdims=True)` without zero-norm clamping (`l2_normalize`).

---

## 2. Why This Causes Problems

1. **Broken Neo4j Checkpointing & Lost Mid-Phase Progress**: Passing `Neo4jCheckpointStore` fails immediately on `phase2:<fp>`, while `FileSystemCheckpointStore` drops pre-crash entities/atoms on restart and 3 of 4 `CheckpointedBatchExecutor` stages never even receive a checkpoint store from `PipelineFactory`.
2. **Incomplete `WorkflowDAG` & Gate Contracts**: Lazy cycle checks fail only when `topological_order()` runs, non-pure gates force brittle spy wrappers, and `ConformalCalibrationGate` overlooks the three stages where `predict_set` actually runs (`phase2`, `phase3b`, `phase5`).
3. **Observability Blind Spots**: Reloading run reports loses `observer_telemetry`, and exceptions during artifact persistence/projection bypass `PhaseFailed`/`RunFailed` telemetry.

---

## 3. Proposed Solution & Remediation Details

1. **Fix `Neo4jCheckpointStore` & Artifact-to-Graph Projection Parity**:
   - Store lineage-scoped `phase_key`s safely as parameterized Neo4j property values (or sanitize/split `(phase, lineage_fp)` in `_Neo4jCheckpointMixin`) instead of rejecting `:` via `_cypher_identifier`; pass `f"{entry.phase_key}:{lineage_fp}"` in `ArtifactExecutionEngine` `clear_phase_checkpoints()`.
   - Either project Phase 1 `:Chapter`/`CONTAINS`/`NEXT` and Phase 5/Enrichment `:Theory`/`HAS_THEORY_ELEMENT` nodes/edges via `ArtifactGraphProjector` (converting `DocumentArtifact` and `TheoryInference` to bulk `UNWIND` batches) or update `../../../../docs/architecture/artifact_run_model.md` explicitly—and fix the WAL vs. `.json.tmp` description at `#L198`.
2. **Wire Checkpointing & Complete Phase 2/3b Resilience**:
   - Wire `checkpoint_store` into `Phase4EntityMaturationRunner`, `TheoreticalEnrichmentRunner`, and `Phase4Runner` -> `TAGARCClassifier` (preserving offline `ArtifactSubgraphReader` for queries while supplying `checkpoint_store` separately for checkpoints), scope `phase4_arc` by `lineage_fingerprint`, enable `guard_systematic_failure=True`, and let poison-pill exceptions propagate to `CheckpointedBatchExecutor` instead of returning `None`.
   - Include `EpisodicEvictionHandler` state (`_last_section_path`, `_last_parent_header`) in STM snapshots, save STM snapshots atomically with/before chunk completion, recover already-checkpointed entities/atoms on mid-phase crash restart, fork the working memory manager for every stream (including the first), and add a `Phase2Runner.run()` crash-recovery test.
   - Add `z_score_normalize` and `dynamic_k_effective` ($K_{\text{eff}}(E)$) pruning to Phase 3b (`consolidation.py`, `Phase3bConfig`) and update `../../../../docs/architecture/runtime_analysis.md`.
3. **Finish `ISSUE-058` `WorkflowDAG` & Pure Quality-Gate Remediation**:
   - Call cycle/topological validation inside `WorkflowDAG.__init__` and resolve `reads_kinds & prev.writes_kinds` across all nodes (using topological/dependency consistency rather than `self._nodes[:i]`).
   - Make `OntologyEntropyGate`, `PercolationQualityGate`, and `ConformalCalibrationGate` pure evaluators returning `QualityGateResult` only; remove `_finalize_gate_evaluation()` side effects and `_GateEventSpy`, centralizing `QualityGateEvaluated`, `QualityGateWarning`, and `QualityGateViolationError` inside `ArtifactExecutionEngine.evaluate_phase_quality_gates()`.
   - Expand `ConformalCalibrationGate` default `target_phases` to cover Phase 2, Phase 3b, Phase 4, and Phase 5 (and enforce `min_population` before choosing L2 vs. L3 in `PercolationQualityGate._compute_l3_percolation`).
4. **Close Remaining Observability, Protocol & Hygiene Items**:
   - Persist `observer_telemetry` in `RunManifest`, reset `SimpleEventEmitter` counters at run start, cover artifact persistence/projection inside phase `try/except` failure emission, let `LangfuseObserver.on_event()` surface errors to the bus counter (or track internally), and fix `event-system.md#L123`.
   - Wrap `DenseRetrievalGlobalRelationExtractor.extract()` progress in `try...finally`, update stale docstrings in `ner_extractor.py`/`adu_segmenter.py`, inherit `Fingerprintable` on `GleaningStoppingOracle` and `TheoryRegistry`, remove the 2 `hasattr(..., "fingerprint")` checks in `decision/`, scan all of `runtime/` in `test_dry_primitives.py`, and use `l2_normalize` in `gm_gbs.py`.

---

## 4. Acceptance Criteria

- [x] `Neo4jCheckpointStore` handles `f"{phase_key}:{lineage_fp}"` keys without `_cypher_identifier` `ValueError`, `ArtifactExecutionEngine` clears lineage-scoped checkpoints on forced re-runs, and `artifact_run_model.md` matches actual `FileSystemCheckpointStore` and `ArtifactGraphProjector` behavior (with `DocumentArtifact` and `TheoryInference` batched via `UNWIND`).
- [x] `Pipeline.for_task()` wires `checkpoint_store` to Phase 4 Maturation, Theoretical Enrichment, and Phase 4 ARC (`phase4_arc:{lineage_fp}` with poison-pill quarantine and `guard_systematic_failure=True`).
- [x] `Phase2Runner.run()` restores `EpisodicEvictionHandler` state + STM snapshots on mid-chapter crash resume, isolates every chapter stream via `fork()`, recovers pre-crash artifacts on restart, and passes an end-to-end crash-resume test in `test_issue_051_scalability_and_resilience.py`.
- [x] Phase 3b supports `z_score_normalize` and `dynamic_k_effective` ($K_{\text{eff}}(E)$) candidate pruning, and `../../../../docs/architecture/runtime_analysis.md` reflects adaptive $K_{\text{eff}}$ / CSLS scaling.
- [x] `WorkflowDAG.__init__` validates acyclicity eagerly and resolves `reads_kinds`/`writes_kinds` across the full node set.
- [x] Built-in quality gates are pure `QualityGateResult` evaluators without `_GateEventSpy` or direct `emit`/`warn`/`raise`, `evaluate_phase_quality_gates()` emits `QualityGateWarning` uniformly for custom and built-in gates, `ConformalCalibrationGate` covers `{"phase2", "phase3b", "phase4", "phase5"}` by default, and `PercolationQualityGate` respects `min_population` when comparing L2 vs. L3.
- [x] `RunReport.observer_telemetry` persists across `get_run_report()`, post-runner write/projection errors emit phase/run failure events, `GleaningStoppingOracle`/`TheoryRegistry` inherit `Fingerprintable` (eliminating `hasattr` in `decision/`), `DenseRetrievalGlobalRelationExtractor.extract()` uses `try...finally` progress guards, and `gm_gbs.py` uses `l2_normalize`.
