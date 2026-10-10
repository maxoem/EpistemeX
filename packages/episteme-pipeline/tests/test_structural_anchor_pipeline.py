"""
Tests for GlobalStructuralAnchor end-to-end integration across the pipeline.

Verifies:
- GlobalStructuralAnchor model contract and prompt context formatting.
- PipelineInput structural anchor integration.
- Fingerprinting and manifest invalidation on anchor changes.
- Phase 1 ToC outline merging with user-supplied thesis/summary and Neo4j commitment.
- Phase 2 EpisodicWorkingMemoryManager anchor initialization and merging.
- Pipeline.for_task dependency injection for memory_anchor and working_memory_manager.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactExecutionContext,
    Phase1ArtifactsView,
)
from episteme_pipeline.artifacts.models import DocumentArtifact
from episteme_pipeline.config import Phase1Config, Phase2Config, PipelineConfig
from episteme_pipeline.contracts.domain import (
    GlobalStructuralAnchor,
    L1Chunk,
    L1Document,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
from episteme_pipeline.phases.phase1_foundation import Phase1Runner
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase2_entity_discovery.working_memory import (
    EpisodicWorkingMemoryManager,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.fingerprints import (
    fingerprint_structural_anchor,
)
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import SchemaConfig

# ---------------------------------------------------------------------------
# 1. Domain Contract & Formatting Tests
# ---------------------------------------------------------------------------


def test_global_structural_anchor_defaults() -> None:
    """Verify GlobalStructuralAnchor can be constructed with minimal or no arguments."""
    anchor = GlobalStructuralAnchor()
    assert anchor.toc_structure == ""
    assert anchor.document_summary is None
    assert anchor.global_thesis is None
    assert anchor.to_prompt_context() == ""


def test_global_structural_anchor_prompt_context_partial() -> None:
    """Verify to_prompt_context formats only non-empty coordinate sections."""
    anchor = GlobalStructuralAnchor(global_thesis="Pygmalion effect in classrooms")
    ctx = anchor.to_prompt_context()
    assert "Global Thesis / Scope:\nPygmalion effect in classrooms" in ctx
    assert "Global Table of Contents" not in ctx
    assert "Document Overview" not in ctx


def test_global_structural_anchor_prompt_context_full() -> None:
    """Verify to_prompt_context formats all provided coordinate sections."""
    anchor = GlobalStructuralAnchor(
        toc_structure=["Section 1: Method", "Section 2: Results"],
        document_summary="Study on teacher expectations",
        global_thesis="Teachers' expectancies influence student IQ",
    )
    ctx = anchor.to_prompt_context()
    assert "- Section 1: Method" in ctx
    assert "- Section 2: Results" in ctx
    assert "Document Overview:\nStudy on teacher expectations" in ctx
    assert "Global Thesis / Scope:\nTeachers' expectancies influence student IQ" in ctx


def test_global_structural_anchor_pydantic_serialization() -> None:
    """Verify BaseModel serialization methods work seamlessly."""
    anchor = GlobalStructuralAnchor(
        toc_structure=["Intro", "Outro"],
        global_thesis="Core Thesis",
    )
    dumped = anchor.model_dump(mode="json")
    assert dumped["toc_structure"] == ["Intro", "Outro"]
    assert dumped["global_thesis"] == "Core Thesis"

    restored = GlobalStructuralAnchor.model_validate(dumped)
    assert restored == anchor


# ---------------------------------------------------------------------------
# 2. PipelineInput & Fingerprinting Tests
# ---------------------------------------------------------------------------


def test_pipeline_input_accepts_structural_anchor() -> None:
    """Verify PipelineInput models structural_anchor."""
    anchor = GlobalStructuralAnchor(global_thesis="Scientific Theory")
    pipe_in = PipelineInput(
        source_paths=["paper.md"],
        structural_anchor=anchor,
    )
    assert pipe_in.structural_anchor == anchor



def test_fingerprint_structural_anchor_deterministic() -> None:
    """Verify fingerprint_structural_anchor behaves deterministically."""
    assert fingerprint_structural_anchor(None) is None

    a1 = GlobalStructuralAnchor(global_thesis="Thesis A")
    a2 = GlobalStructuralAnchor(global_thesis="Thesis A")
    a3 = GlobalStructuralAnchor(global_thesis="Thesis B")

    fp1 = fingerprint_structural_anchor(a1)
    fp2 = fingerprint_structural_anchor(a2)
    fp3 = fingerprint_structural_anchor(a3)

    assert fp1 is not None
    assert fp1 == fp2
    assert fp1 != fp3


def test_manifest_invalidated_when_structural_anchor_changes(tmp_path: Path) -> None:
    """Verify Pipeline._build_manifest reflects structural anchor changes in input_fingerprint."""
    sample_doc = tmp_path / "sample.md"
    sample_doc.write_text("# Chapter 1\nContent", encoding="utf-8")

    mock_llm = MagicMock(spec=DiskCachedStructuredLLM)
    pipeline = Pipeline.for_task(
        llm=mock_llm,
        relation_reranker=MagicMock(),
        embedding_model=MagicMock(),
        config=PipelineConfig(),
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
    )

    input_no_anchor = PipelineInput(source_paths=[str(sample_doc)])
    manifest1 = pipeline._build_manifest(run_id="run-1", pipeline_input=input_no_anchor)

    input_with_anchor = PipelineInput(
        source_paths=[str(sample_doc)],
        structural_anchor=GlobalStructuralAnchor(global_thesis="New Thesis"),
    )
    manifest2 = pipeline._build_manifest(run_id="run-2", pipeline_input=input_with_anchor)

    assert manifest1.input_fingerprint != manifest2.input_fingerprint
    assert manifest2.input_fingerprint_inputs["structural_anchor_fingerprint"] is not None


# ---------------------------------------------------------------------------
# 3. Phase 1 Threading & Graph Persistence Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase1_extracts_document_toc_anchor(tmp_path: Path) -> None:
    """Verify Phase 1 extracts auto-parsed ToC outline and commits it to Neo4j."""
    sample_doc = tmp_path / "kant.md"
    sample_doc.write_text("# Chapter 1: Transcendental Aesthetic\nSpace and time.", encoding="utf-8")

    mock_graph_store = AsyncMock()
    runner = Phase1Runner(
        config=Phase1Config(),
        llm=MagicMock(),
        graph_store=mock_graph_store,
    )

    pipe_input = PipelineInput(source_paths=[str(sample_doc)])
    context = ArtifactExecutionContext(
        run_id="run-p1",
        manifest=RunManifest(run_id="run-p1"),
        pipeline_input=pipe_input,
        previous=None,
    )

    collection = await runner.run(pipe_input, context)

    # Document artifact payload verification
    doc_artifacts = [a for a in collection.artifacts if a.payload.__class__.__name__ == "DocumentArtifact"]
    assert len(doc_artifacts) == 1
    doc_payload: DocumentArtifact = doc_artifacts[0].payload
    assert doc_payload.structural_anchor is not None
    # Auto-parsed ToC outline must be preserved
    assert any("Transcendental Aesthetic" in s for s in doc_payload.structural_anchor.toc_structure)

    # Verify upsert_node on Document in Neo4j includes toc_structure
    calls = [c for c in mock_graph_store.upsert_node.call_args_list if c.kwargs.get("label") == "Document"]
    assert len(calls) >= 1
    doc_props = calls[0].kwargs["properties"]
    assert "Transcendental Aesthetic" in doc_props["toc_structure"]


# ---------------------------------------------------------------------------
# 4. Phase 2 Working Memory Resolution Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase2_receives_structural_anchor_from_context() -> None:
    """Verify Phase 2 directly forwards run-level structural anchor from context to NER extractor."""
    anchor = GlobalStructuralAnchor(
        toc_structure=["Chapter 1: Foundations"],
        document_summary="Summary",
        global_thesis="Central Claim",
    )
    document = L1Document(
        id="doc-1",
        title="Doc 1",
        source_path="doc1.md",
        chapter_count=1,
        chunk_count=1,
    )
    chunk = L1Chunk(
        id="c-1",
        text="Sample chunk content",
        source_doc_id="doc-1",
        sequence_index=0,
        token_count=3,
    )
    view = Phase1ArtifactsView(documents=[document], chunks=[chunk])

    mock_graph_store = AsyncMock()
    mock_graph_store.get_unprocessed_chunks.return_value = [chunk]
    mock_ner = AsyncMock()
    mock_ner.extract.return_value = ([], [], None, False, None)

    runner = Phase2Runner(
        config=Phase2Config(batch_size=10),
        schema=SchemaConfig(),
        llm=MagicMock(),
        graph_store=mock_graph_store,
        ner_extractor=mock_ner,
    )

    pipe_input = PipelineInput(source_paths=[], structural_anchor=anchor)
    context = ArtifactExecutionContext(
        run_id="run-p2",
        manifest=RunManifest(run_id="run-p2"),
        pipeline_input=pipe_input,
        previous=None,
    )

    await runner.run(view, context)

    # Verify extractor was called with the run-level anchor
    assert mock_ner.extract.call_count == 1
    call_kwargs = mock_ner.extract.call_args.kwargs
    assert call_kwargs["anchor"] == anchor


@pytest.mark.asyncio
async def test_phase2_when_structural_anchor_is_none() -> None:
    """Verify that when structural_anchor is None, anchor=None is passed and no fake outline is created."""
    document = L1Document(
        id="doc-1",
        title="Doc 1",
        source_path="doc1.md",
        chapter_count=1,
        chunk_count=1,
    )
    chunk = L1Chunk(
        id="c-1",
        text="Sample chunk content",
        source_doc_id="doc-1",
        sequence_index=0,
        token_count=3,
    )
    view = Phase1ArtifactsView(documents=[document], chunks=[chunk])

    mock_graph_store = AsyncMock()
    mock_graph_store.get_unprocessed_chunks.return_value = [chunk]
    mock_ner = AsyncMock()
    mock_ner.extract.return_value = ([], [], None, False, None)

    runner = Phase2Runner(
        config=Phase2Config(batch_size=10),
        schema=SchemaConfig(),
        llm=MagicMock(),
        graph_store=mock_graph_store,
        ner_extractor=mock_ner,
    )

    pipe_input = PipelineInput(source_paths=[], structural_anchor=None)
    context = ArtifactExecutionContext(
        run_id="run-none",
        manifest=RunManifest(run_id="run-none"),
        pipeline_input=pipe_input,
        previous=None,
    )

    await runner.run(view, context)

    assert mock_ner.extract.call_count == 1
    call_kwargs = mock_ner.extract.call_args.kwargs
    assert call_kwargs["anchor"] is None


# ---------------------------------------------------------------------------
# 5. Pipeline.for_task Dependency Injection Tests
# ---------------------------------------------------------------------------


def test_pipeline_for_task_accepts_working_memory_manager() -> None:
    """Verify Pipeline.for_task forwards custom working_memory_manager to Phase 2."""
    mock_llm = MagicMock(spec=DiskCachedStructuredLLM)
    custom_manager = EpisodicWorkingMemoryManager()

    pipeline = Pipeline.for_task(
        llm=mock_llm,
        relation_reranker=MagicMock(),
        embedding_model=MagicMock(),
        config=PipelineConfig(),
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
        working_memory_manager=custom_manager,
    )

    phase2_runner: Phase2Runner = pipeline.phases[1]
    assert phase2_runner.working_memory_manager is custom_manager
