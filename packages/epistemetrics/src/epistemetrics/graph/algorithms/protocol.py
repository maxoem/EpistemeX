"""
Protocol definition for structural and topological graph algorithms.

Decouples epistemic evaluators and metrics from specific graph computation backends
(e.g. NetworkX vs. Neo4j Graph Data Science).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from epistemetrics.core.models import CentralityResult, PartitionResult


@runtime_checkable
class GraphAlgorithmsEngine(Protocol):
    """Abstract protocol for executing topological graph algorithms.

    All implementations (NetworkX, Neo4j GDS, Adaptive) must conform to this
    contract, returning normalized domain result models (CentralityResult, PartitionResult).
    """

    @property
    def backend_name(self) -> str:
        """Return the unique identifier of the algorithm execution backend.

        Returns
        -------
        str
            Backend name (e.g. 'networkx', 'neo4j_gds', 'adaptive').
        """
        ...

    def page_rank(
        self,
        graph: Any,
        *,
        damping_factor: float = 0.85,
        max_iter: int = 100,
        tolerance: float = 1e-6,
        weight_property: str | None = None,
    ) -> CentralityResult:
        """Compute PageRank centrality for all nodes in the graph.

        Parameters
        ----------
        graph : Any
            Target graph representation (NetworkX graph, TheoryGraph, or GDS projection name).
        damping_factor : float, optional
            Damping factor for random walk transitions (default: 0.85).
        max_iter : int, optional
            Maximum power iterations before convergence (default: 100).
        tolerance : float, optional
            Convergence tolerance threshold (default: 1e-6).
        weight_property : str | None, optional
            Edge attribute name containing relationship weights, or None for unweighted.

        Returns
        -------
        CentralityResult
            Standardized mapping of node IDs to PageRank scores.
        """
        ...

    def betweenness_centrality(
        self,
        graph: Any,
        *,
        normalized: bool = True,
        weight_property: str | None = None,
    ) -> CentralityResult:
        """Compute shortest-path betweenness centrality for all nodes.

        Parameters
        ----------
        graph : Any
            Target graph representation (NetworkX graph, TheoryGraph, or GDS projection name).
        normalized : bool, optional
            Whether to normalize scores by 2 / ((n-1)(n-2)) (default: True).
        weight_property : str | None, optional
            Edge attribute name containing relationship weights/distances, or None.

        Returns
        -------
        CentralityResult
            Standardized mapping of node IDs to betweenness scores.
        """
        ...

    def eigenvector_centrality(
        self,
        graph: Any,
        *,
        max_iter: int = 100,
        tolerance: float = 1e-6,
        weight_property: str | None = None,
    ) -> CentralityResult:
        """Compute eigenvector centrality based on the principal eigenvector of the adjacency matrix.

        Parameters
        ----------
        graph : Any
            Target graph representation (NetworkX graph, TheoryGraph, or GDS projection name).
        max_iter : int, optional
            Maximum power iterations (default: 100).
        tolerance : float, optional
            Convergence tolerance (default: 1e-6).
        weight_property : str | None, optional
            Edge attribute name containing weights, or None.

        Returns
        -------
        CentralityResult
            Standardized mapping of node IDs to eigenvector scores.
        """
        ...

    def weakly_connected_components(
        self,
        graph: Any,
    ) -> PartitionResult:
        """Detect weakly connected components (WCC) in the graph.

        Parameters
        ----------
        graph : Any
            Target graph representation (NetworkX graph, TheoryGraph, or GDS projection name).

        Returns
        -------
        PartitionResult
            Standardized partition result containing component sets and node mappings.
        """
        ...

    def louvain_communities(
        self,
        graph: Any,
        *,
        resolution: float = 1.0,
        seed: int | None = None,
        weight_property: str | None = None,
    ) -> PartitionResult:
        """Detect modular community structures using the Louvain heuristic.

        Parameters
        ----------
        graph : Any
            Target graph representation (NetworkX graph, TheoryGraph, or GDS projection name).
        resolution : float, optional
            Resolution parameter controlling community granularity (default: 1.0).
        seed : int | None, optional
            Random seed for deterministic node visitation order (default: None).
        weight_property : str | None, optional
            Edge attribute name containing weights, or None.

        Returns
        -------
        PartitionResult
            Standardized partition result containing community sets and node mappings.
        """
        ...
