"""Domain models for pipeline configuration views, patch requests, and invalidation previews."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FieldProvenance(StrEnum):
    """Origin of a configuration parameter value."""

    DEFAULT = "default"
    ENV = "env"
    PROFILE = "profile"
    OVERRIDE = "override"


class ConfigView(BaseModel):
    """Effective pipeline configuration with secret redaction and provenance.

    Parameters
    ----------
    values : dict of str to Any
        Resolved configuration tree with secrets masked as '***'.
    provenance : dict of str to FieldProvenance
        Mapping from dot-delimited configuration key paths to their origin source.
    profile_id : str or None, optional
        Base profile name if resolved from a configuration profile.
    schema_version : str
        Version string of the active graph schema.
    """

    values: dict[str, Any]
    provenance: dict[str, FieldProvenance]
    profile_id: str | None = None
    schema_version: str


class ConfigPatch(BaseModel):
    """Patch payload for staging or starting a modified pipeline run.

    Parameters
    ----------
    profile_id : str or None, optional
        Base profile identifier to inherit defaults from.
    patch : dict of str to Any, optional
        Key-value overrides specified as dot-delimited paths.
    parent_run_id : str or None, optional
        Identifier of parent run to evaluate invalidation against.
    source_paths : list of str or None, optional
        Proposed input source paths to check for input invalidation.
    bib_paths : list of str or None, optional
        Proposed bibliography paths.
    structural_anchor : Any or None, optional
        Proposed structural anchor to check for anchor invalidation.
    """

    profile_id: str | None = None
    patch: dict[str, Any] = Field(default_factory=dict)
    parent_run_id: str | None = None
    source_paths: list[str] | None = None
    bib_paths: list[str] | None = None
    structural_anchor: Any | None = None


class InvalidationPreview(BaseModel):
    """Dry-run impact analysis of a configuration patch on cache invalidation.

    Parameters
    ----------
    invalidated_phases : list of int
        List of phase ordinals that will require re-execution.
    reused_phases : list of int
        List of phase ordinals whose cached artifacts can be safely reused.
    changed_fingerprints : dict of str to tuple of (str or None, str or None)
        Map of phase identifier to before/after fingerprint pairs.
    reason : str
        Human-readable explanation of why invalidation occurred.
    estimated_artifact_loss : int
        Estimated count of cached artifacts that will be invalidated.
    """

    invalidated_phases: list[int]
    reused_phases: list[int]
    changed_fingerprints: dict[str, tuple[str | None, str | None]]
    reason: str
    estimated_artifact_loss: int


class PromptResolveRequest(BaseModel):
    """Request payload for resolving structured prompt templates.

    Parameters
    ----------
    provider : str, default "default"
        Prompt provider to query ('default', 'langfuse', 'file').
    label_or_version : str or int, default "production"
        Deployment label (e.g. 'production', 'staging') or integer version tag.
    prompts_dir : str or None, optional
        Filesystem directory path when provider is 'file'.
    host : str or None, optional
        Custom Langfuse host URL.
    public_key : str or None, optional
        Candidate Langfuse public key.
    secret_key : str or None, optional
        Candidate Langfuse secret key.
    """

    provider: str = "default"
    label_or_version: str = "production"
    prompts_dir: str | None = None
    host: str | None = None
    public_key: str | None = None
    secret_key: str | None = None


class LangfuseTestRequest(BaseModel):
    """Payload for testing Langfuse server connectivity and authentication.

    Parameters
    ----------
    host : str or None, optional
        Target Langfuse host URL.
    public_key : str or None, optional
        Candidate public API key.
    secret_key : str or None, optional
        Candidate secret API key.
    """

    host: str | None = None
    public_key: str | None = None
    secret_key: str | None = None


class ResolvedPromptItem(BaseModel):
    """Resolved prompt bundle item carrying templates and version metadata.

    Parameters
    ----------
    name : str
        Canonical prompt bundle identifier.
    version : int or None, optional
        Monotonic version number if tracked by provider.
    label : str or None, optional
        Deployment label (e.g. 'production').
    provider : str
        Source provider ('default', 'langfuse', 'file', 'override').
    direct_template : str
        Primary extraction/reasoning prompt template.
    reasoning_template : str or None, optional
        Intermediate chain-of-thought reasoning template.
    format_template : str or None, optional
        Structured JSON/format constraint template.
    gleaning_template : str or None, optional
        Follow-up gleaning pass prompt template.
    metadata : dict of str to Any, optional
        Associated hyperparameters or tags.
    """

    name: str
    version: int | None = None
    label: str | None = None
    provider: str = "default"
    direct_template: str
    reasoning_template: str | None = None
    format_template: str | None = None
    gleaning_template: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptResolveResponse(BaseModel):
    """Response payload containing all resolved prompt bundles.

    Parameters
    ----------
    provider : str
        Active prompt provider used to resolve bundles.
    label_or_version : str
        Requested deployment label or version.
    bundles : dict of str to ResolvedPromptItem
        Dictionary mapping canonical prompt names to their resolved templates.
    warning : str or None, optional
        Fallback warning message if provider encountered errors or was unreachable.
    """

    provider: str
    label_or_version: str
    bundles: dict[str, ResolvedPromptItem] = Field(default_factory=dict)
    warning: str | None = None


class AvailableInputDoc(BaseModel):
    """Candidate source document discovered in the repository.

    Parameters
    ----------
    path : str
        Relative or absolute file path.
    name : str
        Display filename.
    size_bytes : int
        File size in bytes.
    description : str or None, optional
        Contextual description of the input dataset.
    """

    path: str
    name: str
    size_bytes: int = 0
    description: str | None = None


class LangfuseStatusResponse(BaseModel):
    """Langfuse connection and telemetry observability status.

    Parameters
    ----------
    configured : bool
        Whether public and secret keys are configured in the environment.
    host : str
        Configured Langfuse host URL.
    has_public_key : bool
        Whether LANGFUSE_PUBLIC_KEY is set.
    public_key_preview : str or None, optional
        Masked public key prefix for verification (e.g. 'pk-lf-***').
    has_secret_key : bool
        Whether LANGFUSE_SECRET_KEY is set.
    telemetry_enabled : bool
        Whether runtime telemetry is enabled.
    connected : bool, default False
        Whether an auth check against the host succeeded.
    message : str or None, optional
        Informational status message or error details.
    """

    configured: bool
    host: str
    has_public_key: bool
    public_key_preview: str | None = None
    has_secret_key: bool
    telemetry_enabled: bool
    connected: bool = False
    message: str | None = None
