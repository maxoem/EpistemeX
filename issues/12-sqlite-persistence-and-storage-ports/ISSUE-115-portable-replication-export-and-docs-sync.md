# [ISSUE-115] Portable Research Replication Export/Import (`JSON` / Per-Run `.db`) & Documentation Sync

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-115` |
| **Domain / Category** | `12-SQLite Persistence & Storage Ports` (Reproducibility, Export/Import CLI, Documentation Sync) |
| **Target Package(s)** | `packages/episteme-pipeline` (`storage/`), `packages/episteme-studio` (`api/`, `docs/`), `docs/` |
| **Depends On** | `ISSUE-109`, `ISSUE-112`, `ISSUE-113` |
| **Complexity** | **LOW** |
| **Recommended Model** | **Hydrogen** |
| **Reasoning Effort** | **LOW** |
| **Priority** | **Medium** |
| **Status** | `Open` |
| **ADR Reference** | [ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md), [ADR-0013](../../docs/adr/0013-per-run-neo4j-credentials-and-graph-fallback.md), [Reproducibility Practices](../../docs/research/reproducibility.md) |

---

## 1. Problem & Architectural Context

One legitimate trade-off of moving default storage from per-run JSON directories to a shared `episteme.db` workspace database ([ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md)) is **peer-review & replication sharing**:
- Researchers publishing papers need to export a **single run (plus its resolved `parent_run_id` lineage)** cleanly to Zenodo, Git repositories, or collaborators—**without** shipping unrelated runs, gigabytes of `llm_cache.db`, or secrets/credentials ([ADR-0013](../../docs/adr/0013-per-run-neo4j-credentials-and-graph-fallback.md)).
- Additionally, once `ISSUE-108` through `ISSUE-114` land, existing architecture/reference/deployment docs must accurately reflect the new `StorageBundle` ports, dual SQLite DBs (`episteme.db` + `llm_cache.db`), and Studio endpoints.

---

## 2. Architectural Upgrades Included (`[NO LEGACY]`)

- **Clean Lineage-Aware Export/Import Engine (`episteme_pipeline/storage/export.py`)**: Reuse `RunManifestStore.resolve_lineage()`, `ArtifactStore`, and `EventStore` ports—never reading raw SQLite internals from CLI or Studio endpoints—so export/import automatically works across any storage adapter.
- **Zero Secret Leakage & Cache Isolation**: Automatically apply secret redaction on exported `config_snapshot` fields and never bundle `llm_cache.db` into research replication packages.
- **DuckDB Zero-ETL Companion Docs**: Document the zero-ingestion analytical workflow (`INSTALL sqlite; ATTACH 'episteme.db' AS ep (TYPE sqlite);`) for cross-run ablation analysis over `runs`, `artifacts`, and `events`.

---

## 3. Detailed Design & Implementation Specification

### 3.1 Export / Import Engine (`episteme_pipeline/storage/export.py`)

- **`export_run_bundle(storage: StorageBundle, run_id: str, output_path: Path, *, fmt: Literal["json", "sqlite"], include_lineage: bool = True, include_events: bool = True, include_embeddings: bool = False)`**:
  - Resolves `lineage = await storage.manifests.resolve_lineage(run_id)` (or `[run_id]` when `include_lineage=False`).
  - Redacts any credential-like keys in manifest snapshots before export.
  - **`fmt="json"`**: Writes a clean, deterministic, git-diffable bundle directory (or `.tar.gz`): `manifest.json` (plus `ancestors/*.json`), `artifacts/<kind>/<artifact_id>.json`, `events.jsonl`, and `checksums.sha256`.
  - **`fmt="sqlite"`**: Creates a standalone, self-contained single-run `.db` file (using `SqliteConnectionManager`) containing only the exported run's lineage manifests, artifacts, and events, finalized with `VACUUM` + `journal_mode=DELETE` so it distributes as a single portable file with no `-wal`/`-shm` sidecars.
- **`import_run_bundle(storage: StorageBundle, bundle_path: Path) -> list[str]`**:
  - Auto-detects JSON directory/archive vs. SQLite `.db` bundle, validates Pydantic `RunManifest`, `ArtifactEnvelope`, and `StoredEventRecord` schemas, and idempotently imports them into the target workspace `StorageBundle`.
- Wire thin CLI commands (e.g., `episteme-storage export-run` / `import-run`) and optional Studio export endpoint (`GET /api/runs/{run_id}/export?format=json|sqlite`).

### 3.2 Documentation Synchronization (`docs/` & `packages/episteme-studio/docs/`)

Update all affected docs to remove stale `JsonRunManifestStore` / `JsonArtifactStore` / `FileSystemCheckpointStore` / `DiskCachedStructuredLLM` references and document SQLite default storage:
- [`docs/architecture/overview.md`](../../docs/architecture/overview.md)
- [`docs/architecture/artifact_run_model.md`](../../docs/architecture/artifact_run_model.md)
- [`docs/architecture/event-system.md`](../../docs/architecture/event-system.md)
- [`docs/architecture/cross_cutting_concerns.md`](../../docs/architecture/cross_cutting_concerns.md)
- [`docs/architecture/invalidation_and_resume.md`](../../docs/architecture/invalidation_and_resume.md)
- [`docs/deployment/docker.md`](../../docs/deployment/docker.md) (document `episteme.db` volume mount, `EPISTEME_STUDIO_DB_PATH`, and `--read-only` URI behavior)
- [`docs/research/reproducibility.md`](../../docs/research/reproducibility.md) (document `export-run` / `import-run` and DuckDB `sqlite_scanner` analytics)
- [`docs/reference/protocols.md`](../../docs/reference/protocols.md) & [`docs/reference/config.md`](../../docs/reference/config.md)
- [`packages/episteme-studio/docs/SPEC.md`](../../packages/episteme-studio/docs/SPEC.md)

---

## 4. Testing & Verification Strategy

- Round-trip export/import tests (`tests/unit/storage/test_export_import.py`):
  - Populate workspace DB with multi-hop `parent_run_id` run + another unrelated run + LLM cache entries.
  - Export target run as `fmt="sqlite"` and `fmt="json"`; verify unrelated run and cache entries are **not** included, secrets are redacted, and `journal_mode=DELETE` on exported `.db` leaves no sidecar files.
  - Import exported bundle into a fresh `episteme.db` and assert exact manifest, artifact, and event equality (`idempotency` on second import).
- Verify Zensical / MkDocs documentation builds cleanly without broken links.

---

## 5. Acceptance Criteria

- [ ] `export_run_bundle` (`json` and single-file `sqlite`) and `import_run_bundle` work idempotently across `StorageBundle` ports with secret redaction and cache exclusion.
- [ ] CLI commands and tests pass deterministically via `rtk uv run pytest`.
- [ ] All affected architecture, reference, deployment, reproducibility, and Studio docs are updated and link-verified.
