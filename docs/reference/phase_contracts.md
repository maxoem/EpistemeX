# Phase Contracts

Documentation of the input/output contracts and interfaces for each pipeline phase.

## Common Interfaces

### PhaseRunner

Base interface implemented by all pipeline phases.

::: episteme_pipeline.protocols.phase_runner.PhaseRunner
    options:
      show_root_heading: false
      show_root_toc_entry: false

### PipelineInput

Standard input structure for pipeline execution.

::: episteme_pipeline.contracts.phase_contracts.PipelineInput
    options:
      show_root_heading: false
      show_root_toc_entry: false

### EpistemicCurationLedger

Persistent Human-in-the-Loop (HITL) curation ledger for expert constraints and relation overrides.

::: episteme_pipeline.contracts.phase_contracts.EpistemicCurationLedger
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.contracts.phase_contracts.RelationOverride
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Phase 1: Data Foundation

Handles document parsing and chunking operations.

### Input Contract

Accepts raw document paths and bibliographic information.

### Output Contract

Produces chunked text representations with provenance metadata.

::: episteme_pipeline.contracts.domain.L1Chunk
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.contracts.domain.L1Document
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Phase 2: Entity Discovery

Extracts and types entities from chunked text.

### Domain Objects

::: episteme_pipeline.contracts.domain.L2Entity
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Phase 3: Relation Extraction

Identifies relationships between entities.

### Domain Objects

::: episteme_pipeline.contracts.domain.L2Triple
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Phase 3b: Latent Graph Consolidation

Performs a fast mathematical sweep over dense vectors and 1-hop relation edge Jaccard similarity to merge duplicate
Layer 2 entity nodes before Phase 4.

### Phase Runner

::: episteme_pipeline.phases.phase3b_consolidation.Phase3bLatentConsolidationRunner
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Phase 4: Entity Maturation

Synthesizes canonical descriptions and resolves entity-level epistemic drift.

### Phase Runner

::: episteme_pipeline.phases.phase4_entity_maturation.Phase4EntityMaturationRunner
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Phase 4: Argument Mining

Constructs argumentative structures from text components.

### Domain Objects

::: episteme_pipeline.contracts.domain.TheoryAtom
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Phase 5b: Theory Fusion & Argument Clustering

Groups semantically equivalent argument components and performs theory-level graph clustering.

### Phase Runner

::: episteme_pipeline.phases.phase5_fusion.argument_web.Phase5ArgumentWebRunner
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Artifact Views

Standardized views of phase outputs for downstream consumption.

### Phase 1 Artifacts

::: episteme_pipeline.artifacts.execution.Phase1ArtifactsView
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 2 Artifacts

::: episteme_pipeline.artifacts.execution.Phase2ArtifactsView
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 3 Artifacts

::: episteme_pipeline.artifacts.execution.Phase3ArtifactsView
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Phase 4 Artifacts

::: episteme_pipeline.artifacts.execution.Phase4ArtifactsView
    options:
      show_root_heading: false
      show_root_toc_entry: false

