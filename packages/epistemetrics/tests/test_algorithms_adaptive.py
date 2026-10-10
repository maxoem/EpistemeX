"""
Tests for AdaptiveAlgorithmsEngine auto-detection and fallback logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import networkx as nx
import pytest
from epistemetrics.adapters.neo4j.client import Neo4jClient
from epistemetrics.adapters.neo4j.gds_engine import Neo4jGDSAlgorithmsEngine
from epistemetrics.core.models import CentralityResult
from epistemetrics.graph.algorithms.adaptive_engine import AdaptiveAlgorithmsEngine


@pytest.fixture
def sample_graph() -> nx.DiGraph:
    """Sample test graph."""
    g = nx.DiGraph()
    g.add_edges_from([("A", "B"), ("B", "C"), ("C", "A")])
    return g


def test_adaptive_defaults_to_networkx_without_neo4j(sample_graph: nx.DiGraph) -> None:
    """Adaptive engine uses NetworkX when Neo4j engine is omitted."""
    adaptive = AdaptiveAlgorithmsEngine(neo4j_engine=None)
    assert adaptive.backend_name == "adaptive"

    res = adaptive.page_rank(sample_graph)
    assert res.backend == "networkx"
    assert len(res) == 3


def test_adaptive_routes_to_gds_when_available() -> None:
    """Adaptive engine routes execution to GDS when connected and projection exists."""
    client = MagicMock(spec=Neo4jClient)
    client.is_gds_available.return_value = True

    gds_engine = Neo4jGDSAlgorithmsEngine(client=client)
    gds_engine.has_projection = MagicMock(return_value=True)  # type: ignore[assignment]
    gds_engine.page_rank = MagicMock(  # type: ignore[assignment]
        return_value=CentralityResult(scores={"A": 1.0}, algorithm="pagerank", backend="neo4j_gds")
    )

    adaptive = AdaptiveAlgorithmsEngine(neo4j_engine=gds_engine, prefer_neo4j=True)

    res = adaptive.page_rank("projected_graph_name")
    assert res.backend == "neo4j_gds"
    assert res["A"] == 1.0
    gds_engine.page_rank.assert_called_once()


def test_adaptive_fallback_to_networkx_on_gds_error(sample_graph: nx.DiGraph) -> None:
    """Adaptive engine cleanly falls back to NetworkX if GDS raises an exception."""
    client = MagicMock(spec=Neo4jClient)
    client.is_gds_available.return_value = True

    gds_engine = Neo4jGDSAlgorithmsEngine(client=client)
    gds_engine.has_projection = MagicMock(return_value=True)  # type: ignore[assignment]
    gds_engine.page_rank = MagicMock(side_effect=RuntimeError("GDS procedure crashed"))  # type: ignore[assignment]

    adaptive = AdaptiveAlgorithmsEngine(
        neo4j_engine=gds_engine,
        prefer_neo4j=True,
        fallback_to_networkx=True,
    )

    res = adaptive.page_rank(sample_graph)
    # Even though GDS failed, NetworkX smoothly executed and returned valid results
    assert res.backend == "networkx"
    assert len(res) == 3


def test_adaptive_respects_prefer_neo4j_false(sample_graph: nx.DiGraph) -> None:
    """Adaptive engine skips GDS when prefer_neo4j is explicitly False."""
    client = MagicMock(spec=Neo4jClient)
    gds_engine = Neo4jGDSAlgorithmsEngine(client=client)

    adaptive = AdaptiveAlgorithmsEngine(
        neo4j_engine=gds_engine,
        prefer_neo4j=False,
    )

    res = adaptive.page_rank(sample_graph)
    assert res.backend == "networkx"
    client.is_gds_available.assert_not_called()
