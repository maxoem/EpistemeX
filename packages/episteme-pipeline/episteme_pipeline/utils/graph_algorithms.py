"""Graph algorithms for connected component analysis and partitioning.

Provides disjoint-set (Union-Find) connected components with near-linear time
complexity using path compression.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation
    from episteme_pipeline.schema.default_schema import SchemaConfig


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

    References
    ----------
    .. [1] Bansal, N., Blum, A., & Chawla, S. (2004). Correlation clustering.
       Machine Learning, 56(1), 89-113.
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
        key=lambda e: (float(sim[e[0], e[1]]), -min(e[0], e[1]), -max(e[0], e[1])),
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

    return sorted([sorted(members) for members in cluster_members.values()], key=lambda c: c[0])


@dataclass(frozen=True, slots=True)
class Z1GroundingResult:
    """Result of Schurz-Lakatos :math:`Z_1` empirical-base reachability analysis.

    Attributes
    ----------
    a_atom_ids : frozenset of str
        Theoretical (partition ``"A"``) atom identifiers.
    b_atom_ids : frozenset of str
        Empirical/observational (partition ``"B"``) atom identifiers.
    z1_grounded_ids : frozenset of str
        Theoretical atom identifiers reachable from partition ``"B"`` via
        eligible derivation or corroboration links.
    in_support_degree : dict of (str, int)
        Count of distinct incoming positive-polarity support hyperedges for
        each theoretical atom.
    empirical_content_ratio : float
        Fraction ``|z1_grounded_ids| / |a_atom_ids|`` (``0.0`` when empty).
    """

    a_atom_ids: frozenset[str]
    b_atom_ids: frozenset[str]
    z1_grounded_ids: frozenset[str]
    in_support_degree: dict[str, int]
    empirical_content_ratio: float


def compute_z1_grounding(
    atoms: Sequence[TheoryAtom],
    relations: Sequence[TheoryRelation],
    schema: SchemaConfig,
    *,
    require_admissible: bool = True,
    non_negative_only: bool = True,
) -> Z1GroundingResult:
    """Compute theoretical-to-empirical :math:`Z_1` reachability and support degrees.

    Implements Schurz (1991) / Lakatos (1970) empirical content grounding by
    partitioning atoms via ``schema.resolve_component_partition`` into
    theoretical (``A``) and empirical (``B``) sets and running multi-source BFS
    from ``A`` atoms directly coupled to ``B`` atoms through ``A-A`` links.

    Parameters
    ----------
    atoms : Sequence of TheoryAtom
        Active theory atoms in the graph or subnetwork.
    relations : Sequence of TheoryRelation
        Active theory hyperedges connecting atoms.
    schema : SchemaConfig
        Single source of truth for component partitions and relation polarities.
    require_admissible : bool, default True
        When True, ignores inadmissible, zero-weight, or undercut relations.
    non_negative_only : bool, default True
        When True, excludes negative-polarity attack relations from :math:`Z_1`
        grounding paths.

    Returns
    -------
    Z1GroundingResult
        Frozen summary of ``A``/``B`` partitions, grounded ``A`` atoms, incoming
        support counts, and empirical content ratio.
    """
    a_atoms: set[str] = set()
    b_atoms: set[str] = set()
    for atom in atoms:
        part = schema.resolve_component_partition(atom.component_type)
        if part == "A":
            a_atoms.add(atom.id)
        elif part == "B":
            b_atoms.add(atom.id)

    in_support_degree: dict[str, int] = {aid: 0 for aid in a_atoms}
    adj: dict[str, set[str]] = {aid: set() for aid in a_atoms}
    z1_seeds: set[str] = set()

    for rel in relations:
        if require_admissible and (
            not rel.is_admissible
            or rel.active_weight <= 0.0
            or rel.undercuts_relation_id is not None
        ):
            continue

        pol = schema.resolve_edge_polarity(
            rel.relation_type,
            weight_support=rel.weight_support,
            weight_attack=rel.weight_attack,
            weight=rel.weight,
        )
        premises = rel.effective_premise_ids

        if pol > 0 and rel.target_id in in_support_degree:
            if any(pid != rel.target_id for pid in premises):
                in_support_degree[rel.target_id] += 1

        if non_negative_only and pol < 0:
            continue

        for p_id in premises:
            if p_id in a_atoms and rel.target_id in b_atoms:
                z1_seeds.add(p_id)
            elif rel.target_id in a_atoms and p_id in b_atoms:
                z1_seeds.add(rel.target_id)
            elif p_id in a_atoms and rel.target_id in a_atoms and p_id != rel.target_id:
                adj[p_id].add(rel.target_id)
                adj[rel.target_id].add(p_id)

    z1_grounded = set(z1_seeds)
    queue: deque[str] = deque(sorted(z1_seeds))
    while queue:
        curr = queue.popleft()
        for neighbor in sorted(adj.get(curr, ())):
            if neighbor not in z1_grounded:
                z1_grounded.add(neighbor)
                queue.append(neighbor)

    empirical_content = len(z1_grounded) / len(a_atoms) if a_atoms else 0.0
    return Z1GroundingResult(
        a_atom_ids=frozenset(a_atoms),
        b_atom_ids=frozenset(b_atoms),
        z1_grounded_ids=frozenset(z1_grounded),
        in_support_degree=in_support_degree,
        empirical_content_ratio=empirical_content,
    )


