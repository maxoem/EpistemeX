"""Contextvars-based event emitter management for the pipeline event system.

Provides task-local binding and retrieval of active `EventEmitter` instances,
eliminating the need to pass `event_emitter` through every function and class constructor.
"""
from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from .bus import EventEmitter, NoOpEventEmitter

_DEFAULT_EMITTER = NoOpEventEmitter()
_CURRENT_EVENT_EMITTER: ContextVar[EventEmitter | None] = ContextVar(
    "_CURRENT_EVENT_EMITTER", default=None
)


def get_event_emitter() -> EventEmitter:
    """Retrieve the currently active `EventEmitter` from task-local context.

    Returns
    -------
    EventEmitter
        The active event emitter bound to the current context, or a default
        `NoOpEventEmitter` if no emitter has been set.
    """
    emitter = _CURRENT_EVENT_EMITTER.get()
    return emitter if emitter is not None else _DEFAULT_EMITTER


def set_event_emitter(emitter: EventEmitter | None) -> Token:
    """Set the active `EventEmitter` for the current task-local context.

    Parameters
    ----------
    emitter : Optional[EventEmitter]
        The event emitter to set, or None to clear context.

    Returns
    -------
    Token
        A contextvar token that can be used to reset the previous context value.
    """
    return _CURRENT_EVENT_EMITTER.set(emitter)


@contextmanager
def use_event_emitter(emitter: EventEmitter | None) -> Generator[EventEmitter]:
    """Context manager to bind an `EventEmitter` for the duration of a code block.

    Guarantees that `emitter.flush()` is invoked in a finally block upon exit,
    ensuring that buffered spans and events are drained even if an exception occurs.

    Parameters
    ----------
    emitter : Optional[EventEmitter]
        The event emitter to bind to the current context.

    Yields
    ------
    EventEmitter
        The active event emitter.

    Examples
    --------
    >>> emitter = SimpleEventEmitter()
    >>> with use_event_emitter(emitter):
    ...     # get_event_emitter() returns `emitter` within this block
    ...     do_pipeline_work()
    """
    token = set_event_emitter(emitter)
    try:
        yield get_event_emitter()
    finally:
        if isinstance(emitter, EventEmitter):
            try:
                emitter.flush()
            except Exception:
                pass
        _CURRENT_EVENT_EMITTER.reset(token)
