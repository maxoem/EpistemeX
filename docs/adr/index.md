# Architecture Decision Records (ADR)

This folder contains Architecture Decision Records (ADRs) documenting important design decisions taken during the
project. ADRs capture the context, the decision, alternatives considered, and the rationale.

## Convention

- Files are named with a numeric prefix and short slug: `0001-use-neo4j-for-graph.md`
- Use the template in `../templates/adr/adr_template.md` to create new ADRs.

## Purpose

- Provide a historical trail of major architectural choices and their reasons
- Support research reproducibility
- Help future maintainers understand why decisions were made
- Prevent repeated discussions on settled issues

## Documentation Style: Diátaxis

We follow the **Diátaxis Framework** for our documentation, including ADRs. This ADR (0008) explains our approach:

- **Explanation**: ADRs are primarily "explanation" content - they provide context and understanding
- **Style**: Clear, systematic, focused on the "why" behind decisions
- **Structure**: Context → Decision → Alternatives → Consequences

Learn more about our documentation
approach: [ADR 0008: Diátaxis Documentation Framework](0008-diataxis-documentation-framework.md)

## Records

### Recent Changes

- **0019** - TypeSafe Jev Client Implementation, System 1 Adapters, and Decision Observability (2026-10-01)
- **0018** - Core Decision Engine Architecture, Contracts, and Composition Root (2026-10-01)
- **0017** - Explicit Batch Contracts, Cypher UNWIND Bulk I/O, and Decoupled Embedding Operations (2026-08-18)
- **0016** - Phase 3 Within-Phase Checkpointing, Atomic Batch Recovery, and Poison-Pill Quarantine (2026-09-12)
- **0015** - Post-Processing Theoretical Enrichment and Tenability Evaluation (2026-09-08)
- **0014** - Deterministic Identity Diffing and Progression Workbench (2026-09-08)
- **0013** - Per-Run Neo4j Credentials and Automatic Graph Fallback (2026-09-07)
- **0012** - Phase Configuration Redesign, Staged Epistemic Pipeline Flow, and Langfuse Governance (2026-09-07)
- **0011** - Declarative Graph Metrics Framework, Async Lifecycles, and Gradual Strength Semantics (2026-09-07)
- **0010** - Dual-Driver Graph Preview (Artifact Store vs. Live Neo4j) and Calculation Overlays (2026-09-07)
- **0009** - SOTA Dual-Memory Architecture & Episodic Working Memory (2026-08-05)
- **0008** - Diátaxis Documentation Framework (2026-06-23)
- **0007** - TF Structural Correspondence
- **0006** - QBAF Mapping Deferred
- **0005** - Two-Pass Fusion Strategy
- **0004** - ACC Outputs Triples Single Pass
- **0003** - Coreference Absorbed Into Fusion
- **0002** - TAG Reranker Global Relation Extraction
- **0001** - Neo4j Async Graph Backend

## Related Documentation

- [System Architecture Overview](../architecture/overview.md) - Software architect's overview of technical stack,
  layers, and topology
- [Artifact and Run Model](../architecture/artifact_run_model.md) - Run manifests, artifact envelopes, and execution lifecycle
- [Concepts](../concepts/index.md) - Theoretical foundations
- [API Reference](../reference/pipeline.md) - Technical specifications


