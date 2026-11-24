"""Deterministic tests for ISSUE-110 hardening across Neo4j checkpointing, projection, observability, and protocols.

Verifies:
1. ``Neo4jGraphStore`` (``_Neo4jCheckpointMixin``) accepts lineage-scoped phase keys
   (``f"{phase_key}:{lineage_fp}"``) without ``_cypher_identifier`` ``ValueError``,
   while still rejecting unsafe Cypher identifiers.
2. ``ArtifactExecutionEngine`` clears lineage-scoped checkpoints on forced re-runs.
3. ``ArtifactGraphProjector`` batches ``DocumentArtifact`` and ``TheoryInference``
   nodes via ``GraphWriter.upsert_nodes``.
4. ``RunReport.observer_telemetry`` persists in ``RunManifest`` across
   ``get_run_report()``, and ``SimpleEventEmitter`` resets counters across runs.
5. Post-runner ``artifact_store.write_artifact`` and ``projector.project_collection``
   failures emit symmetric ``ComponentCompleted(success=False)``, ``PhaseFailed``,
   and ``RunFailed`` events.
6. ``LangfuseObserver.on_event()`` surfaces errors to ``SimpleEventEmitter.observer_errors``
   without crashing execution.
7. ``GleaningStoppingOracle`` and ``TheoryRegistry`` satisfy ``Fingerprintable``.
8. ``DenseRetrievalGlobalRelationExtractor.extract()`` emits ``ProgressCompleted``
   in a ``try...finally`` guard on exceptions.
9. ``GraphBERTScoreEvaluator._cosine_similarity`` handles zero-norm vectors safely
   without producing ``NaN``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from episteme_pipeline.artifacts.builders import (
    build_document_artifact,
    build_theory_atom_artifact,
    build_theory_relation_artifact,
)
from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.config import Phase3Config, PipelineConfig, QualityGatesConfig
from episteme_pipeline.contracts.domain import (
    L1Document,
    L2Entity,
    PhaseItemRecord,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.evaluation.scorers.gm_gbs import GraphBERTScoreEvaluator
from episteme_pipeline.events import (
    ComponentCompleted,
    ComponentStarted,
    PhaseFailed,
    ProgressCompleted,
    ProgressStarted,
    RunFailed,
    SimpleEventEmitter,
    use_event_emitter,
)
from episteme_pipeline.events.langfuse_observer import LangfuseObserver
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore
from episteme_pipeline.graph.neo4j_store import Neo4jCheckpointStore, _normalize_phase_key
from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    DenseRetrievalGlobalRelationExtractor,
)
from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    TheoryRegistry,
)
from episteme_pipeline.projection.artifact_projector import ArtifactGraphProjector
from episteme_pipeline.protocols.decision import GleaningStoppingOracle
from episteme_pipeline.protocols.fingerprint import Fingerprintable
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runs.models import RunStatus
from episteme_pipeline.runtime import ArtifactExecutionEngine, WorkflowDAG
from episteme_pipeline.schema.default_schema import SchemaConfig


# ---------------------------------------------------------------------------
# 1. Neo4j Lineage-Scoped Phase Key Checkpointing & Bulk UNWIND Projection
# ---------------------------------------------------------------------------


class _FakeNeo4jResult:
    """Minimal async Neo4j result double capturing queries and returning canned records."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = list(records or [])

    async def single(self) -> dict[str, Any] | None:
        return self._records[0] if self._records else None

    async def data(self) -> list[dict[str, Any]]:
        return list(self._records)

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._idx >= len(self._records):
            raise StopAsyncIteration
        item = self._records[self._idx]
        self._idx += 1
        return item


class _FakeNeo4jSession:
    """Minimal async Neo4j session double recording Cypher queries and params."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.next_records: list[dict[str, Any]] = []

    async def __aenter__(self) -> _FakeNeo4jSession:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, query: str, **params: Any) -> _FakeNeo4jResult:
        self.calls.append((query, params))
        recs = list(self.next_records)
        self.next_records = []
        return _FakeNeo4jResult(recs)

    async def begin_transaction(self) -> _FakeNeo4jTx:
        return _FakeNeo4jTx(self)


class _FakeNeo4jTx:
    """Minimal async Neo4j transaction double."""

    def __init__(self, session: _FakeNeo4jSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeNeo4jTx:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, query: str, **params: Any) -> _FakeNeo4jResult:
        return await self._session.run(query, **params)

    async def commit(self) -> None:
        return None


class _FakeNeo4jDriver:
    """Minimal Neo4j driver double returning a shared fake session."""

    def __init__(self) -> None:
        self.session_obj = _FakeNeo4jSession()

    def session(self, database: str | None = None) -> _FakeNeo4jSession:
        return self.session_obj


@pytest.mark.asyncio
async def test_neo4j_checkpoint_store_supports_lineage_scoped_phase_keys() -> None:
    """Verify Neo4jCheckpointStore handles phase:lineage_fp keys safely and rejects Cypher injection."""
    phase_val, safe_prefix = _normalize_phase_key("phase2:abc-123_def")
    assert phase_val == "phase2:abc-123_def"
    assert safe_prefix == "phase2__abc_123_def"

    for bad in ("phase2; DROP DATABASE", "phase2:a:b", "123bad", "phase2`MATCH"):
        with pytest.raises(ValueError, match="Unsafe Cypher"):
            _normalize_phase_key(bad)

    store = Neo4jCheckpointStore.__new__(Neo4jCheckpointStore)
    driver = _FakeNeo4jDriver()
    store._driver = driver
    store.database = "neo4j"
    store._batch_size = 500
    store._max_retries = 0
    store._retry_base_delay = 0.0

    scoped_phase = "phase2:deadbeef01"

    await store.mark_chunks_processed(["c1", "c2"], scoped_phase)
    assert "c.`phase2__deadbeef01_processed` = true" in driver.session_obj.calls[-1][0]

    driver.session_obj.next_records = [
        {
            "id": "c2",
            "text": "Chunk 2 body",
            "source_doc_id": "d1",
            "sequence_index": 1,
            "token_count": 3,
        }
    ]
    unproc = await store.get_unprocessed_chunks(scoped_phase, ["c1", "c2"])
    assert [c.id for c in unproc] == ["c2"]
    assert driver.session_obj.calls[-1][1]["prop_key"] == "phase2__deadbeef01_processed"

    driver.session_obj.next_records = [{"k": "k2"}]
    unproc_items = await store.filter_unprocessed_items(["k1", "k2"], scoped_phase)
    assert unproc_items == ["k2"]
    assert driver.session_obj.calls[-1][1]["phase"] == scoped_phase

    await store.commit_phase_batch(
        scoped_phase,
        [],
        [PhaseItemRecord(key="k2", status="completed")],
    )
    assert driver.session_obj.calls[-1][1]["phase"] == scoped_phase

    await store.save_chunk_state_snapshot(scoped_phase, "c1", {"active": ["Kant"]})
    assert "c.`phase2__deadbeef01_state_snapshot`" in driver.session_obj.calls[-1][0]

    driver.session_obj.next_records = [{"snapshot": '{"active": ["Kant"]}'}]
    snap = await store.get_chunk_state_snapshot(scoped_phase, "c1")
    assert snap == {"active": ["Kant"]}

    await store.save_checkpoint_payloads(scoped_phase, {"c1": {"entities": []}})
    assert driver.session_obj.calls[-1][1]["phase"] == scoped_phase

    driver.session_obj.next_records = [{"key": "c1", "payload_json": '{"entities": []}'}]
    payloads = await store.get_checkpoint_payloads(scoped_phase)
    assert payloads == {"c1": {"entities": []}}

    await store.clear_phase_checkpoints(scoped_phase)
    clear_queries = [q for q, _ in driver.session_obj.calls[-2:]]
    assert any("c.`phase2__deadbeef01_processed`" in q for q in clear_queries)
    assert any("c.`phase2__deadbeef01_state_snapshot`" in q for q in clear_queries)


@pytest.mark.asyncio
async def test_execution_engine_clears_lineage_scoped_checkpoints_on_forced_rerun(
    tmp_path: Path,
) -> None:
    """Verify ArtifactExecutionEngine clears both unscoped and lineage-scoped checkpoints on forced re-run."""
    chk_store = FileSystemCheckpointStore(tmp_path / "checkpoints")

    class _CheckpointedPhase(PhaseRunner[Any]):
        name = "Phase 4: Argument Mining"
        phase_key = "phase4"
        reads_kinds: frozenset[ArtifactKind] = frozenset()
        writes_kinds = frozenset({ArtifactKind.THEORY_ATOM})

        def __init__(self, store: FileSystemCheckpointStore) -> None:
            self._store = store
            self.seen_lineage_fps: list[str] = []

        @property
        def checkpoint_store(self) -> FileSystemCheckpointStore:
            return self._store

        async def run(
            self, input: Any, context: ArtifactExecutionContext
        ) -> ArtifactCollection:
            fp = context.lineage_fingerprint
            self.seen_lineage_fps.append(fp)
            await self._store.mark_chunks_processed(["c1"], f"phase4:{fp}")
            await self._store.commit_phase_items(
                f"phase4_arc:{fp}",
                [PhaseItemRecord(key="a1::a2", status="completed")],
            )
            return ArtifactCollection([])

    runner = _CheckpointedPhase(chk_store)
    config = PipelineConfig(quality_gates=QualityGatesConfig(enabled=False))
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    doc_path = tmp_path / "doc.md"
    doc_path.write_text("# Doc\nBody.", encoding="utf-8")
    p_input = PipelineInput(source_paths=[str(doc_path)])

    workflow = WorkflowDAG(phases=[runner])
    engine = ArtifactExecutionEngine(workflow=workflow, config=config)

    res1 = await engine.run(p_input, run_id="run-1")
    assert res1.manifest.status == RunStatus.COMPLETED
    fp = runner.seen_lineage_fps[0]
    assert await chk_store.get_unprocessed_chunks(["c1"], f"phase4:{fp}") == []
    assert await chk_store.filter_unprocessed_items(["a1::a2"], f"phase4_arc:{fp}") == []

    # Wrap clear_phase_checkpoints to record cleared tags during forced re-run
    cleared_tags: list[str] = []
    orig_clear = chk_store.clear_phase_checkpoints

    async def spy_clear(phase: str) -> None:
        cleared_tags.append(phase)
        await orig_clear(phase)

    chk_store.clear_phase_checkpoints = spy_clear  # type: ignore[method-assign]

    res2 = await engine.run_from_phase(1, p_input, run_id="run-2")
    assert res2.manifest.status == RunStatus.COMPLETED
    assert f"phase4:{fp}" in cleared_tags
    assert f"phase4_arc:{fp}" in cleared_tags


@pytest.mark.asyncio
async def test_artifact_graph_projector_batches_documents_and_theory_inferences() -> None:
    """Verify ArtifactGraphProjector batches Document and TheoryInference nodes via upsert_nodes."""
    upsert_nodes_calls: list[tuple[str, list[dict[str, Any]]]] = []
    upsert_node_calls: list[str] = []

    class _RecordingGraphWriter:
        async def upsert_node(self, label: str, properties: dict[str, Any], **kwargs: Any) -> None:
            upsert_node_calls.append(label)

        async def upsert_nodes(
            self,
            label: str,
            nodes: list[dict[str, Any]],
            *,
            extra_labels: tuple[str, ...] = (),
        ) -> None:
            upsert_nodes_calls.append((label, list(nodes)))

        async def upsert_entities(self, entities: list[L2Entity]) -> None:
            return None

        async def upsert_triples(self, triples: list[Any]) -> None:
            return None

        async def upsert_relations(self, relations: list[dict[str, Any]]) -> None:
            return None

        async def upsert_theory_atoms(self, atoms: list[TheoryAtom]) -> None:
            return None

        async def upsert_argument_components(self, atoms: list[TheoryAtom]) -> None:
            return None

        async def upsert_argument_relations(self, relations: list[TheoryRelation]) -> None:
            return None

        async def upsert_theory_relations(self, relations: list[TheoryRelation]) -> None:
            return None

        async def upsert_chunks(self, chunks: list[Any]) -> None:
            return None

        async def upsert_structural_edges(self, edges: list[dict[str, Any]]) -> None:
            return None

        async def upsert_fusion_links(self, links: list[dict[str, Any]]) -> None:
            return None

    doc1 = build_document_artifact(
        L1Document(
            id="d1",
            title="Doc 1",
            source_path="/tmp/d1.md",
            chapter_count=1,
            chunk_count=1,
        ),
        run_id="r1",
        phase_name="Phase 1",
        method="loader",
    )
    doc2 = build_document_artifact(
        L1Document(
            id="d2",
            title="Doc 2",
            source_path="/tmp/d2.md",
            chapter_count=1,
            chunk_count=1,
        ),
        run_id="r1",
        phase_name="Phase 1",
        method="loader",
    )
    a1 = build_theory_atom_artifact(
        TheoryAtom(id="a1", component_type="PREMISE", text="P1", source_chunk_id="c1"),
        run_id="r1",
        phase_name="Phase 4",
        method="acc",
    )
    a2 = build_theory_atom_artifact(
        TheoryAtom(id="a2", component_type="CLAIM", text="C1", source_chunk_id="c1"),
        run_id="r1",
        phase_name="Phase 4",
        method="acc",
    )
    a3 = build_theory_atom_artifact(
        TheoryAtom(id="a3", component_type="PREMISE", text="P2", source_chunk_id="c1"),
        run_id="r1",
        phase_name="Phase 4",
        method="acc",
    )
    reified_rel = build_theory_relation_artifact(
        TheoryRelation(
            id="inf_1",
            source_id="a1",
            premise_ids=["a1", "a3"],
            target_id="a2",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="global",
        ),
        run_id="r1",
        phase_name="Phase 4",
        method="arc",
    )

    projector = ArtifactGraphProjector(_RecordingGraphWriter())  # type: ignore[arg-type]
    await projector.project_collection(ArtifactCollection([doc1, doc2, a1, a2, a3, reified_rel]))

    assert upsert_node_calls == []
    batched_by_label = {label: nodes for label, nodes in upsert_nodes_calls}
    assert "Document" in batched_by_label
    assert {n["id"] for n in batched_by_label["Document"]} == {"d1", "d2"}
    assert "TheoryInference" in batched_by_label
    assert [n["id"] for n in batched_by_label["TheoryInference"]] == ["inf_1"]


# ---------------------------------------------------------------------------
# 2. Observability Telemetry Persistence, Reset, Failure Boundaries & Langfuse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_observer_telemetry_persists_and_resets_across_runs(
    tmp_path: Path,
) -> None:
    """Verify observer_telemetry persists in RunManifest across get_run_report() and resets between runs."""

    class _NoOpRunner(PhaseRunner[Any]):
        name = "Phase 1"
        phase_key = "phase1"
        reads_kinds: frozenset[ArtifactKind] = frozenset()
        writes_kinds = frozenset({ArtifactKind.CHUNK})

        async def run(
            self, input: Any, context: ArtifactExecutionContext
        ) -> ArtifactCollection:
            return ArtifactCollection([])

    class _CountingObserver:
        def __init__(self) -> None:
            self.count = 0

        def on_event(self, event: Any) -> None:
            self.count += 1

        def flush(self) -> None:
            pass

    bus = SimpleEventEmitter()
    bus.register_observer(_CountingObserver())

    config = PipelineConfig(quality_gates=QualityGatesConfig(enabled=False))
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    doc_path = tmp_path / "doc.md"
    doc_path.write_text("# Doc\nText.", encoding="utf-8")
    p_input = PipelineInput(source_paths=[str(doc_path)])

    engine = ArtifactExecutionEngine(
        workflow=WorkflowDAG(phases=[_NoOpRunner()]),
        config=config,
        event_emitter=bus,
    )

    res1 = await engine.run(p_input, run_id="run-tel-1")
    run1_delivered = sum(res1.report.observer_telemetry["events_delivered"].values())
    assert run1_delivered > 0

    reloaded = await engine.get_run_report("run-tel-1")
    assert reloaded is not None
    assert reloaded.observer_telemetry == res1.report.observer_telemetry

    # Second run on the SAME shared emitter must reset counters (not accumulate run 1's count)
    res2 = await engine.run(p_input, run_id="run-tel-2")
    run2_delivered = sum(res2.report.observer_telemetry["events_delivered"].values())
    assert run2_delivered <= run1_delivered


@pytest.mark.asyncio
async def test_post_runner_persistence_and_projection_errors_emit_failure_events(
    tmp_path: Path,
) -> None:
    """Verify write_artifact and project_collection failures emit ComponentCompleted(False), PhaseFailed, and RunFailed."""
    doc_env = build_document_artifact(
        L1Document(
            id="d1",
            title="Doc",
            source_path="/tmp/d.md",
            chapter_count=1,
            chunk_count=1,
        ),
        run_id="r-err",
        phase_name="Phase 1",
        method="loader",
    )

    class _EmitDocRunner(PhaseRunner[Any]):
        name = "Phase 1"
        phase_key = "phase1"
        reads_kinds: frozenset[ArtifactKind] = frozenset()
        writes_kinds = frozenset({ArtifactKind.DOCUMENT})

        async def run(
            self, input: Any, context: ArtifactExecutionContext
        ) -> ArtifactCollection:
            return ArtifactCollection([doc_env])

    class _RecordingObserver:
        def __init__(self) -> None:
            self.events: list[Any] = []

        def on_event(self, event: Any) -> None:
            self.events.append(event)

        def flush(self) -> None:
            pass

    config = PipelineConfig(quality_gates=QualityGatesConfig(enabled=False))
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    doc_path = tmp_path / "doc.md"
    doc_path.write_text("# Doc\nText.", encoding="utf-8")
    p_input = PipelineInput(source_paths=[str(doc_path)])

    bus = SimpleEventEmitter()
    obs = _RecordingObserver()
    bus.register_observer(obs)

    engine = ArtifactExecutionEngine(
        workflow=WorkflowDAG(phases=[_EmitDocRunner()]),
        config=config,
        event_emitter=bus,
    )

    async def broken_write(artifact: Any) -> Any:
        raise OSError("Disk full during artifact persistence")

    engine.artifact_store.write_artifact = broken_write  # type: ignore[method-assign]

    with pytest.raises(OSError, match="Disk full"):
        await engine.run(p_input, run_id="run-write-fail")

    started = [e for e in obs.events if isinstance(e, ComponentStarted)]
    completed = [e for e in obs.events if isinstance(e, ComponentCompleted)]
    assert len(started) == 1
    assert len(completed) == 1
    assert completed[0].success is False
    assert any(isinstance(e, PhaseFailed) for e in obs.events)
    assert any(isinstance(e, RunFailed) for e in obs.events)

    manifest = engine.manifest_store.read_manifest("run-write-fail")
    assert manifest is not None
    assert manifest.status == RunStatus.FAILED


def test_langfuse_observer_surfaces_errors_to_event_bus_telemetry() -> None:
    """Verify LangfuseObserver.on_event re-raises handler errors so SimpleEventEmitter counts them."""
    observer = LangfuseObserver.__new__(LangfuseObserver)
    observer.client = MagicMock()
    observer.active_spans = {}

    def failing_resolve(event: Any) -> Any:
        raise RuntimeError("Langfuse transport error")

    observer._resolve_trace_context = failing_resolve  # type: ignore[method-assign]

    bus = SimpleEventEmitter()
    bus.register_observer(observer)

    # Event bus isolates the exception so pipeline never crashes, while incrementing observer_errors
    bus.emit(ComponentStarted(component_name="test", phase="Phase 1", run_id="r1"))
    assert len(bus.observer_errors.get("LangfuseObserver", [])) == 1


# ---------------------------------------------------------------------------
# 3. Protocol Hygiene, Progress Guards & Zero-Norm Clamp
# ---------------------------------------------------------------------------


def test_gleaning_stopping_oracle_and_theory_registry_are_fingerprintable() -> None:
    """Verify GleaningStoppingOracle inherits Fingerprintable and TheoryRegistry implements deterministic fingerprint()."""
    assert issubclass(GleaningStoppingOracle, Fingerprintable)

    registry = TheoryRegistry()
    assert isinstance(registry, Fingerprintable)
    fp1 = registry.fingerprint()
    fp2 = registry.fingerprint()
    assert fp1 == fp2
    assert fp1["class"] == "TheoryRegistry"


@pytest.mark.asyncio
async def test_dense_retrieval_extractor_progress_guard_on_exception() -> None:
    """Verify DenseRetrievalGlobalRelationExtractor.extract emits ProgressCompleted even on exception."""
    import asyncio

    emb = AsyncMock()
    emb.aget_text_embedding_batch.return_value = [[1.0, 0.0], [1.0, 0.0]]

    extractor = DenseRetrievalGlobalRelationExtractor(
        llm=MagicMock(),
        embedding_model=emb,
        reranker=MagicMock(),
        config=Phase3Config(dense_similarity_threshold=0.0, use_csls=False),
    )

    started_pair = asyncio.Event()

    async def slow_pair(*args: Any, **kwargs: Any) -> Any:
        started_pair.set()
        await asyncio.sleep(10)

    extractor._extract_pair = slow_pair  # type: ignore[method-assign]

    class _RecordingObserver:
        def __init__(self) -> None:
            self.events: list[Any] = []

        def on_event(self, event: Any) -> None:
            self.events.append(event)

        def flush(self) -> None:
            pass

    bus = SimpleEventEmitter()
    obs = _RecordingObserver()
    bus.register_observer(obs)

    entities = [
        L2Entity(id="e1", name="A", label="Concept", textual_envelope="A"),
        L2Entity(id="e2", name="B", label="Concept", textual_envelope="B"),
    ]
    with use_event_emitter(bus):
        task = asyncio.create_task(
            extractor.extract(entities, InMemoryGraphStore(), SchemaConfig())
        )
        await started_pair.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert any(isinstance(e, ProgressStarted) for e in obs.events)
    assert any(isinstance(e, ProgressCompleted) for e in obs.events)


def test_gm_gbs_cosine_similarity_handles_zero_norm_vectors_without_nan() -> None:
    """Verify GraphBERTScoreEvaluator._cosine_similarity clamps zero-norm rows safely via l2_normalize."""
    evaluator = GraphBERTScoreEvaluator(embed_fn=lambda xs: np.zeros((len(xs), 3)))
    a = np.array([[0.0, 0.0, 0.0], [3.0, 4.0, 0.0]])
    b = np.array([[0.0, 0.0, 0.0], [3.0, 4.0, 0.0]])
    sim = evaluator._cosine_similarity(a, b)
    assert not np.isnan(sim).any()
    assert sim[0, 0] == pytest.approx(0.0)
    assert sim[1, 1] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_batch_executor_noop_store_and_pydantic_codec_crash_recovery(
    tmp_path: Path,
) -> None:
    """Verify NoOpCheckpointStore and PydanticOutputCodec handle automatic crash recovery inside CheckpointedBatchExecutor."""
    import asyncio

    from episteme_pipeline.protocols.graph_store import NoOpCheckpointStore
    from episteme_pipeline.runtime.batch_executor import (
        CheckpointedBatchExecutor,
        PydanticOutputCodec,
    )

    entities = [
        L2Entity(id=f"e{i}", name=f"Concept_{i}", label="Concept") for i in range(3)
    ]

    # 1. NoOpCheckpointStore treats all items as pending and runs uniformly without None checks
    noop = NoOpCheckpointStore()
    assert await noop.filter_unprocessed_items(["e0", "e1"], "phase4_maturation") == [
        "e0",
        "e1",
    ]
    noop_exec = CheckpointedBatchExecutor[L2Entity, L2Entity](
        checkpoint_store=None,
        phase_tag="phase4_maturation",
        batch_size=2,
        item_key_fn=lambda e: e.id,
        process_item_fn=lambda e: asyncio.sleep(0, result=e.model_copy(update={"is_mature": True})),
        output_codec=PydanticOutputCodec(L2Entity),
    )
    assert isinstance(noop_exec.checkpoint_store, NoOpCheckpointStore)
    noop_res = await noop_exec.execute(entities)
    assert [e.id for e in noop_res.outputs] == ["e0", "e1", "e2"]
    assert all(e.is_mature for e in noop_res.outputs)

    # 2. FileSystemCheckpointStore + PydanticOutputCodec recovers pre-crash batch automatically
    chk_store = FileSystemCheckpointStore(tmp_path / "batch_codec_chk")
    processed_run1: list[str] = []

    async def crash_on_second_batch(entity: L2Entity) -> L2Entity:
        if entity.id == "e2":
            raise asyncio.CancelledError("Simulated crash on batch 2")
        processed_run1.append(entity.id)
        return entity.model_copy(update={"is_mature": True, "description": f"desc_{entity.id}"})

    exec1 = CheckpointedBatchExecutor[L2Entity, L2Entity](
        checkpoint_store=chk_store,
        phase_tag="phase4_maturation:fp_abc",
        batch_size=2,
        item_key_fn=lambda e: e.id,
        process_item_fn=crash_on_second_batch,
        output_codec=PydanticOutputCodec(L2Entity),
    )
    with pytest.raises(asyncio.CancelledError):
        await exec1.execute(entities)
    assert processed_run1 == ["e0", "e1"]

    # Restart recovers e0, e1 automatically and processes ONLY e2
    processed_run2: list[str] = []

    async def process_run2(entity: L2Entity) -> L2Entity:
        processed_run2.append(entity.id)
        return entity.model_copy(update={"is_mature": True, "description": f"desc_{entity.id}"})

    exec2 = CheckpointedBatchExecutor[L2Entity, L2Entity](
        checkpoint_store=chk_store,
        phase_tag="phase4_maturation:fp_abc",
        batch_size=2,
        item_key_fn=lambda e: e.id,
        process_item_fn=process_run2,
        output_codec=PydanticOutputCodec(L2Entity),
    )
    res2 = await exec2.execute(entities)
    assert processed_run2 == ["e2"]
    assert [e.id for e in res2.outputs] == ["e0", "e1", "e2"]
    assert [e.description for e in res2.outputs] == ["desc_e0", "desc_e1", "desc_e2"]
