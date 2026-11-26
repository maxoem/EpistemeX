# 12 — Neuro-Symbolic Epistemic World Models & Lean 4 Formal Verification

This directory specifies the architectural design, formal operator algebra, and research roadmap for integrating **Inductive Graph World Models (Graph-JEPA / EBM, Mode 1)** and an **Agentic Lean 4 Formal Verification Oracle (Mode 2)** into **Episteme** via a dedicated workspace package (`packages/episteme-formal/`).

---

## 1. Executive Overview & Strategic Positioning

Episteme's existing tri-layer architecture ([Formal Graph Model](../../docs/concepts/formal_graph_model.md)) pairs **Layer 1** verbatim provenance and **Layer 2** canonical ontology (`L2Entity` / `EntityConception`) with **Layer 3** defeasible dialectical evaluation (`D-QBAF`, [ADR-0022](../../docs/adr/0022-unified-stratified-epistemic-metamodel.md)) and structuralist model-theoretic tenability ($TS_{\text{local}}, TS_{\text{edge}}$, [ADR-0015](../../docs/adr/0015-theoretical-enrichment-and-tenability-evaluation.md)).

However, two complementary epistemic capabilities are currently missing:
1. **Strict Deductive & Consistency Verification (Mode 2):** Continuous gradual semantics (`D-QBAF`) and AST-level numeric formula evaluation (`SafeFormulaEvaluator`) cannot verify whether a philosophical conclusion deductively follows from a theory's axioms ($\Gamma \vdash \phi$), whether a subtle boundary condition is missing (requiring an implicit lemma / *enthymeme*), or whether an asserted proposition introduces a formal contradiction ($\Gamma \vdash \neg\phi$).
2. **Fast Structural Compatibility & Counterfactual Simulation (Mode 1):** Evaluating candidate insertions or structural perturbations across large `TheoryNet`s currently lacks an inductive, representation-space **Graph World Model** capable of sub-20ms compatibility scoring, latent missing-premise vector prediction, and interactive belief-revision rollouts.

### Unified Algebraic Principle

Rather than bolting ad-hoc `EventEmitter` callbacks onto individual graph inserts, both subsystems instantiate **one unified transactional operator algebra** over the epistemic state:

$$\text{Propose (Changeset)} \longrightarrow \text{Select (Scoped Cone)} \longrightarrow \text{Compute (Energy / Proof)} \longrightarrow \text{Update (Append-Only Delta)}$$

- **Mode 1 (`GraphWorldModelEvaluator`):** Fast, inductive latent-space compatibility scoring ($E_{\text{WM}} \in [0, 1]$) and latent missing-premise prediction ($\tilde{\mathbf{s}}_z$) in milliseconds.
- **Mode 2 (`LeanFormalEvaluator`):** Agentic autoformalization + deterministic Lean 4 kernel checking (via warm `Pantograph` REPL + LogiKEy modal embeddings) + SMT model-finding, gated by vacuity checks and blind sub-agent read-back audits.
- **Mode-2 $\to$ Mode-1 Distillation:** Every Mode-2 Lean verification trajectory is persisted in a `VerificationTrajectoryStore` (Replay Buffer), solving philosophical data scarcity by supplying deterministically verified positive proofs, minimal *proof-sketch* latents, and hard-negative refutations to train and calibrate the Mode-1 Graph World Model.

---

## 2. Specification Suite Registry

| Artifact / Issue | Category | Title & Scope | Target Package(s) | Horizon | Priority | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| [**ADR-0025 Proposal**](ADR-0025-PROPOSAL-epistemic-commit-cascade-and-world-models.md) | **Architecture Decision** | **Transactional Epistemic Commit Cascade, Formal Verification Oracle, and Graph World Models** | `episteme-pipeline`, `episteme-formal` | Horizon 2 & 3 | High | `Proposed` |
| [**ISSUE-111**](ISSUE-111-core-epistemic-commit-interceptor-and-operator-algebra.md) | **Core Pipeline** | **Epistemic Commit Interceptor & Unified Operator Algebra (`Propose -> Select -> Compute -> Update`)** | `episteme-pipeline` (`protocols/`, `contracts/`, `runtime/`, `refinement/`) | Horizon 2 | High | `Proposal` |
| [**ISSUE-112**](ISSUE-112-inductive-graph-world-model-and-jepa-capabilities.md) | **World Models** | **Inductive Graph World Models (Graph-JEPA / EBM): Architecture, Capabilities & Research Guide** | `episteme-formal`, `episteme-pipeline` | Horizon 2 & 3 | High | `Research` |
| [**ISSUE-113**](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md) | **Formal Oracle** | **Lean 4 Deductive Verification Oracle, LogiKEy Embeddings & Faithfulness Auditing** | `episteme-formal`, `episteme-pipeline` | Horizon 2 & 3 | High | `Research` |
| [**ISSUE-114**](ISSUE-114-neuro-symbolic-interaction-dynamics-and-distillation.md) | **Interaction & Distillation** | **Cross-System Interaction Dynamics, Logical Energy & Mode-2-to-Mode-1 Distillation** | `episteme-formal`, `episteme-pipeline`, `epistemetrics` | Horizon 3 | High | `Research` |
| [**ISSUE-115**](ISSUE-115-epistemic-node-router-and-programmatic-empirical-world-models.md) | **Node Router & Empirical WM** | **`EpistemicNodeRouter` & Programmatic Empirical World Models (Hume's Fork)** | `episteme-pipeline`, `epistemetrics`, `episteme-worldmodel` | Horizon 3 | High | `Research` |

---

## 3. Packaging Strategy: Why `packages/episteme-formal/` Inside This Monorepo

### Why NOT a Separate External Repository
A standalone Lean 4 + World Model repository would immediately fail in philosophical domains because formal verification and latent graph prediction are **blind without Episteme's epistemic state controller**:
- **Intensional & Perspectival Scoping ([ADR-0023](../../docs/adr/0023-intensional-perspectival-scoping-and-conception-stratification.md)):** Without isolating `asserted` claims from `suppositional` (*Reductio*) premises and `attributed` opponent reconstructions, classical logic immediately collapses via *Ex Falso Quodlibet* ($\bot \to P$).
- **Dual-Memory & Concept Stratification ([ADR-0009](../../docs/adr/0009-sota-dual-memory-episodic-working-memory.md)):** Without episodic working memory boundaries and `EntityConception` disambiguation, there is no coherent local axiom set $\Gamma$ or canonical vocabulary to pass to a prover.
- **Configurator Role:** In Yann LeCun's cognitive architecture (*A Path Towards Autonomous Machine Intelligence*, 2022), Episteme already functions as the **Configurator + Short/Long-Term Memory** that selects the active task context, perspectives, and subgoals for the World Model and Formal Critic.

### Why NOT Embedded Directly Inside `episteme-pipeline`
Hardwiring Lean 4 (`elan`, `lake`, `Mathlib`, `Pantograph` REPL processes, Z3/CVC5) or PyTorch Geometric Graph-JEPA training loops into `episteme-pipeline` would break lightweight installation, deterministic non-LLM unit tests, and CI turnaround. Following the exact workspace precedent of [`packages/epistemetrics/`](../../packages/epistemetrics/), we isolate all heavy formal and neural adapters inside **`packages/episteme-formal/`**, coupled strictly via narrow hexagonal `Protocol` ports in `episteme-pipeline/protocols/`.

---

## 4. Staged Execution Roadmap (Stage 0 to Stage 4)

| Stage | Deliverable | Scope & Verification Gate | Dependencies |
| :--- | :--- | :--- | :--- |
| **Stage 0** | **2-Week Offline Validation Spike** | Evaluate autoformalization faithfulness, canonical signature stability, and Read-Back precision/recall on 15–20 extracted DE/EN `TheoryNet` subgraphs (`< 15%` semantic drift target). | Existing `TheoryNet` artifacts |
| **Stage 1** | [**ISSUE-111**](ISSUE-111-core-epistemic-commit-interceptor-and-operator-algebra.md) | Implement `EpistemicCommitInterceptor`, `SubgraphSelector`, `EpistemicEvaluator` protocol, `FormalSignatureLedger`, `LOGICAL_CONTRADICTION` deficit kind, and `VerificationTrajectoryStore` in `episteme-pipeline`. | Stage 0 sign-off |
| **Stage 2** | [**ISSUE-113**](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md) | Create `packages/episteme-formal/` with warm `Pantograph` Lean 4 REPL adapter, `EpistemeLogic.Modal` (LogiKEy SSE) + Bourbaki/Sneed structuralist templates, Blind Read-Back + `Jev` gate, `proof-sketch` $\to$ `ENTHYMEME_GAP` mapping, and Z3/`lean-smt` consistency check. | Stage 1 contracts |
| **Stage 3** | [**ISSUE-112**](ISSUE-112-inductive-graph-world-model-and-jepa-capabilities.md) | Train inductive Graph-JEPA / EBM World Model (VICReg + verified margin hinge loss) over `VerificationTrajectoryStore` episodes; validate Mode-1 compatibility AUROC and latent enthymeme retrieval. | Stage 2 Replay Buffer ($\ge 10^3$ verified episodes) |
| **Stage 3b** | [**ISSUE-115**](ISSUE-115-epistemic-node-router-and-programmatic-empirical-world-models.md) | Wire `EpistemicNodeRouter` (Hume's Fork), explicit post-processor `EmpiricalOperationalizer`, and `DomainWorldModelPort` (Corpus, *WorldCoder* B2, Ex-Ante SCM B3) feeding `TS_local` and 2-stage `BRIDGE_SYNTHESIS`. | Stages 1 & 3 |
| **Stage 4** | [**ISSUE-114**](ISSUE-114-neuro-symbolic-interaction-dynamics-and-distillation.md) | Wire `CalibratedCascade` (Mode-1 fast-exit $\to$ Mode-2 Lean escalation $\to$ continuous off-policy distillation), orthogonal `world_model_energy` / `formal_status` projections, and `episteme-studio` counterfactual rollouts. | Stages 2, 3 & 3b |

---

## 5. Consolidated Risk & Mitigation Matrix

| # | Risk / Failure Mode | Root Cause | Architectural Mitigation in This Suite |
| :--- | :--- | :--- | :--- |
| **1** | **Unfaithful Autoformalization (*Semantic Drift*)** | LLMs emit compiling Lean statements that drop hypotheses, become vacuous, or alter philosophical meaning (~43% baseline faithfulness in Bourigault et al., 2026). | **4-Gate Verification Pipeline** ([ISSUE-113](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md)): Vacuity check ($\Gamma \not\vdash \bot$), `#print axioms` hygiene, **Blind Sub-Agent Read-Back** (*Prove2Me*), and `Jev` conformal equivalence gating. |
| **2** | **Paraconsistency & *Principle of Explosion*** | In classical Lean 4, a single unfiltered *Reductio* premise or opponent claim renders $\Gamma \vdash \bot$, making every candidate trivially provable. | Strict `intensional_mode` & `perspective` partitioning ([ADR-0023](../../docs/adr/0023-intensional-perspectival-scoping-and-conception-stratification.md)) inside `SubgraphSelector` + mandatory pre-check $\Gamma \not\vdash \bot$. |
| **3** | **Type & Signature Fragmentation** | Different chunks formalize the same `L2Entity` under incompatible types (`Event -> Prop` vs. `Fact -> Bool`), making theorems non-composable (*Prove2Me* §4.4). | Persistent **`FormalSignatureLedger`** anchored to canonical `L2Entity` / `EntityConception` IDs and injected as immutable Lean preambles. |
| **4** | **Order Sensitivity, *Modus Tollens* & Trilemmas** | Per-statement `EventEmitter` triggers misclassify multi-sentence *Modus Tollens* arguments and miss joint inconsistencies $\{P, Q, R\} \vdash \bot$. | **Episode/Changeset-level `EpistemicCommitInterceptor`** firing at semantic working-memory flushes ([ADR-0009](../../docs/adr/0009-sota-dual-memory-episodic-working-memory.md)), never per raw node insert. |
| **5** | **Transductive OOV & Cold-Start Latency** | Shallow KGEs (TransE/QuatE) cannot embed unseen inserted nodes; cold `lake env lean` calls trigger downstream recompilation cones. | **Inductive Graph-JEPA** encoder over text + local topology ([ISSUE-112](ISSUE-112-inductive-graph-world-model-and-jepa-capabilities.md)) + warm `Pantograph` REPL pool + `CalibratedCascade` gating. |
| **6** | **Specification Weakening & Swarm `False`-Injection** | Prover agents redefine upstream predicates as `False` or use `native_decide`, spreading spec hacks across parallel agents (*AlphaProof Code*, §7 p. 26). | Held-out read-only TCB checked via `leanprover/comparator`, positive reachability witnesses ($\exists m, \Gamma(m)$), semantic mutation tests, and Blind Critic 4-condition amendments ([ISSUE-113](ISSUE-113-lean4-formal-verification-oracle-and-logikey-adapter.md)). |
| **7** | **Direct LLM Simulation Bias, Bad Controls & Duhem–Quine Conflation** | Direct LLM scoring miscalibrates (`MSE = 8,628` vs. `128`; `13.2x` $\hat{\beta}$ inflation); unstructured discovery hits bad controls; in-API operationalization hides bridge defects (*Manning et al.*, 2024; *WorldCoder*, 2024). | Explicit post-processor `EmpiricalOperationalizer` -> `OperationalizedScenarioArtifact`, `WorldCoder` ($\phi_1 \land \phi_2$) programmatic simulation, and pre-registered ex-ante SCMs capped at `in_silico_scm <= 0.35` ([ISSUE-115](ISSUE-115-epistemic-node-router-and-programmatic-empirical-world-models.md)). |
