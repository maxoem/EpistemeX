from pathlib import Path

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus


class StubPhase:
    def __init__(self, name: str):
        self.name = name

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_resume_from_run_persists_new_execution_result(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation"),
            StubPhase("Phase 2: Entity & Local Relation Discovery"),
            StubPhase("Phase 3: Global Relation Extraction"),
        ],
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
        phase_records=[
            RunPhaseRecord(phase_name="Phase 1: Data Foundation", ordinal=1, status=RunStatus.COMPLETED),
            RunPhaseRecord(phase_name="Phase 2: Entity & Local Relation Discovery", ordinal=2, status=RunStatus.COMPLETED),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)

    execution = await pipeline.resume_from_run("run-old", PipelineInput(source_paths=["docs/example.md"]))

    assert execution.report.status == RunStatus.COMPLETED
    assert len(list((tmp_path / "runs").glob("*.json"))) >= 2
