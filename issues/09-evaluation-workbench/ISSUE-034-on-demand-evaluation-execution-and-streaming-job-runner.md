# [ISSUE-034] On-Demand Evaluation Execution, Asynchronous Job Orchestration & Streaming Telemetry

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-034` |
| **Component(s)** | `packages/episteme-studio` (`domain/evaluation.py`, `adapters/evaluation_adapter.py`, `services/evaluation_service.py`, `api/evaluation.py`, `frontend/src/panels/ExecuteEvaluationModal.tsx`), `packages/episteme-pipeline` (`episteme_pipeline.evaluation.harness.EvaluationHarness`) |
| **Roadmap Horizon** | **Horizon 1** (Evaluation Workbench & Execution Workflows) |
| **Priority** | **High** |
| **Status** | `Completed` |
| **Source Ref** | User Story & Evaluation Execution Workflow Analysis; SOTA Evaluation Review Gap 5 |

---

## 1. Problem Statement & Motivation

Currently, the user workflow in Episteme Studio is divided between **Pipeline Execution** (which produces a Run artifact containing Layer 1 chunks, Layer 2 entities/relations, and Layer 3 TheoryNets) and **Passive Evaluation Inspection** (which displays pre-existing evaluation reports, calibration curves, and graph overlays).

However, an evaluation in scientific knowledge extraction is **not just a passive static comparison / diff**:
1. **Active Computational Optimization:** Matching predicted graph structures against a gold standard requires solving maximum-weight bipartite matching (the Hungarian algorithm) over dense embedding spaces (Entity-Aware Graph BERTScore / GM-GBS).
2. **Gold-Free Intrinsic Verification:** An evaluation can run without any gold benchmark at all—computing Sneedian model-theoretic tenability under semantic blur $\delta^*$, Bourbaki structuralist quintuple consistency, Newman centrality distributions, and Quinean web-of-belief coherence.
3. **Downstream Task Execution:** Extrinsic evaluation requires actually executing a test suite of domain competency queries against the graph store, simulating multi-hop neuro-symbolic reasoning, and scoring Mean Reciprocal Rank (MRR) and NDCG@10.
4. **Adversarial Stress-Testing:** Noise robustness evaluation mutates source texts (simulating OCR typos, sentence shuffling, or synonym drift) and executes graph extraction slices dynamically to compute the Robustness Degradation Factor (RDF).

Without an explicit **"Run Evaluation" Execution Workflow**, users cannot:
- Trigger evaluation on an existing run on demand with custom parameters.
- Observe evaluation progress in real time during long-running benchmark or retrieval jobs.
- Cancel or inspect in-flight evaluation jobs.
- Seamlessly transition from a newly executed evaluation into the interactive Graph Overlay and HITL Adjudication Workbench.

---

## 2. User Stories

### User Story 1: The KG Extraction Engineer (On-Demand Benchmark Evaluation)
> **As a** Knowledge Graph Extraction Engineer,  
> **I want to** click an explicit "Run Evaluation" button on any completed run in Episteme Studio, choose a target gold benchmark (e.g. `kant-cpr-gold-v1`), adjust the semantic alignment threshold $\tau$ (e.g. $0.85$), and trigger the evaluation job directly from the UI,  
> **So that** I can immediately assess the precision, recall, and hallucination rate of newly tested prompts or models without writing manual Python or CLI scripts.

### User Story 2: The Computational Epistemologist (Gold-Free Intrinsic Assessment)
> **As a** Computational Epistemologist,  
> **I want to** evaluate a treatise extraction run without a gold standard by selecting the "Intrinsic Structuralist Integrity" mode,  
> **So that** I can verify whether the reconstructed TheoryNet satisfies Bourbaki model class decomposition, Sneedian tenability under blur $\delta^*$, and argumentative polarity balance before publishing the knowledge graph.

### User Story 3: The Benchmark Curator (Live Streaming Telemetry & Cancellation)
> **As a** Benchmark Curator,  
> **I want to** observe real-time stage progress (e.g., "Computing Hungarian GM-GBS Alignment... [45/120]", "Solving Tenability...", "Executing Competency Queries...") via Server-Sent Events (SSE) and have the ability to abort a runaway job,  
> **So that** long-running evaluations do not block my browser session or cause HTTP gateway timeouts (504).

---

## 3. Functional Requirements & Feature Breakdown

```
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    ON-DEMAND EVALUATION ARCHITECTURE                                    |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
|                                                                                                         |
|  [ExecuteEvaluationModal.tsx]  (Frontend UI)                                                            |
|    ├── Run Selector (lineage-aware)                                                                     |
|    ├── Evaluation Mode: [Benchmark Alignment | Intrinsic Epistemic | Competency Suite | Stress Test]     |
|    ├── Hyperparameters: Threshold tau [0.5 - 1.0], Tenability Blur delta* [0.0 - 0.5], Top-K [1 - 50]       |
|    └── [▶ Execute Evaluation] Button                                                                    |
|                                                                                                         |
|       │ POST /api/evaluation/jobs/run (HTTP 202 Accepted)                                               |
|       ▼                                                                                                 |
|  [EvaluationService.start_evaluation_job]  (Backend Service)                                            |
|    ├── Allocates EvaluationJobDescriptor (status: RUNNING)                                              |
|    ├── Spawns background asyncio task (_run_evaluation_job_worker)                                      |
|    └── Returns job_id to client immediately                                                            |
|                                                                                                         |
|       │ Subscribes: GET /api/evaluation/jobs/{job_id}/stream (SSE)                                      |
|       ▼                                                                                                 |
|  [EventBroker]  (Real-Time Streaming Telemetry)                                                         |
|    ├── Emits: "evaluation.stage.started" ("Hungarian Bipartite Alignment")                              |
|    ├── Emits: "evaluation.alignment.progress" (count: 45, total: 120)                                   |
|    ├── Emits: "evaluation.tenability.completed" (delta_star: 0.12, tenable: true)                        |
|    ├── Emits: "evaluation.retrieval.query_completed" (query: "Q1", mrr: 1.0)                            |
|    └── Emits: "evaluation.job.completed" (report_id: "eval_run_4dd7b5fb_01")                            |
|                                                                                                         |
|       │ Auto-Navigation & Lineage Linking                                                               |
|       ▼                                                                                                 |
|  [Evaluation Workbench Canvas & Panels]                                                                 |
|    ├── Opens Graph Overlay (ISSUE-026) with Green TP, Red FP, Ghost FN Nodes                            |
|    ├── Populates HITL Adjudication Queue (ISSUE-027)                                                    |
|    └── Updates Reliability Diagram (ISSUE-028) & Leaderboard (ISSUE-030)                                |
|                                                                                                         |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
```

### Feature 1: Interactive Evaluation Configuration Modal (`ExecuteEvaluationModal.tsx`)
- Triggered from the Run Detail header (`"Evaluate Run"`), the Runs Table actions menu, or the Evaluation Workbench toolbar.
- Provides a step-by-step configuration wizard:
  1. **Step 1: Evaluation Mode Selection:**
     - **Mode A: Gold Benchmark Alignment** (Select from registered benchmarks via `GET /api/evaluation/benchmarks`).
     - **Mode B: Intrinsic Epistemic Integrity** (Gold-free structuralist Bourbaki tenability, Newman centrality, QBAF argumentation balance).
     - **Mode C: Downstream Competency Retrieval** (Select competency query suite, configure hybrid vector/graph search).
     - **Mode D: Adversarial Noise Robustness** (Configure perturbation type: OCR typos, sentence shuffle, synonym drift, and noise ratio $\eta$).
  2. **Step 2: Scorer Strategy & Hyperparameter Sliders:**
     - Alignment strategy: `GM-GBS` (Graph BERTScore), `Exact`, or `Bourbaki Structuralist`.
     - Soft threshold $\tau \in [0.50, 1.00]$ (default: $0.85$).
     - Tenability blur factor $\delta^* \in [0.00, 0.50]$ (default: $0.10$).
     - Competency retrieval evaluation toggle: `[x] Enable Extrinsic Retrieval Scoring`.
  3. **Step 3: Execution Dispatch:**
     - Submits `POST /api/evaluation/jobs/run` and transitions the modal to a live progress stepper.

### Feature 2: Asynchronous Job Execution & Worker Supervision
- Long-running evaluations (especially on full book treatises or multi-hop retrieval suites) run in background asynchronous workers (`asyncio.create_task` or threadpool workers).
- Tracks complete lifecycle states:
  - `PENDING`: Job queued in scheduler.
  - `RUNNING`: Job actively calculating stages.
  - `COMPLETED`: Report synthesized and persisted to disk.
  - `FAILED`: Execution exception captured with stack trace.
  - `ABORTED`: User-initiated cancellation.
- Provides a cancellation endpoint:
  `POST /api/evaluation/jobs/{job_id}/cancel` to safely abort in-flight workers.

### Feature 3: Real-Time SSE Telemetry & Progress Stepper (`JobProgressStepper.tsx`)
- Frontend establishes an EventSource connection to `GET /api/evaluation/jobs/{job_id}/stream`.
- Receives structured `StudioEvent` payloads yielding stage-level progress:
  ```json
  {
    "id": "4",
    "event": "message",
    "data": {
      "seq": 4,
      "kind": "evaluation.stage.progress",
      "phase": "Alignment",
      "message": "Matching predicted triples against gold benchmark...",
      "payload": { "processed": 78, "total": 142, "current_f1": 0.81 }
    }
  }
  ```
- Renders an interactive multi-stage progress stepper:
  1. Graph Materialization & Envelope Loading
  2. Entity & Relation Alignment (Hungarian GM-GBS)
  3. Structuralist Tenability & Poset Verification
  4. Extrinsic Competency Retrieval Simulation
  5. Multi-Modal Evidence Anchoring & Report Materialization

### Feature 4: Post-Evaluation Lineage Linking & Auto-Navigation
- Upon job completion, the synthesized `EvaluationReportDetail` is automatically linked to the run metadata (`runs/{run_id}/evaluation`).
- The user is presented with immediate 1-click action buttons:
  - **"Open Alignment Overlay Canvas"** $\to$ Navigates to `/runs/{id}/canvas?overlay=true` with TP/FP/FN ghost nodes.
  - **"Review Borderline Candidates"** $\to$ Navigates to `/evaluation/adjudication?report_id={id}`.
  - **"View Calibration Curve"** $\to$ Opens Reliability Diagram modal.
  - **"Compare in Leaderboard"** $\to$ Opens `/evaluation/leaderboard`.

---

## 4. Implementation Files & Code References

### 4.1 Domain Schema Layer
* **File:** [`packages/episteme-studio/src/episteme_studio/domain/evaluation.py`](packages/episteme-studio/src/episteme_studio/domain/evaluation.py)
* **Contracts:**
  - `EvaluationJobStatus`: Enum (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `ABORTED`).
  - `EvaluationJobDescriptor`: Full job model containing `job_id`, `status`, `created_at`, `completed_at`, `report_id`, `error`, `report`.
  - `EvaluateRunRequest`: Execution payload containing `run_id`, `benchmark_id`, `strategy`, `parameters`, `evaluate_retrieval`.
  - `CancelEvaluationJobResponse`: Confirmation payload for aborted jobs.

```python
class EvaluationJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"

class CancelEvaluationJobResponse(BaseModel):
    job_id: str
    status: EvaluationJobStatus
    message: str
```

### 4.2 Adapter Layer (Anti-Corruption Layer)
* **File:** [`packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py`](packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py)
* **Implementation:**
  - `EvaluationAdapter.evaluate_run(request: EvaluateRunRequest) -> EvaluationReportDetail`:
    - Bridges to `episteme_pipeline.evaluation.harness.EvaluationHarness`.
    - Reads predicted run artifacts (`TheoryNet`, `L2TripleEnvelope`) from disk or memory.
    - Resolves the gold benchmark dataset (`.jsonld`).
    - Executes the configured scorers (`GraphBERTScoreEvaluator`, `ModelScorer`, `ExtrinsicRetrievalEvaluator`).
    - Emits progress events into the execution context callback.
    - Maps the pipeline's `EvaluationReport` into the Studio's decoupled `EvaluationReportDetail` domain model.

### 4.3 Service Layer & Worker Orchestration
* **File:** [`packages/episteme-studio/src/episteme_studio/services/evaluation_service.py`](packages/episteme-studio/src/episteme_studio/services/evaluation_service.py)
* **Implementation:**
  - `start_evaluation_job(broker, run_request, manifest_request)`: Registers job descriptor and spawns worker task.
  - `_run_evaluation_job_worker(job_id, ...)`: Asynchronous worker wrapping execution, error handling, and event publishing.
  - `cancel_evaluation_job(job_id: str) -> CancelEvaluationJobResponse`: Sets cancellation token, updates status to `ABORTED`, and publishes `evaluation.job.aborted` event.

### 4.4 REST API Layer
* **File:** [`packages/episteme-studio/src/episteme_studio/api/evaluation.py`](packages/episteme-studio/src/episteme_studio/api/evaluation.py)
* **Endpoints:**
  - `POST /api/evaluation/jobs/run` (HTTP 202 Accepted) $\to$ Spawns on-demand run evaluation job.
  - `POST /api/evaluation/jobs/manifest` (HTTP 202 Accepted) $\to$ Spawns batch manifest evaluation job.
  - `GET /api/evaluation/jobs/{job_id}` (HTTP 200 OK) $\to$ Polls current state and retrieved report.
  - `GET /api/evaluation/jobs/{job_id}/stream` (SSE EventSource) $\to$ Streams real-time telemetry events.
  - `POST /api/evaluation/jobs/{job_id}/cancel` (HTTP 200 OK) $\to$ Cancels in-flight evaluation.

### 4.5 Pipeline Evaluation Harness Integration
* **File:** [`packages/episteme-pipeline/episteme_pipeline/evaluation/harness.py`](packages/episteme-pipeline/episteme_pipeline/evaluation/harness.py)
* **Components:**
  - `EvaluationHarnessProtocol`: Formal protocol implemented by `EvaluationHarness`.
  - `evaluate_in_memory(predicted, gold, strategy, ...)`: In-memory evaluation method avoiding database round-trips.
  - Event hooks: Passes `EventEmitter` to receive pipeline-internal `EvaluationScoreLogged` and `EvaluationCompleted` events.

### 4.6 Frontend UI Components
* **Directory:** `packages/episteme-studio/frontend/src/`
* **Components to Wire:**
  - `panels/ExecuteEvaluationModal.tsx`: Step-by-step configuration dialog with benchmark dropdown and parameter sliders.
  - `panels/JobProgressStepper.tsx`: Interactive multi-stage progress component consuming SSE events.
  - `hooks/useEvaluationJob.ts`: Custom React hook managing EventSource lifecycle, reconnection, and state synchronization.

---

## 5. Acceptance Criteria & Verification Plan

1. **On-Demand Dispatch:**
   - Submitting `POST /api/evaluation/jobs/run` with a valid `run_id` returns `HTTP 202 Accepted` and a valid `job_id` within $< 50\text{ms}$.
2. **SSE Telemetry Streaming:**
   - Connecting to `GET /api/evaluation/jobs/{job_id}/stream` receives sequential events with monotonically increasing `seq` IDs.
   - Emits `evaluation.job.started`, intermediate progress updates, and `evaluation.job.completed`.
3. **Cancellation Resilience:**
   - Calling `POST /api/evaluation/jobs/{job_id}/cancel` on a running job stops execution immediately, marks status as `ABORTED`, and closes the SSE stream gracefully.
4. **Decoupled Architecture (Rule D-01):**
   - Pure domain models in `episteme_studio.domain.evaluation` have **0** dependencies on pipeline internal classes.
5. **Report Materialization & Lineage:**
   - Upon completion, the synthesized `EvaluationReportDetail` is discoverable via `GET /api/evaluation/reports/{id}` and `GET /api/runs/{run_id}/evaluation`.
   - The graph overlay endpoint `GET /api/evaluation/reports/{id}/graph-overlay` immediately yields valid TP, FP, and FN ghost nodes.
6. **Automated Unit & Integration Tests:**
   - Unit tests in `packages/episteme-studio/tests/test_evaluation_backend.py` covering job creation, polling, SSE streaming generator, and cancellation.
