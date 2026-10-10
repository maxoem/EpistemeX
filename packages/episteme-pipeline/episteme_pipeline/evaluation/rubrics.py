"""Evaluation rubrics for human review workflows.

Described in docs/evaluation/methodology.md section 9. Each rubric
defines a structured rating system that domain experts can apply to
pipeline artifacts from specific runs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class RatingLevel(BaseModel):
    """A single rating level in a rubric scale."""

    level: str
    label: str
    description: str
    score: float


class RubricCriterion(BaseModel):
    """A single criterion within a human review rubric."""

    name: str
    description: str
    levels: list[RatingLevel] = Field(default_factory=list)


class EvaluationJudgment(BaseModel):
    """A single judgment recorded by a human reviewer.

    Linked to an artifact ref, following the rubric, with the
    chosen level and any free-text notes.
    """

    artifact_ref: str
    rubric: str
    criterion: str
    level: str
    score: float
    reviewer_id: str = ""
    run_id: str = ""
    notes: str = ""
    judged_at: datetime = Field(default_factory=utc_now)


class EvaluationRubric(BaseModel):
    """A reusable human-review rubric tied to an evaluation level.

    For example, "Global Relation Quality" or "Theory-Layer Output Quality"
    as called out in docs/evaluation/methodology.md section 13.
    """

    rubric_id: str
    name: str
    description: str = ""
    evaluation_level: str = ""
    criteria: list[RubricCriterion] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
