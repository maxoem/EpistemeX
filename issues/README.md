# Issue & Feature Specification Registry

This directory contains the structured engineering backlog, feature specifications, and research issues for **Episteme**
(`episteme-pipeline`, `epistemetrics`, and `episteme-studio`).

The issues are decomposed from the master functional specification ([
`requirements_glp_project.md`](issues/shared/requirements_glp_project.md)) and historical visual mapping audit ([
`requirements_visual_mapping.md`](issues/shared/requirements_visual_mapping.md)), realigned with the project's strategic
roadmap in [docs/roadmap.md](docs/roadmap.md).

---

## Directory Organization

```
issues/
├── README.md                                  # Master index and status registry
├── shared/                                    # Historical source specifications
│   ├── requirements_glp_project.md            # Master feature specification report
│   └── requirements_visual_mapping.md         # V0.1/V0.2 triage evaluation
├── 01-visualization/                          # Canvas rendering, layouts, and projections
├── 02-structuralist-engine/                   # Model-theoretic decomposition & tenability
├── 03-epistemic-metrics/                      # Epistemetrics algorithms, virtues & QBAF solvers
├── 04-diachronic-dynamics/                    # Theory reduction, Kuhn-loss & temporal dynamics
├── 05-hitl-and-orchestration/                 # Human curation, staging & decision auditing
├── 06-discovery-and-querying/                 # Hybrid search, LBD Swanson linking & schema design
├── 07-evaluation-harness/                     # Benchmark integrity, alignment & hallucination scoring
├── 08-pipeline-enhancements/                  # Macro community synthesis & chunking hygiene
├── 09-evaluation-workbench/                   # User analytics, coupled views & Studio API endpoints
└── 10-decision-engine-and-jev/                # TypeSafe Jev, System 1 decision engine & dynamic gating
```

---

## Master Active Issues Index

| Issue ID                                                                                               | Title                                                       | Domain / Category        | Target Package                          | Roadmap Horizon | Priority | Status        |
|:-------------------------------------------------------------------------------------------------------|:------------------------------------------------------------|:-------------------------|:----------------------------------------|:----------------|:---------|:--------------|
| [**ISSUE-001**](01-visualization/ISSUE-001-poset-and-spectral-layouts.md)                              | Topological Poset & Spectral Graph Layouts                  | 01-Visualization         | `episteme-studio`                       | Horizon 1       | Medium   | `Open`        |
| [**ISSUE-002**](01-visualization/ISSUE-002-multigraph-encoding-and-projection-cones.md)                | Multigraph Parallel Edges & Layer Projection Cones          | 01-Visualization         | `episteme-studio`                       | Horizon 1       | Low      | `Open`        |
| [**ISSUE-003**](02-structuralist-engine/ISSUE-003-structuralist-quintuple-projections.md)              | Structuralist Quintuple Projections ($M_p, GC, GL$)         | 02-Structuralist         | `episteme-studio` / `episteme-pipeline` | Horizon 1       | High     | `Open`        |
| [**ISSUE-004**](02-structuralist-engine/ISSUE-004-interactive-tenability-blur-slider.md)               | Real-Time Tenability Blur Slider ($\delta^*$)               | 02-Structuralist         | `episteme-studio`                       | Horizon 1       | Medium   | `Open`        |
| [**ISSUE-005**](02-structuralist-engine/ISSUE-005-sneedian-theoreticity-and-ramseyification.md)        | Sneedian $T$-Theoreticity & Ramsey Verification             | 02-Structuralist         | `episteme-pipeline` / `epistemetrics`   | Horizon 3       | Low      | `Research`    |
| [**ISSUE-006**](03-epistemic-metrics/ISSUE-006-novacek-hypothesis-virtues-suite.md)                    | Nováček Hypothesis Virtues Suite                            | 03-Epistemic Metrics     | `epistemetrics` / `episteme-studio`     | Horizon 1 & 2   | High     | `In Progress` |
| [**ISSUE-007**](03-epistemic-metrics/ISSUE-007-pareto-frontier-analytics-view.md)                      | Pareto Frontier Multi-Virtue Visualizer                     | 03-Epistemic Metrics     | `episteme-studio`                       | Horizon 2       | Medium   | `Open`        |
| [**ISSUE-008**](03-epistemic-metrics/ISSUE-008-extended-newman-centrality-metrics.md)                  | Extended Newman Centrality (Closeness, Katz, HITS)          | 03-Epistemic Metrics     | `epistemetrics` / `episteme-studio`     | Horizon 1       | Medium   | `Open`        |
| [**ISSUE-009**](03-epistemic-metrics/ISSUE-009-global-qbaf-solvers-and-thagardian-harmony.md)          | Global QBAF Solvers & Thagardian Harmony (ECHO)             | 03-Epistemic Metrics     | `epistemetrics` / `episteme-studio`     | Horizon 2       | High     | `Open`        |
| [**ISSUE-010**](04-diachronic-dynamics/ISSUE-010-theory-reduction-and-kuhn-loss-tracking.md)           | Theory Reduction Matrices ($\rho$) & Kuhn-Loss              | 04-Diachronic            | `episteme-pipeline` / `episteme-studio` | Horizon 3       | High     | `Research`    |
| [**ISSUE-011**](04-diachronic-dynamics/ISSUE-011-diachronic-timeline-and-terminology-drift.md)         | Diachronic Timeline Scrubber & Terminology Drift            | 04-Diachronic            | `episteme-studio`                       | Horizon 3       | Medium   | `Open`        |
| [**ISSUE-012**](05-hitl-and-orchestration/ISSUE-012-hitl-inline-curation-and-staging-editor.md)        | HITL Inline Curation & Staging Editor                       | 05-HITL & Orchestration  | `episteme-studio`                       | Horizon 1       | High     | `Open`        |
| [**ISSUE-013**](05-hitl-and-orchestration/ISSUE-013-retrieval-mips-and-rerank-decision-auditing.md)    | Retrieval MIPS & Rerank Decision Auditing                   | 05-HITL & Orchestration  | `episteme-studio` / `episteme-pipeline` | Horizon 1       | Medium   | `Open`        |
| [**ISSUE-014**](06-discovery-and-querying/ISSUE-014-neuro-symbolic-hybrid-search.md)                   | Neuro-Symbolic Hybrid Vector & Graph Search                 | 06-Discovery & Query     | `episteme-studio` / `episteme-pipeline` | Horizon 2       | High     | `Open`        |
| [**ISSUE-015**](06-discovery-and-querying/ISSUE-015-literature-based-discovery-swanson-linking.md)     | Literature-Based Discovery (Swanson $A$-$C$-$B$)            | 06-Discovery & Query     | `episteme-pipeline` / `episteme-studio` | Horizon 3       | Low      | `Research`    |
| [**ISSUE-016**](06-discovery-and-querying/ISSUE-016-neutral-contradiction-management-workspace.md)     | Neutral Contradiction Workspace ($\langle B, D, U \rangle$) | 06-Discovery & Query     | `episteme-studio` / `episteme-pipeline` | Horizon 3       | Medium   | `Research`    |
| [**ISSUE-017**](06-discovery-and-querying/ISSUE-017-visual-metamodel-and-schema-designer.md)           | Visual Metamodel & Ontology Schema Designer                 | 06-Discovery & Query     | `episteme-studio` / `episteme-pipeline` | Horizon 1 & 2   | Medium   | `Open`        |
| [**ISSUE-018**](07-evaluation-harness/ISSUE-018-gm-gbs-entity-aware-graph-alignment.md)                | Entity-Aware Graph BERTScore (GM-GBS) Evaluation            | 07-Evaluation Harness    | `episteme-pipeline`                     | Horizon 1       | Critical | `Superseded`  |
| [**ISSUE-019**](07-evaluation-harness/ISSUE-019-oep-graph-edit-distance-and-hallucination-scoring.md)  | Graph Edit Distance (OEP) & Hallucination Scoring           | 07-Evaluation Harness    | `episteme-pipeline`                     | Horizon 1       | High     | `Superseded`  |
| [**ISSUE-020**](07-evaluation-harness/ISSUE-020-extrinsic-retrieval-scorer-and-run-slice-isolation.md) | Extrinsic Retrieval Scorer Fix & Run Slice Isolation        | 07-Evaluation Harness    | `episteme-pipeline`                     | Horizon 1       | Critical | `Superseded`  |
| [**ISSUE-021**](07-evaluation-harness/ISSUE-021-theorynet-layer3-evaluation-and-baselines.md)          | TheoryNet (Layer 3) Benchmark Harness & Baseline Models     | 07-Evaluation Harness    | `episteme-pipeline` / `epistemetrics`   | Horizon 2       | High     | `Superseded`  |
| [**ISSUE-022**](08-pipeline-enhancements/ISSUE-022-hierarchical-leiden-community-summarization.md)     | Hierarchical Leiden Community Summarization & Synthesis     | 08-Pipeline Enhancements | `episteme-pipeline`                     | Horizon 2       | Medium   | `Open`        |
| [**ISSUE-023**](08-pipeline-enhancements/ISSUE-023-chunker-tokenization-and-provenance-hygiene.md)     | SemanticChunker Tokenization & Configurable Encodings       | 08-Pipeline Enhancements | `episteme-pipeline`                     | Horizon 1       | Low      | `Open`        |
| [**ISSUE-024**](07-evaluation-harness/ISSUE-024-scigraph-evaluation-methodology.md)                    | SciGraph Evaluation Methodology (Soft Matching & Querying)  | 07-Evaluation Harness    | `episteme-pipeline` / `epistemetrics`   | Horizon 1 & 2   | High     | `Superseded`  |
| [**ISSUE-025**](03-epistemic-metrics/ISSUE-025-model-theoretic-plausibility-score.md)                  | Model-Theoretic Plausibility Score ($p$) on Edges           | 03-Epistemic Metrics     | `epistemetrics` / `episteme-pipeline`   | Horizon 2       | Medium   | `Open`        |
| [**ISSUE-026**](09-evaluation-workbench/ISSUE-026-evaluation-graph-alignment-overlay-projection.md)    | Evaluation Graph Alignment Overlay & Visual Error Projection| 09-Evaluation Workbench  | `episteme-studio`                       | Horizon 1       | Critical | `Open`        |
| [**ISSUE-027**](09-evaluation-workbench/ISSUE-027-hitl-adjudication-queue-and-live-recalculation.md)   | HITL Borderline Adjudication Queue & Dynamic Re-evaluation  | 09-Evaluation Workbench  | `episteme-studio`                       | Horizon 1       | High     | `Open`        |
| [**ISSUE-028**](09-evaluation-workbench/ISSUE-028-confidence-calibration-reliability-diagrams.md)       | Confidence Calibration Diagnostics & Reliability Diagrams   | 09-Evaluation Workbench  | `episteme-studio`                       | Horizon 1 & 2   | High     | `Open`        |
| [**ISSUE-029**](09-evaluation-workbench/ISSUE-029-multimodal-grounding-evidence-inspection.md)         | Multi-Modal Deep Evidence Grounding & Bounding-Box Inspector| 09-Evaluation Workbench  | `episteme-studio`                       | Horizon 2       | Medium   | `Open`        |
| [**ISSUE-030**](09-evaluation-workbench/ISSUE-030-multi-run-leaderboard-and-pareto-frontier.md)         | Multi-Run Benchmark Leaderboard & Multi-Virtue Pareto       | 09-Evaluation Workbench  | `episteme-studio`                       | Horizon 2       | High     | `Open`        |
| [**ISSUE-031**](09-evaluation-workbench/ISSUE-031-adversarial-noise-robustness-stress-testing.md)       | Adversarial Noise Robustness Benchmarking & RDF Curves      | 09-Evaluation Workbench  | `episteme-studio`                       | Horizon 2       | Medium   | `Open`        |
| [**ISSUE-032**](09-evaluation-workbench/ISSUE-032-competency-query-retrieval-diagnostics.md)           | Downstream Competency Retrieval Per-Query Diagnostics       | 09-Evaluation Workbench  | `episteme-studio`                       | Horizon 1       | Medium   | `Open`        |
| [**ISSUE-033**](09-evaluation-workbench/ISSUE-033-benchmark-catalog-management-and-validation.md)      | Custom Benchmark Registration, Pre-Flight Linter & Export   | 09-Evaluation Workbench  | `episteme-studio`                       | Horizon 1 & 2   | Medium   | `Open`        |
| [**ISSUE-034**](09-evaluation-workbench/ISSUE-034-on-demand-evaluation-execution-and-streaming-job-runner.md) | On-Demand Evaluation Execution & Streaming Job Orchestrator | 09-Evaluation Workbench  | `episteme-studio` / `episteme-pipeline` | Horizon 1       | High     | `Completed`   |
| [**ISSUE-035**](10-decision-engine-and-jev/ISSUE-035-core-decision-engine-architecture-and-contracts.md) | Core Decision Engine Architecture, Contracts & Composition Root | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | High     | `Open`        |
| [**ISSUE-036**](10-decision-engine-and-jev/ISSUE-036-typesafe-jev-client-and-decision-adapter.md)       | TypeSafe Jev Client Implementation & System 1 Adapter       | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | High     | `Open`        |
| [**ISSUE-037**](10-decision-engine-and-jev/ISSUE-037-decision-observability-events-and-langfuse-tracing.md) | Decision Engine Observability, Domain Events & Langfuse Tracing | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | Critical | `Open`        |
| [**ISSUE-038**](10-decision-engine-and-jev/ISSUE-038-phase3-candidate-gating-and-relation-reranking.md) | Phase 3 Candidate Pair Gating & Jev Relation Reranker       | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | High     | `Open`        |
| [**ISSUE-039**](10-decision-engine-and-jev/ISSUE-039-phase4-argument-mining-acc-arc-triage.md)          | Phase 4b Argument Mining: Jev ACC & ARC Triage Classifiers  | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | High     | `Open`        |
| [**ISSUE-040**](10-decision-engine-and-jev/ISSUE-040-gleaning-and-extraction-stopping-gate.md)          | Objective Gleaning Gating via Jev Actor-Critic Stopping Oracle | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | Medium   | `Open`        |
| [**ISSUE-041**](10-decision-engine-and-jev/ISSUE-041-theorynet-calibrated-weights-and-qbaf-propagation.md) | TheoryNet Projection & QBAF Calibrated Probability Propagation | 10-Decision Engine & Jev | `episteme-pipeline` / `epistemetrics`   | Horizon 2       | High     | `Open`        |
| [**ISSUE-042**](10-decision-engine-and-jev/ISSUE-042-episodic-working-memory-jev-state-machine.md)          | Episodic Working Memory: Jev Semantic Boundary Eviction & Reference Resolution | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | High     | `Open`        |
| [**ISSUE-043**](10-decision-engine-and-jev/ISSUE-043-dense-entity-linking-and-ooo-gating.md)                | Dense Entity Linking: Jev Candidate Disambiguation & Out-of-Ontology Gating | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | High     | `Open`        |
| [**ISSUE-044**](10-decision-engine-and-jev/ISSUE-044-phase1-epistemic-relevance-and-noise-gating.md)       | Phase 1 Data Foundation: Epistemic Ingestion Relevance & Noise Gating | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | Medium   | `Open`        |
| [**ISSUE-045**](10-decision-engine-and-jev/ISSUE-045-phase3b-consolidation-merge-verification.md)          | Phase 3b Latent Graph Consolidation: Borderline Cluster Merge & Canonical Election | 10-Decision Engine & Jev | `episteme-pipeline`                     | Horizon 2       | Medium   | `Open`        |

