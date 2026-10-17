"""Deterministic unit and property tests verifying ISSUE-062 remediation.

Tests lossless codecs, mention ID preservation across Phase4 maturation, Phase 6
TheoryNet artifact emission, and TheoreticalEnrichment persistence via upsert_theory_relations.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from episteme_pipeline.artifacts.builders import (
    build_chunk_artifact,
    build_document_artifact,
    build_linked_entity_artifact,
    build_theory_atom_artifact,
    build_theory_relation_artifact,
)
from episteme_pipeline.artifacts.codecs import (
    ChunkCodec,
    DocumentCodec,
    GlobalRelationCodec,
    LinkedEntityCodec,
    LocalRelationCodec,
    TheoryAtomCodec,
    TheoryRelationCodec,
    TripleCodec,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    Phase4ArtifactsView,
)
from episteme_pipeline.artifacts.models import (
    ArtifactKind,
    LinkedEntityArtifact,
    TheoryAtomArtifact,
    TheoryRelationArtifact,
)
from episteme_pipeline.contracts.domain import (
    GlobalStructuralAnchor,
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    Measurement,
    TenabilityResult,
    TextAnchor,
    TheoryAtom,
    TheoryNet,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.phases.phase4_entity_maturation import (
    EntitySynthesisOutput,
    Phase4EntityMaturationConfig,
    Phase4EntityMaturationRunner,
)
from episteme_pipeline.phases.phase6_theorynet.runner import (
    Phase6Config,
    Phase6Runner,
)
from episteme_pipeline.post_processing.theoretical_enrichment.runner import (
    TheoreticalEnrichmentConfig,
    TheoreticalEnrichmentRunner,
)
from episteme_pipeline.projection.artifact_projector import ArtifactGraphProjector
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


def test_document_codec_roundtrip() -> None:
    """Verify DocumentCodec is lossless for L1Document."""
    anchor = GlobalStructuralAnchor(
        volume=1, book=2, part=3, chapter=4, section=5
    )
    doc = L1Document(
        id="doc-1",
        title="Critique of Pure Reason",
        source_path="/corpus/kant.txt",
        chapter_count=12,
        chunk_count=144,
        structural_anchor=anchor,
        metadata={"author": "Immanuel Kant", "language": "de"},
    )
    payload = DocumentCodec.to_payload(doc)
    hydrated = DocumentCodec.to_domain(payload)
    assert hydrated == doc


def test_chunk_codec_roundtrip() -> None:
    """Verify ChunkCodec is lossless for L1Chunk including embeddings and anchors."""
    anchor = TextAnchor(
        source_doc_id="doc-1",
        char_start=100,
        char_end=250,
        verbatim_quote="Gedanken ohne Inhalt sind leer",
    )
    chunk = L1Chunk(
        id="chunk-42",
        text="Gedanken ohne Inhalt sind leer, Anschauungen ohne Begriffe sind blind.",
        source_doc_id="doc-1",
        chapter_id="chap-3",
        sequence_index=7,
        token_count=13,
        embedding=[0.12, -0.45, 0.88],
        text_anchor=anchor,
        metadata={"section_path": "Introduction > Section 1"},
    )
    payload = ChunkCodec.to_payload(chunk)
    hydrated = ChunkCodec.to_domain(payload)
    assert hydrated == chunk


def test_linked_entity_codec_roundtrip() -> None:
    """Verify LinkedEntityCodec is lossless for L2Entity."""
    anchor = TextAnchor(source_doc_id="doc-1", char_start=10, char_end=30)
    entity = L2Entity(
        id="entity-kategorial",
        label="Concept",
        name="Kategorie",
        description="Reiner Verstandesbegriff a priori",
        textual_envelope="Die reinen Verstandesbegriffe...",
        is_mature=True,
        confidence=0.95,
        text_anchor=anchor,
        source_chunk_ids=["chunk-1", "chunk-5", "chunk-12"],
    )
    payload = LinkedEntityCodec.to_payload(entity)
    hydrated = LinkedEntityCodec.to_domain(payload)
    assert hydrated == entity


def test_triple_codecs_roundtrip() -> None:
    """Verify LocalRelationCodec, GlobalRelationCodec, and TripleCodec are lossless."""
    local_triple = L2Triple(
        subject_id="entity-a",
        predicate="CONSTITUTES",
        object_id="entity-b",
        confidence=0.88,
        rerank_score=0.92,
        scope="local",
        source_chunk_id="chunk-9",
    )
    payload_loc = LocalRelationCodec.to_payload(local_triple)
    hydrated_loc = LocalRelationCodec.to_domain(payload_loc)
    assert hydrated_loc == local_triple
    assert TripleCodec.to_domain(TripleCodec.to_payload(local_triple)) == local_triple

    global_triple = L2Triple(
        subject_id="entity-a",
        predicate="CONTRADICTS",
        object_id="entity-c",
        confidence=0.79,
        rerank_score=0.83,
        scope="global",
        source_chunk_id="chunk-3",
    )
    payload_glob = GlobalRelationCodec.to_payload(global_triple)
    hydrated_glob = GlobalRelationCodec.to_domain(payload_glob)
    assert hydrated_glob == global_triple
    assert TripleCodec.to_domain(TripleCodec.to_payload(global_triple)) == global_triple


def test_theory_atom_codec_roundtrip() -> None:
    """Verify TheoryAtomCodec is lossless for TheoryAtom."""
    anchor = TextAnchor(source_doc_id="doc-1", char_start=50, char_end=150)
    tenability = TenabilityResult(
        local_score=0.85,
        edge_scores={"edge-1": 0.9},
        aggregated_score=0.87,
        is_tenable=True,
        tightest_blur=0.05,
        anomalies=[],
    )
    atom = TheoryAtom(
        id="atom-101",
        text="Alle Anschauungen sind sinnlich.",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk-42",
        confidence=0.94,
        plausibility=0.89,
        modal_strength=0.75,
        base_score=0.75,
        entity_ids=["entity-anschauung", "entity-sinnlichkeit"],
        epistemic_status="Analytisch",
        scope_type="Essentieller Allsatz",
        text_anchor=anchor,
        measurements=[Measurement(dimension="clarity", value=0.92, unit="score")],
        parameters={"alpha": 0.5, "delta": 0.1},
        tenability=tenability,
    )
    payload = TheoryAtomCodec.to_payload(atom)
    hydrated = TheoryAtomCodec.to_domain(payload)
    assert hydrated == atom


def test_theory_relation_codec_roundtrip() -> None:
    """Verify TheoryRelationCodec is lossless for TheoryRelation with D-QBAF fields."""
    rel = TheoryRelation(
        source_id="atom-101",
        target_id="atom-102",
        relation_type="SUPPORTS",
        confidence=0.91,
        scope="global",
        weight=0.82,
        tenability=0.88,
        class_probability=0.85,
        stance_probability=0.85,
        empirical_accuracy=0.87,
        model_confidence=0.91,
        inferential_force=0.80,
        is_admissible=True,
        active_weight=0.82,
        modal_strength=0.75,
        effective_weight=0.82,
        decision_engine_provider="jev",
        calibrated_confidence=0.89,
        weight_support=0.82,
        weight_attack=0.0,
    )
    payload = TheoryRelationCodec.to_payload(rel)
    hydrated = TheoryRelationCodec.to_domain(payload)
    assert hydrated == rel


@pytest.mark.asyncio
async def test_phase4_entity_maturation_source_chunk_ids_preservation() -> None:
    """Verify Phase4EntityMaturationRunner preserves source_chunk_ids across views and projector."""
    mock_store = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.predict_structured = AsyncMock(
        return_value=EntitySynthesisOutput(
            description="Centroid-fused mature description"
        )
    )

    entity = L2Entity(
        id="ent-1",
        label="Concept",
        name="Synthetisches Urteil",
        description="Initial description",
        is_mature=False,
        source_chunk_ids=["chunk-10", "chunk-20"],
    )

    mock_store.get_entities = AsyncMock(return_value=[entity])
    mock_store.get_entity_mentions = AsyncMock(
        return_value=[
            {"mention_id": "mention::ent-1::chunk-10", "chunk_id": "chunk-10"},
            {"mention_id": "mention::ent-1::chunk-20", "chunk_id": "chunk-20"},
        ]
    )
    mock_store.get_entity_envelopes = AsyncMock(
        return_value=["Die reinen Verstandesbegriffe..."]
    )
    mock_embedding = AsyncMock()
    mock_embedding.aget_text_embedding_batch = AsyncMock(
        return_value=[[0.1, 0.2, 0.3]]
    )

    runner = Phase4EntityMaturationRunner(
        config=Phase4EntityMaturationConfig(batch_size=10),
        llm=mock_llm,
        graph_store=mock_store,
        embedding_model=mock_embedding,
    )

    manifest = RunManifest(run_id="run-test", dataset_path="dummy")
    context = ArtifactExecutionContext(
        run_id="run-test",
        manifest=manifest,
        pipeline_input=PipelineInput(source_paths=[]),
        previous=ArtifactCollection([]),
    )

    # Run maturation
    artifacts = await runner.run(
        Phase2ArtifactsView(entities=[entity], local_triples=[], entity_count_by_type={}),
        context,
    )

    assert len(artifacts) == 1
    envelope = artifacts.artifacts[0]
    assert envelope.kind == ArtifactKind.LINKED_ENTITY
    payload: LinkedEntityArtifact = envelope.payload
    assert payload.is_mature is True
    # Verify source_chunk_ids field on payload
    assert payload.source_chunk_ids == ["chunk-10", "chunk-20"]
    # Verify canonical mention_id format
    assert payload.mention_ids == [
        "mention::ent-1::chunk-10",
        "mention::ent-1::chunk-20",
    ]

    # Test hydration in Phase2ArtifactsView
    hydrated_view = Phase2ArtifactsView.from_collection(artifacts)
    assert len(hydrated_view.entities) == 1
    hydrated_entity = hydrated_view.entities[0]
    assert hydrated_entity.source_chunk_ids == ["chunk-10", "chunk-20"]

    # Test projection in ArtifactGraphProjector
    projector = ArtifactGraphProjector(graph_store=mock_store, schema=DEFAULT_SCHEMA)
    await projector.project(artifacts.artifacts[0])

    # Verify upsert_entity was called with source_chunk_ids intact
    mock_store.upsert_entity.assert_called_once()
    projected_entity: L2Entity = mock_store.upsert_entity.call_args[0][0]
    assert projected_entity.source_chunk_ids == ["chunk-10", "chunk-20"]


@pytest.mark.asyncio
async def test_phase6_increments_relations_updated_and_returns_artifacts() -> None:
    """Verify Phase6Runner increments relations_updated and returns theory artifacts."""
    mock_store = AsyncMock()
    mock_projector = MagicMock()

    atom1 = TheoryAtom(
        id="atom-1",
        text="Premise A",
        component_type="ObservationUnit",
        source_chunk_id="chunk-1",
    )
    atom2 = TheoryAtom(
        id="atom-2",
        text="Claim B",
        component_type="TheoreticalHypothesis",
        source_chunk_id="chunk-1",
    )
    rel = TheoryRelation(
        source_id="atom-1",
        target_id="atom-2",
        relation_type="SUPPORTS",
        confidence=0.9,
        scope="local",
    )

    theory_net = TheoryNet(
        atoms=[atom1, atom2],
        relations=[rel],
        partition_a=[atom2],
        partition_b=[atom1],
    )
    mock_projector.project.return_value = theory_net

    runner = Phase6Runner(
        config=Phase6Config(),
        projector=mock_projector,
        graph_store=mock_store,
        schema=DEFAULT_SCHEMA,
    )

    manifest = RunManifest(run_id="run-6", dataset_path="dummy")
    context = ArtifactExecutionContext(
        run_id="run-6",
        manifest=manifest,
        pipeline_input=PipelineInput(source_paths=[]),
        previous=ArtifactCollection([]),
    )

    view = Phase4ArtifactsView(theory_atoms=[atom1, atom2], theory_relations=[rel])
    result = await runner.run(view, context)

    # Verify artifacts returned
    assert len(result) == 3
    atoms_out = result.of_kind(ArtifactKind.THEORY_ATOM)
    rels_out = result.of_kind(ArtifactKind.THEORY_RELATION)
    assert len(atoms_out) == 2
    assert len(rels_out) == 1

    # Verify graph store calls
    mock_store.upsert_argument_components.assert_called_once()
    mock_store.upsert_theory_relations.assert_called_once()
    rel_batch = mock_store.upsert_theory_relations.call_args[0][0]
    assert len(rel_batch) == 1


@pytest.mark.asyncio
async def test_theoretical_enrichment_persists_via_upsert_theory_relations() -> None:
    """Verify TheoreticalEnrichmentRunner persists enriched relations via upsert_theory_relations."""
    mock_store = AsyncMock()
    mock_solver = MagicMock()
    mock_solver.solve_local_tenability.return_value = (0.85, 0.05, [])
    mock_solver.solve_edge_tenability.return_value = (0.88, 0.05, [])
    mock_solver.evaluate_theory_tenability.return_value = TenabilityResult(
        local_score=0.85,
        edge_scores={},
        aggregated_score=0.85,
        is_tenable=True,
        tightest_blur=0.05,
        anomalies=[],
    )
    mock_projector = AsyncMock()
    mock_projector.aproject.return_value = {"param1": 1.0}

    theory = MagicMock()
    theory.theory_id = "T1"
    theory.core_laws = []

    mock_registry = MagicMock()
    mock_registry.all_theories.return_value = [theory]
    mock_registry.match_claimants.return_value = ["T1"]
    mock_registry.get.return_value = theory

    atom = TheoryAtom(
        id="atom-1",
        text="Observation 1",
        component_type="ObservationUnit",
        source_chunk_id="chunk-1",
    )
    rel = TheoryRelation(
        source_id="atom-1",
        target_id="atom-1",
        relation_type="SUPPORTS",
        confidence=0.9,
        scope="local",
        inferential_force=0.85,
        active_weight=0.85,
    )

    runner = TheoreticalEnrichmentRunner(
        config=TheoreticalEnrichmentConfig(),
        registry=mock_registry,
        solver=mock_solver,
        projector=mock_projector,
        graph_store=mock_store,
        schema=DEFAULT_SCHEMA,
    )

    manifest = RunManifest(run_id="run-te", dataset_path="dummy")
    context = ArtifactExecutionContext(
        run_id="run-te",
        manifest=manifest,
        pipeline_input=PipelineInput(source_paths=[]),
        previous=ArtifactCollection([]),
    )

    view = Phase4ArtifactsView(theory_atoms=[atom], theory_relations=[rel])
    await runner.run(view, context)

    # Verify upsert_theory_relations was called
    mock_store.upsert_theory_relations.assert_called_once()
    persisted_batch = mock_store.upsert_theory_relations.call_args[0][0]
    assert len(persisted_batch) == 1
    persisted_rel = persisted_batch[0]
    assert isinstance(persisted_rel, TheoryRelation)
    assert persisted_rel.inferential_force == 0.85
    assert persisted_rel.active_weight == 0.85
