# Episteme Studio: Knowledge Graph Evaluation Workbench
## Phase 2: Concrete UI/UX Design, Layout Proportions & Component Specifications

---

## 1. Design System & Visual Doctrine Alignment

All components adhere to the **"Hairline Grid & Flat Containment"** doctrine codified in [`design.md`](file:///Users/maxoehm/EpistemeX/packages/episteme-studio/design.md). The interface functions as a high-acuity scientific instrument (analogous to Palantir Foundry, Linear, or Weights & Biases), maintaining complete token symmetry between **Dark Mode** (analytical operations console) and **Light Mode** (academic scientific monograph).

### 1.1 Palette & Operational State Machine

| Token Role | Dark Theme | Light Theme | Usage in Evaluation Workbench |
|:---|:---|:---|:---|
| **Canvas** | `#09090B` | `#FFFFFF` | Global workspace ground, G6 graph canvas backplane |
| **Surface (Panels)** | `#18181B` | `#F8FAFC` | Docked sidebar rails, vitrine headers, data grid containers |
| **Surface Interactive** | `#27272A` | `#F1F5F9` | Hover states, active segmented pills, input text fields |
| **Rail Background** | `#111827` | `#F8FAFC` | Master benchmark tree, left navigation list |
| **Hairline Dividers** | `rgba(255, 255, 255, 0.08)` | `#E2E8F0` | Universal 1px Cartesian coordinate grid (0px outer margins) |
| **Operational Blue** | `#3B82F6` | `#2563EB` | Active running jobs, active table row border, primary focus |
| **True Positive (Emerald)**| `#10B981` | `#059669` | Verified graph nodes/edges, passed threshold badges |
| **False Positive (Coral)** | `#F87171` | `#DC2626` | Hallucinated entities/triples, overconfident errors |
| **Ghost Reference (Slate)** | `#71717A` | `#94A3B8` | Omitted gold-standard components (dashed stroke, 40% fill) |
| **Polarity Conflict (Amber)**| `#FBBF24` | `#D97706` | Inverted inference polarity (`SUPPORTS` vs. `ATTACKS`) |
| **Ambiguous Halo (Violet)** | `#A78BFA` | `#7C3AED` | Borderline entity alignment requiring review ($\tau \in [0.75, 0.88]$) |

### 1.2 Strict Typography Rules
* **Macro Structural Headers:** **Manrope** (`type-h1`: 24px/600, `type-h2`: 16px/500). Natural sentence/title case. Drop shadows and uppercase monospace headers are strictly prohibited.
* **Interface & Body:** **Inter** (`type-body`: 13px/400, `type-caption`: 11px/400).
* **Tabular Numeral Invariant:** All numerical statistics, confidence scores, $F_1$ deltas, ECE readouts, and execution latencies must enforce **`fontFeature: '"tnum" 1'`** (`body-tabular`) to eliminate horizontal layout jitter during real-time updates.
* **Machine Identifiers:** Strictly reserve **JetBrains Mono** (`type-mono`: 11px/400) for machine keys (`structural_anchor.global_thesis`), triple predicates, SHA run hashes, JSON payloads, and LaTeX expressions.

---

## 2. Page-by-Page Concrete Spatial Layouts

```
+----------------------------------------------------------------------------------------------------+
| TOP GLOBAL HEADER (48px Fixed): Logo | [Explorer] [Corpus] [Evaluation]* [Console] [Execution]   |
+----------------------------------------------------------------------------------------------------+
| CONTEXTUAL ACTION BAR (44px Fixed): Breadcrumbs · Scoping Pills · Quick Filters · Actions · Status |
+------------------------------------+---------------------------------------------------------------+
| PRIMARY CONTROLLER (Left Rail)     | CENTER WORKSPACE (Fluid, Edge-to-Edge Docked)                 |
| (280px - 320px Resizable)          |                                                               |
|                                    |                                                               |
| Mode A: Benchmark Catalog          | Page 1: Benchmark Catalog & Curation Vitrine                  |
| Mode B: Leaderboard Matrix         | Page 2: Multi-Virtue Pareto Studio & Comparison               |
| Mode C: Evaluated Run Reports      | Page 3: Deep Single-Run Evaluation Inspector                  |
|                                    |         (Zero-Box Sub-Tabbed Context Isolation)               |
+------------------------------------+---------------------------------------------------------------+
```

---

### Page 1: Benchmark Catalog & Curation Desk (`/evaluation/benchmarks`)

```
+--------------------------+------------------------------------------+------------------------------+
| BENCHMARK LIST (300px)   | SPECIFICATION VITRINE (Fluid)            | PRE-FLIGHT LINTER (380px)    |
+--------------------------+------------------------------------------+------------------------------+
| Filter: [Search datasets]| Header: Carnap-1928-Aufbau  [v1.1-gold]  | Pre-Flight Integrity Check   |
|                          | Domain: Logical Atomism / Epistemology   | [Valid: 0 Errors, 2 Warns]   |
| > Carnap-1928-Aufbau     |                                          |                              |
|   120 Ent · 340 Rel      | [Structural Invariants]                  | Invariant Checks:            |
|   Status: Verified       | - Total Entities: 120 (4 classes)        | [PASS] DAG Acyclicity (Strict)|
|                          | - Total Relations: 340 (12 predicates)   | [PASS] Root B(TN) = {T0}     |
|   Lakatos-Proofs-1976    | - Specialization Root: T0 (Aufbau Core)  | [WARN] 2 Weakly Grounded ADUs|
|   85 Ent · 210 Rel       |                                          | [PASS] No Dangling Edges     |
|   Status: Verified       | [Poset Specialization Graph Preview]     |                              |
|                          | [Miniature SVG Directed Acyclic Graph]   | Raw Specification:          |
|   Newton-Principia       |                                          | [CodeMirror JSON-LD Editor]  |
|   210 Ent · 620 Rel      | Primary Source Anchor:                   |                              |
|   Status: Draft          | doc_carnap_aufbau_de_1928.pdf (240 pp.)  | Action Triggers:             |
|                          |                                          | [Re-Validate] [Export JSONLD]|
| [+ Promote from Run]     | Actions:                                 |                              |
| [+ Register Benchmark]   | [Clone Benchmark] [Create Revision v1.2] |                              |
+--------------------------+------------------------------------------+------------------------------+
```

* **Left Pane (300px):**
  * Search bar + filter by domain taxonomy.
  * Master dataset list rendering entity count, relation count, and verification status.
  * Primary action buttons: `[+ Promote from Run]` (the "Golden Pathway" action) and `[+ Register Benchmark]`.
* **Center Vitrine (Fluid):**
  * Formal structuralist invariant summary: Total entities partitioned into Bourbaki classes ($M_p, M, M_{pp}, C, I$).
  * Interactive SVG thumbnail preview of the specialization poset hierarchy.
  * Primary document grounding provenance (bound PDF treatises).
* **Right Diagnostic Rail (380px):**
  * Automated pre-flight integrity linter output (`POST /api/evaluation/benchmarks/validate`).
  * Invariant checks: DAG Acyclicity (flags circular taxonomic loops), Root Element Conformity ($B(TN) = \{T_0\}$), Dangling Edge Detection.
  * Embedded CodeMirror JSON-LD editor with syntax error highlighting and line squiggles.

---

### Page 2: Benchmark Leaderboard & Multi-Virtue Pareto Studio (`/evaluation/leaderboard`)

```
+----------------------------------------------------------------------------------------------------+
| Persistent Bar (44px): Benchmark: [Carnap-1928-Aufbau v] | Sort: [F1 Score v] | [+ Evaluate Run]  |
+-------------------------------------------------------------+--------------------------------------+
| INTERACTIVE MULTI-VIRTUE PARETO FRONTIER (58% Width)        | BENCHMARK RUN MATRIX (42% Width)     |
|                                                             |                                      |
| Y-Axis: [Model Tenability δ* v]                             | Linear-Style High-Density Data Grid  |
| X-Axis: [Inference Cost ($)  v]                             | [Search runs...]                     |
|                                                             |                                      |
|   1.0 +----------* Run-082 (Pareto Optimal)                 | Run ID   Model    F1   δ*   Cost  P?|
|       |         /                                           | ------------------------------------ |
|   0.9 |        * Run-041                                    | Run-082  C-3.5S  0.92 0.94 $0.18 [P] |
|       |       /                                             | Run-041  GPT-4o  0.89 0.88 $0.12 [P] |
|   0.8 |      * Run-019 (Dominated)                          | Run-019  DS-R1   0.86 0.74 $0.06 [ ] |
|       |     /                                               | Run-012  L-70B   0.78 0.62 $0.04 [ ] |
|   0.7 |    * Run-012                                        |                                      |
|       +---------------------------------------------        | [Select Run A] vs [Select Run B]     |
|      0.00    0.05    0.10    0.15    0.20    0.25           | [Compare Runs Side-by-Side]          |
+-------------------------------------------------------------+--------------------------------------+
| COLLAPSIBLE PAIRWISE DIFF DOCK (260px Height):                                                     |
| Run-082 (Claude 3.5 Sonnet) vs Run-041 (GPT-4o)                                                    |
| Δ F1: +0.031  |  Δ Tenability δ*: +0.062  |  Δ Polarity Conflicts: -4  |  Δ Cost: +$0.06           |
| Gained Triples: 14  |  Lost Triples: 3  |  Inverted Edges Corrected: 4                             |
+----------------------------------------------------------------------------------------------------+
```

* **Top Toolbar (44px):**
  * Benchmark dataset selector dropdown.
  * Primary metric sort toggle (`Macro F1`, `Bourbaki Tenability δ*`, `ECE`, `Inference Cost`).
  * Action button: `[+ Evaluate Run]` (opens fast post-hoc evaluation modal on cached run artifacts).
  * Action button: `[Launch Longitudinal Trajectory]` (routes to diachronic multi-run analyzer).
* **Left Upper Pane (58% Width):**
  * ECharts scatter canvas plotting runs in multi-dimensional objective space.
  * Axis configuration dropdowns (X: Cost, Latency, Token Count; Y: $F_1$, Tenability $\delta^*$, MRR, ECE).
  * Non-dominated Pareto frontier step-line connecting optimal configurations. Non-dominated runs render with an operational blue vertex and glowing halo.
  * Hovering over any vertex displays an analytical tooltip: Model Name, Prompt Strategy, Execution Date, Exact Scores.
* **Right Upper Pane (42% Width):**
  * Headless Linear-style data grid (fixed 40px row height, tabular numerals, click-to-sort headers).
  * Columns: `Run ID`, `Model Engine`, `Macro F1`, `Tenability δ*`, `Cost ($)`, `Pareto Pill`.
  * Multi-select checkboxes to select two runs for immediate pairwise differential analysis.
* **Collapsible Bottom Diff Dock (260px Height):**
  * Direct pairwise metric delta readout ($\Delta F_1$, $\Delta \delta^*$, $\Delta \text{ECE}$).
  * High-density list of gained triples, lost triples, and polarity corrections between Model A and Model B.

---

### Page 3: Run Evaluation Inspector (`/evaluation/reports/:evaluationId`)

#### Header & Persistent KPI Strip (Fixed 48px + 40px Contextual Sub-Nav)
* **Row 1 (48px):**
  * Breadcrumb: `Evaluation / Carnap-1928-Aufbau / Run-082 (Claude 3.5 Sonnet)`
  * Outcome Pill: `[PASS (94.2%)]` in Success Emerald.
  * Persistent KPI Strip:
    * `Macro F1: 0.924`
    * `ECE: 0.038`
    * `Tenability δ*: 0.941`
    * `Retrieval MRR: 0.812`
  * Action Bar: `[Export Publication LaTeX]` `[Download JSON-LD]` `[Tune Prompt in Execution]`.
* **Row 2 (40px Sub-Nav):**
  Zero-Box Segmented Sub-Tabs isolating analytical focus and preventing DOM bloat:
  `[Topological Canvas]` | `[Epistemic TheoryNet]` | `[Adjudication Queue (24)]` | `[Calibration Lab]` | `[Document Grounding]` | `[Retrieval & Stress]`

---

#### Sub-View 3.1: Topological Canvas Overlay
```
+------------------+---------------------------------------------------+-----------------------------+
| CANVAS HUD       | FULL-BLEED @antv/g6 CANVAS                        | TOPOLOGICAL ERROR QUAD      |
| (Floating 220px) |                                                   | (360px Fixed Dock)          |
+------------------+                                                   +-----------------------------+
| Alignment Filter:|         (Green: True Positive)                    | Selected Edge:              |
| [x] True Pos (88)|           [Qualia] ===has_constituent==> [Sensory]| id: rel_0492_sensory        |
| [x] False Pos (9)|                     \                             | Source: Qualia              |
| [x] Ghost FN (14)|                      \ (Red: Hallucination)       | Target: Sensory Experience  |
| [x] Polarity (3) |                       v                           | Predicate: has_constituent  |
|                  |            [Epistemic Given]                      |                             |
| Ghost Opacity:   |                     .                             | Alignment Status:           |
| [===|=======] 40%|                     . (Dashed: Ghost Omission)    | [FALSE_POSITIVE]            |
|                  |                     v                             |                             |
| Model Classes:   |            [Elementary Experience]                | Gold Target Match:          |
| [x] Mp  [x] M    |                                                   | None (Empirical Hallucin.)  |
| [x] Mpp [x] I    |                                                   | Similarity: 0.12            |
|                  |                                                   |                             |
| Ambiguous Halos: |                                                   | Verbatim Grounding Quote:   |
| 5 Borderline     |                                                   | "The elemental sensations   |
| [Resolve Drawer] |                                                   | cannot be partitioned..."   |
+------------------+---------------------------------------------------+-----------------------------+
```
* **Left HUD (220px Floating Dock):**
  * Toggles for True Positives (Green), False Positives (Coral Red), Ghost False Negatives (Slate Dashed), and Polarity Inversions (Amber).
  * Ghost Node Opacity slider ($0.1 - 1.0$).
  * Hull clustering toggle for Bourbaki classes ($M_p, M, M_{pp}, C, I$).
  * Ambiguous Halo indicator showing count of borderline entity merges ($\tau \in [0.75, 0.88]$) with `[Open Reconciliation Drawer]` button.
* **Center (Fluid):**
  * `@antv/g6` interactive WebGL canvas. Custom node and edge renderers displaying alignment colors, direction arrows, and ghost dashes.
* **Right Dock (360px):**
  * **The Topological Error Quad:** Displays predicted construct, candidate reference target, alignment category, similarity score, original LLM confidence rating, and verbatim grounding quote. Action link: `[Jump to Document BBox]`.

---

#### Sub-View 3.2: Epistemic & TheoryNet Inspector
```
+-------------------------------------------------------------+--------------------------------------+
| CASCADING BOURBAKI MODEL CLASS TREE GRID (56% Width)        | POSET DAG & POLARITY MATRIX (44%)    |
+-------------------------------------------------------------+--------------------------------------+
| Bourbaki Structuralist Completeness (Conditional Cascading) | Specialization Poset Hierarchy       |
| [!] 4 Staged Adjudications Pending Batch Commit (⌘⏎)        | Status: [CYCLIC VIOLATION DETECTED]  |
|                                                             | Root Conformity: B(TN) = {T0} [FAIL] |
| Component Class        Ref  Pred  Match  Coverage  Status   | Transitive Reduction F1: 0.812       |
| ----------------------------------------------------------- | Transitive Reachability F1: 0.840    |
| > Mp (Potential Models)  12    11     10    83.3%   Active  |                                      |
|   v Axiom-01 (Space)      1     1      1   100.0%   [PASS]  | Cyclical Edge Violations (1 Cycle):  |
|   v Axiom-02 (Time)       1     0      0     0.0%   [ROOT]  | Cycle 1: Hyp_04 -> Lem_12 -> Ax_01   |
| > M (Actual Models)      24    20     18    75.0%   Active  |          -> Hyp_04                   |
|   v Sub-Model 02-A        1     0      0     0.0%   [MASK]  | Offending Edge: Lem_12 -[PROVES]->   |
| > Mpp (Partial Pot.)     18    17     17    94.4%   [PASS]  | Action: [Isolate Cycle on Canvas]    |
| > C (Constraints)         8     7      7    87.5%   [PASS]  |                                      |
| > I (Intended Applic.)   30    24     22    73.3%   Active  | Inferential Polarity Concordance     |
|   v Empirical Claim 08    1     0      0     0.0%   [MASK]  | Polarity Accuracy: 96.2%             |
|                                                             | Conflict Rate: 3.8% (3 pairs)        |
| Note: Structural DAG & reachability metrics refresh upon    | Inverted Polarity Pairs:             |
| batch commit. Scalar F1 preview is shown in global header.  | [Axiom-04] -x-> [Hypothesis-12]      |
+-------------------------------------------------------------+--------------------------------------+
```
* **Left Pane (56% Width):**
  * **Cascading Bourbaki Model Tree Grid:** Enforces conditional topological penalty. When parent axiom `Axiom-02 (Time)` fails in $M_p$, child models `Sub-Model 02-A` in $M$ and `Empirical Claim 08` in $I$ are marked **`[MASK: CASCADE_MASKED_ORPHAN]`** with muted typography rather than double-penalizing the pipeline.
  * **Staging Notice:** If the user has staged adjudications in Sub-View 3.3, a status pill indicates that global structural DAG invariants and reachability matrices remain frozen until explicit batch commit (`Cmd+Enter`), preventing false optimistic graph simulation.
* **Right Pane (44% Width):**
  * **Poset Integrity Telemetry & Cyclical Violations:**
    * When acyclicity fails, displays **`[CYCLIC VIOLATION DETECTED]`** and isolates the exact cycle path (e.g., $\text{Hypothesis\_04} \to \text{Lemma\_12} \to \text{Axiom\_01} \to \text{Hypothesis\_04}$).
    * Provides an instant action button: **`[Isolate Cycle on Canvas]`** that jumps directly to Sub-View 3.1, fades unrelated nodes, and centers the camera on the offending circular back-edge with an animated red pulse.
  * **Polarity Inversion Matrix:** High-density breakdown of severe dialectical errors (confusing `SUPPORTS` with `ATTACKS`), with direct links to the relevant text spans.

---

#### Sub-View 3.3: HITL Borderline Adjudication Queue
```
+----------------------------------------------------------------------------------------------------+
| Filter: [Pending (24)] [Adjudicated (8)] [All (32)] | Sim Range: [0.75 ===|=== 0.94] | [Commit: ⌘⏎]|
+--------------------------+------------------------------------------+------------------------------+
| QUEUE LIST (300px)       | ADJUDICATION TRIAD VIEW (Fluid)          | EVIDENCE & ALIASING (360px)  |
+--------------------------+------------------------------------------+------------------------------+
| [j] / [k] to navigate    | Predicted Triple:                        | Primary Source Passage:      |
|                          | (Observation_01)                         | "Every scientific concept    |
| > cand_082 (Sim: 0.86)   |  --[constitutes]-->                      | must ultimately resolve      |
|   Observation_01         | (Phenomenal_State)                       | into phenomenal experiences  |
|   constitutes            | Confidence: 0.88                         | that constitute observation."|
|   Phenomenal_State       |                                          | - Aufbau §64, Page 88        |
|                          | Candidate Gold Reference Match:          |                              |
|   cand_083 (Sim: 0.81)   | (Observation_01)                         | Semantic Similarity:         |
|   Constitution_System    |  --[forms_basis_of]-->                   | - Head Entity:   0.98        |
|   requires               | (Phenomenal_State)                       | - Predicate:     0.79        |
|   Logical_Basis          |                                          | - Tail Entity:   0.94        |
|                          | Decision Actions:                        |                              |
|   cand_084 (Sim: 0.89)   | [A] Accept as True Positive              | Schema Alias Mapping:        |
|   Axiom_Prime            | [R] Reject as False Positive             | [Map "constitutes" to:     ] |
|   entails                | [S] Map as Schema Alias                  | [forms_basis_of           v] |
|   Empirical_Claim        | [U] Undo Last Decision                   | [Apply Predicate Alias]      |
+--------------------------+------------------------------------------+------------------------------+
| HOTKEY HELPER: [A] True Positive  |  [R] False Positive  |  [S] Schema Alias  |  [⌘⏎] Commit Batch  |
+----------------------------------------------------------------------------------------------------+
```
* **Queue List (300px):**
  * Filterable queue of candidate alignments in the uncertainty band ($\tau \in [0.75, 0.94]$).
  * Fast keyboard traversal using `j` / `k` (or $\downarrow$ / $\uparrow$).
* **Center Triad (Fluid):**
  * Side-by-side presentation of Predicted Triple vs. Candidate Gold Triple.
  * Triple-component semantic similarity vector (Head, Predicate, Tail cosine similarity).
* **Right Evidence Pane (360px):**
  * Verbatim primary source quotation with highlighted entity mentions.
  * Schema Alias quick-picker (`cmdk` omnibar) to map unmapped predicates directly to canonical ontology relations.
* **Staging Buffer & Deterministic Batch Commit:**
  * Pressing `[A]`, `[R]`, or `[S]` stages the decision locally in `stagedAdjudications`, updating the queue item status instantly with an $\mathcal{O}(1)$ local score delta animation (`+0.024 F1 [Staged]`).
  * **No Auto-Debounce:** To allow deliberate reading and reflection without network race conditions or mid-deliberation interruptions, the UI never auto-submits on an idle timer.
  * Pressing `[U]` or `Cmd+Z` undoes the last staged decision in the local buffer.
  * Explicit commit: Pressing `Cmd+Enter` (or clicking `[Commit Batch (N)]`) locks the action, dispatches the batched items to `POST .../adjudicate-and-recalculate`, and updates the persistent report and topological graphs upon server acknowledgment.

---

#### Sub-View 3.4: Confidence Calibration & Reliability Lab
```
+-------------------------------------------------------------+--------------------------------------+
| 10-BIN RELIABILITY DIAGRAM (50% Width)                      | OVERCONFIDENT HALLUCINATIONS (50%)   |
+-------------------------------------------------------------+--------------------------------------+
| ECE: 0.038 [Well Calibrated] | MCE: 0.082 | Brier: 0.041    | Assertions with Conf > 0.85 & Emp=0  |
|                                                             |                                      |
| Accuracy                                                    | Assertion ID  Conf  Predicate Issue  |
|   1.0 |                   /| [Empirical Accuracy]           | ------------------------------------ |
|       |                  / |                                | triple_0812   0.99  proves    [FP]   |
|   0.8 |                 /  |                                | triple_0491   0.96  causes    [FP]   |
|       |               /*---| [Calibration Gap]              | triple_0114   0.89  refutes   [FP]   |
|   0.6 |              /     |                                |                                      |
|       |             /      |                                | Selected Hallucination Detail:       |
|   0.4 |            /       |                                | "Euler proved space is absolute..."  |
|       |           /        |                                | Source: Paragraph 14, Page 32        |
|   0.2 |          /         |                                | Error: Historic inversion (Euler was |
|       |        /           |                                | a relationist in this text).         |
|   0.0 +------+------+------+------+------+                  |                                      |
|       0.0   0.2    0.4    0.6    0.8    1.0   Confidence    | Action:                              |
|                                                             | [Tune Extraction Prompt in Execution]|
+-------------------------------------------------------------+--------------------------------------+
| INTERACTIVE THRESHOLD OPTIMIZER (Slider: τ = 0.85):                                                |
| Projected Precision: 94.2%  |  Projected Recall: 88.4%  |  Discarded Valid Triples: 12 (3.1%)      |
+----------------------------------------------------------------------------------------------------+
```
* **Left Pane (50% Width):**
  * ECharts 10-bin Reliability Diagram plotting Mean Predicted Confidence vs. Empirical Accuracy.
  * Shaded calibration gap ($|\text{conf} - \text{acc}|$) between the observed bars and the diagonal identity line.
  * Telemetry tiles: Expected Calibration Error (ECE), Maximum Calibration Error (MCE), and Brier Score.
* **Right Pane (50% Width):**
  * Filterable audit table of **High-Confidence Hallucinations** (claims asserted with confidence $> 0.85$ that failed verification).
  * Selected row inspection: displays the hallucinated statement, source paragraph context, failure rationale, and an actionable deep link: `[Tune Extraction Prompt in Execution]`.
* **Bottom Threshold Optimizer:**
  * Interactive slider for extraction threshold $\tau \in [0.50, 0.99]$, showing dynamic trade-offs between precision, recall, and discarded valid triples.

---

#### Sub-View 3.5: Multi-Modal Document Grounding & Reader
```
+------------------------------------------+---------------------------------------------------------+
| GROUNDING ATOM INSPECTOR (380px Fixed)   | FRAMED DOCUMENT STAGE VITRINE (Fluid)                   |
+------------------------------------------+---------------------------------------------------------+
| Selected Atom: atom_082_general_law      | Toolbar: Page 4 of 240 | Zoom: 100% | Multi-Page: Continuous|
| Type: Bourbaki Actual Model (M)          |                                                         |
| Label: Universal Gravitation Formulation | +-----------------------------------------------------+ |
| AG_IoU Score: 0.912 [PASSED]             | | PAGE 4 (Bottom)                                     | |
|                                          | | ...follows directly from Kepler's third harmonic    | |
| LaTeX Formula Verification:              | | law, establishing that the central force must vary  | |
| Extracted Equation:                      | | [=================================================] | |
|   F = G \frac{m_1 m_2}{r^2}              | | [ F = G \frac{m_1 m_2}{r^2}                       ] | |
| Reference Equation:                      | | [ where G represents the universal constant...   ] | |
|   F = \gamma \frac{M m}{d^2}             | | [=================================================] | |
| Structural Equivalence: PASS (Isomorphic)| +-----------------------------------------------------+ |
|                                          |                     | (Overflow Indicator: Span Cont.)  |
| Multi-Page Span Array:                   | +-----------------------------------------------------+ |
| - Span 1: Page 4, [0.12, 0.82, 0.88, 0.96| | PAGE 5 (Top)                                        | |
| - Span 2: Page 5, [0.12, 0.04, 0.65, 0.18| | [=================================================] | |
|                                          | | [ ...as verified across planetary orbits.         ] | |
| Bounding Box Coordinates:                | | [=================================================] | |
| [x0: 0.12, y0: 0.82, x1: 0.88, y1: 0.96] | | This conclusion forms the inductive foundation...   | |
+------------------------------------------+---------------------------------------------------------+
```
* **Left Pane (380px Fixed):**
  * Component ID, Bourbaki type, and Alignment Grounding IoU ($\text{AG\_IoU}$) score.
  * Side-by-side KaTeX formula verifier rendering the extracted LaTeX formula against the gold reference equation with syntactic equivalence testing.
  * Multi-page `SpanArray` metadata list.
* **Right Vitrine (Fluid):**
  * Virtualized continuous scroll document stage rendering the source PDF pages.
  * High-acuity SVG overlay rendering normalized bounding boxes $[x_0, y_0, x_1, y_1]$ scaled to rendered pixel dimensions.
  * Multi-page span connector indicator showing arguments spanning across the Page 4/5 boundary.

---

#### Sub-View 3.6: Downstream Competency Retrieval & Robustness
```
+----------------------------------------------------------------------------------------------------+
| DOWNSTREAM COMPETENCY QUERY RETRIEVAL MATRIX (50% Height)                                          |
| Global Metrics: MRR: 0.812  |  NDCG@10: 0.846  |  Hits@1: 72.4%  |  Hits@3: 88.1%  |  Hits@10: 95.2%|
|                                                                                                    |
| Query ID  Competency Question Text              Target Category   First Hit  Recip. Rank  Hits@10  |
| -------------------------------------------------------------------------------------------------- |
| Q-01      "How does Aufbau construct 3D space?" Logical Atomism   Rank 1     1.000        [PASS]   |
| Q-04      "What justifies relation description?"Epistemic Logic   Rank 1     1.000        [PASS]   |
| Q-12      "Which axiom refutes solipsism?"      Metaphysics       Rank 14    0.071        [FAIL]   |
|                                                                                                    |
| Failure Diagnosis for Q-12:                                                                        |
| Expected Gold Nodes: [Intersubjective_World, Other_Minds]                                          |
| Retrieved Top Candidate: [Autopsychological_Basis] (Similarity: 0.62)                              |
| Root Cause: Graph path broken between Intersubjective_World and Solipsism_Refutation.              |
+----------------------------------------------------------------------------------------------------+
| ADVERSARIAL STRESS TESTING & NOISE ROBUSTNESS CURVES (50% Height)                                  |
| Overall RDF Score: 0.884 [Resilient] | Baseline F1: 0.924 | Worst-Case Perturbed F1: 0.817         |
|                                                                                                    |
| F1 Score                                                                                           |
|   1.0 +--------*------------------*-------------------* [Synonym Drift: Robust]                    |
|       |         \                  \                   \                                           |
|   0.8 |          \                  *-------------------* [Typo Perturbation: Graceful]            |
|       |           *                                                                                |
|   0.6 |            \                                      [Sentence Shuffle: Vulnerable]           |
|       |             *-----------------------------------*                                          |
|   0.4 +--------------------------------------------------                                          |
|      0.00          0.05            0.10                0.20   Perturbation Rate (Noise Level)      |
|                                                                                                    |
| Action: [Trigger Synthetic Noise Sweep (Typo, Synonym, Shuffling)]                                  |
+----------------------------------------------------------------------------------------------------+
```
* **Top Half (50% Height):**
  * Competency question ranking data grid displaying MRR, NDCG@10, Hits@1/3/10.
  * Diagnostic breakdown for failing queries ($RR < 0.1$): compares the expected gold nodes against retrieved nodes, pinpointing missing graph traversals.
* **Bottom Half (50% Height):**
  * Robustness Degradation Factor (RDF) area chart plotting $F_1$ degradation across synthetic noise sweeps (Typographical errors, Synonym drift, Sentence order shuffling).
  * Trigger button: `[Trigger Synthetic Noise Sweep]` to run adversarial stress testing on demand.

---

## 3. Technical Architecture & State Machine

```
                                      useEvaluationStore (Zustand)
  +---------------------------------------------------------------------------------------------------+
  | - activeEvaluation: EvaluationReportDetail | null                                                 |
  | - graphOverlay: EvaluationGraphOverlay | null                                                     |
  | - adjudicationQueue: AdjudicationQueueItem[]                                                      |
  | - stagedAdjudications: Map<candidate_id, EdgeAdjudicationItem>                                    |
  | - optimisticScalarDeltas: Record<string, number> (F1, Precision, Recall)                          |
  | - hasUncommittedStaging: boolean                                                                  |
  | - activeSubTab: "canvas" | "epistemics" | "adjudication" | "calibration" | "grounding" | "retrieval"|
  | - activeComponentEvidence: GroundingEvaluationDetail | null                                       |
  | - isCommittingBatch: boolean                                                                      |
  +---------------------------------------------------------------------------------------------------+
                  |                                                    |
          Keyboard Actions (a, r, s)                         Explicit Batch Commit (⌘⏎ or Button)
                  v                                                    v
  +-----------------------------------+              +-----------------------------------+
  | Local Staging Buffer (No Auto-RPC)|              | Server RPC                        |
  | - Item marked 'staged' in queue   |              | POST /reports/{id}/adjudicate-    |
  | - O(1) ΔF1 scalar preview added   |              |      and-recalculate              |
  | - Topological invariants marked   |              | - Computes authoritative metrics  |
  |   [Pending Batch Commit]          |              | - Persists updated report         |
  | - Undoable via [u] / ⌘Z           |              | - Reconciles store state & clears |
  +-----------------------------------+              |   staging buffer                  |
                                                     +-----------------------------------+
```

### 3.1 Bounding Box Coordinate Scaling in Continuous Virtualized Documents
PDF coordinates arrive as normalized floating-point ratios $[x_0, y_0, x_1, y_1] \in [0.0, 1.0]$. In a virtualized continuous scrolling document viewer (`MultiPagePdfVitrine`), pages are stacked vertically with page-break gaps.

To position bounding boxes and continuous multi-page connecting splines without stacking elements at the top of the container, coordinates are translated using a **two-tier coordinate mapping**:

#### Tier 1: Global Continuous Container Coordinates (for Cross-Page Connecting Splines)
For an argument spanning from Page $p_{\text{start}}$ to Page $p_{\text{end}}$, the global top coordinate accounts for all preceding rendered page heights and inter-page vertical gaps ($\text{gap}_{\text{page}}$):

$$\text{box}_{\text{top\_global}} = \left( \sum_{i=1}^{p-1} \left( H_{\text{page}(i)} + \text{gap}_{\text{page}} \right) \right) + \left( y_0 \cdot H_{\text{page}(p)} \right)$$

$$\text{box}_{\text{left\_global}} = \left( x_0 \cdot W_{\text{page}(p)} \right) + \text{margin}_{\text{left\_page}(p)}$$

$$\text{box}_{\text{width}} = (x_1 - x_0) \cdot W_{\text{page}(p)}$$

$$\text{box}_{\text{height}} = (y_1 - y_0) \cdot H_{\text{page}(p)}$$

#### Tier 2: Page-Local SVG Highlight Layers (for High-Performance In-Page Rectangles)
Each rendered page card maintains an internal SVG highlight overlay (`position: absolute; inset: 0; pointer-events: none`). In-page highlight quads render directly in local page pixels:
$$\text{quad}_{\text{top}} = y_0 \cdot H_{\text{page}(p)}, \quad \text{quad}_{\text{left}} = x_0 \cdot W_{\text{page}(p)}$$
$$\text{quad}_{\text{width}} = (x_1 - x_0) \cdot W_{\text{page}(p)}, \quad \text{quad}_{\text{height}} = (y_1 - y_0) \cdot H_{\text{page}(p)}$$

A dedicated top-level canvas layer uses the **Tier 1 Global Coordinates** to draw cubic Bézier connecting splines crossing page boundaries from the bottom of Page $p$ to the top of Page $p+1$, accompanied by a continuous overflow badge.

### 3.2 Keyboard Navigation State Machine (`useEvaluationHotkeys`)
A dedicated global keyboard listener governs triage ergonomics while respecting form focus:

```typescript
export function useEvaluationHotkeys(handlers: {
  onAccept: () => void;
  onReject: () => void;
  onOpenAlias: () => void;
  onNext: () => void;
  onPrev: () => void;
  onCommit: () => void;
}) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Strictly bypass when user is typing in inputs or editors
      const target = e.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable ||
        target.closest(".cm-editor")
      ) {
        return;
      }

      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        handlers.onNext();
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        handlers.onPrev();
      } else if (e.key === "a" || e.key === "1") {
        e.preventDefault();
        handlers.onAccept();
      } else if (e.key === "r" || e.key === "2") {
        e.preventDefault();
        handlers.onReject();
      } else if (e.key === "s" || e.key === "3") {
        e.preventDefault();
        handlers.onOpenAlias();
      } else if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handlers.onCommit();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handlers]);
}
```

---

## 4. Frontend Component Hierarchy & File Architecture

```
packages/episteme-studio/frontend/src/
├── api/
│   ├── client.ts                      # + Added evaluation API methods
│   └── types.ts                       # Domain types (already complete)
├── store/
│   ├── evaluationStore.ts             # Unified Zustand store for active evaluation
│   └── leaderboardStore.ts            # Store for benchmark matrices and Pareto plots
├── shell/
│   └── AppShell.tsx                   # + Added "evaluation" tab to NAV_TABS
└── panels/
    └── evaluation/
        ├── EvaluationWorkspace.tsx    # Master router & layout coordinator
        ├── components/
        │   ├── EvaluationHeader.tsx   # Persistent run KPI strip & outcome pill
        │   ├── EvaluationSubNav.tsx   # Zero-box segmented sub-tabs
        │   ├── ExportReportModal.tsx  # LaTeX / JSON-LD / CSV export modal
        │   └── ActionableHookPill.tsx # Deep-links to ConfigEditor / Engine
        ├── catalog/
        │   ├── BenchmarkCatalogPage.tsx # Master-detail benchmark manager
        │   ├── PreFlightLinterRail.tsx  # DAG acyclicity & dangling edge inspector
        │   └── PromoteToGoldModal.tsx   # "Golden Pathway" run-to-gold converter
        ├── leaderboard/
        │   ├── LeaderboardPage.tsx    # Multi-run comparative matrix
        │   ├── ParetoFrontierPlot.tsx # ECharts 2D/3D scatter canvas
        │   └── PairwiseDiffDrawer.tsx # Collapsible run delta comparator
        └── inspector/
            ├── RunEvaluationInspector.tsx # Center coordinator for Sub-Views 3.1-3.6
            ├── canvas/
            │   ├── TopologicalCanvasView.tsx # G6 dual-graph overlay with ghosts
            │   ├── CanvasEvaluationHud.tsx   # Floating filter HUD & ghost opacity
            │   ├── TopologicalErrorQuad.tsx  # Docked error inspector
            │   └── AmbiguousAliasDrawer.tsx  # Non-blocking entity merge drawer
            ├── epistemics/
            │   ├── EpistemicTheoryNetView.tsx # Bourbaki tree & Poset DAG
            │   ├── CascadingBourbakiGrid.tsx  # Masked conditional dependency grid
            │   └── PolarityConflictMatrix.tsx# Argument polarity inversion breakdown
            ├── adjudication/
            │   ├── AdjudicationDeskView.tsx   # 3-pane HITL triage workspace
            │   ├── AdjudicationQueueList.tsx  # Keyboard-navigable candidate queue
            │   ├── AdjudicationTriadCard.tsx  # Side-by-side triple comparison
            │   └── SchemaAliasOmnibar.tsx     # cmdk predicate alias quick-picker
            ├── calibration/
            │   ├── CalibrationLabView.tsx     # ECharts reliability diagram
            │   ├── OverconfidenceTable.tsx    # Assertions with conf > 0.85 & emp=0
            │   └── ThresholdOptimizerBar.tsx  # Precision/Recall tradeoff slider
            ├── grounding/
            │   ├── DocumentGroundingView.tsx  # Two-pane multimodal inspector
            │   ├── MultiPagePdfVitrine.tsx    # PDF.js virtualized canvas with BBoxes
            │   └── LatexFormulaCard.tsx       # Side-by-side KaTeX equation verifier
            └── retrieval/
                ├── RetrievalDiagnosticsView.tsx # Competency query breakdown & RDF
                ├── CompetencyRankingTable.tsx   # MRR/NDCG query ranking matrix
                └── NoiseRobustnessPlot.tsx      # RDF perturbation sweep curves
```

### 4.1 Cross-Module Action Hooks & Deep Navigation Contracts
To close the feedback loop between analytical diagnostics and pipeline configuration, action pills in the Evaluation Workbench dispatch strongly-typed routing mutations to existing application stores:

1. **Schema Drift Hook (`openPredicateInEngine`):**
   * *Trigger:* Unmapped predicate or vocabulary drift flagged in evaluation report.
   * *Target:* `AppShell.setActiveTab("engine")`.
   * *Store Dispatches:*
     ```typescript
     useEngineSettingsStore.getState().setActiveCategory("unmapped");
     useEngineSettingsStore.getState().setUnmappedSubTab("discovered");
     useEngineSettingsStore.getState().setSelectedUnmapped(new Set([predicateName]));
     ```
2. **Ontology Dialectical Criteria Hook (`openArgRelationInEngine`):**
   * *Trigger:* Argument polarity conflict on inferential edge (e.g., `SUPPORTS` inverted to `ATTACKS`).
   * *Target:* `AppShell.setActiveTab("engine")`.
   * *Store Dispatches:*
     ```typescript
     useEngineSettingsStore.getState().setActiveCategory("ontology");
     useEngineSettingsStore.getState().setOntologySubTab("arg_relations");
     useEngineSettingsStore.getState().setSelectedItem({ type: "arg_relation", id: relationId });
     ```
3. **Prompt & Sampling Temperature Tuning Hook (`openPhasePromptInExecution`):**
   * *Trigger:* High-confidence hallucination or extraction collapse on specific text chunk.
   * *Target:* `AppShell.setActiveTab("config")`.
   * *Store Dispatches:* Routes to target extraction phase in `ConfigEditor`, pre-populating the prompt test-run playground with the offending primary source passage.
4. **DAG Cycle Isolation Hook (`isolateCycleInCanvas`):**
   * *Trigger:* Cyclical dependency detected in Poset specialization hierarchy ($T_2 \to T_1 \to T_2$).
   * *Internal Inspector Dispatch:*
     * Switches sub-tab from Sub-View 3.2 to Sub-View 3.1 (`setActiveSubTab("canvas")`).
     * Filters G6 graph canvas to isolate the participating cycle node IDs: `[Hyp_04, Lem_12, Ax_01]`.
     * Centers the camera viewport with an animated bounding box focus, highlighting the circular back-edge with a pulsating amber/red hazard stroke.

---

## 5. Phased Implementation Roadmap

1. **Phase 2.1: API Client & Store Foundations**
   * Wire API methods in `api/client.ts` to backend routes (`/api/evaluation/*`).
   * Create `store/evaluationStore.ts` with optimistic mutation logic and debounced RPC batching.
2. **Phase 2.2: Shell & Navigation Integration**
   * Add `"evaluation"` (`"Evaluation"`, icon: `Activity` / `Award`) to `NAV_TABS` in `AppShell.tsx`.
   * Register the root `EvaluationWorkspace` in `App.tsx`.
3. **Phase 2.3: Page 1 (Benchmark Catalog & "Golden Pathway")**
   * Build `BenchmarkCatalogPage.tsx` with `PreFlightLinterRail.tsx`.
   * Implement `PromoteToGoldModal.tsx` to turn approved pipeline runs into immutable gold standards.
4. **Phase 2.4: Page 2 (Leaderboard & Multi-Virtue Pareto Studio)**
   * Implement `LeaderboardPage.tsx` and `ParetoFrontierPlot.tsx` with ECharts.
   * Add `PairwiseDiffDrawer.tsx` for side-by-side metric delta comparison.
5. **Phase 2.5: Page 3 Sub-Workspaces (Single-Run Inspector)**
   * Sub-View 3.1: G6 canvas overlay with ghost synthesis and Topological Error Quad.
   * Sub-View 3.2: Cascading Bourbaki Model Tree Grid and Poset DAG verification.
   * Sub-View 3.3: 3-pane Adjudication Desk with `useEvaluationHotkeys` and optimistic UI.
   * Sub-View 3.4: 10-bin Reliability Diagram and Overconfidence Hallucination Table.
   * Sub-View 3.5: Multi-page PDF stage vitrine with normalized BBox scaling and KaTeX verifier.
   * Sub-View 3.6: Competency question retrieval diagnostics and RDF noise curves.
6. **Phase 2.6: Academic Export & Cross-Module Action Hooks**
   * Implement publication-ready LaTeX table and JSON-LD export modals.
   * Add direct action deep-links from evaluation failure pills to `ConfigEditor` and `EngineSettings`.
