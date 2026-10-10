"""Artifact-to-graph projection for the current migration bridge."""

from __future__ import annotations

import logging

from episteme_pipeline.artifacts.builders import parse_mention_id
from episteme_pipeline.artifacts.models import (
    TheoryAtomArtifact,
    TheoryRelationArtifact,
    ArtifactEnvelope,
    CanonicalizationArtifact,
    ChunkArtifact,
    DocumentArtifact,
    EntityMentionArtifact,
    FusionDecisionArtifact,
    GlobalRelationArtifact,
    LinkedEntityArtifact,
    LocalRelationArtifact,
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
            await self.graph_store.upsert_chunk(
                L1Chunk(
                    id=payload.chunk_id,
                    text=payload.text,
                    source_doc_id=payload.document_id,
                    chapter_id=payload.chapter_id,
                    sequence_index=payload.sequence_index,
                    token_count=payload.token_count,
                )
            )
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
            # Reconstruct source_chunk_ids from mention ids ("mention::<entity_id>::<chunk_id>")
            chunk_ids: list[str] = []
            for mid in payload.mention_ids:
                _, chunk_id = parse_mention_id(mid)
                if chunk_id:
                    chunk_ids.append(chunk_id)
            # De-duplicate while preserving order
            seen: set[str] = set()
            uniq_chunk_ids = [c for c in chunk_ids if not (c in seen or seen.add(c))]

            await self.graph_store.upsert_entity(
                L2Entity(
                    id=payload.entity_id,
                    label=payload.entity_type,
                    name=payload.canonical_name,
                    description=payload.description,
                    textual_envelope=payload.textual_envelope,
                    is_mature=payload.is_mature,
                    confidence=payload.confidence,
                    source_chunk_ids=uniq_chunk_ids,
                )
            )
            return

        if isinstance(payload, LocalRelationArtifact):
            await self.graph_store.upsert_triple(
                L2Triple(
                    subject_id=payload.subject_entity_id,
                    predicate=payload.predicate,
                    object_id=payload.object_entity_id,
                    confidence=payload.confidence,
                    scope="local",
                    source_chunk_id=payload.source_chunk_id,
                )
            )
            return

        if isinstance(payload, GlobalRelationArtifact):
            await self.graph_store.upsert_triple(
                L2Triple(
                    subject_id=payload.subject_entity_id,
                    predicate=payload.predicate,
                    object_id=payload.object_entity_id,
                    confidence=payload.confidence,
                    scope="global",
                    source_chunk_id=payload.supporting_chunk_ids[0] if payload.supporting_chunk_ids else "",
                )
            )
            return

        if isinstance(payload, TheoryAtomArtifact):
            await self.graph_store.upsert_argument_component(
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
            return

        if isinstance(payload, TheoryRelationArtifact):
            polarity = self.schema.relation_polarities.get(payload.relation_type, 0)
            if polarity == 0:
                polarity = self.schema.relation_polarities.get(payload.relation_type.upper(), 0)
            props = payload.to_graph_properties(polarity=polarity)
            rel = TheoryRelation.from_graph_properties(
                source_id=payload.source_component_id,
                relation_type=payload.relation_type,
                target_id=payload.target_component_id,
                properties=props,
            )
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
