"""
Tracing protocols for backward compatibility.

These protocols are deprecated in favor of the event-driven architecture
but are kept for backward compatibility during the transition.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Any, Optional
from typing import Protocol, Iterator


class TraceSpan(Protocol):
    """Protocol for trace spans."""
    
    def update(self, **kwargs: Any) -> None:
        """Update span with additional data."""
        ...


class TraceSink(Protocol):
    """Protocol for trace sinks (deprecated)."""
    
    @contextmanager
    def span(
        self,
        *,
        name: str,
        input: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> Iterator[TraceSpan]:
        """Create a tracing span."""
        ...


class NoOpTraceSink:
    """No-op trace sink for disabling tracing."""
    
    @contextmanager
    def span(
        self,
        *,
        name: str,
        input: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> Iterator[TraceSpan]:
        """No-op span context manager."""
        yield _NoOpSpan()


class _NoOpSpan:
    """No-op span implementation."""
    
    def update(self, **kwargs: Any) -> None:
        """Ignore span updates."""
        pass
