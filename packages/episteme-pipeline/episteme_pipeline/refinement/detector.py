"""Top-down epistemic deficit and anomaly detection over TheoryNet (ISSUE-053).

Implements :class:`TheoryNetDeficitDetector` satisfying the
:class:`~episteme_pipeline.protocols.refinement.EpistemicDeficitDetector` and
:class:`~episteme_pipeline.protocols.fingerprint.Fingerprintable` protocols.
Inspects materialized L1–L4 artifacts (D-QBAF equilibrium degrees ``tau*``,
controversy volatility ``V``, structuralist tenability ``TS_local`` /
``TS_edge``, empirical :math:`Z_1` grounding, and ``epistemetrics`` graph
centralities/communities) to emit prioritized :class:`EpistemicDeficit`
signals for bounded hermeneutic refinement.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

import networkx as nx
from epistemetrics import (
    betweenness_centrality,
    louvain_communities,
    page_rank,
)
from epistemetrics.core.exceptions import AlgorithmError

from episteme_pipeline.artifacts.models import TheoreticalEnrichmentArtifact
from episteme_pipeline.config import HermeneuticRefinementConfig
from episteme_pipeline.contracts.domain import (
    EpistemicDeficit,
    EpistemicDeficitKind,
    L1Chunk,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import EpistemicDeficitDetected
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

if TYPE_CHECKING:
    from episteme_pipeline.artifacts.execution import (
        ArtifactExecutionContext,
        EpistemicStateView,
    )

_AXIS_A_TOKENS = (
    "HYPOTHESIS",
    "EXPANSION",
    "AXIOM",
    "CLAIM",
    "THEOR",
    "CONJECTURE",
)
_AXIS_B_TOKENS = ("OBSERVATION", "EMPIRIC")
_METADATA_PARAM_KEYS = frozenset(
    {"required_dimensions", "theory_id", "anchor", "text_anchor"}
)


def _dedup_preserve_order(items: Iterable[str]) -> list[str]:
    """Return unique non-empty strings while preserving first-seen order.

    Parameters
    ----------
    items : Iterable of str
        Input sequence of identifiers.

    Returns
    -------
    list of str
        Deduplicated non-empty string identifiers.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _resolve_partition(atom: TheoryAtom, schema: SchemaConfig) -> str:
    """Resolve an atom's structuralist partition (``"A"`` theoretical vs ``"B"`` empirical).

    Parameters
    ----------
    atom : TheoryAtom
        Target L3 theory atom.
    schema : SchemaConfig
        Schema configuration mapping component types to ``"A"`` or ``"B"``.

    Returns
    -------
    str
        ``"A"`` for theoretical antecedents/hypotheses, ``"B"`` for empirical
        observations/statements, or ``""`` when unclassified.
    """
    direct = schema.component_partitions.get(atom.component_type)
    if direct in ("A", "B"):
        return direct
    upper = atom.component_type.upper()
    if any(tok in upper for tok in _AXIS_B_TOKENS):
        return "B"
    if any(tok in upper for tok in _AXIS_A_TOKENS):
        return "A"
    if atom.measurements:
        return "B"
    return ""


def _relation_polarity(rel: TheoryRelation, schema: SchemaConfig) -> int:
    """Resolve signed epistemic polarity (+1 support, -1 attack, 0 neutral).

    Parameters
    ----------
    rel : TheoryRelation
        Target dialectical or structural theory relation.
    schema : SchemaConfig
        Schema configuration providing relation polarity mappings.

    Returns
    -------
    int
        ``1`` for support/entailment, ``-1`` for attack/undercut/inhibit,
        or ``0`` for neutral structural links.
    """
    if rel.weight_support is not None and rel.weight_support > 0:
        return 1
    if rel.weight_attack is not None and rel.weight_attack > 0:
        return -1
    pol = schema.relation_polarities.get(
        rel.relation_type,
        schema.relation_polarities.get(rel.relation_type.upper(), 0),
    )
    if pol != 0:
        return pol
    if rel.weight is not None and rel.weight != 0:
        return 1 if rel.weight > 0 else -1
    return 0


def _triple_polarity(triple: L2Triple, schema: SchemaConfig) -> int:
    """Resolve signed polarity of an L2 entity triple via ``schema``.

    Parameters
    ----------
    triple : L2Triple
        L2 local or global relation triple.
    schema : SchemaConfig
        Schema configuration providing L2 relation polarities.

    Returns
    -------
    int
        ``1`` for supportive predicates, ``-1`` for refutative/contradictory
        predicates, or ``0`` for neutral structural predicates.
    """
    return schema.relation_polarities.get(
        triple.predicate,
        schema.relation_polarities.get(triple.predicate.upper(), 0),
    )


def _enrichment_edge_key(rel: TheoryRelation) -> str:
    """Build the canonical lookup key used by TheoreticalEnrichment edge maps.

    Parameters
    ----------
    rel : TheoryRelation
        Theory relation edge.

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


def _lookup_edge_tenability(
    rel: TheoryRelation,
    edge_tenability_map: dict[str, float],
) -> float | None:
    """Resolve ``TS_edge`` from the relation or enrichment edge map.

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
        _enrichment_edge_key(rel),
        f"{rel.source_id}->{rel.relation_type}->{rel.target_id}",
    ):
        if key in edge_tenability_map:
            return float(edge_tenability_map[key])
    return None


def _build_chunk_neighbors(chunks: Sequence[L1Chunk]) -> dict[str, list[str]]:
    """Map each chunk ID to immediately adjacent and linked chunk IDs.

    Parameters
    ----------
    chunks : Sequence of L1Chunk
        Hydrated L1 chunks present in the current epistemic state.

    Returns
    -------
    dict of str to list of str
        Mapping from chunk ID to ordered adjacent/linked chunk IDs.
    """
    by_doc: dict[str, list[L1Chunk]] = {}
    known_ids: set[str] = set()
    for chunk in chunks:
        known_ids.add(chunk.id)
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
            linked = chunk.metadata.get("linked_chunk_ids")
            if isinstance(linked, list):
                for lid in linked:
                    if isinstance(lid, str) and lid in known_ids and lid != chunk.id:
                        adj.append(lid)
            neighbors[chunk.id] = _dedup_preserve_order(adj)
    return neighbors


def _collect_target_chunks(
    base_chunk_ids: Iterable[str],
    chunk_neighbors: dict[str, list[str]],
) -> list[str]:
    """Expand seed chunk IDs with adjacent/linked chunks from ``chunk_neighbors``.

    Parameters
    ----------
    base_chunk_ids : Iterable of str
        Seed source chunk identifiers.
    chunk_neighbors : dict of str to list of str
        Adjacency index produced by :func:`_build_chunk_neighbors`.

    Returns
    -------
    list of str
        Deduplicated target chunk IDs preserving seed priority order.
    """
    seeds = _dedup_preserve_order(base_chunk_ids)
    expanded = list(seeds)
    for cid in seeds:
        expanded.extend(chunk_neighbors.get(cid, []))
    return _dedup_preserve_order(expanded)


def _build_theory_nx_graph(
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
        Directed TheoryNet graph with strictly positive edge weights suitable
        for ``epistemetrics`` centrality algorithms.
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


def _compute_centralities(
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


def _compute_louvain_communities(graph: nx.DiGraph) -> dict[str, int]:
    """Partition TheoryNet nodes into modular communities via ``epistemetrics``.

    Parameters
    ----------
    graph : nx.DiGraph
        Directed TheoryNet graph.

    Returns
    -------
    dict of str to int
        Deterministic mapping from atom ID to community index.
    """
    if len(graph) == 0:
        return {}
    try:
        partition = louvain_communities(graph, prefer_neo4j=False, seed=42)
        return dict(partition.node_to_partition)
    except AlgorithmError:
        return {str(nid): 0 for nid in graph.nodes}


def _compute_z1_and_support(
    atoms: Sequence[TheoryAtom],
    relations: Sequence[TheoryRelation],
    schema: SchemaConfig,
) -> tuple[dict[str, int], set[str], set[str], set[str]]:
    """Compute incoming support degrees and empirical :math:`Z_1` reachability.

    Parameters
    ----------
    atoms : Sequence of TheoryAtom
        Active theory atoms.
    relations : Sequence of TheoryRelation
        Active theory relations.
    schema : SchemaConfig
        Schema configuration specifying A/B partitions and relation polarities.

    Returns
    -------
    tuple
        ``(in_support_degree, z1_grounded, a_atom_ids, b_atom_ids)``.
    """
    a_atoms: set[str] = set()
    b_atoms: set[str] = set()
    for atom in atoms:
        part = _resolve_partition(atom, schema)
        if part == "A":
            a_atoms.add(atom.id)
        elif part == "B":
            b_atoms.add(atom.id)

    in_support_degree: dict[str, int] = {aid: 0 for aid in a_atoms}
    adj: dict[str, set[str]] = {aid: set() for aid in a_atoms}
    z1_seeds: set[str] = set()

    for rel in relations:
        if (
            not rel.is_admissible
            or rel.active_weight <= 0.0
            or rel.undercuts_relation_id is not None
        ):
            continue
        pol = _relation_polarity(rel, schema)
        premises = rel.effective_premise_ids

        if pol > 0 and rel.target_id in in_support_degree:
            if any(pid != rel.target_id for pid in premises):
                in_support_degree[rel.target_id] += 1

        if pol < 0:
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

    return in_support_degree, z1_grounded, a_atoms, b_atoms


def _extract_required_dimensions(
    atom: TheoryAtom | None = None,
    enrichment: TheoreticalEnrichmentArtifact | None = None,
) -> list[str]:
    """Extract declared ``M_pp`` required empirical dimension names, if any.

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
    return _dedup_preserve_order(dims)


class TheoryNetDeficitDetector:
    """Deterministic epistemic deficit detector over L1–L4 TheoryNet state.

    Detects three structural and semantic deficit classes defined by ISSUE-053:

    1. ``ENTHYMEME_GAP``: ``A``-partition claims with centrality meeting
       ``enthymeme_min_centrality`` that lack incoming positive support or a
       valid :math:`Z_1` grounding path from ``B``-partition observations.
    2. ``POLYSEMY_COLLISION``: ``L2Entity`` or ``TheoryAtom`` hubs bridging
       incompatible theory clusters, communities, conceptions, or conflicting
       support/attack edges with ``controversy_volatility >=
       polysemy_volatility_threshold`` or ``TS_edge <
       polysemy_edge_tenability_threshold``.
    3. ``UNGROUNDED_AXIOM``: ``A``-partition axioms or empirical clusters with
       ``TS_local < ungrounded_local_tenability_threshold``, failed tenability
       evaluation (``is_tenable == False``, local anomalies, missing ``M_pp``
       observation dimensions), or missing :math:`Z_1` reachability when no
       observation atoms exist in their cluster.

    Parameters
    ----------
    config : HermeneuticRefinementConfig or None, optional
        Default refinement thresholds and cycle caps.
    schema : SchemaConfig or None, optional
        Schema configuration specifying A/B partitions and relation polarities.
    detected_in_phase : str or None, optional
        Optional fixed phase tag recorded on emitted deficits and events. When
        ``None``, resolves to ``"theoretical_enrichment"`` if
        ``state.theoretical_enrichments`` is non-empty, else ``"phase6"``.

    References
    ----------
    .. [1] Pan, S., Luo, L., Wang, Y., Chen, C., Wang, J., & Wu, X. (2024).
       Unifying Large Language Models and Knowledge Graphs: A Roadmap. IEEE TKDE.
    .. [2] Schurz, G. (2014). Philosophy of Science: A Unified Approach.
       Routledge.
    """

    def __init__(
        self,
        config: HermeneuticRefinementConfig | None = None,
        schema: SchemaConfig | None = None,
        *,
        detected_in_phase: str | None = None,
    ) -> None:
        self.config: HermeneuticRefinementConfig = config or HermeneuticRefinementConfig()
        self.schema: SchemaConfig = schema or DEFAULT_SCHEMA
        self.detected_in_phase: str | None = detected_in_phase

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic configuration fingerprint for cache invalidation.

        Returns
        -------
        dict of str to Any
            JSON-serializable representation of detector thresholds and schema
            partition/polarity definitions.
        """
        return {
            "class": self.__class__.__name__,
            "config": self.config.model_dump(mode="json"),
            "schema_version": self.schema.version,
            "component_partitions": dict(sorted(self.schema.component_partitions.items())),
            "relation_polarities": dict(sorted(self.schema.relation_polarities.items())),
            "detected_in_phase": self.detected_in_phase,
        }

    def detect_deficits(
        self,
        state: EpistemicStateView,
        *,
        refinement_pass: int = 0,
        config: HermeneuticRefinementConfig | None = None,
        context: ArtifactExecutionContext | None = None,
    ) -> list[EpistemicDeficit]:
        """Inspect cumulative epistemic state and emit prioritized deficits.

        Parameters
        ----------
        state : EpistemicStateView
            Cumulative epistemic state view containing L1–L4 artifacts and
            optional theoretical enrichment records.
        refinement_pass : int, default 0
            Current refinement iteration stamped onto emitted deficits and
            events.
        config : HermeneuticRefinementConfig or None, optional
            Optional configuration overriding detector defaults.
        context : ArtifactExecutionContext or None, optional
            Optional execution context supplying ``run_id`` for event emission.

        Returns
        -------
        list of EpistemicDeficit
            Deduplicated deficits sorted by descending severity, capped at
            ``max_deficits_per_cycle``.
        """
        cfg = config or self.config
        atoms = (
            list(state.canonical_theory_atoms)
            if state.canonical_theory_atoms
            else list(state.theory_atoms)
        )
        relations = (
            list(state.canonical_theory_relations)
            if state.canonical_theory_relations
            else list(state.theory_relations)
        )
        enrichments = list(state.theoretical_enrichments)
        entities = list(state.entities)
        triples = [*state.local_triples, *state.global_triples]

        if not atoms and not enrichments and not entities:
            return []

        phase_label = self.detected_in_phase or (
            "theoretical_enrichment" if enrichments else "phase6"
        )
        atoms_by_id: dict[str, TheoryAtom] = {a.id: a for a in atoms}
        entities_by_id: dict[str, L2Entity] = {e.id: e for e in entities}
        chunk_neighbors = _build_chunk_neighbors(state.chunks)

        nx_graph = _build_theory_nx_graph(atoms, relations)
        pr_scores, btw_scores = _compute_centralities(nx_graph)
        atom_to_community = _compute_louvain_communities(nx_graph)
        in_support_degree, z1_grounded, a_atoms, b_atoms = _compute_z1_and_support(
            atoms, relations, self.schema
        )

        (
            atom_to_enrichments,
            edge_tenability_map,
            equilibrium_map,
            cluster_b_counts,
            cluster_dimensions,
        ) = self._index_enrichments_and_clusters(atoms, enrichments, b_atoms)

        candidates: list[EpistemicDeficit] = []
        candidates.extend(
            self._detect_enthymeme_gaps(
                atoms=atoms,
                atoms_by_id=atoms_by_id,
                entities_by_id=entities_by_id,
                a_atoms=a_atoms,
                b_atoms=b_atoms,
                in_support_degree=in_support_degree,
                z1_grounded=z1_grounded,
                pr_scores=pr_scores,
                btw_scores=btw_scores,
                atom_to_enrichments=atom_to_enrichments,
                equilibrium_map=equilibrium_map,
                cluster_dimensions=cluster_dimensions,
                chunk_neighbors=chunk_neighbors,
                cfg=cfg,
                phase_label=phase_label,
                refinement_pass=refinement_pass,
            )
        )
        candidates.extend(
            self._detect_polysemy_collisions(
                atoms=atoms,
                atoms_by_id=atoms_by_id,
                relations=relations,
                entities=entities,
                triples=triples,
                atom_to_enrichments=atom_to_enrichments,
                atom_to_community=atom_to_community,
                edge_tenability_map=edge_tenability_map,
                chunk_neighbors=chunk_neighbors,
                cfg=cfg,
                phase_label=phase_label,
                refinement_pass=refinement_pass,
            )
        )
        candidates.extend(
            self._detect_ungrounded_axioms(
                atoms=atoms,
                atoms_by_id=atoms_by_id,
                enrichments=enrichments,
                a_atoms=a_atoms,
                z1_grounded=z1_grounded,
                atom_to_enrichments=atom_to_enrichments,
                equilibrium_map=equilibrium_map,
                cluster_b_counts=cluster_b_counts,
                cluster_dimensions=cluster_dimensions,
                chunk_neighbors=chunk_neighbors,
                cfg=cfg,
                phase_label=phase_label,
                refinement_pass=refinement_pass,
            )
        )

        deduped: dict[str, EpistemicDeficit] = {}
        for deficit in candidates:
            existing = deduped.get(deficit.deficit_id)
            if existing is None or deficit.severity > existing.severity:
                deduped[deficit.deficit_id] = deficit

        prioritized = sorted(
            deduped.values(),
            key=lambda d: (-d.severity, d.deficit_kind.value, d.deficit_id),
        )[: cfg.max_deficits_per_cycle]

        self._emit_deficit_events(prioritized, phase_label=phase_label, context=context)
        return prioritized

    def _index_enrichments_and_clusters(
        self,
        atoms: Sequence[TheoryAtom],
        enrichments: Sequence[TheoreticalEnrichmentArtifact],
        b_atoms: set[str],
    ) -> tuple[
        dict[str, list[TheoreticalEnrichmentArtifact]],
        dict[str, float],
        dict[str, float],
        dict[str, int],
        dict[str, set[str]],
    ]:
        """Build deterministic lookup maps across clusters and enrichment records."""
        atom_to_enrichments: dict[str, list[TheoreticalEnrichmentArtifact]] = {}
        edge_tenability_map: dict[str, float] = {}
        equilibrium_map: dict[str, float] = {}
        cluster_b_counts: dict[str, int] = {}
        cluster_dimensions: dict[str, set[str]] = {}

        for atom in atoms:
            chunk_cluster = f"cluster-{atom.source_chunk_id}"
            if atom.id in b_atoms:
                cluster_b_counts[atom.source_chunk_id] = (
                    cluster_b_counts.get(atom.source_chunk_id, 0) + 1
                )
                cluster_b_counts[chunk_cluster] = (
                    cluster_b_counts.get(chunk_cluster, 0) + 1
                )
            dims = cluster_dimensions.setdefault(atom.source_chunk_id, set())
            cdims = cluster_dimensions.setdefault(chunk_cluster, set())
            for meas in atom.measurements:
                d_low = meas.dimension.strip().lower()
                if d_low:
                    dims.add(d_low)
                    cdims.add(d_low)

        enr_by_cluster: dict[str, list[TheoreticalEnrichmentArtifact]] = {}
        for enr in enrichments:
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

        return (
            atom_to_enrichments,
            edge_tenability_map,
            equilibrium_map,
            cluster_b_counts,
            cluster_dimensions,
        )

    def _detect_enthymeme_gaps(
        self,
        *,
        atoms: Sequence[TheoryAtom],
        atoms_by_id: dict[str, TheoryAtom],
        entities_by_id: dict[str, L2Entity],
        a_atoms: set[str],
        b_atoms: set[str],
        in_support_degree: dict[str, int],
        z1_grounded: set[str],
        pr_scores: dict[str, float],
        btw_scores: dict[str, float],
        atom_to_enrichments: dict[str, list[TheoreticalEnrichmentArtifact]],
        equilibrium_map: dict[str, float],
        cluster_dimensions: dict[str, set[str]],
        chunk_neighbors: dict[str, list[str]],
        cfg: HermeneuticRefinementConfig,
        phase_label: str,
        refinement_pass: int,
    ) -> list[EpistemicDeficit]:
        """Detect unwarranted or :math:`Z_1`-disconnected A-partition atoms."""
        max_pr = max((pr_scores.get(aid, 0.0) for aid in a_atoms), default=0.0)
        max_btw = max((btw_scores.get(aid, 0.0) for aid in a_atoms), default=0.0)
        core_claims = [
            atoms_by_id[aid].text
            for aid in sorted(
                a_atoms,
                key=lambda x: (-pr_scores.get(x, 0.0), -btw_scores.get(x, 0.0), x),
            )[:5]
        ]

        deficits: list[EpistemicDeficit] = []
        for atom in sorted(atoms, key=lambda a: a.id):
            if atom.id not in a_atoms or atom.intensional_mode == "suppositional":
                continue

            centrality = float(pr_scores.get(atom.id, 0.0))
            btw = float(btw_scores.get(atom.id, 0.0))
            if centrality < cfg.enthymeme_min_centrality:
                continue

            in_sup = in_support_degree.get(atom.id, 0)
            is_z1 = atom.id in z1_grounded
            if in_sup > 0 and is_z1:
                continue

            base_sev = (
                0.70 if (in_sup == 0 and not is_z1) else (0.60 if in_sup == 0 else 0.50)
            )
            norm_pr = (centrality / max_pr) if max_pr > 0.0 else 0.0
            norm_btw = (btw / max_btw) if max_btw > 0.0 else 0.0
            severity = min(
                1.0,
                max(0.0, round(base_sev + 0.25 * norm_pr + 0.05 * norm_btw, 4)),
            )

            enrs = atom_to_enrichments.get(atom.id, [])
            primary_theory_id = enrs[0].theory_id if enrs else None
            if primary_theory_id is None and isinstance(
                atom.parameters.get("theory_id"), str
            ):
                primary_theory_id = str(atom.parameters["theory_id"])

            projected_params: dict[str, Any] = {}
            for enr in enrs:
                projected_params.update(enr.projected_parameters)
            projected_params.update(atom.parameters)

            param_names = sorted(
                k for k in projected_params if k not in _METADATA_PARAM_KEYS
            )
            target_chunks = _collect_target_chunks(
                [atom.source_chunk_id], chunk_neighbors
            )
            local_and_adjacent_dims = sorted(
                {
                    dim
                    for cid in target_chunks
                    for dim in cluster_dimensions.get(cid, set())
                }
            )
            macro_dims = sorted(
                {
                    dim
                    for dims in cluster_dimensions.values()
                    for dim in dims
                }
            )
            required_dims = _dedup_preserve_order(
                [
                    *_extract_required_dimensions(
                        atom, enrs[0] if enrs else None
                    ),
                    *local_and_adjacent_dims,
                    *macro_dims,
                ]
            )
            entity_names = [
                entities_by_id[eid].name
                for eid in atom.entity_ids
                if eid in entities_by_id
            ]
            theory_lens: dict[str, Any] = {
                "theory_ids": _dedup_preserve_order(
                    [e.theory_id for e in enrs if e.theory_id]
                ),
                "parameter_names": param_names,
                "required_dimensions": required_dims,
                "projected_parameters": {
                    k: v
                    for k, v in projected_params.items()
                    if k not in _METADATA_PARAM_KEYS
                },
                "core_claims": [c for c in core_claims if c != atom.text],
                "atom_text": atom.text,
                "component_type": atom.component_type,
                "entity_names": entity_names,
            }

            tau_star = (
                float(atom.equilibrium_strength)
                if atom.equilibrium_strength is not None
                else equilibrium_map.get(atom.id, atom.effective_base_prior())
            )

            gap_reason = (
                "has zero incoming support edges and no Z1 path to empirical base B"
                if (in_sup == 0 and not is_z1)
                else (
                    "has zero incoming support edges"
                    if in_sup == 0
                    else "lacks a Z1 grounding path to empirical base B"
                )
            )
            if not b_atoms and in_sup == 0:
                gap_reason = "has zero incoming support edges and no empirical B-base"

            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"enthymeme_gap::{atom.id}",
                    deficit_kind=EpistemicDeficitKind.ENTHYMEME_GAP,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=list(atom.entity_ids),
                    target_atom_ids=[atom.id],
                    target_relation_ids=[],
                    theory_id=primary_theory_id,
                    theory_lens=theory_lens,
                    rationale=(
                        f"{atom.component_type} '{atom.id}' (centrality={centrality:.4f}) "
                        f"{gap_reason}."
                    ),
                    metrics={
                        "centrality": round(centrality, 6),
                        "betweenness_centrality": round(btw, 6),
                        "in_support_degree": float(in_sup),
                        "tau_star": round(float(tau_star), 6),
                        "z1_grounded": 1.0 if is_z1 else 0.0,
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
        return deficits

    def _detect_polysemy_collisions(
        self,
        *,
        atoms: Sequence[TheoryAtom],
        atoms_by_id: dict[str, TheoryAtom],
        relations: Sequence[TheoryRelation],
        entities: Sequence[L2Entity],
        triples: Sequence[L2Triple],
        atom_to_enrichments: dict[str, list[TheoreticalEnrichmentArtifact]],
        atom_to_community: dict[str, int],
        edge_tenability_map: dict[str, float],
        chunk_neighbors: dict[str, list[str]],
        cfg: HermeneuticRefinementConfig,
        phase_label: str,
        refinement_pass: int,
    ) -> list[EpistemicDeficit]:
        """Detect entity/atom polysemy bridges across incompatible clusters."""
        deficits: list[EpistemicDeficit] = []
        covered_atoms: set[str] = set()
        covered_relations: set[str] = set()

        triples_by_entity: dict[str, list[L2Triple]] = {}
        for triple in triples:
            triples_by_entity.setdefault(triple.subject_id, []).append(triple)
            if triple.object_id != triple.subject_id:
                triples_by_entity.setdefault(triple.object_id, []).append(triple)

        rels_by_atom: dict[str, list[TheoryRelation]] = {}
        for rel in relations:
            if not rel.is_admissible or rel.undercuts_relation_id is not None:
                continue
            involved = set(rel.effective_premise_ids)
            if rel.target_id in atoms_by_id:
                involved.add(rel.target_id)
            for aid in involved:
                if aid in atoms_by_id:
                    rels_by_atom.setdefault(aid, []).append(rel)

        # 1. Entity-centric polysemy collisions
        for ent in sorted(entities, key=lambda e: e.id):
            linked_atoms = [a for a in atoms if ent.id in a.entity_ids]
            if (
                not linked_atoms
                and (len(ent.conceptions) >= 2 or (ent.polysemy_variance or 0.0) > 0.0)
                and ent.source_chunk_ids
            ):
                ent_chunks = set(ent.source_chunk_ids)
                linked_atoms = [a for a in atoms if a.source_chunk_id in ent_chunks]

            linked_ids = {a.id for a in linked_atoms}
            touching_rels = _dedup_relations(
                [rel for aid in linked_ids for rel in rels_by_atom.get(aid, [])]
            )
            ent_triples = triples_by_entity.get(ent.id, [])

            incompatible, conflict_reasons, implicated_rels = (
                self._assess_incompatibility(
                    atom_ids=linked_ids,
                    touching_rels=touching_rels,
                    entity=ent,
                    ent_triples=ent_triples,
                    atoms_by_id=atoms_by_id,
                    atom_to_enrichments=atom_to_enrichments,
                    atom_to_community=atom_to_community,
                    edge_tenability_map=edge_tenability_map,
                    cfg=cfg,
                )
            )
            if not incompatible:
                continue

            implicated_atom_ids: set[str] = set(linked_ids)
            for rel in implicated_rels:
                for pid in rel.effective_premise_ids:
                    if pid in atoms_by_id:
                        implicated_atom_ids.add(pid)
                if rel.target_id in atoms_by_id:
                    implicated_atom_ids.add(rel.target_id)

            max_vol = max(
                (
                    float(atoms_by_id[aid].controversy_volatility)
                    for aid in implicated_atom_ids
                    if atoms_by_id[aid].controversy_volatility is not None
                ),
                default=0.0,
            )
            ts_values = [
                ts
                for rel in touching_rels
                if (ts := _lookup_edge_tenability(rel, edge_tenability_map)) is not None
            ]
            min_ts_edge = min(ts_values) if ts_values else 1.0
            polysemy_var = (
                float(ent.polysemy_variance)
                if ent.polysemy_variance is not None
                else 0.0
            )

            vol_hit = max_vol >= cfg.polysemy_volatility_threshold
            edge_hit = min_ts_edge < cfg.polysemy_edge_tenability_threshold
            if not (vol_hit or edge_hit):
                continue

            severity = self._polysemy_severity(
                max_vol=max_vol,
                min_ts_edge=min_ts_edge,
                polysemy_var=polysemy_var,
                cfg=cfg,
            )
            target_atoms = sorted(implicated_atom_ids)
            target_rels = [r.relation_id for r in implicated_rels]
            seed_chunks = [
                *ent.source_chunk_ids,
                *(atoms_by_id[aid].source_chunk_id for aid in target_atoms),
            ]
            target_chunks = _collect_target_chunks(seed_chunks, chunk_neighbors)
            enrs = [
                enr
                for aid in target_atoms
                for enr in atom_to_enrichments.get(aid, [])
            ]
            theory_ids = _dedup_preserve_order([e.theory_id for e in enrs if e.theory_id])

            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"polysemy_collision::entity::{ent.id}",
                    deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=[ent.id],
                    target_atom_ids=target_atoms,
                    target_relation_ids=target_rels,
                    theory_id=theory_ids[0] if len(theory_ids) == 1 else None,
                    theory_lens={
                        "entity_name": ent.name,
                        "entity_label": ent.label,
                        "conception_perspectives": [
                            c.perspective for c in ent.conceptions
                        ],
                        "conflicting_theories": theory_ids,
                        "conflicting_clusters": _dedup_preserve_order(
                            [e.cluster_id for e in enrs]
                        ),
                        "conflict_signals": conflict_reasons,
                    },
                    rationale=(
                        f"Entity '{ent.name}' ({ent.id}) bridges incompatible "
                        f"clusters/stances ({', '.join(conflict_reasons)}) with "
                        f"V={max_vol:.3f}, TS_edge={min_ts_edge:.3f}."
                    ),
                    metrics={
                        "controversy_volatility": round(max_vol, 6),
                        "ts_edge": round(min_ts_edge, 6),
                        "polysemy_variance": round(polysemy_var, 6),
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
            covered_atoms.update(target_atoms)
            covered_relations.update(target_rels)

        # 2. Atom-centric polysemy collisions (uncovered by entity-level)
        for atom in sorted(atoms, key=lambda a: a.id):
            if atom.id in covered_atoms:
                continue
            touching_rels = _dedup_relations(rels_by_atom.get(atom.id, []))
            if not touching_rels:
                continue

            vol = (
                float(atom.controversy_volatility)
                if atom.controversy_volatility is not None
                else 0.0
            )
            ts_values = [
                ts
                for rel in touching_rels
                if (ts := _lookup_edge_tenability(rel, edge_tenability_map)) is not None
            ]
            min_ts_edge = min(ts_values) if ts_values else 1.0
            vol_hit = vol >= cfg.polysemy_volatility_threshold
            edge_hit = min_ts_edge < cfg.polysemy_edge_tenability_threshold
            if not (vol_hit or edge_hit):
                continue

            incompatible, conflict_reasons, implicated_rels = (
                self._assess_incompatibility(
                    atom_ids={atom.id},
                    touching_rels=touching_rels,
                    entity=None,
                    ent_triples=(),
                    atoms_by_id=atoms_by_id,
                    atom_to_enrichments=atom_to_enrichments,
                    atom_to_community=atom_to_community,
                    edge_tenability_map=edge_tenability_map,
                    cfg=cfg,
                )
            )
            if not incompatible:
                continue

            implicated_rel_ids = [r.relation_id for r in implicated_rels]
            if implicated_rel_ids and all(
                rid in covered_relations for rid in implicated_rel_ids
            ):
                continue

            neighbor_atom_ids: set[str] = {atom.id}
            for rel in implicated_rels:
                for pid in rel.effective_premise_ids:
                    if pid in atoms_by_id:
                        neighbor_atom_ids.add(pid)
                if rel.target_id in atoms_by_id:
                    neighbor_atom_ids.add(rel.target_id)

            target_atoms = sorted(neighbor_atom_ids)
            target_entities = _dedup_preserve_order(
                [
                    eid
                    for aid in target_atoms
                    for eid in atoms_by_id[aid].entity_ids
                ]
            )
            target_chunks = _collect_target_chunks(
                [atoms_by_id[aid].source_chunk_id for aid in target_atoms],
                chunk_neighbors,
            )
            enrs = [
                enr
                for aid in target_atoms
                for enr in atom_to_enrichments.get(aid, [])
            ]
            theory_ids = _dedup_preserve_order([e.theory_id for e in enrs if e.theory_id])

            severity = self._polysemy_severity(
                max_vol=vol,
                min_ts_edge=min_ts_edge,
                polysemy_var=0.0,
                cfg=cfg,
            )
            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"polysemy_collision::atom::{atom.id}",
                    deficit_kind=EpistemicDeficitKind.POLYSEMY_COLLISION,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=target_entities,
                    target_atom_ids=target_atoms,
                    target_relation_ids=implicated_rel_ids,
                    theory_id=theory_ids[0] if len(theory_ids) == 1 else None,
                    theory_lens={
                        "atom_text": atom.text,
                        "conflicting_theories": theory_ids,
                        "conflicting_clusters": _dedup_preserve_order(
                            [e.cluster_id for e in enrs]
                        ),
                        "conflict_signals": conflict_reasons,
                    },
                    rationale=(
                        f"TheoryAtom '{atom.id}' bridges incompatible clusters/stances "
                        f"({', '.join(conflict_reasons)}) with V={vol:.3f}, "
                        f"TS_edge={min_ts_edge:.3f}."
                    ),
                    metrics={
                        "controversy_volatility": round(vol, 6),
                        "ts_edge": round(min_ts_edge, 6),
                        "polysemy_variance": 0.0,
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
            covered_atoms.update(target_atoms)
            covered_relations.update(implicated_rel_ids)

        return deficits

    def _assess_incompatibility(
        self,
        *,
        atom_ids: set[str],
        touching_rels: Sequence[TheoryRelation],
        entity: L2Entity | None,
        ent_triples: Sequence[L2Triple],
        atoms_by_id: dict[str, TheoryAtom],
        atom_to_enrichments: dict[str, list[TheoreticalEnrichmentArtifact]],
        atom_to_community: dict[str, int],
        edge_tenability_map: dict[str, float],
        cfg: HermeneuticRefinementConfig,
    ) -> tuple[bool, list[str], list[TheoryRelation]]:
        """Check whether an entity or atom set bridges incompatible clusters/stances."""
        reasons: list[str] = []
        implicated: list[TheoryRelation] = []
        rel_polarities: set[int] = set()

        for rel in touching_rels:
            pol = _relation_polarity(rel, self.schema)
            if pol != 0:
                rel_polarities.add(pol)

            endpoints = {
                pid for pid in rel.effective_premise_ids if pid in atoms_by_id
            }
            if rel.target_id in atoms_by_id:
                endpoints.add(rel.target_id)

            ts_edge = _lookup_edge_tenability(rel, edge_tenability_map)
            low_ts = (
                ts_edge is not None and ts_edge < cfg.polysemy_edge_tenability_threshold
            )

            ep_clusters = {
                e.cluster_id
                for aid in endpoints
                for e in atom_to_enrichments.get(aid, [])
            }
            ep_theories = {
                e.theory_id
                for aid in endpoints
                for e in atom_to_enrichments.get(aid, [])
                if e.theory_id
            }
            ep_comms = {
                atom_to_community[aid]
                for aid in endpoints
                if aid in atom_to_community
            }
            ep_perspectives = {
                atoms_by_id[aid].attributed_to.strip().lower()
                for aid in endpoints
                if atoms_by_id[aid].attributed_to
            }
            cross_cluster = (
                len(ep_clusters) > 1
                or len(ep_theories) > 1
                or len(ep_comms) > 1
                or len(ep_perspectives) > 1
            )
            if low_ts and cross_cluster:
                reasons.append("low_ts_edge_cross_cluster")
                implicated.append(rel)
            elif low_ts and pol < 0:
                reasons.append("low_ts_edge_attack")
                implicated.append(rel)
            elif cross_cluster:
                reasons.append("cross_cluster_bridge")
                implicated.append(rel)

        triple_polarities = {
            _triple_polarity(t, self.schema) for t in ent_triples
        } - {0}
        combined_polarities = rel_polarities | triple_polarities
        if 1 in combined_polarities and -1 in combined_polarities:
            reasons.append("conflicting_support_attack")
            implicated.extend(
                r for r in touching_rels if _relation_polarity(r, self.schema) != 0
            )
        elif entity is not None and len(atom_ids) >= 2 and -1 in combined_polarities:
            reasons.append("conflicting_internal_attack")
            implicated.extend(
                r for r in touching_rels if _relation_polarity(r, self.schema) < 0
            )

        all_clusters = {
            e.cluster_id
            for aid in atom_ids
            for e in atom_to_enrichments.get(aid, [])
        }
        all_theories = {
            e.theory_id
            for aid in atom_ids
            for e in atom_to_enrichments.get(aid, [])
            if e.theory_id
        }
        all_comms = {
            atom_to_community[aid] for aid in atom_ids if aid in atom_to_community
        }
        if len(all_clusters) > 1 or len(all_theories) > 1 or len(all_comms) > 1:
            reasons.append("distinct_clusters")

        if entity is not None and (
            len(entity.conceptions) >= 2
            or (entity.polysemy_variance is not None and entity.polysemy_variance > 0.0)
        ):
            reasons.append("multiple_conceptions_or_polysemy")
            if not implicated:
                implicated.extend(touching_rels)

        dedup_reasons = _dedup_preserve_order(reasons)
        dedup_rels = _dedup_relations(implicated) if implicated else list(touching_rels)
        return bool(dedup_reasons), dedup_reasons, dedup_rels

    @staticmethod
    def _polysemy_severity(
        *,
        max_vol: float,
        min_ts_edge: float,
        polysemy_var: float,
        cfg: HermeneuticRefinementConfig,
    ) -> float:
        """Compute normalized ``[0.0, 1.0]`` severity for ``POLYSEMY_COLLISION``."""
        vol_part = 0.0
        if max_vol >= cfg.polysemy_volatility_threshold:
            denom = max(1.0 - cfg.polysemy_volatility_threshold, 1e-6)
            excess = max(0.0, max_vol - cfg.polysemy_volatility_threshold) / denom
            vol_part = 0.55 + 0.40 * min(1.0, excess)

        edge_part = 0.0
        if min_ts_edge < cfg.polysemy_edge_tenability_threshold:
            denom = max(cfg.polysemy_edge_tenability_threshold, 1e-6)
            deficit_ratio = (
                cfg.polysemy_edge_tenability_threshold - min_ts_edge
            ) / denom
            edge_part = 0.55 + 0.40 * min(1.0, max(0.0, deficit_ratio))

        bonus = 0.05 if (vol_part > 0.0 and edge_part > 0.0) or polysemy_var > 0.0 else 0.0
        return min(1.0, round(max(vol_part, edge_part) + bonus, 4))

    def _detect_ungrounded_axioms(
        self,
        *,
        atoms: Sequence[TheoryAtom],
        atoms_by_id: dict[str, TheoryAtom],
        enrichments: Sequence[TheoreticalEnrichmentArtifact],
        a_atoms: set[str],
        z1_grounded: set[str],
        atom_to_enrichments: dict[str, list[TheoreticalEnrichmentArtifact]],
        equilibrium_map: dict[str, float],
        cluster_b_counts: dict[str, int],
        cluster_dimensions: dict[str, set[str]],
        chunk_neighbors: dict[str, list[str]],
        cfg: HermeneuticRefinementConfig,
        phase_label: str,
        refinement_pass: int,
    ) -> list[EpistemicDeficit]:
        """Detect low-tenability or observationally ungrounded axioms/clusters."""
        deficits: list[EpistemicDeficit] = []
        covered_by_enrichment: set[str] = set()

        # 1. Enrichment-cluster level checks
        for enr in sorted(
            enrichments, key=lambda e: (e.theory_id, e.cluster_id, e.enrichment_id)
        ):
            chunk_hint = enr.cluster_id.removeprefix("cluster-")
            claimant_ids = _dedup_preserve_order(enr.claimant_atom_ids)
            if not claimant_ids:
                claimant_ids = [
                    a.id
                    for a in atoms
                    if a.id in a_atoms and a.source_chunk_id == chunk_hint
                ]

            claimant_atoms = [
                atoms_by_id[aid] for aid in claimant_ids if aid in atoms_by_id
            ]
            req_dims = _dedup_preserve_order(
                [
                    *_extract_required_dimensions(None, enr),
                    *(
                        dim
                        for ca in claimant_atoms
                        for dim in _extract_required_dimensions(ca, None)
                    ),
                ]
            )
            observed_dims = (
                cluster_dimensions.get(enr.cluster_id, set())
                | cluster_dimensions.get(chunk_hint, set())
            )
            missing_dims = [d for d in req_dims if d.lower() not in observed_dims]

            has_local_anomaly = any(
                not anom.startswith("Constraint edge ") for anom in enr.anomalies
            )
            low_ts_local = enr.local_tenability < cfg.ungrounded_local_tenability_threshold
            failed_tenable = not enr.is_tenable

            if not (low_ts_local or failed_tenable or has_local_anomaly or missing_dims):
                continue

            gap_local = (
                max(0.0, cfg.ungrounded_local_tenability_threshold - enr.local_tenability)
                / max(cfg.ungrounded_local_tenability_threshold, 1e-6)
                if low_ts_local
                else 0.0
            )
            gap_agg = (
                max(
                    0.0,
                    cfg.ungrounded_local_tenability_threshold - enr.aggregated_tenability,
                )
                / max(cfg.ungrounded_local_tenability_threshold, 1e-6)
                if failed_tenable
                else 0.0
            )
            severity = min(
                1.0,
                max(0.60, round(0.60 + 0.40 * max(gap_local, gap_agg), 4)),
            )

            param_names = sorted(
                k
                for k in {
                    *enr.projected_parameters.keys(),
                    *(
                        pk
                        for ca in claimant_atoms
                        for pk in ca.parameters.keys()
                    ),
                }
                if k not in _METADATA_PARAM_KEYS
            )
            tau_vals = [
                ca.equilibrium_strength
                if ca.equilibrium_strength is not None
                else equilibrium_map.get(ca.id, ca.effective_base_prior())
                for ca in claimant_atoms
            ]
            if not tau_vals and claimant_ids:
                tau_vals = [
                    equilibrium_map[cid]
                    for cid in claimant_ids
                    if cid in equilibrium_map
                ]
            min_tau_star = float(min(tau_vals)) if tau_vals else 0.0

            seed_chunks = [
                *(ca.source_chunk_id for ca in claimant_atoms),
                *([chunk_hint] if chunk_hint and chunk_hint != enr.cluster_id else []),
            ]
            target_chunks = _collect_target_chunks(seed_chunks, chunk_neighbors)

            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"ungrounded_axiom::{enr.theory_id}::{enr.cluster_id}",
                    deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=_dedup_preserve_order(
                        [eid for ca in claimant_atoms for eid in ca.entity_ids]
                    ),
                    target_atom_ids=claimant_ids,
                    target_relation_ids=[],
                    theory_id=enr.theory_id or None,
                    theory_lens={
                        "required_dimensions": req_dims,
                        "parameter_names": param_names,
                        "claimant_atom_ids": claimant_ids,
                        "missing_dimensions": missing_dims,
                        "cluster_id": enr.cluster_id,
                        "anomalies": list(enr.anomalies),
                        "projected_parameters": dict(enr.projected_parameters),
                    },
                    rationale=(
                        f"Cluster '{enr.cluster_id}' under theory '{enr.theory_id}' "
                        f"failed empirical grounding (TS_local={enr.local_tenability:.3f}, "
                        f"is_tenable={enr.is_tenable})."
                    ),
                    metrics={
                        "ts_local": round(float(enr.local_tenability), 6),
                        "aggregated_tenability": round(
                            float(enr.aggregated_tenability), 6
                        ),
                        "tau_star": round(min_tau_star, 6),
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )
            covered_by_enrichment.update(claimant_ids)

        # 2. Atom-level checks (for atoms not already covered by a failing enrichment)
        for atom in sorted(atoms, key=lambda a: a.id):
            if atom.id not in a_atoms or atom.id in covered_by_enrichment:
                continue
            if atom.intensional_mode == "suppositional":
                continue

            ts_local = (
                float(atom.local_tenability)
                if atom.local_tenability is not None
                else (
                    float(atom.tenability.local_score)
                    if atom.tenability is not None
                    else None
                )
            )
            agg_ts = (
                float(atom.tenability.aggregated_score)
                if atom.tenability is not None
                else ts_local
            )
            low_ts = (
                ts_local is not None
                and ts_local < cfg.ungrounded_local_tenability_threshold
            )
            untenable = atom.tenability is not None and not atom.tenability.is_tenable
            no_obs_in_cluster = cluster_b_counts.get(atom.source_chunk_id, 0) == 0
            ungrounded_z1 = (atom.id not in z1_grounded) and no_obs_in_cluster

            enrs = atom_to_enrichments.get(atom.id, [])
            req_dims = _extract_required_dimensions(
                atom, enrs[0] if enrs else None
            )
            observed_dims = cluster_dimensions.get(atom.source_chunk_id, set())
            missing_dims = [d for d in req_dims if d.lower() not in observed_dims]

            if not (low_ts or untenable or ungrounded_z1 or missing_dims):
                continue

            eff_ts_local = float(ts_local) if ts_local is not None else 0.0
            eff_agg = float(agg_ts) if agg_ts is not None else eff_ts_local
            tau_star = (
                float(atom.equilibrium_strength)
                if atom.equilibrium_strength is not None
                else equilibrium_map.get(atom.id, atom.effective_base_prior())
            )

            if low_ts or untenable:
                gap = max(
                    0.0, cfg.ungrounded_local_tenability_threshold - eff_ts_local
                ) / max(cfg.ungrounded_local_tenability_threshold, 1e-6)
                severity = min(1.0, max(0.55, round(0.55 + 0.45 * gap, 4)))
            elif ungrounded_z1:
                prior = atom.modal_prior if atom.modal_prior is not None else 0.6
                severity = min(1.0, round(0.55 + 0.25 * float(prior), 4))
            else:
                severity = 0.65

            theory_id: str | None = enrs[0].theory_id if enrs else None
            if theory_id is None and isinstance(atom.parameters.get("theory_id"), str):
                theory_id = str(atom.parameters["theory_id"])

            param_names = sorted(
                k for k in atom.parameters.keys() if k not in _METADATA_PARAM_KEYS
            )
            target_chunks = _collect_target_chunks(
                [atom.source_chunk_id], chunk_neighbors
            )

            deficits.append(
                EpistemicDeficit(
                    deficit_id=f"ungrounded_axiom::atom::{atom.id}",
                    deficit_kind=EpistemicDeficitKind.UNGROUNDED_AXIOM,
                    severity=severity,
                    target_chunk_ids=target_chunks,
                    target_entity_ids=list(atom.entity_ids),
                    target_atom_ids=[atom.id],
                    target_relation_ids=[],
                    theory_id=theory_id,
                    theory_lens={
                        "required_dimensions": req_dims,
                        "parameter_names": param_names,
                        "claimant_atom_ids": [atom.id],
                        "missing_dimensions": missing_dims,
                        "anomalies": (
                            list(atom.tenability.anomalies)
                            if atom.tenability is not None
                            else []
                        ),
                    },
                    rationale=(
                        f"{atom.component_type} '{atom.id}' lacks empirical grounding "
                        f"(TS_local={eff_ts_local:.3f}, z1_grounded={atom.id in z1_grounded}, "
                        f"cluster_observations={cluster_b_counts.get(atom.source_chunk_id, 0)})."
                    ),
                    metrics={
                        "ts_local": round(eff_ts_local, 6),
                        "aggregated_tenability": round(eff_agg, 6),
                        "tau_star": round(float(tau_star), 6),
                    },
                    detected_in_phase=phase_label,
                    refinement_pass=refinement_pass,
                )
            )

        return deficits

    @staticmethod
    def _emit_deficit_events(
        deficits: Sequence[EpistemicDeficit],
        *,
        phase_label: str,
        context: ArtifactExecutionContext | None,
    ) -> None:
        """Publish :class:`EpistemicDeficitDetected` domain events for deficits."""
        if not deficits:
            return
        emitter = get_event_emitter()
        run_id = context.run_id if context is not None and context.run_id else None
        for deficit in deficits:
            emitter.emit(
                EpistemicDeficitDetected(
                    run_id=run_id,
                    phase=phase_label,
                    deficit_id=deficit.deficit_id,
                    deficit_kind=deficit.deficit_kind.value,
                    severity=deficit.severity,
                    target_chunk_ids=list(deficit.target_chunk_ids),
                    target_entity_ids=list(deficit.target_entity_ids),
                    target_atom_ids=list(deficit.target_atom_ids),
                    target_relation_ids=list(deficit.target_relation_ids),
                    theory_id=deficit.theory_id,
                    refinement_pass=deficit.refinement_pass,
                    rationale=deficit.rationale,
                )
            )


def _dedup_relations(relations: Iterable[TheoryRelation]) -> list[TheoryRelation]:
    """Deduplicate ``TheoryRelation`` instances by canonical ``relation_id``."""
    by_id: dict[str, TheoryRelation] = {}
    for rel in relations:
        by_id.setdefault(rel.relation_id, rel)
    return [by_id[k] for k in sorted(by_id)]
