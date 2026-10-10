from pathlib import Path

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline


class StubPhase:
    def __init__(self, name: str):
        self.name = name

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_disables_phase_reuse_and_hydration(tmp_path: Path, graph_store):
    # Initial config allows reuse to create a prior run
    config1 = PipelineConfig()
    config1.execution.runs_dir = str(tmp_path / "runs")
    config1.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline1 = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation"),
            StubPhase("Phase 2: Entity & Local Relation Discovery"),
        ],
        config=config1,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    result1 = await pipeline1.run(PipelineInput(source_paths=["docs/example.md"]))
    assert result1.report.status.value == "completed"

    # Second config disables both reuse and hydration
    config2 = PipelineConfig()
    config2.execution.runs_dir = str(tmp_path / "runs")
    config2.execution.artifacts_dir = str(tmp_path / "artifacts")
    config2.execution.allow_phase_reuse = False
    config2.execution.allow_artifact_hydration = False

    pipeline2 = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation"),
            StubPhase("Phase 2: Entity & Local Relation Discovery"),
        ],
        config=config2,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    result2 = await pipeline2.run(PipelineInput(source_paths=["docs/example.md"]))
    # Expect no reused phases and full invalidation when reuse is disabled
    assert result2.report.reused_phase_ordinals == []
    assert result2.report.invalidated_phase_ordinals == [1, 2]

