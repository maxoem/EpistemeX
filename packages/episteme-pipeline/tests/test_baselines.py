"""Unit tests verifying comparative baselines for ISSUE-033.

Tests BaselineTextRAG, BaselineNaiveKG, BaselineZeroShotLLM, and comparative
delta scoring in EvaluationHarness deterministically without live LLM calls.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import networkx as nx
import pytest

from episteme_pipeline.contracts.domain import L1Chunk, L2Entity, L2Triple, TheoryAtom, TheoryNet, TheoryRelation
from episteme_pipeline.evaluation.baselines import (
    BaselineNaiveKG,
    BaselineTextRAG,
    BaselineZeroShotLLM,
)
from episteme_pipeline.evaluation.comparison import (
    ComparisonAxis,
    RunComparison,
    compute_run_comparisons,
    format_comparison_markdown,
    is_higher_better,
)
from episteme_pipeline.evaluation.harness import EvaluationHarness
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore


@pytest.fixture
def sample_chunks() -> list[L1Chunk]:
    """Provide deterministic test chunks with structuralist text anchors."""
    return [
        L1Chunk(
            id="chunk_newton_2",
            text="The alteration of motion is ever proportional to the motive force impress'd; and is made in the direction of the right line in which that force is impress'd.",
            source_doc_id="principia_1687",
            sequence_index=0,
            token_count=28,
            metadata={"anchored_node_id": "str:M_CPM_Newton2"},
        ),
        L1Chunk(
            id="chunk_hooke",
            text="The restoring elastic force in a coiled spring is proportional to displacement distance from resting equilibrium.",
            source_doc_id="principia_1687",
            sequence_index=1,
            token_count=16,
            metadata={"anchored_node_id": "str:M_CPM_Hooke"},
        ),
        L1Chunk(
            id="chunk_mass",
            text="The mass of a body remains invariant across spatial coordinate transformations and different observational setups.",
            source_doc_id="principia_1687",
            sequence_index=2,
            token_count=15,
            metadata={"anchored_node_id": "str:GC_Mass"},
        ),
    ]


@pytest.fixture
def sample_queries() -> list[dict[str, Any]]:
    """Provide competency test queries."""
    return [
        {
            "id": "q1",
            "query": "proportional to motive force impressed motion alteration",
            "gold_target_ids": ["str:M_CPM_Newton2"],
        },
        {
            "id": "q2",
            "query": "restoring elastic spring force displacement",
            "gold_target_ids": ["str:M_CPM_Hooke"],
        },
        {
            "id": "q3",
            "query": "body mass remains invariant across coordinate frames",
            "gold_target_ids": ["str:GC_Mass"],
        },
    ]


@pytest.fixture
def pilot_manifest_path() -> Path:
    """Path to STNB pilot evaluation manifest."""
    return Path(__file__).parent.parent / "episteme_pipeline" / "evaluation" / "manifests" / "eval_stnb.yaml"


@pytest.fixture
def pilot_data_path() -> Path:
    """Path to STNB CPM pilot JSON-LD data."""
    return Path(__file__).parent.parent / "episteme_pipeline" / "evaluation" / "data" / "stnb_cpm_pilot.jsonld"


# ---------------------------------------------------------------------------
# BaselineTextRAG Tests
# ---------------------------------------------------------------------------


class TestBaselineTextRAG:
    """Deterministic tests for BaselineTextRAG."""

    @pytest.mark.asyncio
    async def test_indexing_chunks_without_graph_structure(self, sample_chunks: list[L1Chunk]):
        """Verify chunks are indexed into graph store without creating entities or relations."""
        store = InMemoryGraphStore()
        baseline = BaselineTextRAG(graph_store=store)

        count = baseline.index_chunks(sample_chunks, run_id="test_rag")
        assert count == len(sample_chunks)

        # Graph store should only have chunks, no entities or theory atoms
        indexed_chunks = await store.get_chunks()
        assert len(indexed_chunks) == 3
        entities = await store.get_entities()
        assert len(entities) == 0
        triples = await store.get_all_entity_triples()
        assert len(triples) == 0
        atoms = await store.get_theory_atoms()
        assert len(atoms) == 0

    @pytest.mark.asyncio
    async def test_evaluate_queries_with_anchor_mapping(
        self,
        sample_chunks: list[L1Chunk],
        sample_queries: list[dict[str, Any]],
    ):
        """Verify queries targeting anchored nodes achieve hits against raw chunks."""
        store = InMemoryGraphStore()
        baseline = BaselineTextRAG(graph_store=store)
        baseline.index_chunks(sample_chunks, run_id="test_rag")

        metrics = await baseline.evaluate_queries(
            queries=sample_queries,
            chunks=sample_chunks,
            top_k=3,
            run_id="test_rag",
        )

        assert metrics["MRR"] > 0.0
        assert metrics["Hits@1"] > 0.0
        assert metrics["nDCG"] > 0.0

    @pytest.mark.asyncio
    async def test_run_and_evaluate_with_pilot_files(self, pilot_data_path: Path):
        """Verify run_and_evaluate end-to-end execution on STNB pilot benchmark."""
        queries_path = pilot_data_path.parent / "stnb_cpm_queries.yaml"
        baseline = BaselineTextRAG()

        result, meta = await baseline.run_and_evaluate(
            corpus=pilot_data_path,
            queries=queries_path,
            run_id="test_pilot_rag",
            top_k=5,
        )

        assert result.run_id == "test_pilot_rag"
        assert result.phase_name == "Baseline: Flat Text RAG"
        metric_names = {m.name for m in result.metrics}
        assert "mrr" in metric_names
        assert "hits@1" in metric_names
        assert "latency" in metric_names
        assert "token_cost" in metric_names
        assert meta["latency"] > 0.0
        assert meta["token_cost"] == 0.0


# ---------------------------------------------------------------------------
# BaselineNaiveKG Tests
# ---------------------------------------------------------------------------


class TestBaselineNaiveKG:
    """Deterministic tests for BaselineNaiveKG."""

    def test_heuristic_extraction_from_scientific_sentences(self):
        """Verify schema-guided Open-IE extracts entities and relation triples."""
        baseline = BaselineNaiveKG()
        sample_text = (
            "Hookean Force specializes Classical Particle Mechanics. "
            "Newton Second Law implies alteration of motion. "
            "Empirical evidence supports theoretical statement."
        )

        entities, triples = baseline.extract(sample_text)
        assert len(entities) > 0
        assert len(triples) > 0

        # Check extracted predicates match canonical schema relations
        predicates = {t.predicate for t in triples}
        assert "SPECIALIZES" in predicates or "IMPLIES" in predicates or "SUPPORTS" in predicates

    def test_build_digraph(self):
        """Verify build_graph outputs a valid NetworkX DiGraph with schema polarity."""
        baseline = BaselineNaiveKG()
        sample_text = "Theory Element specializes Core Formalism."

        graph = baseline.build_graph(sample_text)
        assert isinstance(graph, nx.DiGraph)
        assert len(graph.nodes) >= 2
        assert len(graph.edges) >= 1
        edge_data = list(graph.edges(data=True))[0][2]
        assert "polarity" in edge_data

    def test_custom_schema_and_polarity_injection(self):
        """Verify BaselineNaiveKG extracts domain relations and assigns polarity from custom schema."""
        from episteme_pipeline.schema.default_schema import SchemaConfig
        custom_schema = SchemaConfig(
            relation_types=["BINDS_TO", "INHIBITS"],
            relation_polarities={"BINDS_TO": 0, "INHIBITS": -1},
        )
        baseline = BaselineNaiveKG(schema=custom_schema)
        sample_text = "Protein kinase binds to substrate. Drug inhibitor inhibits enzyme."

        entities, triples = baseline.extract(sample_text)
        predicates = {t.predicate for t in triples}
        assert "BINDS_TO" in predicates
        assert "INHIBITS" in predicates

        graph = baseline.build_graph(sample_text)
        for u, v, data in graph.edges(data=True):
            if data["label"] == "INHIBITS":
                assert data["polarity"] == -1
            elif data["label"] == "BINDS_TO":
                assert data["polarity"] == 0

    def test_custom_extractor_injection(self):
        """Verify custom extractor_fn overrides heuristic extraction."""
        def custom_extractor(text: str):
            ents = [
                L2Entity(id="custom_a", name="Custom A", label="Concept"),
                L2Entity(id="custom_b", name="Custom B", label="Concept"),
            ]
            trips = [
                L2Triple(subject_id="custom_a", predicate="SUPPORTS", object_id="custom_b", confidence=1.0, scope="local")
            ]
            return ents, trips

        baseline = BaselineNaiveKG(extractor_fn=custom_extractor)
        entities, triples = baseline.extract("Any text ignored")
        assert len(entities) == 2
        assert entities[0].id == "custom_a"
        assert len(triples) == 1
        assert triples[0].predicate == "SUPPORTS"

    @pytest.mark.asyncio
    async def test_run_and_evaluate_with_gold_dict(self):
        """Verify run_and_evaluate evaluates flat KG via ExtractionStrategy with polarity concordance."""
        gold = {
            "l2_entities": [
                L2Entity(id="force", name="force", label="Entity"),
                L2Entity(id="acceleration", name="acceleration", label="Entity"),
            ],
            "l2_triples": [
                L2Triple(subject_id="force", predicate="IMPLIES", object_id="acceleration", confidence=1.0, scope="local")
            ],
        }

        def mock_extractor(text: str):
            ents = [
                L2Entity(id="force", name="force", label="Entity"),
                L2Entity(id="acceleration", name="acceleration", label="Entity"),
            ]
            trips = [
                L2Triple(subject_id="force", predicate="IMPLIES", object_id="acceleration", confidence=1.0, scope="local")
            ]
            return ents, trips

        baseline = BaselineNaiveKG(extractor_fn=mock_extractor)
        results, meta = await baseline.run_and_evaluate(
            corpus="force implies acceleration",
            gold=gold,
            run_id="test_mock_nkg",
        )

        assert len(results) == 1
        res = results[0]
        metric_dict = {m.name: m.value for m in res.metrics}
        assert metric_dict["entity_f1"] == 1.0
        assert metric_dict["relation_f1"] == 1.0
        assert metric_dict["hallucination_rate"] == 0.0
        assert metric_dict["polarity_accuracy"] == 1.0
        assert metric_dict["polarity_conflict_rate"] == 0.0
        assert meta["token_cost"] == 0.0


# ---------------------------------------------------------------------------
# BaselineZeroShotLLM Tests
# ---------------------------------------------------------------------------


class TestBaselineZeroShotLLM:
    """Deterministic tests for BaselineZeroShotLLM."""

    def test_single_pass_pattern_extraction(self):
        """Verify deterministic single-pass extractor extracts TheoryAtoms and relations."""
        baseline = BaselineZeroShotLLM()
        text = (
            "We define the Potential Models Mp_CPM as kinematic states. "
            "Newton's Second Law M_CPM_Newton2 models impressed force. "
            "Hooke's Law M_CPM_Hooke specializes M_CPM_Newton2. "
            "Mass invariance GC_Mass constraints the domain."
        )

        theory_net = baseline.extract_theory_net(text)
        assert isinstance(theory_net, TheoryNet)
        assert len(theory_net.atoms) >= 3

        comp_types = {a.component_type for a in theory_net.atoms}
        assert "PotentialModel" in comp_types
        assert "ActualModel" in comp_types
        assert "Constraint" in comp_types

        # Should infer specialization relation
        assert len(theory_net.relations) >= 1
        assert theory_net.relations[0].relation_type == "specializes"

    def test_custom_extract_fn_injection(self):
        """Verify custom extract_fn is honored for deterministic mock testing."""
        def custom_fn(text: str):
            return TheoryNet(
                atoms=[
                    TheoryAtom(id="str:Mp_CPM", text="Kinematics", component_type="PotentialModel", source_chunk_id="c0"),
                    TheoryAtom(id="str:M_CPM_Newton2", text="F=ma", component_type="ActualModel", source_chunk_id="c1"),
                ],
                relations=[],
            )

        baseline = BaselineZeroShotLLM(extract_fn=custom_fn)
        net = baseline.extract_theory_net("Sample text")
        assert len(net.atoms) == 2
        assert net.atoms[0].id == "str:Mp_CPM"

    @pytest.mark.asyncio
    async def test_run_and_evaluate_with_stnb_pilot(self, pilot_data_path: Path):
        """Verify run_and_evaluate produces structuralist evaluation result."""
        baseline = BaselineZeroShotLLM()
        results, meta = await baseline.run_and_evaluate(
            corpus=pilot_data_path,
            gold=pilot_data_path,
            run_id="test_pilot_zs",
        )

        assert len(results) == 1
        res = results[0]
        metric_dict = {m.name: m.value for m in res.metrics}
        assert "mcc" in metric_dict
        assert "aor" in metric_dict
        assert "pfs" in metric_dict
        assert "ag_iou" in metric_dict
        assert meta["token_cost"] == 0.0


# ---------------------------------------------------------------------------
# Comparative Scoring & Harness Tests
# ---------------------------------------------------------------------------


class TestComparativeScoring:
    """Tests for RunComparison, compute_run_comparisons, and EvaluationHarness integration."""

    def test_is_higher_better(self):
        """Verify directionality detection across evaluation metrics."""
        assert is_higher_better("f1") is True
        assert is_higher_better("mrr") is True
        assert is_higher_better("mcc") is True
        assert is_higher_better("pfs") is True
        assert is_higher_better("hits@1") is True
        assert is_higher_better("latency") is False
        assert is_higher_better("token_cost") is False
        assert is_higher_better("hallucination_rate") is False
        assert is_higher_better("aor") is False

    def test_compute_run_comparisons_delta_and_winner(self):
        """Verify pairwise comparisons calculate correct deltas and winners."""
        baseline_metrics = {
            "f1": 0.60,
            "mrr": 0.40,
            "latency": 0.02,
            "token_cost": 0.0,
        }
        pipeline_metrics = {
            "f1": 0.85,
            "mrr": 0.70,
            "latency": 0.05,
            "token_cost": 0.01,
        }

        comparisons = compute_run_comparisons(
            run_id_a="base_01",
            run_id_b="pipe_01",
            metrics_a=baseline_metrics,
            metrics_b=pipeline_metrics,
            axis=ComparisonAxis.METHOD,
        )

        comp_dict = {c.metric_name: c for c in comparisons}
        assert pytest.approx(comp_dict["f1"].delta, rel=1e-3) == 0.25
        assert comp_dict["f1"].winner == "b"

        assert pytest.approx(comp_dict["mrr"].delta, rel=1e-3) == 0.30
        assert comp_dict["mrr"].winner == "b"

        # For latency and token cost, lower is better -> baseline wins
        assert pytest.approx(comp_dict["latency"].delta, rel=1e-3) == 0.03
        assert comp_dict["latency"].winner == "a"

        assert pytest.approx(comp_dict["token_cost"].delta, rel=1e-3) == 0.01
        assert comp_dict["token_cost"].winner == "a"

    def test_format_comparison_markdown(self):
        """Verify markdown report formatting."""
        comps = [
            RunComparison(
                run_id_a="base",
                run_id_b="pipe",
                metric_name="mrr",
                value_a=0.38,
                value_b=0.58,
                delta=0.20,
                winner="b",
            )
        ]
        md = format_comparison_markdown(comps, title="MRR Delta Test")
        assert "### MRR Delta Test" in md
        assert "| `mrr` | 0.3800 | 0.5800 | +0.2000 | Pipeline |" in md

    @pytest.mark.asyncio
    async def test_harness_evaluate_manifest_with_baseline_text_rag(self, pilot_manifest_path: Path):
        """Verify EvaluationHarness CLI / API integration with --baseline text_rag."""
        harness = EvaluationHarness()
        report = await harness.evaluate_manifest(
            manifest_path=pilot_manifest_path,
            baseline="text_rag",
        )

        assert len(report.run_ids) == 2
        assert any(rid.startswith("baseline_text_rag") for rid in report.run_ids)
        assert len(report.pairwise_comparisons) > 0
        assert "## Comparative Baseline Evaluation: TEXT_RAG vs Pipeline" in report.summary
        assert "ΔMRR:" in report.summary

    @pytest.mark.asyncio
    async def test_harness_evaluate_manifest_with_baseline_naive_kg(self, pilot_manifest_path: Path):
        """Verify EvaluationHarness CLI / API integration with --baseline naive_kg."""
        harness = EvaluationHarness()
        report = await harness.evaluate_manifest(
            manifest_path=pilot_manifest_path,
            baseline="naive_kg",
        )

        assert any(rid.startswith("baseline_naive_kg") for rid in report.run_ids)
        assert len(report.pairwise_comparisons) > 0
        assert "## Comparative Baseline Evaluation: NAIVE_KG vs Pipeline" in report.summary
        assert "ΔF1:" in report.summary

    @pytest.mark.asyncio
    async def test_harness_evaluate_manifest_with_baseline_zero_shot(self, pilot_manifest_path: Path):
        """Verify EvaluationHarness CLI / API integration with --baseline zero_shot."""
        harness = EvaluationHarness()
        report = await harness.evaluate_manifest(
            manifest_path=pilot_manifest_path,
            baseline="zero_shot",
        )

        assert any(rid.startswith("baseline_zero_shot") for rid in report.run_ids)
        assert len(report.pairwise_comparisons) > 0
        assert "## Comparative Baseline Evaluation: ZERO_SHOT vs Pipeline" in report.summary
        assert "ΔF1:" in report.summary
