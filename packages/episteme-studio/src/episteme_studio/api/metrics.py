"""API endpoints for metric descriptors and async execution lifecycle."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from episteme_studio.api.deps import get_graph_service, get_metric_service
from episteme_studio.api.errors import StudioProblemException
from episteme_studio.domain.errors import ProblemDetail
from episteme_studio.domain.graph import GraphView
from episteme_studio.domain.metrics import MetricDescriptor, MetricResult
from episteme_studio.services.graph_service import GraphService
from episteme_studio.services.metric_service import ExecutionStatus, MetricService

router = APIRouter(tags=["metrics"])


class MetricExecutionNotFoundException(StudioProblemException):
    """Raised when a requested execution ID does not exist."""

    def __init__(self, execution_id: str) -> None:
        super().__init__(
            type="metric-execution-not-found",
            title="Metric Execution Not Found",
            status=404,
            detail=f"Execution job '{execution_id}' was not found.",
        )


class ExecuteMetricRequest(BaseModel):
    """Payload for submitting a graph metric calculation job.

    Parameters
    ----------
    metric_id : str
        Identifier of the metric to run.
    focus_node_id : str or None, optional
        Target focus node if single_node scope.
    params : dict of str to Any, optional
        Algorithmic configuration parameters.
    source : Literal["artifacts", "neo4j"] or None, optional
        Data source for the graph projection.
    run_id : str or None, optional
        Target run identifier if using artifact store.
    graph_version : str or None, optional
        Optional graph fingerprint filter.
    """

    metric_id: str
    focus_node_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    source: Literal["artifacts", "neo4j"] | None = None
    run_id: str | None = None
    graph_version: str | None = None


class ExecutionStatusResponse(BaseModel):
    """Status tracking payload for an in-flight or completed execution.

    Parameters
    ----------
    execution_id : str
        Execution identifier.
    status : str
        Current status ("queued", "running", "completed", "failed", "cancelled").
    progress : float or None, optional
        Fractional completion progress.
    result : MetricResult or None, optional
        Result payload if completed.
    error : ProblemDetail or None, optional
        Error details if failed.
    """

    execution_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float | None = None
    result: MetricResult | None = None
    error: ProblemDetail | None = None


@router.get("/api/metrics/definitions", response_model=list[MetricDescriptor])
async def list_metric_definitions(
    metric_service: MetricService = Depends(get_metric_service),
) -> list[MetricDescriptor]:
    """Retrieve all registered metric descriptors with parameters and engine availability.

    Parameters
    ----------
    metric_service : MetricService
        Injected metric service.

    Returns
    -------
    list of MetricDescriptor
        Registered metric descriptors.
    """
    return await metric_service.list_descriptors()


@router.post("/api/metric-executions", status_code=status.HTTP_200_OK)
async def submit_metric_execution(
    payload: ExecuteMetricRequest,
    metric_service: MetricService = Depends(get_metric_service),
    graph_service: GraphService = Depends(get_graph_service),
) -> Response:
    """Submit a metric calculation job with sub-250ms fast-path execution.

    If execution completes within 250ms, returns 200 OK with MetricResult.
    Otherwise schedules background calculation and returns 202 Accepted with polling URL.

    Parameters
    ----------
    payload : ExecuteMetricRequest
        Execution configuration.
    metric_service : MetricService
        Injected metric service.
    graph_service : GraphService
        Injected graph service.

    Returns
    -------
    Response
        200 OK with MetricResult or 202 Accepted with queued job status.
    """
    # Resolve graph snapshot
    graph_view: GraphView
    if payload.source == "neo4j":
        graph_view = await graph_service.get_neo4j_view()
    elif payload.run_id:
        graph_view = graph_service.get_run_graph(run_id=payload.run_id)
    else:
        try:
            reader = graph_service.require_reader()
            summaries = reader.list_runs(limit=1)
            if summaries:
                graph_view = graph_service.get_run_graph(run_id=summaries[0].run_id)
            else:
                graph_view = GraphView(
                    nodes=[],
                    edges=[],
                    source="fixture",
                    graph_version=payload.graph_version or "empty-v0",
                    schema_version="v1",
                )
        except Exception:
            graph_view = GraphView(
                nodes=[],
                edges=[],
                source="fixture",
                graph_version=payload.graph_version or "empty-v0",
                schema_version="v1",
            )

    if payload.graph_version:
        graph_view = graph_view.model_copy(update={"graph_version": payload.graph_version})

    job, completed_fast = await metric_service.submit_execution(
        metric_id=payload.metric_id,
        graph_view=graph_view,
        focus_node_id=payload.focus_node_id,
        params=payload.params,
        fast_path_timeout=0.250,
    )

    if completed_fast and job.result is not None:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=job.result.model_dump(mode="json"),
        )

    # 202 Accepted for long-running / asynchronous execution
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "execution_id": job.execution_id,
            "status": "queued",
            "status_url": f"/api/metric-executions/{job.execution_id}",
        },
    )


@router.get(
    "/api/metric-executions/{execution_id}",
    response_model=ExecutionStatusResponse,
)
async def get_metric_execution(
    execution_id: str,
    metric_service: MetricService = Depends(get_metric_service),
) -> ExecutionStatusResponse:
    """Check status and retrieve results of an async metric execution job.

    Parameters
    ----------
    execution_id : str
        Execution identifier.
    metric_service : MetricService
        Injected metric service.

    Returns
    -------
    ExecutionStatusResponse
        Current execution status and result if finished.

    Raises
    ------
    MetricExecutionNotFoundException
        If the execution ID is unknown (HTTP 404).
    """
    job = metric_service.get_execution(execution_id)
    if job is None:
        raise MetricExecutionNotFoundException(execution_id)

    status_str: Literal["queued", "running", "completed", "failed", "cancelled"]
    if job.status == ExecutionStatus.COMPLETED:
        status_str = "completed"
    elif job.status == ExecutionStatus.FAILED:
        status_str = "failed"
    elif job.status == ExecutionStatus.CANCELLED:
        status_str = "cancelled"
    elif job.status == ExecutionStatus.RUNNING:
        status_str = "running"
    else:
        status_str = "queued"

    return ExecutionStatusResponse(
        execution_id=job.execution_id,
        status=status_str,
        progress=job.progress,
        result=job.result,
        error=job.error,
    )


@router.delete("/api/metric-executions/{execution_id}")
async def cancel_metric_execution(
    execution_id: str,
    metric_service: MetricService = Depends(get_metric_service),
) -> dict[str, Any]:
    """Signal cooperative cancellation to an active metric execution.

    Parameters
    ----------
    execution_id : str
        Execution identifier.
    metric_service : MetricService
        Injected metric service.

    Returns
    -------
    dict of str to Any
        Cancellation acknowledgement.

    Raises
    ------
    MetricExecutionNotFoundException
        If the execution ID is unknown (HTTP 404).
    """
    cancelled = metric_service.cancel_execution(execution_id)
    if not cancelled:
        raise MetricExecutionNotFoundException(execution_id)

    return {
        "execution_id": execution_id,
        "status": "cancelled",
    }
