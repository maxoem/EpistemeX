"""Unit and integration tests for dataset-agnostic evaluation strategies and registry.

Verifies:
1. Sovereign EvaluationStrategy protocol and StrategyRegistry (custom registration, auto-inference).
2. ExtractionStrategy for Layer 2 Named Entity Recognition and Relation Extraction.
3. ArgumentationStrategy for Layer 3 Argument Component (ADU) and Relation (ARC) Mining.
4. StructuralistStrategy for Layer 4 TheoryNet model component decomposition.
5. Universal in-memory search indexing (index_for_search) across chunks, entities, and atoms.
6. Dataset-agnostic in-memory and manifest evaluation in EvaluationHarness.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import networkx as nx
import pytest
import yaml

from episteme_pipeline.artifacts.execution import ArtifactCollection
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ChunkArtifact,
    LinkedEntityArtifact,
    LocalRelationArtifact,
    TheoryAtomArtifact,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryNet,
    TheoryRelation,
)
from episteme_pipeline.evaluation.harness import EvaluationHarness
from episteme_pipeline.evaluation.models import EvaluationLevel, EvaluationOutcome
from episteme_pipeline.evaluation.strategies import (
    ArgumentationStrategy,
    EvaluationStrategy,
    ExtractionStrategy,
    StrategyRegistry,
    StructuralistStrategy,
    default_registry,
)
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore


class TestStrategyRegistry:
    """Test suite for StrategyRegistry resolution, auto-inference, and custom registration."""

    def test_default_registry_contains_standard_strategies(self):
        """Verify default registry provides standard layer aliases."""
        assert isinstance(default_registry.get("structuralist"), StructuralistStrategy)
        assert isinstance(default_registry.get("l4"), StructuralistStrategy)
        assert isinstance(default_registry.get("stnb"), StructuralistStrategy)

        assert isinstance(default_registry.get("extraction"), ExtractionStrategy)
        assert isinstance(default_registry.get("scierc"), ExtractionStrategy)
        assert isinstance(default_registry.get("l2"), ExtractionStrategy)

        assert isinstance(default_registry.get("argumentation"), ArgumentationStrategy)
        assert isinstance(default_registry.get("arg_microtexts"), ArgumentationStrategy)
        assert isinstance(default_registry.get("l3"), ArgumentationStrategy)

    def test_custom_strategy_registration(self):
        """Verify user can register custom evaluation strategy."""
        registry = StrategyRegistry()

        class CustomEvaluator:
            async def evaluate(self, predicted, gold, run_id, context=None):
                return []

        registry.register("custom_domain", CustomEvaluator)
        strat = registry.get("custom_domain")
        assert isinstance(strat, CustomEvaluator)

    def test_strategy_inference_by_dataset_type(self):
        """Verify inference respects dataset_type string."""
        registry = StrategyRegistry()
        assert isinstance(registry.infer(dataset_type="scierc"), ExtractionStrategy)
        assert isinstance(registry.infer(dataset_type="arg_microtexts"), ArgumentationStrategy)
        assert isinstance(registry.infer(dataset_type="structuralist"), StructuralistStrategy)

    def test_strategy_inference_by_gold_filename(self):
        """Verify inference inspects gold path when dataset_type is omitted."""
        registry = StrategyRegistry()
        assert isinstance(registry.infer(gold="data/scierc_test.json"), ExtractionStrategy)
        assert isinstance(registry.infer(gold="data/stnb_cpm_pilot.jsonld"), StructuralistStrategy)
        assert isinstance(registry.infer(gold="data/arg_microtexts.json"), ArgumentationStrategy)

    def test_strategy_inference_by_predicted_artifacts(self):
        """Verify inference detects L2 vs L4 artifact views."""
        registry = StrategyRegistry()

        # L2 Entity Artifact
        ent_env = ArtifactEnvelope(
            artifact_id="art_e1",
            kind=ArtifactKind.LINKED_ENTITY,
            run_id="run_1",
            phase_name="phase2",
            method="test",
            payload=LinkedEntityArtifact(
                entity_id="e1",
                canonical_name="Gravity",
                entity_type="Concept",
            ),
        )
        l2_col = ArtifactCollection(artifacts=[ent_env])
        assert isinstance(registry.infer(predicted=l2_col), ExtractionStrategy)

        # L4 Theory Atom Artifact
        atom_env = ArtifactEnvelope(
            artifact_id="art_a1",
            kind=ArtifactKind.THEORY_ATOM,
            run_id="run_2",
            phase_name="phase4",
            method="test",
            payload=TheoryAtomArtifact(
                component_id="a1",
                chunk_id="c1",
                text="F = ma",
                component_type="actual_model",
            ),
        )
        l4_col = ArtifactCollection(artifacts=[atom_env])
        assert isinstance(registry.infer(predicted=l4_col), StructuralistStrategy)


class TestExtractionStrategy:
    """Test suite for Layer 2 ExtractionStrategy (NER and RE)."""

    @pytest.mark.asyncio
    async def test_extraction_evaluation_metrics_and_oep(self):
        """Verify extraction strategy calculates entity/relation F1 and OEP rates."""
        strategy = ExtractionStrategy()

        predicted = [
            L2Entity(id="e1", name="Force", label="PhysicsConcept"),
            L2Entity(id="e2", name="Mass", label="PhysicsConcept"),
            L2Triple(subject_id="e1", predicate="proportional_to", object_id="e2", confidence=1.0, scope="local"),
        ]

        gold = {
            "l2_entities": [
                L2Entity(id="g1", name="Force", label="PhysicsConcept"),
                L2Entity(id="g2", name="Mass", label="PhysicsConcept"),
                L2Entity(id="g3", name="Acceleration", label="PhysicsConcept"),
            ],
            "l2_triples": [
                L2Triple(subject_id="g1", predicate="proportional_to", object_id="g2", confidence=1.0, scope="local"),
            ],
        }

        results = await strategy.evaluate(predicted=predicted, gold=gold, run_id="run_ext_test")
        assert len(results) == 1
        res = results[0]
        assert res.evaluation_level == EvaluationLevel.STAGE
        metrics = {m.name: m.value for m in res.metrics}

        # 2 pred entities (Force, Mass) match 2 of 3 gold entities (Force, Mass, Acceleration)
        assert metrics["entity_precision"] == 1.0
        assert metrics["entity_recall"] == pytest.approx(2.0 / 3.0)
        assert metrics["entity_f1"] == pytest.approx(0.8)

        # 1 pred triple matches 1 gold triple
        assert metrics["relation_precision"] == 1.0
        assert metrics["relation_recall"] == 1.0
        assert metrics["relation_f1"] == 1.0

        # OEP error rates
        assert metrics["hallucination_rate"] == 0.0
        assert metrics["omission_rate"] == 0.0


class TestArgumentationStrategy:
    """Test suite for Layer 3 ArgumentationStrategy."""

    @pytest.mark.asyncio
    async def test_argumentation_evaluation_metrics(self):
        """Verify argumentation strategy computes ADU and ARC F1."""
        strategy = ArgumentationStrategy()

        predicted = [
            TheoryAtom(id="a1", text="Public transit should be subsidized", component_type="CLAIM", source_chunk_id="c1"),
            TheoryAtom(id="a2", text="It reduces carbon emissions", component_type="PREMISE", source_chunk_id="c1"),
            TheoryRelation(source_id="a2", target_id="a1", relation_type="SUPPORT", confidence=1.0, scope="global"),
        ]

        gold = {
            "l3_atoms": [
                TheoryAtom(id="g1", text="Public transit should be subsidized", component_type="CLAIM", source_chunk_id="c1"),
                TheoryAtom(id="g2", text="It reduces carbon emissions", component_type="PREMISE", source_chunk_id="c1"),
            ],
            "l3_relations": [
                TheoryRelation(source_id="g2", target_id="g1", relation_type="SUPPORT", confidence=1.0, scope="global"),
            ],
        }

        results = await strategy.evaluate(predicted=predicted, gold=gold, run_id="run_arg_test")
        assert len(results) == 1
        metrics = {m.name: m.value for m in results[0].metrics}

        assert metrics["adu_f1"] == 1.0
        assert metrics["arc_f1"] == 1.0
        assert results[0].outcome == EvaluationOutcome.PASS


class TestInMemoryStoreSearchIndexing:
    """Test suite for polymorphic InMemoryGraphStore.index_for_search."""

    def test_index_for_search_handles_artifact_collection(self):
        """Verify index_for_search indexes chunks, entities, and atoms from ArtifactCollection."""
        store = InMemoryGraphStore()

        chunk_env = ArtifactEnvelope(
            artifact_id="art_c1",
            kind=ArtifactKind.CHUNK,
            run_id="run_idx",
            phase_name="phase1",
            method="test",
            payload=ChunkArtifact(
                chunk_id="chunk_principia_1",
                document_id="doc_1",
                text="Newton discovered gravity in 1687.",
                sequence_index=0,
                token_count=6,
            ),
        )
        ent_env = ArtifactEnvelope(
            artifact_id="art_e1",
            kind=ArtifactKind.LINKED_ENTITY,
            run_id="run_idx",
            phase_name="phase2",
            method="test",
            payload=LinkedEntityArtifact(
                entity_id="ent_gravity",
                canonical_name="Universal Gravitation",
                entity_type="Concept",
                description="Governing inverse square force",
            ),
        )
        collection = ArtifactCollection(artifacts=[chunk_env, ent_env])

        indexed_count = store.index_for_search(collection, run_id="run_idx")
        assert indexed_count == 2

        # Verify both chunk and entity are searchable via vector_search
        results = asyncio.run(store.vector_search(query_text="gravity", top_k=5, run_id="run_idx"))
        assert len(results) >= 2
        result_ids = {r.node_id for r in results}
        assert "chunk_principia_1" in result_ids
        assert "ent_gravity" in result_ids


class TestHarnessAgnosticExecution:
    """Test suite verifying EvaluationHarness functions agnostically across layers."""

    @pytest.mark.asyncio
    async def test_evaluate_in_memory_with_l2_extraction(self):
        """Verify evaluate_in_memory automatically selects ExtractionStrategy for L2 data."""
        harness = EvaluationHarness()

        predicted = [
            L2Entity(id="e1", name="Newton", label="Scientist"),
            L2Entity(id="e2", name="Calculus", label="Field"),
            L2Triple(subject_id="e1", predicate="developed", object_id="e2", confidence=1.0, scope="local"),
        ]
        gold = {
            "l2_entities": [
                L2Entity(id="g1", name="Newton", label="Scientist"),
                L2Entity(id="g2", name="Calculus", label="Field"),
            ],
            "l2_triples": [
                L2Triple(subject_id="g1", predicate="developed", object_id="g2", confidence=1.0, scope="local"),
            ],
        }

        # No strategy argument passed: should infer ExtractionStrategy automatically!
        report = await harness.evaluate_in_memory(
            predicted=predicted,
            gold=gold,
            run_id="run_auto_infer_l2",
        )

        assert report.evaluation_id == "eval_run_auto_infer_l2"
        stage_res = report.results_by_level[str(EvaluationLevel.STAGE)][0]
        metrics = {m.name: m.value for m in stage_res.metrics}
        assert "entity_f1" in metrics
        assert metrics["entity_f1"] == 1.0
        assert "relation_f1" in metrics
        assert metrics["relation_f1"] == 1.0

    @pytest.mark.asyncio
    async def test_evaluate_in_memory_with_explicit_strategy_override(self):
        """Verify evaluate_in_memory accepts explicit strategy string."""
        harness = EvaluationHarness()

        predicted = [
            TheoryAtom(id="a1", text="Premise A", component_type="PREMISE", source_chunk_id="c1"),
        ]
        gold = {
            "l3_atoms": [
                TheoryAtom(id="a1", text="Premise A", component_type="PREMISE", source_chunk_id="c1"),
            ],
            "l3_relations": [],
        }

        report = await harness.evaluate_in_memory(
            predicted=predicted,
            gold=gold,
            run_id="run_explicit_strategy",
            strategy="argumentation",
        )

        stage_res = report.results_by_level[str(EvaluationLevel.STAGE)][0]
        assert "adu_f1" in {m.name for m in stage_res.metrics}

    @pytest.mark.asyncio
    async def test_evaluate_manifest_with_scierc(self, tmp_path: Path):
        """Verify evaluate_manifest seamlessly evaluates non-structuralist SciERC benchmark."""
        # 1. Create a mock SciERC json file
        gold_file = tmp_path / "scierc_mock.json"
        gold_data = {
            "doc_key": "doc_0",
            "sentences": [["Deep", "learning", "improves", "vision", "models", "."]],
            "ner": [[[0, 1, "Method"], [3, 4, "Task"]]],
            "relations": [[[0, 1, 3, 4, "USED-FOR"]]],
        }
        import json
        gold_file.write_text(json.dumps(gold_data) + "\n", encoding="utf-8")

        # 2. Create manifest targeting mock SciERC
        manifest_file = tmp_path / "eval_scierc_test.yaml"
        manifest_data = {
            "run_id": "test_scierc_manifest",
            "corpus": {
                "dataset_type": "scierc",
                "gold_standard_path": str(gold_file),
                "limit": 1,
            },
        }
        with open(manifest_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(manifest_data, f)

        # 3. Create harness and populate in-memory store with mock predicted entities
        harness = EvaluationHarness(reports_dir=tmp_path / "reports")
        await harness.graph_store.upsert_entity(L2Entity(id="ent_0", name="Deep learning", label="Method"))
        await harness.graph_store.upsert_entity(L2Entity(id="ent_1", name="vision models", label="Task"))
        await harness.graph_store.upsert_triple(
            L2Triple(subject_id="ent_0", predicate="USED-FOR", object_id="ent_1", confidence=1.0, scope="local")
        )

        report = await harness.evaluate_manifest(manifest_path=manifest_file, build_graph=False)
        assert report.evaluation_id == "eval_test_scierc_manifest"
        stage_res = report.results_by_level[str(EvaluationLevel.STAGE)][0]
        metrics = {m.name: m.value for m in stage_res.metrics}

        assert "entity_f1" in metrics
        assert metrics["entity_f1"] == 1.0
        assert "relation_f1" in metrics
        assert metrics["relation_f1"] == 1.0

    def test_pipeline_builder_resolution_and_custom_registration(self):
        """Verify StrategyRegistry resolves default and custom pipeline builders."""
        registry = StrategyRegistry()

        # Built-in pipeline builders
        l2_builder = registry.get_pipeline_builder("scierc")
        assert callable(l2_builder)
        l3_builder = registry.get_pipeline_builder("argumentation")
        assert callable(l3_builder)
        l4_builder = registry.get_pipeline_builder("structuralist")
        assert callable(l4_builder)

        # Custom pipeline builder registration
        mock_pipeline = object()
        registry.register_pipeline_builder("custom_domain", lambda **kwargs: mock_pipeline)
        resolved = registry.get_pipeline_builder("custom_domain")
        assert resolved() is mock_pipeline

    def test_harness_pluggable_pipeline_builder_resolution(self):
        """Verify EvaluationHarness resolves custom callable or strategy pipeline builders without hardcoding."""
        harness = EvaluationHarness()

        # 1. Custom callable builder reference
        mock_pipe = object()
        built = harness._build_pipeline_for_dataset(
            dataset_type="arbitrary_dataset",
            builder_ref=lambda **kwargs: mock_pipe,
        )
        assert built is mock_pipe

        # 2. Strategy implementing build_pipeline
        class CustomStrategyWithPipeline:
            def build_pipeline(self, **kwargs):
                return mock_pipe

            async def evaluate(self, predicted, gold, run_id, context=None):
                return []

        built_strat = harness._build_pipeline_for_dataset(
            dataset_type="unknown_key",
            strategy=CustomStrategyWithPipeline(),
        )
        assert built_strat is mock_pipe
