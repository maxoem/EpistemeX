# [ISSUE-062] Lossy Domain–Artifact–Graph Codecs, Corrupted Phase 4 Maturation `source_chunk_ids`, and Empty Phase 6 Artifact Output

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-062` |
| **Domain / Category** | `09-Architecture, Workflow & Domain` (Design Patterns, Bidirectional Codec, Artifact Hydration, Graph Projection) |
| **Target Package(s)** | `packages/episteme-pipeline` (`artifacts/models.py`, `artifacts/builders.py`, `artifacts/execution.py`, `projection/artifact_projector.py`, `phases/phase4_entity_maturation/`, `phases/phase6_theorynet/`, `post_processing/theoretical_enrichment/`) |
| **Priority** | **Critical** |
| **Status** | `Open` |
| **Evaluated Docs & ADRs** | [`docs/architecture/design_patterns_and_standards.md §3.5`](../../docs/architecture/design_patterns_and_standards.md), [`docs/architecture/artifact_run_model.md`](../../docs/architecture/artifact_run_model.md), [`docs/workflow/4_entity_maturation/index.md`](../../docs/workflow/4_entity_maturation/index.md), [`docs/workflow/6_theorynet/index.md`](../../docs/workflow/6_theorynet/index.md), [`ADR-0017`](../../docs/adr/0017-artifact-native-execution-and-selective-invalidation.md) |

---

## 1. Current State

In Episteme's Artifact-Native execution architecture ([`ADR-0017`](../../docs/adr/0017-artifact-native-execution-and-selective-invalidation.md)), domain contracts (`L1Chunk`, `L2Entity`, `L2Triple`, `TheoryAtom`, `TheoryRelation`) are serialized into `ArtifactEnvelope` payloads by `artifacts/builders.py`, hydrated back into domain contracts by `ArtifactsView.from_collection()` in `artifacts/execution.py`, and projected into Neo4j by `projection/artifact_projector.py`.

Because conversion logic is scattered across four separate modules instead of using a single **Bidirectional Codec (`ArtifactCodec[DomainT, PayloadT]`)** (see **[Design Patterns & Standards §3.5](../../docs/architecture/design_patterns_and_standards.md)**), five severe data-corruption and information-loss bugs currently exist:

### Bug 1: `Phase4EntityMaturationRunner` Corrupts `mention_ids` and Wipes Out `source_chunk_ids = []`
In [`Phase4EntityMaturationRunner.run()` (`phases/phase4_entity_maturation/__init__.py#L153-L161`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase4_entity_maturation/__init__.py#L153-L161):
```python
artifacts.append(
    build_linked_entity_artifact(
        matured_entity,
        [f"artifact::{cid}" for cid in matured_entity.source_chunk_ids],
        run_id=context.run_id,
        phase_name=self.name,
        method="Phase4EntityMaturationRunner",
    )
)
```
Compare this with `Phase2Runner.run()` (`phase2_entity_discovery/__init__.py#L229-L234`), which passes `artifact::mention::{entity.id}::{cid}`.
Inside `build_linked_entity_artifact` (`artifacts/builders.py#L111`), `"artifact::"` is stripped, storing `mention_ids = [cid, ...]` (raw chunk IDs without `"mention::{entity_id}::"`!).
Subsequently, when `Phase2ArtifactsView.from_collection()` (`artifacts/execution.py#L120-L125`) or `ArtifactGraphProjector._project_linked_entity()` (`projection/artifact_projector.py#L94-L97`) hydrates the matured entity, both call `parse_mention_id(mid)` (`artifacts/builders.py#L81-L97`):
```python
def parse_mention_id(mention_id: str) -> tuple[str, str]:
    normalized = mention_id.removeprefix("artifact::")
    if not normalized.startswith("mention::"):
        return normalized, ""
```
Because `mid` is a raw chunk ID (does not start with `"mention::"`), `parse_mention_id(mid)` returns `(cid, "")` (`chunk_id == ""`)! Both `Phase2ArtifactsView` and `ArtifactGraphProjector` filter `if chunk_id`, resulting in **`source_chunk_ids = []` (empty list!) on every matured entity**!

### Bug 2: `ChunkArtifact` Drops `embedding`, `text_anchor`, and `metadata` (Breaking Phase 2 Section Eviction on Resume)
In [`ChunkArtifact` (`artifacts/models.py#L86-L95`)](../../packages/episteme-pipeline/episteme_pipeline/artifacts/models.py#L86-L95) and [`Phase1ArtifactsView.from_collection()` (`artifacts/execution.py#L84-L95`)](../../packages/episteme-pipeline/episteme_pipeline/artifacts/execution.py#L84-L95):
- `build_chunk_artifact()` (`artifacts/builders.py#L61-L78`) drops `chunk.embedding`, `chunk.text_anchor`, and `chunk.metadata` (converting only `"has_embedding": str(chunk.embedding is not None)` into metadata!).
- When Phase 1 is reused from the artifact store via `Phase1ArtifactsView.from_collection()`, every reconstructed `L1Chunk` has `embedding=None`, `text_anchor=None`, and `metadata={}`.
- In Phase 2, `EpisodicEvictionHandler.check_and_evict()` (`phase2_entity_discovery/working_memory.py#L303-L304`) reads `chunk.metadata.get("section_path")` to detect chapter/section transitions, and `ArtifactGraphProjector._project_chunk()` (`artifact_projector.py#L76-L86`) projects `embedding=None` into Neo4j, wiping out all chunk vector embeddings on re-projection!

### Bug 3: `TheoryAtomArtifact` Drops `entity_ids`, `modal_strength`, `base_score`, `measurements`, `parameters`, and `tenability`
In [`TheoryAtomArtifact` (`artifacts/models.py#L168-L180`)](../../packages/episteme-pipeline/episteme_pipeline/artifacts/models.py#L168-L180) and [`Phase4ArtifactsView.from_collection()` (`artifacts/execution.py#L231-L245`)](../../packages/episteme-pipeline/episteme_pipeline/artifacts/execution.py#L231-L245):
- `build_theory_atom_artifact()` (`builders.py#L156-L176`) only serializes `atom_id`, `chunk_id`, `component_type`, `text`, `confidence`, and `plausibility`.
- All other `TheoryAtom` fields—including `entity_ids` (Layer 2 grounding), `modal_strength` and `base_score` (resolved in Phase 4 via `HybridModalResolver`), `text_anchor`, `measurements`, `parameters`, and `tenability`—are lost whenever `Phase4ArtifactsView.from_collection()` reconstructs `TheoryAtom`s for Phase 5, Phase 6, or Theoretical Enrichment!

### Bug 4: `Phase6Runner.run()` Always Returns `ArtifactCollection([])` and Logs `0 TheoryRelations`
In [`Phase6Runner.run()` (`phases/phase6_theorynet/runner.py#L146-L213`)](../../packages/episteme-pipeline/episteme_pipeline/phases/phase6_theorynet/runner.py#L146-L213):
- Contrary to [`docs/workflow/6_theorynet/index.md#L105`](../../docs/workflow/6_theorynet/index.md#L105) (*"Outputs: `ArtifactCollection` containing formal TheoryNet artifacts"*), `Phase6Runner.run()` returns `ArtifactCollection([])` (an empty list) at lines 146 and 213!
- Consequently, `TheoreticalEnrichmentRunner` (which runs after Phase 6 and consumes `Phase4ArtifactsView` from `ArtifactCollection`) **never receives the equilibrium plausibilities $\tau^*$, active weights, or admissibility flags computed by Phase 6**!
- Additionally, `relations_updated = 0` at line 149 is never incremented inside the relation batch loop (lines 159–162), so line 169 always logs `"Projected N TheoryAtoms and 0 TheoryRelations"`.

### Bug 5: `TheoreticalEnrichmentRunner` Overwrites `TheoryRelation` Graph Edges with Untyped Dicts
In [`TheoreticalEnrichmentRunner.run()` (`post_processing/theoretical_enrichment/runner.py#L301-L313,L381-L383`)](../../packages/episteme-pipeline/episteme_pipeline/post_processing/theoretical_enrichment/runner.py#L301-L313):
- Instead of calling `await self.graph_store.upsert_theory_relations(enriched_relations)` (which uses `TheoryRelation.to_graph_properties()`), `TheoreticalEnrichmentRunner` manually constructs raw dicts with only `confidence`, `source`, `tenability_score`, `tenability_status`, and `anomaly_details` and calls `await self.graph_store.upsert_relations(...)`—bypassing `TheoryRelation.to_graph_properties()` and omitting all D-QBAF properties (`inferential_force`, `stance_probability`, `model_confidence`, `active_weight`, `weight_support`, `weight_attack`).

---

## 2. Proposed Solution & Direct Fixes

Follow **Pattern 5 (`ArtifactCodec[DomainT, PayloadT]`)** in **[`docs/architecture/design_patterns_and_standards.md §3.5`](../../docs/architecture/design_patterns_and_standards.md)**:

### Fix 1: Fix `Phase4EntityMaturationRunner` Mention IDs (`phases/phase4_entity_maturation/__init__.py#L153-L161`) & Store `source_chunk_ids` Explicitly
1. In `Phase4EntityMaturationRunner.run()`, format mention artifact IDs using the canonical `"artifact::mention::{entity_id}::{chunk_id}"` scheme:
   ```python
   artifacts.append(
       build_linked_entity_artifact(
           matured_entity,
           [
               f"artifact::mention::{matured_entity.id}::{cid}"
               for cid in matured_entity.source_chunk_ids
           ],
           run_id=context.run_id,
           phase_name=self.name,
           method="Phase4EntityMaturationRunner",
       )
   )
   ```
2. Add `source_chunk_ids: list[str] = Field(default_factory=list)` directly to `LinkedEntityArtifact` (`artifacts/models.py#L118`) so chunk lineage does not depend on string-splitting `mention_ids`.

### Fix 2: Make `ChunkArtifact` and `TheoryAtomArtifact` Lossless Codecs
1. Add `embedding: list[float] | None = None`, `text_anchor: TextAnchor | None = None`, and `chunk_metadata: dict[str, Any] = Field(default_factory=dict)` to `ChunkArtifact` (`artifacts/models.py#L86`), and map them in both `build_chunk_artifact()` (`builders.py#L61`) and `Phase1ArtifactsView.from_collection()` (`execution.py#L84`).
2. Add `entity_ids: list[str] = Field(default_factory=list)`, `modal_strength: float = 0.6`, `base_score: float | None = None`, `text_anchor: TextAnchor | None = None`, `measurements: dict[str, Any] = Field(default_factory=dict)`, `parameters: dict[str, Any] = Field(default_factory=dict)`, and `tenability: dict[str, Any] = Field(default_factory=dict)` to `TheoryAtomArtifact` (`artifacts/models.py#L168`), and map them in `build_theory_atom_artifact()` and `Phase4ArtifactsView.from_collection()`.

### Fix 3: Emit Updated `TheoryAtomArtifact` and `TheoryRelationArtifact` Envelopes in `Phase6Runner.run()` & Fix Counter
In [`phases/phase6_theorynet/runner.py#L149-L213`](../../packages/episteme-pipeline/episteme_pipeline/phases/phase6_theorynet/runner.py#L149-L213):
```python
for rel_batch in batched(theory_net.relations, 500):
    batch_list = list(rel_batch)
    await self.graph_store.upsert_theory_relations(batch_list)
    relations_updated += len(batch_list)
...
artifacts = [
    build_theory_atom_artifact(
        atom,
        run_id=context.run_id,
        phase_name=self.name,
        method="phase6.theorynet",
    )
    for atom in theory_net.atoms
]
artifacts.extend(
    build_theory_relation_artifact(
        rel,
        run_id=context.run_id,
        phase_name=self.name,
        method="phase6.theorynet",
    )
    for rel in theory_net.relations
)
return ArtifactCollection(artifacts)
```
And in `TheoreticalEnrichmentRunner.run()` (`post_processing/theoretical_enrichment/runner.py#L381-L383`), use `await self.graph_store.upsert_theory_relations(list(batch))` on the enriched `TheoryRelation` domain objects.

---

## 4. Acceptance Criteria

- [ ] Round-trip property tests verify `Codec.to_domain(Codec.to_payload(x)) == x` for `L1Document`, `L1Chunk`, `L2Entity`, `L2Triple`, `TheoryAtom`, and `TheoryRelation`.
- [ ] `Phase4EntityMaturationRunner` preserves `matured_entity.source_chunk_ids` across `Phase2ArtifactsView` and `ArtifactGraphProjector`.
- [ ] `Phase6Runner.run()` increments `relations_updated` and returns updated `TheoryAtomArtifact` and `TheoryRelationArtifact` envelopes consumed by `TheoreticalEnrichmentRunner`.
- [ ] `TheoreticalEnrichmentRunner` persists enriched relations via `upsert_theory_relations` without dropping D-QBAF edge properties.
