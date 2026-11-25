# [0011] Declarative Graph Metrics Framework, Async Lifecycles, and Gradual Strength Semantics

Status: Accepted (2026-09-07)

## Context

Theory graphs and epistemic argument structures (e.g., TheoryNet, Quantitative Bipolar Argumentation Frameworks / QBAF) require both local and global quantitative analysis to be interpretable by domain researchers. 

Previously, graph analytics in Episteme Studio were limited to synchronous node overlays (via `OverlayService`), with several key limitations:
1. **Lack of Causal Edge Explanations**: Argumentative influence flows along directed relations (supports, attacks, rebuttals). Visualizing metric values solely on nodes fails to convey *why* a claim has low or high epistemic strength, which edges transmitted support or attack, and their proportional contributions.
2. **Execution Latency Discrepancy & UX Blocking**: Local metric calculations on small neighborhoods execute in <10ms, while global structural metrics (such as PageRank across thousands of live Neo4j nodes) can take multiple seconds. Blocking the UI or timing out HTTP connections degrades the interactive research experience.
3. **Canvas State Collisions & Race Conditions**: Overwriting node and edge states on the AntV G6 canvas would wipe user selection (`selected`) and hover states. Furthermore, switching focus nodes rapidly or modifying parameter forms while background calculations were in flight could lead to stale asynchronous results overwriting newer queries.
4. **Accessibility (WCAG 2.1 AA Compliance)**: Relying strictly on red/green node colors to denote attack and support paths makes the graph unusable for users with color vision deficiencies.
5. **Infrastructure Heterogeneity**: Neo4j Graph Data Science (GDS) library is not guaranteed to be installed on every deployment, risking query failures when running heavy graph algorithms.

## Decision

We implement an end-to-end declarative metrics architecture across `Episteme_studio` and `packages/episteme-studio/frontend`:

### 1. Declarative Metric Registry & Parameter Schemas
- Defined `MetricDescriptor` with metadata, scope (`global` vs `single_node`), execution engine (`gds`, `python`), availability flags, and JSON Schema definitions for parameters.
- Exposed `GET /api/metrics/definitions` dynamically querying live engine availability (e.g., probing Neo4j for GDS procedures `gds.pageRank.stream`).

### 2. Hybrid Async Execution Lifecycle with Stale Protection
- `POST /api/metric-executions`: Fast-path heuristic executes calculations within a 250ms deadline.
  - Sub-250ms calculations return `200 OK` with the completed `MetricResult` payload immediately.
  - Computations exceeding 250ms return `202 Accepted` with an `execution_id` and polling endpoint `/api/metric-executions/{id}`.
  - Long-running tasks support cooperative cancellation via `DELETE /api/metric-executions/{id}`.
- Client-side Zustand store tracks monotonic `request_sequence` IDs and active `AbortController` handles. Stale responses from previous runs or focus nodes are discarded when newer requests resolve.

### 3. Local Gradual Strength Semantics (QBAF)
- Implemented bounded iterative semantics (`compute_local_gradual_strength`) over subgraphs upstream of a focus node.
- Cycles are prevented from locking by bounded convergence iterations with tolerance $\epsilon$.
- Pathway polarity analysis traces upstream influences and categorizes nodes and edges into `support`, `attack`, or `support + attack` (dual-influence).
- Computes marginal ablation impact $\Delta(u) = \rho(focus) - \rho_{-u}(focus)$ to measure the true causal contribution of each upstream claim.
- Returns detailed `affected_edges` and `affected_nodes` dictionaries.

### 4. Ephemeral Neo4j GDS Projections with Resilient Fallback
- `Neo4jReader.run_gds_pagerank` generates ephemeral in-memory graph projections with unique UUIDs (`pr-proj-<uuid>`).
- Guaranteed projection cleanup is enforced via Python `try ... finally` calling `gds.graph.drop(..., false)`.
- When GDS is unavailable or errors, execution seamlessly falls back to Python in-memory `igraph` PageRank, decorating the result with transparent provenance warnings.

### 5. Canvas Composite States and WCAG Multi-Channel Styling
- AntV G6 canvas utilizes composable states (`metric-focus`, `metric-affected`, `metric-role-support`, `metric-role-attack`, `metric-role-dual`, `metric-dimmed`) without mutating or clearing user `selected` states.
- Multi-channel visual differentiation:
  - Node & Edge badges: `[▲]` for Support, `[▼]` for Attack, `[▲/▼]` for Dual.
  - Stroke patterns: solid for Support, dashed (`[4, 4]`) for Attack, dash-dotted for Dual.
  - Focus node: cyan double-halo focus ring (`#06b6d4`).
  - Unaffected elements: dimmed with 0.6 opacity to maintain WCAG contrast and readability.
- "Clear Metric / Reset View" removes metric visual states while preserving node positions, camera zoom, and loaded subgraphs.

### 6. Dual Context Menus & Edge Inspector Modal
- Added context menu listeners on canvas:
  - Right-clicking nodes opens `NodeContextMenu.tsx` with options to inspect, run local metrics, expand neighbors, or focus camera.
  - Right-clicking edges opens `EdgeContextMenu.tsx` with options to inspect relationship properties, polarity provenance, and highlight source/target claims.
- `EdgeInspectorModal.tsx` provides deep causal inspection of weights $\phi$, epistemic polarities, and contribution shares.

## Alternatives Considered

- **Synchronous-only execution**: Rejected because global analytics on large knowledge graphs cause browser timeouts and freeze user interactions.
- **WebSocket/SSE-only transport for metrics**: Rejected to preserve lightweight stateless REST semantics matching the existing API architecture, while using short polling only for jobs exceeding 250ms.
- **Node-only metric visual explanations**: Rejected because epistemic argument graphs derive meaning from relational inferences; without edge contribution annotations, users cannot verify the reasoning path.

## Consequences

- Researchers can explore quantitative argument metrics with full causal path transparency.
- Graph analytics scale gracefully between sub-millisecond local queries and distributed GDS runs.
- Canvas state management is robust against async race conditions and accessible under WCAG guidelines.

## Related

- `../../packages/episteme-studio/docs/CONTRACT.md` — API contracts for metrics and execution endpoints
- `packages/episteme-studio/src/Episteme_studio/domain/metrics.py` — Domain models for metrics
- `packages/episteme-studio/src/Episteme_studio/services/metric_service.py` — Metric registry and lifecycle manager
- `packages/episteme-studio/src/Episteme_studio/adapters/metrics_adapter.py` — QBAF gradual strength semantics engine
- `packages/episteme-studio/frontend/src/panels/MetricsDrawer.tsx` — Dynamic schema metrics drawer

---

## Addendum (2026-10-02): Calibrated System 1 Priors and Decoupled Modal Edge Weighting

### Context & Theoretical Rationale
In initial iterations of the pipeline and metrics, edge weights in Quantitative Bipolar Argumentation Frameworks (QBAF) were often either uniform ($w = 1.0$) or set to uncalibrated heuristic scores (e.g., verbalized generative LLM confidences). This caused two primary failure modes:
1. **Mathematical Distortion**: Uncalibrated inputs distorted gradual semantics solvers (Eulerian, quadratic energy, or categorization models) and degraded epistemic coherence calculations.
2. **Epistemic Conflation**: Extraction confidence ($P(\text{correct})$ or stance softmax probability) was conflated with propositional modal strength ($M(\phi) \in [0, 1]$). If an author posits a tentative hypothesis ("It is conceivable that space is an illusion"), a high extraction confidence ($P=0.99$) must not elevate a contingent conjecture ($M=0.30$) into an unassailable axiom ($w=0.99$).

### Decision Amendment
We extend the QBAF and TheoryNet architecture to systematically ingest and propagate calibrated System 1 priors:

1. **Decoupled Mathematical Edge Weighting**:
$$w = M(\text{modal\_strength}) \times P(\text{stance})$$
   where $M(\text{modal\_strength}) \in [0, 1]$ encodes philosophical modality (1.0 for deductive necessity/axioms, 0.75 for assertoric claims, 0.30 for tentative conjectures) and $P(\text{stance})$ is the calibrated softmax probability from System 1 Jev.
2. **Admissibility Gating**:
   Empirical expected accuracy ($\text{empirical\_accuracy}$ / `act_probability`) acts as an admissibility gate $\tau_{\text{admissibility}}$. Relations failing the threshold are pruned or marked with zero epistemic tenability (`tenable = False`), protecting gradual equilibrium calculations from uncalibrated noise.
3. **Graph Projection & Persistence**:
   Cypher projection templates in Phase 6 persist `class_probability`, `empirical_accuracy`, `modal_strength`, `effective_weight`, `weight_support`, and `weight_attack` onto `:SUPPORTS` and `:ATTACKS` relationships in the Neo4j Projection Graph.
4. **Sovereign Epistemetrics QBAF Solvers**:
   Gradual semantics solvers are formalized in `epistemetrics.epistemic.qbaf` (`QBAFGradualSemanticsSolver`) supporting Quadratic Energy, Euler, Categorizer, and Linear models, alongside normalization mode comparisons (`compare_qbaf_weight_modes`) between `CALIBRATED_MODAL` and `UNWEIGHTED_BINARY`.
5. **Evaluation Metric Scaffolding**:
   Expected Calibration Error (ECE), Maximum Calibration Error (MCE), and Brier Score are integrated into `CalibrationScorer` and evaluation strategies to continuously audit extraction calibration.

### Consequences
- Gradual semantics solvers converge deterministically without numerical instability under continuous, calibrated weights.
- Dialectical justification degrees $\tau(a)$ reflect both evidentiary empirical accuracy and propositional modality.
- Research benchmarks can isolate the exact contribution of calibrated modal weights vs unweighted binary graphs.

---

## Addendum 2 (2026-10-06): Decoupled D-QBAF Ontologies, Adaptive Continuous Solvers, and Step-Size Dynamics

### Architectural Requirements
Evaluating Layer 3 Dialectical Argument Graphs ($\mathcal{D}$) requires four structural guarantees:
1. **Ontological Separation of Uncertainty Dimensions**: Node-level descriptive authorial commitment $M_{\text{mod}}(\phi_a)$, relational inferential warrant force $I_{w_k}$, and perceptual extraction confidence $(P_{\text{stance}}, C_{\text{cal}})$ must remain decoupled to prevent $M_{\text{mod}}^2$ double-penalization.
2. **Topological Continuity**: Using a single continuous Quadratic Energy formulation across both DAGs and cyclic subgraphs prevents semantic discontinuities when adding a cycle-completing edge.
3. **Adaptive Step-Size Control on High-Degree Hubs**: In the Quadratic Energy ODE $\dot{\mathbf{s}} = \mathbf{f}(\mathbf{s})$, Gershgorin's circle theorem bounds the Jacobian spectral radius as $\rho(J) \le 1 + c \cdot \text{in-deg}_{\text{w}}(i)$ with $c = 3\sqrt{3}/8 \approx 0.65$ (linear in weighted in-degree). Any fixed explicit step $\delta$ violates linear stability on dense hubs where $\delta \cdot \rho(J)$ exceeds the method's stability region; adaptive step-size control eliminates manual step-size tuning and prevents explicit Euler oscillation.
4. **Stationary Termination & Explicit Non-Convergence Reporting**: Cyclic integration terminates as soon as $\|\dot{\mathbf{s}}\|_\infty < \text{atol}$ via a root-finding event and explicitly reports `converged = False` with final residual $\|\dot{\mathbf{s}}(t_{\max})\|_\infty$ if $t_{\max}$ is reached prior to equilibrium.

### Decision Amendments

1. **Ontological Stratification**:
   - The Layer 3 dialectical formalism is standardized as a **Decoupled Quantitative Bipolar Argumentation Framework (D-QBAF)**, strictly separated from the Layer 4 Structuralist Theory-Net ($\mathcal{N} = \langle N, \sigma \rangle$).
   - Three orthogonal uncertainty dimensions are stored separately:
     - **Authorial Propositional Commitment ($M_{\text{mod}}(\phi_a) \in [0, 1]$)** on `TheoryAtom`, decoupled from the configurable D-QBAF base prior $\beta(a)$ (`BasePriorPolicy`: `descriptive_authorial`, `normative_uniform`, or `normative_data_priority`) and tenability-modulated effective prior $\tilde{\beta}(a) = \beta(a) \cdot TS_{\text{local}}(a)$.
     - **Inferential Warrant Force ($I_{w_k} \in [0, 1]$)** on `TheoryRelation` / `:TheoryInference` warrants.
     - **Perception Calibration ($P_{\text{stance}}, C_{\text{cal}} \in [0, 1]$)** on `TheoryRelation`.
2. **Unified Continuous Quadratic Energy Semantics**:
   - Quadratic Energy semantics is applied uniformly across all topologies.
   - **Acyclic Graphs (DAGs)**: Evaluated in exact closed form in $O(|V| + |E|)$ along a single topological pass, avoiding numerical ODE integration on DAGs.
   - **Cyclic Graphs**: Evaluated via adaptive ODE integration (`WeightedQuadraticEnergySolver` using `scipy.integrate.solve_ivp` `RK45` with implicit `Radau` fallback on stiff systems) equipped with terminal root-finding stationary event detection ($\|\dot{\mathbf{s}}\|_\infty < \text{atol}$, `terminal=True, direction=-1`). When `t_max` is reached with residual above tolerance, `converged=False` and `final_delta` are returned explicitly.
3. **Harmonized Bivariate Admissibility Gating**:
   - **Mode 1 (`hard`)**: Enforces database-level pruning in Neo4j GDS projections via Cypher filtering (`WHERE r.perception_stance_prob >= $tau_p AND r.calibrated_confidence >= $tau_c`), delivering strictly qualified subgraphs.
   - **Mode 2 (`soft`)**: Passes candidate subgraphs without Cypher `WHERE` filtering and applies smooth sigmoidal relaxation $\mathcal{F}_{\text{soft}}(r) = \sigma(k(P - \tau_P)) \cdot \sigma(k(C - \tau_C))$ ($k = 20$) in `epistemetrics`. Mode 2 trades strict threshold preservation for smooth parameter differentiability: at exact boundary values $P = \tau_P$ and $C = \tau_C$, $\sigma(0) = 0.5$ attenuates an edge to $0.25$ of its nominal warrant force.
4. **Keynes–Gärdenfors Evidential Weight & Controversy Telemetry**:
   - `QBAFSolverResult` tracks gross evidentiary weight $S^+(a_i) + S^-(a_i)$ and bounded controversy volatility:
     $$\mathcal{V}(a_i) = \mathrm{Wt}(a_i) \cdot \mathrm{Controv}(a_i) = \frac{S^+(a_i) + S^-(a_i)}{1 + S^+(a_i) + S^-(a_i)} \cdot \left(1 - \frac{|S^+(a_i) - S^-(a_i)|}{S^+(a_i) + S^-(a_i)}\right) \in [0, 1]$$
     (defined as $0$ when $S^+(a_i) + S^-(a_i) = 0$), cleanly distinguishing heavily contested claims from unevidenced or uncontested claims independent of $\beta(a_i)$.
5. **Explicit Scoping Decision**:
   - Analytical right inverses are excluded from solver scope in favor of marginal graph ablation ($\Delta(u) = s^*(\text{focus}) - s^*_{-u}(\text{focus})$).

### Consequences
- Eliminates $M_{\text{mod}}^2$ double-penalization while maintaining explicit Toulmin warrant accounting.
- Guarantees $O(|V| + |E|)$ exact evaluation for acyclic graphs and adaptive, early-halting ODE relaxation with explicit non-convergence reporting for cyclic graphs.
- Aligns database projections, `epistemetrics` solvers, and Studio telemetry under one mathematical specification.

---

## Addendum 3 (2026-10-31): Active Inter-Phase Epistemic Quality Gates (`ISSUE-058`)

### Context
While `epistemetrics` provides rich post-construction theory-graph evaluation, structural or calibration pathologies arising mid-run (such as Phase 2 ontological collapse, Phase 3b/5 giant-component percolation, or Phase 3/4 conformal OOD spikes) previously went undetected until after all downstream LLM phases completed.

### Decision Amendment
We complement passive post-construction analytics with active inter-phase `EpistemicQualityGate` circuit breakers evaluated by `ArtifactExecutionEngine` on the `ArtifactCollection` emitted by each phase in `WorkflowDAG`:
- **`OntologyEntropyGate` (Post-Phase 2)**: Enforces Shannon entropy $H(\text{entity\_types}) \ge H_{\min}$, bounds single-type dominance ratio, and verifies non-zero entity density on non-empty chunks.
- **`PercolationQualityGate` (Post-Phase 3b & Phase 5)**: Verifies that the largest merged equivalence class does not exceed $\rho_{\max} \cdot |E|$, preventing giant-component collapse prior to QBAF / TheoryNet synthesis.
- **`ConformalCalibrationGate` (Post-Phase 3 & Phase 4)**: Monitors empirical rates of empty ($|C(X)| = 0$) and ambiguous ($|C(X)| > 1$) conformal prediction sets, emitting `QualityGateWarning` or raising `QualityGateViolationError` before corrupted artifacts are persisted or projected.

---

## Addendum 4 (2026-11-15): Bipartite Inference Hypergraph, Conjunctive T-Norms & Warrant Dynamics (`ISSUE-055`)

### Context
Binary atom-to-atom edges cannot faithfully represent linked/conjunctive inferences (e.g., Duhem–Quine derivation $\text{Law} \land \text{BoundaryCondition} \implies \text{Observation}$, where falsifying the boundary condition must eliminate the derivation's support) or meta-level warrant modifiers (Pollockian undercutters attacking the inference rule rather than rebutting the conclusion below its prior $\tau_0$, and Toulmin backing strengthening a warrant).

### Decision Amendment
1. **Domain & Artifact Hypergraph Support**:
   - `TheoryRelation` (`TheoryInference` alias), `TheoryRelationArtifact` (`TheoryInferenceArtifact` alias), and `epistemetrics.TheoryEdge` now carry optional `id`, `premise_ids: tuple[str, ...]`, and `undercuts_relation_id: str | None`, preserving lossless codec round-trips (`TheoryRelationCodec`) and Phase 5 canonical ID remapping (`_resolve_l3_atoms_and_relations`).
2. **Selective Bipartite `:TheoryInference` Projection (`ArtifactGraphProjector`)**:
   - Inferences with $|\text{Prem}| > 1$ or targeted by an undercutter (`undercuts_relation_id`) or backing relation are materialized as intermediate `:TheoryInference` nodes connected via `HAS_PREMISE`, `CONCLUDES`, `UNDERCUTS`, and `BACKS` edges in a deterministic two-pass `ProjectionBatch.flush()`.
   - Untargeted unary inferences remain lightweight direct pairwise edges, keeping graph projection cost minimal.
3. **Conjunctive T-Norms & Warrant State ODEs (`epistemetrics`)**:
   - `WeightedQuadraticEnergySolver` and `QBAFGradualSemanticsSolver` accept `t_norm: Literal["product", "godel"] = "product"` (configured pipeline-wide via `Phase6Config.conjunctive_t_norm`), aggregating conjunctive premises via Product ($\prod$) or Gödel ($\min$) t-norms. Under `t_norm = "product"`, the coupled ODE vector field is $C^1$; under `t_norm = "godel"`, it is globally Lipschitz continuous (non-$C^1$ across premise-tie hyperplanes $s_j = s_{j'}$), preserving Picard–Lindelöf uniqueness while requiring adaptive step control.
   - Reified warrants are modeled by `HyperedgeSpec` with dynamic warrant state $s(w_k, t)$ modulated by Toulmin backing and Pollockian undercutters in both topological closed-form DAG evaluation and coupled augmented ODE integration (`s_atoms` + `s_warrants`), reported in `QBAFSolverResult.warrant_states` and solver telemetry without polluting atom degree dictionaries.
   - Untargeted 1-premise `HyperedgeSpec` instances reduce numerically identically to pairwise weighted edges.
