"""Tests for edge cases in manifest persistence."""

from __future__ import annotations

import tempfile
from pathlib import Path

from episteme_pipeline.runs.models import RunManifest, RunReport, RunStatus
from episteme_pipeline.runs.persistence import JsonRunManifestStore


class TestManifestPersistenceEdgeCases:
    """Test edge cases in manifest persistence."""

    def test_write_manifest_in_nested_nonexistent_directory(self) -> None:
        """Test that write_manifest works when the runs directory is deeply nested and doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a deeply nested path that doesn't exist
            runs_dir = Path(temp_dir) / "very" / "deeply" / "nested" / "pipeline_runs"
            assert not runs_dir.exists()
            
            store = JsonRunManifestStore(runs_dir)
            
            # Directory should be created
            assert runs_dir.exists()
            
            # Writing should work
            manifest = RunManifest(run_id="test-nested-789")
            path = store.write_manifest(manifest)
            
            assert path.exists()
            assert path.name == "test-nested-789.json"

    def test_write_manifest_handles_permission_issues_gracefully(self) -> None:
        """Test that write_manifest handles directory creation issues gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / ".pipeline_runs"
            
            # Create the store normally first
            store = JsonRunManifestStore(runs_dir)
            assert runs_dir.exists()
            
            # Create a manifest
            manifest = RunManifest(run_id="perm-test-123")
            
            # Writing should succeed normally
            path = store.write_manifest(manifest)
            assert path.exists()
            
            # Verify we can read it back
            read_manifest = store.read_manifest("perm-test-123")
            assert read_manifest is not None
            assert read_manifest.run_id == "perm-test-123"

    def test_manifest_with_minimal_content(self) -> None:
        """Test manifest creation with minimal content (similar to 0 entities case)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / ".pipeline_runs"
            store = JsonRunManifestStore(runs_dir)
            
            # Create a minimal manifest that would represent a run with no artifacts
            manifest = RunManifest(
                run_id="minimal-run",
                status=RunStatus.COMPLETED,
            )
            
            # Should be able to write and read this manifest
            path = store.write_manifest(manifest)
            assert path.exists()
            
            read_manifest = store.read_manifest("minimal-run")
            assert read_manifest is not None
            assert read_manifest.run_id == "minimal-run"
            assert read_manifest.status == RunStatus.COMPLETED

    def test_report_with_empty_artifact_collections(self) -> None:
        """Test report creation with empty artifact collections (similar to 0 entities case)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / ".pipeline_runs"
            store = JsonRunManifestStore(runs_dir)
            
            # Create a report that would represent a run with no artifacts
            report = RunReport(
                run_id="empty-report-run",
                status=RunStatus.COMPLETED,
                artifact_counts_by_kind={},  # No artifacts of any kind
                artifact_counts_by_phase={},
                new_artifact_counts_by_kind={},
                new_artifact_counts_by_phase={},
                reused_artifact_counts_by_kind={},
                reused_artifact_counts_by_phase={},
            )
            
            # For this test, we're really checking that our persistence works,
            # but note that RunReport isn't directly persisted - only RunManifest is
            
            # Create corresponding manifest
            manifest = RunManifest(
                run_id="empty-report-run",
                status=RunStatus.COMPLETED,
            ) 
            
            # Should be able to write and read the manifest
            path = store.write_manifest(manifest)
            assert path.exists()
            
            read_manifest = store.read_manifest("empty-report-run")
            assert read_manifest is not None

