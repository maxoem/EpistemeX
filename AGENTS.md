# AGENT DIRECTIVE: Episteme

## 1. CORE OBJECTIVE

- **Domain:** SOTA theory graph construction for GER/ENG scientific literature (e.g., philosophy).
- **Scope:** Extensible, library-like pipeline. Inspired by argument mining but utilizes a flexible, multi-type
  node/relationship schema.

## 2. ARCHITECTURE & WORKFLOW

- **Tooling:** `uv` (Use `uv sync` for dependencies).
- **Constraint [NO LEGACY]:** Zero backward compatibility required. Prioritize agile, research-driven iteration.
- **Required System Hooks:** All components MUST integrate caching, logging, event publishing, and observability.
- ***Code Quality**: Follow development best practices like SOLID, Hexagonal Architecture, ensure the use of dependency inversion and avoid `getattrb`.

## 3. DOCUMENTATION & STANDARDS

- **Code:** NumPy Style docstrings are MANDATORY for all modules, classes, functions, and methods.
- **System Docs:** Zensical (improved MkDocs). Refer to `docs/index.md` and `docs/documentation.md`.
- **Citations:** Architectural or logic decisions grounded in papers/studies must include explicit references.
- **ADRs:** Significant software changes require an Architecture Decision Record (`ADRs index.md`).

## 4. TESTING (`rtk uv run pytest`)

- **Deterministic (Non-LLM):** Standard unit/integration testing required.

## 5. AGENT PROTOCOL

- Retrieve missing context, external documents, datasets, or user decisions ONLY when strictly necessary to avoid blockers.
- Iff stated, to resolve task without context, adhere!

## 6. REPO MAP

| Path                          | Package             | Role / Layout                                                                                                         |
|-------------------------------|---------------------|-----------------------------------------------------------------------------------------------------------------------|
| `packages/episteme-pipeline/` | `episteme-pipeline` | **Core engine.** Not src-layout: code in `episteme_pipeline/`, examples in `examples/`, tests in `tests/`            |
| `packages/epistemetrics/`     | `epistemetrics`     | **Standalone theory-graph evaluation library** (Schurz/Lakatos/Thagard/Dung). src-layout: `src/epistemetrics/`        |
| `packages/episteme-studio/`   | `episteme-studio`   | **Run-oriented workbench.** FastAPI backend `src/episteme_studio/` + React/TS frontend `frontend/src/`               |
| `docs/`                       |                     | Documents all theoretical and architectural concepts in high detail. Including decisions and pipeline implmentations. |

## 1. CORE PIPELINE (`packages/episteme-pipeline/episteme_pipeline/`)

Layered (see `docs/architecture/overview.md`): Orchestration → Core subsystems → Backends/Observers.

| Module                                    | Contents                                                                                                                                                  |
|-------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `pipeline.py`                             | Orchestrator `Pipeline` (central). Registers runners in hard-coded order.                                                                                 |
| `config.py`                               | `PipelineConfig` + per-phase configs (Pydantic).                                                                                                          |
| `contracts/`                              | Pydantic domain contracts: `L1Chunk/L1Document`, `L2Entity/L2Triple`, `TheoryAtom/TheoryRelation/TheoryNet`; `phase_contracts.py` = phase I/O boundaries. |
| `schema/`                                 | `DEFAULT_SCHEMA`, `SchemaConfig` (entity/relationship taxonomy).                                                                                          |
| `phases/`                                 | Runners, one dir per phase (see §3.1).                                                                                                                    |
| `protocols/`                              | ABCs/interfaces: `PhaseRunner`, `GraphReader/Writer`, `ProcessingGraph/ProjectionGraph/FusionGraph`, extractors, `PhaseCheckpointStore`, tracing.         |
| `graph/`                                  | `neo4j_store.py` (async Cypher store, dual graph strategy), `validation.py`.                                                                              |
| `events/`                                 | Domain event bus + observers (`langfuse_observer`, `progress_observer`).                                                                                  |
| `llm/`                                    | `cache.py`, `metadata.py`, `structured.py` (structured LLM output).                                                                                       |
| `prompts/`                                | `providers.py`, `default_prompts.py`, `input_formatters.py`, `models.py`.                                                                                 |
| `artifacts/`                              | `builders`, `store`, `invalidate`, `execution`, `models` (run artifact system w/ dependency invalidation).                                                |
| `runs/`                                   | run models, `fingerprints.py`, persistence, `observability`, `reporting`.                                                                                 |
| `runtime/`                                | `runner.py` (orchestrates phase execution).                                                                                                               |
| `projection/`                             | `artifact_projector.py`, `theorynet_projector.py` (→ projection graph).                                                                                   |
| `evaluation/`                             | intrinsic/extrinsic metrics, rubrics, datasets, comparison.                                                                                               |
| `post_processing/theoretical_enrichment/` | TheoryNet enrichment.                                                                                                                                     |
| `observability/`, `utils/`                | logging; helpers.                                                                                                                                         |
