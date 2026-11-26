# [ADR-0026 Proposal] Contract-First Workspace Dependency Inversion, Decomposed Runtime & Systems-First Documentation Framing

- **Status:** Proposed
- **Date:** 2026-11-26
- **Extends:** [ADR-0008](../../docs/adr/0008-diataxis-documentation-framework.md) (Diátaxis Documentation), [ADR-0017](../../docs/adr/0017-explicit-batch-contracts-and-bulk-io.md) (Artifact-Native Execution), [ADR-0018](../../docs/adr/0018-decision-engine-architecture-and-contracts.md) (Decision Engine), [ADR-0021](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md) (Incremental Corpus & Curation Ledgers), [ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md) (Closed-Loop Refinement)
- **Prerequisite Foundation For:** [ADR-0025 Proposal](../12-neuro-symbolic-world-models-and-lean/ADR-0025-PROPOSAL-epistemic-commit-cascade-and-world-models.md)
- **Companion Issues:** [Suite Index](index.md), [Execution Plan](EXECUTION-PLAN.md), [ISSUE-116](ISSUE-116-extract-episteme-contracts-and-workspace-dependency-inversion.md), [ISSUE-117](ISSUE-117-execution-engine-decomposition-and-post-forward-stage-port.md), [ISSUE-118](ISSUE-118-pipeline-builder-typed-port-bundles-and-component-discovery.md), [ISSUE-119](ISSUE-119-monorepo-uv-packaging-hygiene-and-plugin-isolation.md), [ISSUE-120](ISSUE-120-documentation-and-readme-systems-first-restructuring.md)

---

## Context

Inspection of the monorepo (`packages/`, `docs/`, `README.md`, `zensical.toml`, and `pyproject.toml`) shows that Episteme's internal software engineering maturity has outpaced its package boundaries, runtime decomposition, and public framing:

1. **Monolithic Package & Inverted Dependencies:**
   - [`packages/episteme-pipeline/pyproject.toml`](../../packages/episteme-pipeline/pyproject.toml#L13-L43) pairs pure Pydantic contracts and narrow Python `Protocol` definitions with 25+ heavy ML, graph-DB, and LLM libraries (`neo4j`, `mteb`, `ogb`, `sentence-transformers`, `langfuse`, and 8 `llama-index-*` integrations).
   - [`episteme-studio/pyproject.toml`](../../packages/episteme-studio/pyproject.toml#L19-L21) must install all of `episteme-pipeline` just to inspect runs and domain models, while [`epistemetrics`](../../packages/epistemetrics/src/epistemetrics/__init__.py#L24-L33) maintains parallel `TheoryNode` / `TheoryEdge` structs to avoid inheriting `episteme-pipeline`.
   - Inside `episteme_pipeline/contracts/domain.py`, [`CandidatePair.key`](../../packages/episteme-pipeline/episteme_pipeline/contracts/domain.py#L1037) imports `stable_fingerprint` upward from `episteme_pipeline.runs.fingerprints`, and [`protocols/refinement.py`](../../packages/episteme-pipeline/episteme_pipeline/protocols/refinement.py#L16-L23) leaks `ArtifactCollection` and `ArtifactExecutionContext`.
   - Root [`pyproject.toml`](../../pyproject.toml#L5) requires `>=3.13`, whereas [`epistemetrics/pyproject.toml`](../../packages/epistemetrics/pyproject.toml#L13) and [`episteme-studio/pyproject.toml`](../../packages/episteme-studio/pyproject.toml#L10) still declare `>=3.11`.

2. **Monolithic Runtime & Composition Root:**
   - [`execution_engine.py`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py) has grown to 2,291 lines with a hardcoded 230-line `_run_refinement_stage()` method and bespoke `RunManifest.refinement_lineage_fingerprint` fields.
   - [`Pipeline.for_task`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py#L239-L264) accepts 23 keyword arguments, and [`PipelineFactory.build_standalone_refinement`](../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L353-L384) relies on traversing `phases` via `find_components()` to rediscover collaborators. Meanwhile, [`find_components()`](../../packages/episteme-pipeline/episteme_pipeline/protocols/fingerprint.py#L120-L125) calls `vars(root)` exclusively, silently returning `{}` for `@dataclass(slots=True)` objects.

3. **Documentation Drift & Epistemology-First Gatekeeping:**
   - [`zensical.toml`](../../zensical.toml#L24) sets `"Home" = "overview.md"`, creating two competing entry pages ([`docs/overview.md`](../../docs/overview.md) titled `T-Episteme` with a dead link to `../paper/index.md`, and [`docs/index.md`](../../docs/index.md) titled `Episteme` claiming "18 ADRs" and a "5-phase extraction pipeline").
   - [`README.md`](../../README.md#L92) still describes a "5-phase extraction engine" despite 8 forward pipeline stages (`1, 2, 3, 3b, 4, 4b, 5, 6`) plus theoretical enrichment and closed-loop refinement.
   - [`docs/architecture/overview.md`](../../docs/architecture/overview.md#L21) still lists `Python >= 3.12`.
   - Crucially, the top-level framing presents philosophy of science (*Structuralist Metatheory, Sneed/Balzer, Schurz, Lakatos, Holons, Hermeneutic Refinement*) before the underlying **NLP, hypergraph extraction, conformal dual-process gating, and content-addressed DAG runtime**—obscuring the system's engineering architecture for ML/NLP practitioners and external domain adopters.

---

## Decision

We adopt **four platform-wide architectural standards** (with zero backward-compatibility shims per `AGENTS.md` §2 `[NO LEGACY]`):

### 1. Contract-First Workspace Dependency Inversion (`packages/episteme-contracts/`)
- Extract pure Pydantic v2 contracts, `SchemaConfig`, `Fingerprintable`, **`stable_fingerprint`**, dataclass-safe `find_components()`, and narrow domain `Protocol` ports into a standalone **`packages/episteme-contracts/`** package with **zero heavy runtime dependencies** (`pydantic>=2.0` + stdlib).
- Define read-only query ports (e.g., `TheorySubgraphQuery`) in `episteme-contracts` so `ArtifactCollection`, checkpoint stores, Neo4j drivers, and LLM adapters remain strictly isolated in `episteme-pipeline` (and opt-in plugins in `episteme-formal` / `episteme-worldmodel`).
- Align all workspace packages on `requires-python = ">=3.13"`, keep heavy plugin packages out of root mandatory `[project].dependencies`, and enforce import boundaries with automated AST tests.

### 2. Five-Service `ArtifactExecutionEngine` Decomposition & Generic `PostForwardStage`
- Refactor `ArtifactExecutionEngine` into a thin facade over five single-responsibility services: **`ManifestTracker`**, **`RunHydrationService`**, **`PhaseExecutor`**, **`ProjectionCoordinator`**, and **`PostForwardRunner`**.
- Replace hardcoded post-forward branches with a uniform **`PostForwardStage(Fingerprintable, Protocol)`** (`stage_key`, `is_enabled(config)`, `run(collection, context)`) tracked via `RunManifest.post_forward_lineage_fingerprints: dict[str, str]`.

### 3. Typed Port Bundles & `PipelineBuilder` Composition Root
- Replace 23-parameter factory signatures with cohesive frozen dataclasses (`ModelPorts`, `ExtractionPorts`, `ArgumentMiningPorts`, `DecisionPorts`, `RefinementPorts`, `StoragePorts`, and optional extension bundles) composed via **`PipelineBuilder`**.
- Extend `find_components()` to inspect `dataclasses.fields()` alongside `__dict__` so frozen/slotted dataclasses never drop component fingerprints.

### 4. Two-Tier "Systems-First Core, Epistemology-Scoped Domain" Documentation & Naming Policy
We separate **how the software engineering platform is described** from **where formal epistemology supplies domain depth**:
- **Tier 1 (Technological / Language-Engineering Core):** Root [`README.md`](../../README.md), [`docs/architecture/`](../../docs/architecture/overview.md), `getting_started/`, `workflow/`, `how_to/`, `reference/`, and runtime orchestration code frame Episteme primarily as an **artifact-native neuro-symbolic language-to-argument-graph platform**:
  - Content-addressed DAG orchestration (`ManifestTracker`, `PostForwardStage`, `PipelineBuilder`),
  - Span-grounded document chunking & hierarchical outlining,
  - Context- and sense-disambiguated entity linking,
  - Calibrated System-1 / System-2 LLM cascades (`ConformalCalibrator` + constrained decoding),
  - Discourse/argument hypergraph mining (`ACC`/`ARC` + Continuous Bipolar Argumentation Equilibrium), and
  - Pluggable symbolic (`Lean 4`/SMT) and programmatic scenario verifiers.
- **Tier 2 (Epistemological & Mathematical Specialty Pillar):** [`docs/concepts/`](../../docs/concepts/index.md), `docs/research/`, `packages/epistemetrics/`, and the Layer-3 `TheoryNet` metamodel preserve full formal philosophy-of-science nomenclature and derivations (*Sneed/Balzer Theory-Nets, D-QBAF stability proofs, Schurz/Lakatos/Thagard metrics*), linked cleanly from Tier 1 via a **Systems $\leftrightarrow$ Epistemology Rosetta Stone**.
- **Document & Navigation Hygiene:** Consolidate `docs/index.md` + `docs/overview.md` into one canonical Zensical home page, remove broken `../paper/index.md` links, update counts to the true 8 forward stages + post-forward stages + 25+ ADRs, and restructure `zensical.toml` into 5 clean audience pillars with per-package API references.

---

## Alternatives Considered

1. **Rewrite Existing Core Classes In-Place to Rename Every Epistemic Symbol (`TheoryAtom -> ClaimNode`, `HermeneuticRefinement -> IterativeRecovery`):**
   - *Rejected:* Unnecessary churn across 25 accepted ADRs and mathematical proofs that genuinely implement Sneed/Balzer structuralism and Toulmin/Dung argumentation at Layer 3. Rename only misleading *runtime/infrastructure* abstractions where appropriate while re-centering entry-point documentation and public positioning.
2. **Keep `episteme-contracts` Inside `episteme_pipeline/contracts/` via Optional Extras (`episteme-pipeline[lite]`):**
   - *Rejected:* Python `import episteme_pipeline` executes package initialization and mixes namespace ownership, still permitting accidental upward imports (`CandidatePair.key -> runs.fingerprints`) unless physically separated at package level and guarded by AST boundary tests.
3. **Keep `Epistemology-First` Pitch in Root `README.md` and Add Only a Small Technical Note:**
   - *Rejected:* External engineers, NLP researchers, and potential Lean/World-Model contributors hit philosophical jargon before discovering Episteme's reusable language-engineering primitives (content-addressed artifact DAGs, conformal LLM cascades, polysemous sense splitting, span provenance).

---

## Consequences

### Positive
- Clean downward workspace dependency DAG unlocking `episteme-formal`, `episteme-worldmodel`, and slim `episteme-studio` clients without pulling multi-GB ML/DB dependencies.
- Cohesive <400-line runtime services and extensional `PostForwardStage` plugins replacing the 2,291-line monolith and 23-argument constructor.
- Accurate, approachable Zensical docs and `README.md` appealing directly to NLP/ML Systems Engineers *without diluting* Episteme's unique formal-epistemology research contribution.

### Negative / Trade-offs
- Touching import paths across `episteme-pipeline`, `episteme-studio`, and `epistemetrics` (clean break per `[NO LEGACY]`) requires coordinated test updates during `WP-1`.
- Restoring sync between `docs/` counts/links and evolving packages requires automated link/doc checks in CI alongside Zensical builds.
