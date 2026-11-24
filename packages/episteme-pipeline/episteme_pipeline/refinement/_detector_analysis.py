"""Structural graph, metric, and cluster indexing helpers for deficit detection.

Computes single-source schema partitions, Schurz-Lakatos :math:`Z_1` grounding,
PageRank and betweenness centralities, Louvain communities, chunk adjacency,
and cluster/enrichment indices shared by the modular deficit sub-detectors.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

import networkx as nx
from epistemetrics import (
    AlgorithmError,
    betweenness_centrality,
    louvain_communities,
    page_rank,
)

from episteme_pipeline.artifacts.execution import EpistemicStateView
from episteme_pipeline.artifacts.models import TheoreticalEnrichmentArtifact
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils.graph_algorithms import compute_z1_grounding
from episteme_pipeline.utils.identifiers import dedup_preserve_order

METADATA_PARAM_KEYS: frozenset[str] = frozenset(
    {"required_dimensions", "theory_id", "perspective", "domain"}
)


def dedup_relations(relations: Iterable[TheoryRelation]) -> list[TheoryRelation]:
    """Deduplicate ``TheoryRelation`` instances deterministically by ``relation_id``.

    Parameters
    ----------
    relations : Iterable of TheoryRelation
        Input sequence of relations.

    Returns
    -------
    list of TheoryRelation
        Deduplicated relations sorted by canonical ``relation_id``.
    """
    by_id: dict[str, TheoryRelation] = {}
    for rel in relations:
        by_id.setdefault(rel.relation_id, rel)
    return [by_id[k] for k in sorted(by_id)]


def enrichment_edge_key(rel: TheoryRelation) -> str:
    """Build the canonical lookup key used by ``TheoreticalEnrichmentArtifact`` maps.

    Parameters
    ----------
    rel : TheoryRelation
        Target theory relation edge.

    Returns
    -------
    str
        Pairwise ``source->type->target`` key when pairwise, else ``relation_id``.
    """
    if (
        rel.has_conjunctive_premises
        or rel.undercuts_relation_id is not None
        or rel.id is not None
    ):
        return rel.relation_id
    return f"{rel.source_id}->{rel.relation_type}->{rel.target_id}"


def lookup_edge_tenability(
    rel: TheoryRelation,
    edge_tenability_map: dict[str, float],
) -> float | None:
    """Resolve ``TS_edge`` from the relation itself or enrichment edge tenability maps.

    Parameters
    ----------
    rel : TheoryRelation
        Target theory relation.
    edge_tenability_map : dict of str to float
        Aggregated ``edge_tenabilities`` across enrichment artifacts.

    Returns
    -------
    float or None
        Resolved ``TS_edge`` score if recorded, otherwise ``None``.
    """
    if rel.edge_tenability is not None:
        return float(rel.edge_tenability)
    for key in (
        rel.relation_id,
        enrichment_edge_key(rel),
        f"{rel.source_id}->{rel.relation_type}->{rel.target_id}",
    ):
        if key in edge_tenability_map:
            return float(edge_tenability_map[key])
    return None


def build_chunk_neighbors(chunks: Sequence[L1Chunk]) -> dict[str, list[str]]:
    """Map each chunk ID to immediately adjacent chunks within the same document.

    Parameters
    ----------
    chunks : Sequence of L1Chunk
        Document chunks available in state.

    Returns
    -------
    dict of str to list of str
        Adjacency table sorted per chunk.
    """
    by_doc: dict[str, list[L1Chunk]] = {}
    for chunk in chunks:
        by_doc.setdefault(chunk.source_doc_id, []).append(chunk)

    neighbors: dict[str, list[str]] = {}
    for doc_chunks in by_doc.values():
        ordered = sorted(doc_chunks, key=lambda c: (c.sequence_index, c.id))
        for idx, chunk in enumerate(ordered):
            adj: list[str] = []
            if idx > 0:
                adj.append(ordered[idx - 1].id)
            if idx + 1 < len(ordered):
                adj.append(ordered[idx + 1].id)
            neighbors[chunk.id] = adj
    return neighbors


def collect_target_chunks(
    seed_chunks: Iterable[str],
    chunk_neighbors: dict[str, list[str]],
) -> list[str]:
    """Expand seed chunk IDs with immediate 1-hop intra-document neighbor chunks.

    Parameters
    ----------
    seed_chunks : Iterable of str
        Core target chunk identifiers.
    chunk_neighbors : dict of str to list of str
        Neighbor map from :func:`build_chunk_neighbors`.

    Returns
    -------
    list of str
        Deduplicated target chunk IDs preserving seed order before neighbors.
    """
    seeds = dedup_preserve_order(seed_chunks)
    expanded = list(seeds)
    for cid in seeds:
        for nbr in chunk_neighbors.get(cid, ()):
            expanded.append(nbr)  # noqa: PERF402 baseline
    return dedup_preserve_order(expanded)


def extract_required_dimensions(
    atom: TheoryAtom | None = None,
    enrichment: TheoreticalEnrichmentArtifact | None = None,
) -> list[str]:
    """Extract declared :math:`M_{pp}` required empirical dimension names, if any.

    Parameters
    ----------
    atom : TheoryAtom or None, optional
        Optional theory atom carrying parameter metadata.
    enrichment : TheoreticalEnrichmentArtifact or None, optional
        Optional enrichment artifact carrying projected parameter metadata.

    Returns
    -------
    list of str
        Deduplicated required empirical measurement dimensions.
    """
    dims: list[str] = []
    sources: list[dict[str, Any]] = []
    if enrichment is not None:
        sources.append(enrichment.projected_parameters)
    if atom is not None:
        sources.append(atom.parameters)
    for src in sources:
        raw = src.get("required_dimensions")
        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    dims.append(item.strip())
    return dedup_preserve_order(dims)


def build_theory_nx_graph(
    atoms: Sequence[TheoryAtom],
    relations: Sequence[TheoryRelation],
) -> nx.DiGraph:
    """Construct a weighted NetworkX ``DiGraph`` over TheoryNet atoms.

    Parameters
    ----------
    atoms : Sequence of TheoryAtom
        Canonical or active theory atoms.
    relations : Sequence of TheoryRelation
        Canonical or active theory relations.

    Returns
    -------
    nx.DiGraph
        Directed TheoryNet graph with strictly positive edge weights.
    """
    graph = nx.DiGraph()
    atom_ids: set[str] = set()
    for atom in sorted(atoms, key=lambda a: a.id):
        atom_ids.add(atom.id)
        graph.add_node(atom.id, component_type=atom.component_type)

    for rel in relations:
        if not rel.is_admissible or rel.undercuts_relation_id is not None:
            continue
        if rel.target_id not in atom_ids:
            continue
        raw_weight = (
            abs(float(rel.active_weight))
            if rel.active_weight > 0.0
            else float(rel.confidence or 1.0)
        )
        edge_weight = max(1e-6, raw_weight)
        for p_id in rel.effective_premise_ids:
            if p_id in atom_ids and p_id != rel.target_id:
                existing = graph.get_edge_data(p_id, rel.target_id)
                best_weight = (
                    max(edge_weight, float(existing["weight"]))
                    if existing is not None
                    else edge_weight
                )
                graph.add_edge(p_id, rel.target_id, weight=best_weight)
    return graph


def compute_centralities(
    graph: nx.DiGraph,
) -> tuple[dict[str, float], dict[str, float]]:
    """Compute PageRank and Betweenness centralities via ``epistemetrics``.

    Parameters
    ----------
    graph : nx.DiGraph
        Directed TheoryNet graph.

    Returns
    -------
    tuple of (dict of str to float, dict of str to float)
        ``(pagerank_scores, betweenness_scores)`` indexed by atom ID.
    """
    if len(graph) == 0:
        return {}, {}

    btw_scores: dict[str, float]
    try:
        btw_res = betweenness_centrality(graph, prefer_neo4j=False)
        btw_scores = dict(btw_res.scores)
    except AlgorithmError:
        btw_scores = {str(nid): 0.0 for nid in graph.nodes}

    try:
        pr_res = page_rank(
            graph,
            prefer_neo4j=False,
            weight_property="weight" if graph.number_of_edges() > 0 else None,
        )
        pr_scores = dict(pr_res.scores)
    except AlgorithmError:
        if any(v > 0.0 for v in btw_scores.values()):
            pr_scores = dict(btw_scores)
        else:
            uniform = 1.0 / float(len(graph))
            pr_scores = {str(nid): uniform for nid in graph.nodes}

    return pr_scores, btw_scores


def compute_louvain_communities(graph: nx.DiGraph) -> dict[str, int]:
    """Partition TheoryNet nodes into modular communities via ``epistemetrics``.

    Parameters
    ----------
    graph : nx.DiGraph
        Directed TheoryNet graph.

    Returns
    -------
    dict of str to int
        Mapping from atom ID to integer community identifier.
    """
    if len(graph) == 0 or graph.number_of_edges() == 0:
        return {str(nid): idx for idx, nid in enumerate(sorted(graph.nodes))}
    try:
        comm_res = louvain_communities(
            graph, prefer_neo4j=False, seed=42, weight_property="weight"
        )
        return {str(k): int(v) for k, v in comm_res.node_to_partition.items()}
    except AlgorithmError:
        return {str(nid): idx for idx, nid in enumerate(sorted(graph.nodes))}


@dataclass(frozen=True, slots=True)
class DetectorStateAnalysis:
    """Precomputed structural, cluster, and empirical indices for one detection pass.

    Attributes
    ----------
    atoms : tuple of TheoryAtom
        Active or canonicalized theory atoms.
    relations : tuple of TheoryRelation
        Active or canonicalized theory relations.
    atoms_by_id : dict of str to TheoryAtom
        Atom lookup map.
    entities_by_id : dict of str to L2Entity
        Entity lookup map.
    a_atoms : frozenset of str
        Theoretical (partition ``"A"``) atom IDs.
    b_atoms : frozenset of str
        Empirical (partition ``"B"``) atom IDs.
    in_support_degree : dict of str to int
        Count of incoming positive-polarity support hyperedges per A-atom.
    incident_degree : dict of str to int
        Total incoming + outgoing relation count per atom ID.
    z1_grounded : frozenset of str
        Theoretical atoms reachable from partition ``"B"`` over admissible
        non-negative paths.
    pr_scores : dict of str to float
        PageRank scores indexed by atom ID.
    btw_scores : dict of str to float
        Betweenness scores indexed by atom ID.
    atom_to_community : dict of str to int
        Louvain community assignments per atom ID.
    atom_to_enrichments : dict of str to list of TheoreticalEnrichmentArtifact
        Associated enrichment records indexed by atom ID.
    edge_tenability_map : dict of str to float
        Aggregated ``TS_edge`` scores indexed by edge key.
    equilibrium_map : dict of str to float
        Enrichment-reported equilibrium strengths per atom ID.
    cluster_b_counts : dict of str to int
        Count of partition-B atoms per chunk/cluster key.
    cluster_dimensions : dict of str to set of str
        Observed measurement dimensions (lowercase) per chunk/cluster key.
    chunk_neighbors : dict of str to list of str
        Immediate previous/next chunks within the same document.
    """

    atoms: tuple[TheoryAtom, ...]
    relations: tuple[TheoryRelation, ...]
    atoms_by_id: dict[str, TheoryAtom]
    entities_by_id: dict[str, L2Entity]
    a_atoms: frozenset[str]
    b_atoms: frozenset[str]
    in_support_degree: dict[str, int]
    incident_degree: dict[str, int]
    z1_grounded: frozenset[str]
    pr_scores: dict[str, float]
    btw_scores: dict[str, float]
    atom_to_community: dict[str, int]
    atom_to_enrichments: dict[str, list[TheoreticalEnrichmentArtifact]]
    edge_tenability_map: dict[str, float]
    equilibrium_map: dict[str, float]
    cluster_b_counts: dict[str, int]
    cluster_dimensions: dict[str, set[str]]
    chunk_neighbors: dict[str, list[str]]


def analyze_detector_state(
    state: EpistemicStateView,
    schema: SchemaConfig,
) -> DetectorStateAnalysis:
    """Compute all graph, enrichment, and partition metrics over ``state``.

    Parameters
    ----------
    state : EpistemicStateView
        Cumulative pipeline state at detection time.
    schema : SchemaConfig
        Single source of truth for component partitions and relation polarities.

    Returns
    -------
    DetectorStateAnalysis
        Indexed state snapshot consumed by each deficit sub-detector.
    """
    atoms = tuple(state.canonical_theory_atoms or state.theory_atoms)
    relations = tuple(state.canonical_theory_relations or state.theory_relations)
    atoms_by_id = {atom.id: atom for atom in atoms}
    entities_by_id = {ent.id: ent for ent in state.entities}

    z1_res = compute_z1_grounding(atoms, relations, schema)
    nx_graph = build_theory_nx_graph(atoms, relations)
    pr_scores, btw_scores = compute_centralities(nx_graph)
    atom_to_community = compute_louvain_communities(nx_graph)
    chunk_neighbors = build_chunk_neighbors(state.chunks)

    incident_degree: dict[str, int] = {aid: 0 for aid in atoms_by_id}
    for rel in relations:
        for pid in rel.effective_premise_ids:
            if pid in incident_degree and pid != rel.target_id:
                incident_degree[pid] += 1
        if rel.target_id in incident_degree:
            incident_degree[rel.target_id] += 1

    atom_to_enrichments: dict[str, list[TheoreticalEnrichmentArtifact]] = {}
    edge_tenability_map: dict[str, float] = {}
    equilibrium_map: dict[str, float] = {}
    cluster_b_counts: dict[str, int] = {}
    cluster_dimensions: dict[str, set[str]] = {}

    for atom in atoms:
        chunk_cluster = f"cluster-{atom.source_chunk_id}"
        if atom.id in z1_res.b_atom_ids:
            cluster_b_counts[atom.source_chunk_id] = (
                cluster_b_counts.get(atom.source_chunk_id, 0) + 1
            )
            cluster_b_counts[chunk_cluster] = cluster_b_counts.get(chunk_cluster, 0) + 1
        dims = cluster_dimensions.setdefault(atom.source_chunk_id, set())
        cdims = cluster_dimensions.setdefault(chunk_cluster, set())
        for meas in atom.measurements:
            d_low = meas.dimension.strip().lower()
            if d_low:
                dims.add(d_low)
                cdims.add(d_low)

    enr_by_cluster: dict[str, list[TheoreticalEnrichmentArtifact]] = {}
    for enr in state.theoretical_enrichments:
        edge_tenability_map.update(enr.edge_tenabilities)
        equilibrium_map.update(enr.equilibrium_strengths)
        enr_by_cluster.setdefault(enr.cluster_id, []).append(enr)
        for aid in enr.claimant_atom_ids:
            atom_to_enrichments.setdefault(aid, []).append(enr)

    for atom in atoms:
        if atom.id not in atom_to_enrichments:
            chunk_enrs = enr_by_cluster.get(f"cluster-{atom.source_chunk_id}", [])
            if chunk_enrs:
                atom_to_enrichments[atom.id] = list(chunk_enrs)

    return DetectorStateAnalysis(
        atoms=atoms,
        relations=relations,
        atoms_by_id=atoms_by_id,
        entities_by_id=entities_by_id,
        a_atoms=z1_res.a_atom_ids,
        b_atoms=z1_res.b_atom_ids,
        in_support_degree=z1_res.in_support_degree,
        incident_degree=incident_degree,
        z1_grounded=z1_res.z1_grounded_ids,
        pr_scores=pr_scores,
        btw_scores=btw_scores,
        atom_to_community=atom_to_community,
        atom_to_enrichments=atom_to_enrichments,
        edge_tenability_map=edge_tenability_map,
        equilibrium_map=equilibrium_map,
        cluster_b_counts=cluster_b_counts,
        cluster_dimensions=cluster_dimensions,
        chunk_neighbors=chunk_neighbors,
    )
