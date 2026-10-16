# [ISSUE-060] Broken System 1 $\to$ System 2 Cascading Classifiers, Inverted Stochastic Audit Semantics & Protocol-Breaking `isinstance` Dispatch

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-060` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Design Patterns, Calibrated Cascade, System 1/2 Decision Engine, Conformal Prediction) |
| **Target Package(s)** | `packages/episteme-pipeline` (`phases/phase4_argument_mining/classifiers.py`, `phases/phase5_fusion/argument_clustering.py`, `phases/phase2_entity_discovery/jev_entity_linker.py`) |
| **Priority** | **Critical** |
| **Status** | `Open` |
| **Evaluated Docs & ADRs** | [`docs/architecture/design_patterns_and_standards.md`](../../docs/architecture/design_patterns_and_standards.md), [`docs/workflow/4_argument_mining/index.md`](../../docs/workflow/4_argument_mining/index.md), [`docs/workflow/5_inter_document_argument_web/index.md`](../../docs/workflow/5_inter_document_argument_web/index.md), [`ADR-0018`](../../docs/adr/0018-system-1-calibrated-decision-engine.md) |

---

## 1. Current State

[`ADR-0018`](../../docs/adr/0018-system-1-calibrated-decision-engine.md) introduces a dual-process neuro-symbolic cascade across the pipeline: a calibrated System 1 `DecisionEngine` (Jev) handles clear-cut classifications (`fast_exit` when $|C(X)| = 1$ and empirical accuracy $\ge \tau$), escalating only ambiguous cases ($|C(X)| \neq 1$) or a small stochastic audit sample (`audit_rate = 0.02`) to System 2 (`StructuredLLM` / `CrossEncoder`).

Because each phase implemented its own cascading wrapper without a shared `CalibratedCascade` abstraction (see **[Design Patterns & Standards §3.4](../../docs/architecture/design_patterns_and_standards.md)**), four severe logic bugs currently break the System 1 $\to$ System 2 cascades:

### Bug 1: `CascadingACCClassifier` Falls Back to the LLM 100% of the Time (`not relations` Always `True`)
In [`phases/phase4_argument_mining/classifiers.py#L185`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py#L185), `JevACCClassifier.classify()` classifies `TheoryAtom` component types using `DecisionEngine.evaluate_choice`, but does not extract intra-chunk relations and **unconditionally returns an empty relation list**:
```python
# JevACCClassifier.classify (line 185):
return atoms, []
```
Then, in [`CascadingACCClassifier.classify()` (`classifiers.py#L244-L275`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py#L244-L275):
```python
atoms, relations = await self.fast_classifier.classify(
    chunk_id, tagged_text, adu_ids, schema, chunk_entities
)
...
if is_uncertain or is_audit or not relations:
    return await self.llm_classifier.classify(
        chunk_id, tagged_text, adu_ids, schema, chunk_entities
    )
```
Because `relations` returned by `JevACCClassifier.classify()` is **always `[]`**, `not relations` evaluates to **`True` 100% of the time**! Consequently, `CascadingACCClassifier` runs `JevACCClassifier` on every chunk, **discards 100% of its classifications**, and calls `self.llm_classifier.classify()` on every single chunk!

### Bug 2: `CascadingARCClassifier.classify_global` Re-Runs the Entire Corpus on Audit or Empty Graph
In [`CascadingARCClassifier.classify_global()` (`classifiers.py#L618-L650`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py#L618-L650):
```python
fast_relations = await self.fast_classifier.classify_global(
    components, graph_store, schema, global_extractor
)

is_audit = random.random() < self.audit_rate
if is_audit or not fast_relations:
    llm_relations = await self.llm_classifier.classify_global(
        components, graph_store, schema, global_extractor
    )
    ...
    return list(merged.values())
```
Instead of evaluating conformal uncertainty and `audit_rate` **per candidate pair** and escalating only ambiguous/audited pairs to `self.llm_classifier`, `CascadingARCClassifier.classify_global` runs `JevARCClassifier` over all pairs and then flips a single coin (`random.random() < self.audit_rate`). When `is_audit` is `True` (or when a corpus legitimately has 0 cross-chunk relations so `not fast_relations` is `True`), it invokes `self.llm_classifier.classify_global` over **100% of the candidate pairs in the entire corpus**! Moreover, for pairs that `JevARCClassifier` rejected because $|C(X)| > 1$ (ambiguous) inside `JevARCClassifier._classify_pair` (`#L510-L512`), `JevARCClassifier` simply returns `None` (drops them) instead of escalating them to `llm_classifier`!

### Bug 3: `InterDocumentClusterVerifier.should_fuse` Approves Rejected Merges on Random Audit!
In [`InterDocumentClusterVerifier.should_fuse()` (`phases/phase5_fusion/argument_clustering.py#L343-L370`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase5_fusion/argument_clustering.py#L343-L370):
```python
is_confirmed = bool(
    decision.selected_option == "EQUIVALENT_FUSION"
    and "EQUIVALENT_FUSION" in prediction_set
    and is_singleton
    and decision.empirical_accuracy >= self.confidence_threshold
)

is_audit = False
if not is_confirmed and self.audit_rate > 0.0:
    if random.random() < self.audit_rate:
        is_confirmed = True
        is_audit = True
```
When Jev rejects a candidate cluster merge (`is_confirmed == False`, e.g., because the two arguments are `COMPETING_THEORIES` or `DISTINCT_APPLICATIONS`), a 2% coin flip (`random.random() < self.audit_rate`) **sets `is_confirmed = True` and returns `True` to `EmbeddingArgumentClustering.cluster()`** (`argument_clustering.py#L140`), which **immediately fuses the rejected cluster** without calling any System 2 verifier! It mistakes a stochastic false-negative audit for randomly overriding rejected merges into approved merges!

### Bug 4: `CascadingEntityLinker.link` Uses `isinstance` and Escalates Confident Novel Entities
In [`CascadingEntityLinker.link()` (`phases/phase2_entity_discovery/jev_entity_linker.py#L411-L426`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/jev_entity_linker.py#L411-L426):
```python
if isinstance(self.primary, JevEntityLinker):
    matched, _decision, is_ambiguous = await self.primary.link_with_decision(
        mention, graph_store, top_k=top_k, threshold=threshold
    )
    if not is_ambiguous:
        return matched
else:
    matched = await self.primary.link(mention, graph_store, top_k=top_k, threshold=threshold)
    if matched is not None:
        return matched
```
Checking `isinstance(self.primary, JevEntityLinker)` violates Open/Closed and Liskov Substitution principles. Any other `EntityLinker` passed as `self.primary` hits the `else` branch, where returning `None` (a confident "Out-of-Ontology / Novel Entity" decision) is treated as a failure and unconditionally escalated to `self.fallback`.

---

## 2. Why This Causes Problems

1. **Zero Speedup in Phase 4 ACC**: `CascadingACCClassifier` pays the latency of running both System 1 Jev *and* System 2 LLM on 100% of chunks, resulting in slower execution than pure LLM mode.
2. **Silent Precision/Recall Corruption in Phase 4 ARC & Phase 5 Fusion**:
   - In Phase 4 ARC, ambiguous pairs ($|C(X)| > 1$) are silently dropped by `JevARCClassifier` instead of escalated to the LLM, while a 0-relation corpus or a 2% coin flip triggers a full-corpus LLM run.
   - In Phase 5 Fusion, 2% of rejected (`COMPETING_THEORIES`) inter-document clusters are randomly merged into the same equivalence class without verification, corrupting the cross-document argument web.

---

## 3. Proposed Solution & Direct Fixes

Apply **Pattern 4 (`CalibratedCascade` & `TriageDecision[T]`)** from **[`docs/architecture/design_patterns_and_standards.md §3.4`](../../docs/architecture/design_patterns_and_standards.md)**:

### Fix 1: Repair `CascadingACCClassifier.classify` (`phases/phase4_argument_mining/classifiers.py#L244-L275`)
Remove `or not relations` from the escalation condition when `len(adu_ids) <= 1` (since a single ADU cannot have intra-chunk relations), and when `len(adu_ids) > 1`, either classify intra-chunk ADU pairs via System 1 `JevARCClassifier` or preserve the confident `JevACCClassifier` atom types while delegating only relation extraction or uncertain atoms:
```python
atoms, relations = await self.fast_classifier.classify(
    chunk_id, tagged_text, adu_ids, schema, chunk_entities
)
if not atoms:
    return await self.llm_classifier.classify(
        chunk_id, tagged_text, adu_ids, schema, chunk_entities
    )

is_uncertain = any(a.confidence < self.confidence_threshold for a in atoms)
is_audit = should_audit_deterministically(chunk_id, "phase4_acc", chunk_id, self.audit_rate)

if is_uncertain or is_audit:
    return await self.llm_classifier.classify(
        chunk_id, tagged_text, adu_ids, schema, chunk_entities
    )
return atoms, relations
```

### Fix 2: Escalate Per-Pair in `CascadingARCClassifier.classify_global` (`classifiers.py#L618-L650`)
Have `JevARCClassifier` return `(confirmed_relations, ambiguous_or_audited_pairs)` so `CascadingARCClassifier` invokes `self.llm_classifier` **only** on the escalated pairs:
```python
fast_relations, escalated_pairs = await self.fast_classifier.classify_global_with_triage(
    components, graph_store, schema, global_extractor, audit_rate=self.audit_rate
)
if not escalated_pairs:
    return fast_relations

llm_relations = await self.llm_classifier.classify_pairs(
    escalated_pairs, graph_store, schema
)
merged = {(r.source_id, r.target_id): r for r in fast_relations}
for r in llm_relations:
    merged[(r.source_id, r.target_id)] = r
return list(merged.values())
```

### Fix 3: Do Not Approve Rejected Clusters on Audit in `InterDocumentClusterVerifier.should_fuse` (`argument_clustering.py#L365-L368`)
Remove `is_confirmed = True` on random audit! Instead, record `is_audit = should_audit_deterministically(...)` in the emitted `FusionClusterVerified` telemetry event (or escalate to a System 2 LLM verifier if provided) while keeping `is_confirmed` faithful to the model's decision:
```python
is_audit = (
    should_audit_deterministically(rep_id, "phase5_fusion", f"{rep_id}:{len(cluster)}", self.audit_rate)
    if self.audit_rate > 0.0
    else False
)
# Never flip is_confirmed = True without a System 2 verification pass!
```

### Fix 4: Add `link_with_decision` (or `TriageDecision[L2Entity | None]`) to `EntityLinker` Protocol
Add a default `link_with_decision` method on the `EntityLinker` base class (`protocols/extractors.py`) returning `TriageDecision(value=matched, is_ambiguous=matched is None, ...)` so `CascadingEntityLinker.link` calls `await self.primary.link_with_decision(...)` polymorphically without `isinstance(self.primary, JevEntityLinker)`.

---

## 4. Acceptance Criteria

- [ ] `CascadingACCClassifier` no longer falls back to `llm_classifier` on 100% of chunks due to `not relations`.
- [ ] `CascadingARCClassifier` escalates only ambiguous ($|C(X)| \neq 1$) or deterministically audited candidate pairs to `llm_classifier`, never re-running the entire corpus on a single coin flip.
- [ ] `InterDocumentClusterVerifier.should_fuse` never sets `is_confirmed = True` on rejected clusters during stochastic auditing.
- [ ] `CascadingEntityLinker` operates polymorphically via the `EntityLinker` protocol with zero `isinstance` checks.
