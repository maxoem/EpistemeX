"""Graph algorithms for connected component analysis and partitioning.

Provides disjoint-set (Union-Find) connected components with near-linear time
complexity using path compression.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import numpy as np


def union_find_components(n: int, edges: Sequence[tuple[int, int]]) -> list[list[int]]:
    """Compute connected components of a graph using path-compressed Union-Find.

    Parameters
    ----------
    n : int
        The number of nodes in the graph (indexed from 0 to n-1).
    edges : Sequence of tuple of (int, int)
        A sequence of undirected edges represented as pairs of node indices.

    Returns
    -------
    list of list of int
        A list of connected components, where each sublist contains the node indices
        belonging to the same connected component.

    Notes
    -----
    Uses path compression to achieve nearly linear amortized time complexity
    :math:`O(V + E \\cdot \\alpha(V))`.
    """
    if n <= 0:
        return []

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        root_x = find(x)
        root_y = find(y)
        if root_x != root_y:
            parent[root_x] = root_y

    for u, v in edges:
        if 0 <= u < n and 0 <= v < n:
            union(u, v)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    return list(groups.values())


def clique_constrained_components(
    n: int,
    edges: Sequence[tuple[int, int]],
    similarity_matrix: Any,
    min_internal_similarity: float = 0.70,
    max_diameter: float | None = None,
) -> list[list[int]]:
    """Compute clique-constrained connected components with diameter and similarity floor guards.

    Prevents single-linkage chaining (transitive bridge collapsing :math:`A \\sim B \\sim C`
    where :math:`A \\not\\sim C`) by ensuring that a merge between two clusters is accepted
    if and only if every pairwise connection within the proposed merged cluster satisfies
    the minimum similarity floor :math:`\\tau_{\\text{floor}}` and maximum diameter constraint.

    Parameters
    ----------
    n : int
        Number of nodes in the graph (indexed from 0 to n-1).
    edges : Sequence of tuple of (int, int)
        Candidate merge edges representing pairwise agreement or threshold satisfaction.
    similarity_matrix : np.ndarray or list of list of float
        Pairwise similarity matrix of shape (n, n).
    min_internal_similarity : float, default 0.70
        Minimum pairwise similarity floor :math:`\\tau_{\\text{floor}}` required between
        any two members in a merged cluster.
    max_diameter : float or None, optional
        Optional maximum diameter bound :math:`\\max_{u, v} (1 - \\text{sim}(u, v)) \\le \\text{max\\_diameter}`.

    Returns
    -------
    list of list of int
        Partition of node indices into clique-constrained clusters.

    Notes
    -----
    Corresponds to complete-linkage / correlation clustering (Bansal et al., 2004).
    Candidate edges are evaluated greedily in descending order of similarity.
    """

    if n <= 0:
        return []
    if not edges:
        return [[i] for i in range(n)]

    sim = np.asarray(similarity_matrix, dtype=np.float32)

    node_to_cluster: list[int] = list(range(n))
    cluster_members: dict[int, set[int]] = {i: {i} for i in range(n)}

    valid_edges = [(u, v) for u, v in edges if 0 <= u < n and 0 <= v < n and u != v]
    sorted_edges = sorted(
        valid_edges,
        key=lambda e: float(sim[e[0], e[1]]),
        reverse=True,
    )

    for u, v in sorted_edges:
        c_u = node_to_cluster[u]
        c_v = node_to_cluster[v]
        if c_u == c_v:
            continue

        members_u = cluster_members[c_u]
        members_v = cluster_members[c_v]

        can_merge = True
        for x in members_u:
            for y in members_v:
                s = float(sim[x, y])
                if s < min_internal_similarity:
                    can_merge = False
                    break
                if max_diameter is not None and (1.0 - s) > max_diameter:
                    can_merge = False
                    break
            if not can_merge:
                break

        if can_merge:
            if len(members_u) < len(members_v):
                c_u, c_v = c_v, c_u
                members_u, members_v = members_v, members_u
            members_u.update(members_v)
            for m in members_v:
                node_to_cluster[m] = c_u
            del cluster_members[c_v]

    return [sorted(members) for members in cluster_members.values()]

