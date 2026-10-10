"""
Tests for Neo4j Graph Data Science (GDS) algorithms engine using mocked Neo4jClient.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from epistemetrics.adapters.neo4j.client import Neo4jClient
from epistemetrics.adapters.neo4j.gds_engine import Neo4jGDSAlgorithmsEngine
from epistemetrics.core.exceptions import GDSNotAvailableError, GDSProjectionError
from epistemetrics.core.models import AlgorithmExecutionMode


@pytest.fixture
def mock_client() -> MagicMock:
    """Provide a mocked Neo4jClient with GDS enabled."""
    client = MagicMock(spec=Neo4jClient)
    client.is_gds_available.return_value = True
    client.check_connectivity.return_value = True
    return client


def test_gds_projection_management(mock_client: MagicMock) -> None:
    """Test GDS project, exists, and drop workflows."""
    engine = Neo4jGDSAlgorithmsEngine(client=mock_client)

    # Mock exists check
    mock_client.execute_query.side_effect = [
        [{"exists": True}],  # has_projection
        [{"graphName": "test_proj", "nodeCount": 10, "relationshipCount": 15}],  # project_graph
        [{"exists": True}],  # temporary_projection check
        [{"graphName": "temp_proj", "nodeCount": 5, "relationshipCount": 5}],  # project
        [{"graphName": "temp_proj"}],  # drop
    ]

    assert engine.has_projection("test_proj") is True

    summary = engine.project_graph("test_proj")
    assert summary["graphName"] == "test_proj"
    assert summary["nodeCount"] == 10

    with engine.temporary_projection("temp_proj") as name:
        assert name == "temp_proj"


def test_gds_pagerank_stream_and_write(mock_client: MagicMock) -> None:
    """Test PageRank execution in STREAM and WRITE modes."""
    engine = Neo4jGDSAlgorithmsEngine(client=mock_client)

    mock_client.execute_query.side_effect = [
        [{"exists": True}],  # has_projection
        [
            {"node_id": "claim_A", "score": 1.25},
            {"node_id": "claim_B", "score": 0.85},
        ],  # stream results
        [{"exists": True}],  # has_projection
        [{"nodePropertiesWritten": 2, "computeMillis": 12}],  # write result
    ]

    # STREAM mode
    res = engine.page_rank("test_proj", mode=AlgorithmExecutionMode.STREAM)
    assert res.algorithm == "pagerank"
    assert res.backend == "neo4j_gds"
    assert len(res) == 2
    assert res["claim_A"] == 1.25
    assert res["claim_B"] == 0.85

    # WRITE mode
    write_res = engine.page_rank("test_proj", mode=AlgorithmExecutionMode.WRITE, write_property="pr")
    assert write_res["nodePropertiesWritten"] == 2


def test_gds_betweenness_stream(mock_client: MagicMock) -> None:
    """Test Betweenness Centrality in STREAM mode with normalization."""
    engine = Neo4jGDSAlgorithmsEngine(client=mock_client)

    mock_client.execute_query.side_effect = [
        [{"exists": True}],
        [
            {"node_id": "A", "score": 4.0},
            {"node_id": "B", "score": 2.0},
            {"node_id": "C", "score": 0.0},
        ],
    ]

    res = engine.betweenness_centrality("test_proj", normalized=True)
    assert res.algorithm == "betweenness"
    assert res.backend == "neo4j_gds"
    assert len(res) == 3
    # With 3 nodes, scale = 2 / ((3-1)*(3-2)) = 2 / 2 = 1.0
    assert res["A"] == 4.0


def test_gds_eigenvector_stream(mock_client: MagicMock) -> None:
    """Test Eigenvector Centrality in STREAM mode."""
    engine = Neo4jGDSAlgorithmsEngine(client=mock_client)

    mock_client.execute_query.side_effect = [
        [{"exists": True}],
        [
            {"node_id": "A", "score": 0.707},
            {"node_id": "B", "score": 0.707},
        ],
    ]

    res = engine.eigenvector_centrality("test_proj")
    assert res.algorithm == "eigenvector"
    assert res.backend == "neo4j_gds"
    assert res["A"] == 0.707


def test_gds_wcc_stream(mock_client: MagicMock) -> None:
    """Test WCC partitioning via GDS."""
    engine = Neo4jGDSAlgorithmsEngine(client=mock_client)

    mock_client.execute_query.side_effect = [
        [{"exists": True}],
        [
            {"node_id": "A", "componentId": 0},
            {"node_id": "B", "componentId": 0},
            {"node_id": "C", "componentId": 1},
        ],
    ]

    res = engine.weakly_connected_components("test_proj")
    assert res.algorithm == "wcc"
    assert res.backend == "neo4j_gds"
    assert res.num_partitions == 2
    assert res.partition_of("A") == res.partition_of("B")
    assert res.partition_of("A") != res.partition_of("C")


def test_gds_louvain_stream(mock_client: MagicMock) -> None:
    """Test Louvain community detection via GDS."""
    engine = Neo4jGDSAlgorithmsEngine(client=mock_client)

    mock_client.execute_query.side_effect = [
        [{"exists": True}],
        [
            {"node_id": "A", "communityId": 10},
            {"node_id": "B", "communityId": 10},
            {"node_id": "C", "communityId": 20},
        ],
    ]

    res = engine.louvain_communities("test_proj")
    assert res.algorithm == "louvain"
    assert res.backend == "neo4j_gds"
    assert res.num_partitions == 2


def test_gds_missing_projection_error(mock_client: MagicMock) -> None:
    """Test that GDSProjectionError is raised when projection is missing."""
    engine = Neo4jGDSAlgorithmsEngine(client=mock_client)
    mock_client.execute_query.return_value = [{"exists": False}]

    with pytest.raises(GDSProjectionError, match="does not exist"):
        engine.page_rank("missing_proj")


def test_gds_not_installed_error() -> None:
    """Test that GDSNotAvailableError is raised when GDS is absent."""
    client = MagicMock(spec=Neo4jClient)
    client.is_gds_available.return_value = False
    client.ensure_gds_available.side_effect = GDSNotAvailableError("GDS not installed")

    engine = Neo4jGDSAlgorithmsEngine(client=client)

    with pytest.raises(GDSNotAvailableError):
        engine.page_rank("some_proj")
