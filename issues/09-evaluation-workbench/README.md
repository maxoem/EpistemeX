# [09-evaluation-workbench] Evaluation Workbench: User Analytics, Coupled Views & Studio API Specification

## 1. Executive Summary & Purpose

With the core evaluation engine implemented in `packages/episteme-pipeline` and the foundational REST endpoints wired in `packages/episteme-studio` (`/api/evaluation/reports`, `/run`, `/compare`, `/benchmarks`, `/manifests`, `/dynamics/trajectory`, `/adjudications`, `/jobs`), the platform enters its next phase: **interactive workbench analytics and decision support**.

Evaluating knowledge graphs of complex scientific and philosophical literature (e.g. Newton's *Principia*, Darwinian evolution, decision-theoretic frameworks) differs fundamentally from shallow entity-linking benchmarks (such as CoNLL or generic KG link prediction). Episteme evaluates:
1. **Bourbaki Structuralist Model Decompositions** ($M_p, M, M_{pp}, C, I$).
2. **Specialization Posets and TheoryNet Hierarchies** (directed acyclic graphs rooted at fundamental laws $T_0$).
3. **Dialectical Polarity Concordance** (ensuring epistemic support vs attack relations are never inverted).
4. **Diachronic Lakatosian Dynamics** (measuring progressive vs degenerating research programmes across historical theory shifts).
5. **Downstream Competency Utility** (retrieval MRR, Hits@k, and nDCG for expert competency questions).
6. **Multi-Modal Grounding & Probability Calibration** (bounding boxes on equations/diagrams, ECE, Brier score).

This directory specifies the user-facing analytics, tightly coupled analytical views, and missing backend endpoints required to operationalize the Evaluation Workbench in Episteme Studio.

---

## 2. User Personas & Core Analytical Use Cases

```
+---------------------------------------------------------------------------------------------------------+
|                                    EPISTEME EVALUATION WORKBENCH PERSONAS                               |
+------------------------------------+------------------------------------+-------------------------------+
|  1. Computational Philosopher      |  2. Knowledge Graph / AI Engineer  |  3. Domain Expert / Curator   |
|  - Bourbaki model completeness     |  - Prompt & model ablation         |  - Borderline edge triage     |
|  - Root conformity & poset DAG     |  - OEP hallucination diagnosis     |  - Multi-modal proof auditing |
|  - Lakatosian degeneration index   |  - Confidence calibration (ECE)    |  - Curated gold standard export|
|  - Ad-hoc immunization detection   |  - Noise robustness sweeps (RDF)   |  - Real-time score impact     |
+------------------------------------+------------------------------------+-------------------------------+
```

### 2.1 Persona 1: The Computational Philosopher / Historian of Science
- **Objective:** Verify whether automated knowledge extraction accurately reconstructs the formal metatheoretical structure of a historical scientific theory.
- **Use Cases:**
  - **UC-1 (Bourbaki Decomposition Audit):** Inspect the ratio of identified actual models ($M$), potential models ($M_p$), non-theoretical models ($M_{pp}$), constraints ($C$), and intended applications ($I$). Identify exactly which formal components were omitted from the historical source text.
  - **UC-2 (Specialization Poset & Root Conformity):** Verify that the theory graph forms a valid DAG hierarchy where specialized laws inherit from a unique root $T_0$ (e.g. Newton's Second Law), checking transitive reduction $F_1$ and reachability $F_1$.
  - **UC-3 (Diachronic Lakatosian Degeneration Trajectory):** Track historical theory revisions $T_0 \to T_1 \to T_2$ over time. Plot the Lakatosian Degeneration Index:
    $$DI = \frac{\Delta \mathcal{A}}{\Delta \mathcal{C}}$$
    Confirm hard-core axiom invariance and identify ad-hoc immunization stratagems (introducing peripheral hypotheses to absorb anomalies without expanding empirical scope).

### 2.2 Persona 2: The Knowledge Graph / AI Researcher & Engineer
- **Objective:** Benchmark and optimize LLM prompt strategies, chunking granularities, embedding spaces, and reasoning temperatures.
- **Use Cases:**
  - **UC-4 (Multi-Run Ablation & Pareto Frontier):** Compare 5 to 20 experimental runs across models (e.g. GPT-4o vs Claude 3.5 Sonnet vs Llama-3 70B) and strategies (zero-shot, few-shot CoT, structured decomposition). Identify Pareto-optimal configurations balancing extraction accuracy, token cost, and latency.
  - **UC-5 (OEP Hallucination & Alignment Diagnostic):** Deconstruct errors into Over-generation (hallucinated entities/triples), Edge errors (inverted or substituted relation predicates), and Property errors (attribute/type mismatches).
  - **UC-6 (Confidence Calibration & Overconfidence Triage):** Evaluate whether pipeline confidence $c \in [0, 1]$ corresponds to empirical validity. Detect overconfident hallucinations ($c > 0.90$ with zero empirical support), compute Expected Calibration Error (ECE) and Brier scores, and inspect reliability diagrams.
  - **UC-7 (Adversarial Noise Robustness & Stress Testing):** Benchmark pipeline resilience under text perturbations (typos, entity synonyms, sentence shuffles) to calculate the Robustness Degradation Factor (RDF).

### 2.3 Persona 3: The Domain Expert / Scientific Annotator (HITL)
- **Objective:** Rapidly audit uncertain machine predictions, resolve borderline relation alignments, and curate sovereign gold standards.
- **Use Cases:**
  - **UC-8 (Borderline Alignment Triage Queue):** Review candidate relations whose soft semantic similarity falls within the uncertainty band $\tau \in [0.80, 0.94]$. Make one-click adjudications: True Positive, False Positive, or Schema Alias.
  - **UC-9 (Deep Multi-Modal Evidence Grounding):** View the primary source evidence behind any asserted relation or contradiction: character-level text spans, verbatim quotes, or bounding boxes $[x_0, y_0, x_1, y_1]$ on figures and mathematical equations.
  - **UC-10 (Dynamic What-If Recalculation):** Immediately observe how an adjudication updates precision, recall, F1, and model completeness without running an entire offline batch re-evaluation, then export the curated benchmark as a versioned JSON-LD dataset.

### 2.4 Persona 4: The Benchmark Administrator / Lab Lead
- **Objective:** Maintain enterprise/academic test suites (STNB, SciERC, DocRED, custom corpora) and evaluate downstream task competency.
- **Use Cases:**
  - **UC-11 (Downstream Competency Query Auditing):** Evaluate information retrieval utility (MRR, Hits@1/3/10, nDCG) on expert competency questions. Drill down into specific queries to examine retrieved subgraphs vs expected gold answers.
  - **UC-12 (Custom Benchmark Onboarding & Pre-Flight Validation):** Upload and lint new domain benchmark datasets, ensuring JSON-LD schema validity, unique theory atom identifiers, and DAG acyclicity before running expensive evaluations.
  - **UC-13 (Async Batch Orchestration & SSE Progress Monitoring):** Run large-scale multi-document evaluations in background workers, streaming real-time stage progress and query scoring over Server-Sent Events (SSE).

---

## 3. Information Grouping & Co-Location Architecture: What Must Be Shown Together

To avoid fragmented user experiences where analysts must switch across multiple disconnected tabs to interpret an evaluation, data must be grouped according to tight semantic coupling:

```
+----------------------------------------------------------------------------------------------------+
|                               EVALUATION WORKBENCH CO-LOCATION MAP                                 |
+----------------------------------------------------------------------------------------------------+
| [View 1: Headline Scorecard & Bourbaki Ledger]                                                     |
|  - Key KPI Cards (MCC, PFS, F1, ECE, MRR) + Poset Health Pill + Bourbaki Class Decomposition Table |
|  - Markdown Executive Commentary + Benchmark Reference Metadata                                    |
+----------------------------------------------------------------------------------------------------+
| [View 2: Interactive Evaluation Graph Overlay (Canvas)]                                            |
|  - Canvas GraphView: TP (green), FP / Hallucinations (red), FN / Omissions (ghost gray nodes)       |
|  - Node/Edge Inspector: Extracted vs Gold properties, similarity score tau, evidence snippets     |
+----------------------------------------------------------------------------------------------------+
| [View 3: HITL Adjudication Workbench]                                                              |
|  - Borderline Triage Queue (tau in [0.80, 0.94]) + Side-by-side Candidate Triple Diff Card         |
|  - Multi-Modal Evidence Anchors (Text & Bounding Box) + One-Click Decision Bar + Live Delta Impact |
+----------------------------------------------------------------------------------------------------+
| [View 4: Confidence Calibration & Reliability Diagram]                                             |
|  - 10-Bin Reliability Diagram (Accuracy vs Confidence) + ECE / MCE / Brier Score Gauge              |
|  - High-Confidence Hallucination Triage Table (confidence > 0.90, empirical match = False)         |
+----------------------------------------------------------------------------------------------------+
| [View 5: Diachronic Lakatosian Degeneration Trajectory]                                            |
|  - Longitudinal Line Chart (DI = delta A / delta C across epochs T_0 -> T_n)                       |
|  - Hard-Core Invariance Status + Per-Node Immunization Index (II) + Temporal Graph Scrubber       |
+----------------------------------------------------------------------------------------------------+
| [View 6: Multi-Run Leaderboard & Multi-Virtue Pareto Frontier]                                     |
|  - Matrix Table (N Runs x All Metrics) + 2D/3D Scatter Plot (F1 vs Cost vs ECE)                    |
|  - Run Pairwise Diff HUD + YAML Configuration Delta Drawer                                         |
+----------------------------------------------------------------------------------------------------+
| [View 7: Downstream Competency Retrieval Diagnostics]                                              |
|  - Macro Ranking Scores (MRR, Hits@k, nDCG) + Per-Query Diagnostic List (Rank, Reciprocal Rank)    |
|  - Query Subgraph Traversal Path Viewer (Retrieved Nodes vs Expected Gold Targets)                |
+----------------------------------------------------------------------------------------------------+
| [View 8: Adversarial Noise Robustness Stress-Tester]                                               |
|  - Degradation Curve Chart (Metric vs Noise Level eta in [0.0, 0.30]) + RDF Score Breakdown        |
+----------------------------------------------------------------------------------------------------+
```

### 3.1 Tight Coupling Rules

1. **Rule C-1 (Metric to Graph Grounding):**
   *A metric indicating an omission or error MUST never be rendered in isolation without direct linkage to the graph canvas.*
   - Clicking an entry in `omitted_components` or `violations` must highlight the missing or invalid element directly on the canvas as a "ghost node" or "conflicted edge" within its structural neighborhood.
2. **Rule C-2 (Adjudication Context Co-Location):**
   *A human reviewer MUST have the predicted triple, candidate reference triple, semantic similarity score, and primary source evidence (text quote and/or visual bounding box) in a single unified card.*
   - If evidence is separated into another tab or requires external navigation, adjudication efficiency drops and review errors escalate.
3. **Rule C-3 (Adjudication to Metric Feedback Loop):**
   *Submitting an adjudication MUST immediately show the live predicted delta on headline metrics ($MCC, F_1, AOR$).*
   - Reviewers must see how their semantic validation changes the benchmark outcome without triggering a lengthy offline batch run.
4. **Rule C-4 (Calibration to Exemplar Coupling):**
   *A reliability diagram MUST be accompanied by an actionable list of miscalibrated assertions.*
   - Displaying that the 0.90–1.00 confidence bin has only 60% accuracy is useless unless the user can click that bin and inspect the specific overconfident hallucinations.
5. **Rule C-5 (Diachronic Trajectory to Topological Mutation Coupling):**
   *A diachronic Lakatosian degeneration curve ($DI$) MUST be synchronised with the graph evolution scrubber.*
   - As the user drags the timeline slider between $T_0 \to T_1 \to T_2$, the canvas must visually highlight newly added auxiliary hypotheses in orange, deleted core axioms in red, and stable core nodes in blue.
6. **Rule C-6 (Comparative Delta to Config Diff Coupling):**
   *Metric deltas between two runs MUST be accompanied by configuration parameter diffs.*
   - When Run B beats Run A on $F_1$ (+0.12), the user must see precisely what changed in the prompt, temperature, chunk size, or model name.

---

## 4. Backend Endpoints Gap Analysis & Missing API Matrix

The existing endpoints implemented in `packages/episteme-studio` provide essential coarse-grained CRUD and execution operations, but fail to satisfy the tightly coupled analytical requirements identified above:

| Analytical Capability | Current Implemented Endpoint | Limitation / Architectural Gap | Missing Endpoint Required | Issue ID |
| :--- | :--- | :--- | :--- | :--- |
| **Visual Graph Error Canvas** | `GET /api/evaluation/reports/{id}` | Only returns scalar counts and string IDs (`omitted_components: [...]`). Graph canvas cannot render alignment states or ghost nodes. | `GET /api/evaluation/reports/{id}/graph-overlay` | **ISSUE-026** |
| **HITL Candidate Triage** | `GET /api/evaluation/adjudications` | Only returns *previously adjudicated* records. Cannot retrieve pending unreviewed candidate pairs in similarity window $[\tau_{min}, \tau_{max}]$. | `GET /api/evaluation/reports/{id}/adjudication-queue` | **ISSUE-027** |
| **Live What-If Re-evaluation** | `POST /api/evaluation/adjudications` | Persists decision records into disk storage without recomputing or returning updated evaluation metrics. | `POST /api/evaluation/reports/{id}/adjudicate-and-recalculate` | **ISSUE-027** |
| **Calibration & Reliability** | `GET /api/evaluation/reports/{id}` | Lacks bin-by-bin calibration data (accuracy, confidence, count) required for reliability diagrams and overconfidence triage. | `GET /api/evaluation/reports/{id}/calibration` | **ISSUE-028** |
| **Multi-Modal Evidence** | `GET /api/runs/{run_id}` | Lacks page-level bounding box coordinates, image crop URLs, and $AG_{\text{IoU}}$ scores for evaluated theoretical components. | `GET /api/evaluation/reports/{id}/evidence/{component_id}` | **ISSUE-029** |
| **Multi-Run Leaderboard** | `POST /api/evaluation/compare` | Only compares two runs side-by-side. Cannot aggregate $N$ runs into a benchmark leaderboard or compute Pareto frontiers. | `POST /api/evaluation/leaderboard`<br>`GET /api/evaluation/leaderboard` | **ISSUE-030** |
| **Noise Robustness Sweeps** | Offline pipeline scorers only | Studio has no endpoint to trigger adversarial noise perturbation sweeps or retrieve Robustness Degradation Factor (RDF) curves. | `POST /api/evaluation/stress-test`<br>`GET /api/evaluation/reports/{id}/robustness` | **ISSUE-031** |
| **Competency Query Diagnostics** | `RetrievalEvaluationDetail` | Only yields macro averages (MRR, Hits@10). Cannot inspect individual queries, ranked retrieved nodes, or search failure paths. | `GET /api/evaluation/reports/{id}/retrieval-diagnostics` | **ISSUE-032** |
| **Custom Benchmark Linter** | `GET /api/evaluation/benchmarks` | Read-only discovery of local files. Cannot upload, validate DAG acyclicity, or pre-flight lint custom user benchmarks. | `POST /api/evaluation/benchmarks`<br>`POST /api/evaluation/benchmarks/validate` | **ISSUE-033** |
| **Academic Multi-Format Export** | `GET /api/evaluation/reports/{id}/markdown` | Only returns raw Markdown. Cannot export publication-ready LaTeX tables, CSV summaries, or standardized JSON-LD graph bundles. | `GET /api/evaluation/reports/{id}/export?format=latex\|csv\|jsonld` | **ISSUE-033** |
| **Interactive Job Execution** | `POST /api/evaluation/run` | Synchronous endpoint risks HTTP timeouts on large graphs; lacks live SSE progress streaming and cancellation supervision. | `POST /api/evaluation/jobs/run`<br>`GET /api/evaluation/jobs/{id}/stream`<br>`POST /api/evaluation/jobs/{id}/cancel` | **ISSUE-034** |

---

## 5. Master Issue Index: Evaluation Workbench Backlog

| Issue ID | Title | Scope / Focus | Roadmap Horizon | Priority |
| :--- | :--- | :--- | :--- | :--- |
| [**ISSUE-026**](ISSUE-026-evaluation-graph-alignment-overlay-projection.md) | Evaluation Graph Alignment Overlay & Visual Error Projection (`GraphView`) | Canvas projection of TP, FP, FN ghost nodes, and alignment states | Horizon 1 | **Critical** |
| [**ISSUE-027**](ISSUE-027-hitl-adjudication-queue-and-live-recalculation.md) | HITL Borderline Adjudication Queue & Dynamic What-If Re-evaluation | Candidate queue triage ($\tau \in [0.80, 0.94]$) and in-place re-scoring | Horizon 1 | **High** |
| [**ISSUE-028**](ISSUE-028-confidence-calibration-reliability-diagrams.md) | Confidence Calibration Diagnostics & Reliability Diagrams (ECE & Brier) | Reliability curve binning, ECE/MCE, and overconfident hallucination triage | Horizon 1 & 2 | **High** |
| [**ISSUE-029**](ISSUE-029-multimodal-grounding-evidence-inspection.md) | Multi-Modal Deep Evidence Grounding & Bounding-Box Inspection | Grounding theory atoms in PDF bounding boxes, equation blocks & $AG_{\text{IoU}}$ | Horizon 2 | **Medium** |
| [**ISSUE-030**](ISSUE-030-multi-run-leaderboard-and-pareto-frontier.md) | Multi-Run Benchmark Leaderboard & Multi-Virtue Pareto Frontier | Aggregating $N \ge 2$ runs into a leaderboard and Pareto-optimal trade-offs | Horizon 2 | **High** |
| [**ISSUE-031**](ISSUE-031-adversarial-noise-robustness-stress-testing.md) | Adversarial Noise Robustness Benchmarking & RDF Degradation Curves | Automated perturbation sweeps and Robustness Degradation Factor curves | Horizon 2 | **Medium** |
| [**ISSUE-032**](ISSUE-032-competency-query-retrieval-diagnostics.md) | Downstream Competency Retrieval Per-Query Diagnostics & Traversal Traces | Per-query ranking breakdown, hit analysis, and graph retrieval failure traces | Horizon 1 | **Medium** |
| [**ISSUE-033**](ISSUE-033-benchmark-catalog-management-and-validation.md) | Custom Benchmark Registration, Pre-Flight Linter & Multi-Format Export | Custom gold upload, DAG acyclicity validation, and LaTeX/CSV export | Horizon 1 & 2 | **Medium** |
| [**ISSUE-034**](ISSUE-034-on-demand-evaluation-execution-and-streaming-job-runner.md) | On-Demand Evaluation Execution, Asynchronous Job Orchestration & Streaming Telemetry | Interactive launch dialog, worker supervision, SSE streaming, and cancellation | Horizon 1 | **High** |
