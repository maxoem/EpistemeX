"""
Neo4j Graph Data Science (GDS) implementation of structural graph algorithms.

Manages server-side GDS graph catalog projections and coordinates procedure execution
by delegating to isolated modular algorithm implementations.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from epistemetrics.adapters.neo4j.client import Neo4jClient
from epistemetrics.core.exceptions import GDSProjectionError
from epistemetrics.core.models import (
    AlgorithmExecutionMode,
    CentralityResult,
    PartitionResult,
)
from epistemetrics.graph.algorithms.betweenness import gds_betweenness
from epistemetrics.graph.algorithms.eigenvector import gds_eigenvector
from epistemetrics.graph.algorithms.louvain import gds_louvain
from epistemetrics.graph.algorithms.pagerank import gds_pagerank
from epistemetrics.graph.algorithms.wcc import gds_wcc

logger = logging.getLogger(__name__)


class Neo4jGDSAlgorithmsEngine:
    """Graph algorithms engine executing directly on Neo4j Graph Data Science (GDS).

    Supports stream, mutate, and write execution modes alongside in-memory catalog
    projection management.

    Parameters
    ----------
    client : Neo4jClient
        Connected Neo4j client instance.
    default_graph_name : str, optional
        Default in-memory GDS projection name (default: 'theory_graph_projection').
    """

    def __init__(
        self,
        client: Neo4jClient,
        default_graph_name: str = "theory_graph_projection",
    ) -> None:
        self.client = client
        self.default_graph_name = default_graph_name

    @property
    def backend_name(self) -> str:
        """Return the unique backend identifier."""
        return "neo4j_gds"

    def has_projection(self, graph_name: str) -> bool:
        """Check whether an in-memory graph projection exists in the GDS catalog."""
        try:
            query = "CALL gds.graph.exists($name) YIELD exists RETURN exists"
            results = self.client.execute_query(query, {"name": graph_name})
            return bool(results and results[0].get("exists", False))
        except Exception as exc:
            logger.debug("Failed to verify GDS projection existence for '%s': %s", graph_name, exc)
            return False

    def project_graph(
        self,
        graph_name: str,
        node_projection: Any = "*",
        relationship_projection: Any = "*",
        configuration: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Project a subgraph from Neo4j into the in-memory GDS graph catalog."""
        self.client.ensure_gds_available()
        config = configuration or {}
        query = (
            "CALL gds.graph.project($graph_name, $node_proj, $rel_proj, $config) "
            "YIELD graphName, nodeCount, relationshipCount "
            "RETURN graphName, nodeCount, relationshipCount"
        )
        params = {
            "graph_name": graph_name,
            "node_proj": node_projection,
            "rel_proj": relationship_projection,
            "config": config,
        }
        try:
            res = self.client.execute_query(query, params)
            if not res:
                raise GDSProjectionError(f"No result returned when creating projection '{graph_name}'.")
            return res[0]
        except Exception as exc:
            raise GDSProjectionError(f"Failed to create GDS projection '{graph_name}': {exc}") from exc

    def drop_projection(self, graph_name: str, fail_if_missing: bool = False) -> bool:
        """Drop an in-memory graph projection from the GDS catalog."""
        if not self.has_projection(graph_name):
            if fail_if_missing:
                raise GDSProjectionError(f"Projection '{graph_name}' does not exist.")
            return False

        query = (
            "CALL gds.graph.drop($graph_name, $fail_if_missing) "
            "YIELD graphName RETURN graphName"
        )
        try:
            self.client.execute_query(query, {"graph_name": graph_name, "fail_if_missing": fail_if_missing})
            return True
        except Exception as exc:
            logger.warning("Failed to drop GDS projection '%s': %s", graph_name, exc)
            return False

    @contextmanager
    def temporary_projection(
        self,
        graph_name: str,
        node_projection: Any = "*",
        relationship_projection: Any = "*",
        configuration: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        """Context manager creating a temporary GDS projection that is automatically dropped on exit."""
        if self.has_projection(graph_name):
            self.drop_projection(graph_name)
        self.project_graph(graph_name, node_projection, relationship_projection, configuration)
        try:
            yield graph_name
        finally:
            self.drop_projection(graph_name)

    def page_rank(
        self,
        graph: Any,
        *,
        damping_factor: float = 0.85,
        max_iter: int = 100,
        tolerance: float = 1e-6,
        weight_property: str | None = None,
        mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
        write_property: str | None = "pagerank",
        mutate_property: str | None = "pagerank",
    ) -> CentralityResult | dict[str, Any]:
        """Execute PageRank centrality via Neo4j GDS."""
        return gds_pagerank(
            client=self.client,
            graph=graph,
            damping_factor=damping_factor,
            max_iter=max_iter,
            tolerance=tolerance,
            weight_property=weight_property,
            mode=mode,
            write_property=write_property,
            mutate_property=mutate_property,
            default_graph_name=self.default_graph_name,
        )

    def betweenness_centrality(
        self,
        graph: Any,
        *,
        normalized: bool = True,
        weight_property: str | None = None,
        mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
        write_property: str | None = "betweenness",
        mutate_property: str | None = "betweenness",
    ) -> CentralityResult | dict[str, Any]:
        """Execute Betweenness Centrality via Neo4j GDS."""
        return gds_betweenness(
            client=self.client,
            graph=graph,
            normalized=normalized,
            weight_property=weight_property,
            mode=mode,
            write_property=write_property,
            mutate_property=mutate_property,
            default_graph_name=self.default_graph_name,
        )

    def eigenvector_centrality(
        self,
        graph: Any,
        *,
        max_iter: int = 100,
        tolerance: float = 1e-6,
        weight_property: str | None = None,
        mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
        write_property: str | None = "eigenvector",
        mutate_property: str | None = "eigenvector",
    ) -> CentralityResult | dict[str, Any]:
        """Execute Eigenvector Centrality via Neo4j GDS."""
        return gds_eigenvector(
            client=self.client,
            graph=graph,
            max_iter=max_iter,
            tolerance=tolerance,
            weight_property=weight_property,
            mode=mode,
            write_property=write_property,
            mutate_property=mutate_property,
            default_graph_name=self.default_graph_name,
        )

    def weakly_connected_components(
        self,
        graph: Any,
        *,
        mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
        write_property: str | None = "wcc",
        mutate_property: str | None = "wcc",
    ) -> PartitionResult | dict[str, Any]:
        """Execute Weakly Connected Components (WCC) via Neo4j GDS."""
        return gds_wcc(
            client=self.client,
            graph=graph,
            mode=mode,
            write_property=write_property,
            mutate_property=mutate_property,
            default_graph_name=self.default_graph_name,
        )

    def louvain_communities(
        self,
        graph: Any,
        *,
        resolution: float = 1.0,
        seed: int | None = None,
        weight_property: str | None = None,
        mode: AlgorithmExecutionMode | str = AlgorithmExecutionMode.STREAM,
        write_property: str | None = "community",
        mutate_property: str | None = "community",
    ) -> PartitionResult | dict[str, Any]:
        """Execute Louvain Community Detection via Neo4j GDS."""
        return gds_louvain(
            client=self.client,
            graph=graph,
            resolution=resolution,
            seed=seed,
            weight_property=weight_property,
            mode=mode,
            write_property=write_property,
            mutate_property=mutate_property,
            default_graph_name=self.default_graph_name,
        )
