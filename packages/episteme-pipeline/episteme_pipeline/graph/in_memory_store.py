"""In-memory graph store implementation conforming to ProcessingGraph.

Enables pure in-memory execution of the pipeline and evaluation harness without
requiring a running Neo4j instance or network connectivity.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
)
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
from episteme_pipeline.protocols.graph_store import ProcessingGraph


def deterministic_text_embedding(text: str, dim: int = 128) -> list[float]:
    """Compute a deterministic hash-based unit embedding for offline testing.

    Parameters
    ----------
    text : str
        Input textual string.
    dim : int, optional
        Dimensionality of the embedding vector (default: 128).

    Returns
    -------
    list of float
        L2-normalized embedding vector.
    """
    if not text:
        return [0.0] * dim
    vec = [0.0] * dim
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return [0.0] * dim
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 7) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


class InMemoryGraphStore(ProcessingGraph):
    """In-memory graph store for offline execution and evaluation."""

    def __init__(self) -> None:
        self._chunks: dict[str, L1Chunk] = {}
        self._entities: dict[str, L2Entity] = {}
        self._triples: list[L2Triple] = []
        self._theory_atoms: dict[str, TheoryAtom] = {}
        self._theory_relations: list[TheoryRelation] = []
        self._generic_relations: list[dict[str, Any]] = []
        self._processed_chunks: dict[str, set[str]] = {}  # chunk_id -> set of phase tags
        self._processed_items: dict[str, dict[str, PhaseItemRecord]] = {}
        self._nodes: dict[str, dict[str, Any]] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._node_run_ids: dict[str, str] = {}

    async def close(self) -> None:
        """Close handle (no-op for in-memory)."""
        pass

    async def get_chunks(
        self, filters: dict | None = None, limit: int | None = None
    ) -> list[L1Chunk]:
        chunks = list(self._chunks.values())
        if limit:
            chunks = chunks[:limit]
        return chunks

    async def get_entities(
        self,
        labels: list[str] | None = None,
        filters: dict | None = None,
    ) -> list[L2Entity]:
        entities = list(self._entities.values())
        if labels:
            entities = [e for e in entities if e.label in labels]
        return entities

    async def get_all_entity_triples(self) -> list[L2Triple]:
        return list(self._triples)

    async def get_neighborhood(self, node_id: str, depth: int = 1) -> SubGraph:
        neighbor_nodes = [
            e for e in self._entities.values() if e.id != node_id
        ][:10]
        neighbor_triples = [
            t for t in self._triples if t.subject_id == node_id or t.object_id == node_id
        ]
        return SubGraph(
            center_id=node_id,
            nodes=neighbor_nodes,
            triples=neighbor_triples,
            depth=depth,
        )

    async def vector_search(
        self,
        embedding: list[float] | None = None,
        top_k: int = 10,
        node_label: str | None = None,
        run_id: str | None = None,
        query_text: str | None = None,
    ) -> list[SearchResult]:
        """Search in-memory entities, atoms, and nodes using embedding cosine similarity."""
        if embedding is None and query_text:
            embedding = deterministic_text_embedding(query_text)

        candidates: dict[str, dict[str, Any]] = {}

        # 0. Ingest chunks
        for cid, chunk in self._chunks.items():
            if cid not in candidates:
                candidates[cid] = {
                    "node_id": cid,
                    "node_label": "Chunk",
                    "node_name": cid,
                    "text": chunk.text,
                    "run_id": self._node_run_ids.get(cid),
                }

        # 1. Ingest entities
        for ent in self._entities.values():
            candidates[ent.id] = {
                "node_id": ent.id,
                "node_label": ent.label,
                "node_name": ent.name or ent.id,
                "text": f"{ent.name or ''} {ent.description or ''} {ent.textual_envelope or ''}".strip(),
                "run_id": self._node_run_ids.get(ent.id),
            }

        # 2. Ingest theory atoms
        for atom in self._theory_atoms.values():
            if atom.id not in candidates:
                candidates[atom.id] = {
                    "node_id": atom.id,
                    "node_label": atom.component_type,
                    "node_name": atom.id,
                    "text": atom.text or atom.id,
                    "run_id": self._node_run_ids.get(atom.id),
                }

        # 3. Ingest generic nodes
        for nid, props in self._nodes.items():
            if nid not in candidates:
                txt = f"{props.get('name', '')} {props.get('label', '')} {props.get('formalAxiom', '')} {props.get('description', '')}"
                if isinstance(props.get("textAnchor"), dict):
                    txt += " " + str(props["textAnchor"].get("verbatimQuote", ""))
                candidates[nid] = {
                    "node_id": nid,
                    "node_label": str(props.get("label", "Concept")),
                    "node_name": str(props.get("name", nid)),
                    "text": txt.strip(),
                    "run_id": props.get("run_id") or self._node_run_ids.get(nid),
                }

        # Filter by run_id if specified
        if run_id:
            candidates = {k: v for k, v in candidates.items() if v.get("run_id") == run_id}

        # Filter by node_label if specified
        if node_label:
            nl_lower = node_label.lower()
            candidates = {
                k: v for k, v in candidates.items() if nl_lower in v["node_label"].lower()
            }

        scored_results: list[SearchResult] = []
        for nid, cand in candidates.items():
            c_emb = self._embeddings.get(nid)
            if not c_emb and cand["text"]:
                c_emb = deterministic_text_embedding(
                    cand["text"], dim=len(embedding) if embedding else 128
                )
                self._embeddings[nid] = c_emb

            score = 1.0
            if embedding and c_emb:
                dot = sum(a * b for a, b in zip(embedding, c_emb))
                score = max(0.0, float(dot))

            scored_results.append(
                SearchResult(
                    node_id=cand["node_id"],
                    score=score,
                    node_label=cand["node_label"],
                    node_name=cand["node_name"],
                )
            )

        scored_results.sort(key=lambda r: r.score, reverse=True)
        return scored_results[:top_k]

    def index_for_search(self, target: Any, run_id: str | None = None) -> int:
        """Polymorphically index chunks, entities, theory atoms, or graph structures for search.

        Supports ArtifactCollection, list of L1Chunk, list of L2Entity, list of TheoryAtom,
        TheoryNet, epistemetrics.TheoryGraph, and NetworkX DiGraph.

        Parameters
        ----------
        target : Any
            The artifact collection, graph, or list of domain items to index.
        run_id : str | None, optional
            Run identifier to associate with indexed nodes.

        Returns
        -------
        int
            Total number of items indexed.
        """
        indexed_count = 0

        # 1. ArtifactCollection: unpack and index all available layers
        if isinstance(target, ArtifactCollection):
            p1 = Phase1ArtifactsView.from_collection(target)
            for chunk in p1.chunks:
                self._chunks[chunk.id] = chunk
                if run_id:
                    self._node_run_ids[chunk.id] = run_id
                self._embeddings[chunk.id] = deterministic_text_embedding(chunk.text)
                self._nodes[chunk.id] = {
                    "label": "Chunk",
                    "name": chunk.id,
                    "text": chunk.text,
                    "run_id": run_id,
                }
                indexed_count += 1

            p2 = Phase2ArtifactsView.from_collection(target)
            for ent in p2.entities:
                self._entities[ent.id] = ent
                if run_id:
                    self._node_run_ids[ent.id] = run_id
                txt = f"{ent.name or ''} {ent.label or ''} {ent.description or ''}".strip()
                self._embeddings[ent.id] = deterministic_text_embedding(txt)
                self._nodes[ent.id] = {
                    "label": ent.label,
                    "name": ent.name or ent.id,
                    "description": ent.description,
                    "run_id": run_id,
                }
                indexed_count += 1
            for trip in p2.local_triples:
                self._triples.append(trip)

            p3 = Phase3ArtifactsView.from_collection(target)
            for trip in p3.global_triples:
                self._triples.append(trip)

            p4 = Phase4ArtifactsView.from_collection(target)
            for atom in p4.theory_atoms:
                self._theory_atoms[atom.id] = atom
                if run_id:
                    self._node_run_ids[atom.id] = run_id
                txt = f"{atom.id} {atom.component_type} {atom.text or ''}".strip()
                self._embeddings[atom.id] = deterministic_text_embedding(txt)
                self._nodes[atom.id] = {
                    "label": atom.component_type,
                    "name": atom.id,
                    "formalAxiom": atom.text or "",
                    "run_id": run_id,
                }
                indexed_count += 1
            for rel in p4.theory_relations:
                self._theory_relations.append(rel)

            return indexed_count

        # 2. Lists of items
        if isinstance(target, list):
            for item in target:
                if isinstance(item, L1Chunk):
                    self._chunks[item.id] = item
                    if run_id:
                        self._node_run_ids[item.id] = run_id
                    self._embeddings[item.id] = deterministic_text_embedding(item.text)
                    indexed_count += 1
                elif isinstance(item, L2Entity):
                    self._entities[item.id] = item
                    if run_id:
                        self._node_run_ids[item.id] = run_id
                    txt = f"{item.name or ''} {item.label or ''} {item.description or ''}".strip()
                    self._embeddings[item.id] = deterministic_text_embedding(txt)
                    indexed_count += 1
                elif isinstance(item, L2Triple):
                    self._triples.append(item)
                elif isinstance(item, TheoryAtom):
                    self._theory_atoms[item.id] = item
                    if run_id:
                        self._node_run_ids[item.id] = run_id
                    txt = f"{item.id} {item.component_type} {item.text or ''}".strip()
                    self._embeddings[item.id] = deterministic_text_embedding(txt)
                    indexed_count += 1
                elif isinstance(item, TheoryRelation):
                    self._theory_relations.append(item)
            return indexed_count

        # 3. TheoryNet domain object
        if hasattr(target, "atoms"):
            for atom in target.atoms:
                self._theory_atoms[atom.id] = atom
                if run_id:
                    self._node_run_ids[atom.id] = run_id
                txt = f"{atom.id} {atom.component_type} {atom.text or ''}"
                self._embeddings[atom.id] = deterministic_text_embedding(txt)
                indexed_count += 1
            if hasattr(target, "relations"):
                for rel in target.relations:
                    self._theory_relations.append(rel)
            return indexed_count

        # 4. NetworkX DiGraph
        if hasattr(target, "nodes") and callable(getattr(target, "nodes")):
            for nid, data in target.nodes(data=True):
                node_id = str(nid)
                lbl = str(data.get("label", data.get("node_type", "Concept")))
                name = str(data.get("name", node_id))
                axiom = str(data.get("formalAxiom", data.get("formal_axiom", "")))
                quote = ""
                anchor = data.get("anchor") or data.get("textAnchor")
                if isinstance(anchor, dict):
                    quote = str(anchor.get("verbatimQuote", anchor.get("quote", "")))

                txt = f"{name} {lbl} {axiom} {quote}".strip()
                self._nodes[node_id] = {
                    "label": lbl,
                    "name": name,
                    "formalAxiom": axiom,
                    "run_id": run_id,
                    **data,
                }
                if run_id:
                    self._node_run_ids[node_id] = run_id
                self._embeddings[node_id] = deterministic_text_embedding(txt)

                chunk_id = anchor.get("chunkId", "") if isinstance(anchor, dict) else ""
                self._theory_atoms[node_id] = TheoryAtom(
                    id=node_id,
                    text=axiom or quote or name,
                    component_type=lbl,
                    source_chunk_id=chunk_id or f"chunk_{node_id}",
                    confidence=float(data.get("confidence", 1.0)),
                )
                indexed_count += 1

            for u, v, edata in target.edges(data=True):
                rel_str = str(edata.get("relation", edata.get("label", "explains")))
                scope_val = edata.get("scope", "global")
                self._theory_relations.append(
                    TheoryRelation(
                        source_id=str(u),
                        target_id=str(v),
                        relation_type=rel_str,
                        confidence=float(edata.get("confidence", 1.0)),
                        scope=scope_val if scope_val in ("local", "global") else "global",
                    )
                )
            return indexed_count

        # 5. epistemetrics.TheoryGraph
        if hasattr(target, "nodes") and isinstance(target.nodes, dict):
            for nid, node in target.nodes.items():
                node_id = str(nid)
                txt = f"{node.name} {node.node_type} {node.description or ''}"
                self._nodes[node_id] = {
                    "label": str(node.node_type),
                    "name": node.name,
                    "description": node.description,
                    "run_id": run_id,
                    **dict(node.attributes),
                }
                if run_id:
                    self._node_run_ids[node_id] = run_id
                self._embeddings[node_id] = deterministic_text_embedding(txt)
                self._theory_atoms[node_id] = TheoryAtom(
                    id=node_id,
                    text=node.description or node.name,
                    component_type=str(node.node_type),
                    source_chunk_id=node.provenance[0] if node.provenance else f"chunk_{node_id}",
                    confidence=node.confidence,
                )
                indexed_count += 1

            for edge in target.edges:
                edge_scope = edge.attributes.get("scope", "global")
                self._theory_relations.append(
                    TheoryRelation(
                        source_id=str(edge.source),
                        target_id=str(edge.target),
                        relation_type=str(edge.relation_type),
                        confidence=edge.confidence,
                        scope=edge_scope if edge_scope in ("local", "global") else "global",
                    )
                )
            return indexed_count

        return indexed_count

    def index_theory_graph(self, graph: Any, run_id: str | None = None) -> None:
        """Index a TheoryGraph, NetworkX DiGraph, or TheoryNet into this store for search.

        Kept for backward-compatibility with existing callers; delegates to `index_for_search`.

        Parameters
        ----------
        graph : Any
            The graph or theory net container.
        run_id : str | None, optional
            Run identifier to associate with indexed nodes.
        """
        self.index_for_search(graph, run_id=run_id)

    async def get_theory_atoms(self) -> list[TheoryAtom]:
        return list(self._theory_atoms.values())

    async def get_all_theory_relations(self) -> list[TheoryRelation]:
        return list(self._theory_relations)

    async def find_entities_by_name(
        self, name: str, label: str | None = None
    ) -> list[L2Entity]:
        name_lower = name.lower()
        matches = []
        for ent in self._entities.values():
            if ent.name and ent.name.lower() == name_lower:
                if label is None or ent.label == label:
                    matches.append(ent)
        return matches

    async def get_entity_envelopes(self, entity_id: str) -> list[str]:
        ent = self._entities.get(entity_id)
        if ent and ent.textual_envelope:
            return [ent.textual_envelope]
        return []

    async def get_chunk_entities(self, chunk_id: str) -> list[L2Entity]:
        return [
            e
            for e in self._entities.values()
            if chunk_id in (e.source_chunk_ids or [])
        ]

    async def upsert_node(
        self,
        label: str,
        node_id: str,
        properties: dict,
        *,
        extra_labels: tuple[str, ...] = (),
        create_only_properties: dict | None = None,
    ) -> None:
        self._nodes[node_id] = {
            "label": label,
            "extra_labels": extra_labels,
            **properties,
        }

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
        return {"chunks": len(dead), "chapters": 0}

    async def upsert_relation(
        self,
        from_id: str,
        relation_type: str,
        to_id: str,
        properties: dict | None = None,
    ) -> None:
        rel_dict = {
            "from_id": from_id,
            "relation_type": relation_type,
            "to_id": to_id,
            "properties": properties or {},
        }
        self._generic_relations.append(rel_dict)
        self._theory_relations.append(
            TheoryRelation(
                source_id=from_id,
                target_id=to_id,
                relation_type=relation_type,
                confidence=float(properties.get("confidence", 1.0)) if properties else 1.0,
                scope=properties.get("scope", "global") if properties else "global",
                weight=float(properties.get("weight", 1.0)) if properties else 1.0,
            )
        )

    async def upsert_relations(self, relations: list[dict]) -> None:
        for r in relations:
            await self.upsert_relation(
                from_id=r["from_id"],
                relation_type=r["relation_type"],
                to_id=r["to_id"],
                properties=r.get("properties"),
            )

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

    async def upsert_argument_component(self, component: TheoryAtom) -> None:
        self._theory_atoms[component.id] = component

    async def upsert_argument_components(
        self, components: list[TheoryAtom]
    ) -> None:
        for comp in components:
            await self.upsert_argument_component(comp)

    async def upsert_community(
        self, community_id: str, level: int, entity_ids: list[str]
    ) -> None:
        for e_id in entity_ids:
            self._generic_relations.append(
                {
                    "from_id": e_id,
                    "relation_type": "IN_COMMUNITY",
                    "to_id": community_id,
                    "properties": {"level": level},
                }
            )

    async def upsert_communities(self, communities: list[dict]) -> None:
        for c in communities:
            await self.upsert_community(c["community_id"], c["level"], c["entity_ids"])

    async def mark_chunk_processed(self, chunk_id: str, phase: str) -> None:
        self._processed_chunks.setdefault(chunk_id, set()).add(phase)

    async def mark_chunks_processed(self, chunk_ids: list[str], phase: str) -> None:
        for cid in chunk_ids:
            await self.mark_chunk_processed(cid, phase)

    async def get_unprocessed_chunks(
        self, phase: str, limit: int | None = None
    ) -> list[L1Chunk]:
        unprocessed = [
            c
            for c in self._chunks.values()
            if phase not in self._processed_chunks.get(c.id, set())
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
        for record in items:
            phase_items[record.key] = record

    async def clear_phase_checkpoints(self, phase: str) -> None:
        if phase in self._processed_items:
            del self._processed_items[phase]
        for tags in self._processed_chunks.values():
            tags.discard(phase)
