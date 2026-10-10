"""Progress observer that updates rich terminal progress bars."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskID,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
except ImportError:
    Progress = None  # type: ignore[assignment, misc]
    Console = None  # type: ignore[assignment, misc]
    RichHandler = None  # type: ignore[assignment, misc]

from episteme_pipeline.events.bus import EventObserver
from episteme_pipeline.events.models import (
    PipelineEvent,
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
)
from episteme_pipeline.observability.logging import silence_noisy_loggers


class RichProgressObserver(EventObserver):
    """Observer that uses `rich.progress` to visualize task progress in the console.

    Parameters
    ----------
    progress : Progress | None, optional
        An existing ``rich.progress.Progress`` instance to use. If None, one will be created.
    console : Console | None, optional
        A ``rich.console.Console`` instance. If provided, this console will be shared between
        the progress display and any logging handlers. If None and ``progress`` is None, a new
        Console is created.
    third_party_log_level : int | None, default=logging.WARNING
        Logging level to assign to noisy third-party loggers (LiteLLM, LlamaIndex, HTTPX, etc.)
        when entering the context manager. If None, third-party log levels are not modified.
    auto_refresh : bool, default=True
        Whether the progress display automatically refreshes periodically.
    transient : bool, default=False
        Whether to clear the progress bars from the console after completion.
    columns : Sequence[Any] | None, optional
        Custom Rich progress columns. Defaults to standard spinner, description, bar,
        M/N counter, percentage, elapsed, and remaining time columns.
    sync_root_handlers : bool, default=True
        Whether to automatically attach any existing ``RichHandler`` instances on the root
        logger to this observer's ``Console`` when entering the context manager. This prevents
        uncoordinated console writes from disrupting the live progress bar.

    Notes
    -----
    Rich live progress display requires an interactive terminal (TTY). In
    non-interactive environments (such as some IDE run windows or non-TTY runners),
    Rich disables live refresh and only outputs the completed progress state upon exit.
    For live progress bars, run the pipeline directly in a standard interactive terminal
    (e.g., ``uv run python examples/pipeline_full_run.py``).

    Raises
    ------
    ImportError
        If ``rich`` is not installed.
    """

    def __init__(
        self,
        progress: Progress | None = None,
        console: Console | None = None,
        third_party_log_level: int | None = logging.WARNING,
        auto_refresh: bool = True,
        transient: bool = False,
        columns: Sequence[Any] | None = None,
        sync_root_handlers: bool = True,
    ) -> None:
        if Progress is None:
            raise ImportError("rich must be installed to use RichProgressObserver.")

        self.progress = progress
        self._console = console or (progress.console if progress is not None else Console())
        self.third_party_log_level = third_party_log_level
        self.auto_refresh = auto_refresh
        self.transient = transient
        self.columns = columns
        self.sync_root_handlers = sync_root_handlers

        self._owns_progress = False
        self._tasks: dict[str, TaskID] = {}

    @property
    def console(self) -> Console:
        """Return the active Rich console instance used by this observer."""
        if self.progress is not None:
            return self.progress.console
        return self._console

    def get_rich_handler(
        self,
        level: int = logging.INFO,
        rich_tracebacks: bool = True,
        show_path: bool = False,
        **kwargs: Any,
    ) -> RichHandler:
        """Create a ``RichHandler`` bound to the exact same console as this progress observer.

        Using this handler guarantees log lines are printed cleanly above the live
        progress bar without corrupting the terminal display.

        Parameters
        ----------
        level : int, default=logging.INFO
            Minimum log level for the handler.
        rich_tracebacks : bool, default=True
            Whether tracebacks are rendered with Rich styling.
        show_path : bool, default=False
            Whether to display source code file paths on log lines.
        **kwargs : Any
            Additional keyword arguments passed to ``RichHandler``.

        Returns
        -------
        RichHandler
            Configured handler bound to this observer's console.
        """
        return RichHandler(
            console=self.console,
            level=level,
            rich_tracebacks=rich_tracebacks,
            show_path=show_path,
            **kwargs,
        )

    def __enter__(self) -> RichProgressObserver:
        """Start the progress display and configure logger coordination.

        Returns
        -------
        RichProgressObserver
            The entered observer instance.
        """
        if self.third_party_log_level is not None:
            silence_noisy_loggers(level=self.third_party_log_level)

        if self.progress is None:
            cols = self.columns or (
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TextColumn("•"),
                TimeElapsedColumn(),
                TextColumn("<"),
                TimeRemainingColumn(),
            )
            self.progress = Progress(
                *cols,
                console=self._console,
                auto_refresh=self.auto_refresh,
                transient=self.transient,
            )
            self._owns_progress = True

        # Sync existing RichHandlers to share the same console so logs don't tear the progress bar
        if self.sync_root_handlers and RichHandler is not None:
            for handler in logging.getLogger().handlers:
                if isinstance(handler, RichHandler) and handler.console is not self.console:
                    handler.console = self.console

        if self._owns_progress:
            self.progress.start()

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop the progress display if owned by this observer.

        Parameters
        ----------
        exc_type : type | None
            Exception type if an exception occurred.
        exc_val : BaseException | None
            Exception value if an exception occurred.
        exc_tb : types.TracebackType | None
            Traceback if an exception occurred.
        """
        if self._owns_progress and self.progress is not None:
            self.progress.stop()
            self._owns_progress = False

    def on_event(self, event: PipelineEvent) -> None:
        """Process pipeline progress events and update the live progress bar.

        Parameters
        ----------
        event : PipelineEvent
            The emitted domain or progress event.
        """
        if self.progress is None:
            return

        if isinstance(event, ProgressStarted):
            desc = event.description if event.description else event.task_name
            task_id = self.progress.add_task(description=desc, total=event.total_items)
            self._tasks[event.task_name] = task_id
            self.progress.refresh()

        elif isinstance(event, ProgressAdvanced):
            task_id = self._tasks.get(event.task_name)
            if task_id is not None:
                self.progress.advance(task_id, advance=event.advance)
                self.progress.refresh()

        elif isinstance(event, ProgressCompleted):
            task_id = self._tasks.get(event.task_name)
            if task_id is not None:
                task = (
                    self.progress._tasks.get(task_id)
                    if hasattr(self.progress, "_tasks")
                    else None
                )
                if task is not None and task.total is not None:
                    self.progress.update(task_id, completed=task.total)
                else:
                    self.progress.update(task_id, completed=None)
                self.progress.refresh()

