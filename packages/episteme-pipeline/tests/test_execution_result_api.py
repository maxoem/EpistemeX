from pathlib import Path

import pytest

from episteme_pipeline.artifacts.execution import ArtifactCollection, ArtifactExecutionContext, Phase1ArtifactsView, Phase2ArtifactsView
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.contracts.domain import L1Chunk, L1Document, L2Entity, L2Triple
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import ExecutionResult, RunManifest, RunPhaseRecord, RunStatus


class StubPhase1:
    name = "Phase 1: Data Foundation"

    async def run(self, input: PipelineInput, context: ArtifactExecutionContext):
        artifacts = []
        for source_path in input.source_paths:
            document = L1Document(
                id="doc-1",
                title="Doc",
                source_path=source_path,
                chapter_count=1,
                chunk_count=1,
            )
            chunk = L1Chunk(
                id="chunk-1",
                text="Hello",
                source_doc_id=document.id,
                chapter_id="chap-1",
                sequence_index=0,
                token_count=1,
            )
            from episteme_pipeline.artifacts.builders import build_document_artifact, build_chunk_artifact
            artifacts.append(build_document_artifact(document, run_id=context.run_id, phase_name=self.name, method="test.phase1"))
            artifacts.append(build_chunk_artifact(chunk, run_id=context.run_id, phase_name=self.name, method="test.phase1"))
        return ArtifactCollection(artifacts)


class StubPhase2:
    name = "Phase 2: Entity & Local Relation Discovery"

    async def run(self, input: Phase1ArtifactsView, context: ArtifactExecutionContext):
        entity = L2Entity(id="entity-1", label="PERSON", name="Kant", source_chunk_ids=["chunk-1"])
        triple = L2Triple(subject_id="entity-1", predicate="MENTIONS", object_id="entity-1", confidence=1.0, scope="local", source_chunk_id="chunk-1")
        from episteme_pipeline.artifacts.builders import build_entity_mention_artifact, build_linked_entity_artifact, build_local_relation_artifact
        mention = build_entity_mention_artifact(entity, "chunk-1", run_id=context.run_id, phase_name=self.name, method="test.phase2")
        linked = build_linked_entity_artifact(entity, [mention.artifact_id], run_id=context.run_id, phase_name=self.name, method="test.phase2")
        relation = build_local_relation_artifact(triple, run_id=context.run_id, phase_name=self.name, method="test.phase2")
        return ArtifactCollection([mention, linked, relation])


class StubPhase3:
    name = "Phase 3: Global Relation Extraction"

    async def run(self, input: Phase2ArtifactsView, context: ArtifactExecutionContext):
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_run_returns_execution_result_with_artifact_report(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
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
    assert execution.report.phase_records[0].phase_name == "Phase 1: Data Foundation"
    assert execution.report.artifact_counts_by_kind["document"] == 1
    assert execution.report.artifact_counts_by_kind["chunk"] == 1


@pytest.mark.asyncio
async def test_resume_from_run_returns_execution_result(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[StubPhase1(), StubPhase2(), StubPhase3()],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    prior = RunManifest(
        run_id="run-old",
        status=RunStatus.COMPLETED,
        input_fingerprint="same-input",
        phase_config_fingerprints={"phase_1": "same-phase", "phase_2": "same-phase", "phase_3": "same-phase"},
        phase_records=[RunPhaseRecord(phase_name="Phase 1: Data Foundation", ordinal=1, status=RunStatus.COMPLETED)],
    )
    pipeline._manifest_store.write_manifest(prior)

    execution = await pipeline.resume_from_run(
        "run-old",
        PipelineInput(source_paths=["docs/example.md"]),
        from_phase=1,
    )

    assert isinstance(execution, ExecutionResult)
    assert execution.report.status == RunStatus.COMPLETED
    assert execution.report.invalidation_reason is not None
