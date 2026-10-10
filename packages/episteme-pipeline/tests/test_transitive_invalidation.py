from pathlib import Path

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus


class StubPhase1:
    name = "Phase 1: Data Foundation"

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


class StubPhase2:
    name = "Phase 2: Entity & Local Relation Discovery"

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


class StubPhase3:
    name = "Phase 3: Global Relation Extraction"

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


class StubPhase4:
    name = "Phase 4: Argument Mining"

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


class StubPhase5:
    name = "Phase 5b: Argument Clustering & Theory Fusion"

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_invalidation_propagates_after_first_invalid_phase(
    tmp_path: Path, graph_store
):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[StubPhase1(), StubPhase2(), StubPhase3(), StubPhase4(), StubPhase5()],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    prior = RunManifest(
        run_id="run-old",
        status=RunStatus.COMPLETED,
        input_fingerprint="same-input",
        phase_config_fingerprints={
            "phase_1": {"config.a": "same"},
            "phase_2": {"config.a": "old"},
            "phase_3": {"config.a": "old"},
            "phase_4": {"config.a": "old"},
            "phase_5": {"config.a": "old"},
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
            RunPhaseRecord(
                phase_name="Phase 3: Global Relation Extraction",
                ordinal=3,
                status=RunStatus.COMPLETED,
            ),
            RunPhaseRecord(
                phase_name="Phase 4: Argument Mining",
                ordinal=4,
                status=RunStatus.COMPLETED,
            ),
            RunPhaseRecord(
                phase_name="Phase 5b: Argument Clustering & Theory Fusion",
                ordinal=5,
                status=RunStatus.COMPLETED,
            ),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)
    pipeline._phase_config_fingerprints = lambda: {
        1: {"config.a": "same"},
        2: {"config.a": "new"},
        3: {"config.a": "new"},
        4: {"config.a": "new"},
        5: {"config.a": "new"},
    }

    decision = await pipeline._choose_reuse_source(
        RunManifest(
            run_id="run-new",
            status=RunStatus.RUNNING,
            input_fingerprint="same-input",
            phase_config_fingerprints={
                "phase_1": {"config.a": "same"},
                "phase_2": {"config.a": "new"},
                "phase_3": {"config.a": "new"},
                "phase_4": {"config.a": "new"},
                "phase_5": {"config.a": "new"},
            },
        )
    )

    assert decision.reused_phase_ordinals == [1]
    assert decision.invalidated_phase_ordinals == [2, 3, 4, 5]
