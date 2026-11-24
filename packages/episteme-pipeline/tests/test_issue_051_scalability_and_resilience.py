"""Tests for ISSUE-051: Episodic memory crash amnesia, concurrent STM streams, and quadratic scaling.

Verifies:
1. Phase 2 persists serialized WorkingMemoryState snapshots and restores exact prior chunk STM upon mid-chapter crash resumption.
2. Phase 2 supports concurrent execution across independent (source_doc_id, chapter_id) streams with sequential intra-chapter STM.
3. CheckpointedBatchExecutor provides ADR-0016 atomic batch checkpointing, poison-pill quarantine, and systematic failure guards.
4. Candidate pair generation supports CSLS, dynamic K_eff scaling, and z-score thresholding in Phase 3, 3b, and 4 ARC.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from episteme_pipeline.config import (
    Phase2Config,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    TheoryAtom,
)
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase2_entity_discovery.working_memory import (
    EpisodicWorkingMemoryManager,
    JsonPatchWorkingMemoryState,
    KeyValueWorkingMemoryState,
    PydanticWorkingMemoryState,
)
from episteme_pipeline.phases.phase4_argument_mining.arc_classifier import (
    TAGARCClassifier,
)
from episteme_pipeline.runtime.batch_executor import (
    CheckpointedBatchExecutor,
    SystematicBatchFailureError,
)
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils.similarity import (
    csls_similarity_matrix,
    dynamic_k_effective,
    z_score_normalize,
)

# ---------------------------------------------------------------------------
# Criterion 1: WorkingMemoryState Snapshot Save/Restore & Crash Resumption
# ---------------------------------------------------------------------------


def test_working_memory_state_snapshot_roundtrip():
    """Verify bit-for-bit state restore across all WorkingMemoryState implementations."""
    # 1. JsonPatchWorkingMemoryState
    jp_state = JsonPatchWorkingMemoryState()
    jp_state.update(
        {
            "active_entities": ["Kant", "Categorical Imperative"],
            "unresolved_references": ["the former"],
            "current_argument_branch": "deontological ethics",
        }
    )
    raw_jp = jp_state.get_raw_state()
    restored_jp = JsonPatchWorkingMemoryState()
    restored_jp.load_raw_state(raw_jp)
    assert restored_jp.get_raw_state() == raw_jp
    assert restored_jp.to_prompt_context() == jp_state.to_prompt_context()

    # 2. PydanticWorkingMemoryState
    pyd_state = PydanticWorkingMemoryState()
    pyd_state.update(
        {
            "active_entities": ["e1", "e2"],
            "unresolved_references": ["m1"],
            "current_argument_branch": "analytic a priori",
        }
    )
    raw_pyd = pyd_state.get_raw_state()
    restored_pyd = PydanticWorkingMemoryState()
    restored_pyd.load_raw_state(raw_pyd)
    assert restored_pyd.get_raw_state() == raw_pyd
    assert restored_pyd.to_prompt_context() == pyd_state.to_prompt_context()

    # 3. KeyValueWorkingMemoryState
    kv_state = KeyValueWorkingMemoryState()
    kv_state.update({"last_entity": "Kant", "chapter": "1"})
    raw_kv = kv_state.get_raw_state()
    restored_kv = KeyValueWorkingMemoryState()
    restored_kv.load_raw_state(raw_kv)
    assert restored_kv.get_raw_state() == raw_kv


@pytest.mark.asyncio
async def test_episodic_working_memory_manager_snapshot_and_restore():
    """Verify EpisodicWorkingMemoryManager snapshots and restores state without amnesia."""
    mgr = EpisodicWorkingMemoryManager(state_strategy="json_patch")
    chunk = L1Chunk(
        id="c1",
        text="Kant explores a priori intuition.",
        source_doc_id="doc1",
        sequence_index=0,
        token_count=10,
        chapter_id="ch1",
    )
    mgr.process_step(
        chunk,
        state_delta={
            "active_entities": ["Kant", "Intuition"],
            "current_argument_branch": "Transcendental Aesthetic",
        },
    )

    snapshot = mgr.snapshot_state()
    assert snapshot["active_entities"] == ["Kant", "Intuition"]
    assert snapshot["current_argument_branch"] == "Transcendental Aesthetic"

    # Create a fresh manager and restore snapshot (simulating process restart mid-chapter)
    mgr_restored = EpisodicWorkingMemoryManager(state_strategy="json_patch")
    mgr_restored.restore_state(snapshot)

    assert mgr_restored.snapshot_state() == snapshot
    assert "Kant" in mgr_restored.state.to_prompt_context()


# ---------------------------------------------------------------------------
# Criterion 2: Chapter-Parallel Execution with Sequential Intra-Chapter STM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase2_concurrent_chapter_streams():
    """Verify Phase 2 processes independent chapters concurrently while keeping intra-chapter order."""
    config = Phase2Config(max_concurrent_chapters=2)
    schema = SchemaConfig()
    llm = MagicMock()
    store = InMemoryGraphStore()

    # Document 1 with Chapter 1 (2 chunks) and Chapter 2 (2 chunks)
    c1_1 = L1Chunk(
        id="c1_1",
        text="Kant defines space.",
        source_doc_id="doc1",
        sequence_index=0,
        token_count=5,
        chapter_id="ch1",
    )
    c1_2 = L1Chunk(
        id="c1_2",
        text="He also defines time.",
        source_doc_id="doc1",
        sequence_index=1,
        token_count=5,
        chapter_id="ch1",
    )
    c2_1 = L1Chunk(
        id="c2_1",
        text="Hume analyzes causation.",
        source_doc_id="doc1",
        sequence_index=2,
        token_count=5,
        chapter_id="ch2",
    )
    c2_2 = L1Chunk(
        id="c2_2",
        text="He rejects necessary connection.",
        source_doc_id="doc1",
        sequence_index=3,
        token_count=5,
        chapter_id="ch2",
    )

    runner = Phase2Runner(
        config=config,
        schema=schema,
        llm=llm,
        graph_store=store,
    )

    # Track execution sequence
    execution_order: list[str] = []

    async def mock_process_chunk(chunk: L1Chunk, **kwargs):
        execution_order.append(chunk.id)
        # Yield to let concurrent tasks interleave
        await asyncio.sleep(0.01)
        entity = L2Entity(
            id=f"e_{chunk.id}", name=f"Entity_{chunk.id}", label="Concept"
        )
        return [(entity, "envelope text")], [], chunk.id, {}, False, None

    runner._process_chunk = mock_process_chunk  # type: ignore[assignment]

    view = MagicMock()
    view.chunks = [c1_1, c1_2, c2_1, c2_2]
    context = MagicMock()
    context.run_id = "test_run_123"
    context.lineage_fingerprint = "test_fp"

    await runner.run(view, context)

    # Both c1_1 must precede c1_2, and c2_1 must precede c2_2
    assert execution_order.index("c1_1") < execution_order.index("c1_2")
    assert execution_order.index("c2_1") < execution_order.index("c2_2")

    # Verify snapshots were saved in store for all chunks
    s1_1 = await store.get_chunk_state_snapshot(
        f"phase2:{context.lineage_fingerprint}", "c1_1"
    )
    assert s1_1 is not None


# ---------------------------------------------------------------------------
# Criterion 3: CheckpointedBatchExecutor & Poison-Pill Quarantine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpointed_batch_executor_quarantine():
    """Verify poisoned items are quarantined as failed and skipped on rerun."""
    store = InMemoryGraphStore()
    phase = "test_phase"

    items = ["item_ok_1", "item_poison_2", "item_ok_3"]

    async def process_item(item: str) -> str:
        if "poison" in item:
            raise ValueError(f"Corrupted item payload: {item}")
        return f"processed_{item}"

    executor = CheckpointedBatchExecutor[str, str](
        checkpoint_store=store,
        phase_tag=phase,
        batch_size=2,
        item_key_fn=lambda x: x,
        process_item_fn=process_item,
        guard_systematic_failure=False,
    )

    result = await executor.execute(items)

    assert result.succeeded_count == 2
    assert result.failed_count == 1
    assert result.outputs == ["processed_item_ok_1", "processed_item_ok_3"]

    # Verify checkpoint store has all 3 keys (including failed poison pill)
    unprocessed = await store.filter_unprocessed_items(items, phase)
    assert unprocessed == []  # All are marked processed, poison-pill won't re-execute

    # Re-executing skips all 3
    result_second = await executor.execute(items)
    assert result_second.outputs == []


@pytest.mark.asyncio
async def test_checkpointed_batch_executor_systematic_failure_guard():
    """Verify executor aborts when all items of the first batch fail."""
    store = InMemoryGraphStore()
    phase = "test_systematic"

    items = ["bad_1", "bad_2"]

    async def fail_item(item: str) -> str:
        raise ConnectionError("LLM API service unavailable")

    executor = CheckpointedBatchExecutor[str, str](
        checkpoint_store=store,
        phase_tag=phase,
        batch_size=2,
        item_key_fn=lambda x: x,
        process_item_fn=fail_item,
        guard_systematic_failure=True,
    )

    with pytest.raises(
        SystematicBatchFailureError, match="All 2 items of the first batch failed"
    ):
        await executor.execute(items)


@pytest.mark.asyncio
async def test_checkpointed_batch_executor_upfront_filter_and_uow_order():
    """Verify upfront filtering packs pending items into dense batches and persists outputs before checkpoints."""
    store = InMemoryGraphStore()
    phase = "test_uow"
    call_log: list[str] = []

    # Pre-mark item_1 and item_3 as already processed
    from episteme_pipeline.contracts.domain import PhaseItemRecord

    await store.commit_phase_items(
        phase,
        [
            PhaseItemRecord(key="item_1", status="completed"),
            PhaseItemRecord(key="item_3", status="completed"),
        ],
    )

    async def process_item(item: str) -> str:
        return f"out_{item}"

    async def on_batch_complete(
        outputs: list[str], records: list[PhaseItemRecord]
    ) -> None:
        # Must run BEFORE item_2 and item_4 are committed to store
        unprocessed_during_hook = await store.filter_unprocessed_items(
            ["item_2", "item_4"], phase
        )
        assert unprocessed_during_hook == ["item_2", "item_4"]
        call_log.append(f"persisted:{len(outputs)}")

    executor = CheckpointedBatchExecutor[str, str](
        checkpoint_store=store,
        phase_tag=phase,
        batch_size=2,
        item_key_fn=lambda x: x,
        process_item_fn=process_item,
        on_batch_complete=on_batch_complete,
    )

    result = await executor.execute(["item_1", "item_2", "item_3", "item_4"])
    assert result.outputs == ["out_item_2", "out_item_4"]
    # Because upfront filtering removes item_1 and item_3 first, item_2 and item_4
    # are packed into a SINGLE batch of size 2 rather than two fragmented batches of size 1
    assert call_log == ["persisted:2"]
    assert await store.filter_unprocessed_items(["item_2", "item_4"], phase) == []


# ---------------------------------------------------------------------------
# Criterion 4: CSLS, Dynamic K_eff, and Z-Score Normalization
# ---------------------------------------------------------------------------


def test_dynamic_k_effective_bounds():
    """Verify sub-linear candidate degree bound scaling."""
    assert dynamic_k_effective(n=1, k_min=2, k_max=20) == 0
    # For small n=4, gamma=2.0 -> ceil(2 * 2) = 4, bounded by [2, 20]
    assert dynamic_k_effective(n=4, k_min=2, k_max=20) == 4
    # For medium n=16 -> ceil(2 * 4) = 8
    assert dynamic_k_effective(n=16, k_min=2, k_max=20) == 8
    # For very large n=10000 -> capped at k_max=20
    assert dynamic_k_effective(n=10000, k_min=2, k_max=20) == 20


def test_csls_similarity_matrix_penalizes_hubs():
    """Verify CSLS penalizes hub vectors with high mean cosine similarity."""
    # Hub vector h is somewhat similar to everyone
    hub = np.array([1.0, 1.0, 1.0, 0.0])
    v1 = np.array([1.0, 0.0, 0.0, 0.0])
    v2 = np.array([0.0, 1.0, 0.0, 0.0])
    v3 = np.array([0.0, 0.0, 1.0, 0.0])
    v4 = np.array([0.0, 0.0, 0.0, 1.0])

    vectors = np.array([hub, v1, v2, v3, v4])
    csls = csls_similarity_matrix(vectors, k_nearest=2)

    # Diagonal is 1.0
    assert np.allclose(np.diag(csls), 1.0)
    # CSLS matrix is symmetric
    assert np.allclose(csls, csls.T)
    # Hub off-diagonal similarity should be reduced relative to raw cosine
    from episteme_pipeline.utils.similarity import cosine_similarity_matrix

    cos = cosine_similarity_matrix(vectors)
    assert csls[0, 1] < cos[0, 1]


def test_z_score_normalize():
    """Verify similarity standardization into zero mean and unit variance."""
    mat = np.array(
        [
            [1.0, 0.9, 0.2],
            [0.9, 1.0, 0.4],
            [0.2, 0.4, 1.0],
        ]
    )
    z = z_score_normalize(mat, symmetric=True)
    # Off-diagonal elements (0.9, 0.2, 0.4)
    off_diag = [z[0, 1], z[0, 2], z[1, 2]]
    assert np.isclose(np.mean(off_diag), 0.0, atol=1e-5)
    assert np.isclose(np.std(off_diag), 1.0, atol=1e-5)


@pytest.mark.asyncio
async def test_arc_classifier_dynamic_k_and_csls():
    """Verify TAGARCClassifier enforces dynamic K_eff and CSLS in candidate pairing."""
    llm = MagicMock()
    emb = AsyncMock()
    # 4 components
    emb.aget_text_embedding_batch.return_value = [
        [1.0, 0.0, 0.0],
        [0.9, 0.1, 0.0],
        [0.8, 0.2, 0.0],
        [0.0, 0.0, 1.0],
    ]

    atoms = [
        TheoryAtom(
            id=f"a{i}",
            text=f"Premise {i}",
            component_type="PREMISE",
            source_chunk_id=f"c{i}",
        )
        for i in range(4)
    ]

    classifier = TAGARCClassifier(
        llm=llm,
        embedding_model=emb,
        use_csls=True,
        use_adaptive_k=True,
        adaptive_k_min=1,
        max_candidates_per_component=2,
    )

    pairs = await classifier._get_pairs_by_embedding(atoms)
    assert len(pairs) > 0
    # Dynamic K_eff(4) = min(2, max(1, 2 * 2)) = 2
    # Ensure no component is paired with more than 2 partners
    from collections import defaultdict

    counts = defaultdict(int)
    for a, b in pairs:
        counts[a.id] += 1
        counts[b.id] += 1
    for count in counts.values():
        assert count <= 2


# ---------------------------------------------------------------------------
# ISSUE-110 Hardening: End-to-End Crash Recovery, Wiring & Phase 3b/ARC Scaling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase2_runner_mid_chapter_crash_resume_restores_stm_eviction_and_artifacts(
    tmp_path,
):
    """Verify Phase2Runner mid-chapter crash resume restores STM, eviction state, stream isolation, and pre-crash artifacts."""
    from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
    from episteme_pipeline.artifacts.models import ArtifactKind
    from episteme_pipeline.artifacts.subgraph_reader import ArtifactSubgraphReader
    from episteme_pipeline.contracts.domain import L2Triple

    chk_store = FileSystemCheckpointStore(tmp_path / "checkpoints")
    config = Phase2Config(max_concurrent_chapters=1)
    schema = SchemaConfig()
    llm = MagicMock()

    c1 = L1Chunk(
        id="c1",
        text="Kant introduces transcendental aesthetics.",
        source_doc_id="doc1",
        sequence_index=0,
        token_count=10,
        chapter_id="ch1",
        metadata={"section_path": ["Part I", "Section 1"], "parent_header": "Part I"},
    )
    c2 = L1Chunk(
        id="c2",
        text="He distinguishes space from time.",
        source_doc_id="doc1",
        sequence_index=1,
        token_count=10,
        chapter_id="ch1",
        metadata={"section_path": ["Part I", "Section 1"], "parent_header": "Part I"},
    )
    c3 = L1Chunk(
        id="c3",
        text="In the next section, categories are deduced.",
        source_doc_id="doc1",
        sequence_index=2,
        token_count=10,
        chapter_id="ch1",
        metadata={"section_path": ["Part I", "Section 2"], "parent_header": "Part I"},
    )

    view = MagicMock()
    view.chunks = [c1, c2, c3]
    view.to_graph_reader.side_effect = lambda: ArtifactSubgraphReader()

    context = MagicMock()
    context.run_id = "run-crash-1"
    context.lineage_fingerprint = "fp_crash_resume"
    context.pipeline_input = None

    # --- Run 1: succeeds on c1, aborts mid-chapter on c2 ---
    runner1 = Phase2Runner(
        config=config,
        schema=schema,
        llm=llm,
        graph_store=chk_store,
    )

    async def process_run1(chunk: L1Chunk, **kwargs):
        if chunk.id == "c2":
            raise asyncio.CancelledError("Simulated mid-chapter crash on c2")
        ent = L2Entity(
            id=f"e_{chunk.id}",
            name=f"Entity_{chunk.id}",
            label="Concept",
            textual_envelope=f"Envelope for {chunk.id}",
            source_chunk_ids=[chunk.id],
        )
        triple = L2Triple(
            subject_id=ent.id,
            predicate="RELATED_TO",
            object_id=ent.id,
            confidence=0.9,
            scope="local",
            source_chunk_id=chunk.id,
        )
        return (
            [(ent, f"Envelope for {chunk.id}")],
            [triple],
            chunk.id,
            {
                "active_entities": ["Kant", "Transcendental Aesthetic"],
                "current_argument_branch": "Aesthetic",
            },
            False,
            None,
        )

    runner1._process_chunk = process_run1  # type: ignore[assignment]

    with pytest.raises(asyncio.CancelledError, match="Simulated mid-chapter crash"):
        await runner1.run(view, context)

    # First chapter stream must have been forked: runner's base manager stays untouched
    assert (
        runner1.working_memory_manager.snapshot_state().get("active_entities", []) == []
    )

    # Persisted snapshot must include EpisodicEvictionHandler state
    phase_tag = f"phase2:{context.lineage_fingerprint}"
    saved_snap = await chk_store.get_chunk_state_snapshot(phase_tag, "c1")
    assert saved_snap is not None
    assert saved_snap["active_entities"] == ["Kant", "Transcendental Aesthetic"]
    assert saved_snap["__eviction_last_section_path"] == ["Part I", "Section 1"]
    assert saved_snap["__eviction_last_parent_header"] == "Part I"

    # --- Run 2: fresh runner resumes from FileSystemCheckpointStore ---
    runner2 = Phase2Runner(
        config=config,
        schema=schema,
        llm=llm,
        graph_store=chk_store,
    )
    processed_in_run2: list[str] = []
    observed_pre_chunk_state: dict[str, dict] = {}

    async def process_run2(chunk: L1Chunk, **kwargs):
        processed_in_run2.append(chunk.id)
        mgr = kwargs["memory_mgr"]
        observed_pre_chunk_state[chunk.id] = mgr.snapshot_state()
        ent = L2Entity(
            id=f"e_{chunk.id}",
            name=f"Entity_{chunk.id}",
            label="Concept",
            textual_envelope=f"Envelope for {chunk.id}",
            source_chunk_ids=[chunk.id],
        )
        return (
            [(ent, f"Envelope for {chunk.id}")],
            [],
            chunk.id,
            {"active_entities": [f"Active_{chunk.id}"]},
            False,
            None,
        )

    runner2._process_chunk = process_run2  # type: ignore[assignment]

    collection = await runner2.run(view, context)

    # c1 must be skipped on restart; only c2 and c3 execute
    assert processed_in_run2 == ["c2", "c3"]

    # Before c2 runs, both STM AND EpisodicEvictionHandler state from c1 are restored
    assert observed_pre_chunk_state["c2"]["active_entities"] == [
        "Kant",
        "Transcendental Aesthetic",
    ]
    assert observed_pre_chunk_state["c2"]["__eviction_last_section_path"] == [
        "Part I",
        "Section 1",
    ]
    assert observed_pre_chunk_state["c2"]["__eviction_last_parent_header"] == "Part I"

    # Returned ArtifactCollection must include recovered pre-crash entities & triples from c1
    linked_ids = {
        env.payload.entity_id for env in collection.of_kind(ArtifactKind.LINKED_ENTITY)
    }
    assert linked_ids == {"e_c1", "e_c2", "e_c3"}
    local_rels = collection.of_kind(ArtifactKind.LOCAL_RELATION)
    assert len(local_rels) == 1
    assert local_rels[0].payload.subject_entity_id == "e_c1"


def test_pipeline_for_task_wires_checkpoint_store_to_maturation_enrichment_and_arc(
    tmp_path,
):
    """Verify Pipeline.for_task wires checkpoint_store into Phase 4 Maturation, Enrichment, and Phase 4 ARC."""
    from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
    from episteme_pipeline.config import PipelineConfig
    from episteme_pipeline.phases.phase4_argument_mining.classifiers import (
        CascadingARCClassifier,
    )
    from episteme_pipeline.pipeline import Pipeline

    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    llm = MagicMock()
    llm.model_name = "mock-llm"
    emb = MagicMock()
    emb.aget_text_embedding = MagicMock()
    reranker = MagicMock()
    reranker.arerank = MagicMock()

    pipeline = Pipeline.for_task(
        task="knowledge_graph",
        llm=llm,
        embedding_model=emb,
        relation_reranker=reranker,
        config=config,
    )

    by_key = {node.phase_key: node.runner for node in pipeline.workflow.nodes}
    assert isinstance(by_key["phase2"].checkpoint_store, FileSystemCheckpointStore)
    assert isinstance(by_key["phase3"].checkpoint_store, FileSystemCheckpointStore)
    assert isinstance(
        by_key["phase4_maturation"].checkpoint_store, FileSystemCheckpointStore
    )
    assert isinstance(by_key["phase4"].checkpoint_store, FileSystemCheckpointStore)
    assert isinstance(
        by_key["theoretical_enrichment"].checkpoint_store, FileSystemCheckpointStore
    )

    arc_cls = by_key["phase4"].arc_classifier
    if isinstance(arc_cls, CascadingARCClassifier):
        assert isinstance(
            arc_cls.llm_classifier.checkpoint_store, FileSystemCheckpointStore
        )
    else:
        assert isinstance(arc_cls.checkpoint_store, FileSystemCheckpointStore)


@pytest.mark.asyncio
async def test_arc_classifier_checkpointed_lineage_quarantine_and_systematic_guard(
    tmp_path,
):
    """Verify TAGARCClassifier uses lineage-scoped checkpoints, quarantines poison pills, recovers relations, and guards systematic failure."""
    from episteme_pipeline.artifacts.checkpoint_store import FileSystemCheckpointStore
    from episteme_pipeline.contracts.domain import TheoryRelation

    chk_store = FileSystemCheckpointStore(tmp_path / "arc_checkpoints")
    atoms = [
        TheoryAtom(
            id="a1", text="Premise 1", component_type="PREMISE", source_chunk_id="c1"
        ),
        TheoryAtom(
            id="a2", text="Claim 2", component_type="CLAIM", source_chunk_id="c2"
        ),
        TheoryAtom(
            id="a3", text="Claim 3", component_type="CLAIM", source_chunk_id="c3"
        ),
    ]
    pairs = [(atoms[0], atoms[1]), (atoms[0], atoms[2])]

    classifier = TAGARCClassifier(
        llm=MagicMock(),
        checkpoint_store=chk_store,
        batch_size=2,
    )

    calls: list[tuple[str, str]] = []

    async def flaky_classify(
        component_a: TheoryAtom,
        component_b: TheoryAtom,
        **kwargs,
    ):
        calls.append((component_a.id, component_b.id))
        if component_b.id == "a3":
            raise ValueError("Poison pill pair a1->a3")
        return TheoryRelation(
            source_id=component_a.id,
            target_id=component_b.id,
            relation_type="SUPPORTS",
            confidence=0.95,
            scope="global",
        )

    classifier._classify_pair = flaky_classify  # type: ignore[assignment]

    rels_first = await classifier.classify_pairs(
        pairs,
        graph_store=InMemoryGraphStore(),
        lineage_fingerprint="lin_A",
    )
    assert len(rels_first) == 1
    assert rels_first[0].source_id == "a1" and rels_first[0].target_id == "a2"
    assert calls == [("a1", "a2"), ("a1", "a3")]

    # Both pairs (completed + quarantined failed) are checkpointed under phase4_arc:lin_A
    unprocessed = await chk_store.filter_unprocessed_items(
        ["arc::a1::a2", "arc::a1::a3"], "phase4_arc:lin_A"
    )
    assert unprocessed == []

    # Re-running with same lineage skips both pairs AND recovers the pre-crash TheoryRelation!
    calls.clear()
    rels_second = await classifier.classify_pairs(
        pairs,
        graph_store=InMemoryGraphStore(),
        lineage_fingerprint="lin_A",
    )
    assert calls == []
    assert len(rels_second) == 1
    assert rels_second[0].source_id == "a1" and rels_second[0].target_id == "a2"

    # Systematic failure guard triggers when all items of batch 0 fail on a fresh lineage
    async def always_fail(
        component_a: TheoryAtom,
        component_b: TheoryAtom,
        **kwargs,
    ):
        raise ConnectionError("LLM endpoint unreachable")

    classifier._classify_pair = always_fail  # type: ignore[assignment]
    with pytest.raises(SystematicBatchFailureError):
        await classifier.classify_pairs(
            pairs,
            graph_store=InMemoryGraphStore(),
            lineage_fingerprint="lin_B",
        )


@pytest.mark.asyncio
async def test_phase3b_consolidation_adaptive_k_and_z_score_pruning():
    """Verify LatentGraphConsolidation enforces dynamic K_eff and z-score pruning while respecting curation constraints."""
    from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
    from episteme_pipeline.phases.phase3b_consolidation.consolidation import (
        LatentGraphConsolidation,
    )

    store = InMemoryGraphStore()
    entities = [
        L2Entity(
            id=f"e{i}",
            name=f"Concept_{i}",
            label="Concept",
            textual_envelope=f"text {i}",
        )
        for i in range(4)
    ]
    await store.upsert_entities(entities)

    # e0 and e1 are nearly identical; e2 is also close to e0/e1; e3 is orthogonal
    emb = AsyncMock()
    emb.aget_text_embedding_batch.return_value = [
        [1.0, 0.0, 0.0],
        [0.99, 0.14, 0.0],
        [0.95, 0.31, 0.0],
        [0.0, 0.0, 1.0],
    ]

    # With max_candidates_per_entity=1 and z_score_threshold=0.5, only the top pair (e0, e1) survives
    consolidator = LatentGraphConsolidation(
        embedding_model=emb,
        dense_similarity_threshold=0.80,
        relation_overlap_threshold=0.0,
        use_csls=False,
        use_adaptive_k=True,
        adaptive_k_min=1,
        max_candidates_per_entity=1,
        z_score_threshold=0.5,
    )
    fp = consolidator.fingerprint()
    assert fp["use_adaptive_k"] is True
    assert fp["z_score_threshold"] == 0.5

    mapping = await consolidator.fuse(store)
    # e0 and e1 merge, but e2 is pruned by k_eff=1 + z-score cutoff!
    assert len(mapping) == 1
    assert set(mapping.keys()) | set(mapping.values()) == {"e0", "e1"}

    # Hard must-link overrides pruning even for orthogonal e3
    ledger = EpistemicCurationLedger(must_link_entities={("e0", "e3")})
    mapping_with_ledger = await consolidator.fuse(store, curation_ledger=ledger)
    # e3 is merged with e0 despite orthogonal embeddings and adaptive K / z-score pruning
    assert "e3" in mapping_with_ledger or "e3" in set(mapping_with_ledger.values())
    assert "e2" not in mapping_with_ledger
    assert "e2" not in set(mapping_with_ledger.values())


@pytest.mark.asyncio
async def test_jev_arc_classifier_uses_csls_and_adaptive_k():
    """Verify JevARCClassifier applies CSLS and dynamic K_eff degree bounds to cross-chunk pairs."""
    from collections import defaultdict

    from episteme_pipeline.decision.mock import MockJevDecisionEngine
    from episteme_pipeline.phases.phase4_argument_mining.classifiers import (
        JevARCClassifier,
    )

    emb = AsyncMock()
    emb.aget_text_embedding_batch.return_value = [
        [1.0, 0.0, 0.0],
        [0.95, 0.1, 0.0],
        [0.90, 0.2, 0.0],
        [0.85, 0.3, 0.0],
    ]
    atoms = [
        TheoryAtom(
            id=f"a{i}",
            text=f"Claim {i}",
            component_type="CLAIM",
            source_chunk_id=f"c{i}",
        )
        for i in range(4)
    ]

    classifier = JevARCClassifier(
        decision_engine=MockJevDecisionEngine(),
        embedding_model=emb,
        use_csls=True,
        use_adaptive_k=True,
        adaptive_k_min=1,
        max_candidates_per_component=1,
    )
    pairs = await classifier._cross_chunk_pairs(atoms, SchemaConfig())
    assert len(pairs) > 0
    counts: dict[str, int] = defaultdict(int)
    for a, b in pairs:
        counts[a.id] += 1
        counts[b.id] += 1
    assert all(c <= 1 for c in counts.values())
