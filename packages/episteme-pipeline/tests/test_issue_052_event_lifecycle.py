"""Unit and integration tests for ISSUE-052: Event Bus Lifecycle Gaps and Audit Completeness.

Covers:
1. Symmetric phase and run lifecycle events on success and failure (ComponentCompleted, PhaseCompleted, PhaseFailed, RunFailed).
2. PhaseReused event emission carrying source_run_id and artifact_count.
3. Guaranteed flush() barrier in use_event_emitter and pipeline observability scope.
4. Observer failure tracking and observer_telemetry persistence in RunReport.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events import (
    ComponentCompleted,
    ComponentStarted,
    CompositeObserver,
    EventObserver,
    PhaseCompleted,
    PhaseFailed,
    PhaseReused,
    RunFailed,
    RunStarted,
    SimpleEventEmitter,
    use_event_emitter,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runs.models import (
    InvalidationDecision,
    ResumePoint,
    RunManifest,
    RunPhaseRecord,
    RunStatus,
)


class RecordingObserver:
    """Observer that records all received events."""

    def __init__(self) -> None:
        self.events: list[Any] = []
        self.flushed: bool = False

    def on_event(self, event: Any) -> None:
        self.events.append(event)

    def flush(self) -> None:
        self.flushed = True


class FaultyObserver:
    """Observer that raises on specific events."""

    def __init__(self, fail_on_type: type | None = None) -> None:
        self.fail_on_type = fail_on_type
        self.events: list[Any] = []
        self.flushed: bool = False

    def on_event(self, event: Any) -> None:
        if self.fail_on_type and isinstance(event, self.fail_on_type):
            raise RuntimeError("Observer disk full or network error")
        self.events.append(event)

    def flush(self) -> None:
        self.flushed = True


class DummyFailingRunner(PhaseRunner):
    """Runner that always raises an exception."""

    phase_key = "phase1"
    name = "Phase 1: Failing Phase"
    checkpoint_store = None

    async def run(
        self, phase_input: Any, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        raise ValueError("Simulated catastrophic phase error")

    def components(self) -> dict[str, Any]:
        return {}


class DummySuccessRunner(PhaseRunner):
    """Runner that succeeds and produces artifacts."""

    phase_key = "phase1"
    name = "Phase 1: Success Phase"
    checkpoint_store = None

    async def run(
        self, phase_input: Any, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        return ArtifactCollection([])

    def components(self) -> dict[str, Any]:
        return {}


# ============================================================================
# Acceptance Criterion 1: Symmetric Failure Events on Phase Exception
# ============================================================================


@pytest.mark.asyncio
async def test_phase_failure_emits_symmetric_failure_events(tmp_path):
    """Verify that when a phase raises, ComponentCompleted(success=False), PhaseCompleted(success=False),
    PhaseFailed, and RunFailed are emitted before the exception propagates."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")
    config.execution.persist_run_manifests = False

    observer = RecordingObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(observer)

    pipeline = Pipeline(
        phases=[DummyFailingRunner()],
        config=config,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
        event_emitter=emitter,
    )

    pipe_input = PipelineInput(source_paths=["/dummy/source.txt"])

    with pytest.raises(ValueError, match="Simulated catastrophic phase error"):
        await pipeline.run(input=pipe_input, run_id="run-fail-test")

    # Verify emitted events
    event_types = [type(e) for e in observer.events]
    assert RunStarted in event_types
    assert ComponentStarted in event_types
    assert ComponentCompleted in event_types
    assert PhaseCompleted in event_types
    assert PhaseFailed in event_types
    assert RunFailed in event_types

    # Verify event properties
    comp_comp = next(e for e in observer.events if isinstance(e, ComponentCompleted))
    assert comp_comp.success is False
    assert "Simulated catastrophic phase error" in (comp_comp.error_message or "")

    phase_comp = next(e for e in observer.events if isinstance(e, PhaseCompleted))
    assert phase_comp.success is False
    assert phase_comp.artifact_count == 0
    assert "Simulated catastrophic phase error" in (phase_comp.error_message or "")

    phase_fail = next(e for e in observer.events if isinstance(e, PhaseFailed))
    assert phase_fail.phase_name == "Phase 1: Failing Phase"
    assert phase_fail.error_type == "ValueError"
    assert "Simulated catastrophic phase error" in phase_fail.error_message
    assert phase_fail.duration_seconds >= 0.0

    run_fail = next(e for e in observer.events if isinstance(e, RunFailed))
    assert run_fail.error_type == "ValueError"
    assert "Simulated catastrophic phase error" in run_fail.error_message
    assert run_fail.duration_seconds >= 0.0

    # Verify flush was called
    assert observer.flushed is True


# ============================================================================
# Acceptance Criterion 2: PhaseReused Events for Hydrated / Reused Phases
# ============================================================================


@pytest.mark.asyncio
async def test_reused_phases_emit_phase_reused_events(tmp_path):
    """Verify that reused phases emit PhaseReused carrying source_run_id and artifact_count."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")
    config.execution.persist_run_manifests = False

    observer = RecordingObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(observer)

    runner1 = DummySuccessRunner()
    pipeline = Pipeline(
        phases=[runner1],
        config=config,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
        event_emitter=emitter,
    )

    manifest = RunManifest(
        run_id="run-new",
        phase_records=[
            RunPhaseRecord(
                phase_name=runner1.name,
                ordinal=1,
                status=RunStatus.PLANNED,
                artifact_ids=[],
            )
        ],
    )

    prior_manifest = RunManifest(
        run_id="run-prior",
        phase_records=[
            RunPhaseRecord(
                phase_name=runner1.name,
                ordinal=1,
                status=RunStatus.COMPLETED,
                artifact_ids=["art-1", "art-2", "art-3"],
            )
        ],
    )
    pipeline._manifest_store.write_manifest(prior_manifest)

    invalidation_decision = InvalidationDecision(
        resume_point=ResumePoint(run_id="run-prior", phase_ordinal=1, phase_name=runner1.name),
        reused_phase_ordinals=[1],
        invalidated_phase_ordinals=[],
        reason="clean-cache-hit",
    )

    # Calling _execute directly with reused phases (start_index = 2, beyond 1)
    result = await pipeline._execute(
        run_id="run-new",
        manifest=manifest,
        start_index=2,
        pipeline_input=PipelineInput(source_paths=["/dummy/source.txt"]),
        initial_previous_collection=None,
        invalidation_decision=invalidation_decision,
    )

    assert result.manifest.status == RunStatus.COMPLETED

    # Check for PhaseReused event
    reused_events = [e for e in observer.events if isinstance(e, PhaseReused)]
    assert len(reused_events) == 1
    reused = reused_events[0]
    assert reused.phase_name == runner1.name
    assert reused.source_run_id == "run-prior"
    assert reused.artifact_count == 3
    assert reused.run_id == "run-new"


# ============================================================================
# Acceptance Criterion 3: Guaranteed flush() Barrier
# ============================================================================


def test_use_event_emitter_flushes_in_finally():
    """Verify use_event_emitter always flushes emitter on exit and exception."""
    mock_emitter = MagicMock(spec=SimpleEventEmitter)

    # Normal exit
    with use_event_emitter(mock_emitter):
        pass
    mock_emitter.flush.assert_called_once()

    # Exception exit
    mock_emitter.reset_mock()
    with pytest.raises(RuntimeError), use_event_emitter(mock_emitter):
        raise RuntimeError("test exception")
    mock_emitter.flush.assert_called_once()


def test_composite_observer_flushes_all_with_isolation():
    """Verify CompositeObserver flushes every child observer with failure isolation."""
    obs1 = RecordingObserver()
    obs2 = MagicMock(spec=EventObserver)
    obs2.flush.side_effect = RuntimeError("Obs2 flush failed")
    obs3 = RecordingObserver()

    composite = CompositeObserver([obs1, obs2, obs3])
    composite.flush()

    assert obs1.flushed is True
    assert obs3.flushed is True


# ============================================================================
# Acceptance Criterion 4: Observer Health & Error Tracking in RunReport
# ============================================================================


@pytest.mark.asyncio
async def test_simple_event_emitter_tracks_observer_errors_in_run_report(tmp_path):
    """Verify SimpleEventEmitter isolates observer failures and surfaces them in RunReport.observer_telemetry."""
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")
    config.execution.persist_run_manifests = False

    faulty = FaultyObserver(fail_on_type=ComponentStarted)
    healthy = RecordingObserver()
    emitter = SimpleEventEmitter()
    emitter.register_observer(faulty)
    emitter.register_observer(healthy)

    pipeline = Pipeline(
        phases=[DummySuccessRunner()],
        config=config,
        graph_reader=MagicMock(),
        projection_graph=MagicMock(),
        checkpoint_store=MagicMock(),
        event_emitter=emitter,
    )

    pipe_input = PipelineInput(source_paths=["/dummy/source.txt"])
    result = await pipeline.run(input=pipe_input, run_id="run-telemetry-test")

    # Verify run completed despite faulty observer
    assert result.manifest.status == RunStatus.COMPLETED

    # Check observer_telemetry
    telemetry = result.report.observer_telemetry
    assert "events_delivered" in telemetry
    assert "observer_errors" in telemetry

    # FaultyObserver should have an error recorded
    errors = telemetry["observer_errors"]
    assert "FaultyObserver" in errors
    assert len(errors["FaultyObserver"]) > 0
    assert "Observer disk full or network error" in errors["FaultyObserver"][0]

    # HealthyObserver should have delivered events
    delivered = telemetry["events_delivered"]
    assert delivered.get("RecordingObserver", 0) > 0


def test_composite_observer_error_telemetry_propagates_to_emitter():
    """Verify CompositeObserver child errors and delivery counts propagate into SimpleEventEmitter telemetry."""
    faulty = FaultyObserver(fail_on_type=ComponentStarted)
    healthy = RecordingObserver()
    composite = CompositeObserver([faulty, healthy])

    emitter = SimpleEventEmitter()
    emitter.register_observer(composite)
    emitter.emit(ComponentStarted(component_name="test_comp", phase="phase1", run_id="run-1"))
    emitter.flush()

    telemetry = emitter.get_observer_telemetry()
    assert "FaultyObserver" in telemetry["observer_errors"]
    assert "Observer disk full or network error" in telemetry["observer_errors"]["FaultyObserver"][0]
    assert telemetry["events_delivered"].get("RecordingObserver", 0) == 1


def test_langfuse_observer_handles_run_lifecycle_events():
    """Verify LangfuseObserver creates spans for RunStarted, RunCompleted, and RunFailed."""
    from episteme_pipeline.events.langfuse_observer import LangfuseObserver
    from episteme_pipeline.events.models import RunCompleted

    mock_client = MagicMock()
    mock_client.get_current_trace_id.return_value = None
    mock_client.get_current_observation_id.return_value = None
    obs = LangfuseObserver(client=mock_client)

    obs.on_event(
        RunStarted(
            run_id="run-lf-1",
            parent_run_id="run-lf-0",
            reused_phase_ordinals=[1],
            invalidated_phase_ordinals=[2],
            invalidation_reason="config-changed:Phase 2",
        )
    )
    obs.on_event(
        RunCompleted(
            run_id="run-lf-1",
            duration_seconds=4.2,
            total_artifacts=12,
        )
    )
    obs.on_event(
        RunFailed(
            run_id="run-lf-1",
            error_type="RuntimeError",
            error_message="boom",
            duration_seconds=1.5,
        )
    )

    span_names = [
        call.kwargs.get("name")
        for call in mock_client.start_observation.call_args_list
    ]
    assert "run.started" in span_names
    assert "run.completed" in span_names
    assert "run.failed" in span_names

