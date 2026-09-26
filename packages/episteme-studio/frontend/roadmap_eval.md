# Episteme Studio: Evaluation Workbench
## Strategic Implementation Roadmap & Technical Traceability Matrix

---

## 1. Executive Strategy: Vertical Slice Architecture

To deliver the high-density Evaluation Workbench without regressions to the existing Episteme Studio platform (`Explorer`, `Corpus`, `Console`, `Execution`, `Engine`), the implementation is organized into **6 sequential phases**.

Each phase represents a **complete, testable vertical slice**:
$$\text{Backend Endpoint Verification} \longrightarrow \text{TypeScript API Client} \longrightarrow \text{Zustand State Slice} \longrightarrow \text{UI View Component} \longrightarrow \text{Integration Testing}$$

---

## 2. Issue & Codebase Traceability Matrix

Every analytical use case in Episteme Studio maps directly to an established backend issue specification (`ISSUE-026` through `ISSUE-033`), domain model, adapter implementation, and test suite:

| Aspect / Analytical Use Case | Issue Reference | Backend Source & Endpoint | Frontend Domain Types | Target UI Component |
|:---|:---|:---|:---|:---|
| **Visual Error Triage & Canvas Overlay** | [`ISSUE-026`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L869) | [`GET /api/evaluation/reports/{id}/graph-overlay`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L446) | [`EvaluationGraphOverlay`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L666) | `Sub-View 3.1: TopologicalCanvasView.tsx` |
| **HITL Borderline Adjudication Desk** | [`ISSUE-027`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L892) | [`GET /adjudication-queue`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L478)<br>[`POST /adjudicate-and-recalculate`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L513) | [`AdjudicationQueueResponse`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L688)<br>[`AdjudicateAndRecalculateResponse`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L701) | `Sub-View 3.3: AdjudicationDeskView.tsx` |
| **Confidence Calibration & Safety** | [`ISSUE-028`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L931) | [`GET /api/evaluation/reports/{id}/calibration`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L539) | [`CalibrationReportDetail`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L730) | `Sub-View 3.4: CalibrationLabView.tsx` |
| **Multimodal Document Grounding** | [`ISSUE-029`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L951) | [`GET /reports/{id}/evidence/{component_id}`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L570) | [`GroundingEvaluationDetail`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L763)<br>[`BoundingBoxCoordinates`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L743) | `Sub-View 3.5: DocumentGroundingView.tsx` |
| **Benchmark Leaderboard & Pareto Frontier**| [`ISSUE-030`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L971) | [`GET /api/evaluation/leaderboard`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L618)<br>[`POST /api/evaluation/compare`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L183) | [`LeaderboardResponse`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L802)<br>[`ComparativeEvaluationResponse`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L644) | `Page 2: LeaderboardPage.tsx` |
| **Adversarial Stress Testing & RDF** | [`ISSUE-031`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L992) | [`POST /api/evaluation/stress-test`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L652)<br>[`GET /reports/{id}/robustness`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L674) | [`NoiseRobustnessReportDetail`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L820) | `Sub-View 3.6: NoiseRobustnessPlot.tsx` |
| **Competency Query Diagnostics** | [`ISSUE-032`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L1016) | [`GET /reports/{id}/retrieval-diagnostics`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L696) | [`RetrievalDiagnosticsResponse`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L861) | `Sub-View 3.6: CompetencyRankingTable.tsx`|
| **Benchmark Curation & Academic Export**| [`ISSUE-033`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L1032) | [`POST /benchmarks/validate`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L728)<br>[`GET /reports/{id}/export`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L773) | [`BenchmarkValidationResult`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L877)<br>[`BenchmarkDescriptor`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L614) | `Page 1: BenchmarkCatalogPage.tsx`<br>`ExportReportModal.tsx` |
| **Bourbaki Decomposition & Poset Integrity**| Formal Epistemics | [`GET /api/evaluation/reports/{id}`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L75) | [`ModelDecompositionEntry`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L571)<br>[`PosetEvaluationDetail`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L581) | `Sub-View 3.2: EpistemicTheoryNetView.tsx` |
| **Lakatosian Diachronic Dynamics** | Longitudinal Studies | [`POST /api/evaluation/dynamics/trajectory`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/src/episteme_studio/api/evaluation.py#L243) | [`DynamicsTrajectoryResponse`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L655) | `LongitudinalTrajectoryStudio.tsx` |

---

## 3. Phased Execution Roadmap

```
+----------------------------------------------------------------------------------------------------+
|                                      PHASE EXECUTION DEPENDENCIES                                  |
+----------------------------------------------------------------------------------------------------+
|  Phase 0: Foundations & Shell Wiring                                                               |
|  (client.ts + useEvaluationStore + AppShell routing)                                               |
+----------------------------------------------------------------------------------------------------+
                   |                                                  |
                   v                                                  v
+------------------------------------+             +------------------------------------+
|  Phase 1: Macro Hubs               |             |  Phase 2: Topological Error Canvas |
|  - Benchmark Catalog (ISSUE-033)   |             |  - G6 Dual-Graph Overlay(ISSUE-026)|
|  - Leaderboard & Pareto (ISSUE-030)|             |  - Error Quad Inspector            |
+------------------------------------+             +------------------------------------+
                   |                                                  |
                   |                                                  v
                   |                               +------------------------------------+
                   |                               |  Phase 3: Formal Epistemic DAGs    |
                   |                               |  - Bourbaki Cascading Tree         |
                   |                               |  - Poset Cyclical Path Isolation   |
                   |                               |  - Lakatosian Dynamics Trajectory  |
                   |                               +------------------------------------+
                   |                                                  |
                   v                                                  v
+---------------------------------------------------------------------------------------+
|  Phase 4: HITL Triage & Calibration Lab                                               |
|  - Staging Buffer Adjudication Desk (ISSUE-027)                                       |
|  - 10-Bin Reliability Diagram & Thresholds (ISSUE-028)                                |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|  Phase 5: Grounding & Retrieval Diagnostics                                           |
|  - Two-Tier Continuous PDF Coordinate Scaling (ISSUE-029)                             |
|  - Competency Query Matrix & Adversarial Noise Curves (ISSUE-031, ISSUE-032)          |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
|  Phase 6: Cross-Module Hooks, Academic Export & Hardening                             |
|  - Deep Links to EngineSettings & ConfigEditor                                        |
|  - Publication-ready LaTeX Booktabs & JSON-LD (ISSUE-033)                             |
|  - Build verification & E2E sanity check                                              |
+---------------------------------------------------------------------------------------+
```

---

### Phase 0: Foundations, Contract Wiring & Shell Integration

#### Goal
Establish the TypeScript API client bindings, global state slice, and shell routing without regressions to existing panels.

#### Tasks
* [ ] **0.1 API Client Implementation (`src/api/client.ts`):**
  * Implement typed methods for all `/api/evaluation/*` routes referencing types in [`src/api/types.ts`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts).
* [ ] **0.2 State Store Definition (`src/store/evaluationStore.ts`):**
  * Create unified Zustand store supporting:
    * `activeReport`: `EvaluationReportDetail | null`
    * `activeSubTab`: `"canvas" | "epistemics" | "adjudication" | "calibration" | "grounding" | "retrieval"`
    * `stagedAdjudications`: `Map<string, EdgeAdjudicationItem>`
    * `optimisticScalarDeltas`: `{ f1: number, precision: number, recall: number }`
    * `isCommittingBatch`: `boolean`
* [ ] **0.3 Shell Navigation Integration (`src/shell/AppShell.tsx` & `src/App.tsx`):**
  * Add `"evaluation"` (`"Evaluation"`, icon: `Activity`) to `NAV_TABS` in `AppShell.tsx`.
  * Add lazy-loaded route in `App.tsx` rendering `EvaluationWorkspace.tsx`.

#### Definition of Done (DoD)
* `npm run build` succeeds.
* Clicking "Evaluation" in the top header navigates to the empty workspace shell with persistent selection.

---

### Phase 1: Macro Hubs (Benchmark Catalog & Leaderboard Studio)

#### Goal
Provide the benchmark dataset management desk and cross-run comparative Pareto analysis.

#### Reference Issues
* [`ISSUE-033`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L1032): Pre-Flight Benchmark Validation & Registration
* [`ISSUE-030`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L971): Multi-Run Benchmark Leaderboard Matrix & Pareto Frontier

#### Tasks
* [ ] **1.1 Benchmark Catalog Page (`src/panels/evaluation/catalog/BenchmarkCatalogPage.tsx`):**
  * Master-detail 3-column split: Dataset list (300px) $\to$ Invariant Vitrine (Fluid) $\to$ Pre-Flight Linter Rail (380px).
* [ ] **1.2 Pre-Flight Linter Rail (`src/panels/evaluation/catalog/PreFlightLinterRail.tsx`):**
  * Calls `validateBenchmark` to display strict DAG acyclicity, root element conformity $B(TN) = \{T_0\}$, and dangling edge detection.
  * Embedded CodeMirror JSON-LD editor with syntax error squiggles.
* [ ] **1.3 "Golden Pathway" Promotion Modal (`src/panels/evaluation/catalog/PromoteToGoldModal.tsx`):**
  * Converts an executed, visually corrected pipeline run into an immutable gold benchmark (`v1.0-gold`).
* [ ] **1.4 Benchmark Leaderboard Matrix (`src/panels/evaluation/leaderboard/LeaderboardPage.tsx`):**
  * Headless Linear-style table (40px fixed rows, tabular numerals `tnum`, click-to-sort headers).
  * 44px top toolbar with benchmark dataset picker and `[+ Fast Evaluate Run]` modal trigger.
* [ ] **1.5 Interactive Multi-Virtue Pareto Canvas (`src/panels/evaluation/leaderboard/ParetoFrontierPlot.tsx`):**
  * ECharts scatter canvas plotting runs in multi-dimensional objective space ($F_1$ vs. Bourbaki Tenability $\delta^*$ vs. Cost/Latency).
  * Renders non-dominated step-line and highlights Pareto-optimal runs with glowing blue vertices.
* [ ] **1.6 Collapsible Pairwise Run Diff Dock (`src/panels/evaluation/leaderboard/PairwiseDiffDrawer.tsx`):**
  * 260px collapsible drawer comparing Model A vs. Model B (metric deltas, gained triples, lost triples, inverted polarities).

#### Definition of Done (DoD)
* Curators can validate, upload, and promote benchmarks.
* Engineers can compare multiple pipeline models on the 2D Pareto frontier and inspect pairwise diffs.

---

### Phase 2: Deep Run Inspector Core & Topological Alignment Canvas

#### Goal
Deliver the single-run diagnostic cockpit (Sub-View 3.1) enabling visual error triage directly on the graph topology.

#### Reference Issues
* [`ISSUE-026`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L869): Visual Error Triage & Canvas Overlay (Ghost Node Synthesis)

#### Tasks
* [ ] **2.1 Run Evaluation Inspector Header (`src/panels/evaluation/components/EvaluationHeader.tsx`):**
  * Persistent 48px header displaying run breadcrumbs, outcome pill (`PASS` / `FAIL`), and persistent KPI strip ($F_1$, ECE, $\delta^*$, MRR) with tabular numerals.
  * Persistent 40px zero-box segmented sub-nav switching between Sub-Views 3.1 through 3.6.
* [ ] **2.2 G6 Dual-Graph Canvas (`src/panels/evaluation/inspector/canvas/TopologicalCanvasView.tsx`):**
  * `@antv/g6` canvas rendering True Positives (Green), False Positives (Coral Red), Ghost False Negatives (Slate Dashed, 40% opacity), and Polarity Inversions (Amber Hazard).
* [ ] **2.3 Canvas Evaluation HUD (`src/panels/evaluation/inspector/canvas/CanvasEvaluationHud.tsx`):**
  * Floating 220px dock with alignment filters, ghost node opacity slider, and Bourbaki hull clustering toggle.
* [ ] **2.4 Docked Topological Error Quad (`src/panels/evaluation/inspector/canvas/TopologicalErrorQuad.tsx`):**
  * 360px docked panel presenting predicted triple, gold reference match, similarity score, LLM confidence, verbatim quote, and a direct `[Jump to Document BBox]` link.
* [ ] **2.5 Ambiguous Entity Reconciliation Drawer (`src/panels/evaluation/inspector/canvas/AmbiguousAliasDrawer.tsx`):**
  * Non-blocking slide-out drawer listing borderline entity merges ($\tau \in [0.75, 0.88]$) for bulk review without blocking canvas interaction.

#### Definition of Done (DoD)
* Selecting any evaluated run renders the G6 dual-graph with synthesized ghost nodes for omissions and synchronizes selection to the Topological Error Quad.

---

### Phase 3: Formal Epistemic Invariants & Dialectical Verification

#### Goal
Provide theoretical coherence metrics (Sub-View 3.2) verifying Bourbaki structuralist decomposition, poset DAG integrity, and diachronic degeneration.

#### Reference Issues
* Bourbaki Decomposition: [`ModelDecompositionEntry`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L571)
* Poset DAG Hierarchy: [`PosetEvaluationDetail`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L581)
* Diachronic Trajectory: [`DynamicsTrajectoryResponse`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/api/types.ts#L655)

#### Tasks
* [ ] **3.1 Cascading Bourbaki Model Tree Grid (`src/panels/evaluation/inspector/epistemics/CascadingBourbakiGrid.tsx`):**
  * Hierarchical tree grid ($M_p \to M \to I$).
  * Implements **Conditional Cascade Masking**: If parent axiom $M_p$ fails, downstream actual models ($M$) and empirical applications ($I$) are labeled `[CASCADE_MASKED_ORPHAN]` to prevent artificial double-penalization.
* [ ] **3.2 Poset Specialization DAG & Cyclical Path Isolation (`src/panels/evaluation/inspector/epistemics/PosetDagViewer.tsx`):**
  * Telemetry readout: Strict DAG verification, root conformity $B(TN) = \{T_0\}$, Transitive Reduction $F_1$, and Reachability $F_1$.
  * **Cyclical Edge Violations Card:**
    * When acyclicity fails, displays the exact cycle path ($A \to B \to C \to A$).
    * Provides an instant `[Isolate Cycle on Canvas]` button that navigates to Sub-View 3.1, dims unrelated nodes, and centers on the circular back-edge with a pulsating red hazard stroke.
* [ ] **3.3 Polarity Conflict Matrix (`src/panels/evaluation/inspector/epistemics/PolarityConflictMatrix.tsx`):**
  * Breakdown of severe inferential errors (confusing `SUPPORTS` with `ATTACKS`), linking directly to source quotes.
* [ ] **3.4 Longitudinal Trajectory Studio (`src/panels/evaluation/longitudinal/LongitudinalTrajectoryStudio.tsx`):**
  * Multi-run diachronic trajectory view calling `POST /api/evaluation/dynamics/trajectory`.
  * Plots the Lakatosian Degeneration Index ($DI$) curve across historical treatise editions ($T_0 \to T_1 \to T_2$).

#### Definition of Done (DoD)
* Computational epistemologists can audit Bourbaki structuralist coverage, immediately isolate circular argument fallacies on the canvas, and inspect historical degeneration curves.

---

### Phase 4: Human-in-the-Loop Triage Desk & Safety Calibration Lab

#### Goal
Deliver keyboard-first relation adjudication (Sub-View 3.3) and uncertainty calibration diagnostics (Sub-View 3.4).

#### Reference Issues
* [`ISSUE-027`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L892): HITL Adjudication Queue & Dynamic Recalculation
* [`ISSUE-028`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L931): Confidence Calibration & Reliability Diagrams

#### Tasks
* [ ] **4.1 HITL Adjudication Desk (`src/panels/evaluation/inspector/adjudication/AdjudicationDeskView.tsx`):**
  * 3-pane layout: Queue list (300px) $\to$ Triad comparison card (Fluid) $\to$ Evidence & Schema Aliasing pane (360px).
* [ ] **4.2 Deterministic Staging Buffer (`src/panels/evaluation/inspector/adjudication/useAdjudicationStaging.ts`):**
  * Keypresses stage decisions locally in `stagedAdjudications` with instant $\mathcal{O}(1)$ local score delta animation (`+0.024 F1 [Staged]`).
  * **No idle auto-debounce:** Prevents network race conditions during deliberate reading.
  * Undo hotkey (`[U]` / `Cmd+Z`).
  * Explicit batch commit via `Cmd+Enter` or `[Commit Batch (N)]` button calling `POST .../adjudicate-and-recalculate`.
* [ ] **4.3 Keyboard Ergonomics (`src/panels/evaluation/inspector/adjudication/useEvaluationHotkeys.ts`):**
  * Hotkeys: `j`/`k` (traverse queue), `a` (Accept TP), `r` (Reject FP), `s` (Schema Alias omnibar), `Cmd+Enter` (Commit).
  * Strict bypass guard when focus is inside text fields, textareas, or code editors.
* [ ] **4.4 Confidence Calibration Lab (`src/panels/evaluation/inspector/calibration/CalibrationLabView.tsx`):**
  * ECharts 10-bin Reliability Diagram plotting Mean Predicted Confidence vs. Empirical Accuracy with shaded calibration gaps.
  * Telemetry readouts: Expected Calibration Error (ECE), Maximum Calibration Error (MCE), and Brier Score.
* [ ] **4.5 Overconfidence Hallucination Table (`src/panels/evaluation/inspector/calibration/OverconfidenceTable.tsx`):**
  * Audit table of assertions with confidence $> 0.85$ that failed verification, complete with source context and prompt-tuning action links.
* [ ] **4.6 Interactive Threshold Slider (`src/panels/evaluation/inspector/calibration/ThresholdOptimizerBar.tsx`):**
  * Dynamic slider ($\tau \in [0.50, 0.99]$) projecting Precision vs. Recall vs. Discarded Triples.

#### Definition of Done (DoD)
* Curators can triage borderline candidates with high-speed keyboard shortcuts, review side-by-side evidence, commit authoritative batches, and audit overconfident errors.

---

### Phase 5: Multimodal Document Grounding & Downstream Diagnostics

#### Goal
Verify document grounding in continuous PDF pages (Sub-View 3.5) and evaluate multi-hop competency retrieval with noise stress testing (Sub-View 3.6).

#### Reference Issues
* [`ISSUE-029`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L951): Multimodal Evidence Grounding Inspection
* [`ISSUE-032`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L1016): Competency Question Per-Query Diagnostics
* [`ISSUE-031`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L992): Adversarial Noise Robustness Stress Testing

#### Tasks
* [ ] **5.1 Multimodal Document Grounding Viewer (`src/panels/evaluation/inspector/grounding/DocumentGroundingView.tsx`):**
  * *Left Pane (380px):* Theory atom details, Alignment Grounding IoU ($\text{AG\_IoU}$), and side-by-side KaTeX formula verifier.
  * *Right Vitrine (Fluid):* `MultiPagePdfVitrine.tsx` rendering continuous virtualized PDF pages.
* [ ] **5.2 Two-Tier Coordinate Scaling Engine (`src/panels/evaluation/inspector/grounding/coordinateScaling.ts`):**
  * *Tier 1 (Global Continuous Container):*
    $$\text{box}_{\text{top\_global}} = \sum_{i=1}^{p-1} \left( H_{\text{page}(i)} + \text{gap}_{\text{page}} \right) + \left( y_0 \cdot H_{\text{page}(p)} \right)$$
  * *Tier 2 (Page-Local SVG Viewports):* Renders within-page bounding quads locally within each page card.
  * Draws continuous cubic Bézier splines across page boundaries for multi-page `SpanArray` arguments.
* [ ] **5.3 Competency Query Ranking Grid (`src/panels/evaluation/inspector/retrieval/CompetencyRankingTable.tsx`):**
  * Table rendering MRR, NDCG@10, Hits@1/3/10. Failing queries expand to compare expected gold nodes against retrieved nodes, pinpointing missing graph paths.
* [ ] **5.4 Adversarial Noise Robustness Curves (`src/panels/evaluation/inspector/retrieval/NoiseRobustnessPlot.tsx`):**
  * Area chart plotting Robustness Degradation Factor (RDF) curves across Typo, Synonym, and Sentence Shuffling perturbation sweeps.
  * `[Trigger Synthetic Noise Sweep]` action button.

#### Definition of Done (DoD)
* RAG architects can audit physical document bounding boxes across page breaks, verify LaTeX formulas, diagnose multi-hop retrieval paths, and evaluate noise robustness.

---

### Phase 6: Cross-Module Integration, Academic Export & Hardening

#### Goal
Close the feedback loop to pipeline configuration, provide academic export formats, and ensure production-grade performance.

#### Reference Issues
* Academic Export: [`ISSUE-033`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/tests/test_evaluation_backend.py#L1084)
* Cross-Module Navigation: [`EngineSettingsPage.tsx`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/panels/engine/EngineSettingsPage.tsx) & [`ConfigEditor.tsx`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/frontend/src/panels/ConfigEditor.tsx)

#### Tasks
* [ ] **6.1 Actionable Epistemic Hooks (`src/panels/evaluation/components/ActionableHookPill.tsx`):**
  * *Schema Drift Hook:* Routes to `EngineSettingsPage` (`activeCategory: "unmapped"`).
  * *Argument Polarity Hook:* Routes to `EngineSettingsPage` (`activeCategory: "ontology"`, `ontologySubTab: "arg_relations"`).
  * *Overconfidence Hook:* Routes to `ConfigEditor`, pre-loading the offending text in the phase prompt tester.
  * *DAG Cycle Isolation Hook:* Switches to Sub-View 3.1, isolating cycle node IDs on the G6 canvas.
* [ ] **6.2 Academic & Publication Export Modal (`src/panels/evaluation/components/ExportReportModal.tsx`):**
  * Exposes `GET /api/evaluation/reports/{id}/export?format={latex|jsonld|csv}`.
  * Interactive modal with syntax-highlighted preview and instant "Copy to Clipboard":
    * **LaTeX:** Publication-ready `\begin{table}` booktabs ready for insertion into papers.
    * **JSON-LD:** Standard semantic graph serialization with provenance headers.
    * **CSV:** Tabular metric summary.
* [ ] **6.3 Hardening & Performance Validation:**
  * Enforce WebGL/Canvas memory cleanup on sub-tab unmount (`g6Instance.destroy()`, `echartsInstance.dispose()`).
  * Verify that tabular numerals (`tnum`) are applied across all metrics.
  * Run test suite: `rtk uv run pytest` and `npm run build`.

#### Definition of Done (DoD)
* Full production build passes with zero TypeScript warnings.
* End-to-end user journeys pass across all 4 personas and 8 analytical use cases.

---

## 4. Verification & Testing Checklist

| Test Suite / Command | Scope Tested | Expected Result |
|:---|:---|:---|
| `rtk uv run pytest packages/episteme-studio/tests/test_evaluation_backend.py` | All backend evaluation endpoints (`ISSUE-026` - `ISSUE-033`) | 100% Pass |
| `cd packages/episteme-studio/frontend && npm run build` | TypeScript types, Zustand store, React components | Zero errors |
| Hotkey Triage Verification | Keyboard navigation `j`/`k`/`a`/`r`/`Cmd+Enter` | Zero main-thread lag, no race conditions |
| Continuous PDF BBox Alignment | Normalized bounding box scaling across page breaks | Accurate geometric alignment with zero Page 1 stacking |
| Cyclical DAG Isolation | Detection and canvas camera zoom to directed cycles | Offending back-edge highlighted in red pulse |
