# [ISSUE-059] Missing `PhaseRunner` Template Method, Unscoped Progress Lifecycle, Silent Exception Swallowing & Invisible Component Fingerprinting

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-059` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Design Patterns, Template Method, Dependency Injection, Observability & Fingerprinting) |
| **Target Package(s)** | `packages/episteme-pipeline` (`protocols/phase_runner.py`, `phases/`, `post_processing/theoretical_enrichment/`, `runtime/runner.py`) |
| **Priority** | **High** |
| **Status** | `Resolved` |
| **Evaluated Docs & ADRs** | [`docs/architecture/design_patterns_and_standards.md`](../../../docs/architecture/design_patterns_and_standards.md), [`docs/architecture/cross_cutting_concerns.md`](../../../docs/architecture/cross_cutting_concerns.md), [`ADR-0016`](../../../docs/adr/0016-phase-3-within-phase-checkpointing-and-atomicity.md), [`ADR-0017`](../../../docs/adr/0017-explicit-batch-contracts-and-bulk-io.md) |

---

## 1. Current State

As documented in **[Design Patterns, Clean Code & Architectural Standards (`§3.1–§3.2`)](../../../docs/architecture/design_patterns_and_standards.md)**, every pipeline phase shares a common execution lifecycle: emitting scoped progress events, slicing work items into batches, executing tasks concurrently with systematic failure circuit-breaking, committing batched graph checkpoints, and exposing its internal strategy components for deterministic run fingerprinting.

Currently, `PhaseRunner` ([`protocols/phase_runner.py`](../../../packages/episteme-pipeline/episteme_pipeline/protocols/phase_runner.py)) is a bare interface without a Template Method or shared execution helpers. Consequently, every concrete runner (`Phase1Runner` through `Phase6Runner` and `TheoreticalEnrichmentRunner`) re-implements this lifecycle ad-hoc with severe inconsistencies:

1. **Duplicated Lifecycle Boilerplate & Unguarded `ProgressStarted` Events**:
   - `@property def event_emitter(self) -> EventEmitter: return get_event_emitter()` is copy-pasted across 12 classes (`Phase1Runner`, `Phase2Runner`, `Phase3Runner`, `Phase3bLatentConsolidationRunner`, `Phase4EntityMaturationRunner`, `Phase4Runner`, `Phase5ArgumentWebRunner`, `Phase6Runner`, `TheoreticalEnrichmentRunner`, `DenseRetrievalGlobalRelationExtractor`, `JevEntityLinker`, `DenseEntityLinker`).
   - Only `Phase4Runner` (`phase4_argument_mining/__init__.py#L286-L298`) wraps `ProgressStarted` / `ProgressCompleted` in a `try ... finally` block. `Phase1Runner` (`#L115,L133`), `Phase2Runner` (`#L195,L219`), `Phase3Runner` (`#L168,L208`), `Phase3bLatentConsolidationRunner` (`#L81,L91`), `Phase4EntityMaturationRunner` (`#L131,L163`), and `Phase5ArgumentWebRunner` (`#L94,L131`) emit `ProgressStarted` **without `try ... finally`**—leaving Studio UI / CLI progress bars hanging indefinitely if an exception is raised mid-phase. `Phase6Runner` and `TheoreticalEnrichmentRunner` omit `ProgressStarted` / `ProgressCompleted` altogether.
   - `for batch in batched(..., 500): await self.graph_store.upsert_*(list(batch))` is manually repeated 15 times across runners instead of being encapsulated in `GraphWriter` / `BatchCheckpointExecutor`.

2. **Silent Exception Swallowing in Extractors Defeating `_guard_systematic_failure` & Corrupting Checkpoints**:
   - In [`LLMNERExtractor.extract()` (`phases/phase2_entity_discovery/ner_extractor.py#L227-L231`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/ner_extractor.py#L227-L231):
     ```python
     except Exception as exc:
         logger.warning("NER extraction failed for chunk %s: %s", chunk_id, exc)
         return [], [], None, False, None
     ```
     Because `LLMNERExtractor.extract` catches all exceptions and returns empty lists, `Phase2Runner._process_batch` (`phase2_entity_discovery/__init__.py#L280-L295`) **never sees an exception** in `asyncio.gather(..., return_exceptions=True)`! As a result:
     - `Phase2Runner._guard_systematic_failure` (`#L241-L259`) is **completely dead code** whenever the LLM endpoint is down, misconfigured, or rate-limited: `failures` is `0`, `succeeded` is `len(batch)`, and Phase 2 silently finishes with `COMPLETED` and 0 extracted entities!
     - Furthermore, in `Phase2Runner._process_chunk` (`#L367-L370`), because returning `[], []` is treated as "nothing extracted — leave chunk UNPROCESSED", any legitimate short paragraph (e.g., an acknowledgments or transition paragraph) that genuinely contains 0 entities is **never marked `phase2_processed = True`** and is re-sent to the LLM on every subsequent run forever!
   - Conversely, in [`LLMADUSegmenter.segment()` (`phases/phase4_argument_mining/adu_segmenter.py#L47-L51`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/adu_segmenter.py#L47-L51) and [`LLMACCClassifier.classify()` (`phases/phase4_argument_mining/acc_classifier.py#L79-L81`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/acc_classifier.py#L79-L81), exceptions are caught and swallowed into `return []` / `return [], []`. Then `Phase4Runner.run()` (`phase4_argument_mining/__init__.py#L225,L254-L256`) appends `cid` to `processed_chunk_ids` for every non-exception result and marks the chunk `phase4_processed = True`—meaning **transient LLM failures in Phase 4 permanently mark the chunk as processed and never retry it**, directly contradicting the module docstring at line 19!

3. **Mid-Loop Component Instantiation & Unused Dependencies Corrupting `method_fingerprints`**:
   - In [`Phase4Runner._process_chunk()` (`phases/phase4_argument_mining/__init__.py#L335-L352`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/__init__.py#L335-L352):
     ```python
     segmenter = self._adu_segmenter_override or LLMADUSegmenter(
         llm=self.llm,
         prompt_template=self.config.adu_segmentation_prompt_template,
     )
     ...
     classifier = self._acc_classifier_override or LLMACCClassifier(
         llm=self.llm,
         prompts=self.config.acc_prompts,
         strategy=self.config.acc_decoding_strategy,
     )
     ```
     `LLMADUSegmenter` and `LLMACCClassifier` are instantiated **inside `_process_chunk` on every chunk** rather than in `Phase4Runner.__init__`. Because `PhaseRunner.components()` (`protocols/phase_runner.py#L50-L64`) inspects `self` before `run()`, the default `ADUSegmenter` and `ACCClassifier` are **invisible to method fingerprinting**!
   - Conversely, [`Phase1Runner.__init__` (`phases/phase1_foundation/__init__.py#L77,L84`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase1_foundation/__init__.py#L77-L84) requires `llm` and binds `self.llm = llm`, even though Phase 1 never uses an LLM. And [`TAGRelationExtractor.__init__` (`phases/phase3_global_relations/tag_extractor.py#L58-L60`)](../../../packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/tag_extractor.py#L58-L60) binds `self.embedding_model = embedding_model`, even though TAG blocking never uses embeddings. Because `find_components()` discovers `self.llm` on `Phase1Runner` and `self.embedding_model` on `TAGRelationExtractor`, changing the LLM temperature or model **falsely invalidates Phase 1 (document chunking & embedding)**!

4. **Unwired System 1 Strategies & Stale Runtime Config**:
   - `Phase2Runner.__init__` (`phase2_entity_discovery/__init__.py#L60-L63,L162-L172`) imports `JevEntityLinker` and `CascadingEntityLinker` but never instantiates them when `decision_engine` is provided.
   - `Phase4Runner.__init__` (`phase4_argument_mining/__init__.py#L141-L167`) accepts `decision_engine` for `HybridModalResolver` and `JevGleaningGate`, but never wires `JevACCClassifier`, `CascadingACCClassifier`, `JevARCClassifier`, or `CascadingARCClassifier`.
   - [`runtime/runner.py` (`#L115,L126-L173`)](../../../packages/episteme-pipeline/episteme_pipeline/runtime/runner.py#L115) passes the removed `max_gleanings=2` argument to `Phase2Config` (silently ignored by Pydantic), duplicates `ModelConfig.from_env()` with conflicting default model names, and creates three separate Neo4j driver connection pools (`Neo4jGraphReader`, `Neo4jGraphWriter`, `Neo4jProcessingGraph`) to the same database.

---

## 2. Why This Causes Problems

- **Silent Data Loss & False-Positive Completion**: When an LLM provider returns 429/500 errors, Phase 2 silently swallows every error in `LLMNERExtractor.extract`, bypasses `_guard_systematic_failure`, and marks the phase `COMPLETED` with an empty ontology. In Phase 4, transient LLM errors permanently checkpoint chunks as `phase4_processed = True`, silently dropping all arguments in those chunks across resumes.
- **Unnecessary Re-Computation & Cache Misses**: Changing an LLM model invalidates Phase 1 chunk embeddings because `Phase1Runner` stores an unused `self.llm` attribute.
- **Dangling UI Progress States**: Any uncaught exception in Phases 1, 2, 3, 3b, 4 Maturation, or 5 leaves progress observers in an unfinished state.

---

## 3. Proposed Solution & Direct Fixes

Follow **[Design Patterns & Standards §3.1–§3.2](../../../docs/architecture/design_patterns_and_standards.md)**:

### Fix 1: Provide `event_emitter`, `progress_scope`, and `BatchCheckpointExecutor` on `PhaseRunner`
In [`packages/episteme-pipeline/episteme_pipeline/protocols/phase_runner.py`](../../../packages/episteme-pipeline/episteme_pipeline/protocols/phase_runner.py):
```python
from contextlib import contextmanager
from typing import Iterator
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import EventEmitter, ProgressAdvanced, ProgressCompleted, ProgressStarted


class PhaseRunner(ABC, Generic[InputT]):
    ...
    @property
    def event_emitter(self) -> EventEmitter:
        """Return the active contextual event emitter."""
        return get_event_emitter()

    @contextmanager
    def progress_scope(self, task_name: str, total_items: int, description: str = "") -> Iterator[callable]:
        """Emit ProgressStarted and guarantee ProgressCompleted in a finally block."""
        self.event_emitter.emit(
            ProgressStarted(task_name=task_name, total_items=total_items, description=description or self.name)
        )
        def advance(step: int = 1) -> None:
            self.event_emitter.emit(ProgressAdvanced(task_name=task_name, advance=step))
        try:
            yield advance
        finally:
            self.event_emitter.emit(ProgressCompleted(task_name=task_name))
```

### Fix 2: Stop Swallowing Exceptions in `LLMNERExtractor`, `LLMADUSegmenter`, and `LLMACCClassifier`
1. In `LLMNERExtractor.extract` (`ner_extractor.py#L227-L231`), `LLMADUSegmenter.segment` (`adu_segmenter.py#L47-L51`), and `LLMACCClassifier.classify` (`acc_classifier.py#L79-L81`), remove the broad `except Exception: return []` catch-all so exceptions propagate to the runner's `asyncio.gather(..., return_exceptions=True)` handler.
2. In `Phase2Runner._process_batch` (`phase2_entity_discovery/__init__.py#L316-L317`), mark every chunk whose `_process_chunk` coroutine returned normally (without raising an exception) as `processed_chunks.append(chunk_id)`—even if the chunk legitimately contained 0 entities or 0 triples—while leaving chunks that raised an exception unmarked for retry and counting them toward `_guard_systematic_failure`.

### Fix 3: Bind All Phase Strategies in `__init__` and Remove Unused Dependencies
1. In `Phase4Runner.__init__` (`phase4_argument_mining/__init__.py#L130-L167`), instantiate `self.adu_segmenter` and `self.acc_classifier` once in `__init__` (using `CascadingACCClassifier` / `CascadingARCClassifier` when `decision_engine` is present and configured), and pass `self.config.adu_segmentation_prompts` (`StructuredPromptBundle`) to `LLMADUSegmenter`:
   ```python
   self.adu_segmenter: ADUSegmenter = adu_segmenter or LLMADUSegmenter(
       llm=self.llm,
       prompts=self.config.adu_segmentation_prompts,
   )
   default_llm_acc = LLMACCClassifier(
       llm=self.llm,
       prompts=self.config.acc_prompts,
       strategy=self.config.acc_decoding_strategy,
   )
   self.acc_classifier: ACCClassifier = acc_classifier or (
       CascadingACCClassifier(
           fast_classifier=JevACCClassifier(self.decision_engine, self.config),
           llm_classifier=default_llm_acc,
           config=self.config,
       )
       if self.decision_engine is not None
       else default_llm_acc
   )
   ```
2. In `Phase1Runner.__init__` (`phase1_foundation/__init__.py#L77,L84`), remove the unused `llm` attribute (`self.llm`) so LLM config changes never invalidate Phase 1. In `TAGRelationExtractor.__init__` (`tag_extractor.py#L58`), remove the unused `self.embedding_model` attribute.
3. In `runtime/runner.py`, replace `Phase2Config(max_gleanings=2)` with `Phase2Config(gleaning=GleaningConfig(max_passes=2))`, delegate environment resolution to `PipelineConfig.from_env()`, and share a single `Neo4jProcessingGraph` instance across `graph_reader`, `projection_graph`, and `checkpoint_store`.

---

## 4. Acceptance Criteria

- [x] `PhaseRunner` provides `event_emitter` and `progress_scope`, and all phase runners wrap progress reporting in `with self.progress_scope(...):`.
- [x] `LLMNERExtractor.extract`, `LLMADUSegmenter.segment`, and `LLMACCClassifier.classify` propagate runtime exceptions to the batch executor instead of returning `[]`, and `_guard_systematic_failure` halts Phase 2 and Phase 4 when Batch 0 fails 100%.
- [x] Legitimate 0-entity chunks in Phase 2 are marked `phase2_processed = True` when `extract()` succeeds without error.
- [x] `Phase4Runner` binds `self.adu_segmenter` and `self.acc_classifier` in `__init__` so `Phase4Runner.components()` includes them in `method_fingerprints`.
- [x] `Phase1Runner` no longer stores `self.llm`, and changing `ModelConfig.llm_model` does not invalidate Phase 1 in `ArtifactInvalidationPlanner`.
