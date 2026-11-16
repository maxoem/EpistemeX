# Phase 6: TheoryNet Projection

## Overview

Phase 6 executes the **TheoryNet Projection** pass (`Phase6Runner`). Operating on canonicalized theory atoms and dialectical relations (`canonical_theory_atoms`, `canonical_theory_relations`) from Phase 4 and Phase 5, Phase 6 materializes the formal **Stratified Epistemic State Tuple** ([ADR-0022](../../adr/0022-unified-stratified-epistemic-metamodel.md)), resolves intensional and perspectival scoping ([ADR-0023](../../adr/0023-intensional-perspectival-scoping-and-conception-stratification.md)), solves continuous D-QBAF gradual semantics, evaluates empirical $Z_1$ reachability, and optionally emits top-down `EpistemicDeficitArtifact` signals ([ADR-0024](../../adr/0024-closed-loop-hermeneutic-refinement.md)).

## Goals

- Resolve node-intrinsic propositional modal priors ($\tau_0(a) \equiv M(\phi_a)$) via `HybridModalResolver`, respecting `EpistemicCurationLedger` overrides.
- Derive decoupled edge-intrinsic Toulmin inferential warrants ($I_{j \to i}$) and enforce bivariate admissibility gating ($\tau_p, \tau_c$) without $M(\phi)^2$ double-penalization.
- Compute D-QBAF equilibrium justification degrees ($\tau^*(a)$) and controversy volatility ($\mathcal{V}(a)$) via `QBAFGradualSemanticsSolver` with intensional supposition/attribution isolation and conjunctive t-norms (`"product"` or `"godel"`).
- Verify structuralist empirical content via $Z_1$ BFS reachability between theoretical $A$-atoms and empirical $B$-atoms.
- Emit `TheoryAtomArtifact`, `TheoryRelationArtifact`, and optional `EpistemicDeficitArtifact` envelopes (`refinement_pass` tracked on provenance), plus optional direct `ProjectionGraph` upserts.

## Steps

1. **Hydration & Curation Ledger Overrides**:
   - Ingests `Phase4ArtifactsView` (`Phase5ArtifactsView`), preferring `canonical_theory_atoms` and `canonical_theory_relations`.
   - Applies `EpistemicCurationLedger.get_modality_override(atom.id)` and `apply_to_theory_relations(...)` when a curation ledger is configured on `PipelineInput`.
2. **Propositional Modal Prior ($\tau_0(a)$ via `HybridModalResolver`)**:
   - For atoms lacking an explicit `modal_prior` and `resolver_type`, invokes `HybridModalResolver.resolve_modality(atom)` combining `StructuralistModalResolver` syntax bounds $[L_{\text{syn}}, U_{\text{syn}}]$ (`ScopeType`, `EpistemicStatus`, component type) with optional `DecisionEngineModalResolver`.
   - Modulates effective prior by local tenability and intensional scoping inside `TheoryAtom.effective_base_prior(...)`:
     $$\tilde{\tau}_0(a) = \tau_0(a) \cdot TS_{\text{local}}(a) \quad (\text{isolated to } 0.0 \text{ when } \texttt{suppositional} \text{ or off-perspective})$$
3. **Relational Warrant & Bivariate Admissibility Gating ($W_{ji}$)**:
   - Inside `TheoryNetProjector.project()`, assigns `inferential_warrant` via `derive_relation_warrant(rel)` if unset (`1.00` entailment/refutation, `0.75` support/attack, `0.60` undercut, `0.40` analogy).
   - Evaluates bivariate admissibility against `tau_p` (perception stance probability $P$) and `tau_c` (calibrated empirical accuracy $C$):
     $$W_{ji} = I_{j \to i} \cdot \mathcal{F}_{\text{gate}}(P_{ji}, C_{ji}) \cdot TS_{\text{edge}}(e_{ji})$$
     where Mode `"hard"` gates `is_admissible = (P >= tau_p and C >= tau_c)` and Mode `"soft"` applies continuous sigmoidal relaxation $\sigma(20(P - \tau_p)) \cdot \sigma(20(C - \tau_c))$.
4. **D-QBAF Equilibrium Solving ($\tau^*(a)$ & $\mathcal{V}(a)$)**:
   - Converts atoms and relations into `epistemetrics.core.models.TheoryNode` / `TheoryEdge` inputs and invokes `QBAFGradualSemanticsSolver.solve(...)` (`WeightNormalizationMode.CALIBRATED_MODAL`, `perspective`, `isolate_suppositional`, `isolate_attributed`, `t_norm`).
   - Populates `atom.equilibrium_strength` ($\tau^*(a)$) via closed-form DAG pass or adaptive `WeightedQuadraticEnergySolver` ODE integration and records `atom.controversy_volatility` ($\mathcal{V}(a)$).
5. **Graph Projection & Empirical Content ($Z_1$) BFS**:
   - When `self.graph_store` is supplied (direct-write mode), upserts batches of 500 via `upsert_argument_components()` and `upsert_theory_relations()`. In artifact-native mode, graph projection is handled later by `ArtifactGraphProjector`.
   - Partitions atoms using `SchemaConfig.component_partitions` (`"A"`: `TheoreticalHypothesis`, `CoreExpansion`; `"B"`: `ObservationUnit`, `EmpiricalStatement`), finds the direct empirical boundary `z1_connected`, and runs BFS across `A`-`A` edges to compute the empirical content ratio $|\text{visited}| / |V_A|$.
6. **Artifact Emission & Optional Top-Down Deficit Detection**:
   - Emits `TheoryAtomArtifact` and `TheoryRelationArtifact` envelopes stamped with `manifest.refinement_pass`.
   - If `self.deficit_detector` (`EpistemicDeficitDetector`, e.g. `TheoryNetDeficitDetector`) is configured, builds an updated `Phase4ArtifactsView` over `theory_net`, runs `detect_deficits(...)`, and emits prioritized `EpistemicDeficitArtifact` envelopes (`ENTHYMEME_GAP`, `POLYSEMY_COLLISION`, `UNGROUNDED_AXIOM`), which `ClosedLoopRefinementCoordinator` consumes during `ArtifactExecutionEngine._run_refinement_stage()` when `max_refinement_cycles > 0`.

## Phase Data Flow

- **Input:** `Phase4ArtifactsView` (`Phase5ArtifactsView` with canonicalized atoms and relations).
- **Output:** `ArtifactCollection` containing `TheoryAtomArtifact`, `TheoryRelationArtifact`, and optional `EpistemicDeficitArtifact` envelopes.
- **Graph updates (via `ArtifactGraphProjector` or optional `graph_store`):**
  - `:TheoryAtom` nodes: `modal_prior`, `equilibrium_strength`, `controversy_volatility`, `intensional_mode`, `attributed_to`, `local_tenability`.
  - `:THEORY_RELATION` edges / reified `:TheoryInference` nodes: `inferential_warrant`, `is_admissible`, `active_weight`, `effective_weight`, `edge_tenability`, `weight_support`, `weight_attack`.

## Pluggability

- **Projector**: Inject custom `TheoryNetProjector` via `Phase6Runner(projector=...)`.
- **Modal Resolver**: Inject `ModalStrengthResolver` via `Phase6Runner(modal_resolver=...)`.
- **Deficit Detector**: Inject `EpistemicDeficitDetector` via `Phase6Runner(deficit_detector=...)` (normalized via `ensure_deficit_detector`).
- **Schema**: Partition definitions, component types, and relation polarities are governed by `SchemaConfig`.

## Implementation

- `episteme_pipeline/phases/phase6_theorynet/runner.py` — `Phase6Runner`
- `episteme_pipeline/projection/theorynet_projector.py` — `TheoryNetProjector`, `derive_atom_modality`, `derive_relation_warrant`
- `episteme_pipeline/decision/modal_resolver.py` — `HybridModalResolver`, `StructuralistModalResolver`, `DecisionEngineModalResolver`
- `episteme_pipeline/refinement/detector.py` — `TheoryNetDeficitDetector`
- `episteme_pipeline/contracts/domain.py` — `TheoryNet`, `TheoryAtom`, `TheoryRelation`, `EpistemicDeficit`
- `episteme_pipeline/config.py` — `Phase6Config`, `HermeneuticRefinementConfig`
