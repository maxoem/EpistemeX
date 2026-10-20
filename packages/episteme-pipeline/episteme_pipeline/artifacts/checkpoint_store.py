"""Filesystem-backed intra-phase checkpoint store for offline pipeline execution.

Provides :class:`FileSystemCheckpointStore`, an implementation of
:class:`~episteme_pipeline.protocols.graph_store.PhaseCheckpointStore` that
persists chunk and item checkpoints to local JSON files scoped by phase and
``lineage_fingerprint``. Enables crash recovery and resumption with zero Neo4j
dependency.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Triple,
    PhaseItemRecord,
)
from episteme_pipeline.protocols.graph_store import PhaseCheckpointStore


def _safe_phase_filename(phase: str) -> str:
    """Convert an arbitrary scoped phase key into a filesystem-safe filename.

    Parameters
    ----------
    phase : str
        Phase key, e.g. ``"phase2:<lineage_fingerprint>"``.

    Returns
    -------
    str
        Safe filename ending with ``.json``.
    """
    prefix = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in phase[:48])
    digest = hashlib.sha256(phase.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}__{digest}.json"


class FileSystemCheckpointStore(PhaseCheckpointStore):
    """Filesystem-backed :class:`PhaseCheckpointStore` scoped by phase and lineage.

    Parameters
    ----------
    checkpoint_dir : str or Path
        Directory where per-phase checkpoint JSON files are persisted.
    """

    def __init__(self, checkpoint_dir: str | Path) -> None:
        self._checkpoint_dir = Path(checkpoint_dir)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict[str, Any]] = {}

    def _phase_path(self, phase: str) -> Path:
        return self._checkpoint_dir / _safe_phase_filename(phase)

    def _load_phase_state(self, phase: str) -> dict[str, Any]:
        if phase in self._cache:
            return self._cache[phase]
        path = self._phase_path(phase)
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                state = {
                    "phase": phase,
                    "processed_chunks": set(raw.get("processed_chunks", [])),
                    "processed_items": dict(raw.get("processed_items", {})),
                    "committed_triples": list(raw.get("committed_triples", [])),
                    "chunk_snapshots": dict(raw.get("chunk_snapshots", {})),
                }
                self._cache[phase] = state
                return state
            except (OSError, json.JSONDecodeError):
                pass
        state = {
            "phase": phase,
            "processed_chunks": set(),
            "processed_items": {},
            "committed_triples": [],
            "chunk_snapshots": {},
        }
        self._cache[phase] = state
        return state

    def _save_phase_state(self, phase: str, state: dict[str, Any]) -> None:
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        path = self._phase_path(phase)
        serializable = {
            "phase": phase,
            "processed_chunks": sorted(state["processed_chunks"]),
            "processed_items": state["processed_items"],
            "committed_triples": state["committed_triples"],
            "chunk_snapshots": state.get("chunk_snapshots", {}),
        }
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        tmp_path.replace(path)

    async def mark_chunk_processed(self, chunk_id: str, phase: str) -> None:
        """Mark a single chunk as processed for ``phase``.

        Parameters
        ----------
        chunk_id : str
            Chunk identifier.
        phase : str
            Phase identifier (optionally lineage-scoped).
        """
        await self.mark_chunks_processed([chunk_id], phase)

    async def mark_chunks_processed(
        self, chunk_ids: list[str], phase: str
    ) -> None:
        """Mark multiple chunks as processed for ``phase``.

        Parameters
        ----------
        chunk_ids : list of str
            Chunk identifiers.
        phase : str
            Phase identifier (optionally lineage-scoped).
        """
        if not chunk_ids:
            return
        state = self._load_phase_state(phase)
        for cid in chunk_ids:
            state["processed_chunks"].add(cid)
            state["processed_items"][cid] = {
                "key": cid,
                "status": "completed",
            }
        self._save_phase_state(phase, state)

    async def get_unprocessed_chunks(
        self, phase: str, limit: int | None = None
    ) -> list[L1Chunk]:
        """Return unprocessed chunks stored in the checkpoint backend.

        Since :class:`FileSystemCheckpointStore` stores only lightweight IDs and
        triples rather than full chunk texts, chunk selection filters the in-memory
        :class:`EpistemicStateView` chunks via :meth:`filter_unprocessed_items`.

        Parameters
        ----------
        phase : str
            Phase identifier.
        limit : int or None, optional
            Optional limit.

        Returns
        -------
        list of L1Chunk
            Always empty list; callers filter ``input_chunks`` via
            :meth:`filter_unprocessed_items`.
        """
        return []

    async def filter_unprocessed_items(
        self, item_keys: list[str], phase: str
    ) -> list[str]:
        """Return subset of ``item_keys`` not yet processed for ``phase``.

        Parameters
        ----------
        item_keys : list of str
            Candidate item or chunk keys.
        phase : str
            Phase identifier (optionally lineage-scoped).

        Returns
        -------
        list of str
            Unprocessed keys in original order.
        """
        state = self._load_phase_state(phase)
        processed_chunks: set[str] = state["processed_chunks"]
        processed_items: dict[str, Any] = state["processed_items"]
        return [
            key
            for key in item_keys
            if key not in processed_items and key not in processed_chunks
        ]

    async def commit_phase_batch(
        self,
        phase: str,
        triples: list[L2Triple],
        items: list[PhaseItemRecord],
    ) -> None:
        """Atomically persist batch triples and item completion records for ``phase``.

        Parameters
        ----------
        phase : str
            Phase identifier (optionally lineage-scoped).
        triples : list of L2Triple
            Extracted triples in the current batch.
        items : list of PhaseItemRecord
            Evaluated item records in the current batch.
        """
        state = self._load_phase_state(phase)
        for item in items:
            state["processed_items"][item.key] = item.model_dump(mode="json")
        for triple in triples:
            state["committed_triples"].append(triple.model_dump(mode="json"))
        self._save_phase_state(phase, state)

    async def commit_phase_items(
        self, phase: str, items: list[PhaseItemRecord]
    ) -> None:
        """Persist phase item checkpoints without requiring triple upserts.

        Parameters
        ----------
        phase : str
            Phase identifier tag.
        items : list[PhaseItemRecord]
            Phase item checkpoint records to persist.
        """
        state = self._load_phase_state(phase)
        for item in items:
            state["processed_items"][item.key] = item.model_dump(mode="json")
        self._save_phase_state(phase, state)

    async def save_chunk_state_snapshot(
        self, phase: str, chunk_id: str, snapshot: dict[str, Any]
    ) -> None:
        """Persist a serialized state machine snapshot associated with a chunk checkpoint.

        Parameters
        ----------
        phase : str
            Phase identifier tag.
        chunk_id : str
            Source chunk identifier.
        snapshot : dict[str, Any]
            State dictionary snapshot.
        """
        state = self._load_phase_state(phase)
        snapshots = state.setdefault("chunk_snapshots", {})
        snapshots[chunk_id] = dict(snapshot)
        self._save_phase_state(phase, state)

    async def get_chunk_state_snapshot(
        self, phase: str, chunk_id: str
    ) -> dict[str, Any] | None:
        """Retrieve a prior serialized state machine snapshot for a chunk checkpoint.

        Parameters
        ----------
        phase : str
            Phase identifier tag.
        chunk_id : str
            Source chunk identifier.

        Returns
        -------
        dict[str, Any] or None
            Restored state snapshot, or None if no prior snapshot was recorded.
        """
        state = self._load_phase_state(phase)
        snapshots = state.get("chunk_snapshots", {})
        res = snapshots.get(chunk_id)
        return dict(res) if res is not None else None


    async def get_committed_triples(self, phase: str) -> list[L2Triple]:
        """Return all :class:`L2Triple` instances committed for ``phase``.

        Parameters
        ----------
        phase : str
            Phase identifier (optionally lineage-scoped).

        Returns
        -------
        list of L2Triple
            Hydrated triples from prior batches of ``phase``.
        """
        state = self._load_phase_state(phase)
        return [
            L2Triple.model_validate(raw) for raw in state["committed_triples"]
        ]

    async def clear_phase_checkpoints(self, phase: str) -> None:
        """Delete all checkpoints recorded for ``phase``.

        Parameters
        ----------
        phase : str
            Phase identifier (optionally lineage-scoped).
        """
        self._cache.pop(phase, None)
        path = self._phase_path(phase)
        if path.exists():
            path.unlink()

    async def close(self) -> None:
        """Close checkpoint store resources (no-op)."""
        return None
