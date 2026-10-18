"""In-memory GraphReader backed deterministically by run artifacts.

Provides :class:`ArtifactSubgraphReader`, an implementation of
:class:`~episteme_pipeline.protocols.graph_store.GraphReader` constructed
purely from an :class:`~episteme_pipeline.artifacts.execution.ArtifactCollection`
or :class:`~episteme_pipeline.artifacts.execution.EpistemicStateView`. This
decouples all pipeline phases (Phases 1–6 and post-processing) from reading
mutable shared Neo4j state during execution.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    SearchResult,
    SubGraph,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.protocols.graph_store import GraphReader

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import (
        ArtifactCollection,
        EpistemicStateView,
    )


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors.

    Parameters
    ----------
    vec_a : list of float
        First vector.
    vec_b : list of float
        Second vector.

    Returns
    -------
    float
        Cosine similarity in ``[-1.0, 1.0]``, or ``0.0`` if norms are zero or
        dimensions mismatch.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a <= 1e-12 or norm_b <= 1e-12:
        return 0.0
    return float(dot / (norm_a * norm_b))


class ArtifactSubgraphReader(GraphReader):
    """Deterministic in-memory :class:`GraphReader` over an artifact view or collection.

    Parameters
    ----------
    documents : Iterable of L1Document, optional
        Hydrated document contracts from Phase 1.
    chunks : Iterable of L1Chunk, optional
        Hydrated chunk contracts from Phase 1.
    entities : Iterable of L2Entity, optional
        Canonical, matured entity contracts from Phases 2 / 3b / 4-maturation.
    triples : Iterable of L2Triple, optional
        Canonical local and global relation triples from Phases 2 / 3.
    theory_atoms : Iterable of TheoryAtom, optional
        Canonical or raw theory atoms from Phases 4 / 5 / 6.
    theory_relations : Iterable of TheoryRelation, optional
        Canonical or raw theory relations from Phases 4 / 5 / 6.
    entity_envelopes : dict of str to list of str, optional
        Mapping from canonical ``entity_id`` to all local mention textual envelopes.
    entity_mentions : dict of str to list of dict, optional
        Mapping from canonical ``entity_id`` to mention metadata records
        (``{"mention_id": str, "chunk_id": str}``).
    """

    def __init__(
        self,
        *,
        documents: Iterable[L1Document] = (),
        chunks: Iterable[L1Chunk] = (),
        entities: Iterable[L2Entity] = (),
        triples: Iterable[L2Triple] = (),
        theory_atoms: Iterable[TheoryAtom] = (),
        theory_relations: Iterable[TheoryRelation] = (),
        entity_envelopes: dict[str, list[str]] | None = None,
        entity_mentions: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._documents: dict[str, L1Document] = {d.id: d for d in documents}
        self._chunks: dict[str, L1Chunk] = {c.id: c for c in chunks}
        self._entities: dict[str, L2Entity] = {e.id: e for e in entities}
        self._triples: list[L2Triple] = list(triples)
        self._theory_atoms: dict[str, TheoryAtom] = {a.id: a for a in theory_atoms}
        self._theory_relations: list[TheoryRelation] = list(theory_relations)
        self._entity_envelopes: dict[str, list[str]] = {
            eid: list(envs) for eid, envs in (entity_envelopes or {}).items()
        }
        for ent in self._entities.values():
            if ent.textual_envelope:
                bucket = self._entity_envelopes.setdefault(ent.id, [])
                if ent.textual_envelope not in bucket:
                    bucket.append(ent.textual_envelope)
        self._entity_mentions: dict[str, list[dict[str, Any]]] = {
            eid: list(recs) for eid, recs in (entity_mentions or {}).items()
        }
        self._communities: list[dict[str, Any]] = []

    @classmethod
    def from_view(cls, view: EpistemicStateView) -> ArtifactSubgraphReader:
        """Construct an :class:`ArtifactSubgraphReader` from an :class:`EpistemicStateView`.

        Parameters
        ----------
        view : EpistemicStateView
            Cumulative inter-phase artifacts view.

        Returns
        -------
        ArtifactSubgraphReader
            Populated in-memory graph reader.
        """
        atoms = (
            view.canonical_theory_atoms
            if view.canonical_theory_atoms
            else view.theory_atoms
        )
        relations = (
            view.canonical_theory_relations
            if view.canonical_theory_relations
            else view.theory_relations
        )
        return cls(
            documents=view.documents,
            chunks=view.chunks,
            entities=view.entities,
            triples=[*view.local_triples, *view.global_triples],
            theory_atoms=atoms,
            theory_relations=relations,
            entity_envelopes=view.entity_envelopes_by_id,
            entity_mentions=view.entity_mentions_by_id,
        )

    @classmethod
    def from_collection(
        cls, collection: ArtifactCollection
    ) -> ArtifactSubgraphReader:
        """Construct an :class:`ArtifactSubgraphReader` directly from an :class:`ArtifactCollection`.

        Parameters
        ----------
        collection : ArtifactCollection
            Run artifact collection.

        Returns
        -------
        ArtifactSubgraphReader
            Populated in-memory graph reader with canonical L2/L3 resolution applied.
        """
        from episteme_pipeline.artifacts.execution import Phase4ArtifactsView

        view = Phase4ArtifactsView.from_collection(collection)
        return cls.from_view(view)

    def register_entity(
        self, entity: L2Entity, envelope: str | None = None
    ) -> None:
        """Register or update an entity in the in-memory reader during intra-phase discovery.

        Parameters
        ----------
        entity : L2Entity
            Discovered or linked entity.
        envelope : str or None, optional
            Optional local mention textual envelope.
        """
        existing = self._entities.get(entity.id)
        if existing is not None:
            merged_chunks = list(
                dict.fromkeys([*existing.source_chunk_ids, *entity.source_chunk_ids])
            )
            self._entities[entity.id] = existing.model_copy(
                update={"source_chunk_ids": merged_chunks}
            )
        else:
            self._entities[entity.id] = entity

        env_text = envelope or entity.textual_envelope
        if env_text:
            bucket = self._entity_envelopes.setdefault(entity.id, [])
            if env_text not in bucket:
                bucket.append(env_text)

    def register_triple(self, triple: L2Triple) -> None:
        """Register an :class:`L2Triple` in the in-memory reader.

        Parameters
        ----------
        triple : L2Triple
            Discovered relation triple.
        """
        self._triples.append(triple)

    def register_theory_atom(self, atom: TheoryAtom) -> None:
        """Register a single :class:`TheoryAtom` in the in-memory reader.

        Parameters
        ----------
        atom : TheoryAtom
            Extracted or classified theory atom.
        """
        self._theory_atoms[atom.id] = atom

    def register_theory_atoms(self, atoms: Iterable[TheoryAtom]) -> None:
        """Register :class:`TheoryAtom` instances in the in-memory reader.

        Parameters
        ----------
        atoms : Iterable of TheoryAtom
            Extracted or classified theory atoms.
        """
        for atom in atoms:
            self.register_theory_atom(atom)

    def register_theory_relation(self, relation: TheoryRelation) -> None:
        """Register a single :class:`TheoryRelation` in the in-memory reader.

        Parameters
        ----------
        relation : TheoryRelation
            Extracted or classified theory relation.
        """
        self._theory_relations.append(relation)

    def register_theory_relations(self, relations: Iterable[TheoryRelation]) -> None:
        """Register :class:`TheoryRelation` instances in the in-memory reader.

        Parameters
        ----------
        relations : Iterable of TheoryRelation
            Extracted or classified theory relations.
        """
        for relation in relations:
            self.register_theory_relation(relation)

    async def get_existing_chunk_ids(self) -> set[str]:
        """Return the set of chunk IDs present in this reader.

        Returns
        -------
        set of str
            Chunk identifiers.
        """
        return set(self._chunks.keys())

    async def get_chunks(
        self,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[L1Chunk]:
        """Return chunks matching optional attribute filters.

        Parameters
        ----------
        filters : dict of str to Any or None, optional
            Attribute filter pairs (e.g. ``{"source_doc_id": "doc-1"}``).
        limit : int or None, optional
            Maximum number of chunks to return.

        Returns
        -------
        list of L1Chunk
            Ordered list of matching chunks.
        """
        chunks = sorted(
            self._chunks.values(),
            key=lambda c: (c.sequence_index, c.id),
        )
        if filters:
            matched: list[L1Chunk] = []
            for chunk in chunks:
                chunk_dict = chunk.model_dump()
                ok = True
                for k, v in filters.items():
                    if k in chunk_dict and chunk_dict[k] != v:
                        ok = False
                        break
                    if k not in chunk_dict and chunk.metadata.get(k) != v:
                        ok = False
                        break
                if ok:
                    matched.append(chunk)
            chunks = matched
        if limit is not None:
            chunks = chunks[:limit]
        return chunks

    async def get_entities(
        self,
        labels: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[L2Entity]:
        """Return canonical entities matching optional label and property filters.

        Parameters
        ----------
        labels : list of str or None, optional
            Allowed entity labels.
        filters : dict of str to Any or None, optional
            Property filter pairs (e.g. ``{"is_mature": False}``).

        Returns
        -------
        list of L2Entity
            Matching canonical entities.
        """
        entities = list(self._entities.values())
        if labels:
            allowed_labels = set(labels)
            entities = [e for e in entities if e.label in allowed_labels]
        if filters:
            matched: list[L2Entity] = []
            for entity in entities:
                ent_dict = entity.model_dump()
                if all(ent_dict.get(k) == v for k, v in filters.items()):
                    matched.append(entity)
            entities = matched
        return entities

    async def get_all_entity_triples(self) -> list[L2Triple]:
        """Return all canonical local and global entity triples.

        Returns
        -------
        list of L2Triple
            All triples in the artifact subgraph.
        """
        return list(self._triples)

    async def get_neighborhood(self, node_id: str, depth: int = 1) -> SubGraph:
        """Return the k-hop relational neighborhood around ``node_id``.

        Supports both L2 entity IDs and L3 :class:`TheoryAtom` IDs (expanding
        from the atom's linked ``entity_ids`` as well as direct triples).

        Parameters
        ----------
        node_id : str
            Center entity or theory atom identifier.
        depth : int, default 1
            Number of traversal hops.

        Returns
        -------
        SubGraph
            Local neighborhood containing connected entities and triples.
        """
        frontier: set[str] = {node_id}
        atom = self._theory_atoms.get(node_id)
        if atom is not None and atom.entity_ids:
            frontier.update(atom.entity_ids)

        visited_nodes: set[str] = set(frontier)
        collected_triples: list[L2Triple] = []
        seen_triple_keys: set[tuple[str, str, str, str]] = set()

        for _ in range(max(1, depth)):
            next_frontier: set[str] = set()
            for triple in self._triples:
                if triple.subject_id in frontier or triple.object_id in frontier:
                    tkey = (
                        triple.subject_id,
                        triple.predicate,
                        triple.object_id,
                        triple.scope,
                    )
                    if tkey not in seen_triple_keys:
                        seen_triple_keys.add(tkey)
                        collected_triples.append(triple)
                    if triple.subject_id not in visited_nodes:
                        next_frontier.add(triple.subject_id)
                    if triple.object_id not in visited_nodes:
                        next_frontier.add(triple.object_id)
            visited_nodes.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break

        nodes: list[L2Entity] = [
            self._entities[nid]
            for nid in sorted(visited_nodes)
            if nid in self._entities
        ]
        return SubGraph(
            center_id=node_id,
            nodes=nodes,
            triples=collected_triples,
            depth=depth,
        )

    async def vector_search(
        self,
        embedding: list[float],
        top_k: int,
        node_label: str | None = None,
        run_id: str | None = None,
    ) -> list[SearchResult]:
        """Perform in-memory cosine similarity search over chunk embeddings.

        Parameters
        ----------
        embedding : list of float
            Query vector.
        top_k : int
            Maximum results to return.
        node_label : str or None, optional
            Optional target node label filter (e.g. ``"Chunk"``).
        run_id : str or None, optional
            Optional run identifier (unused in isolated artifact reader).

        Returns
        -------
        list of SearchResult
            Ranked similarity search results.
        """
        results: list[SearchResult] = []
        if node_label is None or node_label.lower() == "chunk":
            for chunk in self._chunks.values():
                if chunk.embedding:
                    score = _cosine_similarity(embedding, chunk.embedding)
                    results.append(
                        SearchResult(
                            node_id=chunk.id,
                            score=score,
                            properties={
                                "id": chunk.id,
                                "text": chunk.text,
                                "source_doc_id": chunk.source_doc_id,
                            },
                        )
                    )
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def get_theory_atoms(self) -> list[TheoryAtom]:
        """Return all :class:`TheoryAtom` nodes in the artifact subgraph.

        Returns
        -------
        list of TheoryAtom
            Hydrated theory atoms.
        """
        return list(self._theory_atoms.values())

    async def get_all_theory_relations(self) -> list[TheoryRelation]:
        """Return all :class:`TheoryRelation` edges in the artifact subgraph.

        Returns
        -------
        list of TheoryRelation
            Hydrated theory relations.
        """
        return list(self._theory_relations)

    async def find_entities_by_name(
        self, name: str, label: str | None = None
    ) -> list[L2Entity]:
        """Find entities by case-insensitive exact or substring name match.

        Parameters
        ----------
        name : str
            Surface form or canonical name to search for.
        label : str or None, optional
            Optional entity label filter.

        Returns
        -------
        list of L2Entity
            Matching entities ordered by exact match priority then confidence.
        """
        query = name.strip().lower()
        if not query:
            return []
        exact_matches: list[L2Entity] = []
        substring_matches: list[L2Entity] = []
        for entity in self._entities.values():
            if label and entity.label != label:
                continue
            cand = entity.name.strip().lower()
            if cand == query:
                exact_matches.append(entity)
            elif query in cand or cand in query:
                substring_matches.append(entity)
        exact_matches.sort(key=lambda e: e.confidence, reverse=True)
        substring_matches.sort(key=lambda e: e.confidence, reverse=True)
        return [*exact_matches, *substring_matches]

    async def get_entity_envelopes(self, entity_id: str) -> list[str]:
        """Return all local textual envelopes recorded for ``entity_id``.

        Parameters
        ----------
        entity_id : str
            Target entity identifier.

        Returns
        -------
        list of str
            List of textual envelopes from all mentions of ``entity_id``.
        """
        envelopes = list(self._entity_envelopes.get(entity_id, []))
        if not envelopes:
            ent = self._entities.get(entity_id)
            if ent is not None and ent.textual_envelope:
                envelopes.append(ent.textual_envelope)
        return envelopes

    async def get_entity_mentions(self, entity_id: str) -> list[dict[str, Any]]:
        """Return mention metadata dicts ``{"mention_id": ..., "chunk_id": ...}`` for ``entity_id``.

        Parameters
        ----------
        entity_id : str
            Target entity identifier.

        Returns
        -------
        list of dict
            Mention metadata records.
        """
        records = list(self._entity_mentions.get(entity_id, []))
        if not records:
            ent = self._entities.get(entity_id)
            if ent is not None:
                for cid in ent.source_chunk_ids:
                    records.append(
                        {
                            "mention_id": f"mention::{entity_id}::{cid}",
                            "chunk_id": cid,
                        }
                    )
        return records

    async def get_chunk_entities(self, chunk_id: str) -> list[L2Entity]:
        """Return all canonical entities extracted from ``chunk_id``.

        Parameters
        ----------
        chunk_id : str
            Source chunk identifier.

        Returns
        -------
        list of L2Entity
            Entities whose ``source_chunk_ids`` or mentions include ``chunk_id``.
        """
        matched: list[L2Entity] = []
        for entity in self._entities.values():
            if chunk_id in entity.source_chunk_ids:
                matched.append(entity)
                continue
            mentions = self._entity_mentions.get(entity.id, [])
            if any(m.get("chunk_id") == chunk_id for m in mentions):
                matched.append(entity)
        return matched

    async def upsert_community(
        self, community_id: str, level: int, entity_ids: list[str]
    ) -> None:
        """Record a detected Leiden community in memory.

        Parameters
        ----------
        community_id : str
            Community identifier.
        level : int
            Hierarchical Leiden level.
        entity_ids : list of str
            Member node identifiers.
        """
        self._communities.append(
            {
                "community_id": community_id,
                "level": level,
                "entity_ids": list(entity_ids),
            }
        )

    async def upsert_communities(self, communities: list[dict[str, Any]]) -> None:
        """Record a batch of detected Leiden communities in memory.

        Parameters
        ----------
        communities : list of dict
            Community specifications.
        """
        for comm in communities:
            await self.upsert_community(
                comm["community_id"],
                int(comm.get("level", 0)),
                list(comm.get("entity_ids", [])),
            )

    async def close(self) -> None:
        """Close reader resources (no-op for in-memory reader)."""
        return None
