"""Metrics and epistemic overlay adapters bridging graph views to algorithms."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import logging
import igraph as ig
import networkx as nx

logger = logging.getLogger(__name__)

from epistemetrics.core.models import CentralityResult, PartitionResult
from epistemetrics.graph.algorithms import (
    betweenness_centrality,
    eigenvector_centrality,
    louvain_communities,
    page_rank,
    weakly_connected_components,
)
from episteme_studio.domain.graph import GraphView, Layer
from episteme_studio.domain.metrics import (
    AffectedEdgeDetail,
    AffectedNodeDetail,
    MetricResult,
    MetricScope,
)
from episteme_studio.domain.overlays import Overlay, OverlayKind


def compute_gradual_strength(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> Overlay:
    """Compute gradual strength acceptability scores (rho) across arguments.

    Implements the QBAF gradual semantics aggregation defined in
    theorynet_concept.md §4:

    .. math::
        \\alpha(a_i) = \\sum_{(a_j, a_i) \\in \\mathcal{R}_{sup}} \\rho(a_j) \\cdot \\phi(a_j, a_i)
        - \\sum_{(a_j, a_i) \\in \\mathcal{R}_{att}} \\rho(a_j) \\cdot \\phi(a_j, a_i)

    Non-null prior plausibility (tau) initializes strength, and edge weights (phi)
    weigh incoming relations. Missing tau or phi are tracked and reported via
    `incomplete_inputs`.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Optional algorithmic parameters such as 'iterations' (default 10)
        and 'tolerance' (default 1e-4).

    Returns
    -------
    Overlay
        Computed gradual strength overlay.
    """
    opts = params or {}
    max_iterations = int(opts.get("iterations", 10))
    tolerance = float(opts.get("tolerance", 1e-4))

    node_values: dict[str, float | str | None] = {}
    edge_values: dict[str, float | str | None] = {}
    incomplete_inputs = 0

    # Map nodes and track missing tau (prioritizing modal_strength / base_score over legacy plausibility)
    tau_map: dict[str, float | None] = {}
    for node in graph.nodes:
        tau_val = (
            node.modal_strength
            if node.modal_strength is not None
            else (node.base_score if node.base_score is not None else node.plausibility)
        )
        if tau_val is None:
            incomplete_inputs += 1
            tau_map[node.id] = None
        else:
            tau_map[node.id] = float(tau_val)

    # Track incoming edges and missing phi
    incoming_edges: dict[str, list[tuple[str, float, int]]] = defaultdict(list)
    for edge in graph.edges:
        weight = edge.weight
        if weight is None:
            incomplete_inputs += 1
            edge_values[edge.id] = None
        else:
            edge_values[edge.id] = float(weight)

        polarity = edge.polarity
        if weight is not None and polarity in (-1, 1):
            incoming_edges[edge.target].append((edge.source, float(weight), int(polarity)))

    # Initialize rho for nodes with known tau
    rho_current: dict[str, float] = {
        nid: max(0.0, min(1.0, tau))
        for nid, tau in tau_map.items()
        if tau is not None
    }

    # Iterative gradual semantics propagation
    for _ in range(max_iterations):
        max_delta = 0.0
        rho_next: dict[str, float] = {}

        for nid, tau in tau_map.items():
            if tau is None:
                continue

            # Compute alpha(a_i)
            alpha = 0.0
            for src_id, phi, pol in incoming_edges.get(nid, []):
                src_rho = rho_current.get(src_id)
                if src_rho is not None:
                    if pol > 0:
                        alpha += src_rho * phi
                    elif pol < 0:
                        alpha -= src_rho * phi

            # Quadratic energy / gradual update function
            if alpha >= 0.0:
                score = tau + (1.0 - tau) * (alpha / (1.0 + alpha))
            else:
                abs_alpha = abs(alpha)
                score = tau / (1.0 + abs_alpha)

            clamped = max(0.0, min(1.0, score))
            delta = abs(clamped - rho_current.get(nid, tau))
            if delta > max_delta:
                max_delta = delta
            rho_next[nid] = clamped

        rho_current = rho_next
        if max_delta < tolerance:
            break

    # Populate final node values
    for nid, tau in tau_map.items():
        if tau is None:
            node_values[nid] = None
        else:
            node_values[nid] = round(rho_current.get(nid, tau), 4)

    return Overlay(
        id=f"overlay-gradual_strength-{uuid4().hex[:8]}",
        kind=OverlayKind.GRADUAL_STRENGTH,
        params=opts,
        node_values=node_values,
        edge_values=edge_values,
        scale="continuous",
        domain=[0.0, 1.0],
        computed_at=datetime.now(timezone.utc),
        graph_version=graph.graph_version,
        incomplete_inputs=incomplete_inputs,
    )


def compute_modal_strength(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> Overlay:
    """Compute Propositional Modal Strength M(phi) overlay across nodes.

    Extracts authorial certainty M(phi) = tau_0 from nodes resolved via
    the ModalStrengthResolver (Structuralist syntax priors + System 1 Jev calibration).

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Optional parameter overrides.

    Returns
    -------
    Overlay
        Computed modal strength overlay.
    """
    node_values: dict[str, float | str | None] = {}
    edge_values: dict[str, float | str | None] = {}
    incomplete_inputs = 0

    for node in graph.nodes:
        val = (
            node.modal_strength
            if node.modal_strength is not None
            else (node.base_score if node.base_score is not None else node.plausibility)
        )
        if val is None:
            incomplete_inputs += 1
            node_values[node.id] = None
        else:
            node_values[node.id] = round(float(val), 4)

    return Overlay(
        id=f"overlay-modal_strength-{uuid4().hex[:8]}",
        kind=OverlayKind.MODAL_STRENGTH,
        params=params or {},
        node_values=node_values,
        edge_values=edge_values,
        scale="continuous",
        domain=[0.0, 1.0],
        computed_at=datetime.now(timezone.utc),
        graph_version=graph.graph_version,
        incomplete_inputs=incomplete_inputs,
    )


def _calculate_internal_correlation(graph: ig.Graph, community_attribute: str = "community") -> float:
    """Calculate the internal correlation cohesion of communities within a graph.

    Parameters
    ----------
    graph : ig.Graph
        Input igraph instance.
    community_attribute : str, default "community"
        Vertex attribute containing community assignment.

    Returns
    -------
    float
        Internal correlation score between 0.0 and 1.0.
    """
    if graph.vcount() == 0:
        return 0.0
    try:
        if community_attribute not in graph.vertex_attributes():
            return 0.85
        memberships = graph.vs[community_attribute]
        unique_comms = set(memberships)
        if len(unique_comms) <= 1:
            return float(round(max(0.0, min(1.0, graph.density())), 4))
        return float(round(max(0.0, min(1.0, graph.modularity(memberships))), 4))
    except Exception:
        return 0.85


def compute_internal_correlation(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> Overlay:
    """Compute internal correlation cohesion score for theoretical communities.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Optional parameters, such as 'community_attribute' (default 'community').

    Returns
    -------
    Overlay
        Computed internal correlation overlay.
    """
    opts = params or {}
    community_attr = str(opts.get("community_attribute", "community"))

    if not graph.nodes:
        return Overlay(
            id=f"overlay-internal_correlation-{uuid4().hex[:8]}",
            kind=OverlayKind.INTERNAL_CORRELATION,
            params={"score": 0.0, **opts},
            node_values={},
            edge_values={},
            scale="continuous",
            domain=[0.0, 1.0],
            computed_at=datetime.now(timezone.utc),
            graph_version=graph.graph_version,
            incomplete_inputs=0,
        )

    g = ig.Graph(directed=True)
    g.add_vertices(len(graph.nodes))
    node_id_to_idx = {node.id: idx for idx, node in enumerate(graph.nodes)}
    g.vs["name"] = [node.id for node in graph.nodes]

    # Assign community attribute from props or partition or fallback to component
    communities: list[str] = []
    for idx, node in enumerate(graph.nodes):
        comm = node.props.get(community_attr)
        if comm is None:
            comm = node.partition or "default"
        communities.append(str(comm))
    g.vs[community_attr] = communities

    # Add edges
    edges_to_add: list[tuple[int, int]] = []
    for edge in graph.edges:
        src_idx = node_id_to_idx.get(edge.source)
        tgt_idx = node_id_to_idx.get(edge.target)
        if src_idx is not None and tgt_idx is not None:
            edges_to_add.append((src_idx, tgt_idx))
    g.add_edges(edges_to_add)

    score = float(_calculate_internal_correlation(g, community_attribute=community_attr))

    node_values: dict[str, float | str | None] = {
        node.id: communities[idx] for idx, node in enumerate(graph.nodes)
    }

    return Overlay(
        id=f"overlay-internal_correlation-{uuid4().hex[:8]}",
        kind=OverlayKind.INTERNAL_CORRELATION,
        params={"score": score, **opts},
        node_values=node_values,
        edge_values={},
        scale="continuous",
        domain=[0.0, 1.0],
        computed_at=datetime.now(timezone.utc),
        graph_version=graph.graph_version,
        incomplete_inputs=0,
    )


def compute_degree(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> Overlay:
    """Compute node degree centrality across the graph.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Optional parameters.

    Returns
    -------
    Overlay
        Computed degree overlay.
    """
    opts = params or {}
    degree_counts: dict[str, int] = {node.id: 0 for node in graph.nodes}

    for edge in graph.edges:
        if edge.source in degree_counts:
            degree_counts[edge.source] += 1
        if edge.target in degree_counts:
            degree_counts[edge.target] += 1

    node_values: dict[str, float | str | None] = {
        nid: float(cnt) for nid, cnt in degree_counts.items()
    }
    vals = [float(c) for c in degree_counts.values()] if degree_counts else [0.0]
    min_deg = min(vals) if vals else 0.0
    max_deg = max(vals) if vals else 0.0

    return Overlay(
        id=f"overlay-degree-{uuid4().hex[:8]}",
        kind=OverlayKind.DEGREE,
        params=opts,
        node_values=node_values,
        edge_values={},
        scale="continuous",
        domain=[min_deg, max_deg],
        computed_at=datetime.now(timezone.utc),
        graph_version=graph.graph_version,
        incomplete_inputs=0,
    )


def compute_component(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> Overlay:
    """Compute weakly connected components of the graph using epistemetrics.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Optional parameters.

    Returns
    -------
    Overlay
        Computed component overlay.
    """
    opts = params or {}
    if not graph.nodes:
        return Overlay(
            id=f"overlay-component-{uuid4().hex[:8]}",
            kind=OverlayKind.COMPONENT,
            params=opts,
            node_values={},
            edge_values={},
            scale="categorical",
            domain=[],
            computed_at=datetime.now(timezone.utc),
            graph_version=graph.graph_version,
            incomplete_inputs=0,
        )

    res = run_epistemetrics_wcc(graph, params=opts)
    node_values: dict[str, float | str | None] = {
        nid: f"c_{part}" for nid, part in res.node_to_partition.items()
    }
    for node in graph.nodes:
        if node.id not in node_values:
            node_values[node.id] = "c_0"

    domain_vals = sorted(list({str(v) for v in node_values.values() if v is not None}))

    return Overlay(
        id=f"overlay-component-{uuid4().hex[:8]}",
        kind=OverlayKind.COMPONENT,
        params={"component_count": res.num_partitions, "backend": res.backend, **opts},
        node_values=node_values,
        edge_values={},
        scale="categorical",
        domain=domain_vals,
        computed_at=datetime.now(timezone.utc),
        graph_version=graph.graph_version,
        incomplete_inputs=0,
    )


def compute_pagerank(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> Overlay:
    """Compute PageRank centrality scores across the graph using epistemetrics.

    Computes directed PageRank scores using the epistemetrics engine, taking into
    account edge weights when present. Falls back to igraph if engine='igraph'.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Optional parameters such as 'damping' (default 0.85).

    Returns
    -------
    Overlay
        Computed PageRank continuous overlay.
    """
    opts = params or {}
    damping = float(opts.get("damping", 0.85))

    if not graph.nodes:
        return Overlay(
            id=f"overlay-pagerank-{uuid4().hex[:8]}",
            kind=OverlayKind.PAGERANK,
            params={"damping": damping, **opts},
            node_values={},
            edge_values={},
            scale="continuous",
            domain=[0.0, 1.0],
            computed_at=datetime.now(timezone.utc),
            graph_version=graph.graph_version,
            incomplete_inputs=0,
        )

    if opts.get("engine") == "igraph":
        g = ig.Graph(directed=True)
        g.add_vertices(len(graph.nodes))
        node_id_to_idx = {node.id: idx for idx, node in enumerate(graph.nodes)}
        g.vs["name"] = [node.id for node in graph.nodes]

        edges_to_add: list[tuple[int, int]] = []
        weights: list[float] = []
        for edge in graph.edges:
            src_idx = node_id_to_idx.get(edge.source)
            tgt_idx = node_id_to_idx.get(edge.target)
            if src_idx is not None and tgt_idx is not None:
                edges_to_add.append((src_idx, tgt_idx))
                w = float(edge.weight) if edge.weight is not None else 1.0
                weights.append(max(0.01, w))
        g.add_edges(edges_to_add)

        try:
            pr_scores = g.pagerank(directed=True, damping=damping, weights=weights if weights else None)
        except Exception:
            pr_scores = g.pagerank(directed=True, damping=damping)

        node_values: dict[str, float | str | None] = {
            node.id: round(float(pr_scores[idx]), 6)
            for idx, node in enumerate(graph.nodes)
        }
        vals = [float(v) for v in node_values.values() if v is not None]
        min_val = min(vals) if vals else 0.0
        max_val = max(vals) if vals else 1.0
        backend = "igraph"
    else:
        res = run_epistemetrics_pagerank(graph, params={"damping": damping, **opts})
        node_values = {
            nid: round(score, 6) for nid, score in res.scores.items()
        }
        min_val = round(res.min_score, 6)
        max_val = round(res.max_score, 6)
        backend = res.backend

    return Overlay(
        id=f"overlay-pagerank-{uuid4().hex[:8]}",
        kind=OverlayKind.PAGERANK,
        params={"damping": damping, "backend": backend, **opts},
        node_values=node_values,
        edge_values={},
        scale="continuous",
        domain=[min_val, max_val],
        computed_at=datetime.now(timezone.utc),
        graph_version=graph.graph_version,
        incomplete_inputs=0,
    )


def compute_leiden(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> Overlay:
    """Compute Leiden community detection across the graph view using igraph.

    Partitions the graph nodes into disjoint communities maximizing modularity
    via the Leiden algorithm. Takes into account edge weights when present.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Optional algorithmic parameters:
        - gamma / resolution: float (default 1.0)
        - max_levels / n_iterations: int (default 10)
        - objective_function: str (default "modularity")

    Returns
    -------
    Overlay
        Computed Leiden community overlay with categorical scale.
    """
    opts = params or {}
    resolution = float(opts.get("gamma", opts.get("resolution", 1.0)))
    n_iterations = int(opts.get("max_levels", opts.get("n_iterations", 10)))
    objective = str(opts.get("objective_function", "modularity"))

    if not graph.nodes:
        return Overlay(
            id=f"overlay-leiden-{uuid4().hex[:8]}",
            kind=OverlayKind.LEIDEN,
            params={"gamma": resolution, "max_levels": n_iterations, **opts},
            node_values={},
            edge_values={},
            scale="categorical",
            domain=[],
            computed_at=datetime.now(timezone.utc),
            graph_version=graph.graph_version,
            incomplete_inputs=0,
        )

    # Leiden in igraph works on undirected graphs
    g = ig.Graph(directed=False)
    g.add_vertices(len(graph.nodes))
    node_id_to_idx = {node.id: idx for idx, node in enumerate(graph.nodes)}
    g.vs["name"] = [node.id for node in graph.nodes]

    edges_to_add: list[tuple[int, int]] = []
    weights: list[float] = []
    for edge in graph.edges:
        src_idx = node_id_to_idx.get(edge.source)
        tgt_idx = node_id_to_idx.get(edge.target)
        if src_idx is not None and tgt_idx is not None:
            edges_to_add.append((src_idx, tgt_idx))
            w = float(edge.weight) if edge.weight is not None else 1.0
            weights.append(max(0.01, w))
    g.add_edges(edges_to_add)

    try:
        partition = g.community_leiden(
            objective_function=objective,
            weights=weights if weights else None,
            resolution=resolution,
            n_iterations=n_iterations,
        )
        membership = partition.membership
    except Exception as exc:
        logger.warning("igraph community_leiden failed, falling back to components: %s", exc)
        cl = g.connected_components()
        membership = cl.membership

    node_values: dict[str, float | str | None] = {
        node.id: str(membership[idx])
        for idx, node in enumerate(graph.nodes)
    }
    unique_communities = sorted(list({str(v) for v in node_values.values() if v is not None}))

    return Overlay(
        id=f"overlay-leiden-{uuid4().hex[:8]}",
        kind=OverlayKind.LEIDEN,
        params={"gamma": resolution, "max_levels": n_iterations, **opts},
        node_values=node_values,
        edge_values={},
        scale="categorical",
        domain=unique_communities,
        computed_at=datetime.now(timezone.utc),
        graph_version=graph.graph_version,
        incomplete_inputs=0,
    )


def compute_local_gradual_strength(
    graph: GraphView,
    focus_node_id: str,
    params: dict[str, Any] | None = None,
    execution_id: str | None = None,
) -> MetricResult:
    """Compute local gradual strength acceptability score and upstream causal explanations.

    Extracts the upstream induced neighborhood backwards from `focus_node_id` up to
    `max_depth` hops, solves iterative QBAF aggregation semantics:

    .. math::
        \\alpha(a_i) = \\sum_{(a_j, a_i) \\in \\mathcal{R}_{sup}} \\rho(a_j) \\cdot \\phi(a_j, a_i)
        - \\sum_{(a_k, a_i) \\in \\mathcal{R}_{att}} \\rho(a_k) \\cdot \\phi(a_k, a_i)

    Identifies multi-role nodes reached via conflicting pathways (both support and attack),
    computes marginal net contributions via ablation, and generates detailed edge annotations.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view.
    focus_node_id : str
        Target node identifier to evaluate.
    params : dict of str to Any, optional
        Algorithmic parameters such as 'max_depth' (default 2), 'tolerance' (default 1e-4),
        and 'iterations' (default 20).
    execution_id : str or None, optional
        Unique execution id. If None, a random UUID is generated.

    Returns
    -------
    MetricResult
        Complete calculation result with affected nodes, affected edges, and summary.
    """
    opts = params or {}
    max_depth = int(opts.get("max_depth", 2))
    tolerance = float(opts.get("tolerance", 1e-4))
    max_iterations = int(opts.get("iterations", 20))
    exec_id = execution_id or f"exec-{uuid4().hex[:8]}"

    start_time = datetime.now(timezone.utc)
    warnings: list[str] = []

    # Verify focus node exists
    nodes_by_id = {n.id: n for n in graph.nodes}
    if focus_node_id not in nodes_by_id:
        return MetricResult(
            execution_id=exec_id,
            metric_id="gradual_strength_local",
            scope=MetricScope.SINGLE_NODE,
            focus_node_id=focus_node_id,
            result_value=0.0,
            graph_revision=graph.graph_version,
            duration_ms=0,
            summary={
                "focus_strength_rho": 0.0,
                "sum_support_weight": 0.0,
                "sum_attack_weight": 0.0,
                "missing_tau_count": 0,
                "missing_phi_count": 0,
                "tree_depth": 0,
            },
            affected_nodes={},
            affected_edges=[],
            warnings=[f"Focus node '{focus_node_id}' not found in current graph projection."],
            computed_at=start_time,
        )

    # Build backward incoming edge index: target -> list of incoming edges
    incoming_edges_map: dict[str, list[Any]] = defaultdict(list)
    for edge in graph.edges:
        incoming_edges_map[edge.target].append(edge)

    # Upstream BFS traversal from focus node
    visited_nodes: set[str] = {focus_node_id}
    node_distance: dict[str, int] = {focus_node_id: 0}
    traversed_edges: list[Any] = []
    seen_edge_ids: set[str] = set()

    queue: deque[tuple[str, int]] = deque([(focus_node_id, 0)])
    max_hop_reached = 0

    while queue:
        curr_id, curr_dist = queue.popleft()
        if curr_dist >= max_depth:
            continue

        for edge in incoming_edges_map.get(curr_id, []):
            if edge.id not in seen_edge_ids:
                seen_edge_ids.add(edge.id)
                traversed_edges.append(edge)

            src_id = edge.source
            hop = curr_dist + 1
            if hop > max_hop_reached:
                max_hop_reached = hop

            if src_id not in node_distance or hop < node_distance[src_id]:
                node_distance[src_id] = hop

            if src_id not in visited_nodes:
                visited_nodes.add(src_id)
                queue.append((src_id, hop))

    # Relevant nodes and missing counts
    sub_nodes = {nid: nodes_by_id[nid] for nid in visited_nodes if nid in nodes_by_id}
    missing_tau_count = sum(1 for n in sub_nodes.values() if n.plausibility is None)
    missing_phi_count = sum(1 for e in traversed_edges if e.weight is None)

    if missing_tau_count > 0:
        warnings.append(
            f"{missing_tau_count} node(s) had unassigned prior plausibility (tau); defaulted to 0.5."
        )
    if missing_phi_count > 0:
        warnings.append(
            f"{missing_phi_count} edge(s) had unassigned weight (phi); defaulted to 1.0."
        )

    # Plausibility priors
    base_tau: dict[str, float] = {
        nid: float(n.plausibility) if n.plausibility is not None else 0.5
        for nid, n in sub_nodes.items()
    }

    # Edge parameters: weights and polarities
    edge_weights: dict[str, float] = {
        e.id: float(e.weight) if e.weight is not None else 1.0
        for e in traversed_edges
    }

    # Solves QBAF iterative gradual semantics on induced subgraph
    def _solve_qbaf(
        active_tau: dict[str, float],
        disabled_node_id: str | None = None,
    ) -> tuple[dict[str, float], int, bool]:
        rho: dict[str, float] = {
            nid: 0.0 if nid == disabled_node_id else val
            for nid, val in active_tau.items()
        }

        iterations = 0
        converged = False

        for it in range(max_iterations):
            iterations = it + 1
            max_delta = 0.0
            rho_next = dict(rho)

            for nid in sub_nodes:
                if nid == disabled_node_id:
                    rho_next[nid] = 0.0
                    continue

                tau = active_tau.get(nid, 0.5)
                alpha = 0.0

                for edge in incoming_edges_map.get(nid, []):
                    if edge.id not in seen_edge_ids:
                        continue
                    src = edge.source
                    if src == disabled_node_id or src not in rho:
                        continue

                    phi = edge_weights.get(edge.id, 1.0)
                    pol = edge.polarity
                    if pol is None:
                        # Infer polarity from relationship type if unmapped
                        if edge.type in ("SUPPORTS", "CONTAINS"):
                            pol = 1
                        elif edge.type in ("ATTACKS", "UNDERCUTS"):
                            pol = -1
                        else:
                            pol = 0

                    src_score = rho.get(src, 0.5)
                    if pol > 0:
                        alpha += src_score * phi
                    elif pol < 0:
                        alpha -= src_score * phi

                if alpha >= 0.0:
                    score = tau + (1.0 - tau) * (alpha / (1.0 + alpha))
                else:
                    score = tau / (1.0 + abs(alpha))

                clamped = max(0.0, min(1.0, score))
                delta = abs(clamped - rho.get(nid, tau))
                if delta > max_delta:
                    max_delta = delta
                rho_next[nid] = clamped

            rho = rho_next
            if max_delta < tolerance:
                converged = True
                break

        return rho, iterations, converged

    # Baseline calculation
    baseline_rho, iters_run, has_converged = _solve_qbaf(base_tau)
    if not has_converged and max_iterations > 1:
        warnings.append(
            f"Iterative gradual strength did not converge within {max_iterations} iterations (tolerance {tolerance})."
        )

    focus_rho = baseline_rho.get(focus_node_id, 0.5)

    # Multi-role pathway analysis via directed path traversal
    # Build forward graph within traversed edges: source -> list of (target, polarity)
    forward_adj: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for edge in traversed_edges:
        pol = edge.polarity
        if pol is None:
            pol = 1 if edge.type == "SUPPORTS" else (-1 if edge.type in ("ATTACKS", "UNDERCUTS") else 0)
        forward_adj[edge.source].append((edge.target, pol))

    node_roles: dict[str, set[str]] = defaultdict(set)

    def _find_paths(curr: str, target: str, current_sign: int, depth_left: int, visited_path: set[str]) -> None:
        if curr == target:
            if current_sign > 0:
                node_roles[path_origin].add("support")
            elif current_sign < 0:
                node_roles[path_origin].add("attack")
            return

        if depth_left <= 0:
            return

        for next_node, edge_pol in forward_adj.get(curr, []):
            if next_node not in visited_path and edge_pol != 0:
                visited_path.add(next_node)
                _find_paths(
                    next_node,
                    target,
                    current_sign * (1 if edge_pol > 0 else -1),
                    depth_left - 1,
                    visited_path,
                )
                visited_path.remove(next_node)

    for nid in sub_nodes:
        if nid == focus_node_id:
            continue
        path_origin = nid
        _find_paths(nid, focus_node_id, 1, max_depth, {nid})

    # Build affected nodes with marginal contributions
    affected_nodes: dict[str, AffectedNodeDetail] = {}
    for nid, node in sub_nodes.items():
        if nid == focus_node_id:
            affected_nodes[nid] = AffectedNodeDetail(
                roles=["focus"],
                net_contribution=round(focus_rho, 4),
                metadata={"tau": base_tau.get(nid, 0.5), "rho": round(focus_rho, 4)},
            )
            continue

        raw_roles = sorted(list(node_roles.get(nid, set())))
        if not raw_roles:
            # Fallback based on incoming edge type if path sign unresolved
            raw_roles = ["neutral"]

        # Marginal ablation: difference in focus strength without this node
        ablated_rho, _, _ = _solve_qbaf(base_tau, disabled_node_id=nid)
        marginal_delta = focus_rho - ablated_rho.get(focus_node_id, focus_rho)

        affected_nodes[nid] = AffectedNodeDetail(
            roles=raw_roles,
            net_contribution=round(marginal_delta, 4),
            metadata={
                "tau": base_tau.get(nid, 0.5),
                "rho": round(baseline_rho.get(nid, 0.5), 4),
                "hop_distance": node_distance.get(nid, 1),
            },
        )

    # Build affected edges with causal contribution
    affected_edges: list[AffectedEdgeDetail] = []
    sum_support_weight = 0.0
    sum_attack_weight = 0.0

    for edge in traversed_edges:
        pol = edge.polarity
        if pol is None:
            pol = 1 if edge.type == "SUPPORTS" else (-1 if edge.type in ("ATTACKS", "UNDERCUTS") else 0)

        role = "undercut" if edge.type == "UNDERCUTS" else ("support" if pol > 0 else ("attack" if pol < 0 else "neutral"))
        w = edge_weights.get(edge.id, 1.0)
        if pol > 0:
            sum_support_weight += w
        elif pol < 0:
            sum_attack_weight += w

        src_score = baseline_rho.get(edge.source, 0.5)
        signed_contrib = round(src_score * w * (1.0 if pol > 0 else (-1.0 if pol < 0 else 0.0)), 4)
        hop = node_distance.get(edge.source, 1)

        affected_edges.append(
            AffectedEdgeDetail(
                source_node_id=edge.source,
                target_node_id=edge.target,
                relationship_id=edge.id,
                role=role,
                weight=round(w, 4),
                polarity=pol,
                hop_distance=hop,
                contribution=signed_contrib,
                metadata={
                    "type": edge.type,
                    "source_rho": round(src_score, 4),
                },
            )
        )

    end_time = datetime.now(timezone.utc)
    duration_ms = max(1, int((end_time - start_time).total_seconds() * 1000))

    return MetricResult(
        execution_id=exec_id,
        metric_id="gradual_strength_local",
        scope=MetricScope.SINGLE_NODE,
        focus_node_id=focus_node_id,
        result_value=round(focus_rho, 4),
        graph_revision=graph.graph_version,
        duration_ms=duration_ms,
        summary={
            "focus_strength_rho": round(focus_rho, 4),
            "sum_support_weight": round(sum_support_weight, 4),
            "sum_attack_weight": round(sum_attack_weight, 4),
            "missing_tau_count": missing_tau_count,
            "missing_phi_count": missing_phi_count,
            "tree_depth": max_hop_reached,
            "iterations": iters_run,
            "converged": has_converged,
            "affected_node_count": len(affected_nodes),
            "affected_edge_count": len(affected_edges),
        },
        affected_nodes=affected_nodes,
        affected_edges=affected_edges,
        warnings=warnings,
        computed_at=end_time,
    )


def compute_tenability(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> Overlay:
    """Compute epistemic tenability evaluation overlay across the graph view.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Optional algorithmic parameters:
        - theory_id : str or None, default None (all claimant theories)
        - tenability_threshold : float, default 0.5

    Returns
    -------
    Overlay
        Computed tenability overlay with continuous scale in [0.0, 1.0].
    """
    opts = params or {}
    theory_filter = opts.get("theory_id")
    threshold = float(opts.get("tenability_threshold", 0.5))

    node_values: dict[str, float | str | None] = {}
    edge_values: dict[str, float | str | None] = {}
    incomplete_inputs = 0

    for node in graph.nodes:
        tenab = node.tenability or node.props.get("tenability")
        if isinstance(tenab, dict):
            t_id = tenab.get("theory_id")
            if theory_filter and t_id and t_id != theory_filter:
                continue
            score = tenab.get("local_score")
            if score is None:
                score = tenab.get("aggregated_score")
            if score is not None:
                node_values[node.id] = round(float(score), 4)
            else:
                is_tenable = tenab.get("is_tenable")
                if is_tenable is not None:
                    node_values[node.id] = 1.0 if is_tenable else 0.0
                else:
                    incomplete_inputs += 1
        else:
            if node.layer == Layer.L3:
                if node.plausibility is not None:
                    node_values[node.id] = round(float(node.plausibility), 4)
                else:
                    incomplete_inputs += 1

    for edge in graph.edges:
        tenab = edge.tenability or edge.props.get("tenability")
        if tenab is not None:
            try:
                edge_values[edge.id] = round(float(tenab), 4)
            except (ValueError, TypeError):
                pass
        elif edge.weight is not None:
            edge_values[edge.id] = round(float(edge.weight), 4)

    return Overlay(
        id=f"overlay-tenability-{uuid4().hex[:8]}",
        kind=OverlayKind.TENABILITY,
        params=opts,
        node_values=node_values,
        edge_values=edge_values,
        scale="continuous",
        domain=[0.0, 1.0],
        computed_at=datetime.now(timezone.utc),
        graph_version=graph.graph_version,
        incomplete_inputs=incomplete_inputs,
    )


def graph_view_to_networkx(
    graph: GraphView,
    *,
    directed: bool = True,
) -> nx.DiGraph | nx.Graph:
    """Convert a studio GraphView instance into a NetworkX graph for epistemetrics.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to convert.
    directed : bool, default True
        Whether to instantiate a directed DiGraph (True) or undirected Graph (False).

    Returns
    -------
    nx.DiGraph | nx.Graph
        Populated NetworkX graph with node and edge attributes.
    """
    g: nx.DiGraph | nx.Graph = nx.DiGraph() if directed else nx.Graph()

    for node in graph.nodes:
        attrs: dict[str, Any] = {
            "label": node.label,
            "type": node.type,
            "layer": int(node.layer),
            "degree": node.degree,
            "resolved": node.resolved,
            "synthetic": node.synthetic,
        }
        if node.partition is not None:
            attrs["partition"] = node.partition
        if node.plausibility is not None:
            attrs["plausibility"] = float(node.plausibility)
            attrs["tau"] = float(node.plausibility)
        if node.confidence is not None:
            attrs["confidence"] = float(node.confidence)
        if node.props:
            attrs.update(node.props)
        g.add_node(node.id, **attrs)

    for edge in graph.edges:
        e_attrs: dict[str, Any] = {
            "id": edge.id,
            "type": edge.type,
            "layer": int(edge.layer),
        }
        if edge.polarity is not None:
            e_attrs["polarity"] = edge.polarity
        if edge.weight is not None:
            w = float(edge.weight)
            e_attrs["weight"] = max(0.0001, w)
            e_attrs["phi"] = w
        else:
            e_attrs["weight"] = 1.0
        if edge.confidence is not None:
            e_attrs["confidence"] = float(edge.confidence)
        if edge.props:
            e_attrs.update(edge.props)

        if not g.has_node(edge.source):
            g.add_node(edge.source)
        if not g.has_node(edge.target):
            g.add_node(edge.target)

        g.add_edge(edge.source, edge.target, **e_attrs)

    return g


def run_epistemetrics_pagerank(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> CentralityResult:
    """Execute PageRank centrality using the epistemetrics library.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Algorithmic options:
        - damping / damping_factor : float (default 0.85)
        - max_iterations / max_iter : int (default 100)
        - tolerance : float (default 1e-4)

    Returns
    -------
    CentralityResult
        Computed PageRank results from epistemetrics.
    """
    opts = params or {}
    damping = float(opts.get("damping", opts.get("damping_factor", 0.85)))
    max_iter = int(opts.get("max_iterations", opts.get("max_iter", 100)))
    tolerance = float(opts.get("tolerance", 1e-4))
    nx_g = graph_view_to_networkx(graph, directed=True)
    has_weights = any(e.weight is not None for e in graph.edges)
    return page_rank(
        nx_g,
        damping_factor=damping,
        max_iter=max_iter,
        tolerance=tolerance,
        weight_property="weight" if has_weights else None,
    )


def run_epistemetrics_wcc(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> PartitionResult:
    """Detect weakly connected components using the epistemetrics library.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Algorithmic options.

    Returns
    -------
    PartitionResult
        Disjoint component sets and node partition map from epistemetrics.
    """
    nx_g = graph_view_to_networkx(graph, directed=True)
    return weakly_connected_components(nx_g)


def run_epistemetrics_louvain(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> PartitionResult:
    """Detect modular communities using Louvain via the epistemetrics library.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Algorithmic options:
        - resolution / gamma : float (default 1.0)
        - seed : int | None (default None)

    Returns
    -------
    PartitionResult
        Detected community partitions from epistemetrics.
    """
    opts = params or {}
    resolution = float(opts.get("resolution", opts.get("gamma", 1.0)))
    seed = opts.get("seed")
    has_weights = any(e.weight is not None for e in graph.edges)
    nx_g = graph_view_to_networkx(graph, directed=True)
    return louvain_communities(
        nx_g,
        resolution=resolution,
        seed=seed,
        weight_property="weight" if has_weights else None,
    )


def run_epistemetrics_betweenness(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> CentralityResult:
    """Execute betweenness centrality using the epistemetrics library.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Algorithmic options:
        - normalized : bool (default True)

    Returns
    -------
    CentralityResult
        Betweenness centrality results from epistemetrics.
    """
    opts = params or {}
    normalized = bool(opts.get("normalized", True))
    has_weights = any(e.weight is not None for e in graph.edges)
    nx_g = graph_view_to_networkx(graph, directed=True)
    return betweenness_centrality(
        nx_g,
        normalized=normalized,
        weight_property="weight" if has_weights else None,
    )


def run_epistemetrics_eigenvector(
    graph: GraphView,
    params: dict[str, Any] | None = None,
) -> CentralityResult:
    """Execute eigenvector centrality using the epistemetrics library.

    Parameters
    ----------
    graph : GraphView
        The graph snapshot view to analyze.
    params : dict of str to Any, optional
        Algorithmic options:
        - max_iterations / max_iter : int (default 100)
        - tolerance : float (default 1e-4)

    Returns
    -------
    CentralityResult
        Eigenvector centrality results from epistemetrics.
    """
    opts = params or {}
    max_iter = int(opts.get("max_iterations", opts.get("max_iter", 100)))
    tolerance = float(opts.get("tolerance", 1e-4))
    has_weights = any(e.weight is not None for e in graph.edges)
    nx_g = graph_view_to_networkx(graph, directed=True)
    return eigenvector_centrality(
        nx_g,
        max_iter=max_iter,
        tolerance=tolerance,
        weight_property="weight" if has_weights else None,
    )



