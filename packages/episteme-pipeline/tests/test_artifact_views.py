"""Tests for ArtifactsView kind validation in execution.py."""

from episteme_pipeline.artifacts.builders import (
    build_document_artifact,
    build_chunk_artifact,
    build_entity_mention_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
    build_global_relation_artifact,
    build_argument_component_artifact,
    build_argument_relation_artifact,
    build_fusion_cluster_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    ArtifactExecutionContext,
)
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.runs.models import RunManifest

_run_manifest = RunManifest(run_id="test-run")


def _make_phase1_context():
    return ArtifactExecutionContext(
        run_id="test",
        manifest=_run_manifest,
        pipeline_input=PipelineInput(source_paths=[]),
    )


def test_phase1_view_filters_to_allowed_kinds():
    """Phase1ArtifactsView should only include DOCUMENT and CHUNK artifacts."""
    doc = L1Document(
        id="doc-1", title="Doc", source_path="/doc.md", chapter_count=1, chunk_count=1
    )
    chunk = L1Chunk(
        id="chunk-1",
        text="Hello",
        source_doc_id="doc-1",
        chapter_id="chap-1",
        sequence_index=0,
        token_count=1,
    )

    doc_artifact = build_document_artifact(
        doc, run_id="test", phase_name="Phase 1", method="test"
    )
    chunk_artifact = build_chunk_artifact(
        chunk, run_id="test", phase_name="Phase 1", method="test"
    )
    # A phase 4 artifact that would be noise in phase 1
    fusion_artifact = build_fusion_cluster_artifact(
        cluster=["d1"],
        theory_fusion_applied=False,
        run_id="test",
        phase_name="Phase 5a",
        method="test",
    )

    collection = ArtifactCollection([doc_artifact, chunk_artifact, fusion_artifact])
    view = Phase1ArtifactsView.from_collection(collection)

    assert len(view.documents) == 1
    assert len(view.chunks) == 1
    # Fusion artifact should not appear in Phase1 view


def test_phase2_view_filters_to_allowed_kinds():
    """Phase2ArtifactsView should only include ENTITY_MENTION, LINKED_ENTITY, LOCAL_RELATION."""
    entities = L2Entity(id="e1", label="PERSON", name="Kant", source_chunk_ids=["c1"])
    mention = build_entity_mention_artifact(
        entity=entities,
        chunk_id="c1",
        run_id="test",
        phase_name="Phase 2",
        method="test",
    )
    linked = build_linked_entity_artifact(
        entity=entities,
        mention_artifact_ids=[mention.artifact_id],
        run_id="test",
        phase_name="Phase 2",
        method="test",
    )
    relation = build_local_relation_artifact(
        triple=L2Triple(
            subject_id="e1",
            predicate="MENTIONS",
            object_id="e2",
            confidence=0.9,
            scope="local",
            source_chunk_id="c1",
        ),
        run_id="test",
        phase_name="Phase 2",
        method="test",
    )

    collection = ArtifactCollection([mention, linked, relation])
    view = Phase2ArtifactsView.from_collection(collection)

    assert len(view.entities) == 1
    assert len(view.local_triples) == 1


def test_phase3_view_filters_to_allowed_kinds():
    """Phase3ArtifactsView should only include CHUNK and GLOBAL_RELATION artifacts."""
    triple = build_global_relation_artifact(
        triple=L2Triple(
            subject_id="e1",
            predicate="IMPLIZIERT",
            object_id="e2",
            confidence=0.9,
            scope="global",
            source_chunk_id="c1",
        ),
        relation_dist={"IMPLIZIERT": 1},
        run_id="test",
        phase_name="Phase 3",
        method="test",
    )

    collection = ArtifactCollection([triple])
    from episteme_pipeline.artifacts.execution import Phase3ArtifactsView

    view = Phase3ArtifactsView.from_collection(collection)

    assert len(view.global_triples) == 1


def test_phase4_view_filters_to_allowed_kinds():
    """Phase4ArtifactsView should only include ARGUMENT_COMPONENT and ARGUMENT_RELATION."""
    component = build_argument_component_artifact(
        component=TheoryAtom(
            id="ac1",
            text="Claim text",
            component_type="ANTECEDENT",
            source_chunk_id="c1",
        ),
        run_id="test",
        phase_name="Phase 4",
        method="test",
    )
    relation = build_argument_relation_artifact(
        relation=TheoryRelation(
            source_id="ac1",
            target_id="ac2",
            relation_type="SUPPORTS",
            confidence=0.9,
            scope="local",
        ),
        run_id="test",
        phase_name="Phase 4",
        method="test",
    )

    collection = ArtifactCollection([component, relation])
    from episteme_pipeline.artifacts.execution import Phase4ArtifactsView

    view = Phase4ArtifactsView.from_collection(collection)

    assert len(view.theory_atoms) == 1
    assert len(view.theory_relations) == 1


def test_artifact_view_respects_of_kind_filter():
    """Phase views should use of_kind to filter artifacts, not iterate all."""
    # Build artifacts of multiple kinds
    doc = L1Document(
        id="d1", title="T", source_path="/x", chapter_count=1, chunk_count=1
    )
    doc_artifact = build_document_artifact(
        doc, run_id="test", phase_name="Phase 1", method="test"
    )
    fusion_artifact = build_fusion_cluster_artifact(
        cluster=["d1"],
        theory_fusion_applied=False,
        run_id="test",
        phase_name="Phase 5a",
        method="test",
    )

    collection = ArtifactCollection([doc_artifact, fusion_artifact])

    # Phase 1 view should only process documents/chunks, ignoring fusion
    view = Phase1ArtifactsView.from_collection(collection)
    assert len(view.documents) == 1
    assert len(view.chunks) == 0
