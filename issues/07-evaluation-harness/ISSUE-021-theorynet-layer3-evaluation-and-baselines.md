# [ISSUE-021] TheoryNet (Layer 3) Benchmark Harness & Baseline Models

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-021` |
| **Component(s)** | `packages/episteme-pipeline/evaluation`, `packages/epistemetrics` |
| **Roadmap Horizon** | **Horizon 2** (Dialectical Modeling & Benchmarks) |
| **Priority** | High |
| **Status** | `Superseded` (by [ISSUE-028](../09-stnb-evaluation-capabilities/ISSUE-028-evaluation-orchestrator-theorynet-execution.md) and [ISSUE-033](../09-stnb-evaluation-capabilities/ISSUE-033-comparative-baselines-zero-shot-naive-rag.md)) |
| **Source Ref** | [`review/26/09/evaluation_credibility_review.md §4, §5`](review/26/09/evaluation_credibility_review.md#L171-L230), [`ADR 0007`](docs/adr/0007-tf-structural-correspondence.md) |

> [!NOTE]
> **SUPERSEDED**: This issue has been superseded by [`ISSUE-028`](../09-stnb-evaluation-capabilities/ISSUE-028-evaluation-orchestrator-theorynet-execution.md) (Level 4 Pipeline & Evaluation Execution) and [`ISSUE-033`](../09-stnb-evaluation-capabilities/ISSUE-033-comparative-baselines-zero-shot-naive-rag.md) (Comparative Baselines Harness).


---

## 1. Problem Statement & Motivation
The primary scientific contribution of Grund GLP is the automated construction of Layer 3 theory graphs (**Theoriennetze / TF**) from scientific and philosophical literature, transitioning from unstructured text to structured propositional atoms (`TheoryAtom`) and formal epistemological relations (`TheoryRelation`, e.g. `SPECIALIZES`, `CONSTRAINS`, `EXPLAINS`).

However, the existing evaluation harness (`evaluation/` and `pipeline/evaluation/`):
1. **Focuses solely on Layer 2:** Current benchmark tests run on SciERC (a computer science / NLP dataset with 7 relation types), testing standard entity/relation extraction rather than theory graph construction.
2. **Layer 3 evaluation is stubbed:** There is no gold standard dataset, rubric, or scoring path for Layer 3 TheoryNet structures.
3. **Absence of Comparative Baselines:** There are zero baseline models in the repository. A paper or report claiming SOTA theory graph construction must evaluate against recognized baselines (e.g., Direct LLM Zero-Shot extraction, Unconstrained OpenIE, Naive Vector RAG).

---

## 2. Functional Requirements
1. **Curate Gold Theory-Net Benchmarks**:
   - Create a curated gold-standard benchmark dataset for at least one target philosophical/scientific corpus (e.g. Stegmüller / Carnap / Kuhn case studies) containing verified:
     - Grounded `TheoryAtom` sets ($P$ theoretical premises, $B$ empirical observation sentences).
     - Ground-truth specialization hierarchies and theoretical relations.
2. **Implement Standard Baselines**:
   - Implement baseline runners in `packages/episteme-pipeline/evaluation/baselines/`:
     - `BaselineZeroShotLLM`: Single-prompt extraction of TheoryAtoms and relations without pipeline layering.
     - `BaselineNaiveKG`: Standard unipartite entity-relation extraction without Phase 4 maturation or Phase 6 TheoryNet projection.
     - `BaselineTextRAG`: Chunk-level dense retrieval without graph structuring.
3. **Integration with Epistemetrics**:
   - Connect the evaluation harness to `packages/epistemetrics` to evaluate structural and epistemic metrics (coherence, modesty, refutability, empirical power) across predictions vs gold standards vs baselines.
4. **Comparative Benchmark Reporting**:
   - Generate automated markdown/LaTeX tables in `evaluation/reports/` comparing pipeline performance against all baselines.

---

## 3. Acceptance Criteria
- [ ] `run_eval.py` supports running evaluation against TheoryNet gold standards.
- [ ] At least two baseline pipelines (Zero-Shot LLM, Naive KG) are implemented and executable via the evaluation harness.
- [ ] Output reports report epistemic metric differentials between Grund GLP and baselines.
- [ ] CI pipeline includes an evaluation dry-run verifying baseline and scoring execution.

---

## 4. Key Target Files
- [`packages/episteme-pipeline/evaluation/run_eval.py`](packages/episteme-pipeline/evaluation/run_eval.py)
- `packages/episteme-pipeline/evaluation/baselines/`
- [`packages/episteme-pipeline/episteme_pipeline/evaluation/`](packages/episteme-pipeline/episteme_pipeline/evaluation/)
- [`packages/epistemetrics/src/epistemetrics/`](packages/epistemetrics/src/epistemetrics/)
