# [0024] Closed-Loop Hermeneutic Refinement: Top-Down Epistemic Deficit Signals and Localized Recovery

Status: Accepted  
Date: 2026-11-16  
Extends: ADR-0002 (TAG Reranker Global Relation Extraction), ADR-0011 (D-QBAF Gradual Semantics), ADR-0015 (Theoretical Enrichment & Tenability), ADR-0017 (Artifact-Native Execution), ADR-0021 (Incremental Hydration & HITL Constraint Ledger), ADR-0022 (Unified Stratified Epistemic Metamodel), ADR-0023 (Intensional & Perspectival Scoping and Conception Stratification)

---

## Context

`pipeline_architecture.md` grounds Episteme in the **Synergized Bidirectional Reasoning Engine** paradigm (Pan et al., 2024), coupling LLMs and Knowledge Graphs in a mutually beneficial feedback loop. Previously, however, bidirectional feedback existed only **locally within individual phases**—namely Phase 2 episodic working memory ([ADR-0009](0009-sota-dual-memory-episodic-working-memory.md)) and Phase 3 TAG subgraph retrieval ([ADR-0002](0002-tag-reranker-global-relation-extraction.md)). At the macro-architectural level, the pipeline executed strictly as a one-pass feed-forward waterfall:

$$\text{Phase 1 (L1)} \longrightarrow \text{Phases 2/3/3b/4m (L2)} \longrightarrow \text{Phases 4/5 (L3)} \longrightarrow \text{Phase 6 / Theoretical Enrichment (L4)}$$

This open-loop topology caused three recurring epistemological and engineering pathologies:

1. **Unrecovered Enthymemes (Implicit Premises)**: Scholarly prose routinely omits intermediate premises or bridging warrants assumed recoverable from the surrounding macro-theory $T = \langle K, I \rangle$. Because Phase 4 ADU segmentation (`LLMADUSegmenter`) and component classification (`LLMACCClassifier`) inspect chunks bottom-up before $K = \langle M_p, M, M_{pp} \rangle$ is induced, implicit premises are missed, leaving high-centrality theoretical hypotheses (`TheoreticalHypothesis` / `CoreExpansion`) with zero incoming positive support or broken $Z_1$ grounding paths to empirical observations.
2. **Deferred Polysemy Escalation Beyond `EntityConception` Stratification**: [ADR-0023](0023-intensional-perspectival-scoping-and-conception-stratification.md) deliberately avoided eager splitting of polysemous `L2Entity` hubs during Phase 3b/4m, stratifying divergent usages into `EntityConception` facets under a single canonical referent. Yet when Phase 5/6 or `TheoreticalEnrichmentRunner` detects incompatible theory communities, high controversy volatility $\mathcal{V}$, or collapsed edge tenability $TS_{\text{edge}} < 0.5$ caused by conflating distinct senses into one hub entity, there was no top-down mechanism to escalate from `EntityConception` stratification to a surgical post-hoc L2 concept split.
3. **Observationally Ungrounded Axioms**: When Phase 6 $Z_1$ reachability or `TheoreticalEnrichmentRunner` ([ADR-0015](0015-theoretical-enrichment-and-tenability-evaluation.md), [ADR-0022](0022-unified-stratified-epistemic-metamodel.md)) flags `is_tenable == False`, $TS_{\text{local}} < 0.5$, or missing non-theoretical $M_{pp}$ observation dimensions, lower L1/L2/L3 extractors could not re-inspect targeted and immediately adjacent chunks conditioned on the induced theory lens.
4. **Acyclic Forward DAG Constraint**: `WorkflowDAG.topological_order()` enforces strict acyclicity via Kahn's algorithm and raises `ValueError` on cycles, prohibiting cyclic back-edges inside the forward phase dependency graph.

---

## Decision

We introduce a **Bounded Closed-Loop Hermeneutic Refinement Architecture ($\text{L4/L3} \to \text{L2/L1}$)** driven by typed epistemic deficit signals, localized refinement ports, and identity-keyed artifact delta overlays.

### 1. `EpistemicDeficitArtifact` Contract & Taxonomy

Defined across `episteme_pipeline/contracts/domain.py`, `episteme_pipeline/artifacts/models.py`, `codecs.py`, and `builders.py`:

- **`ArtifactKind.EPISTEMIC_DEFICIT = "epistemic_deficit"`** and **`EpistemicDeficitArtifact(DomainObjectPayload[EpistemicDeficit])`** (round-tripped via `EpistemicDeficitCodec` and `build_epistemic_deficit_artifact`).
- Three canonical `EpistemicDeficitKind` classifications detected deterministically by modular `TheoryNetDeficitDetector` (`episteme_pipeline/refinement/detector.py`, orchestrating protocol-backed sub-detectors in `_sub_detectors.py` and graph/community/tenability analysis in `_detector_analysis.py`, implementing `EpistemicDeficitDetector` and `Fingerprintable`), grounded in single-source `SchemaConfig` partition/polarity tables (`schema/default_schema.py`) and shared `Z_1` traversal (`utils/graph_algorithms.compute_z1_grounding`):
  1. **`ENTHYMEME_GAP` (`"enthymeme_gap"`)**: Partition-`"A"` `TheoryAtom`s whose TheoryNet centrality (computed via `epistemetrics.page_rank(..., prefer_neo4j=False)` with `betweenness_centrality` fallback/tie-break) meets `enthymeme_min_centrality` and exhibit `in_support_degree == 0` or lack a $Z_1$ path from Partition-`"B"` empirical observations (when empirical base nodes exist, avoiding duplicate firing with isolated `UNGROUNDED_AXIOM`s). Carries `target_chunk_ids`, `target_atom_ids`, and a macro-theory `theory_lens` (`core_claims`, `parameter_names`, `required_dimensions`).
  2. **`POLYSEMY_COLLISION` (`"polysemy_collision"`)**: `L2Entity` or `TheoryAtom` hubs bridging incompatible clusters (`epistemetrics.louvain_communities`, `TheoreticalEnrichmentArtifact` clusters, multiple `EntityConception`s / conceptual ambiguity cues / `polysemy_variance > 0`, or conflicting support/attack edges via `SchemaConfig.get_relation_polarity`) with `controversy_volatility >= polysemy_volatility_threshold` (default `0.25`) or `TS_edge < polysemy_edge_tenability_threshold` (default `0.5`).
  3. **`UNGROUNDED_AXIOM` (`"ungrounded_axiom"`)**: `TheoreticalEnrichmentArtifact` clusters or Partition-`"A"` atoms exhibiting `TS_local < ungrounded_local_tenability_threshold` (default `0.5`), `is_tenable == False`, local anomalies, missing $M_{pp}$ `required_dimensions`, or broken $Z_1$ grounding when the source cluster lacks Partition-`"B"` observations.
- **Acyclic Forward DAG Isolation**: `EpistemicDeficitArtifact` implements explicit no-op `project_to_graph()` and `collect_for_projection()` methods and is excluded from forward `Phase1ArtifactsView`–`Phase4ArtifactsView` `_allowed_kinds`. Instead, `EpistemicStateView` and `EpistemicDeficitArtifactsView` hydrate `epistemic_deficits` alongside `theoretical_enrichments`, keeping the forward `WorkflowDAG` strictly acyclic.
- **Detection Hooks**: Both `Phase6Runner` and `TheoreticalEnrichmentRunner` accept an optional `deficit_detector: EpistemicDeficitDetector | None = None` (normalized via `ensure_deficit_detector` and bound on `self` for `find_components()` fingerprinting) and emit `EpistemicDeficitArtifact` envelopes when configured.

### 2. Bounded Outer Refinement Loop, System 1 Triage & Localized Handlers

Configured via `HermeneuticRefinementConfig` on `PipelineConfig.refinement`:

- **Zero Feed-Forward Fingerprint Drift**: `max_refinement_cycles: int = 0` (`ge=0, le=5`) defaults to `0`, and `ArtifactExecutionEngine.prompt_fingerprints()` omits the `"refinement"` key unless `max_refinement_cycles > 0`, preserving identical manifest fingerprints on feed-forward runs.
- **Centralized Prompts & Shared Composition Root**: Refinement extraction prompts (`concept_split`, `premise_recovery`, `axiom_grounding`) and System 1 triage templates (`DECISION_*`) live in `episteme_pipeline/prompts/default_prompts.py` and are registered across `DefaultPromptProvider`, `LangfusePromptProvider`, and `FilePromptProvider` (`providers.py`). `PipelineFactory` (`resolve_components`, `_build_entity_linker`, `_build_arc_classifier`, `build_standalone_refinement`) shares single composition-root instances of `CascadingARCClassifier`, `CascadingEntityLinker`, `HybridModalResolver`, `LLMNERExtractor`, and `DecisionEngine` across forward phases and refinement handlers, and injects a `TheoryProjector` (enforced against accidental `TheoryNetProjector` substitution) into `TheoryGuidedAxiomGrounder`.
- Each cycle detects prioritized deficits (deduplicated by `deficit_id`, ranked by descending severity, capped at `max_deficits_per_cycle = 20`, with duplicate-signature suppression across passes) and dispatches strictly localized handlers (using shared triage/linking/scoping helpers in `episteme_pipeline/refinement/_shared.py` and `StructuredPredictable` in `llm/structured.py`) returning a `RefinementDelta`:
  - **`ENTHYMEME_GAP` $\to$ `TheoryGuidedPremiseRecoverer` (`LLMTheoryGuidedPremiseRecoverer`, `episteme_pipeline/refinement/premise_recovery.py`)**: Gates System 2 LLM invocation through System 1 `DecisionEngine.evaluate_noul` recoverability triage (with deterministic HMAC-PRF auditing at `stochastic_audit_rate`). Inspects **only** `deficit.target_chunk_ids` and target claims conditioned on `deficit.theory_lens`, recovers implicit premises/bridging warrants preserving [ADR-0023](0023-intensional-perspectival-scoping-and-conception-stratification.md) fields (`scope_type`, `epistemic_status`, `intensional_mode`, `attributed_to`, `entity_names`), resolves mentioned entities via `EntityLinker` + `EpistemicCurationLedger`, scores `modal_prior` via `ModalStrengthResolver`, and optionally runs `ARCClassifier.classify_pairs(...)` strictly on `(recovered_premise, target_atom_and_neighbors)` pairs (enabled by fixing `TAGARCClassifier.classify_pairs` and implementing `classify_pairs` on `JevARCClassifier` and `CascadingARCClassifier`).
  - **`POLYSEMY_COLLISION` $\to$ `TargetedConceptSplitter` (`ConceptionConceptSplitter`, `episteme_pipeline/refinement/concept_splitter.py`)**: Bridges [ADR-0023](0023-intensional-perspectival-scoping-and-conception-stratification.md) to post-hoc L2 disambiguation. First runs a System 1 `DecisionEngine.evaluate_choice` conformal triage gate distinguishing `UNIVOCAL_DISAGREEMENT` from `TRUE_POLYSEMY_SPLIT` (only escalating singleton ambiguous conformal sets, low-confidence decisions, or deterministic audits). Scopes strictly to entities named or linked by the deficit, partitions via existing `entity.conceptions` ($\ge 2$), `ConceptionClusterer` with real `EmbeddingModel` centroid divergence checks against `polysemy_ambiguity_similarity_threshold` (using shared `utils/similarity.cosine_similarity`), optional `StructuredPredictable` LLM, or deterministic conception/perspective clustering. Retires split parent entities and stale mentions (`retired_entity_ids` and `split_entity_parents` on `RefinementDelta`), emits `cannot_link_pairs` (persisted by `ClosedLoopRefinementCoordinator` into `context.pipeline_input.curation_ledger.cannot_link_entities` and enforced by `EpistemicCurationLedger.is_cannot_link`), rewires **only** `L2Triple`s and `TheoryAtom.entity_ids` scoped to affected chunks/atoms, and optionally invokes `GlobalRelationExtractor.extract_pairs(...)` (using Phase 3 candidate filtering on `DenseRetrievalGlobalRelationExtractor`) strictly on pairs involving the split sense entities.
  - **`UNGROUNDED_AXIOM` $\to$ `LocalizedAxiomGrounder` (`TheoryGuidedAxiomGrounder`, `episteme_pipeline/refinement/axiom_grounder.py`)**: Evaluates System 1 `DecisionEngine.evaluate_noul` empirical-grounding triage, expands `deficit.target_chunk_ids` strictly locally via same-document `sequence_index ± neighbor_window` and bounded `ArtifactSubgraphReader.vector_search` via `EmbeddingModel` (never re-chunking the corpus), invokes `NERExtractor.extract(..., anchor=_TheoryLensAnchor)` and/or structured LLM / deterministic measurement extraction conditioned on $M_{pp}$ / $M_p$ / $M$, resolves entities via `EntityLinker` + `EpistemicCurationLedger`, scores `modal_prior` via `ModalStrengthResolver`, and projects empirical parameters via `TheoryProjector` (`GenericTheoryProjector`).

### 3. Identity-Keyed Overlay, Retirement, Pass-Aware DAG & Component Re-Convergence

- **Extracted Overlay & Slicing Module**: Artifact envelope materialization, parent/mention retirement, overlay merging, and connected-component slicing live in `episteme_pipeline/artifacts/refinement_overlay.py` (`build_deficit_envelope`, `build_delta_envelopes`, `merge_pass_envelopes`, `overlay_collection`, `slice_phase4_component_view`), keeping `ClosedLoopRefinementCoordinator` focused on loop orchestration.
- **Zero Whole-Phase Invalidation & Explicit Retirement**: `ClosedLoopRefinementCoordinator` materializes `RefinementDelta` outputs onto the working `ArtifactCollection` (`latest_by_identity` last-write-wins keyed by `identity_key` with append-only `history`). Split parent `LinkedEntityArtifact` and `EntityMentionArtifact` envelopes are republished with `is_retired = True` (excluding superseded parents, stale mentions, and dangling triples in `_extract_l2_state` and `Phase3ArtifactsView`/`Phase4ArtifactsView` without erasing history).
- **Intra-Pass Overlay Refresh & Connected-Component Re-Convergence**: After each non-empty delta within a pass, `ClosedLoopRefinementCoordinator` refreshes the working `ArtifactCollection` and `EpistemicStateView` so subsequent deficits in the same pass observe up-to-date splits/premises/groundings. At pass tail, `slice_phase4_component_view` isolates connected D-QBAF components touched by the cycle for `TheoryNetProjector` (and optional localized `TheoreticalEnrichmentRunner`) re-scoring, terminating early when no actionable deficits or non-empty deltas remain.
- **Temporally Pass-Aware Lineage**:
  - `RunManifest.refinement_pass: int = 0` and `RunPhaseRecord.refinement_pass: int = 0` (`episteme_pipeline/runs/models.py`), stamped per pass by `ClosedLoopRefinementCoordinator` and preserved across `ArtifactExecutionEngine` parent-chain deduplication (`_collect_parent_chain_artifacts`, `_dedup_chain_artifacts`).
  - `ArtifactProvenance.refinement_pass: int = 0` and `ArtifactProvenance.deficit_id: str | None = None` (`episteme_pipeline/artifacts/models.py`), with pass-scoped `artifact_id`s (`artifact::<base_id>::pass<r>` for $r > 0$) generated by `artifacts/builders.py`. `ArtifactDependencyGraph` (`artifacts/invalidate.py`) tracks envelope pass timestamps so pass-$r$ refined artifacts retain direct `deficit_artifact_id` provenance without introducing cross-pass cycles back onto pass-$(r-1)$ ancestors.
  - `ExecutionConfig.persist_refinement_artifacts: bool = True` (`should_persist_artifacts("refinement")`).
- **Observability**: `EpistemicDeficitDetected`, `RefinementCycleStarted`, and `RefinementCycleCompleted` (`episteme_pipeline/events/models.py`) are integrated into `PipelineEvent`, `LoggingObserver`, `MetricsObserver`, and `LangfuseObserver`.

---

## Alternatives Considered

1. **Embedding Feedback Back-Edges Directly Inside `WorkflowDAG`**:
   - *Rejected*: `WorkflowDAG.topological_order()` guarantees acyclic phase execution and deterministic cache reuse. Cyclic edges inside the DAG would force coarse phase-level invalidation and re-execution of Phases 2–4 across the entire corpus whenever a single localized anomaly occurs.
2. **Eagerly Splitting Polysemous Hub Entities During Phase 3b / Phase 4 Maturation**:
   - *Rejected*: As established in [ADR-0023](0023-intensional-perspectival-scoping-and-conception-stratification.md), splitting all multi-perspective entities up front destroys cross-document topical identity when theories agree on the referent. Deferring splitting to `POLYSEMY_COLLISION` preserves referential unity by default and performs surgical splits only when dialectical or tenability collisions occur.
3. **Full-Corpus Re-Extraction Triggered by Tenability Anomalies**:
   - *Rejected*: Re-running Phases 1–4 globally violates incremental corpus retention invariants ([ADR-0021](0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md)) and incurs prohibitive LLM and embedding costs.

---

## Consequences

### Positive

- **True Macro-Level Bidirectional Reasoning**: Operationalizes Pan et al.'s (2024) $\text{L4/L3} \to \text{L2/L1}$ feedback loop across structuralist tenability, D-QBAF gradual semantics, argumentation mining, and entity discovery.
- **Surgical Subgraph Locality**: Unaffected documents, chunks, entities, and atoms retain pass-0 `artifact_id`s and `refinement_pass == 0`, avoiding redundant recomputation and graph churn.
- **Seamless Continuity with `ADR-0023` & `ADR-0022`**: Upgrades `EntityConception` stratification from passive metadata into an actionable disambiguation substrate (`POLYSEMY_COLLISION`), and converts `TS_local` / `TS_edge` / $\mathcal{V}$ anomalies into targeted epistemic repair.
- **Zero-Regression Opt-In**: With `HermeneuticRefinementConfig.max_refinement_cycles = 0`, purely feed-forward runs exhibit unchanged fingerprints and runtime overhead.

### Negative / Trade-offs

- **Bounded Additional Inference Cost When Enabled**: Activating `max_refinement_cycles >= 1` introduces up to `max_deficits_per_cycle` localized LLM/extractor invocations per cycle; mitigated via deterministic severity ranking, early convergence termination, and `max_refinement_cycles <= 5` bounds.
- **Split-Sense Provenance Complexity**: Post-hoc concept splits introduce `<entity_id>__sense_<k>` identifiers alongside `cannot_link_pairs`, requiring consumers inspecting historical envelopes to distinguish `ArtifactCollection.latest_by_identity` from `ArtifactCollection.history` via `ArtifactProvenance.refinement_pass` and `deficit_id`.

---

## Related

- [ISSUE-053: Closed-Loop Hermeneutic Refinement](../../issues/09-architecture-workflow-domain/resolved/ISSUE-053-closed-loop-hermeneutic-refinement-and-top-down-feedback.md)
- [Pipeline Architecture](../architecture/pipeline_architecture.md)
- [Invalidation and Resume](../architecture/invalidation_and_resume.md)
- [Artifact and Run Model](../architecture/artifact_run_model.md)
- [ADR-0002: TAG Reranker Global Relation Extraction](0002-tag-reranker-global-relation-extraction.md)
- [ADR-0011: Declarative Graph Metrics & D-QBAF](0011-declarative-graph-metrics-and-qbaf-semantics.md)
- [ADR-0015: Theoretical Enrichment & Tenability](0015-theoretical-enrichment-and-tenability-evaluation.md)
- [ADR-0017: Explicit Batch Contracts & Bulk I/O](0017-explicit-batch-contracts-and-bulk-io.md)
- [ADR-0021: Incremental Corpus Evolution & HITL Constraint Ledger](0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md)
- [ADR-0022: Unified Stratified Epistemic Metamodel](0022-unified-stratified-epistemic-metamodel.md)
- [ADR-0023: Intensional & Perspectival Scoping and Conception Stratification](0023-intensional-perspectival-scoping-and-conception-stratification.md)
