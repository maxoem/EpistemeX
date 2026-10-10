"""Reporting utilities for pipeline execution results."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import RunManifest, RunReport


def _outputs(manifest: RunManifest | None) -> dict[str, Any]:
    """
    Where this run actually wrote things, read off the manifest's config snapshot.
    """
    snapshot = getattr(manifest, "config_snapshot", None) or {}
    execution = snapshot.get("execution") or {}
    projected = bool(execution.get("project_artifacts_to_graph", False))
    outputs: dict[str, Any] = {
        "graph": "projected" if projected else "not projected (project_artifacts_to_graph=False)",
    }
    if execution.get("persist_run_manifests", True):
        outputs["runs_dir"] = execution.get("runs_dir")
    outputs["artifacts_dir"] = execution.get("artifacts_dir")
    return {key: value for key, value in outputs.items() if value is not None}


def format_text(report: RunReport | None, manifest: RunManifest | None) -> str:
    """Format a run report as plain text.

    This function is defensive: it works even when ``manifest`` is ``None``
    (e.g., during early prototyping or partial results). In that case it
    derives the ``run_id`` from ``report`` when possible.
    """
    lines: list[str] = []

    # Derive identity safely
    run_id = None
    parent_run_id = None
    if manifest is not None:
        run_id = getattr(manifest, "run_id", None)
        parent_run_id = getattr(manifest, "parent_run_id", None)
    if run_id is None and report is not None:
        run_id = getattr(report, "run_id", None) or getattr(getattr(report, "manifest", None), "run_id", None)

    lines.append("Run completed")
    lines.append(f"  run_id: {run_id or 'unknown'}")
    if parent_run_id:
        lines.append(f"  reused_from: {parent_run_id}")
    if report is not None:
        lines.append(f"  status: {report.status}")
        lines.append(f"  started: {report.started_at}")
        lines.append(f"  completed: {report.completed_at}")
        if report.reused_phase_ordinals:
            lines.append(f"  reused phases: {sorted(report.reused_phase_ordinals)}")
        if report.invalidated_phase_ordinals:
            lines.append(f"  executed phases: {sorted(report.invalidated_phase_ordinals)}")
    else:
        lines.append("  status: unknown")

    if report is not None and report.artifact_counts_by_kind:
        lines.append("\nArtifacts by kind:")
        for kind, count in sorted(report.artifact_counts_by_kind.items()):
            lines.append(f"  {kind}: {count}")

    lines.append("\nOutputs")
    for key, value in _outputs(manifest).items():
        lines.append(f"  {key}: {value}")

    return "\n".join(lines)


def format_markdown(report: RunReport | None, manifest: RunManifest | None) -> str:
    """Format a run report as markdown.

    Handles ``None`` for ``manifest`` and/or ``report`` gracefully.
    """
    lines: list[str] = []

    # Derive identity safely
    run_id = None
    parent_run_id = None
    if manifest is not None:
        run_id = getattr(manifest, "run_id", None)
        parent_run_id = getattr(manifest, "parent_run_id", None)
    if run_id is None and report is not None:
        run_id = getattr(report, "run_id", None) or getattr(getattr(report, "manifest", None), "run_id", None)

    lines.append("# Run Report")
    lines.append("")
    lines.append(f"- **Run ID**: `{run_id or 'unknown'}`")
    if parent_run_id:
        lines.append(f"- **Reused From**: `{parent_run_id}`")
    if report is not None:
        lines.append(f"- **Status**: `{report.status}`")
        lines.append(f"- **Started**: `{report.started_at}`")
        lines.append(f"- **Completed**: `{report.completed_at}`")
        if report.reused_phase_ordinals:
            lines.append(f"- **Reused Phases**: `{sorted(report.reused_phase_ordinals)}`")
        if report.invalidated_phase_ordinals:
            lines.append(f"- **Executed Phases**: `{sorted(report.invalidated_phase_ordinals)}`")
    else:
        lines.append("- **Status**: `unknown`")

    if report is not None and report.artifact_counts_by_kind:
        lines.append("")
        lines.append("## Artifacts by Kind")
        lines.append("")
        for kind, count in sorted(report.artifact_counts_by_kind.items()):
            lines.append(f"- `{kind}`: {count}")

    lines.append("")
    lines.append("## Outputs")
    for key, value in _outputs(manifest).items():
        lines.append(f"- `{key}`: {value}")

    return "\n".join(lines)


def format_json(report: RunReport | None, manifest: RunManifest | None) -> dict:
    """Format a run report as a JSON-serializable dictionary.

    Works when ``manifest`` and/or ``report`` are ``None`` by filling
    sensible defaults.
    """
    run_id = None
    parent_run_id = None
    if manifest is not None:
        run_id = getattr(manifest, "run_id", None)
        parent_run_id = getattr(manifest, "parent_run_id", None)
    if run_id is None and report is not None:
        run_id = getattr(report, "run_id", None) or getattr(getattr(report, "manifest", None), "run_id", None)

    status = getattr(report, "status", None)
    started_at = getattr(report, "started_at", None)
    completed_at = getattr(report, "completed_at", None)
    reused = getattr(report, "reused_phase_ordinals", []) or []
    executed = getattr(report, "invalidated_phase_ordinals", []) or []
    by_kind = getattr(report, "artifact_counts_by_kind", {}) or {}

    return {
        "run_id": run_id,
        "parent_run_id": parent_run_id,
        "status": status,
        "started_at": started_at.isoformat() if started_at else None,
        "completed_at": completed_at.isoformat() if completed_at else None,
        "reused_phases": sorted(reused),
        "executed_phases": sorted(executed),
        "artifacts_by_kind": dict(sorted(by_kind.items())),
        "outputs": _outputs(manifest),
    }
