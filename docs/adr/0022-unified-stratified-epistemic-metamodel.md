# [0022] Unified Stratified Epistemic Metamodel: Reconciling TF, D-QBAF, and Structuralist Tenability Feedback

Status: Accepted  
Date: 2026-11-07  
Partially Supersedes: ADR-0007 (TF scalar `TF(a)` and `plausibility` sections)  
Extends: ADR-0011 (Addendum 2: Continuous D-QBAF), ADR-0015 (Theoretical Enrichment), ADR-0020 (Propositional Modal Strength Resolver)

---

## Context

Across the evolution of the Episteme architecture, three distinct mathematical formalisms were introduced to model Layer 3 (`TheoryNet`) epistemic strength and evaluation:

1. **Theoriennetz (`TF`) & $\kappa$-Structural Correspondence ([ADR-0007](0007-tf-structural-correspondence.md))**: Introduced `structural_correspondence` ($\kappa$-overlap) on edges and an uncalibrated topological count ratio $TF(a) = |S(a)| / (|S(a)| + |A(a)| + 1)$.
2. **Continuous Dynamic QBAF (`D-QBAF`, [ADR-0011 Addendum 2](0011-declarative-graph-metrics-and-qbaf-semantics.md)) & Propositional Modality ([ADR-0020](0020-propositional-modal-strength-resolver.md))**: Established node-intrinsic propositional modal priors $\tau_0(a) \equiv M(\phi_a) \in [0, 1]$ via `HybridModalResolver`, Toulminian inferential warrants $I_{j \to i} \in [0, 1]$ on edges, and continuous D-QBAF equilibrium justification $\tau^*(a) \in [0, 1]$ solved via closed-form topological passes on DAGs and adaptive ODE integration (`RK45`/`Radau`) on cyclic graphs.
3. **Bourbaki/Sneed Structuralist Tenability ([ADR-0015](0015-theoretical-enrichment-and-tenability-evaluation.md))**: Computed local empirical tenability $TS_{\text{local}} = \sup \{1 - \delta\}$ and intertheoretical edge tenability $TS_{\text{edge}} = 1 - \delta_c$ in `TheoreticalEnrichmentRunner`, but operated as an open-loop sink that did not feed back into D-QBAF justification degrees $\tau^*(a)$.

Additionally, `TheoryRelation` and `TheoryRelationArtifact` retained a legacy edge-level `modal_strength` attribute that risked $M(\phi)^2$ double-penalization when multiplied with node modality.

---

## Decision

### 1. Stratified Epistemic State Tuple

Every `TheoryAtom` $a \in \mathcal{A}$ and `TheoryRelation` $e \in \mathcal{R}$ is governed by a four-layer **Stratified Epistemic State Tuple** with strictly orthogonal responsibilities:

1. **Layer 1 — Propositional Prior (Node-Intrinsic, Phase 4 / [ADR-0020](0020-propositional-modal-strength-resolver.md))**:
   $$\tau_0(a) \equiv M(\phi_a) \in [0, 1]$$
   Represents the author's rhetorical/modal commitment to proposition $\phi_a$, derived via `HybridModalResolver` (`StructuralistModalResolver` syntax bounds $[L_{\text{syn}}, U_{\text{syn}}]$ + `DecisionEngineModalResolver`). Stored exclusively on `TheoryAtom` (`modal_prior` / `modal_strength` / `base_score`, alongside `resolver_type` and `syntax_bounds`).

2. **Layer 2 — Relational Warrant & Perceptual Gating (Edge-Intrinsic, Phase 4–6 / [ADR-0011](0011-declarative-graph-metrics-and-qbaf-semantics.md))**:
   $$W_{ji} = I_{j \to i} \cdot \mathcal{F}_{\text{gate}}(P_{ji}, C_{ji}) \cdot TS_{\text{edge}}(e_{ji})$$
   Where $I_{j \to i} \in [0, 1]$ is strictly the Toulminian relational warrant (`inferential_warrant` / `inferential_force`)—**never** the node's modal strength $M(\phi)$—eliminating $M^2$ double-penalization. `modal_strength` is completely removed from `TheoryRelation` and `TheoryRelationArtifact`.

3. **Layer 3 — Empirical & Structural Tenability (Node & Edge Constraints, Post-Processing / [ADR-0015](0015-theoretical-enrichment-and-tenability-evaluation.md))**:
   $$TS_{\text{local}}(a) \in [0, 1], \qquad TS_{\text{edge}}(e) \in [0, 1]$$
   Represents empirical model-theoretic satisfaction ($M_p \cap I$ under blur $\delta^*$) and intertheoretical constraint satisfaction ($C, \rho$), stored as `local_tenability` on `TheoryAtom` and `edge_tenability` on `TheoryRelation`.

4. **Layer 4 — Dialectical Equilibrium (Global Fixed-Point, Phase 6 & Theoretical Enrichment / [ADR-0011 Addendum 2](0011-declarative-graph-metrics-and-qbaf-semantics.md))**:
   $$\tau^*(a) = \tilde{\tau}_0(a) + \bigl(1 - \tilde{\tau}_0(a)\bigr)\,h(E_a) - \tilde{\tau}_0(a)\,h(-E_a), \qquad E_a = \sum_{b \in \text{Supp}(a)} W_{ba}\,\tau^*(b) - \sum_{c \in \text{Att}(a)} W_{ca}\,\tau^*(c), \qquad h(x) = \frac{\max(x, 0)^2}{1 + \max(x, 0)^2}$$
   Where empirical tenability modulates the effective base prior:
   $$\tilde{\tau}_0(a) = \tau_0(a) \cdot TS_{\text{local}}(a)$$
   Solved via closed-form $O(|V| + |E|)$ topological evaluation on DAGs and adaptive ODE integration (`RK45`/`Radau`) on cyclic graphs via `WeightedQuadraticEnergySolver`. Stored on `TheoryAtom` as `equilibrium_strength` (aliased as `plausibility`), accompanied by Keynes-Gärdenfors controversy volatility $\mathcal{V}(a)$ (`controversy_volatility`).

### 2. Closed-Loop Coupling Between `TheoreticalEnrichmentRunner` and D-QBAF

- `TheoryNetProjector` modulates each atom's prior by `local_tenability` ($\tilde{\tau}_0(a) = \tau_0(a) \cdot TS_{\text{local}}(a)$) and each relation's solver weight by `edge_tenability` ($W_{ji} \cdot TS_{\text{edge}}(e)$).
- When `TheoreticalEnrichmentRunner` evaluates $TS_{\text{local}}$ and $TS_{\text{edge}}$, it executes an incremental D-QBAF re-convergence pass via `TheoryNetProjector`, updating `equilibrium_strength`, `plausibility`, and `controversy_volatility` on `TheoryAtom` artifacts and graph projections so empirically falsified hypotheses ($TS_{\text{local}} < 0.5$) immediately reflect degraded dialectical justification $\tau^*$.

### 3. ADR-0007 Supersession Scope

- **Retained from [ADR-0007](0007-tf-structural-correspondence.md)**: $\kappa$-Structural Correspondence (`structural_correspondence` on `TheoryRelation`) and the Sneed/Stegmüller/Balzer structuralist poset hierarchy (`ScopeType`).
- **Superseded in [ADR-0007](0007-tf-structural-correspondence.md)**: The uncalibrated $TF(a)$ count ratio and replacement of QBAF by unweighted `TF` are superseded by [ADR-0011 Addendum 2](0011-declarative-graph-metrics-and-qbaf-semantics.md), [ADR-0020](0020-propositional-modal-strength-resolver.md), and this ADR.

---

## Consequences

- **Zero $M^2$ Double-Penalization**: Removing `modal_strength` from `TheoryRelation` and `TheoryRelationArtifact` ensures node modality $M(\phi_a)$ is applied once at the node prior $\tau_0(a)$ while edges carry `inferential_warrant` $I_{j \to i}$.
- **Bidirectional Empirical-Dialectical Coherence**: Empirically falsified hypotheses ($TS_{\text{local}} < 0.5$) can no longer retain artificially high D-QBAF equilibrium justification $\tau^*(a)$ merely because the author asserted them with high rhetorical certainty.
- **Lossless Artifact Hydration**: `TheoryAtomCodec`, `TheoryRelationCodec`, and `Phase4ArtifactsView` preserve all four layers of the Stratified Epistemic State Tuple across checkpointing and DAG branch reuse.
