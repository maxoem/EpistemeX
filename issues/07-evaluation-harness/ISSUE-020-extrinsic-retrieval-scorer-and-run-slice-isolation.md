# [ISSUE-020] Extrinsic Retrieval Scorer Fix & Per-Run Graph Slice Isolation

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-020` |
| **Component(s)** | `packages/episteme-pipeline` (`evaluation/scorers/retrieval_scorer.py`, `evaluation/eval_pipelines.py`) |
| **Roadmap Horizon** | **Horizon 1** (Evaluation Integrity & Benchmark Harness) |
| **Priority** | Critical / Blocker |
| **Status** | `Superseded` (by [ISSUE-028](../09-stnb-evaluation-capabilities/ISSUE-028-evaluation-orchestrator-theorynet-execution.md) and [ISSUE-032](../09-stnb-evaluation-capabilities/ISSUE-032-extrinsic-retrieval-attribute-fix-and-competency-testbed.md)) |
| **Source Ref** | [`review/26/09/evaluation_credibility_review.md §2.3, §3`](review/26/09/evaluation_credibility_review.md#L121-L170) |

> [!NOTE]
> **SUPERSEDED**: This issue has been superseded by [`ISSUE-028`](../09-stnb-evaluation-capabilities/ISSUE-028-evaluation-orchestrator-theorynet-execution.md) (In-Memory Evaluation & Packaging Consolidation) and [`ISSUE-032`](../09-stnb-evaluation-capabilities/ISSUE-032-extrinsic-retrieval-attribute-fix-and-competency-testbed.md) (Extrinsic Retrieval Attribute Fix & Competency Testbed).


---

## 1. Problem Statement & Motivation
In [`evaluation/scorers/retrieval_scorer.py`](packages/episteme-pipeline/evaluation/scorers/retrieval_scorer.py#L52-L56), the extrinsic retrieval evaluation loop is broken on the critical path:
```python
results = await self.graph_reader.vector_search(
    embedding=query_embedding, top_k=top_k
)
retrieved_ids = [res.id for res in results]
```
The contract defined in [`pipeline/contracts/domain.py`](packages/episteme-pipeline/episteme_pipeline/contracts/domain.py#L94) models search results as:
```python
class SearchResult(BaseModel):
    node_id: str
    score: float
    node_label: str
    node_name: str
```
Because `SearchResult` has no `.id` attribute, calling `retrieval_scorer.score()` raises an `AttributeError` on every execution. This indicates that the extrinsic evaluation pipeline has never been executed to completion.

Furthermore, when `graph_reader.vector_search` is called, it queries the **entire global Neo4j database** without filtering by `run_id`. This causes cross-run contamination: nodes from unrelated test runs or older pipeline executions bleed into the evaluation results.

---

## 2. Functional Requirements
1. **Fix `SearchResult` Attribute Access**:
   - Update line 56 of `retrieval_scorer.py` to use `res.node_id`:
     ```python
     retrieved_ids = [res.node_id for res in results]
     ```
2. **Per-Run Graph Slice Isolation**:
   - Ensure vector search and Cypher neighborhood lookups in `GraphReader` support scoping to a specific `run_id` or `subgraph_id`.
   - Update `eval_pipelines.py` to pass the active evaluation `run_id` to the scorer:
     ```python
     results = await self.graph_reader.vector_search(
         embedding=query_embedding, top_k=top_k, run_id=self.run_id
     )
     ```
3. **Automated CI Integration**:
   - Create deterministic integration tests that spin up an in-memory/mock graph reader, run retrieval scoring, and assert calculated values for MRR, Hits@k, nDCG, and MAP.

---

## 3. Acceptance Criteria
- [ ] `retrieval_scorer.py` accesses `res.node_id` without `AttributeError`.
- [ ] Retrieval scoring correctly isolates queries to the evaluated run slice or manifest artifact collection.
- [ ] Unit tests in `packages/episteme-pipeline/tests/` verify MRR, Hits@k, nDCG, and MAP calculation against mock ground-truth sets.
- [ ] `eval_pipelines.py` executes end-to-end cleanly when invoked via CLI.

---

## 4. Key Target Files
- [`packages/episteme-pipeline/evaluation/scorers/retrieval_scorer.py`](packages/episteme-pipeline/evaluation/scorers/retrieval_scorer.py)
- [`packages/episteme-pipeline/evaluation/eval_pipelines.py`](packages/episteme-pipeline/evaluation/eval_pipelines.py)
- [`packages/episteme-pipeline/episteme_pipeline/protocols/graph_store.py`](packages/episteme-pipeline/episteme_pipeline/protocols/graph_store.py)
