# Configuration Reference

Detailed documentation of all configuration options available in Episteme.

## PipelineConfig

The top-level configuration object that contains settings for all pipeline components.

::: episteme_pipeline.config.PipelineConfig
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Execution Configuration

Controls overall pipeline execution behavior and artifact management.

::: episteme_pipeline.config.ExecutionConfig
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Decision Engine Configuration

Controls System 1 calibrated decision engine routing, provider selection, confidence thresholds, and conformal prediction coverage.

::: episteme_pipeline.config.DecisionEngineConfig
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Phase-Specific Configurations

### Phase 1 Configuration

Settings for the data foundation phase including document processing and chunking.

::: episteme_pipeline.config.Phase1Config
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 2 Configuration

Settings for entity discovery including NER prompts and entity linking parameters.

::: episteme_pipeline.config.Phase2Config
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 3 Configuration

Settings for relation extraction including global relation discovery parameters.

::: episteme_pipeline.config.Phase3Config
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 3b Configuration

Settings for latent graph consolidation including distance and similarity thresholds.

::: episteme_pipeline.config.Phase3bConfig
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 4: Entity Maturation Configuration

Settings for entity maturation including centroid selection and description synthesis parameters.

::: episteme_pipeline.config.Phase4EntityMaturationConfig
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 4: Argument Mining Configuration

Settings for argument mining including ADU segmentation and classification parameters.

::: episteme_pipeline.config.Phase4Config
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 5 Configuration

Settings for alignment fusion including entity matching thresholds.

::: episteme_pipeline.config.Phase5Config
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 6 Configuration

Settings for TheoryNet materialization, D-QBAF gradual semantics, and intensional scoping.

::: episteme_pipeline.config.Phase6Config
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Theoretical Enrichment Configuration

Settings for structuralist Theory-Element induction and tenability evaluation post-processing.

::: episteme_pipeline.config.TheoreticalEnrichmentConfig
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Hermeneutic Refinement Configuration

Settings for bounded top-down epistemic deficit detection and localized refinement (`ISSUE-053`).

::: episteme_pipeline.config.HermeneuticRefinementConfig
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Graph Schema Configuration

Defines the expected structure and constraints for the constructed theory graph.

::: episteme_pipeline.schema.default_schema.SchemaConfig
    options:
      show_root_heading: false
      show_root_toc_entry: false
