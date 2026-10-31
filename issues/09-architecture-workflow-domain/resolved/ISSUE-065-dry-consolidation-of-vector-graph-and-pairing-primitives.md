# [ISSUE-065] DRY Violations Across Mathematical & Graph Primitives, Orchestrator Entrypoint Duplication & Dead Legacy Code

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-065` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (DRY / YAGNI Principles, Shared Mathematical Utilities, Orchestrator Hygiene) |
| **Target Package(s)** | `packages/episteme-pipeline` (`utils/`, `pipeline.py`, `artifacts/mappers.py`, `phases/`) |
| **Priority** | **Medium** |
| **Status** | `Resolved` |
| **Evaluated Docs & ADRs** | [`docs/architecture/design_patterns_and_standards.md §2 & §4.3`](../../../docs/architecture/design_patterns_and_standards.md), [`AGENTS.md §2`](../../../AGENTS.md) |

---

## 1. Current State

As highlighted in **[Design Patterns, Clean Code & Architectural Standards §4.3](../../../docs/architecture/design_patterns_and_standards.md)**, core mathematical algorithms, ID hashing functions, candidate caches, and orchestrator entrypoints have been copy-pasted across multiple phases, while several superseded modules and dead code paths remain in the repository.

### A. Copy-Pasted Mathematical & Graph Algorithms (DRY Violations)
1. **Union-Find Connected Components (`_union_find_components`)**:
   - Identical path-compressed Union-Find implementations are duplicated in [`phases/phase3b_consolidation/consolidation.py#L27-L60`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/consolidation.py#L27-L60) and [`phases/phase5_fusion/argument_clustering.py#L47-L66`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_clustering.py#L47-L66).
2. **Pairwise Cosine Similarity Matrix Calculation**:
   - Re-implemented 6 times across [`sota_entity_linker.py#L240-L254`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/sota_entity_linker.py#L240-L254), [`jev_entity_linker.py#L194-L200`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/jev_entity_linker.py#L194-L200), [`dense_retrieval_extractor.py#L411-L415`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/dense_retrieval_extractor.py#L411-L415), [`consolidation.py#L251-L255`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/consolidation.py#L251-L255), [`arc_classifier.py#L288-L293`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/arc_classifier.py#L288-L293), and [`argument_clustering.py#L121-L127`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_clustering.py#L121-L127).
3. **Deterministic Argument Component ID Hashing (`_stable_component_id`)**:
   - Copy-pasted verbatim between [`phases/phase4_argument_mining/acc_classifier.py#L28-L30`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/acc_classifier.py#L28-L30) and [`phases/phase4_argument_mining/classifiers.py#L43-L59`](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py#L43-L59).
4. **Cross-Chunk Priority Candidate Pairing**:
   - `_get_pairs_by_priority` in [`TAGARCClassifier` (`arc_classifier.py#L216-L263`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/arc_classifier.py#L216-L263) and `_get_cross_chunk_pairs` in [`JevARCClassifier` (`classifiers.py#L547-L577`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py#L547-L577) are identical 30-line loops.
5. **Bi-Encoder Candidate Embedding Cache in Phase 2 Linkers**:
   - `_canonical_entity_string`, `_populate_candidate_cache`, and `_candidate_embeddings` are duplicated between [`JevEntityLinker` (`jev_entity_linker.py#L118-L217`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/jev_entity_linker.py#L118-L217) and [`DenseEntityLinker` (`sota_entity_linker.py#L192-L271`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/sota_entity_linker.py#L192-L271).
6. **`InducedTheoryElement` $\to$ `TheoryElementDefinition` Conversion**:
   - Duplicated verbatim between [`TheoryRegistry.register_induced_theories()` (`enrichment_models.py#L262-L300`)](../../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/enrichment_models.py#L262-L300) and [`LLMTheoryInducer.induce_theories()` (`inducer.py#L160-L180`)](../../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/inducer.py#L160-L180).

### B. Orchestrator Entrypoint Duplication & Missing Context Managers (`pipeline.py`)
1. **`Pipeline.resume_from_run()` Forgets Telemetry & Log Context Managers (`pipeline.py#L1318-L1340`)**:
   - `Pipeline.run()` (`#L455-L515`) and `Pipeline.run_from_phase()` (`#L519-L602`) duplicate ~40 lines of manifest setup and wrap `self._execute(...)` in `with use_event_emitter(contextual_emitter):` and `with run_folder_logger(...):`.
   - However, `Pipeline.resume_from_run()` (`#L1318-L1340`) calls `await self._execute(...)` directly **without** `use_event_emitter` or `run_folder_logger`, so resumed runs lose contextual event routing and per-run log files!
2. **Duplicated Reused-Artifact Resolution (`pipeline.py#L1224-L1260` vs. `#L1285-L1315`)**:
   - `get_run_report()` and `get_run_artifacts()` contain identical 25-line nested loops computing `is_reused` and `ArtifactReportEntry`.

### C. Dead Code & YAGNI Violations
1. **`artifacts/mappers.py` (`#L1-L64`)**: `map_phase1_output_to_artifacts` through `map_phase4_output_to_artifacts` are never called anywhere in `episteme_pipeline` (all runners use `artifacts/builders.py`).
2. **`phases/phase1_foundation/adapters/base.py`**: 4-line unused re-export of `DataSourceAdapter`.
3. **`phases/phase2_entity_discovery/mention_context_injector.py#L23-L32`**: `_normalize_string` (and `import unicodedata`) is never called.
4. **`phases/phase2_entity_discovery/__init__.py#L223-L225`**: Computes `entity_count_by_type` in a loop and never reads it.
5. **`phases/phase5_fusion/models.py#L1-L22`**: `EntitySamenessOutput` is never imported or used anywhere.

---

## 2. Proposed Solution & Direct Fixes

### Step 1: Extract Shared Mathematical & Pairing Primitives into `episteme_pipeline/utils/`
1. Create `episteme_pipeline/utils/similarity.py` providing `l2_normalize(vectors: np.ndarray) -> np.ndarray` (with `norms[norms == 0] = 1e-10` clamping) and `cosine_similarity_matrix(a: np.ndarray, b: np.ndarray | None = None) -> np.ndarray`.
2. Create `episteme_pipeline/utils/graph_algorithms.py` providing `union_find_components(n: int, edges: Sequence[tuple[int, int]]) -> list[list[int]]`.
3. Extract `stable_component_id(chunk_id: str, ac_tag: str) -> str` and `build_cross_chunk_candidate_pairs(...)` into `phases/phase4_argument_mining/pairing.py` and reuse across `LLMACCClassifier`, `JevACCClassifier`, `TAGARCClassifier`, and `JevARCClassifier`.
4. Extract a shared `CandidateEmbeddingCache` mixin/helper used by both `DenseEntityLinker` and `JevEntityLinker`.

### Step 2: Unify Orchestrator Execution & Reporting Helpers in `pipeline.py`
1. Extract `_run_with_observability_context(...)` in `Pipeline` and route `run()`, `run_from_phase()`, and `resume_from_run()` through it so `use_event_emitter` and `run_folder_logger` are always active.
2. Extract `_collect_run_artifact_entries(manifest)` shared by `get_run_report()` and `get_run_artifacts()`.

### Step 3: Prune Dead YAGNI Code
Remove `artifacts/mappers.py`, `phases/phase1_foundation/adapters/base.py`, `phases/phase5_fusion/models.py`, `_normalize_string` in `mention_context_injector.py`, and the unused `entity_count_by_type` loop in `Phase2Runner`.

---

## 3. Acceptance Criteria

- [x] `cosine_similarity_matrix` and `union_find_components` exist in `episteme_pipeline/utils/` with unit tests covering zero-norm vectors and disconnected/connected components, replacing all 6 inline copies.
- [x] `Pipeline.resume_from_run()` executes inside `use_event_emitter` and `run_folder_logger`.
- [x] Dead modules (`artifacts/mappers.py`, `phase1_foundation/adapters/base.py`, `phase5_fusion/models.py`) and unused functions/variables are removed.
