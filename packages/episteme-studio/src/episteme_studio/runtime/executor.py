"""Subprocess execution manager and IPC bridge for pipeline runs."""

from __future__ import annotations

import asyncio
import multiprocessing
import queue
import uuid
from datetime import datetime, timezone
from typing import Any

from episteme_studio.domain.errors import ProblemDetail
from episteme_studio.domain.runs import PhaseStatus, RunStatus
from episteme_studio.runtime.broker import EventBroker
from episteme_studio.runtime.registry import RunHandle, RunRegistry
from episteme_studio.settings import get_env_var

_DEFAULT_PHASES = [
    ("Phase 1: Data Foundation", 1),
    ("Phase 2: Entity & Local Relation Discovery", 2),
    ("Phase 3: Global Relation Extraction", 3),
    ("Phase 3b: Latent Graph Consolidation", 4),
    ("Phase 4: Entity Maturation (Batch Epistemic Synthesis)", 5),
    ("Phase 4: Argument Mining", 6),
    ("Phase 5: Inter-Document Argument Web", 7),
    ("Phase 6: TheoryNet Projection", 8),
]


class RunAlreadyActiveError(Exception):
    """Raised when an execution start is attempted while another run is active."""

    pass


class PipelineExecutor:
    """Manages subprocess execution lifecycle and IPC communication for pipeline runs.

    Parameters
    ----------
    registry : RunRegistry
        Run handle registry.
    broker : EventBroker
        Telemetry event broker.
    """

    def __init__(self, registry: RunRegistry, broker: EventBroker) -> None:
        self.registry = registry
        self.broker = broker

    def start_run(
        self,
        run_id: str | None = None,
        config_dict: dict[str, Any] | None = None,
        source_paths: list[str] | None = None,
        bib_paths: list[str] | None = None,
        metadata: dict[str, str] | None = None,
        structural_anchor: Any | None = None,
        demo_mode: bool = False,
        worker_target: Any = None,
        parent_run_id: str | None = None,
    ) -> RunHandle:
        """Launch a pipeline execution in a dedicated spawned subprocess.

        Parameters
        ----------
        run_id : str or None, optional
            Explicit run identifier, or generated if None.
        config_dict : dict of str to Any or None, optional
            Serialized PipelineConfig dictionary.
        source_paths : list of str or None, optional
            Input document paths to process.
        bib_paths : list of str or None, optional
            Optional file paths to bibliography references (.bib).
        metadata : dict of str to str or None, optional
            Arbitrary execution metadata strings.
        structural_anchor : GlobalStructuralAnchor or dict or None, optional
            Global structural anchor coordinate system.
        demo_mode : bool, default False
            Whether to run in demo simulation mode.
        worker_target : Callable or None, optional
            Custom worker target function override (primarily for test scenarios).
        parent_run_id : str or None, optional
            Parent run identifier to resume or reuse from.

        Returns
        -------
        RunHandle
            Registered handle for the new run.

        Raises
        ------
        RunAlreadyActiveError
            If another run is currently queued or executing (D-27).
        """
        if self.registry.is_any_active():
            raise RunAlreadyActiveError("A pipeline run is already active")

        target_run_id = (
            run_id
            or get_env_var("LANGFUSE_SESSION_ID")
            or f"run-{uuid.uuid4()}"
        )

        initial_phases = [
            PhaseStatus(
                phase_name=name,
                phase_ordinal=ordinal,
                status=RunStatus.PLANNED,
            )
            for name, ordinal in _DEFAULT_PHASES
        ]

        models_info = {}
        if config_dict and "models" in config_dict and isinstance(config_dict["models"], dict):
            models_info = {k: str(v) for k, v in config_dict["models"].items() if v}

        handle = RunHandle(
            run_id=target_run_id,
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            phase_records=initial_phases,
            config_snapshot=config_dict or {},
            input_sources=source_paths or [],
            bib_sources=bib_paths or [],
            metadata=metadata or {},
            structural_anchor=structural_anchor,
            models=models_info,
            parent_run_id=parent_run_id,
        )
        self.registry.register(handle)

        # Set up IPC queue using spawn context (D-05)
        ctx = multiprocessing.get_context("spawn")
        ipc_queue = ctx.Queue()

        if worker_target:
            target_fn = worker_target
        else:
            from episteme_studio.adapters.worker import run_pipeline_worker
            target_fn = run_pipeline_worker

        anchor_dict = (
            structural_anchor.model_dump(mode="python")
            if hasattr(structural_anchor, "model_dump")
            else structural_anchor
        )

        args = (
            target_run_id,
            config_dict or {},
            source_paths or [],
            ipc_queue,
            demo_mode,
            bib_paths or [],
            metadata or {},
            anchor_dict,
            parent_run_id,
        )

        process = ctx.Process(target=target_fn, args=args, daemon=True)
        process.start()
        handle.process = process

        try:
            pid_dir = Path(".pipeline_runs") / target_run_id
            pid_dir.mkdir(parents=True, exist_ok=True)
            (pid_dir / "process.pid").write_text(str(process.pid), encoding="utf-8")
        except Exception:
            pass

        # Start non-blocking background queue reader
        task = asyncio.create_task(self._drain_queue(target_run_id, ipc_queue, handle, process))
        handle.task = task

        return handle

    async def cancel(self, run_id: str) -> RunHandle:
        """Cancel an in-flight run by terminating its subprocess.

        Parameters
        ----------
        run_id : str
            Identifier of the run to cancel.

        Returns
        -------
        RunHandle
            Updated handle in aborted status.

        Raises
        ------
        KeyError
            If the run ID is not found.
        """
        handle = self.registry.get(run_id)
        if not handle:
            raise KeyError(f"Run '{run_id}' not found")

        if handle.status in (RunStatus.PLANNED, RunStatus.RUNNING):
            if handle.process and handle.process.is_alive():
                handle.process.terminate()
                try:
                    await asyncio.to_thread(handle.process.join, 1.0)
                except Exception:
                    pass
                if handle.process.is_alive():
                    handle.process.kill()

            if handle.task and not handle.task.done():
                handle.task.cancel()

            try:
                (Path(".pipeline_runs") / run_id / "process.pid").unlink(missing_ok=True)
            except Exception:
                pass

            handle.status = RunStatus.ABORTED
            handle.completed_at = datetime.now(timezone.utc)

            # Mark any remaining running phase as aborted
            for p in handle.phase_records:
                if p.status == RunStatus.RUNNING:
                    p.status = RunStatus.ABORTED
                    p.completed_at = handle.completed_at

            self.broker.publish(
                run_id,
                {
                    "_raw_type": "RunAborted",
                    "kind": "run.aborted",
                    "run_id": run_id,
                    "level": "warning",
                    "message": f"Run '{run_id}' was cancelled by user.",
                    "timestamp": handle.completed_at,
                },
            )
            self.broker.close_run(run_id)

        return handle

    async def _drain_queue(
        self,
        run_id: str,
        ipc_queue: Any,
        handle: RunHandle,
        process: multiprocessing.Process,
    ) -> None:
        """Asynchronously drain IPC messages from the child process without blocking uvicorn.

        Parameters
        ----------
        run_id : str
            Run identifier.
        ipc_queue : Any
            Multiprocessing queue.
        handle : RunHandle
            Active run handle.
        process : multiprocessing.Process
            Spawned child process.
        """
        try:
            while True:
                # Read from queue with a short timeout using asyncio.to_thread to avoid blocking event loop
                try:
                    item = await asyncio.to_thread(ipc_queue.get, True, 0.2)
                except queue.Empty:
                    if not process.is_alive():
                        try:
                            await asyncio.to_thread(process.join, 1.0)
                        except Exception:
                            pass
                        # Subprocess terminated; drain any remaining items
                        while True:
                            try:
                                item = ipc_queue.get_nowait()
                                terminal = self._process_item(run_id, item, handle)
                                if terminal:
                                    break
                            except queue.Empty:
                                break
                        break
                    continue

                terminal = self._process_item(run_id, item, handle)
                if terminal:
                    break

            # Handle process exit if still marked running
            if handle.status == RunStatus.RUNNING:
                try:
                    await asyncio.to_thread(process.join, 0.5)
                except Exception:
                    pass
                if process.exitcode != 0:
                    handle.status = RunStatus.FAILED
                    handle.completed_at = datetime.now(timezone.utc)
                    handle.failure = ProblemDetail(
                        type="run-crashed",
                        title="Run Subprocess Crashed",
                        status=500,
                        detail=f"Subprocess terminated unexpectedly with exit code {process.exitcode}",
                        extra={"exitcode": process.exitcode},
                    )
                else:
                    handle.status = RunStatus.COMPLETED
                    handle.completed_at = datetime.now(timezone.utc)
                self.broker.close_run(run_id)
        except asyncio.CancelledError:
            pass
        except Exception as err:
            if handle.status == RunStatus.RUNNING:
                handle.status = RunStatus.FAILED
                handle.completed_at = datetime.now(timezone.utc)
                handle.failure = ProblemDetail(
                    type="internal-error",
                    title="Telemetry Reader Error",
                    status=500,
                    detail=str(err),
                )
            self.broker.close_run(run_id)

    def _process_item(self, run_id: str, item: Any, handle: RunHandle) -> bool:
        """Process an individual item received over IPC.

        Returns
        -------
        bool
            True if this was a terminal item ending the run, False otherwise.
        """
        if not isinstance(item, dict):
            return False

        msg_type = item.get("_type")
        if msg_type == "RUN_COMPLETED":
            handle.status = RunStatus.COMPLETED
            handle.completed_at = datetime.now(timezone.utc)
            for p in handle.phase_records:
                if p.status == RunStatus.RUNNING:
                    p.status = RunStatus.COMPLETED
                    p.completed_at = handle.completed_at
            self.broker.close_run(run_id)
            return True

        if msg_type == "RUN_FAILED":
            handle.status = RunStatus.FAILED
            handle.completed_at = datetime.now(timezone.utc)
            for p in handle.phase_records:
                if p.status == RunStatus.RUNNING:
                    p.status = RunStatus.FAILED
                    p.completed_at = handle.completed_at
            handle.failure = ProblemDetail(
                type="run-failed",
                title="Run Execution Failed",
                status=500,
                detail=item.get("error", "Unknown error"),
                extra={"traceback": item.get("traceback", "")},
            )
            self.broker.publish(
                run_id,
                {
                    "_raw_type": "RunFailed",
                    "kind": "run.failed",
                    "run_id": run_id,
                    "level": "error",
                    "message": f"Run failed: {item.get('error')}",
                    "payload": {"traceback": item.get("traceback")},
                    "timestamp": handle.completed_at,
                },
            )
            self.broker.close_run(run_id)
            return True

        # Update phase records and live counts from domain event
        raw_type = item.get("_raw_type", "")
        phase_name = (
            item.get("phase_name")
            or item.get("phase")
            or item.get("component_name")
        )
        phase_ordinal = item.get("phase_ordinal")

        def _matches_phase(p: PhaseStatus, target_name: str | None, target_ordinal: int | None) -> bool:
            if target_ordinal is not None and p.phase_ordinal == target_ordinal:
                return True
            if not target_name:
                return False
            pn_clean = p.phase_name.strip().lower()
            t_clean = str(target_name).strip().lower()
            if pn_clean == t_clean:
                return True
            # Guard against cross-matching distinct phases that share prefix numbers
            if ("maturation" in t_clean and "argument" in pn_clean) or ("argument" in t_clean and "maturation" in pn_clean):
                return False
            if ("3b" in t_clean and "3b" not in pn_clean) or ("3b" in pn_clean and "3b" not in t_clean):
                return False
            if t_clean in ("phase 1", "phase 2", "phase 3", "phase 4", "phase 5", "phase 6", "phase 7"):
                return False
            return t_clean in pn_clean or pn_clean in t_clean

        if phase_name or phase_ordinal:
            if raw_type in ("ComponentStarted", "PhaseStarted"):
                for p in handle.phase_records:
                    if _matches_phase(p, phase_name, phase_ordinal):
                        p.status = RunStatus.RUNNING
                        p.started_at = p.started_at or datetime.now(timezone.utc)
                    elif p.status == RunStatus.RUNNING:
                        # Auto-complete preceding running phase
                        p.status = RunStatus.COMPLETED
                        p.completed_at = p.completed_at or datetime.now(timezone.utc)
            elif raw_type in ("PhaseCompleted", "ComponentCompleted"):
                for p in handle.phase_records:
                    if _matches_phase(p, phase_name, phase_ordinal):
                        p.status = RunStatus.COMPLETED
                        p.completed_at = datetime.now(timezone.utc)
                        art_count = item.get("artifact_count")
                        if art_count is not None:
                            p.artifact_count = art_count
                        dur = item.get("duration_seconds")
                        if dur is not None:
                            p.duration_seconds = dur

        # Increment in-memory live artifact counts from fine-grained domain events
        if raw_type == "ChunksGenerated":
            cnt = item.get("chunk_count") or (len(item.get("chunks", [])) if isinstance(item.get("chunks"), list) else 1)
            handle.artifact_counts_by_kind["chunk"] = handle.artifact_counts_by_kind.get("chunk", 0) + cnt
        elif raw_type == "EntityProcessed":
            handle.artifact_counts_by_kind["entity"] = handle.artifact_counts_by_kind.get("entity", 0) + 1
        elif raw_type == "TripleCommitted":
            handle.artifact_counts_by_kind["local_relation"] = handle.artifact_counts_by_kind.get("local_relation", 0) + 1
        elif raw_type == "FusionDecisionMade":
            handle.artifact_counts_by_kind["fusion_decision"] = handle.artifact_counts_by_kind.get("fusion_decision", 0) + 1

        # Broadcast via broker
        self.broker.publish(run_id, item)
        return False
