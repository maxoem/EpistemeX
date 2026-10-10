"""
PageRank Centrality algorithm for NetworkX, Neo4j GDS, and adaptive dispatch.

Mathematical Formulation
-------------------------
PageRank models the stationary distribution of a random walk with teleportation:

.. math::

    PR(u) = \\frac{1 - d}{|V|} + d \\sum_{v \\in \\mathcal{N}_{in}(u)} \\frac{PR(v)}{|\\mathcal{N}_{out}(v)|}

where :math:`d \\in (0, 1)` is the damping factor (typically 0.85).
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx

from epistemetrics.core.exceptions import (
    AlgorithmConvergenceError,
    AlgorithmError,
    GDSProjectionError,
)
from epistemetrics.core.models import AlgorithmExecutionMode, CentralityResult
from epistemetrics.graph.algorithms.common import (
    extract_nx_graph,
    resolve_gds_graph_name,
)

logger = logging.getLogger(__name__)


def networkx_pagerank(
    graph: Any,
    *,
    damping_factor: float = 0.85,
    max_iter: int = 100,
    tolerance: float = 1e-6,
    weight_property: str | None = None,
) -> CentralityResult:
    """Compute PageRank centrality using NetworkX.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.
    damping_factor : float, optional
        Damping factor :math:`d` (default: 0.85).
    max_iter : int, optional
        Maximum power iteration rounds (default: 100).
    tolerance : float, optional
        Convergence tolerance (default: 1e-6).
    weight_property : str | None, optional
        Edge attribute name for weights, or None.

    Returns
    -------
    CentralityResult
        Standardized mapping from node IDs to PageRank scores.

    Raises
    ------
    AlgorithmConvergenceError
        If power iteration fails to converge within max_iter.
    """
    g = extract_nx_graph(graph)
    if len(g) == 0:
        return CentralityResult(scores={}, algorithm="pagerank", backend="networkx")

    try:
        raw_scores = nx.pagerank(
            g,
            alpha=damping_factor,
            max_iter=max_iter,
            tol=tolerance,
            weight=weight_property,
        )
        scores = {str(node): float(val) for node, val in raw_scores.items()}
        return CentralityResult(scores=scores, algorithm="pagerank", backend="networkx")
    except nx.PowerIterationFailedConvergence as exc:
        raise AlgorithmConvergenceError(
            f"NetworkX PageRank failed to converge after {max_iter} iterations."
        ) from exc
    except Exception as exc:
        raise AlgorithmError(f"NetworkX PageRank computation failed: {exc}") from exc


def gds_pagerank(
    client: Any,
    graph: Any,
    *,
    damping_factor: float = 0.85,
    max_iter: int = 100,
    tolerance: float = 1e-6,
    weight_property: str | None = None,
    mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
    write_property: str | None = "pagerank",
    mutate_property: str | None = "pagerank",
    default_graph_name: str = "theory_graph_projection",
) -> CentralityResult | dict[str, Any]:
    """Execute PageRank centrality via Neo4j Graph Data Science (GDS).

    Parameters
    ----------
    client : Neo4jClient
        Connected Neo4j client instance.
    graph : Any
        Target GDS projection name or domain graph.
    damping_factor : float, optional
        Damping factor (default: 0.85).
    max_iter : int, optional
        Maximum power iterations (default: 100).
    tolerance : float, optional
        Convergence tolerance (default: 1e-6).
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

    config: dict[str, Any] = {
        "dampingFactor": damping_factor,
        "maxIterations": max_iter,
        "tolerance": tolerance,
    }
    if weight_property:
        config["relationshipWeightProperty"] = weight_property

    exec_mode = AlgorithmExecutionMode(mode)

    if exec_mode == AlgorithmExecutionMode.STREAM:
        query = (
            "CALL gds.pageRank.stream($graph_name, $config) "
            "YIELD nodeId, score "
            "RETURN coalesce(gds.util.asNode(nodeId).id, gds.util.asNode(nodeId).name, toString(nodeId)) AS node_id, "
            "score ORDER BY score DESC"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        scores = {str(row["node_id"]): float(row["score"]) for row in rows if row.get("node_id") is not None}
        return CentralityResult(scores=scores, algorithm="pagerank", backend="neo4j_gds")

    if exec_mode == AlgorithmExecutionMode.WRITE:
        config["writeProperty"] = write_property or "pagerank"
        query = (
            "CALL gds.pageRank.write($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    if exec_mode == AlgorithmExecutionMode.MUTATE:
        config["mutateProperty"] = mutate_property or "pagerank"
        query = (
            "CALL gds.pageRank.mutate($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    raise AlgorithmError(f"Unsupported execution mode: {exec_mode}")


def page_rank(
    graph: Any,
    *,
    client: Any | None = None,
    damping_factor: float = 0.85,
    max_iter: int = 100,
    tolerance: float = 1e-6,
    weight_property: str | None = None,
    prefer_neo4j: bool = True,
    fallback_to_networkx: bool = True,
    **kwargs: Any,
) -> CentralityResult:
    """Adaptive entry point for PageRank centrality.

    Routes execution to Neo4j GDS if a connected client is available and the graph
    has a projection; otherwise defaults smoothly to local NetworkX computation.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph, TheoryGraph, or GDS projection name.
    client : Any | None, optional
        Neo4j client instance, or None.
    damping_factor : float, optional
        Damping factor (default: 0.85).
    max_iter : int, optional
        Maximum iterations (default: 100).
    tolerance : float, optional
        Convergence threshold (default: 1e-6).
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
        Computed PageRank scores.
    """
    if prefer_neo4j and client is not None:
        try:
            if client.is_gds_available():
                logger.debug("Executing PageRank via Neo4j GDS.")
                res = gds_pagerank(
                    client,
                    graph,
                    damping_factor=damping_factor,
                    max_iter=max_iter,
                    tolerance=tolerance,
                    weight_property=weight_property,
                    **kwargs,
                )
                if isinstance(res, CentralityResult):
                    return res
        except Exception as exc:
            if not fallback_to_networkx:
                raise
            logger.warning("GDS PageRank execution failed (%s); falling back to NetworkX.", exc)

    logger.debug("Executing PageRank via NetworkX.")
    return networkx_pagerank(
        graph,
        damping_factor=damping_factor,
        max_iter=max_iter,
        tolerance=tolerance,
        weight_property=weight_property,
    )
