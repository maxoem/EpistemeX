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

## Addendum 2 (2026-10-06): Decoupled QBAF Ontologies, Adaptive Continuous Solvers, and Corrected Step-Size Dynamics

### Context & Structural Refactoring
Following rigorous theoretical and numerical evaluation of ticket ISSUE-041 and its formal action plan, several critical defects in earlier gradual semantics models and graph projection pipelines were identified and resolved:
1. **Conflation of Ontological Layers**: Earlier formulations ($w = M \times P$) conflated node-level propositional modality with relational extraction confidence, creating a pseudo-decoupling that quadratically double-penalized tentative premises ($M^2$).
2. **DF-QuAD vs. Quadratic Energy Discontinuity**: Routing DAGs to DF-QuAD and cyclic graphs to Quadratic Energy created an unacceptable semantic discontinuity where adding a single cycle-completing edge shifted equilibrium scores across unrelated acyclic branches.
3. **Numerical Stiffness in High-Degree Networks**: Fixed-step integration ($\delta = 0.01$) on Quadratic Energy models violates stability bounds on dense citation hubs ($\text{indegree} \gg 50$). Potyka's (2018) assertion that bounded derivatives $|\dot{s}_j| \le 1$ imply constant step stability is refuted via Gershgorin Circle bounds: the Jacobian spectral radius grows linearly with in-degree ($\rho(J) \le 1 + 0.65 \cdot \text{indegree}(i) \cdot \bar{W}$), necessitating adaptive step sizes.
4. **Redundant Iterations past Equilibrium**: Integrating cyclic networks out to $t_{\max} = 50.0$ without stationary root-finding performed hundreds of redundant Jacobian evaluations on networks that stabilize by $t \approx 5.5$–$7.0$.

### Decision Amendments

1. **Formal Renaming & Ontological Stratification**:
   - The dialectical theory graph layer is formally standardized as **Quantitative Bipolar Argumentation Frameworks (QBAF)**.
   - Decoupled into three distinct physical layers:
     - **Propositional Modality ($M(\phi) \in [0, 1]$)** on `TheoryAtom` as prior plausibility $\tau_0 \equiv w(a)$.
     - **Inferential Warrant Force ($I_{j \to i} \in [0, 1]$)** on `TheoryRelation` as Toulminian inferential validity.
     - **Perception Calibration ($P(\text{stance}), C \in [0, 1]$)** on `TheoryRelation` as extraction confidence.
2. **Unified Continuous Quadratic Energy Semantics**:
   - Eliminated DF-QuAD dual routing; standardized on Quadratic Energy semantics across all topologies.
   - **Acyclic Graphs (DAGs)**: Evaluated in closed form in $O(|V| + |E|)$ along a single topological pass (Proposition 5), eliminating numerical ODE integration on DAGs.
   - **Cyclic Graphs**: Evaluated via continuous adaptive ODE integration (`WeightedQuadraticEnergySolver` using `scipy.integrate.solve_ivp` RK45 with implicit Radau fallback) equipped with terminal root-finding stationary event detection ($\|\dot{\mathbf{s}}\|_\infty < \text{atol}$ with `terminal=True, direction=-1`), halting integration when equilibrium is reached.
3. **Correction to Potyka (2018) Stability Claim**:
   - Proved that the Jacobian spectral radius $\rho(J)$ grows with in-degree, refuting the claim that fixed step size $\delta=0.01$ is unconditionally stable. Adaptive step control is strictly required.
4. **Harmonized Bivariate Admissibility Gating**:
   - **Mode 1 (`hard`)**: Enforces database-level pruning in Neo4j GDS projections via Cypher filtering (`WHERE r.stance_probability >= $tau_p AND r.model_confidence >= $tau_c`), delivering strictly qualified subgraphs.
   - **Mode 2 (`soft`)**: Passes candidate subgraphs without Cypher `WHERE` filtering and applies continuous sigmoidal relaxation $\mathcal{F}_{\text{soft}}(r) = \sigma(20(P - \tau_P)) \cdot \sigma(20(C - \tau_C))$ in `epistemetrics`.
5. **Keynes-Gärdenfors Orthogonal Telemetry**:
   - `QBAFSolverResult` tracks gross epistemic weight of evidence $E_{\text{total}}$ and controversy volatility index $\mathcal{V}$, enabling Episteme Studio to differentiate heavily contested claims from unevidenced claims.
6. **Explicit Scoping Decision**:
   - Analytical right inverses are formally excluded from solver scope in favor of marginal graph ablation ($\Delta(u) = \rho(\text{focus}) - \rho_{-u}(\text{focus})$).

### Consequences
- Eliminates double-penalization of tentative premises while maintaining rigorous Toulmin warrant accounting.
- Guarantees $O(|V| + |E|)$ execution for acyclic theory graphs while ensuring numerically stable, early-halting ODE relaxation for cyclic structures.
- Provides complete mathematical harmony between database projections, runtime solvers, and visualization telemetry.
