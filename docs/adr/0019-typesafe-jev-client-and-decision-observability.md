# [0019] TypeSafe Jev Client Implementation, System 1 Adapters, and Decision Observability

Status: Accepted (2026-10-01)

## Context

Following [ADR 0018](0018-decision-engine-architecture-and-contracts.md), Episteme is transitioning to a **Dual-Process Neuro-Symbolic Pipeline** (Kahneman System 1 + System 2). In Stage 1, we established the core abstractions: the abstract `DecisionEngine` protocol, Pydantic contracts (`DecisionScore`, `DecisionNoulResult`) supporting dual confidence metrics, centralized prompt management schemas, and composition root wiring.

To operationalize System 1 inference and satisfy Episteme's core directives, we require:

1. **Production-Grade Engine Clients:**
   - **Local Apple Silicon Execution:** Native MLX inference ($7–15\text{ms}$) via `laya_mlx` on macOS arm64 without PyTorch or external API overhead.
   - **Cross-Platform Fallback:** PyTorch/Transformers fallback (`TransformersDecisionEngine`) for Linux/CUDA CI/CD environments where MLX is unavailable, loading equivalent ModernBERT / mmBERT checkpoints.
   - **Deterministic Testing Harness:** An in-memory mock (`MockJevDecisionEngine`) allowing pattern-based fixture registration, simulated latencies, and offline unit testing without GPU requirements or remote weight downloads.
2. **Mandatory Telemetry & Observability:**
   Per system directives, all pipeline operations must integrate logging, domain event publishing, and distributed tracing. Decision evaluations replacing generative LLM calls must report:
   - Inference latency measured with sub-millisecond precision.
   - Dual confidence metrics: categorical softmax peak $P(Y = c \mid X)$ and calibrated empirical accuracy frequency $P(\text{correct} \mid \text{temperature bucket})$.
   - Conformal prediction sets $C(X) \subseteq \mathcal{Y}$ guaranteeing $1 - \alpha$ coverage.
   - Estimated generative LLM token savings.
   - Stochastic false-negative audit routing ($2\%$) to detect calibration drift.
   - An **Active Learning Queue Hook** capturing high-entropy or multi-class decisions for domain expert review in Langfuse Datasets.

## Decision

We implement the complete provider suite and observability layer for Stage 2 of the Decision Engine initiative:

### 1. Concrete Provider Suite (`episteme_pipeline/decision/`)

- **`LayaDecisionEngine` (`pipeline/decision/jev_client.py`):**
  - Interfaces natively with `laya_mlx.load()`.
  - Runs synchronous MLX forward passes in thread pools via `asyncio.to_thread` guarded by configurable timeouts (`timeout_seconds`).
  - Maps Laya's dual outputs: `answers[key]` categorical distribution $\rightarrow$ `class_probability` / `selected_option`, and `action.act_probability` $\rightarrow$ `empirical_accuracy`.
  - Integrates candidate shortlisting (`predict_shortlist`) when option sets exceed budget thresholds.
  - Constructs distribution-free conformal prediction sets $C(X)$ guaranteeing $1 - \alpha$ coverage.
  - Standardizes runtime failures (timeouts, memory exhaustion, token budget overflows) into `DecisionEngineError`.
- **`TransformersDecisionEngine` (`pipeline/decision/jev_client.py`):**
  - Provides a PyTorch / Hugging Face `transformers` execution path for Linux/CUDA systems.
- **`MockJevDecisionEngine` (`pipeline/decision/mock.py`):**
  - Pure in-memory engine supporting rule-based fixture matching on question substrings and state patterns (`register_noul_response`, `register_choice_response`, `register_score_response`).
  - Simulates configurable execution latency and records call audits for test assertions.

### 2. Decision Domain Events (`episteme_pipeline/events/models.py`)

We introduce three new Pydantic domain events:
- `DecisionEvaluationStarted`: Emitted prior to engine execution, capturing `engine_name`, `primitive`, `question`, SHA-256 `state_hash`, and character count.
- `DecisionEvaluationCompleted`: Emitted upon execution completion, capturing selected output, dual confidence scores, conformal prediction set, duration, token savings heuristic, stochastic audit flag, and prompt management coordinates.
- `DecisionGatingTriggered`: Emitted by downstream gating adapters, capturing gate name (`acc_triage`, `gleaning_check`, `cartesian_pair_filter`), action taken (`fast_exit`, `escalated_to_llm`, `stochastic_audit`), empirical accuracy, and gating threshold.

### 3. Observable Decorator (`episteme_pipeline/decision/observable.py`)

- `ObservableDecisionEngine`: Transparently decorates any `DecisionEngine` instance.
- Measures duration using `time.perf_counter()`, computes SHA-256 state hashes, computes token savings heuristics, rolls random samples against `stochastic_audit_rate`, and dispatches start/complete events to `get_event_emitter()`.
- Automatically wraps raw decision engines at the composition root in `ensure_decision_engine`.

### 4. Langfuse Observer & Active Learning Queue (`episteme_pipeline/events/langfuse_observer.py`)

- `LangfuseObserver` intercepts `DecisionEvaluationCompleted` and records a `decision.{primitive}` generation observation attached to the distributed trace.
- Binds directly to managed Langfuse prompts using `prompt_name`, `prompt_version`, and `prompt_label`.
- **Active Learning Queue Hook:** When an evaluation yields a multi-class prediction set ($|C(X)| > 1$) or high entropy ($0.40 \le P \le 0.60$), it tags the span with `active_learning_candidate: True` and enqueues the record into Langfuse Dataset `decision_engine_active_learning` for human review and downstream model fine-tuning.
- Records `decision.gate.{gate_name}` spans for dynamic routing visibility.

## Consequences

### Positive
- Sub-second decision inference ($7–15\text{ms}$) running on local Apple Silicon hardware with zero cloud API dependencies.
- Zero output token generation, slashing pipeline operational costs by up to $85\%$ for classification tasks.
- 100% deterministic test coverage via `MockJevDecisionEngine` without network downloads or API keys.
- Complete traceability of all discrete decisions in Langfuse with prompt linking and active learning candidate collection.

### Neutral / Trade-offs
- Apple Silicon MLX inference requires macOS arm64; Linux/CI environments utilize the Transformers fallback or in-memory mocks.
- Choice sets with high candidate cardinality require embedding-based shortlisting to remain within encoder context budgets (ModernBERT 512/1,024 tokens).

## References

- Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus and Giroux.
- Romano, Y., Patterson, E., & Candès, E. (2019). Conformalized Quantile Regression. *NeurIPS*.
- Convai Innovations / Laya Technical Specification (2025). *Typed Decisions with Bidirectional ModernBERT*.
- Episteme Architecture Decision Record 0018: *Core Decision Engine Architecture, Contracts, and Composition Root*.
