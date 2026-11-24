"""Run-scoped artifact models for the target research-library architecture.

These models intentionally do not replace the current domain models yet.
They provide a first architecture-facing scaffold for the artifact/run model
described in `docs/architecture/artifact_run_model.md` and `docs/architecture/overview.md`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

from episteme_pipeline.contracts.domain import (
    EntityConception,
    EpistemicDeficit,
    EpistemicDeficitKind,
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
from episteme_pipeline.schema.default_schema import StructuralRelationType

if TYPE_CHECKING:
    from episteme_pipeline.protocols.graph_projection import (
        ProjectionBatchAccumulator,
    )
    from episteme_pipeline.protocols.graph_store import ProjectionGraph

DomainT = TypeVar("DomainT")


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class MentionId:
    """Structured identifier helper for L2 entity mentions within L1 chunks.

    Canonical wire format is ``mention::<entity_id>::<chunk_id>`` (or
    ``mention::<chunk_id>`` when no entity ID is bound), optionally prefixed with
    ``artifact::`` in artifact envelopes.
    """

    PREFIX: ClassVar[str] = "mention"
    ARTIFACT_PREFIX: ClassVar[str] = "artifact::"
    SEPARATOR: ClassVar[str] = "::"

    @classmethod
    def format(cls, entity_id: str, chunk_id: str | None = None) -> str:
        """Build a canonical mention identifier from entity and chunk IDs.

        Parameters
        ----------
        entity_id : str
            Canonical or raw entity identifier.
        chunk_id : str or None, optional
            Source chunk identifier, by default None.

        Returns
        -------
        str
            Formatted mention identifier string.
        """
        if chunk_id:
            return f"{cls.PREFIX}{cls.SEPARATOR}{entity_id}{cls.SEPARATOR}{chunk_id}"
        return f"{cls.PREFIX}{cls.SEPARATOR}{entity_id}"

    @classmethod
    def parse(cls, raw_id: str) -> tuple[str, str | None]:
        """Parse a canonical or artifact-prefixed mention identifier.

        Parameters
        ----------
        raw_id : str
            Raw mention identifier string.

        Returns
        -------
        tuple of (str, str or None)
            ``(entity_id, chunk_id)`` pair extracted from ``raw_id``. If the
            format does not match ``mention::...``, returns ``(stripped_id, None)``.
        """
        stripped = raw_id.removeprefix(cls.ARTIFACT_PREFIX)
        parts = stripped.split(cls.SEPARATOR)
        if len(parts) == 3 and parts[0] == cls.PREFIX:
            return parts[1], (parts[2] or None)
        if len(parts) == 2 and parts[0] == cls.PREFIX:
            return "", (parts[1] or None)
        return stripped, None


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
    EPISTEMIC_DEFICIT = "epistemic_deficit"


class ArtifactRef(BaseModel):
    artifact_id: str
    kind: ArtifactKind
    run_id: str
    phase_name: str


class ArtifactProvenance(BaseModel):
    """Provenance and refinement lineage metadata attached to an artifact envelope.

    Parameters
    ----------
    source_path : str or None, optional
        Source document path on disk, by default None.
    source_document_id : str or None, optional
        Originating L1 document identifier, by default None.
    source_chunk_id : str or None, optional
        Originating L1 chunk identifier, by default None.
    upstream_artifact_ids : list of str, optional
        Artifact IDs consumed to produce this artifact.
    notes : dict of str to str, optional
        Freeform provenance key-value notes.
    refinement_pass : int, default 0
        Hermeneutic refinement iteration number that produced this artifact
        (``0`` for initial forward construction).
    deficit_id : str or None, optional
        Identifier of the :class:`EpistemicDeficit` that triggered localized
        refinement for this artifact, if any.
    """

    source_path: str | None = None
    source_document_id: str | None = None
    source_chunk_id: str | None = None
    upstream_artifact_ids: list[str] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)
    refinement_pass: int = Field(default=0, ge=0)
    deficit_id: str | None = None


class DocumentArtifact(DomainObjectPayload[L1Document]):
    document_id: str
    title: str
    source_path: str
    chapter_count: int | None = None
    chunk_count: int | None = None
    structural_anchor: GlobalStructuralAnchor | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
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
        if self.chapter_count is not None:
            props["chapter_count"] = self.chapter_count
        if self.chunk_count is not None:
            props["chunk_count"] = self.chunk_count
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
    is_retired: bool = False

    def to_relation_spec(self) -> dict[str, Any]:
        """Build the ``EXTRACTED_FROM`` edge specification for this mention."""
        parsed_entity_id, _ = MentionId.parse(self.mention_id)
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
            "relation_type": StructuralRelationType.EXTRACTED_FROM.value,
            "to_id": self.chunk_id,
            "properties": props,
        }

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this mention as an ``EXTRACTED_FROM`` relation, or prune if retired."""
        parsed_entity_id, _ = MentionId.parse(self.mention_id)
        resolved_entity_id = self.entity_id or parsed_entity_id or self.mention_id
        if self.is_retired:
            await graph_store.prune_retired_mentions(
                [(resolved_entity_id, self.chunk_id)]
            )
            return
        rel_spec = self.to_relation_spec()
        await graph_store.upsert_relation(
            rel_spec["from_id"],
            rel_spec["relation_type"],
            rel_spec["to_id"],
            rel_spec["properties"],
        )

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this mention's ``EXTRACTED_FROM`` relation or retirement into ``batch``."""
        if self.is_retired:
            parsed_entity_id, _ = MentionId.parse(self.mention_id)
            resolved_entity_id = self.entity_id or parsed_entity_id or self.mention_id
            batch.add_retired_mention(resolved_entity_id, self.chunk_id)
            return
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
    conceptions: list[EntityConception] = Field(default_factory=list)
    polysemy_variance: float | None = Field(default=None, ge=0.0)
    is_retired: bool = False

    def to_domain(self) -> L2Entity:
        """Hydrate into an :class:`L2Entity` via :class:`LinkedEntityCodec`."""
        from episteme_pipeline.artifacts.codecs import LinkedEntityCodec

        return LinkedEntityCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this entity into ``graph_store``, or prune if retired."""
        if self.is_retired:
            await graph_store.prune_retired_entities([self.entity_id])
            return
        await graph_store.upsert_entity(self.to_domain())

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this entity or retirement pruning into ``batch``."""
        if self.is_retired:
            batch.add_retired_entity(self.entity_id)
            return
        batch.add_entity(self.to_domain())


class LocalRelationArtifact(DomainObjectPayload[L2Triple]):
    relation_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    source_chunk_id: str | None = None
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
        return

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """No-op batch projection for fusion decision audit records."""
        return


class CanonicalizationArtifact(BaseArtifactPayload):
    canonical_id: str = ""
    original_artifact_ids: list[str] = Field(default_factory=list)
    canonical_label: str = ""
    canonical_type: str = "entity"
    rationale: str | None = None

    def to_relation_specs(self) -> list[dict[str, Any]]:
        """Build ``SAME_AS`` edge specifications for all non-canonical alias IDs."""
        return [
            {
                "from_id": original_id,
                "relation_type": StructuralRelationType.SAME_AS.value,
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
    modal_prior: float | None = None
    local_tenability: float | None = None
    equilibrium_strength: float | None = None
    controversy_volatility: float | None = None
    intensional_mode: Literal[
        "asserted", "attributed", "suppositional", "historical"
    ] = "asserted"
    attributed_to: str | None = None
    resolver_type: str | None = None
    syntax_bounds: tuple[float, float] | None = None
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
    weight : float or None, optional
        Relational edge weight.
    perception_stance_prob : float or None, optional
        System 1 perception stance probability :math:`P(\\text{stance})`.
    perception_empirical_acc : float or None, optional
        System 1 calibrated empirical accuracy :math:`C`.
    inferential_warrant : float or None, optional
        Explicit Toulminian inferential warrant validity :math:`I_{j \\to i} \\in [0, 1]`,
        or ``None`` if unset (allowing downstream derivation from relation type).
    structural_correspondence : float or None, optional
        :math:`\\kappa`-structural correspondence score from ADR-0007.
    edge_tenability : float or None, optional
        Intertheoretical edge tenability :math:`TS_{\\text{edge}}` from ADR-0015.
    effective_weight : float or None, optional
        Decoupled mathematical edge weight.
    decision_engine_provider : str or None, optional
        Provenance identifier of decision provider.
    calibrated_confidence : float or None, optional
        Empirically calibrated confidence score.
    weight_support : float or None, optional
        Directed support weight contribution in [0.0, 1.0].
    weight_attack : float or None, optional
        Directed attack weight contribution in [0.0, 1.0].
    id : str or None, optional
        Explicit inference identifier, if specified on domain contract.
    premise_ids : tuple of str, optional
        Conjunctive premise atom IDs for multi-premise inferences.
    undercuts_relation_id : str or None, optional
        Target relation/inference ID when acting as a Pollockian undercutter.
    """

    relation_id: str
    source_component_id: str
    target_component_id: str
    relation_type: str
    scope: str
    confidence: float
    id: str | None = None
    premise_ids: tuple[str, ...] = ()
    undercuts_relation_id: str | None = None
    weight: float | None = None
    perception_stance_prob: float | None = None
    perception_empirical_acc: float | None = None
    inferential_warrant: float | None = None
    structural_correspondence: float | None = None
    is_admissible: bool = True
    active_weight: float = 0.75
    effective_weight: float | None = None
    decision_engine_provider: str | None = None
    edge_tenability: float | None = None
    calibrated_confidence: float | None = None
    weight_support: float | None = None
    weight_attack: float | None = None

    def to_domain(self) -> TheoryRelation:
        """Hydrate into a :class:`TheoryRelation` via :class:`TheoryRelationCodec`."""
        from episteme_pipeline.artifacts.codecs import TheoryRelationCodec

        return TheoryRelationCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """Project this theory relation into ``graph_store``.

        Parameters
        ----------
        graph_store : ProjectionGraph
            Target graph store receiving the theory relation.
        """
        await graph_store.upsert_theory_relation(self.to_domain())

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this theory relation into ``batch``."""
        batch.add_theory_relation(self.to_domain())


TheoryInferenceArtifact = TheoryRelationArtifact


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
        return

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """Register this theoretical enrichment payload into ``batch``."""
        batch.add_enrichment(self)


class EpistemicDeficitArtifact(DomainObjectPayload[EpistemicDeficit]):
    """Artifact payload capturing a top-down epistemic deficit signal (ISSUE-053).

    Emitted by Layer 3/4 diagnostic evaluators to guide bounded localized
    re-extraction, concept splitting, or premise recovery without mutating
    forward phase DAG dependencies.

    Parameters
    ----------
    deficit_id : str
        Deterministic identifier for this epistemic deficit.
    deficit_kind : EpistemicDeficitKind
        Taxonomy kind (``enthymeme_gap``, ``polysemy_collision``, or
        ``ungrounded_axiom``).
    severity : float, default 0.5
        Normalized deficit severity in ``[0.0, 1.0]``.
    target_chunk_ids : list of str, optional
        Target L1 chunk identifiers for localized refinement.
    target_entity_ids : list of str, optional
        Target L2 entity identifiers implicated by the deficit.
    target_atom_ids : list of str, optional
        Target L3 theory atom identifiers exhibiting the deficit.
    target_relation_ids : list of str, optional
        Target L3 theory relation identifiers implicated by the deficit.
    theory_id : str or None, optional
        Conditioning Theory-Element identifier, if available.
    theory_lens : dict of str to Any, optional
        Induced macro-theory schema context conditioning recovery.
    rationale : str, default ""
        Diagnostic explanation of the deficit.
    metrics : dict of str to float, optional
        Diagnostic numeric measurements recorded at detection time.
    detected_in_phase : str, default ""
        Machine key or display name of the detecting phase.
    refinement_pass : int, default 0
        Refinement cycle index during which this deficit was detected.
    """

    deficit_id: str
    deficit_kind: EpistemicDeficitKind
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    target_chunk_ids: list[str] = Field(default_factory=list)
    target_entity_ids: list[str] = Field(default_factory=list)
    target_atom_ids: list[str] = Field(default_factory=list)
    target_relation_ids: list[str] = Field(default_factory=list)
    theory_id: str | None = None
    theory_lens: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)
    detected_in_phase: str = ""
    refinement_pass: int = Field(default=0, ge=0)

    def to_domain(self) -> EpistemicDeficit:
        """Hydrate into an :class:`EpistemicDeficit` via :class:`EpistemicDeficitCodec`.

        Returns
        -------
        EpistemicDeficit
            Reconstructed epistemic deficit domain contract.
        """
        from episteme_pipeline.artifacts.codecs import EpistemicDeficitCodec

        return EpistemicDeficitCodec.to_domain(self)

    async def project_to_graph(self, graph_store: ProjectionGraph) -> None:
        """No-op direct projection for epistemic deficit audit payloads."""
        return

    def collect_for_projection(self, batch: ProjectionBatchAccumulator) -> None:
        """No-op batch projection for epistemic deficit audit payloads."""
        return


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
    | EpistemicDeficitArtifact
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
