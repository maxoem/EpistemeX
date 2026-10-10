"""
Integration tests for `Phase3Runner` and `TAGRelationExtractor`.

These tests validate artifact-native Phase 3 execution: candidate filtering,
schema validation, graph commits, and emitted global-relation artifacts.
"""

from __future__ import annotations

import pytest

from episteme_pipeline.artifacts.execution import ArtifactExecutionContext, Phase2ArtifactsView
from episteme_pipeline.config import Phase3Config
from episteme_pipeline.contracts.phase_contracts import (
    L2Entity,
    L2Triple,
    SubGraph,
    PipelineInput,
    CandidatePair,
    PhaseItemRecord,
)
from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
from episteme_pipeline.phases.phase3_global_relations.models import GlobalRelationOutput
from episteme_pipeline.phases.phase3_global_relations.tag_extractor import TAGRelationExtractor
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import SchemaConfig


class StubGlobalExtractor(GlobalRelationExtractor):
    def __init__(self, triples: list[L2Triple]) -> None:
        self._triples = triples

    async def extract_pair(
        self, pair: CandidatePair, graph_store: GraphReader, schema: SchemaConfig
    ) -> L2Triple | None:
        for t in self._triples:
            if {t.subject_id, t.object_id} == {pair.entity_a.id, pair.entity_b.id}:
                return t
        return None

    async def extract(self, entities, graph_store, schema) -> list[L2Triple]:
        return self._triples

    async def get_structural_neighborhood(self, entity: L2Entity, graph_store: GraphReader, depth: int = 2) -> SubGraph:
        return SubGraph(center_id=entity.id, nodes=[], triples=[], depth=depth)


@pytest.fixture
def schema() -> SchemaConfig:
    return SchemaConfig()


@pytest.fixture
def two_entities() -> list[L2Entity]:
    return [
        L2Entity(
            id="e_kant", label="PERSON", name="Kant", source_chunk_ids=["chunk_a"]
        ),
        L2Entity(
            id="e_space", label="KONZEPT", name="space", source_chunk_ids=["chunk_a"]
        ),
    ]


@pytest.fixture
def phase2_view(two_entities) -> Phase2ArtifactsView:
    return Phase2ArtifactsView(
        entities=two_entities,
        local_triples=[],
        entity_count_by_type={"PERSON": 1, "KONZEPT": 1},
    )


def make_runner(graph_store, schema, extractor=None):
    config = Phase3Config()
    return Phase3Runner(
        config=config,
        schema=schema,
        llm=None,
        embedding_model=None,
        graph_store=graph_store,
        global_extractor=extractor or StubGlobalExtractor([]),
    )


def make_context() -> ArtifactExecutionContext:
    return ArtifactExecutionContext(
        run_id="run-test",
        manifest=RunManifest(run_id="run-test"),
        pipeline_input=PipelineInput(source_paths=[]),
        previous=None,
    )


# ---------------------------------------------------------------------------
# Phase3Runner Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_returns_artifact_collection(graph_store, phase2_view, schema):
    runner = make_runner(graph_store, schema)
    result = await runner.run(phase2_view, make_context())
    assert isinstance(result, Phase2ArtifactsView) or hasattr(
        result, "artifacts"
    )


@pytest.mark.asyncio
async def test_run_commits_extracted_triples_to_graph(graph_store, phase2_view, schema):
    triple = L2Triple(
        subject_id="e_kant",
        predicate="IMPLIZIERT",
        object_id="e_space",
        confidence=0.9,
        scope="global",
        source_chunk_id="chunk_a",
    )
    runner = make_runner(graph_store, schema, extractor=StubGlobalExtractor([triple]))
    for entity in phase2_view.entities:
        await graph_store.upsert_entity(entity)
    await runner.run(phase2_view, make_context())
    committed = await graph_store.get_all_entity_triples()
    assert len(committed) == 1
    assert committed[0].subject_id == "e_kant"
    assert committed[0].predicate == "IMPLIZIERT"
    assert committed[0].object_id == "e_space"


@pytest.mark.asyncio
async def test_run_prefers_graph_entities_over_in_memory(
    graph_store, phase2_view, schema
):
    extra = L2Entity(
        id="e_hegel", label="PERSON", name="Hegel", source_chunk_ids=["chunk_b"]
    )
    await graph_store.upsert_entity(extra)
    for entity in phase2_view.entities:
        await graph_store.upsert_entity(entity)

    captured_entities: list[list[L2Entity]] = []

    class CapturingExtractor(GlobalRelationExtractor):
        async def candidate_pairs(self, entities: list[L2Entity]) -> list[CandidatePair]:
            captured_entities.append(entities)
            return await super().candidate_pairs(entities)

        async def get_structural_neighborhood(self, entity: L2Entity, graph_store: GraphReader, depth: int = 2) -> SubGraph:
            return SubGraph(center_id=entity.id, nodes=[], triples=[], depth=depth)

    runner = make_runner(graph_store, schema, extractor=CapturingExtractor())
    await runner.run(phase2_view, make_context())

    assert len(captured_entities[0]) == 3


@pytest.mark.asyncio
async def test_run_with_fewer_than_two_entities_returns_empty(graph_store, schema):
    runner = make_runner(graph_store, schema)
    result = await runner.run(
        Phase2ArtifactsView(
            entities=[L2Entity(id="e1", label="PERSON", name="Kant")],
            local_triples=[],
            entity_count_by_type={"PERSON": 1},
        ),
        make_context(),
    )
    assert result.artifacts == []


@pytest.mark.asyncio
async def test_run_with_no_entities_returns_empty(graph_store, schema):
    runner = make_runner(graph_store, schema)
    result = await runner.run(
        Phase2ArtifactsView(entities=[], local_triples=[], entity_count_by_type={}),
        make_context(),
    )
    assert result.artifacts == []


class TestTAGCandidatePairsWithSchema:
    @pytest.mark.asyncio
    async def test_schema_validation_drops_unknown_relation(self, graph_store, schema):
        config = Phase3Config(global_relation_confidence_threshold=0.0)

        class BadLLM:
            async def astructured_predict(self, model_class, prompt, **kwargs):
                return GlobalRelationOutput(
                    relation="MADE_UP_RELATION", confidence=0.99, direction="A_to_B"
                )

        extractor = TAGRelationExtractor(llm=BadLLM(), embedding_model=None, config=config)
        runner = Phase3Runner(
            config=config,
            schema=schema,
            llm=None,
            embedding_model=None,
            graph_store=graph_store,
            global_extractor=extractor,
        )
        result = await runner.run(
            Phase2ArtifactsView(
                entities=[
                    L2Entity(
                        id="e1",
                        label="PERSON",
                        name="Kant",
                        source_chunk_ids=["chunk_a"],
                    ),
                    L2Entity(
                        id="e2",
                        label="KONZEPT",
                        name="space",
                        source_chunk_ids=["chunk_a"],
                    ),
                ],
                local_triples=[],
                entity_count_by_type={"PERSON": 1, "KONZEPT": 1},
            ),
            make_context(),
        )
        assert result.artifacts == []


@pytest.mark.asyncio
async def test_candidate_pair_key_order_invariance_and_content_sensitivity():
    e1 = L2Entity(id="e1", label="PERSON", name="Kant", textual_envelope="Envelope A")
    e2 = L2Entity(id="e2", label="KONZEPT", name="Space", textual_envelope="Envelope B")
    p1 = CandidatePair(entity_a=e1, entity_b=e2)
    p2 = CandidatePair(entity_a=e2, entity_b=e1)
    assert p1.key == p2.key

    # Changing envelope changes the key
    e2_mutated = L2Entity(id="e2", label="KONZEPT", name="Space", textual_envelope="Envelope Changed")
    p3 = CandidatePair(entity_a=e1, entity_b=e2_mutated)
    assert p3.key != p1.key


@pytest.mark.asyncio
async def test_phase3_resumes_and_skips_premarked_pairs(graph_store, phase2_view, schema):
    # Pre-mark the only candidate pair as completed
    e_kant, e_space = phase2_view.entities
    pair = CandidatePair(entity_a=e_kant, entity_b=e_space)
    await graph_store.commit_phase_batch(
        "phase3",
        triples=[],
        items=[PhaseItemRecord(key=pair.key, status="completed")],
    )

    extracted_pairs: list[CandidatePair] = []

    class MockExtractor(GlobalRelationExtractor):
        async def extract_pair(self, pair, store, schema):
            extracted_pairs.append(pair)
            return None

    runner = make_runner(graph_store, schema, extractor=MockExtractor())
    result = await runner.run(phase2_view, make_context())

    # Pair was already marked, so extractor is never called
    assert len(extracted_pairs) == 0
    assert result.artifacts == []


@pytest.mark.asyncio
async def test_phase3_atomic_commit_per_batch(graph_store, phase2_view, schema):
    e_kant, e_space = phase2_view.entities
    triple = L2Triple(
        subject_id=e_kant.id,
        predicate="IMPLIZIERT",
        object_id=e_space.id,
        confidence=0.9,
        scope="global",
        source_chunk_id="chunk_a",
    )
    runner = make_runner(graph_store, schema, extractor=StubGlobalExtractor([triple]))
    result = await runner.run(phase2_view, make_context())

    # Check that triple was committed
    committed = await graph_store.get_all_entity_triples()
    assert len(committed) == 1

    # Check that checkpoint item was recorded
    pair = CandidatePair(entity_a=e_kant, entity_b=e_space)
    unprocessed = await graph_store.filter_unprocessed_items([pair.key], "phase3")
    assert len(unprocessed) == 0


@pytest.mark.asyncio
async def test_phase3_poison_pill_quarantine(graph_store, phase2_view, schema):
    e3 = L2Entity(id="e3", label="WERK", name="Kritik", source_chunk_ids=["chunk_a"])
    three_view = Phase2ArtifactsView(
        entities=phase2_view.entities + [e3],
        local_triples=[],
        entity_count_by_type={"PERSON": 1, "KONZEPT": 1, "WERK": 1},
    )

    succeeded_calls = 0

    class SelectiveCrashingExtractor(GlobalRelationExtractor):
        async def extract_pair(self, pair, store, schema):
            nonlocal succeeded_calls
            if "e_kant" in pair.key and "e_space" in pair.key:
                raise ValueError("Poison pill token limit exceeded")
            succeeded_calls += 1
            return None

    runner = make_runner(graph_store, schema, extractor=SelectiveCrashingExtractor())
    result = await runner.run(three_view, make_context())

    # The poison pill pair was quarantined as failed
    pair = CandidatePair(entity_a=phase2_view.entities[0], entity_b=phase2_view.entities[1])
    unprocessed = await graph_store.filter_unprocessed_items([pair.key], "phase3")
    assert len(unprocessed) == 0

    record = graph_store._processed_items["phase3"][pair.key]
    assert record.status == "failed"
    assert "Poison pill" in record.error


@pytest.mark.asyncio
async def test_phase3_systematic_failure_guard(graph_store, phase2_view, schema):
    from episteme_pipeline.phases.phase3_global_relations import SystematicPairFailure

    class AllFailExtractor(GlobalRelationExtractor):
        async def extract_pair(self, pair, store, schema):
            raise RuntimeError("API key invalid")

    runner = make_runner(graph_store, schema, extractor=AllFailExtractor())
    with pytest.raises(SystematicPairFailure, match="All 1 candidate pairs of the first batch failed"):
        await runner.run(phase2_view, make_context())


@pytest.mark.asyncio
async def test_phase3_invalidation_clears_checkpoints(graph_store):
    await graph_store.commit_phase_batch(
        "phase3",
        triples=[],
        items=[PhaseItemRecord(key="pair_1", status="completed")],
    )
    assert len(await graph_store.filter_unprocessed_items(["pair_1"], "phase3")) == 0

    await graph_store.clear_phase_checkpoints("phase3")
    assert len(await graph_store.filter_unprocessed_items(["pair_1"], "phase3")) == 1
