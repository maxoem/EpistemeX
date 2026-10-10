"""Observability helpers for pipeline runs.

This module keeps Langfuse (or other tracing backends) optional while providing
lightweight utilities to:

- create a run-level root span that groups all LLM/tool calls
- consistently propagate session/environment/tags/metadata
- publish a compact, run-level summary at the end

It is safe to import without Langfuse installed; functions will no-op.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Protocol
from uuid import uuid4

from episteme_pipeline.protocols.tracing import NoOpTraceSink, TraceSpan

try:  # pragma: no cover
    # Optional dependency; guarded to keep the pipeline importable without it
    from langfuse import get_client, propagate_attributes  # type: ignore
except Exception:  # pragma: no cover
    get_client = None  # type: ignore
    propagate_attributes = None  # type: ignore
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RunManifest, RunReport


class RunPublisher(Protocol):
    """Protocol for publishing run reports to observability backends."""
    
    def publish_run(self, report: RunReport, manifest: RunManifest) -> None:
        """Publish a run report to the observability backend."""
        ...


class LangfusePublisher(RunPublisher):
    """Langfuse publisher that creates run-level spans."""
    
    def __init__(self, client):
        """Initialize with a Langfuse client."""
        self.client = client
    
    def publish_run(self, report: RunReport, manifest: RunManifest) -> None:
        """Create a run-level span in Langfuse with optional per-phase spans."""
        try:
            # Create a summary span for the entire run
            with self.client.start_as_current_observation(
                as_type="span",
                name="kg_construction.summary",
                input={"run_id": manifest.run_id, "status": str(report.status)},
            ) as summary_span:
                summary_span.update(
                    output={
                        "by_kind": dict(sorted(report.artifact_counts_by_kind.items())),
                        "total": sum(report.artifact_counts_by_kind.values()),
                    }
                )
            self.client.flush()
        except Exception:
            # Silently fail if Langfuse is not available or misconfigured
            pass


class LangfuseTraceSink:
    """Trace sink that creates Langfuse spans under the active observation."""

    def __init__(self, client: object | None = None) -> None:
        """Initialize the trace sink.

        Parameters
        ----------
        client
            Optional Langfuse client. When omitted, the active global Langfuse
            client is resolved at span creation time.
        """
        self.client = client
        self._fallback = NoOpTraceSink()

    @contextmanager
    def span(
        self,
        *,
        name: str,
        input: dict[str, object] | None = None,
        enabled: bool = True,
    ) -> Iterator[TraceSpan]:
        """Create a Langfuse span if tracing is available.

        Parameters
        ----------
        name
            Observation name shown in Langfuse.
        input
            Optional structured span input.
        enabled
            When ``False``, the context manager no-ops.

        Yields
        ------
        TraceSpan
            Active Langfuse observation or a no-op span.
        """
        if not enabled or get_client is None:
            with self._fallback.span(name=name, input=input, enabled=False) as span:
                yield span
            return

        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            with self._fallback.span(name=name, input=input, enabled=False) as span:
                yield span
            return

        try:
            client = self.client or get_client()  # type: ignore[misc]
            with client.start_as_current_observation(  # type: ignore[attr-defined]
                as_type="span",
                name=name,
                input=input,
            ) as span:
                yield span
        except Exception:
            with self._fallback.span(name=name, input=input, enabled=False) as span:
                yield span


# -------------------- Utility helpers --------------------


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

    - Works only if Langfuse is available and keys are configured; otherwise
      yields a None client and acts as a no-op.
    - Groups all nested spans (e.g., from LlamaIndex/OpenInference) under one
      root. Use together with the LlamaIndex instrumentor.

    Parameters
    - name:     name of the root span (defaults to "pipeline.run")
    - run_id:   used for trace grouping and defaults for session_id
    - session_id: explicit session grouping id; defaults to run_id if provided
    - version:  surfaced in Langfuse for quick run provenance
    - environment: override tracing environment (otherwise uses env var)
    - tags:     list of tags to propagate to descendants
    - metadata: arbitrary metadata propagated to descendants
    """
    if get_client is None:
        # Langfuse not installed
        yield None
        return

    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        # Not configured — behave like a no-op
        yield None
        return

    # Prefer explicit environment over env var
    lf_client = None
    try:
        if environment:
            # Defer import-time reliance on Langfuse symbols
            from langfuse import Langfuse  # type: ignore

            lf_client = Langfuse(environment=environment)  # type: ignore
        else:
            lf_client = get_client()  # type: ignore
    except Exception:
        yield None
        return

    # Root span groups nested instrumentation
    trace_hex = (run_id or uuid4().hex)
    root_ctx = lf_client.start_as_current_observation(
        as_type="span", name=name, trace_context={"trace_id": trace_hex}
    )

    # Propagate common attributes to all children if available
    pa = (
        propagate_attributes(
            session_id=(session_id or run_id),
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


@contextmanager
def phase_span(client: object | None, *, name: str, ordinal: int | None = None) -> Iterator[None]:
    """Convenience context manager for phase boundaries.

    Creates a child span if a Langfuse client is provided; otherwise no-ops.
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
        # Keep observability best-effort only
        yield None
