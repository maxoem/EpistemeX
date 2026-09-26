# Episteme Knowledge Graph Evaluation: SOTA Gap Analysis & Missing Features

This document tracks identified architectural gaps, missing capabilities, and state-of-the-art (SOTA) evaluation practices to be addressed in upcoming iterations.

---

## 1. Executive Summary

While the **Episteme Evaluation Framework** provides robust sovereign capabilities (formal Bourbaki structuralist decomposition, specialization poset hierarchy checks, schema-driven polarity concordance, GM-GBS soft matching, OEP error tracking, and comparative baseline benchmarking), several advanced features are required to fully comply with state-of-the-art knowledge graph verification and epistemic evaluation standards.

---

## 2. Identified Gaps & Missing Implementations

### Gap 1: Confidence Calibration (ECE & Brier Score)
- **Current State:** Extraction and argumentation components output heuristic confidence scores $c \in [0, 1]$ (e.g. LLM logprobs, cross-encoder probabilities, or hardcoded $1.0$). Intrinsic evaluation scores relation precision/recall via thresholding without assessing probability calibration.
- **SOTA Practice:** Knowledge graph evaluation should compute **Expected Calibration Error (ECE)**, Maximum Calibration Error (MCE), and Brier Score across confidence bins. A well-calibrated epistemic graph ensures that assertions with 90% confidence are empirically correct 90% of the time, preventing overconfident hallucinations.
- **Target Implementation:**
  - Add `episteme_pipeline.evaluation.scorers.calibration.CalibrationScorer`.
  - Report ECE, reliability diagrams, and Brier Score in `EvaluationResult`.

### Gap 2: Diachronic Lakatosian Degeneration Trajectory in Studio
- **Current State:** `epistemetrics.epistemic.dynamics` calculates the Lakatosian Degeneration Index:
  $$DI = \frac{\Delta \mathcal{A}}{\Delta \mathcal{C}}$$
  (tracking anomalous ad-hoc peripheral hypotheses $\mathcal{A}$ versus hard-core explanatory expansion $\mathcal{C}$). While the math exists in `epistemetrics`, Episteme Studio only provides pairwise static run diffs without rendering the longitudinal diachronic trajectory across multiple successive theory shifts.
- **SOTA Practice:** Historical philosophy of science (Lakatos, Kuhn) evaluates research programmes longitudinally. Studio should expose a multi-run diachronic trajectory view plotting $DI$ across versions $T_0 \to T_1 \to T_2$.
- **Target Implementation:**
  - Introduce `POST /api/evaluation/dynamics/trajectory` in `api/evaluation.py`.
  - Expose interactive degeneration charts in the workbench.

### Gap 3: Multi-Modal Evidence Anchoring (Figure & Table Grounding)
- **Current State:** Primary source text grounding is strictly evaluated on character and token spans (`charStart`, `charEnd`, `verbatimQuote`) via $AG_{\text{IoU}}$.
- **SOTA Practice:** Modern scientific literature frequently expresses core empirical laws, experimental data, and structural diagrams in figures, mathematical equation blocks, and tables.
- **Target Implementation:**
  - Expand `EvidenceTrail` and `TextAnchor` to support bounding box regions (`bbox: [x0, y0, x1, y1, page]`) and formula identifiers.
  - Implement visual and tabular grounding IoU metrics.

### Gap 4: Human-in-the-Loop (HITL) Adjudication Seam
- **Current State:** Edge alignment in GM-GBS uses an automated threshold $\tau$ (e.g. $0.95$). If a predicted predicate achieves a similarity score near the threshold (e.g. $\tau \in [0.80, 0.94]$), it is either strictly matched or penalized as a hallucination/omission.
- **SOTA Practice:** SOTA benchmark platforms (e.g. DocRED, SciERC, GLUE) provide a Human-in-the-Loop review queue where borderline alignments can be adjudicated by domain experts directly in the UI.
- **Target Implementation:**
  - Add `POST /api/evaluation/adjudications` endpoint allowing users to mark edge alignments as True Positive, False Positive, or Schema Aliases.
  - Export curated adjudications back into gold-standard datasets (`.jsonld`).

### Gap 5: Asynchronous Streaming for Long-Running Batch Evaluations
- **Current State:** Manifest evaluations and full corpus LLM judging run synchronously within HTTP requests or subprocesses, returning the report upon completion.
- **SOTA Practice:** Batch evaluation across large corpora (e.g., hundreds of documents or full monographs) can take minutes. Evaluation jobs should stream intermediate scoring progress via Server-Sent Events (SSE).
- **Target Implementation:**
  - Add `/api/evaluation/jobs/{job_id}/stream` leveraging `EventBroker` to emit progressive stage scores and query ranking events.

### Gap 6: Graph Perturbation & Noise Robustness Benchmarking
- **Current State:** Pipeline accuracy is evaluated against static source texts.
- **SOTA Practice:** Robustness testing tests the model under text perturbations (adversarial typos, sentence order shuffling, entity name synonym swaps) to compute a **Robustness Degradation Factor (RDF)**:
  $$\text{RDF} = 1.0 - \frac{F_1(\text{perturbed})}{F_1(\text{clean})}$$
- **Target Implementation:**
  - Add stress-testing mutation strategies into `episteme_pipeline.evaluation.strategies`.
