# [ISSUE-024] SciGraph Evaluation Methodology (Soft Matching, Evidence Grounding & Downstream Querying)

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-024` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/evaluation/`, `evaluation/scorers/`), `packages/epistemetrics` |
| **Roadmap Horizon** | **Horizon 1 & 2** (Evaluation Integrity & Benchmark Harness) |
| **Priority** | High |
| **Status** | `Superseded` (by [ISSUE-030](../09-stnb-evaluation-capabilities/ISSUE-030-intrinsic-model-component-and-property-evaluation.md) and [ISSUE-032](../09-stnb-evaluation-capabilities/ISSUE-032-extrinsic-retrieval-attribute-fix-and-competency-testbed.md)) |
| **Source Ref** | Formerly tracked in `docs/TODO_FUTURE.md §1`, `docs/concepts/formal_graph_model.md` |

> [!NOTE]
> **SUPERSEDED**: This issue has been superseded by [`ISSUE-030`](../09-stnb-evaluation-capabilities/ISSUE-030-intrinsic-model-component-and-property-evaluation.md) (Model Component & Property Evaluation) and [`ISSUE-032`](../09-stnb-evaluation-capabilities/ISSUE-032-extrinsic-retrieval-attribute-fix-and-competency-testbed.md) (Competency Querying).


---

## 1. Problem Statement & Motivation
Rigorous empirical and epistemic validation of constructed theory graphs requires moving beyond exact-match string comparisons and ungrounded topological heuristics. In scientific and philosophical corpora, theoretical claims and arguments are inherently paraphrased, grounded in localized text spans, and expected to serve downstream scholarly querying.

To establish benchmark-grade credibility (drawing from SciGraph-LLM evaluation paradigms), the evaluation harness requires three targeted measurement suites:
1. **Semantic Soft-Matching for Paraphrased Claims**: Evaluating extracted Argument Components ($A$) against ground truth using sentence embedding thresholds rather than token-level exact matching.
2. **Evidence Grounding Precision & Coverage**: Quantifying whether extracted Epistemic Justification ($J$) spans accurately isolate textual evidence without under- or over-extraction.
3. **Downstream Query Utility**: Measuring whether the resulting graph can correctly resolve domain competencies and answer substantive scientific questions.

---

## 2. Functional Requirements
1. **Semantic Similarity for Claims (Soft Matching)**:
   - Provide an evaluation method that compares predicted argument propositions against reference gold claims using embedding cosine similarity:
     $$\text{sim}(t_{\text{pred}}, t_{\text{gold}}) \ge \tau \quad (\text{e.g., } \tau = 0.88)$$
   - Calculate soft Precision, Recall, and $F_1$ across claim sets, handling semantic variation in paraphrased natural language assertions.

2. **Evidence Grounding Metrics ($J$-Components)**:
   - Implement **Evidence Precision**: Ratio of correctly localized character/token spans against ground-truth evidence spans.
   - Implement **Evidence Coverage (Recall)**: Fraction of gold reference evidence spans successfully recovered by the pipeline's provenance anchors (`glp:textAnchor`).

3. **Downstream Query Accuracy Benchmark**:
   - Construct a templated competency query testbed (e.g., *"Which theory model explains phenomenon $X$?"*, *"What empirical statement attacks hypothesis $Y$?"*).
   - Evaluate whether graph traversal (Cypher / NetworkX) retrieves the correct theoretical answer, validating the graph's actual utility for AI reasoning.

---

## 3. Acceptance Criteria
- [ ] Claim evaluation module in `pipeline/evaluation/` supports embedding-based soft matching with configurable similarity thresholds.
- [ ] Grounding metrics measure character/token-level span overlap (Intersection over Union / Token F1) for evidence provenance.
- [ ] Evaluation harness includes an end-to-end question-answering benchmark verifying query accuracy against gold theory graphs.
- [ ] Unit tests in `packages/episteme-pipeline/tests/` verify scoring behavior on synthetic claim and evidence alignments.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/evaluation/`
- `packages/episteme-pipeline/evaluation/scorers/`
- `packages/episteme-pipeline/tests/test_evaluation_scaffolding.py`
