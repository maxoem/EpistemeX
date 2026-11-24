---
template: home.html
title: Episteme — Theory Graph Language Pipeline
description: SOTA theory graph construction and evaluation platform for scientific literature
hide:
  - navigation
  - toc
---

# Episteme: Theory Graph Language Pipeline

Welcome to the documentation for _Episteme_, a cutting-edge pipeline for constructing theory graphs from scientific
literature.

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![Status](https://img.shields.io/badge/Status-Research-orange.svg)]()

---

## What is Episteme?

_Episteme_ is a research library designed to construct **theory graphs**—structured representations of theoretical
frameworks—from academic texts in German and English. While designed for computational epistemologists, NLP researchers,
and philosophers of science, the pipeline itself focuses on an agnostic and approach for knowledge graph construction
and may serve different use cases as well.

Our pipeline abstracts unstructured scholarly documents into queryable semantic structures. Unlike traditional knowledge
graphs that focus on factual relationships, theory graphs capture the conceptual and argumentative structures that
underpin scientific theories. The pipeline transforms unstructured scholarly documents into a property graph, that can be stored in any graph database of your choosing. The episteme-pipeline produced a three-layer architecture:

1. **Layer 1 (Provenance Embedding)**: Original documents embedded and queryable in the graph.
2. **Layer 2 (Knowledge Graph)**: Abstraction from original sources as a knowledge graph.
3. **Layer 3 (Theory Framework)**: Higher-level theoretical constructs and argumentative structures.

---

## Documentation Pillars

The documentation is organized into six foundational pillars designed to serve researchers, system architects, and software engineers:

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Getting Started & Tooling__

    ---

    Zero-friction onboarding, environment configuration, step-by-step first run, and the interactive **Episteme Studio workbench**.

    - [Quickstart & Setup](getting_started/quick_start.md){ data-preview }
    - [Episteme Studio Workbench](getting_started/studio.md){ data-preview }
    - [How-To Guides](how_to/run_pipeline.md){ data-preview }

-   :material-microscope:{ .lg .middle } __Research & Epistemology__

    ---

    Formal graph models ($\mathcal{G}_{\text{TheoryNet}}$) and structuralist philosophy of science (*Wissenschaftstheorie*).

    - [Conceptual Foundations](concepts/index.md){ data-preview }
    - [Formal Graph Model](concepts/formal_graph_model.md){ data-preview }
    - [Theory-Nets & Topologies](concepts/theory_nets_and_topologies.md){ data-preview }
    - [Project & Research Roadmap](roadmap.md){ data-preview }

-   :material-pillar:{ .lg .middle } __Architecture & Decisions__

    ---

    System-wide engineering trade-offs, dual-store graph projection, cache invalidation state machines, and **18 Architecture Decision Records (ADRs)**.

    - [Architecture Overview](architecture/overview.md){ data-preview }
    - [Design Patterns & Standards](architecture/design_patterns_and_standards.md){ data-preview }
    - [Artifact & Run Model](architecture/artifact_run_model.md){ data-preview }
    - [Invalidation & Resume](architecture/invalidation_and_resume.md){ data-preview }
    - [Runtime & Complexity Analysis](architecture/runtime_analysis.md){ data-preview }
    - [ADR Register](adr/index.md){ data-preview }

-   :material-cog-sync:{ .lg .middle } __Pipeline & Engineering__

    ---

    Production-grade, deterministic 5-phase extraction pipeline, theoretical enrichment post-processing, and distributed Langfuse tracing.

    - [Pipeline Workflow Overview](workflow/index.md){ data-preview }
    - [Phase 1–5 Execution](workflow/1_data_foundation/index.md){ data-preview }
    - [Theoretical Enrichment](workflow/post_processing/index.md){ data-preview }
    - [Telemetry & Observability](observability/events.md){ data-preview }

-   :material-chart-bell-curve-cumulative:{ .lg .middle } __Epistemetrics & Validation__

    ---

    Standalone quantitative evaluation library measuring empirical creativity, theoretical unification, tacking-paradox homogeneity, and Lakatosian dynamics.

    - [Epistemetrics Suite Overview](concepts/theory/metrics/index.md){ data-preview }
    - [Structural Topology Metrics](concepts/theory/metrics/structural_topology/index.md){ data-preview }
    - [Epistemic Coherence & Harmony](concepts/theory/metrics/epistemic_coherence/system_coherence.md){ data-preview }
    - [Empirical Metrics & Validation](research/metrics.md){ data-preview }

-   :material-code-json:{ .lg .middle } __Reference & Contracts__

    ---

    Strict Pydantic phase I/O boundaries, Neo4j Cypher property graph schemas, Python APIs, and the unified bilingual conceptual glossary.

    - [Phase Contracts](reference/phase_contracts.md){ data-preview }
    - [Graph Schema Reference](reference/schema.md){ data-preview }
    - [Pipeline API Reference](reference/pipeline.md){ data-preview }
    - [Glossary](concepts/glossary.md){ data-preview }

</div>

---

## System Architecture & Processing Flow

![Episteme System Architecture Overview](../paper/graphics/architecture/out/system_architecture_overview.png)



