"""Zero-IO non-blocking event observer for the pipeline execution thread."""

from __future__ import annotations

import queue
from typing import Any

from episteme_studio.adapters.event_mapper import serialize_pipeline_event


class StudioEventObserver:
    """Non-blocking, zero-IO event observer for the pipeline event emitter.

    This observer runs synchronously on the pipeline thread. It must never perform
    disk, network, or database I/O. It serializes incoming events into memory and
    pushes them onto a bounded IPC queue using non-blocking semantics.

    Parameters
    ----------
    out_queue : Any
        A queue (e.g. multiprocessing.Queue or queue.Queue) supporting
        ``put_nowait()``.
    """

    def __init__(self, out_queue: Any) -> None:
        self._queue = out_queue
        self._dropped_count = 0

    @property
    def dropped_count(self) -> int:
        """Get the current count of dropped events since last successful emit.

        Returns
        -------
        int
            Dropped event count.
        """
        return self._dropped_count

    def on_event(self, event: Any) -> None:
        """Handle an incoming event from the pipeline emitter without blocking.

        Parameters
        ----------
        event : Any
            The emitted pipeline event instance or raw dictionary.
        """
        try:
            raw = serialize_pipeline_event(event)
            raw["_dropped_before"] = self._dropped_count
            self._queue.put_nowait(raw)
            self._dropped_count = 0
        except (queue.Full, Exception) as err:  # noqa: BLE001 baseline
            # Check if this is a Full queue exception from queue.Queue or multiprocessing.Queue
            if type(err).__name__ == "Full" or isinstance(err, queue.Full):
                self._dropped_count += 1
            else:
                # Catch any unexpected serialization issue so the pipeline is never crashed
                self._dropped_count += 1
