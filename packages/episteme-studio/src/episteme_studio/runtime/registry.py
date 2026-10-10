"""In-memory registry tracking run handles and active subprocess lifecycles."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from episteme_studio.domain.errors import ProblemDetail
from episteme_studio.domain.runs import (
    GlobalStructuralAnchor,
    PhaseStatus,
    RunDetail,
    RunStatus,
    RunSummary,
)


class RunHandle(BaseModel):
    """Lifecycle handle for an in-flight or recently completed pipeline run.

    Parameters
    ----------
    run_id : str
        Unique run identifier.
    status : RunStatus
        Current execution status.
    created_at : datetime
        Run initialization timestamp.
    started_at : datetime or None, optional
        Execution start timestamp.
    completed_at : datetime or None, optional
        Execution completion timestamp.
    phase_records : list of PhaseStatus, optional
        Dynamic phase status records.
    failure : ProblemDetail or None, optional
        Failure detail if the run ended in an error.
    config_snapshot : dict of str to Any, optional
        Captured configuration snapshot.
    input_sources : list of str, optional
        Input sources provided for the run.
    bib_sources : list of str, optional
        Bibliography sources provided for the run (.bib).
    metadata : dict of str to str, optional
        Run execution metadata strings.
    structural_anchor : GlobalStructuralAnchor or dict or None, optional
        Structural anchor coordinates.
    models : dict of str to str, optional
        Resolved model identifiers.
    """

    model_config = {"arbitrary_types_allowed": True}

    run_id: str
    status: RunStatus = RunStatus.PLANNED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    phase_records: list[PhaseStatus] = Field(default_factory=list)
    failure: ProblemDetail | None = None
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    input_sources: list[str] = Field(default_factory=list)
    bib_sources: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    structural_anchor: Any | None = None
    models: dict[str, str] = Field(default_factory=dict)
    artifact_counts_by_kind: dict[str, int] = Field(default_factory=dict)
    parent_run_id: str | None = None

    # Runtime process and background task (excluded from serialization)
    process: Any = Field(default=None, exclude=True)
    task: Any = Field(default=None, exclude=True)

    def to_summary(self) -> RunSummary:
        """Convert handle to a RunSummary model.

        Returns
        -------
        RunSummary
            Summary view of this run.
        """
        primary_input = None
        if self.input_sources:
            primary_input = self.input_sources[0].split("/")[-1]

        duration = None
        if self.started_at:
            end = self.completed_at or datetime.now(timezone.utc)
            duration = max(0.0, (end - self.started_at).total_seconds())

        total_arts = sum(p.artifact_count for p in self.phase_records) or sum(self.artifact_counts_by_kind.values())

        anchor_obj = None
        if self.structural_anchor:
            if isinstance(self.structural_anchor, GlobalStructuralAnchor):
                anchor_obj = self.structural_anchor
            elif isinstance(self.structural_anchor, dict):
                anchor_obj = GlobalStructuralAnchor(**self.structural_anchor)

        return RunSummary(
            run_id=self.run_id,
            status=self.status,
            created_at=self.created_at,
            completed_at=self.completed_at,
            duration_seconds=duration,
            pipeline_version="0.1.0",
            schema_version="0.1.0",
            input_sources=self.input_sources,
            bib_sources=self.bib_sources,
            metadata=self.metadata,
            structural_anchor=anchor_obj,
            primary_input=primary_input,
            models=self.models,
            artifact_count=total_arts,
            size_bytes=0,
            tags=[],
            parent_run_id=self.parent_run_id,
        )

    def to_detail(self) -> RunDetail:
        """Convert handle to a full RunDetail view.

        Returns
        -------
        RunDetail
            Full manifest detail with live phase records and failure information.
        """
        summary = self.to_summary()
        return RunDetail(
            **summary.model_dump(),
            phase_records=self.phase_records,
            artifact_counts_by_kind=dict(self.artifact_counts_by_kind),
            graph_schema=self.config_snapshot.get("graph_schema", {}),
            config_snapshot=self.config_snapshot,
            fingerprints={},
            method_fingerprints={},
            unresolved_count=0,
            failure=self.failure,
        )


class RunRegistry:
    """Registry maintaining active and memory-resident pipeline runs."""

    def __init__(self) -> None:
        self._runs: dict[str, RunHandle] = {}
        self._lock = asyncio.Lock()

    def register(self, handle: RunHandle) -> None:
        """Register a new run handle.

        Parameters
        ----------
        handle : RunHandle
            The run handle to register.
        """
        self._runs[handle.run_id] = handle

    def get(self, run_id: str) -> RunHandle | None:
        """Look up a run handle by ID.

        Parameters
        ----------
        run_id : str
            Identifier of the run.

        Returns
        -------
        RunHandle or None
            The handle if found, else None.
        """
        return self._runs.get(run_id)

    def list_all(self) -> list[RunHandle]:
        """List all registered run handles ordered by creation time descending.

        Returns
        -------
        list of RunHandle
            All registered handles.
        """
        return sorted(self._runs.values(), key=lambda h: h.created_at, reverse=True)

    def is_any_active(self) -> bool:
        """Check if any run is currently queued or executing.

        Returns
        -------
        bool
            True if an active run exists, False otherwise.
        """
        return any(h.status in (RunStatus.PLANNED, RunStatus.RUNNING) for h in self._runs.values())

    def get_active_run(self) -> RunHandle | None:
        """Get the currently active run handle if one exists.

        Returns
        -------
        RunHandle or None
            Active run handle, or None.
        """
        for h in self._runs.values():
            if h.status in (RunStatus.PLANNED, RunStatus.RUNNING):
                return h
        return None
