# Configure Hermeneutic Refinement & Deficit Detection

This guide shows how to enable bounded closed-loop refinement, tune deficit detection thresholds and System 1 gating parameters, and inspect emitted `EpistemicDeficitArtifact` signals.

---

## 1. Enable Bounded Closed-Loop Refinement

Closed-loop refinement is opt-in (`max_refinement_cycles = 0` by default) so strictly feed-forward runs retain identical manifest and prompt fingerprints. Set `max_refinement_cycles` between `1` and `5` on `PipelineConfig.refinement`:

```python
from episteme_pipeline.config import HermeneuticRefinementConfig, PipelineConfig

config = PipelineConfig(
    refinement=HermeneuticRefinementConfig(
        max_refinement_cycles=2,
        max_deficits_per_cycle=20,
        # Deterministic deficit detector thresholds
        enthymeme_min_centrality=0.05,
        polysemy_volatility_threshold=0.25,
        polysemy_edge_tenability_threshold=0.50,
        polysemy_ambiguity_similarity_threshold=0.82,
        ungrounded_local_tenability_threshold=0.50,
        # System 1 DecisionEngine triage & audit controls
        use_decision_engine_gating=True,
        decision_confidence_threshold=0.70,
        conformal_alpha=0.10,
        stochastic_audit_rate=0.05,
        # Handler enable flags
        enable_theory_guided_premise_recovery=True,
        enable_targeted_concept_split=True,
        enable_localized_axiom_grounding=True,
    )
)
```

---

## 2. Inspect Detected Deficits and Refinement Outputs

After execution, hydrate [`EpistemicDeficitArtifactsView`](../reference/artifacts.md) from the returned `ArtifactCollection` to inspect detected deficits and active (non-retired) entities:

```python
from episteme_pipeline.artifacts.execution import EpistemicDeficitArtifactsView

view = EpistemicDeficitArtifactsView.from_collection(collection)

for deficit in view.to_domain_deficits():
    print(
        f"[pass={deficit.refinement_pass}] {deficit.deficit_kind.value} "
        f"{deficit.deficit_id} severity={deficit.severity:.3f} :: {deficit.rationale}"
    )
```

- Active views (`Phase4ArtifactsView`, `EpistemicStateView`) automatically hide retired parent entities and stale mentions created during `POLYSEMY_COLLISION` concept splits (`is_retired=True`).
- Full pass-0 and pass-$r$ provenance remains intact in `collection.history` tagged with `provenance.refinement_pass` and `provenance.deficit_artifact_id`.

---

## 3. Inject Custom Detectors or Handlers

To emit deficits inside standalone `Phase6Runner` or `TheoreticalEnrichmentRunner` invocations or swap in a custom `EpistemicDeficitDetector` / `HermeneuticRefinementCoordinator`, pass instances into `Pipeline.for_task(...)`:

```python
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.refinement import TheoryNetDeficitDetector

detector = TheoryNetDeficitDetector(config=config.refinement, schema=config.graph_schema)

pipeline = Pipeline.for_task(
    task="knowledge_graph",
    config=config,
    llm=llm,
    embedding_model=embed_model,
    decision_engine=decision_engine,
    deficit_detector=detector,
)
```

See [Deficit Graph Analysis & Closed-Loop Hermeneutic Refinement](../workflow/post_processing/hermeneutic_refinement.md) for the exact graph metrics, trigger conditions, and severity scoring formulas.
