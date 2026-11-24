"""Security guards and validation logic for GLP Studio."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

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
    if any("\x00" in part or os.path.isabs(part) for part in str_parts):
        raise ValueError(f"Path parts {str_parts!r} must be relative to '{base_dir}'.")

    base_real = os.path.realpath(str(base_dir))
    fullpath = os.path.realpath(os.path.join(base_real, *str_parts))
    if allow_base and fullpath == base_real:
        return Path(fullpath)
    if not fullpath.startswith(base_real + os.sep):
        raise ValueError(f"Path '{fullpath}' escapes allowed directory '{base_real}'.")
    return Path(fullpath)


def resolve_path_within_roots(
    path: Path | str,
    allowed_roots: Sequence[Path | str],
) -> Path:
    """Resolve a path and verify it falls inside at least one allowed root.

    Parameters
    ----------
    path : Path or str
        Candidate path to validate.
    allowed_roots : sequence of Path or str
        Trusted root directories permitted to contain ``path``.

    Returns
    -------
    Path
        Normalized real path guaranteed to lie inside one of ``allowed_roots``.

    Raises
    ------
    ValueError
        If ``path`` contains null bytes or resolves outside all
        ``allowed_roots``.
    """
    path_str = str(path)
    if "\x00" in path_str:
        raise ValueError(f"Path {path_str!r} contains null bytes.")

    fullpath = os.path.realpath(path_str)
    for root in allowed_roots:
        root_real = os.path.realpath(str(root))
        if fullpath == root_real or fullpath.startswith(root_real + os.sep):
            return Path(fullpath)
    raise ValueError(f"Path '{path}' is outside allowed directories.")
