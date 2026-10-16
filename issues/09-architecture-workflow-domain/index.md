# Architectural Critique & Remediation Registry (`09-architecture-workflow-domain`)

This directory contains a comprehensive architectural critique of **Episteme** based on a systematic audit of [`docs/architecture/`](../../docs/architecture/overview.md), [`docs/adr/`](../../docs/adr/index.md) (`ADR-0001` through `ADR-0020`), and their foundational composition boundaries in [`packages/episteme-pipeline`](../../packages/episteme-pipeline/episteme_pipeline/pipeline.py).

> [!IMPORTANT]
> **Macro-Level Synthesis**:
> See [**`HIGH-LEVEL-ARCHITECTURAL-CRITIQUE.md`**](HIGH-LEVEL-ARCHITECTURAL-CRITIQUE.md) for the overarching conceptual analysis of the **7 macro-architectural paradigms** (Hermeneutic Feedback Loops, Intensional/Perspectival Attribution, Hypergraph Inference Reification, Compositional Uncertainty Propagation, Incremental Knowledge Base Lifecycle, Active Epistemic Quality Gates, and Declarative Dataflow Separation).

---

## 1. Foundational Architectural Pillars Assessment (What Is Sound & Preserved)

Before detailing the critique issues, our evaluation confirms that **Episteme's five core architectural pillars are fundamentally sound and best-in-class** for a research-engineering platform. None of the issues below require replacing these core paradigms; rather, they **enforce** and **extend** them:

1. **Hexagonal Architecture (Ports & Adapters + Composition Root DI)**: Decoupling domain logic via strict Python `Protocol`s (`GraphReader`/`GraphWriter`, `StructuredLLM`, `EmbeddingModel`, `RelationReranker`, `DecisionEngine`, `ModalStrengthResolver`) normalized at the composition root (`ensure_*`) is exemplary and enables 100% deterministic non-LLM testing (`InMemoryGraphStore`, `MockJevDecisionEngine`).
2. **Artifact-First & Manifest-Driven Execution**: Treating phase outputs as immutable, content-addressed `ArtifactEnvelope[T]` records governed by a `RunManifest`—with dual identifiers (`artifact_id` for lineage + `identity_key` for semantic identity across runs, `ADR-0014`) and recursive component fingerprinting (`Fingerprintable`)—is the right foundation for scientific reproducibility.
3. **Task-Local Domain Event Bus (`contextvars` + `EventObserver`)**: Binding `EventEmitter` to async task contexts (`use_event_emitter`) and emitting semantic domain events to pluggable observers (`LangfuseObserver`, `JsonlRunObserver`, `RichProgressObserver`) avoids constructor prop-drilling and isolates concurrent runs cleanly.
4. **Dual-Process Neuro-Symbolic Engine (System 1 + System 2) & Conformal Triage**: Combining sub-second local System 1 classification (`Laya`/`Jev`, `ADR-0018`/`0019`) with Split Conformal Prediction (`conformal_prediction.md`), decoupled NL-to-Format constrained decoding (`constrained_decoding.md`), and stratified `D-QBAF` ODE/DAG solvers (`ADR-0011 Addendum 2`, `ADR-0020`) is both theoretically and operationally rigorous.
5. **Staged Epistemic Progression ($\Phi_{\text{gen}}$ vs. $\Phi_{\text{spec}}$)**: Separating domain-agnostic extraction (`Phases 1–5`) from domain-specific structuralist theory lenses (`TheoreticalEnrichmentRunner`, `ADR-0015`) preserves library generality across scientific disciplines.

---

## 2. Part I: Subsystem & Boundary Enforcement Issues (`ISSUE-046` – `ISSUE-052`)

These issues address places where current runtime boundaries deviate from or incomplete the promises of the foundational architecture:

| Issue ID | Architectural Critique Title | Primary Lens | Priority | Core Defect & Refinement Summary |
| :--- | :--- | :--- | :--- | :--- |
| [**ISSUE-046**](ISSUE-046-split-brain-state-artifact-vs-neo4j-isolation.md) | **Split-Brain State Architecture: "Artifact-Native" Illusion vs. Shared Mutable Neo4j Stores** | Hexagonal Isolation & State | **Critical** | Phases still read/write `projection_graph`, `checkpoint_store`, and `graph_reader` directly without `run_id` isolation, while `ArtifactGraphProjector` re-projects in an unbatched $O(N)$ loop. **Fix**: `ArtifactSubgraphReader`, lineage-scoped checkpoints, and bulk `UNWIND` projection. |
| [**ISSUE-047**](ISSUE-047-inter-phase-artifacts-view-information-loss-and-identity-collision.md) | **Information Loss, Identity Collision & Severed Lineage in `ArtifactsView` Handoffs** | Domain & Data Contracts | **Critical** | `ArtifactCollection` appends updated entities without deduplicating by `identity_key`; `Phase3ArtifactsView` & `Phase4ArtifactsView` drop `CanonicalizationArtifact` (Phase 3b) and `FusionDecisionArtifact` (Phase 5), causing Phase 6 QBAF to double-count duplicate claims. **Fix**: Identity-resolved collection & canonical rewrite views. |
| [**ISSUE-048**](ISSUE-048-linear-ordinal-invalidation-vs-dag-execution-and-selective-recomputation.md) | **Linear Ordinal Execution & Coarse Cascade Invalidation vs. True Epistemic DAG** | Workflow & Caching | **High** | `_phase_lists_match()` invalidates all phases from Phase 1 whenever a post-processor is toggled; custom phases silently fallback to `phase_key = "phase1"`; `ArtifactDependencyGraph` is unused during execution. **Fix**: Sub-DAG prefix compatibility & delta-aware execution contexts. |
| [**ISSUE-049**](ISSUE-049-reproducibility-hazards-stochastic-auditing-prompt-fingerprints-and-conformal-drift.md) | **Reproducibility & Cache Coherence Hazards in System 1/2 Triage & Conformal Calibration** | Reproducibility & Statistics | **High** | Unseeded 2% stochastic auditing breaks determinism under async concurrency; `_prompt_fingerprints()` hardcodes only 4 phases; unstratified conformal $\mathcal{D}_{\text{cal}}$ violates exchangeability across tasks and GER/ENG domains. **Fix**: HMAC-SHA256 PRF auditing, recursive `Fingerprintable` prompts, and Mondrian calibration. |
| [**ISSUE-050**](ISSUE-050-ontological-schism-tf-vs-dqbaf-vs-structuralist-tenability-feedback.md) | **Theoretical & Ontological Fragmentation Across ADRs (`TF` vs. `D-QBAF` vs. Structuralism)** | Epistemic Metamodel | **High** | `ADR-0007` (TF) and `ADR-0011`/`0020` (D-QBAF) contradict each other; `TheoryRelation` retains `modal_strength` risking $M^2$ double-penalization; `ADR-0015` tenability ($TS_{\text{local}}$) runs *after* Phase 6 and never updates D-QBAF $\tau^*$. **Fix**: Unified L2–L4 metamodel (`ADR-0021`) and coupled tenability-QBAF convergence. |
| [**ISSUE-051**](ISSUE-051-episodic-memory-crash-amnesia-and-quadratic-retrieval-scaling.md) | **Episodic Working Memory Crash Amnesia, Sequential Bottlenecks & Anisotropic Cosine Thresholds** | Scalability & Resilience | **High** | Phase 2 purges RAM Working Memory (`ADR-0009`), so resuming mid-chapter (`ADR-0001`) starts with empty STM; sequential chunking blocks chapter parallelism; raw cosine cutoffs fail under anisotropy/hubness. **Fix**: Checkpointed STM snapshots, ToC-bounded chapter parallelism, `CheckpointedBatchExecutor`, and CSLS scaling. |
| [**ISSUE-052**](ISSUE-052-event-bus-lifecycle-gaps-unflushed-spans-and-audit-completeness.md) | **Event System Lifecycle Gaps: Missing Failure/Reuse Events, Unflushed Spans & Silent Drops** | Observability & Telemetry | **Medium** | Crashing phases never emit `ComponentCompleted(success=False)` or `PhaseFailed`; reused phases emit zero lineage events; synchronous `emit()` lacks a `finally: flush()` barrier. **Fix**: Symmetric lifecycle bracket events, guaranteed flush barrier, and observer drop counters in `RunReport`. |

---

## 3. Part II: Higher-Level Architectural & Epistemic Evolution Issues (`ISSUE-053` – `ISSUE-058`)

These issues translate the 7 macro-level architectural concepts from [**`HIGH-LEVEL-ARCHITECTURAL-CRITIQUE.md`**](HIGH-LEVEL-ARCHITECTURAL-CRITIQUE.md) into concrete architectural evolution specifications:

| Issue ID | Macro-Architectural Evolution Title | Macro Concept Addressed | Priority | Core Architectural Advancement |
| :--- | :--- | :--- | :--- | :--- |
| [**ISSUE-053**](ISSUE-053-closed-loop-hermeneutic-refinement-and-top-down-feedback.md) | **Closed-Loop Hermeneutic Refinement: Top-Down Epistemic Deficit Signals ($\text{L4/L3} \to \text{L1/L2}$)** | #1 Bidirectional Hermeneutic Loop | **High** | Replaces strict one-pass waterfall with bounded top-down feedback: Phase 6 / Enrichment emits `EpistemicDeficitArtifact`s (`ENTHYMEME_GAP`, `POLYSEMY_COLLISION`) that trigger targeted L1/L2 premise recovery and concept splitting. |
| [**ISSUE-054**](ISSUE-054-intensional-perspectival-scoping-and-conception-stratification.md) | **Intensional & Perspectival Scoping: Epistemic Attribution, Counterfactuals & Conceptions** | #2 Intensional & Perspectival Space | **High** | Scopes `TheoryAtom`s by `intensional_mode` (`asserted`, `attributed`, `suppositional` for *Reductio* / opponent exegesis) and stratifies `L2Entity` into *Referential Topic* vs. theory-specific *EntityConceptions* instead of single-centroid averaging. |
| [**ISSUE-055**](ISSUE-055-bipartite-inference-hypergraph-conjunctive-premises-and-undercutters.md) | **Bipartite Inference Hypergraph: Reifying Warrant Nodes for Conjunctive Premises & Undercutters** | #3 Hypergraph Inference Topology | **High** | Reifies multi-premise deductions as `TheoryInference` (Warrant) nodes evaluated via Product/Gödel t-norms, enabling linked vs. convergent premise distinction, Pollockian undercutting defeaters, and Toulmin backings. |
| [**ISSUE-056**](ISSUE-056-non-transitive-consolidation-and-compositional-conformal-risk.md) | **Non-Transitive Consolidation & Compositional End-to-End Conformal Risk Control** | #4 End-to-End Uncertainty & Risk | **Medium** | Replaces transitive Union-Find in Phase 3b/5 with diameter-bounded correlation clustering (preventing single-linkage bridge chaining) and introduces sequence-level $\alpha$-budget allocation across phases. |
| [**ISSUE-057**](ISSUE-057-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md) | **Incremental Knowledge Base Lifecycle ($\mathcal{G}_t + \Delta D \to \mathcal{G}_{t+1}$) & Persistent HITL Constraint Ledgers** | #5 Knowledge Lifecycle & HITL | **High** | Replaces monolithic corpus hashing with per-document content-addressed caching (`document_fingerprints`) for incremental paper additions ($\Delta D$), and introduces a persistent `EpistemicCurationLedger` for human must-link/cannot-link/polarity constraints. |
| [**ISSUE-058**](ISSUE-058-runtime-epistemic-quality-gates-and-declarative-orchestrator.md) | **Active Runtime Epistemic Quality Gates & Declarative Dataflow Orchestration** | #6 Quality Gates & #7 Orchestrator | **Medium** | Introduces inter-phase `EpistemicQualityGate` circuit breakers (ontology entropy, percolation diameter, conformal OOD rate) and splits `Pipeline` into `PipelineFactory` (DI), `WorkflowDAG` (topology), and `ArtifactExecutionEngine` (runtime). |

---

## 4. Recommended Staged Roadmap

```mermaid
flowchart LR
    subgraph Stage1 ["Stage 1: Boundary & State Integrity"]
        I47["ISSUE-047<br/>Identity-Resolved Views"] --> I46["ISSUE-046<br/>Hexagonal Artifact Isolation"]
    end

    subgraph Stage2 ["Stage 2: Determinism & Observability"]
        I49["ISSUE-049<br/>HMAC Audit & Mondrian Conformal"]
        I52["ISSUE-052<br/>Symmetric Event Lifecycle"]
    end

    subgraph Stage3 ["Stage 3: DAG Runtime & Incremental KB"]
        I48["ISSUE-048<br/>Sub-DAG Reuse"] --> I58["ISSUE-058<br/>Declarative DAG & Quality Gates"]
        I51["ISSUE-051<br/>Checkpointed STM & CSLS"] --> I57["ISSUE-057<br/>Incremental Corpus & HITL Ledger"]
    end

    subgraph Stage4 ["Stage 4: Next-Gen Epistemic Expressivity"]
        I50["ISSUE-050<br/>Unified L2-L4 Metamodel"] --> I54["ISSUE-054<br/>Intensional Scoping & Conceptions"]
        I50 --> I55["ISSUE-055<br/>Bipartite Inference Hypergraph"]
        I54 & I55 --> I53["ISSUE-053<br/>Closed-Loop Hermeneutic Refinement"]
        I56["ISSUE-056<br/>Non-Transitive Clustering & RCPS"]
    end

    Stage1 --> Stage2 --> Stage3 --> Stage4
```
