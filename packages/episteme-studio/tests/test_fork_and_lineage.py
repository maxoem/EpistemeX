"""Unit tests for run forking, cache invalidation preview with parent runs, and artifact lineage traversal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.app import create_app
from episteme_studio.domain.config import ConfigPatch
from episteme_studio.services.config_service import ConfigService
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_run_lineage_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a temporary workspace with parent run artifacts and manifests.

    Parameters
    ----------
    tmp_path : Path
        Temporary directory fixture from pytest.

    Returns
    -------
    tuple of Path, Path, Path
        Paths to (runs_dir, artifacts_dir, data_dir).
    """
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True)
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)

    # Create dummy input document
    input_file = data_dir / "paper.txt"
    input_file.write_text("Theoretical physics and epistemology of gravity.", encoding="utf-8")

    # Compute source fingerprint using pipeline fingerprinting logic
    from episteme_pipeline.runs.fingerprints import fingerprint_existing_sources
    source_fp = fingerprint_existing_sources([str(input_file)], [])

    parent_manifest: dict[str, Any] = {
        "run_id": "run-parent-100",
        "status": "completed",
        "created_at": "2026-09-12T10:00:00Z",
        "duration_seconds": 12.5,
        "input_sources": [str(input_file)],
        "source_fingerprint": source_fp,
        "input_fingerprint": source_fp,
        "phase_records": [
            {
                "ordinal": 1,
                "phase_name": "Phase 1: Ingestion",
                "status": "completed",
                "duration_seconds": 2.1,
                "reused": False,
                "artifact_counts_by_kind": {"document": 1, "chunk": 2},
            },
            {
                "ordinal": 2,
                "phase_name": "Phase 2: Entity & Relation Extraction",
                "status": "completed",
                "duration_seconds": 4.2,
                "reused": False,
                "artifact_counts_by_kind": {"entity": 4, "local_relation": 3},
            },
            {
                "ordinal": 3,
                "phase_name": "Phase 3: Global Relations",
                "status": "completed",
                "duration_seconds": 3.0,
                "reused": False,
                "artifact_counts_by_kind": {"global_relation": 2},
            },
            {
                "ordinal": 4,
                "phase_name": "Phase 4: Argument Mining",
                "status": "completed",
                "duration_seconds": 3.2,
                "reused": False,
                "artifact_counts_by_kind": {"theory_atom": 3, "theory_relation": 2},
            },
            {
                "ordinal": 5,
                "phase_name": "Phase 5: Canonicalization & Maturation",
                "status": "completed",
                "duration_seconds": 1.5,
                "reused": False,
                "artifact_counts_by_kind": {"canonical_entity": 2},
            },
            {
                "ordinal": 6,
                "phase_name": "Phase 6: Structural Hierarchy",
                "status": "completed",
                "duration_seconds": 1.8,
                "reused": False,
                "artifact_counts_by_kind": {"hierarchy_node": 2},
            },
            {
                "ordinal": 7,
                "phase_name": "Phase 7: Theoretical Enrichment",
                "status": "completed",
                "duration_seconds": 2.0,
                "reused": False,
                "artifact_counts_by_kind": {"theoretical_enrichment": 1},
            },
            {
                "ordinal": 8,
                "phase_name": "Phase 8: Tenability & Formal Scoring",
                "status": "completed",
                "duration_seconds": 2.2,
                "reused": False,
                "artifact_counts_by_kind": {"tenability_score": 1},
            },
        ],
        "config_snapshot": {
            "execution": {"project_artifacts_to_graph": False},
            "phase1": {"chunk_size": 1000},
            "phase2": {"linking_confidence_threshold": 0.8},
            "phase3": {"community_threshold": 0.7},
            "phase4": {"argument_threshold": 0.75},
            "models": {"llm_model": "gpt-4o"},
        },
    }

    # Write parent manifest
    (runs_dir / "run-parent-100.json").write_text(json.dumps(parent_manifest), encoding="utf-8")

    # Write parent artifact envelopes
    parent_art_dir = artifacts_dir / "run-parent-100"
    parent_art_dir.mkdir(parents=True)

    envelope_doc = {
        "artifact_id": "art-doc-1",
        "run_id": "run-parent-100",
        "kind": "document",
        "phase_ordinal": 1,
        "created_at": "2026-09-12T10:00:01Z",
        "data": {"title": "Paper", "text": "Content"},
    }
    (parent_art_dir / "doc-1.json").write_text(json.dumps(envelope_doc), encoding="utf-8")

    envelope_entity = {
        "artifact_id": "art-ent-1",
        "run_id": "run-parent-100",
        "kind": "entity",
        "phase_ordinal": 2,
        "created_at": "2026-09-12T10:00:03Z",
        "data": {
            "id": "ent-1",
            "name": "General Relativity",
            "label": "General Relativity",
            "entity_type": "Concept",
            "layer": "L2",
        },
    }
    (parent_art_dir / "ent-1.json").write_text(json.dumps(envelope_entity), encoding="utf-8")

    # Create child manifest that forked from parent
    child_manifest: dict[str, Any] = {
        "run_id": "run-child-200",
        "parent_run_id": "run-parent-100",
        "status": "completed",
        "created_at": "2026-09-12T11:00:00Z",
        "duration_seconds": 1.2,
        "input_sources": [str(input_file)],
        "source_fingerprint": source_fp,
        "phase_records": [
            {
                "ordinal": 1,
                "phase_name": "Phase 1: Ingestion",
                "status": "completed",
                "duration_seconds": 0.05,
                "reused": True,
                "artifact_counts_by_kind": {"document": 1, "chunk": 2},
            },
            {
                "ordinal": 2,
                "phase_name": "Phase 2: Entity & Relation Extraction",
                "status": "completed",
                "duration_seconds": 0.05,
                "reused": True,
                "artifact_counts_by_kind": {"entity": 4, "local_relation": 3},
            },
        ],
        "config_snapshot": parent_manifest["config_snapshot"],
    }
    (runs_dir / "run-child-200.json").write_text(json.dumps(child_manifest), encoding="utf-8")

    return runs_dir, artifacts_dir, data_dir


def test_artifact_reader_lineage_resolution(mock_run_lineage_workspace: tuple[Path, Path, Path]) -> None:
    """ArtifactReader resolves artifacts across the parent_run_id lineage chain.

    Parameters
    ----------
    mock_run_lineage_workspace : tuple of Path, Path, Path
        Workspace directories containing parent and child runs.

    Returns
    -------
    None
    """
    runs_dir, artifacts_dir, _ = mock_run_lineage_workspace
    reader = ArtifactReader(runs_dir=runs_dir, artifacts_dir=artifacts_dir)

    # Lineage run IDs should include child and parent
    lineage = reader._get_lineage_run_ids("run-child-200")
    assert lineage == ["run-child-200", "run-parent-100"]

    # Child run directory has no files, but reader inherits envelopes from parent
    artifacts = reader.list_artifacts("run-child-200")
    assert len(artifacts) == 2
    artifact_ids = [a.artifact_id for a in artifacts]
    assert "art-doc-1" in artifact_ids
    assert "art-ent-1" in artifact_ids

    # get_run aggregates artifact counts across lineage
    run_detail = reader.get_run("run-child-200")
    assert run_detail is not None
    assert run_detail.parent_run_id == "run-parent-100"
    assert run_detail.artifact_count >= 2


def test_preview_invalidation_forked_run_unchanged(mock_run_lineage_workspace: tuple[Path, Path, Path]) -> None:
    """Previewing invalidation for a forked run with identical inputs results in all-reused.

    Parameters
    ----------
    mock_run_lineage_workspace : tuple of Path, Path, Path
        Workspace directories.

    Returns
    -------
    None
    """
    runs_dir, artifacts_dir, data_dir = mock_run_lineage_workspace
    reader = ArtifactReader(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
    config_service = ConfigService(reader=reader)

    input_file = data_dir / "paper.txt"
    patch = ConfigPatch(
        parent_run_id="run-parent-100",
        source_paths=[str(input_file)],
        patch={},
    )
    preview = config_service.preview_invalidation(patch)

    assert preview.reason == "all-reused"
    assert preview.invalidated_phases == []
    assert len(preview.reused_phases) == 8
    assert preview.estimated_artifact_loss == 0


def test_preview_invalidation_forked_run_source_changed(mock_run_lineage_workspace: tuple[Path, Path, Path]) -> None:
    """Previewing invalidation when source input is changed invalidates from Phase 1 onward.

    Parameters
    ----------
    mock_run_lineage_workspace : tuple of Path, Path, Path
        Workspace directories.

    Returns
    -------
    None
    """
    runs_dir, artifacts_dir, data_dir = mock_run_lineage_workspace
    reader = ArtifactReader(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
    config_service = ConfigService(reader=reader)

    # Different or modified source file
    other_file = data_dir / "other_paper.txt"
    other_file.write_text("Novel philosophical foundations.", encoding="utf-8")

    patch = ConfigPatch(
        parent_run_id="run-parent-100",
        source_paths=[str(other_file)],
        patch={},
    )
    preview = config_service.preview_invalidation(patch)

    assert preview.reason == "source-changed"
    assert 1 in preview.invalidated_phases
    assert preview.reused_phases == []
    assert preview.estimated_artifact_loss > 0


def test_preview_invalidation_forked_run_phase2_config_changed(mock_run_lineage_workspace: tuple[Path, Path, Path]) -> None:
    """Previewing invalidation when phase 2 config changes reuses Phase 1 and invalidates Phase 2+.

    Parameters
    ----------
    mock_run_lineage_workspace : tuple of Path, Path, Path
        Workspace directories.

    Returns
    -------
    None
    """
    runs_dir, artifacts_dir, data_dir = mock_run_lineage_workspace
    reader = ArtifactReader(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
    config_service = ConfigService(reader=reader)

    input_file = data_dir / "paper.txt"
    patch = ConfigPatch(
        parent_run_id="run-parent-100",
        source_paths=[str(input_file)],
        patch={"phase2.linking_confidence_threshold": 0.99},
    )
    preview = config_service.preview_invalidation(patch)

    assert preview.reason.startswith("config-changed")
    assert 1 in preview.reused_phases
    assert 2 in preview.invalidated_phases
    assert preview.invalidated_phases == list(range(2, 9))


def test_preview_invalidation_models_patch_all_reused(mock_run_lineage_workspace: tuple[Path, Path, Path]) -> None:
    """Changes to models.* config alone do not invalidate phases (per D-14).

    Parameters
    ----------
    mock_run_lineage_workspace : tuple of Path, Path, Path
        Workspace directories.

    Returns
    -------
    None
    """
    runs_dir, artifacts_dir, data_dir = mock_run_lineage_workspace
    reader = ArtifactReader(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
    config_service = ConfigService(reader=reader)

    input_file = data_dir / "paper.txt"
    patch = ConfigPatch(
        parent_run_id="run-parent-100",
        source_paths=[str(input_file)],
        patch={"models.llm_model": "claude-3-5-sonnet-20241022"},
    )
    preview = config_service.preview_invalidation(patch)

    assert preview.reason == "all-reused"
    assert preview.invalidated_phases == []
    assert len(preview.reused_phases) == 8
    assert preview.estimated_artifact_loss == 0


@pytest.mark.asyncio
async def test_api_forked_run_lifecycle(mock_run_lineage_workspace: tuple[Path, Path, Path]) -> None:
    """POST /api/config/invalidation-preview and POST /api/runs support parent_run_id.

    Parameters
    ----------
    mock_run_lineage_workspace : tuple of Path, Path, Path
        Workspace directories containing parent and child runs.

    Returns
    -------
    None
    """
    runs_dir, artifacts_dir, data_dir = mock_run_lineage_workspace
    settings = StudioSettings(runs_dir=runs_dir, artifacts_dir=artifacts_dir, demo_mode=True)
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Preview invalidation for parent run
        input_file = data_dir / "paper.txt"
        preview_resp = await client.post(
            "/api/config/invalidation-preview",
            json={
                "parent_run_id": "run-parent-100",
                "source_paths": [str(input_file)],
                "patch": {},
            },
        )
        assert preview_resp.status_code == 200
        preview = preview_resp.json()
        assert preview["reason"] == "all-reused"
        assert preview["invalidated_phases"] == []
        assert len(preview["reused_phases"]) == 8

        # 2. Start a run with parent_run_id
        start_resp = await client.post(
            "/api/runs",
            json={
                "parent_run_id": "run-parent-100",
                "source_paths": [str(input_file)],
                "demo_mode": True,
            },
        )
        assert start_resp.status_code == 201
        run_data = start_resp.json()
        assert run_data["parent_run_id"] == "run-parent-100"
        assert run_data["status"] == "running"

        # Cancel run to clean up
        await client.post(f"/api/runs/{run_data['run_id']}/cancel")

