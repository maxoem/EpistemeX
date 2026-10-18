"""Artifact-to-graph projection with topological bulk batching."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import batched
from typing import TYPE_CHECKING, Any

from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    BaseArtifactPayload,
    DocumentArtifact,
    TheoreticalEnrichmentArtifact,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.protocols.graph_projection import (
    GraphProjectionProtocol,
    ProjectionBatchAccumulator,
)
from episteme_pipeline.protocols.graph_store import ProjectionGraph
from episteme_pipeline.schema.default_schema import SchemaConfig

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import ArtifactCollection

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ProjectionBatch(ProjectionBatchAccumulator):
    """Topological accumulator for bulk artifact-to-graph projection.

    Collects domain and edge items emitted by :class:`BaseArtifactPayload`
    instances and flushes them to a :class:`ProjectionGraph` in topological
    dependency order (**Nodes before Edges**).
    """

    documents: list[DocumentArtifact] = field(default_factory=list)
    chunks: list[L1Chunk] = field(default_factory=list)
    entities: list[L2Entity] = field(default_factory=list)
    theory_atoms: list[TheoryAtom] = field(default_factory=list)
    relations: list[dict[str, Any]] = field(default_factory=list)
    triples: list[L2Triple] = field(default_factory=list)
    theory_relations: list[TheoryRelation] = field(default_factory=list)
    enrichments: list[TheoreticalEnrichmentArtifact] = field(default_factory=list)

    def add_document(self, document: DocumentArtifact) -> None:
        """Register a document payload for node projection."""
        self.documents.append(document)

    def add_chunk(self, chunk: L1Chunk) -> None:
        """Register a domain chunk for bulk node projection."""
        self.chunks.append(chunk)

    def add_entity(self, entity: L2Entity) -> None:
        """Register a domain entity for bulk node projection."""
        self.entities.append(entity)

    def add_theory_atom(self, atom: TheoryAtom) -> None:
        """Register a theory atom for bulk node projection."""
        self.theory_atoms.append(atom)

    def add_relation(self, relation: dict[str, Any]) -> None:
        """Register a generic graph relation spec for bulk edge projection."""
        self.relations.append(relation)

    def add_triple(self, triple: L2Triple) -> None:
        """Register an L2 triple for bulk edge projection."""
        self.triples.append(triple)

    def add_theory_relation(self, relation: TheoryRelation) -> None:
        """Register a theory relation for bulk edge projection."""
        self.theory_relations.append(relation)

    def add_enrichment(self, enrichment: TheoreticalEnrichmentArtifact) -> None:
        """Register a theoretical enrichment payload for post-projection edge updates."""
        self.enrichments.append(enrichment)

    async def flush(
        self, graph_store: ProjectionGraph, batch_size: int = 500
    ) -> None:
        """Flush accumulated items to ``graph_store`` in topological order (Nodes before Edges).

        Parameters
        ----------
        graph_store : ProjectionGraph
            Target projection graph store.
        batch_size : int, default 500
            Maximum number of items per bulk ``GraphWriter`` batch call.
        """
        effective_batch = max(1, batch_size)
        theory_relations = self.theory_relations

        if self.enrichments and theory_relations:
            edge_tenabilities: dict[str, float] = {}
            for enr in self.enrichments:
                edge_tenabilities.update(enr.edge_tenabilities)
            if edge_tenabilities:
                theory_relations = [
                    rel.model_copy(
                        update={
                            "tenability": edge_tenabilities[
                                f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"
                            ]
                        }
                    )
                    if f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"
                    in edge_tenabilities
                    else rel
                    for rel in theory_relations
                ]

        # ------------------------------------------------------------------
        # Pass 1: Nodes (Documents -> Chunks -> Entities -> TheoryAtoms)
        # ------------------------------------------------------------------
        for doc in self.documents:
            await doc.project_to_graph(graph_store)

        for chunk_batch in batched(self.chunks, effective_batch):
            await graph_store.upsert_chunks(list(chunk_batch))

        for entity_batch in batched(self.entities, effective_batch):
            await graph_store.upsert_entities(list(entity_batch))

        for atom_batch in batched(self.theory_atoms, effective_batch):
            await graph_store.upsert_argument_components(list(atom_batch))

        # ------------------------------------------------------------------
        # Pass 2: Edges (Mentions/Canonicalizations -> Triples -> TheoryRelations)
        # ------------------------------------------------------------------
        for rel_batch in batched(self.relations, effective_batch):
            await graph_store.upsert_relations(list(rel_batch))

        for triple_batch in batched(self.triples, effective_batch):
            await graph_store.upsert_triples(list(triple_batch))

        for trel_batch in batched(theory_relations, effective_batch):
            await graph_store.upsert_theory_relations(list(trel_batch))


class ArtifactGraphProjector(GraphProjectionProtocol):
    """Projects durable run artifacts into a :class:`ProjectionGraph` in topological order.

    Parameters
    ----------
    graph_store : ProjectionGraph
        Target projection graph store.
    schema : SchemaConfig or None, optional
        Domain schema configuration.
    """

    def __init__(
        self,
        graph_store: ProjectionGraph,
        schema: SchemaConfig | None = None,
    ) -> None:
        self.graph_store = graph_store
        self.schema = schema or SchemaConfig()

    async def project(self, artifact: ArtifactEnvelope) -> None:
        """Project a single :class:`ArtifactEnvelope` into the target graph.

        Parameters
        ----------
        artifact : ArtifactEnvelope
            Artifact envelope to project.
        """
        payload = artifact.payload
        if isinstance(payload, BaseArtifactPayload):
            await payload.project_to_graph(self.graph_store)
            return

        logger.warning(
            "No projection rule for payload %s (artifact %s, phase %s) — dropped.",
            type(payload).__name__,
            artifact.artifact_id,
            artifact.phase_name,
        )

    async def project_collection(
        self, collection: ArtifactCollection, batch_size: int = 500
    ) -> None:
        """Bulk-project an :class:`ArtifactCollection` in topological order (Nodes before Edges).

        Parameters
        ----------
        collection : ArtifactCollection
            Artifact collection to project (uses ``latest_by_identity``).
        batch_size : int, default 500
            Maximum number of items per bulk ``GraphWriter`` batch call.
        """
        envelopes = list(collection.latest_by_identity.values())
        if not envelopes:
            return

        batch = ProjectionBatch()
        for envelope in envelopes:
            payload = envelope.payload
            if isinstance(payload, BaseArtifactPayload):
                payload.collect_for_projection(batch)
            else:
                logger.warning(
                    "No projection rule for payload %s (artifact %s, phase %s) — dropped.",
                    type(payload).__name__,
                    envelope.artifact_id,
                    envelope.phase_name,
                )

        await batch.flush(self.graph_store, batch_size=batch_size)
