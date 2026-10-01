# [ISSUE-036] Jev Client Implementation & System 1 Adapter

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-036` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/decision/jev_client.py`, `pipeline/decision/mock.py`) |
| **Roadmap Horizon** | **Horizon 2** (Scalability & Low Latency Inference) |
| **Priority** | High |
| **Status** | Open |
| **Source Ref** | `docs/roadmap.md` (§ JevClassifier), TypeSafe AI Jev Technical Spec |

---

## 1. Problem Statement & Motivation
TypeSafe AI's Jev model is a non-generative, typed System 1 model that evaluates state blocks (strings, JSON objects, or arrays) against typed questions in a single parallel pass ($70–500\text{ms}$). It guarantees zero hallucinations, zero type violations, and emits empirically calibrated probability distributions.

To integrate Jev into Episteme, we need a robust, production-grade client adapter that implements the `DecisionEngine` protocol (`ISSUE-035`), handles supports asynchronous execution, manages timeouts, and provides a deterministic in-memory mock for local unit tests.

Our implementation will use the open source alternative LAYA (see JEV-LAYA-MODEL.md for implementation and usage details). The `LayaDecisionEngine` should support/implement:

- Integrate with our observability principles (events/langfuse)
- 

---

## 2. Technical & Architectural Specification

### What to Add
1. **Concrete Jev Client (`pipeline/decision/jev_client.py`)**:
   - `class JevDecisionEngine`: Implements `DecisionEngine` protocol.
   - Support the three Jev primitives:
     - `evaluate_noul(state, question)`: Maps to Jev `Noul` primitive, returning calibrated probability float.
     - `evaluate_choice(state, question, options)`: Maps to Jev `Choice` primitive, returning structured `DecisionScore` with selected option and full per-option probability mapping.
     - `evaluate_score(state, question, levels)`: Maps to Jev `Score` primitive, returning ordinal score and level distributions.
   - Batch request capability: Support sending multiple questions against a single state block in one parallel HTTP roundtrip.
   - Error handling: Graceful handling of network timeouts, rate limits ($429$), and API errors, raising `DecisionEngineError` with contextual diagnostic data.
2. **Deterministic Mock Engine (`pipeline/decision/mock.py`)**:
   - `class MockJevDecisionEngine`: In-memory implementation for deterministic testing.
   - Allows registering rule-based or fixture-based responses for specific question patterns and state substrings.
   - Simulates realistic calibrated probability distributions and latencies ($5–15\text{ms}$).

### What to Change
- Register `LayaDecisionEngine` and `MockJevDecisionEngine` in `ensure_decision_engine` (`pipeline/protocols/decision.py`) so strings like `"jev"` or `"mock"` instantiate the corresponding class automatically.

### What to Remove
- No removals; purely additive provider module.

---

## 3. Acceptance Criteria
- [ ] `LayaDecisionEngine` implements all methods of `DecisionEngine` (`evaluate_noul`, `evaluate_choice`, `evaluate_score`).
- [ ] Parallel multi-question batching against a single state object is supported.
- [ ] Network failures, rate limits, token limits and timeouts are caught and converted to standardized exceptions without crashing the pipeline.
- [ ] `MockJevDecisionEngine` allows full deterministic testing of pipeline phases without network calls, loading the hf model or API keys.
- [ ] Unit test suite covering authentication, payload serialization, response parsing, and error conditions.

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
