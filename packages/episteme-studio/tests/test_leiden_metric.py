"""Tests for Leiden Community Detection Metric, GDS Execution, and igraph Fallback."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from episteme_studio.adapters.metrics_adapter import compute_leiden
from episteme_studio.adapters.neo4j_reader import Neo4jReader
from episteme_studio.app import create_app
from episteme_studio.domain.graph import GraphView, Layer, StudioEdge, StudioNode
from episteme_studio.domain.metrics import MetricScope
from episteme_studio.domain.overlays import OverlayKind
from episteme_studio.services.metric_service import MetricService
from episteme_studio.services.overlay_service import OverlayService
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient


class _MockNeo4jDriver:
    """Mock Neo4j driver tracking executed queries and transactions."""

    def __init__(self, run_handler=None) -> None:
        self.run_handler = run_handler or self._default_run
        self.executed_queries: list[str] = []

    async def _default_run(self, query: str, **params) -> Any:
        return []

    def session(self, database=None, default_access_mode=None) -> Any:
        driver = self

        class _MockTx:
            async def run(self, q: str, **p) -> Any:
                driver.executed_queries.append(q)
                res = driver.run_handler(q, **p)
                if asyncio.iscoroutine(res):
                    res = await res

                class _MockRes:
                    def keys(self) -> list[str]:
                        if res and isinstance(res, list) and isinstance(res[0], dict):
                            return list(res[0].keys())
                        return ["version"]

                    def __aiter__(self):
                        self._iter = iter(res or [])
                        return self

                    async def __anext__(self):
                        try:
                            return next(self._iter)
                        except StopIteration:
                            raise StopAsyncIteration

                return _MockRes()

        class _MockSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def execute_read(self, fn, *args, **kwargs):
                return await fn(_MockTx())

            async def execute_write(self, fn, *args, **kwargs):
                return await fn(_MockTx())

        return _MockSession()


def _make_clustered_graph() -> GraphView:
    """Construct a synthetic graph with two distinct cliques connected by a weak bridge."""
    nodes = [
        # Cluster A
        StudioNode(id="a1", layer=Layer.L2, type="Entity", label="Node A1"),
        StudioNode(id="a2", layer=Layer.L2, type="Entity", label="Node A2"),
        StudioNode(id="a3", layer=Layer.L2, type="Entity", label="Node A3"),
        # Cluster B
        StudioNode(id="b1", layer=Layer.L2, type="Entity", label="Node B1"),
        StudioNode(id="b2", layer=Layer.L2, type="Entity", label="Node B2"),
        StudioNode(id="b3", layer=Layer.L2, type="Entity", label="Node B3"),
    ]
    edges = [
        # Cluster A internal edges
        StudioEdge(id="e_a1_a2", source="a1", target="a2", type="RELATED", layer=Layer.L2, weight=1.0),
        StudioEdge(id="e_a2_a3", source="a2", target="a3", type="RELATED", layer=Layer.L2, weight=1.0),
        StudioEdge(id="e_a3_a1", source="a3", target="a1", type="RELATED", layer=Layer.L2, weight=1.0),
        # Cluster B internal edges
        StudioEdge(id="e_b1_b2", source="b1", target="b2", type="RELATED", layer=Layer.L2, weight=1.0),
        StudioEdge(id="e_b2_b3", source="b2", target="b3", type="RELATED", layer=Layer.L2, weight=1.0),
        StudioEdge(id="e_b3_b1", source="b3", target="b1", type="RELATED", layer=Layer.L2, weight=1.0),
        # Inter-cluster bridge edge
        StudioEdge(id="e_bridge", source="a3", target="b1", type="RELATED", layer=Layer.L2, weight=0.1),
    ]
    return GraphView(
        nodes=nodes,
        edges=edges,
        source="fixture",
        graph_version="clustered-v1",
        schema_version="v1",
    )


@pytest.mark.asyncio
async def test_compute_leiden_igraph_clusters() -> None:
    """compute_leiden correctly partitions graph and assigns communities to nodes."""
    graph = _make_clustered_graph()
    overlay = compute_leiden(graph, params={"gamma": 1.0, "max_levels": 10})

    assert overlay.kind == OverlayKind.LEIDEN
    assert overlay.scale == "categorical"
    assert len(overlay.node_values) == 6

    # Verify every node received a non-null community
    for nid in ["a1", "a2", "a3", "b1", "b2", "b3"]:
        assert nid in overlay.node_values
        assert overlay.node_values[nid] is not None

    # Nodes in cluster A should share the same community
    assert overlay.node_values["a1"] == overlay.node_values["a2"] == overlay.node_values["a3"]
    # Nodes in cluster B should share the same community
    assert overlay.node_values["b1"] == overlay.node_values["b2"] == overlay.node_values["b3"]
    # Cluster A and Cluster B communities should be distinct
    assert overlay.node_values["a1"] != overlay.node_values["b1"]

    assert len(overlay.domain) >= 2


@pytest.mark.asyncio
async def test_compute_leiden_empty_graph() -> None:
    """compute_leiden handles empty graphs without crashing."""
    graph = GraphView(
        nodes=[],
        edges=[],
        source="fixture",
        graph_version="empty-v1",
        schema_version="v1",
    )
    overlay = compute_leiden(graph)
    assert overlay.kind == OverlayKind.LEIDEN
    assert overlay.node_values == {}
    assert overlay.domain == []


@pytest.mark.asyncio
async def test_overlay_service_supports_leiden() -> None:
    """OverlayService dispatches OverlayKind.LEIDEN to compute_leiden."""
    service = OverlayService()
    graph = _make_clustered_graph()
    overlay = service.compute_overlay(graph, OverlayKind.LEIDEN)

    assert overlay.kind == OverlayKind.LEIDEN
    assert len(overlay.node_values) == 6


@pytest.mark.asyncio
async def test_leiden_descriptor_in_registry() -> None:
    """MetricService.list_descriptors() exposes leiden_global with valid schema."""
    service = MetricService(neo4j_reader=None)
    descriptors = await service.list_descriptors()

    leiden_desc = next((d for d in descriptors if d.id == "leiden_global"), None)
    assert leiden_desc is not None
    assert leiden_desc.scope == MetricScope.GLOBAL
    assert leiden_desc.engine == "gds"
    assert "gamma" in leiden_desc.param_schema["properties"]
    assert "theta" in leiden_desc.param_schema["properties"]
    assert "max_levels" in leiden_desc.param_schema["properties"]


@pytest.mark.asyncio
async def test_run_gds_leiden_lifecycle() -> None:
    """run_gds_leiden creates projection, streams results, and drops projection in finally block."""
    dropped_projections: list[str] = []

    async def custom_run(query: str, **params):
        if "gds.version" in query:
            return [{"version": "2.6.0"}]
        if "gds.graph.project.cypher" in query:
            return [{"nodeCount": 6, "relationshipCount": 7}]
        if "gds.leiden.stream" in query:
            return [
                {"id": "a1", "communityId": 0},
                {"id": "a2", "communityId": 0},
                {"id": "a3", "communityId": 0},
                {"id": "b1", "communityId": 1},
                {"id": "b2", "communityId": 1},
                {"id": "b3", "communityId": 1},
            ]
        if "gds.graph.drop" in query:
            dropped_projections.append(query)
            return [{"graphName": "dropped"}]
        return []

    mock_driver = _MockNeo4jDriver(run_handler=custom_run)
    reader = Neo4jReader(driver=mock_driver)

    communities, summary = await reader.run_gds_leiden(gamma=1.0, theta=0.01)

    assert summary["community_count"] == 2
    assert summary["node_count"] == 6
    assert summary["engine"] == "gds"
    assert communities["a1"] == 0
    assert communities["b1"] == 1

    # Verify gds.graph.drop was executed in finally block
    assert len(dropped_projections) == 1
    assert "CALL gds.graph.drop(" in dropped_projections[0]


@pytest.mark.asyncio
async def test_metric_service_leiden_fallback_to_igraph() -> None:
    """When Neo4j GDS is unavailable, MetricService falls back to igraph with a warning."""
    service = MetricService(neo4j_reader=None)
    graph = _make_clustered_graph()

    result = await service.execute_metric("leiden_global", graph_view=graph)

    assert result.metric_id == "leiden_global"
    assert result.scope == MetricScope.GLOBAL
    assert result.result_value >= 2
    assert len(result.affected_nodes) == 6
    for detail in result.affected_nodes.values():
        assert "cluster" in detail.roles
        assert "community" in detail.metadata

    assert any("in-memory igraph fallback" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_metric_api_execute_leiden() -> None:
    """POST /api/metric-executions succeeds for leiden_global."""
    app = create_app(StudioSettings())
    graph = _make_clustered_graph()

    class _MockGraphService:
        def get_run_graph(self, run_id: str | None = None) -> GraphView:
            return graph

        async def get_neo4j_view(self) -> GraphView:
            return graph

        def require_reader(self):
            class _MockReader:
                def list_runs(self, limit: int = 1):
                    class _MockSummary:
                        run_id = "test-run"
                    return [_MockSummary()]
            return _MockReader()

    from episteme_studio.api.deps import get_graph_service
    app.dependency_overrides[get_graph_service] = lambda: _MockGraphService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/metric-executions",
            json={
                "metric_id": "leiden_global",
                "params": {"gamma": 1.0},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric_id"] == "leiden_global"
        assert len(data["affected_nodes"]) == 6
