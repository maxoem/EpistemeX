"""Graph algorithms for connected component analysis and partitioning.

Provides disjoint-set (Union-Find) connected components with near-linear time
complexity using path compression.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence


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
