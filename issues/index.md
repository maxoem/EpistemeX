# Episteme Issues Index: TypeSafe Jev & Decision Engine Integration

This document proposes the prioritized implementation roadmap and order of execution for integrating **TypeSafe Jev** and the **System 1 Decision Engine** across Episteme.

The detailed issue specifications are registered in [**`10-decision-engine-and-jev/`**](10-decision-engine-and-jev/index.md) and integrated into the [**Master Active Issues Index**](README.md).

---

## 1. Issue Registry & Category Breakdown

| Issue ID | Category | Title | Target Component(s) | Priority |
| :--- | :--- | :--- | :--- | :--- |
| [**ISSUE-035**](10-decision-engine-and-jev/ISSUE-035-core-decision-engine-architecture-and-contracts.md) | **Architecture** | **Core Decision Engine Architecture, Contracts & Composition Root** | `pipeline/protocols/decision.py`, `pipeline/pipeline.py`, `pipeline/config.py` | High |
| [**ISSUE-036**](10-decision-engine-and-jev/ISSUE-036-typesafe-jev-client-and-decision-adapter.md) | **Model / Client** | **TypeSafe Jev Client Implementation & System 1 Adapter** | `pipeline/decision/jev_client.py`, `pipeline/decision/mock.py` | High |
| [**ISSUE-037**](10-decision-engine-and-jev/ISSUE-037-decision-observability-events-and-langfuse-tracing.md) | **Observability** | **Decision Engine Observability, Domain Events & Langfuse Tracing** | `pipeline/events/`, `pipeline/decision/observable.py` | Critical |
| [**ISSUE-038**](10-decision-engine-and-jev/ISSUE-038-phase3-candidate-gating-and-relation-reranking.md) | **Phase 3 Component** | **Phase 3 Candidate Pair Gating & Jev Relation Reranker** | `pipeline/phases/phase3_global_relations/`, `pipeline/config.py` | High |
| [**ISSUE-039**](10-decision-engine-and-jev/ISSUE-039-phase4-argument-mining-acc-arc-triage.md) | **Phase 4b Component** | **Phase 4b Argument Mining: Jev ACC & ARC Triage Classifiers** | `pipeline/phases/phase4_argument_mining/`, `pipeline/config.py` | High |
| [**ISSUE-040**](10-decision-engine-and-jev/ISSUE-040-gleaning-and-extraction-stopping-gate.md) | **Extraction Gating** | **Objective Gleaning Gating via Jev Actor-Critic Stopping Oracle** | `pipeline/decision/gleaning.py`, `pipeline/phases/phase2/`, `pipeline/phases/phase4/` | Medium |
| [**ISSUE-041**](10-decision-engine-and-jev/ISSUE-041-theorynet-calibrated-weights-and-qbaf-propagation.md) | **TheoryNet / Epistemetrics** | **TheoryNet Projection & QBAF Calibrated Probability Propagation** | `pipeline/phases/phase6_theorynet/`, `epistemetrics/` | High |
| [**ISSUE-042**](10-decision-engine-and-jev/ISSUE-042-episodic-working-memory-jev-state-machine.md) | **Dual-Memory (Phase 2)** | **Episodic Working Memory: Jev Semantic Boundary Eviction & Reference Resolution** | `pipeline/phases/phase2_entity_discovery/working_memory.py`, `pipeline/protocols/memory.py` | High |
| [**ISSUE-043**](10-decision-engine-and-jev/ISSUE-043-dense-entity-linking-and-ooo-gating.md) | **Entity Linking (Phase 2)** | **Dense Entity Linking: Jev Candidate Disambiguation & Out-of-Ontology Gating** | `pipeline/phases/phase2_entity_discovery/sota_entity_linker.py`, `pipeline/config.py` | High |
| [**ISSUE-044**](10-decision-engine-and-jev/ISSUE-044-phase1-epistemic-relevance-and-noise-gating.md) | **Ingestion (Phase 1)** | **Phase 1 Data Foundation: Epistemic Ingestion Relevance & Noise Gating** | `pipeline/phases/phase1_foundation/chunker.py`, `pipeline/config.py` | Medium |
| [**ISSUE-045**](10-decision-engine-and-jev/ISSUE-045-phase3b-consolidation-merge-verification.md) | **Consolidation (Phase 3b)** | **Phase 3b Latent Graph Consolidation: Borderline Cluster Merge & Canonical Election** | `pipeline/phases/phase3b_consolidation/`, `pipeline/config.py` | Medium |

---

## 2. Proposed Execution Order

To adhere to Episteme's core directives (zero backward incompatibility, non-LLM deterministic testability, strict observability, and decoupled DI), the issues should be implemented in the following 5-stage order:

### Stage 1: Foundational Architecture & Agnostic Contracts
* **Target Issue**: [**`ISSUE-035`**](10-decision-engine-and-jev/ISSUE-035-core-decision-engine-architecture-and-contracts.md)
* **Goal**: Establish `@runtime_checkable class DecisionEngine(Protocol)`, Pydantic return schemas (`DecisionScore`), `DecisionEngineConfig`, and wire the optional slot into `Pipeline.for_task`.
* **Rationale**: Decouples the rest of the codebase from concrete client libraries. Existing tasks continue running unchanged.

### Stage 2: Client Provider & Telemetry Tracing
* **Target Issues**: [**`ISSUE-036`**](10-decision-engine-and-jev/ISSUE-036-typesafe-jev-client-and-decision-adapter.md) and [**`ISSUE-037`**](10-decision-engine-and-jev/ISSUE-037-decision-observability-events-and-langfuse-tracing.md) (Executed concurrently)
* **Goal**:
  - `ISSUE-036`: Build `JevDecisionEngine` (HTTP client with batching) and `MockJevDecisionEngine` (in-memory deterministic tester).
  - `ISSUE-037`: Wrap the engine in `ObservableDecisionEngine`, define domain events (`DecisionEvaluationCompleted`, `DecisionGatingTriggered`), and stream telemetry/token savings to Langfuse.
* **Rationale**: Enforces Episteme's mandate that all external capabilities integrate event publishing, logging, and Langfuse tracing before phase runners consume them.

### Stage 3: Extraction, Memory & Disambiguation Adapters
* **Target Issues**: [**`ISSUE-044`**](10-decision-engine-and-jev/ISSUE-044-phase1-epistemic-relevance-and-noise-gating.md), [**`ISSUE-042`**](10-decision-engine-and-jev/ISSUE-042-episodic-working-memory-jev-state-machine.md), [**`ISSUE-043`**](10-decision-engine-and-jev/ISSUE-043-dense-entity-linking-and-ooo-gating.md), [**`ISSUE-038`**](10-decision-engine-and-jev/ISSUE-038-phase3-candidate-gating-and-relation-reranking.md), [**`ISSUE-039`**](10-decision-engine-and-jev/ISSUE-039-phase4-argument-mining-acc-arc-triage.md)
* **Goal**:
  - `ISSUE-044`: Pre-filter non-epistemic chunks in Phase 1 before token-heavy extraction.
  - `ISSUE-042`: Offload semantic boundary eviction ($B_i \in \{0, 1\}$) and local demonstrative reference resolution from the generative NER prompt to Jev in Episodic Working Memory.
  - `ISSUE-043`: Disambiguate MIPS candidates and resolve Out-of-Ontology ($e_{\text{new}}$) decisions in Phase 2 Entity Linking.
  - `ISSUE-038`: Deploy `JevRelationReranker` and pre-filter Cartesian candidate pairs ($O(N^2) \to O(N)$) in Phase 3 Global Relations.
  - `ISSUE-039`: Deploy `CascadingACCClassifier` and `CascadingARCClassifier` in Phase 4b Argument Mining to resolve $75\%–85\%$ of components/stances via sub-second fast-exit.
* **Rationale**: Resolves extraction-phase bottlenecks and cleanses runtime memory contexts before consolidation.

### Stage 4: Dynamic Gating & Graph Consolidation
* **Target Issues**: [**`ISSUE-040`**](10-decision-engine-and-jev/ISSUE-040-gleaning-and-extraction-stopping-gate.md) and [**`ISSUE-045`**](10-decision-engine-and-jev/ISSUE-045-phase3b-consolidation-merge-verification.md)
* **Goal**:
  - `ISSUE-040`: Replace introspective LLM boolean checks with an external Jev `Noul` stopping critic ($P(\text{unextracted}) > \tau$).
  - `ISSUE-045`: Verify borderline vector similarity pairs ($0.75 \le \text{cosine} \le 0.88$) in Phase 3b to prevent catastrophic over-merging and elect canonical terms.
* **Rationale**: Decouples generation from evaluation and guarantees topological invariance across the ontology.

### Stage 5: Epistemic Graph Projection & QBAF Gradual Semantics
* **Target Issue**: [**`ISSUE-041`**](10-decision-engine-and-jev/ISSUE-041-theorynet-calibrated-weights-and-qbaf-propagation.md)
* **Goal**: Project Jev's calibrated edge confidence and stance probabilities into Neo4j property graphs and `epistemetrics` QBAF gradual semantics solvers.
* **Rationale**: Replaces arbitrary float heuristics with mathematically sound empirical priors, ensuring robust equilibrium justification convergence ($\tau$).

---

## 3. Mandatory Documentation Updates
As specified in each issue, the following documentation artifacts must be synchronized upon issue completion:
- **System Architecture & ADRs**: Register a new Architecture Decision Record for the Decision Engine and update `docs/architecture/overview.md`.
- **Conceptual Foundations**: Update `docs/concepts/episodic_working_memory.md` and `docs/concepts/dense_alignment.md`.
- **Phase Workflow Guides**: Update `docs/workflow/` across all phases (1 through 6).
- **Observability & Telemetry**: Update `docs/observability/events.md` with decision event schemas and Langfuse span structures.
- **Epistemetrics Semantics**: Update `docs/concepts/theory/metrics/` with calibrated edge weight definitions.
