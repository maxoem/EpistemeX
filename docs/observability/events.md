# Event Reference and Observers

This document serves as the technical reference catalog and developer guide for the **Episteme** event system.
It details all domain event schemas, available built-in observers, and patterns for emitting and consuming events.

*For the conceptual system design, contextvar dispatch mechanics, and architectural guarantees, see
[Event System Architecture](../architecture/event-system.md).*

---

#Base Event Schema

All pipeline events are Pydantic v2 models defined in `pipeline/events/models.py` inheriting from `BaseEvent`:

| Attribute | Type | Description |
|:---|:---|:---|
| `timestamp` | `datetime` | UTC timestamp when the event was created (defaults to `datetime.now(timezone.utc)`). |
| `run_id` | `str \| None` | Identifier for the pipeline run the event belongs to. |
| `phase` | `str \| None` | Pipeline phase name active when the event occurred (e.g., `"phase_2_extraction"`). |

---

#Event Reference Catalog

##Entity & Maturation Events

Events related to entity processing, textual envelope injection, entity linking, and centroid description synthesis.

| Event Class | Emitted In / Phase | Key Attributes | Description |
|:---|:---|:---|:---|
| `EntityProcessed` | Phase 2 (Extraction) | `entity_id: str`<br/>`entity_name: str`<br/>`entity_type: str` | Emitted when an entity mention is extracted and processed. |
| `EnvelopeInjectionAttempted` | Phase 2 (Extraction) | `mention_name: str`<br/>`chunk_id: str` | Attempt made to locate and attach a textual sentence envelope to a mention. |
| `EnvelopeInjectionFailed` | Phase 2 (Extraction) | `mention_name: str`<br/>`mention_quote: str`<br/>`chunk_id: str`<br/>`reason: str` | Failed to locate or inject a textual envelope for a mention after all fallbacks. |
| `EntityLinkingCandidatesRetrieved` | Entity Linking / Fusion | `mention_id: str`<br/>`mention_name: str`<br/>`candidate_count: int`<br/>`candidates: list[dict]` | Dense vector retrieval fetched candidate canonical entities for a mention. |
| `EntityLinkingReranked` | Entity Linking / Fusion | `mention_id: str`<br/>`candidate_id: str`<br/>`score: float`<br/>`accepted: bool`<br/>`threshold: float` | Cross-encoder scored an entity linking candidate against an acceptance threshold. |
| `EntityMaturationSynthesized` | Maturation / Fusion | `entity_id: str`<br/>`entity_name: str`<br/>`envelope_count: int`<br/>`top_k_used: int`<br/>`synthesized_description: str` | LLM synthesized an aggregated entity description from top-K textual envelope centroids. |

##Extraction & Relation Events

Events capturing candidate generation, cross-encoder reranking, and LLM relation decoding.

| Event Class | Emitted In / Phase | Key Attributes | Description |
|:---|:---|:---|:---|
| `DenseCandidatesGenerated` | Phase 2 (Dense Retrieval) | `candidate_count: int`<br/>`candidates: list[dict]`<br/>`entities_count: int` | Dense index retrieved candidate entity pairs for relation extraction. |
| `RerankerScoreAssigned` | Phase 2 (Reranker) | `candidate_pair: tuple[str, str]`<br/>`score: float`<br/>`accepted: bool`<br/>`threshold: float`<br/>`reranker_input: dict \| None` | Cross-encoder scored an entity pair, determining if it advances to LLM extraction. |
| `CandidateRejectedByThreshold` | Phase 2 (Reranker) | `candidate_pair: tuple[str, str]`<br/>`score: float`<br/>`threshold: float`<br/>`reason: str` | Candidate pair rejected due to score falling below the acceptance threshold. |
| `LLMRelationDecoded` | Phase 2 (LLM Extractor) | `candidate_pair: tuple[str, str]`<br/>`relation: str \| None`<br/>`direction: str \| None`<br/>`confidence: float \| None` | LLM extracted or decoded a semantic relation between a candidate pair. |
| `SchemaValidationRejectedRelation` | Phase 2 (Validation) | `candidate_pair: tuple[str, str]`<br/>`relation: str`<br/>`reason: str` | Extracted relation rejected because it does not conform to the active schema taxonomy. |

##Graph & Fusion Events

Events recording persistence into Neo4j and entity fusion / resolution.

| Event Class | Emitted In / Phase | Key Attributes | Description |
|:---|:---|:---|:---|
| `TripleCommitted` | Persistence / Phase 2 & 3 | `subject_id: str`<br/>`predicate: str`<br/>`object_id: str`<br/>`confidence: float`<br/>`scope: str`<br/>`source_chunk_id: str` | Validated triple written to the property graph store. |
| `FusionDecisionMade` | Phase 3 (Fusion) | `entities_fused: list[str]`<br/>`fusion_type: str`<br/>`confidence: float`<br/>`reason: str \| None` | Entity resolution decision merged multiple entity nodes into a canonical node. |

##Pipeline Lifecycle & Projection Events

Events tracking phase execution, component start/stop boundaries, chunk generation, and projection.

| Event Class | Emitted In / Phase | Key Attributes | Description |
|:---|:---|:---|:---|
| `PhaseCompleted` | Pipeline Orchestrator | `phase_name: str`<br/>`duration_seconds: float`<br/>`artifact_count: int`<br/>`success: bool`<br/>`error_message: str \| None` | Pipeline phase finished execution. |
| `ComponentStarted` | Component Runners | `component_name: str`<br/>`input_description: str \| None` | Subsystem component began processing. |
| `ComponentCompleted` | Component Runners | `component_name: str`<br/>`duration_seconds: float`<br/>`output_description: str \| None`<br/>`success: bool` | Subsystem component finished processing. |
| `ChunksGenerated` | Phase 1 (Chunking) | `document_id: str`<br/>`document_title: str`<br/>`chunk_count: int`<br/>`token_count: int` | Text chunking completed for a source document. |
| `ArtifactProjected` | Projection Layer | `artifact_type: str`<br/>`duration_seconds: float`<br/>`success: bool` | Intermediate artifact projected into the projection graph. |

##LLM & Inference Telemetry Events

Events capturing detailed latency, prompt/completion tokens, and model parameters for cost and performance tracking.

| Event Class | Emitted In / Phase | Key Attributes | Description |
|:---|:---|:---|:---|
| `LLMDurationMeasured` | LLM Client Facades | `model_name: str`<br/>`prompt_tokens: int`<br/>`completion_tokens: int`<br/>`duration_seconds: float`<br/>`operation: str` | Latency and token consumption measured for an LLM call. |
| `LLMGenerationCompleted` | LLM Client Facades | `model_name: str`<br/>`prompt: Any`<br/>`output_text: str`<br/>`total_tokens: int`<br/>`duration_seconds: float`<br/>`cached: bool`<br/>`model_parameters: dict \| None` | Comprehensive generation record forwarded to observability backends (e.g., Langfuse). |
| `EmbeddingGenerationCompleted` | Embedding Models | `model_name: str`<br/>`text_count: int`<br/>`total_characters: int`<br/>`total_tokens: int`<br/>`duration_seconds: float`<br/>`cached: bool` | Batch vector embedding generation completed. |

##Decision Engine & System 1 Events

Events emitted during non-generative, typed classification, sub-second routing, and dynamic flow gating (TypeSafe Jev / Laya).

| Event Class | Emitted In / Phase | Key Attributes | Description |
|:---|:---|:---|:---|
| `DecisionEvaluationStarted` | Decision Engine Subsystem | `engine_name: str`<br/>`primitive: str`<br/>`question: str`<br/>`state_hash: str`<br/>`state_character_count: int` | Emitted when a System 1 decision evaluation begins over an input state block. |
| `DecisionEvaluationCompleted` | Decision Engine Subsystem | `engine_name: str`<br/>`primitive: str`<br/>`selected_value: Any`<br/>`class_probability: float`<br/>`empirical_accuracy: float`<br/>`prediction_set: list[str] \| None`<br/>`is_stochastic_audit: bool`<br/>`duration_seconds: float`<br/>`tokens_saved_estimate: int` | Emitted when a System 1 decision completes, capturing calibrated confidence, conformal prediction set, duration, and token savings. |
| `DecisionGatingTriggered` | Phase Gate Adapters | `gate_name: str`<br/>`action_taken: str`<br/>`empirical_accuracy: float`<br/>`threshold: float`<br/>`prediction_set_size: int \| None` | Emitted when a dynamic gate triggers a routing decision (`fast_exit`, `escalated_to_llm`, `stochastic_audit`, `loop_terminated`). |

##Progress, Evaluation & Validation Events

Events tracking progress indicators, epistemic metrics, and schema violation warnings.

| Event Class | Emitted In / Phase | Key Attributes | Description |
|:---|:---|:---|:---|
| `ProgressStarted` | Task Runners | `task_name: str`<br/>`total_items: int \| None`<br/>`description: str` | Progress tracking started for an iterative or batch workload. |
| `ProgressAdvanced` | Task Runners | `task_name: str`<br/>`advance: int` | Progress advanced by `advance` units. |
| `ProgressCompleted` | Task Runners | `task_name: str` | Progress tracking completed for a task. |
| `EvaluationCompleted` | Phase 5 (Evaluation) | `evaluation_id: str`<br/>`run_id: str`<br/>`metrics: dict[str, float]`<br/>`outcome: str` | Evaluation suite finished running. |
| `EvaluationScoreLogged` | Evaluation / Metrics | `metric_name: str`<br/>`score: float`<br/>`comment: str \| None`<br/>`target_id: str \| None` | Specific evaluation score logged (e.g., OEP, GM-GBS, modularity). |
| `ValidationViolationDetected` | Validation Layer | `rule_name: str`<br/>`source_id: str`<br/>`target_id: str`<br/>`description: str` | Graph structural or schema violation detected. |

---

#Built-in Observers

The event system includes several built-in observers located in `pipeline/events/`:

| Observer | Module | Primary Sink | Purpose & Configuration |
|:---|:---|:---|:---|
| `LoggingObserver` | `observers.py` | Python standard `logging` / stdout | Translates domain events into human-readable log messages with appropriate log levels. |
| `JsonlRunObserver` | `observers.py` | Append-only `.jsonl` file | Persists structured JSON lines for every event. Serves as the primary research audit trail and replay log. |
| `MetricsObserver` | `observers.py` | In-memory counters / dictionaries | Aggregates summary statistics (acceptance rates, candidate counts, error counts) during execution. |
| `RichProgressObserver` | `progress_observer.py` | Interactive TTY Console | Displays live, animated progress bars for tasks emitting `ProgressStarted/Advanced/Completed`. Requires an interactive terminal. |
| `LangfuseObserver` | `langfuse_observer.py` | Langfuse API | Maps component lifecycle to spans, LLM events to generations, and evaluation metrics to scores. |
| `CompositeObserver` | `observers.py` | Multiple Observers | Dispatches each event sequentially to an arbitrary list of child observers. |

---

#How-To Guides

##Emitting Events in Pipeline Components

Components retrieve the active emitter via `get_event_emitter()` from task-local context and emit typed event instances:

```python
from pipeline.events import get_event_emitter
from pipeline.events.models import DenseCandidatesGenerated, RerankerScoreAssigned

class DenseRetrievalService:
    def retrieve_candidates(self, entities: list[dict], run_id: str) -> list[dict]:
        # Perform retrieval...
        candidates = [...]

        # Emit domain event:
        get_event_emitter().emit(
            DenseCandidatesGenerated(
                run_id=run_id,
                phase="phase_2_extraction",
                candidate_count=len(candidates),
                candidates=[{"pair": c["pair"], "score": c["score"]} for c in candidates[:10]],
                entities_count=len(entities),
            )
        )
        return candidates
```

!!! tip ""

    Do not pass `event_emitter` through component constructors. `get_event_emitter()` uses Python's `contextvars` to
    automatically resolve the active emitter for the current asynchronous execution context.

##Configuring Observers for a Pipeline Run

Use `CompositeObserver` to fan out events to multiple sinks, and bind the emitter using `use_event_emitter`:

```python
from pathlib import Path
from pipeline.events import (
    SimpleEventEmitter,
    CompositeObserver,
    LoggingObserver,
    JsonlRunObserver,
    use_event_emitter,
)
from pipeline.events.langfuse_observer import LangfuseObserver

# 1. Instantiate desired observers:
observers = [
    LoggingObserver(),
    JsonlRunObserver(filepath=Path("runs/run_001/events.jsonl")),
]

# Add Langfuse if configured:
if langfuse_enabled:
    observers.append(LangfuseObserver())

# 2. Wrap in CompositeObserver and register with emitter:
emitter = SimpleEventEmitter()
emitter.register_observer(CompositeObserver(observers=observers))

# 3. Bind to task-local context for pipeline execution:
with use_event_emitter(emitter):
    result = await pipeline.run(pipeline_input)
```

##Implementing a Custom Observer

To implement a new observer, subclass `EventObserver` and define the `on_event` handler:

```python
import logging
from pipeline.events.bus import EventObserver
from pipeline.events.models import PipelineEvent, TripleCommitted

logger = logging.getLogger(__name__)

class TripleCounterObserver(EventObserver):
    """Custom observer that counts committed triples."""

    def __init__(self) -> None:
        self.count: int = 0

    def on_event(self, event: PipelineEvent) -> None:
        try:
            if isinstance(event, TripleCommitted):
                self.count += 1
        except Exception as e:
            # Observers must isolate exceptions so the pipeline is not interrupted
            logger.warning(f"Error in TripleCounterObserver: {e}")
```

##Decision Engine Observability & Langfuse Tracing

System 1 decision evaluations (via TypeSafe Jev / Laya) are transparently instrumented through `ObservableDecisionEngine`:

1. **Span & Generation Observations**:
   Each `evaluate_choice`, `evaluate_noul`, or `evaluate_score` call produces a `decision.{primitive}` generation observation attached to the current Langfuse trace.
   - **Model & Metadata**: Tagged with `system_1: True`, the specific checkpoint, calibrated `class_probability`, `empirical_accuracy`, and `duration_seconds`.
   - **Prompt Management Linking**: Automatically carries `prompt_name`, `prompt_version`, and `prompt_label` to evaluate rubric performance in the Langfuse UI.
   - **Token Accounting**: Computes `tokens_saved_estimate` (heuristic bypassed prompt + completion tokens) recorded under `usage_details`.

2. **Active Learning Queue Hook**:
   When an evaluation exhibits high epistemic uncertainty—either producing a multi-class conformal prediction set ($|C(X)| > 1$) or intermediate entropy ($0.40 \le P \le 0.60$)—`LangfuseObserver` flags the observation with `active_learning_candidate: True` and writes an entry into the Langfuse Dataset `decision_engine_active_learning` for human review and offline distillation.

3. **Dynamic Gating Telemetry**:
   Dynamic fast-exits and System 2 escalations emit `DecisionGatingTriggered`, recorded as `decision.gate.{gate_name}` spans documenting whether an item was fast-exited, escalated to an LLM, or randomly audited.

---

#Best Practices

1. **Keep Payloads Compact**:
   - Do not embed entire documents, giant prompt templates, or full graph states inside events.
   - Use stable identifiers (`entity_id`, `chunk_id`, `document_id`) and counts.
2. **Ensure Timezone Awareness**:
   - All events default to `datetime.now(timezone.utc)`. Never emit naive datetime objects.
3. **Isolate Failures**:
   - Observers must catch their own exceptions. An observer crash must never fail the pipeline.
4. **Side-Effect Only**:
   - Observers must never mutate the received event instance or attempt to alter pipeline execution flow.
