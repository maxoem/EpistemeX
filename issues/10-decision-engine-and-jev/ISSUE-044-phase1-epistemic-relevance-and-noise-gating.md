# [ISSUE-044] Phase 1 Data Foundation: Epistemic Ingestion Relevance & Noise Gating

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-044` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/phases/phase1_foundation/chunker.py`, `pipeline/phases/phase1_foundation/runner.py`, `pipeline/config.py`) |
| **Roadmap Horizon** | **Horizon 2** (Large Corpus Ingestion & Scalability) |
| **Priority** | Medium |
| **Status** | Open |
| **Source Ref** | `docs/workflow/1_data_foundation/index.md`, `docs/roadmap.md` (§ Streaming Large Corpus Ingestion) |

---

## 1. Problem Statement & Motivation
During Phase 1 document ingestion and chunking, treatises and academic monographs contain extensive non-epistemic passages: title pages, tables of contents, publisher boilerplate, copyright declarations, dedications, index pages, and citation/bibliography lists.

Currently, Episteme chunks the entire source document indiscriminately. Passing these non-epistemic chunks into downstream extraction phases (Phase 2 Entities, Phase 3 Relations, Phase 4b Arguments) causes two major issues:
1. **Severe Token Waste**: Generative LLMs process thousands of tokens of bibliographic references and boilerplate, consuming budget and slowing processing.
2. **Spurious Graph Entities**: Generative extractors mistakenly extract publishers, publication cities, and bibliography author strings as ontological concepts or argumentative claims.

Using Jev's sub-second `Noul` evaluator at the conclusion of Phase 1 chunking allows Episteme to perform **Epistemic Ingestion Gating**, flagging and bypassing non-theoretical chunks before downstream extraction begins.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Epistemic Chunk Filter (`pipeline/phases/phase1_foundation/chunker.py`)**:
   - Add `async def evaluate_chunk_epistemic_relevance(chunk: L1Chunk, decision_engine: DecisionEngine, prompt_bundle: StructuredPromptBundle | None = None) -> tuple[bool, float]`:
     - Evaluates Jev `Noul` using question template from `prompt_bundle.decision_template` (managed in Langfuse) or default: `"Does this text passage contain substantive scientific, theoretical, or philosophical discourse, rather than administrative boilerplate, bibliographic citations, index entries, or publication metadata?"`
     - Returns `(is_epistemic, confidence)`.
2. **Chunk Metadata Attributes (`pipeline/contracts/domain.py`)**:
   - Add `is_epistemic: bool = True` and `epistemic_relevance_score: float | None = None` to `L1Chunk` metadata.
3. **Configuration Options (`pipeline/config.py`)**:
   - Extend `Phase1Config` with:
     - `enable_epistemic_gating: bool = False` (defaults to False for zero regression)
     - `epistemic_relevance_threshold: float = 0.50`
     - `drop_non_epistemic_chunks: bool = False` (if False, tags chunk with `is_epistemic=False` so downstream runners can skip without losing provenance).

### What to Change
1. **`Phase1Runner`**:
   - When `enable_epistemic_gating` is True and `decision_engine` is provided, execute relevance gating over extracted chunks using prompt bundles from `PromptProvider`.
   - When disabled or `decision_engine is None`, all chunks retain default `is_epistemic=True` (exact current behavior).
2. **Downstream Phase Runners (Phase 2, Phase 3, Phase 4b)**:
   - When iterating over chunks, check `chunk.metadata.get("is_epistemic", True)` and bypass non-epistemic chunks immediately.

### What to Remove
- Remove ad-hoc regex heuristics previously used to detect bibliography headers; route through `PromptProvider`.

---

## 3. Acceptance Criteria
- [ ] Non-epistemic chunks (bibliographies, indices, publisher front-matter) are classified with $P(\text{epistemic}) < 0.20$ in $<100\text{ms}$.
- [ ] Downstream phases cleanly bypass chunks marked non-epistemic, saving $100\%$ of extraction tokens on those chunks.
- [ ] Full provenance is preserved in Neo4j (L1 document hierarchy remains intact).
- [ ] Deterministic unit tests verify gating across authentic scholarly text samples.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/phases/phase1_foundation/chunker.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase1_foundation/runner.py`
- `packages/episteme-pipeline/episteme_pipeline/config.py`
- `packages/episteme-pipeline/tests/test_phase1_epistemic_gating.py`

---

## 5. Documentation Updates Required
- Update the Phase 1 Data Foundation workflow documentation (`docs/workflow/1_data_foundation/`) to document epistemic relevance gating.
- Update the runtime complexity analysis documentation to reflect token savings from early ingestion filtering.
