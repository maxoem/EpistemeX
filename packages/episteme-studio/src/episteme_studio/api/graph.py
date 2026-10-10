"""API router exposing Neo4j graph projections, neighborhood expansion, and Cypher console endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from episteme_studio.api.deps import get_graph_service
from episteme_studio.domain.graph import CypherResult, GraphView
from episteme_studio.services.graph_service import GraphService

router = APIRouter(prefix="/api/graph", tags=["graph"])


class CypherRequest(BaseModel):
    """Payload for ad-hoc Cypher query execution.

    Parameters
    ----------
    query : str
        Cypher query statement to execute.
    params : dict of str to Any, optional
        Query parameters to bind.
    limit : int or None, optional
        Maximum row budget cap override.
    """

    query: str = Field(..., description="Cypher query string to execute in read-only transaction mode.")
    params: dict[str, Any] = Field(default_factory=dict, description="Key-value query parameter map.")
    limit: int | None = Field(default=None, description="Maximum returned rows before raising result-too-large.")


@router.get("/view", response_model=GraphView)
async def get_graph_view(
    limit: int = Query(500, description="Node budget limit."),
    layer: int | None = Query(None, description="Optional filter for Layer 1, 2, or 3."),
    service: GraphService = Depends(get_graph_service),
) -> GraphView:
    """Retrieve full or layer-filtered GraphView projected from Neo4j.

    Parameters
    ----------
    limit : int, default 500
        Maximum node count budget.
    layer : int or None, optional
        Optional layer filter.
    service : GraphService
        Injected graph coordination service.

    Returns
    -------
    GraphView
        Materialized graph projection with polarity resolution and budget metadata.
    """
    return await service.get_neo4j_view(budget=limit, layer=layer)


@router.get("/expand", response_model=GraphView)
async def expand_graph(
    seeds: list[str] = Query(..., description="List of seed node IDs to expand from."),
    depth: int = Query(1, ge=1, le=5, description="Expansion hop depth (1 to 5)."),
    limit: int = Query(500, description="Node budget limit."),
    service: GraphService = Depends(get_graph_service),
) -> GraphView:
    """Expand k-hop neighborhood from seed node identifiers.

    Parameters
    ----------
    seeds : list of str
        Seed node IDs.
    depth : int, default 1
        Traversal depth between 1 and 5.
    limit : int, default 500
        Maximum node budget limit.
    service : GraphService
        Injected graph coordination service.

    Returns
    -------
    GraphView
        Sub-graph view containing seeds, neighbors, and interconnected relationships.
    """
    return await service.expand_neo4j_graph(seeds=seeds, depth=depth, budget=limit)


@router.post("/cypher", response_model=CypherResult)
async def execute_cypher(
    payload: CypherRequest,
    service: GraphService = Depends(get_graph_service),
) -> CypherResult:
    """Execute a read-only Cypher query against Neo4j with timeout and row cap enforcement.

    Parameters
    ----------
    payload : CypherRequest
        Cypher statement and query parameters.
    service : GraphService
        Injected graph coordination service.

    Returns
    -------
    CypherResult
        Tabular execution result including columns, rows, and latency.
    """
    return await service.execute_cypher(
        query=payload.query,
        params=payload.params,
        limit=payload.limit,
    )


class Neo4jConnectPayload(BaseModel):
    """Payload to dynamically test and establish an in-session Neo4j connection.

    Parameters
    ----------
    url : str
        Bolt URI, e.g. 'bolt://localhost:7687' or 'neo4j://127.0.0.1:7687'.
    user : str or None, optional
        Neo4j username (e.g. 'neo4j').
    password : str or None, optional
        Neo4j password.
    database : str or None, optional
        Target database name (default: 'neo4j').
    """

    url: str = Field(..., description="Bolt URI for Neo4j database.")
    user: str | None = Field(default=None, description="Neo4j authentication user.")
    password: str | None = Field(default=None, description="Neo4j authentication password.")
    database: str | None = Field(default=None, description="Target Neo4j database.")


class Neo4jConnectResponse(BaseModel):
    """Response returned upon establishing or testing Neo4j connection.

    Parameters
    ----------
    status : str
        Status message, e.g. 'connected'.
    neo4j : bool
        True if connection succeeded and driver is active.
    url : str
        The connected Bolt URI.
    database : str or None, optional
        The connected database name.
    """

    status: str
    neo4j: bool
    url: str
    database: str | None = None


class Neo4jStatusResponse(BaseModel):
    """Response indicating the current Neo4j connection status.

    Parameters
    ----------
    connected : bool
        True if Neo4j driver connection is currently active and healthy.
    url : str or None, optional
        The connected Bolt URI.
    database : str or None, optional
        The active database name.
    """

    connected: bool
    url: str | None = None
    database: str | None = None


@router.get("/status", response_model=Neo4jStatusResponse)
async def get_neo4j_status(request: Request) -> Neo4jStatusResponse:
    """Retrieve the current Neo4j driver connection status and parameters.

    Parameters
    ----------
    request : Request
        Incoming request to access application state.

    Returns
    -------
    Neo4jStatusResponse
        Current connection state.
    """
    connected = bool(getattr(request.app.state, "neo4j_available", False))
    settings = getattr(request.app.state, "settings", None)
    return Neo4jStatusResponse(
        connected=connected,
        url=settings.neo4j_url if settings and connected else None,
        database=settings.neo4j_database if settings and connected else None,
    )


@router.post("/connect", response_model=Neo4jConnectResponse)
async def connect_neo4j(
    payload: Neo4jConnectPayload,
    request: Request,
) -> Neo4jConnectResponse:
    """Test and dynamically establish an in-session Neo4j driver connection.

    Parameters
    ----------
    payload : Neo4jConnectPayload
        Connection parameters.
    request : Request
        Incoming request to access application state.

    Returns
    -------
    Neo4jConnectResponse
        Connection confirmation status.

    Raises
    ------
    StudioProblemException
        If the connection cannot be established or verified.
    """
    from episteme_studio.adapters.neo4j_reader import Neo4jReader
    from episteme_studio.api.errors import StudioProblemException
    from episteme_studio.domain.errors import Neo4jUnavailableError

    try:
        driver = await Neo4jReader.create_and_verify_driver(
            url=payload.url,
            user=payload.user,
            password=payload.password,
            timeout_seconds=3.0,
        )
    except Neo4jUnavailableError as err:
        raise StudioProblemException(
            status=400,
            title="Neo4j Connection Failed",
            type="neo4j-connection-failed",
            detail=str(err),
        )

    # Close previous driver if present
    old_driver = getattr(request.app.state, "neo4j_driver", None)
    if old_driver is not None:
        try:
            await old_driver.close()
        except Exception:
            pass

    request.app.state.neo4j_driver = driver
    request.app.state.neo4j_available = True

    # Update runtime settings in-memory
    settings = getattr(request.app.state, "settings", None)
    if settings:
        settings.neo4j_url = payload.url
        settings.neo4j_user = payload.user
        settings.neo4j_password = payload.password
        settings.neo4j_database = payload.database

    return Neo4jConnectResponse(
        status="connected",
        neo4j=True,
        url=payload.url,
        database=payload.database,
    )


@router.post("/disconnect")
async def disconnect_neo4j(request: Request) -> dict[str, Any]:
    """Disconnect active Neo4j driver connection and reset session state.

    Parameters
    ----------
    request : Request
        Incoming request to access application state.

    Returns
    -------
    dict of str to Any
        Confirmation payload with status 'disconnected'.
    """
    old_driver = getattr(request.app.state, "neo4j_driver", None)
    if old_driver is not None:
        try:
            await old_driver.close()
        except Exception:
            pass

    request.app.state.neo4j_driver = None
    request.app.state.neo4j_available = False

    settings = getattr(request.app.state, "settings", None)
    if settings:
        settings.neo4j_url = None
        settings.neo4j_user = None
        settings.neo4j_password = None
        settings.neo4j_database = None

    return {"status": "disconnected", "neo4j": False}
