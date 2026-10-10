"""
Pydantic models for LLM-structured output in Phase 4 argument mining.

Separate from domain models (`pipeline/contracts/domain.py`) because these carry
LLM-local IDs (e.g. "AC1", "AC2") that need remapping to stable graph IDs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# ADU Segmentation output
# ---------------------------------------------------------------------------


class ADUSegmentationOutput(BaseModel):
    tagged_text: str = Field(description="Full text with <ACn>...</ACn> markup.")
    adu_ids: list[str] = Field(
        default_factory=list,
        description="Ordered list of AC tag IDs found in tagged_text.",
    )


# ---------------------------------------------------------------------------
# ACC Classification output
# ---------------------------------------------------------------------------


class ExtractedComponent(BaseModel):
    id: str = Field(description="AC tag ID, e.g. 'AC1'.")
    component_type: str = Field(
        description="Argument component type. Validated against schema.component_types at runtime.",
    )
    text: str = Field(description="Original span text of this ADU.")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    plausibility: float | None = Field(default=None, ge=0.0, le=1.0, description="Prior plausibility tau of the component.")
    entity_ids: list[str] = Field(default_factory=list, description="List of entity IDs mentioned or discussed in this component.")
    epistemic_status: str | None = Field(default=None, description="Epistemic Status: Synthetisch or Analytisch.")
    scope_type: str | None = Field(default=None, description="Scope / Type of the proposition.")

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ADU text must not be empty")
        return v

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.8

    @field_validator("scope_type", mode="before")
    @classmethod
    def normalize_scope_type(cls, v: Any) -> str | None:
        from episteme_pipeline.contracts.domain import ScopeType
        st = ScopeType.from_str(v)
        return st.value if st is not None else (str(v).strip() if v else None)

    @field_validator("epistemic_status", mode="before")
    @classmethod
    def normalize_epistemic_status(cls, v: Any) -> str | None:
        from episteme_pipeline.contracts.domain import EpistemicStatus
        es = EpistemicStatus.from_str(v)
        return es.value if es is not None else (str(v).strip() if v else None)


class ExtractedTheoryRelation(BaseModel):
    source_id: str = Field(description="References an ExtractedComponent.id.")
    relation: str = Field(
        description="Argument relation type label. Validated against schema.argument_relation_types at runtime."
    )
    target_id: str = Field(description="References an ExtractedComponent.id.")
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    weight: float | None = Field(default=None, ge=0.0, le=1.0, description="Strength weight phi of the relation.")

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5


class ACCOutput(BaseModel):
    components: list[ExtractedComponent] = Field(default_factory=list)
    relations: list[ExtractedTheoryRelation] = Field(default_factory=list)

    def validate_references(self) -> ACCOutput:
        """Remove relations whose source/target references a non-existent component."""
        valid_ids = {c.id for c in self.components}
        valid_relations = [
            r
            for r in self.relations
            if r.source_id in valid_ids and r.target_id in valid_ids
        ]
        return ACCOutput(components=self.components, relations=valid_relations)


# ---------------------------------------------------------------------------
# ARC (Global) output
# ---------------------------------------------------------------------------


class ARCRelationOutput(BaseModel):
    relation_type: str | None = Field(
        default=None,
        description="Argument relation type label, or null. Validated against schema.argument_relation_types at runtime.",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    weight: float | None = Field(default=None, ge=0.0, le=1.0, description="Strength weight phi of the global relation.")
    direction: Literal["A_to_B", "B_to_A"] = "A_to_B"
    reasoning: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5
