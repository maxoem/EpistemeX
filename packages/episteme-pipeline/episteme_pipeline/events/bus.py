"""
EventEmitter protocol and implementations for the pipeline event system.

This module defines how events are emitted and dispatched to observers.

The event system follows the Observer pattern:
- EventEmitter produces events
- EventObserver consumes events
- Observers register with emitters to receive events
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Protocol, List, Optional, Dict, Any

from .models import BaseEvent, PipelineEvent


class EventEmitter(Protocol):
    """Protocol for event emitters.
    
    Defines the interface for objects that can emit events to observers.
    """
    
    @abstractmethod
    def emit(self, event: PipelineEvent) -> None:
        """Emit an event to all registered observers.
        
        Parameters
        ----------
        event : PipelineEvent
            The event to emit.
        """
        ...
        
    @abstractmethod
    def register_observer(self, observer: "EventObserver") -> None:
        """Register an observer to receive events.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to register.
        """
        ...
        
    @abstractmethod
    def unregister_observer(self, observer: "EventObserver") -> None:
        """Unregister an observer.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to unregister.
        """
        ...


class EventObserver(Protocol):
    """Protocol for event observers.
    
    Defines the interface for objects that can consume events from emitters.
    """
    
    @abstractmethod
    def on_event(self, event: PipelineEvent) -> None:
        """Handle an incoming event.
        
        Parameters
        ----------
        event : PipelineEvent
            The event to handle.
        """
        ...


class NoOpEventEmitter(EventEmitter):
    """No-op event emitter that discards all events.
    
    This emitter can be used as a placeholder or for testing when event
    emission is not desired.
    """
    
    def emit(self, event: PipelineEvent) -> None:
        """Discard the event.
        
        Parameters
        ----------
        event : PipelineEvent
            The event to discard.
        """
        pass
        
    def register_observer(self, observer: EventObserver) -> None:
        """No-op registration.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to register (ignored).
        """
        pass
        
    def unregister_observer(self, observer: EventObserver) -> None:
        """No-op unregistration.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to unregister (ignored).
        """
        pass


class SimpleEventEmitter(EventEmitter):
    """Simple event emitter that broadcasts to all registered observers.
    
    This emitter maintains a list of observers and broadcasts each event
    to all of them in sequence.
    """
    
    def __init__(self, debug: bool = False) -> None:
        self._observers: List[EventObserver] = []
        self._debug = debug
        if debug:
            import logging
            self._logger = logging.getLogger(self.__class__.__name__)
            self._logger.setLevel(logging.DEBUG)
        
    def emit(self, event: PipelineEvent) -> None:
        """Broadcast event to all registered observers.
        
        Parameters
        ----------
        event : PipelineEvent
            The event to broadcast.
        """
        if getattr(self, "_debug", False):
            from .models import get_event_type_name, serialize_event
            self._logger.debug(f"Event Emitted [{get_event_type_name(event)}]: {serialize_event(event)}")

        for observer in self._observers:
            observer.on_event(event)
            
    def register_observer(self, observer: EventObserver) -> None:
        """Register an observer.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to register.
        """
        self._observers.append(observer)
        
    def unregister_observer(self, observer: EventObserver) -> None:
        """Unregister an observer.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to unregister.
        """
        self._observers.remove(observer)


class ContextualEventEmitter(EventEmitter):
    """EventEmitter that injects default metadata (e.g., run_id, phase).

    Wraps another emitter and ensures emitted events carry provided defaults
    when those fields are missing or ``None`` on the event.

    Parameters
    ----------
    base : EventEmitter
        Underlying emitter that performs the actual dispatch.
    defaults : dict[str, Any]
        Default fields to inject (e.g., {"run_id": "...", "phase": "..."}).
    """

    def __init__(self, base: EventEmitter, defaults: Optional[Dict[str, Any]] = None) -> None:
        self.base = base
        self.defaults = defaults or {}

    def emit(self, event: PipelineEvent) -> None:
        # Pydantic BaseModel: create a shallow copy with missing defaults filled
        if isinstance(event, BaseEvent):
            updates: Dict[str, Any] = {}
            for k, v in self.defaults.items():
                if getattr(event, k, None) is None:
                    updates[k] = v
            event = event.model_copy(update=updates) if updates else event
        self.base.emit(event)

    def register_observer(self, observer: "EventObserver") -> None:
        self.base.register_observer(observer)

    def unregister_observer(self, observer: "EventObserver") -> None:
        self.base.unregister_observer(observer)
