"""
Betweenness Centrality algorithm for NetworkX, Neo4j GDS, and adaptive dispatch.

Mathematical Formulation
-------------------------
Betweenness centrality quantifies the fraction of all-pairs shortest paths passing through node :math:`v`:

.. math::

    C_B(v) = \\sum_{s \\ne v \\ne t \\in V} \\frac{\\sigma_{st}(v)}{\\sigma_{st}}

where :math:`\\sigma_{st}` is the total number of shortest paths from :math:`s` to :math:`t`,
and :math:`\\sigma_{st}(v)` is the number of those paths passing through :math:`v`.
For directed graphs, scores are normalized by :math:`\\frac{1}{(n - 1)(n - 2)}`.
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from epistemetrics.core.exceptions import AlgorithmError, GDSProjectionError
from epistemetrics.core.models import AlgorithmExecutionMode, CentralityResult
from epistemetrics.graph.algorithms.common import extract_nx_graph, resolve_gds_graph_name

logger = logging.getLogger(__name__)


def networkx_betweenness(
    graph: Any,
    *,
    normalized: bool = True,
    weight_property: str | None = None,
) -> CentralityResult:
    """Compute Betweenness Centrality using NetworkX.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.
    normalized : bool, optional
        Whether to normalize scores (default: True).
    weight_property : str | None, optional
        Edge attribute name for weights/costs, or None.

    Returns
    -------
    CentralityResult
        Standardized mapping from node IDs to betweenness scores.
    """
    g = extract_nx_graph(graph)
    if len(g) == 0:
        return CentralityResult(scores={}, algorithm="betweenness", backend="networkx")

    try:
        raw_scores = nx.betweenness_centrality(
            g,
            normalized=normalized,
            weight=weight_property,
        )
        scores = {str(node): float(val) for node, val in raw_scores.items()}
        return CentralityResult(scores=scores, algorithm="betweenness", backend="networkx")
    except Exception as exc:
        raise AlgorithmError(f"NetworkX betweenness centrality failed: {exc}") from exc


def gds_betweenness(
    client: Any,
    graph: Any,
    *,
    normalized: bool = True,
    weight_property: str | None = None,
    mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
    write_property: str | None = "betweenness",
    mutate_property: str | None = "betweenness",
    default_graph_name: str = "theory_graph_projection",
) -> CentralityResult | dict[str, Any]:
    """Execute Betweenness Centrality via Neo4j Graph Data Science (GDS).

    Parameters
    ----------
    client : Neo4jClient
        Connected Neo4j client instance.
    graph : Any
        Target GDS projection name or domain graph.
    normalized : bool, optional
        Whether to normalize scores (default: True).
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
    CentralityResult | dict[str, Any]
        CentralityResult in STREAM mode; summary dict in MUTATE/WRITE mode.
    """
    client.ensure_gds_available()
    graph_name = resolve_gds_graph_name(graph, default_name=default_graph_name)

    # Check projection exists
    query_exists = "CALL gds.graph.exists($name) YIELD exists RETURN exists"
    exists_res = client.execute_query(query_exists, {"name": graph_name})
    if not (exists_res and exists_res[0].get("exists", False)):
        raise GDSProjectionError(
            f"GDS projection '{graph_name}' does not exist in catalog."
        )

    config: dict[str, Any] = {}
    if weight_property:
        config["relationshipWeightProperty"] = weight_property

    exec_mode = AlgorithmExecutionMode(mode)

    if exec_mode == AlgorithmExecutionMode.STREAM:
        query = (
            "CALL gds.betweenness.stream($graph_name, $config) "
            "YIELD nodeId, score "
            "RETURN coalesce(gds.util.asNode(nodeId).id, gds.util.asNode(nodeId).name, toString(nodeId)) AS node_id, "
            "score ORDER BY score DESC"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        raw_scores = {str(row["node_id"]): float(row["score"]) for row in rows if row.get("node_id") is not None}

        n = len(raw_scores)
        if normalized and n > 2:
            scale = 2.0 / ((n - 1) * (n - 2))
            scores = {node: val * scale for node, val in raw_scores.items()}
        else:
            scores = raw_scores

        return CentralityResult(scores=scores, algorithm="betweenness", backend="neo4j_gds")

    if exec_mode == AlgorithmExecutionMode.WRITE:
        config["writeProperty"] = write_property or "betweenness"
        query = (
            "CALL gds.betweenness.write($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    if exec_mode == AlgorithmExecutionMode.MUTATE:
        config["mutateProperty"] = mutate_property or "betweenness"
        query = (
            "CALL gds.betweenness.mutate($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    raise AlgorithmError(f"Unsupported execution mode: {exec_mode}")


def betweenness_centrality(
    graph: Any,
    *,
    client: Any | None = None,
    normalized: bool = True,
    weight_property: str | None = None,
    prefer_neo4j: bool = True,
    fallback_to_networkx: bool = True,
    **kwargs: Any,
) -> CentralityResult:
    """Adaptive entry point for Betweenness Centrality.

    Routes execution to Neo4j GDS if available and configured; otherwise defaults
    to local NetworkX computation.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph, TheoryGraph, or GDS projection name.
    client : Any | None, optional
        Neo4j client instance, or None.
    normalized : bool, optional
        Whether to normalize scores (default: True).
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
    CentralityResult
        Computed Betweenness scores.
    """
    if prefer_neo4j and client is not None:
        try:
            if client.is_gds_available():
                logger.debug("Executing Betweenness Centrality via Neo4j GDS.")
                res = gds_betweenness(
                    client,
                    graph,
                    normalized=normalized,
                    weight_property=weight_property,
                    **kwargs,
                )
                if isinstance(res, CentralityResult):
                    return res
        except Exception as exc:
            if not fallback_to_networkx:
                raise
            logger.warning("GDS Betweenness execution failed (%s); falling back to NetworkX.", exc)

    logger.debug("Executing Betweenness Centrality via NetworkX.")
    return networkx_betweenness(
        graph,
        normalized=normalized,
        weight_property=weight_property,
    )
