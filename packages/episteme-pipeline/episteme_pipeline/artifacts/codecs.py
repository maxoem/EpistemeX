"""Bidirectional codecs translating between domain contracts and artifact payloads.

Provides strict, lossless mapper implementations conforming to the Bidirectional
Codec Pattern (Design Patterns & Standards §3.5).
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from episteme_pipeline.artifacts.models import (
    ChunkArtifact,
    DocumentArtifact,
    EpistemicDeficitArtifact,
    GlobalRelationArtifact,
    LinkedEntityArtifact,
    LocalRelationArtifact,
    MentionId,
    TheoryAtomArtifact,
    TheoryRelationArtifact,
)
from episteme_pipeline.contracts.domain import (
    EntityConception,
    EpistemicDeficit,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)

DomainT = TypeVar("DomainT")
PayloadT = TypeVar("PayloadT")


class ArtifactCodec(Protocol[DomainT, PayloadT]):
    """Bidirectional codec protocol translating between domain models and artifact payloads."""

    @classmethod
    def to_payload(cls, domain_obj: DomainT) -> PayloadT:
        """Serialize a domain model into an artifact payload.

        Parameters
        ----------
        domain_obj : DomainT
            Domain entity instance to serialize.

        Returns
        -------
        PayloadT
            Serialized artifact payload.
        """
        ...

    @classmethod
    def to_domain(cls, payload: PayloadT) -> DomainT:
        """Hydrate an artifact payload back into a domain model.

        Parameters
        ----------
        payload : PayloadT
            Artifact payload to deserialize.

        Returns
        -------
        DomainT
            Hydrated domain entity instance.
        """
        ...


class DocumentCodec:
    """Bidirectional codec for L1Document and DocumentArtifact."""

    @classmethod
    def to_payload(cls, domain_obj: L1Document) -> DocumentArtifact:
        """Serialize an L1Document into DocumentArtifact.

        Parameters
        ----------
        domain_obj : L1Document
            Source document contract.

        Returns
        -------
        DocumentArtifact
            Lossless document artifact payload.
        """
        return DocumentArtifact(
            document_id=domain_obj.id,
            title=domain_obj.title,
            source_path=domain_obj.source_path,
            chapter_count=domain_obj.chapter_count,
            chunk_count=domain_obj.chunk_count,
            structural_anchor=domain_obj.structural_anchor,
            metadata=dict(domain_obj.metadata),
            ingested_at=domain_obj.ingested_at,
        )

    @classmethod
    def to_domain(cls, payload: DocumentArtifact) -> L1Document:
        """Hydrate a DocumentArtifact into L1Document.

        Parameters
        ----------
        payload : DocumentArtifact
            Document artifact payload.

        Returns
        -------
        L1Document
            Reconstructed document contract.
        """
        raw_meta = dict(payload.metadata)
        chapter_count = (
            payload.chapter_count
            if payload.chapter_count is not None
            else int(raw_meta.pop("chapter_count", "0"))
        )
        chunk_count = (
            payload.chunk_count
            if payload.chunk_count is not None
            else int(raw_meta.pop("chunk_count", "0"))
        )
        return L1Document(
            id=payload.document_id,
            title=payload.title,
            source_path=payload.source_path,
            ingested_at=payload.ingested_at,
            chapter_count=chapter_count,
            chunk_count=chunk_count,
            structural_anchor=payload.structural_anchor,
            metadata=raw_meta,
        )


class ChunkCodec:
    """Bidirectional codec for L1Chunk and ChunkArtifact."""

    @classmethod
    def to_payload(cls, domain_obj: L1Chunk) -> ChunkArtifact:
        """Serialize an L1Chunk into ChunkArtifact.

        Parameters
        ----------
        domain_obj : L1Chunk
            Source chunk contract.

        Returns
        -------
        ChunkArtifact
            Lossless chunk artifact payload.
        """
        return ChunkArtifact(
            chunk_id=domain_obj.id,
            document_id=domain_obj.source_doc_id,
            text=domain_obj.text,
            sequence_index=domain_obj.sequence_index,
            chapter_id=domain_obj.chapter_id,
            token_count=domain_obj.token_count,
            embedding=domain_obj.embedding,
            text_anchor=domain_obj.text_anchor,
            chunk_metadata=domain_obj.metadata,
        )

    @classmethod
    def to_domain(cls, payload: ChunkArtifact) -> L1Chunk:
        """Hydrate a ChunkArtifact into L1Chunk.

        Parameters
        ----------
        payload : ChunkArtifact
            Chunk artifact payload.

        Returns
        -------
        L1Chunk
            Reconstructed chunk contract.
        """
        return L1Chunk(
            id=payload.chunk_id,
            text=payload.text,
            source_doc_id=payload.document_id,
            chapter_id=payload.chapter_id,
            sequence_index=payload.sequence_index,
            token_count=payload.token_count,
            embedding=payload.embedding,
            text_anchor=payload.text_anchor,
            metadata=payload.chunk_metadata,
        )


class LinkedEntityCodec:
    """Bidirectional codec for L2Entity and LinkedEntityArtifact."""

    @classmethod
    def to_payload(cls, domain_obj: L2Entity) -> LinkedEntityArtifact:
        """Serialize an L2Entity into LinkedEntityArtifact.

        Parameters
        ----------
        domain_obj : L2Entity
            Source linked entity contract.

        Returns
        -------
        LinkedEntityArtifact
            Lossless linked entity artifact payload.
        """
        mention_ids = [
            MentionId.format(domain_obj.id, cid) for cid in domain_obj.source_chunk_ids
        ]
        return LinkedEntityArtifact(
            entity_id=domain_obj.id,
            canonical_name=domain_obj.name,
            entity_type=domain_obj.label,
            mention_ids=mention_ids,
            source_chunk_ids=list(domain_obj.source_chunk_ids),
            description=domain_obj.description,
            textual_envelope=domain_obj.textual_envelope,
            is_mature=domain_obj.is_mature,
            confidence=domain_obj.confidence,
            text_anchor=domain_obj.text_anchor,
            conceptions=[c.model_copy(deep=True) for c in domain_obj.conceptions],
            polysemy_variance=domain_obj.polysemy_variance,
        )

    @classmethod
    def to_domain(cls, payload: LinkedEntityArtifact) -> L2Entity:
        """Hydrate a LinkedEntityArtifact into L2Entity.

        Parameters
        ----------
        payload : LinkedEntityArtifact
            Linked entity artifact payload.

        Returns
        -------
        L2Entity
            Reconstructed linked entity contract.
        """
        chunk_ids: list[str] = list(payload.source_chunk_ids)
        if not chunk_ids and payload.mention_ids:
            for mid in payload.mention_ids:
                _, parsed_cid = MentionId.parse(mid)
                if parsed_cid:
                    chunk_ids.append(parsed_cid)
        # Deduplicate while preserving order
        seen: set[str] = set()
        uniq_chunk_ids = [c for c in chunk_ids if not (c in seen or seen.add(c))]

        return L2Entity(
            id=payload.entity_id,
            label=payload.entity_type,
            name=payload.canonical_name,
            description=payload.description,
            textual_envelope=payload.textual_envelope,
            is_mature=payload.is_mature,
            confidence=payload.confidence,
            text_anchor=payload.text_anchor,
            source_chunk_ids=uniq_chunk_ids,
            conceptions=[EntityConception.model_validate(c) for c in payload.conceptions],
            polysemy_variance=payload.polysemy_variance,
        )


class LocalRelationCodec:
    """Bidirectional codec for local L2Triple and LocalRelationArtifact."""

    @classmethod
    def to_payload(cls, domain_obj: L2Triple) -> LocalRelationArtifact:
        """Serialize a local L2Triple into LocalRelationArtifact.

        Parameters
        ----------
        domain_obj : L2Triple
            Source local triple contract.

        Returns
        -------
        LocalRelationArtifact
            Local relation artifact payload.
        """
        cid_key = domain_obj.source_chunk_id or ""
        relation_id = f"local-relation::{cid_key}::{domain_obj.subject_id}::{domain_obj.predicate}::{domain_obj.object_id}"
        return LocalRelationArtifact(
            relation_id=relation_id,
            subject_entity_id=domain_obj.subject_id,
            predicate=domain_obj.predicate,
            object_entity_id=domain_obj.object_id,
            source_chunk_id=domain_obj.source_chunk_id,
            confidence=domain_obj.confidence,
            rerank_score=domain_obj.rerank_score,
            scope="local",
        )

    @classmethod
    def to_domain(cls, payload: LocalRelationArtifact) -> L2Triple:
        """Hydrate a LocalRelationArtifact into L2Triple.

        Parameters
        ----------
        payload : LocalRelationArtifact
            Local relation artifact payload.

        Returns
        -------
        L2Triple
            Reconstructed local triple contract.
        """
        return L2Triple(
            subject_id=payload.subject_entity_id,
            predicate=payload.predicate,
            object_id=payload.object_entity_id,
            confidence=payload.confidence,
            rerank_score=payload.rerank_score,
            scope="local",
            source_chunk_id=payload.source_chunk_id,
        )


class GlobalRelationCodec:
    """Bidirectional codec for global L2Triple and GlobalRelationArtifact."""

    @classmethod
    def to_payload(cls, domain_obj: L2Triple) -> GlobalRelationArtifact:
        """Serialize a global L2Triple into GlobalRelationArtifact.

        Parameters
        ----------
        domain_obj : L2Triple
            Source global triple contract.

        Returns
        -------
        GlobalRelationArtifact
            Global relation artifact payload.
        """
        relation_id = f"global-relation::{domain_obj.subject_id}::{domain_obj.predicate}::{domain_obj.object_id}"
        supporting = [domain_obj.source_chunk_id] if domain_obj.source_chunk_id else []
        return GlobalRelationArtifact(
            relation_id=relation_id,
            subject_entity_id=domain_obj.subject_id,
            predicate=domain_obj.predicate,
            object_entity_id=domain_obj.object_id,
            supporting_chunk_ids=supporting,
            confidence=domain_obj.confidence,
            rerank_score=domain_obj.rerank_score,
            scope="global",
            source_chunk_id=domain_obj.source_chunk_id,
        )

    @classmethod
    def to_domain(cls, payload: GlobalRelationArtifact) -> L2Triple:
        """Hydrate a GlobalRelationArtifact into L2Triple.

        Parameters
        ----------
        payload : GlobalRelationArtifact
            Global relation artifact payload.

        Returns
        -------
        L2Triple
            Reconstructed global triple contract.
        """
        source_cid = payload.source_chunk_id or (
            payload.supporting_chunk_ids[0] if payload.supporting_chunk_ids else None
        )
        return L2Triple(
            subject_id=payload.subject_entity_id,
            predicate=payload.predicate,
            object_id=payload.object_entity_id,
            confidence=payload.confidence,
            rerank_score=payload.rerank_score,
            scope="global",
            source_chunk_id=source_cid,
        )


class TripleCodec:
    """Unified bidirectional codec for L2Triple dispatching by scope."""

    @classmethod
    def to_payload(
        cls, domain_obj: L2Triple
    ) -> LocalRelationArtifact | GlobalRelationArtifact:
        """Serialize an L2Triple into its scoped artifact payload.

        Parameters
        ----------
        domain_obj : L2Triple
            Source triple contract.

        Returns
        -------
        LocalRelationArtifact | GlobalRelationArtifact
            Scoped relation artifact payload.
        """
        if domain_obj.scope == "local":
            return LocalRelationCodec.to_payload(domain_obj)
        return GlobalRelationCodec.to_payload(domain_obj)

    @classmethod
    def to_domain(
        cls, payload: LocalRelationArtifact | GlobalRelationArtifact
    ) -> L2Triple:
        """Hydrate a relation artifact payload into L2Triple.

        Parameters
        ----------
        payload : LocalRelationArtifact | GlobalRelationArtifact
            Relation artifact payload.

        Returns
        -------
        L2Triple
            Reconstructed triple contract.
        """
        if isinstance(payload, LocalRelationArtifact):
            return LocalRelationCodec.to_domain(payload)
        return GlobalRelationCodec.to_domain(payload)


class TheoryAtomCodec:
    """Bidirectional codec for TheoryAtom and TheoryAtomArtifact."""

    @classmethod
    def to_payload(cls, domain_obj: TheoryAtom) -> TheoryAtomArtifact:
        """Serialize a TheoryAtom into TheoryAtomArtifact.

        Parameters
        ----------
        domain_obj : TheoryAtom
            Source theory atom contract.

        Returns
        -------
        TheoryAtomArtifact
            Lossless theory atom artifact payload.
        """
        modal_prior = (
            domain_obj.modal_prior
            if (
                "modal_prior" in domain_obj.model_fields_set
                or domain_obj.resolver_type is not None
                or domain_obj.modal_prior != 0.6
            )
            else None
        )
        return TheoryAtomArtifact(
            component_id=domain_obj.id,
            chunk_id=domain_obj.source_chunk_id,
            text=domain_obj.text,
            component_type=domain_obj.component_type,
            confidence=domain_obj.confidence,
            epistemic_status=domain_obj.epistemic_status,
            scope_type=domain_obj.scope_type,
            entity_ids=list(domain_obj.entity_ids),
            modal_prior=modal_prior,
            local_tenability=domain_obj.local_tenability,
            equilibrium_strength=domain_obj.equilibrium_strength,
            controversy_volatility=domain_obj.controversy_volatility,
            intensional_mode=domain_obj.intensional_mode,
            attributed_to=domain_obj.attributed_to,
            resolver_type=domain_obj.resolver_type,
            syntax_bounds=domain_obj.syntax_bounds,
            text_anchor=domain_obj.text_anchor,
            measurements=list(domain_obj.measurements),
            parameters=dict(domain_obj.parameters),
            tenability=domain_obj.tenability,
        )

    @classmethod
    def to_domain(cls, payload: TheoryAtomArtifact) -> TheoryAtom:
        """Hydrate a TheoryAtomArtifact into TheoryAtom.

        Parameters
        ----------
        payload : TheoryAtomArtifact
            Theory atom artifact payload.

        Returns
        -------
        TheoryAtom
            Reconstructed theory atom contract.
        """
        extra: dict[str, float] = {}
        if payload.modal_prior is not None:
            extra["modal_prior"] = payload.modal_prior
        return TheoryAtom(
            id=payload.component_id,
            text=payload.text,
            component_type=payload.component_type,
            source_chunk_id=payload.chunk_id,
            confidence=payload.confidence,
            local_tenability=payload.local_tenability,
            equilibrium_strength=payload.equilibrium_strength,
            controversy_volatility=payload.controversy_volatility,
            intensional_mode=payload.intensional_mode,
            attributed_to=payload.attributed_to,
            resolver_type=payload.resolver_type,
            syntax_bounds=payload.syntax_bounds,
            entity_ids=list(payload.entity_ids),
            epistemic_status=payload.epistemic_status,
            scope_type=payload.scope_type,
            text_anchor=payload.text_anchor,
            measurements=list(payload.measurements),
            parameters=dict(payload.parameters),
            tenability=payload.tenability,
            **extra,
        )


class TheoryRelationCodec:
    """Bidirectional codec for TheoryRelation and TheoryRelationArtifact."""

    @classmethod
    def to_payload(cls, domain_obj: TheoryRelation) -> TheoryRelationArtifact:
        """Serialize a TheoryRelation into TheoryRelationArtifact.

        Parameters
        ----------
        domain_obj : TheoryRelation
            Source theory relation contract.

        Returns
        -------
        TheoryRelationArtifact
            Lossless theory relation artifact payload.
        """
        relation_id = domain_obj.relation_id
        inferential_warrant = (
            domain_obj.inferential_warrant
            if (
                "inferential_warrant" in domain_obj.model_fields_set
                or domain_obj.inferential_warrant != 0.75
            )
            else None
        )
        return TheoryRelationArtifact(
            relation_id=relation_id,
            source_component_id=domain_obj.source_id,
            target_component_id=domain_obj.target_id,
            id=domain_obj.id,
            premise_ids=domain_obj.premise_ids,
            undercuts_relation_id=domain_obj.undercuts_relation_id,
            relation_type=domain_obj.relation_type,
            scope=domain_obj.scope,
            confidence=domain_obj.confidence,
            weight=domain_obj.weight,
            perception_stance_prob=domain_obj.perception_stance_prob,
            perception_empirical_acc=domain_obj.perception_empirical_acc,
            inferential_warrant=inferential_warrant,
            structural_correspondence=domain_obj.structural_correspondence,
            is_admissible=domain_obj.is_admissible,
            active_weight=domain_obj.active_weight,
            effective_weight=domain_obj.effective_weight,
            decision_engine_provider=domain_obj.decision_engine_provider,
            edge_tenability=domain_obj.edge_tenability,
            calibrated_confidence=domain_obj.calibrated_confidence,
            weight_support=domain_obj.weight_support,
            weight_attack=domain_obj.weight_attack,
        )

    @classmethod
    def to_domain(cls, payload: TheoryRelationArtifact) -> TheoryRelation:
        """Hydrate a TheoryRelationArtifact into TheoryRelation.

        Parameters
        ----------
        payload : TheoryRelationArtifact
            Theory relation artifact payload.

        Returns
        -------
        TheoryRelation
            Reconstructed theory relation contract.
        """
        scope_lit = "local" if payload.scope == "local" else "global"
        extra: dict[str, float] = {}
        if payload.inferential_warrant is not None:
            extra["inferential_warrant"] = payload.inferential_warrant
        return TheoryRelation(
            id=payload.id,
            source_id=payload.source_component_id,
            target_id=payload.target_component_id,
            premise_ids=payload.premise_ids,
            undercuts_relation_id=payload.undercuts_relation_id,
            relation_type=payload.relation_type,
            confidence=payload.confidence,
            scope=scope_lit,
            weight=payload.weight,
            edge_tenability=payload.edge_tenability,
            structural_correspondence=payload.structural_correspondence,
            perception_stance_prob=payload.perception_stance_prob,
            perception_empirical_acc=payload.perception_empirical_acc,
            is_admissible=payload.is_admissible,
            active_weight=payload.active_weight,
            effective_weight=payload.effective_weight,
            decision_engine_provider=payload.decision_engine_provider,
            calibrated_confidence=payload.calibrated_confidence,
            weight_support=payload.weight_support,
            weight_attack=payload.weight_attack,
            **extra,
        )


class EpistemicDeficitCodec:
    """Bidirectional codec for EpistemicDeficit and EpistemicDeficitArtifact."""

    @classmethod
    def to_payload(cls, domain_obj: EpistemicDeficit) -> EpistemicDeficitArtifact:
        """Serialize an EpistemicDeficit into EpistemicDeficitArtifact.

        Parameters
        ----------
        domain_obj : EpistemicDeficit
            Source epistemic deficit contract.

        Returns
        -------
        EpistemicDeficitArtifact
            Lossless epistemic deficit artifact payload.
        """
        return EpistemicDeficitArtifact(
            deficit_id=domain_obj.deficit_id,
            deficit_kind=domain_obj.deficit_kind,
            severity=domain_obj.severity,
            target_chunk_ids=list(domain_obj.target_chunk_ids),
            target_entity_ids=list(domain_obj.target_entity_ids),
            target_atom_ids=list(domain_obj.target_atom_ids),
            target_relation_ids=list(domain_obj.target_relation_ids),
            theory_id=domain_obj.theory_id,
            theory_lens=dict(domain_obj.theory_lens),
            rationale=domain_obj.rationale,
            metrics=dict(domain_obj.metrics),
            detected_in_phase=domain_obj.detected_in_phase,
            refinement_pass=domain_obj.refinement_pass,
        )

    @classmethod
    def to_domain(cls, payload: EpistemicDeficitArtifact) -> EpistemicDeficit:
        """Hydrate an EpistemicDeficitArtifact into EpistemicDeficit.

        Parameters
        ----------
        payload : EpistemicDeficitArtifact
            Epistemic deficit artifact payload.

        Returns
        -------
        EpistemicDeficit
            Reconstructed epistemic deficit contract.
        """
        return EpistemicDeficit(
            deficit_id=payload.deficit_id,
            deficit_kind=payload.deficit_kind,
            severity=payload.severity,
            target_chunk_ids=list(payload.target_chunk_ids),
            target_entity_ids=list(payload.target_entity_ids),
            target_atom_ids=list(payload.target_atom_ids),
            target_relation_ids=list(payload.target_relation_ids),
            theory_id=payload.theory_id,
            theory_lens=dict(payload.theory_lens),
            rationale=payload.rationale,
            metrics=dict(payload.metrics),
            detected_in_phase=payload.detected_in_phase,
            refinement_pass=payload.refinement_pass,
        )
