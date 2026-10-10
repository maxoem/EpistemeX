#!/usr/bin/env python3
"""Smoke test for the example script to verify all imports work."""

import sys

sys.path.insert(0, '..')

def test_imports():
    """Test that all example script imports work.""" 
    
    print("Testing example script imports...")
    
    # Core imports from example 
    from episteme_pipeline.runs.models import RunManifest, RunReport, RunStatus
    from episteme_pipeline.runs.observability import LangfusePublisher
    from episteme_pipeline.runs.reporting import (
        format_json,
        format_markdown,
        format_text,
    )
    
    # Verify functions exist
    assert callable(format_text)
    assert callable(format_markdown)
    assert callable(format_json)
    assert callable(LangfusePublisher)
    
    print("✅ All imports successful")
    
    # Test basic functionality 
    manifest = RunManifest(run_id="smoke-test", status=RunStatus.COMPLETED)
    report = RunReport(
        manifest=manifest,
        run_id="smoke-test",
        status=RunStatus.COMPLETED
    )
    
    text_result = format_text(report, manifest)
    assert "smoke-test" in text_result
    assert "completed" in text_result
    
    print("✅ Basic functionality works")
    
    return True

if __name__ == "__main__":
    try:
        success = test_imports()
        if success:
            print("\n🎉 Smoke test PASSED!")
            print("✅ Example script components are working correctly")
        else:
            print("\n❌ Smoke test FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Smoke test FAILED with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
