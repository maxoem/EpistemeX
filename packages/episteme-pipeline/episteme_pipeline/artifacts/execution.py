from __future__ import annotations

from dataclasses import dataclass

from episteme_pipeline.artifacts.models import (
    TheoreticalEnrichmentArtifact,
    TheoryAtomArtifact,
    TheoryRelationArtifact,
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactPayload,
    ChunkArtifact,
    DocumentArtifact,
    EntityMentionArtifact,
    GlobalRelationArtifact,
    LinkedEntityArtifact,
    LocalRelationArtifact,
)
from episteme_pipeline.artifacts.builders import parse_mention_id
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.runs.models import RunManifest


@dataclass(slots=True)
class ArtifactCollection:
    artifacts: list[ArtifactEnvelope[ArtifactPayload]]

    def of_kind(self, *kinds: ArtifactKind) -> list[ArtifactEnvelope[ArtifactPayload]]:
        allowed = set(kinds)
        return [artifact for artifact in self.artifacts if artifact.kind in allowed]


@dataclass(slots=True)
class Phase1ArtifactsView:
    _allowed_kinds = (ArtifactKind.DOCUMENT, ArtifactKind.CHUNK)

    documents: list[L1Document]
    chunks: list[L1Chunk]

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> "Phase1ArtifactsView":
        documents: list[L1Document] = []
        chunks: list[L1Chunk] = []
        for artifact in collection.of_kind(*cls._allowed_kinds):
            payload = artifact.payload
            if artifact.kind == ArtifactKind.DOCUMENT and isinstance(
                payload, DocumentArtifact
            ):
                documents.append(
                    L1Document(
                        id=payload.document_id,
                        title=payload.title,
                        source_path=payload.source_path,
                        ingested_at=payload.ingested_at,
                        chapter_count=int(payload.metadata.get("chapter_count", "0")),
                        chunk_count=int(payload.metadata.get("chunk_count", "0")),
                        structural_anchor=payload.structural_anchor,
                        metadata=payload.metadata,
                    )
                )
            elif artifact.kind == ArtifactKind.CHUNK and isinstance(
                payload, ChunkArtifact
            ):
                chunks.append(
                    L1Chunk(
                        id=payload.chunk_id,
                        text=payload.text,
                        source_doc_id=payload.document_id,
                        chapter_id=payload.chapter_id,
                        sequence_index=payload.sequence_index,
                        token_count=payload.token_count,
                    )
                )
        return cls(documents=documents, chunks=chunks)


@dataclass(slots=True)
class Phase2ArtifactsView:
    _allowed_kinds = (
        ArtifactKind.ENTITY_MENTION,
        ArtifactKind.LINKED_ENTITY,
        ArtifactKind.LOCAL_RELATION,
    )

    entities: list[L2Entity]
    local_triples: list[L2Triple]
    entity_count_by_type: dict[str, int]

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> "Phase2ArtifactsView":
        entities: list[L2Entity] = []
        triples: list[L2Triple] = []
        entity_count_by_type: dict[str, int] = {}
        mention_chunk_ids_by_entity: dict[str, list[str]] = {}

        for artifact in collection.of_kind(*cls._allowed_kinds):
            payload = artifact.payload
            if artifact.kind == ArtifactKind.ENTITY_MENTION and isinstance(
                payload, EntityMentionArtifact
            ):
                entity_id, chunk_id = parse_mention_id(payload.mention_id)
                mention_chunk_ids_by_entity.setdefault(entity_id, []).append(
                    chunk_id
                )

        for artifact in collection.of_kind(*cls._allowed_kinds):
            payload = artifact.payload
            if artifact.kind == ArtifactKind.LINKED_ENTITY and isinstance(
                payload, LinkedEntityArtifact
            ):
                source_chunk_ids = mention_chunk_ids_by_entity.get(
                    payload.entity_id, []
                )
                entities.append(
                    L2Entity(
                        id=payload.entity_id,
                        label=payload.entity_type,
                        name=payload.canonical_name,
                        description=payload.description,
                        textual_envelope=payload.textual_envelope,
                        is_mature=payload.is_mature,
                        confidence=payload.confidence,
                        source_chunk_ids=source_chunk_ids,
                    )
                )
                entity_count_by_type[payload.entity_type] = (
                    entity_count_by_type.get(payload.entity_type, 0) + 1
                )
            elif artifact.kind == ArtifactKind.LOCAL_RELATION and isinstance(
                payload, LocalRelationArtifact
            ):
                triples.append(
                    L2Triple(
                        subject_id=payload.subject_entity_id,
                        predicate=payload.predicate,
                        object_id=payload.object_entity_id,
                        confidence=payload.confidence,
                        scope="local",
                        source_chunk_id=payload.source_chunk_id,
                    )
                )
        return cls(
            entities=entities,
            local_triples=triples,
            entity_count_by_type=entity_count_by_type,
        )


@dataclass(slots=True)
class Phase3ArtifactsView:
    global_triples: list[L2Triple]
    relation_type_distribution: dict[str, int]
    chunks: list[L1Chunk]

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> "Phase3ArtifactsView":
        triples: list[L2Triple] = []
        distribution: dict[str, int] = {}
        chunks: list[L1Chunk] = []
        for artifact in collection.artifacts:
            payload = artifact.payload
            if artifact.kind == ArtifactKind.CHUNK and isinstance(
                payload, ChunkArtifact
            ):
                chunks.append(
                    L1Chunk(
                        id=payload.chunk_id,
                        text=payload.text,
                        source_doc_id=payload.document_id,
                        chapter_id=payload.chapter_id,
                        sequence_index=payload.sequence_index,
                        token_count=payload.token_count,
                    )
                )
            elif artifact.kind == ArtifactKind.GLOBAL_RELATION and isinstance(
                payload, GlobalRelationArtifact
            ):
                triples.append(
                    L2Triple(
                        subject_id=payload.subject_entity_id,
                        predicate=payload.predicate,
                        object_id=payload.object_entity_id,
                        confidence=payload.confidence,
                        scope="global",
                        source_chunk_id=payload.supporting_chunk_ids[0]
                        if payload.supporting_chunk_ids
                        else "",
                    )
                )
                distribution[payload.predicate] = (
                    distribution.get(payload.predicate, 0) + 1
                )
        return cls(
            global_triples=triples,
            relation_type_distribution=distribution,
            chunks=chunks,
        )


@dataclass(slots=True)
class Phase4ArtifactsView:
    theory_atoms: list[TheoryAtom]
    theory_relations: list[TheoryRelation]

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> "Phase4ArtifactsView":
        components: list[TheoryAtom] = []
        relations: list[TheoryRelation] = []
        for artifact in collection.artifacts:
            payload = artifact.payload
            if artifact.kind == ArtifactKind.THEORY_ATOM and isinstance(
                payload, TheoryAtomArtifact
            ):
                components.append(
                    TheoryAtom(
                        id=payload.component_id,
                        text=payload.text,
                        component_type=payload.component_type,
                        source_chunk_id=payload.chunk_id,
                        plausibility=payload.plausibility,
                        epistemic_status=payload.epistemic_status,
                        scope_type=payload.scope_type,
                    )
                )
            elif artifact.kind == ArtifactKind.THEORY_RELATION and isinstance(
                payload, TheoryRelationArtifact
            ):
                relations.append(
                    TheoryRelation(
                        source_id=payload.source_component_id,
                        target_id=payload.target_component_id,
                        relation_type=payload.relation_type,
                        confidence=payload.confidence,
                        scope=payload.scope,
                        weight=payload.weight,
                        class_probability=payload.class_probability,
                        empirical_accuracy=payload.empirical_accuracy,
                        modal_strength=payload.modal_strength,
                        effective_weight=payload.effective_weight,
                        decision_engine_provider=payload.decision_engine_provider,
                        tenability=payload.tenability,
                        calibrated_confidence=payload.calibrated_confidence,
                        weight_support=payload.weight_support,
                        weight_attack=payload.weight_attack,
                    )
                )
        return cls(theory_atoms=components, theory_relations=relations)


@dataclass(slots=True)
class TheoreticalEnrichmentArtifactsView:
    """Artifact view for theoretical enrichment and tenability evaluation results.

    Parameters
    ----------
    enrichments : list[TheoreticalEnrichmentArtifact]
        Enrichment and tenability score artifacts.
    """

    _allowed_kinds = (ArtifactKind.THEORETICAL_ENRICHMENT,)

    enrichments: list[TheoreticalEnrichmentArtifact]

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> "TheoreticalEnrichmentArtifactsView":
        """Construct the view from an artifact collection.

        Parameters
        ----------
        collection : ArtifactCollection
            The artifact collection to filter.

        Returns
        -------
        TheoreticalEnrichmentArtifactsView
            View containing only theoretical enrichment artifacts.
        """
        enrichments: list[TheoreticalEnrichmentArtifact] = []
        for artifact in collection.of_kind(*cls._allowed_kinds):
            payload = artifact.payload
            if isinstance(payload, TheoreticalEnrichmentArtifact):
                enrichments.append(payload)
        return cls(enrichments=enrichments)


@dataclass(slots=True)
class ArtifactExecutionContext:
    run_id: str
    manifest: RunManifest
    pipeline_input: PipelineInput
    previous: ArtifactCollection | None = None
