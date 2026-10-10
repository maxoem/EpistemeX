# [ISSUE-018] Entity-Aware Graph BERTScore (GM-GBS) Evaluation

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-018` |
| **Component(s)** | `packages/episteme-pipeline` (`evaluation/scorers/gm_gbs.py`) |
| **Roadmap Horizon** | **Horizon 1** (Evaluation Integrity & Benchmark Harness) |
| **Priority** | Critical / Blocker |
| **Status** | `Superseded` (by [ISSUE-030](../09-stnb-evaluation-capabilities/ISSUE-030-intrinsic-model-component-and-property-evaluation.md)) |
| **Source Ref** | [`review/26/09/evaluation_credibility_review.md §2.1`](review/26/09/evaluation_credibility_review.md#L30-L75) |

> [!NOTE]
> **SUPERSEDED**: This issue has been superseded by [`ISSUE-030: Comprehensive Intrinsic Evaluation: Model Component Decomposition & Full Property Subsumption`](../09-stnb-evaluation-capabilities/ISSUE-030-intrinsic-model-component-and-property-evaluation.md).


---

## 1. Problem Statement & Motivation
In [`evaluation/scorers/gm_gbs.py`](packages/episteme-pipeline/evaluation/scorers/gm_gbs.py#L59-L71), Graph BERTScore (GM-GBS) is intended to evaluate edge alignment between a predicted knowledge graph $G_{\text{pred}}$ and a ground-truth graph $G_{\text{gold}}$.

However, the implementation currently extracts only the edge relation labels:
```python
pred_edges = list(pred_graph.edges(data="label"))
gold_edges = list(gold_graph.edges(data="label"))
pred_labels = [str(data) for _, _, data in pred_edges]
gold_labels = [str(data) for _, _, data in gold_edges]
```
The subject and object endpoint nodes (`u` and `v`) are completely omitted from the similarity calculation. As a result:
1. A completely fabricated graph whose entities bear no resemblance to ground truth will score `gm_gbs = 1.0` as long as relation labels (e.g. `USED_FOR`, `PART_OF`) match the label distribution.
2. On datasets such as SciERC, the metric degenerates into a coarse relation-label classification check rather than graph structure / triple evaluation.
3. Any published benchmark using this metric is misleading.

---

## 2. Functional Requirements
1. **Triple-Level Soft/Hard Alignment**:
   - Redefine edge matching so an edge $e = (u, r, v) \in G_{\text{pred}}$ matches $e' = (u', r', v') \in G_{\text{gold}}$ if and only if:
     - Relation semantic similarity: $\text{sim}(r, r') \ge \tau_{\text{rel}}$, **and**
     - Endpoint alignment: $u$ matches $u'$ AND $v$ matches $v'$.
2. **Entity Matching Strategies**:
   - Provide configurable entity matching:
     - **Exact Match**: Case-insensitive string match on canonical name or node ID.
     - **Semantic Soft Match**: Pairwise cosine similarity between node names / descriptions using `embed_fn` with threshold $\tau_{\text{entity}}$ (e.g., $0.85$).
     - **Span Overlap**: Token/character span intersection if evaluating against extracted chunk mention anchors.
3. **Metric Precision, Recall, and F1**:
   - Calculate precision ($|E_{\text{matched\_pred}}| / |E_{\text{pred}}|$), recall ($|E_{\text{matched\_gold}}| / |E_{\text{gold}}|$), and $F_1$.
   - Return detailed alignment records including which predicted triples mapped to which gold triples.

---

## 3. Acceptance Criteria
- [ ] `GraphBERTScoreEvaluator.compute_matches` requires valid endpoint entity alignment in addition to relation label similarity.
- [ ] Synthetic test with perturbed/scrambled entities yields `score < 0.1` instead of `1.0`.
- [ ] Evaluator reports precision, recall, and F1 scores rather than a one-sided precision ratio.
- [ ] Deterministic unit tests in `packages/episteme-pipeline/tests/` verify both exact-name and embedding-based entity matching modes.

---

## 4. Key Target Files
- [`packages/episteme-pipeline/evaluation/scorers/gm_gbs.py`](packages/episteme-pipeline/evaluation/scorers/gm_gbs.py)
- [`packages/episteme-pipeline/tests/test_evaluation_scorers.py`](packages/episteme-pipeline/tests/)
