"""Integration tests for fine-grained nested config fingerprint diffs."""

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus


class StubPhase:
    def __init__(self, name: str, a: int = 1, b: str = "hello", phase_key: str | None = None) -> None:
        self.name = name
        self.phase_key = phase_key or name.lower().split(":")[0].replace(" ", "")
        self.a = a
        self.b = b

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_fine_grained_nested_config_detects_leaf_change(tmp_path, graph_store):
    """Changing only one leaf (e.g. 'a') should invalidate the phase
    based on set-difference of leaf fingerprints."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation", a=10, b="same"),
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
        # New nested format with per-leaf fingerprints
        phase_config_fingerprints={"phase1": {"a": "fp_for_10", "b": "fp_for_same"}},
        phase_records=[
            RunPhaseRecord(
                phase_name="Phase 1: Data Foundation",
                ordinal=1,
                status=RunStatus.COMPLETED,
            ),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)
    pipeline._artifact_store = JsonArtifactStore(tmp_path / "artifacts")

    async def mock_compute_stale_phases(_prior_run_id: str):
        return {}

    pipeline._compute_stale_phases = mock_compute_stale_phases
    pipeline._phase_config_fingerprints = lambda: {
        "phase1": {"a": "fp_for_20", "b": "fp_for_same"}
    }
    pipeline._method_fingerprints = dict

    decision = await pipeline._choose_reuse_source(
        RunManifest(
            run_id="run-new",
            status=RunStatus.RUNNING,
            input_fingerprint="same-input",
            phase_config_fingerprints={
                "phase1": {"a": "fp_for_20", "b": "fp_for_same"},
            },
        )
    )

    # Even though 'b' matches, 'a' changed so phase is invalidated
    assert decision.invalidated_phase_ordinals == [1]
    assert decision.reused_phase_ordinals == []


@pytest.mark.asyncio
async def test_fine_grained_nested_config_all_leaves_match(tmp_path, graph_store):
    """When ALL leaf fingerprints match, phase is reused."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation", a=10, b="same"),
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
        phase_config_fingerprints={"phase1": {"a": "fp_for_10", "b": "fp_for_same"}},
        phase_records=[
            RunPhaseRecord(
                phase_name="Phase 1: Data Foundation",
                ordinal=1,
                status=RunStatus.COMPLETED,
            ),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)
    pipeline._artifact_store = JsonArtifactStore(tmp_path / "artifacts")

    async def mock_compute_stale_phases(_prior_run_id: str):
        return {}

    pipeline._compute_stale_phases = mock_compute_stale_phases
    pipeline._phase_config_fingerprints = lambda: {
        "phase1": {"a": "fp_for_10", "b": "fp_for_same"}
    }
    pipeline._method_fingerprints = dict

    decision = await pipeline._choose_reuse_source(
        RunManifest(
            run_id="run-new",
            status=RunStatus.RUNNING,
            input_fingerprint="same-input",
            phase_config_fingerprints={
                "phase1": {"a": "fp_for_10", "b": "fp_for_same"},
            },
        )
    )

    assert decision.reused_phase_ordinals == [1]
    assert decision.invalidated_phase_ordinals == []
