# [ISSUE-038] Phase 3 Candidate Pair Gating & Jev Relation Reranker

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-038` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/phases/phase3_global_relations/rerankers.py`, `pipeline/phases/phase3_global_relations/extractor.py`, `pipeline/config.py`) |
| **Roadmap Horizon** | **Horizon 2** (Scalability & Low Latency Inference) |
| **Priority** | High |
| **Status** | Open |
| **Source Ref** | `docs/roadmap.md` (§ JevRelationReranker), `docs/workflow/3_relation_extraction/index.md` |

---

## 1. Problem Statement & Motivation
Phase 3 (Global Relation Extraction) faces an $O(N^2)$ combinatorial bottleneck: pairing all discovered entities across distant text chunks creates thousands of candidate pairs. Currently, Episteme uses dense MIPS retrieval followed by a local PyTorch `CrossEncoder` or direct LLM decoding to score and extract triples. 

The local `CrossEncoder` requires substantial GPU/CPU resources and produces scores that often require heuristic sigmoid normalization. Integrating Jev into Phase 3 enables:
1. **Drop-in Relation Reranking (`JevRelationReranker`)**: Rapidly scoring entity candidate pairs ($70–150\text{ms}$) with calibrated confidence scores.
2. **Cartesian Pair Pre-Gating (`JevPairFilter`)**: Filtering out 90%+ irrelevant candidate pairs via a fast `Noul` check before expensive LLM triple extraction prompts are constructed.

---

## 2. Technical & Architectural Specification

### What to Add
1. **`JevRelationReranker` (`pipeline/phases/phase3_global_relations/rerankers.py`)**:
   - Subclass `RelationReranker` ABC.
   - Accepts an injected `DecisionEngine`.
   - Formulates state from contextual subgraph envelopes of `entity_a` and `entity_b`.
   - Evaluates a typed question (e.g. via `evaluate_score` or `evaluate_choice` over relation plausibility levels).
   - Returns calibrated float probability in $[0, 1]$.
2. **Fast Cartesian Pair Pre-Gating (`pipeline/phases/phase3_global_relations/extractor.py`)**:
   - Add `async def filter_candidate_pairs(pairs: list[CandidatePair]) -> list[CandidatePair]`.
   - Uses Jev `Noul` (`"Is there a direct theoretical or semantic relationship between {entity_a} and {entity_b}?"`).
   - Prunes candidate pairs where $P(\text{has\_relation}) < \tau_{\text{rel\_gate}}$ prior to building dense LLM prompt contexts.
3. **Phase Configuration Flags (`pipeline/config.py`)**:
   - Extend `Phase3Config` with `use_jev_reranker: bool = False`, `use_jev_pair_gating: bool = False`, and `pair_gating_threshold: float = 0.60`.

### What to Change
1. **`DenseRetrievalGlobalRelationExtractor`**:
   - Integrate the optional pair pre-gating step between candidate pair retrieval and LLM triple decoding.
2. **`Pipeline.for_task` Wiring**:
   - Automatically instantiate `JevRelationReranker` when `decision_engine` is provided and `config.phase3.use_jev_reranker` is enabled.

### What to Remove
- Remove fallback heuristics that score un-evaluated candidate pairs with default $1.0$ weights.

---

## 3. Acceptance Criteria
- [ ] `JevRelationReranker` implements `RelationReranker` ABC and passes domain contract tests.
- [ ] Cartesian candidate pairs can be pre-filtered via Jev `Noul` checks, reducing candidate volume by $\ge 80\%$ on benchmark corpora.
- [ ] `Phase3Config` cleanly exposes reranker and gating toggles and thresholds.
- [ ] Phase 3 execution benchmarks demonstrate a minimum $3\times$ latency reduction during candidate evaluation.
- [ ] Deterministic unit tests with `MockJevDecisionEngine` verify candidate pruning and reranking logic.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/rerankers.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase3_global_relations/extractor.py`
- `packages/episteme-pipeline/episteme_pipeline/config.py`
- `packages/episteme-pipeline/tests/test_phase3_jev_reranker.py`

---

## 5. Documentation Updates Required
- Update the Phase 3 Global Relations workflow documentation (`docs/workflow/3_relation_extraction/`) to document the Jev reranker and pair gating stage.
- Update ADR 0002 (TAG Reranker Global Relation Extraction) to include the Jev alternative to cross-encoders.
- Update the runtime complexity analysis documentation to reflect the reduction in candidate pair evaluation latency.
