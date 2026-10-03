"""Run metadata models for explicit pipeline execution state."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class RunPhaseRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    phase_name: str
    phase_ordinal: int = Field(alias="ordinal")
    status: RunStatus = RunStatus.PLANNED
    started_at: datetime | None = None
    completed_at: datetime | None = None
    config_fingerprint: str | None = None
    input_fingerprint: str | None = None
    output_fingerprint: str | None = None
    reused: bool = False
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)


class RunManifest(BaseModel):
    run_id: str
    pipeline_version: str = "0.1.0"
    schema_version: str | None = None
    status: RunStatus = RunStatus.PLANNED
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    source_fingerprint: str | None = None
    input_fingerprint: str | None = None
    input_fingerprint_inputs: dict[str, object] = Field(default_factory=dict)
    config_fingerprint: str | None = None
    method_fingerprints: dict[str, str] = Field(default_factory=dict)
    prompts_fingerprints: dict[str, str] = Field(default_factory=dict)
    phase_config_fingerprints: dict[str, object] = Field(default_factory=dict)
    config_snapshot: dict[str, object] = Field(default_factory=dict)
    input_sources: list[str] = Field(default_factory=list)
    phase_records: list[RunPhaseRecord] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    parent_run_id: str | None = None
    decision_metrics: dict[str, object] | None = None


class ResumePoint(BaseModel):
    run_id: str | None = None
    phase_ordinal: int | None = None
    phase_name: str | None = None


class InvalidationDecision(BaseModel):
    resume_point: ResumePoint
    reused_phase_ordinals: list[int] = Field(default_factory=list)
    invalidated_phase_ordinals: list[int] = Field(default_factory=list)
    reason: str = ""


class ArtifactReportEntry(BaseModel):
    artifact_id: str
    identity_key: str
    kind: str
    phase_name: str
    run_id: str | None = None
    reused: bool = False


class RunReport(BaseModel):
    manifest: RunManifest | None = None
    run_id: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: RunStatus = RunStatus.PLANNED
    phase_records: list[RunPhaseRecord] = Field(default_factory=list)
    artifact_counts_by_kind: dict[str, int] = Field(default_factory=dict)
    artifact_counts_by_phase: dict[str, int] = Field(default_factory=dict)
    new_artifact_counts_by_kind: dict[str, int] = Field(default_factory=dict)
    new_artifact_counts_by_phase: dict[str, int] = Field(default_factory=dict)
    reused_artifact_counts_by_kind: dict[str, int] = Field(default_factory=dict)
    reused_artifact_counts_by_phase: dict[str, int] = Field(default_factory=dict)
    reused_phase_ordinals: list[int] = Field(default_factory=list)
    invalidated_phase_ordinals: list[int] = Field(default_factory=list)
    invalidation_reason: str | None = None
    artifact_entries: list[ArtifactReportEntry] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    manifest: RunManifest
    report: RunReport
