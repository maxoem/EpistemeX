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
    AdjudicationRequest,
    AdjudicationResponse,
    BenchmarkDescriptor,
    ComparativeEvaluationResponse,
    CompareRunsRequest,
    DynamicsTrajectoryRequest,
    DynamicsTrajectoryResponse,
    EdgeAdjudicationItem,
    EvaluateManifestRequest,
    EvaluateRunRequest,
    EvaluationJobDescriptor,
    EvaluationJobStatus,
    EvaluationReportDetail,
    EvaluationReportSummary,
    StartEvaluationJobRequest,
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
    ) -> None:
        self.adapter = adapter
        self.reader = reader
        self.reports_dir = Path(reports_dir)
        self._jobs: dict[str, EvaluationJobDescriptor] = {}

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
        return self._jobs.get(job_id)

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
            Registered job descriptor.
        """
        job_id = f"eval_job_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        req_type = "manifest" if manifest_request is not None else "run"
        descriptor = EvaluationJobDescriptor(
            job_id=job_id,
            status=EvaluationJobStatus.RUNNING,
            request_type=req_type,
        )
        self._jobs[job_id] = descriptor

        asyncio.create_task(
            self._run_evaluation_job_worker(
                job_id=job_id,
                manifest_request=manifest_request,
                run_request=run_request,
                broker=broker,
            )
        )
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
            desc = self._jobs[job_id]
            desc.status = EvaluationJobStatus.COMPLETED
            desc.completed_at = datetime.now(timezone.utc)
            desc.report_id = report.evaluation_id
            desc.report = report

            emit(
                "evaluation.job.completed",
                f"Evaluation job completed with outcome: {report.outcome}",
                {"evaluation_id": report.evaluation_id, "outcome": report.outcome},
            )

        except Exception as e:
            logger.error("Evaluation job %s failed: %s", job_id, e, exc_info=True)
            desc = self._jobs.get(job_id)
            if desc:
                desc.status = EvaluationJobStatus.FAILED
                desc.completed_at = datetime.now(timezone.utc)
                desc.error = str(e)
            emit("evaluation.job.failed", f"Evaluation failed: {e}", {"error": str(e)}, level="error")
        finally:
            broker.close_run(job_id)
