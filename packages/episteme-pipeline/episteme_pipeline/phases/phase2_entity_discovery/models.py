"""
Pydantic models for LLM-structured output in Phase 2 NER extraction.

These are the LLM-facing schemas — validated at parse time so the pipeline
never propagates a malformed extraction downstream. The models are separate
from the domain models (`pipeline/contracts/domain.py`) because they include LLM-local
IDs (e.g. "e1", "e2") that need to be remapped to stable graph IDs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ExtractedEntity(BaseModel):
    id: str = Field(description="Local extraction ID, e.g. 'e1'. Used only to reference entities in triples.")
    label: str = Field(description="Entity type label.")
    name: str = Field(description="Canonical, normalized entity name.")
    mention_quote: str = Field(description="Exact verbatim quote of the original span text as it appears in the source chunk. Crucial for substring matching.")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Entity name must not be empty")
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.8


class ExtractedTriple(BaseModel):
    subject_id: str = Field(description="References an ExtractedEntity.id.")
    predicate: str = Field(description="Relation type label.")
    object_id: str = Field(description="References an ExtractedEntity.id.")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5


class WorkingMemorySignal(BaseModel):
    """Encapsulates short-term memory state updates and boundary eviction signals."""

    state_delta: dict[str, Any] | None = Field(
        default=None,
        description="Updates to working memory state: active_entities, unresolved_references, current_argument_branch.",
    )
    boundary_detected: bool = Field(
        default=False,
        description="True if the text reaches a logical/argument boundary (sub-chapter end, argument shift).",
    )
    transitional_summary: str | None = Field(
        default=None,
        description="Short 1-2 sentence summary bridge closing the current episode, if boundary_detected is True.",
    )


class NERExtractionOutput(BaseModel):
    """Top-level structured output schema for the NER extraction prompt."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    triples: list[ExtractedTriple] = Field(default_factory=list)
    working_memory: WorkingMemorySignal | None = Field(
        default=None,
        description="Optional working memory state updates and boundary eviction signals.",
    )

    def validate_references(self) -> NERExtractionOutput:
        """
        Removes triples whose subject_id or object_id references a non-existent
        entity. Called after parsing to ensure downstream consistency.
        """
        valid_ids = {e.id for e in self.entities}
        valid_triples = [
            t for t in self.triples
            if t.subject_id in valid_ids and t.object_id in valid_ids
        ]
        return NERExtractionOutput(
            entities=self.entities,
            triples=valid_triples,
            working_memory=self.working_memory,
        )
