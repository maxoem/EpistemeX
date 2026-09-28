"""Test fixtures and canned demo runs."""

from __future__ import annotations

import importlib.resources
from pathlib import Path

from .demo_run import DEMO_RUN_MANIFEST


def get_fixtures_dir() -> Path:
    """Resolve the packaged fixtures directory.

    Returns
    -------
    Path
        Path to packaged fixtures directory.
    """
    try:
        ref = importlib.resources.files("episteme_studio") / "fixtures"
        return Path(str(ref))
    except Exception:
        return Path(__file__).parent


def get_fixture_runs_dir() -> Path:
    """Resolve directory containing canned demo run manifests.

    Returns
    -------
    Path
        Path to packaged runs directory.
    """
    return get_fixtures_dir() / "runs"


def get_fixture_artifacts_dir() -> Path:
    """Resolve directory containing canned demo artifact envelopes.

    Returns
    -------
    Path
        Path to packaged artifacts directory.
    """
    return get_fixtures_dir() / "artifacts"


def get_fixture_cypher_dir() -> Path:
    """Resolve directory containing canned demo Cypher scripts.

    Returns
    -------
    Path
        Path to packaged cypher directory.
    """
    return get_fixtures_dir() / "cypher"


def get_fixture_reports_dir() -> Path:
    """Resolve directory containing canned demo evaluation reports.

    Returns
    -------
    Path
        Path to packaged reports directory.
    """
    return get_fixtures_dir() / "reports"


__all__ = [
    "DEMO_RUN_MANIFEST",
    "get_fixtures_dir",
    "get_fixture_runs_dir",
    "get_fixture_artifacts_dir",
    "get_fixture_cypher_dir",
    "get_fixture_reports_dir",
]
