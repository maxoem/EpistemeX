# [ISSUE-064] Phase 4–6 & Post-Processing Defects: `processed_chunk_ids` `UnboundLocalError`, Fake `L2Entity` Adapter, Order-Dependent Tenability Lookup & Hardcoded Psychology Parameters

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-064` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Phase 4–6 & Post-Processing Bugs, LSP/OCP Violations, Domain Generality) |
| **Target Package(s)** | `packages/episteme-pipeline` (`phases/phase4_argument_mining/`, `phases/phase6_theorynet/`, `post_processing/theoretical_enrichment/`) |
| **Priority** | **Critical** |
| **Status** | `Resolved` |
| **Evaluated Docs & ADRs** | [`docs/workflow/4_argument_mining/index.md`](../../docs/workflow/4_argument_mining/index.md), [`docs/workflow/6_theorynet/index.md`](../../docs/workflow/6_theorynet/index.md), [`docs/workflow/post_processing/theoretical_enrichment.md`](../../docs/workflow/post_processing/theoretical_enrichment.md), [`docs/architecture/design_patterns_and_standards.md §3.6 & §4.2`](../../docs/architecture/design_patterns_and_standards.md) |

---

## 1. Current State & Identified Defects

Auditing Phases 4, 6, and Theoretical Enrichment (`post_processing/theoretical_enrichment/`) uncovered four concrete implementation and domain bugs:

### Defect 1 (Phase 4): `UnboundLocalError: processed_chunk_ids` When `chunks` Is Empty
In [`Phase4Runner.run()` (`phases/phase4_argument_mining/__init__.py#L203-L306`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/__init__.py#L203-L306):
```python
203:         for batch_idx, chunk_batch in enumerate(batched(chunks, batch_size)):
...
210:             processed_chunk_ids = []
...
254:             if processed_chunk_ids:
255:                 for processed_batch in batched(processed_chunk_ids, 500):
256:                     await self.graph_store.mark_chunks_processed(list(processed_batch), _PHASE_TAG)
...
304:         if processed_chunk_ids:
305:             for chunk_batch in batched(processed_chunk_ids, 500):
306:                 await self.graph_store.mark_chunks_processed(list(chunk_batch), _PHASE_TAG)
```
1. `processed_chunk_ids` is only initialized **inside** the `for batch_idx, chunk_batch` loop at line 210, and already committed per batch at lines 254–256.
2. When `chunks` is empty (e.g., all chunks were already processed in a prior run and Phase 4 is resuming at the global ARC step, or 0 chunks exist), the loop at line 203 does not execute, and line 304 crashes with **`UnboundLocalError: cannot access local variable 'processed_chunk_ids' where it is not associated with a value`**!

### Defect 2 (Phase 4): Fake `L2Entity` Adapter (`_component_as_entity`) & Silent Disabling of Global ARC
In [`TAGARCClassifier` (`phases/phase4_argument_mining/arc_classifier.py#L36-L58,L359-L369`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/arc_classifier.py#L36-L58):
```python
def _component_as_entity(component: TheoryAtom) -> L2Entity:
    return L2Entity(
        id=component.id,
        label="TheoryAtom",
        name=component.text[:80],
        description=component.component_type,
    )
...
entity_a = _component_as_entity(component_a)
entity_b = _component_as_entity(component_b)
env_a, env_b = await asyncio.gather(
    global_extractor.get_structural_neighborhood(entity_a, graph_store, self.subgraph_depth),
    global_extractor.get_structural_neighborhood(entity_b, graph_store, self.subgraph_depth),
)
```
And in [`Phase4Runner.__init__()` (`phases/phase4_argument_mining/__init__.py#L154-L167`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/__init__.py#L154-L167):
```python
self.arc_classifier = arc_classifier or (
    TAGARCClassifier(...)
    if global_extractor is not None
    else None
)
```
1. Both `TAGRelationExtractor.get_structural_neighborhood()` and `DenseRetrievalGlobalRelationExtractor.get_structural_neighborhood()` are 1-line passthroughs to `await graph_store.get_neighborhood(entity.id, depth=depth)`!
2. Coupling Phase 4 `TAGARCClassifier` to Phase 3's `GlobalRelationExtractor` via a fake `L2Entity` adapter violates Liskov Substitution and Hexagonal layer boundaries (see **[Design Patterns & Standards §4.2](../../docs/architecture/design_patterns_and_standards.md)**)—and worse, if `Phase4Runner` is instantiated without `global_extractor`, **global cross-chunk ARC is silently disabled (`self.arc_classifier = None`)** even though `graph_store.get_neighborhood()` is directly available on `GraphReader`!

### Defect 3 (Post-Processing): Single-Pass Order-Dependent Bug in `TheoreticalEnrichmentRunner._find_target_parameters`
In [`TheoreticalEnrichmentRunner.run()` (`post_processing/theoretical_enrichment/runner.py#L222-L289,L385-L391`)](../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/runner.py#L222-L289):
```python
cluster_theory_params: dict[tuple[str, str], dict[str, Any]] = {}
{a.id: a for a in input.theory_atoms}  # Line 224: unassigned dead expression!

for cluster in clusters:
    for theory in candidate_theories:
        proj_params = await self.projector.aproject(cluster, theory)
        cluster_theory_params[(cluster.cluster_id, theory.name)] = proj_params
        ...
        for rel in outgoing_rels:
            target_params = self._find_target_parameters(
                rel.target_id, clusters, cluster_theory_params, theory.name
            )
```
Look at what happens in this single-pass `for cluster in clusters:` loop:
- While processing `clusters[0]`, `cluster_theory_params` only contains parameters for `clusters[0]`!
- For every outgoing relation `rel` from `clusters[0]` to a target atom in `clusters[k]` ($k > 0$), `self._find_target_parameters(...)` looks up `cluster_theory_params.get((c.cluster_id, theory_name), {})`—which **has not been populated yet**!
- Consequently, forward inter-cluster edges always receive `target_params = {}`, causing edge tenability evaluation (`solve_edge_tenability`) to depend entirely on the arbitrary iteration order of `clusters`!

### Defect 4 (Post-Processing): Hardcoded Psychology/Neuroscience Parameter Names in `TenabilitySolver.solve_edge_tenability`
In [`TenabilitySolver.solve_edge_tenability()` (`post_processing/theoretical_enrichment/solvers.py#L238-L249`)](../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py#L238-L249):
```python
if not shared_keys:
    repression = source_params.get("RepressionMagnitude") or target_params.get("RepressionMagnitude")
    amygdala = source_params.get("AmygdalaHyperactivity") or target_params.get("AmygdalaHyperactivity")
    dopamine = source_params.get("DopamineDepletion") or target_params.get("DopamineDepletion")

    if repression is not None and amygdala is not None:
        ...
```
The core domain-agnostic mathematical solver (`TenabilitySolver`) contains hardcoded parameter names (`"RepressionMagnitude"`, `"AmygdalaHyperactivity"`, `"DopamineDepletion"`) from a specific psychology/neuroscience test fixture! This violates both `ADR-0015` (Domain-Agnostic Core Invariance) and the Open/Closed Principle.

---

## 2. Proposed Solution & Direct Fixes

### Fix 1: Delete Redundant Post-Loop Checkpoint Block in `Phase4Runner.run()` (`phases/phase4_argument_mining/__init__.py#L304-L306`)
Delete lines 304–306 in `phases/phase4_argument_mining/__init__.py` (since `processed_chunk_ids` is already committed at the end of each batch at lines 254–256).

### Fix 2: Decouple `TAGARCClassifier` from `GlobalRelationExtractor` & `_component_as_entity`
1. In `TAGARCClassifier._classify_pair()` (`phases/phase4_argument_mining/arc_classifier.py#L359-L369`), call `graph_store.get_neighborhood(component_a.id, depth=self.subgraph_depth)` directly instead of fabricating dummy `L2Entity` instances for `global_extractor.get_structural_neighborhood()`.
2. Delete `_component_as_entity()` (`arc_classifier.py#L36-L58`), make `global_extractor` optional/deprecated in `ARCClassifier.classify_global()`, and always instantiate `TAGARCClassifier` (or `CascadingARCClassifier`) in `Phase4Runner.__init__()` even when `global_extractor is None`.

### Fix 3: Split `TheoreticalEnrichmentRunner.run()` into Two Passes (`post_processing/theoretical_enrichment/runner.py#L222-L295`)
Separate parameter projection + local tenability (Pass 1) from inter-cluster edge tenability evaluation (Pass 2) so `cluster_theory_params` is 100% populated before any edge lookup occurs:
```python
# Pass 1: Project parameters and evaluate local tenability for all (cluster, theory) pairs
cluster_theory_params: dict[tuple[str, str], dict[str, Any]] = {}
for cluster in clusters:
    for theory in self._match_theories(cluster, all_theories):
        proj_params = await self.projector.aproject(cluster, theory)
        cluster_theory_params[(cluster.cluster_id, theory.name)] = proj_params
        local_result = self.solver.solve_local_tenability(cluster, theory, proj_params)
        ...

# Pass 2: Evaluate inter-cluster / intertheoretical edge tenability with complete parameter map
for cluster in clusters:
    for theory in self._match_theories(cluster, all_theories):
        proj_params = cluster_theory_params[(cluster.cluster_id, theory.name)]
        for rel in self._outgoing_relations(cluster, input.theory_relations):
            target_params = self._find_target_parameters(
                rel.target_id, clusters, cluster_theory_params, theory.name
            )
            edge_result = self.solver.solve_edge_tenability(
                rel, theory, proj_params, target_params
            )
            ...
```

### Fix 4: Replace Hardcoded Psychology Parameters in `TenabilitySolver.solve_edge_tenability` with Generic Normalized Parameter Distance
In [`post_processing/theoretical_enrichment/solvers.py#L238-L249`](../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/solvers.py#L238-L249), replace the hardcoded `"RepressionMagnitude"` / `"AmygdalaHyperactivity"` / `"DopamineDepletion"` check with a domain-general comparison across all numeric values in `source_params.values()` and `target_params.values()` (or explicit `bridge_laws` declared on `TheoryElementDefinition`).

---

## 3. Acceptance Criteria

- [x] Running `Phase4Runner.run()` when `chunks == []` completes cleanly without raising `UnboundLocalError`.
- [x] `TAGARCClassifier` queries `graph_store.get_neighborhood(component.id, depth=...)` directly without `_component_as_entity` or requiring `global_extractor`.
- [x] `TheoreticalEnrichmentRunner.run()` populates `cluster_theory_params` across all clusters in Pass 1 before evaluating outgoing edges in Pass 2, making edge tenability invariant to cluster ordering.
- [x] `TenabilitySolver.solve_edge_tenability()` contains zero hardcoded domain-specific parameter strings.
