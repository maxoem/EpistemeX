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
    EvaluationReportDetail,
    EvaluationReportSummary,
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
