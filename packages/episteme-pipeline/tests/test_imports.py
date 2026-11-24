#!/usr/bin/env python3
"""Test script to verify imports work."""  # noqa: EXE001 baseline

try:
    from episteme_pipeline.events.bus import SimpleEventEmitter  # noqa: F401 baseline

    print("✓ SimpleEventEmitter imported successfully")
except ImportError as e:
    print(f"✗ Failed to import SimpleEventEmitter: {e}")

try:
    from episteme_pipeline.events.models import DenseCandidatesGenerated  # noqa: F401 baseline

    print("✓ DenseCandidatesGenerated imported successfully")
except ImportError as e:
    print(f"✗ Failed to import DenseCandidatesGenerated: {e}")

try:
    from episteme_pipeline.events.observers import (
        JsonlRunObserver,  # noqa: F401 baseline
        LoggingObserver,  # noqa: F401 baseline
        MetricsObserver,  # noqa: F401 baseline
    )

    print("✓ Observers imported successfully")
except ImportError as e:
    print(f"✗ Failed to import observers: {e}")

try:
    from episteme_pipeline.events.langfuse_observer import LangfuseObserver  # noqa: F401 baseline

    print("✓ LangfuseObserver imported successfully")
except ImportError as e:
    print(f"✗ Failed to import LangfuseObserver: {e}")

print("Import tests complete.")
