"""Tests for logging configuration and noisy logger silencing."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from episteme_pipeline.observability.logging import (
    DEFAULT_NOISY_LOGGERS,
    _configure_litellm_flags,
    configure_pipeline_logging,
    silence_noisy_loggers,
)


def test_silence_noisy_loggers_default() -> None:
    """Test that silence_noisy_loggers configures all default noisy loggers to WARNING."""
    # Reset some loggers to INFO first
    for name in ("litellm", "httpx", "llama_index"):
        logging.getLogger(name).setLevel(logging.INFO)

    silence_noisy_loggers(level=logging.WARNING)

    for name in DEFAULT_NOISY_LOGGERS:
        if name.startswith("asyncio"):
            assert logging.getLogger(name).level == logging.ERROR
        else:
            assert logging.getLogger(name).level == logging.WARNING



def test_silence_noisy_loggers_custom_level_and_extras() -> None:
    """Test configuring noisy loggers to a custom level (e.g. DEBUG) and adding extra loggers."""
    extra = ["custom_noisy_lib", "another_noisy_lib"]
    silence_noisy_loggers(level=logging.DEBUG, extra_loggers=extra)

    assert logging.getLogger("litellm").level == logging.DEBUG
    assert logging.getLogger("httpx").level == logging.DEBUG
    assert logging.getLogger("custom_noisy_lib").level == logging.DEBUG
    assert logging.getLogger("another_noisy_lib").level == logging.DEBUG


def test_configure_litellm_flags() -> None:
    """Test setting verbose and debug flags on litellm module."""
    mock_litellm = MagicMock()
    mock_litellm._logging = MagicMock()

    # When WARNING or higher
    _configure_litellm_flags(mock_litellm, logging.WARNING)
    assert mock_litellm.suppress_debug_info is True
    assert mock_litellm.set_verbose is False
    mock_litellm._logging._disable_debugging.assert_called_once()

    # When DEBUG
    _configure_litellm_flags(mock_litellm, logging.DEBUG)
    assert mock_litellm.suppress_debug_info is False
    assert mock_litellm.set_verbose is True


def test_configure_pipeline_logging() -> None:
    """Test configure_pipeline_logging sets level and third-party logger levels."""
    root_logger, handler = configure_pipeline_logging(
        level=logging.INFO,
        third_party_log_level=logging.ERROR,
    )

    assert root_logger.level == logging.INFO
    assert handler is not None
    assert logging.getLogger("litellm").level == logging.ERROR
    assert logging.getLogger("httpx").level == logging.ERROR
