"""System endpoints for health checks, server capabilities, and active schema discovery."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from episteme_studio.api.deps import get_engine_settings_service, get_settings
from episteme_studio.domain.overlays import OverlayKind
from episteme_studio.services.engine_settings_service import EngineSettingsService
from episteme_studio.settings import StudioSettings

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str = "ok"


class CapabilitiesResponse(BaseModel):
    """Server capability manifest indicating available subsystems."""

    artifacts: bool = Field(description="True if artifact store is available on disk.")
    neo4j: bool = Field(description="True if Neo4j driver connection is active.")
    execution: bool = Field(description="True if pipeline execution subsystem is enabled.")
    overlays: list[str] = Field(description="List of available or implemented overlay kinds.")


@router.get("/api/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Liveness check endpoint.

    Returns
    -------
    HealthResponse
        Status indicator.
    """
    return HealthResponse(status="ok")


@router.get("/api/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities(
    request: Request,
    settings: StudioSettings = Depends(get_settings),
) -> CapabilitiesResponse:
    """Retrieve server capabilities and active backend feature flags.

    Parameters
    ----------
    request : Request
        Incoming request to access application state.
    settings : StudioSettings
        Injected application settings.

    Returns
    -------
    CapabilitiesResponse
        Subsystem availability.
    """
    artifacts_available = settings.artifacts_dir.exists() or settings.demo_mode
    neo4j_available = bool(getattr(request.app.state, "neo4j_available", False))
    return CapabilitiesResponse(
        artifacts=artifacts_available,
        neo4j=neo4j_available,
        execution=settings.execution_enabled,
        overlays=[
            OverlayKind.GRADUAL_STRENGTH.value,
            OverlayKind.INTERNAL_CORRELATION.value,
            OverlayKind.DEGREE.value,
            OverlayKind.COMPONENT.value,
            OverlayKind.PAGERANK.value,
        ],
    )


@router.get("/api/schema")
async def get_schema(
    engine_service: EngineSettingsService = Depends(get_engine_settings_service),
) -> dict[str, Any]:
    """Retrieve the active SchemaConfig ontology definition.

    Returns
    -------
    dict of str to Any
        Dictionary containing entity types, relation types, polarities, and partitions.
    """
    mapper = await engine_service.get_schema_mapper()
    return mapper.to_dict()
