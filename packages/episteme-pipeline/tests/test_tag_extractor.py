"""Tests for TAGRelationExtractor candidate pair logic (pure Python, no LLM)."""

import pytest
from episteme_pipeline.config import Phase3Config
from episteme_pipeline.contracts.domain import L2Entity, L2Triple, SubGraph
from episteme_pipeline.phases.phase3_global_relations.tag_extractor import (
    TAGRelationExtractor,
)
from episteme_pipeline.utils import format_envelope


def make_entity(
    eid: str,
    label: str = "PERSON",
    name: str | None = None,
    chunks: list[str] | None = None,
) -> L2Entity:
    return L2Entity(
        id=eid,
        label=label,
        name=name or eid,
        source_chunk_ids=chunks or [],
    )


@pytest.fixture
def extractor() -> TAGRelationExtractor:
    config = Phase3Config()
    return TAGRelationExtractor(llm=None, embedding_model=None, config=config)


class TestCandidatePairs:
    def test_no_candidates_when_no_shared_chunks(self, extractor):
        entities = [
            make_entity("e1", chunks=["chunk_a"]),
            make_entity("e2", chunks=["chunk_b"]),
        ]
        pairs = extractor._candidate_pairs(entities)
        assert pairs == []

    def test_pair_generated_for_shared_chunk(self, extractor):
        entities = [
            make_entity("e1", chunks=["chunk_a"]),
            make_entity("e2", chunks=["chunk_a"]),
        ]
        pairs = extractor._candidate_pairs(entities)
        assert len(pairs) == 1
        ids = {e_id for a, b in pairs for e_id in (a.id, b.id)}
        assert ids == {"e1", "e2"}

    def test_no_self_pairs(self, extractor):
        entities = [make_entity("e1", chunks=["chunk_a"])]
        pairs = extractor._candidate_pairs(entities)
        assert pairs == []

    def test_no_duplicate_pairs(self, extractor):
        # e1 and e2 share two chunks — should only produce one pair
        entities = [
            make_entity("e1", chunks=["chunk_a", "chunk_b"]),
            make_entity("e2", chunks=["chunk_a", "chunk_b"]),
        ]
        pairs = extractor._candidate_pairs(entities)
        assert len(pairs) == 1

    def test_three_entities_same_chunk_produce_three_pairs(self, extractor):
        entities = [
            make_entity("e1", chunks=["chunk_a"]),
            make_entity("e2", chunks=["chunk_a"]),
            make_entity("e3", chunks=["chunk_a"]),
        ]
        pairs = extractor._candidate_pairs(entities)
        assert len(pairs) == 3

    def test_max_candidates_per_entity_is_respected(self):
        config = Phase3Config(max_candidates_per_entity_pair=2)
        extractor = TAGRelationExtractor(llm=None, embedding_model=None, config=config)
        # Hub entity e_hub shares chunk with 5 others
        entities = [make_entity("e_hub", chunks=["chunk_a"])] + [
            make_entity(f"e{i}", chunks=["chunk_a"]) for i in range(5)
        ]
        pairs = extractor._candidate_pairs(entities)
        # e_hub should be paired with at most max_candidates_per_entity_pair=2 entities
        hub_pair_count = sum(1 for a, b in pairs if a.id == "e_hub" or b.id == "e_hub")
        assert hub_pair_count <= 2

    def test_entities_with_no_chunks_produce_no_pairs(self, extractor):
        entities = [make_entity("e1", chunks=[]), make_entity("e2", chunks=[])]
        pairs = extractor._candidate_pairs(entities)
        assert pairs == []


class TestFormatEnvelope:
    def test_empty_envelopes_return_fallback(self):
        env_a = SubGraph(center_id="e1", nodes=[], triples=[], depth=2)
        env_b = SubGraph(center_id="e2", nodes=[], triples=[], depth=2)
        result = format_envelope(env_a, env_b)
        assert "No graph context" in result

    def test_nodes_included_in_output(self):
        node = L2Entity(id="n1", label="PERSON", name="Kant", description="Philosopher")
        env_a = SubGraph(center_id="e1", nodes=[node], triples=[], depth=1)
        env_b = SubGraph(center_id="e2", nodes=[], triples=[], depth=1)
        result = format_envelope(env_a, env_b)
        assert "Kant" in result
        assert "PERSON" in result

    def test_triples_included_in_output(self):
        triple = L2Triple(
            subject_id="e1",
            predicate="IMPLIZIERT",
            object_id="e2",
            confidence=0.9,
            scope="global",
            source_chunk_id="chunk_x",
        )
        env_a = SubGraph(center_id="e1", nodes=[], triples=[triple], depth=1)
        env_b = SubGraph(center_id="e2", nodes=[], triples=[], depth=1)
        result = format_envelope(env_a, env_b)
        assert "IMPLIZIERT" in result

    def test_deduplicates_nodes_from_both_envelopes(self):
        node = L2Entity(id="shared", label="KONZEPT", name="space")
        env_a = SubGraph(center_id="e1", nodes=[node], triples=[], depth=1)
        env_b = SubGraph(center_id="e2", nodes=[node], triples=[], depth=1)
        result = format_envelope(env_a, env_b)
        # "space" should appear only once in the node list
        assert result.count("space") == 1

    def test_include_description_flag(self):
        node = L2Entity(id="n1", label="PERSON", name="Kant", description="Philosopher")
        env_a = SubGraph(center_id="e1", nodes=[node], triples=[], depth=1)
        env_b = SubGraph(center_id="e2", nodes=[], triples=[], depth=1)
        with_desc = format_envelope(env_a, env_b, include_description=True)
        without_desc = format_envelope(env_a, env_b, include_description=False)
        assert "Philosopher" in with_desc
        assert "Philosopher" not in without_desc
