"""Tests for run manifest persistence behavior."""

from __future__ import annotations

import tempfile
from pathlib import Path

from episteme_pipeline.runs.models import RunManifest, RunStatus
from episteme_pipeline.runs.persistence import JsonRunManifestStore


class TestJsonRunManifestStore:
    """Test suite for JsonRunManifestStore."""

    def test_write_manifest_creates_directory_if_missing(self) -> None:
        """Test that write_manifest creates the runs directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / "nonexistent" / ".pipeline_runs"
            # Directory should not exist yet
            assert not runs_dir.exists()
            
            store = JsonRunManifestStore(runs_dir)
            
            # Directory should be created by __init__
            assert runs_dir.exists()
            
            # Create a test manifest
            manifest = RunManifest(run_id="test-run-123")
            
            # Writing should succeed
            path = store.write_manifest(manifest)
            
            # File should exist
            assert path.exists()
            assert path.name == "test-run-123.json"

    def test_write_manifest_with_empty_results(self) -> None:
        """Test writing manifest when pipeline completes with no entities processed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / ".pipeline_runs"
            store = JsonRunManifestStore(runs_dir)
            
            # Create a manifest that represents a successful run with no artifacts
            manifest = RunManifest(
                run_id="empty-run-456",
                status=RunStatus.COMPLETED,
            )
            
            # This should succeed even with "empty" results
            path = store.write_manifest(manifest)
            
            # File should exist
            assert path.exists()
            
            # Should be readable back
            read_manifest = store.read_manifest("empty-run-456")
            assert read_manifest is not None
            assert read_manifest.run_id == "empty-run-456"
            assert read_manifest.status == RunStatus.COMPLETED

