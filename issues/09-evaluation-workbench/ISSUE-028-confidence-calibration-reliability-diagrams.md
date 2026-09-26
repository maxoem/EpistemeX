# [ISSUE-028] Confidence Calibration Diagnostics & Reliability Diagrams (ECE & Brier)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-028` |
| **Component(s)** | `packages/episteme-studio` (`domain/evaluation.py`, `adapters/evaluation_adapter.py`, `services/evaluation_service.py`, `api/evaluation.py`, `frontend/src/panels/`) |
| **Roadmap Horizon** | **Horizon 1 & 2** (Epistemic Reliability & Calibration) |
| **Priority** | **High** |
| **Status** | `Open` |
| **Source Ref** | SOTA Review Gap 1; `episteme_pipeline.evaluation.scorers.calibration` |

---

## 1. Problem Statement & Motivation

State-of-the-art knowledge graph extraction engines (using LLMs, cross-encoders, or heuristic confidence assigners) output continuous probability scores $c \in [0, 1]$ on extracted nodes, properties, and relations. However, high confidence often masks severe hallucinations: models frequently output 98% confidence on entirely fabricated triples.

While commit `529df16` implemented `CalibrationScorer` within `episteme-pipeline` to compute **Expected Calibration Error (ECE)**, **Maximum Calibration Error (MCE)**, and **Brier Score**, **Episteme Studio has no endpoint to expose structured calibration diagnostics to the frontend**:
1. **Cannot Render Reliability Diagrams:** The frontend chart library (`ECharts` in `EpistemicCharts.tsx`) requires bin-by-bin calibration data (mean confidence, empirical accuracy, sample count, and calibration gap across 10 equal-width bins) to plot the canonical reliability curve against the $y = x$ perfect-calibration diagonal.
2. **Missing Actionable Miscalibration Triage:** Knowing that ECE is $0.14$ does not help an engineer fix prompt hallucinations. The engineer needs to inspect the specific assertions that populate the high-confidence miscalibration zone ($c \ge 0.90$ with zero empirical support).

---

## 2. Functional Requirements

### 2.1 Domain Schema & Contracts (`episteme_studio.domain.evaluation`)

Define clean Pydantic domain models for calibration diagnostics (strictly adhering to rule D-01):

```python
class CalibrationBinDetail(BaseModel):
    bin_index: int
    bin_lower: float
    bin_upper: float
    sample_count: int
    mean_confidence: float
    empirical_accuracy: float
    calibration_gap: float  # |mean_confidence - empirical_accuracy|

class MiscalibratedAssertionItem(BaseModel):
    assertion_id: str
    assertion_type: str     # 'triple', 'entity', 'property'
    descriptor: str         # e.g., '(Newton, DISPROVES, GravitationalConstant)'
    confidence: float       # e.g., 0.96
    empirical_match: bool   # False (hallucination)
    discrepancy: float      # confidence - 0.0
    evidence_text: str | None = None
    rationale: str | None = None

class CalibrationReportDetail(BaseModel):
    evaluation_id: str
    run_id: str
    expected_calibration_error: float  # ECE
    maximum_calibration_error: float   # MCE
    brier_score: float
    is_well_calibrated: bool           # True if ECE < 0.05
    num_samples: int
    bins: list[CalibrationBinDetail]
    high_confidence_hallucinations: list[MiscalibratedAssertionItem]
    chart_series: dict[str, Any]       # Pre-structured ECharts dataset
```

### 2.2 Adapter Bridging (`episteme_studio.adapters.evaluation_adapter.EvaluationAdapter`)
- In `EvaluationAdapter`:
  - Connect to `episteme_pipeline.evaluation.scorers.calibration.CalibrationScorer`.
  - Extract confidence scores and ground-truth match indicators across all predicted entities and triples.
  - Compute 10 equal-width bins $[0.0-0.1, 0.1-0.2, \dots, 0.9-1.0]$.
  - Filter top miscalibrated items where `confidence >= 0.85` and `empirical_match == False`.
  - Package into `CalibrationReportDetail` and persist alongside evaluation reports.

### 2.3 Studio API Endpoints (`episteme_studio.api.evaluation`)
Expose:
- `GET /api/evaluation/reports/{evaluation_id}/calibration`
  - Query parameters: `min_confidence_filter: float = 0.85`, `limit: int = 50`
  - Returns: `CalibrationReportDetail`
- `GET /api/runs/{run_id}/evaluation/calibration`
  - Convenience endpoint resolving by `run_id`.

### 2.4 Frontend Visualization (`frontend/src/panels/EpistemicCharts.tsx`)
- Implement `ReliabilityDiagramCard`:
  - Bar/Line composite chart:
    - Blue bars: Sample count histogram per bin (secondary y-axis).
    - Red line with circular points: Observed empirical accuracy per bin (primary y-axis).
    - Gray dashed diagonal: Perfect calibration reference line ($y = x$).
    - Shaded red areas: Calibration gap (under-confidence or over-confidence).
  - Headline KPI pill displaying ECE and Brier score with color-coded severity:
    - ECE $\le 0.05$: Green (Well Calibrated).
    - ECE $\in (0.05, 0.12]$: Yellow (Moderately Miscalibrated).
    - ECE $> 0.12$: Red (Severely Overconfident).
  - Drill-down drawer displaying the **High-Confidence Hallucinations Ledger**.

---

## 3. Acceptance Criteria

- [ ] `domain/evaluation.py` defines `CalibrationReportDetail` and `CalibrationBinDetail` without pipeline dependencies.
- [ ] `adapters/evaluation_adapter.py` formats calibration output from `CalibrationScorer`.
- [ ] `GET /api/evaluation/reports/{evaluation_id}/calibration` returns HTTP 200 with 10 bins, ECE, MCE, Brier score, and miscalibrated assertions.
- [ ] Bins accurately reflect the $[0, 1]$ probability spectrum with non-negative sample counts.
- [ ] Unit tests in `test_evaluation_backend.py` verify calculations, bin edge boundaries, and JSON serialization.

---

## 4. Key Target Files

- [`packages/episteme-studio/src/episteme_studio/domain/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/domain/evaluation.py)
- [`packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py)
- [`packages/episteme-studio/src/episteme_studio/services/evaluation_service.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/services/evaluation_service.py)
- [`packages/episteme-studio/src/episteme_studio/api/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py)
- [`packages/episteme-studio/frontend/src/panels/EpistemicCharts.tsx`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/panels/EpistemicCharts.tsx)
