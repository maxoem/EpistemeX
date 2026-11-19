# [ISSUE-113] Studio Backend Adapter Decomposition, Indexed Query APIs & Docker Read-Only Hardening

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-113` |
| **Domain / Category** | `12-SQLite Persistence & Storage Ports` (Studio Backend, God-Class Decomposition, Query APIs, Container Security) |
| **Target Package(s)** | `packages/episteme-studio` (`adapters/`, `services/`, `api/`, `runtime/`, `lifespan.py`, `settings.py`, `fixtures/`) |
| **Depends On** | `ISSUE-109`, `ISSUE-112` |
| **Complexity** | **HIGH** |
| **Recommended Model** | **Argon** |
| **Reasoning Effort** | **HIGH** |
| **Priority** | **Critical** |
| **Status** | `Open` |
| **ADR Reference** | [ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md), [ADR-0010](../../docs/adr/0010-graph-preview-driver-selection-neo4j.md), [ADR-0013](../../docs/adr/0013-per-run-neo4j-credentials-and-graph-fallback.md), [Docker Guide](../../docs/deployment/docker.md) |

---

## 1. Problem & Architectural Context

Inspecting `packages/episteme-studio/src/episteme_studio/` exposes severe scalability and clean-architecture bottlenecks in the Studio backend:

1. **1,349-Line God-Adapter (`adapters/artifact_reader.py`)**: `ArtifactReader` handles manifest discovery, multi-directory (`extra_*_dirs`) filesystem traversal, OS PID liveness healing, `parent_run_id` recursion, size calculations, graph materialization, evidence trail extraction, and evaluation helpers in a single class.
2. **Per-Request Adapter Instantiation**: `RunService.from_settings`, `GraphService.from_settings`, and `api/runs.py:get_graph_service` instantiate fresh `ArtifactReader(...)` objects per HTTP request rather than injecting shared lifespan-managed ports via `api/deps.py`.
3. **$O(\text{Total Artifacts})$ Sidebar & Filter Queries**: `ArtifactReader.list_runs()` parses every artifact JSON file across every run just to sum `size_bytes`; `list_artifacts(run_id, kind=...)` reads every artifact file including embeddings before filtering; `GET /api/runs/{run_id}/events` only streams from RAM `EventBroker` (`capacity=10000`) with zero historical query endpoint.
4. **Hardcoded Flat-File Worker & Lifespan Reflection**: `worker.py` line 462 hardcodes `JsonRunManifestStore(".pipeline_runs")`; `lifespan.py` uses `hasattr`/`getattr` checks against `app.state`.

---

## 2. Architectural Upgrades Included (`[NO LEGACY]`)

- **Decompose `ArtifactReader` into Focused Adapters**: Replace the 1,349-line `ArtifactReader` with three cohesive single-responsibility adapters inside `episteme_studio/adapters/` backed by `StorageBundle`:
  1. `RunQueryAdapter` (`adapters/run_query_adapter.py`): `list_runs`, `get_run`, `list_artifacts` (paginated/filtered), `abort_run_cleanup`.
  2. `GraphProjectionAdapter` (`adapters/graph_projection_adapter.py`): `get_graph`, `get_node_evidence`, `get_lineage_envelopes` (explicitly passing `include_embeddings=False` so graph visualization never loads `embedding_blob`).
  3. `EventQueryAdapter` (`adapters/event_query_adapter.py`): `query_history`, `get_summary`, mapping `StoredEventRecord` → `StudioEvent`.
- **Lifespan-Managed DI (`lifespan.py` & `api/deps.py`)**: Construct one `StorageBundle` (configured from `StudioSettings` with `read_only=settings.read_only`) inside `lifespan.py`, store it on typed `app.state` without `hasattr`/`getattr`, inject via FastAPI `Depends(...)`, and `await storage.close()` cleanly on shutdown.
- **Keep `adapters/` as the Strict Anti-Corruption Layer (`SPEC.md §2` D-01)**: Only `episteme_studio/adapters/` imports `episteme_pipeline.*` (`StorageBundle`, `EventQuery`, `ArtifactQuery`). `domain/`, `services/`, and `api/` stay 100% decoupled from pipeline types.

---

## 3. Detailed Design & Implementation Specification

### 3.1 `StudioSettings` & Docker Compose (`settings.py`, `docker-compose.yml`)

- Add `db_path: Path | None = None` (`EPISTEME_STUDIO_DB_PATH`) and `cache_db_path: Path | None = None` (`EPISTEME_STUDIO_CACHE_DB_PATH`), defaulting cleanly relative to `runs_dir` (`<runs_dir>/episteme.db`, `<runs_dir>/llm_cache.db`).
- In `--demo --read-only` mode ([`docker.md`](../../docs/deployment/docker.md)): support either mounting/opening a pre-seeded read-only `demo.db` via SQLite URI `mode=ro&immutable=1` or hydrating canned demo runs into `/tmp/episteme_demo.db` (leveraging `--tmpfs /tmp`) when `demo_mode=True`. Verify zero writes occur outside `/tmp` under `--read-only`.

### 3.2 Upgraded Services & Worker (`services/`, `adapters/worker.py`, `runtime/executor.py`)

- Refactor `RunService`, `GraphService`, `DiffService`, `EvaluationAdapter`, and `OverlayService` to accept the decomposed adapters via constructor DI (no per-request `from_settings()` filesystem scanning).
- Update `worker.py` (including `_run_demo_pipeline`) and `PipelineExecutor` to write manifests, artifacts, and events into the configured `StorageBundle` (eliminating `JsonRunManifestStore(".pipeline_runs")`).

### 3.3 New & Upgraded REST/SSE Endpoints (`api/runs.py`, `domain/runs.py`, `domain/events.py`)

1. **`GET /api/runs`**: Powered by `RunManifestStore.list_run_summaries()` (`< 5 ms` even with dozens of 500-page runs on disk).
2. **`GET /api/runs/{run_id}/artifacts`**: Add optional query params `kind`, `phase`, `search`, `latest_only: bool = True`, `cursor: str | None = None`, `limit: int = 200` returning paginated `ArtifactPageResponse` (omitting heavy embeddings).
3. **`GET /api/runs/{run_id}/events/history`**: Query `EventQueryAdapter` with `phase`, `kind`, `level`, `q` (FTS5 search), `after_seq`, `before_seq`, `limit` (`<= 1000`), returning `EventPageResponse(items, total_matching, has_more, oldest_seq, newest_seq)`.
4. **`GET /api/runs/{run_id}/events/summary`**: Return `EventSummaryResponse` (counts by level, phase, kind, total events, time range).
5. **`GET /api/runs/{run_id}/events` (SSE Seamless Handoff)**: If `since` / `Last-Event-ID` predates the oldest sequence in `EventBroker`'s live ring buffer, stream the historical gap first from `SqliteEventStore.query_events(after_seq=since_seq)` and seamlessly continue into live `EventBroker.subscribe(...)` without sequence gaps or duplicates.

---

## 4. Testing & Verification Strategy

- Studio FastAPI integration tests (`packages/episteme-studio/tests/`):
  - `GET /api/runs` & `GET /api/runs/{id}/graph` over SQLite-backed runs (verifying zero `embedding_blob` reads and `< 20 ms` latency on 25k-artifact fixture runs).
  - `GET /api/runs/{id}/events/history` pagination, FTS5 `q` search, `phase`/`level`/`kind` filtering, and `GET /api/runs/{id}/events/summary`.
  - SSE replay continuity test: emit 15,000 events (exceeding `EventBroker(capacity=10000)`), connect with `since=500`, verify events `501..15000` arrive in exact sequence without eviction gap.
  - `--demo --read-only` test simulating read-only SQLite URI (`mode=ro&immutable=1`) verifying all read endpoints return `200 OK` and all write endpoints continue returning `403`.
  - AST check verifying zero `hasattr`/`getattr` in `lifespan.py` and zero `episteme_pipeline` imports outside `adapters/`.

---

## 5. Acceptance Criteria

- [ ] Monolithic `ArtifactReader` is cleanly replaced by `RunQueryAdapter`, `GraphProjectionAdapter`, and `EventQueryAdapter` injected via `lifespan.py` / `api/deps.py`.
- [ ] `GET /api/runs/{run_id}/events/history`, `.../events/summary`, and paginated `.../artifacts` endpoints are live and schema-documented.
- [ ] SSE stream seamlessly bridges SQLite history to live `EventBroker` events without >10k ring-buffer drops.
- [ ] `--demo --read-only` mode works cleanly against SQLite immutable URI or `/tmp` demo DB; `worker.py` no longer references `JsonRunManifestStore`.
