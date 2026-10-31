# Artifacts Reference

Documentation of the artifact system used for persisting and reusing pipeline outputs.

## Artifact System Overview

The artifact system provides persistent storage and retrieval of intermediate pipeline results, enabling efficient reuse
and resumption of work.

## Core Components

### ArtifactCollection

Container for all artifacts produced by a pipeline phase.

::: episteme_pipeline.artifacts.execution.ArtifactCollection
    options:
      show_root_heading: false
      show_root_toc_entry: false

### ArtifactExecutionContext

Context information for artifact processing.

::: episteme_pipeline.artifacts.execution.ArtifactExecutionContext
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Incremental Hydration & Retention

Declarative hydration and retention scope for incremental corpus evolution.

### IncrementalRetentionScope

::: episteme_pipeline.artifacts.execution.IncrementalRetentionScope
    options:
      show_root_heading: false
      show_root_toc_entry: false

### ArtifactHydrator

::: episteme_pipeline.artifacts.execution.ArtifactHydrator
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Hydration Results

::: episteme_pipeline.artifacts.execution.Phase1HydrationResult
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.execution.Phase2HydrationResult
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.execution.Phase3HydrationResult
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.execution.Phase4HydrationResult
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Storage Implementation

### JsonArtifactStore

Default artifact storage using JSON serialization.

::: episteme_pipeline.artifacts.store.JsonArtifactStore
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Artifact Types

### Entity Artifacts

Storage format for entity extraction results.

::: episteme_pipeline.artifacts.models.EntityMentionArtifact
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.models.LinkedEntityArtifact
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Relation Artifacts

Storage format for relationship extraction results.

::: episteme_pipeline.artifacts.models.LocalRelationArtifact
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.models.GlobalRelationArtifact
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Argument Artifacts

Storage format for argument mining results.

::: episteme_pipeline.artifacts.models.TheoryAtomArtifact
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.models.TheoryRelationArtifact
    options:
      show_root_heading: false
      show_root_toc_entry: false

### Fusion Artifacts

Storage format for entity alignment results.

::: episteme_pipeline.artifacts.models.FusionDecisionArtifact
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.artifacts.models.CanonicalizationArtifact
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Content Addressing

Artifacts are stored using content-addressed identifiers to enable automatic deduplication.

### Fingerprinting

::: episteme_pipeline.runs.fingerprints.stable_fingerprint
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.runs.fingerprints.fingerprint_method
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.runs.fingerprints.fingerprint_phase_config
    options:
      show_root_heading: false
      show_root_toc_entry: false

::: episteme_pipeline.runs.fingerprints.fingerprint_existing_sources
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Run Manifests

Tracking execution metadata and artifact lineage.

### RunManifest

::: episteme_pipeline.runs.models.RunManifest
    options:
      show_root_heading: false
      show_root_toc_entry: false

### ExecutionResult

::: episteme_pipeline.runs.models.ExecutionResult
    options:
      show_root_heading: false
      show_root_toc_entry: false

## Artifact Reuse

Mechanisms for detecting and reusing equivalent artifacts.

### InvalidationDecision

::: episteme_pipeline.runs.models.InvalidationDecision
    options:
      show_root_heading: false
      show_root_toc_entry: false

### ResumePoint

::: episteme_pipeline.runs.models.ResumePoint
    options:
      show_root_heading: false
      show_root_toc_entry: false
