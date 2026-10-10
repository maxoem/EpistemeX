"""Unit tests for Neo4j to epistemetrics adapter."""

from unittest.mock import AsyncMock

import pytest

import epistemetrics as em
from episteme_pipeline.contracts.domain import L2Entity, L2Triple, TheoryAtom, TheoryRelation
from episteme_pipeline.evaluation.benchmarks.neo4j_to_epistemetrics import export_neo4j_to_theory_graph


class TestNeo4jToEpistemetricsAdapter:
    """Test suite for converting Neo4j data structures to epistemetrics TheoryGraph."""

    @pytest.mark.asyncio
    async def test_export_neo4j_to_theory_graph(self):
        mock_reader = AsyncMock()
        mock_reader.get_entities.return_value = [
            L2Entity(id="e1", label="Axiom", name="Newton's First Law", description="Inertia"),
            L2Entity(id="e2", label="Phenomenon", name="Uniform Motion"),
        ]
        mock_reader.get_all_entity_triples.return_value = [
            L2Triple(subject_id="e1", predicate="EXPLAINS", object_id="e2", confidence=0.95, scope="global"),
        ]
        mock_reader.get_theory_atoms.return_value = [
            TheoryAtom(id="a1", text="Bodies remain in uniform motion unless acted upon.", component_type="Claim", source_chunk_id="chunk1"),
            TheoryAtom(id="a2", text="Empirical verification via frictionless planes.", component_type="Evidence", source_chunk_id="chunk1"),
        ]
        mock_reader.get_all_theory_relations.return_value = [
            TheoryRelation(source_id="a2", target_id="a1", relation_type="SUPPORTS", confidence=0.9, scope="local"),
        ]

        tg = await export_neo4j_to_theory_graph(mock_reader, name="TestExportedGraph")

        assert isinstance(tg, em.TheoryGraph)
        assert tg.name == "TestExportedGraph"
        assert tg.num_nodes == 4
        assert tg.num_edges == 2

        # Check L2 mappings
        e1_node = tg.get_node("e1")
        assert e1_node is not None
        assert e1_node.type == em.NodeType.AXIOM
        assert e1_node.epistemic_status == em.EpistemicStatus.HARD_CORE

        # Check L3 mappings
        a1_node = tg.get_node("a1")
        assert a1_node is not None
        assert a1_node.type == em.NodeType.CLAIM

        # Check that metrics run on exported graph
        report = em.analyze_theory_graph(tg)
        assert isinstance(report, em.EpistemicReport)
        assert report.num_nodes == 4
        assert report.num_edges == 2
