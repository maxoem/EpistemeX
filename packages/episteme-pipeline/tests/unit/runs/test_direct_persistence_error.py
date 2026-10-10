"""Direct test of the FileNotFoundError scenario."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from episteme_pipeline.runs.models import RunManifest, RunStatus
from episteme_pipeline.runs.persistence import JsonRunManifestStore


def test_file_not_found_error_reproduction() -> None:
    """Test that reproduces the FileNotFoundError that occurred in real usage."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # This simulates the exact scenario that caused the error:
        # 1. The .pipeline_runs directory does not exist
        runs_root = Path(temp_dir)
        runs_dir = runs_root / ".pipeline_runs"
        
        # Confirm it does NOT exist yet
        assert not runs_dir.exists()
        
        # 2. Try to write a manifest to a NON-EXISTENT directory
        # This should work due to mkdir(parents=True, exist_ok=True) in __init__
        store = JsonRunManifestStore(runs_dir)
        
        # Now it SHOULD exist
        assert runs_dir.exists()
        
        # Writing should succeed
        manifest = RunManifest(
            run_id="test-run-f12281a0-1267-43fd-8dfa-4c23d9e35789",
            status=RunStatus.COMPLETED,
        )
        
        # This should NOT fail with FileNotFoundError
        path = store.write_manifest(manifest)
        
        # Verify the file was created
        assert path.exists()
        assert path.name == "test-run-f12281a0-1267-43fd-8dfa-4c23d9e35789.json"
        
        # Verify content is readable
        content = path.read_text()
        parsed = json.loads(content)
        assert parsed["run_id"] == "test-run-f12281a0-1267-43fd-8dfa-4c23d9e35789"

