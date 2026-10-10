"""Unit tests for TheoryGraph lifecycle, serialization, and epistemic analysis."""

import epistemetrics as em
import networkx as nx
from epistemetrics.core.models import (
    TheoryEdge,
    TheoryNode,
)


class TestTheoryGraph:
    """Test suite for TheoryGraph operations and analysis."""

    def test_theory_graph_construction_and_accessors(self):
        tg = em.TheoryGraph(name="NewtonianMechanics")
        assert tg.name == "NewtonianMechanics"
        assert tg.num_nodes == 0
        assert tg.num_edges == 0

        # Add nodes
        n1 = tg.add_node(
            "A1",
            name="Newton's Second Law",
            node_type=em.NodeType.AXIOM,
            epistemic_status=em.EpistemicStatus.HARD_CORE,
            description="F = m * a",
            provenance=["chunk-001"],
            attributes={"formalAxiom": "\\sum F = m \\cdot a"},
        )
        assert isinstance(n1, TheoryNode)
        assert n1.type == em.NodeType.AXIOM
        assert n1.epistemic_status == em.EpistemicStatus.HARD_CORE
        assert n1.attributes["formalAxiom"] == "\\sum F = m \\cdot a"

        n2 = tg.add_node(
            "P1",
            name="Planetary Orbits",
            node_type=em.NodeType.PHENOMENON,
            epistemic_status=em.EpistemicStatus.NEUTRAL,
        )
        assert n2.type == em.NodeType.PHENOMENON

        # Add edge
        e1 = tg.add_edge(
            "A1",
            "P1",
            relation_type=em.RelationType.EXPLAINS,
            confidence=0.95,
            weight=1.0,
            attributes={"scope": "global"},
        )
        assert isinstance(e1, TheoryEdge)
        assert e1.type == em.RelationType.EXPLAINS
        assert e1.polarity == 1
        assert e1.attributes["scope"] == "global"

        assert tg.num_nodes == 2
        assert tg.num_edges == 1
        assert tg.has_node("A1")
        assert tg.has_edge("A1", "P1")
        assert not tg.has_edge("P1", "A1")

        # Container protocols
        assert "A1" in tg
        assert tg["A1"].id == "A1"
        assert tg.get_node("A1") is not None
        assert tg.get_node("nonexistent") is None
        assert len(tg.get_edge("A1", "P1")) == 1

    def test_enum_from_str_parsing(self):
        # NodeType parsing
        assert em.NodeType.from_str("AXIOM") == em.NodeType.AXIOM
        assert em.NodeType.from_str("axiom") == em.NodeType.AXIOM
        assert em.NodeType.from_str("PotentialModel") == em.NodeType.POTENTIAL_MODEL
        assert em.NodeType.from_str("actual_model") == em.NodeType.ACTUAL_MODEL
        assert em.NodeType.from_str("PartialPotentialModel") == em.NodeType.PARTIAL_POTENTIAL_MODEL
        assert em.NodeType.from_str("GlobalConstraint") == em.NodeType.CONSTRAINT
        assert em.NodeType.from_str("ParadigmaticApplication") == em.NodeType.PARADIGM
        assert em.NodeType.from_str("unknown_xyz") == em.NodeType.CONCEPT

        # EpistemicStatus parsing
        assert em.EpistemicStatus.from_str("HARD_CORE") == em.EpistemicStatus.HARD_CORE
        assert em.EpistemicStatus.from_str("hard_core") == em.EpistemicStatus.HARD_CORE
        assert em.EpistemicStatus.from_str("ProtectiveBelt") == em.EpistemicStatus.PROTECTIVE_BELT
        assert em.EpistemicStatus.from_str("auxiliary") == em.EpistemicStatus.PROTECTIVE_BELT
        assert em.EpistemicStatus.from_str("unknown_status") == em.EpistemicStatus.NEUTRAL

        # RelationType parsing
        assert em.RelationType.from_str("EXPLAINS") == em.RelationType.EXPLAINS
        assert em.RelationType.from_str("hasActualModel") == em.RelationType.HAS_ACTUAL_MODEL
        assert em.RelationType.from_str("str:hasPotentialModel") == em.RelationType.HAS_POTENTIAL_MODEL
        assert em.RelationType.from_str("specializes") == em.RelationType.SPECIALIZES
        assert em.RelationType.from_str("attacks") == em.RelationType.ATTACKS
        assert em.RelationType.ATTACKS.default_polarity == -1
        assert em.RelationType.SPECIALIZES.default_polarity == 0
        assert em.RelationType.SUPPORTS.default_polarity == 1

    def test_serialization_roundtrip(self):
        tg = em.TheoryGraph(name="RoundtripGraph")
        tg.add_node("u1", name="Law 1", node_type=em.NodeType.AXIOM)
        tg.add_node("u2", name="Obs 1", node_type=em.NodeType.EVIDENCE)
        tg.add_edge("u1", "u2", relation_type=em.RelationType.SUPPORTS)

        data = tg.to_dict()
        assert data["name"] == "RoundtripGraph"
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) == 1

        reconstituted = em.TheoryGraph.from_dict(data)
        assert reconstituted.name == tg.name
        assert reconstituted.num_nodes == tg.num_nodes
        assert reconstituted.num_edges == tg.num_edges
        assert reconstituted.get_node("u1").type == em.NodeType.AXIOM

    def test_networkx_interoperability(self):
        G = nx.MultiDiGraph()
        G.add_node("n1", name="Element A", node_type="potential_model", epistemic_status="hard_core")
        G.add_node("n2", name="Element B", node_type="actual_model", epistemic_status="hard_core")
        G.add_edge("n1", "n2", relation_type="has_actual_model", weight=2.0)

        tg = em.TheoryGraph.from_networkx(G, name="FromNX")
        assert tg.num_nodes == 2
        assert tg.num_edges == 1
        assert tg.get_node("n1").type == em.NodeType.POTENTIAL_MODEL
        assert tg.get_node("n2").type == em.NodeType.ACTUAL_MODEL

        back_to_nx = tg.to_networkx()
        assert isinstance(back_to_nx, nx.MultiDiGraph)
        assert back_to_nx.number_of_nodes() == 2
        assert back_to_nx.number_of_edges() == 1

    def test_analyze_theory_graph_and_report(self):
        tg = em.TheoryGraph(name="SampleTheory")
        tg.add_node("core1", name="Core Law", node_type=em.NodeType.AXIOM, epistemic_status=em.EpistemicStatus.HARD_CORE)
        tg.add_node("aux1", name="Auxiliary Hypothesis", node_type=em.NodeType.HYPOTHESIS, epistemic_status=em.EpistemicStatus.PROTECTIVE_BELT)
        tg.add_node("obs1", name="Observation", node_type=em.NodeType.PHENOMENON)
        tg.add_edge("core1", "aux1", relation_type=em.RelationType.SPECIALIZES)
        tg.add_edge("aux1", "obs1", relation_type=em.RelationType.EXPLAINS)

        report = em.analyze_theory_graph(tg)
        assert isinstance(report, em.EpistemicReport)
        assert report.num_nodes == 3
        assert report.num_edges == 2
        assert report.is_dag is True
        assert report.weakly_connected_components == 1
        assert "axiom" in report.node_type_counts
        assert "hard_core" in report.epistemic_status_counts

        md = report.to_markdown()
        assert "# Epistemic Theory Graph Analysis Report" in md
        assert "**Total Nodes:** 3" in md
        assert "**Total Edges:** 2" in md
