"""Unit tests verifying architectural remediations and contract fixes."""

from unittest.mock import MagicMock

from episteme_pipeline.artifacts.builders import (
    build_chunk_artifact,
    build_document_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    Phase1ArtifactsView,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.invalidate import (
    ArtifactDependencyGraph,
    _compare_dag_structures,
)
from episteme_pipeline.config import ExecutionConfig, PipelineConfig
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, L2_RELATION_TYPES


def test_default_schema_has_no_empty_strings():
    """Verify L2_RELATION_TYPES has no trailing empty string."""
    assert "" not in L2_RELATION_TYPES
    assert "" not in DEFAULT_SCHEMA.relation_types


def test_execution_config_has_all_phase_toggles():
    """Verify ExecutionConfig includes persistence toggles for all pipeline phases."""
    config = ExecutionConfig()
    assert hasattr(config, "persist_phase1_artifacts")
    assert hasattr(config, "persist_phase2_artifacts")
    assert hasattr(config, "persist_phase3_artifacts")
    assert hasattr(config, "persist_phase3b_artifacts")
    assert hasattr(config, "persist_phase4_maturation_artifacts")
    assert hasattr(config, "persist_phase4_artifacts")
    assert hasattr(config, "persist_phase5_artifacts")


def test_pipeline_for_task_instantiation():
    """Verify Pipeline.for_task instantiates all 7 phase runners without TypeError."""
    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
    mock_llm = MagicMock(spec=DiskCachedStructuredLLM)
    mock_reranker = MagicMock()
    mock_embed = MagicMock()
    mock_reader = MagicMock()
    mock_proj = MagicMock()
    mock_ckpt = MagicMock()
    config = PipelineConfig()

    pipeline = Pipeline.for_task(
        llm=mock_llm,
        relation_reranker=mock_reranker,
        embedding_model=mock_embed,
        config=config,
        graph_reader=mock_reader,
        projection_graph=mock_proj,
        checkpoint_store=mock_ckpt,
    )

    assert len(pipeline.phases) == 9
    phase_names = [p.name for p in pipeline.phases]
    assert "Phase 1:" in phase_names[0]
    assert "Phase 2:" in phase_names[1]
    assert "Phase 3:" in phase_names[2]
    assert "Phase 3b:" in phase_names[3]
    assert "Phase 4: Entity Maturation" in phase_names[4]
    assert "Phase 4: Argument Mining" in phase_names[5]
    assert "Phase 5" in phase_names[6]


def test_phase_config_fingerprints_mapping():
    """Verify each phase runner maps to its correct sub-config."""
    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
    mock_llm = MagicMock(spec=DiskCachedStructuredLLM)
    mock_reranker = MagicMock()
    mock_embed = MagicMock()
    mock_reader = MagicMock()
    mock_proj = MagicMock()
    mock_ckpt = MagicMock()
    config = PipelineConfig()

    pipeline = Pipeline.for_task(
        llm=mock_llm,
        relation_reranker=mock_reranker,
        embedding_model=mock_embed,
        config=config,
        graph_reader=mock_reader,
        projection_graph=mock_proj,
        checkpoint_store=mock_ckpt,
    )

    cfg_fps = pipeline._phase_config_fingerprints()
    assert len(cfg_fps) == 9
    # Modifying phase3b config should change fingerprint for phase index 4
    cfg_fps_orig_4 = cfg_fps[4]
    pipeline.config.phase3b.dense_similarity_threshold = 0.99
    cfg_fps_new = pipeline._phase_config_fingerprints()
    assert cfg_fps_new[4] != cfg_fps_orig_4
    # Modifying phase4_maturation config should change fingerprint for phase index 5
    cfg_fps_orig_5 = cfg_fps[5]
    pipeline.config.phase4_maturation.maturation_top_k = 99
    cfg_fps_new_5 = pipeline._phase_config_fingerprints()
    assert cfg_fps_new_5[5] != cfg_fps_orig_5


def test_prompt_fingerprints_includes_entity_synthesis():
    """Verify _prompt_fingerprints includes entity_synthesis template."""
    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
    mock_llm = MagicMock(spec=DiskCachedStructuredLLM)
    mock_reranker = MagicMock()
    mock_embed = MagicMock()
    mock_reader = MagicMock()
    mock_proj = MagicMock()
    mock_ckpt = MagicMock()
    config = PipelineConfig()

    pipeline = Pipeline.for_task(
        llm=mock_llm,
        relation_reranker=mock_reranker,
        embedding_model=mock_embed,
        config=config,
        graph_reader=mock_reader,
        projection_graph=mock_proj,
        checkpoint_store=mock_ckpt,
    )

    prompts = pipeline._prompt_fingerprints()
    assert "entity_synthesis" in prompts.get("phase4_maturation", {})


def test_build_phase_input_routing():
    """Verify _build_phase_input routes inputs accurately to phase views."""
    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
    mock_llm = MagicMock(spec=DiskCachedStructuredLLM)
    mock_reranker = MagicMock()
    mock_embed = MagicMock()
    mock_reader = MagicMock()
    mock_proj = MagicMock()
    mock_ckpt = MagicMock()
    config = PipelineConfig()

    pipeline = Pipeline.for_task(
        llm=mock_llm,
        relation_reranker=mock_reranker,
        embedding_model=mock_embed,
        config=config,
        graph_reader=mock_reader,
        projection_graph=mock_proj,
        checkpoint_store=mock_ckpt,
    )

    inp = PipelineInput(source_paths=["doc.txt"])
    doc = L1Document(id="doc1", title="Doc 1", source_path="doc.txt", chapter_count=1, chunk_count=1)
    chunk = L1Chunk(id="c1", text="Sample text", source_doc_id="doc1", sequence_index=0, token_count=2)
    doc_art = build_document_artifact(doc, run_id="r1", phase_name="P1", method="m")
    chunk_art = build_chunk_artifact(chunk, run_id="r1", phase_name="P1", method="m")
    col1 = ArtifactCollection([doc_art, chunk_art])

    p1_in = pipeline._build_phase_input(entry=pipeline._phase_entries[0], pipeline_input=inp, previous=None)
    assert isinstance(p1_in, PipelineInput)

    p2_in = pipeline._build_phase_input(entry=pipeline._phase_entries[1], pipeline_input=inp, previous=col1)
    assert isinstance(p2_in, Phase1ArtifactsView)
    assert len(p2_in.chunks) == 1

    p3b_in = pipeline._build_phase_input(entry=pipeline._phase_entries[3], pipeline_input=inp, previous=col1)
    assert isinstance(p3b_in, Phase3ArtifactsView)

    p4m_in = pipeline._build_phase_input(entry=pipeline._phase_entries[4], pipeline_input=inp, previous=col1)
    assert isinstance(p4m_in, Phase3ArtifactsView)

    p4a_in = pipeline._build_phase_input(entry=pipeline._phase_entries[5], pipeline_input=inp, previous=col1)
    assert isinstance(p4a_in, Phase3ArtifactsView)
    assert len(p4a_in.chunks) == 1

    p5_in = pipeline._build_phase_input(entry=pipeline._phase_entries[6], pipeline_input=inp, previous=col1)
    assert isinstance(p5_in, Phase4ArtifactsView)


def test_symmetrical_dag_structure_comparison():
    """Verify _compare_dag_structures detects deleted prior nodes as stale."""
    doc = L1Document(id="doc1", title="Doc 1", source_path="doc.txt", chapter_count=1, chunk_count=1)
    art1 = build_document_artifact(doc, run_id="r1", phase_name="P1", method="m")
    dag_current = ArtifactDependencyGraph.from_artifacts([art1])

    # Prior run contained art1 AND art2
    prior_upstream = {
        art1.identity_key: set(),
        "document::doc2": set(),
    }

    stale = _compare_dag_structures(dag_current, prior_upstream)
    assert "document::doc2" in stale


def test_qbaf_projection_preserves_weights():
    """Verify TheoryNetProjector.compute_weight preserves pre-computed weights."""
    proj = TheoryNetProjector()
    comp = TheoryAtom(id="a1", text="Text", component_type="ANTECEDENT", source_chunk_id="c1", plausibility=0.85)
    rel = TheoryRelation(source_id="a1", target_id="a2", relation_type="SUPPORTS", confidence=0.9, scope="local", weight=0.75)

    assert proj.compute_weight(comp) == 0.85
    assert proj.compute_relation_weight(rel) == 0.75
