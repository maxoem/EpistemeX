"""Endpoints for browsing, inspecting, executing, and streaming pipeline runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse

from episteme_studio.api.deps import (
    get_broker,
    get_evaluation_service,
    get_run_service,
    get_settings,
)
from episteme_studio.domain.evaluation import EvaluationReportDetail
from episteme_studio.domain.graph import GraphView
from episteme_studio.domain.runs import (
    ArtifactRef,
    EvidenceTrail,
    RunDetail,
    RunSummary,
    StartRunRequest,
)
from episteme_studio.runtime.broker import EventBroker
from episteme_studio.services.evaluation_service import EvaluationService
from episteme_studio.services.graph_service import GraphService
from episteme_studio.services.run_service import RunService
from episteme_studio.settings import StudioSettings

router = APIRouter(prefix="/api/runs", tags=["runs"])


def get_graph_service(settings: StudioSettings = Depends(get_settings)) -> GraphService:
    """Dependency provider for GraphService.

    Parameters
    ----------
    settings : StudioSettings
        Current application settings.

    Returns
    -------
    GraphService
        Instantiated graph service.
    """
    return GraphService.from_settings(settings)


@router.get("", response_model=list[RunSummary])
async def list_runs(service: RunService = Depends(get_run_service)) -> list[RunSummary]:
    """List all available pipeline runs.

    Parameters
    ----------
    service : RunService
        Injected run service.

    Returns
    -------
    list of RunSummary
        Discovered run summaries.
    """
    return service.list_runs()


@router.post("", response_model=RunSummary, status_code=201)
async def create_run(
    request: StartRunRequest,
    service: RunService = Depends(get_run_service),
) -> RunSummary:
    """Initiate a new pipeline run in a dedicated subprocess (D-05, D-27).

    Parameters
    ----------
    request : StartRunRequest
        Run configuration and source paths.
    service : RunService
        Injected run service.

    Returns
    -------
    RunSummary
        Created run summary.
    """
    return service.start_run(request)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, service: RunService = Depends(get_run_service)) -> RunDetail:
    """Retrieve full detail for a run manifest by identifier.

    Parameters
    ----------
    run_id : str
        Unique run ID.
    service : RunService
        Injected run service.

    Returns
    -------
    RunDetail
        Full run manifest and phase metadata.
    """
    return service.get_run(run_id)


@router.post("/{run_id}/cancel", response_model=RunSummary)
async def cancel_run(
    run_id: str,
    service: RunService = Depends(get_run_service),
) -> RunSummary:
    """Cancel an active pipeline run and terminate its subprocess.

    Parameters
    ----------
    run_id : str
        Run identifier to abort.
    service : RunService
        Injected run service.

    Returns
    -------
    RunSummary
        Updated run summary in aborted status.
    """
    return await service.cancel_run(run_id)


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    since: int | None = Query(None, description="Sequence number threshold to replay after"),
    broker: EventBroker = Depends(get_broker),
    service: RunService = Depends(get_run_service),
) -> EventSourceResponse:
    """Stream real-time telemetry events via Server-Sent Events (SSE).

    Replays buffered history on initial connect or reconnect using ``Last-Event-ID``
    or ``since`` query parameter, then streams live events as emitted.

    Parameters
    ----------
    run_id : str
        Run identifier.
    request : Request
        Incoming HTTP request.
    since : int or None, optional
        Threshold sequence number.
    broker : EventBroker
        Telemetry event broker.
    service : RunService
        Run service.

    Returns
    -------
    EventSourceResponse
        SSE stream of StudioEvents.
    """
    # Verify run existence in registry or disk
    service.get_run(run_id)

    last_event_id = request.headers.get("last-event-id")
    since_seq = since
    if last_event_id and last_event_id.isdigit():
        since_seq = int(last_event_id)

    async def event_generator():
        async for event in broker.subscribe(run_id, since_seq=since_seq):
            if await request.is_disconnected():
                break
            yield {
                "id": str(event.seq),
                "event": "message",
                "data": event.model_dump_json(),
            }

    return EventSourceResponse(event_generator())


@router.get("/{run_id}/graph", response_model=GraphView)
async def get_run_graph(
    run_id: str,
    budget: int | None = None,
    use_run_schema: bool = False,
    service: GraphService = Depends(get_graph_service),
) -> GraphView:
    """Materialize GraphView projection from run artifacts.

    Parameters
    ----------
    run_id : str
        Run identifier.
    budget : int or None, optional
        Element budget override.
    use_run_schema : bool, default False
        Whether to evaluate under run's embedded schema snapshot.
    service : GraphService
        Injected graph service.

    Returns
    -------
    GraphView
        Nodes and edges across L1, L2, and L3.
    """
    return service.get_run_graph(run_id, budget=budget, use_run_schema=use_run_schema)


@router.get("/{run_id}/artifacts", response_model=list[ArtifactRef])
async def list_run_artifacts(
    run_id: str,
    kind: str | None = None,
    service: RunService = Depends(get_run_service),
) -> list[ArtifactRef]:
    """List artifact envelopes for a run, optionally filtered by kind.

    Parameters
    ----------
    run_id : str
        Run identifier.
    kind : str or None, optional
        Filter by artifact kind.
    service : RunService
        Injected run service.

    Returns
    -------
    list of ArtifactRef
        Artifact references.
    """
    return service.list_artifacts(run_id, kind=kind)


@router.get("/{run_id}/evidence/{node_id}", response_model=EvidenceTrail)
async def get_node_evidence(
    run_id: str,
    node_id: str,
    service: GraphService = Depends(get_graph_service),
) -> EvidenceTrail:
    """Trace node grounding back to source L1 text chunks.

    Parameters
    ----------
    run_id : str
        Run identifier.
    node_id : str
        Node identifier.
    service : GraphService
        Injected graph service.

    Returns
    -------
    EvidenceTrail
        Grounding chunks with highlighted spans and extraction modes.
    """
    return service.get_evidence(run_id, node_id)


@router.get("/{run_id}/langfuse")
async def get_run_langfuse_stats(
    run_id: str,
    host: str | None = Query(None, description="Langfuse host override"),
    public_key: str | None = Query(None, description="Langfuse public key override"),
    secret_key: str | None = Query(None, description="Langfuse secret key override"),
    limit: int = Query(250, description="Maximum observations to return"),
    service: RunService = Depends(get_run_service),
) -> dict:
    """Retrieve Langfuse observation metrics and generation traces for a run.

    Parameters
    ----------
    run_id : str
        Run identifier.
    host : str or None, optional
        Langfuse host override.
    public_key : str or None, optional
        Langfuse public key override.
    secret_key : str or None, optional
        Langfuse secret key override.
    limit : int, default 250
        Maximum observations to return.
    service : RunService
        Injected run service.

    Returns
    -------
    dict
        Parsed observations and trace summary.
    """
    return service.get_run_langfuse_stats(
        run_id, host=host, public_key=public_key, secret_key=secret_key, limit=limit
    )


@router.get("/{run_id}/evaluation", response_model=EvaluationReportDetail | None)
async def get_run_evaluation(
    run_id: str,
    eval_service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportDetail | None:
    """Retrieve evaluation report associated with this run, if available.

    Parameters
    ----------
    run_id : str
        Run identifier.
    eval_service : EvaluationService
        Evaluation service.

    Returns
    -------
    EvaluationReportDetail or None
        Evaluation report detail if evaluated, None otherwise.
    """
    return eval_service.get_run_evaluation(run_id)

