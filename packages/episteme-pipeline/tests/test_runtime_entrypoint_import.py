"""Regression tests for the pipeline runtime entry point imports.

The episteme-studio worker imports the pipeline through
``episteme_pipeline.runtime.runner.run_pipeline``. A stale top-level ``phases``
import in the runner previously raised
``ModuleNotFoundError: No module named 'phases'`` because every phase
module lives under the ``episteme_pipeline.phases`` namespace.
"""

from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import re

import episteme_pipeline


def test_all_pipeline_modules_import_without_error():
    """Every module under the ``pipeline`` package must import cleanly.

    Walks the full package tree and imports each submodule, failing on any
    import-time breakage (missing/relocated modules, stale namespaces,
    undeclared optional dependencies, syntax errors, ...). This is the
    general guard that would have caught the original
    ``ModuleNotFoundError: No module named 'phases'`` regardless of which
    entry point triggered it.
    """
    broken: list[tuple[str, str]] = []
    for module in pkgutil.walk_packages(
        episteme_pipeline.__path__, prefix="episteme_pipeline."
    ):
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # noqa: BLE001 - any import-time error is a defect
            broken.append((module.name, f"{type(exc).__name__}: {exc}"))

    assert not broken, (
        f"{len(broken)} episteme_pipeline module(s) failed to import: {broken}"
    )


def test_pipeline_runtime_package_importable():
    """Importing the runtime package must not raise ModuleNotFoundError.

    ``episteme_pipeline.runtime.runner`` is the exact module loaded by the
    episteme-studio worker (``episteme_pipeline.runtime.runner import run_pipeline``).
    """
    runtime = importlib.import_module("episteme_pipeline.runtime")
    assert callable(runtime.run_pipeline)


def test_run_pipeline_importable_from_runner():
    """Direct module import reproduces the reported worker traceback."""
    from episteme_pipeline.runtime.runner import run_pipeline

    assert callable(run_pipeline)


def test_reranker_resolvable_from_canonical_namespace():
    """The reranker used by the runner must live at episteme_pipeline.phases.*.

    ``phases`` is not a top-level package; the symbolic name the runner
    depends on must be reachable under the ``pipeline`` namespace.
    """
    rerankers = importlib.import_module(
        "episteme_pipeline.phases.phase3_global_relations.rerankers"
    )
    assert hasattr(rerankers, "SentenceTransformerCrossEncoderReranker")


def test_runner_has_no_stale_top_level_phases_import():
    """Sources under episteme_pipeline.runtime must not reference a top-level ``phases``.

    Guard against reintroduction of the ``from phases. ...`` style import
    that broke the episteme-studio worker entry point.
    """
    runner_spec = importlib.util.find_spec("episteme_pipeline.runtime.runner")
    assert runner_spec is not None and runner_spec.origin is not None
    with open(runner_spec.origin, encoding="utf-8") as handle:
        source = handle.read()

    offending = [
        line.strip()
        for line in source.splitlines()
        if re.match(r"^\s*(?:from phases\b|import phases\b)", line)
        and not line.lstrip().startswith("#")
    ]
    assert not offending, (
        f"runner.py contains stale top-level 'phases' imports: {offending}"
    )
