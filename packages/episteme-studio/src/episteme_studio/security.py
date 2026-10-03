"""Security guards and validation logic for GLP Studio."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .settings import StudioSettings


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
