"""Deterministic unit tests verifying ISSUE-059 remediation.

Tests PhaseRunner lifecycle, progress scope guarantees, exception propagation across
extractors and classifiers, systematic failure circuit breakers, 0-entity chunk marking,
and component wiring for deterministic fingerprinting.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase1ArtifactsView,
    Phase3ArtifactsView,
)
from episteme_pipeline.config import (
    Phase1Config,
    Phase2Config,
    Phase4Config,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import (
    BaseEvent,
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
)
from episteme_pipeline.phases.phase1_foundation import Phase1Runner
from episteme_pipeline.phases.phase2_entity_discovery import (
    Phase2Runner,
    SystematicChunkFailure,
)
from episteme_pipeline.phases.phase2_entity_discovery.ner_extractor import (
    LLMNERExtractor,
)
from episteme_pipeline.phases.phase3_global_relations.tag_extractor import (
    TAGRelationExtractor,
)
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
from episteme_pipeline.phases.phase4_argument_mining.acc_classifier import (
    LLMACCClassifier,
)
from episteme_pipeline.phases.phase4_argument_mining.adu_segmenter import (
    LLMADUSegmenter,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


class DummyRunner(PhaseRunner[None]):
    """Dummy phase runner used for testing base PhaseRunner lifecycle."""

    name = "Dummy Phase"
    phase_key = "dummy"

    async def run(
        self, input: None, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Run dummy phase."""
        return ArtifactCollection([])


def test_progress_scope_symmetric_completion_on_exception() -> None:
    """Verify progress_scope guarantees ProgressCompleted is emitted even on exception."""
    from episteme_pipeline.events import PipelineEvent, SimpleEventEmitter, use_event_emitter

    emitter = SimpleEventEmitter()
    captured: list[PipelineEvent] = []

    class CapturedObserver:
        def on_event(self, event: PipelineEvent) -> None:
            captured.append(event)

    emitter.register_observer(CapturedObserver())

    runner = DummyRunner()

    with pytest.raises(ZeroDivisionError):
        with use_event_emitter(emitter):
            with runner.progress_scope("task-test", total_items=10, description="Testing Scope") as advance:
                advance(3)
                _ = 1 / 0

    assert len(captured) == 3
    assert isinstance(captured[0], ProgressStarted)
    assert captured[0].task_name == "task-test"
    assert captured[0].total_items == 10
    assert captured[0].description == "Testing Scope"

    assert isinstance(captured[1], ProgressAdvanced)
    assert captured[1].task_name == "task-test"
    assert captured[1].advance == 3

    assert isinstance(captured[2], ProgressCompleted)
    assert captured[2].task_name == "task-test"


@pytest.mark.asyncio
async def test_llm_ner_extractor_propagates_exceptions() -> None:
    """Verify LLMNERExtractor does not swallow exceptions into empty lists."""
    mock_llm = AsyncMock()
    mock_llm.predict_structured = AsyncMock(side_effect=RuntimeError("NER LLM Connection Timeout"))

    extractor = LLMNERExtractor(
        llm=mock_llm,
        prompts=Phase2Config().ner_prompts,
    )

    with pytest.raises(RuntimeError, match="NER LLM Connection Timeout"):
        await extractor.extract(
            chunk_id="chunk-1",
            chunk_text="Ein Text über empirische Anschauung.",
            schema=DEFAULT_SCHEMA,
        )


@pytest.mark.asyncio
async def test_llm_adu_segmenter_propagates_exceptions() -> None:
    """Verify LLMADUSegmenter does not swallow exceptions into empty results."""
    mock_llm = AsyncMock()
    mock_llm.predict_structured = AsyncMock(side_effect=RuntimeError("ADU Rate Limit Exceeded"))

    segmenter = LLMADUSegmenter(
        llm=mock_llm,
        prompts=Phase4Config().adu_segmentation_prompts,
    )

    with pytest.raises(RuntimeError, match="ADU Rate Limit Exceeded"):
        await segmenter.segment(
            chunk_id="chunk-1",
            chunk_text="Alle Prämissen bedürfen einer Deduktion.",
        )


@pytest.mark.asyncio
async def test_llm_acc_classifier_propagates_exceptions() -> None:
    """Verify LLMACCClassifier does not swallow exceptions into empty results."""
    mock_llm = AsyncMock()
    mock_llm.predict_structured = AsyncMock(side_effect=RuntimeError("ACC Tokenizer Crash"))

    classifier = LLMACCClassifier(
        llm=mock_llm,
        prompts=Phase4Config().acc_prompts,
    )

    with pytest.raises(RuntimeError, match="ACC Tokenizer Crash"):
        await classifier.classify(
            chunk_id="chunk-1",
            tagged_text="<AC1>Alle Prämissen bedürfen einer Deduktion.</AC1>",
            adu_ids=["AC1"],
            schema=DEFAULT_SCHEMA,
        )


@pytest.mark.asyncio
async def test_phase2_guard_systematic_failure_on_first_batch() -> None:
    """Verify Phase2Runner raises SystematicChunkFailure when first batch fails 100%."""
    chunks = [
        L1Chunk(
            id="chunk-1",
            text="Text eins",
            source_doc_id="doc-1",
            sequence_index=0,
            token_count=2,
        ),
        L1Chunk(
            id="chunk-2",
            text="Text zwei",
            source_doc_id="doc-1",
            sequence_index=1,
            token_count=2,
        ),
    ]

    mock_store = AsyncMock()
    mock_store.get_unprocessed_chunks = AsyncMock(return_value=chunks)
    mock_store.get_processed_chunk_ids = AsyncMock(return_value=[])

    mock_extractor = AsyncMock()
    mock_extractor.extract = AsyncMock(side_effect=RuntimeError("Endpoint 503"))

    runner = Phase2Runner(
        config=Phase2Config(batch_size=2),
        schema=DEFAULT_SCHEMA,
        llm=AsyncMock(),
        graph_store=mock_store,
        ner_extractor=mock_extractor,
    )

    context = ArtifactExecutionContext(
        run_id="run-sys-2",
        manifest=RunManifest(run_id="run-sys-2", dataset_path="dummy"),
        pipeline_input=PipelineInput(source_paths=[]),
    )

    view = Phase1ArtifactsView(documents=[], chunks=chunks)

    with pytest.raises(SystematicChunkFailure, match="All 2 chunks of the first batch failed"):
        await runner.run(view, context)


@pytest.mark.asyncio
async def test_phase4_guard_systematic_failure_on_first_batch() -> None:
    """Verify Phase4Runner raises SystematicChunkFailure when first batch fails 100%."""
    chunks = [
        L1Chunk(
            id="chunk-1",
            text="Text eins",
            source_doc_id="doc-1",
            sequence_index=0,
            token_count=2,
        ),
        L1Chunk(
            id="chunk-2",
            text="Text zwei",
            source_doc_id="doc-1",
            sequence_index=1,
            token_count=2,
        ),
    ]

    mock_store = AsyncMock()
    mock_store.get_theory_atoms = AsyncMock(return_value=[])
    mock_store.get_unprocessed_chunks = AsyncMock(return_value=chunks)
    mock_store.get_processed_chunk_ids = AsyncMock(return_value=[])

    mock_segmenter = AsyncMock()
    mock_segmenter.segment = AsyncMock(side_effect=RuntimeError("Model Quota Exceeded"))

    runner = Phase4Runner(
        config=Phase4Config(batch_size=2),
        schema=DEFAULT_SCHEMA,
        llm=AsyncMock(),
        embedding_model=AsyncMock(),
        graph_store=mock_store,
        adu_segmenter=mock_segmenter,
    )

    context = ArtifactExecutionContext(
        run_id="run-sys-4",
        manifest=RunManifest(run_id="run-sys-4", dataset_path="dummy"),
        pipeline_input=PipelineInput(source_paths=[]),
    )

    view = Phase3ArtifactsView(global_triples=[], relation_type_distribution={}, chunks=chunks)

    with pytest.raises(SystematicChunkFailure, match="All 2 chunks of the first batch failed"):
        await runner.run(view, context)


@pytest.mark.asyncio
async def test_phase2_marks_zero_entity_chunks_processed() -> None:
    """Verify Phase2Runner marks chunks with 0 entities as processed when extraction succeeds."""
    chunk = L1Chunk(
        id="chunk-empty",
        text="Inhaltsverzeichnis des Werkes.",
        source_doc_id="doc-1",
        sequence_index=0,
        token_count=3,
    )

    mock_store = AsyncMock()
    mock_store.get_unprocessed_chunks = AsyncMock(return_value=[chunk])
    mock_store.get_processed_chunk_ids = AsyncMock(return_value=[])

    mock_extractor = AsyncMock()
    # Legitimate non-argumentative or empty chunk returns 0 entities and 0 triples without exception
    mock_extractor.extract = AsyncMock(return_value=([], [], None, False, None))

    runner = Phase2Runner(
        config=Phase2Config(batch_size=10),
        schema=DEFAULT_SCHEMA,
        llm=AsyncMock(),
        graph_store=mock_store,
        ner_extractor=mock_extractor,
    )

    context = ArtifactExecutionContext(
        run_id="run-zero-ent",
        manifest=RunManifest(run_id="run-zero-ent", dataset_path="dummy"),
        pipeline_input=PipelineInput(source_paths=[]),
    )

    view = Phase1ArtifactsView(documents=[], chunks=[chunk])
    artifacts = await runner.run(view, context)

    assert len(artifacts) == 0
    # Crucial assertion: mark_chunks_processed was called with ["chunk-empty"]
    mock_store.mark_chunks_processed.assert_called_once_with(["chunk-empty"], "phase2")


def test_phase4_components_discoverable_for_fingerprinting() -> None:
    """Verify Phase4Runner binds adu_segmenter and acc_classifier in __init__ for fingerprinting."""
    runner = Phase4Runner(
        config=Phase4Config(),
        schema=DEFAULT_SCHEMA,
        llm=AsyncMock(),
        embedding_model=AsyncMock(),
        graph_store=AsyncMock(),
    )

    components = runner.components()
    # Both must be discovered as internal strategy components
    assert "adu_segmenter" in components
    assert "acc_classifier" in components
    assert "arc_classifier" in components


def test_phase1_runner_has_no_llm_attribute() -> None:
    """Verify Phase1Runner does not bind self.llm so LLM config changes do not invalidate Phase 1."""
    runner = Phase1Runner(
        config=Phase1Config(),
        llm=AsyncMock(),
        graph_store=AsyncMock(),
    )

    # Architectural rule: no getattr/hasattr. Check __dict__ directly.
    assert "llm" not in runner.__dict__

    # find_components must not find any LLM component on Phase 1
    components = runner.components()
    for name, comp in components.items():
        assert "llm" not in name.lower()


def test_tag_relation_extractor_has_no_embedding_model_attribute() -> None:
    """Verify TAGRelationExtractor does not bind self.embedding_model."""
    extractor = TAGRelationExtractor(
        llm=AsyncMock(),
        embedding_model=AsyncMock(),
    )

    # Check that embedding_model is not stored in __dict__
    assert "embedding_model" not in extractor.__dict__
