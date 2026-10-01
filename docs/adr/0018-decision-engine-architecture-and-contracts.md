# [0018] Core Decision Engine Architecture, Contracts, and Composition Root

Status: Accepted (2026-10-01)

## Context

Episteme constructs formal theory graphs (TheoryNet) and argument structures (QBAF) from scientific and philosophical literature. Historically, the pipeline relied exclusively on generative Large Language Models (LLMs) and cross-encoders for all extraction, classification, reference resolution, and dialectical validation tasks.

While generative LLMs excel at open-ended contextual synthesis, deploying them for discrete routing, binary gating, and categorical classification incurs significant drawbacks:

1. **Latency Overhead:** Generative roundtrips take between $1.5\text{s}$ and $6.0\text{s}$ per query. Scientific texts with hundreds of Argumentative Discourse Units (ADUs) and $O(N^2)$ candidate relation pairs result in prolonged execution times.
2. **Token Burn:** Repetitive categorical classifications generate excessive token overhead when small, specialized classifiers could resolve decisions in a single sub-second forward pass ($70–500\text{ms}$).
3. **Uncalibrated Confidence:** Generative LLMs emit uncalibrated verbalized confidence scores or raw token log-probabilities that do not correspond to empirical accuracy frequencies. In contrast, gradual argumentation semantics (such as QBAF and Quaternary frameworks) and TheoryNet edge weights strictly require mathematically grounded probabilities.

To address this, Episteme is adopting a **Dual-Process Neuro-Symbolic Architecture** (Kahneman System 1 + System 2):
- **System 1 (TypeSafe Jev / Laya):** Fast, non-generative, typed classification, and calibrated decision gating over structured state blocks (`Choice`, `Score`, `Noul`).
- **System 2 (Generative LLMs):** Deep conceptual synthesis, open-ended hypothesis formulation, and multi-hop philosophical reasoning.

Introducing this subsystem requires strict architectural guarantees:
- **Strictly Optional Dependency:** Existing pipeline runners must execute with zero regressions when a decision engine is not configured (`decision_engine=None`).
- **Prompt Management Governance:** Decision questions and rubric criteria must not be hardcoded string literals; they must integrate into Episteme's centralized prompt store (`StructuredPromptBundle`, `PromptProvider`, and `LangfusePromptProvider`).
- **Composition Root Dependency Injection:** All wiring must occur at the composition root (`Pipeline.for_task`) using runtime-checkable protocols.

## Decision

We introduce an abstract, contract-driven **Decision Engine protocol**, Pydantic return models supporting dual confidence metrics, configuration schemas, prompt bundle extensions, and composition root dependency injection.

### 1. Structural Protocol and Pydantic Contracts (`pipeline/protocols/decision.py`)

We define the `@runtime_checkable` protocol `DecisionEngine` specifying three core primitives:

```python
@runtime_checkable
class DecisionEngine(Protocol):
    async def evaluate_noul(
        self, state: str | dict[str, Any] | list[Any], question: str
    ) -> DecisionNoulResult: ...

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore: ...

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[int | str],
    ) -> DecisionScore: ...
```

#### Dual Confidence Metrics
The return models decouple the categorical softmax distribution from calibrated empirical accuracy:
- `class_probability`: Softmax probability $P(Y = c \mid X)$ of the selected option.
- `empirical_accuracy`: Calibrated empirical frequency of correctness (Laya `action.act_probability`).
- `prediction_set`: Optional conformal prediction set $C(X) \subseteq \mathcal{Y}$ guaranteeing $1 - \alpha$ coverage.
- `tokens_saved_estimate`: Estimated token savings achieved by avoiding generative inference.

### 2. Composition Root Normalization (`ensure_decision_engine`)

Following the pattern established by `ensure_embedding_model` and `ensure_structured_llm`, we provide `ensure_decision_engine(engine: Any | None) -> DecisionEngine | None`.
- `None` passes through cleanly.
- Conforming instances (checked via protocol or method inspection) are returned directly.
- Incompatible objects raise `TypeError` at construction time.

### 3. Prompt Management Integration

We extend `StructuredPromptBundle` in `prompts/models.py` with:
- `decision_template: str | None = None`: The decision question or evaluation prompt.
- `decision_criteria: dict[str, str] | list[str] | None = None`: Option definitions and evaluation rubrics.

We register default decision questions and rubric criteria in `prompts/default_prompts.py` (`DECISION_EPISTEMIC_RELEVANCE_QUESTION`, `DECISION_ACC_QUESTION`, `DECISION_ARC_QUESTION`, `DECISION_BOUNDARY_QUESTION`). Both `DefaultPromptProvider` and `LangfusePromptProvider` support fetching, versioning, and synchronizing decision prompt bundles under `production` and `staging` labels.

### 4. Configuration Schema (`pipeline/config.py`)

We introduce `DecisionEngineConfig`:
- `provider`: `"none"`, `"laya"`, `"transformers"`, `"mock"`.
- `api_key`: Optional `SecretStr` for remote providers.
- `endpoint_url`: Optional HTTP/gRPC endpoint.
- `timeout_seconds`: Per-decision call timeout (default: 2.0s).
- `default_confidence_threshold`: Empirical accuracy threshold for fast-exit triage (default: 0.85).
- `conformal_alpha`: Significance level for conformal sets (default: 0.05 for 95% coverage).
- `stochastic_audit_rate`: Audit rate (default: 0.02) routing 2% of fast-exits to System 2 for calibration drift detection.
- `fallback_to_llm`: Boolean flag enabling graceful escalation to generative LLMs on timeout or error.

`PipelineConfig` embeds `decision_engine: DecisionEngineConfig | None = None`.

### 5. Pipeline Wiring (`Pipeline.for_task`)

`Pipeline.for_task` accepts `decision_engine: Any | None = None`. If omitted (or configured as `"none"`), the pipeline executes baseline generative LLM and CrossEncoder runners with zero regressions. When supplied, `Pipeline` normalizes and preserves the engine instance for injection into phase triage adapters.

## Alternatives Considered

1. **Direct Coupling to Laya / MLX SDK:**
   *Rejected.* Coupling core pipeline protocols to a concrete framework prevents running unit tests on non-macOS/CI environments and violates Episteme's contract-driven architecture.
2. **Scalar Cutoff Gating Without Conformal Sets:**
   *Rejected.* Fixed scalar thresholds without conformal prediction coverage guarantees can lead to catastrophic false negatives in unorthodox philosophical texts.
3. **Hardcoded In-Memory String Prompts:**
   *Rejected.* Hardcoding prompts directly in phase implementations breaks prompt observability, versioning, and Langfuse synchronization.

## Consequences

### Positive
- Establishes a clean, extensible contract for all System 1 integrations.
- Zero regressions or breaking changes for existing test suites and generative workflows.
- Centralized prompt management and Langfuse governance extended to all discrete decisions.
- Unblocks Stage 2 (concrete client implementation, mock engine, and Langfuse span tracing) and Stages 3–5 (phase triage adapters).

### Negative
- Adds an additional configuration block and protocol layer to maintain.
