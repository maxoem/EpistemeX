from __future__ import annotations

from dataclasses import dataclass

from episteme_pipeline.artifacts.builders import parse_mention_id
from episteme_pipeline.artifacts.codecs import (
    ChunkCodec,
    DocumentCodec,
    GlobalRelationCodec,
    LinkedEntityCodec,
    LocalRelationCodec,
    TheoryAtomCodec,
    TheoryRelationCodec,
)
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactPayload,
    ChunkArtifact,
    DocumentArtifact,
    EntityMentionArtifact,
    GlobalRelationArtifact,
    LinkedEntityArtifact,
    LocalRelationArtifact,
    TheoreticalEnrichmentArtifact,
    TheoryAtomArtifact,
    TheoryRelationArtifact,
)
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
    """Homogeneous or heterogeneous collection of artifact envelopes.

    Parameters
    ----------
    artifacts : list[ArtifactEnvelope[ArtifactPayload]]
        List of envelopes contained within this collection.
    """

    artifacts: list[ArtifactEnvelope[ArtifactPayload]]

    def __len__(self) -> int:
        """Return the number of artifacts in the collection.

        Returns
        -------
        int
            Count of artifacts.
        """
        return len(self.artifacts)

    def __iter__(self):
        """Iterate over the artifact envelopes in the collection.

        Returns
        -------
        Iterator[ArtifactEnvelope[ArtifactPayload]]
            Iterator over envelopes.
        """
        return iter(self.artifacts)

    def __getitem__(self, index: int) -> ArtifactEnvelope[ArtifactPayload]:
        """Index into the artifact collection.

        Parameters
        ----------
        index : int
            Position index.

        Returns
        -------
        ArtifactEnvelope[ArtifactPayload]
            Artifact envelope at index.
        """
        return self.artifacts[index]

    def of_kind(self, *kinds: ArtifactKind) -> list[ArtifactEnvelope[ArtifactPayload]]:
        allowed = set(kinds)
        return [artifact for artifact in self.artifacts if artifact.kind in allowed]


@dataclass(slots=True)
class Phase1ArtifactsView:
    _allowed_kinds = (ArtifactKind.DOCUMENT, ArtifactKind.CHUNK)

    documents: list[L1Document]
    chunks: list[L1Chunk]

    @classmethod
    def from_collection(cls, collection: ArtifactCollection) -> Phase1ArtifactsView:
        documents: list[L1Document] = []
        chunks: list[L1Chunk] = []
        for artifact in collection.of_kind(*cls._allowed_kinds):
            payload = artifact.payload
            if artifact.kind == ArtifactKind.DOCUMENT and isinstance(
                payload, DocumentArtifact
            ):
                documents.append(DocumentCodec.to_domain(payload))
            elif artifact.kind == ArtifactKind.CHUNK and isinstance(
                payload, ChunkArtifact
            ):
                chunks.append(ChunkCodec.to_domain(payload))
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
    def from_collection(cls, collection: ArtifactCollection) -> Phase2ArtifactsView:
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
                entity = LinkedEntityCodec.to_domain(payload)
                if not entity.source_chunk_ids:
                    source_chunk_ids = mention_chunk_ids_by_entity.get(
                        payload.entity_id, []
                    )
                    entity = entity.model_copy(
                        update={"source_chunk_ids": source_chunk_ids}
                    )
                entities.append(entity)
                entity_count_by_type[payload.entity_type] = (
                    entity_count_by_type.get(payload.entity_type, 0) + 1
                )
            elif artifact.kind == ArtifactKind.LOCAL_RELATION and isinstance(
                payload, LocalRelationArtifact
            ):
                triples.append(LocalRelationCodec.to_domain(payload))
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
    def from_collection(cls, collection: ArtifactCollection) -> Phase3ArtifactsView:
        triples: list[L2Triple] = []
        distribution: dict[str, int] = {}
        chunks: list[L1Chunk] = []
        for artifact in collection.artifacts:
            payload = artifact.payload
            if artifact.kind == ArtifactKind.CHUNK and isinstance(
                payload, ChunkArtifact
            ):
                chunks.append(ChunkCodec.to_domain(payload))
            elif artifact.kind == ArtifactKind.GLOBAL_RELATION and isinstance(
                payload, GlobalRelationArtifact
            ):
                triples.append(GlobalRelationCodec.to_domain(payload))
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
    def from_collection(cls, collection: ArtifactCollection) -> Phase4ArtifactsView:
        components: list[TheoryAtom] = []
        relations: list[TheoryRelation] = []
        for artifact in collection.artifacts:
            payload = artifact.payload
            if artifact.kind == ArtifactKind.THEORY_ATOM and isinstance(
                payload, TheoryAtomArtifact
            ):
                components.append(TheoryAtomCodec.to_domain(payload))
            elif artifact.kind == ArtifactKind.THEORY_RELATION and isinstance(
                payload, TheoryRelationArtifact
            ):
                relations.append(TheoryRelationCodec.to_domain(payload))
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
    def from_collection(cls, collection: ArtifactCollection) -> TheoreticalEnrichmentArtifactsView:
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
