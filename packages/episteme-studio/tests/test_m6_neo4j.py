"""Tests for Milestone 6: Neo4j integration, Cypher console, and UNDERCUTS reification."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from typing import Any, Self

import pytest
from episteme_studio.adapters.neo4j_reader import Neo4jReader
from episteme_studio.app import create_app
from episteme_studio.domain.errors import Neo4jUnavailableError
from episteme_studio.domain.graph import (
    Layer,
    StudioEdge,
    StudioNode,
    reify_inferences,
)
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient
from neo4j import RoutingControl
from neo4j.exceptions import ClientError


class _MockAsyncResult:
    """Mock Neo4j AsyncResult supporting __aiter__ and keys()."""

    def __init__(self, cols: list[str], records: list[dict[str, Any]]) -> None:
        self._cols = cols
        self._records = records

    def keys(self) -> list[str]:
        return list(self._cols)

    def __aiter__(self):
        self._iter = iter(self._records)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _MockAsyncTx:
    """Mock Neo4j AsyncTransaction."""

    def __init__(self, run_handler) -> None:
        self.run_handler = run_handler

    async def run(self, query: str, **params) -> _MockAsyncResult:
        res = self.run_handler(query, **params)
        if asyncio.iscoroutine(res):
            res = await res
        return res


class _MockAsyncSession:
    """Mock Neo4j AsyncSession."""

    def __init__(self, run_handler) -> None:
        self.run_handler = run_handler

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute_read(self, tx_func, *args, **kwargs):
        tx = _MockAsyncTx(self.run_handler)
        return await tx_func(tx, *args, **kwargs)


class _MockAsyncDriver:
    """Mock Neo4j AsyncDriver."""

    def __init__(self, run_handler=None) -> None:
        self.run_handler = run_handler or self._default_run
        self.closed = False
        self.session_access_mode = None

    async def _default_run(self, query: str, **params) -> _MockAsyncResult:
        return _MockAsyncResult(["count"], [{"count": 1}])

    def session(self, database=None, default_access_mode=None) -> _MockAsyncSession:
        self.session_access_mode = default_access_mode
        return _MockAsyncSession(self.run_handler)

    async def verify_connectivity(self) -> None:
        pass

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_lifespan_creates_single_driver_and_closes() -> None:
    """One AsyncDriver managed in the lifespan, not per request, and closed on exit."""
    mock_driver = _MockAsyncDriver()

    app = create_app(StudioSettings(neo4j_url="bolt://127.0.0.1:7687"))
    app.state.neo4j_driver = mock_driver
    app.state.neo4j_available = True

    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/capabilities")
            assert resp.status_code == 200
            assert resp.json()["neo4j"] is True
            # Driver on app.state is preserved across requests
            assert app.state.neo4j_driver is mock_driver

    # After lifespan context closes
    assert mock_driver.closed is True


@pytest.mark.asyncio
async def test_capabilities_reports_false_when_neo4j_down() -> None:
    """With Neo4j down/unreachable, /api/capabilities reports false and console is greyed out."""
    settings = StudioSettings(neo4j_url="bolt://127.0.0.1:9999", demo_mode=True)
    app = create_app(settings)
    app.state.neo4j_driver = None
    app.state.neo4j_available = False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["neo4j"] is False
        assert data["artifacts"] is True


@pytest.mark.asyncio
async def test_read_only_violation_rejected_with_403() -> None:
    """A write statement is rejected with neo4j-read-only-violation via read access mode (D-23)."""
    async def write_rejection_handler(query: str, **params):
        if "CREATE" in query.upper() or "MERGE" in query.upper() or "DELETE" in query.upper():
            # Neo4j server raises ClientError when writing in read access mode
            raise ClientError("Writing in read access mode not allowed. (Neo.ClientError.Statement.AccessMode)")
        return _MockAsyncResult(["n"], [])

    mock_driver = _MockAsyncDriver(run_handler=write_rejection_handler)
    app = create_app(StudioSettings(neo4j_url="bolt://127.0.0.1:7687"))
    app.state.neo4j_driver = mock_driver
    app.state.neo4j_available = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"query": "CREATE (n:Test {name: 'WriteTest'}) RETURN n"}
        resp = await client.post("/api/graph/cypher", json=payload)
        assert resp.status_code == 403
        data = resp.json()
        assert data["type"] == "neo4j-read-only-violation"
        assert "read access mode" in data["detail"].lower()
        # Verify read access mode was configured on the session
        assert mock_driver.session_access_mode == RoutingControl.READ


@pytest.mark.asyncio
async def test_query_timeout_returns_504() -> None:
    """A cartesian-product query hits the timeout and returns query-timeout (status 504)."""
    async def slow_handler(query: str, **params):
        # Simulate long-running query
        await asyncio.sleep(0.5)
        return _MockAsyncResult(["n"], [])

    mock_driver = _MockAsyncDriver(run_handler=slow_handler)
    app = create_app(StudioSettings(neo4j_url="bolt://127.0.0.1:7687", query_timeout_seconds=0.05))
    app.state.neo4j_driver = mock_driver
    app.state.neo4j_available = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/graph/cypher",
            json={"query": "MATCH (a), (b), (c) RETURN a, b, c"},
        )
        assert resp.status_code == 504
        data = resp.json()
        assert data["type"] == "query-timeout"
        assert "exceeded timeout limit" in data["detail"]


@pytest.mark.asyncio
async def test_row_cap_enforced_returns_413() -> None:
    """Row cap enforced, with result-too-large past it (status 413)."""
    # Return 10 rows when cap is 5
    records = [{"id": i, "val": f"v{i}"} for i in range(10)]
    mock_driver = _MockAsyncDriver(
        run_handler=lambda q, **p: _MockAsyncResult(["id", "val"], records)
    )
    app = create_app(StudioSettings(neo4j_url="bolt://127.0.0.1:7687"))
    app.state.neo4j_driver = mock_driver
    app.state.neo4j_available = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Cap at 5 rows
        resp = await client.post(
            "/api/graph/cypher",
            json={"query": "MATCH (n) RETURN n", "limit": 5},
        )
        assert resp.status_code == 413
        data = resp.json()
        assert data["type"] == "result-too-large"
        assert "exceeded row budget cap (5 rows)" in data["detail"]


@pytest.mark.asyncio
async def test_undercuts_reification() -> None:
    """UNDERCUTS reifies to a synthetic Inference node (D-21)."""
    nodes = [
        StudioNode(id="premise_1", layer=Layer.L3, type="Claim", label="Premise 1"),
        StudioNode(id="conclusion_1", layer=Layer.L3, type="Claim", label="Conclusion 1"),
        StudioNode(id="attacker_1", layer=Layer.L3, type="Claim", label="Attacker 1"),
    ]
    edges = [
        StudioEdge(
            id="rel_supports_1",
            source="premise_1",
            target="conclusion_1",
            type="SUPPORTS",
            layer=Layer.L3,
            polarity=1,
        ),
        StudioEdge(
            id="rel_undercut_1",
            source="attacker_1",
            target="rel_supports_1",  # Targeting an edge!
            type="UNDERCUTS",
            layer=Layer.L3,
            polarity=-1,
            target_kind="edge",
        ),
    ]

    reified_nodes, reified_edges = reify_inferences(nodes, edges)

    # A synthetic Inference node must be created
    synthetic = [n for n in reified_nodes if n.synthetic]
    assert len(synthetic) == 1
    inf_node = synthetic[0]
    assert inf_node.id == "inference::rel_supports_1"
    assert inf_node.type == "Inference"
    assert inf_node.props["reified_edge_id"] == "rel_supports_1"
    assert inf_node.resolved is True

    # The UNDERCUTS edge must be rewired to the synthetic node
    undercut_edge = next(e for e in reified_edges if e.id == "rel_undercut_1")
    assert undercut_edge.target == "inference::rel_supports_1"
    assert undercut_edge.target_kind == "node"
    assert undercut_edge.props["original_target_edge_id"] == "rel_supports_1"


@pytest.mark.asyncio
async def test_unmapped_predicates_ranking() -> None:
    """Unmapped Predicates ranks predicates by frequency with an example edge each (D-15)."""
    # Sample nodes
    nodes = [
        {"id": "c1", "labels": ["Concept", "Entity"], "props": {"name": "Concept 1"}},
        {"id": "c2", "labels": ["Concept", "Entity"], "props": {"name": "Concept 2"}},
        {"id": "c3", "labels": ["Concept", "Entity"], "props": {"name": "Concept 3"}},
    ]
    # Relationships with open-vocabulary German predicates not in standard schema
    rels = [
        {"source_id": "c1", "target_id": "c2", "rel_type": "WIDERSPRICHT", "rel_id": "r1", "props": {}},
        {"source_id": "c2", "target_id": "c3", "rel_type": "WIDERSPRICHT", "rel_id": "r2", "props": {}},
        {"source_id": "c1", "target_id": "c3", "rel_type": "BASIERT_AUF", "rel_id": "r3", "props": {}},
    ]

    async def mock_run(query: str, **params):
        if "labels(n)" in query:
            return _MockAsyncResult(["id", "labels", "props"], nodes)
        return _MockAsyncResult(["source_id", "target_id", "rel_type", "rel_id", "props"], rels)

    mock_driver = _MockAsyncDriver(run_handler=mock_run)
    reader = Neo4jReader(driver=mock_driver)
    view = await reader.get_graph_view(budget=10)

    # WIDERSPRICHT appeared 2 times, BASIERT_AUF appeared 1 time
    assert "WIDERSPRICHT" in view.unmapped_predicates
    assert view.unmapped_predicates["WIDERSPRICHT"] == 2
    assert "BASIERT_AUF" in view.unmapped_predicates
    assert view.unmapped_predicates["BASIERT_AUF"] == 1


@pytest.mark.asyncio
async def test_d18_identity_key_stability() -> None:
    """Verify D-18: confirm identity_key is stable across repeated runs over the same input."""
    # Compare runs over scieERC texts
    run_a = Path(".pipeline_artifacts/run-96c2cc30-f109-44b7-b9bb-dca728e2b0e4")
    run_b = Path(".pipeline_artifacts/run-dd36e818-be22-4373-a83d-99a5a653521d")

    if run_a.exists() and run_b.exists():
        import json

        def extract_keys(run_dir: Path) -> set[str]:
            keys = set()
            for f in run_dir.glob("*.json"):
                data = json.loads(f.read_text(encoding="utf-8"))
                ik = data.get("identity_key")
                if ik:
                    keys.add(ik)
            return keys

        keys_a = extract_keys(run_a)
        keys_b = extract_keys(run_b)

        assert len(keys_a) > 0, "Expected non-empty identity_keys in run A"
        # Exact 100% match across runs
        assert keys_a == keys_b, f"identity_key drift detected between {run_a} and {run_b}"


@pytest.mark.asyncio
async def test_dynamic_neo4j_connect_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/graph/connect establishes an in-session driver connection."""
    app = create_app(StudioSettings(demo_mode=True))
    mock_driver = _MockAsyncDriver()

    async def mock_create_and_verify(*args, **kwargs):
        return mock_driver

    monkeypatch.setattr(Neo4jReader, "create_and_verify_driver", mock_create_and_verify)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cap_resp = await client.get("/api/capabilities")
        assert cap_resp.json()["neo4j"] is False

        conn_resp = await client.post(
            "/api/graph/connect",
            json={"url": "bolt://127.0.0.1:7687", "user": "neo4j", "password": "secretpassword"},
        )
        assert conn_resp.status_code == 200
        assert conn_resp.json()["status"] == "connected"
        assert conn_resp.json()["neo4j"] is True

        cap_resp_after = await client.get("/api/capabilities")
        assert cap_resp_after.json()["neo4j"] is True


@pytest.mark.asyncio
async def test_neo4j_status_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/graph/status accurately reports connection state and parameters."""
    app = create_app(StudioSettings(demo_mode=True))
    mock_driver = _MockAsyncDriver()

    async def mock_create_and_verify(*args, **kwargs):
        return mock_driver

    monkeypatch.setattr(Neo4jReader, "create_and_verify_driver", mock_create_and_verify)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Initially disconnected
        resp = await client.get("/api/graph/status")
        assert resp.status_code == 200
        assert resp.json() == {"connected": False, "url": None, "database": None}

        # Connect
        await client.post(
            "/api/graph/connect",
            json={"url": "bolt://127.0.0.1:7687", "user": "neo4j", "password": "secretpassword", "database": "neo4j"},
        )

        # Connected status reported
        resp_after = await client.get("/api/graph/status")
        assert resp_after.status_code == 200
        assert resp_after.json() == {"connected": True, "url": "bolt://127.0.0.1:7687", "database": "neo4j"}



@pytest.mark.asyncio
async def test_dynamic_neo4j_connect_failure_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/graph/connect returns 400 ProblemDetail on unreachable database."""
    app = create_app(StudioSettings(demo_mode=True))

    async def mock_fail(*args, **kwargs):
        raise Neo4jUnavailableError("Failed to reach server")

    monkeypatch.setattr(Neo4jReader, "create_and_verify_driver", mock_fail)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        conn_resp = await client.post(
            "/api/graph/connect",
            json={"url": "bolt://127.0.0.1:9999", "user": "neo4j", "password": "wrong"},
        )
        assert conn_resp.status_code == 400
        assert conn_resp.headers["content-type"] == "application/problem+json"
        data = conn_resp.json()
        assert data["type"] == "neo4j-connection-failed"


def test_settings_neo4j_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """StudioSettings falls back to standard NEO4J_URL and NEO4J_USERNAME."""
    monkeypatch.delenv("EPISTEME_STUDIO_NEO4J_URL", raising=False)
    monkeypatch.delenv("EPISTEME_STUDIO_NEO4J_USER", raising=False)
    monkeypatch.setenv("NEO4J_URL", "bolt://standard-host:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "custom-user")

    settings = StudioSettings()
    assert settings.neo4j_url == "bolt://standard-host:7687"
    assert settings.neo4j_user == "custom-user"


def test_neo4j_isolation_guard() -> None:
    """AST guard: Only adapters/ may import neo4j; domain/, services/, and api/ must not."""
    src_dir = Path(__file__).parent.parent / "src" / "episteme_studio"
    forbidden_dirs = [src_dir / "domain", src_dir / "services", src_dir / "api", src_dir / "runtime"]

    violations = []
    for d in forbidden_dirs:
        for py_file in d.glob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] == "neo4j":
                            violations.append(f"{py_file.name}:{node.lineno} imports '{alias.name}'")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".")[0] == "neo4j":
                        violations.append(f"{py_file.name}:{node.lineno} imports from '{node.module}'")

    assert not violations, "Neo4j driver imported outside adapters/:\n" + "\n".join(violations)


@pytest.mark.asyncio
async def test_execute_cypher_sync_and_async_keys_support() -> None:
    """Verify execute_cypher supports both synchronous and asynchronous keys() methods.

    Tests that Neo4j driver's synchronous keys() list and any mock coroutine keys()
    are properly unpacked without raising TypeError.
    """
    driver_sync = _MockAsyncDriver(
        lambda q, **kw: _MockAsyncResult(["col_a", "col_b"], [{"col_a": 1, "col_b": "two"}])
    )
    reader_sync = Neo4jReader(driver=driver_sync)
    res_sync = await reader_sync.execute_cypher("RETURN 1 AS col_a, 'two' AS col_b")
    assert res_sync.columns == ["col_a", "col_b"]
    assert res_sync.rows == [{"col_a": 1, "col_b": "two"}]

    class _MockAsyncKeysResult(_MockAsyncResult):
        async def keys(self) -> list[str]:
            return self._cols

    driver_async_keys = _MockAsyncDriver(
        lambda q, **kw: _MockAsyncKeysResult(["col_x"], [{"col_x": 42}])
    )
    reader_async = Neo4jReader(driver=driver_async_keys)
    res_async = await reader_async.execute_cypher("RETURN 42 AS col_x")
    assert res_async.columns == ["col_x"]
    assert res_async.rows == [{"col_x": 42}]


@pytest.mark.asyncio
async def test_disconnect_neo4j_endpoint() -> None:
    """POST /api/graph/disconnect closes driver and resets state."""
    mock_driver = _MockAsyncDriver()
    app = create_app(StudioSettings())
    app.state.neo4j_driver = mock_driver
    app.state.neo4j_available = True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/graph/disconnect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"
        assert data["neo4j"] is False
        assert app.state.neo4j_available is False
        assert app.state.neo4j_driver is None
        assert mock_driver.closed is True


