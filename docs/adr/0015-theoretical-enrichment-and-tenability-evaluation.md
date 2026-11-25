# [0015] Post-Processing Theoretical Enrichment (Phi_spec) and Tenability Evaluation (TS_local, TS_edge)

Status: Accepted (2026-09-08)

## Context

Scientific theories cannot be adequately characterized as flat collections of linguistic assertions. In the structuralist metatheory of science ([Stegmüller, 1976]; [Balzer et al., 1987]; [Schurz, 2014]), a theory-element is formalized as $T = \langle K, I \rangle$, comprising a formal core $K = \langle M_p, M, M_{pp}, GC, GL \rangle$ and a domain of intended applications $I \subseteq M_{pp}$.

Episteme operationalizes structuralism across three tiers: universal **Tier A (*Structuralism Light*)** capturing specialization posets $\langle N, \sigma \rangle$ and $T$-theoreticity ($M_p / M_{pp}$); **Tier B (Parametric Enrichment)** defined in this ADR for domains possessing explicit quantitative or symbolic laws; and **Tier C (Full BMS Model Theory)** as a regulative ideal.

Initial NLP ingestion and argument mining phases (Phases 1–4) must remain strictly domain-agnostic ($\Phi_{\text{gen}}$). Hardcoding domain-specific parameter extraction into core prompts degrades pipeline generality, inflates token budgets with hallucinated parameters, and causes type collisions in multi-theoretical texts (e.g., neuropsychoanalysis combining neurology and psychoanalysis).

Evaluating whether an empirical application satisfies a theory requires continuous approximation rather than binary truth values ([Stegmüller, 1976]; [Balzer et al., 1987, Ch. VII]). Using Bourbaki's **uniform spaces** and **admissible blurs ($\mathfrak{A}$)**, tenability evaluates the tightest inaccuracy neighborhood $\delta$ under which projected parameters satisfy core laws $M$, empirical consequence $\operatorname{Cn}_{\text{str}}(K)$, and intertheoretical constraints $GC, GL$.

## Decision

We implement a dedicated, modular post-processing runner: **Theoretical Enrichment & Tenability Evaluation** (`TheoreticalEnrichmentRunner`), decoupled from sequential pipeline phase numbers into `packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/`, executing the dual-enrichment architecture $\Phi(y) = \Phi_{\text{spec}}(\Phi_{\text{gen}}(y))$:

### 1. Separation of Domain-Agnostic Extraction from Specific Enrichment
* **General Extraction ($\Phi_{\text{gen}}$)** remains in core Phases 1–5, emitting domain-agnostic `ObservationUnit` (Partition $B$), `EmpiricalStatement` ($B$), and `TheoreticalHypothesis` ($A$) nodes with typed relations (`CONSTRAINS`, `REDUCES_TO`, `COHERES_WITH`).
* **Specific Enrichment ($\Phi_{\text{spec}}$)** is deferred to Theoretical Enrichment post-processing, where domain-specific lenses project empirical clusters into bespoke theoretical spaces $M_p$.

### 2. Multi-Theory Lenses over Shared Empirical Clusters (Mixed Models)
* When a text discusses multiple theories, empirical clusters of `ObservationUnit` nodes are treated as shared **Intended Applications ($I$)**.
* The cluster is evaluated through multiple distinct theoretical lenses in parallel (these are examples, and should be dynamically extracted during pipeline run)
  * **Neurology Lens ($\Phi_{\text{spec-Neuro}}$):** Filters physiological/fMRI dimensions, ignores verbal associations, and estimates neurochemical parameters (e.g. `DopamineDepletion`, `AmygdalaHyperactivity`).
  * **Psychoanalysis Lens ($\Phi_{\text{spec-Freud}}$):** Filters verbal repetition and affect dimensions, ignores fMRI blood flows, and estimates unconscious parameters (e.g. `RepressionMagnitude`, `UnconsciousResistance`).
* **Intertheoretical Links ($GL$):** Inter-model relations (`CONSTRAINS`, `REDUCES_TO`, `COHERES_WITH`) connect the theoretical hypotheses, checking whether Freud's parameters mathematically cohere with the neurological parameters.

### 3. Continuous Tenability Optimization Solvers
* **Local Tenability ($TS_{\text{local}}$):** Computes the tightest admissible blur $\delta^*$ reconciling projected parameters with core laws $M$:
$$TS_{\text{local}}(y, M) = \sup \{ 1 - \delta \mid \exists x^* \in M : (\Phi(y), x^*) \in u_\delta \}$$
* **Edge Tenability ($TS_{\text{edge}}$):** Evaluates cross-cluster constraints and inter-theory links:
$$TS_{\text{edge}}(e) = \sup \{ 1 - \delta_C \mid (\Phi(y_a), \Phi(y_b)) \in v_{\delta_C} \}$$
* **Anomaly Flagging:** Any hypothesis or constraint edge with $TS < 0.5$ is flagged as an untenable anomaly or category error.

### 4. Pluggable Runner, Config & Registry Architecture
* Implements `PhaseRunner[Phase4ArtifactsView]` with machine key `phase_key = "theoretical_enrichment"`.
* Configured via `TheoreticalEnrichmentConfig` under `pipeline_config.theoretical_enrichment`.
* Provides `TheoryRegistry` for user-defined Theory-Element schemas and custom `TheoryProjector` implementations.
* Supports pluggable injection via `Pipeline(phases=[...])` and `Pipeline.for_task(..., post_processors=[...])`.
* Emits domain events (`TheoreticalClusterIdentified`, `TheoreticalParametersProjected`, `TenabilityEvaluationCompleted`, `TenabilityAnomalyDetected`) hooked into `EventEmitter`.

### 5. Dynamic Two-Stage Theory Induction & Safe Symbolic Laws
* Instead of hardcoding default scientific domains (e.g. neurology or psychoanalysis), `TheoryRegistry` is dynamically populated by `LLMTheoryInducer`.
* The inducer inspects the graph's `TheoreticalHypothesis` nodes (Partition $A$) and empirical observation types (Partition $B$) at macro graph scope to discover active Theory-Elements $T = \langle K, I \rangle$ with their non-theoretical dimensions ($M_{pp}$), latent parameters ($M_p$), and symbolic constraint laws ($M$).
* Core laws are evaluated safely via an AST-based formula evaluator (`SafeFormulaEvaluator`), eliminating `eval()` security risks while supporting non-linear and functional constraints.

### 6. Closed-Loop D-QBAF Re-Convergence & Top-Down Deficit Emission ([ADR-0022](0022-unified-stratified-epistemic-metamodel.md), [ADR-0024](0024-closed-loop-hermeneutic-refinement.md))
* Following Step 4 (`TS_edge` evaluation), `TheoreticalEnrichmentRunner` executes Step 4.5 via `TheoryNetProjector.project(...)` to propagate $TS_{\text{local}}$ and $TS_{\text{edge}}$ back into D-QBAF equilibrium acceptability $s^*(a)$ and controversy volatility $\mathcal{V}(a)$ ([ADR-0022](0022-unified-stratified-epistemic-metamodel.md)).
* When configured with an `EpistemicDeficitDetector` (`TheoryNetDeficitDetector`), `TheoreticalEnrichmentRunner` translates failing empirical/structural criteria ($TS_{\text{local}} < 0.5$, `is_tenable == False`, missing $M_{pp}$ `required_dimensions`, or $TS_{\text{edge}} < 0.5$ / elevated $\mathcal{V}$ bridging incompatible clusters) into typed `EpistemicDeficitArtifact` signals (`UNGROUNDED_AXIOM`, `POLYSEMY_COLLISION`, `ENTHYMEME_GAP`) triggering localized top-down recovery ([ADR-0024](0024-closed-loop-hermeneutic-refinement.md)).

## Alternatives Considered

1. **Extracting Parameters During Ingestion (Phase 2/4):** Rejected because it destroys pipeline domain-independence, blows up prompt sizes, and fails when texts discuss novel or conflicting theories.
2. **Binary Truth Values ($\text{Score} \in \{0, 1\}$):** Rejected because real-world empirical data always contains noise; threshold discontinuities obscure meaningful gradations in empirical fit ([Stegmüller, 1976]).
3. **Single Universal Parametric Space:** Rejected because heterogeneous quantities (meters, seconds, Hz, psychic repression) cannot be meaningfully combined into a single metric distance without arbitrary scaling factors.
4. **Hardcoding as Sequential "Phase 7":** Rejected because theoretical enrichment is an optional, analytical post-processing pass. Forcing an ordinal phase number creates false linearity and awkward numbering when other post-processors are introduced or skipped.
5. **Hardcoding Default Domain Theories:** Rejected because real-world scientific literature spans physics, biology, economics, philosophy, and psychology; hardcoding theories breaks library generality and requires manual updates for each new domain.

## Consequences

- The pipeline maintains pristine separation between domain-agnostic structural extraction and theory-specific quantitative semantics.
- Mixed-domain scientific literature can be evaluated without ontological confusion or hardcoded domain schemas.
- Tenability scores provide continuous, grounded epistemic confidence for computational philosophy of science.
- Custom theories and laws can be induced autonomously by LLM or registered programmatically.
- Post-processing suites remain modular and independently configurable.

## Related

- [`docs/concepts/theory/metrics/epistemic_coherence/tenability.md`](../concepts/theory/metrics/epistemic_coherence/tenability.md) — Mathematical specification of tenability and admissible blurs.
- [`docs/reference/theoretical_enrichment.md`](../reference/theoretical_enrichment.md) — Theoretical Enrichment post-processor reference documentation.
- [`packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/runner.py`](../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/runner.py) — Post-processor runner implementation.
- [ADR 0006: QBAF Mapping Deferred](0006-qbaf-mapping-deferred.md) — Early precedent for deferring quantitative weight computation.
- [ADR 0011: Declarative Graph Metrics Framework](0011-declarative-graph-metrics-and-qbaf-semantics.md) — Async metrics architecture.
- [ADR 0022: Unified Stratified Epistemic Metamodel](0022-unified-stratified-epistemic-metamodel.md) — Coupled D-QBAF feedback from $TS_{\text{local}}$ and $TS_{\text{edge}}$.
- [ADR 0024: Closed-Loop Hermeneutic Refinement](0024-closed-loop-hermeneutic-refinement.md) — Top-down `EpistemicDeficitArtifact` emission and localized recovery triggered by tenability anomalies.
