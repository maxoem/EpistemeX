"""
Adapters for backward compatibility with the tracing system.

This module provides adapters to bridge the gap between the legacy TraceSink
API and the new event-based observability system.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

from .bus import EventEmitter, SimpleEventEmitter
from .models import ComponentStarted, ComponentCompleted


class TraceSinkToEventEmitterAdapter(EventEmitter):
    """Adapter that converts TraceSink calls to events.
    
    This adapter allows gradual migration from the legacy TraceSink API
    to the event-based observability system. It forwards TraceSink spans
    as ComponentStarted/Completed events while maintaining backward
    compatibility.
    
    Parameters
    ----------
    trace_sink : TraceSink
        Legacy trace sink to wrap.
    """
    
    def __init__(self, trace_sink: Any) -> None:
        self.trace_sink = trace_sink
        # Create an internal event emitter to forward events
        self._internal_emitter = SimpleEventEmitter()
        
    def emit(self, event: Any) -> None:
        """Forward events to internal emitter.
        
        This method bridges the EventEmitter interface with the internal
        SimpleEventEmitter for actual event distribution.
        
        Parameters
        ----------
        event : Any
            The event to emit.
        """
        self._internal_emitter.emit(event)
        
    def register_observer(self, observer: Any) -> None:
        """Register observer with internal emitter.
        
        Allows observers to receive events from the adapter.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to register.
        """
        self._internal_emitter.register_observer(observer)
        
    def unregister_observer(self, observer: Any) -> None:
        """Unregister observer with internal emitter.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to unregister.
        """
        self._internal_emitter.unregister_observer(observer)

    @contextmanager
    def trace_span(self, name: str, input: Optional[Dict[str, Any]] = None):
        """Context manager that wraps trace sink span for backward compatibility.
        
        Emits ComponentStarted and ComponentCompleted events while delegating
        to the underlying TraceSink for actual tracing.
        
        Parameters
        ----------
        name : str
            Name of the span/component.
        input : dict, optional
            Input data for the span.
            
        Yields
        ------
        TraceSpan
            The trace span from the underlying TraceSink.
        """
        start_time = time.time()
        # Emit start event
        self.emit(ComponentStarted(component_name=name, input_description=str(input)))
        
        try:
            with self.trace_sink.span(name=name, input=input) as span:
                yield span
            # Emit completion event on success
            duration = time.time() - start_time
            self.emit(ComponentCompleted(component_name=name, duration_seconds=duration, success=True))
        except Exception as e:
            # Emit completion event on error
            duration = time.time() - start_time
            self.emit(ComponentCompleted(component_name=name, duration_seconds=duration, success=False, error_message=str(e)))
            raise

