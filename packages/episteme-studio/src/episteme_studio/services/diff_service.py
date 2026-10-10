"""Domain service computing semantic and structural diffs between two pipeline runs."""

from __future__ import annotations

from typing import Any

from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.domain.diff import (
    ConfigDeltaItem,
    DiffKPIs,
    EdgeDiffStatus,
    GraphDiffView,
    NodeDiffStatus,
    PolarityInversion,
)
from episteme_studio.domain.graph import GraphView, Layer, StudioEdge, StudioNode


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Recursively flatten nested dictionary keys into dot-separated paths.

    Parameters
    ----------
    d : dict of str to Any
        Dictionary to flatten.
    prefix : str, default ""
        Current path prefix for recursive invocations.

    Returns
    -------
    dict of str to Any
        Flattened key-value map.
    """
    items: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            items.update(_flatten_dict(v, key))
        else:
            items[key] = v
    return items


def _categorize_config_key(key: str) -> str:
    """Categorize configuration dot-path into functional tiers.

    Parameters
    ----------
    key : str
        Dot-separated configuration key.

    Returns
    -------
    str
        One of 'models', 'prompts', 'phase', or 'general'.
    """
    lower = key.lower()
    if lower.startswith("models") or "model" in lower:
        return "models"
    if lower.startswith("prompts") or "prompt" in lower:
        return "prompts"
    if lower.startswith("phase") or "phase" in lower:
        return "phase"
    return "general"


class DiffService:
    """Orchestrates deterministic run-to-run diff computation over the artifact store.

    Parameters
    ----------
    reader : ArtifactReader
        Artifact reader adapter providing access to on-disk manifests and graphs.
    """

    def __init__(self, reader: ArtifactReader) -> None:
        self.reader = reader

    def compute_run_diff(
        self,
        base_run_id: str,
        target_run_id: str,
        weight_shift_threshold: float = 0.15,
    ) -> GraphDiffView:
        """Compute the full topological and semantic difference between Run A and Run B.

        Parameters
        ----------
        base_run_id : str
            Unique run ID for baseline Run A.
        target_run_id : str
            Unique run ID for candidate Run B.
        weight_shift_threshold : float, default 0.15
            Absolute weight delta threshold to qualify an edge as 'weight_shifted'.

        Returns
        -------
        GraphDiffView
            Unified diff view containing union topology, status classifications,
            polarity inversions, config deltas, and summary KPIs.

        Raises
        ------
        FileNotFoundError
            If either run manifest or artifact directory is missing.
        """
        graph_a = self.reader.get_graph(base_run_id)
        graph_b = self.reader.get_graph(target_run_id)

        detail_a = self.reader.get_run(base_run_id)
        detail_b = self.reader.get_run(target_run_id)

        if detail_a is None:
            raise FileNotFoundError(f"Baseline run '{base_run_id}' not found.")
        if detail_b is None:
            raise FileNotFoundError(f"Candidate run '{target_run_id}' not found.")

        # 1. Node Diffing by stable identity_key / id
        nodes_a: dict[str, StudioNode] = {n.id: n for n in graph_a.nodes}
        nodes_b: dict[str, StudioNode] = {n.id: n for n in graph_b.nodes}

        all_node_ids = set(nodes_a.keys()) | set(nodes_b.keys())
        node_diff: dict[str, NodeDiffStatus] = {}
        union_nodes: list[StudioNode] = []

        nodes_retained = 0
        nodes_gained = 0
        nodes_lost = 0

        for nid in all_node_ids:
            in_a = nid in nodes_a
            in_b = nid in nodes_b

            if in_a and in_b:
                node_diff[nid] = NodeDiffStatus.RETAINED
                nodes_retained += 1
                # Prefer candidate representation for updated confidence/labels
                union_nodes.append(nodes_b[nid])
            elif in_b:
                node_diff[nid] = NodeDiffStatus.GAINED
                nodes_gained += 1
                union_nodes.append(nodes_b[nid])
            else:
                node_diff[nid] = NodeDiffStatus.LOST
                nodes_lost += 1
                union_nodes.append(nodes_a[nid])

        # 2. Edge Diffing by endpoints and semantic polarities
        # Map (source, target) -> edge
        endpoints_a: dict[tuple[str, str], StudioEdge] = {(e.source, e.target): e for e in graph_a.edges}
        endpoints_b: dict[tuple[str, str], StudioEdge] = {(e.source, e.target): e for e in graph_b.edges}

        all_pairs = set(endpoints_a.keys()) | set(endpoints_b.keys())
        edge_diff: dict[str, EdgeDiffStatus] = {}
        polarity_inversions: list[PolarityInversion] = []
        union_edges: list[StudioEdge] = []

        edges_retained = 0
        edges_gained = 0
        edges_lost = 0

        # Also track by individual edge id for direct frontend lookups
        for src, tgt in all_pairs:
            in_a = (src, tgt) in endpoints_a
            in_b = (src, tgt) in endpoints_b

            if in_a and in_b:
                edge_a = endpoints_a[(src, tgt)]
                edge_b = endpoints_b[(src, tgt)]
                canon_edge_id = edge_b.id

                # Check for Polarity Inversion (e.g. +1 vs -1)
                pol_a = edge_a.polarity
                pol_b = edge_b.polarity
                is_inverted = pol_a is not None and pol_b is not None and (pol_a * pol_b < 0)

                if is_inverted:
                    edge_diff[canon_edge_id] = EdgeDiffStatus.POLARITY_INVERTED
                    edge_diff[edge_a.id] = EdgeDiffStatus.POLARITY_INVERTED
                    src_label = nodes_b.get(src, nodes_a.get(src)).label if (src in nodes_b or src in nodes_a) else src
                    tgt_label = nodes_b.get(tgt, nodes_a.get(tgt)).label if (tgt in nodes_b or tgt in nodes_a) else tgt

                    polarity_inversions.append(
                        PolarityInversion(
                            edge_id=canon_edge_id,
                            source=src,
                            target=tgt,
                            source_label=src_label,
                            target_label=tgt_label,
                            predicate_a=edge_a.type,
                            polarity_a=pol_a,
                            weight_a=edge_a.weight or edge_a.confidence,
                            predicate_b=edge_b.type,
                            polarity_b=pol_b,
                            weight_b=edge_b.weight or edge_b.confidence,
                            scope=edge_b.props.get("scope", "global"),
                        )
                    )
                    edges_retained += 1
                    union_edges.append(edge_b)

                else:
                    # Check for weight or confidence shift
                    w_a = edge_a.weight if edge_a.weight is not None else edge_a.confidence
                    w_b = edge_b.weight if edge_b.weight is not None else edge_b.confidence
                    if w_a is not None and w_b is not None and abs(w_b - w_a) >= weight_shift_threshold:
                        edge_diff[canon_edge_id] = EdgeDiffStatus.WEIGHT_SHIFTED
                        edge_diff[edge_a.id] = EdgeDiffStatus.WEIGHT_SHIFTED
                    else:
                        edge_diff[canon_edge_id] = EdgeDiffStatus.RETAINED
                        edge_diff[edge_a.id] = EdgeDiffStatus.RETAINED
                    edges_retained += 1
                    union_edges.append(edge_b)

            elif in_b:
                edge_b = endpoints_b[(src, tgt)]
                edge_diff[edge_b.id] = EdgeDiffStatus.GAINED
                edges_gained += 1
                union_edges.append(edge_b)
            else:
                edge_a = endpoints_a[(src, tgt)]
                edge_diff[edge_a.id] = EdgeDiffStatus.LOST
                edges_lost += 1
                union_edges.append(edge_a)

        # 3. Argument Divergence (Gradual Strength Δρ)
        rho_deltas: dict[str, float] = {}
        max_rho_drift = 0.0
        for nid in all_node_ids:
            if nid in nodes_a and nid in nodes_b:
                node_a = nodes_a[nid]
                node_b = nodes_b[nid]
                if node_a.layer == Layer.L3:
                    # Check for explicit rho or plausibility
                    rho_a = node_a.props.get("rho", node_a.plausibility)
                    rho_b = node_b.props.get("rho", node_b.plausibility)
                    if isinstance(rho_a, (int, float)) and isinstance(rho_b, (int, float)):
                        delta = round(float(rho_b) - float(rho_a), 4)
                        rho_deltas[nid] = delta
                        if abs(delta) > max_rho_drift:
                            max_rho_drift = abs(delta)

        # 4. Configuration Delta Isolation
        flat_cfg_a = _flatten_dict(detail_a.config_snapshot or {})
        flat_cfg_b = _flatten_dict(detail_b.config_snapshot or {})

        # Also incorporate resolved models dict
        for m_key, m_val in (detail_a.models or {}).items():
            flat_cfg_a[f"models.{m_key}"] = m_val
        for m_key, m_val in (detail_b.models or {}).items():
            flat_cfg_b[f"models.{m_key}"] = m_val

        all_cfg_keys = sorted(set(flat_cfg_a.keys()) | set(flat_cfg_b.keys()))
        config_diff: list[ConfigDeltaItem] = []

        for key in all_cfg_keys:
            val_a = flat_cfg_a.get(key)
            val_b = flat_cfg_b.get(key)
            if val_a != val_b:
                # Ignore dynamic runtime paths or timestamps
                if any(ignored in key.lower() for ignored in ("run_id", "timestamp", "created_at", "dir")):
                    continue
                config_diff.append(
                    ConfigDeltaItem(
                        path=key,
                        category=_categorize_config_key(key),
                        value_a=val_a,
                        value_b=val_b,
                    )
                )

        # 5. Summary Key Performance Indicators
        total_unique_nodes = len(all_node_ids)
        jaccard_nodes = (nodes_retained / total_unique_nodes) if total_unique_nodes > 0 else 1.0

        total_unique_pairs = len(all_pairs)
        jaccard_edges = (edges_retained / total_unique_pairs) if total_unique_pairs > 0 else 1.0

        l2_a = sum(1 for n in nodes_a.values() if n.layer == Layer.L2)
        l2_b = sum(1 for n in nodes_b.values() if n.layer == Layer.L2)
        l3_a = sum(1 for n in nodes_a.values() if n.layer == Layer.L3)
        l3_b = sum(1 for n in nodes_b.values() if n.layer == Layer.L3)

        kpis = DiffKPIs(
            nodes_retained=nodes_retained,
            nodes_gained=nodes_gained,
            nodes_lost=nodes_lost,
            edges_retained=edges_retained,
            edges_gained=edges_gained,
            edges_lost=edges_lost,
            polarity_inversions_count=len(polarity_inversions),
            jaccard_node_similarity=round(jaccard_nodes, 4),
            jaccard_edge_similarity=round(jaccard_edges, 4),
            l2_entity_delta=l2_b - l2_a,
            l3_atom_delta=l3_b - l3_a,
            max_rho_drift=round(max_rho_drift, 4),
        )

        # 6. Assemble Union GraphView
        layer_counts = {
            1: sum(1 for n in union_nodes if n.layer == Layer.L1),
            2: sum(1 for n in union_nodes if n.layer == Layer.L2),
            3: sum(1 for n in union_nodes if n.layer == Layer.L3),
        }

        union_graph = GraphView(
            nodes=union_nodes,
            edges=union_edges,
            source="artifacts",
            run_id=f"diff::{base_run_id}::{target_run_id}",
            graph_version=f"diff:{len(union_nodes)}:{len(union_edges)}",
            schema_version=graph_b.schema_version or graph_a.schema_version,
            truncated=False,
            dropped_count=0,
            unmapped_predicates=graph_b.unmapped_predicates or graph_a.unmapped_predicates,
            unresolved_count=graph_b.unresolved_count + graph_a.unresolved_count,
            layer_counts=layer_counts,
        )

        return GraphDiffView(
            run_a_id=base_run_id,
            run_b_id=target_run_id,
            union_graph=union_graph,
            node_diff=node_diff,
            edge_diff=edge_diff,
            polarity_inversions=polarity_inversions,
            rho_deltas=rho_deltas,
            config_diff=config_diff,
            kpis=kpis,
        )
