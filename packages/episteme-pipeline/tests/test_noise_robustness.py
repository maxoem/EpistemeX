"""Unit tests for noise robustness perturbation benchmarking and RDF calculation."""

from __future__ import annotations

import networkx as nx
import pytest

from episteme_pipeline.contracts.domain import L2Triple
from episteme_pipeline.evaluation.models import DatasetType, EvaluationOutcome
from episteme_pipeline.evaluation.strategies import (
    ExtractionStrategy,
    NoiseRobustnessStrategy,
    apply_entity_synonym_swaps,
    apply_graph_perturbation,
    apply_sentence_shuffling,
    apply_typo_noise,
    compute_rdf,
    default_registry,
)


class TestNoisePerturbations:
    """Test suite for adversarial text mutations and graph perturbations."""

    def test_apply_typo_noise(self):
        """Verify adversarial character mutations."""
        text = "Epistemic theories require rigorous formal proof and empirical validation."
        noisy = apply_typo_noise(text, typo_rate=1.0, seed=42)
        assert noisy != text
        # Word count should remain identical
        assert len(noisy.split()) == len(text.split())

    def test_apply_sentence_shuffling(self):
        """Verify discourse sentence order shuffling."""
        text = "First sentence here. Second sentence follows. Third sentence concludes."
        shuffled = apply_sentence_shuffling(text, seed=42)
        assert "sentence" in shuffled
        assert len(shuffled.split(".")) == len(text.split("."))

    def test_apply_entity_synonym_swaps(self):
        """Verify canonical entity synonym replacements."""
        text = "Albert Einstein formulated the theory of Special Relativity in 1905."
        synonyms = {"Albert Einstein": "A. Einstein", "Special Relativity": "SR"}
        swapped = apply_entity_synonym_swaps(text, synonyms=synonyms)
        assert "A. Einstein" in swapped
        assert "SR" in swapped
        assert "Special Relativity" not in swapped

    def test_apply_graph_perturbation(self):
        """Verify edge dropout on NetworkX DiGraphs."""
        g = nx.DiGraph()
        for i in range(10):
            g.add_edge(f"n{i}", f"n{i+1}", label="RELATES_TO")
        assert g.number_of_edges() == 10

        perturbed = apply_graph_perturbation(g, drop_rate=0.30, seed=42)
        assert perturbed.number_of_edges() == 7

    def test_compute_rdf(self):
        """Verify Robustness Degradation Factor (RDF) mathematical formula."""
        # 1. Zero degradation (f1_clean == f1_perturbed) -> RDF = 0.0
        assert compute_rdf(1.0, 1.0) == 0.0
        assert compute_rdf(0.8, 0.8) == 0.0

        # 2. 25% degradation (f1_clean = 0.8, f1_pert = 0.6) -> RDF = 1 - 0.75 = 0.25
        assert pytest.approx(compute_rdf(0.8, 0.6), 0.001) == 0.25

        # 3. Complete collapse (f1_clean = 0.8, f1_pert = 0.0) -> RDF = 1.0
        assert compute_rdf(0.8, 0.0) == 1.0

        # 4. Zero clean baseline
        assert compute_rdf(0.0, 0.0) == 0.0


class TestNoiseRobustnessStrategy:
    """Test suite for NoiseRobustnessStrategy execution."""

    @pytest.mark.asyncio
    async def test_evaluate_noise_robustness(self):
        """Verify evaluation of clean vs perturbed predictions."""
        gold_triples = [
            L2Triple(subject_id="e1", predicate="causes", object_id="e2", confidence=1.0, scope="local"),
            L2Triple(subject_id="e2", predicate="inhibits", object_id="e3", confidence=1.0, scope="local"),
            L2Triple(subject_id="e3", predicate="activates", object_id="e4", confidence=1.0, scope="local"),
            L2Triple(subject_id="e4", predicate="binds", object_id="e5", confidence=1.0, scope="local"),
        ]
        pred_triples = list(gold_triples)

        strategy = NoiseRobustnessStrategy(drop_rate=0.5, seed=42, max_rdf_threshold=0.6)
        results = await strategy.evaluate(pred_triples, gold_triples, run_id="stress_run")

        assert len(results) == 1
        res = results[0]
        assert res.dataset_type == DatasetType.STRESS_TEST
        assert res.robustness_factor is not None

        metric_dict = {m.name: m.value for m in res.metrics}
        assert "rdf" in metric_dict
        assert "f1_clean" in metric_dict
        assert "f1_perturbed" in metric_dict
        assert metric_dict["f1_clean"] == 1.0
        assert metric_dict["f1_perturbed"] < 1.0
        assert res.robustness_factor == metric_dict["rdf"]

    def test_registry_resolution(self):
        """Verify StrategyRegistry resolves robustness aliases and infers stress_test."""
        strat = default_registry.get("robustness")
        assert isinstance(strat, NoiseRobustnessStrategy)
        assert isinstance(default_registry.get("stress_test"), NoiseRobustnessStrategy)

        inferred = default_registry.infer(dataset_type="stress_test")
        assert isinstance(inferred, NoiseRobustnessStrategy)
