"""Epistemic analysis and reporting for scientific theory graphs.

Provides baseline topological summary statistics, epistemic distribution analysis,
and markdown serialization for scientific theory evaluations.
"""

from __future__ import annotations

from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from epistemetrics.graph.algorithms.pagerank import networkx_pagerank
from epistemetrics.graph.theory_graph import TheoryGraph


class EpistemicReport(BaseModel):
    """Analytical summary and epistemic assessment of a TheoryGraph.

    Parameters
    ----------
    num_nodes : int
        Total number of nodes in the theory graph.
    num_edges : int
        Total number of relations in the theory graph.
    density : float
        Graph connectivity density.
    is_dag : bool
        Whether the graph structure forms a directed acyclic graph.
    weakly_connected_components : int
        Number of weakly connected subgraphs.
    node_type_counts : dict[str, int]
        Distribution of nodes across ontological types.
    relation_type_counts : dict[str, int]
        Distribution of edges across relation types.
    epistemic_status_counts : dict[str, int]
        Distribution of nodes across Lakatosian epistemic statuses.
    top_central_nodes : list[tuple[str, float]]
        Top nodes ranked by PageRank centrality.
    metrics : dict[str, Any]
        Arbitrary extra metric outputs.
    """

    model_config = ConfigDict(frozen=True)

    num_nodes: int = Field(default=0, description="Total number of nodes in graph.")
    num_edges: int = Field(default=0, description="Total number of edges in graph.")
    density: float = Field(default=0.0, description="Graph edge density.")
    is_dag: bool = Field(
        default=False, description="Whether the graph forms a directed acyclic graph."
    )
    weakly_connected_components: int = Field(
        default=0, description="Count of weakly connected components."
    )
    node_type_counts: dict[str, int] = Field(
        default_factory=dict, description="Distribution of node types."
    )
    relation_type_counts: dict[str, int] = Field(
        default_factory=dict, description="Distribution of relation types."
    )
    epistemic_status_counts: dict[str, int] = Field(
        default_factory=dict, description="Distribution of epistemic statuses."
    )
    top_central_nodes: list[tuple[str, float]] = Field(
        default_factory=list, description="Top nodes by PageRank centrality."
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Additional custom or structural metrics."
    )

    def to_markdown(self) -> str:
        """Format the epistemic report as a readable GitHub-flavored Markdown document.

        Returns
        -------
        str
            Markdown representation of the epistemic analysis.
        """
        lines = [
            "# Epistemic Theory Graph Analysis Report",
            "",
            "## Graph Summary",
            f"- **Total Nodes:** {self.num_nodes}",
            f"- **Total Edges:** {self.num_edges}",
            f"- **Density:** {self.density:.4f}",
            f"- **Acyclic (DAG):** {'Yes' if self.is_dag else 'No'}",
            f"- **Weakly Connected Components:** {self.weakly_connected_components}",
            "",
            "## Epistemic Distribution",
            "### Node Classifications",
        ]
        for k, v in sorted(self.node_type_counts.items()):
            lines.append(f"- `{k}`: {v}")
        lines.append("")
        lines.append("### Epistemic Status (Lakatosian Stance)")
        for k, v in sorted(self.epistemic_status_counts.items()):
            lines.append(f"- `{k}`: {v}")
        lines.append("")
        lines.append("### Relational Classifications")
        for k, v in sorted(self.relation_type_counts.items()):
            lines.append(f"- `{k}`: {v}")
        if self.top_central_nodes:
            lines.append("")
            lines.append("## Centrality Rankings (PageRank)")
            for nid, score in self.top_central_nodes:
                lines.append(f"- `{nid}`: {score:.4f}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert the report to a dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary representation of the report.
        """
        return self.model_dump()


def analyze_theory_graph(tg: TheoryGraph) -> EpistemicReport:
    """Analyze a TheoryGraph and compute structural and epistemic summary metrics.

    Parameters
    ----------
    tg : TheoryGraph
        Domain theory graph to analyze.

    Returns
    -------
    EpistemicReport
        Comprehensive report containing structural and epistemic statistics.
    """
    g = tg.nx_graph
    n = tg.num_nodes
    m = tg.num_edges

    density = 0.0
    if n > 1:
        density = float(m) / (n * (n - 1))

    is_dag = False
    if n > 0:
        try:
            is_dag = nx.is_directed_acyclic_graph(g)
        except Exception:
            is_dag = False

    wcc_count = 0
    if n > 0:
        try:
            wcc_count = nx.number_weakly_connected_components(g)
        except Exception:
            wcc_count = 1

    node_type_counts: dict[str, int] = {}
    epistemic_status_counts: dict[str, int] = {}
    for node in tg.nodes.values():
        t_key = (
            node.node_type.value
            if hasattr(node.node_type, "value")
            else str(node.node_type)
        )
        node_type_counts[t_key] = node_type_counts.get(t_key, 0) + 1
        s_key = (
            node.epistemic_status.value
            if hasattr(node.epistemic_status, "value")
            else str(node.epistemic_status)
        )
        epistemic_status_counts[s_key] = epistemic_status_counts.get(s_key, 0) + 1

    rel_type_counts: dict[str, int] = {}
    for edge in tg.edges:
        r_key = (
            edge.relation_type.value
            if hasattr(edge.relation_type, "value")
            else str(edge.relation_type)
        )
        rel_type_counts[r_key] = rel_type_counts.get(r_key, 0) + 1

    top_nodes: list[tuple[str, float]] = []
    if n > 0:
        try:
            pr = networkx_pagerank(tg)
            top_nodes = pr.top_k(5)
        except Exception:
            top_nodes = []

    return EpistemicReport(
        num_nodes=n,
        num_edges=m,
        density=density,
        is_dag=is_dag,
        weakly_connected_components=wcc_count,
        node_type_counts=node_type_counts,
        relation_type_counts=rel_type_counts,
        epistemic_status_counts=epistemic_status_counts,
        top_central_nodes=top_nodes,
    )
