"""Tests for new _method_fingerprints, config_snapshot, and input_sources wiring in RunManifest."""

from unittest.mock import MagicMock

import pytest

from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.protocols.graph_store import ProcessingGraph


@pytest.fixture
def simple_config():
    return PipelineConfig()


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.model_name = "gpt-4"
    llm.model_name_or_provider = "openai"
    return llm


@pytest.fixture
def mock_embedding_model():
    emb = MagicMock()
    emb.model_name = "text-embedding-3-small"
    emb.model_name_or_provider = "openai"
    return emb


def _make_phase4_runner(config, llm, embedding_model):
    """Create a minimal Phase4Runner for _method_fingerprints testing."""
    graph_store = MagicMock(spec=ProcessingGraph)
    extractor = MagicMock()

    class DummyGraphReader:
        async def get_chunks(self, filters=None, limit=None):
            return []

    graph_reader = DummyGraphReader()
    projection_graph = DummyGraphReader()

    from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner

    runner = Phase4Runner(
        config.phase4,
        config.graph_schema,
        llm=llm,
        embedding_model=embedding_model,
        graph_store=graph_store,
        global_extractor=extractor,
    )
    return runner


def test_method_fingerprints_captures_llm(
    mock_llm, mock_embedding_model, simple_config
):
    """Verify _method_fingerprints captures LLM and embedding_model identity."""
    from episteme_pipeline.pipeline import Pipeline

    runner = _make_phase4_runner(simple_config, mock_llm, mock_embedding_model)
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.config = simple_config
    pipeline._phase_entries = [
        MagicMock(
            index=4,
            runner=runner,
            input_view_type=None,
        )
    ]

    fps = pipeline._method_fingerprints()

    assert "Phase 4: Argument Mining.llm" in fps
    assert "Phase 4: Argument Mining.embedding_model" in fps
    assert (
        fps["Phase 4: Argument Mining.llm"]
        != fps["Phase 4: Argument Mining.embedding_model"]
    )


def test_method_fingerprints_uses_class_when_no_model_attrs(
    mock_llm, mock_embedding_model, simple_config
):
    """Verify falls back to class name when model_name/model_name_or_provider are not available."""

    class BareLLM:
        pass

    bare_llm = BareLLM()

    from episteme_pipeline.pipeline import Pipeline

    runner = _make_phase4_runner(simple_config, bare_llm, mock_embedding_model)
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.config = simple_config
    pipeline._phase_entries = [
        MagicMock(
            index=4,
            runner=runner,
            input_view_type=None,
        )
    ]

    # Should not raise, even with a bare object
    fps = pipeline._method_fingerprints()
    assert isinstance(fps, dict)


def test_build_manifest_captures_source_fingerprint(simple_config):
    """Verify RunManifest.source_fingerprint is populated."""
    from episteme_pipeline.pipeline import Pipeline
    from episteme_pipeline.phases.phase1_foundation import Phase1Runner
    from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
    from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
    from episteme_pipeline.phases.phase3_global_relations.tag_extractor import (
        TAGRelationExtractor,
    )
    from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
    from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
    from episteme_pipeline.phases.phase4_entity_maturation import Phase4EntityMaturationRunner
    from episteme_pipeline.phases.phase5_fusion import Phase5ArgumentWebRunner

    llm = MagicMock()
    llm.model_name = "gpt-4"
    llm.model_name_or_provider = "openai"
    emb = MagicMock()
    emb.model_name = "text-embedding-3-small"
    emb.model_name_or_provider = "openai"

    class DummyGraph:
        async def get_chunks(self, filters=None, limit=None):
            return []

    graph_reader = DummyGraph()
    projection_graph = DummyGraph()
    checkpoint_store = DummyGraph()

    global_extractor = TAGRelationExtractor(llm, emb, simple_config.phase3)
    phases = [
        Phase1Runner(
            simple_config.phase1, llm=llm, embedding_model=emb, graph_store=projection_graph
        ),
        Phase2Runner(
            simple_config.phase2,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
        ),
        Phase3Runner(
            simple_config.phase3,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
        Phase3bLatentConsolidationRunner(
            simple_config.phase3b,
            embedding_model=emb,
            graph_store=graph_reader,
        ),
        Phase4EntityMaturationRunner(
            simple_config.phase4_maturation,
            llm=llm,
            graph_store=graph_reader,
        ),
        Phase4Runner(
            simple_config.phase4,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
            global_extractor=global_extractor,
        ),
        Phase5ArgumentWebRunner(
            simple_config.phase5, embedding_model=emb, graph_store=graph_reader
        ),
    ]

    pipeline = Pipeline(
        phases=phases,
        config=simple_config,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
    )

    manifest = pipeline._build_manifest(
        run_id="test-run-1",
        pipeline_input=PipelineInput(
            source_paths=["/path/doc.md"], metadata={"k": "v"}
        ),
    )

    assert manifest.source_fingerprint is not None
    assert len(manifest.source_fingerprint) == 64  # SHA-256 hex


def test_build_manifest_captures_config_snapshot(simple_config):
    """Verify RunManifest.config_snapshot is populated."""
    from episteme_pipeline.pipeline import Pipeline
    from episteme_pipeline.phases.phase1_foundation import Phase1Runner
    from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
    from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
    from episteme_pipeline.phases.phase3_global_relations.tag_extractor import (
        TAGRelationExtractor,
    )
    from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
    from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
    from episteme_pipeline.phases.phase4_entity_maturation import Phase4EntityMaturationRunner
    from episteme_pipeline.phases.phase5_fusion import Phase5ArgumentWebRunner

    llm = MagicMock()
    llm.model_name = "gpt-4"
    llm.model_name_or_provider = "openai"
    emb = MagicMock()
    emb.model_name = "text-embedding-3-small"
    emb.model_name_or_provider = "openai"

    class DummyGraph:
        async def get_chunks(self, filters=None, limit=None):
            return []

    graph_reader = DummyGraph()
    projection_graph = DummyGraph()
    checkpoint_store = DummyGraph()

    global_extractor = TAGRelationExtractor(llm, emb, simple_config.phase3)
    phases = [
        Phase1Runner(
            simple_config.phase1, llm=llm, embedding_model=emb, graph_store=projection_graph
        ),
        Phase2Runner(
            simple_config.phase2,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
        ),
        Phase3Runner(
            simple_config.phase3,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
        Phase3bLatentConsolidationRunner(
            simple_config.phase3b,
            embedding_model=emb,
            graph_store=graph_reader,
        ),
        Phase4EntityMaturationRunner(
            simple_config.phase4_maturation,
            llm=llm,
            graph_store=graph_reader,
        ),
        Phase4Runner(
            simple_config.phase4,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
            global_extractor=global_extractor,
        ),
        Phase5ArgumentWebRunner(
            simple_config.phase5, embedding_model=emb, graph_store=graph_reader
        ),
    ]

    pipeline = Pipeline(
        phases=phases,
        config=simple_config,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
    )

    manifest = pipeline._build_manifest(
        run_id="test-run-2",
        pipeline_input=PipelineInput(source_paths=["/path/doc.md"]),
    )

    assert "graph_schema" in manifest.config_snapshot
    assert "phase1" in manifest.config_snapshot
    assert "phase2" in manifest.config_snapshot
    # Verify it's a serializable dict (not a Pydantic model instance)
    assert isinstance(manifest.config_snapshot, dict)


def test_build_manifest_captures_input_sources(simple_config):
    """Verify RunManifest.input_sources is populated."""
    from pathlib import Path
    from episteme_pipeline.pipeline import Pipeline
    from episteme_pipeline.phases.phase1_foundation import Phase1Runner
    from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
    from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
    from episteme_pipeline.phases.phase3_global_relations.tag_extractor import (
        TAGRelationExtractor,
    )
    from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
    from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
    from episteme_pipeline.phases.phase4_entity_maturation import Phase4EntityMaturationRunner
    from episteme_pipeline.phases.phase5_fusion import Phase5ArgumentWebRunner

    llm = MagicMock()
    llm.model_name = "gpt-4"
    llm.model_name_or_provider = "openai"
    emb = MagicMock()
    emb.model_name = "text-embedding-3-small"
    emb.model_name_or_provider = "openai"

    class DummyGraph:
        async def get_chunks(self, filters=None, limit=None):
            return []

    graph_reader = DummyGraph()
    projection_graph = DummyGraph()
    checkpoint_store = DummyGraph()

    global_extractor = TAGRelationExtractor(llm, emb, simple_config.phase3)
    phases = [
        Phase1Runner(
            simple_config.phase1, llm=llm, embedding_model=emb, graph_store=projection_graph
        ),
        Phase2Runner(
            simple_config.phase2,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
        ),
        Phase3Runner(
            simple_config.phase3,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
        Phase3bLatentConsolidationRunner(
            simple_config.phase3b,
            embedding_model=emb,
            graph_store=graph_reader,
        ),
        Phase4EntityMaturationRunner(
            simple_config.phase4_maturation,
            llm=llm,
            graph_store=graph_reader,
        ),
        Phase4Runner(
            simple_config.phase4,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
            global_extractor=global_extractor,
        ),
        Phase5ArgumentWebRunner(
            simple_config.phase5, embedding_model=emb, graph_store=graph_reader
        ),
    ]

    pipeline = Pipeline(
        phases=phases,
        config=simple_config,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
    )

    test_path = Path(__file__).parent / "doc.md"
    test_path.touch()
    try:
        manifest = pipeline._build_manifest(
            run_id="test-run-3",
            pipeline_input=PipelineInput(source_paths=[str(test_path)]),
        )

        assert len(manifest.input_sources) >= 1
        assert str(test_path) in manifest.input_sources
    finally:
        test_path.unlink(missing_ok=True)


def test_method_fingerprints_not_empty(simple_config):
    """Verify method fingerprints are non-empty for a fully configured pipeline."""
    from episteme_pipeline.pipeline import Pipeline
    from episteme_pipeline.phases.phase1_foundation import Phase1Runner
    from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
    from episteme_pipeline.phases.phase3_global_relations import Phase3Runner
    from episteme_pipeline.phases.phase3_global_relations.tag_extractor import (
        TAGRelationExtractor,
    )
    from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
    from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
    from episteme_pipeline.phases.phase4_entity_maturation import Phase4EntityMaturationRunner
    from episteme_pipeline.phases.phase5_fusion import Phase5ArgumentWebRunner

    llm = MagicMock()
    llm.model_name = "gpt-4"
    llm.model_name_or_provider = "openai"
    emb = MagicMock()
    emb.model_name = "text-embedding-3-small"
    emb.model_name_or_provider = "openai"

    class DummyGraph:
        async def get_chunks(self, filters=None, limit=None):
            return []

    graph_reader = DummyGraph()
    projection_graph = DummyGraph()
    checkpoint_store = DummyGraph()

    global_extractor = TAGRelationExtractor(llm, emb, simple_config.phase3)
    phases = [
        Phase1Runner(
            simple_config.phase1, llm=llm, embedding_model=emb, graph_store=projection_graph
        ),
        Phase2Runner(
            simple_config.phase2,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
        ),
        Phase3Runner(
            simple_config.phase3,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
        Phase3bLatentConsolidationRunner(
            simple_config.phase3b,
            embedding_model=emb,
            graph_store=graph_reader,
        ),
        Phase4EntityMaturationRunner(
            simple_config.phase4_maturation,
            llm=llm,
            graph_store=graph_reader,
        ),
        Phase4Runner(
            simple_config.phase4,
            simple_config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
            global_extractor=global_extractor,
        ),
        Phase5ArgumentWebRunner(
            simple_config.phase5, embedding_model=emb, graph_store=graph_reader
        ),
    ]

    pipeline = Pipeline(
        phases=phases,
        config=simple_config,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
    )

    manifest = pipeline._build_manifest(
        run_id="test-run-4",
        pipeline_input=PipelineInput(source_paths=["/path/doc.md"]),
    )

    assert len(manifest.method_fingerprints) > 0
