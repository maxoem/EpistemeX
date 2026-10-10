# Decision Engines Reference

### AutoDecisionEngine

Default client for provisioning a decision engine backend (the refactor of the original `JevClient`).

::: episteme_pipeline.decision.jev_client.AutoDecisionEngine
    options:
      show_root_heading: false
      show_root_toc_entry: false

### LayaDecisionEngine

Apple Silicon (MLX) decision engine backend.

::: episteme_pipeline.decision.jev_client.LayaDecisionEngine
    options:
      show_root_heading: false
      show_root_toc_entry: false

### MockJevDecisionEngine

In-memory deterministic decision engine used for testing.

::: episteme_pipeline.decision.mock.MockJevDecisionEngine
    options:
      show_root_heading: false
      show_root_toc_entry: false

### ObservableDecisionEngine

Decorator adding decision audit/observability on top of an underlying decision engine.

::: episteme_pipeline.decision.observable.ObservableDecisionEngine
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Modal Resolvers

Modal resolvers fuse modality evidence, capturing fusion mode, fusion $\alpha$, epistemic status priors, and
underlying decision engine instances.

### StructuralistModalResolver

::: episteme_pipeline.decision.modal_resolver.StructuralistModalResolver
    options:
      show_root_heading: false
      show_root_toc_entry: false

### DecisionEngineModalResolver

::: episteme_pipeline.decision.modal_resolver.DecisionEngineModalResolver
    options:
      show_root_heading: false
      show_root_toc_entry: false

### HybridModalResolver

::: episteme_pipeline.decision.modal_resolver.HybridModalResolver
    options:
      show_root_heading: false
      show_root_toc_entry: false
