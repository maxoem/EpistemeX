"""Tests for pipeline behavior when completing with no entities processed."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from episteme_pipeline import Pipeline
from episteme_pipeline.artifacts.execution import ArtifactCollection, ArtifactExecutionContext
from episteme_pipeline.config import PipelineConfig, ExecutionConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.runs.models import RunStatus


class MockPhaseRunner:
    """Mock phase runner that simulates processing with no results."""
    
    def __init__(self, phase_num: int, name: str):
        self.phase_num = phase_num
        self.name = name
        self.config = MagicMock()
        
    async def validate(self, input: PipelineInput) -> tuple[bool, str]:
        return True, ""
        
    async def run(self, input: PipelineInput, context: ArtifactExecutionContext) -> ArtifactCollection:
        # Return an empty artifact collection to simulate no entities found
        return ArtifactCollection(artifacts=[])


@pytest.mark.asyncio
async def test_pipeline_completes_with_no_entities() -> None:
    """Test that pipeline completes successfully and writes manifest even when no entities are processed."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set up temporary directories
        runs_dir = Path(temp_dir) / ".pipeline_runs"
        artifacts_dir = Path(temp_dir) / ".pipeline_artifacts"
        
        # Create config with temporary directories
        config = PipelineConfig(
            execution=ExecutionConfig(
                runs_dir=str(runs_dir),
                artifacts_dir=str(artifacts_dir),
                project_artifacts_to_graph=False,
                allow_phase_reuse=False,
                allow_artifact_hydration=False,
            )
        )
        
        # Create mock phase runners that simulate no entities found
        mock_phases = [
            MockPhaseRunner(1, "Phase 1: Data Foundation"),
            MockPhaseRunner(2, "Phase 2: Entity Discovery"),
            MockPhaseRunner(3, "Phase 3: Global Relations")
        ]
        
        # Create pipeline with mocks for graph stores
        mock_graph_reader = AsyncMock()
        mock_projection_graph = AsyncMock()
        mock_checkpoint_store = AsyncMock()
        
        pipeline = Pipeline(
            phases=mock_phases,
            config=config,
            graph_reader=mock_graph_reader,
            projection_graph=mock_projection_graph,
            checkpoint_store=mock_checkpoint_store,
        )
        
        # Test input
        input_data = PipelineInput(source_paths=["fake_source.txt"])
        
        # Execute pipeline with default generated run_id
        result = await pipeline.run(input_data)
        
        # Assertions
        assert result.manifest is not None
        assert result.report is not None
        assert result.manifest.status == RunStatus.COMPLETED
        assert result.report.status == RunStatus.COMPLETED
        assert result.manifest.run_id.startswith("run-")
        
        # Verify manifest file was created
        manifest_file = runs_dir / f"{result.manifest.run_id}.json"
        assert manifest_file.exists(), f"Manifest file should exist at {manifest_file}"
        
        # Verify we can read it back
        read_manifest = pipeline._manifest_store.read_manifest(result.manifest.run_id)
        assert read_manifest is not None
        assert read_manifest.run_id == result.manifest.run_id


@pytest.mark.asyncio
async def test_pipeline_accepts_explicit_run_id() -> None:
    """Verify that pipeline.run and run_from_phase accept and preserve an explicit run_id.

    Parameters
    ----------
    None

    Returns
    -------
    None
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        runs_dir = Path(temp_dir) / ".pipeline_runs"
        artifacts_dir = Path(temp_dir) / ".pipeline_artifacts"

        config = PipelineConfig(
            execution=ExecutionConfig(
                runs_dir=str(runs_dir),
                artifacts_dir=str(artifacts_dir),
                project_artifacts_to_graph=False,
                allow_phase_reuse=False,
                allow_artifact_hydration=False,
            )
        )

        mock_phases = [
            MockPhaseRunner(1, "Phase 1: Data Foundation"),
            MockPhaseRunner(2, "Phase 2: Entity Discovery"),
        ]

        pipeline = Pipeline(
            phases=mock_phases,
            config=config,
            graph_reader=AsyncMock(),
            projection_graph=AsyncMock(),
            checkpoint_store=AsyncMock(),
        )

        input_data = PipelineInput(source_paths=["source.txt"])
        custom_run_id = "unified-orchestrator-trace-12345"

        result = await pipeline.run(input_data, run_id=custom_run_id)
        assert result.manifest.run_id == custom_run_id
        assert (runs_dir / f"{custom_run_id}.json").exists()

        custom_phase_run_id = "phase-resume-trace-67890"
        phase_result = await pipeline.run_from_phase(1, input_data, run_id=custom_phase_run_id)
        assert phase_result.manifest.run_id == custom_phase_run_id
        assert (runs_dir / f"{custom_phase_run_id}.json").exists()


