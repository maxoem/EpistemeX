"""Tests for Milestone 3: Run browser, manifest reader, and phase status extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from episteme_studio.app import create_app
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_list_runs_endpoint() -> None:
    """GET /api/runs lists existing pipeline runs from disk."""
    settings = StudioSettings()
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/runs")
        assert response.status_code == 200
        runs = response.json()
        assert isinstance(runs, list)
        assert len(runs) > 0, "Expected existing runs to be discovered in .pipeline_runs"

        first_run = runs[0]
        assert "run_id" in first_run
        assert "status" in first_run
        assert "created_at" in first_run
        assert "artifact_count" in first_run
        assert "size_bytes" in first_run
        assert "primary_input" in first_run
        assert "duration_seconds" in first_run
        assert "reused_phase_count" in first_run
        assert "total_phase_count" in first_run
        assert isinstance(first_run.get("models"), dict)


@pytest.mark.asyncio
async def test_get_run_detail_preserves_own_schema_and_phases() -> None:
    """GET /api/runs/{run_id} renders under that run's OWN graph_schema and dynamic phases (D-13, D-22)."""
    settings = StudioSettings()
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First get available runs
        list_resp = await client.get("/api/runs")
        runs = list_resp.json()
        assert len(runs) > 0
        target_run_id = runs[0]["run_id"]

        response = await client.get(f"/api/runs/{target_run_id}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["run_id"] == target_run_id
        assert "graph_schema" in detail
        assert "phase_records" in detail
        assert "primary_input" in detail
        assert "duration_seconds" in detail
        assert "langfuse_url" in detail

        # Verify phase_records use ordinal and preserve non-unique names like 'Phase 4'
        phase_records = detail["phase_records"]
        assert isinstance(phase_records, list)
        for p in phase_records:
            assert "yield_summary" in p
            assert "duration_seconds" in p
            assert "artifact_counts_by_kind" in p

        if len(phase_records) >= 8:
            # Check for multiple phases named 'Phase 4'
            phase_4_names = [p["phase_name"] for p in phase_records if "Phase 4" in p["phase_name"]]
            assert len(phase_4_names) >= 2


@pytest.mark.asyncio
async def test_unknown_run_returns_404_problem_detail() -> None:
    """GET /api/runs/{nonexistent} returns 404 RFC 7807 problem+json."""
    settings = StudioSettings()
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/runs/run-does-not-exist-9999")
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
        data = response.json()
        assert data["type"] == "run-not-found"
        assert data["status"] == 404


@pytest.mark.asyncio
async def test_corrupted_run_manifest_returns_problem_detail(tmp_path: Path) -> None:
    """A corrupted or truncated JSON manifest yields a ProblemDetail, not an unhandled 500 crash."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    # Write invalid JSON
    bad_manifest = runs_dir / "run-corrupted.json"
    bad_manifest.write_text("{ incomplete json ...", encoding="utf-8")

    settings = StudioSettings(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Listing runs should skip corrupted files without throwing
        list_resp = await client.get("/api/runs")
        assert list_resp.status_code == 200
        assert list_resp.json() == []

        # Requesting the corrupted run directly should return problem+json
        resp = await client.get("/api/runs/run-corrupted")
        assert resp.status_code == 500
        assert resp.headers["content-type"] == "application/problem+json"
        body = resp.json()
        assert body["type"] == "corrupted-manifest"


@pytest.mark.asyncio
async def test_get_run_langfuse_stats_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the /api/runs/{run_id}/langfuse endpoint returns structured stats.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture for manipulating environment variables.

    Returns
    -------
    None
    """
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)

    settings = StudioSettings()
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Unconfigured keys without query parameters
        resp = await client.get("/api/runs/run-mock-123/langfuse?public_key=&secret_key=")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert data["run_id"] == "run-mock-123"
        assert isinstance(data["observations"], list)


def test_artifact_reader_aggregates_component_fingerprints(tmp_path: Path) -> None:
    """Verify ArtifactReader aggregates phase_config, method, and direct fingerprints.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory for pipeline runs.

    Returns
    -------
    None
    """
    from episteme_studio.adapters.artifact_reader import ArtifactReader

    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    manifest_data = {
        "run_id": "test-run-fps",
        "status": "completed",
        "created_at": "2026-10-10T12:00:00Z",
        "pipeline_version": "0.1.0",
        "fingerprints": {"legacy_fp": "hash_legacy"},
        "phase_config_fingerprints": {
            0: "hash_phase0",
            "phase2": "hash_phase2",
        },
        "method_fingerprints": {
            "phase2.decision_engine": "hash_de_v1",
            "phase2.modal_resolver": "hash_mr_v1",
            "phase3.relation_reranker": "hash_rr_v1",
        },
    }
    manifest_path = runs_dir / "test-run-fps.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    reader = ArtifactReader(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
    detail = reader.get_run("test-run-fps")

    assert detail is not None
    assert detail.method_fingerprints == {
        "phase2.decision_engine": "hash_de_v1",
        "phase2.modal_resolver": "hash_mr_v1",
        "phase3.relation_reranker": "hash_rr_v1",
    }
    # Fingerprints should aggregate phase_config_fingerprints, method_fingerprints, and direct fingerprints
    assert detail.fingerprints["0"] == "hash_phase0"
    assert detail.fingerprints["phase2"] == "hash_phase2"
    assert detail.fingerprints["phase2.decision_engine"] == "hash_de_v1"
    assert detail.fingerprints["phase2.modal_resolver"] == "hash_mr_v1"
    assert detail.fingerprints["phase3.relation_reranker"] == "hash_rr_v1"
    assert detail.fingerprints["legacy_fp"] == "hash_legacy"


