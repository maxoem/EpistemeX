"""
Graph algorithms subsystem for epistemetrics.

Provides isolated algorithm implementations for PageRank, Betweenness Centrality,
Eigenvector Centrality, Weakly Connected Components (WCC), and Louvain Community Detection
alongside engine coordination classes.
"""

from __future__ import annotations

from epistemetrics.graph.algorithms.adaptive_engine import AdaptiveAlgorithmsEngine
from epistemetrics.graph.algorithms.betweenness import (
    betweenness_centrality,
    gds_betweenness,
    networkx_betweenness,
)
from epistemetrics.graph.algorithms.community_metrics import (
    participation_coefficient,
    per_community_modularity,
    signed_modularity,
)
from epistemetrics.graph.algorithms.eigenvector import (
    eigenvector_centrality,
    gds_eigenvector,
    networkx_eigenvector,
)
from epistemetrics.graph.algorithms.katz import (
    katz_centrality,
    networkx_katz,
)
from epistemetrics.graph.algorithms.louvain import (
    gds_louvain,
    louvain_communities,
    networkx_louvain,
)
from epistemetrics.graph.algorithms.networkx_engine import NetworkXAlgorithmsEngine
from epistemetrics.graph.algorithms.pagerank import (
    gds_pagerank,
    networkx_pagerank,
    page_rank,
)
from epistemetrics.graph.algorithms.protocol import GraphAlgorithmsEngine
from epistemetrics.graph.algorithms.wcc import (
    gds_wcc,
    networkx_wcc,
    weakly_connected_components,
)

__all__ = [
    "AdaptiveAlgorithmsEngine",
    "GraphAlgorithmsEngine",
    "NetworkXAlgorithmsEngine",
    "betweenness_centrality",
    "eigenvector_centrality",
    "gds_betweenness",
    "gds_eigenvector",
    "gds_louvain",
    "gds_pagerank",
    "gds_wcc",
    "katz_centrality",
    "louvain_communities",
    "networkx_betweenness",
    "networkx_eigenvector",
    "networkx_katz",
    "networkx_louvain",
    "networkx_pagerank",
    "networkx_wcc",
    "page_rank",
    "participation_coefficient",
    "per_community_modularity",
    "signed_modularity",
    "weakly_connected_components",
]
