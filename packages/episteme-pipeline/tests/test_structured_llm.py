from __future__ import annotations

from pydantic import BaseModel
from llama_index.core import PromptTemplate

from episteme_pipeline.llm import (
    LlamaIndexStructuredLLMAdapter,
    StructuredPredictionError,
    ensure_structured_llm,
)
from episteme_pipeline.llm.structured import sanitize_structured_output
from episteme_pipeline.phases.phase2_entity_discovery.ner_extractor import LLMNERExtractor
from episteme_pipeline.schema.default_schema import SchemaConfig


class _SimpleOutput(BaseModel):
    value: int


class _CompletionResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def test_sanitize_structured_output_extracts_first_json_value() -> None:
    sanitized = sanitize_structured_output(
        "assistant: ```json\n{\"value\": 7}\n```\nextra text"
    )

    assert sanitized.value == {"value": 7}
    assert "trimmed_prefix" in sanitized.actions
    assert "stripped_role_prefix" in sanitized.actions
    assert "trimmed_suffix" in sanitized.actions


class _StrictSuccessLLM:
    async def astructured_predict(self, output_cls, prompt, llm_kwargs=None, **prompt_args):
        return output_cls(value=3)

    async def acomplete(self, prompt: str, **kwargs):
        raise AssertionError("Fallback completion should not be called")


class _ExceptionRecoveryLLM:
    def __init__(self) -> None:
        self.complete_calls = 0

    async def astructured_predict(self, output_cls, prompt, llm_kwargs=None, **prompt_args):
        raise ValueError("assistant: {\"value\": 5}")

    async def acomplete(self, prompt: str, **kwargs):
        self.complete_calls += 1
        return _CompletionResponse("{\"value\": 0}")


class _CompletionFallbackLLM:
    def __init__(self, completion_text: str) -> None:
        self.complete_calls = 0
        self.completion_text = completion_text

    async def astructured_predict(self, output_cls, prompt, llm_kwargs=None, **prompt_args):
        raise RuntimeError("strict path failed")

    async def acomplete(self, prompt: str, **kwargs):
        self.complete_calls += 1
        return _CompletionResponse(self.completion_text)


async def test_structured_llm_adapter_uses_strict_path_first() -> None:
    adapter = LlamaIndexStructuredLLMAdapter(_StrictSuccessLLM())

    output = await adapter.predict_structured(
        _SimpleOutput,
        PromptTemplate("ignored"),
    )

    assert output.value == 3


async def test_structured_llm_adapter_recovers_from_exception_payload() -> None:
    llm = _ExceptionRecoveryLLM()
    adapter = LlamaIndexStructuredLLMAdapter(llm)

    output = await adapter.predict_structured(
        _SimpleOutput,
        PromptTemplate("ignored"),
    )

    assert output.value == 5
    assert llm.complete_calls == 0


async def test_structured_llm_adapter_falls_back_to_raw_completion() -> None:
    llm = _CompletionFallbackLLM("```json\n{\"value\": 9}\n```")
    adapter = LlamaIndexStructuredLLMAdapter(llm)

    output = await adapter.predict_structured(
        _SimpleOutput,
        PromptTemplate("value={value}"),
        value=9,
    )

    assert output.value == 9
    assert llm.complete_calls == 1


async def test_structured_llm_adapter_raises_on_unrecoverable_output() -> None:
    adapter = LlamaIndexStructuredLLMAdapter(
        _CompletionFallbackLLM("not json at all")
    )

    try:
        await adapter.predict_structured(
            _SimpleOutput,
            PromptTemplate("ignored"),
        )
    except StructuredPredictionError:
        pass
    else:
        raise AssertionError("Expected StructuredPredictionError")


class _WrappedNERLLM:
    async def astructured_predict(self, output_cls, prompt, llm_kwargs=None, **prompt_args):
        raise ValueError(
            """assistant: {
  "entities": [
    {"id": "e1", "label": "AXIOM", "name": "axioms", "mention_quote": "axioms"},
    {"id": "e2", "label": "KONZEPT", "name": "core", "mention_quote": "core"},
    {"id": "e3", "label": "KONZEPT", "name": "periphery", "mention_quote": "periphery"},
    {"id": "e4", "label": "KONZEPT", "name": "theory identity", "mention_quote": "theory identity"},
    {"id": "e5", "label": "KONZEPT", "name": "roles", "mention_quote": "roles"}
  ],
  "triples": [
    {"subject_id": "e2", "predicate": "TEIL_VON", "object_id": "e1", "confidence": 0.92},
    {"subject_id": "e3", "predicate": "TEIL_VON", "object_id": "e1", "confidence": 0.92},
    {"subject_id": "e1", "predicate": "BEHANDELT_THEMA", "object_id": "e4", "confidence": 0.85},
    {"subject_id": "e5", "predicate": "TEIL_VON", "object_id": "e1", "confidence": 0.85}
  ]
}"""
        )

    async def acomplete(self, prompt: str, **kwargs):
        raise AssertionError("Exception recovery should be enough for this test")


async def test_llm_ner_extractor_recovers_wrapped_assistant_json() -> None:
    extractor = LLMNERExtractor(_WrappedNERLLM())

    entities, triples, *_ = await extractor.extract(
        chunk_id="chunk_1",
        chunk_text="ignored",
        schema=SchemaConfig(
            node_types=["AXIOM", "KONZEPT"],
            relation_types=["TEIL_VON", "BEHANDELT_THEMA"],
        ),
    )


    assert len(entities) == 5
    assert {entity.label for entity in entities} == {"AXIOM", "KONZEPT"}
    assert len(triples) == 4
    assert {triple.predicate for triple in triples} == {
        "TEIL_VON",
        "BEHANDELT_THEMA",
    }


def test_ensure_structured_llm_wraps_once() -> None:
    wrapped = ensure_structured_llm(_StrictSuccessLLM())

    assert wrapped is not None
    assert ensure_structured_llm(wrapped) is wrapped
