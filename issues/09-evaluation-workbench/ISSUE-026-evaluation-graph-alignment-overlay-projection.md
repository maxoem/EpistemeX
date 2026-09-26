# [ISSUE-026] Evaluation Graph Alignment Overlay & Visual Error Projection (`GraphView`)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-026` |
| **Component(s)** | `packages/episteme-studio` (`domain/evaluation.py`, `adapters/evaluation_adapter.py`, `services/evaluation_service.py`, `api/evaluation.py`, `frontend/src/graph/`) |
| **Roadmap Horizon** | **Horizon 1** (Evaluation Workbench & Interactive Alignment) |
| **Priority** | **Critical** / Blocker for Frontend Integration |
| **Status** | `Open` |
| **Source Ref** | Evaluation Workbench Gap Analysis (§3, §4) |

---

## 1. Problem Statement & Motivation

Currently, the studio evaluation endpoint [`GET /api/evaluation/reports/{evaluation_id}`](packages/episteme-studio/src/episteme_studio/api/evaluation.py) provides high-level scalars (MCC, PFS, F1, MRR) and raw identifiers:
```json
{
  "evaluation_id": "eval_principia_01",
  "omitted_components": ["str:CPM_Axiom_3_ActionReaction", "str:Gravitational_Force_Law"],
  "violations": [{"type": "disjointness", "node_id": "str:Impulse_Definition"}]
}
```

However, a knowledge graph analyst **cannot diagnose extraction failures from flat lists of string identifiers**. To understand *why* an axiom was omitted or *where* a hallucinated edge occurs, the user must view the evaluated entities and relations directly on the **Graph Canvas**:
1. **Missing Topological Context:** An omitted component ($FN$) is meaningless without seeing which parent theory atom it failed to connect to in the specialization poset.
2. **No Visual Error Projection:** The frontend canvas (`packages/episteme-studio/frontend/src/graph/GraphCanvas.tsx`) currently renders either the predicted run graph or a Neo4j snapshot. It has no mechanism to render:
   - **True Positives ($TP$, green):** Predicted entities/edges successfully aligned with gold standards.
   - **False Positives / Hallucinations ($FP$, red):** Entities/edges extracted by the model with no empirical basis in gold annotations.
   - **False Negatives / Omissions ($FN$, ghost gray nodes/edges):** Gold reference components that the pipeline completely missed, injected as "virtual ghost nodes" into the visualization.
   - **Borderline Matches ($BORDERLINE$, amber):** Soft alignments requiring human review ($\tau \in [0.80, 0.94]$).
   - **Polarity Inversions ($CONFLICT$, purple dashed):** Relations where direction or epistemic polarity (`SUPPORT` vs `ATTACK`) was inverted.

Without a dedicated backend endpoint projecting the evaluation alignment onto a unified `GraphView`, the frontend is forced to perform ad-hoc client-side joins between raw graph artifacts and report metrics, violating separation of concerns and degrading client performance.

---

## 2. Functional Requirements

### 2.1 Domain Schema & Contracts (`episteme_studio.domain.evaluation`)
Define pure Pydantic schema models representing the evaluation graph overlay without any dependencies on `episteme_pipeline.*` (strictly adhering to rule D-01):

```python
class NodeAlignmentStatus(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"  # Ghost node from gold reference
    BORDERLINE = "borderline"

class EdgeAlignmentStatus(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"  # Ghost edge from gold reference
    BORDERLINE = "borderline"
    POLARITY_CONFLICT = "polarity_conflict"

class EvaluationNodeOverlay(BaseModel):
    id: str
    label: str
    class_name: str | None = None  # e.g., 'actual_models', 'potential_models'
    symbol: str | None = None      # e.g., 'M', 'Mp', 'GC'
    alignment_status: NodeAlignmentStatus
    gold_id: str | None = None
    similarity_score: float = 1.0
    is_ghost: bool = False         # True if synthesized from gold reference
    properties: dict[str, Any] = Field(default_factory=dict)

class EvaluationEdgeOverlay(BaseModel):
    id: str
    source: str
    target: str
    predicate: str
    alignment_status: EdgeAlignmentStatus
    gold_predicate: str | None = None
    similarity_score: float = 1.0
    is_ghost: bool = False
    evidence_snippet: str | None = None

class EvaluationGraphOverlay(BaseModel):
    evaluation_id: str
    run_id: str
    benchmark_id: str | None = None
    nodes: list[EvaluationNodeOverlay]
    edges: list[EvaluationEdgeOverlay]
    summary_counts: dict[str, int] = Field(
        default_factory=lambda: {
            "tp_nodes": 0, "fp_nodes": 0, "fn_nodes": 0,
            "tp_edges": 0, "fp_edges": 0, "fn_edges": 0, "conflict_edges": 0
        }
    )
```

### 2.2 Anti-Corruption Adapter (`episteme_studio.adapters.evaluation_adapter.EvaluationAdapter`)
- Implement `build_graph_overlay(evaluation_id: str) -> EvaluationGraphOverlay`:
  1. Retrieve the predicted graph envelope (TheoryNet / L2Triples / GraphView) and target gold benchmark (`.jsonld`).
  2. Map predicted nodes to reference nodes via the alignment matrix produced by `SoftTripleAlignmentScorer` or `ModelDecompositionScorer`.
  3. Mark matched entities as `TRUE_POSITIVE`, unaligned predicted entities as `FALSE_POSITIVE`.
  4. For all reference entities absent from the predicted graph, synthesize **Ghost Nodes** (`is_ghost=True`, `alignment_status=FALSE_NEGATIVE`), retaining their Bourbaki symbols ($M, M_p, C$) and labels.
  5. Process edges analogously: compute predicted edge alignment, flag dialectical polarity inversions as `POLARITY_CONFLICT`, and synthesize ghost edges for omitted gold relationships.
  6. Calculate summary counts and cache the synthesized overlay in memory / disk alongside the evaluation report.

### 2.3 API Endpoints (`episteme_studio.api.evaluation`)
Expose the overlay for consumption by the Studio canvas:
- `GET /api/evaluation/reports/{evaluation_id}/graph-overlay`
  - Query parameters: `include_ghosts: bool = True`, `filter_status: str | None = None`
  - Returns: `EvaluationGraphOverlay`
- `GET /api/runs/{run_id}/evaluation/graph-overlay`
  - Shortcut finding the primary evaluation report associated with `run_id` and returning its graph overlay.

### 2.4 Frontend Visual Encoding (`packages/episteme-studio/frontend/src/graph/`)
- In `useGraphData.ts` and `nodeStyling.ts` / `edgeStyling.ts`:
  - When the user selects the **"Evaluation Overlay"** in `OverlaySwitcher.tsx`:
    - `TRUE_POSITIVE` nodes render with green halos / badges.
    - `FALSE_POSITIVE` nodes render with warning amber/red halos and a "Hallucinated" badge.
    - `FALSE_NEGATIVE` nodes render as translucent dashed-stroke "ghost nodes".
    - `POLARITY_CONFLICT` edges render with alternating red-purple dashed strokes.
  - Clicking any node opens `NodeInspectorPanel.tsx`, displaying predicted vs reference attributes and similarity scores.

---

## 3. Acceptance Criteria

- [ ] `domain/evaluation.py` defines `EvaluationGraphOverlay`, `EvaluationNodeOverlay`, and `EvaluationEdgeOverlay` without any pipeline imports.
- [ ] `adapters/evaluation_adapter.py` correctly reconstructs the dual-graph alignment, injecting ghost nodes for omitted components from `stnb_cpm_pilot.jsonld`.
- [ ] `GET /api/evaluation/reports/{evaluation_id}/graph-overlay` returns HTTP 200 with complete node/edge alignment classifications.
- [ ] Omitted components (e.g. missing Bourbaki axioms) appear in the response with `is_ghost=True` and `alignment_status="false_negative"`.
- [ ] Comprehensive unit tests in `test_evaluation_backend.py` verify overlay synthesis, ghost node injection, and summary counting.

---

## 4. Key Target Files

- [`packages/episteme-studio/src/episteme_studio/domain/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/domain/evaluation.py)
- [`packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py)
- [`packages/episteme-studio/src/episteme_studio/services/evaluation_service.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/services/evaluation_service.py)
- [`packages/episteme-studio/src/episteme_studio/api/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py)
- [`packages/episteme-studio/frontend/src/graph/styling/nodeStyling.ts`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/graph/styling/nodeStyling.ts)
- [`packages/episteme-studio/frontend/src/graph/styling/edgeStyling.ts`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/graph/styling/edgeStyling.ts)
