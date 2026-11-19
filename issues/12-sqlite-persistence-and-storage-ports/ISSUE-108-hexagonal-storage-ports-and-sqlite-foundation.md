# [ISSUE-108] Hexagonal Storage Ports, `StorageConfig`, and SQLite Engine Foundation

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-108` |
| **Domain / Category** | `12-SQLite Persistence & Storage Ports` (Hexagonal Ports, Configuration, Connection & Migration Engine) |
| **Target Package(s)** | `packages/episteme-pipeline` (`protocols/`, `config.py`, `storage/`) |
| **Depends On** | — (Stage 1 Foundation) |
| **Complexity** | **HIGH** |
| **Recommended Model** | **Argon** |
| **Reasoning Effort** | **HIGH** |
| **Priority** | **Critical** |
| **Status** | `Open` |
| **ADR Reference** | [ADR-0025: Embedded SQLite Default Persistence & Storage Ports](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md) |

---

## 1. Problem & Architectural Context

Persistence contracts in `episteme-pipeline` are currently fragmented, under-specified, or bypassed:

1. [`episteme_pipeline/protocols/artifact_store.py`](../../packages/episteme-pipeline/episteme_pipeline/protocols/artifact_store.py) defines only 3 methods (`write_artifact`, `get_artifact`, `list_run_artifacts`), omitting batch writes, paginated queries, pre-aggregated run stats, and lifecycle closing—causing [`pipeline.py`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py) and [`execution_engine.py`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py) to bypass the protocol and type-hint concrete `JsonArtifactStore`.
2. [`episteme_pipeline/protocols/checkpoint_store.py`](../../packages/episteme-pipeline/episteme_pipeline/protocols/checkpoint_store.py) (`CheckpointStoreProtocol`) is dead duplicate code, while the active [`PhaseCheckpointStore`](../../packages/episteme-pipeline/episteme_pipeline/protocols/graph_store.py#L215) inherits from `GraphHandle` even when backed by non-graph storage.
3. No protocol ports exist at all for **Run Manifests** (`JsonRunManifestStore`), **Structured LLM Caching** (`DiskCachedStructuredLLM`), or **Persistent Queryable Events** (`EventStore`).
4. `ExecutionConfig` (`episteme_pipeline/config.py`) exposes only directory strings (`runs_dir`, `artifacts_dir`) with no declarative `StorageConfig` describing the storage backend (`sqlite` vs. `memory`), dual database paths, WAL pragmas, or read-only container mode.

Before implementing any SQLite adapter (`ISSUE-109` through `ISSUE-112`), we must establish the unified Hexagonal port surface, configuration contracts, SQLite schema/connection engine, and deterministic `InMemoryStorageBundle`.

---

## 2. Architectural Upgrades Included (`[NO LEGACY]`)

- **Consolidate Storage Ports**: Create a single canonical module `episteme_pipeline/protocols/storage.py` defining all five persistence ports (`RunManifestStore`, `ArtifactStore`, `PhaseCheckpointStore`, `EventStore`, `LLMCacheStore`) and a typed `StorageBundle` container.
- **Delete Dead & Fragmented Protocols**: Remove `episteme_pipeline/protocols/checkpoint_store.py` (`CheckpointStoreProtocol`) and retire `episteme_pipeline/protocols/artifact_store.py` (updating callers directly to `protocols/storage.py`).
- **Decouple `PhaseCheckpointStore` from `GraphHandle`**: Checkpointing is a storage/execution concern, not a graph database handle. Give `PhaseCheckpointStore` its own `async def close() -> None` lifecycle method directly in `protocols/storage.py` (while Neo4j checkpoint implementations can implement both `GraphHandle` and `PhaseCheckpointStore` cleanly).
- **Avoid `aiosqlite` / Event-Loop Conflicts**: Per Studio D-05 (`nest_asyncio` is a dependency; uvicorn + `asyncio.run` workers create multiple loops), implement `SqliteConnectionManager` over Python stdlib `sqlite3` with thread-safe lock coordination and `asyncio.to_thread()`, eliminating background-thread loop-binding bugs.

---

## 3. Detailed Design & Implementation Specification

### 3.1 Query & Summary Contracts (`episteme_pipeline/protocols/storage.py`)

Define immutable Pydantic v2 / frozen dataclass DTOs shared by both pipeline and Studio adapters:

- **`ArtifactQuery`**: `run_id: str`, `kinds: tuple[str, ...] = ()`, `phase_name: str | None = None`, `identity_key: str | None = None`, `latest_only: bool = True`, `include_embeddings: bool = False`, `cursor: str | None = None`, `limit: int = 200`.
- **`ArtifactPage`**: `items: list[ArtifactEnvelope[ArtifactPayload]]`, `next_cursor: str | None`, `total_count: int`.
- **`RunArtifactStats`**: `run_id: str`, `artifact_count: int`, `size_bytes: int`, `counts_by_kind: dict[str, int]`.
- **`EventQuery`**: `run_id: str`, `phase: str | None = None`, `kind: str | None = None`, `level: str | None = None`, `search_query: str | None = None` (FTS5), `after_seq: int | None = None`, `before_seq: int | None = None`, `limit: int = 200`.
- **`StoredEventRecord` & `EventPage`**: Persisted event record (`run_id`, `seq`, `timestamp`, `phase`, `kind`, `level`, `component`, `entity_id`, `summary`, `payload: dict[str, Any]`) + cursor-paginated response (`items`, `total_matching`, `has_more`, `oldest_seq`, `newest_seq`).
- **`EventSummary`**: `run_id`, `total_events`, `counts_by_level`, `counts_by_phase`, `counts_by_kind`, `first_timestamp`, `last_timestamp`.
- **`CacheEntry` & `CacheStats`**: `cache_key`, `cache_version`, `cache_prefix`, `method_fp`, `output_schema`, `payload_json`, `hit_count`, `size_bytes`; aggregate stats (`total_entries`, `total_bytes`, `total_hits`, `entries_by_schema`).

### 3.2 Five Narrow Hexagonal Ports (`episteme_pipeline/protocols/storage.py`)

```python
@runtime_checkable
class RunManifestStore(Protocol):
    async def write_manifest(self, manifest: RunManifest) -> None: ...
    async def read_manifest(self, run_id: str) -> RunManifest | None: ...
    async def list_manifests(self, *, status: RunStatus | None = None, limit: int | None = None) -> list[RunManifest]: ...
    async def list_run_summaries(self, *, status: RunStatus | None = None, limit: int = 200, offset: int = 0) -> list[RunSummaryRecord]: ...
    async def latest_manifest(self, *, only_completed: bool = True) -> RunManifest | None: ...
    async def resolve_lineage(self, run_id: str) -> list[str]: ...
    async def close(self) -> None: ...

@runtime_checkable
class ArtifactStore(Protocol):
    async def write_artifact(self, artifact: ArtifactEnvelope[ArtifactPayload]) -> None: ...
    async def write_artifacts(self, artifacts: Sequence[ArtifactEnvelope[ArtifactPayload]]) -> None: ...
    async def get_artifact(self, artifact_id: str, *, run_id: str | None = None) -> ArtifactEnvelope[ArtifactPayload] | None: ...
    async def query_artifacts(self, query: ArtifactQuery) -> ArtifactPage: ...
    async def list_run_artifacts(self, run_id: str, *, include_embeddings: bool = True) -> list[ArtifactEnvelope[ArtifactPayload]]: ...
    async def list_phase_artifacts(self, run_id: str, phase_name: str, *, include_embeddings: bool = True) -> list[ArtifactEnvelope[ArtifactPayload]]: ...
    async def get_run_stats(self, run_id: str) -> RunArtifactStats: ...
    async def close(self) -> None: ...
```

Alongside `PhaseCheckpointStore` (migrated cleanly from `protocols/graph_store.py`), `EventStore` (`append_batch`, `query_events`, `get_event_summary`, `delete_run_events`, `close`), `LLMCacheStore` (`get`, `put`, `delete`, `stats`, `prune`, `clear`, `close`), and `StorageBundle` dataclass owning `manifests`, `artifacts`, `checkpoints`, `events`, `llm_cache`, plus an `async def close() -> None` method.

### 3.3 `StorageConfig` (`episteme_pipeline/config.py`)

Nest `storage: StorageConfig = Field(default_factory=StorageConfig)` inside `ExecutionConfig`:
- `backend: Literal["sqlite", "memory"] = "sqlite"` (extensible later to `"postgres"`)
- `db_path: str | None = None` (defaults dynamically to `Path(runs_dir) / "episteme.db"` if `None`)
- `cache_db_path: str | None = None` (defaults dynamically to `Path(runs_dir) / "llm_cache.db"` if `None`)
- `read_only: bool = False` (uses SQLite `mode=ro&immutable=1` URI for `--read-only` / `--demo` containers)
- `wal_mode: bool = True`
- `busy_timeout_ms: int = 10000`
- `cache_max_bytes: int | None = None` (optional LRU size bound for `llm_cache.db`)
- `cache_ttl_days: int | None = None` (optional TTL pruning bound)

### 3.4 `SqliteConnectionManager`, Migrations & `StorageFactory` (`episteme_pipeline/storage/`)

Create package `episteme_pipeline/storage/`:
- `sqlite_engine.py`:
  - `SqliteConnectionManager(db_path: Path | str, *, read_only: bool = False, wal_mode: bool = True, busy_timeout_ms: int = 10000, schema_kind: Literal["main", "cache"])`
  - Configures pragmas on connect: `PRAGMA busy_timeout=...`, `PRAGMA foreign_keys=ON`, `PRAGMA temp_store=MEMORY`, `PRAGMA cache_size=-65536`, and when writable: `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, `PRAGMA auto_vacuum=INCREMENTAL` (on cache DB).
  - Opens `file:<encoded_path>?mode=ro&immutable=1` when `read_only=True` (skipping migrations and write pragmas cleanly).
  - Applies monotonic DDL migrations via `PRAGMA user_version` (`SCHEMA_VERSION = 1`) creating the complete `episteme.db` or `llm_cache.db` schema from [ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md).
  - Provides explicit `execute_read(...)`, `execute_write(...)`, and `transaction()` context manager guarded by a `threading.RLock` + `asyncio.to_thread()` helpers (`run_read`, `run_write`).
- `memory.py`: `InMemoryRunManifestStore`, `InMemoryArtifactStore`, `InMemoryCheckpointStore`, `InMemoryEventStore`, `InMemoryLLMCacheStore`, and `InMemoryStorageBundle` for zero-I/O deterministic tests.
- `factory.py`: `StorageFactory.from_execution_config(config: ExecutionConfig) -> StorageBundle` and `StorageFactory.in_memory() -> StorageBundle`.

---

## 4. Testing & Verification Strategy

- Unit tests (`tests/unit/storage/test_sqlite_engine.py`):
  - Schema creation, idempotent re-opening, and `PRAGMA user_version` verification for both `"main"` (`episteme.db`) and `"cache"` (`llm_cache.db`).
  - WAL mode activation, `busy_timeout`, and read-only URI mode (`mode=ro&immutable=1`) over a `chmod 0444` file in a read-only parent directory (verifying zero `-wal`/`-shm` creation and explicit error on write attempts).
  - Concurrent `asyncio.gather` reader + writer stress test confirming zero `database is locked` errors under `busy_timeout=10000`.
  - `StorageFactory.from_execution_config` routing (`"sqlite"` vs. `"memory"`), `StorageBundle.close()` teardown, and zero `getattr`/`hasattr` AST check.

---

## 5. Acceptance Criteria

- [ ] `episteme_pipeline/protocols/storage.py` defines all 5 narrow storage ports, DTOs, and `StorageBundle` with complete NumPy docstrings.
- [ ] Dead `protocols/checkpoint_store.py` is deleted and `PhaseCheckpointStore` is decoupled from `GraphHandle`.
- [ ] `StorageConfig` is added to `ExecutionConfig` in `episteme_pipeline/config.py` with `"sqlite"` as default backend.
- [ ] `SqliteConnectionManager` initializes `episteme.db` and `llm_cache.db` schemas, pragmas, migrations, and read-only immutable URI mode cleanly.
- [ ] `InMemoryStorageBundle` and `StorageFactory` are implemented and covered by deterministic non-LLM tests (`rtk uv run pytest`).
