"""Endpoints for requesting, listing, and computing graph overlays."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from episteme_studio.api.deps import get_graph_service, get_overlay_service
from episteme_studio.api.errors import OverlayNotImplementedException
from episteme_studio.domain.errors import OverlayNotImplementedError
from episteme_studio.domain.graph import GraphView
from episteme_studio.domain.overlays import Overlay, OverlayKind
from episteme_studio.services.graph_service import GraphService
from episteme_studio.services.overlay_service import OverlayService

router = APIRouter(prefix="/api/overlays", tags=["overlays"])


class ComputeOverlayRequest(BaseModel):
    """Payload for requesting an overlay computation on a graph.

    Parameters
    ----------
    run_id : str or None, optional
        Target run identifier to retrieve graph snapshot from.
    graph_version : str or None, optional
        Optional explicit graph version fingerprint.
    kind : OverlayKind
        The algorithm kind to execute.
    source : Literal["artifacts", "neo4j"] or None, optional
        Source driver for the graph projection.
    params : dict of str to Any, optional
        Algorithmic parameters passed to the overlay computation.
    """

    run_id: str | None = None
    graph_version: str | None = None
    kind: OverlayKind
    source: Literal["artifacts", "neo4j"] | None = None
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=list[Overlay])
async def list_overlays(
    graph_version: str | None = Query(default=None, description="Filter by graph version"),
    overlay_service: OverlayService = Depends(get_overlay_service),
) -> list[Overlay]:
    """Retrieve previously computed and cached graph overlays.

    Parameters
    ----------
    graph_version : str or None, optional
        Optional filter for a specific graph version.
    overlay_service : OverlayService
        Injected overlay service.

    Returns
    -------
    list of Overlay
        List of cached overlays matching the filter.
    """
    return overlay_service.list_overlays(graph_version=graph_version)


@router.post("", response_model=Overlay)
async def compute_overlay(
    payload: ComputeOverlayRequest,
    overlay_service: OverlayService = Depends(get_overlay_service),
    graph_service: GraphService = Depends(get_graph_service),
) -> Overlay:
    """Compute a graph overlay or return a cached result.

    Parameters
    ----------
    payload : ComputeOverlayRequest
        Overlay request parameters.
    overlay_service : OverlayService
        Injected overlay service.
    graph_service : GraphService
        Injected graph service.

    Returns
    -------
    Overlay
        Computed or cached overlay.

    Raises
    ------
    OverlayNotImplementedException
        If the overlay kind is reserved or not implemented (HTTP 501).
    """
    if payload.kind in (OverlayKind.B_CONSISTENCY, OverlayKind.STABLE_EXTENSION):
        raise OverlayNotImplementedException(
            f"Overlay kind '{payload.kind.value}' is reserved and not implemented yet (D-12)."
        )

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

    try:
        return overlay_service.compute_overlay(
            graph=graph_view,
            kind=payload.kind,
            params=payload.params,
        )
    except OverlayNotImplementedError as exc:
        raise OverlayNotImplementedException(str(exc)) from exc
