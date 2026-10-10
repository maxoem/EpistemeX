"""
Shared utility functions for graph algorithm implementations.
"""

from __future__ import annotations

from typing import Any

import networkx as nx


def extract_nx_graph(graph: Any) -> nx.Graph:
    """Extract or unwrap an underlying NetworkX graph from domain containers.

    Parameters
    ----------
    graph : Any
        Graph instance, domain TheoryGraph, or NetworkX graph object.

    Returns
    -------
    nx.Graph
        Underlying NetworkX Graph, DiGraph, or MultiDiGraph.

    Raises
    ------
    TypeError
        If graph cannot be converted or unwrapped into a NetworkX graph.
    """
    if isinstance(graph, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
        return graph
    if hasattr(graph, "nx_graph"):
        return graph.nx_graph
    if hasattr(graph, "graph") and isinstance(graph.graph, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
        return graph.graph
    raise TypeError(
        f"Expected a NetworkX graph or TheoryGraph containing 'nx_graph', got {type(graph).__name__}"
    )


def resolve_gds_graph_name(graph: Any, default_name: str = "theory_graph_projection") -> str:
    """Resolve the target GDS projection name from a graph argument.

    Parameters
    ----------
    graph : Any
        Projection name string or domain graph object.
    default_name : str, optional
        Default projection name if graph has none (default: 'theory_graph_projection').

    Returns
    -------
    str
        Resolved GDS graph projection name.
    """
    if isinstance(graph, str) and graph:
        return graph
    if hasattr(graph, "projection_name") and getattr(graph, "projection_name"):
        return getattr(graph, "projection_name")
    if hasattr(graph, "name") and getattr(graph, "name"):
        return getattr(graph, "name")
    return default_name
