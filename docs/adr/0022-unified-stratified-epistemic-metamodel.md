# [0022] Unified Stratified Epistemic Metamodel: Reconciling TF, D-QBAF, and Structuralist Tenability Feedback

Status: Accepted  
Date: 2026-11-07  
Partially Supersedes: ADR-0007 (TF scalar `TF(a)` and `plausibility` sections)  
Extends: ADR-0011 (Addendum 2: Continuous D-QBAF), ADR-0015 (Theoretical Enrichment), ADR-0020 (Propositional Modal Strength Resolver)

---

## Context

Episteme's epistemic representation integrates three analytical mechanisms across the Layer 3 Dialectical Argument Graph ($\mathcal{D}$) and Layer 4 Structuralist Theory-Net ($\mathcal{N} = \langle N, \sigma \rangle$):

1. **$\kappa$-Structural Correspondence ([ADR-0007](0007-tf-structural-correspondence.md))**: Construction-time structural overlap score $\mathrm{ov}_{\text{str}}$ (`structural_correspondence`) assessing atom-to-entity grounding compatibility.
2. **Continuous Dynamic QBAF (`D-QBAF`, [ADR-0011 Addendum 2](0011-declarative-graph-metrics-and-qbaf-semantics.md)) & Propositional Modal Resolver ([ADR-0020](0020-propositional-modal-strength-resolver.md))**: Descriptive authorial commitment $M_{\text{mod}}(\phi_a) \in [0, 1]$ via `HybridModalResolver`, configurable solver base priors $\beta(a) \in [0, 1]$ (`BasePriorPolicy`), Toulminian inferential warrants $I_{w_k} \in [0, 1]$, and continuous D-QBAF equilibrium acceptability $s^*(a) \in [0, 1]$ solved via closed-form topological passes on DAGs and adaptive ODE integration (`RK45`/`Radau`) on cyclic graphs.
3. **Bourbaki/Sneed Structuralist Tenability ([ADR-0015](0015-theoretical-enrichment-and-tenability-evaluation.md))**: Local empirical tenability $TS_{\text{local}}(a) = \sup\{1 - \delta\}$ under uniform-space admissible blurs $\mathfrak{A}$ and intertheoretical constraint tenability $TS_{\text{edge}}(e) = 1 - \delta_C$ in `TheoreticalEnrichmentRunner`.

Without closed-loop coupling, empirical tenability operates as an open-loop sink disconnected from dialectical equilibrium $s^*(a)$, and storing `modal_strength` on relations risks $M_{\text{mod}}^2$ double-penalization.

---

## Decision

### 1. Stratified Epistemic State Tuple

Every `TheoryAtom` $a \in \mathcal{A}$ and `TheoryRelation` / `:TheoryInference` warrant $w_k \in \mathcal{W}$ is governed by a four-layer **Stratified Epistemic State Tuple** with orthogonal responsibilities (symbols follow [`docs/concepts/notation.md`](../concepts/notation.md)):

1. **Layer 1 — Authorial Commitment & Configurable Base Prior (Node-Intrinsic, Phase 4 / [ADR-0020](0020-propositional-modal-strength-resolver.md))**:
   $$M_{\text{mod}}(\phi_a) \in [0, 1], \qquad \beta(a) \in [0, 1]$$
   $M_{\text{mod}}(\phi_a)$ captures the author's descriptive modal commitment derived via `HybridModalResolver` (`StructuralistModalResolver` syntax bounds $[M_{\min}, M_{\max}]$ + `DecisionEngineModalResolver`) and stored exclusively on `TheoryAtom` (`modal_strength`). The solver base prior $\beta(a)$ is derived from `BasePriorPolicy` (`descriptive_authorial`, `normative_uniform`, or `normative_data_priority`).

2. **Layer 2 — Relational Warrant & Perceptual Gating (Inference-Intrinsic, Phase 4–6 / [ADR-0011](0011-declarative-graph-metrics-and-qbaf-semantics.md))**:
   $$W_{w_k} = I_{w_k} \cdot \mathcal{F}_{\text{gate}}(P_{w_k}, C_{w_k}) \cdot TS_{\text{edge}}(w_k)$$
   where $I_{w_k} \in [0, 1]$ is strictly the Toulminian relational warrant (`inferential_force`)—never the node's modal commitment $M_{\text{mod}}(\phi_a)$—eliminating $M_{\text{mod}}^2$ double-penalization. `TheoryRelation` and `TheoryRelationArtifact` carry no `modal_strength` field.

3. **Layer 3 — Empirical & Structural Tenability (Model-Theoretic Constraints, Post-Processing / [ADR-0015](0015-theoretical-enrichment-and-tenability-evaluation.md))**:
   $$TS_{\text{local}}(a) \in [0, 1], \qquad TS_{\text{edge}}(e) \in [0, 1]$$
   Represents approximate empirical satisfaction ($M_p \cap I$ under uniform-space blurs $\mathfrak{A}$ and structuralist empirical consequence $\operatorname{Cn}_{\text{str}}(K)$) and intertheoretical constraint satisfaction ($GC, GL$), stored as `local_tenability` on `TheoryAtom` and `edge_tenability` on `TheoryRelation`.

4. **Layer 4 — Dialectical Equilibrium (Global Fixed-Point, Phase 6 & Theoretical Enrichment / [ADR-0011 Addendum 2](0011-declarative-graph-metrics-and-qbaf-semantics.md))**:
   $$s^*(a) = \tilde{\beta}(a) + \bigl(1 - \tilde{\beta}(a)\bigr)\,h(E_a) - \tilde{\beta}(a)\,h(-E_a), \qquad E_a = S^+(a) - S^-(a), \qquad h(x) = \frac{\max(x, 0)^2}{1 + \max(x, 0)^2}$$
   where empirical tenability modulates the effective base prior:
   $$\tilde{\beta}(a) = \beta(a) \cdot TS_{\text{local}}(a)$$
   and $S^+(a), S^-(a)$ aggregate supporting and attacking warrants via the configured conjunctive t-norm ($\prod$ or $\min$). Evaluated in closed form $O(|V| + |E|)$ on DAGs and via adaptive ODE integration (`RK45`/`Radau`) on cyclic graphs in `WeightedQuadraticEnergySolver`. Stored on `TheoryAtom` as `equilibrium_strength` (`plausibility`), accompanied by bounded Keynes–Gärdenfors controversy volatility $\mathcal{V}(a) = \mathrm{Wt}(a) \cdot \mathrm{Controv}(a) \in [0, 1]$ (`controversy_volatility`).

### 2. Closed-Loop Coupling Between `TheoreticalEnrichmentRunner` and D-QBAF

- `TheoryNetProjector` modulates each atom's base prior by `local_tenability` ($\tilde{\beta}(a) = \beta(a) \cdot TS_{\text{local}}(a)$) and each warrant's weight by `edge_tenability` ($W_{w_k} \cdot TS_{\text{edge}}(w_k)$).
- After computing $TS_{\text{local}}$ and $TS_{\text{edge}}$, `TheoreticalEnrichmentRunner` runs an incremental D-QBAF re-convergence pass via `TheoryNetProjector`, updating `equilibrium_strength`, `plausibility`, and `controversy_volatility` on `TheoryAtom` artifacts and graph projections so empirically untenable hypotheses ($TS_{\text{local}} < 0.5$) directly propagate into dialectical acceptability $s^*(a)$.

### 3. Architectural Boundary with ADR-0007

- **Retained from [ADR-0007](0007-tf-structural-correspondence.md)**: Construction-time $\kappa$-Structural Correspondence ($\mathrm{ov}_{\text{str}}$, `structural_correspondence` on `TheoryRelation`) and the structuralist statement-scope taxonomy (`ScopeType`).
- **Superseded in [ADR-0007](0007-tf-structural-correspondence.md)**: Unweighted `TF(a)` count ratios are superseded by Continuous D-QBAF ([ADR-0011 Addendum 2](0011-declarative-graph-metrics-and-qbaf-semantics.md)), the Propositional Modal Strength Resolver ([ADR-0020](0020-propositional-modal-strength-resolver.md)), and this metamodel.

---

## Consequences

- **Zero $M_{\text{mod}}^2$ Double-Penalization**: Node commitment $M_{\text{mod}}(\phi_a)$ is confined to `TheoryAtom` while inferences carry `inferential_force` $I_{w_k}$.
- **Bidirectional Empirical-Dialectical Coherence**: Empirically falsified hypotheses ($TS_{\text{local}} < 0.5$) cannot retain artificially high D-QBAF equilibrium acceptability $s^*(a)$ solely from high rhetorical certainty.
- **Lossless Artifact Hydration**: `TheoryAtomCodec`, `TheoryRelationCodec`, and `Phase4ArtifactsView` preserve all four layers of the Stratified Epistemic State Tuple across checkpointing and DAG branch reuse.

---

## Related

- [ADR-0007: TF Structural Correspondence](0007-tf-structural-correspondence.md)
- [ADR-0011: Declarative Graph Metrics & D-QBAF](0011-declarative-graph-metrics-and-qbaf-semantics.md)
- [ADR-0015: Theoretical Enrichment & Tenability](0015-theoretical-enrichment-and-tenability-evaluation.md)
- [ADR-0020: Propositional Modal Strength Resolver](0020-propositional-modal-strength-resolver.md)
- [ADR-0023: Intensional & Perspectival Scoping and Conception Stratification](0023-intensional-perspectival-scoping-and-conception-stratification.md)
- [ADR-0024: Closed-Loop Hermeneutic Refinement](0024-closed-loop-hermeneutic-refinement.md) — Uses Layer 3/4 tenability ($TS_{\text{local}}$, $TS_{\text{edge}}$) and D-QBAF telemetry ($\tau^*$, $\mathcal{V}$) to emit `EpistemicDeficitArtifact` signals driving bounded top-down refinement.
