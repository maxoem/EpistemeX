# [ISSUE-110] SQLite Atomic Checkpoint Store & Elimination of $O(N^2)$ Full-File Rewrites

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-110` |
| **Domain / Category** | `12-SQLite Persistence & Storage Ports` (Intra-Phase Durability, WAL Checkpointing, Poison-Pill Quarantine) |
| **Target Package(s)** | `packages/episteme-pipeline` (`storage/`, `artifacts/`, `runtime/`, `pipeline.py`) |
| **Depends On** | `ISSUE-108` |
| **Complexity** | **MEDIUM** |
| **Recommended Model** | **Neon** |
| **Reasoning Effort** | **MEDIUM** |
| **Priority** | **High** |
| **Status** | `Open` |
| **ADR Reference** | [ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md), [ADR-0016](../../docs/adr/0016-phase-3-within-phase-checkpointing-and-atomicity.md), [ADR-0009](../../docs/adr/0009-sota-dual-memory-episodic-working-memory.md) |

---

## 1. Problem & Architectural Context

[`FileSystemCheckpointStore`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/checkpoint_store.py) enables offline crash recovery ([ADR-0016](../../docs/adr/0016-phase-3-within-phase-checkpointing-and-atomicity.md)), Phase 2 working memory state snapshots ([ADR-0009](../../docs/adr/0009-sota-dual-memory-episodic-working-memory.md), `ISSUE-051`), and poison-pill quarantine. However, inspecting its implementation reveals a severe scalability defect:

- Although `docs/architecture/artifact_run_model.md` calls it an "append-only JSONL WAL", `_save_phase_state()` serializes the **entire** accumulated dictionary (`processed_chunks`, `processed_items`, `committed_triples`, `chunk_snapshots`) with `json.dumps(..., indent=2)` and atomically replaces the entire file on *every* batch commit.
- For a **100–500 page monograph** generating 10,000+ Phase 3 candidate pairs (200+ batches) and thousands of committed triples, rewriting the growing file on every batch produces **$O(N^2)$ disk I/O**, turning checkpointing into a major bottleneck and risking OOM from keeping the entire JSON state dictionary in memory.

---

## 2. Architectural Upgrades Included (`[NO LEGACY]`)

- **True $O(B)$ Transactional Batch Checkpoints**: Replace full-file JSON rewrites with `SqliteCheckpointStore` executing incremental row upserts inside a single `BEGIN IMMEDIATE ... COMMIT` transaction per batch (`commit_phase_batch`, `commit_phase_items`, `save_chunk_state_snapshot`).
- **Safe Bind-Parameter Chunking**: Phase 3 can pass tens of thousands of candidate keys into `filter_unprocessed_items(item_keys, phase)`. SQLite's parameter limit (`SQLITE_MAX_VARIABLE_NUMBER`, 999 or 32,766 depending on build) is handled cleanly by querying in fixed 500-key slices (or a temp table within a read transaction) so large monographs never raise `OperationalError: too many SQL variables`.
- **Clean Removal of `FileSystemCheckpointStore`**: Wire `SqliteCheckpointStore` (from `StorageBundle.checkpoints`) as the default in `PipelineFactory` and `Pipeline`, and remove `episteme_pipeline/artifacts/checkpoint_store.py` once tests migrate. Preserve Neo4j's optional `PhaseCheckpointStore` adapter (`graph/neo4j_store.py`) implementing the decoupled `protocols/storage.py:PhaseCheckpointStore`.

---

## 3. Detailed Design & Implementation Specification

### 3.1 `SqliteCheckpointStore` (`episteme_pipeline/storage/sqlite_checkpoint_store.py`)

Implements `PhaseCheckpointStore` against `episteme.db` tables (`phase_checkpoints`, `checkpoint_triples`, `checkpoint_snapshots`):

1. **`filter_unprocessed_items(item_keys, phase)`**:
   - Slices `item_keys` in batches of 500; executes `SELECT item_key FROM phase_checkpoints WHERE phase_key = ? AND status IN ('completed', 'failed') AND item_key IN (...)` to exclude both completed items and quarantined poison-pill items (`status = 'failed'`), preserving input order.
2. **`commit_phase_batch(phase, triples, items)`**:
   - Executes inside one atomic SQLite transaction (`BEGIN IMMEDIATE ... COMMIT`):
     - Upserts `PhaseItemRecord` rows into `phase_checkpoints` (`ON CONFLICT(phase_key, item_key) DO UPDATE SET status=excluded.status, error_message=excluded.error_message, run_id=excluded.run_id, updated_at=excluded.updated_at`).
     - Inserts extracted `L2Triple` records into `checkpoint_triples` (`triple_json`), associating each triple with `phase_key` and `item_key` (if present, or batch marker) to maintain atomic single-transaction durability per [ADR-0016](../../docs/adr/0016-phase-3-within-phase-checkpointing-and-atomicity.md).
3. **`commit_phase_items(phase, items)` / `mark_chunks_processed(chunk_ids, phase)`**:
   - Batch-upserts `phase_checkpoints` with `status = 'completed'`.
4. **`save_chunk_state_snapshot` / `get_chunk_state_snapshot`**:
   - Upserts / fetches `WorkingMemoryState` JSON snapshots keyed by `(phase_key, chunk_id)` in `checkpoint_snapshots` in $O(1)$ without rewriting other chunks' snapshots.
5. **`get_committed_triples(phase)`**:
   - Streams `SELECT triple_json FROM checkpoint_triples WHERE phase_key = ? ORDER BY id ASC` and validates `L2Triple`.
6. **`clear_phase_checkpoints(phase)`**:
   - Atomically deletes all rows matching `phase_key = ?` across `phase_checkpoints`, `checkpoint_triples`, and `checkpoint_snapshots`.

---

## 4. Testing & Verification Strategy

- Parameterized contract test suite (`tests/unit/storage/test_checkpoint_contracts.py`) verifying `SqliteCheckpointStore` and `InMemoryCheckpointStore`:
  - Crash recovery: commit Batch 0 + Batch 1, simulate crash mid-Batch 2, reopen DB, verify `filter_unprocessed_items` skips Batches 0–1 and `get_committed_triples` returns exact Batch 0–1 triples.
  - Poison-pill quarantine (`status='failed'`): verify failed items are skipped on subsequent resume while error diagnostics remain queryable.
  - Large input safety: pass `10,000` item keys to `filter_unprocessed_items()` confirming chunking stays below SQLite bind-parameter limits.
  - Phase 2 `WorkingMemoryState` snapshot persistence and restoration.
  - `BatchCheckpointExecutor` integration tests verifying zero regressions in Phase 2, Phase 3, and Phase 4 runners.

---

## 5. Acceptance Criteria

- [ ] `SqliteCheckpointStore` implements all `PhaseCheckpointStore` methods with atomic single-transaction batch commits.
- [ ] `filter_unprocessed_items` safely handles `>= 10,000` keys via parameter chunking.
- [ ] `PipelineFactory` and `Pipeline` default to `StorageBundle.checkpoints` (`SqliteCheckpointStore`), and `FileSystemCheckpointStore` is cleanly removed.
- [ ] Neo4j optional checkpoint store compiles and passes tests against the decoupled `PhaseCheckpointStore` protocol.
