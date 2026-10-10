"""
Tests for NetworkX structural graph algorithms engine.
"""

from __future__ import annotations

import networkx as nx
import pytest
from epistemetrics.graph.algorithms.networkx_engine import NetworkXAlgorithmsEngine


@pytest.fixture
def sample_digraph() -> nx.DiGraph:
    """Create a sample directed graph for centrality and component tests."""
    g = nx.DiGraph()
    # Component 1: 0 -> 1 -> 2 -> 0, 1 -> 3
    g.add_edges_from([
        ("0", "1"),
        ("1", "2"),
        ("2", "0"),
        ("1", "3"),
    ])
    # Component 2: 4 -> 5
    g.add_edges_from([
        ("4", "5"),
    ])
    return g


@pytest.fixture
def sample_multigraph() -> nx.MultiDiGraph:
    """Create a sample MultiDiGraph with parallel edges."""
    g = nx.MultiDiGraph()
    g.add_edge("A", "B", key=0, weight=1.0)
    g.add_edge("A", "B", key=1, weight=2.0)
    g.add_edge("B", "C", key=0, weight=1.5)
    g.add_edge("C", "A", key=0, weight=1.0)
    return g


def test_networkx_pagerank(sample_digraph: nx.DiGraph) -> None:
    """Verify PageRank computation on directed graph."""
    engine = NetworkXAlgorithmsEngine()
    result = engine.page_rank(sample_digraph, damping_factor=0.85)

    assert result.algorithm == "pagerank"
    assert result.backend == "networkx"
    assert len(result) == 6
    assert "0" in result
    assert result["1"] > 0.0
    assert result.max_score >= result.min_score
    top = result.top_k(2)
    assert len(top) == 2
    assert top[0][1] >= top[1][1]


def test_networkx_betweenness(sample_digraph: nx.DiGraph) -> None:
    """Verify Betweenness Centrality on directed graph."""
    engine = NetworkXAlgorithmsEngine()
    result = engine.betweenness_centrality(sample_digraph, normalized=True)

    assert result.algorithm == "betweenness"
    assert result.backend == "networkx"
    assert len(result) == 6
    # Node 1 is a bridge to node 3
    assert result["1"] >= 0.0


def test_networkx_eigenvector(sample_digraph: nx.DiGraph) -> None:
    """Verify Eigenvector Centrality computation."""
    engine = NetworkXAlgorithmsEngine()
    result = engine.eigenvector_centrality(sample_digraph)

    assert result.algorithm == "eigenvector"
    assert result.backend == "networkx"
    assert len(result) == 6


def test_networkx_eigenvector_multigraph(sample_multigraph: nx.MultiDiGraph) -> None:
    """Verify Eigenvector Centrality properly converts MultiDiGraph."""
    engine = NetworkXAlgorithmsEngine()
    result = engine.eigenvector_centrality(sample_multigraph)

    assert len(result) == 3
    assert all(score >= 0.0 for score in result.values())


def test_networkx_wcc(sample_digraph: nx.DiGraph) -> None:
    """Verify Weakly Connected Components detection."""
    engine = NetworkXAlgorithmsEngine()
    result = engine.weakly_connected_components(sample_digraph)

    assert result.algorithm == "wcc"
    assert result.backend == "networkx"
    assert result.num_partitions == 2
    # Component 1 has 4 nodes {'0', '1', '2', '3'}
    # Component 2 has 2 nodes {'4', '5'}
    assert result.partition_sizes == [4, 2]
    assert result.partition_of("0") == result.partition_of("3")
    assert result.partition_of("4") == result.partition_of("5")
    assert result.partition_of("0") != result.partition_of("4")


def test_networkx_louvain(sample_digraph: nx.DiGraph) -> None:
    """Verify Louvain Community Detection."""
    engine = NetworkXAlgorithmsEngine()
    result = engine.louvain_communities(sample_digraph, seed=42)

    assert result.algorithm == "louvain"
    assert result.backend == "networkx"
    assert result.num_partitions >= 2
    assert "0" in result.node_to_partition
    assert "5" in result.node_to_partition


def test_networkx_empty_graph() -> None:
    """Verify graceful handling of empty graphs."""
    engine = NetworkXAlgorithmsEngine()
    empty = nx.DiGraph()

    pr = engine.page_rank(empty)
    assert len(pr) == 0

    bet = engine.betweenness_centrality(empty)
    assert len(bet) == 0

    eig = engine.eigenvector_centrality(empty)
    assert len(eig) == 0

    wcc = engine.weakly_connected_components(empty)
    assert wcc.num_partitions == 0

    louv = engine.louvain_communities(empty)
    assert louv.num_partitions == 0
