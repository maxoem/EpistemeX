"""Langfuse adapter and context utilities for pipeline runs.

This module provides Langfuse integration for pipeline runs, acting as an adapter
between domain events and Langfuse observations. It creates run-level root
observations that group all phase and LLM calls, and propagates session/environment
attributes to descendant observations.

Functions will safely no-op if Langfuse is not installed or configured.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Protocol
from uuid import uuid4

try:  # pragma: no cover
    # Optional dependency; guarded to keep the pipeline importable without it
    from langfuse import get_client, propagate_attributes  # type: ignore
except Exception:  # pragma: no cover
    get_client = None  # type: ignore
    propagate_attributes = None  # type: ignore

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import RunManifest, RunReport


class RunPublisher(Protocol):
    """Protocol for publishing run reports to observability backends."""

    def publish_run(self, report: RunReport, manifest: RunManifest | None) -> None:
        """Publish a run report to the observability backend.

        Parameters
        ----------
        report : RunReport
            Run execution report.
        manifest : RunManifest, optional
            Run manifest containing metadata and configuration fingerprints.
        """
        ...


class LangfusePublisher(RunPublisher):
    """Langfuse publisher that creates run-level spans and records evaluation metrics.

    Parameters
    ----------
    client : Any
        Langfuse client instance.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    def publish_run(self, report: RunReport, manifest: RunManifest | None) -> None:
        """Create a summary span and publish run-level scores to Langfuse.

        Parameters
        ----------
        report : RunReport
            Execution report for the completed run.
        manifest : RunManifest, optional
            Execution manifest.
        """
        if not self.client:
            return

        run_id = getattr(manifest, "run_id", None) or getattr(report, "run_id", None)
        status_str = str(getattr(report, "status", "unknown"))

        try:
            with self.client.start_as_current_observation(
                as_type="span",
                name="kg_construction.summary",
                input={
                    "run_id": run_id,
                    "status": status_str,
                },
            ) as summary_span:
                artifact_counts = getattr(report, "artifact_counts_by_kind", {})
                phase_counts = getattr(report, "artifact_counts_by_phase", {})
                reused_counts = getattr(report, "reused_artifact_counts_by_kind", {})
                summary_span.update(
                    output={
                        "by_kind": dict(sorted(artifact_counts.items())),
                        "by_phase": dict(sorted(phase_counts.items())),
                        "reused_by_kind": dict(sorted(reused_counts.items())),
                        "total_artifacts": sum(artifact_counts.values()),
                        "total_reused": sum(reused_counts.values()),
                    }
                )

            # Publish quality scores if available
            trace_id = None
            if run_id:
                trace_id = hashlib.md5(run_id.encode("utf-8")).hexdigest()

            if hasattr(self.client, "create_score") and trace_id:
                self.client.create_score(
                    trace_id=trace_id,
                    name="pipeline_total_artifacts",
                    value=float(sum(artifact_counts.values())),
                    comment=f"Run status: {status_str}",
                )

            self.client.flush()
        except Exception:
            # Silently ignore errors to ensure best-effort tracing
            pass


@contextmanager
def phase_span(client: object | None, *, name: str, ordinal: int | None = None) -> Iterator[None]:
    """Convenience context manager for phase boundaries.

    Parameters
    ----------
    client : object, optional
        Langfuse client instance.
    name : str
        Name of the phase span.
    ordinal : int, optional
        Ordinal position of the phase in the pipeline.

    Yields
    ------
    None
    """
    if not client:
        yield None
        return

    try:
        with client.start_as_current_observation(  # type: ignore[attr-defined]
            as_type="span",
            name=name,
            input={"phase_ordinal": ordinal} if ordinal is not None else None,
        ):
            yield None
    except Exception:
        yield None


@contextmanager
def run_observability_context(
    *,
    name: str = "pipeline.run",
    run_id: str | None = None,
    session_id: str | None = None,
    version: str | None = None,
    environment: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> Iterator[object | None]:
    """Create a root observation and propagate common attributes.

    Groups all nested spans and generations (e.g., from phase runners, components,
    and LLMs) under one root trace, and tags them with a searchable session_id.

    Parameters
    ----------
    name : str, default="pipeline.run"
        Name of the root span.
    run_id : str, optional
        Used for trace grouping and defaults for session_id if omitted.
    session_id : str, optional
        Explicit session grouping ID for Langfuse sessions. Defaults to run_id.
    version : str, optional
        Surfaced in Langfuse for run provenance and versioning.
    environment : str, optional
        Override tracing environment (e.g., "production", "development").
    tags : list of str, optional
        List of tags to propagate to descendants.
    metadata : dict, optional
        Arbitrary metadata propagated to descendants.

    Yields
    ------
    object or None
        Active Langfuse client instance, or None if Langfuse is unavailable.
    """
    if get_client is None:
        yield None
        return

    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        yield None
        return

    lf_client = None
    try:
        if environment:
            from langfuse import Langfuse  # type: ignore

            lf_client = Langfuse(environment=environment)  # type: ignore
        else:
            lf_client = get_client()  # type: ignore
    except Exception:
        yield None
        return

    resolved_session_id = session_id or run_id
    trace_hex = hashlib.md5(run_id.encode("utf-8")).hexdigest() if run_id else uuid4().hex

    root_ctx = lf_client.start_as_current_observation(
        as_type="span",
        name=name,
        trace_context={"trace_id": trace_hex},
        input={"run_id": run_id, "session_id": resolved_session_id},
    )

    pa = (
        propagate_attributes(
            session_id=resolved_session_id,
            version=version,
            metadata={"tags": tags or []} | (metadata or {}),
        )
        if propagate_attributes is not None
        else nullcontext()
    )

    try:
        with root_ctx, pa:
            yield lf_client
    finally:
        try:
            lf_client.flush()
        except Exception:
            pass


class LangfuseTraceSink:
    """DEPRECATED: Backward compatible trace sink that wraps Langfuse functionality."""

    def __init__(self, client: object | None = None) -> None:
        """Initialize the trace sink."""
        self.client = client

    @contextmanager
    def span(
        self, *, name: str, input: dict[str, object] | None = None, enabled: bool = True
    ) -> Iterator[object]:
        """DEPRECATED: Create a Langfuse span for backward compatibility."""
        if not enabled or get_client is None:
            yield None
            return

        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            yield None
            return

        try:
            client = self.client or get_client()
            with client.start_as_current_observation(as_type="span", name=name, input=input) as span:
                yield span
        except Exception:
            yield None
