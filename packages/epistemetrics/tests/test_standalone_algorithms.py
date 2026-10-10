"""
Tests for standalone modular algorithm functions.
"""

from __future__ import annotations

import networkx as nx
import pytest

from epistemetrics.graph.algorithms.betweenness import betweenness_centrality, networkx_betweenness
from epistemetrics.graph.algorithms.eigenvector import eigenvector_centrality, networkx_eigenvector
from epistemetrics.graph.algorithms.louvain import louvain_communities, networkx_louvain
from epistemetrics.graph.algorithms.pagerank import networkx_pagerank, page_rank
from epistemetrics.graph.algorithms.wcc import networkx_wcc, weakly_connected_components


@pytest.fixture
def sample_graph() -> nx.DiGraph:
    """Sample test graph."""
    g = nx.DiGraph()
    g.add_edges_from([
        ("A", "B"),
        ("B", "C"),
        ("C", "A"),
        ("B", "D"),
    ])
    return g


def test_standalone_pagerank(sample_graph: nx.DiGraph) -> None:
    """Test standalone page_rank function."""
    res_direct = networkx_pagerank(sample_graph)
    res_adaptive = page_rank(sample_graph)

    assert res_direct.scores == res_adaptive.scores
    assert res_adaptive.algorithm == "pagerank"
    assert res_adaptive.backend == "networkx"
    assert "A" in res_adaptive


def test_standalone_betweenness(sample_graph: nx.DiGraph) -> None:
    """Test standalone betweenness_centrality function."""
    res_direct = networkx_betweenness(sample_graph)
    res_adaptive = betweenness_centrality(sample_graph)

    assert res_direct.scores == res_adaptive.scores
    assert res_adaptive.algorithm == "betweenness"
    assert "B" in res_adaptive


def test_standalone_eigenvector(sample_graph: nx.DiGraph) -> None:
    """Test standalone eigenvector_centrality function."""
    res_direct = networkx_eigenvector(sample_graph)
    res_adaptive = eigenvector_centrality(sample_graph)

    assert res_direct.scores == res_adaptive.scores
    assert res_adaptive.algorithm == "eigenvector"


def test_standalone_wcc(sample_graph: nx.DiGraph) -> None:
    """Test standalone weakly_connected_components function."""
    res_direct = networkx_wcc(sample_graph)
    res_adaptive = weakly_connected_components(sample_graph)

    assert res_direct.num_partitions == res_adaptive.num_partitions
    assert res_adaptive.num_partitions == 1
    assert res_adaptive.partition_of("A") == res_adaptive.partition_of("D")


def test_standalone_louvain(sample_graph: nx.DiGraph) -> None:
    """Test standalone louvain_communities function."""
    res_direct = networkx_louvain(sample_graph, seed=42)
    res_adaptive = louvain_communities(sample_graph, seed=42)

    assert res_direct.num_partitions == res_adaptive.num_partitions
    assert res_adaptive.algorithm == "louvain"
