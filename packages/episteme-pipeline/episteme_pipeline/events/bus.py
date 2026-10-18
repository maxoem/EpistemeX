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
from typing import Any, Protocol, runtime_checkable

from .models import BaseEvent, PipelineEvent


@runtime_checkable
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
    def register_observer(self, observer: EventObserver) -> None:
        """Register an observer to receive events.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to register.
        """
        ...
        
    @abstractmethod
    def unregister_observer(self, observer: EventObserver) -> None:
        """Unregister an observer.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to unregister.
        """
        ...

    def flush(self) -> None:
        """Flush pending events or spans across all registered observers."""
        ...

    def get_observer_telemetry(self) -> dict[str, Any]:
        """Return observer delivery statistics and recorded errors.

        Returns
        -------
        dict of str to Any
            Dictionary containing events_delivered and observer_errors mappings.
        """
        ...


@runtime_checkable
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

    def flush(self) -> None:
        """Flush any pending buffered events or telemetry spans."""
        ...


@runtime_checkable
class TelemetryReportingObserver(Protocol):
    """Protocol for composite or telemetry-reporting observers."""

    def get_observer_telemetry(self) -> dict[str, Any]:
        """Return nested observer delivery statistics and recorded errors."""
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
        
    def register_observer(self, observer: EventObserver) -> None:
        """No-op registration.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to register (ignored).
        """
        
    def unregister_observer(self, observer: EventObserver) -> None:
        """No-op unregistration.
        
        Parameters
        ----------
        observer : EventObserver
            The observer to unregister (ignored).
        """

    def flush(self) -> None:
        """No-op flush."""

    def get_observer_telemetry(self) -> dict[str, Any]:
        """Return empty observer telemetry.

        Returns
        -------
        dict of str to Any
            Empty events_delivered and observer_errors mappings.
        """
        return {"events_delivered": {}, "observer_errors": {}}


class SimpleEventEmitter(EventEmitter):
    """Simple event emitter that broadcasts to all registered observers with failure isolation.
    
    This emitter maintains a list of observers and broadcasts each event
    to all of them in sequence, tracking successful deliveries and isolated errors.
    """
    
    def __init__(self, debug: bool = False) -> None:
        import logging
        from collections import defaultdict

        self._observers: list[EventObserver] = []
        self._debug = debug
        self.events_delivered: dict[str, int] = defaultdict(int)
        self.observer_errors: dict[str, list[str]] = defaultdict(list)
        self._logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self._logger.setLevel(logging.DEBUG)
        
    def emit(self, event: PipelineEvent) -> None:
        """Broadcast event to all registered observers with failure isolation.
        
        Parameters
        ----------
        event : PipelineEvent
            The event to broadcast.
        """
        if self._debug:
            from .models import get_event_type_name, serialize_event
            self._logger.debug(f"Event Emitted [{get_event_type_name(event)}]: {serialize_event(event)}")

        for observer in list(self._observers):
            obs_name = observer.__class__.__name__
            try:
                observer.on_event(event)
                self.events_delivered[obs_name] += 1
            except Exception as exc:
                self.observer_errors[obs_name].append(f"{type(exc).__name__}: {exc}")
                self._logger.warning(
                    "Observer %s failed to process event: %s",
                    obs_name,
                    exc,
                )
            
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
        if observer in self._observers:
            self._observers.remove(observer)

    def flush(self) -> None:
        """Flush pending spans and buffered events across all registered observers."""
        for observer in list(self._observers):
            if isinstance(observer, EventObserver):
                try:
                    observer.flush()
                except Exception as exc:
                    obs_name = observer.__class__.__name__
                    self.observer_errors[obs_name].append(f"flush:{type(exc).__name__}: {exc}")
                    self._logger.warning("Observer %s failed to flush: %s", obs_name, exc)

    def get_observer_telemetry(self) -> dict[str, Any]:
        """Return observer delivery statistics and recorded errors.

        Aggregates direct observer metrics as well as nested metrics from any
        registered :class:`TelemetryReportingObserver` (e.g., ``CompositeObserver``).

        Returns
        -------
        dict of str to Any
            Dictionary containing events_delivered and observer_errors mappings.
        """
        delivered = dict(self.events_delivered)
        errors = {k: list(v) for k, v in self.observer_errors.items()}

        for observer in self._observers:
            if isinstance(observer, TelemetryReportingObserver):
                sub_tel = observer.get_observer_telemetry()
                for k, count in sub_tel.get("events_delivered", {}).items():
                    delivered[k] = delivered.get(k, 0) + count
                for k, err_list in sub_tel.get("observer_errors", {}).items():
                    errors.setdefault(k, []).extend(err_list)

        return {
            "events_delivered": delivered,
            "observer_errors": errors,
        }


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

    def __init__(self, base: EventEmitter, defaults: dict[str, Any] | None = None) -> None:
        self.base = base
        self.defaults = defaults or {}

    def emit(self, event: PipelineEvent) -> None:
        # Pydantic BaseModel: create a shallow copy with missing defaults filled
        if isinstance(event, BaseEvent):
            current_dump = event.model_dump()
            updates: dict[str, Any] = {
                k: v for k, v in self.defaults.items() if current_dump.get(k) is None
            }
            event = event.model_copy(update=updates) if updates else event
        self.base.emit(event)

    def register_observer(self, observer: EventObserver) -> None:
        self.base.register_observer(observer)

    def unregister_observer(self, observer: EventObserver) -> None:
        self.base.unregister_observer(observer)

    def flush(self) -> None:
        """Flush the underlying base event emitter."""
        if isinstance(self.base, EventEmitter):
            self.base.flush()

    def get_observer_telemetry(self) -> dict[str, Any]:
        """Return observer telemetry from the underlying base emitter.

        Returns
        -------
        dict of str to Any
            Observer telemetry dictionary.
        """
        if isinstance(self.base, EventEmitter):
            return self.base.get_observer_telemetry()
        return {"events_delivered": {}, "observer_errors": {}}
