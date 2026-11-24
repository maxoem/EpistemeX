"""Import-sanity tests for the episteme_studio package.

Guards against import-time breakage across the entire studio package,
including the ``episteme_studio.adapters.worker`` entry point that launches the
pipeline in a subprocess (pipeline.py:417). This is the general guard
for the ``ModuleNotFoundError: No module named 'phases'`` failure that
previously surfaced when starting a pipeline from the studio worker: the
studio worker imports ``episteme_pipeline.runtime.runner``, which referenced the
top-level ``phases`` namespace instead of ``episteme_pipeline.phases``.
"""

from __future__ import annotations

import importlib
import pkgutil

import episteme_studio


def test_all_episteme_studio_modules_import_without_error():
    """Every module under the ``episteme_studio`` package must import cleanly.

    Walks the full package tree and imports each submodule, failing on any
    import-time breakage (missing/relocated modules, stale namespaces,
    undeclared dependencies, syntax errors, ...), including the worker
    adapter that bootstraps the pipeline runtime.
    """
    broken: list[tuple[str, str]] = []
    for module in pkgutil.walk_packages(
        episteme_studio.__path__, prefix="episteme_studio."
    ):
        try:
            importlib.import_module(module.name)
        except Exception as exc:  # noqa: BLE001 - any import-time error is a defect
            broken.append((module.name, f"{type(exc).__name__}: {exc}"))

    assert not broken, (
        f"{len(broken)} episteme_studio module(s) failed to import: {broken}"
    )


def test_worker_pipeline_entrypoint_importable():
    """The worker's pipeline entry point must be importable.

    Reproduces the exact import performed by the worker subprocess:
    ``from episteme_pipeline.runtime.runner import run_pipeline``.
    """
    from episteme_studio.adapters.worker import run_pipeline_worker

    assert callable(run_pipeline_worker)
