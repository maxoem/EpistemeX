"""
Eigenvector Centrality algorithm for NetworkX, Neo4j GDS, and adaptive dispatch.

Mathematical Formulation
-------------------------
Eigenvector centrality assigns relative scores to all nodes based on the principle
that connections to high-scoring nodes contribute more to the score of the node in question:

.. math::

    \\lambda x_v = \\sum_{u \\in \\mathcal{N}_{in}(v)} A_{uv} x_u

or in matrix form :math:`A x = \\lambda x`, where :math:`\\lambda` is the principal eigenvalue.
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
from epistemetrics.graph.algorithms.common import extract_nx_graph, resolve_gds_graph_name

logger = logging.getLogger(__name__)


def networkx_eigenvector(
    graph: Any,
    *,
    max_iter: int = 100,
    tolerance: float = 1e-6,
    weight_property: str | None = None,
) -> CentralityResult:
    """Compute Eigenvector Centrality using NetworkX with NumPy eigensolver fallback.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.
    max_iter : int, optional
        Maximum power iterations (default: 100).
    tolerance : float, optional
        Convergence tolerance (default: 1e-6).
    weight_property : str | None, optional
        Edge weight attribute name, or None.

    Returns
    -------
    CentralityResult
        Standardized mapping from node IDs to eigenvector scores.

    Raises
    ------
    AlgorithmConvergenceError
        If both power iteration and NumPy eigensolvers fail to converge.
    """
    g = extract_nx_graph(graph)
    if len(g) == 0:
        return CentralityResult(scores={}, algorithm="eigenvector", backend="networkx")

    calc_graph = g
    if isinstance(g, (nx.MultiGraph, nx.MultiDiGraph)):
        calc_graph = nx.DiGraph(g) if g.is_directed() else nx.Graph(g)

    try:
        raw_scores = nx.eigenvector_centrality(
            calc_graph,
            max_iter=max_iter,
            tol=tolerance,
            weight=weight_property,
        )
        scores = {str(node): float(val) for node, val in raw_scores.items()}
        return CentralityResult(scores=scores, algorithm="eigenvector", backend="networkx")
    except (nx.PowerIterationFailedConvergence, nx.NetworkXError):
        logger.debug("NetworkX power iteration eigenvector failed; using numpy solver fallback.")
        try:
            raw_scores = nx.eigenvector_centrality_numpy(
                calc_graph,
                weight=weight_property,
                max_iter=max_iter,
                tol=tolerance,
            )
            scores = {str(node): float(val) for node, val in raw_scores.items()}
            return CentralityResult(scores=scores, algorithm="eigenvector", backend="networkx")
        except Exception as inner_exc:
            raise AlgorithmConvergenceError(
                f"Eigenvector centrality failed to converge: {inner_exc}"
            ) from inner_exc


def gds_eigenvector(
    client: Any,
    graph: Any,
    *,
    max_iter: int = 100,
    tolerance: float = 1e-6,
    weight_property: str | None = None,
    mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
    write_property: str | None = "eigenvector",
    mutate_property: str | None = "eigenvector",
    default_graph_name: str = "theory_graph_projection",
) -> CentralityResult | dict[str, Any]:
    """Execute Eigenvector Centrality via Neo4j Graph Data Science (GDS).

    Parameters
    ----------
    client : Neo4jClient
        Connected Neo4j client instance.
    graph : Any
        Target GDS projection name or domain graph.
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

    query_exists = "CALL gds.graph.exists($name) YIELD exists RETURN exists"
    exists_res = client.execute_query(query_exists, {"name": graph_name})
    if not (exists_res and exists_res[0].get("exists", False)):
        raise GDSProjectionError(
            f"GDS projection '{graph_name}' does not exist in catalog."
        )

    config: dict[str, Any] = {
        "maxIterations": max_iter,
        "tolerance": tolerance,
    }
    if weight_property:
        config["relationshipWeightProperty"] = weight_property

    exec_mode = AlgorithmExecutionMode(mode)

    if exec_mode == AlgorithmExecutionMode.STREAM:
        query = (
            "CALL gds.eigenvector.stream($graph_name, $config) "
            "YIELD nodeId, score "
            "RETURN coalesce(gds.util.asNode(nodeId).id, gds.util.asNode(nodeId).name, toString(nodeId)) AS node_id, "
            "score ORDER BY score DESC"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        scores = {str(row["node_id"]): float(row["score"]) for row in rows if row.get("node_id") is not None}
        return CentralityResult(scores=scores, algorithm="eigenvector", backend="neo4j_gds")

    if exec_mode == AlgorithmExecutionMode.WRITE:
        config["writeProperty"] = write_property or "eigenvector"
        query = (
            "CALL gds.eigenvector.write($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    if exec_mode == AlgorithmExecutionMode.MUTATE:
        config["mutateProperty"] = mutate_property or "eigenvector"
        query = (
            "CALL gds.eigenvector.mutate($graph_name, $config) "
            "YIELD nodePropertiesWritten, computeMillis "
            "RETURN nodePropertiesWritten, computeMillis"
        )
        rows = client.execute_query(query, {"graph_name": graph_name, "config": config})
        return rows[0] if rows else {}

    raise AlgorithmError(f"Unsupported execution mode: {exec_mode}")


def eigenvector_centrality(
    graph: Any,
    *,
    client: Any | None = None,
    max_iter: int = 100,
    tolerance: float = 1e-6,
    weight_property: str | None = None,
    prefer_neo4j: bool = True,
    fallback_to_networkx: bool = True,
    **kwargs: Any,
) -> CentralityResult:
    """Adaptive entry point for Eigenvector Centrality.

    Routes execution to Neo4j GDS if available and configured; otherwise defaults
    to local NetworkX computation with automated solver fallback.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph, TheoryGraph, or GDS projection name.
    client : Any | None, optional
        Neo4j client instance, or None.
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
        Computed Eigenvector scores.
    """
    if prefer_neo4j and client is not None:
        try:
            if client.is_gds_available():
                logger.debug("Executing Eigenvector Centrality via Neo4j GDS.")
                res = gds_eigenvector(
                    client,
                    graph,
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
            logger.warning("GDS Eigenvector execution failed (%s); falling back to NetworkX.", exc)

    logger.debug("Executing Eigenvector Centrality via NetworkX.")
    return networkx_eigenvector(
        graph,
        max_iter=max_iter,
        tolerance=tolerance,
        weight_property=weight_property,
    )
