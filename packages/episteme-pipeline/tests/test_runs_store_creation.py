from __future__ import annotations

from pathlib import Path

import pytest

from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.phases.phase1_foundation import Phase1Runner
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import RunStatus
from episteme_pipeline.runs.persistence import JsonRunManifestStore


class _NoopPhase:
    name = "Phase X: Noop"

    async def run(self, input, context):
        # Pass artifacts-through without writes
        return input


@pytest.mark.asyncio
async def test_pipeline_init_creates_runs_and_artifacts_dirs(tmp_path: Path, graph_store):
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    # Initialize with no phases — should create both dirs eagerly
    Pipeline(phases=[], config=cfg, graph_reader=graph_store, projection_graph=graph_store, checkpoint_store=graph_store)

    assert (tmp_path / "runs").exists()
    assert (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
async def test_run_persists_manifest_even_with_no_phases(tmp_path: Path, graph_store):
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(phases=[], config=cfg, graph_reader=graph_store, projection_graph=graph_store, checkpoint_store=graph_store)
    result = await pipeline.run(PipelineInput(source_paths=[]))

    # Manifest written and status completed
    store = JsonRunManifestStore(cfg.execution.runs_dir)
    manifests = store.list_manifests()
    assert any(m.run_id == result.manifest.run_id for m in manifests)
    m = next(m for m in manifests if m.run_id == result.manifest.run_id)
    assert m.status == RunStatus.COMPLETED


@pytest.mark.asyncio
async def test_run_persists_manifest_when_phase2_has_nothing_to_do(tmp_path: Path, graph_store, schema):
    cfg = PipelineConfig()
    cfg.execution.runs_dir = str(tmp_path / "runs")
    cfg.execution.artifacts_dir = str(tmp_path / "artifacts")

    # Build Phase 1 + Phase 2 with no input paths so Phase 1 produces no chunks
    phases = [
        Phase1Runner(cfg.phase1, llm=None, embedding_model=None, graph_store=graph_store),
        Phase2Runner(cfg.phase2, schema, llm=None, embedding_model=None, graph_store=graph_store),
    ]
    pipeline = Pipeline(phases=phases, config=cfg, graph_reader=graph_store, projection_graph=graph_store, checkpoint_store=graph_store)

    result = await pipeline.run(PipelineInput(source_paths=[]))

    # Manifest directory exists and manifest written even though phases produced no artifacts
    runs_dir = Path(cfg.execution.runs_dir)
    assert runs_dir.exists()
    files = list(runs_dir.glob("*.json"))
    assert any(f.name.startswith(result.manifest.run_id) for f in files)

    # get_run_report must succeed
    report = await pipeline.get_run_report(result.manifest.run_id)
    assert report.run_id == result.manifest.run_id
    assert report.status == RunStatus.COMPLETED
