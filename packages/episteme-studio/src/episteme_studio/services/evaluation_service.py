"""Service layer orchestrating knowledge graph evaluation queries and execution.

In accordance with SPEC §2, this service layer coordinates domain workflows
and remains free of FastAPI dependencies for complete unit testability.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.adapters.evaluation_adapter import EvaluationAdapter
from episteme_studio.domain.events import StudioEvent
from episteme_studio.domain.evaluation import (
    AdjudicateAndRecalculateRequest,
    AdjudicateAndRecalculateResponse,
    AdjudicationQueueResponse,
    AdjudicationRequest,
    AdjudicationResponse,
    BenchmarkDescriptor,
    BenchmarkValidationResult,
    CalibrationReportDetail,
    CancelEvaluationJobResponse,
    ComparativeEvaluationResponse,
    CompareRunsRequest,
    DynamicsTrajectoryRequest,
    DynamicsTrajectoryResponse,
    EdgeAdjudicationItem,
    EvaluateManifestRequest,
    EvaluateRunRequest,
    EvaluationGraphOverlay,
    EvaluationJobDescriptor,
    EvaluationJobStatus,
    EvaluationReportDetail,
    EvaluationReportSummary,
    GroundingEvaluationDetail,
    LeaderboardRequest,
    LeaderboardResponse,
    NoiseRobustnessReportDetail,
    RegisterBenchmarkRequest,
    RetrievalDiagnosticsResponse,
    StartEvaluationJobRequest,
    StressTestRequest,
)
from episteme_studio.runtime.broker import EventBroker
from episteme_studio.settings import StudioSettings


class EvaluationService:
    """Service managing evaluation reports, benchmark execution, and baseline comparisons.

    Parameters
    ----------
    adapter : EvaluationAdapter
        Underlying evaluation adapter bridging to episteme-pipeline.
    reader : ArtifactReader
        Artifact reader for inspecting run intermediates.
    reports_dir : Path or str, default 'evaluation/reports'
        Output directory for evaluation reports.
    """

    def __init__(
        self,
        adapter: EvaluationAdapter,
        reader: ArtifactReader,
        reports_dir: Path | str = "evaluation/reports",
        jobs_dir: Path | str | None = None,
        max_concurrent_jobs: int = 2,
    ) -> None:
        self.adapter = adapter
        self.reader = reader
        self.reports_dir = Path(reports_dir)
        self._jobs_dir = Path(jobs_dir) if jobs_dir else (self.reports_dir.parent / ".evaluation_jobs")
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, EvaluationJobDescriptor] = {}
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._cancellation_events: dict[str, asyncio.Event] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)

    def _persist_job(self, desc: EvaluationJobDescriptor) -> None:
        """Persist evaluation job descriptor to disk for crash resilience.

        Parameters
        ----------
        desc : EvaluationJobDescriptor
            Job descriptor to serialize and persist.
        """
        try:
            target_file = self._jobs_dir / f"{desc.job_id}.json"
            target_file.write_text(desc.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to persist evaluation job %s: %s", desc.job_id, e)

    @classmethod
    def from_settings(cls, settings: StudioSettings) -> EvaluationService:
        """Instantiate EvaluationService from configuration settings.

        Parameters
        ----------
        settings : StudioSettings
            Application configuration settings.

        Returns
        -------
        EvaluationService
            Configured service instance.
        """
        adapter = EvaluationAdapter(
            reports_dir=settings.reports_dir,
            include_fixtures=settings.demo_mode,
        )
        reader = ArtifactReader(
            runs_dir=settings.runs_dir,
            artifacts_dir=settings.artifacts_dir,
            langfuse_host=settings.langfuse_host,
            extra_runs_dirs=settings.extra_runs_dirs,
            extra_artifacts_dirs=settings.extra_artifacts_dirs,
        )
        return cls(adapter=adapter, reader=reader, reports_dir=settings.reports_dir)

    def list_reports(
        self,
        run_id: str | None = None,
        outcome: str | None = None,
    ) -> list[EvaluationReportSummary]:
        """List all discovered evaluation report summaries.

        Parameters
        ----------
        run_id : str or None, optional
            Filter by participating run identifier.
        outcome : str or None, optional
            Filter by evaluation outcome ('pass', 'fail', 'warning').

        Returns
        -------
        list of EvaluationReportSummary
            Summaries sorted newest first.
        """
        return self.adapter.list_reports(run_id=run_id, outcome=outcome)

    def get_report(self, evaluation_id: str) -> EvaluationReportDetail | None:
        """Retrieve full detailed evaluation report by identifier.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.

        Returns
        -------
        EvaluationReportDetail or None
            Detailed report if found, None otherwise.
        """
        return self.adapter.get_report(evaluation_id)

    def get_run_evaluation(self, run_id: str) -> EvaluationReportDetail | None:
        """Retrieve the primary evaluation report associated with a pipeline run.

        Parameters
        ----------
        run_id : str
            Target run identifier.

        Returns
        -------
        EvaluationReportDetail or None
            Report detail if evaluated, None otherwise.
        """
        return self.adapter.get_report(run_id)

    async def evaluate_run(self, request: EvaluateRunRequest) -> EvaluationReportDetail:
        """Evaluate a completed pipeline run against a gold standard benchmark.

        Parameters
        ----------
        request : EvaluateRunRequest
            Run evaluation request parameters.

        Returns
        -------
        EvaluationReportDetail
            Synthesized evaluation report.
        """
        return await self.adapter.evaluate_run(
            run_id=request.run_id,
            reader=self.reader,
            gold_standard_path=request.gold_standard_path,
            benchmark_id=request.benchmark_id,
            queries_path=request.queries_path,
            strategy=request.strategy,
            baseline=request.baseline,
            min_mcc=request.min_mcc,
            min_pfs=request.min_pfs,
            sim_threshold=request.sim_threshold,
            persist=request.persist,
            llm_model=request.llm_model,
            embedding_model=request.embedding_model,
        )

    async def evaluate_manifest(self, request: EvaluateManifestRequest) -> EvaluationReportDetail:
        """Execute a batch evaluation configured by an immutable YAML manifest.

        Parameters
        ----------
        request : EvaluateManifestRequest
            Manifest evaluation request parameters.

        Returns
        -------
        EvaluationReportDetail
            Parsed evaluation report detail.
        """
        return await self.adapter.evaluate_manifest(
            manifest_path=request.manifest_path,
            baseline=request.baseline,
            build_graph=request.build_graph,
        )

    def compare_runs(self, request: CompareRunsRequest) -> ComparativeEvaluationResponse:
        """Compare two evaluated pipeline runs side-by-side.

        Parameters
        ----------
        request : CompareRunsRequest
            Run comparison request.

        Returns
        -------
        ComparativeEvaluationResponse
            Comparative metric deltas and summary markdown.
        """
        return self.adapter.compare_runs(
            run_id_a=request.run_id_a,
            run_id_b=request.run_id_b,
            axis=request.axis,
        )

    def list_benchmarks(self) -> list[BenchmarkDescriptor]:
        """List registered gold-standard benchmarks available for evaluation.

        Returns
        -------
        list of BenchmarkDescriptor
            Discovered benchmark descriptors.
        """
        return self.adapter.discover_benchmarks()

    def list_manifests(self) -> list[dict[str, Any]]:
        """List available declarative evaluation YAML manifests.

        Returns
        -------
        list of dict of str to Any
            Manifest descriptors.
        """
        return self.adapter.discover_manifests()

    def compute_dynamics_trajectory(
        self,
        request: DynamicsTrajectoryRequest,
    ) -> DynamicsTrajectoryResponse:
        """Compute diachronic Lakatosian degeneration trajectory across multiple successive runs.

        Parameters
        ----------
        request : DynamicsTrajectoryRequest
            Trajectory request options.

        Returns
        -------
        DynamicsTrajectoryResponse
            Trajectory metrics and interactive chart data.
        """
        return self.adapter.evaluate_trajectory(request=request, reader=self.reader)

    def save_adjudications(self, request: AdjudicationRequest) -> AdjudicationResponse:
        """Store expert edge adjudications and optionally export curated gold standard dataset.

        Parameters
        ----------
        request : AdjudicationRequest
            Review adjudications to persist.

        Returns
        -------
        AdjudicationResponse
            Adjudication result summary.
        """
        return self.adapter.save_adjudications(request)

    def list_adjudications(self) -> list[EdgeAdjudicationItem]:
        """List all previously recorded human review adjudications.

        Returns
        -------
        list of EdgeAdjudicationItem
            Stored edge review items.
        """
        return self.adapter.list_adjudications()

    def get_job(self, job_id: str) -> EvaluationJobDescriptor | None:
        """Retrieve the status and metadata of an evaluation job.

        Parameters
        ----------
        job_id : str
            Unique job identifier.

        Returns
        -------
        EvaluationJobDescriptor or None
            Job descriptor if registered, None otherwise.
        """
        if job_id in self._jobs:
            return self._jobs[job_id]

        target_file = self._jobs_dir / f"{job_id}.json"
        if target_file.is_file():
            try:
                desc = EvaluationJobDescriptor.model_validate_json(target_file.read_text(encoding="utf-8"))
                self._jobs[job_id] = desc
                return desc
            except Exception as e:
                logger.warning("Failed to read job file for %s: %s", job_id, e)
        return None

    async def start_evaluation_job(
        self,
        broker: EventBroker,
        manifest_request: EvaluateManifestRequest | None = None,
        run_request: EvaluateRunRequest | None = None,
    ) -> EvaluationJobDescriptor:
        """Spawn a background asynchronous batch evaluation job streaming events via SSE.

        Parameters
        ----------
        broker : EventBroker
            Event broker instance to publish telemetry events to.
        manifest_request : EvaluateManifestRequest or None, optional
            Manifest evaluation options.
        run_request : EvaluateRunRequest or None, optional
            Run evaluation options.

        Returns
        -------
        EvaluationJobDescriptor
            Registered job descriptor in PENDING or RUNNING status.
        """
        job_id = f"eval_job_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        req_type = "manifest" if manifest_request is not None else "run"
        descriptor = EvaluationJobDescriptor(
            job_id=job_id,
            status=EvaluationJobStatus.PENDING,
            request_type=req_type,
        )
        self._jobs[job_id] = descriptor
        self._persist_job(descriptor)
        self._cancellation_events[job_id] = asyncio.Event()

        task = asyncio.create_task(
            self._run_evaluation_job_worker(
                job_id=job_id,
                manifest_request=manifest_request,
                run_request=run_request,
                broker=broker,
            )
        )
        self._tasks[job_id] = task
        return descriptor

    async def _run_evaluation_job_worker(
        self,
        job_id: str,
        manifest_request: EvaluateManifestRequest | None,
        run_request: EvaluateRunRequest | None,
        broker: EventBroker,
    ) -> None:
        """Execute evaluation job asynchronously in background and emit SSE events."""
        def emit(kind: str, message: str, payload: dict[str, Any] | None = None, level: str = "info") -> None:
            event = StudioEvent(
                seq=1,
                run_id=job_id,
                ts=datetime.now(timezone.utc),
                kind=kind,
                level=level,
                phase="Evaluation",
                message=message,
                payload=payload or {},
            )
            broker.publish(job_id, event)

        try:
            # Guard execution with bounded concurrency semaphore
            async with self._semaphore:
                cancel_event = self._cancellation_events.get(job_id)
                if cancel_event and cancel_event.is_set():
                    desc = self._jobs.get(job_id)
                    if desc:
                        desc.status = EvaluationJobStatus.ABORTED
                        desc.completed_at = datetime.now(timezone.utc)
                        self._persist_job(desc)
                    emit("evaluation.job.aborted", f"Job {job_id} was aborted before start", {"job_id": job_id}, level="warning")
                    return

                desc = self._jobs[job_id]
                desc.status = EvaluationJobStatus.RUNNING
                self._persist_job(desc)

                emit("evaluation.job.started", "Asynchronous evaluation job started", {"job_id": job_id})

                report: EvaluationReportDetail
                if manifest_request is not None:
                    emit(
                        "evaluation.stage.started",
                        "Evaluating manifest configuration",
                        {"manifest_path": manifest_request.manifest_path},
                    )
                    report = await self.evaluate_manifest(manifest_request)
                elif run_request is not None:
                    emit(
                        "evaluation.stage.started",
                        f"Evaluating run {run_request.run_id}",
                        {"run_id": run_request.run_id},
                    )
                    report = await self.evaluate_run(run_request)
                else:
                    raise ValueError("Neither manifest_request nor run_request was provided.")

                # Check if cancellation was requested during evaluation
                if cancel_event and cancel_event.is_set():
                    desc = self._jobs.get(job_id, desc)
                    desc.status = EvaluationJobStatus.ABORTED
                    desc.completed_at = datetime.now(timezone.utc)
                    self._persist_job(desc)
                    emit("evaluation.job.aborted", f"Job {job_id} was cancelled by user", {"job_id": job_id}, level="warning")
                    return

                # Emit stage completion telemetry
                for level, results in report.results_by_level.items():
                    for res in results:
                        emit(
                            "evaluation.stage.completed",
                            f"Stage completed: {res.phase_name or level}",
                            {
                                "stage": level,
                                "phase_name": res.phase_name,
                                "metrics": [m.model_dump() for m in res.metrics],
                                "outcome": res.outcome,
                            },
                        )

                if report.retrieval_detail and report.retrieval_detail.num_queries > 0:
                    emit(
                        "evaluation.query.ranked",
                        "Competency retrieval queries evaluated",
                        {
                            "mrr": report.retrieval_detail.mrr,
                            "hits_at_1": report.retrieval_detail.hits_at_1,
                            "ndcg": report.retrieval_detail.ndcg,
                            "num_queries": report.retrieval_detail.num_queries,
                        },
                    )

                # Mark completed
                desc.status = EvaluationJobStatus.COMPLETED
                desc.completed_at = datetime.now(timezone.utc)
                desc.report_id = report.evaluation_id
                desc.report = report
                self._persist_job(desc)

                emit(
                    "evaluation.job.completed",
                    f"Evaluation job completed with outcome: {report.outcome}",
                    {"evaluation_id": report.evaluation_id, "outcome": report.outcome},
                )

        except asyncio.CancelledError:
            logger.info("Evaluation job %s cancelled", job_id)
            desc = self._jobs.get(job_id)
            if desc:
                desc.status = EvaluationJobStatus.ABORTED
                desc.completed_at = datetime.now(timezone.utc)
                self._persist_job(desc)
            emit("evaluation.job.aborted", f"Evaluation job {job_id} cancelled by user", {"job_id": job_id}, level="warning")
        except Exception as e:
            logger.error("Evaluation job %s failed: %s", job_id, e, exc_info=True)
            desc = self._jobs.get(job_id)
            if desc:
                desc.status = EvaluationJobStatus.FAILED
                desc.completed_at = datetime.now(timezone.utc)
                desc.error = str(e)
                self._persist_job(desc)
            emit("evaluation.job.failed", f"Evaluation failed: {e}", {"error": str(e)}, level="error")
        finally:
            broker.close_run(job_id)

    def cancel_evaluation_job(
        self,
        job_id: str,
        broker: EventBroker | None = None,
    ) -> CancelEvaluationJobResponse:
        """Cancel an in-flight or queued evaluation job.

        Parameters
        ----------
        job_id : str
            Unique job identifier.
        broker : EventBroker or None, optional
            Event broker instance to publish cancellation telemetry.

        Returns
        -------
        CancelEvaluationJobResponse
            Confirmation response payload.

        Raises
        ------
        KeyError
            If the job is not found.
        """
        desc = self.get_job(job_id)
        if not desc:
            raise KeyError(f"Evaluation job '{job_id}' not found")

        if desc.status in (EvaluationJobStatus.COMPLETED, EvaluationJobStatus.FAILED, EvaluationJobStatus.ABORTED):
            return CancelEvaluationJobResponse(
                job_id=job_id,
                status=desc.status,
                message=f"Evaluation job '{job_id}' is already in terminal state '{desc.status}'.",
            )

        desc.status = EvaluationJobStatus.ABORTED
        desc.completed_at = datetime.now(timezone.utc)
        self._persist_job(desc)

        cancel_event = self._cancellation_events.get(job_id)
        if cancel_event:
            cancel_event.set()

        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        if broker:
            broker.publish(
                job_id,
                StudioEvent(
                    seq=1,
                    run_id=job_id,
                    ts=datetime.now(timezone.utc),
                    kind="evaluation.job.aborted",
                    level="warning",
                    phase="Evaluation",
                    message=f"Evaluation job '{job_id}' was cancelled by user.",
                    payload={"job_id": job_id},
                ),
            )
            broker.close_run(job_id)

        return CancelEvaluationJobResponse(
            job_id=job_id,
            status=EvaluationJobStatus.ABORTED,
            message=f"Evaluation job '{job_id}' successfully cancelled.",
        )

    # -------------------------------------------------------------------------
    # Evaluation Workbench & Interactive Analytics (ISSUE-026 - ISSUE-033)
    # -------------------------------------------------------------------------

    def build_graph_overlay(
        self,
        evaluation_id: str,
        include_ghosts: bool = True,
        filter_status: str | None = None,
    ) -> EvaluationGraphOverlay:
        """Construct interactive graph canvas overlay projecting evaluation alignment and errors.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.
        include_ghosts : bool, default True
            Whether to synthesize ghost nodes/edges for omitted gold components.
        filter_status : str or None, optional
            Filter elements by alignment status.

        Returns
        -------
        EvaluationGraphOverlay
            Complete node and edge overlay with alignment classifications.
        """
        return self.adapter.build_graph_overlay(
            evaluation_id=evaluation_id,
            include_ghosts=include_ghosts,
            filter_status=filter_status,
        )

    def get_adjudication_queue(
        self,
        evaluation_id: str,
        status: str = "pending",
        min_sim: float = 0.75,
        max_sim: float = 0.95,
    ) -> AdjudicationQueueResponse:
        """Retrieve candidate edge alignments in uncertainty band for human review.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.
        status : str, default 'pending'
            Filter by triage status ('pending', 'adjudicated', 'all').
        min_sim : float, default 0.75
            Minimum soft similarity threshold.
        max_sim : float, default 0.95
            Maximum soft similarity threshold.

        Returns
        -------
        AdjudicationQueueResponse
            Queue containing candidate items and status counts.
        """
        return self.adapter.get_adjudication_queue(
            evaluation_id=evaluation_id,
            status=status,
            min_sim=min_sim,
            max_sim=max_sim,
        )

    def adjudicate_and_recalculate(
        self,
        evaluation_id: str,
        request: AdjudicateAndRecalculateRequest,
    ) -> AdjudicateAndRecalculateResponse:
        """Register expert decisions and dynamically recalculate evaluation report metrics.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.
        request : AdjudicateAndRecalculateRequest
            Submitted review items and target export destination.

        Returns
        -------
        AdjudicateAndRecalculateResponse
            Updated report and metric deltas.
        """
        return self.adapter.adjudicate_and_recalculate(
            evaluation_id=evaluation_id,
            request=request,
        )

    def get_calibration_report(
        self,
        evaluation_id: str,
        min_confidence_filter: float = 0.85,
        limit: int = 50,
    ) -> CalibrationReportDetail:
        """Compute confidence calibration metrics, 10-bin reliability diagram, and overconfidence errors.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.
        min_confidence_filter : float, default 0.85
            Threshold for flagging overconfident errors.
        limit : int, default 50
            Maximum miscalibrated errors to return.

        Returns
        -------
        CalibrationReportDetail
            Calibration metrics, bin distributions, and miscalibrated assertions.
        """
        return self.adapter.get_calibration_report(
            evaluation_id=evaluation_id,
            min_confidence_filter=min_confidence_filter,
            limit=limit,
        )

    def get_evidence_detail(
        self,
        evaluation_id: str,
        component_id: str,
    ) -> GroundingEvaluationDetail:
        """Retrieve multi-modal primary source evidence grounding for an evaluated construct.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.
        component_id : str
            Construct or axiom identifier.

        Returns
        -------
        GroundingEvaluationDetail
            Multi-modal bounding boxes, verbatim text anchors, and IoU score.
        """
        return self.adapter.get_evidence_detail(
            evaluation_id=evaluation_id,
            component_id=component_id,
        )

    def compute_leaderboard(
        self,
        request: LeaderboardRequest,
    ) -> LeaderboardResponse:
        """Construct multi-run benchmark leaderboard matrix and calculate Pareto frontier.

        Parameters
        ----------
        request : LeaderboardRequest
            Benchmark filtering, Pareto axes, and sorting options.

        Returns
        -------
        LeaderboardResponse
            Aggregated leaderboard entries and non-dominated Pareto frontier points.
        """
        return self.adapter.compute_leaderboard(request=request)

    def execute_stress_test(
        self,
        request: StressTestRequest,
    ) -> NoiseRobustnessReportDetail:
        """Trigger synthetic adversarial noise sweeps and calculate Robustness Degradation Factors.

        Parameters
        ----------
        request : StressTestRequest
            Target run, perturbation modalities, and noise rates.

        Returns
        -------
        NoiseRobustnessReportDetail
            Degradation series and RDF robustness score.
        """
        return self.adapter.execute_stress_test(request=request)

    def get_robustness_report(self, evaluation_id: str) -> NoiseRobustnessReportDetail:
        """Retrieve previously executed noise robustness report.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.

        Returns
        -------
        NoiseRobustnessReportDetail
            Stored robustness report.
        """
        return self.adapter.get_robustness_report(evaluation_id=evaluation_id)

    def get_retrieval_diagnostics(
        self,
        evaluation_id: str,
        failed_only: bool = False,
        limit: int = 100,
    ) -> RetrievalDiagnosticsResponse:
        """Expose per-query competency question ranking breakdowns and retrieval failures.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.
        failed_only : bool, default False
            Whether to only return queries where first hit rank > 10.
        limit : int, default 100
            Maximum queries to return.

        Returns
        -------
        RetrievalDiagnosticsResponse
            Query breakdown items with ranking positions and hit flags.
        """
        return self.adapter.get_retrieval_diagnostics(
            evaluation_id=evaluation_id,
            failed_only=failed_only,
            limit=limit,
        )

    def validate_benchmark(self, raw_content: str) -> BenchmarkValidationResult:
        """Pre-flight lint and validate benchmark dataset structure, uniqueness, and DAG acyclicity.

        Parameters
        ----------
        raw_content : str
            JSON-LD or YAML dataset content.

        Returns
        -------
        BenchmarkValidationResult
            Verification results with detected issues and root element conformity.
        """
        return self.adapter.validate_benchmark(raw_content=raw_content)

    def register_benchmark(self, request: RegisterBenchmarkRequest) -> BenchmarkDescriptor:
        """Register a new gold-standard benchmark in the filesystem catalog.

        Parameters
        ----------
        request : RegisterBenchmarkRequest
            Benchmark metadata and raw contents.

        Returns
        -------
        BenchmarkDescriptor
            Registered benchmark descriptor.
        """
        return self.adapter.register_benchmark(request=request)

    def export_report(self, evaluation_id: str, format: str = "latex") -> tuple[str, str]:
        """Export publication-ready LaTeX tables, CSV summaries, or JSON-LD graph bundles.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.
        format : str, default 'latex'
            Export format ('latex', 'csv', 'jsonld').

        Returns
        -------
        tuple of str, str
            (Export content string, MIME media type).
        """
        return self.adapter.export_report(evaluation_id=evaluation_id, format=format)
