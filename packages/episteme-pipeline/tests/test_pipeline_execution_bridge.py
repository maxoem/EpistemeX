from pathlib import Path

import pytest

from episteme_pipeline.artifacts.builders import (
    build_chunk_artifact,
    build_document_artifact,
    build_entity_mention_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
)
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.domain import L1Chunk, L1Document, L2Entity, L2Triple
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import ExecutionResult, RunStatus


class StubPhase1:
    name = "Phase 1: Data Foundation"

    async def run(self, input: PipelineInput, context: ArtifactExecutionContext) -> ArtifactCollection:
        document = L1Document(
            id="doc-1",
            title="Doc",
            source_path=input.source_paths[0],
            chapter_count=1,
            chunk_count=1,
        )
        chunk = L1Chunk(
            id="chunk-1",
            text="Hello world",
            source_doc_id="doc-1",
            chapter_id="chap-1",
            sequence_index=0,
            token_count=2,
        )
        return ArtifactCollection([
            build_document_artifact(document, run_id=context.run_id, phase_name=self.name, method="test.phase1"),
            build_chunk_artifact(chunk, run_id=context.run_id, phase_name=self.name, method="test.phase1"),
        ])


class StubPhase2:
    name = "Phase 2: Entity & Local Relation Discovery"

    async def run(self, input: Phase1ArtifactsView, context: ArtifactExecutionContext) -> ArtifactCollection:
        entity = L2Entity(id="entity-1", label="PERSON", name="Kant", source_chunk_ids=["chunk-1"])
        triple = L2Triple(subject_id="entity-1", predicate="MENTIONS", object_id="entity-1", confidence=1.0, scope="local", source_chunk_id="chunk-1")
        mention = build_entity_mention_artifact(entity, "chunk-1", run_id=context.run_id, phase_name=self.name, method="test.phase2")
        linked = build_linked_entity_artifact(entity, [mention.artifact_id], run_id=context.run_id, phase_name=self.name, method="test.phase2")
        relation = build_local_relation_artifact(triple, run_id=context.run_id, phase_name=self.name, method="test.phase2")
        return ArtifactCollection([mention, linked, relation])


class StubPhase3:
    name = "Phase 3: Global Relation Extraction"

    async def run(self, input, context: ArtifactExecutionContext) -> ArtifactCollection:
        return ArtifactCollection([])


class StubPhase3First:
    name = "Phase 3: Global Relation Extraction"
    input_view = Phase2ArtifactsView

    def __init__(self) -> None:
        self.received_input = None

    async def run(
        self, input: Phase2ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        self.received_input = input
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_pipeline_persists_manifest_and_phase1_phase2_artifacts(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
    config.execution.persist_phase1_artifacts = True
    config.execution.persist_phase2_artifacts = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[StubPhase1(), StubPhase2(), StubPhase3()],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    execution = await pipeline.run(PipelineInput(source_paths=["docs/example.md"]))

    assert isinstance(execution, ExecutionResult)
    assert execution.report.status == RunStatus.COMPLETED
    assert len(list((tmp_path / "runs").glob("*.json"))) == 1
    assert len(list((tmp_path / "artifacts").glob("**/*.json"))) == 5
    assert execution.report.artifact_counts_by_kind["document"] == 1
    assert execution.report.artifact_counts_by_kind["chunk"] == 1
    assert execution.report.artifact_counts_by_kind["entity_mention"] == 1


@pytest.mark.asyncio
async def test_pipeline_passes_phase_view_when_first_configured_phase_is_phase3(
    tmp_path: Path, graph_store
):
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    phase3 = StubPhase3First()
    pipeline = Pipeline(
        phases=[phase3],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    execution = await pipeline.run(PipelineInput(source_paths=["docs/example.md"]))

    assert isinstance(execution, ExecutionResult)
    assert execution.report.status == RunStatus.COMPLETED
    assert isinstance(phase3.received_input, Phase2ArtifactsView)
    assert phase3.received_input.entities == []
