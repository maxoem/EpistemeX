"""Integration tests exercising the full artifact pipeline through all phases."""

from pathlib import Path

import pytest

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    Phase3ArtifactsView,
)
from episteme_pipeline.artifacts.mappers import (
    map_phase1_output_to_artifacts,
    map_phase2_output_to_artifacts,
    map_phase3_output_to_artifacts,
)
from episteme_pipeline.artifacts.models import ArtifactKind
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
)
from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation
from episteme_pipeline.contracts.phase_contracts import (
    PipelineInput,
    Phase1Output,
    Phase2Output,
    Phase3Output,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import (
    ExecutionResult,
    RunStatus,
)


class FullStubPhase1:
    """Stub Phase 1: produces DOCUMENT + CHUNK artifacts."""

    name = "Phase 1: Data Foundation"
    phase_key = "phase1"

    async def run(
        self, input: PipelineInput, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        artifacts = []
        for source_path in input.source_paths:
            doc = L1Document(
                id="doc-int-1",
                title="Integration Test Doc",
                source_path=source_path,
                chapter_count=1,
                chunk_count=1,
            )
            chunk = L1Chunk(
                id="chunk-int-1",
                text="Kant argued that space is a form of intuition. Hegel disagreed.",
                source_doc_id=doc.id,
                chapter_id="chap-1",
                sequence_index=0,
                token_count=14,
            )
            artifacts.append(ArtifactCollection.__new__(ArtifactCollection))
        artifacts = map_phase1_output_to_artifacts(
            Phase1Output(
                documents=[doc],
                chunks=[chunk],
            ),
            run_id=context.run_id,
        )
        return ArtifactCollection(artifacts)


class FullStubPhase2:
    """Stub Phase 2: produces ENTITY_MENTION + LINKED_ENTITY + LOCAL_RELATION."""

    name = "Phase 2: Entity & Local Relation Discovery"
    phase_key = "phase2"

    async def run(
        self,
        input: Phase1ArtifactsView,
        context: ArtifactExecutionContext,
    ) -> ArtifactCollection:
        entities = [
            L2Entity(
                id="entity-kant",
                label="PERSON",
                name="Kant",
                source_chunk_ids=["chunk-int-1"],
            ),
            L2Entity(
                id="entity-hegel",
                label="PERSON",
                name="Hegel",
                source_chunk_ids=["chunk-int-1"],
            ),
        ]
        output = Phase2Output(
            entities=entities,
            local_triples=[
                L2Triple(
                    subject_id="entity-kant",
                    predicate="OPPOSED_TO",
                    object_id="entity-hegel",
                    confidence=0.9,
                    scope="local",
                    source_chunk_id="chunk-int-1",
                ),
            ],
        )
        return ArtifactCollection(
            map_phase2_output_to_artifacts(output, run_id=context.run_id)
        )


class FullStubPhase3:
    """Stub Phase 3: produces GLOBAL_RELATION artifacts."""

    name = "Phase 3: Global Relation Extraction"
    phase_key = "phase3"

    async def run(
        self,
        input: Phase2ArtifactsView,
        context: ArtifactExecutionContext,
    ) -> ArtifactCollection:
        output = Phase3Output(
            global_triples=[
                L2Triple(
                    subject_id="entity-kant",
                    predicate="IMPLIZIERT",
                    object_id="entity-hegel",
                    confidence=0.85,
                    scope="global",
                    source_chunk_id="chunk-int-1",
                ),
            ],
        )
        return ArtifactCollection(
            map_phase3_output_to_artifacts(output, run_id=context.run_id)
        )


class FullStubPhase4:
    """Stub Phase 4: produces ARGUMENT_COMPONENT + ARGUMENT_RELATION."""

    name = "Phase 4: Argument Mining"
    phase_key = "phase4"

    async def run(
        self,
        input: Phase3ArtifactsView,
        context: ArtifactExecutionContext,
    ) -> ArtifactCollection:
        from episteme_pipeline.artifacts.builders import (
            build_argument_component_artifact,
            build_argument_relation_artifact,
        )

        components = [
            TheoryAtom(
                id="ac-int-1",
                text="Kant's transcendental idealism provides the foundation.",
                component_type="ANTECEDENT",
                source_chunk_id="chunk-int-1",
            ),
            TheoryAtom(
                id="ac-int-2",
                text="Hegel's dialectics refute this foundation.",
                component_type="EMPIRICAL_OBSERVATION",
                source_chunk_id="chunk-int-1",
            ),
        ]
        relations = [
            TheoryRelation(
                source_id="ac-int-1",
                target_id="ac-int-2",
                relation_type="ATTACKS",
                confidence=0.95,
                scope="local",
            ),
        ]
        artifacts = []
        for i, comp in enumerate(components):
            artifacts.append(
                build_argument_component_artifact(
                    comp,
                    run_id=context.run_id,
                    phase_name="Phase 4: Argument Mining",
                    method="stub.phase4",
                )
            )
        for j, rel in enumerate(relations):
            artifacts.append(
                build_argument_relation_artifact(
                    rel,
                    run_id=context.run_id,
                    phase_name="Phase 4: Argument Mining",
                    method="stub.phase4",
                )
            )
        return ArtifactCollection(artifacts)


class FullStubPhase5a:
    """Stub Phase 5a: returns empty collection (instance fusion)."""

    name = "Phase 5a: Instance Fusion"
    phase_key = "phase3b"

    async def run(
        self,
        input: Phase2ArtifactsView,
        context: ArtifactExecutionContext,
    ) -> ArtifactCollection:
        return ArtifactCollection([])


class FullStubPhase5b:
    """Stub Phase 5b: returns empty collection (theory fusion)."""

    name = "Phase 5b: Theory Fusion"
    phase_key = "phase5"

    async def run(
        self, input: PipelineInput, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_full_run_through_all_phases(tmp_path: Path, graph_store):
    """Exercise the full artifact pipeline: Phase 1 -> 2 -> 3 -> 4 -> 5a -> 5b."""
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    # Phase order: 1, 2, 5a, 3, 4, 5b (as defined in _build_execution_plan)
    pipeline = Pipeline(
        phases=[
            FullStubPhase1(),
            FullStubPhase2(),
            FullStubPhase5a(),
            FullStubPhase3(),
            FullStubPhase4(),
            FullStubPhase5b(),
        ],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    result = await pipeline.run(
        PipelineInput(source_paths=["docs/integration_test.md"])
    )

    assert isinstance(result, ExecutionResult)
    assert result.manifest.status == RunStatus.COMPLETED
    assert result.report.status == RunStatus.COMPLETED

    # Verify phase records exist for all executed phases
    phase_names = {r.phase_name for r in result.report.phase_records}
    assert "Phase 1: Data Foundation" in phase_names
    assert "Phase 2: Entity & Local Relation Discovery" in phase_names
    assert "Phase 3: Global Relation Extraction" in phase_names
    assert "Phase 4: Argument Mining" in phase_names

    # Verify artifacts were produced and stored
    assert result.report.artifact_counts_by_kind[ArtifactKind.DOCUMENT.value] >= 1
    assert result.report.artifact_counts_by_kind[ArtifactKind.CHUNK.value] >= 1
    assert result.report.artifact_counts_by_kind[ArtifactKind.LINKED_ENTITY.value] >= 2
    assert result.report.artifact_counts_by_kind[ArtifactKind.LOCAL_RELATION.value] >= 1
    assert result.report.artifact_counts_by_kind[ArtifactKind.GLOBAL_RELATION.value] >= 1
    assert result.report.artifact_counts_by_kind[ArtifactKind.THEORY_ATOM.value] >= 2
    assert result.report.artifact_counts_by_kind[ArtifactKind.THEORY_RELATION.value] >= 1


@pytest.mark.asyncio
async def test_full_run_artifact_persistence(tmp_path: Path, graph_store):
    """Verify artifacts are written to the JsonArtifactStore during full run."""
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            FullStubPhase1(),
            FullStubPhase2(),
            FullStubPhase5a(),
            FullStubPhase3(),
            FullStubPhase4(),
            FullStubPhase5b(),
        ],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    result = await pipeline.run(
        PipelineInput(source_paths=["docs/full_persist_test.md"])
    )

    # Verify artifacts exist on disk
    store = JsonArtifactStore(tmp_path / "artifacts")
    artifacts = await store.list_run_artifacts(result.manifest.run_id)
    assert len(artifacts) > 0

    # Verify manifest exists
    manifest = pipeline._manifest_store.read_manifest(result.manifest.run_id)
    assert manifest is not None
    assert manifest.status == RunStatus.COMPLETED


@pytest.mark.asyncio
async def test_full_run_with_artifact_views(tmp_path: Path, graph_store):
    """Verify artifact views can be built from persisted artifacts."""
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            FullStubPhase1(),
            FullStubPhase2(),
            FullStubPhase5a(),
            FullStubPhase3(),
            FullStubPhase4(),
            FullStubPhase5b(),
        ],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    result = await pipeline.run(PipelineInput(source_paths=["docs/view_test.md"]))

    # After the run, verify we can build views from the stored artifacts
    store = JsonArtifactStore(tmp_path / "artifacts")
    all_artifacts = await store.list_run_artifacts(result.manifest.run_id)

    p1_collection = ArtifactCollection(
        [
            a
            for a in all_artifacts
            if a.kind in (ArtifactKind.DOCUMENT, ArtifactKind.CHUNK)
        ]
    )
    p1_view = Phase1ArtifactsView.from_collection(p1_collection)
    assert len(p1_view.documents) >= 1
    assert len(p1_view.chunks) >= 1

    p2_collection = ArtifactCollection(
        [
            a
            for a in all_artifacts
            if a.kind
            in (
                ArtifactKind.ENTITY_MENTION,
                ArtifactKind.LINKED_ENTITY,
                ArtifactKind.LOCAL_RELATION,
            )
        ]
    )
    p2_view = Phase2ArtifactsView.from_collection(p2_collection)
    assert len(p2_view.entities) >= 2


@pytest.mark.asyncio
async def test_full_run_schema_version_persisted(tmp_path: Path, graph_store):
    """Verify schema_version is set in manifest and persisted."""
    config = PipelineConfig()
    config.graph_schema.version = "v2-integration"
    config.execution.persist_run_manifests = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            FullStubPhase1(),
            FullStubPhase2(),
            FullStubPhase3(),
            FullStubPhase4(),
        ],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    result = await pipeline.run(PipelineInput(source_paths=["docs/schema_ver_test.md"]))

    assert result.manifest.schema_version == "v2-integration"

    # Verify persisted manifest has the schema version
    persisted = pipeline._manifest_store.read_manifest(result.manifest.run_id)
    assert persisted is not None
    assert persisted.schema_version == "v2-integration"
