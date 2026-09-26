"""FastAPI dependency providers for settings, stores, and execution services."""

from __future__ import annotations

from typing import cast
from fastapi import Depends, Request

from episteme_studio.runtime.broker import EventBroker
from episteme_studio.runtime.executor import PipelineExecutor
from episteme_studio.runtime.registry import RunRegistry
from episteme_studio.services.run_service import RunService
from episteme_studio.settings import StudioSettings


def get_settings(request: Request) -> StudioSettings:
    """Retrieve StudioSettings stored on the FastAPI application state.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    StudioSettings
        The active configuration.
    """
    return cast(StudioSettings, request.app.state.settings)


def get_broker(request: Request) -> EventBroker:
    """Retrieve the EventBroker instance from application state.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    EventBroker
        Shared event broker.
    """
    if not hasattr(request.app.state, "broker") or request.app.state.broker is None:
        request.app.state.broker = EventBroker()
    return cast(EventBroker, request.app.state.broker)


def get_registry(request: Request) -> RunRegistry:
    """Retrieve the RunRegistry instance from application state.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    RunRegistry
        In-memory run registry.
    """
    if not hasattr(request.app.state, "registry") or request.app.state.registry is None:
        request.app.state.registry = RunRegistry()
    return cast(RunRegistry, request.app.state.registry)


def get_executor(request: Request) -> PipelineExecutor:
    """Retrieve the PipelineExecutor instance from application state.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    PipelineExecutor
        Subprocess execution manager.
    """
    if not hasattr(request.app.state, "executor") or request.app.state.executor is None:
        broker = get_broker(request)
        registry = get_registry(request)
        request.app.state.executor = PipelineExecutor(registry, broker)
    return cast(PipelineExecutor, request.app.state.executor)


def get_run_service(
    settings: StudioSettings = Depends(get_settings),
    registry: RunRegistry = Depends(get_registry),
    executor: PipelineExecutor = Depends(get_executor),
) -> RunService:
    """Dependency provider for RunService.

    Parameters
    ----------
    settings : StudioSettings
        Current application settings.
    registry : RunRegistry
        Run handle registry.
    executor : PipelineExecutor
        Subprocess pipeline executor.

    Returns
    -------
    RunService
        Instantiated run service.
    """
    return RunService.from_settings(settings, registry=registry, executor=executor)


def get_neo4j_reader(request: Request) -> Neo4jReader:
    """Retrieve Neo4jReader using the driver stored on application state.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    Neo4jReader
        Configured Neo4j reader.

    Raises
    ------
    Neo4jUnavailableException
        If Neo4j is not available or driver is not configured.
    """
    from episteme_studio.adapters.neo4j_reader import Neo4jReader
    from episteme_studio.api.errors import Neo4jUnavailableException

    driver = getattr(request.app.state, "neo4j_driver", None)
    if driver is None:
        raise Neo4jUnavailableException("Neo4j is not configured or offline.")
    settings = get_settings(request)
    return Neo4jReader(driver=driver, database=settings.neo4j_database)


def get_graph_service(
    request: Request,
    settings: StudioSettings = Depends(get_settings),
) -> GraphService:
    """Dependency provider for GraphService.

    Parameters
    ----------
    request : Request
        Incoming request.
    settings : StudioSettings
        Current application settings.

    Returns
    -------
    GraphService
        Service coordinating graph operations.
    """
    from episteme_studio.adapters.neo4j_reader import Neo4jReader
    from episteme_studio.services.graph_service import GraphService

    driver = getattr(request.app.state, "neo4j_driver", None)
    neo4j_reader = (
        Neo4jReader(driver=driver, database=settings.neo4j_database)
        if driver is not None
        else None
    )
    return GraphService.from_settings(settings=settings, neo4j_reader=neo4j_reader)


def get_overlay_service(request: Request) -> Any:
    """Retrieve the OverlayService instance from application state.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    OverlayService
        Shared overlay service.
    """
    from episteme_studio.services.overlay_service import OverlayService

    if not hasattr(request.app.state, "overlay_service") or request.app.state.overlay_service is None:
        request.app.state.overlay_service = OverlayService()
    return cast(OverlayService, request.app.state.overlay_service)


def get_config_service(
    request: Request,
    settings: StudioSettings = Depends(get_settings),
) -> Any:
    """Retrieve the ConfigService instance from application state.

    Parameters
    ----------
    request : Request
        Incoming request.
    settings : StudioSettings
        Current application settings.

    Returns
    -------
    ConfigService
        Shared configuration service.
    """
    from episteme_studio.adapters.artifact_reader import ArtifactReader
    from episteme_studio.services.config_service import ConfigService

    if not hasattr(request.app.state, "config_service") or request.app.state.config_service is None:
        reader = ArtifactReader(
            runs_dir=settings.runs_dir,
            artifacts_dir=settings.artifacts_dir,
            langfuse_host=settings.langfuse_host,
        )
        request.app.state.config_service = ConfigService(reader=reader)
    return cast(ConfigService, request.app.state.config_service)


def get_metric_service(request: Request) -> Any:
    """Retrieve the MetricService instance from application state.

    Parameters
    ----------
    request : Request
        Incoming request.

    Returns
    -------
    MetricService
        Shared metric service.
    """
    from episteme_studio.adapters.neo4j_reader import Neo4jReader
    from episteme_studio.services.metric_service import MetricService

    if not hasattr(request.app.state, "metric_service") or request.app.state.metric_service is None:
        driver = getattr(request.app.state, "neo4j_driver", None)
        settings = get_settings(request)
        reader = (
            Neo4jReader(driver=driver, database=settings.neo4j_database)
            if driver is not None
            else None
        )
        request.app.state.metric_service = MetricService(neo4j_reader=reader)
    else:
        driver = getattr(request.app.state, "neo4j_driver", None)
        settings = get_settings(request)
        reader = (
            Neo4jReader(driver=driver, database=settings.neo4j_database)
            if driver is not None
            else None
        )
        request.app.state.metric_service.set_neo4j_reader(reader)

    return cast(MetricService, request.app.state.metric_service)


def get_engine_settings_service(
    request: Request,
    settings: StudioSettings = Depends(get_settings),
) -> Any:
    """Retrieve the EngineSettingsService instance from application state.

    Parameters
    ----------
    request : Request
        Incoming request.
    settings : StudioSettings
        Current application settings.

    Returns
    -------
    EngineSettingsService
        Shared engine settings service.
    """
    from episteme_studio.adapters.artifact_reader import ArtifactReader
    from episteme_studio.adapters.engine_storage import FileEngineSettingsStorage
    from episteme_studio.services.engine_settings_service import EngineSettingsService

    if not hasattr(request.app.state, "engine_settings_service") or request.app.state.engine_settings_service is None:
        reader = ArtifactReader(
            runs_dir=settings.runs_dir,
            artifacts_dir=settings.artifacts_dir,
            langfuse_host=settings.langfuse_host,
        )
        storage_file = (
            settings.runs_dir.parent / ".pipeline_engine_settings.json"
            if settings.runs_dir
            else None
        )
        storage = FileEngineSettingsStorage(storage_file)
        request.app.state.engine_settings_service = EngineSettingsService(
            storage=storage,
            reader=reader,
        )
    return cast(EngineSettingsService, request.app.state.engine_settings_service)


def get_evaluation_service(
    request: Request,
    settings: StudioSettings = Depends(get_settings),
) -> Any:
    """Retrieve the EvaluationService instance from application state.

    Parameters
    ----------
    request : Request
        Incoming request.
    settings : StudioSettings
        Current application settings.

    Returns
    -------
    EvaluationService
        Configured evaluation service.
    """
    from episteme_studio.services.evaluation_service import EvaluationService

    if not hasattr(request.app.state, "evaluation_service") or request.app.state.evaluation_service is None:
        request.app.state.evaluation_service = EvaluationService.from_settings(settings)
    return request.app.state.evaluation_service

