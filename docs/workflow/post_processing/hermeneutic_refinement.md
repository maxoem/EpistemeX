# Deficit Graph Analysis & Closed-Loop Hermeneutic Refinement

## Overview

The **Closed-Loop Hermeneutic Refinement** subsystem (`episteme_pipeline/refinement/`) implements bounded top-down feedback ($\text{L4/L3} \to \text{L2/L1}$) over finalized TheoryNet and Theoretical Enrichment graphs ([ADR 0024](../../adr/0024-closed-loop-hermeneutic-refinement.md)).

A critical architectural invariant of this subsystem is the **strict separation between deterministic graph diagnosis and learned System 1 / System 2 repair**:

| Layer / Stage | Modules | Mechanism Used | LLMs / Embeddings / `DecisionEngine`? |
|:---|:---|:---|:---|
| **1. Upstream Scoring** | Phases 2–6 & Theoretical Enrichment | Produces conceptions, relations, `controversy_volatility`, `TS_local`, `TS_edge`, and `tau_star` | Yes (upstream phases) |
| **2. Deficit Graph Analysis** | `detector.py`, `_detector_analysis.py`, `_sub_detectors.py`, `compute_z1_grounding` | **100% deterministic** BFS reachability, `epistemetrics` centrality & Louvain clustering, single-source `SchemaConfig` partition/polarity checks, and arithmetic threshold rules | **No** — zero LLMs, zero embeddings, zero `DecisionEngine`, zero NNs/GNNs, zero fuzzy solvers |
| **3. Triage & Localized Repair** | `_shared.py`, `concept_splitter.py`, `premise_recovery.py`, `axiom_grounder.py` | Evaluates System 1 conformal/calibratable gates (`DecisionEngine`), checks `EmbeddingModel` divergence / dense retrieval, and dispatches bounded System 2 recovery | **Yes** — System 1 gating + embeddings + localized LLM extractors |
| **4. Overlay & Re-Convergence** | `coordinator.py`, `artifacts/refinement_overlay.py`, `artifacts/invalidate.py` | Applies identity-keyed deltas, retires split parents/mentions, preserves pass-aware DAG lineage, and slices connected D-QBAF components | Deterministic (`TheoryNetProjector` / optional local enrichment re-scoring) |

---

## Execution Lifecycle & Invocation Entry Points

```mermaid
flowchart LR
    FWD["Forward WorkflowDAG Complete<br/>(Phases 1–6 + Optional Enrichment)"] --> GATE{"max_refinement_cycles > 0?"}
    GATE -->|No (default 0)| END_FF["Zero Fingerprint Drift<br/>Return Forward Collection"]
    GATE -->|Yes| INIT["ArtifactExecutionEngine._run_refinement_stage()<br/>ClosedLoopRefinementCoordinator.refine()"]
    INIT --> P1["Pass 1: EpistemicDeficitArtifactsView<br/>+ detector.detect_deficits(pass=0)"]
    P1 --> PREP["analyze_detector_state(state, schema)<br/>Z_1 BFS, PageRank, Betweenness, Louvain"]
    PREP --> SUB["Run 3 Sub-Detectors<br/>(EnthymemeGap, PolysemyCollision, UngroundedAxiom)"]
    SUB --> RANK["Deduplicate, Sort (-severity, kind, id)<br/>Cap at max_deficits_per_cycle"]
    RANK --> ACT{"Any actionable<br/>unhandled deficits?"}
    ACT -->|No| DONE["Converged / Early Exit"]
    ACT -->|Yes| HANDLERS["System 1 DecisionEngine Triage<br/>+ Localized L1/L2/L3 Handlers"]
    HANDLERS --> OVERLAY["Refresh Working Overlay & Retire Split Parents<br/>Slice Connected Component -> TheoryNetProjector"]
    OVERLAY --> NEXT["End-of-Pass detect_deficits(pass=r)<br/>Seed pending_detected for Pass r+1"]
    NEXT -->|Not converged & r < R_max| ACT
    NEXT -->|Converged or r == R_max| DONE
```

### Invocation Notes

1. **Primary Runtime Loop (`ClosedLoopRefinementCoordinator.refine`)**:
   - Triggered by `ArtifactExecutionEngine._run_refinement_stage()` after all forward `WorkflowDAG` nodes complete whenever `config.refinement.max_refinement_cycles > 0`.
   - On Pass 1 (`pending_detected is None`), calls `self.detector.detect_deficits(state, refinement_pass=0, ...)` directly over the live cumulative state (including Phase 6 D-QBAF equilibrium scores and Theoretical Enrichment tenability scores).
   - Within a pass, after each non-empty deficit `RefinementDelta`, updates the working `ArtifactCollection` and `EpistemicStateView` before handling subsequent deficits. At pass tail, slices affected connected components via `slice_phase4_component_view`, runs `TheoryNetProjector` (and optional localized `TheoreticalEnrichmentRunner` re-scoring), then runs `detect_deficits(post_state, refinement_pass=pass_idx, ...)` to test convergence and seed `pending_detected` for the next pass.
2. **Optional Forward Emission Hooks (`Phase6Runner`, `TheoreticalEnrichmentRunner`)**:
   - Both runners accept an optional `deficit_detector: EpistemicDeficitDetector | None` (normalized via `ensure_deficit_detector`) to emit `EpistemicDeficitArtifact` envelopes directly during forward execution.
   - Note that `PipelineFactory.build_phases` currently wires `components.deficit_detector` (`TheoryNetDeficitDetector`) into `ClosedLoopRefinementCoordinator` rather than constructing forward runners with `deficit_detector`.

---

## Stage 1: Deficit Graph Analysis (`_detector_analysis.py`)

Before any sub-detector evaluates rules, [`analyze_detector_state`](../../reference/refinement.md) builds an immutable `DetectorStateAnalysis` snapshot over `EpistemicStateView` (preferring `canonical_theory_atoms` and `canonical_theory_relations` when populated):

1. **Single-Source Schema Partitions & $Z_1$ Empirical Reachability (`compute_z1_grounding`)**:
   - Maps each atom's `component_type` via `SchemaConfig.resolve_component_partition(...)` into Partition `"A"` (theoretical hypotheses/claims) or Partition `"B"` (empirical observations/data).
   - Evaluates admissible, non-undercut relations (`rel.is_admissible`, `rel.active_weight > 0.0`, `rel.undercuts_relation_id is None`) using `SchemaConfig.resolve_edge_polarity(...)`:
     - Counts `in_support_degree[target_id]` for every positive-polarity hyperedge (`pol > 0`) with at least one premise distinct from `target_id`.
     - Seeds multi-source BFS on every `"A"` atom directly connected to a `"B"` atom across non-negative relations (`pol >= 0`) and propagates symmetrically across admissible `"A"`–`"A"` links to determine `z1_grounded`.
2. **Weighted Directed TheoryNet Projection (`build_theory_nx_graph`)**:
   - Builds a NetworkX `DiGraph` containing all active atoms and admissible, non-undercut edges with positive edge weights:
     $$w(u \to v) = \max\bigl(10^{-6},\; |\text{active\_weight}| \text{ if } \text{active\_weight} > 0 \text{ else } \text{confidence} \text{ or } 1.0\bigr)$$
   - Retains the maximum weight when multiple parallel premise-to-target links share `(u, v)`.
3. **`epistemetrics` Topological Metrics (`compute_centralities`, `compute_louvain_communities`)**:
   - Runs `epistemetrics.betweenness_centrality(graph, prefer_neo4j=False)` (falls back to `0.0` on `AlgorithmError`).
   - Runs `epistemetrics.page_rank(graph, prefer_neo4j=False, weight_property="weight")` (falls back to `btw_scores` if non-zero, otherwise uniform $1 / |V|$ on `AlgorithmError`).
   - Runs weighted `epistemetrics.louvain_communities(graph, prefer_neo4j=False, seed=42, weight_property="weight")` (falls back to singleton sorted node indices on `AlgorithmError` or zero edges).
4. **Incident Degree, Enrichment Maps, Cluster Evidence, & Chunk Neighbors**:
   - Computes `incident_degree` across all `relations` (total incident endpoint count per atom).
   - Indexes `TheoreticalEnrichmentArtifact`s into `edge_tenability_map`, `equilibrium_map`, `atom_to_enrichments` (matching `claimant_atom_ids` first, falling back to `cluster-<source_chunk_id>`).
   - Counts empirical `"B"` atoms (`cluster_b_counts`) and collects lowercase `Measurement.dimension` tokens (`cluster_dimensions`) per `source_chunk_id` and `cluster-<source_chunk_id>`.
   - Builds intra-document chunk adjacency (`sequence_index ± 1`, sorted deterministically) for 1-hop `collect_target_chunks` expansion.

---

## Stage 2: Sub-Detector Logic & Severity Formulas (`_sub_detectors.py`)

[`TheoryNetDeficitDetector`](../../reference/refinement.md) invokes three single-responsibility sub-detectors and normalizes every severity into $[0.0, 1.0]$.

### 1. `EnthymemeGapSubDetector` (`ENTHYMEME_GAP`)

Detects central theoretical `"A"`-partition claims lacking incoming warrant or an empirical $Z_1$ derivation chain.

- **Scope & Filters**:
  - Scans `"A"` atoms (`atom.id in analysis.a_atoms`), **skipping** `intensional_mode == "suppositional"` (ADR-0023 suppositional/reductio assumptions are intentionally isolated from factual support).
  - Requires `pr_scores[atom.id] >= cfg.enthymeme_min_centrality` (default `0.0`).
  - Skips atoms that already satisfy **both** `in_support_degree > 0` and `atom.id in analysis.z1_grounded`.
  - **Disambiguation Guard against `UNGROUNDED_AXIOM`**: If an `"A"` atom has `incident_degree == 0` **and** `cluster_b_counts[atom.source_chunk_id] == 0`, it is skipped here so `UngroundedAxiomSubDetector` handles isolated observation-less axioms without double-firing.
- **Severity Formula**:
  $$\text{severity} = \min\!\left(1.0,\; \text{base\_sev} + 0.25 \cdot \frac{PR(a)}{\max PR} + 0.05 \cdot \frac{BTW(a)}{\max BTW}\right)$$
  where:
  - $\text{base\_sev} = 0.70$ when `in_support_degree == 0` and $a \notin Z_1$
  - $\text{base\_sev} = 0.60$ when `in_support_degree == 0` only
  - $\text{base\_sev} = 0.50$ when `in_support_degree > 0` but $a \notin Z_1$
- **Constructed `theory_lens`**: Top-5 PageRank `"A"` core claims, projected/atom parameter names & values, declared + local + macro `required_dimensions`, linked entity names, and 1-hop neighbor chunks.

### 2. `PolysemyCollisionSubDetector` (`POLYSEMY_COLLISION`)

Detects conflated `L2Entity` or `TheoryAtom` hubs whose divergent usages induce high controversy volatility or collapsed intertheoretical edge tenability.

- **Two-Pass Traversal**:
  1. **Entity-centric pass** (sorted by `entity.id`): inspects entities not already split (`entity.id` has no `__sense_` children). Gathers atoms referencing `entity.id` (falling back to chunk-colocated atoms if `entity` already carries $\ge 2$ `conceptions` or `polysemy_variance > 0` and is not in `cannot_link`), touching admissible non-undercut `TheoryRelation`s, and `L2Triple`s.
  2. **Atom-centric pass** (sorted by `atom.id`): evaluates any atom with incident relations not already covered in the entity pass.
- **Trigger Gate (Requires BOTH Structural Incompatibility AND Quantitative Threshold)**:
  1. **Structural incompatibility** (`_assess_incompatibility`) must record at least one signal:
     - `low_ts_edge_cross_cluster` or `low_ts_edge_attack` (`TS_edge < polysemy_edge_tenability_threshold`)
     - `cross_cluster_bridge` / `distinct_clusters` (spanning $>1$ `cluster_id`, $>1$ `theory_id`, $>1$ `louvain_communities` partition, or $>1$ `attributed_to` perspective)
     - `conflicting_support_attack` (both `+1` and `-1` edge/triple polarities via `SchemaConfig`) or `conflicting_internal_attack`
     - `conception_stratification` (`len(entity.conceptions) >= 2` or `entity.polysemy_variance > 0.0`)
     - *Already-split suppression*: Skips entities/atoms whose implicated relations already span distinct `__sense_` forks or `EpistemicCurationLedger.is_cannot_link` pairs.
  2. **Numeric threshold gate**:
     $$\max_a \mathcal{V}(a) \ge \theta_V \quad \lor \quad \min_e TS_{\text{edge}}(e) < \theta_{TS_{\text{edge}}}$$
     with defaults $\theta_V = 0.25$ (`polysemy_volatility_threshold`) and $\theta_{TS_{\text{edge}}} = 0.5$ (`polysemy_edge_tenability_threshold`).
- **Severity Formula (`_polysemy_severity`)**:
  - Volatility component (if triggered): $\text{vol\_part} = 0.55 + 0.40 \cdot \min\bigl(1.0,\, \frac{V_{\max} - \theta_V}{\max(1 - \theta_V,\, 10^{-6})}\bigr)$
  - Edge tenability component (if triggered): $\text{edge\_part} = 0.55 + 0.40 \cdot \min\bigl(1.0,\, \frac{\theta_{TS_{\text{edge}}} - TS_{\min}}{\max(\theta_{TS_{\text{edge}}},\, 10^{-6})}\bigr)$
  - Final: $\min\bigl(1.0,\; \max(\text{vol\_part}, \text{edge\_part}) + (0.05 \text{ if both trigger or } \text{polysemy\_variance} > 0)\bigr)$.

### 3. `UngroundedAxiomSubDetector` (`UNGROUNDED_AXIOM`)

Detects failing structuralist tenability evaluations or theoretical postulates lacking empirical observation dimensions or an empirical `"B"` base.

- **Two-Pass Traversal**:
  1. **Enrichment-cluster pass** (over `state.theoretical_enrichments`): fires if any of:
     - `enr.local_tenability < cfg.ungrounded_local_tenability_threshold` (`0.5`)
     - `not enr.is_tenable`
     - Non-constraint local `anomalies` exist (`not a.startswith("Constraint edge ")`)
     - Declared `required_dimensions` ($M_{pp}$) are absent from observed cluster `Measurement.dimension`s
     - Zero `"B"` atoms in the cluster (`cluster_b_counts == 0`) while claimant atoms exist and none are $Z_1$-grounded.
  2. **Atom-level pass** (over remaining non-suppositional `"A"` atoms not covered by a failing enrichment): fires if `ts_local < 0.5`, `tenability.is_tenable == False`, missing `required_dimensions`, or `isolated_no_obs` (`atom not in z1_grounded` and `cluster_b_counts[chunk_id] == 0` and `(incident_degree == 0 or bool(req_dims))`).
- **Severity Formula**:
  - **Enrichment pass**: $\min\bigl(1.0,\; \max(0.55 \text{ or } 0.60,\; 0.60 + 0.35 \cdot \frac{\theta_{TS} - TS_{\text{local}}}{\max(\theta_{TS},\, 10^{-6})})\bigr)$
  - **Atom pass**:
    - Low $TS_{\text{local}}$ or `is_tenable == False`: $\min\bigl(1.0,\; \max(0.55,\; 0.55 + 0.45 \cdot \frac{\theta_{TS} - TS_{\text{local}}}{\max(\theta_{TS},\, 10^{-6})})\bigr)$
    - Isolated without observations: $\min\bigl(1.0,\; 0.55 + 0.25 \cdot (\text{modal\_prior or } 0.6)\bigr)$
    - Missing dimensions only: `0.65`.

---

## Stage 3: Ranking, Cap, & Handoff to Refinement Handlers

`TheoryNetDeficitDetector.detect_deficits(...)` merges deficits from all three sub-detectors, keeps the highest severity per `deficit_id`, sorts by `(-severity, deficit_kind.value, deficit_id)`, truncates to `cfg.max_deficits_per_cycle` (default `20`), and hands off to `ClosedLoopRefinementCoordinator`:

1. **`ENTHYMEME_GAP` $\to$ `LLMTheoryGuidedPremiseRecoverer`** (`premise_recovery.py`):
   - Evaluates System 1 `DecisionEngine.evaluate_noul` recoverability gate with deterministic HMAC-PRF auditing (`stochastic_audit_rate`), extracts implicit premises over `target_chunk_ids` using centralized prompts (`premise_recovery_prompts`), preserves ADR-0023 scoping (`scope_type`, `epistemic_status`, `intensional_mode`, `attributed_to`), links entities via `EntityLinker` + `EpistemicCurationLedger`, resolves `modal_prior` via `HybridModalResolver`, and scores local pairs via shared `CascadingARCClassifier.classify_pairs`.
2. **`POLYSEMY_COLLISION` $\to$ `ConceptionConceptSplitter`** (`concept_splitter.py`):
   - Evaluates System 1 `DecisionEngine.evaluate_choice` conformal triage gate (`UNIVOCAL_DISAGREEMENT` vs. `TRUE_POLYSEMY_SPLIT`, escalating ambiguous conformal sets or low-confidence singletons), partitions via existing conceptions or real `EmbeddingModel` centroid cosine divergence (`cosine_similarity < polysemy_ambiguity_similarity_threshold`), retires split parent entities and stale mentions (`is_retired = True` in `RefinementDelta`), records `cannot_link_pairs`, rewires scoped `L2Triple`s / `TheoryAtom.entity_ids`, and optionally invokes `DenseRetrievalGlobalRelationExtractor` pair extraction.
3. **`UNGROUNDED_AXIOM` $\to$ `TheoryGuidedAxiomGrounder`** (`axiom_grounder.py`):
   - Evaluates System 1 `DecisionEngine.evaluate_noul` empirical-grounding gate, expands locally via adjacent chunks + bounded `ArtifactSubgraphReader.vector_search`, extracts entities/measurements via `LLMNERExtractor` / structured LLM / deterministic extraction, resolves entities + `modal_prior`, and projects $M_p$ parameters via `TheoryProjector`.

---

## Related Documentation

- **Architecture**: [Pipeline Architecture](../../architecture/pipeline_architecture.md), [ADR-0024: Closed-Loop Hermeneutic Refinement](../../adr/0024-closed-loop-hermeneutic-refinement.md)
- **How-To**: [Configure Hermeneutic Refinement](../../how_to/configure_hermeneutic_refinement.md)
- **API Reference**: [Refinement & Deficit Detection Reference](../../reference/refinement.md), [Configuration Reference](../../reference/config.md)
- **Code**: `packages/episteme-pipeline/episteme_pipeline/refinement/`
