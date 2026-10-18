"""Shared work-list selection for the chunk-processing phases (F-07).

Phase 2 (entity discovery) and Phase 4 (argument mining) answer the same
question — *which chunks does this phase still owe work on?* — and both had
their own copy of the answer. The copies diverged: Phase 4's treated **every**
chunk in the graph as already processed, so once Phase 1 had written anything
the fallback always produced an empty work list and the phase returned
immediately. One implementation, used by both.
"""

from __future__ import annotations

from collections.abc import Sequence

from episteme_pipeline.contracts.domain import L1Chunk
from episteme_pipeline.protocols.graph_store import (
    GraphReader,
    PhaseCheckpointStore,
    ProcessingGraph,
)


async def select_pending_chunks(
    graph_store: ProcessingGraph | PhaseCheckpointStore | None,
    phase_tag: str,
    view_chunks: Sequence[L1Chunk],
) -> list[L1Chunk]:
    """Return the chunks ``phase_tag`` still has to process.

    When ``graph_store`` is ``None``, all ``view_chunks`` are returned. When
    ``graph_store`` implements ``PhaseCheckpointStore`` only (such as
    ``FileSystemCheckpointStore``), pending chunks are filtered directly via
    ``filter_unprocessed_items``. When ``graph_store`` also implements
    ``GraphReader`` (such as ``ProcessingGraph``), ``get_unprocessed_chunks``
    and ``get_chunks(filters={f"{phase_tag}_processed": True})`` are consulted.

    Parameters
    ----------
    graph_store : ProcessingGraph | PhaseCheckpointStore | None
        Checkpoint or processing graph store for the current run.
    phase_tag : str
        The phase's checkpoint tag, e.g. ``"phase2"`` or
        ``"phase2:<lineage_fingerprint>"``.
    view_chunks : Sequence[L1Chunk]
        Chunks carried by the incoming artifact view.

    Returns
    -------
    list of L1Chunk
        Chunks remaining to be processed in this phase.
    """
    if graph_store is None:
        return list(view_chunks)

    if isinstance(graph_store, PhaseCheckpointStore) and not isinstance(
        graph_store, GraphReader
    ):
        unprocessed_ids = set(
            await graph_store.filter_unprocessed_items(
                [chunk.id for chunk in view_chunks], phase_tag
            )
        )
        return [chunk for chunk in view_chunks if chunk.id in unprocessed_ids]

    pending = await graph_store.get_unprocessed_chunks(phase_tag)
    if pending:
        return pending

    processed = await graph_store.get_chunks(
        filters={f"{phase_tag}_processed": True}
    )
    processed_ids = {chunk.id for chunk in processed}
    return [chunk for chunk in view_chunks if chunk.id not in processed_ids]


__all__ = ["select_pending_chunks"]
