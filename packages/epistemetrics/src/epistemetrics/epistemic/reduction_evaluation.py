"""Intertheoretical Link Prediction and Reduction Evaluation.

Operationalizes Task 4 of the Structuralist Theory-Net Benchmark (STNB):
1. Evaluates directed cross-theory links (`str:reducesTo`, `str:presupposes`)
   connecting distinct Theory Elements across scientific theory-nets.
2. Computes relational precision, recall, and link F1 scores.
"""

from __future__ import annotations

from typing import Any

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from epistemetrics.core.models import (
    RelationType,
)
from epistemetrics.graph.theory_graph import TheoryGraph


class ReductionEvaluationResult(BaseModel):
    """Result container for intertheoretical link prediction and reduction evaluation.

    Parameters
    ----------
    precision : float
        Overall relational link precision in [0.0, 1.0].
    recall : float
        Overall relational link recall in [0.0, 1.0].
    f1 : float
        Overall relational link F1 score in [0.0, 1.0].
    per_relation_scores : dict[str, dict[str, float]]
        Breakdown of precision, recall, and F1 by relation type (e.g. 'reduces_to', 'presupposes').
    reduction_links_ref_count : int
        Number of ground-truth reduction links in reference graph.
    reduction_links_pred_count : int
        Number of predicted reduction links.
    reduction_links_matched_count : int
        Number of correctly predicted reduction links.
    presupposition_links_ref_count : int
        Number of ground-truth presupposition links in reference graph.
    presupposition_links_pred_count : int
        Number of predicted presupposition links.
    presupposition_links_matched_count : int
        Number of correctly predicted presupposition links.
    matched_links : list[tuple[str, str, str]]
        List of correctly predicted (source, target, relation) triples.
    unmatched_ref_links : list[tuple[str, str, str]]
        List of reference triples omitted in predictions.
    spurious_pred_links : list[tuple[str, str, str]]
        List of predicted triples absent in reference graph.
    details : dict[str, Any]
        Diagnostic metadata.
    """

    model_config = ConfigDict(frozen=True)

    precision: float = Field(..., description="Overall relational link precision in [0.0, 1.0].")
    recall: float = Field(..., description="Overall relational link recall in [0.0, 1.0].")
    f1: float = Field(..., description="Overall relational link F1 score in [0.0, 1.0].")
    per_relation_scores: dict[str, dict[str, float]] = Field(
        default_factory=dict, description="Precision, recall, F1 per relation type."
    )
    reduction_links_ref_count: int = Field(
        default=0, description="Reference count of reduction links."
    )
    reduction_links_pred_count: int = Field(
        default=0, description="Predicted count of reduction links."
    )
    reduction_links_matched_count: int = Field(
        default=0, description="Matched count of reduction links."
    )
    presupposition_links_ref_count: int = Field(
        default=0, description="Reference count of presupposition links."
    )
    presupposition_links_pred_count: int = Field(
        default=0, description="Predicted count of presupposition links."
    )
    presupposition_links_matched_count: int = Field(
        default=0, description="Matched count of presupposition links."
    )
    matched_links: list[tuple[str, str, str]] = Field(
        default_factory=list, description="Correctly matched (source, target, relation) triples."
    )
    unmatched_ref_links: list[tuple[str, str, str]] = Field(
        default_factory=list, description="Omitted reference triples."
    )
    spurious_pred_links: list[tuple[str, str, str]] = Field(
        default_factory=list, description="False positive predicted triples."
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Evaluation diagnostics."
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert result model to a serializable dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary representation of reduction evaluation results.
        """
        return self.model_dump()

    def to_markdown(self) -> str:
        """Format the reduction evaluation result as a Markdown report.

        Returns
        -------
        str
            GitHub-flavored Markdown report.
        """
        lines = [
            "# Intertheoretical Reduction & Link Evaluation Report",
            "",
            "## Quantitative Benchmark Metrics",
            f"- **Overall Relational Precision:** {self.precision:.4f}",
            f"- **Overall Relational Recall:** {self.recall:.4f}",
            f"- **Overall Relational F1:** {self.f1:.4f}",
            "",
            "## Link Category Breakdown",
            "| Relation Type | Reference Count | Predicted Count | Matched | Precision | Recall | F1 |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]

        for rel, scores in self.per_relation_scores.items():
            ref_c = (
                self.reduction_links_ref_count
                if rel == "reduces_to"
                else self.presupposition_links_ref_count
            )
            pred_c = (
                self.reduction_links_pred_count
                if rel == "reduces_to"
                else self.presupposition_links_pred_count
            )
            match_c = (
                self.reduction_links_matched_count
                if rel == "reduces_to"
                else self.presupposition_links_matched_count
            )
            p = scores.get("precision", 0.0)
            r = scores.get("recall", 0.0)
            f = scores.get("f1", 0.0)
            lines.append(f"| `{rel}` | {ref_c} | {pred_c} | {match_c} | {p:.2%} | {r:.2%} | {f:.4f} |")

        if self.unmatched_ref_links:
            lines.append("")
            lines.append("## Omitted Reference Links")
            for s, t, r in self.unmatched_ref_links:
                lines.append(f"- ❌ Missing: `{s}` -[{r}]-> `{t}`")

        return "\n".join(lines)


def _canonicalize_intertheoretical_relation(rel_val: Any) -> RelationType | None:
    """Normalize relation value to intertheoretical REDUCES_TO or PRESUPPOSES."""
    if isinstance(rel_val, RelationType):
        if rel_val in {RelationType.REDUCES_TO, RelationType.PRESUPPOSES}:
            return rel_val
        return None

    if not isinstance(rel_val, str):
        return None

    cleaned = rel_val.strip()
    if ":" in cleaned:
        cleaned = cleaned.split(":")[-1]
    cleaned = cleaned.lower().replace("-", "_").replace(" ", "_")

    if cleaned in {"reducesto", "reduces_to", "reduction"}:
        return RelationType.REDUCES_TO
    if cleaned in {"presupposes", "presupposition"}:
        return RelationType.PRESUPPOSES

    return None


def extract_intertheoretical_links(
    graph: Any,
    allowed_relations: set[RelationType] | None = None,
) -> set[tuple[str, str, str]]:
    """Extract directed intertheoretical links from a TheoryGraph or NetworkX graph.

    Parameters
    ----------
    graph : TheoryGraph or nx.DiGraph
        Source graph.
    allowed_relations : set of RelationType, optional
        Set of allowed relation types (defaults to {RelationType.REDUCES_TO, RelationType.PRESUPPOSES}).

    Returns
    -------
    set of tuple of (str, str, str)
        Set of (source_id, target_id, relation_str) triples.
    """
    targets = allowed_relations or {RelationType.REDUCES_TO, RelationType.PRESUPPOSES}
    links: set[tuple[str, str, str]] = set()

    if isinstance(graph, TheoryGraph):
        for edge in graph.edges:
            rel = _canonicalize_intertheoretical_relation(edge.relation_type)
            if not rel:
                rel = _canonicalize_intertheoretical_relation(
                    edge.attributes.get("relation") or edge.attributes.get("label")
                )
            if rel and rel in targets:
                links.add((str(edge.source), str(edge.target), rel.value))
        return links

    if isinstance(graph, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
        if graph.is_multigraph():
            for u, v, _k, data in graph.edges(keys=True, data=True):
                raw_rel = data.get("relation_type", data.get("relation", data.get("label", "")))
                rel = _canonicalize_intertheoretical_relation(raw_rel)
                if rel and rel in targets:
                    links.add((str(u), str(v), rel.value))
        else:
            for u, v, data in graph.edges(data=True):
                raw_rel = data.get("relation_type", data.get("relation", data.get("label", "")))
                rel = _canonicalize_intertheoretical_relation(raw_rel)
                if rel and rel in targets:
                    links.add((str(u), str(v), rel.value))
        return links

    raise TypeError(
        f"Unsupported graph type {type(graph).__name__}. Expected TheoryGraph or NetworkX Graph."
    )


def evaluate_intertheoretical_links(
    pred_graph: Any,
    ref_graph: Any,
    *,
    allowed_relations: set[RelationType] | None = None,
    node_mapping: dict[str, str] | None = None,
) -> ReductionEvaluationResult:
    """Evaluate intertheoretical reduction and presupposition link predictions.

    Parameters
    ----------
    pred_graph : TheoryGraph or nx.DiGraph
        Predicted theory graph containing intertheoretical links.
    ref_graph : TheoryGraph or nx.DiGraph
        Ground truth reference graph.
    allowed_relations : set of RelationType, optional
        Target relation types to evaluate. Defaults to {REDUCES_TO, PRESUPPOSES}.
    node_mapping : dict of str to str, optional
        Optional mapping from predicted node IDs to reference node IDs.

    Returns
    -------
    ReductionEvaluationResult
        Precision, recall, and F1 scores overall and per relation type.
    """
    mapping = node_mapping or {}
    ref_links = extract_intertheoretical_links(ref_graph, allowed_relations=allowed_relations)
    pred_raw_links = extract_intertheoretical_links(pred_graph, allowed_relations=allowed_relations)

    # Apply node mapping to predicted links
    pred_links: set[tuple[str, str, str]] = set()
    for u, v, r in pred_raw_links:
        u_m = mapping.get(u, u)
        v_m = mapping.get(v, v)
        pred_links.add((u_m, v_m, r))

    matched_links = sorted(list(pred_links & ref_links))
    unmatched_ref = sorted(list(ref_links - pred_links))
    spurious_pred = sorted(list(pred_links - ref_links))

    tp = len(matched_links)
    fp = len(spurious_pred)
    fn = len(unmatched_ref)

    if len(ref_links) == 0 and len(pred_links) == 0:
        precision = 1.0
        recall = 1.0
        f1 = 1.0
    else:
        precision = float(tp) / float(tp + fp) if (tp + fp) > 0 else 0.0
        recall = float(tp) / float(tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2.0 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

    # Breakdown per relation
    rel_names = ["reduces_to", "presupposes"]
    per_rel_scores: dict[str, dict[str, float]] = {}

    reduces_ref_c = sum(1 for _, _, r in ref_links if r == "reduces_to")
    reduces_pred_c = sum(1 for _, _, r in pred_links if r == "reduces_to")
    reduces_match_c = sum(1 for _, _, r in matched_links if r == "reduces_to")

    presupp_ref_c = sum(1 for _, _, r in ref_links if r == "presupposes")
    presupp_pred_c = sum(1 for _, _, r in pred_links if r == "presupposes")
    presupp_match_c = sum(1 for _, _, r in matched_links if r == "presupposes")

    for rel_str, ref_c, pred_c, match_c in [
        ("reduces_to", reduces_ref_c, reduces_pred_c, reduces_match_c),
        ("presupposes", presupp_ref_c, presupp_pred_c, presupp_match_c),
    ]:
        if ref_c == 0 and pred_c == 0:
            p_rel, r_rel, f_rel = 1.0, 1.0, 1.0
        else:
            p_rel = float(match_c) / float(pred_c) if pred_c > 0 else 0.0
            r_rel = float(match_c) / float(ref_c) if ref_c > 0 else 0.0
            f_rel = (
                2.0 * (p_rel * r_rel) / (p_rel + r_rel)
                if (p_rel + r_rel) > 0
                else 0.0
            )
        per_rel_scores[rel_str] = {
            "precision": p_rel,
            "recall": r_rel,
            "f1": f_rel,
        }

    return ReductionEvaluationResult(
        precision=precision,
        recall=recall,
        f1=f1,
        per_relation_scores=per_rel_scores,
        reduction_links_ref_count=reduces_ref_c,
        reduction_links_pred_count=reduces_pred_c,
        reduction_links_matched_count=reduces_match_c,
        presupposition_links_ref_count=presupp_ref_c,
        presupposition_links_pred_count=presupp_pred_c,
        presupposition_links_matched_count=presupp_match_c,
        matched_links=matched_links,
        unmatched_ref_links=unmatched_ref,
        spurious_pred_links=spurious_pred,
        details={
            "total_ref_links": len(ref_links),
            "total_pred_links": len(pred_links),
        },
    )
