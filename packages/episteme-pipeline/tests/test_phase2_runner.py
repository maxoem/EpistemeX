"""
Integration tests for Phase2Runner using mock LLM and InMemoryGraphStore.

These tests verify the runner's orchestration logic: batch processing,
entity linking, graph commit, crash-resilient processing, and output contract.
They do NOT test LLM accuracy — the mock returns fixed structured output.
"""

from __future__ import annotations

import pytest

from episteme_pipeline.artifacts.execution import ArtifactExecutionContext, Phase1ArtifactsView, Phase2ArtifactsView
from episteme_pipeline.config import Phase2Config
from episteme_pipeline.contracts.domain import L1Chunk, L1Document, L2Entity, L2Triple
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase2_entity_discovery.models import (
    ExtractedEntity,
    ExtractedTriple,
    NERExtractionOutput,
)
from episteme_pipeline.protocols.extractors import EntityLinker, NERExtractor
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import SchemaConfig


# ---------------------------------------------------------------------------
# Stub implementations
# ---------------------------------------------------------------------------


class StubNERExtractor(NERExtractor):
    """Returns a fixed extraction result for every chunk."""

    def __init__(self, entities: list[ExtractedEntity], triples: list[ExtractedTriple]) -> None:
        self._result = NERExtractionOutput(entities=entities, triples=triples)

    async def extract(
        self, chunk_id, chunk_text, schema, memory=None, anchor=None
    ) -> tuple[list[L2Entity], list[L2Triple], dict | None, bool, str | None]:
        from episteme_pipeline.phases.phase2_entity_discovery.ner_extractor import _stable_entity_id

        id_map: dict[str, str] = {}
        entities: list[L2Entity] = []
        valid_node_types = set(schema.node_types)

        for ext in self._result.entities:
            if ext.label not in valid_node_types:
                continue
            stable_id = _stable_entity_id(ext.label, ext.name)
            id_map[ext.id] = stable_id
            entities.append(
                L2Entity(id=stable_id, label=ext.label, name=ext.name, source_chunk_ids=[chunk_id])
            )

        triples: list[L2Triple] = []
        valid_rel_types = set(schema.relation_types)
        for t in self._result.triples:
            if t.predicate not in valid_rel_types:
                continue
            subj = id_map.get(t.subject_id)
            obj = id_map.get(t.object_id)
            if subj and obj:
                triples.append(
                    L2Triple(
                        subject_id=subj, predicate=t.predicate, object_id=obj,
                        confidence=t.confidence, scope="local", source_chunk_id=chunk_id,
                    )
                )

        wm = self._result.working_memory
        memory_update = wm.state_delta if wm else None
        boundary_detected = wm.boundary_detected if wm else False
        transitional_summary = wm.transitional_summary if wm else None
        return entities, triples, memory_update, boundary_detected, transitional_summary


class StubEntityLinker(EntityLinker):
    """Never links — always mints new entities."""

    async def link(self, mention, graph_store, top_k=10, threshold=0.85) -> L2Entity | None:
        return None


class StubLinkingEntityLinker(EntityLinker):
    """Always links to a fixed canonical entity."""

    def __init__(self, canonical: L2Entity) -> None:
        self.canonical = canonical

    async def link(self, mention, graph_store, top_k=10, threshold=0.85) -> L2Entity | None:
        return self.canonical


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def schema() -> SchemaConfig:
    return SchemaConfig(
        node_types=["PERSON", "KONZEPT", "Person", "Concept"],
        relation_types=["IMPLIZIERT", "IMPLIES"],
    )


@pytest.fixture
def two_chunks() -> list[L1Chunk]:
    return [
        L1Chunk(id="chunk_0001", text="Kant discussed space.", source_doc_id="doc1", sequence_index=0, token_count=4),
        L1Chunk(id="chunk_0002", text="Hegel followed Kant.", source_doc_id="doc1", sequence_index=1, token_count=4),
    ]


@pytest.fixture
def phase1_view(two_chunks) -> Phase1ArtifactsView:
    from datetime import datetime, timezone

    document = L1Document(
        id="doc1",
        title="Test",
        source_path="test.tex",
        ingested_at=datetime.now(timezone.utc),
        chapter_count=1,
        chunk_count=2,
    )
    return Phase1ArtifactsView(documents=[document], chunks=two_chunks)


def make_context() -> ArtifactExecutionContext:
    return ArtifactExecutionContext(
        run_id="run-test",
        manifest=RunManifest(run_id="run-test"),
        pipeline_input=PipelineInput(source_paths=[]),
        previous=None,
    )


def make_runner(graph_store, ner_extractor=None, entity_linker=None, schema=None):
    config = Phase2Config(batch_size=10)
    schema = schema or SchemaConfig(
        node_types=["PERSON", "KONZEPT", "Person", "Concept"],
        relation_types=["IMPLIZIERT", "IMPLIES"],
    )
    return Phase2Runner(
        config=config,
        schema=schema,
        llm=None,
        embedding_model=None,
        graph_store=graph_store,
        ner_extractor=ner_extractor or StubNERExtractor([], []),
        entity_linker=entity_linker or StubEntityLinker(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_returns_phase2_artifact_collection(graph_store, phase1_view):
    runner = make_runner(graph_store)
    result = await runner.run(phase1_view, make_context())
    view = Phase2ArtifactsView.from_collection(result)
    assert isinstance(view, Phase2ArtifactsView)


@pytest.mark.asyncio
async def test_run_extracts_entities_and_commits_to_graph(graph_store, phase1_view, schema):
    extracted = [
        ExtractedEntity(id="e1", label="PERSON", name="Kant", mention_quote="Kant"),
    ]
    runner = make_runner(graph_store, ner_extractor=StubNERExtractor(extracted, []), schema=schema)
    result = await runner.run(phase1_view, make_context())
    view = Phase2ArtifactsView.from_collection(result)

    assert len(view.entities) > 0
    assert any(e.name == "Kant" for e in view.entities)
    entities_in_graph = await graph_store.get_entities()
    assert any(e.name == "Kant" for e in entities_in_graph)


@pytest.mark.asyncio
async def test_run_marks_chunks_as_processed(graph_store, phase1_view, two_chunks, schema):
    # With non-empty extraction, chunks are marked processed
    for chunk in two_chunks:
        await graph_store.upsert_chunk(chunk)
    extracted = [ExtractedEntity(id="e1", label="PERSON", name="Kant", mention_quote="Kant")]
    runner = make_runner(graph_store, ner_extractor=StubNERExtractor(extracted, []), schema=schema)
    await runner.run(phase1_view, make_context())

    for chunk in two_chunks:
        unprocessed = await graph_store.get_unprocessed_chunks("phase2")
        assert chunk not in unprocessed


@pytest.mark.asyncio
async def test_run_resumes_from_graph_unprocessed_chunks(graph_store, phase1_view, two_chunks):
    # Pre-populate graph with chunks; mark first as already processed
    for chunk in two_chunks:
        await graph_store.upsert_chunk(chunk)
    await graph_store.mark_chunk_processed(two_chunks[0].id, "phase2")

    extracted = [ExtractedEntity(id="e1", label="PERSON", name="ResumedEntity", mention_quote="X")]
    runner = make_runner(graph_store, ner_extractor=StubNERExtractor(extracted, []))
    result = await runner.run(phase1_view, make_context())
    view = Phase2ArtifactsView.from_collection(result)

    # Only one chunk was unprocessed, so only one chunk's entities are extracted
    assert len(view.entities) == 1


@pytest.mark.asyncio
async def test_run_fallback_does_not_treat_all_graph_chunks_as_processed(
    graph_store, phase1_view, two_chunks
):
    """Fallback path should process chunks not explicitly marked as done."""
    for chunk in two_chunks:
        await graph_store.upsert_chunk(chunk)

    await graph_store.mark_chunk_processed(two_chunks[0].id, "phase2")

    original_get_unprocessed = graph_store.get_unprocessed_chunks
    original_get_chunks = graph_store.get_chunks

    async def return_empty(*args, **kwargs):
        return []

    async def return_processed(filters=None, limit=None):
        if filters == {"phase2_processed": True}:
            return [two_chunks[0]]
        return await original_get_chunks(filters=filters, limit=limit)

    graph_store.get_unprocessed_chunks = return_empty  # type: ignore[method-assign]
    graph_store.get_chunks = return_processed  # type: ignore[method-assign]
    try:
        extracted = [
            ExtractedEntity(id="e1", label="PERSON", name="RecoveredEntity", mention_quote="RecoveredEntity")
        ]
        runner = make_runner(graph_store, ner_extractor=StubNERExtractor(extracted, []))
        result = await runner.run(phase1_view, make_context())
    finally:
        graph_store.get_unprocessed_chunks = original_get_unprocessed  # type: ignore[method-assign]
        graph_store.get_chunks = original_get_chunks  # type: ignore[method-assign]

    view = Phase2ArtifactsView.from_collection(result)
    assert len(view.entities) == 1


@pytest.mark.asyncio
async def test_entity_linking_redirects_id_in_triples(graph_store, phase1_view, schema):
    canonical = L2Entity(id="canonical_kant", label="PERSON", name="Immanuel Kant")
    await graph_store.upsert_entity(canonical)

    extracted_entities = [
        ExtractedEntity(id="e1", label="PERSON", name="Kant", mention_quote="Kant"),
        ExtractedEntity(id="e2", label="KONZEPT", name="space", mention_quote="space"),
    ]
    extracted_triples = [
        ExtractedTriple(subject_id="e1", predicate="IMPLIZIERT", object_id="e2", confidence=0.9),
    ]

    linker = StubLinkingEntityLinker(canonical)
    runner = make_runner(
        graph_store,
        ner_extractor=StubNERExtractor(extracted_entities, extracted_triples),
        entity_linker=linker,
        schema=schema,
    )
    result = await runner.run(phase1_view, make_context())
    view = Phase2ArtifactsView.from_collection(result)

    # All triples with Kant as subject should use the canonical ID
    for triple in view.local_triples:
        if triple.predicate == "IMPLIZIERT":
            assert triple.subject_id == canonical.id


@pytest.mark.asyncio
async def test_entity_count_by_type_is_correct(graph_store, phase1_view, schema):
    extracted = [
        ExtractedEntity(id="e1", label="PERSON", name="Kant", mention_quote="Kant"),
        ExtractedEntity(id="e2", label="PERSON", name="Hegel", mention_quote="Hegel"),
        ExtractedEntity(id="e3", label="KONZEPT", name="space", mention_quote="space"),
    ]
    runner = make_runner(graph_store, ner_extractor=StubNERExtractor(extracted, []), schema=schema)
    result = await runner.run(phase1_view, make_context())
    view = Phase2ArtifactsView.from_collection(result)

    # Each chunk processes the same 3 entities (2 chunks total)
    assert view.entity_count_by_type.get("PERSON", 0) >= 2
    assert view.entity_count_by_type.get("KONZEPT", 0) >= 1


@pytest.mark.asyncio
async def test_unknown_entity_labels_are_dropped(graph_store, phase1_view, schema):
    extracted = [
        ExtractedEntity(id="e1", label="UNKNOWN_TYPE", name="Thing", mention_quote="Thing"),
    ]
    runner = make_runner(graph_store, ner_extractor=StubNERExtractor(extracted, []), schema=schema)
    result = await runner.run(phase1_view, make_context())
    view = Phase2ArtifactsView.from_collection(result)
    assert view.entities == []


@pytest.mark.asyncio
async def test_empty_extraction_leaves_chunks_unprocessed(graph_store, phase1_view, two_chunks):
    # With empty extraction, chunks remain unprocessed for retry
    runner = make_runner(graph_store, ner_extractor=StubNERExtractor([], []))
    for chunk in two_chunks:
        await graph_store.upsert_chunk(chunk)
    await runner.run(phase1_view, make_context())
    unprocessed = await graph_store.get_unprocessed_chunks("phase2")
    assert sorted([c.id for c in unprocessed]) == sorted([c.id for c in two_chunks])
