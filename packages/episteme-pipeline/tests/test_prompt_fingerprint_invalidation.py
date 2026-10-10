"""Tests for prompt version changes tracked in method fingerprints."""

import pytest

from episteme_pipeline.artifacts.execution import ArtifactCollection, ArtifactExecutionContext
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import RunManifest, RunPhaseRecord, RunStatus


@pytest.mark.asyncio
async def test_prompt_fingerprints_includes_all_prompts(tmp_path, graph_store):
    """_prompt_fingerprints returns prompts grouped by phase."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    fps = pipeline._prompt_fingerprints()

    # Should have entries for all active phase keys
    assert "phase2" in fps
    assert "phase3" in fps
    assert "phase4_maturation" in fps
    assert "phase4" in fps

    assert "ner_extraction" in fps["phase2"]
    assert "entity_linking" in fps["phase2"]
    assert "global_relation" in fps["phase3"]
    assert "entity_synthesis" in fps["phase4_maturation"]
    assert "adu_segmentation" in fps["phase4"]
    assert "acc_classification" in fps["phase4"]
    assert "arc_classification" in fps["phase4"]


@pytest.mark.asyncio
async def test_prompt_fingerprints_are_deterministic(tmp_path, graph_store):
    """Re-running _prompt_fingerprints returns identical values."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    fps1 = pipeline._prompt_fingerprints()
    assert len(fps1) == 4

    fps2 = pipeline._prompt_fingerprints()
    assert fps1 == fps2


@pytest.mark.asyncio
async def test_prompt_fingerprints_differ_when_template_changes(tmp_path, graph_store):
    """Changing a single prompt template changes its fingerprint."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline1 = Pipeline(
        phases=[],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )
    fps1 = pipeline1._prompt_fingerprints()

    # Create a config with a modified prompt
    config2 = PipelineConfig()
    config2.execution.runs_dir = str(tmp_path / "runs")
    config2.execution.artifacts_dir = str(tmp_path / "artifacts")
    config2.phase2.ner_prompts.direct_template = "CUSTOM NER PROMPT v2"

    pipeline2 = Pipeline(
        phases=[],
        config=config2,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )
    fps2 = pipeline2._prompt_fingerprints()

    # ner_extraction should differ
    assert fps1["phase2"]["ner_extraction"] != fps2["phase2"]["ner_extraction"]
    # Other prompts should match
    assert fps1["phase3"]["global_relation"] == fps2["phase3"]["global_relation"]
    assert fps1["phase4"]["acc_classification"] == fps2["phase4"]["acc_classification"]


@pytest.mark.asyncio
async def test_prompt_in_method_fingerprints(tmp_path, graph_store):
    """Prompt fingerprints are included in method fingerprints under phase keys."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    class StubPhase:
        name = "Phase 2: Entity & Local Relation Discovery"
        phase_key = "phase2"

        async def run(self, input, context: ArtifactExecutionContext):
            return ArtifactCollection([])

    pipeline = Pipeline(
        phases=[StubPhase()],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    method_fps = pipeline._method_fingerprints()
    prompt_fps = pipeline._prompt_fingerprints()

    # Should have prompt fingerprints under the phase key
    phase_prefix = f"{StubPhase.name}.prompt."
    prompt_keys = [k for k in method_fps if k.startswith(phase_prefix)]
    assert len(prompt_keys) == 2  # ner_extraction and entity_linking for phase2

    for key in prompt_keys:
        actual_fp = method_fps[key]
        prompt_name = key.replace(phase_prefix, "")
        expected_fp = prompt_fps["phase2"].get(prompt_name)
        assert actual_fp == expected_fp


@pytest.mark.asyncio
async def test_method_fingerprint_invalidates_on_prompt_change(tmp_path, graph_store):
    """Changing a prompt template invalidates the phase via method fingerprint mismatch."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    class StubPhase:
        name = "Phase 2: Entity & Local Relation Discovery"
        phase_key = "phase2"

        async def run(self, input, context: ArtifactExecutionContext):
            return ArtifactCollection([])

    # Build manifest with default prompts
    pipeline = Pipeline(
        phases=[StubPhase()],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    default_fps = pipeline._prompt_fingerprints()

    prior = RunManifest(
        run_id="run-old",
        status=RunStatus.COMPLETED,
        input_fingerprint="same-input",
        method_fingerprints={
            f"{StubPhase.name}.llm": "llm-fp",
            f"{StubPhase.name}.prompt.ner_extraction": default_fps["phase2"]["ner_extraction"],
        },
        phase_config_fingerprints={"phase_1": default_fps},
        phase_records=[
            RunPhaseRecord(
                phase_name=StubPhase.name,
                ordinal=1,
                status=RunStatus.COMPLETED,
            ),
        ],
    )
    pipeline._manifest_store.write_manifest(prior)
    pipeline._artifact_store = JsonArtifactStore(tmp_path / "artifacts")

    async def mock_stale(_prior_run_id: str):
        return {}

    pipeline._compute_stale_phases = mock_stale
    pipeline._phase_config_fingerprints = lambda: {1: default_fps}

    # Now simulate changed prompt in current run
    changed_ner_fp = "changed_ner_extraction_fingerprint"

    def changed_method_fps():
        return {
            f"{StubPhase.name}.llm": "llm-fp",
            f"{StubPhase.name}.prompt.ner_extraction": changed_ner_fp,
        }

    pipeline._method_fingerprints = changed_method_fps

    decision = await pipeline._choose_reuse_source(
        RunManifest(
            run_id="run-new",
            status=RunStatus.RUNNING,
            input_fingerprint="same-input",
            method_fingerprints={
                f"{StubPhase.name}.llm": "llm-fp",
                f"{StubPhase.name}.prompt.ner_extraction": changed_ner_fp,
            },
            phase_config_fingerprints={"phase_1": default_fps},
        )
    )

    assert decision.invalidated_phase_ordinals == [1]
    assert decision.reused_phase_ordinals == []
