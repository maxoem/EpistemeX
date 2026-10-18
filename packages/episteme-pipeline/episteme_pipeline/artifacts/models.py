"""Run-scoped artifact models for the target research-library architecture.

These models intentionally do not replace the current domain models yet.
They provide a first architecture-facing scaffold for the artifact/run model
described in `docs/architecture/artifact_run_model.md` and `docs/architecture/overview.md`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

from episteme_pipeline.contracts.domain import (
    GlobalStructuralAnchor,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    Measurement,
    TenabilityResult,
    TextAnchor,
    TheoryAtom,
    TheoryRelation,
)

if TYPE_CHECKING:
    from episteme_pipeline.protocols.graph_projection import (
        ProjectionBatchAccumulator,
    )
    from episteme_pipeline.protocols.graph_store import ProjectionGraph

DomainT = TypeVar("DomainT")


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


def _split_mention_id(mention_id: str) -> tuple[str, str]:
    """Parse a canonical ``mention::<entity_id>::<chunk_id>`` identifier."""
    stripped = mention_id.removeprefix("artifact::")
    parts = stripped.split("::")
    if len(parts) == 3 and parts[0] == "mention":
        return parts[1], parts[2]
    if len(parts) == 2 and parts[0] == "mention":
        return "", parts[1]
    return stripped, ""


class BaseArtifactPayload(BaseModel, ABC):
    """Abstract base interface for all run-scoped artifact payloads.

    Enforces polymorphic graph projection (both single-envelope and batched
    collection accumulation) so callers never need procedural ``isinstance``
    dispatch chains over concrete payload classes.
    """

    @abstractmethod
    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this payload directly into ``graph_store``."""
        ...

    @abstractmethod
    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this payload into a topological ``ProjectionBatchAccumulator``."""
        ...


class DomainObjectPayload[DomainT](BaseArtifactPayload, ABC):
    """Abstract interface for artifact payloads backed by a domain contract ``DomainT``."""

    @abstractmethod
    def to_domain(self) -> DomainT:
        """Hydrate this artifact payload into its corresponding domain model."""
        ...


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


class DocumentArtifact(DomainObjectPayload[L1Document]):
    document_id: str
    title: str
    source_path: str
    structural_anchor: GlobalStructuralAnchor | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=utc_now)

    def to_domain(self) -> L1Document:
        """Hydrate into an :class:`L1Document` via :class:`DocumentCodec`."""
        from episteme_pipeline.artifacts.codecs import DocumentCodec

        return DocumentCodec.to_domain(self)

    def to_node_properties(self) -> dict[str, Any]:
        """Build target graph node properties for this document."""
        props: dict[str, Any] = {
            "title": self.title,
            "source_path": self.source_path,
        }
        if self.structural_anchor is not None:
            anchor = self.structural_anchor
            if anchor.toc_structure:
                props["toc_structure"] = (
                    "\n".join(anchor.toc_structure)
                    if isinstance(anchor.toc_structure, list)
                    else str(anchor.toc_structure)
                )
            if anchor.document_summary:
                props["document_summary"] = anchor.document_summary
            if anchor.global_thesis:
                props["global_thesis"] = anchor.global_thesis
        if self.metadata:
            props.update(self.metadata)
        return props

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this document node into ``graph_store``."""
        await graph_store.upsert_node(
            label="Document",
            node_id=self.document_id,
            properties=self.to_node_properties(),
        )

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this document payload into ``batch``."""
        batch.add_document(self)


class ChunkArtifact(DomainObjectPayload[L1Chunk]):
    chunk_id: str
    document_id: str
    text: str
    sequence_index: int
    chapter_id: str | None = None
    token_count: int
    embedding: list[float] | None = None
    text_anchor: TextAnchor | None = None
    chunk_metadata: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> L1Chunk:
        """Hydrate into an :class:`L1Chunk` via :class:`ChunkCodec`."""
        from episteme_pipeline.artifacts.codecs import ChunkCodec

        return ChunkCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this chunk into ``graph_store``."""
        await graph_store.upsert_chunk(self.to_domain())

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this chunk into ``batch``."""
        batch.add_chunk(self.to_domain())


class EntityMentionArtifact(BaseArtifactPayload):
    mention_id: str
    chunk_id: str
    surface_form: str
    entity_type: str
    entity_id: str | None = None
    textual_envelope: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    confidence: float | None = None

    def to_relation_spec(self) -> dict[str, Any]:
        """Build the ``EXTRACTED_FROM`` edge specification for this mention."""
        parsed_entity_id, _ = _split_mention_id(self.mention_id)
        resolved_entity_id = self.entity_id or parsed_entity_id or self.mention_id
        props: dict[str, Any] = {
            "entity_type": self.entity_type,
            "surface_form": self.surface_form,
        }
        if self.textual_envelope:
            props["textual_envelope"] = self.textual_envelope
        if self.confidence is not None:
            props["confidence"] = self.confidence
        return {
            "from_id": resolved_entity_id,
            "relation_type": "EXTRACTED_FROM",
            "to_id": self.chunk_id,
            "properties": props,
        }

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this mention as an ``EXTRACTED_FROM`` relation."""
        rel_spec = self.to_relation_spec()
        await graph_store.upsert_relation(
            rel_spec["from_id"],
            rel_spec["relation_type"],
            rel_spec["to_id"],
            rel_spec["properties"],
        )

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this mention's ``EXTRACTED_FROM`` relation into ``batch``."""
        batch.add_relation(self.to_relation_spec())


class LinkedEntityArtifact(DomainObjectPayload[L2Entity]):
    entity_id: str
    canonical_name: str
    entity_type: str
    mention_ids: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)
    description: str | None = None
    textual_envelope: str | None = None
    is_mature: bool = False
    confidence: float | None = None
    text_anchor: TextAnchor | None = None

    def to_domain(self) -> L2Entity:
        """Hydrate into an :class:`L2Entity` via :class:`LinkedEntityCodec`."""
        from episteme_pipeline.artifacts.codecs import LinkedEntityCodec

        return LinkedEntityCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this entity into ``graph_store``."""
        await graph_store.upsert_entity(self.to_domain())

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this entity into ``batch``."""
        batch.add_entity(self.to_domain())


class LocalRelationArtifact(DomainObjectPayload[L2Triple]):
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    source_chunk_id: str
    confidence: float
    rerank_score: float | None = None
    scope: Literal["local"] = "local"

    def to_domain(self) -> L2Triple:
        """Hydrate into a local :class:`L2Triple` via :class:`LocalRelationCodec`."""
        from episteme_pipeline.artifacts.codecs import LocalRelationCodec

        return LocalRelationCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this local triple into ``graph_store``."""
        await graph_store.upsert_triple(self.to_domain())

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this local triple into ``batch``."""
        batch.add_triple(self.to_domain())


class GlobalRelationArtifact(DomainObjectPayload[L2Triple]):
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float
    rerank_score: float | None = None
    scope: Literal["global"] = "global"
    source_chunk_id: str | None = None

    def to_domain(self) -> L2Triple:
        """Hydrate into a global :class:`L2Triple` via :class:`GlobalRelationCodec`."""
        from episteme_pipeline.artifacts.codecs import GlobalRelationCodec

        return GlobalRelationCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this global triple into ``graph_store``."""
        await graph_store.upsert_triple(self.to_domain())

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this global triple into ``batch``."""
        batch.add_triple(self.to_domain())


class FusionDecisionArtifact(BaseArtifactPayload):
    decision_id: str
    artifact_ids: list[str] = Field(default_factory=list)
    decision_type: Literal["merge", "keep_separate", "cluster"]
    canonical_artifact_id: str | None = None
    rationale: str | None = None
    confidence: float | None = None

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """No-op direct projection for fusion decision audit records."""
        return None

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """No-op batch projection for fusion decision audit records."""
        return None


class CanonicalizationArtifact(BaseArtifactPayload):
    canonical_id: str = ""
    original_artifact_ids: list[str] = Field(default_factory=list)
    canonical_label: str = ""
    canonical_type: str = "entity"
    rationale: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_canonicalization_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            normalized = dict(data)
            if not normalized.get("canonical_id") and normalized.get(
                "canonical_entity_id"
            ):
                normalized["canonical_id"] = normalized["canonical_entity_id"]
            if not normalized.get("original_artifact_ids") and normalized.get(
                "merged_entity_ids"
            ):
                normalized["original_artifact_ids"] = list(
                    normalized["merged_entity_ids"]
                )
            if not normalized.get("canonical_label") and normalized.get("canonical_id"):
                normalized["canonical_label"] = str(normalized["canonical_id"])
            return normalized
        return data

    @property
    def canonical_entity_id(self) -> str:
        """Return the canonical entity identifier."""
        return self.canonical_id

    @property
    def merged_entity_ids(self) -> list[str]:
        """Return the list of merged alias entity identifiers."""
        return self.original_artifact_ids

    def to_relation_specs(self) -> list[dict[str, Any]]:
        """Build ``SAME_AS`` edge specifications for all non-canonical alias IDs."""
        return [
            {
                "from_id": original_id,
                "relation_type": "SAME_AS",
                "to_id": self.canonical_id,
                "properties": {
                    "confidence": 1.0,
                    "source": "phase3b_consolidation",
                },
            }
            for original_id in self.original_artifact_ids
            if original_id != self.canonical_id
        ]

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project ``SAME_AS`` relations into ``graph_store``."""
        for spec in self.to_relation_specs():
            await graph_store.upsert_relation(
                spec["from_id"],
                spec["relation_type"],
                spec["to_id"],
                spec["properties"],
            )

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register ``SAME_AS`` relations into ``batch``."""
        for spec in self.to_relation_specs():
            batch.add_relation(spec)


class TheoryAtomArtifact(DomainObjectPayload[TheoryAtom]):
    component_id: str
    chunk_id: str
    text: str
    component_type: str
    confidence: float | None = None
    plausibility: float | None = None
    epistemic_status: str | None = None
    scope_type: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    modal_strength: float = 0.6
    base_score: float | None = None
    text_anchor: TextAnchor | None = None
    measurements: list[Measurement] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    tenability: TenabilityResult | None = None

    def to_domain(self) -> TheoryAtom:
        """Hydrate into a :class:`TheoryAtom` via :class:`TheoryAtomCodec`."""
        from episteme_pipeline.artifacts.codecs import TheoryAtomCodec

        return TheoryAtomCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this theory atom into ``graph_store``."""
        await graph_store.upsert_argument_component(self.to_domain())

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this theory atom into ``batch``."""
        batch.add_theory_atom(self.to_domain())


class TheoryRelationArtifact(DomainObjectPayload[TheoryRelation]):
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
    stance_probability: float | None = None
    empirical_accuracy: float | None = None
    model_confidence: float | None = None
    inferential_force: float = 0.75
    is_admissible: bool = True
    active_weight: float = 0.75
    modal_strength: float = 1.0
    effective_weight: float | None = None
    decision_engine_provider: str | None = None
    tenability: float | None = None
    calibrated_confidence: float | None = None
    weight_support: float | None = None
    weight_attack: float | None = None

    def to_domain(self) -> TheoryRelation:
        """Hydrate into a :class:`TheoryRelation` via :class:`TheoryRelationCodec`."""
        from episteme_pipeline.artifacts.codecs import TheoryRelationCodec

        return TheoryRelationCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this theory relation into ``graph_store``."""
        await graph_store.upsert_theory_relation(self.to_domain())

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this theory relation into ``batch``."""
        batch.add_theory_relation(self.to_domain())

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
            "stance_probability": self.stance_probability,
            "empirical_accuracy": self.empirical_accuracy,
            "model_confidence": self.model_confidence,
            "inferential_force": self.inferential_force,
            "is_admissible": self.is_admissible,
            "active_weight": self.active_weight,
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


class TheoreticalEnrichmentArtifact(BaseArtifactPayload):
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

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """No-op direct single-envelope projection for enrichment summaries."""
        return None

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this theoretical enrichment payload into ``batch``."""
        batch.add_enrichment(self)


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


class ArtifactEnvelope[ArtifactPayloadT: ArtifactPayload](BaseModel):
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
