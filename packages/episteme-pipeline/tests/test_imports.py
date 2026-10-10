#!/usr/bin/env python3
"""Test script to verify imports work."""

try:
    from episteme_pipeline.events.bus import SimpleEventEmitter
    print("✓ SimpleEventEmitter imported successfully")
except ImportError as e:
    print(f"✗ Failed to import SimpleEventEmitter: {e}")

try:
    from episteme_pipeline.events.models import DenseCandidatesGenerated
    print("✓ DenseCandidatesGenerated imported successfully")
except ImportError as e:
    print(f"✗ Failed to import DenseCandidatesGenerated: {e}")

try:
    from episteme_pipeline.events.observers import (
        JsonlRunObserver,
        LoggingObserver,
        MetricsObserver,
    )
    print("✓ Observers imported successfully")
except ImportError as e:
    print(f"✗ Failed to import observers: {e}")

try:
    from episteme_pipeline.events.langfuse_observer import LangfuseObserver
    print("✓ LangfuseObserver imported successfully")
except ImportError as e:
    print(f"✗ Failed to import LangfuseObserver: {e}")
    
print("Import tests complete.")
