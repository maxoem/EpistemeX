"""Logging context managers and utilities."""

from __future__ import annotations

import contextlib
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console

DEFAULT_NOISY_LOGGERS: tuple[str, ...] = (
    "litellm",
    "LiteLLM",
    "LiteLLM Router",
    "LiteLLM Proxy",
    "llama_index",
    "llama_index.core",
    "llama_index.llms",
    "llama_index.llms.litellm",
    "llama_index.embeddings",
    "llama_index.embeddings.litellm",
    "httpx",
    "httpcore",
    "openai",
    "openai._base_client",
    "urllib3",
    "urllib3.connectionpool",
    "neo4j",
    "neo4j.pool",
    "neo4j.io",
    "asyncio",
    "transformers",
    "sentence_transformers",
    "filelock",
    "fsspec",
)


def silence_noisy_loggers(
    level: int = logging.WARNING,
    extra_loggers: Sequence[str] | None = None,
    include_defaults: bool = True,
) -> None:
    """Set the logging level for noisy third-party libraries (LiteLLM, LlamaIndex, HTTPX, Neo4j, asyncio, etc.).

    Parameters
    ----------
    level : int, default=logging.WARNING
        Logging level to assign to the noisy loggers (e.g., ``logging.WARNING``,
        ``logging.INFO``, or ``logging.DEBUG``).
    extra_loggers : Sequence[str] | None, optional
        Additional logger names to configure.
    include_defaults : bool, default=True
        Whether to include ``DEFAULT_NOISY_LOGGERS``.

    Notes
    -----
    When ``level >= logging.WARNING``:
    - LiteLLM's internal debugging flags (``suppress_debug_info``, ``set_verbose``)
      are disabled to prevent raw terminal echoes.
    - Python's ``asyncio`` logger is set to ``logging.ERROR`` because asyncio
      emits slow callback warnings (e.g. ``Executing <Task ...> took 0.15s``) at
      ``logging.WARNING`` level.
    When set to a more verbose level like ``logging.DEBUG``, those flags and full
    asyncio logging are enabled.
    """
    targets: list[str] = []
    if include_defaults:
        targets.extend(DEFAULT_NOISY_LOGGERS)
    if extra_loggers:
        targets.extend(extra_loggers)

    for name in targets:
        # Special-case asyncio: asyncio logs slow task callbacks (>100ms) at WARNING level.
        # When silencing to WARNING, asyncio needs to be at ERROR to suppress slow callback spam.
        if name.startswith("asyncio") and level == logging.WARNING:
            logging.getLogger(name).setLevel(logging.ERROR)
        else:
            logging.getLogger(name).setLevel(level)

    # Configure LiteLLM module-level flags if litellm is imported or available
    litellm_mod = sys.modules.get("litellm")
    if litellm_mod is not None:
        _configure_litellm_flags(litellm_mod, level)
    else:
        try:
            import litellm  # type: ignore[import-not-found]
            _configure_litellm_flags(litellm, level)
        except (ImportError, AttributeError):
            pass



def _configure_litellm_flags(litellm_module: Any, level: int) -> None:
    """Configure LiteLLM internal verbose/debug flags based on log level."""
    if litellm_module is None:
        return
    try:
        if level >= logging.WARNING:
            litellm_module.suppress_debug_info = True
            litellm_module.set_verbose = False
            if hasattr(litellm_module, "_logging") and hasattr(litellm_module._logging, "_disable_debugging"):
                litellm_module._logging._disable_debugging()
        else:
            litellm_module.suppress_debug_info = False
            litellm_module.set_verbose = (level == logging.DEBUG)
    except Exception:
        pass


def configure_pipeline_logging(
    level: int = logging.INFO,
    third_party_log_level: int | None = logging.WARNING,
    console: Console | None = None,
    rich_tracebacks: bool = True,
    show_path: bool = False,
) -> tuple[logging.Logger, Any | None]:
    """Configure root logging for the pipeline with optional Rich formatting and logger silencing.

    Parameters
    ----------
    level : int, default=logging.INFO
        Logging level for pipeline application logs.
    third_party_log_level : int | None, default=logging.WARNING
        Logging level for noisy dependencies (LiteLLM, HTTPX, etc.). If None,
        third-party loggers remain unchanged.
    console : Console | None, optional
        A ``rich.console.Console`` instance to bind to the RichHandler. If None and
        Rich is available, a new Console instance is created.
    rich_tracebacks : bool, default=True
        Whether RichHandler formats exception tracebacks.
    show_path : bool, default=False
        Whether RichHandler prints the originating source path on each log line.

    Returns
    -------
    tuple[logging.Logger, Any | None]
        A tuple of ``(root_logger, handler)`` where handler is the created
        ``RichHandler`` (or ``StreamHandler``).
    """
    if third_party_log_level is not None:
        silence_noisy_loggers(level=third_party_log_level)

    try:
        from rich.console import Console as RichConsole
        from rich.logging import RichHandler

        effective_console = console or RichConsole()
        handler: logging.Handler = RichHandler(
            console=effective_console,
            rich_tracebacks=rich_tracebacks,
            show_path=show_path,
        )
    except ImportError:
        handler = logging.StreamHandler()

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if not any(type(h) is type(handler) for h in root_logger.handlers):
        root_logger.addHandler(handler)

    return root_logger, handler


@contextlib.contextmanager
def run_folder_logger(runs_dir: str, run_id: str):
    """Context manager to route standard logs into the specific run folder.

    This keeps the pipeline orchestrator decoupled from Python logging internals.
    All logs emitted within this context are written to `<runs_dir>/<run_id>/pipeline.log`.

    Parameters
    ----------
    runs_dir : str
        Base directory containing pipeline runs.
    run_id : str
        Unique identifier for the current run.
    """
    log_dir = Path(runs_dir) / run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pipeline.log"

    # Use standard FileHandler for runtime-defined log routing
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    file_handler.setLevel(logging.DEBUG)

    # Attach to root logger to capture everything
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    try:
        yield
    finally:
        root_logger.removeHandler(file_handler)
        file_handler.close()
