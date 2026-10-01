# [ISSUE-042] Episodic Working Memory: Jev Semantic Boundary Eviction & Reference Resolution

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-042` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/phases/phase2_entity_discovery/working_memory.py`, `pipeline/protocols/memory.py`, `pipeline/phases/phase2_entity_discovery/ner_extractor.py`) |
| **Roadmap Horizon** | **Horizon 2** (Dual-Memory Architecture & Scalable Ingestion) |
| **Priority** | High |
| **Status** | Open |
| **Source Ref** | `docs/concepts/episodic_working_memory.md`, ADR 0009 (`0009-sota-dual-memory-episodic-working-memory.md`) |

---

## 1. Problem Statement & Motivation
Episteme implements a **SOTA Dual-Memory Architecture** (Short-Term Memory / RAM vs. Long-Term Memory / Disk in Neo4j). In Phase 2 Entity Discovery, STM maintains a rolling structured state machine (`active_entities`, `unresolved_references`, `current_argument_branch`) across sequential chunks ($C_i$) within a global structural coordinate system ($A_{\text{anchor}}$).

Currently, two key operations in Episodic Working Memory suffer from generative LLM liabilities:
1. **Semantic Boundary Eviction ($B_i \in \{0, 1\}$)**:
   - The formal model defines $(S_i, \Delta G_i, B_i) = \text{Extract}(C_i, A_{\text{anchor}}, S_{i-1})$. When $B_i = 1$, STM short-lived variables are purged from RAM.
   - Currently, `boundary_detected` is coupled into the heavy generative `NERExtractionOutput` prompt. Asking an LLM to simultaneously extract entities and perform metacognitive boundary classification degrades both tasks and causes missed semantic episode transitions.
2. **Local Anaphora & Demonstrative Reference Resolution**:
   - Scientific texts frequently employ implicit demonstratives (*"this assumption"*, *"the second premise"*, *"his critique"*).
   - Resolving `unresolved_references` against candidate `active_entities` in STM currently either requires an additional LLM roundtrip or is left unresolved until graph fusion.
3. **Naive FIFO Memory Pruning**:
   - `JsonPatchWorkingMemoryState` caps `active_entities` to the last 15 items using a naive insertion-order FIFO queue, frequently evicting central foundational concepts when intermediate auxiliary terms are discussed.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Jev Semantic Eviction Evaluator (`pipeline/phases/phase2_entity_discovery/working_memory.py`)**:
   - Extend `EpisodicEvictionHandler` to accept an optional injected `DecisionEngine`.
   - Method `async def evaluate_semantic_boundary(chunk: L1Chunk, current_state: WorkingMemoryState, anchor: GlobalStructuralAnchor | None, prompt_bundle: StructuredPromptBundle | None = None) -> tuple[bool, float]`:
     - Formulates state from the current chunk, section path, and active argument branch (budgeted $\le 800$ tokens).
     - Asks Jev `Noul` using question template sourced from `prompt_bundle.decision_template` (managed in Langfuse) or default: `"Does this text chunk conclude the current semantic argument episode or mark a thematic transition to a new section/claim?"`
     - If $P(\text{semantic\_boundary}) \ge \tau_{\text{eviction}}$, emits `EvictionSignal(boundary_detected=True, boundary_type="semantic")`, returning `(True, result.empirical_accuracy)`.
   - **Scope Clarification**: STM eviction is explicitly designed for short-term RAM state during sequential chunk reading; long-term cross-document entity and theory consolidation is managed by downstream Phase 3b and Phase 5.
2. **Jev Local Reference Resolver (`pipeline/phases/phase2_entity_discovery/working_memory.py`)**:
   - Add `async def resolve_reference(reference_phrase: str, chunk_sentence: str, active_entities: list[str], prompt_bundle: StructuredPromptBundle | None = None) -> tuple[str | None, float]`:
     - If `active_entities` is non-empty, calls Jev `Choice`:
       - `state`: Local sentence containing the demonstrative/pronoun + definitions of active entities.
       - `options`: `active_entities + ["UNRESOLVED"]`.
     - Returns `(matched_entity, result.empirical_accuracy)` if $\text{empirical\_accuracy} \ge \tau_{\text{resolution}}$, or `None` if unresolved.
3. **Salience-Driven Working Memory Retention**:
   - Replace naive FIFO list slicing (`[-15:]`) with an optional Jev `Score` or relevance ranking, retaining foundational concepts in STM across the episode.

### What to Change
1. **`LLMNERExtractor` (`pipeline/phases/phase2_entity_discovery/ner_extractor.py`)**:
   - When `decision_engine` is provided, decouple `boundary_detected` from the generative NER prompt schema to save tokens and avoid LLM bias.
   - When `decision_engine is None`, preserve the existing fallback behavior where the LLM emits `boundary_detected` directly within `NERExtractionOutput`.
2. **`EpisodicWorkingMemoryManager`**:
   - Accept optional `decision_engine: DecisionEngine | None = None` and optional prompt bundles from `PromptProvider`.

### What to Remove
- Remove hardcoded string questions inside working memory methods; route all prompts through `PromptProvider`.

---

## 3. Acceptance Criteria
- [ ] `EpisodicEvictionHandler` uses Jev `Noul` to detect semantic episode boundaries with calibrated probability in $<150\text{ms}$.
- [ ] STM automatically purges short-lived RAM variables upon structural or semantic boundary detection.
- [ ] `unresolved_references` (e.g. "this assumption") resolve to correct `active_entities` via Jev `Choice` without generative LLM calls.
- [ ] Generative NER prompt tokens are reduced by offloading boundary detection from the output schema.
- [ ] Deterministic unit tests with `MockJevDecisionEngine` verify boundary eviction signals and reference resolution.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/protocols/memory.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/working_memory.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/ner_extractor.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/models.py`
- `packages/episteme-pipeline/tests/test_episodic_working_memory_jev.py`

---

## 5. Documentation Updates Required
- Update the Episodic Working Memory conceptual documentation (`docs/concepts/episodic_working_memory.md`) to detail the Jev boundary eviction model and local reference resolution.
- Update ADR 0009 (`0009-sota-dual-memory-episodic-working-memory.md`) to record the separation of extraction from boundary evaluation.
- Update the Phase 2 workflow documentation (`docs/workflow/2_entity_discovery/pipeline_explanation.md`).
