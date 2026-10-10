"""Event broker managing per-run ring buffers, monotonic seq, and SSE fan-out."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from typing import Any

from episteme_studio.adapters.event_mapper import to_studio_event
from episteme_studio.domain.events import StudioEvent


class EventBroker:
    """Broker maintaining telemetry ring buffers and multiplexing streams to clients.

    Parameters
    ----------
    capacity : int, default 10000
        Maximum number of events retained in memory per run.
    """

    def __init__(self, capacity: int = 10000) -> None:
        self.capacity = capacity
        self._buffers: dict[str, deque[StudioEvent]] = defaultdict(lambda: deque(maxlen=self.capacity))
        self._seqs: dict[str, int] = defaultdict(int)
        self._notifiers: dict[str, set[asyncio.Event]] = defaultdict(set)
        self._closed_runs: set[str] = set()

    def publish(self, run_id: str, event_data: dict[str, Any] | StudioEvent) -> StudioEvent:
        """Publish a new telemetry event for a run.

        Assigns a monotonic sequence number, records the event in the ring buffer,
        and awakens all active subscribers awaiting new events.

        Parameters
        ----------
        run_id : str
            Identifier of the pipeline run.
        event_data : dict of str to Any or StudioEvent
            Raw event dictionary or pre-formed StudioEvent.

        Returns
        -------
        StudioEvent
            The published event.
        """
        self._seqs[run_id] += 1
        seq = self._seqs[run_id]

        if isinstance(event_data, StudioEvent):
            event = event_data.model_copy(update={"seq": seq})
        else:
            event = to_studio_event(event_data, seq=seq)

        self._buffers[run_id].append(event)

        # Notify all active subscribers awaiting new events
        for notifier in list(self._notifiers.get(run_id, ())):
            notifier.set()

        return event

    def get_history(self, run_id: str, since_seq: int | None = None) -> list[StudioEvent]:
        """Retrieve buffered event history for a run.

        Parameters
        ----------
        run_id : str
            Identifier of the pipeline run.
        since_seq : int or None, optional
            Sequence number threshold. If provided, returns events with seq > since_seq.
            If None, returns all buffered events.

        Returns
        -------
        list of StudioEvent
            Ordered list of buffered events.
        """
        buffer = list(self._buffers.get(run_id, []))
        if since_seq is None:
            return buffer
        return [e for e in buffer if e.seq > since_seq]

    async def subscribe(
        self,
        run_id: str,
        since_seq: int | None = None,
    ) -> AsyncIterator[StudioEvent]:
        """Subscribe to an event stream with historical replay via ring buffer cursor.

        Parameters
        ----------
        run_id : str
            Identifier of the pipeline run.
        since_seq : int or None, optional
            If provided, replays events with seq > since_seq before streaming live events.
            If None, replays all buffered events.

        Yields
        ------
        StudioEvent
            Replayed and live events.
        """
        cursor_seq = since_seq or 0
        notifier = asyncio.Event()
        self._notifiers[run_id].add(notifier)

        try:
            while True:
                buf = self._buffers.get(run_id)
                events_to_yield: list[StudioEvent] = []
                if buf:
                    oldest_seq = buf[0].seq
                    cursor_seq = max(cursor_seq, oldest_seq - 1)

                    for ev in list(buf):
                        if ev.seq > cursor_seq:
                            events_to_yield.append(ev)

                for ev in events_to_yield:
                    yield ev
                    cursor_seq = ev.seq

                if run_id in self._closed_runs:
                    curr_max = self._seqs.get(run_id, 0)
                    if cursor_seq >= curr_max:
                        break

                if not events_to_yield:
                    notifier.clear()
                    if run_id in self._closed_runs and cursor_seq >= self._seqs.get(run_id, 0):
                        break
                    try:
                        await asyncio.wait_for(notifier.wait(), timeout=15.0)
                    except TimeoutError:
                        pass
        finally:
            self._notifiers[run_id].discard(notifier)

    def close_run(self, run_id: str) -> None:
        """Signal termination to all current subscribers of a run.

        Parameters
        ----------
        run_id : str
            Identifier of the pipeline run.
        """
        self._closed_runs.add(run_id)
        for notifier in list(self._notifiers.get(run_id, ())):
            notifier.set()
