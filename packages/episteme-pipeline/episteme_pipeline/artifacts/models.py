"""Run-scoped artifact models for the target research-library architecture.

These models intentionally do not replace the current domain models yet.
They provide a first architecture-facing scaffold for the artifact/run model
described in `docs/architecture/artifact_run_model.md` and `docs/architecture/overview.md`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, Self, TypeVar

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
    """Artifact payload capturing a Layer 3 TheoryAtom with Stratified Epistemic State Tuple."""

    component_id: str
    chunk_id: str
    text: str
    component_type: str
    confidence: float | None = None
    epistemic_status: str | None = None
    scope_type: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    modal_prior: float = 0.6
    local_tenability: float | None = None
    equilibrium_strength: float | None = None
    controversy_volatility: float | None = None
    resolver_type: str | None = None
    syntax_bounds: tuple[float, float] | None = None
    text_anchor: TextAnchor | None = None
    measurements: list[Measurement] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    tenability: TenabilityResult | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_atom_artifact_fields(cls, data: Any) -> Any:
        """Normalize legacy alias keys into canonical TheoryAtomArtifact fields."""
        if not isinstance(data, Mapping):
            return data
        normalized = dict(data)
        if "modal_prior" not in normalized or normalized["modal_prior"] is None:
            if "modal_strength" in normalized and normalized["modal_strength"] is not None:
                normalized["modal_prior"] = normalized["modal_strength"]
            elif "base_score" in normalized and normalized["base_score"] is not None:
                normalized["modal_prior"] = normalized["base_score"]
        normalized.pop("modal_strength", None)
        normalized.pop("base_score", None)
        if "equilibrium_strength" not in normalized or normalized["equilibrium_strength"] is None:
            if "plausibility" in normalized and normalized["plausibility"] is not None:
                normalized["equilibrium_strength"] = normalized["plausibility"]
        normalized.pop("plausibility", None)
        return normalized

    @property
    def modal_strength(self) -> float:
        """Author propositional modal certainty :math:`M(\\phi_a)` (alias for ``modal_prior``)."""
        return self.modal_prior

    @modal_strength.setter
    def modal_strength(self, value: float) -> None:
        self.modal_prior = float(value)

    @property
    def base_score(self) -> float:
        """Prior plausibility :math:`\\tau_0(a)` for D-QBAF (alias for ``modal_prior``)."""
        return self.modal_prior

    @base_score.setter
    def base_score(self, value: float) -> None:
        self.modal_prior = float(value)

    @property
    def plausibility(self) -> float | None:
        """Dialectical equilibrium justification degree :math:`\\tau^*(a)` (alias for ``equilibrium_strength``)."""
        return self.equilibrium_strength

    @plausibility.setter
    def plausibility(self, value: float | None) -> None:
        self.equilibrium_strength = float(value) if value is not None else None

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        """Create a copy of the artifact payload, normalizing legacy alias keys in ``update``."""
        if update:
            norm = dict(update)
            if "modal_prior" not in norm:
                if "modal_strength" in norm and norm["modal_strength"] is not None:
                    norm["modal_prior"] = norm["modal_strength"]
                elif "base_score" in norm and norm["base_score"] is not None:
                    norm["modal_prior"] = norm["base_score"]
            norm.pop("modal_strength", None)
            norm.pop("base_score", None)
            if "equilibrium_strength" not in norm and "plausibility" in norm:
                norm["equilibrium_strength"] = norm["plausibility"]
            norm.pop("plausibility", None)
            update = norm
        return super().model_copy(update=update, deep=deep)

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

    Preserves decoupled calibration metrics, Toulmin inferential warrants,
    structural correspondence, and tenability weights across pipeline phase
    boundaries (strictly free of node-level modal strength).

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
    perception_stance_prob : float | None, optional
        System 1 perception stance probability :math:`P(\\text{stance})`.
    perception_empirical_acc : float | None, optional
        System 1 calibrated empirical accuracy :math:`C`.
    inferential_warrant : float, default 0.75
        Toulminian inferential warrant validity :math:`I_{j \\to i} \\in [0, 1]`.
    structural_correspondence : float | None, optional
        :math:`\\kappa`-structural correspondence score from ADR-0007.
    edge_tenability : float | None, optional
        Intertheoretical edge tenability :math:`TS_{\\text{edge}}` from ADR-0015.
    effective_weight : float | None, optional
        Decoupled mathematical edge weight.
    decision_engine_provider : str | None, optional
        Provenance identifier of decision provider.
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
    perception_stance_prob: float | None = None
    perception_empirical_acc: float | None = None
    inferential_warrant: float = 0.75
    structural_correspondence: float | None = None
    is_admissible: bool = True
    active_weight: float = 0.75
    effective_weight: float | None = None
    decision_engine_provider: str | None = None
    edge_tenability: float | None = None
    calibrated_confidence: float | None = None
    weight_support: float | None = None
    weight_attack: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_relation_artifact_fields(cls, data: Any) -> Any:
        """Normalize legacy alias keys into canonical TheoryRelationArtifact fields."""
        if not isinstance(data, Mapping):
            return data
        normalized = dict(data)
        if "inferential_warrant" not in normalized or normalized["inferential_warrant"] is None:
            if "inferential_force" in normalized and normalized["inferential_force"] is not None:
                normalized["inferential_warrant"] = normalized["inferential_force"]
        normalized.pop("inferential_force", None)

        if "perception_stance_prob" not in normalized or normalized["perception_stance_prob"] is None:
            if "stance_probability" in normalized and normalized["stance_probability"] is not None:
                normalized["perception_stance_prob"] = normalized["stance_probability"]
            elif "class_probability" in normalized and normalized["class_probability"] is not None:
                normalized["perception_stance_prob"] = normalized["class_probability"]
        normalized.pop("stance_probability", None)
        normalized.pop("class_probability", None)

        if "perception_empirical_acc" not in normalized or normalized["perception_empirical_acc"] is None:
            if "empirical_accuracy" in normalized and normalized["empirical_accuracy"] is not None:
                normalized["perception_empirical_acc"] = normalized["empirical_accuracy"]
        normalized.pop("empirical_accuracy", None)

        if "calibrated_confidence" not in normalized or normalized["calibrated_confidence"] is None:
            if "model_confidence" in normalized and normalized["model_confidence"] is not None:
                normalized["calibrated_confidence"] = normalized["model_confidence"]
        normalized.pop("model_confidence", None)

        if "edge_tenability" not in normalized or normalized["edge_tenability"] is None:
            if "tenability" in normalized and normalized["tenability"] is not None:
                normalized["edge_tenability"] = normalized["tenability"]
        normalized.pop("tenability", None)
        return normalized

    @property
    def inferential_force(self) -> float:
        """Toulminian inferential warrant validity :math:`I_{j \\to i}` (alias for ``inferential_warrant``)."""
        return self.inferential_warrant

    @inferential_force.setter
    def inferential_force(self, value: float) -> None:
        self.inferential_warrant = float(value)

    @property
    def stance_probability(self) -> float | None:
        """Perception stance probability :math:`P(\\text{stance})` (alias for ``perception_stance_prob``)."""
        return self.perception_stance_prob

    @stance_probability.setter
    def stance_probability(self, value: float | None) -> None:
        self.perception_stance_prob = float(value) if value is not None else None

    @property
    def class_probability(self) -> float | None:
        """Softmax class probability :math:`P(\\text{stance})` (alias for ``perception_stance_prob``)."""
        return self.perception_stance_prob

    @class_probability.setter
    def class_probability(self, value: float | None) -> None:
        self.perception_stance_prob = float(value) if value is not None else None

    @property
    def empirical_accuracy(self) -> float | None:
        """Calibrated empirical accuracy :math:`C` (alias for ``perception_empirical_acc``)."""
        return self.perception_empirical_acc

    @empirical_accuracy.setter
    def empirical_accuracy(self, value: float | None) -> None:
        self.perception_empirical_acc = float(value) if value is not None else None

    @property
    def model_confidence(self) -> float | None:
        """Calibrated model confidence (alias for ``calibrated_confidence``)."""
        return self.calibrated_confidence

    @model_confidence.setter
    def model_confidence(self, value: float | None) -> None:
        self.calibrated_confidence = float(value) if value is not None else None

    @property
    def tenability(self) -> float | None:
        """Intertheoretical edge tenability :math:`TS_{\\text{edge}}` (alias for ``edge_tenability``)."""
        return self.edge_tenability

    @tenability.setter
    def tenability(self, value: float | None) -> None:
        self.edge_tenability = float(value) if value is not None else None

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        """Create a copy of the artifact payload, normalizing legacy alias keys in ``update``."""
        if update:
            norm = dict(update)
            if "inferential_warrant" not in norm and "inferential_force" in norm:
                norm["inferential_warrant"] = norm["inferential_force"]
            norm.pop("inferential_force", None)
            if "perception_stance_prob" not in norm:
                if "stance_probability" in norm:
                    norm["perception_stance_prob"] = norm["stance_probability"]
                elif "class_probability" in norm:
                    norm["perception_stance_prob"] = norm["class_probability"]
            norm.pop("stance_probability", None)
            norm.pop("class_probability", None)
            if "perception_empirical_acc" not in norm and "empirical_accuracy" in norm:
                norm["perception_empirical_acc"] = norm["empirical_accuracy"]
            norm.pop("empirical_accuracy", None)
            if "calibrated_confidence" not in norm and "model_confidence" in norm:
                norm["calibrated_confidence"] = norm["model_confidence"]
            norm.pop("model_confidence", None)
            if "edge_tenability" not in norm and "tenability" in norm:
                norm["edge_tenability"] = norm["tenability"]
            norm.pop("tenability", None)
            update = norm
        return super().model_copy(update=update, deep=deep)

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
        return self.to_domain().to_graph_properties(polarity=polarity)


class TheoreticalEnrichmentArtifact(BaseArtifactPayload):
    enrichment_id: str
    cluster_id: str
    theory_id: str
    claimant_atom_ids: list[str] = Field(default_factory=list)
    projected_parameters: dict[str, Any] = Field(default_factory=dict)
    local_tenability: float
    edge_tenabilities: dict[str, float] = Field(default_factory=dict)
    equilibrium_strengths: dict[str, float] = Field(default_factory=dict)
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
