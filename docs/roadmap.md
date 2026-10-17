# Project & Research Roadmap

This document outlines the strategic engineering and research roadmap for **Episteme**.

The project unifies **computational epistemic research** (formal TheoryNet models, structuralist philosophy of science,
and epistemetrics) with a **production-grade software engine** (`episteme-pipeline`, `epistemetrics`, and `episteme-studio`).

---

## Delivered Capabilities & Completed Milestones

**Production Engine | Implemented**

Foundational architectural capabilities and inference systems that have transitioned from research and evaluation into production-grade, tested implementations within the core engine.

| Target / Initiative                            | Component            | Status        | Key Deliverable & Implementation Artifacts                                                                                                                           |
|:-----------------------------------------------|:---------------------|:--------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **TypeSafe / Jev Classification & Gating**     | `episteme-pipeline`  | `Implemented` | Sub-second typed classification, conformal prediction set gating, and AOP routing (`JevClassifier`, `JevEntityLinker`, `JevRelationReranker`, `JevGleaningGate`) |

---

### TypeSafe / Jev Typed Classification & Gating Engine (`JevClassifier`)

| Status        | Target Component                                                                                                                                                                         | Focus Area                                 |
|:--------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------|
| `Implemented` | `episteme-pipeline` (`episteme_pipeline/decision/`, `pipeline/phases/phase2_entity_discovery/`, `pipeline/phases/phase3_global_relations/`, `pipeline/phases/phase4_argument_mining/`) | Ultra-Low Latency Inference & Flow Routing |

Integrates TypeSafe's Jev as a non-generative, typed classification and decision-gating adapter across the pipeline. Fully implemented and integrated into production.

Unlike generative LLMs, Jev directly emits typed values and calibrated confidence scores (empirically reflecting true
classification accuracy / ground-truth fit frequencies rather than uncalibrated LLM probabilities) with sub-second
response times (70–500ms) at 40–200× lower cost and latency.

**Delivered Capabilities & Implementation Artifacts:**

- **`JevEntityLinker` & `CascadingEntityLinker`**: Fast candidate triage and conformal prediction set gating ($C(X)$) in Phase 2 Entity Discovery ([`jev_entity_linker.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/jev_entity_linker.py)).
- **`JevGleaningGate`**: Non-generative critic oracle decoupling generative extraction from deterministic stopping criteria in Phase 2 and Phase 4 ([`gleaning.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-pipeline/episteme_pipeline/decision/gleaning.py)).
- **`JevRelationReranker` & Jev Pair Gating**: Drop-in calibrated reranking and binary `Noul` gating in Phase 3 Global Relations ([`rerankers.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/rerankers.py)).
- **`JevClusterVerification`**: Borderline candidate verification and canonical terminology election via Jev `Choice` in Phase 3b Consolidation ([`consolidation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-pipeline/episteme_pipeline/phases/phase3b_consolidation/consolidation.py)).
- **`JevACCClassifier` & `JevARCClassifier`**: High-throughput argument component and defeasible stance classification in Phase 4 Argument Mining ([`classifiers.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/classifiers.py)).
- **Engine Clients & Test Harness**: Complete runtime provisioning via `AutoDecisionEngine`, `LayaDecisionEngine`, and deterministic `MockJevDecisionEngine` ([`decision/`](file:///Users/maxoehm/EpistemeX/packages/episteme-pipeline/episteme_pipeline/decision/)).

---

## Horizon 1: Platform Stabilization & Core Engine

**Current Focus | Active Development**

Focuses on completing the transition to a non-linear stage-execution engine, operationalizing the automated evaluation
harness, and hardening the user workbench.

| Target / Initiative              | Component                        | Status               | Key Deliverable                                                    |
|:---------------------------------|:---------------------------------|:---------------------|:-------------------------------------------------------------------|
| **DAG Stage Execution Engine**   | `episteme-pipeline`                   | `Active Development` | Non-linear DAG stage scheduler (`_execute_via_plan`)               |
| **Evaluation Harness Execution** | `episteme-pipeline` / `epistemetrics` | `Active Development` | Wire G-BS, OEP, MRR, and nDCG to `EvaluationRun`                   |
| **Neo4j Constraint Reasoning**   | `episteme-pipeline`                   | `Active Development` | Polarity-aware disjointness & schema validation (`GraphValidator`) |
| **Episteme Studio Workbench v0.2**    | `episteme-studio`                     | `Active Development` | Run-to-run identity diffing, candidate triage, and tenability UI   |

---

### DAG Stage Execution Engine (`_execute_via_plan`)

| Status               | Target Component                                             | Focus Area                |
|:---------------------|:-------------------------------------------------------------|:--------------------------|
| `Active Development` | `episteme-pipeline` (`pipeline/pipeline.py`, `pipeline/runtime/`) | Stage Graph Orchestration |

Refactors pipeline execution from a sequential 1-based ordinal loop into an arbitrary Directed Acyclic Graph (DAG) stage
execution plan (`_build_execution_plan`, `_resolve_phase_order`, `_execute_via_plan`).

**Key Capabilities & Milestones:**

- Supports non-linear, branching, and conditionally skipped phase topologies.
- Preserves deterministic `RunManifest` tracking and artifact-envelope provenance across concurrent branches.
- Enables injecting analytical passes at arbitrary graph boundaries rather than appending solely at the tail.

---

### Evaluation Harness Execution & Scorer Wiring

| Status               | Target Component                                          | Focus Area                  |
|:---------------------|:----------------------------------------------------------|:----------------------------|
| `Active Development` | `episteme-pipeline` & `epistemetrics` (`pipeline/evaluation/`) | Automated Metric Evaluation |

Wires intrinsic and extrinsic scorers into the `EvaluationRun` orchestrator (`pipeline/evaluation/`).

**Key Capabilities & Milestones:**

- Connects Graph BERTScore (G-BS) and Optimal Edit Paths (OEP) with injected embedding functions for soft semantic
  matching.
- Binds extrinsic ranking metrics (MRR, nDCG@k, Hits@k, AP) to evaluation datasets.
- Formats evaluation results into standardized `EvaluationReport` Pydantic models and automated Markdown summaries.

---

### Neo4j Structural Reasoning & Constraint Validation

| Status               | Target Component                                       | Focus Area                    |
|:---------------------|:-------------------------------------------------------|:------------------------------|
| `Active Development` | `episteme-pipeline` (`pipeline/graph/`, `pipeline/events/`) | Schema & Logical Disjointness |

Integrates `GraphValidator` checks directly into the pipeline lifecycle.

**Key Capabilities & Milestones:**

- Enforces polarity-aware disjointness (preventing simultaneous positive and negative edges to identical targets).
- Validates `L3_COMPONENT_TYPES` and structural constraints natively in Neo4j via async Cypher.
- Emits `EvaluationCompleted` and `ValidationViolationDetected` domain events to the event bus.

---

### Episteme Studio Workbench v0.2

| Status               | Target Component                                  | Focus Area                       |
|:---------------------|:--------------------------------------------------|:---------------------------------|
| `Active Development` | `episteme-studio` (`src/Episteme_studio/`, `frontend/src/`) | Visual Exploration & Run Diffing |

Hardens the run-oriented workbench for researchers and reviewers.

**Key Capabilities & Milestones:**

- Interactive tri-layer graph explorer (L1 Provenance, L2 Knowledge Graph, L3 TheoryNet).
- Visual run-to-run identity diffing (`diff_artifacts`) showing added, modified, and stale entities.
- Interactive candidate triple triage and tenability blur inspection ($\delta^*$).

---

## Horizon 2: Scalability, Benchmarking & Dialectical Modeling

**Medium-Term | Under Evaluation**

Focuses on validating extraction quality against external academic baselines, scaling to large-scale literature corpora,
and deepening gradual argumentation semantics.

| Target / Initiative                            | Component                        | Status             | Key Deliverable                                                               |
|:-----------------------------------------------|:---------------------------------|:-------------------|:------------------------------------------------------------------------------|
| **Authentic Human Baseline & LLM Judges**      | `episteme-pipeline`                   | `Under Evaluation` | Human-annotated gold standard & Krippendorff's $\alpha$ calibration           |
| **Standardized Benchmark Adapters**            | `episteme-pipeline`                   | `Under Evaluation` | Adapters for `Arg-Microtexts`, `SciERC`, and `SciFact`                        |
| **Weak Supervision for Extraction**            | `episteme-pipeline`                   | `Under Evaluation` | CQP rhetorical queries & SetFit few-shot classifier bootstrapping             |
| **Gradual Semantics Solvers (QBAF)**           | `epistemetrics` / `episteme-pipeline` | `Under Evaluation` | Iterative convergence algorithms for TheoryNet $(\text{TF} = (\text{At}, R))$ |
| **Streaming Large Corpus Ingestion**           | `episteme-pipeline`                   | `Under Evaluation` | Memory-bounded chunking & windowed episodic memory eviction                   |
| **Pluggable Vector Store Adapters**            | `episteme-pipeline`                   | `Under Evaluation` | Qdrant, Milvus, and pgvector reference implementations                        |
| **World Models & Empirical Simulation**        | `episteme-pipeline` / `epistemetrics` | `Under Evaluation` | Simulating world dynamics & environments to evaluate empirical node correctness |

---

### Authentic Human Baseline & LLM-as-a-Judge Calibration

| Status             | Target Component                        | Focus Area                        |
|:-------------------|:----------------------------------------|:----------------------------------|
| `Under Evaluation` | `episteme-pipeline` (`pipeline/evaluation/`) | Empirical Grounding & Calibration |

Establishes a human-expert baseline on authentic scientific texts before deploying automated LLM judges.

**Key Capabilities & Milestones:**

- Curate and verify gold-standard annotations from authentic corpus runs (`planwirtschaft.md`,
  `teachers_expectancies.md`).
- Calculate inter-annotator agreement (Krippendorff's $\alpha$) across domain-expert evaluation rubrics.
- Mathematically correlate human quality judgments with LLM-as-a-judge scores, enforcing strict calibration before
  deployment.

---

### Standardized Public Benchmark Adapters

| Status             | Target Component                                 | Focus Area                  |
|:-------------------|:-------------------------------------------------|:----------------------------|
| `Under Evaluation` | `episteme-pipeline` (`pipeline/evaluation/adapters/`) | Standardized NLP Benchmarks |

Standardizes evaluation against recognized NLP and argument mining benchmarks.

**Key Capabilities & Milestones:**

- **`Arg-Microtexts` Adapter**: Benchmark Layer 3 argument discourse units and support/attack relation classification.
- **`SciERC` Adapter**: Benchmark Layer 2 scientific entity recognition and relation extraction.
- **`SciFact` Adapter**: Benchmark extrinsic claim verification and evidence retrieval.

---

### Weak Supervision for Logical Patterns

| Status             | Target Component                                                                                       | Focus Area                         |
|:-------------------|:-------------------------------------------------------------------------------------------------------|:-----------------------------------|
| `Under Evaluation` | `episteme-pipeline` (`pipeline/phases/phase2_entity_discovery/`, `pipeline/phases/phase4_argument_mining/`) | Zero-Cost Classifier Bootstrapping |

Bootstraps extraction classifiers without expensive manual labeling.

**Key Capabilities & Milestones:**

- Formulate high-precision Corpus Query Processor (CQP) patterns for discourse markers and dialectical connectives.
- Train few-shot classifiers (e.g., SetFit) using query matches as silver-standard training data.

---

### Advanced Gradual Semantics Solvers (QBAF & TheoryNet)

| Status             | Target Component                                                       | Focus Area                     |
|:-------------------|:-----------------------------------------------------------------------|:-------------------------------|
| `Under Evaluation` | `epistemetrics` & `episteme-pipeline` (`pipeline/phases/phase6_theorynet/`) | Argumentation Convergence Math |

Implements high-performance iterative convergence algorithms for dense, cyclic argumentation networks. Governed
by [ADR 0011](adr/0011-declarative-graph-metrics-and-qbaf-semantics.md).

**Key Capabilities & Milestones:**

- Implements gradual argumentation semantics (Eulerian, quadratic energy, and categorization models).
- Solves for equilibrium justification degrees ($\tau$) and empirical content ratios ($B \cap P$) in TheoryNet
  ($\text{TF} = (\text{At}, R)$).

---

### Streaming & Large Corpus Ingestion

| Status             | Target Component                                      | Focus Area             |
|:-------------------|:------------------------------------------------------|:-----------------------|
| `Under Evaluation` | `episteme-pipeline` (`pipeline/phases/phase1_foundation/`) | Memory-Bounded Scaling |

Enables memory-bounded ingestion of multi-chapter scientific treatises and book-length corpora.

**Key Capabilities & Milestones:**

- Incremental, streaming chunk generation with ToC boundary preservation.
- Windowed episodic memory eviction to prevent RAM exhaustion during multi-hundred-page processing.

---

### Pluggable Vector Store Adapters

| Status             | Target Component                   | Focus Area                 |
|:-------------------|:-----------------------------------|:---------------------------|
| `Under Evaluation` | `episteme-pipeline` (`pipeline/graph/`) | Backend Storage Decoupling |

Supports specialized vector backends alongside Neo4j.

**Key Capabilities & Milestones:**

- Reference adapters for Qdrant, Milvus, and pgvector implementing `GraphReader` / vector search protocols.
- Decouples dense similarity candidate blocking from property graph traversal.

---

### World Models for Empirical Node Validation

| Status             | Target Component                                                                                         | Focus Area                                    |
|:-------------------|:---------------------------------------------------------------------------------------------------------|:----------------------------------------------|
| `Under Evaluation` | `episteme-pipeline` / `epistemetrics` (`pipeline/phases/phase6_theorynet/`, `epistemetrics/epistemic/`) | Environmental Simulation & Empirical Adequacy |

Explores generative and neuro-symbolic world models as simulation testbeds for evaluating the correctness, empirical adequacy, and real-world grounding of empirical nodes in theory graphs.

In formal structuralism (*Wissenschaftstheorie*) and Episteme's tri-layer architecture, intended applications ($I$) and empirical nodes assert concrete claims about domain phenomena. Traditional pipelines evaluate these nodes via static text matching or subjective LLM plausibility scores ($p(i, x)$). By integrating world models, Episteme simulates environment dynamics, state transitions, and counterfactual interventions directly, providing objective empirical feedback on whether extracted empirical assertions hold.

**Key Capabilities & Milestones:**

- **Domain Environment Simulation**: Constructs executable generative or symbolic simulation sandboxes modeling the physical, social, or historical conditions asserted by empirical claims.
- **Empirical Node Correctness Evaluation**: Evaluates whether the factual claims, observational residuals ($d(i, x)$), and predictive implications of candidate empirical nodes hold under forward simulation rollouts.
- **Counterfactual & Perturbation Stress-Testing**: Systematically perturbs simulation parameters to evaluate the boundary conditions, empirical vulnerability, and falsifiability of theoretical nodes.
- **Closed-Loop Grounding**: Synthesizes empirical simulation rollouts with TheoryNet post-processing, computing grounded empirical adequacy and tenability scores for empirical subgraphs.

---

## Horizon 3: Epistemic Frontiers & Scientific Research

**Long-Term | Under Consideration / Research**

Explores cutting-edge intersections of structuralist philosophy of science, geometric deep learning, and neuro-symbolic
reasoning. Anchored in *Pan et al. (2024)* and related literature. Detailed analysis available
in [Literature & Future Directions](research/future_research_goals.md).

| Research Frontier            | Literature Anchor       | Status                           | Core Concept & Scope                                                                 |
|:-----------------------------|:------------------------|:---------------------------------|:-------------------------------------------------------------------------------------|
| **Hypercomplex Embeddings**  | Nayyeri et al. (2022)   | `Under Consideration / Research` | 4D quaternions ($\mathbb{H}^d$) for multi-scale text-graph rotations                 |
| **Contrastive Retrieval**    | SimKGC (ACL 2022)       | `Under Consideration / Research` | Siamese InfoNCE loss separating plausible from topical triples                       |
| **Model-Agnostic Loss**      | CoDEx (2022)            | `Under Consideration / Research` | LLM-guided loss for Neo4j candidate triple plausibility                              |
| **Graph Reasoning (RoG)**    | Luo et al. (2023)       | `Under Consideration / Research` | Two-stage grounded path generation and constrained inference                         |
| **Cross-Paradigm Synthesis** | Structuralism / Lakatos | `Under Consideration / Research` | Inter-theory constraint edges ($TS_{\text{edge}}$) and admissible blurs ($\delta^*$) |

---

### Hypercomplex & Quaternion Embeddings ($\mathbb{H}^d$)

| Status                           | Literature Anchor     | Theoretical Domain                          |
|:---------------------------------|:----------------------|:--------------------------------------------|
| `Under Consideration / Research` | Nayyeri et al. (2022) | 4D Hypercomplex Embeddings ($\mathbb{H}^d$) |

Standard Euclidean embeddings struggle to represent complex non-commutative relational structures without large
parameter inflation. Using 4D hypercomplex space ($\mathbb{H}^d$, Hamilton
products $q = a + b\mathbf{i} + c\mathbf{j} + d\mathbf{k}$), word-, sentence-, and document-level representations can be
unified with graph structure embeddings to perform expressive multi-scale relational rotations in TheoryNet topologies.

---

### Contrastive Learning for Candidate Relation Retrieval

| Status                           | Literature Anchor                              | Theoretical Domain               |
|:---------------------------------|:-----------------------------------------------|:---------------------------------|
| `Under Consideration / Research` | SimKGC (ACL 2022) & Justin et al. (EMNLP 2022) | Siamese InfoNCE Contrastive Loss |

Raw LLM text embeddings often capture topical similarity rather than relational truth. Training Siamese encoders via
contrastive learning (InfoNCE loss) discriminates plausible from implausible candidate triples, significantly boosting
candidate retrieval precision in Phase 3 Global Relation Discovery.

---

### Model-Agnostic Knowledge Loss Functions

| Status                           | Literature Anchor         | Theoretical Domain            |
|:---------------------------------|:--------------------------|:------------------------------|
| `Under Consideration / Research` | CoDEx (Alam et al., 2022) | Model-Agnostic Loss Functions |

Incorporates a model-agnostic loss function that leverages LLM textual guidance to score triple plausibility directly in
Neo4j without requiring full model fine-tuning.

---

### Reasoning on Graphs & Path Generation (RoG)

| Status                           | Literature Anchor                        | Theoretical Domain                 |
|:---------------------------------|:-----------------------------------------|:-----------------------------------|
| `Under Consideration / Research` | RoG (Luo et al., arXiv:2310.01061, 2023) | Faithful Multi-Hop Graph Reasoning |

Neuro-symbolic reasoning over theory graphs via two-stage planning and retrieval: a planning module generates relation
paths grounded in the graph as faithful reasoning plans, followed by multi-hop constrained LLM inference.

---

### Cross-Paradigm Theory Synthesis & Incommensurability Analysis

| Status                           | Literature Anchor                                 | Theoretical Domain           |
|:---------------------------------|:--------------------------------------------------|:-----------------------------|
| `Under Consideration / Research` | Structuralism (Balzer, Moulines, Sneed) / Lakatos | Diachronic Paradigm Dynamics |

Extends `TheoreticalEnrichmentRunner` to model competing scientific paradigms, formalizing cross-theory constraint edges
($TS_{\text{edge}}$), admissible blurs ($\delta^*$), and Kuhn-incommensurability boundaries.
