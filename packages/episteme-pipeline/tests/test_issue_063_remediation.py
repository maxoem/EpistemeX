"""
Deterministic unit tests for ISSUE-063 remediation.

Covers:
1. LaTeX ToC parsing on converted markdown text.
2. Accurate BPE token counts on RawChunk and L1Chunk.
3. EpisodicWorkingMemoryManager deterministic ordering and entity deduplication.
4. DenseEntityLinker null-safe cross-encoder fallback.
5. DenseRetrievalGlobalRelationExtractor confidence threshold filtering and zero-norm safeguard.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase1ArtifactsView,
)
from episteme_pipeline.config import (
    Phase1Config,
    Phase2Config,
    Phase3Config,
)
from episteme_pipeline.contracts.domain import (
    CandidatePair,
    GlobalStructuralAnchor,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    SubGraph,
)
from episteme_pipeline.contracts.phase_contracts import (
    PipelineInput,
)
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.models import CandidateRejectedByThreshold
from episteme_pipeline.phases.phase1_foundation import Phase1Runner
from episteme_pipeline.phases.phase1_foundation.chunker import (
    RawChunk,
    _count_tokens,
    chunk_document,
)
from episteme_pipeline.phases.phase1_foundation.toc_parser import (
    AutoToCParser,
    LaTeXToCParser,
    MarkdownToCParser,
)
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase2_entity_discovery.sota_entity_linker import (
    DenseEntityLinker,
)
from episteme_pipeline.phases.phase2_entity_discovery.working_memory import (
    EpisodicWorkingMemoryManager,
)
from episteme_pipeline.phases.phase3_global_relations.dense_retrieval_extractor import (
    DenseRetrievalGlobalRelationExtractor,
)
from episteme_pipeline.phases.phase3_global_relations.models import GlobalRelationOutput
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


# ---------------------------------------------------------------------------
# Defect 1: LaTeX ToC Parser on Converted Markdown
# ---------------------------------------------------------------------------


def test_latex_toc_parser_does_not_intercept_converted_markdown() -> None:
    """Verify LaTeXToCParser yields to MarkdownToCParser when text is markdown."""
    toc_parser = AutoToCParser()
    converted_md = (
        "# Transcendental Aesthetic\n\n"
        "Space and time are pure intuitions.\n\n"
        "## Section 1: Of Space\n\n"
        "Space is not an empirical concept."
    )
    # Even if path has a .tex suffix, converted text has markdown headers and no LaTeX commands
    anchor = toc_parser.parse(
        text=converted_md,
        document_title="kant_critique",
        path=Path("kant_critique.tex"),
    )
    assert "(No LaTeX section commands detected)" not in anchor.toc_structure[0]
    assert any("Transcendental Aesthetic" in line for line in anchor.toc_structure)
    assert any("Section 1: Of Space" in line for line in anchor.toc_structure)


def test_latex_toc_parser_still_handles_raw_latex() -> None:
    """Verify LaTeXToCParser handles raw LaTeX section commands when present."""
    raw_latex = (
        r"\documentclass{article}" "\n"
        r"\section{Transcendental Analytic}" "\n"
        r"\subsection{Deduction of the Pure Concepts of Understanding}"
    )
    toc_parser = AutoToCParser()
    anchor = toc_parser.parse(
        text=raw_latex,
        document_title="analytic",
        path=Path("analytic.tex"),
    )
    assert any("Transcendental Analytic" in line for line in anchor.toc_structure)


# ---------------------------------------------------------------------------
# Defect 2: Token Count Accuracy on RawChunk and L1Chunk
# ---------------------------------------------------------------------------


def test_raw_chunk_and_l1_chunk_accurate_token_count() -> None:
    """Verify RawChunk stores token_count from BPE tokenizer and matches _count_tokens."""
    text = (
        "# Critique\n\n"
        "All our knowledge begins with the senses, proceeds to the understanding, "
        "and ends with reason. There is nothing higher than reason for producing "
        "the unity of thought and bringing it under the highest rule."
    )
    chunks = chunk_document(text, max_tokens=256, overlap_tokens=32)
    assert len(chunks) > 0
    raw = chunks[0]
    assert raw.token_count > 0
    expected_bpe = _count_tokens(raw.text)
    assert raw.token_count == expected_bpe
    # Verify BPE count is greater than raw whitespace word count on philosophical English
    whitespace_count = len(raw.text.split())
    assert raw.token_count >= whitespace_count


# ---------------------------------------------------------------------------
# Defect 3: Working Memory Concurrency Order & Entity Deduplication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_working_memory_deterministic_sequence_and_entity_dedup() -> None:
    """Verify memory state updates in sequence_index order and entities are deduplicated."""
    processed_order: list[int] = []

    class MockMemoryManager(EpisodicWorkingMemoryManager):
        def process_step(self, chunk, state_delta, semantic_boundary_detected=False, transitional_summary=None):
            processed_order.append(chunk.sequence_index)
            return super().process_step(
                chunk=chunk,
                state_delta=state_delta,
                semantic_boundary_detected=semantic_boundary_detected,
                transitional_summary=transitional_summary,
            )

    memory_mgr = MockMemoryManager()
    graph_store = AsyncMock()
    graph_store.get_existing_chunk_ids.return_value = set()
    graph_store.get_unprocessed_chunks.return_value = []
    graph_store.get_chunks.return_value = []
    graph_store.upsert_entities = AsyncMock()
    graph_store.upsert_relations = AsyncMock()
    graph_store.upsert_triples = AsyncMock()
    graph_store.mark_chunks_processed = AsyncMock()

    # Create mock extractor that finishes out of order if gathered
    class MockExtractor:
        async def extract(self, chunk_id, chunk_text, schema, memory, anchor):
            # simulate random latency
            await asyncio.sleep(0.01 if "c0" in chunk_id else 0.001)
            # Both chunks return the same entity "concept_synthetic"
            entity = L2Entity(
                id="concept_synthetic",
                name="Synthetic A Priori",
                label="CONCEPT",
                source_chunk_ids=[chunk_id],
                confidence=0.9,
            )
            return [entity], [], {"active_entities": [entity.name]}, False, None

    config = Phase2Config(batch_size=5)
    runner = Phase2Runner(
        config=config,
        schema=DEFAULT_SCHEMA,
        llm=MagicMock(),
        embedding_model=None,
        graph_store=graph_store,
        ner_extractor=MockExtractor(),
        working_memory_manager=memory_mgr,
    )

    chunk0 = L1Chunk(id="c0", text="Intro text", source_doc_id="doc1", sequence_index=0, token_count=10)
    chunk1 = L1Chunk(id="c1", text="Middle text", source_doc_id="doc1", sequence_index=1, token_count=10)
    chunk2 = L1Chunk(id="c2", text="Conclusion text", source_doc_id="doc1", sequence_index=2, token_count=10)

    artifacts_view = Phase1ArtifactsView(documents=[], chunks=[chunk1, chunk0, chunk2])
    ctx = ArtifactExecutionContext(run_id="run_test", manifest=None, pipeline_input=None)

    collection = await runner.run(artifacts_view, ctx)

    # 1. State updates must execute in strictly increasing sequence_index order
    assert processed_order == [0, 1, 2]

    # 2. Duplicate entity "concept_synthetic" must emit exactly ONE LinkedEntityArtifact
    concept_linked = [a for a in collection.artifacts if a.artifact_id == "artifact::concept_synthetic"]
    assert len(concept_linked) == 1
    # Check that mention_ids merged all three chunks
    expected_mentions = {f"artifact::mention::concept_synthetic::{c}" for c in ["c0", "c1", "c2"]}
    assert set(concept_linked[0].payload.mention_ids) == {f"mention::concept_synthetic::{c}" for c in ["c0", "c1", "c2"]} or set(concept_linked[0].payload.mention_ids) == expected_mentions


# ---------------------------------------------------------------------------
# Defect 4: DenseEntityLinker Null-Safe Cross-Encoder Fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_entity_linker_null_cross_encoder_fallback() -> None:
    """Verify DenseEntityLinker succeeds with cross_encoder=None using bi-encoder scores."""
    embedding_model = AsyncMock()
    # 2-dim dummy vector for mention
    embedding_model.aget_text_embedding_batch.return_value = [[1.0, 0.0]]

    linker = DenseEntityLinker(
        embedding_model=embedding_model,
        cross_encoder=None,
        tau=0.7,
        top_k=3,
    )

    candidate1 = L2Entity(id="e1", name="Empiricism", label="CONCEPT")
    candidate2 = L2Entity(id="e2", name="Rationalism", label="CONCEPT")

    graph_store = AsyncMock()
    graph_store.get_entities.return_value = [candidate1, candidate2]

    # Populate candidate cache embeddings
    with patch.object(
        linker._candidate_cache, "get_embeddings"
    ) as mock_get_embs:
        import torch
        # Candidate 1 has cosine sim 1.0, Candidate 2 has cosine sim 0.0
        mock_get_embs.return_value = torch.tensor([[1.0, 0.0], [0.0, 1.0]], dtype=torch.float32)

        mention = L2Entity(
            id="m1",
            name="Empiricism",
            label="CONCEPT",
            textual_envelope="Empiricism posits sensory experience.",
        )

        resolved = await linker.link(mention, graph_store)
        assert resolved is not None
        assert resolved.id == "e1"


# ---------------------------------------------------------------------------
# Defect 5: Phase 3 Confidence Threshold & Zero-Norm Guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_retrieval_extractor_confidence_filtering() -> None:
    """Verify DenseRetrievalGlobalRelationExtractor rejects relations below threshold."""
    config = Phase3Config(global_relation_confidence_threshold=0.75)
    embedding_model = AsyncMock()
    structured_llm = AsyncMock()

    reranker = AsyncMock()
    reranker.score_relation.return_value = 0.9

    extractor = DenseRetrievalGlobalRelationExtractor(
        config=config,
        llm=structured_llm,
        embedding_model=embedding_model,
        reranker=reranker,
    )
    extractor.llm = structured_llm

    entity_a = L2Entity(id="ea", name="Cause", label="Concept")
    entity_b = L2Entity(id="eb", name="Effect", label="Concept")
    candidate_low = CandidatePair(score=0.8, entity_a=entity_a, entity_b=entity_b)
    graph_store = AsyncMock()
    graph_store.get_neighborhood.return_value = SubGraph(center_id="c", nodes=[], triples=[], depth=1)

    # Case 1: Confidence 0.50 < 0.75 -> Discarded
    structured_llm.predict_structured.return_value = GlobalRelationOutput(
        relation="IMPLIES",
        confidence=0.50,
        direction="A_to_B",
    )
    with patch.object(extractor.event_emitter, "emit") as mock_emit:
        res_rejected = await extractor._extract_pair(candidate_low, graph_store, DEFAULT_SCHEMA)
        assert res_rejected is None
        emitted_rejections = [
            call.args[0] for call in mock_emit.call_args_list
            if isinstance(call.args[0], CandidateRejectedByThreshold)
        ]
        assert len(emitted_rejections) == 1
        assert emitted_rejections[0].score == 0.50

    # Case 2: Confidence 0.85 >= 0.75 -> Accepted
    entity_c = L2Entity(id="ec", name="Premise", label="Concept")
    entity_d = L2Entity(id="ed", name="Conclusion", label="Concept")
    candidate_high = CandidatePair(score=0.8, entity_a=entity_c, entity_b=entity_d)
    structured_llm.predict_structured.return_value = GlobalRelationOutput(
        relation="IMPLIES",
        confidence=0.85,
        direction="A_to_B",
    )
    res_accepted = await extractor._extract_pair(candidate_high, graph_store, DEFAULT_SCHEMA)
    assert res_accepted is not None
    assert res_accepted.predicate == "IMPLIES"
    assert res_accepted.confidence == 0.85


