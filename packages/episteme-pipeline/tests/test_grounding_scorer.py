"""Unit tests for multi-modal evidence grounding and IoU scorers.

Verifies:
1. 2D spatial bounding box IoU calculation across formats and page boundaries.
2. Tabular cell intersection IoU with table ID matching.
3. Visual figure grounding with identifier and bounding box overlap.
4. Unified multi-modal anchor routing across modalities.
5. GroundingScorer batch evaluation and threshold filtering.
"""

from __future__ import annotations

import pytest

from episteme_pipeline.evaluation.scorers.grounding import (
    GroundingEvaluationResult,
    GroundingScorer,
    calculate_anchor_iou,
    calculate_bbox_iou,
    calculate_tabular_grounding_iou,
    calculate_visual_grounding_iou,
)


class TestBBoxIoU:
    """Test suite for calculate_bbox_iou."""

    def test_identical_bounding_boxes(self):
        """Verify identical bounding boxes yield 1.0 IoU."""
        b1 = [10.0, 10.0, 50.0, 50.0, 1]
        b2 = [10.0, 10.0, 50.0, 50.0, 1]
        assert calculate_bbox_iou(b1, b2) == 1.0

    def test_partial_spatial_overlap(self):
        """Verify partial 2D overlap computes exact spatial ratio."""
        # Box 1: [10, 10, 50, 50] -> width=40, height=40, area=1600
        # Box 2: [30, 10, 70, 50] -> width=40, height=40, area=1600
        # Intersection: x in [30, 50] (w=20), y in [10, 50] (h=40) -> inter=800
        # Union = 1600 + 1600 - 800 = 2400 -> IoU = 800 / 2400 = 1/3
        b1 = [10.0, 10.0, 50.0, 50.0, 1]
        b2 = [30.0, 10.0, 70.0, 50.0, 1]
        assert pytest.approx(calculate_bbox_iou(b1, b2), 0.001) == 1.0 / 3.0

    def test_disjoint_bounding_boxes(self):
        """Verify disjoint bounding boxes yield 0.0 IoU."""
        b1 = [10.0, 10.0, 50.0, 50.0, 1]
        b2 = [60.0, 60.0, 100.0, 100.0, 1]
        assert calculate_bbox_iou(b1, b2) == 0.0

    def test_page_mismatch_disallows_match(self):
        """Verify identical coordinates on different pages return 0.0 IoU."""
        b1 = [10.0, 10.0, 50.0, 50.0, 1]
        b2 = [10.0, 10.0, 50.0, 50.0, 2]
        assert calculate_bbox_iou(b1, b2) == 0.0

    def test_dict_format_and_none_handling(self):
        """Verify dictionary coordinates and None input handling."""
        d1 = {"x0": 0.0, "y0": 0.0, "x1": 10.0, "y1": 10.0, "page": 1}
        d2 = {"left": 0.0, "top": 0.0, "right": 10.0, "bottom": 10.0, "page": 1}
        assert calculate_bbox_iou(d1, d2) == 1.0

        assert calculate_bbox_iou(None, None) == 1.0
        assert calculate_bbox_iou(d1, None) == 0.0
        assert calculate_bbox_iou(None, d2) == 0.0


class TestTabularAndVisualGrounding:
    """Test suite for tabular and visual grounding IoU functions."""

    def test_tabular_exact_match(self):
        """Verify identical table ID and cell coordinates return 1.0."""
        t1 = {"table_id": "table_1", "cells": [(1, 1), (1, 2)]}
        t2 = {"table_id": "table_1", "cells": [(1, 1), (1, 2)]}
        assert calculate_tabular_grounding_iou(t1, t2) == 1.0

    def test_tabular_partial_overlap(self):
        """Verify partial cell overlap calculates Jaccard index."""
        t1 = {"table_id": "table_1", "cells": [(1, 1), (1, 2)]}
        t2 = {"table_id": "table_1", "cells": [(1, 1), (2, 2)]}
        # intersection = 1, union = 3 -> 1/3
        assert pytest.approx(calculate_tabular_grounding_iou(t1, t2), 0.001) == 1.0 / 3.0

    def test_tabular_mismatched_table_id(self):
        """Verify different table identifiers return 0.0."""
        t1 = {"table_id": "table_1", "cells": [(1, 1)]}
        t2 = {"table_id": "table_2", "cells": [(1, 1)]}
        assert calculate_tabular_grounding_iou(t1, t2) == 0.0

    def test_visual_figure_grounding(self):
        """Verify visual grounding evaluates figure IDs and optional bounding boxes."""
        f1 = {"figure_id": "fig_01", "bbox": [0.0, 0.0, 10.0, 10.0, 1]}
        f2 = {"figure_id": "fig_01", "bbox": [0.0, 0.0, 10.0, 10.0, 1]}
        assert calculate_visual_grounding_iou(f1, f2) == 1.0

        f3 = {"figure_id": "fig_02", "bbox": [0.0, 0.0, 10.0, 10.0, 1]}
        assert calculate_visual_grounding_iou(f1, f3) == 0.0


class TestAnchorRoutingAndScorer:
    """Test suite for calculate_anchor_iou and GroundingScorer."""

    def test_multimodal_anchor_routing(self):
        """Verify calculate_anchor_iou routes to correct modality."""
        # Visual routing
        a_vis1 = {"bbox": [10.0, 10.0, 50.0, 50.0, 1]}
        a_vis2 = {"bbox": [10.0, 10.0, 50.0, 50.0, 1]}
        assert calculate_anchor_iou(a_vis1, a_vis2) == 1.0

        # Tabular routing
        a_tab1 = {"table_id": "tab_1", "cells": [(0, 0)]}
        a_tab2 = {"table_id": "tab_1", "cells": [(0, 0)]}
        assert calculate_anchor_iou(a_tab1, a_tab2) == 1.0

        # Formula routing
        a_form1 = {"formula_id": "eq_01"}
        a_form2 = {"formula_id": "eq_01"}
        assert calculate_anchor_iou(a_form1, a_form2) == 1.0

        # Text character span routing
        a_text1 = {"charStart": 100, "charEnd": 200, "sourceDocId": "doc1"}
        a_text2 = {"charStart": 100, "charEnd": 200, "sourceDocId": "doc1"}
        assert calculate_anchor_iou(a_text1, a_text2) == 1.0

        # Verbatim quote fallback
        a_quote1 = {"verbatimQuote": "force equals mass times acceleration"}
        a_quote2 = {"verbatimQuote": "force equals mass times acceleration"}
        assert calculate_anchor_iou(a_quote1, a_quote2) == 1.0

    def test_grounding_scorer_batch_evaluation(self):
        """Verify GroundingScorer evaluates mixed modality batches."""
        scorer = GroundingScorer(min_iou=0.5)

        refs = [
            {"charStart": 0, "charEnd": 100, "sourceDocId": "doc1"},
            {"bbox": [10.0, 10.0, 50.0, 50.0, 1]},
            {"table_id": "t1", "cells": [(0, 0)]},
            {"formula_id": "eq_newton"},
        ]
        preds = [
            {"charStart": 0, "charEnd": 100, "sourceDocId": "doc1"},  # IoU 1.0
            {"bbox": [10.0, 10.0, 50.0, 50.0, 1]},                    # IoU 1.0
            {"table_id": "t1", "cells": [(0, 0)]},                    # IoU 1.0
            {"formula_id": "eq_schrodinger"},                         # IoU 0.0
        ]

        result = scorer.score(refs, preds)
        assert isinstance(result, GroundingEvaluationResult)
        assert result.sample_count == 4
        assert result.matches == 3
        assert pytest.approx(result.overall_iou, 0.01) == 0.75
        assert result.text_iou == 1.0
        assert result.visual_iou == 1.0
        assert result.tabular_iou == 1.0
        assert result.formula_iou == 0.0
        assert len(result.details) == 4
