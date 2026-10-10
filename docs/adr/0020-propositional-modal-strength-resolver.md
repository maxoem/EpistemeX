# [0020] Propositional Modal Strength Resolver, Structuralist Syntax Priors, and Neuro-Symbolic Hybrid Estimation

Status: Accepted (2026-10-07)

## Context

In Episteme's TheoryNet architecture ([ADR 0011](0011-declarative-graph-metrics-and-qbaf-semantics.md)) dialectical
arguments are formalized as a **Decoupled Quantitative Bipolar Argumentation Framework (D-QBAF)**.
A core pillar of D-QBAF is the clean decoupling of three orthogonal dimensions of uncertainty:

1. **Authorial Propositional Modality** ($M (\phi_a) \equiv \tau_0 (a)$ on nodes): Grounded in Toulmin's (1958) *Modal
   Qualifier* and Schurz's (2014) *Epistemic Status*.
2. **Inferential Warrant Validity** ($\mathcal{I} (a_j \to a_i)$ on edges): Grounded in Toulmin's *Warrant and Backing*.
3. **Perception Extraction Confidence** ($\mathcal{P} (\text{stance}), \mathcal{C}$): Classifier probability and
   calibrated empirical precision.

### The Problem with Static Hardcoded Heuristics

Previously, node modality was derived via a rigid function (`derive_atom_modality`) that used coarse keyword matching on
`component_type` (e.g., assigning $0.85$ to empirical observations, $0.60$ to hypotheses, and $0.35$ to conjectures).
This suffered from three fundamental limitations:

1. **Context & Hedging Blindness:** Modality is expressed through linguistic hedges, modal auxiliaries (*may*, *might*,
   *must*), and evidentials (*"we conclusively demonstrate"* vs. *"it is conceivable that"*). A hypothesis asserted as
   almost certain and one posited as a wild guess both received $0.60$.
2. **Ignoring Structuralist Syntax:** Episteme's schema ([docs/reference/schema.md](../reference/schema.md)) already
   extracts fine-grained structuralist properties: `ScopeType` (`Essentieller Allsatz`, `Statistischer Allsatz`,
   `Lokalisierter Existenzsatz`, `Existenzsatz`) and `EpistemicStatus` (`Analytisch` vs. `Synthetisch`). The old logic
   ignored `ScopeType` entirely.
3. **Bypassing the Dual-Process Architecture:** The System 1 `DecisionEngine`
   ([ADR 0018](0018-decision-engine-architecture-and-contracts.md), [ADR 0019](0019-typesafe-jev-client-and-decision-observability.md))
   was not utilized to evaluate authorial commitment, missing out on sub-second calibrated predictions.

---

## Decision

We implement a modular, pluggable **Propositional Modal Strength Resolution Framework**.

### 1. The Core Abstraction (`episteme_pipeline/protocols/modality.py`)

- Defined the abstract `@runtime_checkable` `ModalStrengthResolver` protocol with async and sync resolution contracts:
    - `async def resolve_modality(self, atom: TheoryAtom, context: str | None = None) -> float`
    - `def resolve_modality_sync(self, atom: TheoryAtom, context: str | None = None) -> float`
- Provided `ensure_modal_strength_resolver` for composition root normalization.

### 2. Concrete Provider Suite (`episteme_pipeline/decision/modal_resolver.py`)

- **`StructuralistModalResolver` (Symbolic Reference):**
    - Evaluates Schurz's (2014) structuralist ontology deterministically:
        - `Essentieller Allsatz + Analytisch` $\to 1.00$ (Axiomatic / Nomological analytic necessity)
        - `Essentieller Allsatz + Synthetisch` $\to 0.90$ (Universal empirical law)
        - `Lokalisierter Existenzsatz` $\to 0.85$ (Empirical observational datum priority)
        - `Lokalisierter Allsatz` $\to 0.85$ (Bounded universal empirical generalization)
        - `Statistischer/probabilistischer Allsatz` $\to 0.75$ (Probabilistic law)
        - `Existenzsatz` $\to 0.55$ (Contingent hypothesis)
    - Provides `get_syntax_bounds(atom)` returning admissible interval $[M_{\min}, M_{\max}]$ for guardrailing.
- **`DecisionEngineModalResolver` (System 1 Linguistic Estimator):**
    - Evaluates claim text and surrounding sentence context against ordinal certainty levels using
      `DecisionEngine.evaluate_choice`.
    - Calculates expected continuous modal strength $\mathbb{E}[M] = \sum_k v_k \cdot p_k$ over predicted probabilities.
- **`HybridModalResolver` (Neuro-Symbolic Composite):**
    - Harmonizes structuralist syntax with empirical linguistic scoring:
        - **Guardrail Mode (Default):** Runs `DecisionEngineModalResolver` and clamps the result within the
          structuralist interval $[M_{\min}, M_{\max}]$.
        - **Convex Mode:** Computes weighted sum $\alpha M_{\text{syntax}} + (1 - \alpha) M_{\text{engine}}$.
        - **Structural / Engine Only Modes:** Allows pure execution of either constituent.

### 3. Observability & Domain Events (`episteme_pipeline/events/models.py`)

- Introduced `ModalStrengthResolved(BaseEvent)` capturing `atom_id`, `modal_strength`, `resolver_type`, `scope_type`,
  `epistemic_status`, `raw_engine_score`, and `clamped`.
- Emitted automatically by `HybridModalResolver` through the task-local `EventEmitter`.

### 4. Lifecycle Integration & Composition Root

- Added `ModalResolverConfig` in `pipeline/config.py`, embedded into `Phase4Config`, `Phase6Config`, and
  `PipelineConfig`.
- Injected `modal_resolver` into:
    - **Phase 4 (`Phase4Runner` & `DecisionEngineACCClassifier`):** Resolves propositional certainty on newly mined ADUs
      using the chunk context window.
    - **Phase 6 (`Phase6Runner` & `TheoryNetProjector`):** Ensures all projected `TheoryAtom` instances carry calibrated
      modal base scores before running QBAF gradual semantics convergence.
    - **Composition Root (`Pipeline.for_task`):** Automatically initializes the hybrid resolver with the active
      `decision_engine` and configuration.

---

## Consequences

### Positive

- **Neuro-Symbolic Rigor:** Combines theoretical constraints from philosophy of science (Schurz 2014) with calibrated
  machine learning (System 1 Jev).
- **Context-Sensitive Modality:** Nuanced authorial hedging (*"we tentatively hypothesize"*) accurately modulates
  initial claim standing in QBAF.
- **Full Inversion of Control:** Resolvers can be mocked, swapped, or tuned via configuration without touching phase
  logic.
- **Clean Decoupling:** Replaces ad-hoc string regexes with a typed, observable protocol backed by unit tests.

### Negative / Trade-offs

- Slight additional compute during Phase 4 ADU classification when running System 1 decision engine evaluation.
