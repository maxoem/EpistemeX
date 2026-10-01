"""FastAPI endpoints for knowledge graph evaluation, reports, and benchmarks."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sse_starlette.sse import EventSourceResponse

from episteme_studio.api.deps import get_broker, get_evaluation_service
from episteme_studio.api.errors import (
    BenchmarkNotFoundException,
    EvaluationReportNotFoundException,
)
from episteme_studio.domain.evaluation import (
    AdjudicateAndRecalculateRequest,
    AdjudicateAndRecalculateResponse,
    AdjudicationQueueResponse,
    AdjudicationRequest,
    AdjudicationResponse,
    BenchmarkDescriptor,
    BenchmarkPreviewResponse,
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
    EvaluationReportDetail,
    EvaluationReportSummary,
    GroundingEvaluationDetail,
    LeaderboardRequest,
    LeaderboardResponse,
    NoiseRobustnessReportDetail,
    RegisterBenchmarkRequest,
    RetrievalDiagnosticsResponse,
    StressTestRequest,
)
from episteme_studio.runtime.broker import EventBroker
from episteme_studio.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.get("/reports", response_model=list[EvaluationReportSummary])
async def list_evaluation_reports(
    run_id: str | None = Query(None, description="Filter by participating run identifier"),
    outcome: str | None = Query(None, description="Filter by evaluation outcome ('pass', 'fail', 'warning')"),
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[EvaluationReportSummary]:
    """List all available evaluation report summaries.

    Parameters
    ----------
    run_id : str or None, optional
        Filter by participating run ID.
    outcome : str or None, optional
        Filter by outcome status.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    list of EvaluationReportSummary
        Discovered evaluation report summaries.
    """
    return service.list_reports(run_id=run_id, outcome=outcome)


@router.get("/reports/{evaluation_id}", response_model=EvaluationReportDetail)
async def get_evaluation_report(
    evaluation_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportDetail:
    """Retrieve full evaluation report detail by identifier.

    Parameters
    ----------
    evaluation_id : str
        Unique evaluation or run identifier.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationReportDetail
        Full evaluation report detail.

    Raises
    ------
    EvaluationReportNotFoundException
        If the requested evaluation report cannot be found.
    """
    report = service.get_report(evaluation_id)
    if not report:
        raise EvaluationReportNotFoundException(evaluation_id)
    return report


@router.get("/reports/{evaluation_id}/markdown", response_class=PlainTextResponse)
async def get_evaluation_report_markdown(
    evaluation_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> str:
    """Retrieve raw Markdown commentary for an evaluation report.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    str
        Markdown report content.

    Raises
    ------
    EvaluationReportNotFoundException
        If the requested evaluation report cannot be found.
    """
    report = service.get_report(evaluation_id)
    if not report:
        raise EvaluationReportNotFoundException(evaluation_id)
    return report.summary_markdown


@router.post("/run", response_model=EvaluationReportDetail, status_code=status.HTTP_201_CREATED)
async def evaluate_run(
    request: EvaluateRunRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportDetail:
    """Evaluate a completed pipeline run against a gold standard benchmark.

    Evaluates the extracted graph or theory atoms of `run_id` in-memory
    against the target gold benchmark, computing structuralist model decomposition,
    poset integrity, polarity concordance, retrieval effectiveness, and comparative baselines.

    Parameters
    ----------
    request : EvaluateRunRequest
        Evaluation request options.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationReportDetail
        Synthesized evaluation report.
    """
    return await service.evaluate_run(request)


@router.post("/manifest", response_model=EvaluationReportDetail, status_code=status.HTTP_200_OK)
async def evaluate_manifest(
    request: EvaluateManifestRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportDetail:
    """Trigger a batch evaluation configured by an immutable YAML manifest.

    Parameters
    ----------
    request : EvaluateManifestRequest
        Manifest path and execution options.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationReportDetail
        Synthesized evaluation report.
    """
    return await service.evaluate_manifest(request)


@router.post("/compare", response_model=ComparativeEvaluationResponse)
async def compare_runs(
    request: CompareRunsRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> ComparativeEvaluationResponse:
    """Compare two evaluated pipeline runs side-by-side.

    Parameters
    ----------
    request : CompareRunsRequest
        Comparison request specifying run identifiers.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    ComparativeEvaluationResponse
        Pairwise metric deltas and summary comparison markdown.
    """
    return service.compare_runs(request)


@router.get("/benchmarks", response_model=list[BenchmarkDescriptor])
async def list_benchmarks(
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[BenchmarkDescriptor]:
    """List available gold-standard evaluation benchmarks.

    Parameters
    ----------
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    list of BenchmarkDescriptor
        Registered and discovered benchmark descriptors.
    """
    return service.list_benchmarks()


@router.get("/benchmarks/{benchmark_id}/preview", response_model=BenchmarkPreviewResponse)
async def get_benchmark_preview(
    benchmark_id: str,
    limit: int = 50,
    service: EvaluationService = Depends(get_evaluation_service),
) -> BenchmarkPreviewResponse:
    """Fetch tabular preview records for a benchmark in Hugging Face style.

    Parameters
    ----------
    benchmark_id : str
        Benchmark identifier.
    limit : int, default 50
        Maximum records to fetch.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    BenchmarkPreviewResponse
        Dataset rows and schema preview.
    """
    try:
        return service.get_benchmark_preview(benchmark_id=benchmark_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/manifests", response_model=list[dict[str, Any]])
async def list_manifests(
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[dict[str, Any]]:
    """List available evaluation run manifests.

    Parameters
    ----------
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    list of dict of str to Any
        Discovered manifest descriptors.
    """
    return service.list_manifests()


@router.post("/dynamics/trajectory", response_model=DynamicsTrajectoryResponse)
async def compute_dynamics_trajectory(
    request: DynamicsTrajectoryRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> DynamicsTrajectoryResponse:
    """Evaluate longitudinal diachronic theory evolution and Lakatosian degeneration trajectory.

    Plots the Lakatosian Degeneration Index (DI) across successive historical versions
    T_0 -> T_1 -> T_2, verifying hard-core axiom invariance and detecting ad-hoc immunization.

    Parameters
    ----------
    request : DynamicsTrajectoryRequest
        Chronological run sequence or snapshot payloads.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    DynamicsTrajectoryResponse
        Step-by-step DI metrics, immunization indices, and chart series.
    """
    return service.compute_dynamics_trajectory(request)


@router.post("/adjudications", response_model=AdjudicationResponse)
async def record_adjudications(
    request: AdjudicationRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> AdjudicationResponse:
    """Record human-in-the-loop review adjudications for borderline relation alignments.

    Supports marking edge alignments as True Positive, False Positive, or Schema Aliases,
    and optionally exporting curated annotations back into a gold standard dataset (.jsonld).

    Parameters
    ----------
    request : AdjudicationRequest
        Batch of edge review decisions.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    AdjudicationResponse
        Summary of stored adjudications and export status.
    """
    return service.save_adjudications(request)


@router.get("/adjudications", response_model=list[EdgeAdjudicationItem])
async def list_adjudications(
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[EdgeAdjudicationItem]:
    """Retrieve all previously recorded human review adjudications.

    Parameters
    ----------
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    list of EdgeAdjudicationItem
        Stored adjudication records.
    """
    return service.list_adjudications()


@router.post("/jobs/manifest", response_model=EvaluationJobDescriptor, status_code=status.HTTP_202_ACCEPTED)
async def create_manifest_evaluation_job(
    request: EvaluateManifestRequest,
    broker: EventBroker = Depends(get_broker),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationJobDescriptor:
    """Spawn an asynchronous batch evaluation job from a manifest, streaming telemetry via SSE.

    Parameters
    ----------
    request : EvaluateManifestRequest
        Manifest path and evaluation parameters.
    broker : EventBroker
        Telemetry event broker.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationJobDescriptor
        Tracking descriptor with job identifier.
    """
    return await service.start_evaluation_job(broker=broker, manifest_request=request)


@router.post("/jobs/run", response_model=EvaluationJobDescriptor, status_code=status.HTTP_202_ACCEPTED)
async def create_run_evaluation_job(
    request: EvaluateRunRequest,
    broker: EventBroker = Depends(get_broker),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationJobDescriptor:
    """Spawn an asynchronous run evaluation job against a gold benchmark.

    Parameters
    ----------
    request : EvaluateRunRequest
        Run ID and benchmark parameters.
    broker : EventBroker
        Telemetry event broker.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationJobDescriptor
        Tracking descriptor with job identifier.
    """
    return await service.start_evaluation_job(broker=broker, run_request=request)


@router.get("/jobs/{job_id}", response_model=EvaluationJobDescriptor)
async def get_evaluation_job(
    job_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationJobDescriptor:
    """Retrieve the status and results of an asynchronous evaluation job.

    Parameters
    ----------
    job_id : str
        Evaluation job identifier.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationJobDescriptor
        Current job state and synthesized report if finished.

    Raises
    ------
    HTTPException
        If the job_id cannot be found.
    """
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation job '{job_id}' not found.",
        )
    return job


@router.get("/jobs/{job_id}/stream")
async def stream_evaluation_job_telemetry(
    job_id: str,
    request: Request,
    since: int | None = Query(None, description="Sequence number threshold to replay after"),
    broker: EventBroker = Depends(get_broker),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EventSourceResponse:
    """Stream real-time stage progress and query ranking telemetry for an evaluation job via SSE.

    Parameters
    ----------
    job_id : str
        Target evaluation job identifier.
    request : Request
        Incoming HTTP request.
    since : int or None, optional
        Threshold sequence number to replay after.
    broker : EventBroker
        Telemetry event broker.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EventSourceResponse
        Server-Sent Events stream yielding stage and ranking updates.
    """
    last_event_id = request.headers.get("last-event-id")
    since_seq = since
    if last_event_id and last_event_id.isdigit():
        since_seq = int(last_event_id)

    async def event_generator():
        async for event in broker.subscribe(job_id, since_seq=since_seq):
            if await request.is_disconnected():
                break
            yield {
                "id": str(event.seq),
                "event": "message",
                "data": event.model_dump_json(),
            }

    return EventSourceResponse(event_generator())


@router.post("/jobs/{job_id}/cancel", response_model=CancelEvaluationJobResponse)
async def cancel_evaluation_job(
    job_id: str,
    broker: EventBroker = Depends(get_broker),
    service: EvaluationService = Depends(get_evaluation_service),
) -> CancelEvaluationJobResponse:
    """Cancel an in-flight or queued evaluation job.

    Parameters
    ----------
    job_id : str
        Target evaluation job identifier.
    broker : EventBroker
        Telemetry event broker.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    CancelEvaluationJobResponse
        Confirmation payload for the cancelled evaluation job.

    Raises
    ------
    HTTPException
        If the job_id cannot be found.
    """
    try:
        return service.cancel_evaluation_job(job_id, broker=broker)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation job '{job_id}' not found.",
        )


# =============================================================================
# Evaluation Workbench Endpoints (ISSUE-026 - ISSUE-033)
# =============================================================================


@router.get("/reports/{evaluation_id}/graph-overlay", response_model=EvaluationGraphOverlay)
async def get_evaluation_graph_overlay(
    evaluation_id: str,
    include_ghosts: bool = Query(True, description="Whether to include synthesized ghost nodes for omissions"),
    filter_status: str | None = Query(None, description="Optional alignment status filter"),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationGraphOverlay:
    """Retrieve interactive graph canvas overlay projecting evaluation alignment and errors.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    include_ghosts : bool, default True
        Whether to synthesize ghost nodes/edges for omitted components.
    filter_status : str or None, optional
        Filter elements by alignment status ('true_positive', 'false_positive', etc.).
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationGraphOverlay
        Constructed graph overlay.
    """
    return service.build_graph_overlay(
        evaluation_id=evaluation_id,
        include_ghosts=include_ghosts,
        filter_status=filter_status,
    )


@router.get("/reports/{evaluation_id}/adjudication-queue", response_model=AdjudicationQueueResponse)
async def get_adjudication_queue(
    evaluation_id: str,
    status: str = Query("pending", description="Filter by status ('pending', 'adjudicated', 'all')"),
    min_sim: float = Query(0.75, description="Minimum soft similarity threshold"),
    max_sim: float = Query(0.95, description="Maximum soft similarity threshold"),
    service: EvaluationService = Depends(get_evaluation_service),
) -> AdjudicationQueueResponse:
    """Retrieve candidate relation alignments in uncertainty band for human expert adjudication.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    status : str, default 'pending'
        Triage filter status.
    min_sim : float, default 0.75
        Minimum similarity bound.
    max_sim : float, default 0.95
        Maximum similarity bound.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    AdjudicationQueueResponse
        Queue containing candidate items and counts.
    """
    return service.get_adjudication_queue(
        evaluation_id=evaluation_id,
        status=status,
        min_sim=min_sim,
        max_sim=max_sim,
    )


@router.post("/reports/{evaluation_id}/adjudicate-and-recalculate", response_model=AdjudicateAndRecalculateResponse)
async def adjudicate_and_recalculate(
    evaluation_id: str,
    request: AdjudicateAndRecalculateRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> AdjudicateAndRecalculateResponse:
    """Submit human review adjudications and dynamically recompute evaluation metrics in-place.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    request : AdjudicateAndRecalculateRequest
        Submitted review decisions.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    AdjudicateAndRecalculateResponse
        Updated evaluation report and metric deltas.
    """
    return service.adjudicate_and_recalculate(evaluation_id=evaluation_id, request=request)


@router.get("/reports/{evaluation_id}/calibration", response_model=CalibrationReportDetail)
async def get_calibration_report(
    evaluation_id: str,
    min_confidence: float = Query(0.85, description="Threshold for highlighting overconfident assertions"),
    limit: int = Query(50, description="Max miscalibrated assertions to return"),
    service: EvaluationService = Depends(get_evaluation_service),
) -> CalibrationReportDetail:
    """Retrieve confidence calibration metrics, 10-bin reliability diagram, and overconfidence errors.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    min_confidence : float, default 0.85
        Overconfidence threshold.
    limit : int, default 50
        Max errors to return.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    CalibrationReportDetail
        ECE, MCE, Brier score, bins, and miscalibrated assertions.
    """
    return service.get_calibration_report(
        evaluation_id=evaluation_id,
        min_confidence_filter=min_confidence,
        limit=limit,
    )


@router.get("/reports/{evaluation_id}/evidence/{component_id}", response_model=GroundingEvaluationDetail)
async def get_component_evidence(
    evaluation_id: str,
    component_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> GroundingEvaluationDetail:
    """Retrieve multi-modal primary source evidence grounding for an evaluated construct.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    component_id : str
        Target construct or axiom identifier.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    GroundingEvaluationDetail
        Multi-modal bounding boxes, verbatim text anchors, and IoU score.
    """
    return service.get_evidence_detail(evaluation_id=evaluation_id, component_id=component_id)


@router.post("/leaderboard", response_model=LeaderboardResponse)
async def get_benchmark_leaderboard_post(
    request: LeaderboardRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> LeaderboardResponse:
    """Construct multi-run benchmark leaderboard matrix and calculate Pareto frontier (POST).

    Parameters
    ----------
    request : LeaderboardRequest
        Leaderboard request parameters.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    LeaderboardResponse
        Aggregated leaderboard matrix and Pareto non-dominated points.
    """
    return service.compute_leaderboard(request)


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_benchmark_leaderboard_get(
    benchmark_id: str | None = Query(None, description="Benchmark identifier filter"),
    sort_by: str = Query("f1", description="Primary sorting KPI"),
    ascending: bool = Query(False, description="Sort direction"),
    service: EvaluationService = Depends(get_evaluation_service),
) -> LeaderboardResponse:
    """Construct multi-run benchmark leaderboard matrix and calculate Pareto frontier (GET).

    Parameters
    ----------
    benchmark_id : str or None, optional
        Target benchmark.
    sort_by : str, default 'f1'
        Primary sort metric.
    ascending : bool, default False
        Sort ascending or descending.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    LeaderboardResponse
        Aggregated leaderboard matrix and Pareto non-dominated points.
    """
    return service.compute_leaderboard(
        LeaderboardRequest(
            benchmark_id=benchmark_id,
            sort_by=sort_by,
            ascending=ascending,
        )
    )


@router.post("/stress-test", response_model=NoiseRobustnessReportDetail, status_code=status.HTTP_201_CREATED)
async def execute_stress_test(
    request: StressTestRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> NoiseRobustnessReportDetail:
    """Trigger synthetic adversarial noise sweeps and calculate Robustness Degradation Factors.

    Parameters
    ----------
    request : StressTestRequest
        Perturbation modalities and noise levels.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    NoiseRobustnessReportDetail
        Degradation curve series and RDF scores.
    """
    return service.execute_stress_test(request)


@router.get("/reports/{evaluation_id}/robustness", response_model=NoiseRobustnessReportDetail)
async def get_robustness_report(
    evaluation_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> NoiseRobustnessReportDetail:
    """Retrieve previously executed noise robustness report.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    NoiseRobustnessReportDetail
        Noise robustness degradation report.
    """
    return service.get_robustness_report(evaluation_id=evaluation_id)


@router.get("/reports/{evaluation_id}/retrieval-diagnostics", response_model=RetrievalDiagnosticsResponse)
async def get_retrieval_diagnostics(
    evaluation_id: str,
    failed_only: bool = Query(False, description="Whether to only return queries where first hit rank > 10"),
    limit: int = Query(100, description="Max queries to return"),
    service: EvaluationService = Depends(get_evaluation_service),
) -> RetrievalDiagnosticsResponse:
    """Expose per-query competency question ranking breakdowns and retrieval failures.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    failed_only : bool, default False
        Filter to failing queries.
    limit : int, default 100
        Maximum query count.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    RetrievalDiagnosticsResponse
        Detailed competency question ranking diagnostics.
    """
    return service.get_retrieval_diagnostics(
        evaluation_id=evaluation_id,
        failed_only=failed_only,
        limit=limit,
    )


@router.post("/benchmarks/validate", response_model=BenchmarkValidationResult)
async def validate_benchmark(
    request: dict[str, Any],
    service: EvaluationService = Depends(get_evaluation_service),
) -> BenchmarkValidationResult:
    """Pre-flight lint and validate benchmark dataset structure, uniqueness, and DAG acyclicity.

    Parameters
    ----------
    request : dict of str to Any
        Payload containing 'content' string.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    BenchmarkValidationResult
        Validation outcome report.
    """
    raw_content = request.get("content", "")
    return service.validate_benchmark(raw_content=raw_content)


@router.post("/benchmarks", response_model=BenchmarkDescriptor, status_code=status.HTTP_201_CREATED)
async def register_benchmark(
    request: RegisterBenchmarkRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> BenchmarkDescriptor:
    """Register a new gold-standard benchmark in the filesystem catalog.

    Parameters
    ----------
    request : RegisterBenchmarkRequest
        Benchmark definition payload.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    BenchmarkDescriptor
        Created benchmark descriptor.
    """
    return service.register_benchmark(request)


@router.get("/reports/{evaluation_id}/export")
async def export_evaluation_report(
    evaluation_id: str,
    format: str = Query("latex", description="Export format ('latex', 'csv', 'jsonld')"),
    service: EvaluationService = Depends(get_evaluation_service),
) -> Response:
    """Export publication-ready LaTeX tables, CSV summaries, or JSON-LD graph bundles.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    format : str, default 'latex'
        Format identifier ('latex', 'csv', 'jsonld').
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    Response
        Exported text/data with appropriate MIME type.
    """
    content, media_type = service.export_report(evaluation_id=evaluation_id, format=format)
    return Response(content=content, media_type=media_type)
