# [ISSUE-111] Decoupled `LLMCacheStore` Port & Isolated SQLite LLM Cache (`llm_cache.db`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-111` |
| **Domain / Category** | `12-SQLite Persistence & Storage Ports` (LLM Caching, Concurrency Safety, Decorator Pattern) |
| **Target Package(s)** | `packages/episteme-pipeline` (`llm/cache.py`, `llm/structured.py`, `storage/`, `runtime/`, `evaluation/`) |
| **Depends On** | `ISSUE-108` |
| **Complexity** | **LOW** |
| **Recommended Model** | **Hydrogen** |
| **Reasoning Effort** | **MEDIUM** |
| **Priority** | **Medium** |
| **Status** | `Open` |
| **ADR Reference** | [ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md), [Cross-Cutting Concerns](../../docs/architecture/cross_cutting_concerns.md), [Design Patterns & Standards](../../docs/architecture/design_patterns_and_standards.md) |

---

## 1. Problem & Architectural Context

[`DiskCachedStructuredLLM`](../../packages/episteme-pipeline/episteme_pipeline/llm/cache.py) wraps `StructuredLLM` via the Decorator pattern, storing one JSON file per SHA-256 cache key under `.pipeline_runs/llm_cache/`. At higher concurrency and monograph scale, this causes four concrete issues:

1. **Non-Atomic Concurrent Writes**: `cache_path.write_text(...)` executes without temp-file replacement; concurrent `asyncio.gather` extraction tasks targeting overlapping prompts/chunks can produce partially written JSON files.
2. **Filesystem Coupling**: Caching is fused directly to `Path` files rather than an `LLMCacheStore` port, preventing alternative backends (`InMemoryLLMCacheStore`, SQLite, or future Redis/Postgres).
3. **No Accounting or Eviction**: There is no `hit_count`, `last_accessed_at`, total cache byte tracking, or TTL/LRU pruning.
4. **Reflection Anti-Pattern (`AGENTS.md §2`)**: Line 53 uses `getattr(base_llm, "base_llm", base_llm)` to locate the underlying LLM object for fingerprinting.

---

## 2. Architectural Upgrades Included (`[NO LEGACY]`)

- **Separate Protocol-Backed Decorator (`CachedStructuredLLM`)**: Refactor `episteme_pipeline/llm/cache.py` into `CachedStructuredLLM(base_llm: StructuredLLM, cache_store: LLMCacheStore)` that wraps any `StructuredLLM` and delegates storage solely to `LLMCacheStore`.
- **Eliminate `getattr` Reflection**: Replace `getattr(base_llm, "base_llm", base_llm)` with explicit `Fingerprintable` / `unwrap_base_llm()` support on `StructuredLLM` adapters ([`llm/structured.py`](../../packages/episteme-pipeline/episteme_pipeline/llm/structured.py)), matching [`design_patterns_and_standards.md §4.1`](../../docs/architecture/design_patterns_and_standards.md).
- **Physical Isolation in `llm_cache.db`**: Back `SqliteLLMCacheStore` with `llm_cache.db` (configured via `StorageConfig.cache_db_path`), ensuring heavy Phase 2/3/4 cache writes never contend with `episteme.db` run/event/checkpoint locks and keeping research run archives cleanly separable from disposable compute caches.
- **Remove Flat-File Cache Directory Clutter**: Replace `DiskCachedStructuredLLM` file-per-key writes cleanly at all wiring sites (`PipelineFactory.resolve_components`, `llm/structured.py:ensure_structured_llm`, `evaluation/pipelines.py`).

---

## 3. Detailed Design & Implementation Specification

### 3.1 `SqliteLLMCacheStore` (`episteme_pipeline/storage/sqlite_cache_store.py`)

Implements `LLMCacheStore` over `llm_cache.db`:
- **`get(cache_key: str) -> str | None`**:
  - Fetches `payload_json` where `cache_key = ?` (and optional TTL guard `created_at >= cutoff`).
  - On hit, updates `hit_count = hit_count + 1` and `last_accessed_at = utc_now` atomically (using batched/throttled or direct WAL update; in read-only mode, skips access timestamp mutation cleanly).
- **`put(entry: CacheEntry) -> None`**:
  - Executes atomic `INSERT INTO llm_cache (...) VALUES (...) ON CONFLICT(cache_key) DO UPDATE SET payload_json=excluded.payload_json, size_bytes=excluded.size_bytes, last_accessed_at=excluded.last_accessed_at`.
- **`stats() -> CacheStats`**:
  - Computes `COUNT(*)`, `SUM(size_bytes)`, `SUM(hit_count)`, and grouped counts by `output_schema` in milliseconds via SQL aggregates.
- **`prune(max_bytes: int | None = None, max_age_days: int | None = None) -> int`**:
  - Deletes expired entries (`created_at < cutoff`) and evicts least-recently-used rows (`ORDER BY last_accessed_at ASC`) until `SUM(size_bytes) <= max_bytes`, followed by `PRAGMA incremental_vacuum`.

### 3.2 `CachedStructuredLLM` (`episteme_pipeline/llm/cache.py`)

- Preserves the exact cache-key payload fields (`CACHE_VERSION`, `method`, `strategy`, `output_schema`, `schema_json_hash`, `prompt`, `prompt_bundle_hash`, `args`, `llm_kwargs`), `NL_TO_FORMAT` two-pass delegation, and `LLMGenerationCompleted(cached=True)` event emission.
- Idempotent factory wrapper `ensure_cached_llm(llm, cache_store: LLMCacheStore)` checks `isinstance(llm, CachedStructuredLLM)` per `design_patterns_and_standards.md §3.3`.
- Inject `StorageBundle.llm_cache` from `PipelineFactory` and `evaluation/pipelines.py`.

---

## 4. Testing & Verification Strategy

- Contract tests (`tests/unit/storage/test_llm_cache_store.py`):
  - Cache hit/miss behavior for both `predict_text` and `predict_structured` (including `NL_TO_FORMAT` two-pass keys and `LLMGenerationCompleted(cached=True)` emission).
  - Concurrent `asyncio.gather` writes of 100 identical/distinct keys verifying zero JSON corruption.
  - LRU eviction (`prune(max_bytes=...)`), TTL expiration (`prune(max_age_days=...)`), and `stats()` verification.
  - Read-only mode gracefully hits cache without attempting `UPDATE last_accessed_at`.
  - AST/grep verification confirming zero `getattr` calls in `episteme_pipeline/llm/cache.py`.

---

## 5. Acceptance Criteria

- [ ] `SqliteLLMCacheStore` (in `llm_cache.db`) and `InMemoryLLMCacheStore` implement `LLMCacheStore`.
- [ ] `CachedStructuredLLM` replaces `DiskCachedStructuredLLM` with zero `getattr` reflection and full `Fingerprintable` determinism.
- [ ] `PipelineFactory`, `llm/structured.py`, and `evaluation/pipelines.py` wire `CachedStructuredLLM` with `StorageBundle.llm_cache`.
- [ ] Cache stats, TTL/LRU pruning, and concurrent async stress tests pass cleanly via `rtk uv run pytest`.
