"""
Pydantic models for LLM-structured output in Phase 4 argument mining.

Separate from domain models (`pipeline/contracts/domain.py`) because these carry
LLM-local IDs (e.g. "AC1", "AC2") that need remapping to stable graph IDs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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
    plausibility: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Prior plausibility tau of the component.",
    )
    entity_ids: list[str] = Field(
        default_factory=list,
        description="List of entity IDs mentioned or discussed in this component.",
    )
    epistemic_status: str | None = Field(
        default=None, description="Epistemic Status: Synthetisch or Analytisch."
    )
    scope_type: str | None = Field(
        default=None, description="Scope / Type of the proposition."
    )
    intensional_mode: Literal[
        "asserted", "attributed", "suppositional", "historical"
    ] = Field(
        default="asserted",
        description="Intensional context mode: 'asserted', 'attributed', 'suppositional', or 'historical'.",
    )
    attributed_to: str | None = Field(
        default=None,
        description="Agent, author, or school identifier when intensional_mode is 'attributed'.",
    )

    @field_validator("intensional_mode", mode="before")
    @classmethod
    def normalize_intensional_mode(
        cls, v: Any
    ) -> Literal["asserted", "attributed", "suppositional", "historical"]:
        """Normalize intensional_mode via IntensionalMode enum."""
        from episteme_pipeline.contracts.domain import IntensionalMode

        norm = IntensionalMode.from_str(v).value
        if norm == "attributed":
            return "attributed"
        if norm == "suppositional":
            return "suppositional"
        if norm == "historical":
            return "historical"
        return "asserted"

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
    """LLM-extracted local dialectical relation or multi-premise inference."""

    id: str | None = Field(
        default=None,
        description="Optional local identifier for the relation (e.g. 'R1') so undercutters/backings can reference it.",
    )
    source_id: str = Field(
        default="",
        description="References primary premise ExtractedComponent.id.",
    )
    premise_ids: list[str] = Field(
        default_factory=list,
        description="Optional ordered list of conjunctive premise IDs (e.g. ['AC1', 'AC2']).",
    )
    relation: str = Field(
        description="Argument relation type label. Validated against schema.argument_relation_types at runtime."
    )
    target_id: str = Field(
        default="",
        description="References target ExtractedComponent.id (or relation ID for undercutters/backings).",
    )
    undercuts_relation_id: str | None = Field(
        default=None,
        description="Optional target local relation ID (e.g. 'R1') when acting as an undercutting defeater.",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    weight: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Strength weight phi of the relation."
    )

    @model_validator(mode="after")
    def normalize_hyperedge_refs(self) -> ExtractedTheoryRelation:
        """Normalize conjunctive ``premise_ids`` and undercutter target references."""
        if self.premise_ids:
            seen: set[str] = set()
            cleaned: list[str] = []
            for pid in self.premise_ids:
                p_str = str(pid).strip()
                if p_str and p_str not in seen:
                    seen.add(p_str)
                    cleaned.append(p_str)
            self.premise_ids = cleaned
            if not self.source_id and self.premise_ids:
                self.source_id = self.premise_ids[0]
        if self.undercuts_relation_id is not None:
            u_str = str(self.undercuts_relation_id).strip()
            self.undercuts_relation_id = u_str or None
        if not self.target_id and self.undercuts_relation_id:
            self.target_id = self.undercuts_relation_id
        return self

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
        """Remove relations whose source, conjunctive premises, or target references do not exist."""
        valid_atom_ids = {c.id for c in self.components}
        prelim: list[ExtractedTheoryRelation] = []
        for r in self.relations:
            eff_premises = (
                r.premise_ids
                if r.premise_ids
                else ([r.source_id] if r.source_id else [])
            )
            if eff_premises and all(pid in valid_atom_ids for pid in eff_premises):
                prelim.append(r)

        valid_relations: list[ExtractedTheoryRelation] = []
        valid_rel_ids: set[str] = set()
        remaining = prelim
        while remaining:
            progressed = False
            next_remaining: list[ExtractedTheoryRelation] = []
            valid_targets = valid_atom_ids | valid_rel_ids
            for r in remaining:
                target_ok = r.target_id in valid_targets
                undercut_ok = (
                    r.undercuts_relation_id is None
                    or r.undercuts_relation_id in valid_rel_ids
                )
                if target_ok and undercut_ok:
                    valid_relations.append(r)
                    if r.id:
                        valid_rel_ids.add(r.id)
                    progressed = True
                else:
                    next_remaining.append(r)
            if not progressed:
                break
            remaining = next_remaining
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
    weight: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Strength weight phi of the global relation.",
    )
    direction: Literal["A_to_B", "B_to_A"] = "A_to_B"
    reasoning: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.5
