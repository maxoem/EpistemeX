# [ADR-0025 Proposal] Transactional Epistemic Commit Cascade, Formal Verification Oracle, and Graph World Models

- **Status:** Proposed
- **Date:** 2026-11-25
- **Extends:** [ADR-0009](../../docs/adr/0009-sota-dual-memory-episodic-working-memory.md) (Dual-Memory), [ADR-0015](../../docs/adr/0015-theoretical-enrichment-and-tenability-evaluation.md) (Theoretical Enrichment), [ADR-0017](../../docs/adr/0017-explicit-batch-contracts-and-bulk-io.md) (Artifact-Native Batching), [ADR-0018](../../docs/adr/0018-decision-engine-architecture-and-contracts.md) (Dual-Process Decision Engine), [ADR-0021](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md) (Incremental Hydration), [ADR-0022](../../docs/adr/0022-unified-stratified-epistemic-metamodel.md) (Stratified Epistemic Metamodel), [ADR-0023](../../docs/adr/0023-intensional-perspectival-scoping-and-conception-stratification.md) (Intensional Scoping), [ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md) (Closed-Loop Hermeneutic Refinement)
- **Companion Issues:** [ISSUE-111](ISSUE-111-core-epistemic-commit-interceptor-and-operator-algebra.md), [ISSUE-112](ISSUE-112-inductive-graph-world-model-and-jepa-capabilities.md), [ISSUE-113](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md), [ISSUE-114](ISSUE-114-neuro-symbolic-interaction-dynamics-and-distillation.md)

---

## Context

Episteme constructs tri-layer Theory Graphs (`L1` Provenance, `L2` Ontology, `L3` TheoryNet) and evaluates argumentative plausibility via a continuous Decoupled Quantitative Bipolar Argumentation Framework (`D-QBAF`, [ADR-0022](../../docs/adr/0022-unified-stratified-epistemic-metamodel.md)) paired with structuralist tenability optimization (`TS_local`, `TS_edge`, [ADR-0015](../../docs/adr/0015-theoretical-enrichment-and-tenability-evaluation.md)). While this captures *gradual dialectical weight* and *approximate numerical law satisfaction*, it lacks two complementary capabilities:

1. **Deterministic Formal Deduction & Consistency Verification (Mode 2):** Checking whether a newly extracted or curated proposition $\phi$ is deductively entailed by an existing local axiom cone ($\Gamma \vdash \phi$), deductively refuted ($\Gamma \vdash \neg\phi$), consistent yet independent, or missing explicit bridging lemmas (*enthymemes*)—using agentic autoformalization backed by a deterministic **Lean 4** kernel and SMT model-finding.
2. **Latent Structural Compatibility & Simulation (Mode 1):** An inductive **Graph World Model** (in the sense of LeCun's JEPA / Energy-Based Models, 2022) that estimates structural compatibility in milliseconds, predicts latent vector representations of missing enthymemes, and supports counterfactual belief-revision rollouts.

### Why Naive "Insert Event Triggers" Fail in Both Episteme and Research Practice

At first glance, integrating Lean 4 or a World Model looks like a simple reactive hook on Episteme's hexagonal `EventEmitter` whenever a Lean-capable processor inserts a statement during an "active" intra-document mode. Closer inspection of the codebase and belief-revision theory reveals four structural reasons why an `EventEmitter`-based per-insert trigger is an architectural anti-pattern:

1. **`EventEmitter` Is Strictly Passive Telemetry, Not Control Flow:** In [`episteme_pipeline/events/bus.py`](../../packages/episteme-pipeline/episteme_pipeline/events/bus.py), `EventObserver.on_event(event) -> None` returns nothing, cannot mutate pipeline state, and is discarded under `NoOpEventEmitter`. Furthermore, per [ADR-0017](../../docs/adr/0017-explicit-batch-contracts-and-bulk-io.md), phases do not issue row-by-row graph inserts; they emit immutable `ArtifactCollection` envelopes persisted via 500-item Cypher `UNWIND` batches in `ArtifactGraphProjector`. Hanging verification logic on `EventObserver` would bypass `find_components()` manifest fingerprinting ([Design Patterns](../../docs/architecture/design_patterns_and_standards.md#L48-L55)) and break deterministic cache invalidation.
2. **Order Sensitivity, *Modus Tollens*, and Joint Inconsistencies (*Trilemmas*):** In formal belief revision and philosophical text analysis, incremental single-sentence checking is non-commutative:
   - *Modus Tollens:* A philosopher may state an opponent's thesis $A$ and conditional $A \to B$ in paragraphs 1–2, then establish $\neg B$ in paragraph 4 to refute $A$. Triggering on the single insert of $\neg B$ against $\{A, A \to B\}$ falsely flags $\neg B$ as incompatible rather than triggering revision of $A$.
   - *Joint Inconsistency (Trilemmas):* Sets such as $\{P, Q, R\}$ are frequently pairwise consistent while $P \land Q \land R \vdash \bot$. Single-node insert checks silently admit $P$ and $Q$ and blame only $R$ because of textual order.
3. **Active Database Termination Hazards (`Insert -> Event -> Update -> Event`):** When a verification update inserts a recovered enthymeme or splits a polysemous concept, that update is itself a graph mutation. Unbounded event-driven triggers risk infinite feedback loops and async race conditions across `asyncio.gather` batches.
4. **Toolchain & Representation State Coupling:** Lean 4 statements do not typecheck in isolation; they require a compiled `.olean` environment of shared neighbor definitions (*Prove2Me*, Chen et al., 2026, §4.1). Likewise, transductive shallow graph embeddings (TransE/RotatE/QuatE lookup tables) fail out-of-vocabulary on newly inserted statements unless wrapped in an **inductive** encoder.

---

## Decision

We adopt a **Transactional Epistemic Commit Cascade** built around one shared algebraic cycle—**`Propose -> Select -> Compute -> Update`**—executed through explicit hexagonal ports and isolated in a dedicated workspace package (`packages/episteme-formal/`).

### 1. `EpistemicCommitInterceptor` (Unit-of-Work Middleware, Not `EventEmitter`)

Verification and World-Model evaluation are invoked through an explicit `EpistemicCommitInterceptor` port (implementing `Fingerprintable`), supporting two activation modes cleanly:
- **Active / Intra-Document Episode Mode:** Fires deterministically at **semantic episode boundaries**—specifically when `EpisodicWorkingMemoryManager` ([ADR-0009](../../docs/adr/0009-sota-dual-memory-episodic-working-memory.md)) flushes a coherent argument episode, or when `episteme-studio` submits an interactive curation `EpistemicChangeset` ([ADR-0021](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md)). Operating on **episode changesets** rather than single raw statements captures multi-premise *Modus Tollens* structures and joint trilemmas.
- **Batch Post-Forward Mode:** Fires over connected `EpistemicStateView` components inside `ClosedLoopRefinementCoordinator` ([ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md)), governed by `HermeneuticRefinementConfig`.

### 2. Unified Operator Protocol (`Propose -> Select -> Compute -> Update`) & `CalibratedCascade`

Both the Graph World Model and the Lean 4 Formal Oracle implement the exact same `EpistemicEvaluator` protocol and compose via Episteme's canonical **`CalibratedCascade`** pattern ([Design Patterns §3.4](../../docs/architecture/design_patterns_and_standards.md#L153-L198)):
- **`Select` (`SubgraphSelector`):** Extracts a `ScopedVerificationContext` combining: (i) structuralist poset ancestors up to root $T_0$, (ii) $k$-hop argumentative neighbors filtered strictly by `intensional_mode` and `perspective` ([ADR-0023](../../docs/adr/0023-intensional-perspectival-scoping-and-conception-stratification.md)), and (iii) polarity-opposed contrastive anchors sharing canonical `L2Entity` referents (eliminating confirmation bias).
- **`Compute` Mode 1 (`GraphWorldModelEvaluator`):** Inductive Graph-JEPA / EBM predicting latent compatibility energy $E_{\text{WM}} \in [0, 1]$ and missing-premise latent vectors $\tilde{\mathbf{s}}_z$ in $< 20\text{ms}$. Unambiguous low-energy changesets fast-exit (subject to deterministic SHA-256 `should_audit_deterministically` auditing).
- **`Compute` Mode 2 (`LeanFormalEvaluator`):** Escalated on high-centrality, high-volatility ($\mathcal{V}$), ambiguous, or audited items. Runs canonical signature injection from `FormalSignatureLedger`, a mandatory vacuity check ($\Gamma \not\vdash \bot$), **Blind Sub-Agent Read-Back + `Jev` equivalence gating**, and warm `Pantograph` Lean 4 proof / `proof-sketch` search paired with SMT (Z3/CVC5) satisfiability checking.
- **`Update` (Pure `StateReducer` with `max_cascade_depth <= 2`):** Emits immutable `RefinementDelta` overlays (`ArtifactCollection.latest_by_identity`) rather than in-place mutations. Logical incompatibilities route dialectically (`LOGICAL_CONTRADICTION`, `ENTHYMEME_GAP`, or `POLYSEMY_COLLISION` split) rather than silently discarding valid philosophical claims.

### 3. Orthogonal State Stratification (Extending [ADR-0022](../../docs/adr/0022-unified-stratified-epistemic-metamodel.md))

To prevent Mode-1 neural plausibility and Mode-2 formal deductibility from oscillating or overwriting one another's edge weights, `TheoryAtom` and `TheoryRelation` store **strictly orthogonal verification metadata**:
- `world_model_energy: float | None` (Mode-1 structural/topological compatibility energy)
- `formal_status: Literal["entailed", "refuted", "consistent", "sketch_verified", "unverified"]` (4-valued Mode-2 kernel/SMT outcome)
- `logical_energy: float | None` (Mode-2 normalized proof-sketch assumption cost $E_{\text{logic}} \in [0, 1]$)
- `formal_assumptions: tuple[str, ...]` (imported `proof-sketch` child lemmas or `#print axioms` trace)

### 4. Mode-2 $\to$ Mode-1 Replay Buffer (`VerificationTrajectoryStore`)

Every `(ScopedVerificationContext, EpistemicChangeset, VerificationVerdict, RefinementDelta)` tuple produced by Lean 4 is logged to an append-only `VerificationTrajectoryStore`. This enables offline and continual **Mode-2 $\to$ Mode-1 amortized inference distillation** (LeCun, 2022, §3.1.3), turning verified Lean proofs and refutations into gold-standard training supervision and hard negatives for the Graph-JEPA World Model.

### 5. Dedicated Workspace Package (`packages/episteme-formal/`)

Analogous to [`packages/epistemetrics/`](../../packages/epistemetrics/), heavy Lean 4 (`Pantograph`, `elan`, LogiKEy preambles), SMT, and Graph-JEPA neural dependencies live in **`packages/episteme-formal/`**, preserving a zero-regression, lightweight `episteme-pipeline` core.

---

## Alternatives Considered

1. **Attaching Lean 4 Verification to `EventEmitter` / `EventObserver`:**
   - *Rejected:* Violates `EventObserver`'s passive telemetry contract, bypasses `ArtifactExecutionEngine` manifest fingerprinting and `ArtifactCollection` bulk projection ([ADR-0017](../../docs/adr/0017-explicit-batch-contracts-and-bulk-io.md)), and risks non-terminating event loops.
2. **Synchronous Single-Statement Lean Checking Inside Phase 2/4 Chunk Loops:**
   - *Rejected:* Breaks on multi-sentence *Modus Tollens* and trilemmas, incurs extreme cold-compile latency, and cannot access cross-chapter axioms before episodic consolidation.
3. **Standalone External Repository Outside the Episteme Monorepo:**
   - *Rejected:* Formal verification and World Models depend directly on Episteme's `intensional_mode` isolation ([ADR-0023](../../docs/adr/0023-intensional-perspectival-scoping-and-conception-stratification.md)), `EntityConception` disambiguation, and `L1`/`L2`/`L3` contracts; duplicating that infrastructure externally would recreate Episteme poorly.
4. **Using Transductive Shallow Graph Embeddings (TransE/RotatE/QuatE) Directly as the World Model:**
   - *Rejected:* Transductive lookup embeddings cannot score newly inserted, previously unseen statements zero-shot in Active Mode. They must be replaced by an **inductive** Graph-JEPA encoder (optionally using hypercomplex quaternion projections inside its relational predictor head).
5. **Rejecting / Dropping Logically Incompatible Candidate Nodes (`Γ ⊢ ¬φ`):**
   - *Rejected:* In philosophical literature, contradiction is a primary epistemic signal—indicating either an authorial refutation (`ATTACKS`), an unspoken conceptual distinction (`POLYSEMY_COLLISION`), or a genuine theoretical antinomy (`LOGICAL_CONTRADICTION`).

---

## Consequences

### Positive
- **Unified Neuro-Symbolic Architecture:** Unifies Active Episode Mode, Post-Forward Hermeneutic Refinement ([ADR-0024](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md)), Graph World Models, and Lean 4 under one deterministic `Propose -> Select -> Compute -> Update` contract.
- **Self-Bootstrapping Training Loop:** Lean 4 provides immediate formal rigor in Stage 2 while organically curating the verified Replay Buffer needed to train a calibrated Graph-JEPA World Model in Stage 3.
- **Zero-Regression Opt-In:** When `EpistemicCommitInterceptor` is disabled or unconfigured, existing `episteme-pipeline` manifests, fingerprints, and runtimes remain completely unchanged.

### Negative / Trade-offs
- **External Toolchain Management:** `packages/episteme-formal/` requires managing pinned `elan` / Lean 4 / `Pantograph` toolchains and SMT binaries in environments where Mode-2 formal checking is enabled.
- **Faithfulness Verification Overhead:** Every Mode-2 Lean verification incurs at least one independent LLM Read-Back call plus `Jev` equivalence gating to prevent silent semantic drift.
- **Signature Ledger Maintenance:** Maintaining `FormalSignatureLedger` across incremental corpus updates ([ADR-0021](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md)) requires local connected-component re-evaluation when a hub concept splits.

---

## Related

- [Suite Index](index.md)
- [ISSUE-111: Core Epistemic Commit Interceptor & Operator Algebra](ISSUE-111-core-epistemic-commit-interceptor-and-operator-algebra.md)
- [ISSUE-112: Inductive Graph World Models (Graph-JEPA / EBM)](ISSUE-112-inductive-graph-world-model-and-jepa-capabilities.md)
- [ISSUE-113: Lean 4 Formal Verification Oracle & LogiKEy Adapter](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md)
- [ISSUE-114: Cross-System Interaction Dynamics & Mode-2-to-Mode-1 Distillation](ISSUE-114-neuro-symbolic-interaction-dynamics-and-distillation.md)
