"""Community modularity, signed modularity, and participation coefficient metrics.

Implements:
- Additive per-community modularity contributions :math:`q_c` satisfying
  :math:`Q_{\\text{mod}} = \\sum_c q_c`.
- Traag & Bruggeman (2009) signed modularity :math:`Q_{\\text{signed}}` over
  positive (support) and negative (attack) links.
- Guimerà & Amaral (2005) cross-community participation coefficient
  :math:`P_i = 1 - \\sum_c (k_{i,c} / k_i)^2` as a diversity-sensitive proxy
  for explanatory unification.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

import networkx as nx

from epistemetrics.core.models import PartitionResult
from epistemetrics.graph.algorithms.common import extract_nx_graph


def _to_undirected_weighted(
    graph: Any,
    weight_property: str | None = "weight",
) -> nx.Graph:
    """Collapse a directed or multigraph into an undirected weighted simple graph."""
    g = extract_nx_graph(graph)
    u_graph = nx.Graph()
    for node, data in g.nodes(data=True):
        u_graph.add_node(str(node), **data)

    for u, v, data in g.edges(data=True):
        su, sv = str(u), str(v)
        w = float(data.get(weight_property, 1.0)) if weight_property else 1.0
        if u_graph.has_edge(su, sv):
            u_graph[su][sv]["weight"] += w
        else:
            u_graph.add_edge(su, sv, weight=w)
    return u_graph


def per_community_modularity(
    graph: Any,
    communities: Sequence[set[str]] | PartitionResult,
    *,
    resolution: float = 1.0,
    weight_property: str | None = "weight",
) -> tuple[float, dict[int, float]]:
    """Compute global modularity and additive per-community contributions.

    .. math::

        q_c = \\frac{e_c}{m} - \\gamma_{\\text{res}} \\left(\\frac{K_c}{2m}\\right)^2, \\qquad
        Q_{\\text{mod}} = \\sum_{c} q_c

    where :math:`e_c` is total internal edge weight inside community :math:`c`,
    :math:`K_c` is the sum of weighted degrees of nodes in :math:`c`, and
    :math:`m` is total graph edge weight.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.
    communities : Sequence of set of str or PartitionResult
        Disjoint community partition covering the graph nodes.
    resolution : float, default 1.0
        Modularity resolution parameter :math:`\\gamma_{\\text{res}}`.
    weight_property : str or None, default "weight"
        Edge weight attribute name, or None for unit weights.

    Returns
    -------
    tuple of (float, dict of int to float)
        Global modularity ``Q_mod`` and mapping ``community_idx -> q_c``.
    """
    parts = (
        communities.partitions
        if isinstance(communities, PartitionResult)
        else list(communities)
    )
    u_graph = _to_undirected_weighted(graph, weight_property=weight_property)
    two_m = sum(
        (2.0 if u == v else 2.0) * float(data["weight"])
        for u, v, data in u_graph.edges(data=True)
        if float(data["weight"]) > 0.0
    )
    if two_m <= 0.0:
        return 0.0, {idx: 0.0 for idx in range(len(parts))}

    degrees: dict[str, float] = {
        n: sum(
            float(d["weight"]) * (2.0 if nbr == n else 1.0)
            for nbr, d in u_graph[n].items()
            if float(d["weight"]) > 0.0
        )
        for n in u_graph.nodes()
    }

    contributions: dict[int, float] = {}
    for idx, comm in enumerate(parts):
        comm_nodes = {str(n) for n in comm if str(n) in u_graph}
        internal_two_e = 0.0
        for u in comm_nodes:
            for v, data in u_graph[u].items():
                w = float(data["weight"])
                if w > 0.0 and v in comm_nodes:
                    internal_two_e += w * (2.0 if u == v else 1.0)
        k_c = sum(degrees[n] for n in comm_nodes)
        q_c = (internal_two_e / two_m) - resolution * ((k_c / two_m) ** 2)
        contributions[idx] = float(q_c)

    return float(sum(contributions.values())), contributions


def signed_modularity(
    graph: Any,
    communities: Sequence[set[str]] | PartitionResult,
    *,
    resolution: float = 1.0,
    weight_property: str | None = "weight",
) -> tuple[float, dict[int, float]]:
    """Compute Traag & Bruggeman (2009) signed modularity and per-community terms.

    Separates positive (support) edges :math:`w_{ij}^+ = \\max(w_{ij}, 0)` and
    negative (attack) edges :math:`w_{ij}^- = \\max(-w_{ij}, 0)` so placing
    adversarial opponents in the same community is penalized:

    .. math::

        Q_{\\text{signed}} = \\frac{2m^+}{2m^+ + 2m^-} Q^+(C) - \\frac{2m^-}{2m^+ + 2m^-} Q^-(C)

    Parameters
    ----------
    graph : Any
        Signed NetworkX graph or TheoryGraph.
    communities : Sequence of set of str or PartitionResult
        Disjoint community partition.
    resolution : float, default 1.0
        Resolution parameter :math:`\\gamma_{\\text{res}}`.
    weight_property : str or None, default "weight"
        Signed edge weight attribute name.

    Returns
    -------
    tuple of (float, dict of int to float)
        Global signed modularity ``Q_signed`` and per-community contributions.
    """
    parts = (
        communities.partitions
        if isinstance(communities, PartitionResult)
        else list(communities)
    )
    g = extract_nx_graph(graph)
    pos_g = nx.Graph()
    neg_g = nx.Graph()
    for n in g.nodes():
        sn = str(n)
        pos_g.add_node(sn)
        neg_g.add_node(sn)

    for u, v, data in g.edges(data=True):
        su, sv = str(u), str(v)
        raw_w = float(data.get(weight_property, 1.0)) if weight_property else 1.0
        pol = data.get("polarity")
        if pol is not None and raw_w >= 0.0:
            raw_w = raw_w * (1.0 if int(pol) > 0 else (-1.0 if int(pol) < 0 else 0.0))
        if raw_w > 0.0:
            if pos_g.has_edge(su, sv):
                pos_g[su][sv]["weight"] += raw_w
            else:
                pos_g.add_edge(su, sv, weight=raw_w)
        elif raw_w < 0.0:
            mag = -raw_w
            if neg_g.has_edge(su, sv):
                neg_g[su][sv]["weight"] += mag
            else:
                neg_g.add_edge(su, sv, weight=mag)

    two_m_pos = 2.0 * sum(float(d["weight"]) for _, _, d in pos_g.edges(data=True))
    two_m_neg = 2.0 * sum(float(d["weight"]) for _, _, d in neg_g.edges(data=True))
    denom = two_m_pos + two_m_neg
    if denom <= 0.0:
        return 0.0, {idx: 0.0 for idx in range(len(parts))}

    _, q_pos_map = per_community_modularity(
        pos_g, parts, resolution=resolution, weight_property="weight"
    )
    _, q_neg_map = per_community_modularity(
        neg_g, parts, resolution=resolution, weight_property="weight"
    )

    signed_map: dict[int, float] = {}
    for idx in range(len(parts)):
        q_s = (two_m_pos / denom) * q_pos_map.get(idx, 0.0) - (
            two_m_neg / denom
        ) * q_neg_map.get(idx, 0.0)
        signed_map[idx] = float(q_s)

    return float(sum(signed_map.values())), signed_map


def participation_coefficient(
    graph: Any,
    partition: Mapping[str, int] | PartitionResult,
    *,
    direction: str = "out",
    weight_property: str | None = None,
) -> dict[str, float]:
    """Compute Guimerà & Amaral (2005) cross-community participation coefficient.

    .. math::

        P_i = 1 - \\sum_{c} \\left(\\frac{k_{i,c}}{k_i}\\right)^2 \\in [0, 1)

    Measures how evenly a node's connections (e.g. outgoing support links in
    Layer 3) span distinct communities, serving as a diversity-sensitive proxy
    for explanatory unification.

    Parameters
    ----------
    graph : Any
        Target NetworkX graph or domain TheoryGraph.
    partition : Mapping of str to int or PartitionResult
        Mapping from node ID to community index.
    direction : {"out", "in", "both"}, default "out"
        Edge incidence direction on directed graphs (ignored on undirected graphs).
    weight_property : str or None, optional
        Optional edge weight attribute name.

    Returns
    -------
    dict of str to float
        Participation coefficient :math:`P_i \\in [0, 1)` per node (``0.0`` for
        zero-degree nodes or nodes connected solely within a single community).
    """
    node_to_comm = (
        partition.node_to_partition
        if isinstance(partition, PartitionResult)
        else {str(k): int(v) for k, v in partition.items()}
    )
    g = extract_nx_graph(graph)
    scores: dict[str, float] = {}

    for node in g.nodes():
        nid = str(node)
        comm_weights: dict[int, float] = defaultdict(float)

        if g.is_directed():
            edge_iter = []
            if direction in ("out", "both"):
                edge_iter.extend((v, d) for _, v, d in g.out_edges(node, data=True))
            if direction in ("in", "both"):
                edge_iter.extend((u, d) for u, _, d in g.in_edges(node, data=True))
        else:
            edge_iter = [(v, d) for _, v, d in g.edges(node, data=True)]

        total_w = 0.0
        for nbr, data in edge_iter:
            nbr_id = str(nbr)
            if nbr_id not in node_to_comm:
                continue
            w = float(data.get(weight_property, 1.0)) if weight_property else 1.0
            if w <= 0.0:
                continue
            comm_weights[node_to_comm[nbr_id]] += w
            total_w += w

        if total_w <= 0.0:
            scores[nid] = 0.0
        else:
            sum_sq = sum((w_c / total_w) ** 2 for w_c in comm_weights.values())
            scores[nid] = float(max(0.0, 1.0 - sum_sq))

    return scores
