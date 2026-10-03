"""Service layer orchestrating run discovery, inspection, execution, and cancellation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from episteme_studio.adapters.artifact_reader import ArtifactReader, ArtifactStoreError
from episteme_studio.api.errors import StudioProblemException
from episteme_studio.domain.runs import (
    RunDetail,
    RunStatus,
    RunSummary,
    StartRunRequest,
)
from episteme_studio.runtime.executor import PipelineExecutor, RunAlreadyActiveError
from episteme_studio.runtime.registry import RunRegistry

if TYPE_CHECKING:
    from episteme_studio.settings import StudioSettings


class RunService:
    """Orchestrates run queries, manifest extraction, execution, and cancellation.

    Parameters
    ----------
    reader : ArtifactReader
        Underlying filesystem artifact reader.
    registry : RunRegistry or None, optional
        In-memory execution handle registry.
    executor : PipelineExecutor or None, optional
        Subprocess execution manager.
    """

    def __init__(
        self,
        reader: ArtifactReader,
        registry: RunRegistry | None = None,
        executor: PipelineExecutor | None = None,
        config_service: Any = None,
        settings: StudioSettings | None = None,
    ) -> None:
        from episteme_studio.services.config_service import ConfigService

        self.reader = reader
        self.registry = registry
        self.executor = executor
        self.config_service = config_service or ConfigService()
        self.settings = settings

    @classmethod
    def from_settings(
        cls,
        settings: StudioSettings,
        registry: RunRegistry | None = None,
        executor: PipelineExecutor | None = None,
        config_service: Any = None,
    ) -> RunService:
        """Instantiate RunService from configuration settings.

        Parameters
        ----------
        settings : StudioSettings
            Application configuration settings.
        registry : RunRegistry or None, optional
            In-memory run registry.
        executor : PipelineExecutor or None, optional
            Subprocess executor.
        config_service : ConfigService or None, optional
            Configuration service for resolving staged patches.

        Returns
        -------
        RunService
            Configured service instance.
        """
        reader = ArtifactReader(
            runs_dir=settings.runs_dir,
            artifacts_dir=settings.artifacts_dir,
            langfuse_host=settings.langfuse_host,
            extra_runs_dirs=settings.extra_runs_dirs,
            extra_artifacts_dirs=settings.extra_artifacts_dirs,
        )
        return cls(
            reader,
            registry=registry,
            executor=executor,
            config_service=config_service,
            settings=settings,
        )

    def list_runs(self) -> list[RunSummary]:
        """List all available pipeline runs, combining disk manifests and active runs.

        Returns
        -------
        list of RunSummary
            Summaries of all discovered runs.
        """
        disk_runs = self.reader.list_runs()
        if not self.registry:
            return disk_runs

        active_handles = self.registry.list_all()
        disk_map = {r.run_id: r for r in disk_runs}

        # In-memory handles take precedence for active or recently completed runs
        for handle in active_handles:
            if (
                handle.status == RunStatus.RUNNING
                and handle.process
                and not handle.process.is_alive()
            ):
                handle.status = RunStatus.FAILED
                handle.completed_at = datetime.now(timezone.utc)
            summary = handle.to_summary()
            disk_map[handle.run_id] = summary

        # Sort descending by created_at
        return sorted(disk_map.values(), key=lambda r: r.created_at, reverse=True)

    def _enrich_handle_detail(self, handle: Any) -> RunDetail:
        """Enrich in-memory handle detail with on-disk artifact counts and size.

        Parameters
        ----------
        handle : RunHandle
            The in-memory execution handle.

        Returns
        -------
        RunDetail
            Enriched run detail with live yields and artifact rollups.
        """
        detail = handle.to_detail()
        run_id = handle.run_id
        # Scan on-disk artifacts for live yields
        disk_counts = self.reader._count_artifacts_by_kind(run_id)
        merged_counts = dict(detail.artifact_counts_by_kind)
        for k, v in disk_counts.items():
            merged_counts[k] = max(merged_counts.get(k, 0), v)
        detail.artifact_counts_by_kind = merged_counts
        total_arts = sum(merged_counts.values())
        if total_arts > 0:
            detail.artifact_count = max(detail.artifact_count, total_arts)
        detail.size_bytes = max(
            detail.size_bytes, self.reader._calculate_run_size_bytes(run_id)
        )

        # If on-disk intermediate manifest exists, sync phase records from it
        try:
            disk_run = self.reader.get_run(run_id)
            if disk_run and disk_run.phase_records:
                disk_phases_by_ord = {
                    p.phase_ordinal: p for p in disk_run.phase_records
                }
                for i, p in enumerate(detail.phase_records):
                    dp = disk_phases_by_ord.get(p.phase_ordinal)
                    if dp and dp.status in (RunStatus.COMPLETED, RunStatus.FAILED):
                        detail.phase_records[i] = dp
        except Exception:
            pass

        return detail

    def get_run(self, run_id: str) -> RunDetail:
        """Retrieve full details for a specific run from memory or disk.

        Parameters
        ----------
        run_id : str
            Identifier of run to retrieve.

        Returns
        -------
        RunDetail
            Detailed run information.

        Raises
        ------
        StudioProblemException
            If run is not found or manifest is corrupted.
        """
        # 1. Check in-memory registry first for active/failed runs
        if self.registry:
            handle = self.registry.get(run_id)
            if handle and (
                handle.status
                in (RunStatus.PLANNED, RunStatus.RUNNING, RunStatus.ABORTED)
                or handle.failure is not None
            ):
                return self._enrich_handle_detail(handle)

        # 2. Check disk manifest
        try:
            run = self.reader.get_run(run_id)
        except ArtifactStoreError as err:
            raise StudioProblemException(
                type="corrupted-manifest",
                title="Corrupted Run Manifest",
                status=500,
                detail=str(err),
                instance=f"/api/runs/{run_id}",
            ) from err

        if run is not None:
            return run

        # 3. Fall back to registry handle if present
        if self.registry:
            handle = self.registry.get(run_id)
            if handle:
                return self._enrich_handle_detail(handle)

        raise StudioProblemException(
            type="run-not-found",
            title="Run Not Found",
            status=404,
            detail=f"Run manifest for '{run_id}' does not exist on disk or in active registry.",
            instance=f"/api/runs/{run_id}",
        )

    def start_run(self, request: StartRunRequest) -> RunSummary:
        """Initiate a new pipeline execution in a subprocess.

        Parameters
        ----------
        request : StartRunRequest
            Execution configuration parameters.

        Returns
        -------
        RunSummary
            Summary of the created run.

        Raises
        ------
        StudioProblemException
            If executor is unavailable or another run is already active.
        """
        if self.settings and self.settings.read_only:
            raise StudioProblemException(
                type="read-only-mode",
                title="Read-Only Mode",
                status=403,
                detail="Pipeline execution is disabled on this read-only instance.",
                instance="/api/runs",
            )

        if (
            not getattr(request, "demo_mode", False)
            and self.settings
            and not self.settings.execution_enabled
        ):
            raise StudioProblemException(
                type="execution-disabled",
                title="Pipeline Execution Disabled",
                status=403,
                detail="Real pipeline execution is disabled on this instance. Set EPISTEME_STUDIO_EXECUTION_ENABLED=true to enable.",
                instance="/api/runs",
            )

        if not self.executor:
            raise StudioProblemException(
                type="execution-unavailable",
                title="Execution Unavailable",
                status=503,
                detail="Pipeline execution is disabled or unconfigured.",
                instance="/api/runs",
            )

        try:
            resolved_cfg = self.config_service.resolve_run_config(
                profile_id=request.profile_id,
                patch=request.patch,
                parent_run_id=request.parent_run_id,
            )
            config_dict = resolved_cfg.model_dump(mode="python")

            handle = self.executor.start_run(
                run_id=getattr(request, "run_id", None),
                config_dict=config_dict,
                source_paths=request.source_paths,
                bib_paths=request.bib_paths,
                metadata=request.metadata,
                structural_anchor=request.structural_anchor,
                demo_mode=request.demo_mode,
                parent_run_id=request.parent_run_id,
            )
            return handle.to_summary()
        except RunAlreadyActiveError as err:
            raise StudioProblemException(
                type="run-already-active",
                title="Run Already Active",
                status=409,
                detail="Another pipeline execution is currently active. Concurrent runs are rejected (D-27).",
                instance="/api/runs",
            ) from err

    def _terminate_orphaned_run_process(self, run_id: str) -> None:
        """Check for and terminate any lingering OS processes associated with a run.

        Parameters
        ----------
        run_id : str
            Unique run identifier.
        """
        import os
        import signal
        import time

        pid_file = self.reader.runs_dir / run_id / "process.pid"
        if not pid_file.is_file():
            alt_pid = self.reader.runs_dir / f"{run_id}.pid"
            if alt_pid.is_file():
                pid_file = alt_pid
            else:
                return

        try:
            pid_str = pid_file.read_text(encoding="utf-8").strip()
            pid = int(pid_str)
        except Exception:
            pid_file.unlink(missing_ok=True)
            return

        try:
            os.kill(pid, 0)
        except OSError:
            pid_file.unlink(missing_ok=True)
            return

        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(10):
                time.sleep(0.05)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        except OSError:
            pass
        finally:
            pid_file.unlink(missing_ok=True)

    async def cancel_run(self, run_id: str) -> RunSummary:
        """Cancel an in-flight or stale run.

        Parameters
        ----------
        run_id : str
            Identifier of run to cancel.

        Returns
        -------
        RunSummary
            Updated summary with aborted status.

        Raises
        ------
        StudioProblemException
            If run is not found in active registry or on disk.
        """
        from datetime import datetime, timezone

        # 1. Terminate any lingering OS process
        self._terminate_orphaned_run_process(run_id)

        # 2. Cancel in-memory handle if active in executor
        handle = None
        if self.executor:
            try:
                handle = await self.executor.cancel(run_id)
            except KeyError:
                handle = None

        # 3. Mark the run as aborted on disk
        disk_summary = None
        try:
            disk_summary = self.reader.abort_run(run_id)
        except Exception:
            disk_summary = None

        # 4. If neither memory nor disk had this run, raise 404
        if not handle and not disk_summary:
            raise StudioProblemException(
                type="run-not-found",
                title="Run Not Found",
                status=404,
                detail=f"Run '{run_id}' not found in active registry or on disk.",
                instance=f"/api/runs/{run_id}/cancel",
            )

        # 5. Broadcast abortion event via broker if broker is available
        if self.executor and self.executor.broker:
            self.executor.broker.publish(
                run_id,
                {
                    "_raw_type": "RunAborted",
                    "kind": "run.aborted",
                    "run_id": run_id,
                    "level": "warning",
                    "message": f"Run '{run_id}' was cancelled by user.",
                    "timestamp": datetime.now(timezone.utc),
                },
            )
            self.executor.broker.close_run(run_id)

        # 6. Return the updated summary
        if handle:
            return handle.to_summary()
        return disk_summary

    def list_artifacts(self, run_id: str, kind: str | None = None) -> list:
        """List individual artifact envelopes for a run.

        Parameters
        ----------
        run_id : str
            Unique run ID.
        kind : str or None, optional
            Filter by artifact kind.

        Returns
        -------
        list of ArtifactRef
            Artifact references.
        """
        run = self.get_run(run_id)
        return self.reader.list_artifacts(run_id, kind=kind)

    def get_run_langfuse_stats(
        self,
        run_id: str,
        host: str | None = None,
        public_key: str | None = None,
        secret_key: str | None = None,
        limit: int = 250,
    ) -> dict[str, Any]:
        """Fetch Langfuse observations and metrics for a specific pipeline run.

        Parameters
        ----------
        run_id : str
            Identifier of the pipeline run.
        host : str or None, optional
            Langfuse host override.
        public_key : str or None, optional
            Langfuse public key override.
        secret_key : str or None, optional
            Langfuse secret key override.
        limit : int, default 250
            Maximum observations to return.

        Returns
        -------
        dict
            Dictionary with configured, connected, count, and observations list.
        """
        import hashlib
        from episteme_studio.settings import get_env_var

        active_host = (
            host
            or get_env_var("EPISTEME_STUDIO_LANGFUSE_HOST")
            or get_env_var("LANGFUSE_HOST")
            or get_env_var("LANGFUSE_BASE_URL")
            or "http://localhost:3000"
        )
        active_pk = (
            public_key
            if public_key is not None
            else (get_env_var("LANGFUSE_PUBLIC_KEY") or "")
        )
        active_sk = (
            secret_key
            if secret_key is not None
            else (get_env_var("LANGFUSE_SECRET_KEY") or "")
        )

        has_pk = bool(active_pk.strip())
        has_sk = bool(active_sk.strip())
        trace_hex = hashlib.md5(run_id.encode("utf-8")).hexdigest() if run_id else ""

        if not (has_pk and has_sk):
            return {
                "configured": False,
                "connected": False,
                "run_id": run_id,
                "trace_id": trace_hex,
                "count": 0,
                "observations": [],
                "message": "Langfuse credentials not configured in environment or settings.",
            }

        try:
            from langfuse import Langfuse

            client = Langfuse(
                public_key=active_pk, secret_key=active_sk, host=active_host
            )
        except Exception as exc:
            return {
                "configured": True,
                "connected": False,
                "run_id": run_id,
                "trace_id": trace_hex,
                "count": 0,
                "observations": [],
                "message": f"Failed to initialize Langfuse client: {exc}",
            }

        candidate_ids = [run_id]
        if run_id.startswith("run-"):
            candidate_ids.append(run_id[4:])
        else:
            candidate_ids.append(f"run-{run_id}")

        raw_records = []

        # 1. Query by session_id
        for cid in candidate_ids:
            if raw_records:
                break
            try:
                res_session = client.api.observations.get_many(
                    session_id=cid,
                    fields="core,basic,model,usage,metrics,prompt",
                    limit=limit,
                )
                if res_session and res_session.data:
                    raw_records.extend(res_session.data)
            except Exception:
                pass

        # 2. Query by trace_id (md5 hashes and raw candidate IDs)
        if not raw_records:
            trace_candidates = [
                hashlib.md5(cid.encode("utf-8")).hexdigest() for cid in candidate_ids
            ] + candidate_ids
            for tid in trace_candidates:
                if raw_records:
                    break
                try:
                    res_trace = client.api.observations.get_many(
                        trace_id=tid,
                        fields="core,basic,model,usage,metrics,prompt",
                        limit=limit,
                    )
                    if res_trace and res_trace.data:
                        raw_records.extend(res_trace.data)
                except Exception:
                    pass

        seen = set()
        parsed = []
        for obs in raw_records:
            obs_id = getattr(obs, "id", None)
            if not obs_id or obs_id in seen:
                continue
            seen.add(obs_id)
            d = obs.dict() if hasattr(obs, "dict") else obs.model_dump()
            usage = d.get("usageDetails") or d.get("usage") or {}
            cost_details = d.get("costDetails") or {}
            inp_tok = int(usage.get("input") or d.get("inputUsage") or 0)
            out_tok = int(usage.get("output") or d.get("outputUsage") or 0)
            tot_tok = int(
                usage.get("total") or d.get("totalUsage") or (inp_tok + out_tok)
            )
            cost_usd = float(d.get("totalCost") or cost_details.get("total") or 0.0)

            start_t = d.get("startTime")
            end_t = d.get("endTime")
            lat = d.get("latency")
            if lat is None and start_t and end_t:
                try:
                    lat = (end_t - start_t).total_seconds()
                except Exception:
                    lat = 0.0

            level_val = d.get("level")
            if hasattr(level_val, "value"):
                level_str = level_val.value
            else:
                level_str = str(level_val) if level_val else None

            parsed.append(
                {
                    "id": obs_id,
                    "name": d.get("name") or "unnamed_call",
                    "type": d.get("type") or "GENERATION",
                    "startTime": start_t.isoformat()
                    if hasattr(start_t, "isoformat")
                    else str(start_t or ""),
                    "endTime": end_t.isoformat()
                    if hasattr(end_t, "isoformat")
                    else (str(end_t) if end_t else None),
                    "latencySeconds": float(lat or 0.0),
                    "model": d.get("model") or "",
                    "inputTokens": inp_tok,
                    "outputTokens": out_tok,
                    "totalTokens": tot_tok,
                    "costUsd": cost_usd,
                    "promptName": d.get("promptName"),
                    "promptVersion": d.get("promptVersion"),
                    "statusMessage": d.get("statusMessage"),
                    "level": level_str,
                }
            )

        # Sort chronological
        parsed.sort(key=lambda x: x["startTime"])

        return {
            "configured": True,
            "connected": True,
            "run_id": run_id,
            "trace_id": trace_hex,
            "count": len(parsed),
            "observations": parsed,
        }
