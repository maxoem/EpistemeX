"""CheckpointedBatchExecutor & CheckpointedStreamExecutor — atomic execution (ADR-0016).

Generalizes upfront item filtering, atomic unit-of-work checkpointing, order-invariant
item hashing, poison-pill dead-letter quarantine, stateful sequential stream execution,
and first-batch systematic failure guards across all pipeline phases.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Sequence
from itertools import batched
import logging
from typing import Any

from episteme_pipeline.contracts.domain import PhaseItemRecord
from episteme_pipeline.protocols.graph_store import PhaseCheckpointStore

logger = logging.getLogger(__name__)


class SystematicBatchFailureError(RuntimeError):
    """Raised when an entire initial batch fails systematically across all items."""


class BatchExecutionResult[OutT]:
    """Aggregated result of checkpointed batch or stream execution.

    Parameters
    ----------
    outputs : list of OutT
        Successfully extracted or evaluated output items.
    records : list of PhaseItemRecord
        Item checkpoint records tracking completion and failure statuses.
    succeeded_count : int
        Total number of successfully processed items.
    failed_count : int
        Total number of quarantined failed items.
    """

    def __init__(
        self,
        outputs: list[OutT],
        records: list[PhaseItemRecord],
        succeeded_count: int,
        failed_count: int,
    ) -> None:
        self.outputs = outputs
        self.records = records
        self.succeeded_count = succeeded_count
        self.failed_count = failed_count


class CheckpointedBatchExecutor[ItemT, OutT]:
    """Atomic batch executor with upfront filtering, unit-of-work persistence, and quarantine.

    Adheres to ADR-0016 and Pattern 2 (Template Method + Unit of Work):
    1. Filters already committed items upfront via :meth:`PhaseCheckpointStore.filter_unprocessed_items`
       so remaining work is packed into dense batches of ``batch_size``.
    2. Executes processing concurrently in discrete batches of size ``batch_size``.
    3. Aborts immediately via :class:`SystematicBatchFailureError` if all items of the
       first evaluated batch fail systematically.
    4. Quarantines individual poisoned items with status ``failed``, preventing
       infinite retry loops upon subsequent run resumption.
    5. Persists domain outputs via ``on_batch_complete`` *before* committing item
       checkpoints via :meth:`PhaseCheckpointStore.commit_phase_items`, ensuring
       items are never marked completed if output persistence fails.

    Parameters
    ----------
    checkpoint_store : PhaseCheckpointStore or None
        Storage client supporting phase item checkpointing.
    phase_tag : str
        Lineage-scoped phase identifier tag (e.g. ``phase4:fingerprint``).
    batch_size : int, default 10
        Batch chunk size.
    item_key_fn : Callable[[ItemT], str]
        Deterministic, order-invariant key generator for input items.
    process_batch_fn : Callable[[list[ItemT]], Awaitable[tuple[list[OutT], list[PhaseItemRecord]]]] or None, default None
        Function processing an entire batch of items at once. Mutually exclusive with ``process_item_fn``.
    process_item_fn : Callable[[ItemT], Awaitable[OutT | None]] or None, default None
        Function processing an individual item. Mutually exclusive with ``process_batch_fn``.
    on_batch_complete : Callable[[list[OutT], list[PhaseItemRecord]], Awaitable[None]] or None, default None
        Optional asynchronous persistence callback invoked after each batch finishes
        and *before* item checkpoints are committed.
    guard_systematic_failure : bool, default True
        Whether to abort if all items in the initial batch fail.
    custom_commit_fn : Callable[[str, list[OutT], list[PhaseItemRecord]], Awaitable[None]] or None, default None
        Optional custom atomic persistence callback replacing default ``commit_phase_items``.
    """

    def __init__(
        self,
        checkpoint_store: PhaseCheckpointStore | None,
        phase_tag: str,
        *,
        batch_size: int = 10,
        item_key_fn: Callable[[ItemT], str],
        process_batch_fn: (
            Callable[
                [list[ItemT]],
                Awaitable[tuple[list[OutT], list[PhaseItemRecord]]],
            ]
            | None
        ) = None,
        process_item_fn: Callable[[ItemT], Awaitable[OutT | None]] | None = None,
        on_batch_complete: (
            Callable[[list[OutT], list[PhaseItemRecord]], Awaitable[None]] | None
        ) = None,
        guard_systematic_failure: bool = True,
        custom_commit_fn: (
            Callable[
                [str, list[OutT], list[PhaseItemRecord]],
                Awaitable[None],
            ]
            | None
        ) = None,
    ) -> None:
        if (process_batch_fn is None) == (process_item_fn is None):
            raise ValueError(
                "Exactly one of process_batch_fn or process_item_fn must be provided."
            )

        self.checkpoint_store = checkpoint_store
        self.phase_tag = phase_tag
        self.batch_size = max(1, batch_size)
        self.item_key_fn = item_key_fn
        self.process_batch_fn = process_batch_fn
        self.process_item_fn = process_item_fn
        self.on_batch_complete = on_batch_complete
        self.guard_systematic_failure = guard_systematic_failure
        self.custom_commit_fn = custom_commit_fn

    async def execute(
        self,
        items: Sequence[ItemT],
        on_batch_advance: Callable[[int], None] | None = None,
    ) -> BatchExecutionResult[OutT]:
        """Execute checkpointed batches across input items.

        Parameters
        ----------
        items : Sequence of ItemT
            All candidate items to evaluate.
        on_batch_advance : Callable[[int], None] or None, optional
            Optional progress reporter callback receiving the batch item count.

        Returns
        -------
        BatchExecutionResult of OutT
            Execution result container with accumulated outputs and item records.

        Raises
        ------
        SystematicBatchFailureError
            If all items in the first evaluated batch fail.
        """
        if not items:
            return BatchExecutionResult(
                outputs=[], records=[], succeeded_count=0, failed_count=0
            )

        if self.checkpoint_store is not None:
            all_keys = [self.item_key_fn(item) for item in items]
            pending_keys = set(
                await self.checkpoint_store.filter_unprocessed_items(
                    all_keys, self.phase_tag
                )
            )
            pending_items = [
                item for item in items if self.item_key_fn(item) in pending_keys
            ]
            skipped_count = len(items) - len(pending_items)
            if skipped_count > 0 and on_batch_advance is not None:
                on_batch_advance(skipped_count)
        else:
            pending_items = list(items)

        if not pending_items:
            return BatchExecutionResult(
                outputs=[], records=[], succeeded_count=0, failed_count=0
            )

        all_outputs: list[OutT] = []
        all_records: list[PhaseItemRecord] = []
        succeeded_total = 0
        failed_total = 0

        for batch_tuple in batched(pending_items, self.batch_size):
            pending_batch = list(batch_tuple)
            first_exception: Exception | None = None

            if self.process_batch_fn is not None:
                batch_outputs, batch_records = await self.process_batch_fn(
                    pending_batch
                )
            else:
                assert self.process_item_fn is not None
                tasks = [self.process_item_fn(item) for item in pending_batch]
                raw_results = await asyncio.gather(*tasks, return_exceptions=True)

                batch_outputs = []
                batch_records = []
                for item, res in zip(pending_batch, raw_results):
                    key = self.item_key_fn(item)
                    if isinstance(res, Exception):
                        if first_exception is None:
                            first_exception = res
                        logger.error(
                            "CheckpointedBatchExecutor: Item %s failed with %s: %s",
                            key,
                            type(res).__name__,
                            res,
                        )
                        batch_records.append(
                            PhaseItemRecord(key=key, status="failed", error=str(res))
                        )
                    else:
                        batch_records.append(
                            PhaseItemRecord(key=key, status="completed")
                        )
                        if res is not None:
                            batch_outputs.append(res)

            failed_records = [r for r in batch_records if r.status == "failed"]

            if (
                self.guard_systematic_failure
                and succeeded_total == 0
                and len(failed_records) == len(pending_batch)
                and len(pending_batch) > 0
            ):
                sample_error = failed_records[0].error or "Unknown error"
                raise SystematicBatchFailureError(
                    f"All {len(pending_batch)} items of the first batch failed in "
                    f"{self.phase_tag}. Halting execution: {sample_error}"
                ) from first_exception

            succeeded_total += len(
                [r for r in batch_records if r.status == "completed"]
            )
            failed_total += len(failed_records)
            all_outputs.extend(batch_outputs)
            all_records.extend(batch_records)

            # Unit-of-Work invariant: persist domain outputs BEFORE committing item checkpoints
            if self.on_batch_complete is not None:
                await self.on_batch_complete(batch_outputs, batch_records)

            if self.custom_commit_fn is not None:
                await self.custom_commit_fn(
                    self.phase_tag, batch_outputs, batch_records
                )
            elif self.checkpoint_store is not None and batch_records:
                await self.checkpoint_store.commit_phase_items(
                    self.phase_tag, batch_records
                )

            if on_batch_advance is not None:
                on_batch_advance(len(pending_batch))

        return BatchExecutionResult(
            outputs=all_outputs,
            records=all_records,
            succeeded_count=succeeded_total,
            failed_count=failed_total,
        )


class CheckpointedStreamExecutor[StreamKeyT, ItemT, StateT, OutT]:
    """Sequential intra-stream executor with bounded cross-stream concurrency and state snapshots.

    Implements Pattern 2 (Unit-of-Work Checkpointing) and Pattern 6 (Stateful Sequential
    Context ``S_t = f(S_{t-1}, x_t)``):
    1. Partitions pending items into independent streams via ``stream_key_fn`` and orders
       each stream sequentially via ``sort_key_fn``.
    2. Bounds concurrent stream execution using ``asyncio.Semaphore(max_concurrent_streams)``.
    3. Restores prior working state via :meth:`PhaseCheckpointStore.get_chunk_state_snapshot`
       when resuming a partially completed stream mid-way.
    4. Executes items sequentially within each stream, persisting domain outputs before
       saving state snapshots.
    5. Enforces a shared first-batch systematic failure circuit-breaker across streams.

    Parameters
    ----------
    checkpoint_store : PhaseCheckpointStore or None
        Optional checkpoint store supporting state snapshot persistence.
    phase_tag : str
        Lineage-scoped phase identifier tag.
    item_key_fn : Callable[[ItemT], str]
        Deterministic identifier extractor for items.
    stream_key_fn : Callable[[ItemT], StreamKeyT]
        Stream partitioning key extractor (e.g. ``(source_doc_id, chapter_id)``).
    sort_key_fn : Callable[[ItemT], Any]
        Intra-stream sequential ordering key (e.g. ``sequence_index``).
    init_state_fn : Callable[[StreamKeyT], StateT]
        Factory initializing isolated working state for a stream.
    restore_state_fn : Callable[[StateT, dict[str, Any]], None]
        Callback restoring stream state from a persisted snapshot dictionary.
    snapshot_state_fn : Callable[[StateT], dict[str, Any]]
        Callback serializing stream state into a snapshot dictionary.
    process_item_fn : Callable[[ItemT, StateT], Awaitable[OutT]]
        Sequential step processor evaluating ``item`` against ``state`` and updating ``state``.
    persist_item_fn : Callable[[ItemT, OutT], Awaitable[None]] or None, default None
        Unit-of-work persistence callback invoked after ``process_item_fn`` succeeds and
        before saving the state snapshot.
    max_concurrent_streams : int, default 4
        Maximum number of streams evaluated concurrently.
    first_batch_size : int, default 10
        Window size for the initial systematic failure guard.
    guard_systematic_failure : bool, default True
        Whether to abort when the initial ``first_batch_size`` items fail identically.
    """

    def __init__(
        self,
        checkpoint_store: PhaseCheckpointStore | None,
        phase_tag: str,
        *,
        item_key_fn: Callable[[ItemT], str],
        stream_key_fn: Callable[[ItemT], StreamKeyT],
        sort_key_fn: Callable[[ItemT], Any],
        init_state_fn: Callable[[StreamKeyT], StateT],
        restore_state_fn: Callable[[StateT, dict[str, Any]], None],
        snapshot_state_fn: Callable[[StateT], dict[str, Any]],
        process_item_fn: Callable[[ItemT, StateT], Awaitable[OutT]],
        persist_item_fn: Callable[[ItemT, OutT], Awaitable[None]] | None = None,
        max_concurrent_streams: int = 4,
        first_batch_size: int = 10,
        guard_systematic_failure: bool = True,
    ) -> None:
        self.checkpoint_store = checkpoint_store
        self.phase_tag = phase_tag
        self.item_key_fn = item_key_fn
        self.stream_key_fn = stream_key_fn
        self.sort_key_fn = sort_key_fn
        self.init_state_fn = init_state_fn
        self.restore_state_fn = restore_state_fn
        self.snapshot_state_fn = snapshot_state_fn
        self.process_item_fn = process_item_fn
        self.persist_item_fn = persist_item_fn
        self.max_concurrent_streams = max(1, max_concurrent_streams)
        self.first_batch_size = max(1, first_batch_size)
        self.guard_systematic_failure = guard_systematic_failure

    async def execute(
        self,
        pending_items: Sequence[ItemT],
        *,
        all_items: Sequence[ItemT] | None = None,
        on_item_advance: Callable[[int], None] | None = None,
    ) -> BatchExecutionResult[OutT]:
        """Execute partitioned sequential streams concurrently.

        Parameters
        ----------
        pending_items : Sequence of ItemT
            Unprocessed items remaining for this phase.
        all_items : Sequence of ItemT or None, optional
            Complete sequence of items (including already processed ones) used to locate
            the predecessor item when restoring state snapshots mid-stream.
        on_item_advance : Callable[[int], None] or None, optional
            Progress callback invoked as each item completes.

        Returns
        -------
        BatchExecutionResult of OutT
            Aggregated outputs, item checkpoint records, and completion counts.

        Raises
        ------
        SystematicBatchFailureError
            If the first ``min(len(pending_items), first_batch_size)`` items fail with
            the same exception type and zero items have succeeded.
        """
        if not pending_items:
            return BatchExecutionResult(
                outputs=[], records=[], succeeded_count=0, failed_count=0
            )

        stream_pending_map: dict[StreamKeyT, list[ItemT]] = defaultdict(list)
        for item in pending_items:
            stream_pending_map[self.stream_key_fn(item)].append(item)

        stream_all_map: dict[StreamKeyT, list[ItemT]] = defaultdict(list)
        for item in all_items if all_items is not None else pending_items:
            stream_all_map[self.stream_key_fn(item)].append(item)

        stream_keys = sorted(stream_pending_map.keys())  # type: ignore[type-var]
        for k in stream_keys:
            stream_pending_map[k].sort(key=self.sort_key_fn)
            stream_all_map[k].sort(key=self.sort_key_fn)

        sem = asyncio.Semaphore(self.max_concurrent_streams)
        first_batch_target = min(len(pending_items), self.first_batch_size)
        succeeded_total = 0
        all_failures: list[Exception] = []

        async def _run_single_stream(
            stream_key: StreamKeyT,
        ) -> tuple[list[OutT], list[PhaseItemRecord]]:
            nonlocal succeeded_total
            async with sem:
                state = self.init_state_fn(stream_key)
                stream_pending = stream_pending_map[stream_key]
                stream_all = stream_all_map[stream_key]

                # Mid-stream crash recovery from predecessor snapshot
                if self.checkpoint_store is not None and stream_all and stream_pending:
                    first_pending_key = self.item_key_fn(stream_pending[0])
                    first_idx = next(
                        (
                            i
                            for i, candidate in enumerate(stream_all)
                            if self.item_key_fn(candidate) == first_pending_key
                        ),
                        0,
                    )
                    if first_idx > 0:
                        prior_key = self.item_key_fn(stream_all[first_idx - 1])
                        prior_snapshot = (
                            await self.checkpoint_store.get_chunk_state_snapshot(
                                self.phase_tag, prior_key
                            )
                        )
                        if prior_snapshot is not None:
                            self.restore_state_fn(state, prior_snapshot)
                            logger.info(
                                "Resumed working state for stream %s from prior item %s",
                                stream_key,
                                prior_key,
                            )

                stream_outputs: list[OutT] = []
                stream_records: list[PhaseItemRecord] = []

                for item in stream_pending:
                    key = self.item_key_fn(item)
                    try:
                        output = await self.process_item_fn(item, state)
                    except Exception as exc:
                        logger.error(
                            "Item %s processing failed (will retry on re-run): %s",
                            key,
                            exc,
                        )
                        all_failures.append(exc)
                        stream_records.append(
                            PhaseItemRecord(key=key, status="failed", error=str(exc))
                        )
                        if (
                            self.guard_systematic_failure
                            and succeeded_total == 0
                            and len(all_failures) == first_batch_target
                            and first_batch_target > 0
                        ):
                            failure_types = {type(e) for e in all_failures}
                            if len(failure_types) == 1:
                                first_exc = all_failures[0]
                                raise SystematicBatchFailureError(
                                    f"All {first_batch_target} items of the first batch failed "
                                    f"with {type(first_exc).__name__}: {first_exc}. "
                                    f"This is a configuration or interface error, not a per-item "
                                    f"data error — aborting {self.phase_tag}."
                                ) from first_exc
                        continue

                    if self.persist_item_fn is not None:
                        await self.persist_item_fn(item, output)

                    if self.checkpoint_store is not None:
                        await self.checkpoint_store.save_chunk_state_snapshot(
                            self.phase_tag, key, self.snapshot_state_fn(state)
                        )

                    succeeded_total += 1
                    stream_outputs.append(output)
                    stream_records.append(
                        PhaseItemRecord(key=key, status="completed")
                    )
                    if on_item_advance is not None:
                        on_item_advance(1)

                return stream_outputs, stream_records

        stream_results = await asyncio.gather(
            *(_run_single_stream(k) for k in stream_keys)
        )

        all_outputs: list[OutT] = []
        all_records: list[PhaseItemRecord] = []
        for s_outputs, s_records in stream_results:
            all_outputs.extend(s_outputs)
            all_records.extend(s_records)

        return BatchExecutionResult(
            outputs=all_outputs,
            records=all_records,
            succeeded_count=succeeded_total,
            failed_count=len(all_failures),
        )


# Alias for alternative terminology
BatchCheckpointExecutor = CheckpointedBatchExecutor

