from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import ArtifactCollection
    from episteme_pipeline.artifacts.models import (
        ArtifactEnvelope,
        ArtifactPayload,
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


class ProjectionBatchAccumulator(Protocol):
    """Accumulator interface collecting typed domain and relation items for bulk projection."""

    def add_document(self, document: DocumentArtifact) -> None:
        """Register a document payload for node projection."""
        ...

    def add_chunk(self, chunk: L1Chunk) -> None:
        """Register a domain chunk for bulk node projection."""
        ...

    def add_entity(self, entity: L2Entity) -> None:
        """Register a domain entity for bulk node projection."""
        ...

    def add_theory_atom(self, atom: TheoryAtom) -> None:
        """Register a theory atom for bulk node projection."""
        ...

    def add_relation(self, relation: dict[str, Any]) -> None:
        """Register a generic graph relation spec for bulk edge projection."""
        ...

    def add_triple(self, triple: L2Triple) -> None:
        """Register an L2 triple for bulk edge projection."""
        ...

    def add_theory_relation(self, relation: TheoryRelation) -> None:
        """Register a theory relation for bulk edge projection."""
        ...

    def add_enrichment(self, enrichment: TheoreticalEnrichmentArtifact) -> None:
        """Register a theoretical enrichment payload for post-projection edge updates."""
        ...


class GraphProjectionProtocol(ABC):
    """Projects durable artifacts into the graph representation."""

    @abstractmethod
    async def project(self, artifact: ArtifactEnvelope[ArtifactPayload]) -> None:
        """Project a single artifact envelope into the target graph."""
        ...

    async def project_collection(
        self, collection: ArtifactCollection, batch_size: int = 500
    ) -> None:
        """Project an :class:`ArtifactCollection` into the target graph in bulk.

        Parameters
        ----------
        collection : ArtifactCollection
            Collection of artifact envelopes to project.
        batch_size : int, default 500
            Maximum items per bulk write call.
        """
        for artifact in collection.latest_by_identity.values():
            await self.project(artifact)
