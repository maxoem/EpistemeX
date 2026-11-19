# [ISSUE-112] Persistent Batched SQLite Event Store (`SqliteEventObserver`) with FTS5 Search

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-112` |
| **Domain / Category** | `12-SQLite Persistence & Storage Ports` (Telemetry Persistence, Non-Blocking Observer, FTS5 Indexing) |
| **Target Package(s)** | `packages/episteme-pipeline` (`storage/`, `events/`, `runtime/`), `packages/episteme-studio` (`runtime/`, `adapters/`) |
| **Depends On** | `ISSUE-108` |
| **Complexity** | **MEDIUM** |
| **Recommended Model** | **Neon** |
| **Reasoning Effort** | **HIGH** |
| **Priority** | **Critical** |
| **Status** | `Open` |
| **ADR Reference** | [ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md), [Event System Architecture](../../docs/architecture/event-system.md), [Episteme Studio SPEC §4](../../packages/episteme-studio/docs/SPEC.md) |

---

## 1. Problem & Architectural Context

Today, domain events are ephemeral inside Studio and unindexed in CLI runs:
- [`episteme_studio/adapters/worker.py`](../../packages/episteme-studio/src/episteme_studio/adapters/worker.py) attaches only `StudioEventObserver` (pushing onto a multiprocessing IPC queue) and optional `LangfuseObserver`.
- [`episteme_studio/runtime/broker.py`](../../packages/episteme-studio/src/episteme_studio/runtime/broker.py) retains only `deque(maxlen=10000)` in RAM. On a **100–500 page monograph** emitting **50,000–200,000+ events**, Phase 1–3 telemetry is silently evicted before the run finishes, everything disappears when Studio restarts, and historical runs cannot be filtered or full-text searched.
- Meanwhile, [`SPEC.md §4`](../../packages/episteme-studio/docs/SPEC.md#L167-L171) imposes a strict architectural constraint: `SimpleEventEmitter.emit()` invokes `observer.on_event(event)` **synchronously on the pipeline thread**. Any synchronous SQLite write inside `on_event` would stall LLM/extraction throughput.

---

## 2. Architectural Upgrades Included (`[NO LEGACY]`)

- **Shared Event Normalization (`episteme_pipeline/events/serializer.py` or `models.py`)**: Extract deterministic event classification (`kind`, `level`, `entity_id`, concise human `summary`) into `episteme-pipeline` so `SqliteEventObserver` and Studio's [`event_mapper.py`](../../packages/episteme-studio/src/episteme_studio/adapters/event_mapper.py) share one canonical semantic mapping instead of duplicating formatting logic.
- **Non-Blocking Batched Queue Observer (`SqliteEventObserver`)**: Enforce the `SPEC.md §4` non-blocking invariant with a background daemon writer thread draining batches into single SQLite transactions, plus a strict `flush()` barrier honoring [ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md) and `ISSUE-052`.
- **De-Couple Live Streaming from Durable History**: `EventBroker` remains strictly a fast live-SSE fan-out multiplexer; all durable persistence flows through `EventStore`.

---

## 3. Detailed Design & Implementation Specification

### 3.1 `SqliteEventStore` (`episteme_pipeline/storage/sqlite_event_store.py`)

Implements `EventStore` against `episteme.db` (`events` + `events_fts` virtual table):
- **`append_batch(events: Sequence[StoredEventRecord]) -> None`**:
  - Executes inside one `BEGIN IMMEDIATE ... executemany ... COMMIT` transaction.
  - Inserts into `events(run_id, seq, timestamp, phase, kind, level, component, entity_id, summary, payload_json)`. Sync triggers automatically keep `events_fts` (FTS5 over `summary`, `kind`, `phase`, `entity_id`, `payload_json`) consistent.
- **`query_events(query: EventQuery) -> EventPage`**:
  - Composes parameterized SQL predicates for `run_id`, optional `phase`, `kind`, `level`, `after_seq`, `before_seq`, and `events_fts MATCH ?` when `search_query` is present (sanitizing FTS5 query tokens safely so punctuation like `:` or `-` in entity IDs never causes FTS5 syntax errors).
  - Returns ordered `StoredEventRecord` slices with `total_matching`, `has_more`, `oldest_seq`, and `newest_seq` for infinite scroll & cursor pagination.
- **`get_event_summary(run_id: str) -> EventSummary`**:
  - Executes SQL `GROUP BY level`, `GROUP BY phase`, `GROUP BY kind` aggregates in `< 5 ms` without loading event payloads into Python.

### 3.2 `SqliteEventObserver` (`episteme_pipeline/events/sqlite_observer.py`)

Implements `EventObserver` and `TelemetryReportingObserver`:
- `__init__(self, event_store: EventStore, *, run_id: str | None = None, batch_size: int = 100, flush_interval_s: float = 0.25, max_queue_size: int = 50_000)`
- **`on_event(event: PipelineEvent) -> None`** (synchronous, non-blocking):
  - Assigns monotonic `seq` per `run_id`, builds `StoredEventRecord`, and pushes via `queue.put_nowait()`. If the queue exceeds `max_queue_size`, drops oldest/increments `dropped_count` cleanly so backpressure never blocks extraction, surfacing `dropped_count` in `get_observer_telemetry()` (captured by `RunReport.observer_telemetry`).
- **Background Flusher Thread**:
  - Drains up to `batch_size` items or wakes on `flush_interval_s` / explicit flush sentinel, calling `event_store.append_batch_sync(batch)` (or synchronous connection manager write method).
- **`flush() -> None` & `close() -> None`**:
  - Enqueues a `threading.Event` barrier sentinel and blocks until the background writer drains and commits every preceding event, ensuring `RunCompleted` / `RunFailed` and final spans are durable before process exit.

### 3.3 Wiring Across CLI & Studio Worker

- **`runtime/runner.py` (`run_pipeline`)**: Automatically attach `SqliteEventObserver` (from `StorageBundle.events`) inside `CompositeObserver` when `StorageConfig.backend == "sqlite"`.
- **Studio Subprocess / Executor Integration**:
  - Ensure events emitted inside Studio worker runs (`run_pipeline_worker`, including demo runs and `StreamTee` terminal events via `PipelineExecutor._drain_queue`) persist cleanly to `episteme.db` with consistent `seq` numbering matching live SSE `EventBroker` sequences (persisting either via `SqliteEventObserver` in the worker or batched persistence in `PipelineExecutor._drain_queue`—choose a single writer path per run to avoid duplicate `(run_id, seq)` conflicts!).

---

## 4. Testing & Verification Strategy

- Unit & concurrency tests (`tests/unit/storage/test_sqlite_event_store.py`):
  - Emit **10,000 events** concurrently across rapid `on_event()` calls; measure `on_event()` call latency (non-blocking), call `flush()`, and assert exact 10,000 rows persisted with monotonic `(run_id, seq)` and zero duplicates.
  - FTS5 search tests: search for entity IDs containing hyphens/colons (`entity_kant::123`), relation predicates (`SUPPORTS`), error strings, and combined filters (`phase` + `level` + `q` + `after_seq`/`before_seq` pagination).
  - Failure isolation test: inject failing observer alongside `SqliteEventObserver` in `CompositeObserver` verifying pipeline continues and `observer_errors` / `dropped_events` accounting works.
  - Summary aggregation accuracy test (`get_event_summary`).

---

## 5. Acceptance Criteria

- [ ] `SqliteEventStore` and `InMemoryEventStore` implement `EventStore` with FTS5 search, cursor pagination, and SQL summary aggregates.
- [ ] `SqliteEventObserver` never blocks `on_event()` on disk I/O and guarantees full batch commit on `flush()`.
- [ ] Both CLI `run_pipeline()` runs and Studio-launched runs (including terminal/demo events) persist searchable events without duplicate `(run_id, seq)` collisions.
- [ ] 10k+ event batch ingestion, FTS5 special-character safety, and filter/pagination tests pass cleanly via `rtk uv run pytest`.
