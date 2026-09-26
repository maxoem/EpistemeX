# [ISSUE-030] Multi-Run Benchmark Leaderboard & Multi-Virtue Pareto Frontier

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-030` |
| **Component(s)** | `packages/episteme-studio` (`domain/evaluation.py`, `adapters/evaluation_adapter.py`, `services/evaluation_service.py`, `api/evaluation.py`, `frontend/src/panels/`) |
| **Roadmap Horizon** | **Horizon 2** (Cross-Run Analytics & Pareto Frontier) |
| **Priority** | **High** |
| **Status** | `Open` |
| **Source Ref** | Evaluation Workbench Gap Analysis (§3, §4); Nováček / Epistemetrics Pareto Virtues |

---

## 1. Problem Statement & Motivation

Currently, Episteme Studio provides the [`POST /api/evaluation/compare`](packages/episteme-studio/src/episteme_studio/api/evaluation.py) endpoint to compare exactly **two runs** (`run_id_a` vs `run_id_b`) side-by-side.

However, scientific research and ML engineering workflows require evaluating **10 to 50 experimental variants** (different foundation models, prompt ablations, chunking parameters, and reasoning budgets) against a common benchmark:
1. **No Matrix Leaderboard:** Analysts have no aggregated view showing how all runs rank across structuralist metrics (MCC, PFS), graph topology (poset $F_1$, DAG conformity), calibration (ECE), and downstream retrieval (MRR, Hits@10).
2. **Missing Multi-Virtue Pareto Frontier:** Epistemic evaluation is inherently multi-objective: an engineer must trade off extraction fidelity against token latency, computational cost, and probability calibration. Studio lacks an endpoint that computes the **Pareto-optimal frontier** to identify non-dominated runs.

---

## 2. Functional Requirements

### 2.1 Domain Schema & Contracts (`episteme_studio.domain.evaluation`)

Define clean Pydantic domain models for multi-run leaderboard and Pareto analysis:

```python
class LeaderboardEntry(BaseModel):
    run_id: str
    evaluation_id: str
    benchmark_id: str
    model_name: str | None = None
    prompt_strategy: str | None = None
    outcome: EvaluationOutcome
    evaluated_at: datetime
    metrics: dict[str, float]       # e.g., {'mcc': 1.0, 'f1': 0.88, 'ece': 0.04, 'mrr': 0.72}
    total_cost_usd: float | None = None
    duration_seconds: float | None = None
    is_pareto_optimal: bool = False

class ParetoFrontierPoint(BaseModel):
    run_id: str
    coordinates: dict[str, float]   # e.g., {'f1': 0.88, 'cost': 0.12, 'ece': 0.04}
    dominated_by: list[str] = Field(default_factory=list)

class LeaderboardRequest(BaseModel):
    benchmark_id: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    pareto_axes: list[str] = Field(default_factory=lambda: ["f1", "ece"])
    sort_by: str = "f1"
    ascending: bool = False

class LeaderboardResponse(BaseModel):
    benchmark_id: str | None
    total_runs: int
    entries: list[LeaderboardEntry]
    pareto_frontier: list[ParetoFrontierPoint]
    summary_markdown: str = ""
```

### 2.2 Pareto Optimization & Aggregation Logic (`EvaluationAdapter`)
- In `EvaluationAdapter`:
  - Query all persisted evaluation reports matching `benchmark_id` or `run_ids`.
  - Extract headline KPIs and execution metadata (duration, token costs from Langfuse observations if available).
  - Compute the Pareto frontier across specified axes (e.g. maximizing $F_1$ while minimizing ECE and cost):
    - A run $x$ dominates $y$ iff $x$ is no worse than $y$ in all objectives and strictly better in at least one objective.
    - Mark all non-dominated runs with `is_pareto_optimal = True`.
  - Format a markdown leaderboard table with rank medals (🥇, 🥈, 🥉).

### 2.3 Studio API Endpoints (`episteme_studio.api.evaluation`)
Expose:
- `POST /api/evaluation/leaderboard`
  - Body: `LeaderboardRequest`
  - Returns: `LeaderboardResponse`
- `GET /api/evaluation/leaderboard`
  - Query parameters: `benchmark_id: str | None = None`, `sort_by: str = 'f1'`
  - Returns: `LeaderboardResponse`

### 2.4 Frontend Integration (`frontend/src/panels/`)
- Create `BenchmarkLeaderboardView.tsx`:
  - Top Toolbar: Benchmark picker, column visibility toggle, and Pareto axis selector.
  - Interactive Table:
    - Sortable columns for each KPI (MCC, F1, Poset F1, ECE, MRR, Latency, Cost).
    - Status pills (`Pass`, `Warning`, `Fail`).
    - Pareto Star badge (⭐) indicating non-dominated runs.
    - Checkbox selection allowing multi-run selection to launch canvas diffs.
  - Interactive 2D/3D Scatter Plot (ECharts):
    - Plots runs along chosen axes (e.g. $F_1$ vs ECE vs Cost).
    - Highlights the Pareto convex hull line connecting optimal configurations.

---

## 3. Acceptance Criteria

- [ ] `domain/evaluation.py` defines `LeaderboardEntry`, `LeaderboardRequest`, and `LeaderboardResponse`.
- [ ] `POST /api/evaluation/leaderboard` successfully aggregates across multiple persisted evaluation reports.
- [ ] Pareto frontier calculation correctly identifies non-dominated runs for arbitrary pairs/triples of metrics.
- [ ] Markdown summary table formats cleanly with rank indicators.
- [ ] Unit tests in `test_evaluation_backend.py` verify multi-run aggregation and Pareto dominance edge cases.

---

## 4. Key Target Files

- [`packages/episteme-studio/src/episteme_studio/domain/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/domain/evaluation.py)
- [`packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py)
- [`packages/episteme-studio/src/episteme_studio/services/evaluation_service.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/services/evaluation_service.py)
- [`packages/episteme-studio/src/episteme_studio/api/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py)
- [`packages/episteme-studio/frontend/src/panels/RunCompareModal.tsx`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/panels/RunCompareModal.tsx)
