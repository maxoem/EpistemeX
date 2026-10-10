"""
Event observers for the pipeline event system.

Observers translate domain events into various outputs:
- Logs
- JSONL event streams
- Metrics aggregations
- Observability traces
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import TextIO

from .bus import EventObserver
from .models import (
    CandidateRejectedByThreshold,
    DenseCandidatesGenerated,
    EntityMaturationSynthesized,
    LLMRelationDecoded,
    PipelineEvent,
    RerankerScoreAssigned,
    SchemaValidationRejectedRelation,
    TripleCommitted,
    get_event_type_name,
    serialize_event,
)


class LoggingObserver(EventObserver):
    """Observer that emits compact logs for events.

    This observer converts domain events into human-readable log messages
    with appropriate log levels based on event types.

    Parameters
    ----------
    logger : logging.Logger, optional
        Logger instance to use. If not provided, uses module logger.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def on_event(self, event: PipelineEvent) -> None:
        """Log the event with appropriate level based on event type.

        Parameters
        ----------
        event : PipelineEvent
            The event to log.
        """
        event_type = get_event_type_name(event)
        serialized = serialize_event(event)

        # Customize log messages based on event type
        if isinstance(event, DenseCandidatesGenerated):
            self.logger.info(
                f"Dense retrieval: {event.candidate_count} candidates from "
                f"{event.entities_count} entities"
            )
        elif isinstance(event, RerankerScoreAssigned):
            status = "ACCEPTED" if event.accepted else "REJECTED"
            self.logger.info(
                f"Reranker scored {event.score:.3f} for {event.candidate_pair} "
                f"({status} at threshold {event.threshold})"
            )
        elif isinstance(event, CandidateRejectedByThreshold):
            self.logger.debug(
                f"Candidate {event.candidate_pair} rejected: "
                f"score {event.score:.3f} < threshold {event.threshold}"
            )
        elif isinstance(event, LLMRelationDecoded):
            if event.relation:
                self.logger.info(
                    f"LLM decoded relation '{event.relation}' for {event.candidate_pair} "
                    f"(confidence: {event.confidence:.3f})"
                )
            else:
                self.logger.debug(f"LLM found no relation for {event.candidate_pair}")
        elif isinstance(event, SchemaValidationRejectedRelation):
            self.logger.warning(
                f"Schema validation rejected relation '{event.relation}' "
                f"for {event.candidate_pair}: {event.reason}"
            )
        elif isinstance(event, TripleCommitted):
            self.logger.info(
                f"Committed triple: {event.subject_id} --{event.predicate}--> "
                f"{event.object_id} (confidence: {event.confidence:.3f})"
            )
        elif isinstance(event, EntityMaturationSynthesized):
            self.logger.info(
                f"Synthesized mature description for entity '{event.entity_name}' "
                f"using top {event.top_k_used} of {event.envelope_count} envelopes."
            )
        else:
            # Generic logging for other events
            self.logger.debug(f"{event_type}: {serialized}")


class JsonlRunObserver(EventObserver):
    """Observer that writes event records to a JSONL file.

    This observer writes events as JSON lines to a file, suitable for
    research analysis and audit trails.

    Parameters
    ----------
    file_path : str or Path
        Path to the JSONL file to write events to.
    """

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self.file_handle: TextIO | None = None

    def __enter__(self) -> JsonlRunObserver:
        """Open the file for writing.

        Creates parent directories if they don't exist.

        Returns
        -------
        JsonlRunObserver
            Self for context manager use.
        """
        # Ensure parent directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_handle = self.file_path.open("w", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close the file.

        Parameters
        ----------
        exc_type : type
            Exception type if an exception occurred.
        exc_val : Exception
            Exception instance if an exception occurred.
        exc_tb : traceback
            Traceback if an exception occurred.
        """
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None

    def on_event(self, event: PipelineEvent) -> None:
        """Write the event as a JSON line.

        Parameters
        ----------
        event : PipelineEvent
            The event to write to the file.

        Raises
        ------
        RuntimeError
            If the observer is not being used as a context manager.
        """
        if not self.file_handle:
            raise RuntimeError("JsonlRunObserver must be used as a context manager")

        # Add event type to serialized data
        serialized = serialize_event(event)
        serialized["_event_type"] = get_event_type_name(event)
        # Ensure datetimes and other non-JSON types are serialized
        self.file_handle.write(json.dumps(serialized, default=str) + "\n")
        self.file_handle.flush()


class MetricsObserver(EventObserver):
    """Observer that aggregates metrics from events.

    This observer collects statistics from events, such as acceptance rates
    and counts of various event types.
    """

    def __init__(self) -> None:
        self.event_counts: dict[str, int] = defaultdict(int)
        self.candidate_acceptance_rates: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "accepted": 0}
        )
        self.total_triples_committed = 0

    def on_event(self, event: PipelineEvent) -> None:
        """Aggregate metrics from the event.

        Parameters
        ----------
        event : PipelineEvent
            The event to collect metrics from.
        """
        event_type = get_event_type_name(event)
        self.event_counts[event_type] += 1

        if isinstance(event, RerankerScoreAssigned):
            key = f"{event.candidate_pair[0]}-{event.candidate_pair[1]}"
            self.candidate_acceptance_rates[key]["total"] += 1
            if event.accepted:
                self.candidate_acceptance_rates[key]["accepted"] += 1
        elif isinstance(event, TripleCommitted):
            self.total_triples_committed += 1

    def get_candidate_acceptance_rate(self, candidate_key: str) -> float:
        """Get the acceptance rate for a specific candidate.

        Parameters
        ----------
        candidate_key : str
            Key identifying the candidate pair.

        Returns
        -------
        float
            Acceptance rate (0.0 to 1.0).
        """
        stats = self.candidate_acceptance_rates[candidate_key]
        if stats["total"] == 0:
            return 0.0
        return stats["accepted"] / stats["total"]

    def get_overall_candidate_acceptance_rate(self) -> float:
        """Get the overall candidate acceptance rate.

        Returns
        -------
        float
            Overall acceptance rate (0.0 to 1.0).
        """
        total_candidates = sum(
            stats["total"] for stats in self.candidate_acceptance_rates.values()
        )
        total_accepted = sum(
            stats["accepted"] for stats in self.candidate_acceptance_rates.values()
        )
        if total_candidates == 0:
            return 0.0
        return total_accepted / total_candidates


class CompositeObserver(EventObserver):
    """Observer that forwards events to multiple observers.

    This observer acts as a fan-out mechanism, distributing events to all
    registered observers with failure isolation.

    Parameters
    ----------
    observers : list of EventObserver
        List of observers to forward events to.
    """

    def __init__(self, observers: list[EventObserver]) -> None:
        self.observers = observers

    def on_event(self, event: PipelineEvent) -> None:
        """Forward event to all observers with failure isolation.

        Parameters
        ----------
        event : PipelineEvent
            The event to forward to all observers.
        """
        # Failure-isolated forwarding - one observer failing shouldn't break others
        for observer in self.observers:
            try:
                observer.on_event(event)
            except Exception as e:
                # Log the error but continue with other observers
                logging.getLogger(__name__).warning(
                    f"Observer {observer.__class__.__name__} failed to process event: {e}"
                )
