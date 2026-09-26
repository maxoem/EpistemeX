"""Multi-Modal Evidence Anchoring and Grounding Scorers.

Evaluates the precision of primary source evidence grounding across multi-modal
modalities (text character spans, 2D document bounding boxes, tables, figures,
and mathematical formula identifiers).

Grounded in document layout analysis and knowledge extraction benchmarks (DocRED,
SciERC, Visual MRC), this module prevents visual/tabular hallucinations by verifying
that predicted assertions are anchored to the exact empirical source regions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class GroundingEvaluationResult(BaseModel):
    """Result container for multi-modal evidence grounding evaluation.

    Parameters
    ----------
    overall_iou : float
        Micro-averaged grounding Intersection over Union (IoU) across all anchors.
    text_iou : float
        Average IoU across textual character span anchors.
    visual_iou : float
        Average 2D spatial IoU across bounding box / figure anchors.
    tabular_iou : float
        Average cell intersection ratio across tabular anchors.
    formula_iou : float
        Average match score across mathematical formula identifiers.
    sample_count : int
        Total number of evaluated evidence anchor pairs.
    matches : int
        Count of anchor pairs achieving IoU >= threshold.
    details : list of dict of str to Any
        Per-sample alignment breakdown and diagnostic errors.
    """

    model_config = ConfigDict(frozen=True)

    overall_iou: float = Field(..., description="Micro-averaged grounding IoU across all modalities.")
    text_iou: float = Field(default=0.0, description="Average IoU for text character spans.")
    visual_iou: float = Field(default=0.0, description="Average 2D spatial IoU for visual bounding boxes.")
    tabular_iou: float = Field(default=0.0, description="Average cell IoU for tabular data.")
    formula_iou: float = Field(default=0.0, description="Average match score for mathematical formulas.")
    sample_count: int = Field(default=0, description="Total evaluated anchor pairs.")
    matches: int = Field(default=0, description="Anchor pairs meeting or exceeding the match threshold.")
    details: list[dict[str, Any]] = Field(default_factory=list, description="Per-anchor alignment breakdown.")


def calculate_bbox_iou(
    bbox_ref: Sequence[float] | Mapping[str, Any] | None,
    bbox_pred: Sequence[float] | Mapping[str, Any] | None,
) -> float:
    """Calculate 2D spatial Intersection over Union (IoU) between bounding boxes.

    Supports coordinate formats:
    - Sequence of 4 or 5 numbers: [x0, y0, x1, y1] or [x0, y0, x1, y1, page]
    - Mapping with keys 'x0', 'y0', 'x1', 'y1' (or 'left', 'top', 'right', 'bottom')
      and optional 'page'.

    Parameters
    ----------
    bbox_ref : Sequence of float or Mapping of str to Any or None
        Reference bounding box region.
    bbox_pred : Sequence of float or Mapping of str to Any or None
        Predicted bounding box region.

    Returns
    -------
    float
        Spatial IoU score in [0.0, 1.0].
    """
    if bbox_ref is None and bbox_pred is None:
        return 1.0
    if bbox_ref is None or bbox_pred is None:
        return 0.0

    def parse_bbox(b: Sequence[float] | Mapping[str, Any]) -> tuple[float, float, float, float, int | None] | None:
        if isinstance(b, Mapping):
            x0 = b.get("x0", b.get("left"))
            y0 = b.get("y0", b.get("top"))
            x1 = b.get("x1", b.get("right"))
            y1 = b.get("y1", b.get("bottom"))
            p = b.get("page")
            if all(v is not None for v in (x0, y0, x1, y1)):
                try:
                    return float(x0), float(y0), float(x1), float(y1), (int(p) if p is not None else None)
                except (ValueError, TypeError):
                    return None
            return None

        if isinstance(b, (list, tuple)) and len(b) >= 4:
            try:
                x0, y0, x1, y1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                page = int(b[4]) if len(b) >= 5 and b[4] is not None else None
                return x0, y0, x1, y1, page
            except (ValueError, TypeError):
                return None
        return None

    r_parsed = parse_bbox(bbox_ref)
    p_parsed = parse_bbox(bbox_pred)
    if r_parsed is None or p_parsed is None:
        return 0.0

    rx0, ry0, rx1, ry1, r_page = r_parsed
    px0, py0, px1, py1, p_page = p_parsed

    # Disallow match across different document pages
    if r_page is not None and p_page is not None and r_page != p_page:
        return 0.0

    inter_x0 = max(rx0, px0)
    inter_y0 = max(ry0, py0)
    inter_x1 = min(rx1, px1)
    inter_y1 = min(ry1, py1)

    inter_w = max(0.0, inter_x1 - inter_x0)
    inter_h = max(0.0, inter_y1 - inter_y0)
    inter_area = inter_w * inter_h

    area_r = max(0.0, rx1 - rx0) * max(0.0, ry1 - ry0)
    area_p = max(0.0, px1 - px0) * max(0.0, py1 - py0)
    union_area = area_r + area_p - inter_area

    if union_area <= 0.0:
        return 1.0 if (area_r == 0.0 and area_p == 0.0) else 0.0
    return float(inter_area) / float(union_area)


def calculate_tabular_grounding_iou(
    ref_anchor: Mapping[str, Any] | None,
    pred_anchor: Mapping[str, Any] | None,
) -> float:
    """Calculate grounding Intersection over Union (IoU) between tabular anchors.

    Compares table identifiers and cell coordinate intersections (row, col).

    Parameters
    ----------
    ref_anchor : Mapping of str to Any or None
        Reference tabular anchor descriptor.
    pred_anchor : Mapping of str to Any or None
        Predicted tabular anchor descriptor.

    Returns
    -------
    float
        Tabular grounding IoU score in [0.0, 1.0].
    """
    if not ref_anchor and not pred_anchor:
        return 1.0
    if not ref_anchor or not pred_anchor:
        return 0.0

    t_ref = ref_anchor.get("table_id") or ref_anchor.get("tableId")
    t_pred = pred_anchor.get("table_id") or pred_anchor.get("tableId")

    if t_ref and t_pred and str(t_ref).strip() != str(t_pred).strip():
        return 0.0

    def extract_cells(a: Mapping[str, Any]) -> set[tuple[int, int]]:
        raw_cells = a.get("cells") or a.get("cell_indices") or []
        res: set[tuple[int, int]] = set()
        for c in raw_cells:
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                try:
                    res.add((int(c[0]), int(c[1])))
                except (ValueError, TypeError):
                    pass
            elif isinstance(c, str) and ":" in c:
                parts = c.split(":")
                try:
                    res.add((int(parts[0]), int(parts[1])))
                except (ValueError, TypeError):
                    pass
        return res

    cells_ref = extract_cells(ref_anchor)
    cells_pred = extract_cells(pred_anchor)

    if not cells_ref and not cells_pred:
        # If no specific cells are specified, table ID match is sufficient
        return 1.0 if (t_ref and t_pred and str(t_ref).strip() == str(t_pred).strip()) else 0.0

    intersection = len(cells_ref & cells_pred)
    union = len(cells_ref | cells_pred)
    return float(intersection) / float(union) if union > 0 else 0.0


def calculate_visual_grounding_iou(
    ref_anchor: Mapping[str, Any] | None,
    pred_anchor: Mapping[str, Any] | None,
) -> float:
    """Calculate grounding Intersection over Union (IoU) between visual/figure anchors.

    Compares figure identifiers and spatial bounding box intersections.

    Parameters
    ----------
    ref_anchor : Mapping of str to Any or None
        Reference visual anchor descriptor.
    pred_anchor : Mapping of str to Any or None
        Predicted visual anchor descriptor.

    Returns
    -------
    float
        Visual grounding IoU score in [0.0, 1.0].
    """
    if not ref_anchor and not pred_anchor:
        return 1.0
    if not ref_anchor or not pred_anchor:
        return 0.0

    fig_ref = ref_anchor.get("figure_id") or ref_anchor.get("figureId")
    fig_pred = pred_anchor.get("figure_id") or pred_anchor.get("figureId")

    if fig_ref and fig_pred and str(fig_ref).strip() != str(fig_pred).strip():
        return 0.0

    b_ref = ref_anchor.get("bbox") or ref_anchor.get("boundingBox")
    b_pred = pred_anchor.get("bbox") or pred_anchor.get("boundingBox")

    if b_ref is not None and b_pred is not None:
        return calculate_bbox_iou(b_ref, b_pred)

    if fig_ref and fig_pred and str(fig_ref).strip() == str(fig_pred).strip():
        return 1.0

    return 0.0


def calculate_anchor_iou(
    anchor_ref: Mapping[str, Any] | None,
    anchor_pred: Mapping[str, Any] | None,
) -> float:
    """Calculate multi-modal Intersection over Union (IoU) between source anchors.

    Supports text character spans, 2D bounding boxes, formula identifiers,
    and tabular/visual grounding references.

    Parameters
    ----------
    anchor_ref : Mapping of str to Any or None
        Reference source anchor coordinates.
    anchor_pred : Mapping of str to Any or None
        Predicted source anchor coordinates.

    Returns
    -------
    float
        Intersection over Union score in [0.0, 1.0].
    """
    if not anchor_ref and not anchor_pred:
        return 1.0
    if not anchor_ref or not anchor_pred:
        return 0.0

    doc_ref = anchor_ref.get("sourceDocId") or anchor_ref.get("source_doc_id")
    doc_pred = anchor_pred.get("sourceDocId") or anchor_pred.get("source_doc_id")
    if doc_ref and doc_pred and str(doc_ref).strip() != str(doc_pred).strip():
        return 0.0

    # 1. Visual / Bounding Box Grounding
    b_ref = anchor_ref.get("bbox") or anchor_ref.get("boundingBox")
    b_pred = anchor_pred.get("bbox") or anchor_pred.get("boundingBox")
    if b_ref is not None and b_pred is not None:
        return calculate_bbox_iou(b_ref, b_pred)

    # 2. Tabular Grounding
    if ("table_id" in anchor_ref or "tableId" in anchor_ref) and (
        "table_id" in anchor_pred or "tableId" in anchor_pred
    ):
        return calculate_tabular_grounding_iou(anchor_ref, anchor_pred)

    # 3. Figure Grounding
    if ("figure_id" in anchor_ref or "figureId" in anchor_ref) and (
        "figure_id" in anchor_pred or "figureId" in anchor_pred
    ):
        return calculate_visual_grounding_iou(anchor_ref, anchor_pred)

    # 4. Mathematical Formula Grounding
    f_ref = anchor_ref.get("formula_id") or anchor_ref.get("formulaId")
    f_pred = anchor_pred.get("formula_id") or anchor_pred.get("formulaId")
    if f_ref and f_pred:
        return 1.0 if str(f_ref).strip() == str(f_pred).strip() else 0.0

    # 5. Character Span Grounding
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

        inter_start = max(s_ref, s_pred)
        inter_end = min(e_ref, e_pred)
        intersection = max(0, inter_end - inter_start)

        union_start = min(s_ref, s_pred)
        union_end = max(e_ref, e_pred)
        union = max(0, union_end - union_start)

        return float(intersection) / float(union) if union > 0 else 0.0

    # 6. Fallback to verbatimQuote token overlap
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


class GroundingScorer:
    """Evaluates multi-modal evidence grounding between predicted and reference assertions.

    Parameters
    ----------
    min_iou : float, default 0.5
        Minimum IoU threshold required to qualify as a valid grounding match.
    """

    def __init__(self, min_iou: float = 0.5) -> None:
        self.min_iou = min_iou

    def score(
        self,
        reference_anchors: Sequence[Mapping[str, Any] | None],
        predicted_anchors: Sequence[Mapping[str, Any] | None],
    ) -> GroundingEvaluationResult:
        """Evaluate a collection of predicted anchors against reference gold anchors.

        Parameters
        ----------
        reference_anchors : Sequence of Mapping of str to Any or None
            Reference gold standard anchors.
        predicted_anchors : Sequence of Mapping of str to Any or None
            Predicted assertion anchors.

        Returns
        -------
        GroundingEvaluationResult
            Synthesized grounding metrics across modalities.
        """
        if len(reference_anchors) != len(predicted_anchors):
            raise ValueError(
                f"Anchor sequence length mismatch: {len(reference_anchors)} ref vs {len(predicted_anchors)} pred."
            )

        total_pairs = len(reference_anchors)
        if total_pairs == 0:
            return GroundingEvaluationResult(
                overall_iou=1.0,
                text_iou=1.0,
                visual_iou=1.0,
                tabular_iou=1.0,
                formula_iou=1.0,
                sample_count=0,
                matches=0,
            )

        ious: list[float] = []
        text_ious: list[float] = []
        visual_ious: list[float] = []
        tabular_ious: list[float] = []
        formula_ious: list[float] = []
        match_count = 0
        details: list[dict[str, Any]] = []

        for i, (ref, pred) in enumerate(zip(reference_anchors, predicted_anchors)):
            iou = calculate_anchor_iou(ref, pred)
            ious.append(iou)
            is_match = iou >= self.min_iou
            if is_match:
                match_count += 1

            modality = "text"
            if ref and ("bbox" in ref or "boundingBox" in ref or "figure_id" in ref or "figureId" in ref):
                modality = "visual"
                visual_ious.append(iou)
            elif ref and ("table_id" in ref or "tableId" in ref):
                modality = "tabular"
                tabular_ious.append(iou)
            elif ref and ("formula_id" in ref or "formulaId" in ref):
                modality = "formula"
                formula_ious.append(iou)
            else:
                text_ious.append(iou)

            details.append(
                {
                    "index": i,
                    "modality": modality,
                    "iou": iou,
                    "is_match": is_match,
                }
            )

        mean_overall = sum(ious) / total_pairs
        mean_text = sum(text_ious) / len(text_ious) if text_ious else 1.0
        mean_visual = sum(visual_ious) / len(visual_ious) if visual_ious else 1.0
        mean_tabular = sum(tabular_ious) / len(tabular_ious) if tabular_ious else 1.0
        mean_formula = sum(formula_ious) / len(formula_ious) if formula_ious else 1.0

        return GroundingEvaluationResult(
            overall_iou=mean_overall,
            text_iou=mean_text,
            visual_iou=mean_visual,
            tabular_iou=mean_tabular,
            formula_iou=mean_formula,
            sample_count=total_pairs,
            matches=match_count,
            details=details,
        )
