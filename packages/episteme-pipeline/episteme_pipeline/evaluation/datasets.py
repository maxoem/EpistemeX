"""Evaluation dataset scaffolding.

Supports the four dataset types described in docs/evaluation/methodology.md:
gold, silver, review, and stress-test.

Each dataset is a reference to a collection of evaluation artifacts (gold
standards, review samples, etc.) that can be linked to evaluation reports.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class DatasetReference(BaseModel):
    """Reference to an evaluation dataset on disk or in storage.

    Evaluations are always linked to a concrete dataset identified by ID.
    The reference points to where the dataset lives and what it contains.
    """

    dataset_id: str
    dataset_type: str  # gold | silver | review | stress_test
    source_paths: list[str] = Field(default_factory=list)
    schema_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class EvaluationDataset(BaseModel):
    """Describes a named evaluation dataset for reproducible evaluation.

    Tied to a specific corpus, schema, and set of artifact references
    that a reviewer or automated scorer can use to assess pipeline output.
    """

    dataset_id: str
    name: str
    description: str = ""
    dataset_type: str  # gold | silver | review | stress_test
    corpus_ref: str | None = None
    schema_version: str | None = None
    pipeline_version: str | None = None
    references: list[DatasetReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
