#!/usr/bin/env python3
"""Standalone test to reproduce and verify the FileNotFoundError issue."""

import json
import os

# Import our models and persistence
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, '..')

from episteme_pipeline.runs.models import RunManifest, RunStatus
from episteme_pipeline.runs.persistence import JsonRunManifestStore


def test_file_creation_scenario():
    """Test the exact scenario that caused the FileNotFoundError."""
    
    print("Testing manifest persistence with realistic scenario...")
    
    # Create a temporary directory to simulate the working directory
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            print(f"Working in temporary directory: {temp_dir}")
            
            # This simulates what happens in a real run:
            # 1. The .pipeline_runs directory doesn't exist initially
            runs_dir = Path("../.pipeline_runs")
            print(f"Runs directory exists before: {runs_dir.exists()}")
            
            # 2. Create a store (this should create the directory)
            store = JsonRunManifestStore(str(runs_dir))
            print(f"Runs directory exists after store init: {runs_dir.exists()}")
            
            # 3. Create a manifest for an "empty" run (like when no entities are found)
            run_id = f"run-{uuid4()}"
            manifest = RunManifest(
                run_id=run_id,
                status=RunStatus.COMPLETED,
            )
            
            # 4. Write the manifest (this is where the FileNotFoundError occurred)
            print("Attempting to write manifest...")
            try:
                path = store.write_manifest(manifest)
                print(f"SUCCESS: Manifest written to {path}")
                
                # 5. Verify the file exists and is readable
                assert path.exists(), "Manifest file should exist"
                content = path.read_text()
                parsed = json.loads(content)
                assert parsed["run_id"] == run_id, "Run ID should match"
                print("SUCCESS: Manifest file is readable and correct")
                
                return True
                
            except Exception as e:
                print(f"ERROR: Failed to write manifest: {e}")
                print(f"Error type: {type(e).__name__}")
                return False
    finally:
        os.chdir(original_cwd)

def test_multiple_writes():
    """Test multiple writes to ensure no race conditions."""
    
    print("\nTesting multiple concurrent writes...")
    
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.chdir(temp_dir)
            
            runs_dir = Path("../.pipeline_runs")
            store = JsonRunManifestStore(str(runs_dir))
            
            # Write multiple manifests rapidly
            success_count = 0
            for i in range(5):
                run_id = f"run-concurrent-{i}-{uuid4()}"
                manifest = RunManifest(
                    run_id=run_id,
                    status=RunStatus.COMPLETED,
                )
                
                try:
                    path = store.write_manifest(manifest)
                    assert path.exists()
                    success_count += 1
                    print(f"  Write {i+1}: SUCCESS")
                except Exception as e:
                    print(f"  Write {i+1}: FAILED - {e}")
                    
            print(f"Successfully wrote {success_count}/5 manifests")
            return success_count == 5
    finally:
        os.chdir(original_cwd)

if __name__ == "__main__":
    print("=== Testing Persistence Issue ===")
    
    success1 = test_file_creation_scenario()
    success2 = test_multiple_writes()
    
    if success1 and success2:
        print("\n✅ ALL TESTS PASSED - The FileNotFoundError issue appears to be resolved!")
    else:
        print("\n❌ SOME TESTS FAILED - The issue may still exist")
        
    print("\nNote: If you're still seeing FileNotFoundError in examples/, that might be")
    print("due to a different issue such as path resolution in your specific setup.")
