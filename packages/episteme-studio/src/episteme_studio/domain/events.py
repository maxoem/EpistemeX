"""Domain models for telemetry events streamed over SSE."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StudioEvent(BaseModel):
    """Normalized telemetry event streamed to clients.

    Parameters
    ----------
    seq : int
        Monotonically increasing sequence number per run (used as SSE id).
    run_id : str
        Pipeline run identifier.
    ts : datetime
        Timestamp when the event occurred.
    kind : str
        Normalized event type (e.g. 'phase.started', 'node.extracted'). Open string.
    level : Literal["debug", "info", "warning", "error"], default "info"
        Log severity level.
    phase : str or None, optional
        Phase name context in which the event was emitted.
    message : str or None, optional
        Human-readable event description.
    payload : dict of str to Any, optional
        Structured event data.
    dropped_before : int, default 0
        Count of events dropped from the ring buffer prior to this event.
    """

    seq: int
    run_id: str
    ts: datetime
    kind: str
    level: Literal["debug", "info", "warning", "error"] = "info"
    phase: str | None = None
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    dropped_before: int = 0
