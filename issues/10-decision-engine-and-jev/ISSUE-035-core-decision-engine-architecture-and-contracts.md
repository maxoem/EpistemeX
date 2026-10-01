# [ISSUE-035] Core Decision Engine Architecture, Contracts & Composition Root

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-035` |
| **Component(s)** | `packages/episteme-pipeline` (`pipeline/protocols/decision.py`, `pipeline/config.py`, `pipeline/pipeline.py`) |
| **Roadmap Horizon** | **Horizon 2** (Scalability & Low Latency Inference) |
| **Priority** | High |
| **Status** | Open |
| **Source Ref** | `docs/roadmap.md` (§ Horizon 2 JevClassifier), `docs/architecture/overview.md` |

---

## 1. Problem Statement & Motivation
Currently, Episteme relies on generative LLMs and cross-encoders for all extraction, classification, and validation tasks. Generative LLMs exhibit high latency ($1.5\text{s}–6.0\text{s}$), significant token burn, and uncalibrated confidence estimates for discrete decisions. 

To integrate TypeSafe's Jev (and similar non-generative, typed System 1 models) cleanly without tight-coupling or architectural degradation, the pipeline requires an abstract, contract-driven **Decision Engine protocol** integrated via constructor Dependency Injection (DI) at the composition root (`Pipeline.for_task`).

### Critical Architectural Guarantees:
1. **Strictly Optional Dependency**: `DecisionEngine` is 100% optional. When `decision_engine=None` (the default), every phase runner MUST continue to execute with full fidelity using the current generative LLM / CrossEncoder approach with zero regressions.
2. **Prompt Management Integration**: Decision questions, instructions, and criteria schemas must NOT be hardcoded string literals. They MUST integrate into Episteme's centralized prompt management architecture (`pipeline/prompts/models.py` and `pipeline/prompts/providers.py`), enabling versioning, label resolution (`production`, `staging`), and remote updates via `LangfusePromptProvider`.

---

## 2. Technical & Architectural Specification

### What to Add
1. **Core Structural Protocol (`pipeline/protocols/decision.py`)**:
   - Define `@runtime_checkable class DecisionEngine(Protocol)`.
   - Define contracts for the three core primitives:
     - `async def evaluate_noul(self, state: str | dict[str, Any] | list[Any], question: str) -> float`: Evaluates a yes/no statement, returning a calibrated probability in $[0, 1]$.
     - `async def evaluate_choice(self, state: str | dict[str, Any] | list[Any], question: str, options: list[str] | dict[str, str]) -> DecisionScore`: Evaluates categorical choices, returning the selected option, per-option probability distribution, and confidence score. Supports criteria definitions.
     - `async def evaluate_score(self, state: str | dict[str, Any] | list[Any], question: str, levels: list[int | str]) -> DecisionScore`: Evaluates ordered scales.
   - Define Pydantic models `DecisionScore`, `DecisionChoice`, and `DecisionNoulResult`.
2. **Prompt Management Integration (`pipeline/prompts/models.py` & `pipeline/prompts/providers.py`)**:
   - Extend `StructuredPromptBundle` in `prompts/models.py` to support `decision_template: str | None = None` and `decision_criteria: dict[str, str] | list[str] | None = None`.
   - Register default decision questions and rubric criteria in `prompts/default_prompts.py` (e.g. `DECISION_EPISTEMIC_RELEVANCE_QUESTION`, `DECISION_ACC_QUESTION`, `DECISION_ARC_QUESTION`, `DECISION_BOUNDARY_QUESTION`).
   - Update `DefaultPromptProvider` and `LangfusePromptProvider` in `prompts/providers.py` to fetch, version, and sync decision prompt bundles by name (e.g. `"decision_acc"`, `"decision_arc"`, `"decision_boundary"`) under `production` / `staging` labels.
3. **Configuration Support (`pipeline/config.py`)**:
   - Add `DecisionEngineConfig` covering `provider: str = "none"` (`"none"` | `"jev"` | `"laya"` | `"mock"`), `api_key: SecretStr | None`, `endpoint_url: str | None`, `timeout_seconds: float = 2.0`, `default_confidence_threshold: float = 0.85`, and `fallback_to_llm: bool = True`.
   - Embed `decision_engine: DecisionEngineConfig | None = None` into `PipelineConfig`.
4. **Engine Normalization Helper**:
   - Add `ensure_decision_engine(engine: Any | None) -> DecisionEngine | None` mirroring `ensure_embedding_model` and `ensure_structured_llm`. Returns `None` cleanly if disabled or not provided.

### What to Change
1. **Composition Root (`pipeline/pipeline.py`)**:
   - Update `Pipeline.for_task` signature to accept `decision_engine: Any | None = None`.
   - If `decision_engine is None` (and `config.decision_engine is None` or `provider == "none"`), pipeline executes the baseline generative LLM / CrossEncoder runners without modification.
   - If `decision_engine` is provided, normalize it, wrap it with `ObservableDecisionEngine` (`ISSUE-037`), and wire it into phase runners via cascading triage adapters.

### What to Remove
- Remove any implicit reliance on hardcoded model providers or direct LLM prompt roundtrips for binary/categorical pipeline routing flags.

---

## 3. Acceptance Criteria
- [ ] `DecisionEngine` protocol and Pydantic return contracts defined in `protocols/decision.py`.
- [ ] Pipeline executes identically to master when `decision_engine=None` (zero regressions for existing test suites).
- [ ] `StructuredPromptBundle` in `prompts/models.py` supports decision templates and criteria definitions.
- [ ] `DefaultPromptProvider` and `LangfusePromptProvider` in `prompts/providers.py` fetch and synchronize decision prompts.
- [ ] Static type conformance tests verify that mock and concrete implementations satisfy `DecisionEngine`.
- [ ] `PipelineConfig` accepts `decision_engine` configuration block with serializable defaults.
- [ ] `Pipeline.for_task` normalizes and wires `decision_engine` via dependency injection without breaking existing tasks.

---

## 4. Key Target Files
- `packages/episteme-pipeline/episteme_pipeline/protocols/decision.py`
- `packages/episteme-pipeline/episteme_pipeline/prompts/models.py`
- `packages/episteme-pipeline/episteme_pipeline/prompts/providers.py`
- `packages/episteme-pipeline/episteme_pipeline/prompts/default_prompts.py`
- `packages/episteme-pipeline/episteme_pipeline/config.py`
- `packages/episteme-pipeline/episteme_pipeline/pipeline.py`
- `packages/episteme-pipeline/tests/test_decision_engine_protocol.py`

---

## 5. Documentation Updates Required
- Update the system architecture overview documentation to include the Decision Engine subsystem alongside LLM and Embedding subsystems.
- Draft an Architecture Decision Record (ADR) detailing the two-tier contract design, optional dependency guarantees, and DI strategy.
- Update the configuration and prompt management reference documentation to describe `DecisionEngineConfig` and decision prompt templates.
