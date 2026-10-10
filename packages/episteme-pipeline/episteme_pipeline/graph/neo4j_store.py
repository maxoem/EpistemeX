"""
Neo4j graph components split by responsibility.

Node taxonomy
-------------
Every L2 entity node carries an explicit ``:Entity`` marker label in addition to
its semantic label (``:Concept``, ``:Theory``, ...). Reads select on that marker.

Before F-05 the reads instead identified entities *by exclusion* — "anything
that is not a ``:Chunk``, ``:Chapter`` or ``:Document``" — which silently swept
up the ``:TheoryAtom`` nodes written by Phase 4 and the ``:Community``
nodes written by fusion. On any re-run against a populated graph, Phase 3, Phase
3b and Phase 4 maturation all pulled argument components into their entity sets.

For a graph populated before the marker existed, call
:meth:`_Neo4jWriteMixin.backfill_entity_labels` once.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any

from pydantic import BaseModel

from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    L2Triple,
    Measurement,
    SearchResult,
    SubGraph,
    TenabilityResult,
    TheoryAtom,
    TheoryRelation,
    PhaseItemRecord,
)
from episteme_pipeline.protocols.graph_store import (
    EntityGraph,
    FusionGraph,
    PhaseCheckpointStore,
    ProcessingGraph,
    ProjectionGraph,
)

logger = logging.getLogger(__name__)

#: Marker label stamped on every L2 entity node, and the label reads select on.
ENTITY_LABEL = "Entity"

#: Labels that are structurally *not* entities. Used only by the one-time
#: backfill migration, which has to reproduce the old exclusion heuristic.
_NON_ENTITY_LABELS = ("Chunk", "Chapter", "Document", "TheoryAtom", "Community")

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _cypher_identifier(value: str, *, kind: str) -> str:
    """Validate a label, relationship type or property name before interpolation.

    Cypher cannot parameterise these, so they have to be interpolated into the
    query string — and they come straight from LLM output (``entity.label``,
    ``triple.predicate``). A backtick or newline in a generated predicate breaks
    the query or injects into it; a space produces a label that is unqueryable
    without backticks at every later call site (F-11).

    Whitespace is normalised to underscores because "Political Theory" is a
    plausible model output with an obvious intended meaning. Anything still
    outside ``[A-Za-z_][A-Za-z0-9_]*`` is rejected rather than escaped: it
    signals a broken extraction upstream, and writing it would put a node into
    the graph that no later query can find.
    """
    normalised = "_".join(str(value).split())
    if not _IDENTIFIER_RE.match(normalised):
        raise ValueError(
            f"Unsafe Cypher {kind} {value!r}: expected a name of letters, digits "
            "and underscores not starting with a digit."
        )
    return normalised


def _is_homogeneous_primitive_list(items: list | tuple) -> bool:
    """Check whether all items are primitive and share an identical type for Neo4j array storage.

    Neo4j prohibits heterogeneous arrays (e.g. mixed int and string, or bool and int).
    """
    if not items:
        return True
    first = items[0]
    if isinstance(first, bool):
        expected_type = bool
    elif isinstance(first, int):
        expected_type = int
    elif isinstance(first, float):
        expected_type = float
    elif isinstance(first, str):
        expected_type = str
    else:
        return False

    return all(type(item) is expected_type for item in items)


def _serialize_prop_value(value: Any) -> Any:
    """Coerce a Python value into a Neo4j Cypher-compatible property type.

    Parameters
    ----------
    value : Any
        Property value to serialize or coerce.

    Returns
    -------
    Any
        Coerced primitive value, list of primitives, JSON string, or None if unset.
    """
    if value is None:
        return None
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        if not value:
            return None
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        if not value:
            return []
        if _is_homogeneous_primitive_list(value):
            return list(value)
        serialized_items = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            for item in value
        ]
        return json.dumps(serialized_items, ensure_ascii=False)
    return value


def _writable_props(properties: dict) -> dict:
    """Prepare property dictionary ahead of ``SET n += $props``.

    Setting a property to ``null`` in Cypher **removes** it. So an upsert that
    carries unset optional fields does not leave them alone — it erases whatever
    an earlier phase wrote there. Phase 4 maturation writes a synthesised
    ``description``; a later Phase 2 re-run re-linking the same entity would
    upsert ``description=None`` and wipe it (F-06).

    Additionally, Neo4j prohibits nested Maps (dictionaries) and lists of maps.
    This helper serializes non-primitive structures (e.g. ``parameters``,
    ``measurements``, ``tenability``) to JSON strings, and prunes ``None``
    and empty mappings (dictionaries) so they never trigger ``CypherTypeError: Map{}``.

    Nothing in the pipeline needs to clear a property, so ``None`` is read as
    "no opinion" rather than "delete".

    Parameters
    ----------
    properties : dict
        Raw properties dictionary intended for Cypher persistence.

    Returns
    -------
    dict
        Cleaned properties dictionary containing only Cypher-compatible primitive
        types, primitive lists, and JSON-encoded complex structures.
    """
    out = {}
    for key, value in properties.items():
        serialized = _serialize_prop_value(value)
        if serialized is not None:
            out[key] = serialized
    return out


class _Neo4jConnection:
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        self.url = url
        self.username = username
        self.password = password
        self.database = database
        self._driver = None
        self._driver_lock = threading.Lock()

    def _get_driver(self):
        if self._driver is None:
            with self._driver_lock:
                if self._driver is None:
                    try:
                        from neo4j import AsyncGraphDatabase
                    except ImportError:
                        raise RuntimeError("neo4j package is required: pip install neo4j")
                    self._driver = AsyncGraphDatabase.driver(
                        self.url, auth=(self.username, self.password)
                    )
        return self._driver

    def _session(self):
        return self._get_driver().session(database=self.database)

    async def close(self) -> None:
        with self._driver_lock:
            driver = self._driver
            self._driver = None
        if driver is not None:
            await driver.close()

    async def ensure_indexes(self, embedding_dim: int = 4096) -> None:
        async with self._session() as session:
            await session.run(
                "CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS "
                "FOR (c:Chunk) ON (c.embedding) "
                f"OPTIONS {{indexConfig: {{`vector.dimensions`: {embedding_dim}, "
                f"`vector.similarity_function`: 'cosine'}}}}"
            )
            await session.run(
                "CREATE CONSTRAINT phase_item_phase_key IF NOT EXISTS "
                "FOR (p:PhaseItem) REQUIRE (p.phase, p.key) IS UNIQUE"
            )


class _Neo4jWriteMixin:
    async def upsert_node(
        self,
        label: str,
        node_id: str,
        properties: dict,
        *,
        extra_labels: tuple[str, ...] = (),
        create_only_properties: dict | None = None,
    ) -> None:
        """MERGE a node on ``label`` and ``id``, then add ``extra_labels``.

        The extra labels are applied with a separate ``SET n:X`` rather than
        folded into the MERGE pattern: ``MERGE (n:Concept:Entity {id: ...})``
        matches only nodes carrying *both* labels, so against a graph written
        before the marker existed it would create a duplicate node with the same
        id instead of matching the existing one. ``SET n:X`` is idempotent.

        ``create_only_properties`` are written through ``ON CREATE SET`` and
        left untouched on subsequent runs. First-seen timestamps belong here:
        writing them unconditionally rewrote every node's properties on every
        run, so no part of the graph was ever byte-stable across runs (F-11).
        """
        primary = _cypher_identifier(label, kind="label")
        extras = [
            safe
            for safe in (
                _cypher_identifier(extra, kind="label") for extra in extra_labels
            )
            if safe != primary
        ]
        create_props = _writable_props(create_only_properties or {})
        query = f"MERGE (n:`{primary}` {{id: $id}}) "
        if create_props:
            query += "ON CREATE SET n += $create_props "
        if extras:
            query += "SET n" + "".join(f":`{extra}`" for extra in extras) + " "
        query += "SET n += $props"
        props = _writable_props({**properties, "id": node_id})
        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                await tx.run(
                    query, id=node_id, props=props, create_props=create_props
                )
                await tx.commit()

    async def upsert_relations(
        self, relations: list[dict]
    ) -> None:
        if not relations:
            return
        rels_by_type: dict[str, list[dict]] = {}
        for r in relations:
            rel_safe = _cypher_identifier(r["relation_type"], kind="relationship type")
            rels_by_type.setdefault(rel_safe, []).append({
                "from_id": r["from_id"],
                "to_id": r["to_id"],
                "props": _writable_props(r.get("properties") or {})
            })
            
        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                for rel_type, batch_data in rels_by_type.items():
                    query = f"""
                    UNWIND $batch AS rel
                    MATCH (a {{id: rel.from_id}})
                    MATCH (b {{id: rel.to_id}})
                    MERGE (a)-[r:`{rel_type}`]->(b)
                    SET r += rel.props
                    """
                    await tx.run(query, batch=batch_data)
                await tx.commit()

    async def upsert_relation(
        self,
        from_id: str,
        relation_type: str,
        to_id: str,
        properties: dict | None = None,
    ) -> None:
        await self.upsert_relations([{
            "from_id": from_id, 
            "relation_type": relation_type, 
            "to_id": to_id, 
            "properties": properties
        }])

    async def upsert_chunks(self, chunks: list[L1Chunk]) -> None:
        if not chunks:
            return
        query = """
        UNWIND $batch AS chunk
        MERGE (c:Chunk {id: chunk.id})
        ON CREATE SET c += chunk.create_props
        SET c += chunk.props
        """
        batch_data = []
        for c in chunks:
            props = c.model_dump(exclude={"id", "metadata"})
            if c.metadata:
                props.update(c.metadata)
            create_props = props.pop("_create_props", {})
            batch_data.append({
                "id": c.id,
                "props": _writable_props(props),
                "create_props": _writable_props(create_props)
            })

        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                await tx.run(query, batch=batch_data)
                await tx.commit()

    async def upsert_chunk(self, chunk: L1Chunk) -> None:
        await self.upsert_chunks([chunk])

    async def prune_document_children(
        self,
        document_id: str,
        *,
        keep_chunk_ids: list[str],
        keep_chapter_ids: list[str],
    ) -> dict[str, int]:
        """Delete Chunk/Chapter nodes of ``document_id`` that the source no longer yields.

        Chunk ids are content-addressed (see
        ``episteme_pipeline.phases.phase1_foundation.provenance``), so editing a document
        produces new chunk nodes and leaves the previous ones behind. Without
        this sweep every re-ingest of an evolving source accumulated dead chunks
        that ``get_chunks()`` still returned, and stale entity extractions
        stayed anchored to text that no longer exists (F-11).

        ``DETACH DELETE`` also removes the pruned chunk's ``EXTRACTED_FROM`` and
        ``NEXT`` edges. Entities that were only ever supported by a pruned chunk
        survive as unsupported nodes; re-running Phase 2 re-links them from the
        current text, and orphan-entity collection is a separate concern.

        Returns ``{"chunks": n, "chapters": n}``.
        """
        query = (
            "MATCH (d:Document {id: $doc_id}) "
            "OPTIONAL MATCH (d)-[:CONTAINS]->(chap:Chapter)-[:CONTAINS]->(c:Chunk) "
            "WHERE NOT c.id IN $keep_chunks "
            "WITH d, collect(DISTINCT c) AS dead_chunks "
            "FOREACH (n IN dead_chunks | DETACH DELETE n) "
            "WITH d, size(dead_chunks) AS chunks_deleted "
            "OPTIONAL MATCH (d)-[:CONTAINS]->(chap:Chapter) "
            "WHERE NOT chap.id IN $keep_chapters "
            "WITH chunks_deleted, collect(DISTINCT chap) AS dead_chapters "
            "FOREACH (n IN dead_chapters | DETACH DELETE n) "
            "RETURN chunks_deleted, size(dead_chapters) AS chapters_deleted"
        )
        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                result = await tx.run(
                    query,
                    doc_id=document_id,
                    keep_chunks=list(keep_chunk_ids),
                    keep_chapters=list(keep_chapter_ids),
                )
                row = await result.single()
                await tx.commit()
        deleted = {
            "chunks": int(row["chunks_deleted"]) if row else 0,
            "chapters": int(row["chapters_deleted"]) if row else 0,
        }
        if deleted["chunks"] or deleted["chapters"]:
            logger.info(
                "Pruned %d stale chunk(s) and %d stale chapter(s) from document %s.",
                deleted["chunks"],
                deleted["chapters"],
                document_id,
            )
        return deleted

    async def upsert_entities(self, entities: list[L2Entity]) -> None:
        if not entities:
            return
        
        # In Cypher, we cannot set dynamic labels cleanly from a parameter in SET.
        # But we can group entities by label, and do one UNWIND per label.
        entities_by_label: dict[str, list[dict]] = {}
        for e in entities:
            props = e.model_dump(exclude={"id", "label"})
            if not e.is_mature:
                props.pop("is_mature", None)
            
            label_safe = _cypher_identifier(e.label, kind="label")
            entities_by_label.setdefault(label_safe, []).append(
                {"id": e.id, "props": _writable_props(props)}
            )
        
        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                for label, batch_data in entities_by_label.items():
                    query = f"""
                    UNWIND $batch AS entity
                    MERGE (n:`{label}` {{id: entity.id}})
                    SET n:`{ENTITY_LABEL}`
                    SET n += entity.props
                    """
                    await tx.run(query, batch=batch_data)
                await tx.commit()

    async def upsert_entity(self, entity: L2Entity) -> None:
        await self.upsert_entities([entity])

    async def backfill_entity_labels(self) -> int:
        """One-time migration: stamp ``:Entity`` on pre-existing L2 nodes.

        Graphs populated before F-05 identified entities by exclusion. This
        reproduces that heuristic once so the exclusion is never needed again.
        Returns the number of nodes labelled. Safe to re-run — already-labelled
        nodes are skipped.
        """
        exclusions = " ".join(f"AND NOT n:`{label}`" for label in _NON_ENTITY_LABELS)
        query = (
            f"MATCH (n) WHERE NOT n:`{ENTITY_LABEL}` {exclusions} "
            f"SET n:`{ENTITY_LABEL}` "
            "RETURN count(n) AS labelled"
        )
        async with self._session() as session:
            result = await session.run(query)
            row = await result.single()
        labelled = int(row["labelled"]) if row else 0
        logger.info("Backfilled :%s onto %d nodes.", ENTITY_LABEL, labelled)
        return labelled
        
    async def upsert_triples(self, triples: list[L2Triple]) -> None:
        if not triples:
            return
        
        triples_by_rel: dict[str, list[dict]] = {}
        for t in triples:
            rel_safe = _cypher_identifier(t.predicate, kind="relationship type")
            props = _writable_props({
                "confidence": t.confidence,
                "scope": t.scope,
                "source_chunk_id": t.source_chunk_id,
            })
            triples_by_rel.setdefault(rel_safe, []).append({
                "from_id": t.subject_id,
                "to_id": t.object_id,
                "props": props
            })
            
        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                for rel_type, batch_data in triples_by_rel.items():
                    query = f"""
                    UNWIND $batch AS rel
                    MATCH (a {{id: rel.from_id}})
                    MATCH (b {{id: rel.to_id}})
                    MERGE (a)-[r:`{rel_type}`]->(b)
                    SET r += rel.props
                    """
                    await tx.run(query, batch=batch_data)
                await tx.commit()

    async def upsert_triple(self, triple: L2Triple) -> None:
        await self.upsert_triples([triple])

    async def upsert_argument_components(self, components: list[TheoryAtom]) -> None:
        """Upsert a batch of TheoryAtom nodes into Neo4j.

        Parameters
        ----------
        components : list of TheoryAtom
            Theory atom nodes to merge into the graph store.
        """
        if not components:
            return
        query = """
        UNWIND $batch AS comp
        MERGE (n:TheoryAtom {id: comp.id})
        SET n += comp.props
        """
        batch_data = []
        for c in components:
            props = c.model_dump(exclude={"id"})
            # Drop empty defaults so they neither cause Cypher Map{} errors
            # nor wipe existing enriched properties on re-runs (F-06).
            if not c.parameters:
                props.pop("parameters", None)
            if not c.measurements:
                props.pop("measurements", None)
            if c.tenability is None:
                props.pop("tenability", None)
            if not c.entity_ids:
                props.pop("entity_ids", None)
            batch_data.append({"id": c.id, "props": _writable_props(props)})

        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                await tx.run(query, batch=batch_data)
                await tx.commit()

    async def upsert_argument_component(self, component: TheoryAtom) -> None:
        """Upsert a single TheoryAtom node into Neo4j.

        Parameters
        ----------
        component : TheoryAtom
            Theory atom node to merge into the graph store.
        """
        await self.upsert_argument_components([component])

    async def upsert_theory_relations(self, relations: list[TheoryRelation]) -> None:
        """Upsert a batch of TheoryRelation edges into Neo4j between TheoryAtom nodes.

        Parameters
        ----------
        relations : list of TheoryRelation
            Domain relations to persist into the graph store.
        """
        if not relations:
            return
        rels_by_type: dict[str, list[dict]] = {}
        for rel in relations:
            rel_safe = _cypher_identifier(rel.relation_type, kind="relationship type")
            props = rel.to_graph_properties()
            rels_by_type.setdefault(rel_safe, []).append({
                "from_id": rel.source_id,
                "to_id": rel.target_id,
                "props": _writable_props(props),
            })

        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                for rel_type, batch_data in rels_by_type.items():
                    query = f"""
                    UNWIND $batch AS rel
                    MATCH (a {{id: rel.from_id}})
                    MATCH (b {{id: rel.to_id}})
                    MERGE (a)-[r:`{rel_type}`]->(b)
                    SET r += rel.props
                    """
                    await tx.run(query, batch=batch_data)
                await tx.commit()

    async def upsert_theory_relation(self, relation: TheoryRelation) -> None:
        """Upsert a single TheoryRelation edge into Neo4j.

        Parameters
        ----------
        relation : TheoryRelation
            Domain relation to persist into the graph store.
        """
        await self.upsert_theory_relations([relation])

    async def upsert_communities(self, communities: list[dict]) -> None:
        if not communities:
            return
        query_node = """
        UNWIND $batch AS comm
        MERGE (c:Community {id: comm.community_id})
        SET c.level = comm.level
        WITH c, comm
        UNWIND comm.entity_ids AS entity_id
        MATCH (e {id: entity_id})
        MERGE (e)-[:IN_COMMUNITY]->(c)
        """
        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                await tx.run(query_node, batch=communities)
                await tx.commit()

    async def upsert_community(self, community_id: str, level: int, entity_ids: list[str]) -> None:
        await self.upsert_communities([{"community_id": community_id, "level": level, "entity_ids": entity_ids}])


#: Projects an entity row. ``labels(n)[0]`` is arbitrary for a multi-labelled
#: node and would now often return the marker itself, so the semantic label is
#: selected explicitly.
_ENTITY_RETURN = (
    "RETURN n.id AS id, "
    f"coalesce(head([l IN labels(n) WHERE l <> '{ENTITY_LABEL}']), '{ENTITY_LABEL}') AS label, "
    "properties(n) AS props"
)


def _entity_from_row(row: dict) -> L2Entity:
    props = row.get("props") or {}
    return L2Entity(
        id=row["id"],
        label=row["label"],
        name=props.get("name", row["id"]),
        description=props.get("description"),
        textual_envelope=props.get("textual_envelope"),
        is_mature=props.get("is_mature", False),
        confidence=props.get("confidence"),
        source_chunk_ids=props.get("source_chunk_ids", []),
    )


def _property_filter(alias: str, filters: dict | None) -> tuple[str, dict]:
    """Build validated ``alias.key = $key`` clauses and their parameter map.

    The property name is validated because it is interpolated twice — once as a
    property accessor and once as the parameter name — and neither position can
    be parameterised (F-11).
    """
    if not filters:
        return "", {}
    clauses: list[str] = []
    params: dict = {}
    for key, value in filters.items():
        safe = _cypher_identifier(key, kind="property name")
        clauses.append(f"{alias}.`{safe}` = ${safe}")
        params[safe] = value
    return " AND ".join(clauses), params


#: Projects nodes and relationships into plain maps *inside* Cypher. The driver's
#: ``Result.data()`` flattens Node and Relationship objects to property dicts,
#: dropping ``labels`` and ``type`` — the previous implementation read them off
#: the result and so recorded every neighbour's label as ``"Unknown"``.
_NEIGHBORHOOD_PROJECTION = (
    "[n IN {nodes} | {{"
    "  id: n.id,"
    f"  label: coalesce(head([l IN labels(n) WHERE l <> '{ENTITY_LABEL}']), '{ENTITY_LABEL}'),"
    "  name: coalesce(n.name, n.id)"
    "}}] AS neighbors, "
    "[r IN {rels} | {{"
    "  subject_id: startNode(r).id,"
    "  predicate: type(r),"
    "  object_id: endNode(r).id,"
    "  confidence: coalesce(r.confidence, 1.0)"
    "}}] AS triples"
)


def _apoc_neighborhood_query() -> str:
    projection = _NEIGHBORHOOD_PROJECTION.format(
        nodes="[x IN nodes WHERE x <> center]", rels="relationships"
    )
    return (
        f"MATCH (center:`{ENTITY_LABEL}` {{id: $node_id}}) "
        "CALL apoc.path.subgraphAll(center, "
        f"  {{maxLevel: $depth, labelFilter: '+{ENTITY_LABEL}'}}) "
        "YIELD nodes, relationships "
        f"RETURN {projection}"
    )


def _plain_neighborhood_query(depth: int) -> str:
    """Variable-length-pattern equivalent of the APOC subgraph read.

    The upper bound of a variable-length pattern cannot be parameterised in
    Cypher, so it is interpolated — as an ``int``, from a caller-supplied hop
    count that has already been floored at 1.
    """
    projection = _NEIGHBORHOOD_PROJECTION.format(nodes="neighbor_nodes", rels="rels")
    return (
        f"MATCH (center:`{ENTITY_LABEL}` {{id: $node_id}}) "
        f"OPTIONAL MATCH p = (center)-[*1..{int(depth)}]-(m:`{ENTITY_LABEL}`) "
        f"WHERE all(x IN nodes(p) WHERE x:`{ENTITY_LABEL}`) "
        "WITH center, collect(DISTINCT m) AS neighbor_nodes, "
        "     reduce(acc = [], q IN collect(p) | acc + relationships(q)) AS rels "
        f"RETURN {projection}"
    )


def _is_missing_procedure(exc: Exception) -> bool:
    """True when Neo4j rejected the query because APOC is not installed.

    Matches on the driver's structured error code rather than the message text,
    so it does not drift with server wording or locale.
    """
    code = getattr(exc, "code", "") or ""
    return "ProcedureNotFound" in code or "UnknownProcedure" in code


class _Neo4jReadMixin:
    #: Flipped to False the first time an APOC call reports the procedure missing.
    _apoc_available: bool = True

    async def get_theory_atoms(self) -> list[TheoryAtom]:
        """Fetch all TheoryAtom nodes from the Neo4j graph.

        Returns
        -------
        list of TheoryAtom
            All materialized TheoryAtom entities, reconstructing deserialized
            measurements, parameters, and tenability if present.
        """
        query = (
            "MATCH (n:TheoryAtom) "
            "RETURN n.id as id, n.text as text, n.component_type as component_type, "
            "n.source_chunk_id as source_chunk_id, n.confidence as confidence, n.plausibility as plausibility, "
            "n.epistemic_status as epistemic_status, n.scope_type as scope_type, "
            "n.entity_ids as entity_ids, n.parameters as parameters, "
            "n.measurements as measurements, n.tenability as tenability"
        )
        async with self._session() as session:
            result = await session.run(query)
            rows = await result.data()

        atoms: list[TheoryAtom] = []
        for row in rows:
            raw_params = row.get("parameters")
            params = {}
            if isinstance(raw_params, str):
                try:
                    loaded = json.loads(raw_params)
                    if isinstance(loaded, dict):
                        params = loaded
                    else:
                        logger.warning(
                            "Expected dict for parameters of TheoryAtom %s, got %s",
                            row.get("id"),
                            type(loaded).__name__,
                        )
                except Exception as exc:
                    logger.warning(
                        "Failed to parse parameters JSON for TheoryAtom %s: %s",
                        row.get("id"),
                        exc,
                    )
            elif isinstance(raw_params, dict):
                params = raw_params

            raw_meas = row.get("measurements")
            meas_list: list[Measurement] = []
            if isinstance(raw_meas, str):
                try:
                    data = json.loads(raw_meas)
                    if isinstance(data, list):
                        meas_list = [
                            m if isinstance(m, Measurement) else Measurement.model_validate(m)
                            for m in data
                        ]
                except Exception as exc:
                    logger.warning(
                        "Failed to parse measurements JSON for TheoryAtom %s: %s",
                        row.get("id"),
                        exc,
                    )
            elif isinstance(raw_meas, list):
                try:
                    meas_list = [
                        m if isinstance(m, Measurement) else Measurement.model_validate(m)
                        for m in raw_meas
                    ]
                except Exception as exc:
                    logger.warning(
                        "Failed to validate measurements list for TheoryAtom %s: %s",
                        row.get("id"),
                        exc,
                    )

            raw_tenab = row.get("tenability")
            tenability_res: TenabilityResult | None = None
            if isinstance(raw_tenab, str):
                try:
                    tenability_res = TenabilityResult.model_validate_json(raw_tenab)
                except Exception as exc:
                    logger.warning(
                        "Failed to parse tenability JSON for TheoryAtom %s: %s",
                        row.get("id"),
                        exc,
                    )
            elif isinstance(raw_tenab, dict):
                try:
                    tenability_res = TenabilityResult.model_validate(raw_tenab)
                except Exception as exc:
                    logger.warning(
                        "Failed to validate tenability dict for TheoryAtom %s: %s",
                        row.get("id"),
                        exc,
                    )
            elif isinstance(raw_tenab, TenabilityResult):
                tenability_res = raw_tenab

            atoms.append(
                TheoryAtom(
                    id=row["id"],
                    text=row["text"],
                    component_type=row["component_type"],
                    source_chunk_id=row["source_chunk_id"],
                    confidence=row.get("confidence"),
                    plausibility=row.get("plausibility"),
                    epistemic_status=row.get("epistemic_status"),
                    scope_type=row.get("scope_type"),
                    entity_ids=row.get("entity_ids") or [],
                    parameters=params,
                    measurements=meas_list,
                    tenability=tenability_res,
                )
            )
        return atoms

    async def get_all_theory_relations(self) -> list[TheoryRelation]:
        query = (
            "MATCH (a:TheoryAtom)-[r]->(b:TheoryAtom) "
            "RETURN a.id as source_id, type(r) as relation_type, b.id as target_id, "
            "coalesce(r.confidence, 1.0) as confidence, coalesce(r.scope, 'global') as scope, "
            "r.weight as weight, r.tenability as tenability, properties(r) as props"
        )
        async with self._session() as session:
            result = await session.run(query)
            rows = await result.data()
        return [
            TheoryRelation.from_graph_properties(
                source_id=row["source_id"],
                relation_type=row["relation_type"],
                target_id=row["target_id"],
                properties={
                    **row.get("props", {}),
                    **{
                        k: v
                        for k, v in row.items()
                        if k not in ("source_id", "relation_type", "target_id", "props")
                        and v is not None
                    },
                },
            )
            for row in rows
        ]

    async def find_entities_by_name(self, name: str, label: str | None = None) -> list[L2Entity]:
        label_filter = (
            f"AND n:`{_cypher_identifier(label, kind='label')}` " if label else ""
        )
        # Use properties(n) to avoid warnings for missing keys like 'name'
        query = (
            f"MATCH (n:`{ENTITY_LABEL}`) "
            "WHERE (toLower(coalesce(n.name, '')) CONTAINS toLower($name) "
            "     OR toLower($name) CONTAINS toLower(coalesce(n.name, ''))) "
            f"{label_filter}"
            f"{_ENTITY_RETURN} "
            "LIMIT 20"
        )
        async with self._session() as session:
            result = await session.run(query, name=name)
            rows = await result.data()
        return [_entity_from_row(row) for row in rows]

    async def get_chunks(self, filters: dict | None = None, limit: int | None = None) -> list[L1Chunk]:
        clause, params = _property_filter("c", filters)
        where = f"WHERE {clause}" if clause else ""
        limit_clause = f"LIMIT {int(limit)}" if limit else ""
        query = (
            f"MATCH (c:Chunk) {where} "
            "RETURN c.id as id, c.text as text, c.source_doc_id as source_doc_id, "
            "c.chapter_id as chapter_id, c.sequence_index as sequence_index, c.token_count as token_count "
            f"{limit_clause}"
        )
        async with self._session() as session:
            result = await session.run(query, **params)
            rows = await result.data()
        return [
            L1Chunk(
                id=row["id"],
                text=row["text"],
                source_doc_id=row["source_doc_id"],
                chapter_id=row.get("chapter_id"),
                sequence_index=row["sequence_index"],
                token_count=row.get("token_count", 0),
            )
            for row in rows
        ]

    async def get_entities(self, labels: list[str] | None = None, filters: dict | None = None) -> list[L2Entity]:
        conditions: list[str] = []
        if labels:
            safe = [_cypher_identifier(label, kind="label") for label in labels]
            conditions.append("(" + " OR ".join(f"n:`{label}`" for label in safe) + ")")
        # `filters` used to be accepted and silently ignored.
        clause, params = _property_filter("n", filters)
        if clause:
            conditions.append(clause)
        where = f"WHERE {' AND '.join(conditions)} " if conditions else ""
        query = f"MATCH (n:`{ENTITY_LABEL}`) {where}{_ENTITY_RETURN}"
        async with self._session() as session:
            result = await session.run(query, **params)
            rows = await result.data()
        return [_entity_from_row(row) for row in rows]

    async def get_all_entity_triples(self) -> list[L2Triple]:
        query = (
            f"MATCH (a:`{ENTITY_LABEL}`)-[r]->(b:`{ENTITY_LABEL}`) "
            "RETURN a.id as subj, type(r) as pred, b.id as obj, coalesce(r.confidence, 1.0) as conf"
        )
        async with self._session() as session:
            result = await session.run(query)
            rows = await result.data()
        
        return [
            L2Triple(
                subject_id=row["subj"],
                predicate=row["pred"],
                object_id=row["obj"],
                confidence=row["conf"],
                scope="global",
                source_chunk_id="global",
            )
            for row in rows
        ]

    async def get_entity_envelopes(self, entity_id: str) -> list[str]:
        query = (
            "MATCH (e {id: $entity_id})-[r:EXTRACTED_FROM]->(c:Chunk) "
            "WHERE r.textual_envelope IS NOT NULL "
            "RETURN r.textual_envelope AS envelope"
        )
        async with self._session() as session:
            result = await session.run(query, entity_id=entity_id)
            rows = await result.data()
        return [row["envelope"] for row in rows]

    async def get_chunk_entities(self, chunk_id: str) -> list[L2Entity]:
        query = (
            f"MATCH (n:`{ENTITY_LABEL}`)-[:EXTRACTED_FROM]->(c:Chunk {{id: $chunk_id}}) "
            f"{_ENTITY_RETURN}"
        )
        async with self._session() as session:
            result = await session.run(query, chunk_id=chunk_id)
            rows = await result.data()
        return [_entity_from_row(row) for row in rows]

    async def get_neighborhood(self, node_id: str, depth: int = 1) -> SubGraph:
        """Depth-limited entity neighborhood, preferring APOC and degrading to plain Cypher.

        ``apoc.path.subgraphAll`` is a plugin procedure, not core Neo4j — on a
        stock image the call fails with a procedure-not-found error that reads
        like a bug in this pipeline (F-11). The first such failure is logged and
        remembered, and every subsequent call uses the variable-length-pattern
        fallback below. The fallback returns the same neighborhood; it just
        cannot deduplicate paths server-side, so it is slower on dense graphs.
        """
        hops = max(1, int(depth))
        if getattr(self, "_apoc_available", True):
            try:
                rows = await self._run_neighborhood(_apoc_neighborhood_query(), node_id, hops)
            except Exception as exc:
                if not _is_missing_procedure(exc):
                    raise
                self._apoc_available = False
                logger.warning(
                    "apoc.path.subgraphAll is unavailable (%s); falling back to "
                    "plain-Cypher neighborhood traversal. Install the APOC plugin "
                    "for faster subgraph reads.",
                    exc,
                )
                rows = await self._run_neighborhood(
                    _plain_neighborhood_query(hops), node_id, hops
                )
        else:
            rows = await self._run_neighborhood(_plain_neighborhood_query(hops), node_id, hops)

        nodes: list[L2Entity] = []
        triples: list[L2Triple] = []
        seen_triples: set[tuple[str, str, str]] = set()
        for row in rows:
            for neighbor in row.get("neighbors") or []:
                nodes.append(
                    L2Entity(
                        id=neighbor["id"],
                        label=neighbor["label"],
                        name=neighbor["name"],
                    )
                )
            for rel in row.get("triples") or []:
                key = (rel["subject_id"], rel["predicate"], rel["object_id"])
                if key in seen_triples:
                    # The plain-Cypher fallback walks overlapping paths, so the
                    # same relationship can surface once per path through it.
                    continue
                seen_triples.add(key)
                triples.append(
                    L2Triple(
                        subject_id=rel["subject_id"],
                        predicate=rel["predicate"],
                        object_id=rel["object_id"],
                        confidence=rel["confidence"],
                        scope="local",
                        source_chunk_id="global",
                    )
                )

        return SubGraph(center_id=node_id, nodes=nodes, triples=triples, depth=depth)

    async def _run_neighborhood(self, query: str, node_id: str, depth: int) -> list[dict]:
        async with self._session() as session:
            result = await session.run(query, node_id=node_id, depth=depth)
            return await result.data()

    async def vector_search(
        self,
        embedding: list[float],
        top_k: int,
        node_label: str | None = None,
        run_id: str | None = None,
    ) -> list[SearchResult]:
        where_conditions: list[str] = []
        params: dict[str, Any] = {"index": "chunk_embedding", "k": top_k, "embedding": embedding}
        if node_label:
            safe_label = _cypher_identifier(node_label, kind="label")
            where_conditions.append(f"node:`{safe_label}`")
        if run_id:
            where_conditions.append("node.run_id = $run_id")
            params["run_id"] = run_id

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions) + " "

        query = (
            "CALL db.index.vector.queryNodes($index, $k, $embedding) "
            "YIELD node, score "
            f"{where_clause}"
            "RETURN node.id as node_id, score, "
            f"coalesce(head([l IN labels(node) WHERE l <> '{ENTITY_LABEL}']), head(labels(node)), 'Unknown') as node_label, "
            "coalesce(node.name, node.id) as node_name"
        )
        async with self._session() as session:
            result = await session.run(query, **params)
            rows = await result.data()
        return [
            SearchResult(node_id=row["node_id"], score=row["score"], node_label=row["node_label"], node_name=row["node_name"])
            for row in rows
        ]


class _Neo4jCheckpointMixin:
    async def mark_chunks_processed(self, chunk_ids: list[str], phase: str) -> None:
        if not chunk_ids:
            return
        prop_key = _cypher_identifier(f"{phase}_processed", kind="property name")
        query = f"UNWIND $chunk_ids AS chunk_id MATCH (c:Chunk {{id: chunk_id}}) SET c.`{prop_key}` = true"
        async with self._session() as session:
            await session.run(query, chunk_ids=chunk_ids)

    async def mark_chunk_processed(self, chunk_id: str, phase: str) -> None:
        await self.mark_chunks_processed([chunk_id], phase)

    async def get_unprocessed_chunks(self, phase: str, limit: int | None = None) -> list[L1Chunk]:
        limit_clause = f"LIMIT {limit}" if limit else ""
        query = (
            "MATCH (c:Chunk) WHERE coalesce(c[$prop_key], false) = false "
            "RETURN c.id as id, c.text as text, c.source_doc_id as source_doc_id, "
            "c.chapter_id as chapter_id, c.sequence_index as sequence_index, c.token_count as token_count "
            f"{limit_clause}"
        )
        async with self._session() as session:
            result = await session.run(query, prop_key=f"{phase}_processed")
            rows = await result.data()
        return [
            L1Chunk(
                id=row["id"],
                text=row["text"],
                source_doc_id=row["source_doc_id"],
                chapter_id=row.get("chapter_id"),
                sequence_index=row["sequence_index"],
                token_count=row.get("token_count", 0),
            )
            for row in rows
        ]

    async def filter_unprocessed_items(
        self, item_keys: list[str], phase: str
    ) -> list[str]:
        if not item_keys:
            return []
        phase_safe = _cypher_identifier(phase, kind="phase identifier")
        query = (
            "UNWIND $keys AS k "
            "WITH k "
            "WHERE NOT EXISTS { MATCH (p:PhaseItem {phase: $phase, key: k}) } "
            "RETURN k"
        )
        async with self._session() as session:
            result = await session.run(query, keys=item_keys, phase=phase_safe)
            rows = await result.data()
        return [r["k"] for r in rows]

    async def commit_phase_batch(
        self,
        phase: str,
        triples: list[L2Triple],
        items: list[PhaseItemRecord],
    ) -> None:
        if not triples and not items:
            return
        phase_safe = _cypher_identifier(phase, kind="phase identifier")

        triples_by_rel: dict[str, list[dict]] = {}
        for t in triples:
            rel_safe = _cypher_identifier(t.predicate, kind="relationship type")
            props = _writable_props({
                "confidence": t.confidence,
                "scope": t.scope,
                "source_chunk_id": t.source_chunk_id,
            })
            triples_by_rel.setdefault(rel_safe, []).append({
                "from_id": t.subject_id,
                "to_id": t.object_id,
                "props": props,
            })

        items_payload = [
            {"key": item.key, "status": item.status, "error": item.error}
            for item in items
        ]

        async with self._session() as session:
            async with await session.begin_transaction() as tx:
                for rel_type, batch_data in triples_by_rel.items():
                    query = f"""
                    UNWIND $batch AS rel
                    MATCH (a {{id: rel.from_id}})
                    MATCH (b {{id: rel.to_id}})
                    MERGE (a)-[r:`{rel_type}`]->(b)
                    SET r += rel.props
                    """
                    await tx.run(query, batch=batch_data)

                if items_payload:
                    checkpoint_query = (
                        "UNWIND $items AS item "
                        "MERGE (p:PhaseItem {phase: $phase, key: item.key}) "
                        "SET p.status = item.status, "
                        "    p.error = item.error, "
                        "    p.updated_at = datetime() "
                    )
                    await tx.run(checkpoint_query, phase=phase_safe, items=items_payload)
                await tx.commit()

    async def clear_phase_checkpoints(self, phase: str) -> None:
        phase_safe = _cypher_identifier(phase, kind="phase identifier")
        query = "MATCH (p:PhaseItem {phase: $phase}) DELETE p"
        async with self._session() as session:
            await session.run(query, phase=phase_safe)


class Neo4jGraphWriter(_Neo4jConnection, _Neo4jWriteMixin, ProjectionGraph):
    pass


# Reader also needs write capabilities to satisfy FusionGraph/EntityGraph
# and to allow phases to create relations (e.g., SAME_AS) through this handle.
class Neo4jGraphReader(
    _Neo4jConnection, _Neo4jReadMixin, _Neo4jWriteMixin, EntityGraph, FusionGraph
):
    pass


class Neo4jCheckpointStore(_Neo4jConnection, _Neo4jCheckpointMixin, PhaseCheckpointStore):
    pass


class Neo4jProcessingGraph(
    _Neo4jConnection,
    _Neo4jReadMixin,
    _Neo4jWriteMixin,
    _Neo4jCheckpointMixin,
    ProcessingGraph,
):
    pass
