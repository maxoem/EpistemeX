"""Katz Centrality algorithm for directed, acyclic, and cyclic graphs.

Mathematical Formulation
------------------------
Katz centrality assigns each node a baseline weight :math:`\\beta` plus the
attenuated sum of incoming neighbor centralities:

.. math::

    x_i = \\alpha \\sum_{j} A_{ji} x_j + \\beta

Unlike standard eigenvector centrality, Katz centrality remains strictly
non-degenerate on directed acyclic graphs (DAGs) where the adjacency matrix is
nilpotent.
"""

from __future__ import annotations

import logging
from typing import Any

import networkx as nx
import numpy as np

from epistemetrics.core.exceptions import AlgorithmError
from epistemetrics.core.models import CentralityResult
from epistemetrics.graph.algorithms.common import extract_nx_graph

logger = logging.getLogger(__name__)


def _has_negative_weight(g: nx.Graph, weight_property: str | None) -> bool:
    """Return True if any edge carries a negative numeric weight."""
    if weight_property is None:
        return False
    for _, _, data in g.edges(data=True):
        val = data.get(weight_property)
        if val is not None and float(val) < 0.0:
            return True
    return False


def networkx_katz(
    graph: Any,
    *,
    alpha: float | None = None,
    beta: float = 1.0,
    max_iter: int = 1000,
    tolerance: float = 1e-6,
    normalized: bool = True,
    weight_property: str | None = None,
) -> CentralityResult:
    """Compute Katz Centrality on directed or undirected non-negative graphs.

    When ``alpha`` is omitted, a safe attenuation factor strictly below the
    reciprocal spectral radius is selected automatically (``0.1`` on DAGs where
    :math:`\\rho(A) = 0`, and ``0.85 / \\max(1.0, \\rho(A))`` on cyclic graphs).

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.
    alpha : float or None, optional
        Attenuation factor. If None, selected safely below ``1 / rho(A)``.
    beta : float, default 1.0
        Baseline centrality constant assigned to every node.
    max_iter : int, default 1000
        Maximum iterations for iterative computation.
    tolerance : float, default 1e-6
        Convergence tolerance.
    normalized : bool, default True
        Whether to L2-normalize the resulting centrality vector.
    weight_property : str or None, optional
        Edge weight attribute name, or None for unit weights.

    Returns
    -------
    CentralityResult
        Standardized mapping from node IDs to Katz centrality scores.

    Raises
    ------
    AlgorithmError
        If the graph contains negative edge weights or computation fails.
    """
    g = extract_nx_graph(graph)
    if len(g) == 0:
        return CentralityResult(scores={}, algorithm="katz", backend="networkx")

    calc_graph = g
    if isinstance(g, (nx.MultiGraph, nx.MultiDiGraph)):
        calc_graph = nx.DiGraph() if g.is_directed() else nx.Graph()
        calc_graph.add_nodes_from(g.nodes(data=True))
        for u, v, data in g.edges(data=True):
            w = float(data.get(weight_property, 1.0)) if weight_property else 1.0
            if calc_graph.has_edge(u, v):
                calc_graph[u][v]["_katz_w"] += w
            else:
                calc_graph.add_edge(u, v, _katz_w=w)
        weight_key: str | None = "_katz_w"
    else:
        weight_key = weight_property

    if _has_negative_weight(calc_graph, weight_key):
        raise AlgorithmError(
            "Katz centrality requires an unsigned non-negative projection; "
            "negative edge weights are not supported."
        )

    eff_alpha = alpha
    if eff_alpha is None:
        if calc_graph.is_directed() and nx.is_directed_acyclic_graph(calc_graph):
            eff_alpha = 0.1
        else:
            adj = nx.to_numpy_array(calc_graph, weight=weight_key, dtype=np.float64)
            eigvals = np.linalg.eigvals(adj)
            spectral_radius = float(np.max(np.abs(eigvals))) if len(eigvals) else 0.0
            eff_alpha = 0.1 if spectral_radius <= 1e-12 else 0.85 / spectral_radius

    try:
        raw_scores = nx.katz_centrality_numpy(
            calc_graph,
            alpha=eff_alpha,
            beta=beta,
            normalized=normalized,
            weight=weight_key,
        )
        scores = {str(node): float(val) for node, val in raw_scores.items()}
        return CentralityResult(scores=scores, algorithm="katz", backend="networkx")
    except Exception as exc:
        try:
            raw_scores = nx.katz_centrality(
                calc_graph,
                alpha=eff_alpha,
                beta=beta,
                max_iter=max_iter,
                tol=tolerance,
                normalized=normalized,
                weight=weight_key,
            )
            scores = {str(node): float(val) for node, val in raw_scores.items()}
            return CentralityResult(scores=scores, algorithm="katz", backend="networkx")
        except Exception as inner_exc:
            raise AlgorithmError(
                f"Katz centrality computation failed: {inner_exc}"
            ) from exc


def katz_centrality(
    graph: Any,
    *,
    alpha: float | None = None,
    beta: float = 1.0,
    max_iter: int = 1000,
    tolerance: float = 1e-6,
    normalized: bool = True,
    weight_property: str | None = None,
) -> CentralityResult:
    """Compute Katz Centrality on a NetworkX graph or TheoryGraph.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.
    alpha : float or None, optional
        Attenuation factor. If None, selected automatically below ``1 / rho(A)``.
    beta : float, default 1.0
        Baseline centrality constant.
    max_iter : int, default 1000
        Maximum iterations.
    tolerance : float, default 1e-6
        Convergence tolerance.
    normalized : bool, default True
        Whether to L2-normalize scores.
    weight_property : str or None, optional
        Edge weight attribute name.

    Returns
    -------
    CentralityResult
        Computed Katz centrality scores.
    """
    return networkx_katz(
        graph,
        alpha=alpha,
        beta=beta,
        max_iter=max_iter,
        tolerance=tolerance,
        normalized=normalized,
        weight_property=weight_property,
    )
