"""Unit tests for Confidence Calibration Scorer (ECE, MCE, and Brier Score)."""

from __future__ import annotations

import pytest

from episteme_pipeline.contracts.domain import L2Triple, TheoryRelation
from episteme_pipeline.evaluation.models import EvaluationOutcome
from episteme_pipeline.evaluation.scorers.calibration import (
    CalibrationResult,
    CalibrationScorer,
    ReliabilityBin,
)


class TestCalibrationScorer:
    """Test suite for CalibrationScorer mathematical accuracy and result formats."""

    def test_perfect_calibration(self):
        """Verify ECE and Brier Score for perfectly calibrated predictions."""
        scorer = CalibrationScorer(num_bins=2)
        # Bins: [0.0, 0.5) and [0.5, 1.0]
        # In lower bin: conf 0.2, 0.2 with accuracy 0.0 (gap = 0.2)
        # If perfectly calibrated:
        confidences = [0.1, 0.1, 0.9, 0.9]
        labels = [0, 0, 1, 1]
        res = scorer.compute_calibration(confidences, labels)

        assert isinstance(res, CalibrationResult)
        assert res.sample_count == 4
        assert res.num_bins == 2
        # In bin 0: avg_conf=0.1, acc=0.0 -> gap=0.1
        # In bin 1: avg_conf=0.9, acc=1.0 -> gap=0.1
        assert pytest.approx(res.ece, 0.001) == 0.1
        assert pytest.approx(res.mce, 0.001) == 0.1
        # Brier = ( (0.1-0)^2 * 2 + (0.9-1)^2 * 2 ) / 4 = (0.01*2 + 0.01*2)/4 = 0.01
        assert pytest.approx(res.brier_score, 0.001) == 0.01

    def test_overconfident_hallucination(self):
        """Verify calibration penalizes overconfident wrong predictions."""
        scorer = CalibrationScorer(num_bins=10)
        confidences = [1.0, 1.0, 1.0, 1.0]
        labels = [0, 0, 0, 0]  # All hallucinations
        res = scorer.compute_calibration(confidences, labels)

        assert pytest.approx(res.ece, 0.001) == 1.0
        assert pytest.approx(res.mce, 0.001) == 1.0
        assert pytest.approx(res.brier_score, 0.001) == 1.0

    def test_empty_predictions(self):
        """Verify handling of empty inputs."""
        scorer = CalibrationScorer(num_bins=5)
        res = scorer.compute_calibration([], [])
        assert res.sample_count == 0
        assert res.ece == 0.0
        assert res.mce == 0.0
        assert res.brier_score == 0.0

    def test_mismatched_lengths_raise_error(self):
        """Verify length mismatch raises ValueError."""
        scorer = CalibrationScorer()
        with pytest.raises(ValueError, match="matching length"):
            scorer.compute_calibration([0.5], [1, 0])

    def test_evaluate_with_l2_triples(self):
        """Verify evaluate parses L2Triple predictions against reference triples."""
        scorer = CalibrationScorer(num_bins=5)
        pred_triples = [
            L2Triple(subject_id="e1", predicate="causes", object_id="e2", confidence=0.9, scope="local"),
            L2Triple(subject_id="e2", predicate="inhibits", object_id="e3", confidence=0.8, scope="local"),
            L2Triple(subject_id="e3", predicate="hallucinated", object_id="e4", confidence=0.7, scope="local"),
        ]
        gold_triples = [
            L2Triple(subject_id="e1", predicate="causes", object_id="e2", confidence=1.0, scope="local"),
            L2Triple(subject_id="e2", predicate="inhibits", object_id="e3", confidence=1.0, scope="local"),
        ]

        res = scorer.evaluate(pred_triples, gold_triples)
        assert res.sample_count == 3
        # 2 correct (conf 0.9, 0.8), 1 wrong (conf 0.7)
        assert len(res.bins) == 5

    def test_evaluate_to_result_model(self):
        """Verify evaluate_to_result produces a compliant EvaluationResult."""
        scorer = CalibrationScorer(num_bins=5, max_ece_threshold=0.20, max_brier_threshold=0.25)
        preds = [(0.9, 1), (0.85, 1), (0.2, 0), (0.1, 0)]
        eval_result = scorer.evaluate_to_result(preds, None, run_id="test_run_cal")

        assert eval_result.run_id == "test_run_cal"
        assert eval_result.outcome == EvaluationOutcome.PASS
        assert eval_result.reliability_diagram is not None
        assert len(eval_result.reliability_diagram) == 5

        # Check metric entries
        metric_names = {m.name: m.value for m in eval_result.metrics}
        assert "ece" in metric_names
        assert "mce" in metric_names
        assert "brier_score" in metric_names
        assert metric_names["ece"] <= 0.20
        assert "markdown_report" in eval_result.notes
