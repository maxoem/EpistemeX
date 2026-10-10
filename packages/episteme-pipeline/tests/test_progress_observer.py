"""Tests for RichProgressObserver."""

from __future__ import annotations

import logging

from episteme_pipeline.events.bus import SimpleEventEmitter
from episteme_pipeline.events.models import (
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
)
from episteme_pipeline.events.progress_observer import RichProgressObserver
from rich.console import Console
from rich.logging import RichHandler


def test_progress_observer_lifecycle() -> None:
    """Test entering and exiting RichProgressObserver context manager."""
    console = Console(file=None, quiet=True)
    with RichProgressObserver(console=console) as observer:
        assert observer.progress is not None
        assert observer._owns_progress is True
        assert observer.console is console

    assert observer._owns_progress is False


def test_progress_observer_events() -> None:
    """Test that ProgressStarted, ProgressAdvanced, and ProgressCompleted update tasks."""
    console = Console(file=None, quiet=True)
    emitter = SimpleEventEmitter()

    with RichProgressObserver(console=console) as observer:
        emitter.register_observer(observer)

        task_name = "test_phase_1"
        emitter.emit(ProgressStarted(task_name=task_name, total_items=10, description="Testing Phase 1"))

        task_id = observer._tasks.get(task_name)
        assert task_id is not None
        task = observer.progress._tasks[task_id]
        assert task.description == "Testing Phase 1"
        assert task.total == 10
        assert task.completed == 0

        # Advance
        emitter.emit(ProgressAdvanced(task_name=task_name, advance=4))
        assert observer.progress._tasks[task_id].completed == 4

        # Complete
        emitter.emit(ProgressCompleted(task_name=task_name))
        assert observer.progress._tasks[task_id].completed == 10


def test_progress_observer_get_rich_handler() -> None:
    """Test get_rich_handler binds to the observer console."""
    console = Console(file=None, quiet=True)
    observer = RichProgressObserver(console=console)
    handler = observer.get_rich_handler(level=logging.WARNING)

    assert isinstance(handler, RichHandler)
    assert handler.console is console
    assert handler.level == logging.WARNING


def test_progress_observer_syncs_existing_rich_handler() -> None:
    """Test that entering RichProgressObserver syncs console to existing root RichHandler."""
    custom_console = Console(file=None, quiet=True)
    other_console = Console(file=None, quiet=True)
    existing_handler = RichHandler(console=other_console)
    root_logger = logging.getLogger()
    root_logger.addHandler(existing_handler)

    try:
        with RichProgressObserver(console=custom_console, sync_root_handlers=True):
            assert existing_handler.console is custom_console
    finally:
        root_logger.removeHandler(existing_handler)


def test_progress_observer_configurable_third_party_log_level() -> None:
    """Test third_party_log_level configuration on RichProgressObserver."""
    console = Console(file=None, quiet=True)

    # Set to WARNING
    with RichProgressObserver(console=console, third_party_log_level=logging.WARNING):
        assert logging.getLogger("litellm").level == logging.WARNING
        assert logging.getLogger("httpx").level == logging.WARNING

    # Set to DEBUG
    with RichProgressObserver(console=console, third_party_log_level=logging.DEBUG):
        assert logging.getLogger("litellm").level == logging.DEBUG
        assert logging.getLogger("httpx").level == logging.DEBUG

    # None should not alter existing log level
    logging.getLogger("litellm").setLevel(logging.ERROR)
    with RichProgressObserver(console=console, third_party_log_level=None):
        assert logging.getLogger("litellm").level == logging.ERROR
