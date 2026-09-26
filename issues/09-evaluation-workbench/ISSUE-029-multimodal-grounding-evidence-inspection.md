# [ISSUE-029] Multi-Modal Deep Evidence Grounding & Bounding-Box Inspection

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-029` |
| **Component(s)** | `packages/episteme-studio` (`domain/evaluation.py`, `adapters/evaluation_adapter.py`, `services/evaluation_service.py`, `api/evaluation.py`, `frontend/src/panels/`) |
| **Roadmap Horizon** | **Horizon 2** (Multi-Modal Scientific Grounding) |
| **Priority** | **Medium** |
| **Status** | `Open` |
| **Source Ref** | SOTA Review Gap 3; `episteme_pipeline.evaluation.scorers.grounding` |

---

## 1. Problem Statement & Motivation

Scientific treatises (e.g. Newton's *Principia*, Einstein's 1905 papers) formulate fundamental hypotheses through **geometric diagrams, tabular observations, and mathematical formula blocks**, rather than prose sentences alone.

In commit `529df16`, `episteme-pipeline` added multi-modal grounding scorers (`episteme_pipeline.evaluation.scorers.grounding`) supporting bounding boxes $[x_0, y_0, x_1, y_1]$ and formula identifiers, computing the Alignment Grounding IoU ($AG_{\text{IoU}}$).

However, **Episteme Studio has no endpoint to retrieve or visualize multi-modal grounding evidence for evaluated components**:
1. When an analyst reviews an axiom in the Model Decomposition table or an edge in the HITL triage queue, clicking "View Evidence" either opens an empty panel or only shows a raw text chunk ID.
2. The user cannot see the bounding box overlay on the source PDF page or diagram, nor can they inspect why the grounding scorer penalized an alignment ($AG_{\text{IoU}} < 0.50$).

---

## 2. Functional Requirements

### 2.1 Domain Schema & Contracts (`episteme_studio.domain.evaluation`)

Define clean Pydantic domain models for multi-modal evidence inspection:

```python
class BoundingBoxCoordinates(BaseModel):
    page: int
    x0: float  # Normalized coordinates [0.0, 1.0]
    y0: float
    x1: float
    y1: float

class MultiModalEvidenceAnchor(BaseModel):
    anchor_id: str
    doc_id: str
    media_type: str               # 'text', 'figure', 'equation', 'table'
    verbatim_text: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox: BoundingBoxCoordinates | None = None
    formula_latex: str | None = None
    image_uri: str | None = None  # URL or static path to cropped snippet

class GroundingEvaluationDetail(BaseModel):
    component_id: str
    component_type: str           # 'entity', 'triple', 'axiom'
    label: str
    predicted_anchor: MultiModalEvidenceAnchor | None = None
    reference_anchor: MultiModalEvidenceAnchor | None = None
    iou_score: float              # AG_IoU in [0.0, 1.0]
    grounding_passed: bool        # True if iou_score >= threshold (e.g., 0.50)
    failure_reason: str | None = None
```

### 2.2 Adapter Implementation (`EvaluationAdapter`)
- In `EvaluationAdapter`:
  - Query intermediate extraction envelopes (`L1Document`, `L1Chunk`, `EvidenceTrail`) and gold benchmark references (`.jsonld`).
  - Extract page geometry and bounding box data associated with `component_id`.
  - Calculate normalized bounding boxes and construct image preview URIs if static rendering is available.
  - Return `GroundingEvaluationDetail`.

### 2.3 Studio API Endpoints (`episteme_studio.api.evaluation`)
Expose:
- `GET /api/evaluation/reports/{evaluation_id}/evidence/{component_id}`
  - Returns: `GroundingEvaluationDetail`
- `GET /api/runs/{run_id}/evidence/{component_id}`
  - Run-centric fallback endpoint.

### 2.4 Frontend Evidence Drawer Integration (`frontend/src/panels/StageProvenancePane.tsx`)
- In `NodeInspectorPanel.tsx` and `EdgeInspectorPanel.tsx`:
  - When the user selects the **Evidence** tab:
    - Display the **Multi-Modal Document Viewer**:
      - For text anchors: Highlight the verbatim span in context with character offset badges.
      - For figures and formulas: Render the cropped PDF page snippet with an interactive SVG bounding box overlay (green for gold anchor, blue for predicted anchor, overlapping region shaded).
    - Display the $AG_{\text{IoU}}$ metric card with pass/fail indicator.

---

## 3. Acceptance Criteria

- [ ] `domain/evaluation.py` defines `MultiModalEvidenceAnchor`, `BoundingBoxCoordinates`, and `GroundingEvaluationDetail`.
- [ ] `GET /api/evaluation/reports/{evaluation_id}/evidence/{component_id}` returns HTTP 200 with complete bounding box and text anchors.
- [ ] If gold standard reference contains a visual or formula anchor, `reference_anchor` is populated alongside `predicted_anchor` with calculated `iou_score`.
- [ ] Unit tests in `test_evaluation_backend.py` verify coordinate normalization and error handling for missing components.

---

## 4. Key Target Files

- [`packages/episteme-studio/src/episteme_studio/domain/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/domain/evaluation.py)
- [`packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/adapters/evaluation_adapter.py)
- [`packages/episteme-studio/src/episteme_studio/services/evaluation_service.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/services/evaluation_service.py)
- [`packages/episteme-studio/src/episteme_studio/api/evaluation.py`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py)
- [`packages/episteme-studio/frontend/src/panels/StageProvenancePane.tsx`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/panels/StageProvenancePane.tsx)
