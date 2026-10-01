# [ISSUE-037] Decision Engine Observability, Domain Events & Langfuse Tracing

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-037` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/events/models.py`, `pipeline/decision/observable.py`, `pipeline/events/langfuse_observer.py`) |
| **Roadmap Horizon** | **Horizon 2** (Scalability & Observability) |
| **Priority** | Critical |
| **Status** | Open |
| **Source Ref** | `docs/observability/events.md`, `pipeline/protocols/extractors.py` (`ObservableEmbeddingModel`) |

---

## 1. Problem Statement & Motivation
Episteme strictly enforces system hooks across all components: caching, logging, event publishing, and observability. When a decision engine like Jev executes a sub-second decision, replaces an LLM call, or gates pipeline execution, this operation must be fully observable. 

Currently, telemetry observers (such as `LangfuseObserver`) track embedding generations and generative LLM completions, but have no domain event representation for discrete, typed decision evaluations or dynamic flow gating. We must ensure that Jev model invocations emit domain events and push spans and metrics to Langfuse, including latency, calibrated confidence, chosen primitive, and estimated token savings.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Domain Event Models (`pipeline/events/models.py`)**:
   - `DecisionEvaluationStarted(DomainEvent)`:
     - `engine_name: str`
     - `primitive: str` (`"noul"` | `"choice"` | `"score"`)
     - `question: str`
     - `state_hash: str` (stable sha256 of input state)
     - `state_character_count: int`
   - `DecisionEvaluationCompleted(DomainEvent)`:
     - `engine_name: str`
     - `primitive: str`
     - `question: str`
     - `prompt_name: str | None` (from `StructuredPromptBundle.name`)
     - `prompt_version: int | str | None` (from `StructuredPromptBundle.version`)
     - `prompt_label: str | None` (e.g. `'production'`)
     - `selected_value: str | int | bool | float`
     - `confidence: float`
     - `probabilities: dict[str, float] | None`
     - `duration_seconds: float`
     - `tokens_saved_estimate: int` (heuristic based on bypassed LLM prompt + completion)
   - `DecisionGatingTriggered(DomainEvent)`:
     - `gate_name: str` (e.g. `"gleaning_check"`, `"acc_triage"`, `"cartesian_pair_filter"`)
     - `action_taken: str` (`"fast_exit"` | `"escalated_to_llm"` | `"loop_terminated"`)
     - `confidence: float`
     - `threshold: float`
2. **Observable Decorator (`pipeline/decision/observable.py`)**:
   - `class ObservableDecisionEngine`: Decorates any `DecisionEngine` instance.
   - Measures execution duration via `time.perf_counter()`.
   - Emits `DecisionEvaluationStarted` and `DecisionEvaluationCompleted` events to the active `EventEmitter`.
   - Passes all method calls through to the inner engine.
3. **Langfuse Telemetry Observer Hook (`pipeline/events/langfuse_observer.py`)**:
   - Register event handlers for `DecisionEvaluationCompleted` and `DecisionGatingTriggered`.
   - Record decision invocations as specialized spans/observations in the active Langfuse trace.
   - Bind the span directly to the managed Langfuse prompt (using `prompt_name` and `prompt_version`) to track prompt effectiveness and regression in Langfuse UI.
   - Attach metadata tags: `system_1: true`, `primitive`, `calibrated_confidence`, `tokens_saved`.
   - Track decision distribution across runs (measuring fast-exit ratio vs. LLM escalation ratio).

### What to Change
- In `ensure_decision_engine` (`pipeline/protocols/decision.py`), automatically wrap any raw decision engine with `ObservableDecisionEngine` unless it is already wrapped.

### What to Remove
- No removals; non-breaking extension of the event bus.

---

## 3. Acceptance Criteria
- [ ] `DecisionEvaluationStarted`, `DecisionEvaluationCompleted`, and `DecisionGatingTriggered` domain events defined and validated in `pipeline/events/models.py`.
- [ ] `ObservableDecisionEngine` transparently wraps `DecisionEngine` instances and emits events with precise duration and confidence scores.
- [ ] `LangfuseObserver` intercepts decision events and attaches structured spans and tags to distributed trace trees.
- [ ] Token savings metrics are computed and exported to telemetry.
- [ ] Deterministic unit tests verify event emission without requiring active Langfuse servers.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/events/models.py`
- `packages/episteme-pipeline/episteme_pipeline/decision/observable.py`
- `packages/episteme-pipeline/episteme_pipeline/events/langfuse_observer.py`
- `packages/episteme-pipeline/tests/test_observable_decision_engine.py`

---

## 5. Documentation Updates Required
- Update the telemetry and domain events documentation (`docs/observability/events.md`) with the new decision event schemas.
- Document Langfuse span hierarchy and dashboard visualization for System 1 fast exits vs. System 2 escalations.
- Update ADRs to reflect the standardized observability requirements for non-generative decision engines.
