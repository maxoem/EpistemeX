"""
NetworkX engine coordinating local execution of graph algorithms.

Conforms to GraphAlgorithmsEngine by delegating each algorithm call to its
isolated modular implementation.
"""

from __future__ import annotations

from typing import Any

from epistemetrics.core.models import CentralityResult, PartitionResult
from epistemetrics.graph.algorithms.betweenness import networkx_betweenness
from epistemetrics.graph.algorithms.eigenvector import networkx_eigenvector
from epistemetrics.graph.algorithms.louvain import networkx_louvain
from epistemetrics.graph.algorithms.pagerank import networkx_pagerank
from epistemetrics.graph.algorithms.wcc import networkx_wcc


class NetworkXAlgorithmsEngine:
    """Graph algorithms engine backed strictly by NetworkX.

    Guarantees pure local execution with zero database dependencies.
    """

    @property
    def backend_name(self) -> str:
        """Return the unique backend identifier."""
        return "networkx"

    def page_rank(
        self,
        graph: Any,
        *,
        damping_factor: float = 0.85,
        max_iter: int = 100,
        tolerance: float = 1e-6,
        weight_property: str | None = None,
    ) -> CentralityResult:
        """Compute PageRank centrality using NetworkX."""
        return networkx_pagerank(
            graph,
            damping_factor=damping_factor,
            max_iter=max_iter,
            tolerance=tolerance,
            weight_property=weight_property,
        )

    def betweenness_centrality(
        self,
        graph: Any,
        *,
        normalized: bool = True,
        weight_property: str | None = None,
    ) -> CentralityResult:
        """Compute Betweenness Centrality using NetworkX."""
        return networkx_betweenness(
            graph,
            normalized=normalized,
            weight_property=weight_property,
        )

    def eigenvector_centrality(
        self,
        graph: Any,
        *,
        max_iter: int = 100,
        tolerance: float = 1e-6,
        weight_property: str | None = None,
    ) -> CentralityResult:
        """Compute Eigenvector Centrality using NetworkX with NumPy fallback."""
        return networkx_eigenvector(
            graph,
            max_iter=max_iter,
            tolerance=tolerance,
            weight_property=weight_property,
        )

    def weakly_connected_components(
        self,
        graph: Any,
    ) -> PartitionResult:
        """Detect weakly connected components using NetworkX."""
        return networkx_wcc(graph)

    def louvain_communities(
        self,
        graph: Any,
        *,
        resolution: float = 1.0,
        seed: int | None = None,
        weight_property: str | None = None,
    ) -> PartitionResult:
        """Detect modular community structures using NetworkX Louvain implementation."""
        return networkx_louvain(
            graph,
            resolution=resolution,
            seed=seed,
            weight_property=weight_property,
        )
