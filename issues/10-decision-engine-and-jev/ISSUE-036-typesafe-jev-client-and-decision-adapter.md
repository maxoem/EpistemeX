# [ISSUE-036] Jev Client Implementation & System 1 Adapter

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-036` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/decision/jev_client.py`, `pipeline/decision/mock.py`) |
| **Roadmap Horizon** | **Horizon 2** (Scalability & Low Latency Inference) |
| **Priority** | High |
| **Status** | Completed |
| **Source Ref** | `docs/roadmap.md` (§ JevClassifier), TypeSafe AI Jev Technical Spec |

---

## 1. Problem Statement & Motivation
TypeSafe AI's Jev model is a non-generative, typed System 1 model that evaluates state blocks (strings, JSON objects, or arrays) against typed questions in a single parallel pass ($70–500\text{ms}$). It guarantees zero hallucinations, zero type violations, and emits empirically calibrated probability distributions.

To integrate Jev into Episteme, we need a robust, production-grade client adapter that implements the `DecisionEngine` protocol (`ISSUE-035`), handles supports asynchronous execution, manages timeouts, and provides a deterministic in-memory mock for local unit tests.

Our primary local engine implementation will use the open source model LAYA (see [`JEV-LAYA-MODEL.md`](JEV-LAYA-MODEL.md) for architectural and runtime details). The `DecisionEngine` provider suite must implement:

1. **Dual-Confidence Output Mapping**:
   - Accurately map Laya's outputs: `result["answers"][key]` categorical softmax distribution $\rightarrow$ `class_probability` and `selected_option`; and `result["action"]["act_probability"]` calibrated empirical accuracy $\rightarrow$ `empirical_accuracy`.
2. **Cross-Platform Execution & Fallbacks**:
   - `LayaDecisionEngine`: High-performance Apple Silicon MLX inference ($7–15\text{ms}$) on macOS.
   - `TransformersDecisionEngine`: PyTorch/ONNX fallback for Linux/CUDA CI/CD environments where MLX is unavailable, loading the equivalent Hugging Face `ModernBERT` / `mmBERT` checkpoints.
   - `MockJevDecisionEngine`: In-memory deterministic mock for instant unit tests without downloading weights.
3. **Context Length Guards & Candidate Shortlisting**:
   - ModernBERT context window is 512 / 1,024 tokens. When candidate sets are large (e.g. in Phase 2 Entity Linking), automatically leverage `predict_shortlist` to prevent token truncation across option criteria.
4. **Observability Integration**:
   - Seamless integration with domain events and Langfuse spans via `ObservableDecisionEngine` (`ISSUE-037`).

---

## 2. Technical & Architectural Specification

### What to Add
1. **Concrete Local Client (`pipeline/decision/jev_client.py`)**:
   - `class LayaDecisionEngine`: Implements `DecisionEngine` protocol via `laya_mlx`.
   - `class TransformersDecisionEngine`: Fallback implementation using Hugging Face `transformers` / `optimum`.
   - Support the three core primitives:
     - `evaluate_noul(state, question)`: Maps to Jev `Noul`, returning `DecisionNoulResult(probability=p, empirical_accuracy=act_p, passed=...)`.
     - `evaluate_choice(state, question, options, alpha=None)`: Maps to Jev `Choice`. Populates `DecisionScore` with `class_probability`, `empirical_accuracy` (`action.act_probability`), full categorical distribution, and conformal prediction set $C(X)$ when `alpha` is specified.
     - `evaluate_score(state, question, levels)`: Maps to Jev `Score`, returning expected level and level probabilities.
   - Batch request capability: Support sending multiple questions against a single state block in one forward pass (`batch_size=16` default).
   - Dynamic shortlisting: Use `predict_shortlist` for choice sets with $>5$ options to prevent exceeding ModernBERT's 1,024 token budget.
   - Error handling: Graceful handling of token overflows, device memory exhaustion, and runtime timeouts, raising `DecisionEngineError`.
2. **Deterministic Mock Engine (`pipeline/decision/mock.py`)**:
   - `class MockJevDecisionEngine`: In-memory implementation for deterministic testing.
   - Allows registering rule-based or fixture-based responses for specific question patterns and state substrings.
   - Emits realistic `class_probability`, `empirical_accuracy`, and prediction sets with simulated latencies ($5–15\text{ms}$).

### What to Change
- Register `LayaDecisionEngine`, `TransformersDecisionEngine`, and `MockJevDecisionEngine` in `ensure_decision_engine` (`pipeline/protocols/decision.py`) with automatic platform detection (MLX on macOS arm64, Transformers on Linux).

### What to Remove
- No removals; purely additive provider module.

---

## 3. Acceptance Criteria
- [x] `LayaDecisionEngine` implements all methods of `DecisionEngine` (`evaluate_noul`, `evaluate_choice`, `evaluate_score`).
- [x] Parallel multi-question batching against a single state object is supported.
- [x] Network failures, rate limits, token limits and timeouts are caught and converted to standardized exceptions without crashing the pipeline.
- [x] `MockJevDecisionEngine` allows full deterministic testing of pipeline phases without network calls, loading the hf model or API keys.
- [x] Unit test suite covering authentication, payload serialization, response parsing, and error conditions.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/decision/__init__.py`
- `packages/episteme-pipeline/episteme_pipeline/decision/jev_client.py`
- `packages/episteme-pipeline/episteme_pipeline/decision/mock.py`
- `packages/episteme-pipeline/tests/test_jev_client.py`

---

## 5. Documentation Updates Required
- Update the developer documentation and environment configuration guide.
- Document the Jev client capabilities, primitives, and batching mechanisms in the system reference documentation.
- Add an example walkthrough showing how to use `MockJevDecisionEngine` in test suites.
