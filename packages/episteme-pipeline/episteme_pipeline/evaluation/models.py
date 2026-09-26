"""Evaluation models for the construction pipeline.

This module provides the minimum viable evaluation scaffolding as described
in `docs/research/evaluation_methodology.md` and `docs/research/evaluation_harness.md`.

Evaluation results are always linked to concrete runs, artifacts, and datasets.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field

from episteme_pipeline.evaluation.comparison import RunComparison


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvaluationLevel(StrEnum):
    COMPONENT = "component"
    STAGE = "stage"
    END_TO_END = "end_to_end"
    DOWNSTREAM = "downstream"


class DatasetType(StrEnum):
    GOLD = "gold"
    SILVER = "silver"
    REVIEW = "review"
    STRESS_TEST = "stress_test"


class EvaluationOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    INCONCLUSIVE = "inconclusive"


class EvaluationMetric(BaseModel):
    """A single scalar metric within an evaluation level."""

    name: str
    value: float
    unit: str = ""
    threshold: float | None = None
    passes_threshold: bool | None = None


class EvaluationErrorBucket(BaseModel):
    """An error class and its count for error analysis."""

    bucket: str
    count: int
    description: str | None = None


class EvaluationResult(BaseModel):
    """Evaluation result for a single evaluation level on a single run."""

    run_id: str
    evaluation_level: EvaluationLevel
    phase_name: str | None = None
    dataset_ref: str | None = None
    dataset_type: DatasetType | None = None
    metrics: list[EvaluationMetric] = Field(default_factory=list)
    error_buckets: list[EvaluationErrorBucket] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)
    outcome: EvaluationOutcome = EvaluationOutcome.INCONCLUSIVE
    evaluated_at: datetime = Field(default_factory=utc_now)


class EvaluationReport(BaseModel):
    """A full evaluation report tied to one or more runs.

    Per methodology.md section 8, every evaluation report must reference:
    - run ID(s),
    - corpus ID,
    - method IDs,
    - prompt IDs,
    - schema snapshot,
    - code version,
    - artifact references.
    """

    evaluation_id: str
    run_ids: list[str]
    dataset_ref: str | None = None
    dataset_type: DatasetType | None = None
    schema_version: str | None = None
    pipeline_version: str | None = None
    results_by_level: dict[str, list[EvaluationResult]] = Field(default_factory=dict)
    pairwise_comparisons: list[RunComparison] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)
