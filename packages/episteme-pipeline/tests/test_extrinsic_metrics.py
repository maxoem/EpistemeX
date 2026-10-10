"""Tests for extrinsic evaluation metrics."""

from __future__ import annotations

import pytest
from episteme_pipeline.contracts.domain import SearchResult
from episteme_pipeline.evaluation.extrinsic import (
    calculate_hits_at_k,
    calculate_mrr,
    calculate_ndcg,
)
from episteme_pipeline.evaluation.scorers.retrieval import (
    ExtrinsicRetrievalEvaluator,
)
from episteme_pipeline.evaluation.scorers.retrieval_scorer import (
    ExtrinsicRetrievalEvaluator as AliasEvaluator,
)
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore


class TestMRR:
    def test_mrr_perfect_ranking(self):
        rankings = [["a", "b", "c"]]
        gold_standards = [{"a"}]
        assert calculate_mrr(rankings, gold_standards) == 1.0

    def test_mrr_second_position(self):
        rankings = [["b", "a", "c"]]
        gold_standards = [{"a"}]
        assert calculate_mrr(rankings, gold_standards) == 0.5

    def test_mrr_no_relevant(self):
        rankings = [["b", "c", "d"]]
        gold_standards = [{"a"}]
        assert calculate_mrr(rankings, gold_standards) == 0.0

    def test_mrr_empty_input(self):
        assert calculate_mrr([], []) == 0.0


class TestHitsAtK:
    def test_hits_at_k_hit(self):
        rankings = [["a", "b", "c"]]
        gold_standards = [{"b"}]
        assert calculate_hits_at_k(rankings, gold_standards, k=2) == 1.0

    def test_hits_at_k_miss(self):
        rankings = [["a", "b", "c"]]
        gold_standards = [{"c"}]
        assert calculate_hits_at_k(rankings, gold_standards, k=2) == 0.0


class TestNDCG:
    def test_ndcg_perfect(self):
        rankings = [["a", "b", "c"]]
        gold_standards = [{"a": 1.0, "b": 0.5}]
        assert calculate_ndcg(rankings, gold_standards, k=3) == 1.0

    def test_ndcg_empty(self):
        assert calculate_ndcg([], []) == 0.0

    def test_ndcg_partial(self):
        rankings = [["c", "a", "b"]]
        gold_standards = [{"a": 1.0, "b": 0.5}]
        ndcg = calculate_ndcg(rankings, gold_standards, k=3)
        assert 0.0 < ndcg < 1.0


class TestMetricsBounded:
    def test_metrics_bounded(self):
        rankings = [["a", "b", "c"], ["d", "e", "f"]]
        gold_sets = [{"a", "c"}, {"g"}]
        gold_dicts = [{"a": 1.0, "c": 0.5}, {"g": 1.0}]

        mrr = calculate_mrr(rankings, gold_sets)
        assert 0.0 <= mrr <= 1.0

        hits = calculate_hits_at_k(rankings, gold_sets, k=2)
        assert 0.0 <= hits <= 1.0

        ndcg = calculate_ndcg(rankings, gold_dicts, k=2)
        assert 0.0 <= ndcg <= 1.0


class MockGraphReader:
    def __init__(self, results: list[SearchResult]):
        self.results = results
        self.last_run_id = None
        self.last_k = None

    async def vector_search(self, embedding, top_k, node_label=None, run_id=None):
        self.last_run_id = run_id
        self.last_k = top_k
        return self.results[:top_k]


class TestExtrinsicRetrievalEvaluator:
    """Test suite for ISSUE-032 Extrinsic Retrieval Scorer and SearchResult fix."""

    @pytest.mark.asyncio
    async def test_search_result_node_id_property_access(self):
        """Verify res.node_id is accessed without AttributeError."""
        mock_results = [
            SearchResult(
                node_id="str:M_CPM_Newton2",
                score=0.98,
                node_label="ActualModel",
                node_name="Newton 2",
            ),
            SearchResult(
                node_id="str:M_CPM_Newton1",
                score=0.75,
                node_label="ActualModel",
                node_name="Newton 1",
            ),
        ]
        reader = MockGraphReader(mock_results)
        evaluator = ExtrinsicRetrievalEvaluator(graph_reader=reader)

        # Query targeting Newton 2
        metrics = await evaluator.evaluate_query(
            query="impressed force acceleration",
            gold_node_ids={"str:M_CPM_Newton2"},
            top_k=5,
        )

        assert metrics["MRR"] == 1.0
        assert metrics["Hits@1"] == 1.0
        assert metrics["Hits@3"] == 1.0
        assert metrics["Hits@10"] == 1.0
        assert metrics["nDCG"] == 1.0

    @pytest.mark.asyncio
    async def test_scoped_run_id_forwarding(self):
        """Verify run_id parameter is passed to vector_search."""
        mock_results = [
            SearchResult(node_id="n1", score=1.0, node_label="Law", node_name="N1")
        ]
        reader = MockGraphReader(mock_results)
        evaluator = ExtrinsicRetrievalEvaluator(graph_reader=reader)

        await evaluator.evaluate_query(
            query="test query",
            gold_node_ids={"n1"},
            top_k=5,
            run_id="run_slice_123",
        )
        assert reader.last_run_id == "run_slice_123"
        assert reader.last_k == 5

    @pytest.mark.asyncio
    async def test_batch_evaluation_averaging(self):
        """Verify evaluate_batch computes macro averages across multiple queries."""
        mock_results = [
            SearchResult(node_id="q1_target", score=0.9, node_label="Law", node_name="Q1"),
            SearchResult(node_id="other", score=0.8, node_label="Law", node_name="Other"),
            SearchResult(node_id="q2_target", score=0.7, node_label="Law", node_name="Q2"),
        ]
        reader = MockGraphReader(mock_results)
        evaluator = ExtrinsicRetrievalEvaluator(graph_reader=reader)

        batch_queries = [
            {"query": "Query 1", "gold_target_ids": ["q1_target"]},  # Rank 1 -> MRR 1.0
            {"query": "Query 2", "gold_target_ids": ["q2_target"]},  # Rank 3 -> MRR 1/3 ~ 0.333
        ]

        summary = await evaluator.evaluate_batch(batch_queries, top_k=5)
        expected_mrr = (1.0 + (1.0 / 3.0)) / 2.0
        assert pytest.approx(summary["MRR"], rel=1e-3) == expected_mrr
        assert pytest.approx(summary["Hits@1"], rel=1e-3) == 0.5
        assert summary["Hits@3"] == 1.0
        assert summary["Hits@10"] == 1.0

    def test_retrieval_scorer_alias_import(self):
        """Verify retrieval_scorer.py backward-compatibility alias."""
        assert AliasEvaluator is ExtrinsicRetrievalEvaluator

    @pytest.mark.asyncio
    async def test_offline_in_memory_retrieval_with_deterministic_embedder(self):
        """Verify zero-dependency offline retrieval using InMemoryGraphStore."""
        store = InMemoryGraphStore()
        await store.upsert_node(
            label="ActualModel",
            node_id="str:M_CPM_Newton2",
            properties={
                "name": "Newton Second Law",
                "formalAxiom": "F = m * a",
                "text": "The alteration of motion is ever proportional to the motive force impressed",
            },
        )
        await store.upsert_node(
            label="ActualModel",
            node_id="str:M_CPM_Hooke",
            properties={
                "name": "Hooke Law",
                "formalAxiom": "F = -k * x",
                "text": "Restoring spring elastic tension proportional to displacement distance",
            },
        )

        evaluator = ExtrinsicRetrievalEvaluator(graph_reader=store)
        metrics = await evaluator.evaluate_query(
            query="proportional to motive force impressed",
            gold_node_ids={"str:M_CPM_Newton2"},
            top_k=2,
        )

        assert metrics["MRR"] == 1.0
        assert metrics["Hits@1"] == 1.0
        assert metrics["nDCG"] == 1.0
