# [ISSUE-109] SQLite Run Manifest & Indexed Artifact Store + Orchestrator DIP Refactor

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-109` |
| **Domain / Category** | `12-SQLite Persistence & Storage Ports` (Run Manifests, Artifact Lineage, Orchestrator DI) |
| **Target Package(s)** | `packages/episteme-pipeline` (`storage/`, `pipeline.py`, `runtime/`, `artifacts/`) |
| **Depends On** | `ISSUE-108` |
| **Complexity** | **HIGH** |
| **Recommended Model** | **Argon** |
| **Reasoning Effort** | **HIGH** |
| **Priority** | **Critical** |
| **Status** | `Open` |
| **ADR Reference** | [ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md), [ADR-0014](../../docs/adr/0014-deterministic-identity-diffing-and-progression-workbench.md), [ADR-0021](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md), [ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md) |

---

## 1. Problem & Architectural Context

At **100–500 pages**, a single run emits **20,000–80,000+ artifacts** (many carrying 1536–3072-float chunk/entity embeddings). Currently:
- [`JsonArtifactStore`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/store.py) writes one pretty-printed JSON file per artifact with non-atomic `write_text()`, requires directory scans on cold `get_artifact()`, and parses *all* JSON files in a run to serve `list_phase_artifacts()`.
- [`JsonRunManifestStore`](../../packages/episteme-pipeline/episteme_pipeline/runs/persistence.py) has no protocol port, and [`Pipeline`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py) / [`ArtifactExecutionEngine`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py) explicitly type-hint and instantiate concrete `JsonRunManifestStore` and `JsonArtifactStore`.
- Hermeneutic refinement ([ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md)) emits pass-$r$ envelopes sharing `identity_key` with pass-0 envelopes while appending to `history`; resolving `latest_by_identity` and walking multi-hop `parent_run_id` lineage currently requires deserializing whole directories into Python memory.

---

## 2. Architectural Upgrades Included (`[NO LEGACY]`)

- **True Orchestrator Dependency Inversion**: Refactor `Pipeline`, `ArtifactExecutionEngine`, `PipelineFactory`, and `runtime/runner.py` to depend strictly on `StorageBundle` / `RunManifestStore` / `ArtifactStore` protocols rather than concrete `Json*` classes.
- **Separate Dense Vector Storage (`embedding_blob`)**: On `ChunkArtifact` (and optional embedding-bearing payloads), serialize `embedding` as compact `float32` raw bytes in SQLite's nullable `embedding_blob` column (`array('f', emb).tobytes()` or NumPy `np.asarray(emb, dtype=np.float32).tobytes()`), leaving `payload_json` clean and fast to parse when `include_embeddings=False`.
- **Pre-Aggregated Run Statistics**: Maintain `artifact_count`, `size_bytes`, and `artifact_counts_by_kind_json` inside `runs` atomically during manifest/artifact writes so Studio sidebar discovery never touches the `artifacts` table.
- **Remove Flat-File Default Stores**: Once `SqliteRunManifestStore` and `SqliteArtifactStore` pass the full pipeline and contract test suites, remove `JsonRunManifestStore` (`runs/persistence.py`) and `JsonArtifactStore` (`artifacts/store.py`) rather than supporting dual write paths (export to JSON is handled cleanly by `ISSUE-115`).

---

## 3. Detailed Design & Implementation Specification

### 3.1 `SqliteRunManifestStore` (`episteme_pipeline/storage/sqlite_manifest_store.py`)

Implements `RunManifestStore`:
- `write_manifest(manifest)`: Serializes `manifest.model_dump(mode="json")`, extracts indexed columns (`run_id`, `parent_run_id`, `status`, `schema_version`, `created_at`, `started_at`, `completed_at`, `refinement_pass`, `input_sources_json`), and executes `INSERT INTO runs ... ON CONFLICT(run_id) DO UPDATE SET ...` while preserving/updating computed artifact rollups.
- `read_manifest(run_id)`: Indexed primary-key lookup returning validated `RunManifest | None`.
- `list_run_summaries(status, limit, offset)`: Reads only summary columns (`run_id`, `parent_run_id`, `status`, `schema_version`, `created_at`, `started_at`, `completed_at`, `refinement_pass`, `artifact_count`, `size_bytes`, `artifact_counts_by_kind_json`, `input_sources_json`, plus lightweight model names) — never parsing full `manifest_json` config/phase payloads when listing runs.
- `latest_manifest(only_completed=True)`: Indexed `ORDER BY created_at DESC LIMIT 1` (replaces scanning & validating every JSON manifest on disk).
- `resolve_lineage(run_id)`: Recursive SQLite CTE walking `parent_run_id` with cycle protection (`NOT instr(path, ',' || parent_run_id || ',')`) returning ordered ancestor chain `[run_id, parent, ...]`.

### 3.2 `SqliteArtifactStore` (`episteme_pipeline/storage/sqlite_artifact_store.py`)

Implements `ArtifactStore`:
- **Batched Transactional Writes (`write_artifacts`)**: Groups phase output envelopes into a single `BEGIN IMMEDIATE ... executemany ... COMMIT` transaction, extracting any `embedding` vector into `embedding_blob` (`float32` bytes), computing byte sizes, and updating the parent run's `artifact_count`, `size_bytes`, and `artifact_counts_by_kind_json` atomically in the same transaction.
- **SQL-Native `latest_only` & Lineage Resolution**:
  - `query_artifacts(ArtifactQuery)`: Uses window functions (`ROW_NUMBER() OVER (PARTITION BY COALESCE(identity_key, artifact_id) ORDER BY refinement_pass DESC, created_at DESC)`) when `latest_only=True`, optional `kind` / `phase_name` / `identity_key` predicates, keyset cursor pagination, and conditional projection omitting `embedding_blob` unless `include_embeddings=True`.
- **Pass-0 vs. Pass-$r$ History**: `list_run_artifacts()` returns full append-only envelope history ordered deterministically so `ArtifactCollection` preserves both `history` and `latest_by_identity` semantics ([ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md)) as well as incremental `ArtifactHydrator` lineage ([ADR-0021](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md)).
- **`hydrate_previous_collection` Optimization**: `ArtifactExecutionEngine` reads only the needed upstream `kind`s via `query_artifacts` instead of loading every envelope on disk into RAM.

### 3.3 Orchestrator Wiring (`pipeline.py`, `execution_engine.py`, `pipeline_factory.py`, `runner.py`)

- Add optional `storage: StorageBundle | None = None` to `Pipeline.__init__`, `ArtifactExecutionEngine.__init__`, and `PipelineFactory.resolve_components`. When omitted, build from `StorageFactory.from_execution_config(config.execution)`.
- Update `ArtifactExecutionEngine` phase persistence to flush each phase's newly emitted artifacts via a single `await self.artifact_store.write_artifacts(new_envelopes)` batch call rather than one transaction per artifact.
- Ensure `Pipeline` / `ArtifactExecutionEngine` close managed `StorageBundle` resources cleanly on shutdown (or leave caller-owned injected bundles open).

---

## 4. Testing & Verification Strategy

- **Parameterized Storage Contract Suite** (`tests/unit/storage/test_storage_contracts.py`): Run identical tests against `InMemoryStorageBundle` and `SqliteStorageBundle`:
  - Manifest write/update/latest/cycle-safe lineage CTE resolution.
  - Artifact batch writes, `latest_only=True` vs. `latest_only=False` across `refinement_pass` `0..3` ([ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md)), incremental hydration across `parent_run_id` chains ([ADR-0021](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md)), and lossless `embedding_blob` float32 round-trip.
  - Synthetic 500-page scale test: insert **25,000 artifacts** across 10 runs and verify `list_run_summaries()` and `query_artifacts(kind="theory_atom", limit=200)` execute in `< 20 ms` with zero `embedding_blob` reads.
- Update existing `tests/unit/runs/` and pipeline integration tests to use `InMemoryStorageBundle` or `SqliteStorageBundle` via `StorageFactory`, and verify `rtk uv run pytest` passes 100%.

---

## 5. Acceptance Criteria

- [ ] `SqliteRunManifestStore` and `SqliteArtifactStore` implement `RunManifestStore` and `ArtifactStore` completely.
- [ ] `Pipeline`, `ArtifactExecutionEngine`, `PipelineFactory`, and `runtime/runner.py` depend strictly on storage protocols (`StorageBundle`) with zero concrete `Json*` store references.
- [ ] Embeddings are stored separately in `embedding_blob` and skipped cleanly when `include_embeddings=False`.
- [ ] Batch phase artifact writes commit in a single transaction and update pre-aggregated `runs` counters atomically.
- [ ] Parameterized contract tests, ADR-0021/ADR-0024 lineage/refinement tests, and 25k-artifact benchmark pass deterministically.
