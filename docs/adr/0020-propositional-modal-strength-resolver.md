# [0020] Propositional Modal Strength Resolver, Structuralist Syntax Priors, and Neuro-Symbolic Hybrid Estimation

Status: Accepted (2026-10-07)

## Context

In Episteme's Layer 3 Dialectical Argument Graph ($\mathcal{D}$, [ADR 0011](0011-declarative-graph-metrics-and-qbaf-semantics.md)), arguments are formalized as a **Decoupled Quantitative Bipolar Argumentation Framework (D-QBAF)**.
D-QBAF separates three orthogonal dimensions of uncertainty:

1. **Descriptive Authorial Commitment** ($M_{\text{mod}}(\phi_a) \in [0, 1]$ on nodes): Linguistic and structural commitment with which an author states proposition $\phi_a$ (modal auxiliaries, hedges, and syntactic scope). This is an Episteme-specific operationalization inspired by linguistic epistemic modality and informed by Schurz's (2014) syntactic statement classification (`ScopeType` and `EpistemicStatus`); it is distinct from Toulmin's (1958) *Modal Qualifier* (which qualifies the inferential step from data via warrant to claim) and from Schurz's non-numeric analytic/synthetic distinction.
2. **Inferential Warrant Force** ($I_{w_k} \in [0, 1]$ on `:TheoryInference` warrants / edges): Conditional support or attack strength of the inference step (Toulmin's *Warrant* and *Backing*).
3. **Perception Extraction Confidence** ($P_{\text{stance}}, C_{\text{cal}} \in [0, 1]$): Classifier probability and calibrated empirical precision.

### Separation Between Descriptive Commitment and Normative Base Prior

Descriptive authorial commitment $M_{\text{mod}}(\phi_a)$ measures how strongly a text *asserts* a proposition, not how justified the proposition *ought* to be. Coupling D-QBAF exclusively to $M_{\text{mod}}(\phi_a)$ would allow dogmatic phrasing to outweigh cautious, well-evidenced claims. Accordingly, D-QBAF separates $M_{\text{mod}}(\phi_a)$ from the configurable solver base prior $\beta(a) \in [0, 1]$ (`BasePriorPolicy`):

- `descriptive_authorial`: $\beta(a) = M_{\text{mod}}(\phi_a)$ (models the author's stated commitments).
- `normative_uniform`: $\beta(a) = \beta_{\text{hyp}}$ (neutral prior, default $0.5$, isolating dialectical support/attack structure).
- `normative_data_priority`: $\beta(a) = \beta_{\text{data}}$ (default $0.8$) for evidential base atoms (`ObservationUnit`) and $\beta_{\text{hyp}}$ (default $0.5$) for theoretical claims (defeasible Data Priority).

### Limitations of Static Component-Type Heuristics

Deriving $M_{\text{mod}}(\phi_a)$ solely from coarse keyword lookup on `component_type` fails along three axes:

1. **Context & Hedging Blindness:** Linguistic hedges, modal auxiliaries (*may*, *might*, *must*), and evidential markers (*"we conclusively demonstrate"* vs. *"it is conceivable that"*) cannot be recovered from node type alone.
2. **Unused Syntactic Classification:** Episteme's schema ([docs/reference/schema.md](../reference/schema.md)) extracts `ScopeType` (`Essentieller Allsatz`, `Statistischer Allsatz`, `Lokalisierter Existenzsatz`, `Existenzsatz`) and `EpistemicStatus` (`Analytisch` vs. `Synthetisch`), providing structured upper/lower sanity bounds for authorial commitment.
3. **Underutilized System 1 Calibration:** The calibrated System 1 `DecisionEngine` ([ADR 0018](0018-decision-engine-architecture-and-contracts.md), [ADR 0019](0019-typesafe-jev-client-and-decision-observability.md)) enables sub-second contextual commitment estimation.

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

- **Neuro-Symbolic Guardrailing:** Combines syntactic statement-type bounds (inspired by Schurz 2014's statement taxonomy) with calibrated linguistic estimation (System 1 Jev).
- **Context-Sensitive Descriptive Commitment:** Nuanced authorial hedging (*"we tentatively hypothesize"*) is captured in $M_{\text{mod}}(\phi_a)$ without forcing normative D-QBAF priors to equate rhetorical confidence with epistemic warrant.
- **Full Inversion of Control:** Resolvers can be mocked, swapped, or tuned via configuration without modifying phase logic.
- **Typed Observable Contract:** Exposes a typed protocol emitting `ModalStrengthResolved` telemetry events.
- **Orthogonal to Intensional Scoping ([ADR 0023](0023-intensional-perspectival-scoping-and-conception-stratification.md)):** `ModalStrengthResolver` computes descriptive commitment $M_{\text{mod}}(\phi_a)$ independently of whether the claim is `asserted`, `suppositional` (*Reductio*), `attributed` to another philosopher, or `historical`; downstream D-QBAF projection applies `BasePriorPolicy`, perspective filtering, and supposition gating (`effective_base_prior` and `QBAFGradualSemanticsSolver`) without mutating $M_{\text{mod}}(\phi_a)$.
- **Orthogonal to Warrant Reification, Backing & Undercutting:** Toulmin's *Backing* (`BACKS`) and Pollockian *Undercutters* (`UNDERCUTS`) target reified `:TheoryInference` warrant nodes $\mathcal{W}$, modulating dynamic inferential validity $s(w_k, t)$ in D-QBAF without altering node-level descriptive commitment $M_{\text{mod}}(\phi_a)$.

### Negative / Trade-offs

- Slight additional compute during Phase 4 ADU classification when running System 1 decision engine evaluation.
