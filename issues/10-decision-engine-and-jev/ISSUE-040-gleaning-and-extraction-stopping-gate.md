# [ISSUE-040] Objective Gleaning Gating via Jev Actor-Critic Stopping Oracle

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-040` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/decision/gleaning.py`, `pipeline/phases/phase2_entity_discovery/`, `pipeline/phases/phase4_argument_mining/`, `pipeline/config.py`) |
| **Roadmap Horizon** | **Horizon 2** (Scalability & Dynamic Gating) |
| **Priority** | Medium |
| **Status** | Completed |
| **Source Ref** | `docs/roadmap.md` (§ AOP Decision Points & Dynamic Gating) |

---

## 1. Problem Statement & Motivation
Iterative extraction passes ("gleaning") are used to ensure comprehensive entity and argument extraction across dense scientific texts. Currently, stopping criteria for gleaning passes either rely on fixed loop bounds or generative LLM metacognition (e.g. asking the LLM to output `has_more: bool` or an integer estimate of remaining items).

Asking an autoregressive LLM to self-evaluate its extraction completeness suffers from fundamental flaws:
1. **Confirmation Bias / Premature Stopping**: An LLM conditioned on its own prior output exhibits high false-negative stopping rates, claiming the text is fully extracted even when subtle propositions remain.
2. **Hallucinatory Over-Extraction**: Conversely, if forced to glean repeatedly, an LLM often hallucinates spurious entities to satisfy the perceived instruction demand.
3. **High Token Overhead**: Generating metacognitive introspective tokens costs hundreds of tokens and seconds per chunk.

By decoupling the *Actor* (generative LLM extractor) from the *Critic* (external Jev `Noul` evaluator), we establish an objective, calibrated stopping oracle.

---

## 2. Technical & Architectural Specification

### What to Add
1. **`JevGleaningGate` (`pipeline/decision/gleaning.py`)**:
   - `class JevGleaningGate`:
     - Accepts injected `DecisionEngine` and optional `StructuredPromptBundle` from `PromptProvider`.
     - Method `async def should_glean(chunk_text: str, current_extractions: list[Any], pass_count: int, max_passes: int, threshold: float = 0.65, audit_rate: float = 0.02) -> tuple[bool, float]`:
       - **Context Length Budgeting**: Compresses `chunk_text` and current extracted entity/claim names to fit within ModernBERT's 1,024 token limit.
       - Asks Jev `Noul` using question template from `bundle.decision_template` (managed in Langfuse) or default: `"Does the source text contain salient theoretical assertions, definitions, or argument components that are missing from the current extraction list?"`
       - Returns `(True, result.empirical_accuracy)` if $P(\text{unextracted}) \ge \text{threshold}$ and $\text{pass\_count} < \text{max\_passes}$.
       - **Stochastic Gleaning Audit**: With probability `audit_rate` ($2\%$), forces an extra gleaning pass even when the critic predicts no unextracted items, tracking false-negative critic errors in Langfuse.
       - Emits a `DecisionGatingTriggered` domain event with gating statistics and Langfuse prompt tracking metadata.
2. **Gleaning Configuration (`pipeline/config.py`)**:
   - Extend `Phase2Config` and `Phase4Config` with:
     - `enable_jev_gleaning_gate: bool = False` (defaults to False for complete backward compatibility!)
     - `gleaning_confidence_threshold: float = 0.65`
     - `gleaning_audit_rate: float = 0.02`
     - `max_gleaning_passes: int = 3`

### What to Change
1. **`Phase2Runner` & `NERExtractor`**:
   - When `enable_jev_gleaning_gate` is True and `decision_engine` is provided, evaluate continuation through `JevGleaningGate.should_glean`.
   - When `enable_jev_gleaning_gate` is False or `decision_engine is None`, execute standard LLM gleaning loop unchanged (`self.max_gleanings` loop with `NER_GLEANING_PROMPT`).
2. **`Phase4Runner` (ADU & Argument Extraction)**:
   - In ADU segmentation and local extraction passes, gate multi-pass refinement through `JevGleaningGate` only when enabled.

### What to Remove
- Remove hardcoded prompt strings; bind gleaning evaluation questions to `PromptProvider`.

---

## 3. Acceptance Criteria
- [x] `JevGleaningGate` objectively evaluates extraction completeness using Jev `Noul` in $<150\text{ms}$.
- [x] Gleaning stops immediately when $P(\text{unextracted}) < \text{threshold}$, eliminating redundant LLM passes.
- [x] Multi-pass extraction triggers reliably on dense text chunks containing overlooked propositions.
- [x] Gating events are recorded in Langfuse traces to monitor gleaning distribution across documents.
- [x] Unit tests verify stopping conditions across zero, single, and multi-pass scenarios.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/decision/gleaning.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase2_entity_discovery/runner.py`
- `packages/episteme-pipeline/episteme_pipeline/phases/phase4_argument_mining/runner.py`
- `packages/episteme-pipeline/episteme_pipeline/config.py`
- `packages/episteme-pipeline/tests/test_jev_gleaning_gate.py`

---

## 5. Documentation Updates Required
- Update the Entity Discovery (`docs/workflow/2_entity_discovery/`) and Argument Mining (`docs/workflow/4_argument_mining/`) workflow documentation to explain the Actor-Critic gleaning architecture.
- Document tuning guidelines for `gleaning_confidence_threshold` based on desired precision vs. recall.
- Update ADR records regarding iterative extraction passes and dynamic stopping rules.
