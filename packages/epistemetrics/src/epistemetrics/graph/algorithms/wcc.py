"""
Weakly Connected Components (WCC) algorithm for NetworkX, Neo4j GDS, and adaptive dispatch.

Mathematical Formulation
-------------------------
A weakly connected component of a directed graph :math:`G = (V, E)` is a maximal
subgraph where every pair of vertices is connected by a path in the underlying
undirected graph :math:`G_{undir} = (V, E \\cup \\{ (v, u) \\mid (u, v) \\in E \\})`.

In theory evaluation (Gerhard Schurz), WCC detection tests whether an empirical
consequence graph decomposes into disconnected factors, exposing ad-hoc tacking paradoxes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import networkx as nx

from epistemetrics.core.exceptions import AlgorithmError, GDSProjectionError
from epistemetrics.core.models import AlgorithmExecutionMode, PartitionResult
from epistemetrics.graph.algorithms.common import extract_nx_graph, resolve_gds_graph_name

logger = logging.getLogger(__name__)


def networkx_wcc(graph: Any) -> PartitionResult:
    """Detect weakly connected components using NetworkX.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.

    Returns
    -------
    PartitionResult
        Standardized partition result containing component sets and node mappings.
    """
    g = extract_nx_graph(graph)
    if len(g) == 0:
        return PartitionResult(
            partitions=[],
            node_to_partition={},
            algorithm="wcc",
            backend="networkx",
        )

    try:
        if g.is_directed():
            components = [set(map(str, c)) for c in nx.weakly_connected_components(g)]
        else:
            components = [set(map(str, c)) for c in nx.connected_components(g)]

        # Deterministic sorting: by descending partition size, then lexicographically by smallest node ID
        components.sort(key=lambda s: (-len(s), min(s) if s else ""))

        node_to_partition = {
            node_id: idx
            for idx, comp in enumerate(components)
            for node_id in comp
        }

        return PartitionResult(
            partitions=components,
            node_to_partition=node_to_partition,
            algorithm="wcc",
            backend="networkx",
        )
    except Exception as exc:
        raise AlgorithmError(f"NetworkX weakly connected components failed: {exc}") from exc


def gds_wcc(
    client: Any,
    graph: Any,
    *,
    mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
    write_property: str | None = "wcc",
    mutate_property: str | None = "wcc",
    default_graph_name: str = "theory_graph_projection",
) -> PartitionResult | dict[str, Any]:
    """Execute Weakly Connected Components (WCC) via Neo4j Graph Data Science (GDS).

    Parameters
    ----------
    client : Neo4jClient
        Connected Neo4j client instance.
    graph : Any
        Target GDS projection name or domain graph.
    mode : AlgorithmExecutionMode | str, optional
        Execution mode: STREAM, MUTATE, or WRITE (default: STREAM).
    write_property : str | None, optional
        Node property name for WRITE mode.
    mutate_property : str | None, optional
        In-memory property name for MUTATE mode.
    default_graph_name : str, optional
        Default projection name if graph is unspecified (default: 'theory_graph_projection').

    Returns
    -------
    PartitionResult | dict[str, Any]
        PartitionResult in STREAM mode; summary dict in MUTATE/WRITE mode.
    """
    client.ensure_gds_available()
    graph_name = resolve_gds_graph_name(graph, default_name=default_graph_name)

    query_exists = "CALL gds.graph.exists($name) YIELD exists RETURN exists"
    exists_res = client.execute_query(query_exists, {"name": graph_name})
    if not (exists_res and exists_res[0].get("exists", False)):
        raise GDSProjectionError(
            f"GDS projection '{graph_name}' does not exist in catalog."
        )

    config: dict[str, Any] = {}
    exec_mode = AlgorithmExecutionMode(mode)

    if exec_mode == AlgorithmExecutionMode.STREAM:
        query = (
            "CALL gds.wcc.stream($graph_name, $config) "
            "YIELD nodeId, componentId "
            "RETURN coalesce(gds.util.asNode(nodeId).id, gds.util.asNode(nodeId).name, toString(nodeId)) AS node_id, "
            "componentId"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})

        groups: dict[int, set[str]] = defaultdict(set)
        for row in rows:
            nid = row.get("node_id")
            cid = row.get("componentId")
            if nid is not None and cid is not None:
                groups[int(cid)].add(str(nid))

        partitions = list(groups.values())
        partitions.sort(key=lambda s: (-len(s), min(s) if s else ""))

        node_to_partition = {
            node_id: idx
            for idx, comp in enumerate(partitions)
            for node_id in comp
        }

        return PartitionResult(
            partitions=partitions,
            node_to_partition=node_to_partition,
            algorithm="wcc",
            backend="neo4j_gds",
        )

    if exec_mode == AlgorithmExecutionMode.WRITE:
        config["writeProperty"] = write_property or "wcc"
        query = (
            "CALL gds.wcc.write($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    if exec_mode == AlgorithmExecutionMode.MUTATE:
        config["mutateProperty"] = mutate_property or "wcc"
        query = (
            "CALL gds.wcc.mutate($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    raise AlgorithmError(f"Unsupported execution mode: {exec_mode}")


def weakly_connected_components(
    graph: Any,
    *,
    client: Any | None = None,
    prefer_neo4j: bool = True,
    fallback_to_networkx: bool = True,
    **kwargs: Any,
) -> PartitionResult:
    """Adaptive entry point for Weakly Connected Components (WCC).

    Routes execution to Neo4j GDS if available and configured; otherwise defaults
    to local NetworkX computation.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph, TheoryGraph, or GDS projection name.
    client : Any | None, optional
        Neo4j client instance, or None.
    prefer_neo4j : bool, optional
        Whether to attempt Neo4j GDS execution first (default: True).
    fallback_to_networkx : bool, optional
        Whether to fallback to NetworkX if Neo4j GDS fails (default: True).
    **kwargs : Any
        Additional options passed to backend (e.g. mode, write_property).

    Returns
    -------
    PartitionResult
        Detected component partitions and node mappings.
    """
    if prefer_neo4j and client is not None:
        try:
            if client.is_gds_available():
                logger.debug("Executing WCC via Neo4j GDS.")
                res = gds_wcc(client, graph, **kwargs)
                if isinstance(res, PartitionResult):
                    return res
        except Exception as exc:
            if not fallback_to_networkx:
                raise
            logger.warning("GDS WCC execution failed (%s); falling back to NetworkX.", exc)

    logger.debug("Executing WCC via NetworkX.")
    return networkx_wcc(graph)
