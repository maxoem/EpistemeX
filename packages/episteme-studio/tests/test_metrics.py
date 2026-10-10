"""Tests for Stories 2, 3, 4, and 7: Async Lifecycles, QBAF Explanations, GDS Projections & Fallbacks."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from episteme_studio.adapters.metrics_adapter import compute_local_gradual_strength
from episteme_studio.adapters.neo4j_reader import Neo4jReader
from episteme_studio.app import create_app
from episteme_studio.domain.graph import GraphView, Layer, StudioEdge, StudioNode
from episteme_studio.domain.metrics import MetricScope
from episteme_studio.services.metric_service import MetricService
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


def _make_sample_graph() -> GraphView:
    """Create a sample epistemic graph for testing local gradual strength."""
    nodes = [
        StudioNode(id="focus", layer=Layer.L3, type="Claim", label="Main Thesis", plausibility=0.6),
        StudioNode(id="premise_1", layer=Layer.L3, type="Claim", label="Supporting Premise", plausibility=0.8),
        StudioNode(id="counter_1", layer=Layer.L3, type="Claim", label="Counterargument", plausibility=0.7),
        StudioNode(id="rebuttal_1", layer=Layer.L3, type="Claim", label="Rebuttal", plausibility=0.9),
    ]
    edges = [
        StudioEdge(id="e1", source="premise_1", target="focus", type="SUPPORTS", layer=Layer.L3, polarity=1, weight=0.9),
        StudioEdge(id="e2", source="counter_1", target="focus", type="ATTACKS", layer=Layer.L3, polarity=-1, weight=0.8),
        StudioEdge(id="e3", source="rebuttal_1", target="counter_1", type="ATTACKS", layer=Layer.L3, polarity=-1, weight=0.85),
    ]
    return GraphView(
        nodes=nodes,
        edges=edges,
        source="fixture",
        graph_version="test-graph-v1",
        schema_version="v1",
    )


@pytest.mark.asyncio
async def test_fast_path_sub_250ms_returns_200_ok() -> None:
    """Sub-250ms metric calculations return 200 OK with MetricResult directly."""
    app = create_app(StudioSettings())
    graph = _make_sample_graph()

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
                "metric_id": "gradual_strength_local",
                "focus_node_id": "focus",
                "params": {"max_depth": 2, "iterations": 10},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric_id"] == "gradual_strength_local"
        assert data["scope"] == "single_node"
        assert data["focus_node_id"] == "focus"
        assert "result_value" in data
        assert "affected_nodes" in data
        assert "affected_edges" in data


@pytest.mark.asyncio
async def test_async_long_running_returns_202_accepted_and_polls() -> None:
    """Long-running executions return 202 Accepted with status URL, then complete on poll."""
    metric_service = MetricService()
    graph = _make_sample_graph()

    # Artificially test submit_execution with timeout=0.0001s and mock delay to force async background job
    job, is_fast = await metric_service.submit_execution(
        metric_id="gradual_strength_local",
        graph_view=graph,
        focus_node_id="focus",
        params={"max_depth": 2, "_mock_delay": 0.1},
        fast_path_timeout=0.00001,
    )
    assert is_fast is False
    assert job.status.value in ("queued", "running")

    # Wait for the background task to complete
    if job.task:
        await job.task

    assert job.status.value == "completed"
    assert job.result is not None
    assert job.result.focus_node_id == "focus"


@pytest.mark.asyncio
async def test_cooperative_cancellation() -> None:
    """DELETE /api/metric-executions/{id} cancels an in-flight background execution."""
    app = create_app(StudioSettings())
    metric_service: MetricService = app.state.metric_service
    graph = _make_sample_graph()

    job, is_fast = await metric_service.submit_execution(
        metric_id="gradual_strength_local",
        graph_view=graph,
        focus_node_id="focus",
        params={"_mock_delay": 1.0},
        fast_path_timeout=0.00001,
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        del_resp = await client.delete(f"/api/metric-executions/{job.execution_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "cancelled"

        # Polling status reports cancelled
        status_resp = await client.get(f"/api/metric-executions/{job.execution_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_qbaf_cyclic_graph_terminates_without_locking() -> None:
    """Circular argument graphs (A attacks B, B attacks A) converge without infinite loops."""
    nodes = [
        StudioNode(id="A", layer=Layer.L3, type="Claim", label="Claim A", plausibility=0.6),
        StudioNode(id="B", layer=Layer.L3, type="Claim", label="Claim B", plausibility=0.6),
    ]
    edges = [
        StudioEdge(id="e_ab", source="A", target="B", type="ATTACKS", layer=Layer.L3, polarity=-1, weight=0.8),
        StudioEdge(id="e_ba", source="B", target="A", type="ATTACKS", layer=Layer.L3, polarity=-1, weight=0.8),
    ]
    graph = GraphView(
        nodes=nodes,
        edges=edges,
        source="fixture",
        graph_version="cyclic-v1",
        schema_version="v1",
    )

    result = compute_local_gradual_strength(
        graph=graph,
        focus_node_id="A",
        params={"max_depth": 3, "iterations": 15, "tolerance": 1e-4},
    )
    assert result.result_value is not None
    assert 0.0 <= float(result.result_value) <= 1.0
    assert "A" in result.affected_nodes
    assert "B" in result.affected_nodes
    assert result.summary["iterations"] <= 15


@pytest.mark.asyncio
async def test_multi_role_node_detection_opposing_pathways() -> None:
    """Nodes reaching the focus via both support and attack pathways are tagged multi-role."""
    # S supports focus directly (+1)
    # S also attacks M, which supports focus -> net path (-1 * +1 = -1)
    nodes = [
        StudioNode(id="F", layer=Layer.L3, type="Claim", label="Focus Thesis", plausibility=0.5),
        StudioNode(id="M", layer=Layer.L3, type="Claim", label="Intermediate", plausibility=0.7),
        StudioNode(id="S", layer=Layer.L3, type="Claim", label="Controversial Source", plausibility=0.8),
    ]
    edges = [
        StudioEdge(id="e_sf", source="S", target="F", type="SUPPORTS", layer=Layer.L3, polarity=1, weight=0.7),
        StudioEdge(id="e_sm", source="S", target="M", type="ATTACKS", layer=Layer.L3, polarity=-1, weight=0.8),
        StudioEdge(id="e_mf", source="M", target="F", type="SUPPORTS", layer=Layer.L3, polarity=1, weight=0.9),
    ]
    graph = GraphView(
        nodes=nodes,
        edges=edges,
        source="fixture",
        graph_version="multi-role-v1",
        schema_version="v1",
    )

    result = compute_local_gradual_strength(
        graph=graph,
        focus_node_id="F",
        params={"max_depth": 3},
    )
    s_detail = result.affected_nodes.get("S")
    assert s_detail is not None
    assert "support" in s_detail.roles
    assert "attack" in s_detail.roles
    # Marginal net contribution calculated
    assert s_detail.net_contribution is not None

    # Edge annotations
    assert len(result.affected_edges) == 3
    edge_roles = {e.relationship_id: e.role for e in result.affected_edges}
    assert edge_roles["e_sf"] == "support"
    assert edge_roles["e_sm"] == "attack"


@pytest.mark.asyncio
async def test_gds_projection_dropped_in_finally_on_error() -> None:
    """Ephemeral GDS projection is guaranteed to be dropped if streaming query fails."""
    drop_called = False

    def _handler(query: str, **params):
        nonlocal drop_called
        if "gds.version" in query:
            return [{"version": "2.6.0"}]
        if "gds.graph.project.cypher" in query:
            return [{"graphName": "proj"}]
        if "gds.pageRank.stream" in query:
            raise RuntimeError("Simulated PageRank streaming failure")
        if "gds.graph.drop" in query:
            drop_called = True
            return [{"graphName": "dropped"}]
        return []

    mock_driver = _MockNeo4jDriver(run_handler=_handler)
    reader = Neo4jReader(driver=mock_driver)

    with pytest.raises(RuntimeError, match="Simulated PageRank streaming failure"):
        await reader.run_gds_pagerank()

    assert drop_called is True
    assert any("gds.graph.drop" in q for q in mock_driver.executed_queries)


@pytest.mark.asyncio
async def test_pagerank_epistemetrics_fallback_when_gds_missing() -> None:
    """When GDS is missing, execute_metric falls back to epistemetrics and records warning."""
    service = MetricService(neo4j_reader=None)  # No Neo4j reader, forces in-memory fallback
    graph = _make_sample_graph()

    result = await service.execute_metric(
        metric_id="pagerank_global",
        graph_view=graph,
        params={"damping": 0.85},
    )
    assert result.metric_id == "pagerank_global"
    assert result.scope == MetricScope.GLOBAL
    assert len(result.affected_nodes) == len(graph.nodes)
    assert any("Executed via in-memory epistemetrics fallback" in w for w in result.warnings)
    assert result.summary["engine"] == "epistemetrics"


@pytest.mark.asyncio
async def test_epistemetrics_components_betweenness_and_eigenvector() -> None:
    """Verify component, betweenness, and eigenvector metrics execute via epistemetrics."""
    service = MetricService(neo4j_reader=None)
    graph = _make_sample_graph()

    # Weakly connected components
    comp_res = await service.execute_metric("component_global", graph_view=graph)
    assert comp_res.metric_id == "component_global"
    assert comp_res.summary["engine"] == "epistemetrics"
    assert comp_res.result_value >= 1

    # Betweenness centrality
    bet_res = await service.execute_metric("betweenness_global", graph_view=graph)
    assert bet_res.metric_id == "betweenness_global"
    assert bet_res.summary["engine"] == "epistemetrics"
    assert len(bet_res.affected_nodes) == len(graph.nodes)

    # Eigenvector centrality
    eig_res = await service.execute_metric("eigenvector_global", graph_view=graph)
    assert eig_res.metric_id == "eigenvector_global"
    assert eig_res.summary["engine"] == "epistemetrics"
    assert len(eig_res.affected_nodes) == len(graph.nodes)
