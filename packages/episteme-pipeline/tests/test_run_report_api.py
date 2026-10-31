from pathlib import Path

import pytest
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactProvenance,
    ChunkArtifact,
)
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import (
    ArtifactReportEntry,
    RunManifest,
    RunPhaseRecord,
    RunReport,
    RunStatus,
)


class StubPhase:
    def __init__(self, name: str = "Phase 1: Data Foundation", phase_key: str = "phase1") -> None:
        self.name = name
        self.phase_key = phase_key

    async def run(self, input, context):
        from episteme_pipeline.artifacts.execution import ArtifactCollection
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_get_run_report_returns_manifest_and_artifact_summary(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(phases=[StubPhase()], config=config, graph_reader=graph_store, projection_graph=graph_store, checkpoint_store=graph_store)

    manifest = RunManifest(
        run_id="run-1",
        status=RunStatus.COMPLETED,
        phase_records=[RunPhaseRecord(phase_name="Phase 1: Data Foundation", ordinal=1, status=RunStatus.COMPLETED)],
    )
    pipeline._manifest_store.write_manifest(manifest)

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
    await artifact_store.write_artifact(
        ArtifactEnvelope(
            artifact_id="artifact::chunk-1",
            identity_key="chunk::chunk-1",
            kind=ArtifactKind.CHUNK,
            run_id="run-1",
            phase_name="Phase 1: Data Foundation",
            method="phase1.foundation",
            dependency_fingerprint="dep-1",
            provenance=ArtifactProvenance(),
            payload=ChunkArtifact(
                chunk_id="chunk-1",
                document_id="doc-1",
                text="hello",
                sequence_index=0,
                token_count=1,
            ),
        )
    )
    pipeline._artifact_store = artifact_store

    report = await pipeline.get_run_report("run-1")

    assert isinstance(report, RunReport)
    assert report.manifest.run_id == "run-1"
    assert report.artifact_counts_by_kind["chunk"] == 1
    assert report.artifact_entries[0].identity_key == "chunk::chunk-1"
    assert report.artifact_entries[0].run_id == "run-1"
    assert report.artifact_entries[0].reused is False


@pytest.mark.asyncio
async def test_reused_run_copies_reused_artifact_entries_and_counts(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(phases=[StubPhase()], config=config, graph_reader=graph_store, projection_graph=graph_store, checkpoint_store=graph_store)

    manifest = RunManifest(
        run_id="run-1",
        status=RunStatus.COMPLETED,
        input_fingerprint="same-input",
        phase_config_fingerprints={"phase1": "same-phase"},
        phase_records=[
            RunPhaseRecord(
                phase_name="Phase 1: Data Foundation",
                phase_ordinal=1,
                status=RunStatus.COMPLETED,
                artifact_ids=["artifact::chunk-1"],
            )
        ],
    )
    pipeline._manifest_store.write_manifest(manifest)

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
    await artifact_store.write_artifact(
        ArtifactEnvelope(
            artifact_id="artifact::chunk-1",
            identity_key="chunk::chunk-1",
            kind=ArtifactKind.CHUNK,
            run_id="run-1",
            phase_name="Phase 1: Data Foundation",
            method="phase1.foundation",
            dependency_fingerprint="dep-1",
            provenance=ArtifactProvenance(),
            payload=ChunkArtifact(
                chunk_id="chunk-1",
                document_id="doc-1",
                text="hello",
                sequence_index=0,
                token_count=1,
            ),
        )
    )
    pipeline._artifact_store = artifact_store

    pipeline._build_manifest = lambda *, run_id, pipeline_input: RunManifest(
        run_id=run_id,
        status=RunStatus.RUNNING,
        input_fingerprint="same-input",
        phase_config_fingerprints={"phase1": "same-phase"},
        input_fingerprint_inputs={"source_paths": list(pipeline_input.source_paths), "metadata": pipeline_input.metadata},
    )

    result = await pipeline.run(PipelineInput(source_paths=[]))

    assert result.report.reused_phase_ordinals == [1]
    assert result.report.invalidated_phase_ordinals == []
    assert result.report.artifact_counts_by_kind["chunk"] == 1
    assert result.report.reused_artifact_counts_by_kind["chunk"] == 1
    assert result.report.new_artifact_counts_by_kind == {}
    assert len(result.report.artifact_entries) == 1
    assert result.report.artifact_entries[0].artifact_id == "artifact::chunk-1"
    assert result.report.artifact_entries[0].run_id == "run-1"
    assert result.report.artifact_entries[0].reused is True


@pytest.mark.asyncio
async def test_get_run_artifacts_supports_filters(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(phases=[StubPhase()], config=config, graph_reader=graph_store, projection_graph=graph_store, checkpoint_store=graph_store)

    manifest = RunManifest(
        run_id="run-1",
        status=RunStatus.COMPLETED,
        phase_records=[RunPhaseRecord(phase_name="Phase 1: Data Foundation", ordinal=1, status=RunStatus.COMPLETED)],
    )
    pipeline._manifest_store.write_manifest(manifest)

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
    await artifact_store.write_artifact(
        ArtifactEnvelope(
            artifact_id="artifact::chunk-1",
            identity_key="chunk::chunk-1",
            kind=ArtifactKind.CHUNK,
            run_id="run-1",
            phase_name="Phase 1: Data Foundation",
            method="phase1.foundation",
            dependency_fingerprint="dep-1",
            provenance=ArtifactProvenance(),
            payload=ChunkArtifact(
                chunk_id="chunk-1",
                document_id="doc-1",
                text="hello",
                sequence_index=0,
                token_count=1,
            ),
        )
    )
    pipeline._artifact_store = artifact_store

    artifacts = await pipeline.get_run_artifacts("run-1", phase_name="Phase 1: Data Foundation", kind="chunk")

    assert len(artifacts) == 1
    assert isinstance(artifacts[0], ArtifactReportEntry)


@pytest.mark.asyncio
async def test_get_run_report_reconstructs_new_vs_reused_breakdown_from_manifest(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[StubPhase(phase_key="phase1"), StubPhase(phase_key="phase2")],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    manifest = RunManifest(
        run_id="run-2",
        status=RunStatus.COMPLETED,
        phase_records=[
            RunPhaseRecord(phase_name="Phase 1: Data Foundation", ordinal=1, status=RunStatus.COMPLETED, reused=True),
            RunPhaseRecord(phase_name="Phase 1: Data Foundation", ordinal=2, status=RunStatus.COMPLETED, reused=False),
        ],
    )
    pipeline._manifest_store.write_manifest(manifest)

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
    await artifact_store.write_artifact(
        ArtifactEnvelope(
            artifact_id="artifact::chunk-reused",
            identity_key="chunk::chunk-reused",
            kind=ArtifactKind.CHUNK,
            run_id="run-2",
            phase_name="Phase 1: Data Foundation",
            method="phase1.foundation",
            dependency_fingerprint="dep-1",
            provenance=ArtifactProvenance(),
            payload=ChunkArtifact(
                chunk_id="chunk-reused",
                document_id="doc-1",
                text="hello",
                sequence_index=0,
                token_count=1,
            ),
        )
    )
    pipeline._artifact_store = artifact_store

    report = await pipeline.get_run_report("run-2")

    assert report.artifact_counts_by_kind["chunk"] == 1
    assert report.reused_artifact_counts_by_kind["chunk"] == 1
