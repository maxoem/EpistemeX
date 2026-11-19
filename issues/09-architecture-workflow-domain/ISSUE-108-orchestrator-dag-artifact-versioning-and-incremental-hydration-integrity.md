# [ISSUE-108] Orchestrator DAG Integrity, Forward-Pass Artifact Versioning & Incremental Hydration Remediation

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-108` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (DAG Dataflow, Artifact Persistence, Incremental Hydration, Graph Projection) |
| **Originating Issues** | [`ISSUE-047`](resolved/ISSUE-047-inter-phase-artifacts-view-information-loss-and-identity-collision.md), [`ISSUE-048`](resolved/ISSUE-048-linear-ordinal-invalidation-vs-dag-execution-and-selective-recomputation.md), [`ISSUE-050`](resolved/ISSUE-050-ontological-schism-tf-vs-dqbaf-vs-structuralist-tenability-feedback.md), [`ISSUE-053`](ISSUE-053-closed-loop-hermeneutic-refinement-and-top-down-feedback.md), [`ISSUE-054`](resolved/ISSUE-054-intensional-perspectival-scoping-and-conception-stratification.md), [`ISSUE-057`](resolved/ISSUE-057-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md), [`ISSUE-062`](resolved/ISSUE-062-lossy-artifact-codecs-corrupted-maturation-mentions-and-empty-phase6-artifacts.md) |
| **Target Package(s)** | `packages/episteme-pipeline` (`runtime/`, `artifacts/`, `runs/`, `contracts/`, `phases/`, `post_processing/`, `tests/`) |
| **Priority** | **Critical** |
| **Status** | `Open` |
| **Evaluated Docs & ADRs** | [`docs/architecture/artifact_run_model.md`](../../docs/architecture/artifact_run_model.md), [`docs/architecture/invalidation_and_resume.md`](../../docs/architecture/invalidation_and_resume.md), [`ADR-0021`](../../docs/adr/0021-incremental-corpus-evolution-and-persistent-hitl-constraint-ledger.md), [`ADR-0022`](../../docs/adr/0022-unified-stratified-epistemic-metamodel.md), [`ADR-0024`](../../docs/adr/0024-closed-loop-hermeneutic-refinement.md) |

---

## 1. Current State & Audit Findings

Post-remediation auditing of `09-architecture-workflow-domain` revealed **five high-impact integration bugs and regressions** spanning orchestrator DAG wiring, disk artifact versioning, incremental hydration invalidation, refinement graph projection, and broken issue-path test coupling:

1. **`TheoreticalEnrichmentRunner` DAG Severing of Phase 5 & Phase 6 (`ISSUE-050`, `ISSUE-062`, `ISSUE-048`)**:
   - [`TheoreticalEnrichmentRunner.dependencies`](../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/runner.py#L121-L123) hardcodes `("phase4",)` with `reads_kinds = frozenset({ArtifactKind.THEORY_ATOM, ArtifactKind.THEORY_RELATION})`.
   - [`WorkflowDAG.dependencies()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/workflow_dag.py#L307-L308) gives explicit `dependencies` precedence over kind-based edge inference, excluding `"phase5"` and `"phase6"` from `transitive_dependencies()["theoretical_enrichment"]`.
   - [`ArtifactExecutionEngine.execute()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py#L1044-L1063) builds `branch_previous` strictly from `upstream_keys`. Consequently, in every orchestrated `Pipeline.run()` with enrichment enabled, `TheoreticalEnrichmentRunner` **never receives Phase 5 `FusionDecisionArtifact`s or Phase 6 `TheoryAtomArtifact`/`TheoryRelationArtifact` outputs** (curated ledger overrides, resolved `modal_prior`, `equilibrium_strength`). Step 4.5 (`runner.py#L575-L581`) then re-emits atoms whose `equilibrium_strength` changed from `None`, **silently overwriting Phase 6's fused and curated atoms** in `ArtifactCollection` and `ProjectionGraph` with un-fused Phase 4 atoms.
   - Related DAG/view omissions:
     - [`Phase4Runner.reads_kinds`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/__init__.py#L150-L156) omits `ArtifactKind.CANONICALIZATION`, breaking the `phase3b -> phase4` edge in custom workflows without `phase4_maturation`.
     - [`TheoreticalEnrichmentArtifactsView`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/execution.py#L1103) defines `_allowed_kinds` without exposing the public `allowed_kinds = _allowed_kinds` attribute.

2. **Same-Run Forward-Pass Artifact Overwrite & Broken Partial Reuse (`ISSUE-047`)**:
   - [`_scoped_artifact_id()`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/builders.py#L34-L51) only appends `::pass<r>` when `refinement_pass > 0`. On the initial forward pass (`refinement_pass == 0`), [`build_linked_entity_artifact()`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/builders.py#L329), [`build_theory_atom_artifact()`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/builders.py#L516), and [`build_theory_relation_artifact()`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/builders.py#L586) emit identical `artifact::<id>` strings across distinct phases.
   - Because [`JsonArtifactStore.write_artifact()`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/store.py#L34) writes to `{run_id}/{artifact_id}.json`, `Phase4EntityMaturationRunner` (`phase4_entity_maturation/__init__.py#L560-L570`) **overwrites Phase 2's raw entity JSON on disk** (and records a self-referential `upstream_artifact_ids=[f"artifact::{matured_entity.id}"]`), while `Phase6Runner` and `TheoreticalEnrichmentRunner` overwrite Phase 4's `TheoryAtom`/`TheoryRelation` JSONs.
   - When a follow-up run reuses Phases 1–3 (e.g. after changing `phase4_maturation` config), [`hydrate_previous_collection()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py#L1964-L1968) filters stored artifacts by `allowed_phase_names`. Because the overwritten JSON now carries `phase_name="Phase 4: Entity Maturation..."`, **all matured entities vanish from Phase 2's hydrated collection**.

3. **Incremental Hydration Ledger Invalidation, Reuse-Flag Bypass & Non-Deterministic Hashing (`ISSUE-057`)**:
   - [`ArtifactHydrator.can_hydrate`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/execution.py#L1379-L1390) checks only `is_phase_unchanged()` and **never compares `manifest.curation_ledger_fingerprint != prior_manifest.curation_ledger_fingerprint`**, returning stale hydrated Phase 2/3/4 artifacts after `cannot_link` or `REJECTED` ledger edits on unchanged documents.
   - [`choose_reuse_source()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py#L597-L599) mutates `resume_point.run_id = prior.run_id` before returning early on `not allow_phase_reuse`, and [`execute()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py#L1012-L1021) unconditionally loads `prior_manifest`/`prior_artifacts` regardless of `allow_phase_reuse=False` or `allow_artifact_hydration=False`.
   - [`fingerprint_curation_ledger()`](../../packages/episteme-pipeline/episteme_pipeline/runs/fingerprints.py#L290-L313) passes `ledger.model_dump(mode="json")` to `stable_fingerprint()`. Because `must_link_entities` and `cannot_link_entities` are `set[tuple[str, str]]`, Pydantic serializes them in arbitrary hash-set order, making `curation_ledger_fingerprint` **dependent on `PYTHONHASHSEED`**.
   - [`RelationOverride.polarity`](../../packages/episteme-pipeline/episteme_pipeline/contracts/phase_contracts.py#L48) is declared on the contract but never read by `apply_to_triples()` (`#L225-L260`) or `apply_to_theory_relations()` (`#L293-L356`).
   - [`Phase2Runner._deduplicate_entities()`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/__init__.py#L420-L476) remaps `entity.id -> existing_id` on `is_must_link` without rewriting `all_triples` endpoints or `mention_envelopes` keys, leaving dangling triple/mention references.
   - `tests/test_incremental_corpus_and_curation_ledger.py` tests phase runners in isolation; no end-to-end multi-run `Pipeline.run()` incremental corpus + ledger edit test exists.

4. **Retired Split Entities Re-Projected to Graph & Standalone Refinement Wiring (`ISSUE-053`)**:
   - [`EntityMentionArtifact`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/models.py#L291-L304) and [`LinkedEntityArtifact`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/models.py#L327-L334) do **not** guard `project_to_graph()` or `collect_for_projection()` on `self.is_retired`. When `project_artifacts_to_graph=True`, [`_run_refinement_stage()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/execution_engine.py#L1512-L1523) projects `latest_new_artifacts`, re-upserting retired parent hubs (with empty `source_chunk_ids`) and stale `EXTRACTED_FROM` edges into Neo4j / `InMemoryGraphStore`.
   - [`PipelineFactory.build_standalone_refinement()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L277-L345) leaves `premise_recoverer=None`, preventing `ENTHYMEME_GAP` recovery on standalone `Pipeline(...)` construction outside `Pipeline.for_task()`.
   - Re-running an identical refinement run reuses forward phases via `choose_reuse_source()`, but `_run_refinement_stage()` still re-executes because refinement sits outside `WorkflowDAG` reuse tracking.

5. **Broken `ISSUE-054` Doc-Sync Test & Minor Codec Edge Cases (`ISSUE-054`, `ISSUE-062`)**:
   - [`test_issue_054_documentation_and_adr_sync()`](../../packages/episteme-pipeline/tests/test_issue_054_intensional_scoping_and_conceptions.py#L863-L871) hardcodes `issues/09-architecture-workflow-domain/ISSUE-054-...md`, currently causing workspace `pytest` to fail (`1 failed, 1098 passed`) now that `ISSUE-054` resides in `resolved/`.
   - [`DocumentCodec.to_payload()`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/codecs.py#L90) stringifies non-`str` values in `L1Document.metadata`, and [`LocalRelationCodec.to_payload()`](../../packages/episteme-pipeline/episteme_pipeline/artifacts/codecs.py#L278) coerces `source_chunk_id=None` to `""`.

---

## 2. Why This Causes Problems

1. **Silent End-to-End Epistemic Corruption (`TheoreticalEnrichmentRunner`)**: Every production run enabling both Phase 6 TheoryNet and Theoretical Enrichment silently drops Phase 5 equivalence fusions, HITL modality overrides, and Phase 6 QBAF posteriors—replacing them in the final graph with un-fused Phase 4 atoms.
2. **Broken Reproducibility & Resumability**: Overwriting forward-pass JSONs on disk destroys provenance history and drops entities during upstream-reused runs, while non-deterministic set hashing and unvalidated ledger hydration cause either spurious cache misses across processes or stale graphs after HITL edits.
3. **Graph Pollution During Refinement**: Splitting polysemous hub concepts via `ISSUE-053` leaves zombie retired entities and edges inside `ProjectionGraph`, distorting downstream graph queries and visualization.
4. **CI Suite Failure**: Hardcoded paths into `issues/09-architecture-workflow-domain/` break `pytest` whenever completed issues are moved to `resolved/` or `issues/archived/`.

---

## 3. Proposed Solution & Remediation Details

1. **Restore Full Phase 5/6 -> Theoretical Enrichment Dataflow**:
   - Update `TheoreticalEnrichmentRunner.dependencies` (e.g., `("phase6",)` or kind-inferred post-Phase-6) and `reads_kinds` (`THEORY_ATOM`, `THEORY_RELATION`, `FUSION_DECISION`) so `WorkflowDAG` and `ArtifactExecutionEngine` deliver Phase 5 fusions and Phase 6 QBAF/curated atoms to enrichment. Keep `test_issue_048_dag_execution.py` independent-branch tests intact (using `StubValidPhase`).
   - Add `ArtifactKind.CANONICALIZATION` to `Phase4Runner.reads_kinds` and expose `allowed_kinds = _allowed_kinds` on `TheoreticalEnrichmentArtifactsView`.
2. **Phase-Scoped / Versioned Forward-Pass `artifact_id`s**:
   - Disambiguate `artifact_id` across forward-pass producers (e.g., encoding phase tag or producer scope in `_scoped_artifact_id()` while keeping semantic `identity_key` constant for `ArtifactCollection` deduplication and avoiding self-referential `upstream_artifact_ids`) so `JsonArtifactStore` retains all per-phase versions on disk and `hydrate_previous_collection()` (`allowed_phase_names`) works across arbitrary resume boundaries.
3. **Deterministic Ledger Fingerprinting, Hydration Invalidation & Reuse Flag Enforcement**:
   - Sort `must_link_entities` and `cannot_link_entities` canonically inside `fingerprint_curation_ledger()`.
   - Require `manifest.curation_ledger_fingerprint == prior_manifest.curation_ledger_fingerprint` in `ArtifactHydrator.can_hydrate` (and invalidate affected phases cleanly on ledger edits).
   - Ensure `choose_reuse_source()` clears/omits `resume_point.run_id` when `not allow_phase_reuse`, and guard `prior_manifest`/`prior_artifacts` hydration in `ArtifactExecutionEngine.execute()` on `allow_phase_reuse` / `allow_artifact_hydration`.
   - Implement `RelationOverride.polarity` handling in `apply_to_triples()` / `apply_to_theory_relations()`, and rewrite `all_triples` endpoints and `mention_envelopes` keys when `Phase2Runner._deduplicate_entities()` merges `is_must_link` entities.
4. **Refinement Projection Retirement Guard & Standalone Wiring**:
   - Skip (or prune) artifacts with `is_retired=True` inside `LinkedEntityArtifact` and `EntityMentionArtifact` `project_to_graph()` / `collect_for_projection()` (and ensure `_run_refinement_stage` prunes retired parent nodes/edges in `ProjectionGraph` when updating).
   - Wire `premise_recoverer` in `PipelineFactory.build_standalone_refinement()` and record/check refinement pass lineage for reuse when inputs/config/refinement parameters are unchanged.
5. **Test & Codec Cleanup**:
   - Decouple `test_issue_054_documentation_and_adr_sync()` from transient issue folder locations (e.g. search active/`resolved/`/`issues/archived/`, or assert on permanent `docs/adr/` + codebase specs).
   - Preserve exact metadata value types in `DocumentCodec` and round-trip `source_chunk_id=None` in `LocalRelationCodec`.
   - Add true multi-run orchestrated `Pipeline.run()` integration tests covering: (a) Phase 5/6 -> Theoretical Enrichment coupling, (b) forward-pass partial resume preserving Phase 2 raw vs. Phase 4 matured history, (c) incremental $\Delta D$ + `EpistemicCurationLedger` edit invalidation, and (d) `is_retired` suppression in `ProjectionGraph`.

---

## 4. Acceptance Criteria

- [ ] `TheoreticalEnrichmentRunner` receives Phase 5 `FusionDecisionArtifact`s and Phase 6 QBAF/curated `TheoryAtomArtifact`s/`TheoryRelationArtifact`s when executed via `Pipeline.run()` / `ArtifactExecutionEngine`, verified by an end-to-end orchestrated integration test (while preserving `test_issue_048_dag_execution.py` independent-branch semantics).
- [ ] `Phase4Runner.reads_kinds` includes `ArtifactKind.CANONICALIZATION` and `TheoreticalEnrichmentArtifactsView` exposes `allowed_kinds`.
- [ ] Forward-pass updates (`Phase4EntityMaturationRunner`, `Phase6Runner`, `TheoreticalEnrichmentRunner`) write non-colliding `artifact_id`s (with non-self-referential `upstream_artifact_ids`) so `JsonArtifactStore` preserves full version history on disk and partial upstream reuse (`allowed_phase_names`) retains all entities/atoms.
- [ ] `fingerprint_curation_ledger()` produces identical SHA-256 digests regardless of `PYTHONHASHSEED`, `ArtifactHydrator.can_hydrate` invalidates stale hydration when `curation_ledger_fingerprint` changes, and `allow_phase_reuse=False` / `allow_artifact_hydration=False` strictly disable prior-run hydration.
- [ ] `RelationOverride.polarity` is honored in `apply_to_triples()` / `apply_to_theory_relations()`, and `Phase2Runner._deduplicate_entities()` rewrites `all_triples` and `mention_envelopes` on must-link merges without dangling IDs.
- [ ] Retired split entities and mentions (`is_retired=True`) are never re-upserted into `ProjectionGraph` during `_run_refinement_stage()`, `PipelineFactory.build_standalone_refinement()` wires `premise_recoverer`, and identical refinement runs support clean reuse tracking.
- [ ] `DocumentCodec` and `LocalRelationCodec` preserve exact metadata types and `None` `source_chunk_id`, and `test_issue_054_documentation_and_adr_sync()` passes regardless of whether `ISSUE-054` is in `resolved/` or `issues/archived/`.
