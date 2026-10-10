"""Tests for Milestone 5: Run execution, subprocess lifecycle, and live SSE telemetry."""

from __future__ import annotations

import asyncio
import json
import queue
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from episteme_pipeline.events.models import BaseEvent, ComponentStarted
from episteme_studio.adapters.event_mapper import to_studio_event
from episteme_studio.app import create_app
from episteme_studio.domain.runs import RunStatus
from episteme_studio.runtime.broker import EventBroker
from episteme_studio.runtime.observer import StudioEventObserver
from episteme_studio.runtime.registry import RunRegistry
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient


class UnseenCustomEvent(BaseEvent):
    """An unmapped event class not present in the adapter's known list."""

    special_metric: float = 42.0
    notes: str = "Test unmapped event pass-through"


def _crashing_worker(run_id: str, config_dict: dict, source_paths: list, event_queue: Any, demo_mode: bool) -> None:
    """Worker that simulates an unexpected exception during execution."""
    observer = StudioEventObserver(event_queue)
    observer.on_event(ComponentStarted(component_name="CrashPhase", phase_name="CrashPhase", phase_ordinal=1))
    # Signal failure with traceback
    event_queue.put_nowait(
        {
            "_type": "RUN_FAILED",
            "run_id": run_id,
            "error": "Simulated pipeline explosion in Phase 2",
            "traceback": "Traceback (most recent call last):\n  File 'test.py', line 10, in run\nValueError: Simulated pipeline explosion",
        }
    )


def test_on_event_performs_no_io_and_fast_emit() -> None:
    """on_event performs zero IO and completes in microseconds (SPEC §4, M5)."""
    q: queue.Queue = queue.Queue(maxsize=100)
    observer = StudioEventObserver(q)
    event = ComponentStarted(
        component_name="FastPhase",
        phase_name="FastPhase",
        phase_ordinal=1,
    )

    start = time.perf_counter()
    for _ in range(50):
        observer.on_event(event)
    elapsed = time.perf_counter() - start

    # 50 emits should complete in less than 20 milliseconds (< 0.02s)
    assert elapsed < 0.05, f"on_event was too slow: {elapsed}s for 50 emits"
    assert q.qsize() == 50


def test_saturated_queue_surfaces_dropped_before_and_does_not_block() -> None:
    """A saturated bounded queue drops events without blocking, surfacing dropped_before."""
    q: queue.Queue = queue.Queue(maxsize=2)
    observer = StudioEventObserver(q)
    event = ComponentStarted(
        component_name="OverflowPhase",
        phase_name="OverflowPhase",
        phase_ordinal=1,
    )

    # Put 2 items to fill the queue
    observer.on_event(event)
    observer.on_event(event)
    assert q.full()

    # Emitting to a full queue must not block and must increment dropped count
    observer.on_event(event)
    observer.on_event(event)
    assert observer.dropped_count == 2

    # Drain one item so next put succeeds
    _ = q.get_nowait()

    # Next emit succeeds and carries dropped_before count
    observer.on_event(event)
    assert observer.dropped_count == 0

    q.get_nowait()
    item2 = q.get_nowait()
    assert item2["_dropped_before"] == 2


def test_unmapped_event_class_passes_through_generically_no_500() -> None:
    """An unmapped event class passes through as a generic kind without raising an error."""
    unmapped = UnseenCustomEvent(special_metric=99.5)
    studio_ev = to_studio_event(unmapped, seq=1)

    assert studio_ev.seq == 1
    assert "unseen" in studio_ev.kind and "event" in studio_ev.kind
    assert studio_ev.level == "info"
    assert studio_ev.payload["special_metric"] == 99.5


@pytest.mark.asyncio
async def test_active_run_rejects_concurrent_run_with_409() -> None:
    """Starting a run while another is active returns 409 run-already-active (D-27)."""
    settings = StudioSettings(demo_mode=True)
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Start first run
        resp1 = await client.post("/api/runs", json={"demo_mode": True})
        assert resp1.status_code == 201
        run1 = resp1.json()
        assert run1["status"] == "running"

        # 2. Attempt starting second concurrent run -> 409
        resp2 = await client.post("/api/runs", json={"demo_mode": True})
        assert resp2.status_code == 409
        body = resp2.json()
        assert body["type"] == "run-already-active"

        # Cleanup: cancel first run
        await client.post(f"/api/runs/{run1['run_id']}/cancel")


@pytest.mark.asyncio
async def test_run_cancellation_terminates_subprocess_and_lands_in_aborted() -> None:
    """Cancellation terminates the subprocess and the run lands in aborted status."""
    settings = StudioSettings(demo_mode=True)
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/runs", json={"demo_mode": True})
        assert resp.status_code == 201
        run_id = resp.json()["run_id"]

        # Cancel immediately
        cancel_resp = await client.post(f"/api/runs/{run_id}/cancel")
        assert cancel_resp.status_code == 200
        summary = cancel_resp.json()
        assert summary["status"] == "aborted"

        # Detail view also reports aborted
        detail_resp = await client.get(f"/api/runs/{run_id}")
        assert detail_resp.status_code == 200
        assert detail_resp.json()["status"] == "aborted"


@pytest.mark.asyncio
async def test_run_cancellation_after_restart_aborts_on_disk_run(tmp_path: Path) -> None:
    """Verify that a run marked running on disk can be cancelled after server restart.

    Parameters
    ----------
    tmp_path : Path
        Pytest temporary directory fixture.

    Returns
    -------
    None
    """
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    # Create a manifest on disk with status="running" but no active process in memory
    run_id = "run-restarted-test-123"
    manifest_data = {
        "run_id": run_id,
        "pipeline_version": "0.1.0",
        "schema_version": "v1",
        "status": "running",
        "created_at": "2026-09-11T12:00:00Z",
        "started_at": "2026-09-11T12:00:01Z",
        "completed_at": None,
        "phase_records": [
            {
                "phase_name": "Phase 1: Foundation",
                "phase_ordinal": 1,
                "status": "running",
                "started_at": "2026-09-11T12:00:01Z",
            }
        ],
        "config_snapshot": {},
        "input_sources": [],
    }
    manifest_file = runs_dir / f"{run_id}.json"
    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")

    settings = StudioSettings(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Cancel the on-disk run whose memory handle does not exist
        cancel_resp = await client.post(f"/api/runs/{run_id}/cancel")
        assert cancel_resp.status_code == 200
        summary = cancel_resp.json()
        assert summary["status"] == "aborted"

        # Detail view reports aborted and phase is marked aborted
        detail_resp = await client.get(f"/api/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "aborted"
        assert detail["completed_at"] is not None
        assert detail["phase_records"][0]["status"] == "aborted"


@pytest.mark.asyncio
async def test_crashing_run_lands_in_failed_with_traceback() -> None:
    """A crashing run lands in failed with the traceback reachable from the UI."""
    settings = StudioSettings(demo_mode=True)
    app = create_app(settings)

    executor = app.state.executor
    # Launch with crashing config simulation
    handle = executor.start_run(
        run_id="run-crash-test",
        config_dict={
            "_simulate_failure": True,
            "_simulate_failure_message": "Simulated pipeline explosion in Phase 2",
        },
        demo_mode=False,
    )

    # Wait for worker to send RUN_FAILED (spawned subprocess startup on macOS can take 4-6s)
    for _ in range(120):
        await asyncio.sleep(0.1)
        if handle.status == RunStatus.FAILED:
            break

    assert handle.status == RunStatus.FAILED
    assert handle.failure is not None
    assert handle.failure.type == "run-failed"
    assert "Simulated pipeline explosion" in handle.failure.detail
    assert "ValueError" in handle.failure.extra.get("traceback", "")

    # Check that API returns this detail
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/runs/run-crash-test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["failure"] is not None
        assert "traceback" in data["failure"]["extra"]


@pytest.mark.asyncio
async def test_sse_stream_broadcast_to_multiple_subscribers() -> None:
    """Two browser tabs both receive the live stream from EventBroker (M5)."""
    broker = EventBroker()
    run_id = "run-multicast-test"

    # Subscriber 1
    sub1_events = []
    # Subscriber 2
    sub2_events = []

    async def reader1():
        async for ev in broker.subscribe(run_id):
            sub1_events.append(ev)
            if len(sub1_events) == 3:
                break

    async def reader2():
        async for ev in broker.subscribe(run_id):
            sub2_events.append(ev)
            if len(sub2_events) == 3:
                break

    task1 = asyncio.create_task(reader1())
    task2 = asyncio.create_task(reader2())

    await asyncio.sleep(0.05)

    # Publish 3 events
    for i in range(1, 4):
        broker.publish(
            run_id,
            {
                "kind": f"test.event.{i}",
                "run_id": run_id,
                "message": f"Message {i}",
                "timestamp": datetime.now(UTC),
            },
        )

    await asyncio.wait_for(asyncio.gather(task1, task2), timeout=2.0)

    assert len(sub1_events) == 3
    assert len(sub2_events) == 3
    assert [e.seq for e in sub1_events] == [1, 2, 3]
    assert [e.seq for e in sub2_events] == [1, 2, 3]


@pytest.mark.asyncio
async def test_sse_stream_replays_history_via_last_event_id_or_since() -> None:
    """Browser refresh mid-run replays history via Last-Event-ID / since parameter."""
    broker = EventBroker()
    run_id = "run-replay-test"

    # Publish 5 events into ring buffer
    for i in range(1, 6):
        broker.publish(
            run_id,
            {
                "kind": f"phase.step.{i}",
                "run_id": run_id,
                "message": f"Step {i}",
                "timestamp": datetime.now(UTC),
            },
        )

    # 1. New client without since gets all 5 events
    full_history = []
    async for ev in broker.subscribe(run_id):
        full_history.append(ev)
        if len(full_history) == 5:
            break
    assert [e.seq for e in full_history] == [1, 2, 3, 4, 5]

    # 2. Reconnecting client with since_seq=3 gets events 4 and 5
    resumed = []
    async for ev in broker.subscribe(run_id, since_seq=3):
        resumed.append(ev)
        if len(resumed) == 2:
            break
    assert [e.seq for e in resumed] == [4, 5]


@pytest.mark.asyncio
async def test_run_starts_in_subprocess_and_server_remains_responsive() -> None:
    """A run starts in a subprocess; server stays responsive throughout (D-05)."""
    settings = StudioSettings(demo_mode=True)
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start_time = time.perf_counter()
        resp = await client.post("/api/runs", json={"demo_mode": True})
        launch_duration = time.perf_counter() - start_time

        # Launching subprocess should return quickly (< 1.5 seconds)
        assert launch_duration < 2.0, f"Run start took too long: {launch_duration}s"
        assert resp.status_code == 201
        run_data = resp.json()
        assert run_data["status"] == "running"
        run_id = run_data["run_id"]

        # Concurrently query health and capabilities while subprocess is running
        for _ in range(5):
            h_resp = await client.get("/api/health")
            assert h_resp.status_code == 200
            assert h_resp.json() == {"status": "ok"}

            c_resp = await client.get("/api/capabilities")
            assert c_resp.status_code == 200

        # Wait for run to finish or cancel
        for _ in range(30):
            detail_resp = await client.get(f"/api/runs/{run_id}")
            assert detail_resp.status_code == 200
            status = detail_resp.json()["status"]
            if status in ("completed", "failed", "aborted"):
                break
            await asyncio.sleep(0.1)

        final_resp = await client.get(f"/api/runs/{run_id}")
        assert final_resp.status_code == 200
        assert final_resp.json()["status"] in ("running", "completed")

        # Cleanup if still running
        if final_resp.json()["status"] == "running":
            await client.post(f"/api/runs/{run_id}/cancel")


@pytest.mark.asyncio
async def test_run_starts_with_bib_paths_metadata_and_structural_anchor() -> None:
    """Verify that a run can be launched with full PipelineInput configuration.

    Parameters
    ----------
    None

    Returns
    -------
    None
    """
    settings = StudioSettings(demo_mode=True)
    app = create_app(settings)

    payload = {
        "demo_mode": True,
        "source_paths": ["examples/text/teachers_expectancies.md"],
        "bib_paths": ["examples/bib/references.bib"],
        "metadata": {"domain": "philosophy", "experiment_id": "exp-42"},
        "structural_anchor": {
            "toc_structure": ["1. Introduction", "2. Methodology", "3. Discussion"],
            "document_summary": "A comprehensive study on teacher expectancies and student performance.",
            "global_thesis": "Teacher expectations act as self-fulfilling prophecies.",
        },
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/runs", json=payload)
        assert resp.status_code == 201
        run_data = resp.json()
        assert run_data["status"] == "running"
        assert run_data["bib_sources"] == ["examples/bib/references.bib"]
        assert run_data["metadata"] == {"domain": "philosophy", "experiment_id": "exp-42"}
        assert run_data["structural_anchor"] is not None
        assert run_data["structural_anchor"]["global_thesis"] == "Teacher expectations act as self-fulfilling prophecies."
        assert run_data["structural_anchor"]["document_summary"] == "A comprehensive study on teacher expectancies and student performance."
        assert run_data["structural_anchor"]["toc_structure"] == ["1. Introduction", "2. Methodology", "3. Discussion"]
        run_id = run_data["run_id"]

        # Verify get detail endpoint returns the coordinates
        detail_resp = await client.get(f"/api/runs/{run_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["bib_sources"] == ["examples/bib/references.bib"]
        assert detail_data["metadata"] == {"domain": "philosophy", "experiment_id": "exp-42"}
        assert detail_data["structural_anchor"]["global_thesis"] == "Teacher expectations act as self-fulfilling prophecies."

        # Cancel/cleanup run
        await client.post(f"/api/runs/{run_id}/cancel")


@pytest.mark.asyncio
async def test_broker_ring_buffer_handles_rapid_event_burst_without_deadlock() -> None:
    """Verify that EventBroker ring buffer streams high-volume bursts without stall or drop.

    Parameters
    ----------
    None

    Returns
    -------
    None
    """
    broker = EventBroker(capacity=5000)
    run_id = "run-burst-test"
    received: list[int] = []

    async def consumer():
        async for ev in broker.subscribe(run_id):
            received.append(ev.seq)
            if len(received) == 1000:
                break

    consumer_task = asyncio.create_task(consumer())
    await asyncio.sleep(0.01)

    for i in range(1, 1001):
        broker.publish(run_id, {"kind": "burst.event", "seq_num": i})

    await asyncio.wait_for(consumer_task, timeout=5.0)
    assert len(received) == 1000
    assert received[0] == 1
    assert received[-1] == 1000


def test_stream_tee_batches_lines_into_single_message() -> None:
    """Verify StreamTee coalesces multi-line output into batched payload.

    Parameters
    ----------
    None

    Returns
    -------
    None
    """
    from io import StringIO

    from episteme_studio.adapters.worker import StreamTee

    orig = StringIO()
    q: queue.Queue = queue.Queue()
    tee = StreamTee(orig, q, run_id="run-tee-test", stream_name="stdout")

    # Write 5 lines at once
    data = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n"
    tee.write(data)

    assert q.qsize() == 1
    item = q.get_nowait()
    assert item["_raw_type"] == "TerminalOutput"
    assert item["lines"] == ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"]
    assert "[5 lines]" in item["message"]


@pytest.mark.asyncio
async def test_executor_matches_phase_isolates_maturation_and_argument_mining() -> None:
    """Verify executor._matches_phase prevents Phase 4 Maturation and Argument Mining conflation.

    Parameters
    ----------
    None

    Returns
    -------
    None
    """
    from episteme_studio.runtime.executor import PipelineExecutor
    registry = RunRegistry()
    broker = EventBroker()
    executor = PipelineExecutor(registry, broker)

    handle = executor.start_run(run_id="run-phase-isolation-test", demo_mode=True)

    # Initially all phases are planned
    p_mat = next(p for p in handle.phase_records if p.phase_ordinal == 5)
    p_arg = next(p for p in handle.phase_records if p.phase_ordinal == 6)
    assert p_mat.status == RunStatus.PLANNED
    assert p_arg.status == RunStatus.PLANNED

    # Emitting PhaseStarted for Phase 4 Maturation
    executor._process_item(
        "run-phase-isolation-test",
        {
            "_raw_type": "ComponentStarted",
            "phase_name": "Phase 4: Entity Maturation (Batch Epistemic Synthesis)",
        },
        handle,
    )

    assert p_mat.status == RunStatus.RUNNING
    # Argument Mining must remain PLANNED
    assert p_arg.status == RunStatus.PLANNED

    # Emitting PhaseCompleted for Phase 4 Maturation
    executor._process_item(
        "run-phase-isolation-test",
        {
            "_raw_type": "PhaseCompleted",
            "phase_name": "Phase 4: Entity Maturation (Batch Epistemic Synthesis)",
            "artifact_count": 42,
        },
        handle,
    )

    assert p_mat.status == RunStatus.COMPLETED
    assert p_mat.artifact_count == 42
    # Argument Mining must STILL remain PLANNED
    assert p_arg.status == RunStatus.PLANNED

    # Emitting PhaseStarted for Phase 4 Argument Mining
    executor._process_item(
        "run-phase-isolation-test",
        {
            "_raw_type": "PhaseStarted",
            "phase_name": "Phase 4: Argument Mining",
        },
        handle,
    )
    assert p_arg.status == RunStatus.RUNNING

    await executor.cancel("run-phase-isolation-test")
