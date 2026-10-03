"""Configuration endpoints for viewing effective settings, profiles, and invalidation previews."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile

from episteme_studio.api.deps import get_config_service, get_settings
from episteme_studio.api.errors import (
    InvalidConfigPatchException,
    StudioProblemException,
)
from episteme_studio.settings import StudioSettings
from episteme_studio.domain.config import (
    AvailableInputDoc,
    ConfigPatch,
    ConfigView,
    InvalidationPreview,
    LangfuseStatusResponse,
    LangfuseTestRequest,
    PromptResolveRequest,
    PromptResolveResponse,
)
from episteme_studio.domain.errors import InvalidConfigPatchError
from episteme_studio.services.config_service import ConfigService

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/effective", response_model=ConfigView)
async def get_effective_config(
    profile_id: str | None = Query(
        default=None, description="Configuration profile identifier"
    ),
    config_service: ConfigService = Depends(get_config_service),
) -> ConfigView:
    """Retrieve the effective configuration with secrets masked and provenance mapped.

    Parameters
    ----------
    profile_id : str or None, optional
        Profile identifier to apply as base settings.
    config_service : ConfigService
        Injected configuration service.

    Returns
    -------
    ConfigView
        Masked configuration dictionary and provenance mapping.
    """
    return config_service.get_effective_config(profile_id=profile_id)


@router.get("/profiles", response_model=list[str])
async def list_profiles(
    config_service: ConfigService = Depends(get_config_service),
) -> list[str]:
    """List available configuration profile names.

    Parameters
    ----------
    config_service : ConfigService
        Injected configuration service.

    Returns
    -------
    list of str
        List of profile names.
    """
    return config_service.list_profiles()


@router.post("/invalidation-preview", response_model=InvalidationPreview)
async def preview_invalidation(
    payload: ConfigPatch,
    config_service: ConfigService = Depends(get_config_service),
) -> InvalidationPreview:
    """Preview cache and phase invalidation for a proposed configuration patch.

    Per D-14, changes targeting ``models.*`` produce zero phase invalidations,
    as model definitions are observability metadata rather than phase inputs.

    Parameters
    ----------
    payload : ConfigPatch
        Configuration patch payload with dot-delimited parameter updates.
    config_service : ConfigService
        Injected configuration service.

    Returns
    -------
    InvalidationPreview
        Report detailing invalidated vs reused phases and estimated artifact loss.

    Raises
    ------
    InvalidConfigPatchException
        If the patch fails validation or addresses invalid configuration keys.
    """
    try:
        return config_service.preview_invalidation(
            patch=payload.patch,
            profile_id=payload.profile_id,
            parent_run_id=payload.parent_run_id,
            source_paths=payload.source_paths,
            bib_paths=payload.bib_paths,
            structural_anchor=payload.structural_anchor,
        )
    except InvalidConfigPatchError as exc:
        raise InvalidConfigPatchException(str(exc)) from exc


@router.post("/prompts/resolve", response_model=PromptResolveResponse)
async def resolve_prompts(
    request: PromptResolveRequest,
    config_service: ConfigService = Depends(get_config_service),
) -> PromptResolveResponse:
    """Resolve structured prompt templates from Langfuse or local defaults.

    Parameters
    ----------
    request : PromptResolveRequest
        Provider name and target deployment label or version.
    config_service : ConfigService
        Injected configuration service.

    Returns
    -------
    PromptResolveResponse
        Resolved prompt bundles with templates, version metadata, and optional fallback warnings.
    """
    return config_service.resolve_prompts(
        provider=request.provider,
        label_or_version=request.label_or_version,
        prompts_dir=request.prompts_dir,
        host=request.host,
        public_key=request.public_key,
        secret_key=request.secret_key,
    )


@router.get("/inputs", response_model=list[AvailableInputDoc])
async def list_inputs(
    config_service: ConfigService = Depends(get_config_service),
) -> list[AvailableInputDoc]:
    """List candidate input documents available in the repository.

    Parameters
    ----------
    config_service : ConfigService
        Injected configuration service.

    Returns
    -------
    list of AvailableInputDoc
        Discovered corpus files.
    """
    return config_service.list_available_inputs()


@router.post("/inputs/upload", response_model=AvailableInputDoc)
async def upload_input(
    file: UploadFile = File(...),
    config_service: ConfigService = Depends(get_config_service),
    settings: StudioSettings = Depends(get_settings),
) -> AvailableInputDoc:
    """Upload a candidate input document into the workspace.

    Parameters
    ----------
    file : UploadFile
        Uploaded file payload.
    config_service : ConfigService
        Injected configuration service.
    settings : StudioSettings
        Injected application settings.

    Returns
    -------
    AvailableInputDoc
        Metadata record for the uploaded document ready for pipeline execution.

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
            detail="File upload is disabled on this read-only instance.",
            instance="/api/config/inputs/upload",
        )
    content = await file.read()
    return config_service.upload_input(file.filename or "uploaded_doc.txt", content)


@router.get("/langfuse/status", response_model=LangfuseStatusResponse)
async def get_langfuse_status(
    config_service: ConfigService = Depends(get_config_service),
) -> LangfuseStatusResponse:
    """Retrieve Langfuse connection status, credentials detection, and telemetry state.

    Parameters
    ----------
    config_service : ConfigService
        Injected configuration service.

    Returns
    -------
    LangfuseStatusResponse
        Status of Langfuse host, masked public key, and active telemetry.
    """
    return config_service.get_langfuse_status()


@router.post("/langfuse/test", response_model=LangfuseStatusResponse)
async def test_langfuse_connection(
    payload: LangfuseTestRequest,
    config_service: ConfigService = Depends(get_config_service),
    settings: StudioSettings = Depends(get_settings),
) -> LangfuseStatusResponse:
    """Test Langfuse server authentication with specified or default credentials.

    Parameters
    ----------
    payload : LangfuseTestRequest
        Optional host, public key, and secret key overrides to test.
    config_service : ConfigService
        Injected configuration service.
    settings : StudioSettings
        Injected application settings.

    Returns
    -------
    LangfuseStatusResponse
        Connection status and diagnostic message.
    """
    if settings.read_only:
        return LangfuseStatusResponse(
            connected=False,
            host=payload.host or "http://localhost:3000",
            public_key_configured=False,
            active_telemetry=False,
            message="Langfuse connection testing is disabled in read-only mode.",
        )
    return config_service.test_langfuse(
        host=payload.host,
        public_key=payload.public_key,
        secret_key=payload.secret_key,
    )
