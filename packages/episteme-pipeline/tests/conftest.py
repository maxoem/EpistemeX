"""
Shared test fixtures and in-memory graph store for pipeline unit tests.
"""

from __future__ import annotations

import os

# Ensure Hugging Face and Transformers operate in offline mode during unit tests
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import pytest
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation
from episteme_pipeline.contracts.phase_contracts import (
    L1Chunk,
    L2Entity,
    L2Triple,
    PhaseItemRecord,
    SearchResult,
    SubGraph,
)
from episteme_pipeline.protocols.graph_store import ProcessingGraph
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

# ---------------------------------------------------------------------------
# In-memory GraphStore (no Neo4j required)
# ---------------------------------------------------------------------------


class InMemoryGraphStore(ProcessingGraph):
    """Minimal in-memory implementation for unit testing."""

    def __init__(self) -> None:
        self._chunks: dict[str, L1Chunk] = {}
        self._entities: dict[str, L2Entity] = {}
        self._triples: list[L2Triple] = []
        self._theory_atoms: dict[str, TheoryAtom] = {}
        self._relations: list[tuple[str, str, str, dict]] = []
        self._processed: dict[str, set[str]] = {}  # chunk_id -> set of phase tags
        self._processed_items: dict[str, dict[str, PhaseItemRecord]] = {}

    async def get_chunks(self, filters=None, limit=None) -> list[L1Chunk]:
        chunks = list(self._chunks.values())
        if limit:
            chunks = chunks[:limit]
        return chunks

    async def get_entities(self, labels=None, filters=None) -> list[L2Entity]:
        entities = list(self._entities.values())
        if labels:
            entities = [e for e in entities if e.label in labels]
        return entities

    async def get_neighborhood(self, node_id: str, depth: int = 1) -> SubGraph:
        return SubGraph(center_id=node_id, nodes=[], triples=[], depth=depth)

    async def vector_search(self, embedding, top_k, node_label=None, run_id=None) -> list[SearchResult]:
        return []

    async def upsert_node(
        self,
        label: str,
        node_id: str,
        properties: dict,
        *,
        extra_labels: tuple[str, ...] = (),
        create_only_properties: dict | None = None,
    ) -> None:
        pass  # nodes are tracked via typed methods below

    async def prune_document_children(
        self,
        document_id: str,
        *,
        keep_chunk_ids: list[str],
        keep_chapter_ids: list[str],
    ) -> dict[str, int]:
        keep = set(keep_chunk_ids)
        dead = [
            cid
            for cid, chunk in self._chunks.items()
            if chunk.source_doc_id == document_id and cid not in keep
        ]
        for cid in dead:
            del self._chunks[cid]
        # Chapters are not modelled as nodes here.
        return {"chunks": len(dead), "chapters": 0}

    async def upsert_relation(self, from_id, relation_type, to_id, properties=None) -> None:
        self._relations.append((from_id, relation_type, to_id, properties or {}))

    async def upsert_relations(self, relations: list[dict]) -> None:
        for r in relations:
            await self.upsert_relation(r["from_id"], r["relation_type"], r["to_id"], r.get("properties"))

    async def upsert_chunk(self, chunk: L1Chunk) -> None:
        self._chunks[chunk.id] = chunk

    async def upsert_chunks(self, chunks: list[L1Chunk]) -> None:
        for c in chunks:
            await self.upsert_chunk(c)

    async def upsert_entity(self, entity: L2Entity) -> None:
        self._entities[entity.id] = entity

    async def upsert_entities(self, entities: list[L2Entity]) -> None:
        for e in entities:
            await self.upsert_entity(e)

    async def upsert_triple(self, triple: L2Triple) -> None:
        self._triples.append(triple)

    async def upsert_triples(self, triples: list[L2Triple]) -> None:
        for t in triples:
            await self.upsert_triple(t)

    async def upsert_theory_atom(self, component: TheoryAtom) -> None:
        self._theory_atoms[component.id] = component

    async def upsert_argument_component(self, component: TheoryAtom) -> None:
        self._theory_atoms[component.id] = component

    async def upsert_argument_components(self, components: list[TheoryAtom]) -> None:
        for c in components:
            await self.upsert_argument_component(c)

    async def upsert_theory_relation(self, relation: TheoryRelation) -> None:
        self._relations.append((relation.source_id, relation.relation_type, relation.target_id, relation.to_graph_properties()))

    async def upsert_theory_relations(self, relations: list[TheoryRelation]) -> None:
        for r in relations:
            await self.upsert_theory_relation(r)

    async def get_theory_atoms(self) -> list[TheoryAtom]:
        return list(self._theory_atoms.values())

    async def get_all_entity_triples(self) -> list[L2Triple]:
        return self._triples

    async def upsert_community(self, community_id: str, level: int, entity_ids: list[str]) -> None:
        self._relations.extend([(entity_id, "IN_COMMUNITY", community_id, {"level": level}) for entity_id in entity_ids])

    async def upsert_communities(self, communities: list[dict]) -> None:
        for c in communities:
            await self.upsert_community(c["community_id"], c["level"], c["entity_ids"])

    async def mark_chunk_processed(self, chunk_id: str, phase: str) -> None:
        self._processed.setdefault(chunk_id, set()).add(phase)

    async def mark_chunks_processed(self, chunk_ids: list[str], phase: str) -> None:
        for cid in chunk_ids:
            await self.mark_chunk_processed(cid, phase)

    async def get_unprocessed_chunks(self, phase: str, limit=None) -> list[L1Chunk]:
        unprocessed = [
            c for c in self._chunks.values()
            if phase not in self._processed.get(c.id, set())
        ]
        if limit:
            unprocessed = unprocessed[:limit]
        return unprocessed

    async def filter_unprocessed_items(
        self, item_keys: list[str], phase: str
    ) -> list[str]:
        phase_items = self._processed_items.get(phase, {})
        return [k for k in item_keys if k not in phase_items]

    async def commit_phase_batch(
        self,
        phase: str,
        triples: list[L2Triple],
        items: list[PhaseItemRecord],
    ) -> None:
        await self.upsert_triples(triples)
        phase_items = self._processed_items.setdefault(phase, {})
        for item in items:
            phase_items[item.key] = item

    async def clear_phase_checkpoints(self, phase: str) -> None:
        self._processed_items.pop(phase, None)

    async def find_entities_by_name(self, name: str, label=None) -> list[L2Entity]:
        name_lower = name.strip().lower()
        results = []
        for e in self._entities.values():
            if label and e.label != label:
                continue
            e_lower = e.name.strip().lower()
            if name_lower in e_lower or e_lower in name_lower:
                results.append(e)
        return results

    async def close(self) -> None:
        pass

    async def get_entity_envelopes(self, entity_id: str) -> list[str]:
        return [
            rel[3].get("textual_envelope")
            for rel in self._relations
            if rel[0] == entity_id and rel[1] == "EXTRACTED_FROM" and rel[3].get("textual_envelope")
        ]

    async def get_all_theory_relations(self) -> list[TheoryRelation]:
        return []

    async def get_chunk_entities(self, chunk_id: str) -> list[L2Entity]:
        return []

    async def upsert_argument_component(self, component: TheoryAtom) -> None:
        await self.upsert_theory_atom(component)

    async def upsert_argument_components(self, components: list[TheoryAtom]) -> None:
        for c in components:
            await self.upsert_argument_component(c)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def schema() -> SchemaConfig:
    return DEFAULT_SCHEMA


@pytest.fixture
def graph_store() -> InMemoryGraphStore:
    return InMemoryGraphStore()


@pytest.fixture
def config() -> PipelineConfig:
    return PipelineConfig()


@pytest.fixture
def sample_chunk() -> L1Chunk:
    return L1Chunk(
        id="chunk_0001",
        text="Kant argued that space is a form of intuition. Hegel disagreed.",
        source_doc_id="doc_kant",
        chapter_id="doc_kant_chap_intro",
        sequence_index=0,
        token_count=14,
    )


@pytest.fixture
def sample_entities() -> list[L2Entity]:
    return [
        L2Entity(id="entity_kant", label="PERSON", name="Kant", source_chunk_ids=["chunk_0001"]),
        L2Entity(id="entity_hegel", label="PERSON", name="Hegel", source_chunk_ids=["chunk_0001"]),
        L2Entity(id="entity_space", label="KONZEPT", name="space", source_chunk_ids=["chunk_0001"]),
        L2Entity(id="entity_time", label="KONZEPT", name="time", source_chunk_ids=["chunk_0002"]),
    ]
