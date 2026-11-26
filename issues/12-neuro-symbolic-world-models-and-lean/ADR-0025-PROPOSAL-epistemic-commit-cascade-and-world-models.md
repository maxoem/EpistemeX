# [ADR-0025 Proposal] Transactional Epistemic Verification Cascade, Opt-In Lean 4 Integration & World Models

- **Status:** Proposed (Requires [ADR-0026 Proposal](../13-core-architecture-and-docs-refactoring/ADR-0026-PROPOSAL-contract-first-workspace-modular-runtime-and-systems-first-framing.md) Foundation)
- **Date:** 2026-11-26
- **Extends:** [ADR-0015](../../docs/adr/0015-theoretical-enrichment-and-tenability-evaluation.md) (Theoretical Enrichment), [ADR-0017](../../docs/adr/0017-explicit-batch-contracts-and-bulk-io.md) (Artifact-Native Batching), [ADR-0018](../../docs/adr/0018-decision-engine-architecture-and-contracts.md) (Dual-Process Decision Engine), [ADR-0021](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md) (Incremental Hydration & Ledger Fingerprinting), [ADR-0022](../../docs/adr/0022-unified-stratified-epistemic-metamodel.md) (Stratified Epistemic Metamodel), [ADR-0023](../../docs/adr/0023-intensional-perspectival-scoping-and-conception-stratification.md) (Intensional Scoping), [ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md) (Closed-Loop Hermeneutic Refinement)
- **Companion Issues:** [EXECUTION-PLAN](EXECUTION-PLAN.md), [ISSUE-111](ISSUE-111-core-epistemic-commit-interceptor-and-operator-algebra.md), [ISSUE-112](ISSUE-112-inductive-graph-world-model-and-jepa-capabilities.md), [ISSUE-113](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md), [ISSUE-114](ISSUE-114-neuro-symbolic-interaction-dynamics-and-distillation.md), [ISSUE-115](ISSUE-115-epistemic-node-router-and-programmatic-empirical-world-models.md)

---

## Context

Episteme constructs tri-layer Theory Graphs (`L1` Provenance, `L2` Ontology, `L3` TheoryNet) and evaluates argumentative plausibility via continuous `D-QBAF` ([ADR-0022](../../docs/adr/0022-unified-stratified-epistemic-metamodel.md)) paired with structuralist tenability optimization (`TS_local`, `TS_edge`, [ADR-0015](../../docs/adr/0015-theoretical-enrichment-and-tenability-evaluation.md)). While this models *gradual dialectical weight* and *numerical law satisfaction*, three complementary needs arise for formal and mechanistic domains:

1. **Opt-In Deductive Verification & Calculation (Mode 2 — Lean 4 + SMT):** Checking whether formalizable or scholar-authored propositions $\phi$ are entailed by a scoped axiom cone ($\Gamma \vdash \phi$), refuted ($\Gamma \vdash \neg\phi$), consistent yet independent, or missing bridging lemmas (*enthymemes*)—plus executing typed structuralist calculations (`#eval` / kernel steps).
2. **Fast Inductive Triage & Exact Counterfactual Sensitivity (Mode 1 — Type-A World Model):** Calibrated millisecond pre-screening (`DecisionEngine` / 4-class inductive verifier with `ConformalCalibrator`) paired with exact deterministic `D-QBAF` perturbation rollouts in `epistemetrics` (with an optional Horizon-3 Graph-JEPA track once trajectories scale).
3. **Empirical & Mechanistic Scenario Testing (Type-B World Model):** Compiling synthetic hypotheses and Lean-derived predictions $\hat{b}$ into a schema-validated **Declarative Typed Transition / Causal Graph IR** evaluated deterministically without ever executing untrusted LLM-generated Python.

### Why Reactive Per-Insert Hooks and Monolithic Packaging Fail

1. **`EventEmitter` Is Strictly Passive Telemetry:** In [`episteme_pipeline/events/bus.py`](../../packages/episteme-pipeline/episteme_pipeline/events/bus.py), `EventObserver.on_event(event) -> None` returns nothing and is suppressed under `NoOpEventEmitter`. Phases emit immutable `ArtifactCollection`s persisted via 500-item bulk projection ([ADR-0017](../../docs/adr/0017-explicit-batch-contracts-and-bulk-io.md)).
2. **Layer-Ordering Mismatch in Phase 2 vs. L3 Reasoning:** `EpisodicWorkingMemoryManager` ([ADR-0009](../../docs/adr/0009-sota-dual-memory-episodic-working-memory.md)) operates during **Phase 2 (`L2` entities/triples)**, before **Phases 4–6 (`TheoryAtom`, `TheoryRelation`, `intensional_mode`, and `TheoryNet` poset roots $T_0$)** exist. Streaming formal L3 checks inside Phase 2 cannot select L3 poset or intensional cones—whereas **batch post-forward execution** over `EpistemicStateView` handles *Modus Tollens* (`{A, A -> B, ¬B}`) and joint *Trilemmas* (`{P, Q, R} |- ⊥`) with full dialectical context.
3. **Heavy Dependency Coupling & Toolchain Incompatibility:** Currently [`episteme-pipeline/pyproject.toml`](../../packages/episteme-pipeline/pyproject.toml#L13-L43) bundles pure Pydantic models alongside `neo4j`, `llama-index-*`, `mteb`, `ogb`, `sentence-transformers`, and `langfuse`, and [`domain.py`](../../packages/episteme-pipeline/episteme_pipeline/contracts/domain.py#L1037) imports `stable_fingerprint` upward from `runs/fingerprints.py`. Meanwhile, Lean 4 (`elan`, `Pantograph`, `Z3`, `leanprover/comparator`) and PyTorch/PyG training wheels have incompatible build/Docker/GPU toolchains.

---

## Decision

We adopt an **artifact-native, dependency-inverted Neuro-Symbolic Verification Architecture** built around pure domain services, generic post-forward orchestration, sidecar verdict artifacts, and three strictly separated downstream packages:

### 1. Clean Workspace Dependency Inversion (`packages/episteme-contracts/`) & Tooling Split

- **`packages/episteme-contracts/` (Zero Heavy Dependencies):** Owns only Pydantic v2 domain contracts (`L1/L2/L3`, `EpistemicDeficit`, `RefinementDelta`, `EpistemicCurationLedger`, `FormalSignatureLedger`, `VerificationVerdict`, `TransitionGraphIR`, `OperationalizedScenarioArtifact`), `SchemaConfig`, `Fingerprintable` + `stable_fingerprint`, and narrow read-only `Protocol` ports (`TheorySubgraphQuery`, `EpistemicEvaluator`, `EpistemicNodeRouter`, `EmpiricalOperationalizer`, `DomainWorldModelPort`, `VerificationTrajectorySink`). Keeps artifact persistence/codecs strictly inside `episteme-pipeline`.
- **`packages/episteme-formal/` (Symbolic Only):** Opt-in Lean 4 (`EpistemeLogic.Modal`, structuralist templates), warm `Pantograph` REPL, 5-Gate hardening + `leanprover/comparator`, SMT (`Z3`/`CVC5`/`lean-smt`), and deterministic `TransitionGraphIR -> Lean 4` transpiler. Excluded from mandatory root `pyproject.toml` dependencies.
- **`packages/episteme-worldmodel/` (World Models Only):** Tier-1 calibrated 4-class inductive triage, exact `epistemetrics` counterfactual helpers, deterministic `TransitionGraphIR` interpreter, and optional Horizon-3 PyTorch/PyG Graph-JEPA isolated behind a `[train]` extra. Excluded from mandatory root `pyproject.toml` dependencies.

### 2. Decomposed `ArtifactExecutionEngine`, `PostForwardStage` & `PipelineBuilder`

- Decompose the 2,291-line [`execution_engine.py`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py) into five cohesive collaborators: `ManifestTracker`, `RunHydrationService`, `PhaseExecutor`, `ProjectionCoordinator`, and `PostForwardRunner`.
- Introduce a uniform `PostForwardStage(Fingerprintable, Protocol)` (`stage_key`, `is_enabled(config)`, `run(collection, context) -> ArtifactCollection`) tracked via `RunManifest.post_forward_lineage_fingerprints: dict[str, str]`, composing non-redundantly:
  1. `ClosedLoopRefinementStage` (integrating a `VerificationDeficitDetector` when `max_refinement_cycles > 0`),
  2. `FormalVerificationStage` (standalone certification when `max_refinement_cycles == 0` or final post-refinement certification pass),
  3. `EmpiricalOperationalizationStage` (wrapping standalone `EmpiricalOperationalizationRunner` once claims and `A |- b_hat` entailments stabilize).
- Replace the 23-argument [`Pipeline.for_task`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py#L239-L264) signature with typed port bundles (`ModelPorts`, `ExtractionPorts`, `ArgumentMiningPorts`, `DecisionPorts`, `RefinementPorts`, `VerificationPorts`, `StoragePorts`) passed to `PipelineBuilder`, with `find_components()` updated to traverse `@dataclass` fields safely.

### 3. Pure `EpistemicVerificationService` (Batch + Async Studio Adapters Only)

Phases 1–6 remain strictly batch and artifact-native. All verification runs through a pure domain service **`EpistemicVerificationService`** accepting `(TheorySubgraphQuery, EpistemicChangeset) -> VerificationOutcome`:
- **`Route` (`EpistemicNodeRouter` + `DecisionEngine`):** Classifies each item across the **2×2 Hume's Fork matrix** (`Partition A/B` × `Analytisch/Synthetisch`) into `FORMAL_CASCADE`, `EMPIRICAL_WORLD`, `BRIDGE_SYNTHESIS`, or `DQBAF_ONLY`—ensuring qualitative prose is never forced into Lean 4.
- **`Select` (`SubgraphSelector` over `TheorySubgraphQuery`):** Extracts perspective- and `intensional_mode`-isolated cones (`Poset root T_0`, $k$-hop argumentative dependencies, polarity-opposed contrastive anchors, and immutable `FormalSignatureLedger`). Replacing L2-only `GraphReader` with `TheorySubgraphQuery` (implemented by `EpistemicStateView`) gives L3-native selection without pulling `ArtifactCollection` into `episteme-contracts`.
- **`Compute` (`CalibratedCascade`):** Mode-1 4-class calibrated triage + deterministic SHA-256 auditing (`should_audit_deterministically`) escalates ambiguous, high-centrality, or `human_verified` items to Mode-2 Lean 4 / SMT (with MCS cone pre-repair, anti-skeleton structural checks, cross-family Blind Read-Back, `native_decide` ban, and `leanprover/comparator` replay).
- **Two Runtime Adapters:**
  1. **Batch Pipeline Adapter:** Pluggable `VerificationDeficitDetector` inside `ClosedLoopRefinementStage` + standalone `FormalVerificationStage` (`max_cascade_depth <= 2`).
  2. **Async `episteme-studio` HITL Job Adapter:** Returns `<20ms` Tier-1 triage + exact `epistemetrics` `D-QBAF` perturbation sensitivity immediately, and dispatches multi-second Mode-2 Lean verification asynchronously via non-blocking `sse-starlette` jobs.

### 4. Slim `TheoryAtom`, Sidecar `ArtifactKind.VERIFICATION_VERDICT`, Versioned Ledgers & Write-Only Replay Sink

- **Zero Hash Churn on `TheoryAtom` / `TheoryRelation`:** Verification outcomes are emitted as standalone sidecar envelopes **`ArtifactKind.VERIFICATION_VERDICT`** (`VerificationVerdictArtifact`, `identity_key = f"verification::{target_id}"`) joined onto Neo4j nodes/edges during `ProjectionCoordinator` runs (or exposed on read views as optional `verification: EpistemicVerificationMetadata | None = None`). Enabling or disabling verification never invalidates upstream Phase 4–6 `TheoryAtomArtifact` IDs.
- **Versioned `FormalSignatureLedger`:** Modeled cleanly after `EpistemicCurationLedger` ([`phase_contracts.py`](../../packages/episteme-pipeline/episteme_pipeline/contracts/phase_contracts.py#L105)) as an explicit `PipelineInput.formal_signature_ledger` captured in `RunManifest.signature_ledger_fingerprint`. Blind-Critic-approved amendments mint a new ledger version on a child run (`parent_run_id`), guaranteeing an immutable held-out TCB inside any single run.
- **Write-Only `VerificationTrajectoryStore`:** Excluded from `Fingerprintable` and manifest hashing, recording `propensity_score` so off-policy Mode-1 recalibration via Inverse Propensity Weighting (IPW) never busts pipeline caches.

### 5. Declarative Transition Graph IR (`ISSUE-115`) & Interactive Studio Simulation

- Bridge-principle operationalization happens in a standalone **`EmpiricalOperationalizationRunner`** (`EmpiricalOperationalizationStage`), strictly separated from both `TheoreticalEnrichmentRunner` and `DomainWorldModelPort`.
- It emits a **Declarative Typed Transition / Causal Graph IR** (`TransitionGraphIR` reusing `SafeFormulaEvaluator` ASTs—never raw LLM-generated Python), executable by a deterministic interpreter in `episteme-worldmodel` or optionally transpiled into total Lean 4 state machines in `episteme-formal`.
- LLM-based social simulation (`studio_scm_dag`, Regime B3) remains strictly an interactive `episteme-studio` sensitivity probe with zero automatic write-back into `TS_local`.

---

## Alternatives Considered

1. **Active Intra-Document Episode Interception Inside Phase 2 (`EpistemicCommitInterceptor` on Working-Memory Flushes):**
   - *Deferred / Rejected for Core Architecture:* Creates a layer-ordering mismatch (Phase 2 lacks Phase 4–6 `TheoryAtom`, `intensional_mode`, and `TheoryNet` poset roots) and adds invasive runtime hooks across extractors. Replaced cleanly by pure batch `EpistemicVerificationService` over `EpistemicStateView` plus async `episteme-studio` HITL jobs.
2. **Keeping Domain Contracts & Protocols Inside `episteme-pipeline` or Merging Lean 4 + PyTorch in One Package:**
   - *Rejected:* Forces `episteme-formal`, `episteme-worldmodel`, and `episteme-studio` to inherit `neo4j`, `mteb`, `ogb`, and `llama-index-*` (risking circular imports and bloated CI/Docker images).
3. **Adding Flat Verification Columns onto `TheoryAtom` or Mutating `FormalSignatureLedger` In-Place:**
   - *Rejected:* Churns Phase 4/6 `TheoryAtomArtifact` IDs on verification reruns and violates *AlphaProof Code*'s immutable held-out TCB guarantee.
4. **Prompting LLMs for Plausibility Scores or Executing LLM-Generated Python (`exec()`):**
   - *Rejected:* Empirical social benchmarks demonstrate massive LLM calibration distortion (`~67×` MSE; `13.2×` $\hat{\beta}$ inflation in Manning et al., 2024), while raw `exec()` introduces security and reproducibility hazards.

---

## Consequences

### Positive
- **Strict Dependency Inversion & Minimal Environments:** `episteme-contracts` stays dependency-light, and heavy Lean 4 / PyTorch stacks remain strictly opt-in outside mandatory `uv sync`.
- **Composable Post-Forward Orchestration:** Hermeneutic refinement, formal certification, empirical operationalization, and future extensions compose uniformly as `PostForwardStage` plugins over `ArtifactCollection`.
- **Zero-Diff Opt-Out & Safe Replay:** `ArtifactKind.VERIFICATION_VERDICT` sidecars and a non-fingerprinted trajectory sink keep existing Episteme runs deterministic and cache-stable.

### Negative / Trade-offs
- **Upfront Prerequisite Refactoring (`Phase 1A/1B/1C`):** Extracting `episteme-contracts`, breaking up `execution_engine.py`, and introducing `PipelineBuilder` port bundles must land cleanly before merging `episteme-formal` and `episteme-worldmodel`.
- **Versioned Cross-Package Coordination:** Keeping `episteme-contracts` schemas strictly synchronized across four workspace packages requires discipline and schema regression tests in root CI.

---

## Related

- [Suite Index](index.md)
- [Execution Plan](EXECUTION-PLAN.md)
- [ISSUE-111: `episteme-contracts`, Orchestrator Decomposition & Verification Service](ISSUE-111-core-epistemic-commit-interceptor-and-operator-algebra.md)
- [ISSUE-112: Type-A World Models (Inductive Triage, Exact D-QBAF Counterfactuals & JEPA Track)](ISSUE-112-inductive-graph-world-model-and-jepa-capabilities.md)
- [ISSUE-113: Opt-In Lean 4 Verification & Calculation Adapter](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md)
- [ISSUE-114: Cross-System Interaction Dynamics & Mode-2-to-Mode-1 Calibration](ISSUE-114-neuro-symbolic-interaction-dynamics-and-distillation.md)
- [ISSUE-115: `EpistemicNodeRouter` (2×2 Hume's Fork) & Declarative Transition Graph World Models](ISSUE-115-epistemic-node-router-and-programmatic-empirical-world-models.md)
