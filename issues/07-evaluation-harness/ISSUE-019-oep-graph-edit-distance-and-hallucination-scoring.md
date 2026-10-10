# [ISSUE-019] Graph Edit Distance (OEP) & Hallucination/Omission Scoring Fidelity

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-019` |
| **Component(s)** | `packages/episteme-pipeline` (`evaluation/scorers/oep.py`) |
| **Roadmap Horizon** | **Horizon 1** (Evaluation Integrity & Benchmark Harness) |
| **Priority** | High |
| **Status** | `Superseded` (by [ISSUE-030](../09-stnb-evaluation-capabilities/ISSUE-030-intrinsic-model-component-and-property-evaluation.md)) |
| **Source Ref** | [`review/26/09/evaluation_credibility_review.md §2.2`](review/26/09/evaluation_credibility_review.md#L76-L120) |

> [!NOTE]
> **SUPERSEDED**: This issue has been superseded by [`ISSUE-030: Comprehensive Intrinsic Evaluation: Model Component Decomposition & Full Property Subsumption`](../09-stnb-evaluation-capabilities/ISSUE-030-intrinsic-model-component-and-property-evaluation.md).


---

## 1. Problem Statement & Motivation
In [`evaluation/scorers/oep.py`](packages/episteme-pipeline/evaluation/scorers/oep.py), the `OptimalEditPathEvaluator` claims to compute "Optimal Edit Paths (OEP) to calculate hallucination and omission rates."

However, the implementation contains fundamental conceptual and algebraic flaws:
1. **OEP is not an edit path:** No node insertions, node deletions, edge substitutions, or sequence of edit operations are computed. Instead, the implementation computes:
   $$\text{hallucination\_rate} = \frac{|E_{\text{pred}}| - |E_{\text{matched\_pred}}|}{|E_{\text{pred}}|} = 1 - \text{precision}$$
   $$\text{omission\_rate} = \frac{|E_{\text{gold}}| - |\text{unique\_matched\_gold}|}{|E_{\text{gold}}|}$$
   Because $\text{precision}$ is already computed as GM-GBS in `gm_gbs.py`, `hallucination_rate` is literally $1 - \text{gm\_gbs}$. Reporting both presents the same single scalar under two different names.
2. **Duplicate Edge Counting Skew:** `oep.py` uses `len(set(matched_gold_edges))` for omissions, but raw list length for hallucinations, leading to skewed calculations when multiple predicted edges match the same gold edge.
3. **Empty Graph Artifact:** When an empty prediction graph is evaluated ($|E_{\text{pred}}| = 0$), `hallucination_rate` returns `0.0`, rewarding degenerate empty pipeline runs as "zero hallucination".

---

## 2. Functional Requirements
1. **Transparent Metric Renaming & Schema Alignment**:
   - Refactor or re-label metrics to be mathematically transparent:
     - Clearly label edge-level set differences as **Edge Precision / Recall / F1** rather than invoking the theoretical machinery of "Optimal Edit Paths" unless a true graph edit distance algorithm is run.
     - Formulate **Hallucination Rate** as the ratio of unsupported predicted triples to total predicted triples: $\frac{|E_{\text{pred}} \setminus E_{\text{gold\_matched}}|}{|E_{\text{pred}}|}$ (with explicit empty-graph handling: return `NaN` or mark execution invalid, not `0.0`).
     - Formulate **Omission Rate** as $\frac{|E_{\text{gold}} \setminus E_{\text{pred\_matched}}|}{|E_{\text{gold}}|}$.
2. **True Bounded Graph Edit Distance (Optional Engine)**:
   - For subgraphs under $N \le 200$, offer an optional true Graph Edit Distance calculator (e.g., using `networkx.graph_edit_distance` with custom node/edge substitution cost functions) to compute actual edit operation counts (insertions, deletions, substitutions).
3. **Bijective Edge Matching**:
   - Enforce 1-to-1 (bijective) or maximum-weight bipartite matching between $E_{\text{pred}}$ and $E_{\text{gold}}$ so that a single gold edge cannot be credited multiple times by duplicate or redundant predictions.

---

## 3. Acceptance Criteria
- [ ] Hallucination and omission calculations use consistent, bijective matching without duplicate-count artifacts.
- [ ] Evaluating an empty prediction graph on non-empty gold data raises an explicit warning or returns `omission_rate = 1.0` and `hallucination_rate = NaN` (never reporting clean 0.0 hallucination for no output).
- [ ] Documentation and metric outputs remove false claims of computing edit path sequences unless the true GED engine is invoked.
- [ ] Unit tests in `packages/episteme-pipeline/tests/` verify known edge configurations (completely disjoint graphs, duplicate edges, subgraphs).

---

## 4. Key Target Files
- [`packages/episteme-pipeline/evaluation/scorers/oep.py`](packages/episteme-pipeline/evaluation/scorers/oep.py)
- [`packages/episteme-pipeline/episteme_pipeline/evaluation/intrinsic.py`](packages/episteme-pipeline/episteme_pipeline/evaluation/intrinsic.py)
