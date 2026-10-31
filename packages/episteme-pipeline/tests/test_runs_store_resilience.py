from __future__ import annotations

import os
from pathlib import Path

import pytest
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.persistence import JsonRunManifestStore


class _Noop:
    name = "Phase X: Noop"
    phase_key = "phase_noop"
    async def run(self, input, context):
        from episteme_pipeline.artifacts.execution import ArtifactCollection
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_manifest_writer_recreates_directory_if_deleted(tmp_path: Path, graph_store):
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(phases=[_Noop()], config=cfg, graph_reader=graph_store, projection_graph=graph_store, checkpoint_store=graph_store)

    # Simulate external deletion of the runs directory mid-execution
    runs_dir = Path(cfg.execution.runs_dir)
    assert runs_dir.exists()
    os.rmdir(runs_dir)
    assert not runs_dir.exists()

    result = await pipeline.run(PipelineInput(source_paths=[]))

    # Writer must recreate and persist
    store = JsonRunManifestStore(cfg.execution.runs_dir)
    manifest = store.read_manifest(result.manifest.run_id)
    assert manifest is not None


@pytest.mark.asyncio
async def test_manifest_writer_supports_custom_runs_dir_name(tmp_path: Path, graph_store):
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / ".custom_runs_dir")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(phases=[_Noop()], config=cfg, graph_reader=graph_store, projection_graph=graph_store, checkpoint_store=graph_store)
    result = await pipeline.run(PipelineInput(source_paths=[]))

    store = JsonRunManifestStore(cfg.execution.runs_dir)
    assert store.read_manifest(result.manifest.run_id) is not None

