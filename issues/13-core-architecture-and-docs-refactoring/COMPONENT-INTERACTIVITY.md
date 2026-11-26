# Component, Module & Port Interactivity Architecture

- **Governing Index:** [Suite Index](index.md)
- **Governing ADR:** [ADR-0026 Proposal](ADR-0026-PROPOSAL-contract-first-workspace-modular-runtime-and-systems-first-framing.md)
- **Execution Plan:** [Execution Plan](EXECUTION-PLAN.md)
- **Downstream Neuro-Symbolic Plugins:** [Suite 12 Index](../12-neuro-symbolic-world-models-and-lean/index.md)

---

## 1. Static Component, Module & Hexagonal Port Interactivity (`flowchart TD`)

All workspace runtime packages (`episteme-pipeline`, `episteme-studio`, and opt-in Suite 12 plugins `episteme-formal` and `episteme-worldmodel`) depend strictly **downward** on pure `packages/episteme-contracts/`. Neither `episteme-contracts` nor `episteme-pipeline` imports optional symbolic or ML/GPU plugin code.

```mermaid
flowchart TD
    subgraph Contracts ["packages/episteme-contracts (Pure Pydantic v2 + Protocols)"]
        C_FP["fingerprint.py (Fingerprintable, stable_fingerprint, dataclass find_components)"]
        C_Schema["schema.py (SchemaConfig, DEFAULT_SCHEMA)"]
        C_Domain["domain.py & curation.py (L1-L3 Models, RefinementDelta, Ledgers)"]
        C_Ports["protocols/* (PhaseRunner, PostForwardStage, DecisionEngine, TheorySubgraphQuery)"]
    end

    subgraph Pipeline ["packages/episteme-pipeline (Runtime & Extraction Engine)"]
        subgraph CompRoot ["Composition Root"]
            P_Bundles["Frozen Port Bundles (Model, Extraction, Decision, Refinement, Storage, VerificationPorts)"]
            P_Builder["PipelineBuilder -> PipelineFactory"]
            P_Facade["Pipeline Facade"]
            P_Bundles --> P_Builder --> P_Facade
        end

        subgraph ExecEngine ["ArtifactExecutionEngine (5-Service Runtime)"]
            E_Man["ManifestTracker (Fingerprints, Reuse, RunReport)"]
            E_Hyd["RunHydrationService (Parent-Chain Dedup & Hydration)"]
            E_Fwd["PhaseExecutor (WorkflowDAG Phases 1-6 + Quality Gates)"]
            E_Post["PostForwardRunner (Ordered PostForwardStage Loop)"]
            E_Proj["ProjectionCoordinator (latest_by_identity + Sidecar Joins)"]
            P_Facade --> E_Man
            P_Facade --> E_Hyd
            P_Facade --> E_Fwd
            P_Facade --> E_Post
            E_Fwd --> E_Proj
            E_Post --> E_Proj
        end

        subgraph Adapters ["Persistence & Telemetry Adapters"]
            A_Art["JsonArtifactStore & JsonRunManifestStore"]
            A_Neo["ArtifactGraphProjector -> Neo4jGraphStore"]
            A_Evt["EventEmitter -> LangfuseObserver (Telemetry Only)"]
            E_Hyd --> A_Art
            E_Man --> A_Art
            E_Proj --> A_Neo
            E_Fwd -.-> A_Evt
            E_Post -.-> A_Evt
        end
    end

    subgraph Metrics ["packages/epistemetrics (Standalone Formal & Graph Math)"]
        M_Solvers["QBAFGradualSemanticsSolver & WeightedQuadraticEnergySolver"]
        M_Top["Topology, Centrality & Scientific Virtue Analyzers"]
    end

    subgraph Studio ["packages/episteme-studio (Workbench UI & API)"]
        S_API["FastAPI Read API (Contract Views & Manifest Reports)"]
        S_Jobs["Async Job Runner (sse-starlette Streams & HITL Jobs)"]
        S_API --> C_Domain
        S_API --> E_Man
        S_Jobs --> P_Builder
        S_Jobs --> M_Solvers
    end

    subgraph Plugins ["Opt-In Suite 12 Plugins (Excluded from Root Deps)"]
        PL_Formal["episteme-formal (Pantograph Lean 4, SMT, comparator)"]
        PL_WM["episteme-worldmodel (Tier-1 Triage, TransitionGraphIR, JEPA[train])"]
    end

    Pipeline --> Contracts
    Pipeline --> Metrics
    Studio --> Contracts
    Studio --> Pipeline
    Studio --> Metrics
    PL_Formal -.->|"Implements EpistemicEvaluator"| C_Ports
    PL_WM -.->|"Implements DomainWorldModelPort / Router"| C_Ports
    PL_Formal -.->|"Injected into VerificationPorts"| P_Bundles
    PL_WM -.->|"Injected into VerificationPorts"| P_Bundles
```

---

## 2. End-to-End Runtime Execution & Dataflow Interactivity (`sequenceDiagram`)

Trace of a single execution across `PipelineBuilder`, the decomposed `ArtifactExecutionEngine` services, ordered `PostForwardStage` plugins, and bulk persistence/projection:

```mermaid
sequenceDiagram
    autonumber
    participant Caller as Caller or Studio Job Runner
    participant Builder as PipelineBuilder and Port Bundles
    participant Engine as ArtifactExecutionEngine
    participant Manifest as ManifestTracker
    participant Hydrate as RunHydrationService
    participant PhaseExec as PhaseExecutor
    participant PostRun as PostForwardRunner
    participant Proj as ProjectionCoordinator
    participant Store as JsonStore and Neo4j

    Caller->>Builder: bind Model, Extraction, Decision, Refinement, Storage, optional VerificationPorts
    Builder->>Engine: build() -> wired WorkflowDAG and PostForwardStages
    Caller->>Engine: run(PipelineInput, run_id, parent_run_id)
    Engine->>Manifest: build_manifest(input, curation_ledger, signature_ledger)
    Manifest->>Store: read prior manifests and compute lineage hashes
    Manifest-->>Engine: InvalidationDecision (reused vs invalidated phases)
    Engine->>Hydrate: hydrate_previous_collection(parent_run_id, reused_phases)
    Hydrate->>Store: load and deduplicate parent-chain artifacts
    Hydrate-->>Engine: cumulative ArtifactCollection

    loop For each invalidated WorkflowNode in WorkflowDAG (Phases 1 to 6)
        Engine->>PhaseExec: run_node(entry, cumulative_collection, context)
        PhaseExec->>PhaseExec: evaluate EpistemicQualityGate and emit Telemetry
        PhaseExec->>Store: persist phase artifacts to JsonArtifactStore
        PhaseExec->>Proj: project_collection(latest_by_identity batch=500)
        Proj->>Store: write bulk Cypher UNWIND batch to Neo4j
    end

    Engine->>PostRun: run_stages(forward_collection, manifest, context)
    loop For each enabled PostForwardStage (Refinement, Verification, Operationalization)
        PostRun->>Manifest: check post_forward_lineage_fingerprints[stage_key]
        alt Stage cache hit in parent_manifest
            PostRun->>Hydrate: load reused stage delta artifacts
        else Stage invalidated or first run
            PostRun->>PostRun: stage.run(collection, context) -> delta artifacts and sidecars
            PostRun->>Store: write delta artifacts (VERIFICATION_VERDICT / OPERATIONALIZED_SCENARIO)
        end
        PostRun->>Proj: project_latest_overlays_and_sidecars()
        Proj->>Store: join sidecars onto Neo4j TheoryAtom / TheoryRelation
    end

    Engine->>Manifest: finalize RunManifest and assemble RunReport
    Manifest-->>Caller: ExecutionResult(manifest, report)
```

---

## 3. Module Interaction Matrix & Architectural Invariants

| Caller Module | Target Port / Service | Interaction Mode | Enforced Architectural Guardrail |
| :--- | :--- | :--- | :--- |
| **`episteme-contracts`** | Python stdlib + `pydantic>=2.0` | Pure data models & ABC/Protocols | **Zero upward imports** (`test_package_boundaries.py` AST check); owns `stable_fingerprint` and dataclass-safe `find_components()`. |
| **`PipelineBuilder`** | Frozen Port Bundles (`ModelPorts`..`VerificationPorts`) | Constructor / builder DI | Replaces 23-kwarg `Pipeline.for_task` and reflective scraping in `PipelineFactory.build_standalone_refinement`. |
| **`PhaseExecutor`** | `PhaseRunner` & `EpistemicQualityGate` | Async batch over `EpistemicStateView` | Passes immutable views; emits telemetry only via `EventEmitter` (never control flow). |
| **`PostForwardRunner`** | Ordered `PostForwardStage` sequence | Async artifact-to-artifact transform | Uniform lineage hashing in `RunManifest.post_forward_lineage_fingerprints[stage_key]`; zero special-case `_run_refinement_stage()` code. |
| **`ProjectionCoordinator`** | `ArtifactGraphProjector` (`Neo4j`) | Batched `latest_by_identity` overlays | Sidecar `ArtifactKind.VERIFICATION_VERDICT` envelopes join at projection time without churning `TheoryAtomArtifact` IDs. |
| **`ManifestTracker`** | `Fingerprintable` components + ledgers | Synchronous deterministic SHA-256 | Traverses dataclass bundles; **explicitly ignores write-only sinks** (`VerificationTrajectorySink`) so replay writes never bust caches. |
| **`episteme-studio`** | `episteme-contracts` + `ManifestTracker` / `Async Job Runner` | Sync reads / `sse-starlette` async jobs | Read endpoints use pure contract models; multi-second refinement/Lean verification never blocks FastAPI event loops. |

---

## 4. Recommended Execution Sequencing: Suite 13 $\to$ Suite 12 (`flowchart LR`)

Always build **Suite 13 first**, because Suite 12 plugins import `episteme-contracts`, attach through `PostForwardStage`, and inject into `PipelineBuilder` port bundles. One zero-code fast-track exists: Suite 12's **Stage 0 validation spike** runs offline against existing `TheoryNet` JSON artifacts in parallel with `WP-1`.

```mermaid
flowchart LR
    S0["Suite 12 Stage 0: 2-Week Offline Validation Spike (Zero Core Code Changes)"] -.->|"Runs in Parallel"| WP1
    WP1["1. Suite 13 WP-1 (ISSUE-116): Extract episteme-contracts"] --> WP2["2. Suite 13 WP-2 (ISSUE-117): Engine 5-Service Split + PostForwardStage"]
    WP1 --> WP4["Suite 13 WP-4 (ISSUE-119): uv Hygiene + Python 3.13 + AST Tests"]
    WP1 --> WP5["Suite 13 WP-5 (ISSUE-120): README + Zensical Docs Refactor"]
    WP1 -.->|"Unblocked Immediately After WP-1"| P23["Suite 12 Phase 2 & 3B: episteme-formal / episteme-worldmodel Skeletons"]
    WP2 --> WP3["3. Suite 13 WP-3 (ISSUE-118): PipelineBuilder Port Bundles"]
    WP3 --> P1C["4. Suite 12 Phase 1C (ISSUE-111): EpistemicVerificationService + Sidecars"]
    P1C --> P4["5. Suite 12 Phase 3A & 4 (ISSUE-115 / ISSUE-114): Router, CalibratedCascade & Studio Async Jobs"]
    P23 --> P4
```
