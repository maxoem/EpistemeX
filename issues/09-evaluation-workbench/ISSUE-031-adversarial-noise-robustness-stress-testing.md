# [ISSUE-031] Adversarial Noise Robustness Benchmarking & RDF Degradation Curves

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-031` |
| **Component(s)** | `packages/episteme-studio` (`domain/evaluation.py`, `adapters/evaluation_adapter.py`, `services/evaluation_service.py`, `api/evaluation.py`, `frontend/src/panels/`) |
| **Roadmap Horizon** | **Horizon 2** (Adversarial Stress Testing & Robustness) |
| **Priority** | **Medium** |
| **Status** | `Open` |
| **Source Ref** | SOTA Review Gap 6; `episteme_pipeline.evaluation.strategies` |

---

## 1. Problem Statement & Motivation

Knowledge extraction models evaluated exclusively on clean, curated scientific texts often fail catastrophically in production when encountering OCR noise, authorial typos, terminology drift, or irregular syntax.

Commit `529df16` implemented text perturbation strategies within `episteme-pipeline` to compute the **Robustness Degradation Factor (RDF)**:
$$\text{RDF} = 1.0 - \frac{F_1(\text{perturbed})}{F_1(\text{clean})}$$
measuring the rate at which extraction accuracy collapses under adversarial noise.

However, **Episteme Studio has no endpoints to trigger stress-testing runs or visualize degradation curves**:
1. Users cannot trigger a perturbation sweep from the Studio interface to evaluate a pipeline's resilience.
2. Users cannot view degradation curve charts plotting $F_1$, MCC, and Poset validity against noise rates $\eta \in [0.0, 0.30]$ across perturbation modalities (typo insertion, synonym substitution, sentence shuffling).

---

## 2. Functional Requirements

### 2.1 Domain Schema & Contracts (`episteme_studio.domain.evaluation`)

Define clean Pydantic domain models for stress testing (strictly adhering to rule D-01):

```python
class PerturbationType(StrEnum):
    TYPO_INSERTION = "typo_insertion"
    SYNONYM_REPLACEMENT = "synonym_replacement"
    SENTENCE_SHUFFLE = "sentence_shuffle"
    COMPOSITE = "composite"

class PerturbationSweepPoint(BaseModel):
    noise_level: float               # e.g., 0.05, 0.10, 0.20
    f1_score: float
    mcc_score: float
    poset_dag_valid: bool
    rdf_delta: float                 # Degradation factor at this noise level

class NoiseRobustnessReportDetail(BaseModel):
    evaluation_id: str
    run_id: str
    overall_rdf: float               # Overall Robustness Degradation Factor
    is_resilient: bool               # True if overall_rdf < 0.15
    baseline_f1: float               # Clean F1 score
    worst_case_f1: float
    breakdown_by_perturbation: dict[str, list[PerturbationSweepPoint]]
    chart_series: dict[str, Any]     # Formatted for frontend plotting

class StressTestRequest(BaseModel):
    run_id: str
    benchmark_id: str | None = None
    perturbation_types: list[PerturbationType] = Field(
        default_factory=lambda: [PerturbationType.TYPO_INSERTION, PerturbationType.SYNONYM_REPLACEMENT]
    )
    noise_levels: list[float] = Field(default_factory=lambda: [0.05, 0.10, 0.20])
```

### 2.2 Adapter Implementation (`EvaluationAdapter`)
- In `EvaluationAdapter`:
  - Interface with `episteme_pipeline.evaluation.strategies` to execute perturbation sweeps across specified noise levels.
  - Collect evaluated metrics at each step and compute per-modality RDF values.
  - Format chart series with noise rate on the x-axis and metric scores on the y-axis.

### 2.3 Studio API Endpoints (`episteme_studio.api.evaluation`)
Expose:
- `POST /api/evaluation/stress-test`
  - Body: `StressTestRequest`
  - Returns: `NoiseRobustnessReportDetail` (HTTP 201)
- `GET /api/evaluation/reports/{evaluation_id}/robustness`
  - Returns: `NoiseRobustnessReportDetail`

### 2.4 Frontend Integration (`frontend/src/panels/EpistemicCharts.tsx`)
- Implement `RobustnessDegradationCard`:
  - Multi-line chart (ECharts) plotting $F_1$ and MCC curves across noise levels $[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]$.
  - Visual degradation threshold line (e.g. 80% of baseline).
  - Headline RDF score badge:
    - $\text{RDF} < 0.10$: Green (Highly Resilient).
    - $\text{RDF} \in [0.10, 0.25]$: Amber (Moderately Fragile).
    - $\text{RDF} > 0.25$: Red (Brittle / Vulnerable).

---

## 3. Acceptance Criteria

- [ ] `domain/evaluation.py` defines `NoiseRobustnessReportDetail` and `StressTestRequest`.
- [ ] `POST /api/evaluation/stress-test` triggers noise sweeps and computes the correct RDF score.
- [ ] `GET /api/evaluation/reports/{evaluation_id}/robustness` returns the structured curve dataset.
- [ ] Multiple perturbation types (typos, synonyms, shuffle) can be tested within a single request.
- [ ] Unit tests in `test_evaluation_backend.py` verify RDF mathematical calculations and serialization.

---

## 4. Key Target Files

- [`packages/episteme-studio/src/episteme_studio/domain/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/domain/evaluation.py)
- [`packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py)
- [`packages/episteme-studio/src/episteme_studio/services/evaluation_service.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/services/evaluation_service.py)
- [`packages/episteme-studio/src/episteme_studio/api/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py)
- [`packages/episteme-studio/frontend/src/panels/EpistemicCharts.tsx`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/panels/EpistemicCharts.tsx)
