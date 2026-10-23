# Pipeline Implementation Workflow

This section documents how theoretical and epistemological concepts are implemented in the Python pipeline code.

---

## Pipeline Execution Phases

The Episteme pipeline executes eight sequential phases, each building deterministically on the outputs of preceding
phases:

### [Phase 1: Data Foundation](1_data_foundation/)

**Purpose**: Source document ingestion, format conversion (TeX, Markdown), and deterministic chunking with full
provenance tracking.  
**Theoretical Basis**: Layer 1 (Empirical Manifold)  
**Key Concepts**: Structural chunking (ToC/Header-aware), exact tokenization, stable content hashing, `Document` $\to$
`Chapter` $\to$ `Chunk` graph hierarchy.

### [Phase 2: Entity Discovery](2_entity_discovery/)

**Purpose**: Named entity recognition, within-chunk local coreference resolution, entity linking, and episodic working
memory.  
**Theoretical Basis**: Layer 2 (Deterministic Ontology)  
**Key Concepts**: Textual envelopes ($T_n$), Table-of-Contents structural anchors, RAM-only state machine with boundary
eviction resets, deterministic entity IDs.

### [Phase 3: Global Relation Extraction](3_relation_extraction/)

**Purpose**: Cross-document semantic relationship identification.  
**Theoretical Basis**: Global relations in Heterogeneous Information Networks (HIN)  
**Key Concepts**: Dense candidate retrieval (MIPS bi-encoder), cross-encoder relational reranking, constrained LLM
triple decoding, TAG subgraph envelopes.

### [Phase 3b: Latent Graph Consolidation](3b_consolidation/)

**Purpose**: Non-generative mathematical sweep over dense vectors and 1-hop relation signatures to resolve parallel
entity duplicates.  
**Theoretical Basis**: Latent topological invariance  
**Key Concepts**: Pairwise cosine similarity matrix, Jaccard relation-overlap verification, Clique-constrained clustering,
canonical entity election.

### [Phase 4: Entity Maturation (Batch Synthesis)](4_entity_maturation/)

**Purpose**: Canonical entity description synthesis and epistemic drift mitigation.  
**Theoretical Basis**: Stage 2 Maturation / Topological Invariance / Description Versioning  
**Key Concepts**: Mention envelope retrieval (`EXTRACTED_FROM`), geometric centroid calculation in latent space, Top-K
representative selection, LLM-based description fusion.

### [Phase 4b: Argument Mining](4_argument_mining/)

**Purpose**: Argumentative discourse unit (ADU) segmentation, classification (ACC), local relation extraction,
cross-chunk stance classification (ARC), and Theoriennetz (TF) mapping.  
**Theoretical Basis**: Computational Argumentation & Epistemic Justification (ADR 0004, ADR 0007)  
**Key Concepts**: Claim/Premise extraction, single-pass ACC+ARI classification, TAG-based ARC cross-chunk relations,
structural correspondence.

### [Phase 5: Alignment & Theory Fusion](5_inter_document_argument_web/)

**Purpose**: Cross-document argument component clustering and theory-level community detection.  
**Theoretical Basis**: Theory graph fusion (ADR 0005)  
**Key Concepts**: Cosine similarity clustering of argument components, representative election for Key Point Analysis,
hierarchical Leiden community detection.

### [Phase 6: TheoryNet Projection](6_theorynet/)

**Purpose**: Formal TheoryNet projection, argument acceptability, and empirical content / $Z_1$ connectivity
verification.  
**Theoretical Basis**: Formal TheoryNet ($\rho, \alpha$) & Quaternary Bipolar Argumentation Frameworks (QBAF)  
**Key Concepts**: Plausibility mapping, relation confidence/weight propagation, bipartite empirical-theoretical
partitioning ($A$-atoms vs. $B$-atoms).

---

## Post-Processing & Analytical Evaluation

Post-processing modules execute after the core sequential phases (Phases 1–6) to evaluate, enrich, and validate the
constructed graph without breaking domain independence:

### [Post-Processing System](post_processing/index.md)

**Purpose**: Decoupled lifecycle orchestration, cumulative artifact aggregation, and pluggable runner interface.  
**Theoretical Basis**: Metatheoretical separation of domain-agnostic extraction ($\Phi_{\text{gen}}$) from specific
analytical evaluation ($\Phi_{\text{spec}}$) (ADR 0015).  
**Key Concepts**: `PhaseRunner` protocol, `ArtifactCollection` cumulative filtering, dual persistence (artifacts +
Neo4j), event telemetry.

### [Theoretical Enrichment & Tenability Evaluation](post_processing/theoretical_enrichment.md)

**Purpose**: Structuralist model enrichment ($\Phi_{\text{spec}}$) and continuous tenability optimization
($TS_{\text{local}}, TS_{\text{edge}}$).  
**Theoretical Basis**: Structuralist Metatheory of Science
([Stegmüller, 1976]; [Balzer et al., 1987]; [Schurz, 2024]).  
**Key Concepts**: Bourbaki uniformities, admissible blurs ($\mathcal{A}$), AST-based safe core laws ($M$), dynamic
theory induction, anomaly detection.

---

## Architecture Overview

```mermaid
flowchart TD
    P1["Phase 1: Data Foundation<br>(Document/Chapter/Chunk)"] --> P2["Phase 2: Entity Discovery<br>(L2 Entities, Local Triples, Episodic RAM)"]
    P2 --> P3["Phase 3: Global Relations<br>(Dense Retrieval + Cross-Encoder)"]
    P3 --> P3b["Phase 3b: Latent Consolidation<br>(Clique-Constrained + Jaccard Sweep)"]
    P3b --> P4["Phase 4: Entity Maturation<br>(Centroid Synthesis & Stabilization)"]
    P4 --> P4b["Phase 4b: Argument Mining<br>(ADU, ACC+ARI, ARC, TF Mapping)"]
    P4b --> P5["Phase 5: Alignment & Theory Fusion<br>(Argument Clustering & Leiden Communities)"]
    P5 --> P6["Phase 6: TheoryNet Projection<br>(Plausibility & Empirical Content Bounds)"]
    P6 --> G[("Theory Graph in Neo4j")]
    G --> H["Post-Processing Suite (Phi_spec)"]
    H --> H1["Theoretical Enrichment & Tenability"]
    H --> H2["Analytical Solvers & Epistemetrics"]
```

---

## Software Design Patterns Across Workflow Phases

To keep the pipeline extensible for rapid research iteration while serving as a readable knowledge project, each phase applies canonical software design patterns defined in **[Design Patterns, Clean Code & Architectural Standards](../architecture/design_patterns_and_standards.md)**:

| Phase / Subsystem | Primary Design Patterns Applied | Core Ports & Abstractions (`episteme_pipeline/protocols/`) |
| :--- | :--- | :--- |
| **Orchestrator (`Pipeline`)** | **Composition Root / Facade**, **Decorator (`ensure_*`)**, **Visitor (`Fingerprintable`)** | `PhaseRunner[ViewT]`, `Fingerprintable`, `ArtifactViewProtocol[ViewT]` |
| **Phase 1: Data Foundation** | **Adapter Pattern** (`TexAdapter`, `MarkdownAdapter`), **Strategy / Chain of Responsibility** (`AutoToCParser`) | `DataSourceAdapter`, `ToCParserStrategy`, `EmbeddingModel` |
| **Phase 2: Entity Discovery** | **Strategy Pattern** (`NERExtractor`, `EntityLinker`), **Calibrated Cascade** (`CascadingEntityLinker`, `JevGleaningGate`), **Stateful Reducer** (`EpisodicWorkingMemoryManager`) | `NERExtractor`, `EntityLinker`, `GleaningStoppingOracle`, `WorkingMemoryState` |
| **Phase 3: Global Relations** | **Retrieve $\to$ Rerank $\to$ Decode Pipeline**, **Calibrated Cascade** (System 1 pair gating), **Unit-of-Work Batch Checkpointing** (`ADR-0016`) | `GlobalRelationExtractor`, `RelationReranker`, `PhaseCheckpointStore` |
| **Phase 3b: Consolidation** | **Strategy Pattern** (`InstanceFusion`), **Conformal Triage Gate** (borderline verification & canonical surface election) | `InstanceFusion`, `DecisionEngine` |
| **Phase 4: Entity Maturation** | **Two-Stage Batch Synthesis** (latent geometric centroid + top-$K$ LLM synthesis) | `PhaseRunner[Phase3ArtifactsView]`, `StructuredLLM`, `EmbeddingModel` |
| **Phase 4b: Argument Mining** | **Strategy Pattern** (`ADUSegmenter`, `ACCClassifier`, `ARCClassifier`, `ModalStrengthResolver`), **Calibrated Cascade** (`CascadingACCClassifier`, `CascadingARCClassifier`) | `ADUSegmenter`, `ACCClassifier`, `ARCClassifier`, `ModalStrengthResolver` |
| **Phase 5: Theory Fusion** | **Strategy Pattern** (`ArgumentClustering`, `TheoryFusion`), **Conformal Triage Gate** (`InterDocumentClusterVerifier`) | `ArgumentClustering`, `TheoryFusion`, `DecisionEngine` |
| **Phase 6: TheoryNet** | **Projector / Builder Pattern** (`TheoryNetProjector`), **Topology-Adaptive Solver Strategy** (DAG closed-form vs. cyclic ODE QBAF) | `TheoryNetProjector`, `ModalStrengthResolver` |
| **Post-Processing ($\Phi_{\text{spec}}$)** | **Open/Closed Plugin Runner** (`PhaseRunner[ViewT]`), **Strategy Pattern** (`TheoryInducer`, `TheoryProjector`, `TenabilitySolver`) | `PhaseRunner`, `TheoryProjector`, `TenabilitySolver` |

---

## Event System & Observability

The pipeline uses an event-driven architecture for telemetry and monitoring:

- [Event System & Telemetry](../observability/events.md) - Event definitions and usage
- [Langfuse Integration](../observability/langfuse.md) - Real-time LLM tracing and token monitoring

## Configuration

All phases are configured through `episteme_pipeline/config.py`. See:

- [Configuration Guide](../getting_started/configuration.md) - Setup and environment configuration
- [Customizing Configuration](../how_to/customize_config.md) - Advanced phase overrides and custom prompts

---

## Related Documentation

- **Architecture & Standards**: [Design Patterns, Clean Code & Architectural Standards](../architecture/design_patterns_and_standards.md) - Canonical engineering patterns and anti-pattern guide
- **Theory**: [Concepts](../concepts/) - Mathematical and epistemological foundations
- **API**: [Reference](../reference/) - Technical API documentation and contracts
- **Decisions**: [ADRs](../adr/) - Architectural Decision Records

