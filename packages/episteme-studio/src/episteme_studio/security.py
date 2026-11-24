"""Security guards and validation logic for GLP Studio."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .settings import StudioSettings

_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class SecurityConfigurationError(ValueError):
    """Raised when server security invariants are violated."""


def validate_host_and_token(settings: StudioSettings) -> None:
    """Ensure non-loopback bindings are protected by an authentication token.

    Parameters
    ----------
    settings : StudioSettings
        The studio configuration to validate.

    Raises
    ------
    SecurityConfigurationError
        If host is non-loopback and token is not provided (unless in demo_mode or read_only mode).
    """
    if settings.demo_mode or settings.read_only:
        return

    if not settings.is_loopback() and not settings.token:
        raise SecurityConfigurationError(
            f"Cannot bind to external interface '{settings.host}' without setting "
            f"EPISTEME_STUDIO_TOKEN. Please set the token or bind to 127.0.0.1."
        )


def validate_safe_identifier(value: str, label: str = "identifier") -> str:
    """Validate that an identifier is safe to embed in a single path segment.

    Parameters
    ----------
    value : str
        Identifier string to validate.
    label : str, default 'identifier'
        Human-readable label included in error messages.

    Returns
    -------
    str
        The validated identifier string.

    Raises
    ------
    ValueError
        If the identifier is empty, represents a dot directory, contains path
        separators or null bytes, or contains characters outside
        ``[A-Za-z0-9._-]``.
    """
    if (
        not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
        or not _SAFE_IDENTIFIER_RE.match(value)
    ):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def resolve_safe_child(
    base_dir: Path | str,
    *parts: str | Path,
    allow_base: bool = False,
) -> Path:
    """Resolve a path under a base directory and enforce containment.

    Parameters
    ----------
    base_dir : Path or str
        Trusted root directory that the resolved path must remain within.
    *parts : str or Path
        Relative path segments joined onto ``base_dir``.
    allow_base : bool, default False
        If ``True``, allow the resolved path to equal ``base_dir`` itself.

    Returns
    -------
    Path
        Normalized real path guaranteed to reside within ``base_dir``.

    Raises
    ------
    ValueError
        If any path segment is absolute or resolves outside ``base_dir``.
    """
    str_parts = [str(part) for part in parts]
    if any("\x00" in part or Path(part).is_absolute() for part in str_parts):
        raise ValueError(f"Path parts {str_parts!r} must be relative to '{base_dir}'.")

    base_resolved = Path(base_dir).resolve()
    candidate = base_resolved.joinpath(*str_parts).resolve()
    if allow_base and candidate == base_resolved:
        return candidate
    if candidate == base_resolved or not candidate.is_relative_to(base_resolved):
        raise ValueError(
            f"Path '{candidate}' escapes allowed directory '{base_resolved}'."
        )
    return candidate
