"""
Louvain Community Detection algorithm for NetworkX, Neo4j GDS, and adaptive dispatch.

Mathematical Formulation
-------------------------
The Louvain method is a greedy optimization heuristic maximizing graph modularity :math:`Q`:

.. math::

    Q = \\frac{1}{2m} \\sum_{i, j} \\left[ A_{ij} - \\gamma \\frac{k_i k_j}{2m} \\right] \\delta(c_i, c_j)

where :math:`A_{ij}` represents the edge weight between nodes :math:`i` and :math:`j`,
:math:`k_i` is the degree of node :math:`i`, :math:`m` is the total edge weight,
:math:`\\gamma` is the resolution parameter, and :math:`\\delta(c_i, c_j) = 1` if nodes
belong to the same community, and 0 otherwise.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import networkx as nx

from epistemetrics.core.exceptions import AlgorithmError, GDSProjectionError
from epistemetrics.core.models import AlgorithmExecutionMode, PartitionResult
from epistemetrics.graph.algorithms.common import (
    extract_nx_graph,
    resolve_gds_graph_name,
)

logger = logging.getLogger(__name__)


def networkx_louvain(
    graph: Any,
    *,
    resolution: float = 1.0,
    seed: int | None = None,
    weight_property: str | None = None,
) -> PartitionResult:
    """Detect modular communities using NetworkX Louvain implementation.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.
    resolution : float, optional
        Resolution parameter controlling community scale (default: 1.0).
    seed : int | None, optional
        Random seed for reproducible node traversal (default: None).
    weight_property : str | None, optional
        Edge attribute name for weights, or None.

    Returns
    -------
    PartitionResult
        Standardized partition result containing community sets and node mappings.
    """
    g = extract_nx_graph(graph)
    if len(g) == 0:
        return PartitionResult(
            partitions=[],
            node_to_partition={},
            algorithm="louvain",
            backend="networkx",
        )

    try:
        undirected_g = g.to_undirected() if g.is_directed() else g
        if isinstance(undirected_g, nx.MultiGraph):
            undirected_g = nx.Graph(undirected_g)

        raw_communities = nx.community.louvain_communities(
            undirected_g,
            weight=weight_property,
            resolution=resolution,
            seed=seed,
        )

        communities = [set(map(str, c)) for c in raw_communities]
        communities.sort(key=lambda s: (-len(s), min(s) if s else ""))

        node_to_partition = {
            node_id: idx
            for idx, comp in enumerate(communities)
            for node_id in comp
        }

        return PartitionResult(
            partitions=communities,
            node_to_partition=node_to_partition,
            algorithm="louvain",
            backend="networkx",
        )
    except Exception as exc:
        raise AlgorithmError(f"NetworkX Louvain community detection failed: {exc}") from exc


def gds_louvain(
    client: Any,
    graph: Any,
    *,
    resolution: float = 1.0,
    seed: int | None = None,
    weight_property: str | None = None,
    mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
    write_property: str | None = "community",
    mutate_property: str | None = "community",
    default_graph_name: str = "theory_graph_projection",
) -> PartitionResult | dict[str, Any]:
    """Execute Louvain Community Detection via Neo4j Graph Data Science (GDS).

    Parameters
    ----------
    client : Neo4jClient
        Connected Neo4j client instance.
    graph : Any
        Target GDS projection name or domain graph.
    resolution : float, optional
        Resolution parameter (default: 1.0).
    seed : int | None, optional
        Random seed for determinism (default: None).
    weight_property : str | None, optional
        Edge weight property name, or None.
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
    if seed is not None:
        config["seed"] = seed
    if weight_property:
        config["relationshipWeightProperty"] = weight_property

    exec_mode = AlgorithmExecutionMode(mode)

    if exec_mode == AlgorithmExecutionMode.STREAM:
        query = (
            "CALL gds.louvain.stream($graph_name, $config) "
            "YIELD nodeId, communityId "
            "RETURN coalesce(gds.util.asNode(nodeId).id, gds.util.asNode(nodeId).name, toString(nodeId)) AS node_id, "
            "communityId"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})

        groups: dict[int, set[str]] = defaultdict(set)
        for row in rows:
            nid = row.get("node_id")
            cid = row.get("communityId")
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
            algorithm="louvain",
            backend="neo4j_gds",
        )

    if exec_mode == AlgorithmExecutionMode.WRITE:
        config["writeProperty"] = write_property or "community"
        query = (
            "CALL gds.louvain.write($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    if exec_mode == AlgorithmExecutionMode.MUTATE:
        config["mutateProperty"] = mutate_property or "community"
        query = (
            "CALL gds.louvain.mutate($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    raise AlgorithmError(f"Unsupported execution mode: {exec_mode}")


def louvain_communities(
    graph: Any,
    *,
    client: Any | None = None,
    resolution: float = 1.0,
    seed: int | None = None,
    weight_property: str | None = None,
    prefer_neo4j: bool = True,
    fallback_to_networkx: bool = True,
    **kwargs: Any,
) -> PartitionResult:
    """Adaptive entry point for Louvain Community Detection.

    Routes execution to Neo4j GDS if available and configured; otherwise defaults
    to local NetworkX computation.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph, TheoryGraph, or GDS projection name.
    client : Any | None, optional
        Neo4j client instance, or None.
    resolution : float, optional
        Resolution parameter (default: 1.0).
    seed : int | None, optional
        Random seed for determinism (default: None).
    weight_property : str | None, optional
        Edge weight property, or None.
    prefer_neo4j : bool, optional
        Whether to attempt Neo4j GDS execution first (default: True).
    fallback_to_networkx : bool, optional
        Whether to fallback to NetworkX if Neo4j GDS fails (default: True).
    **kwargs : Any
        Additional options passed to backend (e.g. mode, write_property).

    Returns
    -------
    PartitionResult
        Detected community partitions and node mappings.
    """
    if prefer_neo4j and client is not None:
        try:
            if client.is_gds_available():
                logger.debug("Executing Louvain via Neo4j GDS.")
                res = gds_louvain(
                    client,
                    graph,
                    resolution=resolution,
                    seed=seed,
                    weight_property=weight_property,
                    **kwargs,
                )
                if isinstance(res, PartitionResult):
                    return res
        except Exception as exc:
            if not fallback_to_networkx:
                raise
            logger.warning("GDS Louvain execution failed (%s); falling back to NetworkX.", exc)

    logger.debug("Executing Louvain via NetworkX.")
    return networkx_louvain(
        graph,
        resolution=resolution,
        seed=seed,
        weight_property=weight_property,
    )
