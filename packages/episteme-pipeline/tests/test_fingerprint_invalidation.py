from pathlib import Path

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.fingerprints import fingerprint_existing_sources
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus


class StubPhase:
    def __init__(self, name: str, fingerprint: str, phase_key: str | None = None):
        self.name = name
        self.fingerprint = fingerprint
        self.phase_key = phase_key or name.lower().split(":")[0].replace(" ", "")

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_choose_reuse_source_detects_phase_config_change(
    tmp_path: Path, graph_store
):
    source = tmp_path / "doc.md"
    source.write_text("hello", encoding="utf-8")

    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation", "same"),
            StubPhase("Phase 2: Entity & Local Relation Discovery", "new"),
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
        phase_config_fingerprints={"phase1": "same", "phase2": "old"},
        input_fingerprint_inputs={
            "source_paths": [str(source)],
            "metadata": {},
            "source_fingerprint": fingerprint_existing_sources([str(source)]),
        },
        phase_records=[
            RunPhaseRecord(
                phase_name="Phase 1: Data Foundation",
                ordinal=1,
                status=RunStatus.COMPLETED,
            ),
            RunPhaseRecord(
                phase_name="Phase 2: Entity & Local Relation Discovery",
                ordinal=2,
                status=RunStatus.COMPLETED,
            ),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)
    pipeline._build_manifest = lambda *, run_id, pipeline_input: RunManifest(
        run_id=run_id,
        status=RunStatus.RUNNING,
        input_fingerprint="same-input",
        input_fingerprint_inputs={
            "source_paths": [str(source)],
            "metadata": {},
            "source_fingerprint": fingerprint_existing_sources([str(source)]),
        },
        phase_config_fingerprints={"phase1": "same", "phase2": "new"},
    )
    pipeline._phase_config_fingerprints = lambda: {"phase1": "same", "phase2": "new"}

    decision = await pipeline._choose_reuse_source(
        pipeline._build_manifest(
            run_id="run-new", pipeline_input=PipelineInput(source_paths=[str(source)])
        )
    )

    assert decision.reused_phase_ordinals == [1]
    assert decision.invalidated_phase_ordinals == [2]


@pytest.mark.asyncio
async def test_choose_reuse_source_detects_source_change(tmp_path: Path, graph_store):
    source = tmp_path / "doc.md"
    source.write_text("hello", encoding="utf-8")

    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[StubPhase("Phase 1: Data Foundation", "same")],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    prior = RunManifest(
        run_id="run-old",
        status=RunStatus.COMPLETED,
        input_fingerprint="old-input",
        phase_config_fingerprints={"phase1": "same"},
        input_fingerprint_inputs={
            "source_paths": [str(source)],
            "metadata": {},
            "source_fingerprint": "old-source",
        },
        phase_records=[
            RunPhaseRecord(
                phase_name="Phase 1: Data Foundation",
                ordinal=1,
                status=RunStatus.COMPLETED,
            )
        ],
    )
    pipeline._manifest_store.write_manifest(prior)
    pipeline._build_manifest = lambda *, run_id, pipeline_input: RunManifest(
        run_id=run_id,
        status=RunStatus.RUNNING,
        input_fingerprint="new-input",
        input_fingerprint_inputs={
            "source_paths": [str(source)],
            "metadata": {},
            "source_fingerprint": fingerprint_existing_sources([str(source)]),
        },
        phase_config_fingerprints={"phase1": "same"},
    )

    decision = await pipeline._choose_reuse_source(
        pipeline._build_manifest(
            run_id="run-new", pipeline_input=PipelineInput(source_paths=[str(source)])
        )
    )

    assert decision.reused_phase_ordinals == []
    assert decision.invalidated_phase_ordinals == [1]
