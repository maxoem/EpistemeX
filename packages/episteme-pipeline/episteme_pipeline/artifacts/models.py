"""Run-scoped artifact models for the target research-library architecture.

These models intentionally do not replace the current domain models yet.
They provide a first architecture-facing scaffold for the artifact/run model
described in `docs/architecture/artifact_run_model.md` and `docs/architecture/overview.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

from episteme_pipeline.contracts.domain import GlobalStructuralAnchor


def utc_now() -> datetime:
    return datetime.now(UTC)


class ArtifactKind(StrEnum):
    DOCUMENT = "document"
    CHUNK = "chunk"
    ENTITY_MENTION = "entity_mention"
    LINKED_ENTITY = "linked_entity"
    LOCAL_RELATION = "local_relation"
    GLOBAL_RELATION = "global_relation"
    THEORY_ATOM = "theory_atom"
    THEORY_RELATION = "theory_relation"
    FUSION_DECISION = "fusion_decision"
    CANONICALIZATION = "canonicalization"
    THEORETICAL_ENRICHMENT = "theoretical_enrichment"


class ArtifactRef(BaseModel):
    artifact_id: str
    kind: ArtifactKind
    run_id: str
    phase_name: str


class ArtifactProvenance(BaseModel):
    source_path: str | None = None
    source_document_id: str | None = None
    source_chunk_id: str | None = None
    upstream_artifact_ids: list[str] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)


class DocumentArtifact(BaseModel):
    document_id: str
    title: str
    source_path: str
    structural_anchor: GlobalStructuralAnchor | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=utc_now)


class ChunkArtifact(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    sequence_index: int
    chapter_id: str | None = None
    token_count: int


class EntityMentionArtifact(BaseModel):
    mention_id: str
    chunk_id: str
    surface_form: str
    entity_type: str
    start_char: int | None = None
    end_char: int | None = None
    confidence: float | None = None


class LinkedEntityArtifact(BaseModel):
    entity_id: str
    canonical_name: str
    entity_type: str
    mention_ids: list[str] = Field(default_factory=list)
    description: str | None = None
    textual_envelope: str | None = None
    is_mature: bool = False
    confidence: float | None = None


class LocalRelationArtifact(BaseModel):
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    source_chunk_id: str
    confidence: float
    scope: Literal["local"] = "local"


class GlobalRelationArtifact(BaseModel):
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float
    rerank_score: float | None = None
    scope: Literal["global"] = "global"


class FusionDecisionArtifact(BaseModel):
    decision_id: str
    artifact_ids: list[str] = Field(default_factory=list)
    decision_type: Literal["merge", "keep_separate", "cluster"]
    rationale: str | None = None
    confidence: float | None = None


class CanonicalizationArtifact(BaseModel):
    canonical_id: str
    original_artifact_ids: list[str] = Field(default_factory=list)
    canonical_label: str
    canonical_type: str


class TheoryAtomArtifact(BaseModel):
    component_id: str
    chunk_id: str
    text: str
    component_type: str
    confidence: float | None = None
    plausibility: float | None = None
    epistemic_status: str | None = None
    scope_type: str | None = None


class TheoryRelationArtifact(BaseModel):
    """Artifact payload capturing a dialectical TheoryRelation.

    Preserves decoupled calibration metrics, modal strengths, and mathematical
    weights across pipeline phase boundaries.

    Parameters
    ----------
    relation_id : str
        Canonical unique identifier of the relation.
    source_component_id : str
        Source component identifier.
    target_component_id : str
        Target component identifier.
    relation_type : str
        Relational classification.
    scope : str
        Local or global scope.
    confidence : float
        Extraction confidence score.
    weight : float | None, optional
        Relational edge weight.
    class_probability : float | None, optional
        Softmax stance probability.
    empirical_accuracy : float | None, optional
        Calibrated empirical accuracy frequency from decision engine.
    modal_strength : float, default 1.0
        Propositional modal strength in [0.0, 1.0].
    effective_weight : float | None, optional
        Decoupled mathematical edge weight.
    decision_engine_provider : str | None, optional
        Provenance identifier of decision provider.
    tenability : float | None, optional
        Epistemic tenability score.
    calibrated_confidence : float | None, optional
        Empirically calibrated confidence score.
    weight_support : float | None, optional
        Directed support weight contribution in [0.0, 1.0].
    weight_attack : float | None, optional
        Directed attack weight contribution in [0.0, 1.0].
    """

    relation_id: str
    source_component_id: str
    target_component_id: str
    relation_type: str
    scope: str
    confidence: float
    weight: float | None = None
    class_probability: float | None = None
    empirical_accuracy: float | None = None
    modal_strength: float = 1.0
    effective_weight: float | None = None
    decision_engine_provider: str | None = None
    tenability: float | None = None
    calibrated_confidence: float | None = None
    weight_support: float | None = None
    weight_attack: float | None = None

    def to_graph_properties(self, polarity: int = 0) -> dict[str, Any]:
        """Convert artifact payload into serialized projection properties.

        Parameters
        ----------
        polarity : int, default 0
            Epistemic polarity (+1, -1, 0).

        Returns
        -------
        dict of str to Any
            Graph edge properties conforming to the projection schema.
        """
        eff_w = (
            self.effective_weight
            if self.effective_weight is not None
            else (self.weight if self.weight is not None else 1.0)
        )
        cal_conf = (
            self.calibrated_confidence
            if self.calibrated_confidence is not None
            else (
                self.empirical_accuracy
                if self.empirical_accuracy is not None
                else self.confidence
            )
        )
        w_supp = (
            self.weight_support
            if self.weight_support is not None
            else (eff_w if polarity > 0 else 0.0)
        )
        w_att = (
            self.weight_attack
            if self.weight_attack is not None
            else (eff_w if polarity < 0 else 0.0)
        )

        props: dict[str, Any] = {
            "scope": self.scope,
            "confidence": self.confidence,
            "calibrated_confidence": cal_conf,
            "class_probability": self.class_probability,
            "empirical_accuracy": self.empirical_accuracy,
            "modal_strength": self.modal_strength,
            "effective_weight": eff_w,
            "weight": self.weight if self.weight is not None else eff_w,
            "decision_engine_provider": self.decision_engine_provider,
            "weight_support": w_supp,
            "weight_attack": w_att,
        }
        if self.tenability is not None:
            props["tenability"] = self.tenability
        return props


class TheoreticalEnrichmentArtifact(BaseModel):
    enrichment_id: str
    cluster_id: str
    theory_id: str
    projected_parameters: dict[str, Any] = Field(default_factory=dict)
    local_tenability: float
    edge_tenabilities: dict[str, float] = Field(default_factory=dict)
    aggregated_tenability: float
    admissible_blur_delta: float
    is_tenable: bool
    anomalies: list[str] = Field(default_factory=list)


ArtifactPayload = (
    DocumentArtifact
    | ChunkArtifact
    | EntityMentionArtifact
    | LinkedEntityArtifact
    | LocalRelationArtifact
    | GlobalRelationArtifact
    | TheoryAtomArtifact
    | TheoryRelationArtifact
    | FusionDecisionArtifact
    | CanonicalizationArtifact
    | TheoreticalEnrichmentArtifact
)

ArtifactPayloadT = TypeVar("ArtifactPayloadT", bound=ArtifactPayload)


class ArtifactEnvelope(BaseModel, Generic[ArtifactPayloadT]):
    artifact_id: str
    identity_key: str | None = None
    kind: ArtifactKind
    run_id: str
    phase_name: str
    method: str
    method_version: str = "v1"
    config_fingerprint: str | None = None
    dependency_fingerprint: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    provenance: ArtifactProvenance = Field(default_factory=ArtifactProvenance)
    payload: ArtifactPayloadT
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def populate_identity_key(self):
        if self.identity_key is None:
            self.identity_key = self.artifact_id
        return self

    def ref(self) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=self.artifact_id,
            kind=self.kind,
            run_id=self.run_id,
            phase_name=self.phase_name,
        )
