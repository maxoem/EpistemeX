"""Unit tests for Langfuse generation observability, token extraction, and session propagation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from llama_index.core import PromptTemplate
from pydantic import BaseModel

from episteme_pipeline.events.bus import SimpleEventEmitter
from episteme_pipeline.events.context import use_event_emitter
from episteme_pipeline.events.langfuse_observer import LangfuseObserver
from episteme_pipeline.events.models import (
    EvaluationCompleted,
    EvaluationScoreLogged,
    LLMGenerationCompleted,
)
from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
from episteme_pipeline.llm.metadata import LLMResponseMetadataExtractor
from episteme_pipeline.llm.structured import LlamaIndexStructuredLLMAdapter


class _FakeStructuredOutput(BaseModel):
    name: str
    value: int


class _FakeCompletionResponse:
    def __init__(self, text: str, usage: dict[str, int] | None = None) -> None:
        self.text = text
        self.additional_kwargs = {"usage": usage} if usage else {}


class _FakeLLMWithUsage:
    def __init__(self, model_name: str = "mock-gpt-4o", usage: dict[str, int] | None = None) -> None:
        self.model_name = model_name
        self.temperature = 0.2
        self.max_tokens = 1000
        self.usage = usage or {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}

    async def astructured_predict(self, output_cls: type[Any], prompt: Any, **kwargs: Any) -> Any:
        res = output_cls(name="test_entity", value=42)
        # Mock usage attached to object
        res.__dict__["usage"] = self.usage
        return res

    async def acomplete(self, prompt: str, **kwargs: Any) -> _FakeCompletionResponse:
        return _FakeCompletionResponse(
            text='{"name": "test_entity", "value": 42}',
            usage=self.usage,
        )


class _MockLangfuseClient:
    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []
        self.scores: list[dict[str, Any]] = []
        self._current_trace_id = "trace-12345"

    def get_current_trace_id(self) -> str:
        return self._current_trace_id

    def create_score(self, *, trace_id: str, name: str, value: float, comment: str | None = None) -> None:
        self.scores.append({"trace_id": trace_id, "name": name, "value": value, "comment": comment})

    def start_observation(
        self,
        *,
        name: str,
        input: Any = None,
        output: Any = None,
        as_type: str = "span",
        usage_details: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        rec: dict[str, Any] = {
            "name": name,
            "input": input,
            "output": output,
            "as_type": as_type,
            "usage_details": usage_details,
            "metadata": metadata,
            "updates": [],
            "kwargs": kwargs,
            "ended": False,
        }
        self.spans.append(rec)

        class _Obs:
            def end(self_inner: Any) -> None:
                rec["ended"] = True

            def update(self_inner: Any, **kw: Any) -> None:
                if rec["ended"]:
                    # Real OpenTelemetry / Langfuse behavior: updates after end() are silently dropped
                    return
                rec["updates"].append(kw)
                if "output" in kw:
                    rec["output"] = kw["output"]
                if "usage_details" in kw:
                    rec["usage_details"] = kw["usage_details"]
                if "metadata" in kw:
                    rec["metadata"] = kw["metadata"]

        return _Obs()


def test_token_usage_extractor_from_dict_and_objects() -> None:
    """Test extracting usage from dictionary, attributes, and text fallback."""
    # From dict
    usage_dict = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    u1 = LLMResponseMetadataExtractor.extract_usage(usage_dict)
    assert u1.prompt_tokens == 10
    assert u1.completion_tokens == 20
    assert u1.total_tokens == 30

    # From completion response with additional_kwargs
    resp = _FakeCompletionResponse("hello world", usage={"prompt_tokens": 5, "completion_tokens": 15})
    u2 = LLMResponseMetadataExtractor.extract_usage(resp)
    assert u2.prompt_tokens == 5
    assert u2.completion_tokens == 15
    assert u2.total_tokens == 20

    # From fallback estimation
    u3 = LLMResponseMetadataExtractor.extract_usage(None, prompt_text="A short prompt", output_text="A short response")
    assert u3.prompt_tokens > 0
    assert u3.completion_tokens > 0
    assert u3.total_tokens == u3.prompt_tokens + u3.completion_tokens


@pytest.mark.asyncio
async def test_structured_llm_adapter_emits_generation_event() -> None:
    """Adapter emits LLMGenerationCompleted with extracted tokens."""
    emitter = SimpleEventEmitter()
    events: list[Any] = []

    class _Capture:
        def on_event(self, e: Any) -> None:
            events.append(e)

    emitter.register_observer(_Capture())

    with use_event_emitter(emitter):
        llm = _FakeLLMWithUsage(model_name="gpt-4o-mini", usage={"prompt_tokens": 50, "completion_tokens": 75})
        adapter = LlamaIndexStructuredLLMAdapter(llm)

        # 1. Structured prediction
        res = await adapter.predict_structured(
            _FakeStructuredOutput,
            PromptTemplate("Extract entity from: {text}"),
            text="sample input",
        )
        assert res.name == "test_entity"
        assert res.value == 42

        # 2. Text prediction
        text_res = await adapter.predict_text(
            PromptTemplate("Summarize: {text}"),
            text="sample input",
        )
        assert "test_entity" in text_res

    generation_events = [e for e in events if isinstance(e, LLMGenerationCompleted)]
    assert len(generation_events) == 2

    # Structured predict event assertions
    struct_event = generation_events[0]
    assert struct_event.operation == "structured_predict"
    assert struct_event.model_name == "gpt-4o-mini"
    assert struct_event.prompt_tokens == 50
    assert struct_event.completion_tokens == 75
    assert struct_event.total_tokens == 125
    assert struct_event.output_json == {"name": "test_entity", "value": 42}
    assert struct_event.cached is False

    # Text predict event assertions
    text_event = generation_events[1]
    assert text_event.operation == "text_completion"
    assert text_event.prompt_tokens == 50
    assert text_event.completion_tokens == 75


@pytest.mark.asyncio
async def test_disk_cache_emits_cached_generation_event(tmp_path: Path) -> None:
    """DiskCachedStructuredLLM emits LLMGenerationCompleted with cached=True on cache hits."""
    emitter = SimpleEventEmitter()
    events: list[Any] = []

    class _Capture:
        def on_event(self, e: Any) -> None:
            events.append(e)

    emitter.register_observer(_Capture())

    with use_event_emitter(emitter):
        llm = _FakeLLMWithUsage(model_name="gpt-4o-mini")
        adapter = LlamaIndexStructuredLLMAdapter(llm)
        cached_llm = DiskCachedStructuredLLM(adapter, cache_dir=tmp_path / "cache")

        # First call (Cache Miss)
        await cached_llm.predict_structured(
            _FakeStructuredOutput,
            PromptTemplate("Extract: {text}"),
            text="same input",
        )
        miss_events = [e for e in events if isinstance(e, LLMGenerationCompleted)]
        assert len(miss_events) == 1
        assert miss_events[0].cached is False

        # Second call (Cache Hit)
        events.clear()
        cached_res = await cached_llm.predict_structured(
            _FakeStructuredOutput,
            PromptTemplate("Extract: {text}"),
            text="same input",
        )
        assert cached_res.name == "test_entity"
        hit_events = [e for e in events if isinstance(e, LLMGenerationCompleted)]
        assert len(hit_events) == 1
        assert hit_events[0].cached is True
        assert hit_events[0].prompt_tokens == 0
        assert hit_events[0].completion_tokens == 0


def test_langfuse_observer_maps_generation_and_scores(monkeypatch: Any) -> None:
    """LangfuseObserver maps LLMGenerationCompleted to 'generation' observation and publishes scores."""
    monkeypatch.setattr("episteme_pipeline.events.langfuse_observer.LANGFUSE_AVAILABLE", True)
    client = _MockLangfuseClient()
    obs = LangfuseObserver(client=client)

    # 1. Emit LLMGenerationCompleted
    obs.on_event(
        LLMGenerationCompleted(
            model_name="openai/gpt-4o",
            prompt="Extract claims from text",
            output_text='{"claims": ["c1", "c2"]}',
            output_json={"claims": ["c1", "c2"]},
            prompt_tokens=120,
            completion_tokens=45,
            total_tokens=165,
            duration_seconds=0.45,
            operation="structured_predict",
            cached=False,
            model_parameters={"temperature": 0.0},
        )
    )

    gen_spans = [s for s in client.spans if s["as_type"] == "generation"]
    assert len(gen_spans) == 1
    gen = gen_spans[0]
    assert gen["name"] == "llm.structured_predict"
    assert gen["kwargs"]["model"] == "openai/gpt-4o"
    assert gen["input"] == "Extract claims from text"
    assert gen["output"] == {"claims": ["c1", "c2"]}
    assert gen["usage_details"] == {"input": 120, "output": 45, "total": 165}
    assert gen["metadata"]["cached"] is False
    assert gen["metadata"]["duration_seconds"] == 0.45

    # 2. Emit EvaluationScoreLogged
    obs.on_event(
        EvaluationScoreLogged(
            metric_name="oep_score",
            score=0.88,
            comment="High epistemic consistency",
        )
    )

    assert len(client.scores) == 1
    score_entry = client.scores[0]
    assert score_entry["name"] == "oep_score"
    assert score_entry["value"] == 0.88
    assert score_entry["comment"] == "High epistemic consistency"
    assert score_entry["trace_id"] == "trace-12345"

    # 3. Emit EvaluationCompleted
    obs.on_event(
        EvaluationCompleted(
            evaluation_id="eval-run-99",
            run_id="run-12345",
            metrics={"gm_gbs": 0.92, "oep": 0.88},
            outcome="passed",
        )
    )
    assert len(client.scores) == 3


class _MockRawEmbeddingEncoder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self.device = "cpu"
        self.dimension = 384

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dimension for _ in texts]


@pytest.mark.asyncio
async def test_observable_embedding_model_emits_events() -> None:
    """ObservableEmbeddingModel emits EmbeddingGenerationCompleted upon computing embeddings."""
    from episteme_pipeline.protocols.extractors import ensure_embedding_model
    from episteme_pipeline.events.models import EmbeddingGenerationCompleted

    emitter = SimpleEventEmitter()
    events: list[Any] = []

    class _Capture:
        def on_event(self, e: Any) -> None:
            events.append(e)

    emitter.register_observer(_Capture())

    with use_event_emitter(emitter):
        raw_encoder = _MockRawEmbeddingEncoder(model_name="sentence-transformers/all-MiniLM-L6-v2")
        model = ensure_embedding_model(raw_encoder)
        assert model is not None

        # 1. Single embedding
        vec = await model.aget_text_embedding("A brief entity description.")
        assert len(vec) == 384

        # 2. Batch embedding
        batch = await model.aget_text_embedding_batch(["Text A", "Text B", "Text C"])
        assert len(batch) == 3
        assert len(batch[0]) == 384

    embed_events = [e for e in events if isinstance(e, EmbeddingGenerationCompleted)]
    assert len(embed_events) == 2

    e1 = embed_events[0]
    assert e1.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert e1.text_count == 1
    assert e1.total_characters > 0
    assert e1.prompt_tokens > 0
    assert e1.vector_dim == 384

    e2 = embed_events[1]
    assert e2.text_count == 3
    assert e2.vector_dim == 384


def test_langfuse_observer_maps_embedding_generation(monkeypatch: Any) -> None:
    """LangfuseObserver maps EmbeddingGenerationCompleted to 'generation' observation with token usage."""
    from episteme_pipeline.events.models import EmbeddingGenerationCompleted

    monkeypatch.setattr("episteme_pipeline.events.langfuse_observer.LANGFUSE_AVAILABLE", True)
    client = _MockLangfuseClient()
    obs = LangfuseObserver(client=client)

    obs.on_event(
        EmbeddingGenerationCompleted(
            model_name="text-embedding-3-small",
            text_count=5,
            total_characters=250,
            prompt_tokens=60,
            total_tokens=60,
            duration_seconds=0.12,
            vector_dim=1536,
            operation="embedding",
        )
    )

    embed_spans = [s for s in client.spans if s["name"] == "embed.embedding"]
    assert len(embed_spans) == 1
    span = embed_spans[0]
    assert span["as_type"] == "generation"
    assert span["kwargs"]["model"] == "text-embedding-3-small"
    assert "Embedded 5 texts" in span["input"]
    assert span["output"] == {"text_count": 5, "vector_dim": 1536}
    assert span["usage_details"] == {"input": 60, "output": 0, "total": 60}
    assert span["metadata"]["vector_dim"] == 1536


def test_langfuse_observer_maps_domain_and_lifecycle_events(monkeypatch: Any) -> None:
    """LangfuseObserver captures domain outputs (reranker, linking, chunks) and lifecycle properly."""
    from episteme_pipeline.events.models import (
        ComponentStarted,
        ComponentCompleted,
        PhaseCompleted,
        RerankerScoreAssigned,
        LLMDurationMeasured,
    )

    monkeypatch.setattr("episteme_pipeline.events.langfuse_observer.LANGFUSE_AVAILABLE", True)
    client = _MockLangfuseClient()
    obs = LangfuseObserver(client=client)

    # 1. Component lifecycle
    obs.on_event(ComponentStarted(component_name="ner_extractor", input_description="Extracting from chunk_1"))
    assert len(client.spans) == 1
    assert client.spans[0]["name"] == "component.ner_extractor"
    assert client.spans[0]["ended"] is False

    obs.on_event(
        ComponentCompleted(
            component_name="ner_extractor",
            duration_seconds=1.23,
            success=True,
            output_description="Found 3 entities",
        )
    )
    assert client.spans[0]["ended"] is True
    assert client.spans[0]["output"]["duration_seconds"] == 1.23
    assert client.spans[0]["output"]["success"] is True

    # 2. Phase lifecycle
    obs.on_event(
        PhaseCompleted(
            phase_name="phase1",
            duration_seconds=2.5,
            artifact_count=10,
            success=True,
        )
    )
    phase_span = client.spans[1]
    assert phase_span["name"] == "phase.phase1"
    assert phase_span["input"] == {"artifact_count": 10}
    assert phase_span["output"]["duration_seconds"] == 2.5
    assert phase_span["output"]["success"] is True

    # 3. Reranker score event
    obs.on_event(
        RerankerScoreAssigned(
            candidate_pair=("ent_1", "ent_2"),
            score=0.91,
            accepted=True,
            threshold=0.85,
            entity_a={"name": "A"},
            entity_b={"name": "B"},
            reranker_input={"query_chars": 100, "doc_chars": 150},
        )
    )
    rerank_span = client.spans[2]
    assert rerank_span["name"] == "phase3.dense.rerank"
    assert rerank_span["input"]["candidate_pair"] == ("ent_1", "ent_2")
    assert rerank_span["output"]["score"] == 0.91
    assert rerank_span["output"]["accepted"] is True

    # 4. LLMDurationMeasured should be ignored (no duplicate generation created)
    obs.on_event(
        LLMDurationMeasured(
            model_name="test-model",
            prompt_tokens=10,
            completion_tokens=20,
            duration_seconds=0.5,
            operation="structured_predict",
        )
    )
    assert len([s for s in client.spans if s["name"] == "llm.structured_predict"]) == 0

