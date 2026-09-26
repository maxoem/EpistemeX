# [ISSUE-033] Custom Benchmark Registration, Pre-Flight Linter & Multi-Format Report Export

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-033` |
| **Component(s)** | `packages/episteme-studio` (`domain/evaluation.py`, `adapters/evaluation_adapter.py`, `services/evaluation_service.py`, `api/evaluation.py`, `frontend/src/panels/`) |
| **Roadmap Horizon** | **Horizon 1 & 2** (Benchmark Management & Academic Dissemination) |
| **Priority** | **Medium** |
| **Status** | `Open` |
| **Source Ref** | Evaluation Workbench Gap Analysis (§3, §4); D-01 Clean Architecture |

---

## 1. Problem Statement & Motivation

As research groups adapt Episteme to new scientific disciplines (e.g. quantum mechanics, evolutionary biology, or cognitive psychology), they need to introduce **custom domain gold standards and competency query suites**.

Currently, the evaluation subsystem has several key limitations:
1. **Read-Only Benchmark Discovery:** `GET /api/evaluation/benchmarks` only discovers pre-existing files on local disk. There is no API endpoint to upload or register new benchmark datasets.
2. **Missing Pre-Flight Linter:** Running an evaluation on a malformed gold dataset (e.g. invalid JSON-LD, duplicate atom identifiers, or a specialization graph containing cycles) causes late-stage pipeline crashes during in-memory evaluation. Users need an automated validation endpoint to verify benchmark datasets prior to evaluation.
3. **Restricted Export Formats:** `GET /api/evaluation/reports/{evaluation_id}/markdown` only returns raw Markdown. Computational philosophers and academic researchers require **publication-ready LaTeX tables** (e.g. Bourbaki model decomposition tables, comparative deltas, and poset integrity matrices) to insert directly into papers, as well as CSV and JSON-LD graph bundles for replication archives.

---

## 2. Functional Requirements

### 2.1 Domain Schema & Contracts (`episteme_studio.domain.evaluation`)

Define clean Pydantic domain models:

```python
class BenchmarkValidationIssue(BaseModel):
    severity: str                 # 'error', 'warning'
    rule_id: str                  # e.g., 'DAG_CYCLE_DETECTED', 'DUPLICATE_ID', 'MISSING_ROOT'
    message: str
    location: str | None = None   # JSON path or line number

class BenchmarkValidationResult(BaseModel):
    is_valid: bool
    total_entities: int = 0
    total_triples: int = 0
    is_dag: bool = True
    root_element: str | None = None
    issues: list[BenchmarkValidationIssue] = Field(default_factory=list)

class RegisterBenchmarkRequest(BaseModel):
    id: str
    name: str
    description: str
    task_type: str                # 'structuralist', 'extraction', 'argumentation', 'retrieval'
    gold_standard_jsonld: str     # Raw JSON-LD string or file path
    queries_yaml: str | None = None
```

### 2.2 Adapter Implementation (`EvaluationAdapter`)
- Implement `validate_benchmark(raw_content: str, format: str) -> BenchmarkValidationResult`:
  - Verify JSON/JSON-LD syntax.
  - Parse theory elements and verify unique entity IDs.
  - Construct the specialization graph using NetworkX:
    - Check for acyclicity (`nx.is_directed_acyclic_graph`).
    - If cycles exist, report `DAG_CYCLE_DETECTED` with the offending cycle path.
    - Check root conformity: ensure single root element $T_0$.
- Implement `export_report(evaluation_id: str, format: str) -> str`:
  - `latex`: Format standalone LaTeX tables using `booktabs` for Model Decomposition, Poset Metrics, and Comparative Deltas.
  - `csv`: Output a tabular CSV containing metric names, values, thresholds, and pass/fail indicators.
  - `jsonld`: Export the full evaluated graph with embedded evaluation annotations.

### 2.3 Studio API Endpoints (`episteme_studio.api.evaluation`)
Expose:
- `POST /api/evaluation/benchmarks/validate`
  - Body: `dict[str, str]` (raw content or filesystem path)
  - Returns: `BenchmarkValidationResult`
- `POST /api/evaluation/benchmarks`
  - Body: `RegisterBenchmarkRequest`
  - Returns: `BenchmarkDescriptor` (HTTP 201)
- `GET /api/evaluation/reports/{evaluation_id}/export`
  - Query parameter: `format: str = 'latex'` (choices: `latex`, `csv`, `jsonld`)
  - Returns: `PlainTextResponse` or `Response` with appropriate MIME type (`text/x-tex`, `text/csv`, `application/ld+json`).

### 2.4 Frontend Integration (`frontend/src/panels/`)
- In `PhaseCatalogDrawer.tsx` or a new `BenchmarkManagerModal.tsx`:
  - Provide a Drag & Drop upload zone for `.jsonld` and `.yaml` files.
  - Display real-time validation results (green checkmark if DAG is valid, red error list if cycles or schema errors exist).
- In `EvaluationReportView`:
  - Add an **Export** dropdown button: `Copy LaTeX Table`, `Download CSV`, `Download JSON-LD`.

---

## 3. Acceptance Criteria

- [ ] `domain/evaluation.py` defines `BenchmarkValidationResult`, `BenchmarkValidationIssue`, and `RegisterBenchmarkRequest`.
- [ ] `POST /api/evaluation/benchmarks/validate` detects cycles in specialization graphs and reports `is_dag = False` with the cycle nodes.
- [ ] `POST /api/evaluation/benchmarks` registers new benchmarks and persists them in the benchmark catalog.
- [ ] `GET /api/evaluation/reports/{evaluation_id}/export?format=latex` generates compilable LaTeX `booktabs` code.
- [ ] `GET /api/evaluation/reports/{evaluation_id}/export?format=csv` generates standard CSV rows.
- [ ] Unit tests in `test_evaluation_backend.py` verify validation, registration, and exports.

---

## 4. Key Target Files

- [`packages/episteme-studio/src/episteme_studio/domain/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/domain/evaluation.py)
- [`packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py)
- [`packages/episteme-studio/src/episteme_studio/services/evaluation_service.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/services/evaluation_service.py)
- [`packages/episteme-studio/src/episteme_studio/api/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py)
