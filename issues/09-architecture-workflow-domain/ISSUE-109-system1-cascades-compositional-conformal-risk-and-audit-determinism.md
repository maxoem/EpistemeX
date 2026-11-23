# [ISSUE-109] System 1/2 Cascade Regression, Compositional Conformal Risk Budgeting & Audit Determinism

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-109` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (System 1/2 Triage, Conformal Risk Control, Reproducibility) |
| **Originating Issues** | [`ISSUE-049`](resolved/ISSUE-049-reproducibility-hazards-stochastic-auditing-prompt-fingerprints-and-conformal-drift.md), [`ISSUE-054`](resolved/ISSUE-054-intensional-perspectival-scoping-and-conception-stratification.md), [`ISSUE-056`](resolved/ISSUE-056-non-transitive-consolidation-and-compositional-conformal-risk.md), [`ISSUE-060`](resolved/ISSUE-060-broken-system1-system2-cascades-and-flawed-audit-semantics.md) |
| **Target Package(s)** | `packages/episteme-pipeline` (`decision/`, `config.py`, `runtime/`, `phases/phase3_global_relations/`, `phases/phase3b_consolidation/`, `phases/phase4_argument_mining/`, `phases/phase5_fusion/`, `llm/`, `runs/`, `tests/`) |
| **Priority** | **High** |
| **Status** | `Resolved` |
| **Evaluated Docs & ADRs** | [`docs/architecture/conformal_prediction.md`](../../docs/architecture/conformal_prediction.md), [`ADR-0018`](../../docs/adr/0018-decision-engine-architecture-and-contracts.md), [`ADR-0019`](../../docs/adr/0019-typesafe-jev-client-and-decision-observability.md), [`ADR-0023`](../../docs/adr/0023-intensional-perspectival-scoping-and-conception-stratification.md) |

---

## 1. Current State & Audit Findings

Auditing the System 1/2 cascade classifiers, compositional conformal risk pipeline, Phase 3b clustering, and determinism invariants identified **four connected groups of regressions and unwired configuration**:

1. **`CascadingACCClassifier` ~100% LLM Escalation Regression & System-1 Verification Gaps (`ISSUE-060`, `ISSUE-054`)**:
   - Commit `bb59bcb` (`ISSUE-054`) re-introduced `missing_multi_adu_relations = len(adu_ids) > 1 and not relations` and `has_entity_context = bool(chunk_entities)` in [`CascadingACCClassifier.classify()`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py#L376-L396). Meanwhile, [`JevACCClassifier.classify()`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py#L275) unconditionally returns `(atoms, [])` and ignores `chunk_entities`. Consequently, **~100% of multi-ADU chunks and entity-bearing chunks execute Jev, discard its output, and escalate to `LLMACCClassifier`**.
   - [`Phase4Runner.__init__`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/__init__.py#L237-L241) constructs `JevACCClassifier` with default `infer_intensional_mode=False` (`classifiers.py#L144`), causing high-confidence single-ADU entity-less chunks to fast-exit as `intensional_mode="asserted"` without checking suppositional/attributed framing.
   - `JevACCClassifier` and `CascadingACCClassifier` (`classifiers.py#L114-L399`) inherit `Fingerprintable.fingerprint() -> None` rather than exposing configuration thresholds/flags.
   - [`InterDocumentClusterVerifier.verify()`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_clustering.py#L401) computes `is_confirmed = has_equivalent and (len(pred_set) == 1 or emp_acc >= self.confidence_threshold)`, which can mark an ambiguous prediction set (`len(pred_set) > 1`) confirmed (`is_confirmed=True`) while emitting `action_taken="active_learning"` (`#L403-L404`).

2. **Disconnected Compositional Conformal Risk Budgeting (`ISSUE-056`)**:
   - `config.phase4.conformal_alpha` ([`config.py#L989`](../../packages/episteme-pipeline/episteme_pipeline/config.py#L989), allocated weight `0.25`—the largest budget share) is **completely dead configuration**: never read or passed to `evaluate_choice(..., alpha=...)` in [`Phase4Runner.__init__`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/__init__.py#L235-L279), [`PipelineFactory._build_arc_classifier()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L263-L273), `JevACCClassifier` (`classifiers.py#L139-L146,L224-L242`), or `JevARCClassifier` (`classifiers.py#L422-L431,L658-L662`). Phase 4 silently runs at the engine's unbudgeted default `0.05`, violating $\sum \alpha_m \le \alpha_{\text{global}}$.
   - [`ConformalCalibrator.predict_set()` / `.calibrate()`](../../packages/episteme-pipeline/episteme_pipeline/decision/conformal.py#L209-L301) and [`ObservableDecisionEngine`](../../packages/episteme-pipeline/episteme_pipeline/decision/observable.py#L339-L342,L417-L420) ignore `global_alpha` and `risk_budget_weights` (never invoking `get_allocated_alpha()`). Wiring them in [`PipelineFactory.resolve_components()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L447-L470) currently affects only `fingerprint()`.
   - [`DecisionEngineConfig.risk_budget_weights`](../../packages/episteme-pipeline/episteme_pipeline/config.py#L833-L840) allocates `30%` of the default risk budget to non-conformal phases (`phase3_global_relations=0.20`, `phase4_entity_maturation=0.10`) while omitting `refinement.conformal_alpha` (`config.py#L635`) from [`PipelineConfig.sync_allocated_risk_budgets()`](../../packages/episteme-pipeline/episteme_pipeline/config.py#L969-L994).

3. **Phase 3b Non-Transitive Clustering Scale Mismatch, Rejection Bypass & Weak Tests (`ISSUE-056`)**:
   - [`LatentGraphConsolidation.fuse()`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/consolidation.py#L337-L352) omits `BorderlinePairVerifier`-rejected pairs (e.g. `DISTINCT_SEPARATE`) from `edges` without setting `sim_matrix[i, j] = -1.0` (unlike `curation_ledger.is_cannot_link` at `#L310-L315`). Since `borderline_similarity_lower=0.75 >= min_internal_similarity=0.70`, rejected pairs can still merge transitively via a third node.
   - `Phase3bConfig.use_csls` defaults to `True` (`config.py#L283`), storing CSLS scores ($2\cos - r_T(u) - r_T(v)$, not bounded in $[0, 1]$) inside `sim_matrix` (`consolidation.py#L293`) yet evaluating them directly against cosine-calibrated `min_internal_similarity=0.70` and `1.0 - s > max_diameter` in `clique_constrained_components`.
   - [`test_issue_056_non_transitive_consolidation.py`](../../packages/episteme-pipeline/tests/test_issue_056_non_transitive_consolidation.py#L84-L96,L121-L131) uses vectors with `cos(v1, v2) ≈ 0.69 < 0.85` and `≈ 0.485 < 0.85`, so bridge edges are never formed above `0.85`—meaning unconstrained Union-Find would also pass both tests.

4. **Residual Reproducibility, Mondrian Calibration & Cache Leaks (`ISSUE-049`)**:
   - Unseeded `random.random()` remains in two stochastic audit gates:
     - [`JevGleaningGate.should_continue()`](../../packages/episteme-pipeline/episteme_pipeline/decision/gleaning.py#L288)
     - [`DenseRetrievalGlobalRelationExtractor.filter_candidate_pairs()`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/dense_retrieval_extractor.py#L533)
   - [`ConformalCalibrator.calibrate()`](../../packages/episteme-pipeline/episteme_pipeline/decision/conformal.py#L231) unconditionally overwrites `self.alpha = effective_alpha` even during stratum-scoped `(task_id, language)` calibration, silently mutating global `self.alpha` for unrelated strata.
   - [`ObservableDecisionEngine.evaluate_choice()`](../../packages/episteme-pipeline/episteme_pipeline/decision/observable.py#L340-L342) and `evaluate_score()` (`#L418-L420`) never pass `language`, and [`PipelineFactory.resolve_components()`](../../packages/episteme-pipeline/episteme_pipeline/runtime/pipeline_factory.py#L465-L469) constructs it with `task_id=None`, preventing Mondrian quantile lookup through `ObservableDecisionEngine`.
   - Minor leaks/docs: `ObservableDecisionEngine._compute_state_hash` (`decision/observable.py#L183`) uses `str(state)` instead of canonical sorted JSON; `DiskCachedStructuredLLM.predict_text` (`llm/cache.py#L118-L120`) omits `prompt_bundle_hash` in NL-to-Format Pass 1; `fingerprint_method()` (`runs/fingerprints.py#L136-L194`) does not probe `.seed`; [`docs/architecture/conformal_prediction.md`](../../docs/architecture/conformal_prediction.md#L147) still contains stale pre-refactor links (`pipeline.py#L879-L891`, `phase3b_consolidation/runner.py`, `phase5_fusion/runner.py`).

---

## 2. Why This Causes Problems

1. **Defeated System-1 Cost & Latency Savings**: Every multi-ADU or entity-bearing chunk pays for a System 1 inference only to throw away the result and invoke the full generative LLM fallback.
2. **Broken Statistical Coverage Guarantees**: Phase 4 consumes zero risk-budget allocation, `ConformalCalibrator` ignores allocated phase $\alpha_m$ and mutates global `self.alpha` on stratum calibration, and `ObservableDecisionEngine` drops Mondrian strata.
3. **Invalid Phase 3b Similarity Bounds & Non-Discriminating Tests**: Comparing unbounded CSLS values against `[0, 1]` cosine diameter bounds and failing to block rejected borderline merges compromises cluster purity while existing tests fail to distinguish `clique_constrained_components` from Union-Find.
4. **Non-Determinism Under Async Concurrency**: Remaining `random.random()` calls in Phase 3 gating and gleaning break deterministic replay across runs.

---

## 3. Proposed Solution & Remediation Details

1. **Resolve `CascadingACCClassifier` Escalation & Cluster Confirmation Semantics**:
   - Decide and implement explicit System-1 vs. System-2 boundary policy: either avoid invoking `JevACCClassifier` on chunks guaranteed to escalate (or implement fast System-1 relation/entity-binding support / configurable escalation toggles for `require_multi_adu_relations` and `require_entity_binding`), align `infer_intensional_mode` handling, and implement `fingerprint()` on `JevACCClassifier` and `CascadingACCClassifier`.
   - In `InterDocumentClusterVerifier.verify()`, ensure ambiguous clusters (`len(pred_set) > 1`) cannot silently set `is_confirmed = True` unless explicitly configured, keeping `is_confirmed` consistent with `action_taken="active_learning"`.
2. **Wire End-to-End Compositional Conformal Risk Budgeting**:
   - Pass `config.phase4.conformal_alpha` into `Phase4Runner`, `PipelineFactory._build_arc_classifier()`, `JevACCClassifier`, and `JevARCClassifier` so all `evaluate_choice` / `calibrator.predict_set` calls honor the Phase 4 budget.
   - Make `ConformalCalibrator.predict_set()` / `.calibrate()` and `ObservableDecisionEngine` resolve `get_allocated_alpha(task_id)` when `alpha is None`.
   - Reconcile `DecisionEngineConfig.risk_budget_weights` with actual conformal consumers (removing dead weights on non-conformal phases or explicitly routing them, and wiring `refinement.conformal_alpha` into `sync_allocated_risk_budgets()`).
3. **Fix Phase 3b Matrix Semantics, Rejected Pairs & Tests**:
   - Store raw cosine matrix alongside CSLS ranking in `LatentGraphConsolidation.fuse()` so `min_internal_similarity` and `max_diameter` are evaluated against consistent `[0, 1]` cosine similarities.
   - Set `sim_matrix[i, j] = sim_matrix[j, i] = -1.0` for pairs rejected by `BorderlinePairVerifier` so they cannot merge transitively.
   - Rewrite `test_issue_056_non_transitive_consolidation.py` fixtures so bridge edges genuinely exceed the merge threshold (`>= threshold`) and demonstrably fail under Union-Find while succeeding under `clique_constrained_components`.
4. **Close Remaining Determinism, Mondrian & Cache Leaks**:
   - Replace `random.random()` in `JevGleaningGate.should_continue()` and `DenseRetrievalGlobalRelationExtractor.filter_candidate_pairs()` with `should_audit_deterministically(...)`.
   - In `ConformalCalibrator.calibrate()`, update `self.alpha` only on global (`task_id is None and language is None`) calibration, storing stratum-specific `alpha` metadata without mutating `self.alpha`.
   - Pass `task_id` and `language` consistently from phase callers / `ObservableDecisionEngine` into conformal calibration lookups.
   - Canonicalize `ObservableDecisionEngine._compute_state_hash` via sorted JSON, include `prompt_bundle_hash` in `DiskCachedStructuredLLM.predict_text`, probe `.seed` in `fingerprint_method()`, and update stale links in `docs/architecture/conformal_prediction.md`.

---

## 4. Acceptance Criteria

- [x] `CascadingACCClassifier` no longer runs `JevACCClassifier` only to discard and re-escalate 100% of multi-ADU and entity-bearing chunks; `JevACCClassifier`/`CascadingACCClassifier` expose `fingerprint()`, `infer_intensional_mode` escalation policy is consistent, and `InterDocumentClusterVerifier.verify()` does not confirm ambiguous `len(pred_set) > 1` clusters.
- [x] `config.phase4.conformal_alpha` and `refinement.conformal_alpha` are synced from `DecisionEngineConfig` and passed to `evaluate_choice(..., alpha=...)` / `predict_set(...)`, `ConformalCalibrator` honors `get_allocated_alpha(task_id)`, and `risk_budget_weights` allocate budget strictly across active conformal stages.
- [x] `LatentGraphConsolidation.fuse()` separates CSLS candidate ranking from raw cosine `min_internal_similarity` / `max_diameter` checks, stamps `sim_matrix[i, j] = -1.0` on rejected borderline pairs, and is verified by discriminating Phase 3b/5 tests that fail under Union-Find.
- [x] `JevGleaningGate.should_continue()` and `DenseRetrievalGlobalRelationExtractor.filter_candidate_pairs()` use deterministic HMAC-SHA256 auditing (`should_audit_deterministically`) with zero unseeded `random.random()` calls.
- [x] `ConformalCalibrator.calibrate()` preserves global `self.alpha` on stratum-scoped calibration, `ObservableDecisionEngine` propagates `task_id`/`language`, `ObservableDecisionEngine._compute_state_hash` uses canonical JSON, `DiskCachedStructuredLLM.predict_text` hashes `prompt_bundle_hash`, `fingerprint_method()` reads `.seed`, and `docs/architecture/conformal_prediction.md` links are current.
