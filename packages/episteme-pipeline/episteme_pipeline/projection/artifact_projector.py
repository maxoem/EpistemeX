"""Artifact-to-graph projection for the current migration bridge."""

from __future__ import annotations

import logging

from episteme_pipeline.artifacts.builders import parse_mention_id
from episteme_pipeline.artifacts.codecs import (
    ChunkCodec,
    GlobalRelationCodec,
    LinkedEntityCodec,
    LocalRelationCodec,
    TheoryAtomCodec,
    TheoryRelationCodec,
)
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    CanonicalizationArtifact,
    ChunkArtifact,
    DocumentArtifact,
    EntityMentionArtifact,
    FusionDecisionArtifact,
    GlobalRelationArtifact,
    LinkedEntityArtifact,
    LocalRelationArtifact,
    TheoryAtomArtifact,
    TheoryRelationArtifact,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.protocols.graph_projection import GraphProjectionProtocol
from episteme_pipeline.protocols.graph_store import ProjectionGraph
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)

#: Payload kinds the pipeline produces that this projector deliberately does not
#: write. Phase 3b and Phase 5b commit their merges and clusters to the graph
#: from inside the runner, so the artifact is a record of the decision rather
#: than an instruction to project. Listed explicitly so they do not trip the
#: unknown-payload warning below.
_NOT_PROJECTED = (FusionDecisionArtifact,)


class ArtifactGraphProjector(GraphProjectionProtocol):
    def __init__(
        self,
        graph_store: ProjectionGraph,
        schema: SchemaConfig | None = None,
    ) -> None:
        self.graph_store = graph_store
        self.schema = schema or SchemaConfig()

    async def project(self, artifact: ArtifactEnvelope) -> None:
        payload = artifact.payload

        if isinstance(payload, DocumentArtifact):
            await self.graph_store.upsert_node(
                label="Document",
                node_id=payload.document_id,
                properties={
                    "title": payload.title,
                    "source_path": payload.source_path,
                },
            )
            return

        if isinstance(payload, ChunkArtifact):
            await self.graph_store.upsert_chunk(ChunkCodec.to_domain(payload))
            return

        if isinstance(payload, EntityMentionArtifact):
            # mention_id format: "mention::<entity_id>::<chunk_id>"
            entity_id, chunk_id = parse_mention_id(payload.mention_id)
            if not entity_id:
                entity_id = payload.mention_id
            await self.graph_store.upsert_relation(
                entity_id,
                "EXTRACTED_FROM",
                payload.chunk_id,
                {"entity_type": payload.entity_type, "surface_form": payload.surface_form},
            )
            return

        if isinstance(payload, LinkedEntityArtifact):
            entity = LinkedEntityCodec.to_domain(payload)
            if not entity.source_chunk_ids:
                # Reconstruct source_chunk_ids from mention ids ("mention::<entity_id>::<chunk_id>")
                chunk_ids: list[str] = []
                for mid in payload.mention_ids:
                    _, chunk_id = parse_mention_id(mid)
                    if chunk_id:
                        chunk_ids.append(chunk_id)
                seen: set[str] = set()
                uniq_chunk_ids = [c for c in chunk_ids if not (c in seen or seen.add(c))]
                entity = entity.model_copy(update={"source_chunk_ids": uniq_chunk_ids})

            await self.graph_store.upsert_entity(entity)
            return

        if isinstance(payload, LocalRelationArtifact):
            await self.graph_store.upsert_triple(LocalRelationCodec.to_domain(payload))
            return

        if isinstance(payload, GlobalRelationArtifact):
            await self.graph_store.upsert_triple(GlobalRelationCodec.to_domain(payload))
            return

        if isinstance(payload, TheoryAtomArtifact):
            await self.graph_store.upsert_argument_component(TheoryAtomCodec.to_domain(payload))
            return

        if isinstance(payload, TheoryRelationArtifact):
            rel = TheoryRelationCodec.to_domain(payload)
            await self.graph_store.upsert_theory_relation(rel)
            return

        if isinstance(payload, CanonicalizationArtifact):
            # Write a SAME_AS edge from each duplicate to the canonical entity
            for original_id in payload.original_artifact_ids:
                if original_id != payload.canonical_id:
                    await self.graph_store.upsert_relation(
                        original_id,
                        "SAME_AS",
                        payload.canonical_id,
                        {"confidence": 1.0, "source": "phase3b_consolidation"},
                    )
            return

        if isinstance(payload, _NOT_PROJECTED):
            return

        logger.warning(
            "No projection rule for payload %s (artifact %s, phase %s) — dropped.",
            type(payload).__name__,
            artifact.artifact_id,
            artifact.phase_name,
        )
