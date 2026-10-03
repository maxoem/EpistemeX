"""API endpoints for engine settings, schema customization, and open-vocabulary predicate resolution."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends

from episteme_studio.api.deps import get_engine_settings_service, get_settings
from episteme_studio.api.errors import StudioProblemException
from episteme_studio.domain.engine import (
    DecisionEngineStatusResponse,
    DecisionTestRequest,
    DecisionTestResponse,
    EngineSettings,
    EngineSettingsPatch,
    PredicateMapping,
    UnmappedPredicateInfo,
)
from episteme_studio.services.engine_settings_service import EngineSettingsService
from episteme_studio.settings import StudioSettings

router = APIRouter(prefix="/api/engine", tags=["engine"])


@router.get("/settings", response_model=EngineSettings)
async def get_engine_settings(
    service: EngineSettingsService = Depends(get_engine_settings_service),
) -> EngineSettings:
    """Retrieve the active engine settings, including ontology schema, aliases, and model defaults.

    Returns
    -------
    EngineSettings
        Active engine settings.
    """
    return await service.get_settings()


@router.put("/settings", response_model=EngineSettings)
async def update_engine_settings(
    patch: EngineSettingsPatch,
    service: EngineSettingsService = Depends(get_engine_settings_service),
    settings: StudioSettings = Depends(get_settings),
) -> EngineSettings:
    """Update and persist engine settings (schema modifications, aliases, model defaults).

    Parameters
    ----------
    patch : EngineSettingsPatch
        Partial configuration update.
    service : EngineSettingsService
        Injected engine settings service.
    settings : StudioSettings
        Injected application settings.

    Returns
    -------
    EngineSettings
        Persisted engine settings.

    Raises
    ------
    StudioProblemException
        If the instance is operating in read-only mode.
    """
    if settings.read_only:
        raise StudioProblemException(
            type="read-only-mode",
            title="Read-Only Mode",
            status=403,
            detail="Updating engine settings is disabled on this read-only instance.",
            instance="/api/engine/settings",
        )
    return await service.update_settings(patch)


@router.post("/settings/reset", response_model=EngineSettings)
async def reset_engine_settings(
    service: EngineSettingsService = Depends(get_engine_settings_service),
    settings: StudioSettings = Depends(get_settings),
) -> EngineSettings:
    """Reset engine settings back to pipeline factory defaults.

    Parameters
    ----------
    service : EngineSettingsService
        Injected engine settings service.
    settings : StudioSettings
        Injected application settings.

    Returns
    -------
    EngineSettings
        Clean factory engine settings.

    Raises
    ------
    StudioProblemException
        If the instance is operating in read-only mode.
    """
    if settings.read_only:
        raise StudioProblemException(
            type="read-only-mode",
            title="Read-Only Mode",
            status=403,
            detail="Resetting engine settings is disabled on this read-only instance.",
            instance="/api/engine/settings/reset",
        )
    return await service.reset_settings()


@router.get("/schema")
async def get_engine_schema(
    service: EngineSettingsService = Depends(get_engine_settings_service),
) -> dict[str, Any]:
    """Retrieve the serialized ontology dictionary for the active engine schema.

    Returns
    -------
    dict of str to Any
        Active ontology specification with definitions, polarities, partitions, and aliases.
    """
    mapper = await service.get_schema_mapper()
    return mapper.to_dict()


@router.get("/unmapped-predicates", response_model=list[UnmappedPredicateInfo])
async def get_unmapped_predicates(
    service: EngineSettingsService = Depends(get_engine_settings_service),
) -> list[UnmappedPredicateInfo]:
    """Retrieve unmapped predicates observed in historical runs.

    Returns
    -------
    list of UnmappedPredicateInfo
        Aggregated unmapped predicates and frequencies.
    """
    return await service.discover_unmapped_predicates()


@router.post("/map-predicate", response_model=EngineSettings)
async def map_unmapped_predicate(
    mapping: PredicateMapping,
    service: EngineSettingsService = Depends(get_engine_settings_service),
    settings: StudioSettings = Depends(get_settings),
) -> EngineSettings:
    """Assign an open-vocabulary predicate to a dialectical polarity or canonical relation.

    Parameters
    ----------
    mapping : PredicateMapping
        Predicate mapping rule.

    Returns
    -------
    EngineSettings
        Updated engine settings reflecting the new mapping.
    """
    if settings.read_only:
        raise StudioProblemException(
            type="read-only-mode",
            title="Read-Only Mode",
            status=403,
            detail="Mapping predicates is disabled on this read-only instance.",
            instance="/api/engine/map-predicate",
        )
    return await service.map_predicate(mapping)


@router.get("/decision/status", response_model=DecisionEngineStatusResponse)
async def get_decision_engine_status(
    service: EngineSettingsService = Depends(get_engine_settings_service),
) -> DecisionEngineStatusResponse:
    """Retrieve hardware capabilities, MLX status, and checkpoint cache state for the Decision Engine.

    Returns
    -------
    DecisionEngineStatusResponse
        Status and discovery report.
    """
    return await service.get_decision_status()


@router.post("/decision/test", response_model=DecisionTestResponse)
async def test_decision_engine(
    request: DecisionTestRequest,
    service: EngineSettingsService = Depends(get_engine_settings_service),
) -> DecisionTestResponse:
    """Execute an isolated sandboxed test of a System 1 decision primitive.

    Parameters
    ----------
    request : DecisionTestRequest
        Sandbox test payload.

    Returns
    -------
    DecisionTestResponse
        Decision evaluation result.
    """
    return await service.test_decision(request)
