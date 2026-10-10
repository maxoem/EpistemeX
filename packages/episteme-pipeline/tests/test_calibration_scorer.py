"""Unit tests for Confidence Calibration Scorer (ECE, MCE, and Brier Score)."""

from __future__ import annotations

import networkx as nx
import pytest

from episteme_pipeline.contracts.domain import L2Triple, TheoryAtom, TheoryNet, TheoryRelation
from episteme_pipeline.evaluation.models import EvaluationOutcome
from episteme_pipeline.evaluation.scorers.calibration import (
    CalibrationDataExtractor,
    CalibrationResult,
    CalibrationScorer,
    DefaultCalibrationDataExtractor,
    compute_calibration_metrics,
)
from epistemetrics.core.models import RelationType, TheoryEdge
from epistemetrics.graph.theory_graph import TheoryGraph


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

    def test_evaluate_with_theory_edges(self):
        """Verify evaluate parses epistemetrics TheoryEdge objects with empirical accuracy."""
        scorer = CalibrationScorer(num_bins=5)
        pred_edges = [
            TheoryEdge(
                source="c1",
                target="c2",
                relation_type=RelationType.EXPLAINS,
                confidence=0.8,
                empirical_accuracy=0.85,
            ),
            TheoryEdge(
                source="c2",
                target="c3",
                relation_type=RelationType.SUPPORTS,
                confidence=0.7,
                class_probability=0.75,
            ),
            TheoryEdge(
                source="c3",
                target="c4",
                relation_type=RelationType.ATTACKS,
                confidence=0.6,
            ),
        ]
        gold_edges = [
            TheoryEdge(
                source="c1",
                target="c2",
                relation_type=RelationType.EXPLAINS,
            ),
            TheoryEdge(
                source="c2",
                target="c3",
                relation_type=RelationType.SUPPORTS,
            ),
        ]
        res = scorer.evaluate(pred_edges, gold_edges)
        assert res.sample_count == 3
        assert len(res.bins) == 5

    def test_evaluate_with_theory_net(self):
        """Verify evaluate extracts relations from TheoryNet containers."""
        scorer = CalibrationScorer(num_bins=5)
        pred_net = TheoryNet(
            atoms=[
                TheoryAtom(id="a1", text="Atom 1", component_type="CLAIM", source_chunk_id="chunk_1"),
                TheoryAtom(id="a2", text="Atom 2", component_type="PREMISE", source_chunk_id="chunk_1"),
            ],
            relations=[
                TheoryRelation(
                    source_id="a2",
                    target_id="a1",
                    relation_type="SUPPORTS",
                    confidence=0.9,
                    scope="global",
                    calibrated_confidence=0.88,
                ),
            ],
        )
        gold_net = TheoryNet(
            atoms=[],
            relations=[
                TheoryRelation(
                    source_id="a2",
                    target_id="a1",
                    relation_type="SUPPORTS",
                    confidence=1.0,
                    scope="global",
                ),
            ],
        )
        res = scorer.evaluate(pred_net, gold_net)
        assert res.sample_count == 1
        assert pytest.approx(res.ece, 0.001) == abs(1.0 - 0.88)

    def test_evaluate_with_theory_graph(self):
        """Verify evaluate extracts edges from TheoryGraph instances."""
        scorer = CalibrationScorer(num_bins=5)
        pred_tg = TheoryGraph(name="pred")
        gold_tg = TheoryGraph(name="gold")

        pred_tg.add_edge(
            source="n1",
            target="n2",
            relation_type=RelationType.EXPLAINS,
            confidence=0.95,
        )
        gold_tg.add_edge(
            source="n1",
            target="n2",
            relation_type=RelationType.EXPLAINS,
            confidence=1.0,
        )

        res = scorer.evaluate(pred_tg, gold_tg)
        assert res.sample_count == 1

    def test_evaluate_with_networkx_digraph(self):
        """Verify evaluate extracts edge data from NetworkX DiGraph."""
        scorer = CalibrationScorer(num_bins=5)
        g_pred = nx.DiGraph()
        g_pred.add_edge("u1", "v1", relation_type="CAUSES", confidence=0.8)
        g_pred.add_edge("u2", "v2", relation_type="INHIBITS", confidence=0.4)

        g_gold = nx.DiGraph()
        g_gold.add_edge("u1", "v1", relation_type="CAUSES")

        res = scorer.evaluate(g_pred, g_gold)
        assert res.sample_count == 2

    def test_compute_calibration_metrics_pure_function(self):
        """Verify standalone compute_calibration_metrics computes identical metrics."""
        confidences = [0.2, 0.4, 0.6, 0.8]
        labels = [0, 0, 1, 1]
        res = compute_calibration_metrics(confidences, labels, num_bins=4)

        assert isinstance(res, CalibrationResult)
        assert res.sample_count == 4
        assert res.num_bins == 4
        assert len(res.bins) == 4

        with pytest.raises(ValueError, match="num_bins must be a positive integer"):
            compute_calibration_metrics(confidences, labels, num_bins=0)

    def test_custom_calibration_data_extractor_injection(self):
        """Verify CalibrationScorer accepts custom CalibrationDataExtractor implementation."""
        class CustomMockExtractor:
            """Mock extractor for testing port injection."""

            def extract_predictions(self, data: Any) -> list[tuple[str, float]]:
                return [("custom::rel_1", 0.95), ("custom::rel_2", 0.25)]

            def extract_gold_keys(self, data: Any) -> set[str]:
                return {"custom::rel_1"}

        custom_extractor = CustomMockExtractor()
        assert isinstance(custom_extractor, CalibrationDataExtractor)

        scorer = CalibrationScorer(num_bins=2, extractor=custom_extractor)
        res = scorer.evaluate("dummy_pred_input", "dummy_gold_input")

        assert res.sample_count == 2
        # rel_1 matched (conf 0.95, label 1), rel_2 not in gold (conf 0.25, label 0)
        assert res.brier_score < 0.1

    def test_default_extractor_atoms_and_relations(self):
        """Verify DefaultCalibrationDataExtractor directly extracts typed atoms and relations."""
        extractor = DefaultCalibrationDataExtractor()
        atom = TheoryAtom(id="atom_1", text="Test Atom", component_type="CLAIM", source_chunk_id="chunk_1", plausibility=0.85)
        rel = TheoryRelation(
            source_id="atom_1",
            target_id="atom_2",
            relation_type="SUPPORTS",
            confidence=0.8,
            calibrated_confidence=0.92,
            scope="global",
        )

        preds = extractor.extract_predictions([atom, rel])
        assert len(preds) == 2
        assert preds[0] == ("atom_1::claim", 0.85)
        assert preds[1] == ("atom_1::supports::atom_2", 0.92)

        golds = extractor.extract_gold_keys([atom, rel])
        assert golds == {"atom_1", "atom_1::supports::atom_2"}
