from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    L2Triple,
    PhaseItemRecord,
    SearchResult,
    SubGraph,
    TheoryAtom,
    TheoryRelation,
)


class GraphHandle(ABC):
    """Lifecycle surface shared by every graph-backed handle.

    Each handle owns a driver and a connection pool; leaking one keeps the event
    loop alive at shutdown. ``close()`` was previously an undeclared
    implementation detail that callers relied on anyway (F-11).
    """

    @abstractmethod
    async def close(self) -> None: ...


class GraphReader(GraphHandle, ABC):
    """Read surface for graph-backed pipeline components."""

    @abstractmethod
    async def get_chunks(
        self, filters: dict | None = None, limit: int | None = None
    ) -> list[L1Chunk]: ...

    @abstractmethod
    async def get_entities(
        self,
        labels: list[str] | None = None,
        filters: dict | None = None,
    ) -> list[L2Entity]: ...

    @abstractmethod
    async def get_all_entity_triples(self) -> list[L2Triple]: ...

    @abstractmethod
    async def get_neighborhood(
        self, node_id: str, depth: int = 1
    ) -> SubGraph:
        """Return a depth-limited structural neighborhood around a node.

        Parameters
        ----------
        node_id
            Identifier of the center node whose local graph context should be
            retrieved.
        depth
            Maximum hop distance from ``node_id`` to include in the returned
            neighborhood.

        Returns
        -------
        SubGraph
            Serializable neighborhood snapshot centered on ``node_id``. The
            result must expose the center identifier, neighboring nodes,
            directed relations, and the requested depth without leaking
            backend-specific driver objects.

        Notes
        -----
        This method defines a pipeline contract, not a storage-engine detail.
        Implementations may use Neo4j, in-memory fixtures, or other backends,
        but consumers should only rely on the ``SubGraph`` semantics.
        """
        ...

    @abstractmethod
    async def vector_search(
        self,
        embedding: list[float],
        top_k: int,
        node_label: str | None = None,
        run_id: str | None = None,
    ) -> list[SearchResult]: ...

    @abstractmethod
    async def get_theory_atoms(self) -> list[TheoryAtom]: ...

    @abstractmethod
    async def get_all_theory_relations(self) -> list[TheoryRelation]: ...

    @abstractmethod
    async def find_entities_by_name(
        self, name: str, label: str | None = None
    ) -> list[L2Entity]: ...

    @abstractmethod
    async def get_entity_envelopes(self, entity_id: str) -> list[str]:
        """Return the stored textual envelopes for ``entity_id``.

        An envelope is the sentence-level context a mention was extracted from.
        Phase 4 maturation needs these to synthesise an entity description, and
        used to guard the call with ``hasattr`` because the contract did not
        declare it. Implementations with no envelope storage return an
        empty list.
        """
        ...

    @abstractmethod
    async def get_chunk_entities(self, chunk_id: str) -> list[L2Entity]:
        """Return all entities extracted from a specific chunk."""
        ...


class GraphWriter(GraphHandle, ABC):
    @abstractmethod
    async def upsert_node(
        self,
        label: str,
        node_id: str,
        properties: dict,
        *,
        extra_labels: tuple[str, ...] = (),
        create_only_properties: dict | None = None,
    ) -> None:
        """Idempotently write a node identified by ``label`` and ``node_id``.

        ``extra_labels`` are additional labels stamped on the node (the
        ``:Entity`` marker, F-05). ``create_only_properties`` are written once,
        when the node is first created, and never rewritten — first-seen
        timestamps belong here so that re-running an unchanged corpus leaves the
        graph byte-identical (F-11).
        """
        ...

    @abstractmethod
    async def prune_document_children(
        self,
        document_id: str,
        *,
        keep_chunk_ids: list[str],
        keep_chapter_ids: list[str],
    ) -> dict[str, int]:
        """Delete the document's Chapter/Chunk nodes that are no longer produced.

        Chunk identity is content-addressed, so re-ingesting an edited source
        creates new chunk nodes rather than updating the old ones. Callers pass
        the ids the current ingest produced; everything else under
        ``document_id`` is removed. Returns ``{"chunks": n, "chapters": n}``.
        """
        ...

    @abstractmethod
    async def upsert_relation(
        self,
        from_id: str,
        relation_type: str,
        to_id: str,
        properties: dict | None = None,
    ) -> None: ...

    @abstractmethod
    async def upsert_relations(
        self, relations: list[dict]
    ) -> None: ...

    @abstractmethod
    async def upsert_chunk(self, chunk: L1Chunk) -> None: ...

    @abstractmethod
    async def upsert_chunks(self, chunks: list[L1Chunk]) -> None: ...

    @abstractmethod
    async def upsert_entity(self, entity: L2Entity) -> None: ...

    @abstractmethod
    async def upsert_entities(self, entities: list[L2Entity]) -> None: ...

    @abstractmethod
    async def upsert_triple(self, triple: L2Triple) -> None: ...

    @abstractmethod
    async def upsert_triples(self, triples: list[L2Triple]) -> None: ...

    @abstractmethod
    async def upsert_argument_component(
        self, component: TheoryAtom
    ) -> None: ...
    
    @abstractmethod
    async def upsert_argument_components(
        self, components: list[TheoryAtom]
    ) -> None: ...

    @abstractmethod
    async def upsert_theory_relation(
        self, relation: TheoryRelation
    ) -> None: ...

    @abstractmethod
    async def upsert_theory_relations(
        self, relations: list[TheoryRelation]
    ) -> None: ...

    @abstractmethod
    async def upsert_community(self, community_id: str, level: int, entity_ids: list[str]) -> None: ...

    @abstractmethod
    async def upsert_communities(self, communities: list[dict]) -> None: ...


class PhaseCheckpointStore(GraphHandle, ABC):
    @abstractmethod
    async def mark_chunk_processed(self, chunk_id: str, phase: str) -> None: ...
    
    @abstractmethod
    async def mark_chunks_processed(self, chunk_ids: list[str], phase: str) -> None: ...

    @abstractmethod
    async def get_unprocessed_chunks(
        self, phase: str, limit: int | None = None
    ) -> list[L1Chunk]: ...

    @abstractmethod
    async def filter_unprocessed_items(
        self, item_keys: list[str], phase: str
    ) -> list[str]:
        """Filter item keys and return only those not yet marked processed.

        Parameters
        ----------
        item_keys : list[str]
            Candidate item keys to check.
        phase : str
            Phase identifier tag.

        Returns
        -------
        list[str]
            Subset of item keys that have not been marked in the store.
        """
        ...

    @abstractmethod
    async def commit_phase_batch(
        self,
        phase: str,
        triples: list[L2Triple],
        items: list[PhaseItemRecord],
    ) -> None:
        """Atomically commit triples and item checkpoints within a single transaction.

        Parameters
        ----------
        phase : str
            Phase identifier tag.
        triples : list[L2Triple]
            Triples to upsert.
        items : list[PhaseItemRecord]
            Phase item checkpoint records to persist.
        """
        ...

    @abstractmethod
    async def commit_phase_items(
        self, phase: str, items: list[PhaseItemRecord]
    ) -> None:
        """Persist phase item checkpoints without requiring triple upserts.

        Parameters
        ----------
        phase : str
            Phase identifier tag.
        items : list[PhaseItemRecord]
            Phase item checkpoint records to persist.
        """
        ...

    @abstractmethod
    async def save_chunk_state_snapshot(
        self, phase: str, chunk_id: str, snapshot: dict[str, Any]
    ) -> None:
        """Persist a serialized state machine snapshot associated with a chunk checkpoint.

        Parameters
        ----------
        phase : str
            Phase identifier tag.
        chunk_id : str
            Source chunk identifier.
        snapshot : dict[str, Any]
            State dictionary snapshot.
        """
        ...

    @abstractmethod
    async def get_chunk_state_snapshot(
        self, phase: str, chunk_id: str
    ) -> dict[str, Any] | None:
        """Retrieve a prior serialized state machine snapshot for a chunk checkpoint.

        Parameters
        ----------
        phase : str
            Phase identifier tag.
        chunk_id : str
            Source chunk identifier.

        Returns
        -------
        dict[str, Any] or None
            Restored state snapshot, or None if no prior snapshot was recorded.
        """
        ...

    @abstractmethod
    async def clear_phase_checkpoints(self, phase: str) -> None:
        """Clear all item checkpoints for the given phase upon invalidation.

        Parameters
        ----------
        phase : str
            Phase identifier tag.
        """
        ...


    async def get_committed_triples(self, phase: str) -> list[L2Triple]:
        """Return triples committed across prior batches for ``phase``.

        Parameters
        ----------
        phase : str
            Phase identifier (optionally scoped by lineage fingerprint).

        Returns
        -------
        list of L2Triple
            Committed triples for ``phase``.
        """
        return []


class EntityGraph(GraphReader, GraphWriter, ABC):
    """Entity-focused read/write operations."""


class ProjectionGraph(GraphWriter, ABC):
    """Artifact projection write surface."""


class ProcessingGraph(GraphReader, GraphWriter, PhaseCheckpointStore, ABC):
    """Processing surface with graph read/write and checkpoint tracking."""


class FusionGraph(GraphReader, GraphWriter, ABC):
    """Read/write graph surface used by fusion steps."""


__all__ = [
    "EntityGraph",
    "FusionGraph",
    "GraphHandle",
    "GraphReader",
    "GraphWriter",
    "PhaseCheckpointStore",
    "ProcessingGraph",
    "ProjectionGraph",
]
