"""Comprehensive Intrinsic Evaluation: Model Component Decomposition & Property Subsumption.

Operationalizes formal structuralist metatheory of science (Balzer, Moulines, & Sneed, 1987)
to determine whether a predicted scientific theory graph possesses at least the theoretical
capabilities of a reference gold graph (G_pred >=cap G_ref).

Evaluates the decomposition of Theory Elements into their constituent model classes:
1. Potential Models (M_p): Conceptual framework, primitive base sets, function signatures.
2. Actual Models (M): Governing laws, mathematical differential equations, substantive axioms.
3. Partial Potential Models (M_pp): T-non-theoretical empirical observational basis.
4. Global Invariance Constraints (GC): Cross-model invariant physical properties.
5. Paradigmatic Applications (I_0): Canonical exemplar systems and prototypes.
"""

from __future__ import annotations

import re
from typing import Any, Mapping
import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from epistemetrics.core.models import (
    EpistemicStatus,
    NodeType,
    RelationType,
    TheoryEdge,
    TheoryNode,
)
from epistemetrics.graph.theory_graph import TheoryGraph


class ModelComponentEvaluationResult(BaseModel):
    """Result container for intrinsic model component and property subsumption evaluation.

    Parameters
    ----------
    mcc : float
        Model Component Completeness score in [0.0, 1.0].
    aor : float
        Axiomatic Omission Rate in [0.0, 1.0]. Zero omission (0.0) is required for capability equivalence.
    pfs : float
        Property Fidelity Score in [0.0, 1.0] across attributes.
    ag_iou : float
        Average Text Anchor Grounding character span IoU in [0.0, 1.0].
    is_subsumed : bool
        True if G_pred subsumes the capabilities of G_ref (AOR == 0.0 and thresholds met).
    component_counts_ref : dict[str, int]
        Total count of reference components categorized by formal model class.
    component_counts_pred : dict[str, int]
        Total count of predicted components categorized by formal model class.
    component_matches : dict[str, int]
        Count of successfully matched components per model class.
    component_scores : dict[str, float]
        Completeness ratios per formal model class.
    unmatched_ref_nodes : list[str]
        Identifiers of reference nodes omitted in predicted graph.
    matched_node_pairs : list[tuple[str, str]]
        Pairs of (ref_node_id, pred_node_id) established during evaluation.
    node_property_fidelity : dict[str, float]
        Macro accuracy scores across tested node properties.
    edge_fidelity : float
        Relational category, direction, and polarity fidelity across structural edges.
    details : dict[str, Any]
        Diagnostic breakdown and per-node match statistics.
    """

    model_config = ConfigDict(frozen=True)

    mcc: float = Field(
        ..., description="Model Component Completeness score in [0.0, 1.0]."
    )
    aor: float = Field(
        ...,
        description="Axiomatic Omission Rate in [0.0, 1.0]. Zero omission (0.0) is mandatory.",
    )
    pfs: float = Field(
        ..., description="Property Fidelity Score in [0.0, 1.0] across attributes."
    )
    ag_iou: float = Field(
        ...,
        description="Average Text Anchor Grounding character span IoU in [0.0, 1.0].",
    )
    is_subsumed: bool = Field(
        ...,
        description="Capability subsumption status (G_pred >=cap G_ref).",
    )
    component_counts_ref: dict[str, int] = Field(
        default_factory=dict, description="Reference component counts per model class."
    )
    component_counts_pred: dict[str, int] = Field(
        default_factory=dict, description="Predicted component counts per model class."
    )
    component_matches: dict[str, int] = Field(
        default_factory=dict, description="Matched component counts per model class."
    )
    component_scores: dict[str, float] = Field(
        default_factory=dict, description="Completeness scores per model class."
    )
    unmatched_ref_nodes: list[str] = Field(
        default_factory=list, description="IDs of reference nodes missing in predicted graph."
    )
    matched_node_pairs: list[tuple[str, str]] = Field(
        default_factory=list, description="Matched (reference_id, predicted_id) tuples."
    )
    node_property_fidelity: dict[str, float] = Field(
        default_factory=dict, description="Per-property fidelity scores."
    )
    edge_fidelity: float = Field(
        default=1.0, description="Fidelity of relational structure and semantics."
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Detailed diagnostic evaluation metadata."
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert result model to a serializable dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary representation of evaluation results.
        """
        return self.model_dump()

    def to_markdown(self) -> str:
        """Format the evaluation result as a comprehensive Markdown report.

        Returns
        -------
        str
            GitHub-flavored Markdown report.
        """
        status_badge = "✅ PASSED (Subsumes Capabilities)" if self.is_subsumed else "❌ FAILED (Capability Deficit)"
        lines = [
            "# Formal Structuralist Model Evaluation Report",
            "",
            f"**Capability Subsumption ($G_{{pred}} \\succeq_{{cap}} G_{{ref}}$):** {status_badge}",
            "",
            "## Quantitative Benchmark Metrics",
            f"- **Model Component Completeness (MCC):** {self.mcc:.4f}",
            f"- **Axiomatic Omission Rate (AOR):** {self.aor:.4f} {'(Zero Omission ✅)' if self.aor == 0.0 else '(Laws Omitted ❌)'}",
            f"- **Property Fidelity Score (PFS):** {self.pfs:.4f}",
            f"- **Text Anchor Grounding IoU ($AG_{{IoU}}$):** {self.ag_iou:.4f}",
            f"- **Relational Edge Fidelity:** {self.edge_fidelity:.4f}",
            "",
            "## Model Class Decomposition Breakdown",
            "| Model Class | Symbol | Reference Count | Predicted Count | Matched | Completeness |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ]

        class_symbols = {
            "potential_models": "$\\mathcal{M}_p$",
            "actual_models": "$\\mathcal{M}$",
            "partial_potential_models": "$\\mathcal{M}_{pp}$",
            "constraints": "$GC$",
            "paradigms": "$I_0$",
            "theory_elements": "$T$",
        }

        for m_class, symbol in class_symbols.items():
            ref_c = self.component_counts_ref.get(m_class, 0)
            pred_c = self.component_counts_pred.get(m_class, 0)
            matched_c = self.component_matches.get(m_class, 0)
            score = self.component_scores.get(m_class, 1.0 if ref_c == 0 else 0.0)
            lines.append(f"| `{m_class}` | {symbol} | {ref_c} | {pred_c} | {matched_c} | {score:.2%} |")

        if self.unmatched_ref_nodes:
            lines.append("")
            lines.append("## Omitted Reference Components")
            for node_id in self.unmatched_ref_nodes:
                lines.append(f"- ❌ Missing: `{node_id}`")

        return "\n".join(lines)


def normalize_formula(formula: str) -> str:
    """Normalize a mathematical formula for symbolic and token comparison.

    Parameters
    ----------
    formula : str
        Input mathematical expression or proposition string.

    Returns
    -------
    str
        Standardized, whitespace-normalized lowercase token string.
    """
    if not formula:
        return ""
    cleaned = formula.replace("\\cdot", "*").replace("·", "*")
    cleaned = cleaned.replace("\\", " ")
    cleaned = re.sub(r"[{}\[\]()_,^]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def formula_similarity(f1: str, f2: str) -> float:
    """Compute symbolic token similarity between two mathematical expressions.

    Parameters
    ----------
    f1 : str
        First mathematical expression string.
    f2 : str
        Second mathematical expression string.

    Returns
    -------
    float
        Jaccard similarity between canonical formula tokens [0.0, 1.0].
    """
    if not f1 and not f2:
        return 1.0
    if not f1 or not f2:
        return 0.0

    n1 = normalize_formula(f1)
    n2 = normalize_formula(f2)
    if n1 == n2:
        return 1.0

    t1 = set(n1.split())
    t2 = set(n2.split())
    if not t1 or not t2:
        return 0.0

    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return float(intersection) / float(union) if union > 0 else 0.0


def calculate_anchor_iou(
    anchor_ref: Mapping[str, Any] | None,
    anchor_pred: Mapping[str, Any] | None,
) -> float:
    """Calculate character span Intersection over Union (IoU) between text anchors.

    Parameters
    ----------
    anchor_ref : Mapping of str to Any or None
        Reference text anchor coordinates.
    anchor_pred : Mapping of str to Any or None
        Predicted text anchor coordinates.

    Returns
    -------
    float
        Intersection over Union score in [0.0, 1.0].
    """
    if not anchor_ref and not anchor_pred:
        return 1.0
    if not anchor_ref or not anchor_pred:
        return 0.0

    def get_span(a: Mapping[str, Any]) -> tuple[int, int] | None:
        s = a.get("charStart") if a.get("charStart") is not None else a.get("char_start")
        if s is None:
            s = a.get("start_char") or a.get("char_offset")
        e = a.get("charEnd") if a.get("charEnd") is not None else a.get("char_end")
        if e is None:
            e = a.get("end_char")
        if e is None and s is not None and "length" in a:
            e = s + a["length"]
        if s is not None and e is not None:
            try:
                return int(s), int(e)
            except (ValueError, TypeError):
                return None
        return None

    span_ref = get_span(anchor_ref)
    span_pred = get_span(anchor_pred)

    if span_ref is not None and span_pred is not None:
        s_ref, e_ref = span_ref
        s_pred, e_pred = span_pred

        doc_ref = anchor_ref.get("sourceDocId") or anchor_ref.get("source_doc_id")
        doc_pred = anchor_pred.get("sourceDocId") or anchor_pred.get("source_doc_id")
        if doc_ref and doc_pred and str(doc_ref).strip() != str(doc_pred).strip():
            return 0.0

        inter_start = max(s_ref, s_pred)
        inter_end = min(e_ref, e_pred)
        intersection = max(0, inter_end - inter_start)

        union_start = min(s_ref, s_pred)
        union_end = max(e_ref, e_pred)
        union = max(0, union_end - union_start)

        return float(intersection) / float(union) if union > 0 else 0.0

    # Fallback to verbatimQuote token overlap
    q_ref = str(anchor_ref.get("verbatimQuote", "") or "")
    q_pred = str(anchor_pred.get("verbatimQuote", "") or "")
    if q_ref and q_pred:
        t_ref = set(q_ref.lower().split())
        t_pred = set(q_pred.lower().split())
        if not t_ref and not t_pred:
            return 1.0
        inter = len(t_ref & t_pred)
        un = len(t_ref | t_pred)
        return float(inter) / float(un) if un > 0 else 0.0

    return 0.0


def _extract_graph_nodes_and_edges(
    graph: Any,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Unpack a TheoryGraph or NetworkX graph into normalized nodes and edges dictionaries.

    Parameters
    ----------
    graph : Any
        TheoryGraph instance or NetworkX graph.

    Returns
    -------
    tuple of (dict[str, dict[str, Any]], list[dict[str, Any]])
        Tuple containing node dictionary and edge list.
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    if isinstance(graph, TheoryGraph):
        for nid, node in graph.nodes.items():
            attrs = dict(node.attributes)
            anchor = (
                attrs.get("textAnchor")
                or attrs.get("text_anchor")
                or attrs.get("anchor")
                or attrs.get("Episteme:textAnchor")
                or attrs.get("glp:textAnchor")
            )
            formal_axiom = (
                attrs.get("formalAxiom")
                or attrs.get("formal_axiom")
                or attrs.get("str:formalAxiom")
                or ""
            )
            nodes[nid] = {
                "id": node.id,
                "name": node.name,
                "node_type": node.node_type,
                "epistemic_status": node.epistemic_status,
                "confidence": node.confidence,
                "description": node.description,
                "formal_axiom": formal_axiom,
                "anchor": anchor,
                "attributes": attrs,
            }
        for edge in graph.edges:
            edges.append(
                {
                    "source": edge.source,
                    "target": edge.target,
                    "relation_type": edge.relation_type,
                    "confidence": edge.confidence,
                    "weight": edge.weight,
                    "polarity": edge.polarity,
                    "attributes": edge.attributes,
                }
            )
        return nodes, edges

    if isinstance(graph, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
        for nid, data in graph.nodes(data=True):
            node_id = str(nid)
            attrs = dict(data)
            anchor = (
                attrs.get("textAnchor")
                or attrs.get("text_anchor")
                or attrs.get("anchor")
                or attrs.get("Episteme:textAnchor")
                or attrs.get("glp:textAnchor")
            )
            formal_axiom = (
                attrs.get("formalAxiom")
                or attrs.get("formal_axiom")
                or attrs.get("str:formalAxiom")
                or ""
            )
            n_type = NodeType.from_str(
                attrs.get("node_type", attrs.get("type", attrs.get("label", "concept")))
            )
            e_status = EpistemicStatus.from_str(
                attrs.get("epistemic_status", "neutral")
            )
            name = str(attrs.get("name", attrs.get("label", node_id)))
            nodes[node_id] = {
                "id": node_id,
                "name": name,
                "node_type": n_type,
                "epistemic_status": e_status,
                "confidence": float(attrs.get("confidence", 1.0)),
                "description": attrs.get("description"),
                "formal_axiom": formal_axiom,
                "anchor": anchor,
                "attributes": attrs,
            }

        if graph.is_multigraph():
            for u, v, _k, data in graph.edges(keys=True, data=True):
                r_type = RelationType.from_str(
                    data.get("relation_type", data.get("relation", data.get("type", "explains")))
                )
                edges.append(
                    {
                        "source": str(u),
                        "target": str(v),
                        "relation_type": r_type,
                        "confidence": float(data.get("confidence", 1.0)),
                        "weight": float(data.get("weight", 1.0)),
                        "polarity": int(data.get("polarity", r_type.default_polarity)),
                        "attributes": dict(data),
                    }
                )
        else:
            for u, v, data in graph.edges(data=True):
                r_type = RelationType.from_str(
                    data.get("relation_type", data.get("relation", data.get("type", "explains")))
                )
                edges.append(
                    {
                        "source": str(u),
                        "target": str(v),
                        "relation_type": r_type,
                        "confidence": float(data.get("confidence", 1.0)),
                        "weight": float(data.get("weight", 1.0)),
                        "polarity": int(data.get("polarity", r_type.default_polarity)),
                        "attributes": dict(data),
                    }
                )
        return nodes, edges

    raise TypeError(
        f"Unsupported graph type {type(graph).__name__}. Expected TheoryGraph or NetworkX Graph."
    )


def _classify_model_components(
    nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, set[str]]:
    """Partition graph nodes into the five structuralist model classes and theory elements.

    Categories
    ----------
    - 'potential_models' (M_p)
    - 'actual_models' (M)
    - 'partial_potential_models' (M_pp)
    - 'constraints' (GC)
    - 'paradigms' (I_0)
    - 'theory_elements' (T)

    Parameters
    ----------
    nodes : dict[str, dict[str, Any]]
        Extracted graph nodes dictionary.
    edges : list[dict[str, Any]]
        Extracted graph edge list.

    Returns
    -------
    dict[str, set[str]]
        Mapping from formal model class category to set of matching node IDs.
    """
    classes: dict[str, set[str]] = {
        "potential_models": set(),
        "actual_models": set(),
        "partial_potential_models": set(),
        "constraints": set(),
        "paradigms": set(),
        "theory_elements": set(),
    }

    # 1. Inspect direct node types
    for nid, node in nodes.items():
        nt = node["node_type"]
        if nt == NodeType.POTENTIAL_MODEL:
            classes["potential_models"].add(nid)
        elif nt in {NodeType.ACTUAL_MODEL, NodeType.AXIOM}:
            classes["actual_models"].add(nid)
        elif nt == NodeType.PARTIAL_POTENTIAL_MODEL:
            classes["partial_potential_models"].add(nid)
        elif nt == NodeType.CONSTRAINT:
            classes["constraints"].add(nid)
        elif nt == NodeType.PARADIGM:
            classes["paradigms"].add(nid)
        elif nt == NodeType.THEORY_ELEMENT:
            classes["theory_elements"].add(nid)
        else:
            # Fallback by attributes or label clues
            attrs = node.get("attributes", {})
            if "formalAxiom" in attrs or "formal_axiom" in attrs or node.get("formal_axiom"):
                classes["actual_models"].add(nid)
            elif "base_sets" in attrs or "signatures" in attrs:
                classes["potential_models"].add(nid)
            elif "observational_base" in attrs or "non_theoretical_terms" in attrs:
                classes["partial_potential_models"].add(nid)
            elif "invariant_property" in attrs or "cross_model_rule" in attrs:
                classes["constraints"].add(nid)
            elif "exemplar_system" in attrs:
                classes["paradigms"].add(nid)

    # 2. Inspect incoming structural composition edges
    for edge in edges:
        rel = edge["relation_type"]
        target = edge["target"]
        if target in nodes:
            if rel == RelationType.HAS_POTENTIAL_MODEL:
                classes["potential_models"].add(target)
            elif rel == RelationType.HAS_ACTUAL_MODEL:
                classes["actual_models"].add(target)
            elif rel == RelationType.HAS_PARTIAL_POTENTIAL_MODEL:
                classes["partial_potential_models"].add(target)
            elif rel == RelationType.HAS_CONSTRAINT:
                classes["constraints"].add(target)
            elif rel in {RelationType.HAS_PARADIGM, RelationType.HAS_INTENDED_APPLICATION}:
                classes["paradigms"].add(target)

    return classes


def _compute_node_match_similarity(
    ref_node: dict[str, Any], pred_node: dict[str, Any]
) -> tuple[float, dict[str, float]]:
    """Compute detailed similarity score between a reference node and a candidate predicted node.

    Parameters
    ----------
    ref_node : dict[str, Any]
        Reference node data dictionary.
    pred_node : dict[str, Any]
        Candidate predicted node data dictionary.

    Returns
    -------
    tuple of (float, dict[str, float])
        Combined similarity score in [0.0, 1.0] and property breakdown.
    """
    ref_id = ref_node["id"]
    pred_id = pred_node["id"]
    is_exact_id = ref_id == pred_id

    # 1. Type compatibility
    ref_t = ref_node["node_type"]
    pred_t = pred_node["node_type"]
    if ref_t == pred_t:
        type_sim = 1.0
    elif (ref_t in {NodeType.ACTUAL_MODEL, NodeType.AXIOM}) and (
        pred_t in {NodeType.ACTUAL_MODEL, NodeType.AXIOM}
    ):
        type_sim = 0.95
    else:
        type_sim = 0.0

    # 2. Epistemic status match
    status_sim = 1.0 if ref_node["epistemic_status"] == pred_node["epistemic_status"] else 0.5

    # 3. Label / Name / ID text similarity
    ref_name = ref_node["name"].lower()
    pred_name = pred_node["name"].lower()
    t_ref = set(ref_name.split())
    t_pred = set(pred_name.split())
    if t_ref and t_pred:
        name_sim = len(t_ref & t_pred) / len(t_ref | t_pred)
    elif is_exact_id:
        name_sim = 1.0
    else:
        name_sim = 0.0

    # 4. Formal Axiom match
    ref_axiom = ref_node.get("formal_axiom", "")
    pred_axiom = pred_node.get("formal_axiom", "")
    has_axiom = bool(ref_axiom)
    axiom_sim = formula_similarity(ref_axiom, pred_axiom) if has_axiom else 1.0

    # 5. Text Anchor Grounding match
    ref_anchor = ref_node.get("anchor")
    pred_anchor = pred_node.get("anchor")
    has_anchor = bool(ref_anchor)
    anchor_sim = (
        calculate_anchor_iou(ref_anchor, pred_anchor) if has_anchor else 1.0
    )

    # Weighted composite similarity
    if has_axiom and has_anchor:
        combined = (
            0.35 * axiom_sim
            + 0.25 * name_sim
            + 0.20 * anchor_sim
            + 0.10 * type_sim
            + 0.10 * status_sim
        )
    elif has_axiom:
        combined = (
            0.45 * axiom_sim
            + 0.25 * name_sim
            + 0.15 * type_sim
            + 0.15 * status_sim
        )
    elif has_anchor:
        combined = (
            0.35 * anchor_sim
            + 0.35 * name_sim
            + 0.15 * type_sim
            + 0.15 * status_sim
        )
    else:
        combined = 0.50 * name_sim + 0.30 * type_sim + 0.20 * status_sim

    if is_exact_id:
        combined = max(combined, 0.85)

    prop_breakdown = {
        "type": type_sim,
        "status": status_sim,
        "name": name_sim,
        "axiom": axiom_sim,
        "anchor": anchor_sim,
    }
    return combined, prop_breakdown


def evaluate_model_components(
    pred_graph: Any,
    ref_graph: Any,
    *,
    min_mcc: float = 1.0,
    min_pfs: float = 0.8,
    sim_threshold: float = 0.50,
) -> ModelComponentEvaluationResult:
    """Evaluate whether a predicted theory graph has at least the capabilities of a gold reference graph.

    Verifies model component completeness across all five formal model classes
    (M_p, M, M_pp, GC, I_0), verifies zero axiomatic omissions (AOR == 0.0),
    and measures property fidelity and text anchor grounding IoU.

    Parameters
    ----------
    pred_graph : TheoryGraph or nx.DiGraph or nx.MultiDiGraph
        The generated or predicted theory graph.
    ref_graph : TheoryGraph or nx.DiGraph or nx.MultiDiGraph
        The gold ground truth reference theory graph.
    min_mcc : float, optional
        Minimum required Model Component Completeness for subsumption (default: 1.0).
    min_pfs : float, optional
        Minimum required Property Fidelity Score for subsumption (default: 0.8).
    sim_threshold : float, optional
        Minimum node similarity threshold to accept an alignment (default: 0.50).

    Returns
    -------
    ModelComponentEvaluationResult
        Comprehensive evaluation output containing MCC, AOR, PFS, AG_IoU, and subsumption verdict.
    """
    ref_nodes, ref_edges = _extract_graph_nodes_and_edges(ref_graph)
    pred_nodes, pred_edges = _extract_graph_nodes_and_edges(pred_graph)

    # Edge cases: empty graphs
    if not ref_nodes:
        is_empty_pred = len(pred_nodes) == 0
        return ModelComponentEvaluationResult(
            mcc=1.0 if is_empty_pred else 0.0,
            aor=0.0,
            pfs=1.0,
            ag_iou=1.0,
            is_subsumed=is_empty_pred,
            component_counts_ref={},
            component_counts_pred={},
            component_matches={},
            component_scores={},
            unmatched_ref_nodes=[],
            matched_node_pairs=[],
            node_property_fidelity={"type": 1.0, "status": 1.0},
            edge_fidelity=1.0,
            details={"status": "Reference graph is empty."},
        )

    # Partition both graphs into formal model classes
    ref_classes = _classify_model_components(ref_nodes, ref_edges)
    pred_classes = _classify_model_components(pred_nodes, pred_edges)

    component_counts_ref = {k: len(v) for k, v in ref_classes.items()}
    component_counts_pred = {k: len(v) for k, v in pred_classes.items()}

    matched_pairs: list[tuple[str, str]] = []
    matched_ref_nodes: set[str] = set()
    matched_pred_nodes: set[str] = set()
    component_matches: dict[str, int] = {k: 0 for k in ref_classes}
    node_pair_properties: dict[str, list[float]] = {
        "type": [],
        "status": [],
        "axiom": [],
        "anchor": [],
    }

    # Match nodes class by class
    eval_classes = [
        "potential_models",
        "actual_models",
        "partial_potential_models",
        "constraints",
        "paradigms",
        "theory_elements",
    ]

    for m_class in eval_classes:
        candidates_ref = list(ref_classes[m_class])
        candidates_pred = [
            pid for pid in pred_classes[m_class] if pid not in matched_pred_nodes
        ]

        # Compute pairwise score matrix
        pair_scores: list[tuple[float, str, str, dict[str, float]]] = []
        for r_id in candidates_ref:
            for p_id in candidates_pred:
                score, props = _compute_node_match_similarity(
                    ref_nodes[r_id], pred_nodes[p_id]
                )
                pair_scores.append((score, r_id, p_id, props))

        # Greedy maximum weight matching
        pair_scores.sort(key=lambda item: item[0], reverse=True)
        for score, r_id, p_id, props in pair_scores:
            if r_id in matched_ref_nodes or p_id in matched_pred_nodes:
                continue
            if score >= sim_threshold:
                matched_ref_nodes.add(r_id)
                matched_pred_nodes.add(p_id)
                matched_pairs.append((r_id, p_id))
                component_matches[m_class] += 1
                node_pair_properties["type"].append(props["type"])
                node_pair_properties["status"].append(props["status"])
                if ref_nodes[r_id].get("formal_axiom"):
                    node_pair_properties["axiom"].append(props["axiom"])
                if ref_nodes[r_id].get("anchor"):
                    node_pair_properties["anchor"].append(props["anchor"])

    # Fallback match for any remaining unmatched reference nodes across any unused predicted nodes
    unmatched_ref = [rid for rid in ref_nodes if rid not in matched_ref_nodes]
    remaining_pred = [pid for pid in pred_nodes if pid not in matched_pred_nodes]
    fallback_pairs: list[tuple[float, str, str, dict[str, float]]] = []
    for r_id in unmatched_ref:
        for p_id in remaining_pred:
            score, props = _compute_node_match_similarity(
                ref_nodes[r_id], pred_nodes[p_id]
            )
            fallback_pairs.append((score, r_id, p_id, props))

    fallback_pairs.sort(key=lambda item: item[0], reverse=True)
    for score, r_id, p_id, props in fallback_pairs:
        if r_id in matched_ref_nodes or p_id in matched_pred_nodes:
            continue
        if score >= sim_threshold:
            matched_ref_nodes.add(r_id)
            matched_pred_nodes.add(p_id)
            matched_pairs.append((r_id, p_id))
            # Attribute to category
            for m_class, nodeset in ref_classes.items():
                if r_id in nodeset:
                    component_matches[m_class] += 1
            node_pair_properties["type"].append(props["type"])
            node_pair_properties["status"].append(props["status"])
            if ref_nodes[r_id].get("formal_axiom"):
                node_pair_properties["axiom"].append(props["axiom"])
            if ref_nodes[r_id].get("anchor"):
                node_pair_properties["anchor"].append(props["anchor"])

    unmatched_ref_final = [rid for rid in ref_nodes if rid not in matched_ref_nodes]

    # Calculate per-class completeness scores
    component_scores: dict[str, float] = {}
    for k in ref_classes:
        ref_count = len(ref_classes[k])
        if ref_count == 0:
            component_scores[k] = 1.0
        else:
            component_scores[k] = float(component_matches[k]) / float(ref_count)

    # 1. Model Component Completeness (MCC)
    # Total reference components across the 5 formal classes
    total_ref_core_components = sum(
        len(ref_classes[k])
        for k in [
            "potential_models",
            "actual_models",
            "partial_potential_models",
            "constraints",
            "paradigms",
        ]
    )
    total_matched_core_components = sum(
        component_matches[k]
        for k in [
            "potential_models",
            "actual_models",
            "partial_potential_models",
            "constraints",
            "paradigms",
        ]
    )

    if total_ref_core_components > 0:
        mcc = float(total_matched_core_components) / float(total_ref_core_components)
    else:
        # If no decomposition classes are tagged, fall back to general node coverage
        mcc = float(len(matched_ref_nodes)) / float(len(ref_nodes)) if ref_nodes else 1.0

    # 2. Axiomatic Omission Rate (AOR)
    actual_models_ref_count = len(ref_classes["actual_models"])
    if actual_models_ref_count == 0:
        aor = 0.0
    else:
        actual_models_matched = component_matches["actual_models"]
        aor = float(actual_models_ref_count - actual_models_matched) / float(
            actual_models_ref_count
        )

    # 3. Text Anchor Grounding IoU (AG_IoU)
    if node_pair_properties["anchor"]:
        ag_iou = sum(node_pair_properties["anchor"]) / len(
            node_pair_properties["anchor"]
        )
    else:
        # If no nodes in reference had anchors, grounding is considered trivially satisfied
        ag_iou = 1.0

    # 4. Property Fidelity Score (PFS) & Edge Fidelity
    # Node attribute fidelities
    prop_fidelities: dict[str, float] = {}
    for prop_name, vals in node_pair_properties.items():
        prop_fidelities[prop_name] = (sum(vals) / len(vals)) if vals else 1.0

    # Map matched ref_id -> pred_id
    ref_to_pred = dict(matched_pairs)

    # Evaluate edges
    edge_fidelity_scores: list[float] = []
    if ref_edges:
        # Index pred edges for quick lookup
        pred_edge_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for pe in pred_edges:
            key = (pe["source"], pe["target"])
            pred_edge_map.setdefault(key, []).append(pe)

        for re_edge in ref_edges:
            s_ref = re_edge["source"]
            t_ref = re_edge["target"]
            s_pred = ref_to_pred.get(s_ref)
            t_pred = ref_to_pred.get(t_ref)

            if s_pred and t_pred and (s_pred, t_pred) in pred_edge_map:
                candidate_edges = pred_edge_map[(s_pred, t_pred)]
                best_edge_score = 0.0
                for ce in candidate_edges:
                    rel_match = 1.0 if ce["relation_type"] == re_edge["relation_type"] else 0.5
                    pol_match = 1.0 if ce["polarity"] == re_edge["polarity"] else 0.0
                    w_ref = re_edge.get("weight", 1.0)
                    w_pred = ce.get("weight", 1.0)
                    weight_fid = max(
                        0.0, 1.0 - abs(w_ref - w_pred) / max(w_ref, 1.0)
                    )
                    score = 0.5 * rel_match + 0.3 * pol_match + 0.2 * weight_fid
                    if score > best_edge_score:
                        best_edge_score = score
                edge_fidelity_scores.append(best_edge_score)
            else:
                edge_fidelity_scores.append(0.0)

    edge_fidelity = (
        sum(edge_fidelity_scores) / len(edge_fidelity_scores)
        if edge_fidelity_scores
        else 1.0
    )

    # Macro property fidelity score
    pfs = 0.5 * (
        (prop_fidelities.get("type", 1.0) + prop_fidelities.get("status", 1.0)) / 2.0
    ) + 0.5 * edge_fidelity

    # Capability Subsumption Check: G_pred >=cap G_ref
    # Must have ZERO axiomatic omissions (AOR == 0.0), MCC >= min_mcc, PFS >= min_pfs
    is_subsumed = bool((aor == 0.0) and (mcc >= min_mcc) and (pfs >= min_pfs))

    return ModelComponentEvaluationResult(
        mcc=round(mcc, 4),
        aor=round(aor, 4),
        pfs=round(pfs, 4),
        ag_iou=round(ag_iou, 4),
        is_subsumed=is_subsumed,
        component_counts_ref=component_counts_ref,
        component_counts_pred=component_counts_pred,
        component_matches=component_matches,
        component_scores=component_scores,
        unmatched_ref_nodes=unmatched_ref_final,
        matched_node_pairs=matched_pairs,
        node_property_fidelity=prop_fidelities,
        edge_fidelity=round(edge_fidelity, 4),
        details={
            "min_mcc_required": min_mcc,
            "min_pfs_required": min_pfs,
            "total_ref_nodes": len(ref_nodes),
            "total_pred_nodes": len(pred_nodes),
            "total_ref_edges": len(ref_edges),
            "total_pred_edges": len(pred_edges),
        },
    )
