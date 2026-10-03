"""Neo4j graph reader adapter translating Neo4j projections to GLP Studio domain models.

Provides read-only Cypher query execution with timeout management, row capping,
schema polarity mapping, and UNDERCUTS reification per Milestone M6 and D-21/D-23.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import time
from datetime import date, datetime, time as dt_time
from typing import Any
from uuid import uuid4

from episteme_studio.adapters.schema_mapper import SchemaMapper
from episteme_studio.domain.errors import (
    Neo4jReadOnlyViolationError,
    Neo4jUnavailableError,
    QueryTimeoutError,
    ResultTooLargeError,
)
from episteme_studio.domain.graph import (
    CypherResult,
    GraphView,
    Layer,
    StudioEdge,
    StudioNode,
    reify_inferences,
)

logger = logging.getLogger(__name__)


def _serialize_neo4j_value(val: Any) -> Any:
    """Recursively convert Neo4j types to JSON-serializable Python data structures.

    Parameters
    ----------
    val : Any
        Raw value from Neo4j driver record.

    Returns
    -------
    Any
        JSON-serializable representation.
    """
    if val is None or isinstance(val, (str, int, float, bool)):
        return val

    # Neo4j Node
    if hasattr(val, "labels") and hasattr(val, "element_id"):
        return {
            "_type": "Node",
            "id": getattr(val, "element_id", None),
            "labels": list(getattr(val, "labels", [])),
            "properties": {k: _serialize_neo4j_value(v) for k, v in dict(val).items()},
        }

    # Neo4j Relationship
    if hasattr(val, "type") and hasattr(val, "start_node") and hasattr(val, "end_node"):
        start_id = getattr(val.start_node, "element_id", None) if hasattr(val, "start_node") else None
        end_id = getattr(val.end_node, "element_id", None) if hasattr(val, "end_node") else None
        return {
            "_type": "Relationship",
            "id": getattr(val, "element_id", None),
            "type": getattr(val, "type", None),
            "start": start_id,
            "end": end_id,
            "properties": {k: _serialize_neo4j_value(v) for k, v in dict(val).items()},
        }

    # Neo4j Path
    if hasattr(val, "nodes") and hasattr(val, "relationships"):
        return {
            "_type": "Path",
            "nodes": [_serialize_neo4j_value(n) for n in val.nodes],
            "relationships": [_serialize_neo4j_value(r) for r in val.relationships],
        }

    # Datetime / Date
    if isinstance(val, (datetime, date, dt_time)):
        return val.isoformat()

    # Collections
    if isinstance(val, (list, tuple, set)):
        return [_serialize_neo4j_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _serialize_neo4j_value(v) for k, v in val.items()}

    return str(val)


class Neo4jReader:
    """Adapter executing read-only operations against a Neo4j property graph instance.

    Parameters
    ----------
    driver : Any
        Active Neo4j AsyncDriver instance.
    database : str or None, optional
        Target database name. Defaults to None (server default).
    schema_mapper : SchemaMapper or None, optional
        Active schema mapper for relation polarity resolution.
    """

    def __init__(
        self,
        driver: Any,
        database: str | None = None,
        schema_mapper: SchemaMapper | None = None,
    ) -> None:
        self._driver = driver
        self._database = database
        self._schema_mapper = schema_mapper or SchemaMapper()

    @classmethod
    async def create_and_verify_driver(
        cls,
        url: str,
        user: str | None = None,
        password: str | None = None,
        timeout_seconds: float = 3.0,
    ) -> Any:
        """Create an AsyncGraphDatabase driver and verify its connectivity.

        Parameters
        ----------
        url : str
            Neo4j Bolt connection URI.
        user : str or None, optional
            Username for authentication.
        password : str or None, optional
            Password for authentication.
        timeout_seconds : float, default 3.0
            Maximum time to wait for connectivity check.

        Returns
        -------
        Any
            Connected and verified Neo4j async driver instance.

        Raises
        ------
        Neo4jUnavailableError
            If connectivity fails or times out.
        """
        from neo4j import AsyncGraphDatabase

        auth = (user, password) if user else None
        try:
            driver = AsyncGraphDatabase.driver(url, auth=auth)
            async with asyncio.timeout(timeout_seconds):
                await driver.verify_connectivity()
            return driver
        except Exception as err:
            raise Neo4jUnavailableError(f"Could not establish connection to Neo4j at {url}: {err}")

    async def check_connectivity(self, timeout: float = 2.0) -> bool:
        """Verify driver connectivity to the Neo4j cluster or instance.

        Parameters
        ----------
        timeout : float, default 2.0
            Maximum time in seconds to wait for ping response.

        Returns
        -------
        bool
            True if connection succeeded; False otherwise.
        """
        if self._driver is None:
            return False
        try:
            async with asyncio.timeout(timeout):
                await self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def check_gds_availability(self, timeout: float = 2.0) -> bool:
        """Verify whether the Neo4j Graph Data Science (GDS) library is installed and available.

        Parameters
        ----------
        timeout : float, default 2.0
            Maximum time in seconds to wait for probe response.

        Returns
        -------
        bool
            True if GDS is available; False otherwise.
        """
        if self._driver is None:
            return False
        try:
            res = await self.execute_cypher("RETURN gds.version() AS version", timeout=timeout)
            return len(res.rows) > 0 and res.rows[0].get("version") is not None
        except Exception:
            return False

    async def execute_cypher(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        limit: int = 500,
        timeout: float = 30.0,
    ) -> CypherResult:
        """Execute a read-only Cypher query with timeout and row cap enforcement.

        Parameters
        ----------
        query : str
            Cypher query string.
        params : dict of str to Any, optional
            Query parameters.
        limit : int, default 500
            Maximum allowed number of returned rows.
        timeout : float, default 30.0
            Transaction timeout budget in seconds.

        Returns
        -------
        CypherResult
            Columns, rows, row count, and execution latency.

        Raises
        ------
        Neo4jUnavailableError
            If driver is missing or connection failed.
        Neo4jReadOnlyViolationError
            If query attempts to mutate graph state.
        QueryTimeoutError
            If execution exceeded the timeout threshold.
        ResultTooLargeError
            If query output exceeded the row cap.
        """
        if self._driver is None:
            raise Neo4jUnavailableError("Neo4j driver is not configured.")

        try:
            from neo4j import RoutingControl
            from neo4j.exceptions import ClientError, Neo4jError, TransientError
        except ImportError:
            raise Neo4jUnavailableError("neo4j package is not installed.")

        start_time = time.perf_counter()

        try:
            async with asyncio.timeout(timeout):
                async with self._driver.session(
                    database=self._database,
                    default_access_mode=RoutingControl.READ,
                ) as session:
                    # Execute in read mode to enforce server-side read-only semantics (D-23, D-26)
                    async def _run_tx(tx: Any) -> tuple[list[str], list[dict[str, Any]]]:
                        result = await tx.run(query, **(params or {}))
                        raw_keys = result.keys()
                        if inspect.isawaitable(raw_keys):
                            cols = list(await raw_keys)
                        else:
                            cols = list(raw_keys)
                        out_rows: list[dict[str, Any]] = []

                        async for record in result:
                            if len(out_rows) >= limit:
                                raise ResultTooLargeError(
                                    f"Query exceeded row budget cap ({limit} rows). "
                                    "Add a LIMIT clause or refine your query."
                                )
                            out_rows.append(
                                {k: _serialize_neo4j_value(record[k]) for k in cols}
                            )
                        return cols, out_rows

                    columns, rows = await session.execute_read(_run_tx)

        except ResultTooLargeError:
            raise
        except (asyncio.TimeoutError, TimeoutError):
            raise QueryTimeoutError(
                f"Cypher query exceeded timeout limit of {timeout}s."
            )
        except TransientError as e:
            code = getattr(e, "code", "")
            if "Terminated" in code or "TimedOut" in code:
                raise QueryTimeoutError(str(e))
            raise
        except ClientError as e:
            code = getattr(e, "code", "")
            msg = str(e)
            if "AccessMode" in code or "read access mode" in msg.lower() or "writing in read" in msg.lower():
                raise Neo4jReadOnlyViolationError(
                    f"Write statement rejected by read access mode: {msg}"
                )
            raise
        except Neo4jError as e:
            code = getattr(e, "code", "")
            msg = str(e)
            if "AccessMode" in code or "read access mode" in msg.lower():
                raise Neo4jReadOnlyViolationError(str(e))
            raise
        except Exception as e:
            if "read access mode" in str(e).lower():
                raise Neo4jReadOnlyViolationError(str(e))
            raise

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return CypherResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=round(elapsed_ms, 2),
        )

    async def get_graph_view(
        self,
        budget: int = 500,
        layer: int | None = None,
        timeout: float = 30.0,
    ) -> GraphView:
        """Project graph contents from Neo4j into a GraphView domain model.

        Parameters
        ----------
        budget : int, default 500
            Maximum element count before truncation.
        layer : int or None, optional
            If set, filters nodes and edges to Layer 1, 2, or 3.
        timeout : float, default 30.0
            Maximum query execution timeout in seconds.

        Returns
        -------
        GraphView
            Materialized nodes and edges with polarity resolution and budget metadata.
        """
        if self._driver is None:
            raise Neo4jUnavailableError("Neo4j driver is not configured.")

        # Cypher query for nodes
        node_query = (
            "MATCH (n) "
            "WHERE ($layer IS NULL "
            "  OR ($layer = 1 AND (n:Chunk OR n:Document)) "
            "  OR ($layer = 2 AND n:Entity) "
            "  OR ($layer = 3 AND n:TheoryAtom)) "
            "RETURN coalesce(n.id, elementId(n)) AS id, "
            "       labels(n) AS labels, "
            "       properties(n) AS props "
            "LIMIT $limit"
        )

        # Cypher query for relationships
        rel_query = (
            "MATCH (s)-[r]->(t) "
            "WHERE ($layer IS NULL "
            "  OR ($layer = 1 AND (s:Chunk OR s:Document) AND (t:Chunk OR t:Document)) "
            "  OR ($layer = 2 AND s:Entity AND t:Entity) "
            "  OR ($layer = 3 AND s:TheoryAtom AND t:TheoryAtom)) "
            "RETURN coalesce(s.id, elementId(s)) AS source_id, "
            "       coalesce(t.id, elementId(t)) AS target_id, "
            "       type(r) AS rel_type, "
            "       elementId(r) AS rel_id, "
            "       properties(r) AS props "
            "LIMIT $limit"
        )

        try:
            node_res = await self.execute_cypher(
                node_query,
                params={"layer": layer, "limit": budget * 2},
                limit=budget * 2 + 1,
                timeout=timeout,
            )
            rel_res = await self.execute_cypher(
                rel_query,
                params={"layer": layer, "limit": budget * 4},
                limit=budget * 4 + 1,
                timeout=timeout,
            )
        except ResultTooLargeError:
            node_res = await self.execute_cypher(
                node_query,
                params={"layer": layer, "limit": budget},
                limit=budget,
                timeout=timeout,
            )
            rel_res = await self.execute_cypher(
                rel_query,
                params={"layer": layer, "limit": budget * 2},
                limit=budget * 2,
                timeout=timeout,
            )

        nodes: list[StudioNode] = []
        edges: list[StudioEdge] = []
        unmapped_predicates: dict[str, int] = {}

        for row in node_res.rows:
            node_id = str(row["id"])
            labels = set(row.get("labels") or [])
            props = dict(row.get("props") or {})

            # Determine Layer
            if "TheoryAtom" in labels:
                node_layer = Layer.L3
                semantic_type = props.get("component_type") or "TheoryAtom"
                label = props.get("text") or node_id
            elif "Entity" in labels:
                node_layer = Layer.L2
                semantic_labels = [lbl for lbl in labels if lbl != "Entity"]
                semantic_type = semantic_labels[0] if semantic_labels else "Entity"
                label = props.get("name") or props.get("label") or node_id
            elif "Chunk" in labels:
                node_layer = Layer.L1
                semantic_type = "Chunk"
                label = f"Chunk {props.get('chunk_index', node_id)}"
            elif "Document" in labels:
                node_layer = Layer.L1
                semantic_type = "Document"
                label = props.get("title") or props.get("filename") or node_id
            else:
                node_layer = Layer.L2
                semantic_type = next(iter(labels)) if labels else "Unknown"
                label = props.get("name") or props.get("label") or node_id

            if len(label) > 60:
                label = label[:57] + "..."

            partition = props.get("epistemic_status") or props.get("partition")
            if partition not in ("B", "A"):
                partition = None

            tenability_prop = props.get("tenability")
            parameters_prop = props.get("parameters")
            if isinstance(tenability_prop, str):
                try:
                    tenability_prop = json.loads(tenability_prop)
                except Exception:
                    pass
            if isinstance(parameters_prop, str):
                try:
                    parameters_prop = json.loads(parameters_prop)
                except Exception:
                    pass

            clean_props = {k: v for k, v in props.items() if k not in ("embedding",)}
            if tenability_prop is not None:
                clean_props["tenability"] = tenability_prop
            if parameters_prop is not None:
                clean_props["parameters"] = parameters_prop

            base_sc = props.get("base_score", props.get("plausibility"))
            tier_node = props.get("decision_tier", "system_1" if props.get("is_fast_exit") else "legacy")
            nodes.append(
                StudioNode(
                    id=node_id,
                    layer=node_layer,
                    type=semantic_type,
                    label=label,
                    partition=partition,
                    plausibility=base_sc,
                    confidence=props.get("confidence"),
                    empirical_accuracy=props.get("empirical_accuracy"),
                    modal_strength=props.get("modal_strength", base_sc),
                    base_score=base_sc,
                    scope_type=props.get("scope_type"),
                    epistemic_status=props.get("epistemic_status"),
                    modal_resolver=props.get("modal_resolver") or props.get("resolver_type"),
                    raw_modal_score=props.get("raw_modal_score") or props.get("raw_engine_score"),
                    is_modal_clamped=props.get("is_modal_clamped") or props.get("clamped"),
                    qbaf_tau=props.get("qbaf_tau"),
                    total_weight_of_evidence=props.get("total_weight_of_evidence"),
                    volatility_index=props.get("volatility_index"),
                    decision_tier=tier_node,
                    conformal_set_size=props.get("conformal_set_size"),
                    is_out_of_ontology=bool(props.get("is_out_of_ontology", False)),
                    decision_id=props.get("decision_id"),
                    parameters=parameters_prop if isinstance(parameters_prop, dict) else None,
                    tenability=tenability_prop if isinstance(tenability_prop, dict) else None,
                    resolved=True,
                    props=clean_props,
                )
            )

        for row in rel_res.rows:
            source_id = str(row["source_id"])
            target_id = str(row["target_id"])
            rel_type = str(row["rel_type"])
            rel_id = str(row["rel_id"])
            props = dict(row.get("props") or {})

            polarity = self._schema_mapper.resolve_polarity(rel_type)
            if polarity is None:
                unmapped_predicates[rel_type] = unmapped_predicates.get(rel_type, 0) + 1

            edge_layer = Layer.L2
            if rel_type in ("SUPPORTS", "ATTACKS", "UNDERCUTS", "PART_OF_ARGUMENT", "CONSTRAINS", "REDUCES_TO"):
                edge_layer = Layer.L3
            elif rel_type in ("CONTAINS", "NEXT_CHUNK", "MENTIONED_IN"):
                edge_layer = Layer.L1

            edge_tenability = props.get("tenability")
            if edge_tenability is not None:
                try:
                    edge_tenability = float(edge_tenability)
                except (ValueError, TypeError):
                    edge_tenability = None

            tier_edge = props.get("decision_tier", "system_1" if props.get("is_fast_exit") else "legacy")
            inf_force = props.get("inferential_force", props.get("modal_strength"))
            edges.append(
                StudioEdge(
                    id=rel_id,
                    source=source_id,
                    target=target_id,
                    type=rel_type,
                    layer=edge_layer,
                    polarity=polarity,
                    weight=props.get("weight"),
                    confidence=props.get("confidence"),
                    tenability=edge_tenability,
                    empirical_accuracy=props.get("empirical_accuracy"),
                    model_confidence=props.get("model_confidence", props.get("calibrated_confidence")),
                    stance_probability=props.get("stance_probability", props.get("class_probability")),
                    inferential_force=inf_force,
                    active_weight=props.get("active_weight", props.get("weight")),
                    is_admissible=bool(props.get("is_admissible", True)),
                    modal_strength=props.get("modal_strength"),
                    qbaf_tau=props.get("qbaf_tau"),
                    decision_tier=tier_edge,
                    conformal_set_size=props.get("conformal_set_size"),
                    decision_id=props.get("decision_id"),
                    props=props,
                )
            )

        # Apply UNDERCUTS reification (D-21)
        reified_nodes, edges = reify_inferences(nodes, edges)
        nodes_by_id = {n.id: n for n in reified_nodes}

        # Calculate node degrees
        for edge in edges:
            if edge.source in nodes_by_id:
                nodes_by_id[edge.source].degree += 1
            if edge.target in nodes_by_id:
                nodes_by_id[edge.target].degree += 1

        # Layer counts before budgeting
        layer_counts = {
            1: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L1),
            2: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L2),
            3: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L3),
        }

        total_nodes = len(nodes_by_id)
        truncated = False
        dropped_count = 0

        if total_nodes > budget:
            truncated = True
            dropped_count = total_nodes - budget
            sorted_nodes = sorted(nodes_by_id.values(), key=lambda n: n.degree, reverse=True)
            active_nodes = sorted_nodes[:budget]
            active_ids = {n.id for n in active_nodes}
            nodes = active_nodes
            edges = [e for e in edges if e.source in active_ids and e.target in active_ids]
        else:
            nodes = list(nodes_by_id.values())

        content = f"{sorted(n.id for n in nodes)}::{sorted(e.id for e in edges)}"
        graph_version = hashlib.sha256(content.encode()).hexdigest()[:16]

        return GraphView(
            nodes=nodes,
            edges=edges,
            source="neo4j",
            graph_version=graph_version,
            schema_version="default",
            truncated=truncated,
            dropped_count=dropped_count,
            unmapped_predicates=unmapped_predicates,
            unresolved_count=0,
            layer_counts=layer_counts,
        )

    async def expand_graph(
        self,
        seeds: list[str],
        depth: int = 1,
        budget: int = 500,
        timeout: float = 30.0,
    ) -> GraphView:
        """Traverse and expand the k-hop neighborhood from seed node identifiers.

        Parameters
        ----------
        seeds : list of str
            Initial node IDs to expand from.
        depth : int, default 1
            Hop distance (clamped between 1 and 5).
        budget : int, default 500
            Maximum nodes permitted in the returned projection.
        timeout : float, default 30.0
            Maximum query execution timeout in seconds.

        Returns
        -------
        GraphView
            Sub-graph view containing seeds, neighbors, and interconnected relationships.
        """
        if self._driver is None:
            raise Neo4jUnavailableError("Neo4j driver is not configured.")

        safe_depth = max(1, min(int(depth), 5))

        expand_nodes_query = (
            "MATCH (s) WHERE coalesce(s.id, elementId(s)) IN $seeds "
            f"OPTIONAL MATCH (s)-[*1..{safe_depth}]-(m) "
            "WITH collect(DISTINCT s) + collect(DISTINCT m) AS all_nodes "
            "UNWIND all_nodes AS n "
            "RETURN DISTINCT coalesce(n.id, elementId(n)) AS id, "
            "                labels(n) AS labels, "
            "                properties(n) AS props "
            "LIMIT $limit"
        )

        node_res = await self.execute_cypher(
            expand_nodes_query,
            params={"seeds": seeds, "limit": budget * 2},
            limit=budget * 2 + 1,
            timeout=timeout,
        )

        matched_ids = [str(r["id"]) for r in node_res.rows]

        rel_query = (
            "MATCH (s)-[r]->(t) "
            "WHERE coalesce(s.id, elementId(s)) IN $matched_ids "
            "  AND coalesce(t.id, elementId(t)) IN $matched_ids "
            "RETURN coalesce(s.id, elementId(s)) AS source_id, "
            "       coalesce(t.id, elementId(t)) AS target_id, "
            "       type(r) AS rel_type, "
            "       elementId(r) AS rel_id, "
            "       properties(r) AS props "
            "LIMIT $limit"
        )

        rel_res = await self.execute_cypher(
            rel_query,
            params={"matched_ids": matched_ids, "limit": budget * 4},
            limit=budget * 4 + 1,
            timeout=timeout,
        )

        nodes: list[StudioNode] = []
        edges: list[StudioEdge] = []
        unmapped_predicates: dict[str, int] = {}

        for row in node_res.rows:
            node_id = str(row["id"])
            labels = set(row.get("labels") or [])
            props = dict(row.get("props") or {})

            if "TheoryAtom" in labels:
                node_layer = Layer.L3
                semantic_type = props.get("component_type") or "TheoryAtom"
                label = props.get("text") or node_id
            elif "Entity" in labels:
                node_layer = Layer.L2
                semantic_labels = [lbl for lbl in labels if lbl != "Entity"]
                semantic_type = semantic_labels[0] if semantic_labels else "Entity"
                label = props.get("name") or props.get("label") or node_id
            elif "Chunk" in labels:
                node_layer = Layer.L1
                semantic_type = "Chunk"
                label = f"Chunk {props.get('chunk_index', node_id)}"
            else:
                node_layer = Layer.L2
                semantic_type = next(iter(labels)) if labels else "Unknown"
                label = props.get("name") or props.get("label") or node_id

            if len(label) > 60:
                label = label[:57] + "..."

            partition = props.get("epistemic_status") or props.get("partition")
            if partition not in ("B", "A"):
                partition = None

            tenability_prop = props.get("tenability")
            parameters_prop = props.get("parameters")
            if isinstance(tenability_prop, str):
                try:
                    tenability_prop = json.loads(tenability_prop)
                except Exception:
                    pass
            if isinstance(parameters_prop, str):
                try:
                    parameters_prop = json.loads(parameters_prop)
                except Exception:
                    pass

            clean_props = {k: v for k, v in props.items() if k not in ("embedding",)}
            if tenability_prop is not None:
                clean_props["tenability"] = tenability_prop
            if parameters_prop is not None:
                clean_props["parameters"] = parameters_prop

            base_sc = props.get("base_score", props.get("plausibility"))
            tier_node = props.get("decision_tier", "system_1" if props.get("is_fast_exit") else "legacy")
            nodes.append(
                StudioNode(
                    id=node_id,
                    layer=node_layer,
                    type=semantic_type,
                    label=label,
                    partition=partition,
                    plausibility=base_sc,
                    confidence=props.get("confidence"),
                    empirical_accuracy=props.get("empirical_accuracy"),
                    modal_strength=props.get("modal_strength", base_sc),
                    base_score=base_sc,
                    scope_type=props.get("scope_type"),
                    epistemic_status=props.get("epistemic_status"),
                    modal_resolver=props.get("modal_resolver") or props.get("resolver_type"),
                    raw_modal_score=props.get("raw_modal_score") or props.get("raw_engine_score"),
                    is_modal_clamped=props.get("is_modal_clamped") or props.get("clamped"),
                    qbaf_tau=props.get("qbaf_tau"),
                    total_weight_of_evidence=props.get("total_weight_of_evidence"),
                    volatility_index=props.get("volatility_index"),
                    decision_tier=tier_node,
                    conformal_set_size=props.get("conformal_set_size"),
                    is_out_of_ontology=bool(props.get("is_out_of_ontology", False)),
                    decision_id=props.get("decision_id"),
                    parameters=parameters_prop if isinstance(parameters_prop, dict) else None,
                    tenability=tenability_prop if isinstance(tenability_prop, dict) else None,
                    resolved=True,
                    props=clean_props,
                )
            )

        for row in rel_res.rows:
            source_id = str(row["source_id"])
            target_id = str(row["target_id"])
            rel_type = str(row["rel_type"])
            rel_id = str(row["rel_id"])
            props = dict(row.get("props") or {})

            polarity = self._schema_mapper.resolve_polarity(rel_type)
            if polarity is None:
                unmapped_predicates[rel_type] = unmapped_predicates.get(rel_type, 0) + 1

            edge_layer = Layer.L2
            if rel_type in ("SUPPORTS", "ATTACKS", "UNDERCUTS", "PART_OF_ARGUMENT", "CONSTRAINS", "REDUCES_TO"):
                edge_layer = Layer.L3
            elif rel_type in ("CONTAINS", "NEXT_CHUNK", "MENTIONED_IN"):
                edge_layer = Layer.L1

            edge_tenability = props.get("tenability")
            if edge_tenability is not None:
                try:
                    edge_tenability = float(edge_tenability)
                except (ValueError, TypeError):
                    edge_tenability = None

            tier_edge = props.get("decision_tier", "system_1" if props.get("is_fast_exit") else "legacy")
            inf_force = props.get("inferential_force", props.get("modal_strength"))
            edges.append(
                StudioEdge(
                    id=rel_id,
                    source=source_id,
                    target=target_id,
                    type=rel_type,
                    layer=edge_layer,
                    polarity=polarity,
                    weight=props.get("weight"),
                    confidence=props.get("confidence"),
                    tenability=edge_tenability,
                    empirical_accuracy=props.get("empirical_accuracy"),
                    model_confidence=props.get("model_confidence", props.get("calibrated_confidence")),
                    stance_probability=props.get("stance_probability", props.get("class_probability")),
                    inferential_force=inf_force,
                    active_weight=props.get("active_weight", props.get("weight")),
                    is_admissible=bool(props.get("is_admissible", True)),
                    modal_strength=props.get("modal_strength"),
                    qbaf_tau=props.get("qbaf_tau"),
                    decision_tier=tier_edge,
                    conformal_set_size=props.get("conformal_set_size"),
                    decision_id=props.get("decision_id"),
                    props=props,
                )
            )

        # Apply UNDERCUTS reification (D-21)
        reified_nodes, edges = reify_inferences(nodes, edges)
        nodes_by_id = {n.id: n for n in reified_nodes}

        for edge in edges:
            if edge.source in nodes_by_id:
                nodes_by_id[edge.source].degree += 1
            if edge.target in nodes_by_id:
                nodes_by_id[edge.target].degree += 1

        layer_counts = {
            1: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L1),
            2: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L2),
            3: sum(1 for n in nodes_by_id.values() if n.layer == Layer.L3),
        }

        total_nodes = len(nodes_by_id)
        truncated = False
        dropped_count = 0

        if total_nodes > budget:
            truncated = True
            dropped_count = total_nodes - budget
            sorted_nodes = sorted(nodes_by_id.values(), key=lambda n: n.degree, reverse=True)
            active_nodes = sorted_nodes[:budget]
            active_ids = {n.id for n in active_nodes}
            nodes = active_nodes
            edges = [e for e in edges if e.source in active_ids and e.target in active_ids]
        else:
            nodes = list(nodes_by_id.values())

        content = f"{sorted(n.id for n in nodes)}::{sorted(e.id for e in edges)}"
        graph_version = hashlib.sha256(content.encode()).hexdigest()[:16]

        return GraphView(
            nodes=nodes,
            edges=edges,
            source="neo4j",
            graph_version=graph_version,
            schema_version="default",
            truncated=truncated,
            dropped_count=dropped_count,
            unmapped_predicates=unmapped_predicates,
            unresolved_count=0,
            layer_counts=layer_counts,
        )

    async def run_gds_pagerank(
        self,
        damping: float = 0.85,
        max_iterations: int = 20,
        tolerance: float = 1e-4,
        timeout: float = 60.0,
    ) -> tuple[dict[str, float], dict[str, Any]]:
        """Execute PageRank using the Neo4j GDS library with ephemeral projection lifecycle.

        Creates a unique UUID-tagged projection, streams PageRank centrality scores,
        and guarantees projection cleanup in a finally block.

        Parameters
        ----------
        damping : float, default 0.85
            Damping factor for PageRank random walk.
        max_iterations : int, default 20
            Maximum number of iterations.
        tolerance : float, default 1e-4
            Convergence threshold.
        timeout : float, default 60.0
            Timeout budget in seconds.

        Returns
        -------
        tuple of (dict of str to float, dict of str to Any)
            Node ID to normalized score map, and summary statistics.

        Raises
        ------
        Neo4jUnavailableError
            If Neo4j is unavailable or GDS is not installed.
        QueryTimeoutError
            If execution exceeded timeout limit.
        """
        if self._driver is None:
            raise Neo4jUnavailableError("Neo4j driver is not configured.")

        has_gds = await self.check_gds_availability()
        if not has_gds:
            raise Neo4jUnavailableError("Neo4j GDS library is not installed or available.")

        proj_name = f"pr-proj-{uuid4().hex[:8]}"

        try:
            # 1. Create ephemeral projection
            project_cypher = (
                f"CALL gds.graph.project.cypher('{proj_name}', "
                "'MATCH (n) RETURN id(n) AS id, labels(n) AS labels', "
                "'MATCH (s)-[r]->(t) RETURN id(s) AS source, id(t) AS target, coalesce(r.weight, 1.0) AS weight')"
            )
            await self.execute_cypher(project_cypher, timeout=timeout)

            # 2. Run PageRank stream
            stream_cypher = (
                f"CALL gds.pageRank.stream('{proj_name}', {{"
                f"  dampingFactor: {damping}, "
                f"  maxIterations: {max_iterations}, "
                f"  tolerance: {tolerance}, "
                f"  relationshipWeightProperty: 'weight'"
                f"}}) "
                "YIELD nodeId, score "
                "RETURN gds.util.asNode(nodeId).id AS id, score "
                "ORDER BY score DESC"
            )
            res = await self.execute_cypher(stream_cypher, limit=5000, timeout=timeout)

            scores: dict[str, float] = {}
            for row in res.rows:
                nid = row.get("id")
                if nid is not None:
                    scores[str(nid)] = round(float(row["score"]), 6)

            vals = list(scores.values()) if scores else [0.0]
            summary = {
                "min_score": round(min(vals), 6),
                "max_score": round(max(vals), 6),
                "mean_score": round(sum(vals) / len(vals), 6) if vals else 0.0,
                "iteration_count": max_iterations,
                "node_count": len(scores),
                "engine": "gds",
            }
            return scores, summary

        finally:
            # 3. Always drop ephemeral projection in finally block
            try:
                drop_cypher = f"CALL gds.graph.drop('{proj_name}', false)"
                await self.execute_cypher(drop_cypher, timeout=10.0)
            except Exception as drop_err:
                logger.warning("Failed to drop GDS ephemeral projection %s: %s", proj_name, drop_err)

    async def run_gds_leiden(
        self,
        gamma: float = 1.0,
        theta: float = 0.01,
        tolerance: float = 1e-4,
        max_levels: int = 10,
        timeout: float = 60.0,
    ) -> tuple[dict[str, int | str], dict[str, Any]]:
        """Execute Leiden community detection using the Neo4j GDS library.

        Creates an ephemeral projection, streams Leiden community assignments,
        and guarantees projection cleanup in a finally block.

        Parameters
        ----------
        gamma : float, default 1.0
            Resolution parameter controlling community granularity.
        theta : float, default 0.01
            Randomness parameter for the refinement phase.
        tolerance : float, default 1e-4
            Convergence threshold.
        max_levels : int, default 10
            Maximum number of hierarchical clustering levels.
        timeout : float, default 60.0
            Execution timeout in seconds.

        Returns
        -------
        tuple of (dict of str to (int or str), dict of str to Any)
            Map of node ID to community ID, and summary statistics.

        Raises
        ------
        Neo4jUnavailableError
            If Neo4j driver is not configured or GDS is not available.
        QueryTimeoutError
            If execution exceeded timeout limit.
        """
        if self._driver is None:
            raise Neo4jUnavailableError("Neo4j driver is not configured.")

        has_gds = await self.check_gds_availability()
        if not has_gds:
            raise Neo4jUnavailableError("Neo4j GDS library is not installed or available.")

        proj_name = f"leiden-proj-{uuid4().hex[:8]}"

        try:
            # 1. Create ephemeral projection
            project_cypher = (
                f"CALL gds.graph.project.cypher('{proj_name}', "
                "'MATCH (n) RETURN id(n) AS id, labels(n) AS labels', "
                "'MATCH (s)-[r]->(t) RETURN id(s) AS source, id(t) AS target, coalesce(r.weight, 1.0) AS weight')"
            )
            await self.execute_cypher(project_cypher, timeout=timeout)

            # 2. Run Leiden stream
            stream_cypher = (
                f"CALL gds.leiden.stream('{proj_name}', {{"
                f"  gamma: {gamma}, "
                f"  theta: {theta}, "
                f"  tolerance: {tolerance}, "
                f"  maxLevels: {max_levels}, "
                f"  relationshipWeightProperty: 'weight'"
                f"}}) "
                "YIELD nodeId, communityId "
                "RETURN coalesce(gds.util.asNode(nodeId).id, elementId(gds.util.asNode(nodeId))) AS id, communityId "
                "ORDER BY communityId ASC"
            )
            res = await self.execute_cypher(stream_cypher, limit=10000, timeout=timeout)

            communities: dict[str, int | str] = {}
            for row in res.rows:
                nid = row.get("id")
                comm_id = row.get("communityId")
                if nid is not None and comm_id is not None:
                    communities[str(nid)] = comm_id

            unique_communities = set(communities.values())
            summary = {
                "community_count": len(unique_communities),
                "node_count": len(communities),
                "gamma": gamma,
                "theta": theta,
                "max_levels": max_levels,
                "engine": "gds",
            }
            return communities, summary

        finally:
            # 3. Always drop ephemeral projection in finally block
            try:
                drop_cypher = f"CALL gds.graph.drop('{proj_name}', false)"
                await self.execute_cypher(drop_cypher, timeout=10.0)
            except Exception as drop_err:
                logger.warning("Failed to drop GDS ephemeral projection %s: %s", proj_name, drop_err)
