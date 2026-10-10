"""
Adaptive graph algorithms engine with automated Neo4j GDS / NetworkX fallback.

Coordinates dynamic algorithm routing and fallback by composing the Neo4j GDS
engine and the local NetworkX engine.
"""

from __future__ import annotations

import logging
from typing import Any

from epistemetrics.adapters.neo4j.gds_engine import Neo4jGDSAlgorithmsEngine
from epistemetrics.core.models import CentralityResult, PartitionResult
from epistemetrics.graph.algorithms.networkx_engine import NetworkXAlgorithmsEngine

logger = logging.getLogger(__name__)


class AdaptiveAlgorithmsEngine:
    """Adaptive dispatcher executing algorithms on Neo4j GDS or NetworkX.

    Provides a uniform, drop-in interface for epistemic metrics. Downstream metrics
    call algorithm methods on this engine; the engine handles backend selection,
    availability detection, and resilient fallback transparently.

    Parameters
    ----------
    neo4j_engine : Neo4jGDSAlgorithmsEngine | None, optional
        Configured Neo4j GDS engine, or None if Neo4j is not configured.
    networkx_engine : NetworkXAlgorithmsEngine | None, optional
        Configured NetworkX engine (defaults to a new instance).
    prefer_neo4j : bool, optional
        Whether to attempt Neo4j GDS execution before NetworkX (default: True).
    fallback_to_networkx : bool, optional
        Whether to fall back to NetworkX if Neo4j GDS fails or is unavailable (default: True).
    """

    def __init__(
        self,
        neo4j_engine: Neo4jGDSAlgorithmsEngine | None = None,
        networkx_engine: NetworkXAlgorithmsEngine | None = None,
        *,
        prefer_neo4j: bool = True,
        fallback_to_networkx: bool = True,
    ) -> None:
        self.neo4j_engine = neo4j_engine
        self.networkx_engine = networkx_engine or NetworkXAlgorithmsEngine()
        self.prefer_neo4j = prefer_neo4j
        self.fallback_to_networkx = fallback_to_networkx

    @property
    def backend_name(self) -> str:
        """Return composite backend identifier."""
        return "adaptive"

    def can_use_neo4j(self, graph: Any) -> bool:
        """Evaluate whether Neo4j GDS is operational and suitable for the given graph.

        Parameters
        ----------
        graph : Any
            Target graph representation.

        Returns
        -------
        bool
            True if Neo4j GDS can execute on the target graph, False otherwise.
        """
        if not self.prefer_neo4j or self.neo4j_engine is None:
            return False

        try:
            if not self.neo4j_engine.client.is_gds_available():
                return False

            if isinstance(graph, str):
                return self.neo4j_engine.has_projection(graph)

            if hasattr(graph, "projection_name") and getattr(graph, "projection_name"):
                return self.neo4j_engine.has_projection(getattr(graph, "projection_name"))

            return False
        except Exception as exc:
            logger.debug("Error checking Neo4j GDS capability: %s", exc)
            return False

    def page_rank(
        self,
        graph: Any,
        *,
        damping_factor: float = 0.85,
        max_iter: int = 100,
        tolerance: float = 1e-6,
        weight_property: str | None = None,
        **kwargs: Any,
    ) -> CentralityResult:
        """Compute PageRank, routing to Neo4j GDS if available, otherwise NetworkX."""
        if self.can_use_neo4j(graph) and self.neo4j_engine is not None:
            try:
                logger.debug("Executing PageRank via Neo4j GDS engine.")
                res = self.neo4j_engine.page_rank(
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
                if not self.fallback_to_networkx:
                    raise
                logger.warning("Neo4j GDS PageRank execution failed (%s); falling back to NetworkX.", exc)

        logger.debug("Executing PageRank via NetworkX engine.")
        return self.networkx_engine.page_rank(
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
        **kwargs: Any,
    ) -> CentralityResult:
        """Compute Betweenness Centrality, routing to Neo4j GDS if available, otherwise NetworkX."""
        if self.can_use_neo4j(graph) and self.neo4j_engine is not None:
            try:
                logger.debug("Executing Betweenness Centrality via Neo4j GDS engine.")
                res = self.neo4j_engine.betweenness_centrality(
                    graph,
                    normalized=normalized,
                    weight_property=weight_property,
                    **kwargs,
                )
                if isinstance(res, CentralityResult):
                    return res
            except Exception as exc:
                if not self.fallback_to_networkx:
                    raise
                logger.warning(
                    "Neo4j GDS Betweenness execution failed (%s); falling back to NetworkX.",
                    exc,
                )

        logger.debug("Executing Betweenness Centrality via NetworkX engine.")
        return self.networkx_engine.betweenness_centrality(
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
        **kwargs: Any,
    ) -> CentralityResult:
        """Compute Eigenvector Centrality, routing to Neo4j GDS if available, otherwise NetworkX."""
        if self.can_use_neo4j(graph) and self.neo4j_engine is not None:
            try:
                logger.debug("Executing Eigenvector Centrality via Neo4j GDS engine.")
                res = self.neo4j_engine.eigenvector_centrality(
                    graph,
                    max_iter=max_iter,
                    tolerance=tolerance,
                    weight_property=weight_property,
                    **kwargs,
                )
                if isinstance(res, CentralityResult):
                    return res
            except Exception as exc:
                if not self.fallback_to_networkx:
                    raise
                logger.warning(
                    "Neo4j GDS Eigenvector execution failed (%s); falling back to NetworkX.",
                    exc,
                )

        logger.debug("Executing Eigenvector Centrality via NetworkX engine.")
        return self.networkx_engine.eigenvector_centrality(
            graph,
            max_iter=max_iter,
            tolerance=tolerance,
            weight_property=weight_property,
        )

    def weakly_connected_components(
        self,
        graph: Any,
        **kwargs: Any,
    ) -> PartitionResult:
        """Detect Weakly Connected Components (WCC), routing to Neo4j GDS if available, otherwise NetworkX."""
        if self.can_use_neo4j(graph) and self.neo4j_engine is not None:
            try:
                logger.debug("Executing WCC via Neo4j GDS engine.")
                res = self.neo4j_engine.weakly_connected_components(graph, **kwargs)
                if isinstance(res, PartitionResult):
                    return res
            except Exception as exc:
                if not self.fallback_to_networkx:
                    raise
                logger.warning("Neo4j GDS WCC execution failed (%s); falling back to NetworkX.", exc)

        logger.debug("Executing WCC via NetworkX engine.")
        return self.networkx_engine.weakly_connected_components(graph)

    def louvain_communities(
        self,
        graph: Any,
        *,
        resolution: float = 1.0,
        seed: int | None = None,
        weight_property: str | None = None,
        **kwargs: Any,
    ) -> PartitionResult:
        """Detect Louvain communities, routing to Neo4j GDS if available, otherwise NetworkX."""
        if self.can_use_neo4j(graph) and self.neo4j_engine is not None:
            try:
                logger.debug("Executing Louvain Community Detection via Neo4j GDS engine.")
                res = self.neo4j_engine.louvain_communities(
                    graph,
                    resolution=resolution,
                    seed=seed,
                    weight_property=weight_property,
                    **kwargs,
                )
                if isinstance(res, PartitionResult):
                    return res
            except Exception as exc:
                if not self.fallback_to_networkx:
                    raise
                logger.warning("Neo4j GDS Louvain execution failed (%s); falling back to NetworkX.", exc)

        logger.debug("Executing Louvain Community Detection via NetworkX engine.")
        return self.networkx_engine.louvain_communities(
            graph,
            resolution=resolution,
            seed=seed,
            weight_property=weight_property,
        )
