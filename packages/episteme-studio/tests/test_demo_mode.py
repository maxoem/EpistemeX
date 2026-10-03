"""Tests for episteme-studio canned demo mode."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from episteme_studio.app import create_app
from episteme_studio.settings import StudioSettings


@pytest.mark.asyncio
async def test_demo_mode_lists_canned_runs() -> None:
    """When demo_mode=True, list_runs returns packaged demo runs."""
    settings = StudioSettings(neo4j_url=None, demo_mode=True)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/runs")
        assert response.status_code == 200
        runs = response.json()
        assert len(runs) >= 2

        run_ids = {r["run_id"] for r in runs}
        assert "run-demo-physics" in run_ids
        assert "run-demo-psychology" in run_ids


@pytest.mark.asyncio
async def test_demo_mode_get_run_detail() -> None:
    """When demo_mode=True, get_run returns full RunDetail for physics run."""
    settings = StudioSettings(neo4j_url=None, demo_mode=True)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/runs/run-demo-physics")
        assert response.status_code == 200
        detail = response.json()
        assert detail["run_id"] == "run-demo-physics"
        assert detail["status"] == "completed"
        assert len(detail["phase_records"]) >= 6
        assert (
            "BasicAxiom" in detail["config_snapshot"]["graph_schema"]["component_types"]
        )


@pytest.mark.asyncio
async def test_demo_mode_get_graph() -> None:
    """When demo_mode=True, get_graph returns full L1/L2/L3 graph from envelopes."""
    settings = StudioSettings(neo4j_url=None, demo_mode=True)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/runs/run-demo-physics/graph")
        assert response.status_code == 200
        graph = response.json()
        assert len(graph["nodes"]) > 0
        assert len(graph["edges"]) > 0

        layers = {n["layer"] for n in graph["nodes"]}
        # Verify all 3 layers exist: L1 (1), L2 (2), L3 (3)
        assert 1 in layers
        assert 2 in layers
        assert 3 in layers


@pytest.mark.asyncio
async def test_demo_mode_psychology_graph() -> None:
    """When demo_mode=True, psychology run has all 3 layers and conflict edges."""
    settings = StudioSettings(neo4j_url=None, demo_mode=True)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/runs/run-demo-psychology/graph")
        assert response.status_code == 200
        graph = response.json()
        assert len(graph["nodes"]) > 0
        assert len(graph["edges"]) > 0

        edge_types = {e["type"] for e in graph["edges"]}
        assert "ATTACKS" in edge_types
        assert "SUPPORTS" in edge_types


def test_demo_and_read_only_allow_non_loopback_binding_without_token() -> None:
    """Non-loopback bindings are permitted without token when demo_mode or read_only is active."""
    from episteme_studio.security import validate_host_and_token

    # demo_mode permits 0.0.0.0 without token
    validate_host_and_token(StudioSettings(host="0.0.0.0", token=None, demo_mode=True))

    # read_only permits 0.0.0.0 without token
    validate_host_and_token(StudioSettings(host="0.0.0.0", token=None, read_only=True))


@pytest.mark.asyncio
async def test_read_only_mode_blocks_mutations() -> None:
    """When read_only=True, run triggering, file uploads, and engine settings updates are blocked with 403."""
    settings = StudioSettings(neo4j_url=None, demo_mode=True, read_only=True)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. POST /api/runs is blocked
        run_resp = await client.post("/api/runs", json={"demo_mode": True})
        assert run_resp.status_code == 403
        assert run_resp.json()["type"] == "read-only-mode"

        # 2. POST /api/config/inputs/upload is blocked
        upload_resp = await client.post(
            "/api/config/inputs/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert upload_resp.status_code == 403
        assert upload_resp.json()["type"] == "read-only-mode"

        # 3. PUT /api/engine/settings is blocked
        engine_resp = await client.put(
            "/api/engine/settings",
            json={"aliases": {"TEST": "CONTAINS"}},
        )
        assert engine_resp.status_code == 403
        assert engine_resp.json()["type"] == "read-only-mode"


@pytest.mark.asyncio
async def test_execution_disabled_blocks_real_runs() -> None:
    """When execution_enabled=False, real pipeline runs (demo_mode=False) are rejected with 403."""
    settings = StudioSettings(neo4j_url=None, execution_enabled=False, demo_mode=False)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/runs", json={"demo_mode": False})
        assert resp.status_code == 403
        assert resp.json()["type"] == "execution-disabled"


@pytest.mark.asyncio
async def test_demo_mode_decision_engine_safeguards() -> None:
    """When demo_mode=True or read_only=True, decision engine is sandboxed to offline simulation."""
    settings = StudioSettings(neo4j_url=None, demo_mode=True, read_only=True)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Status reflects demo mode
        status_resp = await client.get("/api/engine/decision/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["available"] is True
        assert "demo" in status_data["provider"]
        assert status_data["device"] == "simulated"
        assert status_data["model_metadata"]["demo_mode"] is True
        assert status_data["model_metadata"]["read_only"] is True

        # 2. Decision test runs safely in offline simulation stub
        test_resp = await client.post(
            "/api/engine/decision/test",
            json={
                "primitive": "choice",
                "input_text": "Der Satz vom Widerspruch ist das Fundament der Logik.",
                "candidate_labels": ["Axiom", "Empirical", "Conjecture"],
            },
        )
        assert test_resp.status_code == 200
        test_data = test_resp.json()
        assert test_data["primitive"] == "choice"
        assert test_data["selected_option"] == "Axiom"
        assert test_data["empirical_accuracy"] >= 0.8
        assert len(test_data["prediction_set"]) >= 1
        assert test_data["tokens_saved_estimate"] > 0
        assert test_data["tier"] in ("fast_exit", "system1", "system2")

