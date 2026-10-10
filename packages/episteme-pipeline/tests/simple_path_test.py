#!/usr/bin/env python3
"""Simple test for path creation without dependencies."""

import os
import tempfile
from pathlib import Path


def test_path_creation():
    """Test if directories are created properly."""
    
    print("Testing path creation scenario...")
    
    # Create a temporary directory to simulate the working directory
    original_cwd = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Working in temporary directory: {temp_dir}")
            os.chdir(temp_dir)
            
            # Test the exact pattern that had issues:
            # 1. Relative path that doesn't exist
            runs_dir = Path("../.pipeline_runs")
            print(f"Path exists before: {runs_dir.exists()}")
            
            # 2. Create directory with parents=True
            runs_dir.mkdir(parents=True, exist_ok=True)
            print(f"Path exists after mkdir: {runs_dir.exists()}")
            
            # 3. Try to create a file in it
            run_file = runs_dir / "test-run-123.json"
            try:
                run_file.write_text('{"test": "data"}')
                print(f"File created successfully: {run_file.exists()}")
                print("SUCCESS: No FileNotFoundError!")
                return True
            except Exception as e:
                print(f"ERROR: {e}")
                return False
    finally:
        os.chdir(original_cwd)

if __name__ == "__main__":
    success = test_path_creation()
    if success:
        print("\n✅ Path creation works fine - the issue might be elsewhere")
    else:
        print("\n❌ Path creation failed")
