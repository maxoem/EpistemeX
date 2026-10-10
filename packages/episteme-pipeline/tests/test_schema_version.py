"""Tests for schema_version on RunManifest and SchemaConfig."""

from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.schema.default_schema import SchemaConfig


def test_schema_config_has_version_field():
    """Verify SchemaConfig exposes a version field."""
    schema = SchemaConfig()
    assert schema.version == "v1"


def test_schema_config_version_can_be_customized():
    """Verify schema version can be overridden."""
    schema = SchemaConfig(version="v2-beta")
    assert schema.version == "v2-beta"


def test_build_manifest_includes_schema_version(config):
    """Verify RunManifest.schema_version is set from SchemaConfig.version."""
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

    llm = _make_mock_llm()
    emb = _make_mock_embed()

    class DummyGraph:
        async def get_chunks(self, filters=None, limit=None):
            return []

    graph_reader = DummyGraph()
    projection_graph = DummyGraph()
    checkpoint_store = DummyGraph()

    global_extractor = TAGRelationExtractor(llm, emb, config.phase3)
    phases = [
        Phase1Runner(
            config.phase1, llm=llm, embedding_model=emb, graph_store=projection_graph
        ),
        Phase2Runner(
            config.phase2,
            config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
        ),
        Phase3Runner(
            config.phase3,
            config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
        Phase3bLatentConsolidationRunner(
            config.phase3b,
            embedding_model=emb,
            graph_store=graph_reader,
        ),
        Phase4EntityMaturationRunner(
            config.phase4_maturation,
            llm=llm,
            graph_store=graph_reader,
        ),
        Phase4Runner(
            config.phase4,
            config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
            global_extractor=global_extractor,
        ),
        Phase5ArgumentWebRunner(
            config.phase5, embedding_model=emb, graph_store=graph_reader
        ),
    ]

    pipeline = Pipeline(
        phases=phases,
        config=config,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
    )

    manifest = pipeline._build_manifest(
        run_id="test-run-schema",
        pipeline_input=PipelineInput(source_paths=["/path/doc.md"]),
    )

    assert manifest.schema_version == config.graph_schema.version
    assert manifest.schema_version == "v1"


def test_build_manifest_schema_version_tracks_config_change(config):
    """Verify schema_version changes when SchemaConfig.version is different."""

    config.graph_schema.version = "v2-custom"

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

    llm = _make_mock_llm()
    emb = _make_mock_embed()

    class DummyGraph:
        async def get_chunks(self, filters=None, limit=None):
            return []

    graph_reader = DummyGraph()
    projection_graph = DummyGraph()
    checkpoint_store = DummyGraph()

    global_extractor = TAGRelationExtractor(llm, emb, config.phase3)
    phases = [
        Phase1Runner(
            config.phase1, llm=llm, embedding_model=emb, graph_store=projection_graph
        ),
        Phase2Runner(
            config.phase2,
            config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
        ),
        Phase3Runner(
            config.phase3,
            config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=graph_reader,
            global_extractor=global_extractor,
        ),
        Phase3bLatentConsolidationRunner(
            config.phase3b,
            embedding_model=emb,
            graph_store=graph_reader,
        ),
        Phase4EntityMaturationRunner(
            config.phase4_maturation,
            llm=llm,
            graph_store=graph_reader,
        ),
        Phase4Runner(
            config.phase4,
            config.graph_schema,
            llm=llm,
            embedding_model=emb,
            graph_store=checkpoint_store,
            global_extractor=global_extractor,
        ),
        Phase5ArgumentWebRunner(
            config.phase5, embedding_model=emb, graph_store=graph_reader
        ),
    ]

    pipeline = Pipeline(
        phases=phases,
        config=config,
        graph_reader=graph_reader,
        projection_graph=projection_graph,
        checkpoint_store=checkpoint_store,
    )

    manifest = pipeline._build_manifest(
        run_id="test-run-schema-v2",
        pipeline_input=PipelineInput(source_paths=["/path/doc.md"]),
    )

    assert manifest.schema_version == "v2-custom"


def _make_mock_llm():
    from unittest.mock import MagicMock

    llm = MagicMock()
    llm.model_name = "gpt-4"
    llm.model_name_or_provider = "openai"
    return llm


def _make_mock_embed():
    from unittest.mock import MagicMock

    emb = MagicMock()
    emb.model_name = "text-embedding-3-small"
    emb.model_name_or_provider = "openai"
    return emb
