"""Poset Specialization Hierarchy and Model Subsumption Evaluation.

Operationalizes Task 2 of the Structuralist Theory-Net Benchmark (STNB):
1. Strict partial order verification (cycle-free DAG, transitivity, irreflexivity, antisymmetry).
2. Root Element Conformity: B(TN_pred) = {T_{0, gold}}.
3. Hierarchical Model Inheritance Subsumption:
   M_p(T_j) <= M_p(T_i) and M(T_j) < M(T_i) for T_i -alpha-> T_j.
4. Poset Transitive Reduction F1 (Precision, Recall, F1).
5. Specialization Reachability coverage and derivation path preservation.
"""

from __future__ import annotations

from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from epistemetrics.core.models import (
    NodeType,
    RelationType,
)
from epistemetrics.graph.theory_graph import TheoryGraph


class PosetEvaluationResult(BaseModel):
    """Evaluation result for specialization poset hierarchies and structural subsumption.

    Parameters
    ----------
    is_dag : bool
        True if the specialization relation forms a Directed Acyclic Graph.
    is_strict_partial_order : bool
        True if irreflexivity, antisymmetry, and DAG properties hold.
    has_unique_root : bool
        True if the graph possesses a unique greatest lower bound / root element.
    root_node : str | None
        Identifier of the unique root theory element if identified, else None.
    root_conformity : bool
        True if the predicted root matches the reference gold root element.
    hierarchical_subsumption_score : float
        Ratio of specialization edges satisfying model inheritance subsumption [0.0, 1.0].
    hierarchical_subsumption_valid : bool
        True if all evaluated specialization edges satisfy model inheritance subsumption.
    precision : float
        Transitive reduction edge precision in [0.0, 1.0].
    recall : float
        Transitive reduction edge recall in [0.0, 1.0].
    f1 : float
        Transitive reduction edge Poset F1 score in [0.0, 1.0].
    reachability_precision : float
        Transitive closure reachability path precision in [0.0, 1.0].
    reachability_recall : float
        Transitive closure reachability path recall in [0.0, 1.0].
    reachability_f1 : float
        Transitive closure reachability path F1 score in [0.0, 1.0].
    cycles : list[list[str]]
        List of detected elementary cycles if the graph violates DAG acyclicity.
    num_predicted_edges : int
        Number of specialization edges in the predicted graph.
    num_reference_edges : int
        Number of specialization edges in the reference graph.
    details : dict[str, Any]
        Detailed diagnostic and structural metadata.
    """

    model_config = ConfigDict(frozen=True)

    is_dag: bool = Field(..., description="Whether specialization relation is a DAG.")
    is_strict_partial_order: bool = Field(
        ..., description="Whether relation forms a strict partial order."
    )
    has_unique_root: bool = Field(
        ..., description="Whether a unique root element T_0 exists."
    )
    root_node: str | None = Field(
        default=None, description="Identifier of the identified root theory element."
    )
    root_conformity: bool = Field(
        ..., description="Whether predicted root matches gold standard root."
    )
    hierarchical_subsumption_score: float = Field(
        ..., description="Ratio of edges satisfying model inheritance subsumption."
    )
    hierarchical_subsumption_valid: bool = Field(
        ..., description="Whether all specialization edges satisfy subsumption."
    )
    precision: float = Field(
        ..., description="Poset transitive reduction precision."
    )
    recall: float = Field(
        ..., description="Poset transitive reduction recall."
    )
    f1: float = Field(..., description="Poset transitive reduction F1 score.")
    reachability_precision: float = Field(
        default=1.0, description="Reachability path precision."
    )
    reachability_recall: float = Field(
        default=1.0, description="Reachability path recall."
    )
    reachability_f1: float = Field(
        default=1.0, description="Reachability path F1 score."
    )
    cycles: list[list[str]] = Field(
        default_factory=list, description="Detected cycles violating DAG structure."
    )
    num_predicted_edges: int = Field(
        default=0, description="Number of predicted specialization edges."
    )
    num_reference_edges: int = Field(
        default=0, description="Number of reference specialization edges."
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic structural evaluation metadata."
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert result model to a serializable dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary representation of poset evaluation results.
        """
        return self.model_dump()

    def to_markdown(self) -> str:
        """Format the poset evaluation result as a Markdown report.

        Returns
        -------
        str
            GitHub-flavored Markdown report.
        """
        status_dag = "✅ PASSED (Acyclic DAG)" if self.is_dag else "❌ FAILED (Cycles Detected)"
        status_root = "✅ PASSED" if self.root_conformity else "❌ FAILED"
        status_subsume = "✅ PASSED" if self.hierarchical_subsumption_valid else "❌ FAILED"

        lines = [
            "# Specialization Poset Hierarchy Evaluation Report",
            "",
            f"- **DAG Property & Strict Partial Order:** {status_dag}",
            f"- **Root Element Conformity ($B(TN) = \\{{T_0\\}}$):** {status_root} (Root: `{self.root_node}`)",
            f"- **Hierarchical Model Inheritance Subsumption:** {status_subsume} ({self.hierarchical_subsumption_score:.2%})",
            "",
            "## Quantitative Benchmark Metrics",
            f"- **Poset Transitive Reduction F1:** {self.f1:.4f} (Precision: {self.precision:.4f}, Recall: {self.recall:.4f})",
            f"- **Specialization Reachability F1:** {self.reachability_f1:.4f} (Precision: {self.reachability_precision:.4f}, Recall: {self.reachability_recall:.4f})",
            f"- **Specialization Edge Counts:** Predicted = {self.num_predicted_edges}, Reference = {self.num_reference_edges}",
        ]

        if self.cycles:
            lines.append("")
            lines.append("## Detected Cycles")
            for cycle in self.cycles:
                lines.append(f"- ❌ Cycle: `{' -> '.join(cycle)}`")

        return "\n".join(lines)


def _is_specialization_edge(rel_val: Any) -> bool:
    """Determine whether an edge relation value represents specialization."""
    if isinstance(rel_val, RelationType):
        return rel_val == RelationType.SPECIALIZES
    if isinstance(rel_val, str):
        cleaned = rel_val.strip()
        if ":" in cleaned:
            cleaned = cleaned.split(":")[-1]
        cleaned = cleaned.lower().replace("-", "_")
        return cleaned in {"specializes", "specialization", "specialized_by"}
    return False


def extract_specialization_subgraph(graph: Any) -> nx.DiGraph:
    """Extract the directed specialization subgraph from a TheoryGraph or NetworkX graph.

    Preserves parent -> child orientation (T_i -> T_j where T_j specializes T_i).

    Parameters
    ----------
    graph : TheoryGraph or nx.DiGraph or nx.MultiDiGraph
        Source graph containing theory elements and structural relations.

    Returns
    -------
    nx.DiGraph
        Directed graph containing only specialization edges and involved nodes.
    """
    spec_graph = nx.DiGraph()

    if isinstance(graph, TheoryGraph):
        for nid, node in graph.nodes.items():
            if node.node_type == NodeType.THEORY_ELEMENT:
                spec_graph.add_node(nid, **node.attributes)

        for edge in graph.edges:
            if _is_specialization_edge(edge.relation_type) or _is_specialization_edge(
                edge.attributes.get("relation") or edge.attributes.get("label")
            ):
                spec_graph.add_edge(edge.source, edge.target, **edge.attributes)

        return spec_graph

    if isinstance(graph, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
        for nid, data in graph.nodes(data=True):
            n_type = str(data.get("node_type", data.get("type", data.get("label", ""))))
            if "theory_element" in n_type.lower() or "theoryelement" in n_type.lower():
                spec_graph.add_node(str(nid), **data)

        if graph.is_multigraph():
            for u, v, _k, data in graph.edges(keys=True, data=True):
                rel = data.get("relation_type", data.get("relation", data.get("label", "")))
                if _is_specialization_edge(rel):
                    spec_graph.add_edge(str(u), str(v), **data)
        else:
            for u, v, data in graph.edges(data=True):
                rel = data.get("relation_type", data.get("relation", data.get("label", "")))
                if _is_specialization_edge(rel):
                    spec_graph.add_edge(str(u), str(v), **data)

        return spec_graph

    raise TypeError(
        f"Unsupported graph type {type(graph).__name__}. Expected TheoryGraph or NetworkX DiGraph."
    )


def find_poset_roots(dag: nx.DiGraph) -> list[str]:
    """Find all candidate root nodes (greatest lower bounds) in a directed acyclic graph.

    A root node has in-degree 0 and can reach other nodes in its component.

    Parameters
    ----------
    dag : nx.DiGraph
        Directed acyclic graph.

    Returns
    -------
    list of str
        Identifiers of nodes with zero in-degree that have descendants or are components roots.
    """
    if dag.number_of_nodes() == 0:
        return []

    # Nodes with in-degree 0
    zero_in = [n for n, deg in dag.in_degree() if deg == 0]
    if not zero_in:
        return []

    # If edges exist, prioritize nodes that actually reach other nodes
    if dag.number_of_edges() > 0:
        branching_roots = [n for n in zero_in if dag.out_degree(n) > 0]
        if branching_roots:
            return branching_roots

    return zero_in


def verify_strict_partial_order(graph: nx.DiGraph) -> tuple[bool, list[list[str]]]:
    """Verify strict partial order properties: irreflexivity, antisymmetry, and DAG acyclicity.

    Parameters
    ----------
    graph : nx.DiGraph
        Directed graph to check.

    Returns
    -------
    tuple of (bool, list of list of str)
        Boolean indicating whether graph is a valid strict partial order DAG,
        and list of detected cycles if invalid.
    """
    # 1. Irreflexivity: check self-loops
    self_loops = list(nx.nodes_with_selfloops(graph))
    if self_loops:
        cycles = [[n, n] for n in self_loops]
        return False, cycles

    # 2. Acyclicity via NetworkX (implies antisymmetry and cycle-freeness)
    is_dag = nx.is_directed_acyclic_graph(graph)
    if is_dag:
        return True, []

    # Extract elementary cycles for diagnostics
    try:
        cycles = list(nx.simple_cycles(graph))
    except Exception:
        cycles = [["detected_cycle"]]

    return False, cycles


def compute_transitive_reduction_f1(
    pred_dag: nx.DiGraph,
    ref_dag: nx.DiGraph,
    node_mapping: dict[str, str] | None = None,
) -> tuple[float, float, float]:
    """Compute Precision, Recall, and Poset F1 over transitive reductions of specialization DAGs.

    Parameters
    ----------
    pred_dag : nx.DiGraph
        Predicted specialization DAG.
    ref_dag : nx.DiGraph
        Reference gold specialization DAG.
    node_mapping : dict[str, str] | None, optional
        Optional mapping from predicted node IDs to reference node IDs.

    Returns
    -------
    tuple of (float, float, float)
        Poset precision, recall, and F1 score in [0.0, 1.0].
    """
    mapping = node_mapping or {}

    # Empty cases
    ref_edge_count = ref_dag.number_of_edges()
    pred_edge_count = pred_dag.number_of_edges()

    if ref_edge_count == 0 and pred_edge_count == 0:
        return 1.0, 1.0, 1.0
    if ref_edge_count == 0 or pred_edge_count == 0:
        return 0.0, 0.0, 0.0

    # Ensure DAGs for transitive reduction
    if not nx.is_directed_acyclic_graph(ref_dag):
        ref_tr = ref_dag
    else:
        ref_tr = nx.transitive_reduction(ref_dag)

    if not nx.is_directed_acyclic_graph(pred_dag):
        pred_tr = pred_dag
    else:
        pred_tr = nx.transitive_reduction(pred_dag)

    ref_edges: set[tuple[str, str]] = set()
    for u, v in ref_tr.edges():
        ref_edges.add((str(u), str(v)))

    pred_edges: set[tuple[str, str]] = set()
    for u, v in pred_tr.edges():
        u_mapped = mapping.get(str(u), str(u))
        v_mapped = mapping.get(str(v), str(v))
        pred_edges.add((u_mapped, v_mapped))

    tp = len(pred_edges & ref_edges)
    fp = len(pred_edges - ref_edges)
    fn = len(ref_edges - pred_edges)

    precision = float(tp) / float(tp + fp) if (tp + fp) > 0 else 0.0
    recall = float(tp) / float(tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2.0 * (precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return precision, recall, f1


def compute_specialization_reachability(
    pred_dag: nx.DiGraph,
    ref_dag: nx.DiGraph,
    node_mapping: dict[str, str] | None = None,
) -> tuple[float, float, float]:
    """Compute reachability path precision, recall, and F1 over transitive closures.

    Verifies whether all reference derivation paths exist in the predicted specialization DAG.

    Parameters
    ----------
    pred_dag : nx.DiGraph
        Predicted specialization DAG.
    ref_dag : nx.DiGraph
        Reference gold specialization DAG.
    node_mapping : dict[str, str] | None, optional
        Optional mapping from predicted node IDs to reference node IDs.

    Returns
    -------
    tuple of (float, float, float)
        Reachability path precision, recall, and F1 in [0.0, 1.0].
    """
    mapping = node_mapping or {}

    if ref_dag.number_of_edges() == 0 and pred_dag.number_of_edges() == 0:
        return 1.0, 1.0, 1.0
    if ref_dag.number_of_edges() == 0 or pred_dag.number_of_edges() == 0:
        return 0.0, 0.0, 0.0

    # Build reference reachability pairs (u != v)
    ref_paths: set[tuple[str, str]] = set()
    for u in ref_dag.nodes():
        for v in nx.descendants(ref_dag, u):
            ref_paths.add((str(u), str(v)))

    # Build predicted reachability pairs (u != v)
    pred_paths: set[tuple[str, str]] = set()
    for u in pred_dag.nodes():
        u_mapped = mapping.get(str(u), str(u))
        for v in nx.descendants(pred_dag, u):
            v_mapped = mapping.get(str(v), str(v))
            pred_paths.add((u_mapped, v_mapped))

    tp = len(pred_paths & ref_paths)
    fp = len(pred_paths - ref_paths)
    fn = len(ref_paths - pred_paths)

    precision = float(tp) / float(tp + fp) if (tp + fp) > 0 else 0.0
    recall = float(tp) / float(tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2.0 * (precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return precision, recall, f1


def check_hierarchical_subsumption(
    graph: Any,
    spec_edges: list[tuple[str, str]] | None = None,
) -> tuple[float, bool, dict[str, Any]]:
    """Verify hierarchical model inheritance subsumption across specialization edges.

    For every specialization edge T_i -> T_j:
    M_p(T_j) <= M_p(T_i) and M(T_j) < M(T_i).
    Syntactically, T_j introduces additional restricting laws/axioms beyond T_i,
    shrinking its actual models M(T_j) while preserving/extending potential model framework.

    Parameters
    ----------
    graph : TheoryGraph or nx.DiGraph
        Graph containing theory elements and model class decomposition links.
    spec_edges : list of tuple of (str, str), optional
        List of (parent_id, child_id) specialization edges to evaluate.

    Returns
    -------
    tuple of (float, bool, dict of str to Any)
        Subsumption score [0.0, 1.0], boolean validity flag, and per-edge diagnostic details.
    """
    if spec_edges is None:
        spec_dag = extract_specialization_subgraph(graph)
        spec_edges = list(spec_dag.edges())

    if not spec_edges:
        return 1.0, True, {"total_edges": 0, "passed_edges": 0}

    # Extract node attributes and model links
    node_actual_models: dict[str, set[str]] = {}
    node_potential_models: dict[str, set[str]] = {}
    node_attrs: dict[str, dict[str, Any]] = {}

    if isinstance(graph, TheoryGraph):
        for nid, node in graph.nodes.items():
            node_attrs[nid] = dict(node.attributes)
            node_actual_models[nid] = set()
            node_potential_models[nid] = set()
            # Direct attributes if present
            if "actual_models" in node.attributes:
                for m in node.attributes["actual_models"]:
                    node_actual_models[nid].add(str(m))
            if "potential_models" in node.attributes:
                for m in node.attributes["potential_models"]:
                    node_potential_models[nid].add(str(m))

        for edge in graph.edges:
            rel = edge.relation_type
            if rel == RelationType.HAS_ACTUAL_MODEL:
                node_actual_models.setdefault(edge.source, set()).add(edge.target)
            elif rel == RelationType.HAS_POTENTIAL_MODEL:
                node_potential_models.setdefault(edge.source, set()).add(edge.target)

    elif isinstance(graph, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
        for nid, data in graph.nodes(data=True):
            node_attrs[str(nid)] = dict(data)
            node_actual_models[str(nid)] = set()
            node_potential_models[str(nid)] = set()
            if "actual_models" in data:
                for m in data["actual_models"]:
                    node_actual_models[str(nid)].add(str(m))
            if "potential_models" in data:
                for m in data["potential_models"]:
                    node_potential_models[str(nid)].add(str(m))

        for u, v, data in graph.edges(data=True):
            rel = str(data.get("relation_type", data.get("relation", data.get("label", ""))))
            if rel in {"hasActualModel", "HAS_ACTUAL_MODEL", "has_actual_model"}:
                node_actual_models.setdefault(str(u), set()).add(str(v))
            elif rel in {"hasPotentialModel", "HAS_POTENTIAL_MODEL", "has_potential_model"}:
                node_potential_models.setdefault(str(u), set()).add(str(v))

    passed_count = 0
    edge_diagnostics: list[dict[str, Any]] = []

    for parent_id, child_id in spec_edges:
        p_act = node_actual_models.get(parent_id, set())
        c_act = node_actual_models.get(child_id, set())
        p_pot = node_potential_models.get(parent_id, set())
        c_pot = node_potential_models.get(child_id, set())

        # Check actual models:
        # In Bourbaki structuralism, child specializes parent by adding laws.
        # Syntactically: child has laws that restrict parent.
        # Either child declares distinct specialized laws (c_act != empty, or c_act != p_act)
        # or cumulative laws expand.
        has_specializing_laws = len(c_act) > 0 or "formalAxiom" in node_attrs.get(child_id, {})

        # Check potential models:
        # Conceptual base sets/signatures: child framework is compatible with parent framework
        has_compatible_potential = True
        if p_pot and c_pot:
            # Child either shares or specializes potential model signatures
            has_compatible_potential = len(c_pot) > 0

        is_subsumed = has_specializing_laws and has_compatible_potential
        if is_subsumed:
            passed_count += 1

        edge_diagnostics.append(
            {
                "parent_id": parent_id,
                "child_id": child_id,
                "parent_actual_models": list(p_act),
                "child_actual_models": list(c_act),
                "has_specializing_laws": has_specializing_laws,
                "has_compatible_potential": has_compatible_potential,
                "is_subsumed": is_subsumed,
            }
        )

    score = float(passed_count) / float(len(spec_edges)) if spec_edges else 1.0
    valid = (score == 1.0)
    details = {
        "total_edges": len(spec_edges),
        "passed_edges": passed_count,
        "score": score,
        "edge_breakdown": edge_diagnostics,
    }
    return score, valid, details


def evaluate_specialization_poset(
    pred_graph: Any,
    ref_graph: Any | None = None,
    *,
    gold_root_id: str | None = None,
    node_mapping: dict[str, str] | None = None,
) -> PosetEvaluationResult:
    """Evaluate specialization poset hierarchies, DAG acyclicity, and model subsumption.

    Parameters
    ----------
    pred_graph : TheoryGraph or nx.DiGraph
        Predicted theory graph containing specialization relations.
    ref_graph : TheoryGraph or nx.DiGraph, optional
        Reference gold theory graph.
    gold_root_id : str, optional
        Explicit gold root theory element identifier (e.g. 'str:T_CPM_Base').
        If omitted and ref_graph is provided, ref_graph's unique root is used.
    node_mapping : dict of str to str, optional
        Optional mapping from predicted node IDs to reference node IDs.

    Returns
    -------
    PosetEvaluationResult
        Comprehensive evaluation report with strict partial order, root conformity,
        and transitive reduction F1 metrics.
    """
    pred_dag = extract_specialization_subgraph(pred_graph)
    is_spo, cycles = verify_strict_partial_order(pred_dag)
    is_dag = len(cycles) == 0

    pred_roots = find_poset_roots(pred_dag)
    has_unique_root = len(pred_roots) == 1
    root_node = pred_roots[0] if has_unique_root else None

    # Determine reference gold root
    ref_dag: nx.DiGraph | None = None
    if ref_graph is not None:
        ref_dag = extract_specialization_subgraph(ref_graph)
        if gold_root_id is None:
            ref_roots = find_poset_roots(ref_dag)
            if len(ref_roots) == 1:
                gold_root_id = ref_roots[0]

    # Verify Root Element Conformity: B(TN_pred) = {T_{0, gold}}
    if gold_root_id is not None:
        mapped_root = (node_mapping or {}).get(root_node, root_node) if root_node else None
        root_conformity = has_unique_root and (
            mapped_root == gold_root_id or root_node == gold_root_id
        )
    else:
        root_conformity = has_unique_root

    # Hierarchical model inheritance subsumption
    subsume_score, subsume_valid, subsume_details = check_hierarchical_subsumption(
        pred_graph, spec_edges=list(pred_dag.edges())
    )

    # Transitive reduction F1 & Reachability path metrics
    if ref_dag is not None:
        prec, rec, f1 = compute_transitive_reduction_f1(
            pred_dag, ref_dag, node_mapping=node_mapping
        )
        r_prec, r_rec, r_f1 = compute_specialization_reachability(
            pred_dag, ref_dag, node_mapping=node_mapping
        )
        num_ref_edges = ref_dag.number_of_edges()
    else:
        prec, rec, f1 = 1.0, 1.0, 1.0
        r_prec, r_rec, r_f1 = 1.0, 1.0, 1.0
        num_ref_edges = 0

    details = {
        "pred_roots": pred_roots,
        "gold_root_id": gold_root_id,
        "cycles": cycles,
        "subsumption": subsume_details,
    }

    return PosetEvaluationResult(
        is_dag=is_dag,
        is_strict_partial_order=is_spo,
        has_unique_root=has_unique_root,
        root_node=root_node,
        root_conformity=root_conformity,
        hierarchical_subsumption_score=subsume_score,
        hierarchical_subsumption_valid=subsume_valid,
        precision=prec,
        recall=rec,
        f1=f1,
        reachability_precision=r_prec,
        reachability_recall=r_rec,
        reachability_f1=r_f1,
        cycles=cycles,
        num_predicted_edges=pred_dag.number_of_edges(),
        num_reference_edges=num_ref_edges,
        details=details,
    )
