# Architecture: Cross-Cutting Concerns

This document details the design patterns and guidelines for managing cross-cutting concerns (Events/Observability,
Prompts, Caching, and Logging) in the `episteme-pipeline` without overcomplicating the codebase.

---

## Architectural Principles

1. **Keep Data Models Pure & Serializable**: Configuration models (e.g. `PipelineConfig`, `Phase2Config`) must be pure
   Pydantic data schemas without stateful runtime objects attached to them.
2. **Task-Local Context over Prop-Drilling**: Cross-cutting runtime services (like the `EventEmitter`) are dispatched
   via task-local execution contexts (`contextvars`) rather than passed through every function signature.
3. **Constructor Injection for Components**: Dependencies (like prompt bundles or LLM adapters) are passed explicitly
   into component constructors (`__init__`), keeping runtime execution methods (`extract()`, `run()`) focused strictly
   on data inputs.
4. **Single Source of Truth**: Avoid duplicate data models across modules.

---

## Events & Observability (`episteme_pipeline/events`)

### Design Pattern: Task-Local Context (`contextvars`)

Instead of passing an `event_emitter` parameter down 5 layers of method signatures or storing it on `PipelineConfig`,
active `EventEmitter` instances are bound to the execution context using `contextvars`.

#### Setting the Event Context

The pipeline orchestrator binds the active emitter at run time:

```python
from episteme_pipeline.events import use_event_emitter, SimpleEventEmitter

emitter = SimpleEventEmitter()
emitter.register_observer(LoggingObserver())

with use_event_emitter(emitter):
    # Any component invoked within this block automatically emits to `emitter`
    await pipeline.run(pipeline_input)
```

#### Emitting Events in Components

Components retrieve the active emitter dynamically without needing `event_emitter` passed into their constructors or
methods:

```python
from episteme_pipeline.events import get_event_emitter, TripleCommitted

# Retrieves context emitter, or fallback NoOpEventEmitter if none set
get_event_emitter().emit(TripleCommitted(subject_id=..., predicate=..., object_id=...))
```

---

## Prompt Management (`episteme_pipeline/prompts` & `episteme_pipeline/config.py`)

### Design Pattern: Unified `StructuredPromptBundle` via Constructor Injection

Prompts are managed using a single canonical Pydantic model (`StructuredPromptBundle` in `episteme_pipeline/config.py`).

#### Canonical Schema (`episteme_pipeline/config.py`)

```python
class StructuredPromptBundle(BaseModel):
    direct_template: str
    reasoning_template: str | None = None
    format_template: str | None = None
    gleaning_template: str | None = None
```

#### Prompt Constants (`episteme_pipeline/prompts/default_prompts.py`)

All default prompt templates live in `episteme_pipeline/prompts/default_prompts.py`.

#### Component Injection (`LLMNERExtractor`)

Extractors accept `prompts: StructuredPromptBundle | None = None` directly in `__init__`:

```python
class LLMNERExtractor(NERExtractor):
    def __init__(
        self, 
        llm: Any, 
        prompts: StructuredPromptBundle | None = None,
        max_gleanings: int = 0,
    ) -> None:
        self.llm = ensure_structured_llm(llm)
        self.prompts = prompts or DEFAULT_NER_PROMPTS
        self.max_gleanings = max_gleanings

    async def extract(self, chunk_id: str, chunk_text: str, schema: SchemaConfig):
        # Uses self.prompts.direct_template / self.prompts.gleaning_template
        raw = await self.llm.predict_structured(NERExtractionOutput, self.prompts, chunk_text=chunk_text)
```

---

## LLM Caching (`episteme_pipeline/llm/cache.py`)

### Design Pattern: Decorator / Adapter Wrapping

Caching is decoupled from business logic. Extractor implementations do not check or write to disk cache manually.
Instead, structured LLMs are wrapped via `DiskCachedStructuredLLM`:

```python
from episteme_pipeline.llm.cache import DiskCachedStructuredLLM

# LLM adapter is wrapped cleanly
cached_llm = DiskCachedStructuredLLM(llm_adapter)
```

---

## Logging

### Design Pattern: Module-Level Standard Loggers

Logging uses Python's standard `logging` module bound per-module. Heavy Dependency Injection for loggers is avoided:

```python
import logging

logger = logging.getLogger(__name__)

# Usage inside functions:
logger.info("Processed %d entities in chunk %s", len(entities), chunk_id)
```
