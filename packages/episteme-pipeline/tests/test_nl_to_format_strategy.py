"""Regression tests for the NL_TO_FORMAT decoding strategy (F-10).

``ensure_structured_llm`` wraps every adapter in ``DiskCachedStructuredLLM``, so
the object a phase holds is the cache, not the adapter. ``execute_nl_to_format``
used to gate the two-pass path on ``isinstance(llm, LlamaIndexStructuredLLMAdapter)``
— a check that therefore never held. NL_TO_FORMAT is the configured default for
NER, global relations, ACC and ARC, and all four silently ran as single-pass
DIRECT.

Nothing raised: the fallback branch is a valid decode, just not the requested
one. Hence these tests, which assert on the *number of model calls* rather than
on the result.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from episteme_pipeline.config import StructuredDecodingStrategy
from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
from episteme_pipeline.llm.structured import (
    LlamaIndexStructuredLLMAdapter,
    ensure_structured_llm,
)
from pydantic import BaseModel


class Answer(BaseModel):
    value: str


@dataclass
class _Bundle:
    """Stands in for StructuredPromptBundle; templates are plain strings."""

    direct_template: str = "DIRECT {topic}"
    reasoning_template: str = "REASON {topic}"
    format_template: str = "FORMAT {topic} :: {reasoning_text}"


class _RecordingLLM:
    """Minimal llama-index-shaped facade that records every call."""

    def __init__(self) -> None:
        self.completions: list[str] = []
        self.structured: list[str] = []

    async def acomplete(self, prompt: str, **kwargs):
        self.completions.append(prompt)

        class _Resp:
            text = "because reasons"

        return _Resp()

    async def astructured_predict(self, output_cls, prompt, llm_kwargs=None, **kw):
        rendered = prompt.template if hasattr(prompt, "template") else str(prompt)
        self.structured.append(rendered.format(**kw))
        return output_cls(value="ok")


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "llm_cache"


@pytest.mark.asyncio
async def test_nl_to_format_runs_two_passes_through_the_cache(cache_dir):
    """The decorated stack must still make a reasoning call, then a format call."""
    base = _RecordingLLM()
    llm = DiskCachedStructuredLLM(
        LlamaIndexStructuredLLMAdapter(base), cache_dir=cache_dir
    )

    result = await llm.predict_structured(
        Answer,
        _Bundle(),
        strategy=StructuredDecodingStrategy.NL_TO_FORMAT,
        topic="t",
    )

    assert result.value == "ok"
    assert base.completions == ["REASON t"], "reasoning pass did not run"
    assert len(base.structured) == 1
    assert "because reasons" in base.structured[0], (
        "format pass did not receive the reasoning output"
    )


@pytest.mark.asyncio
async def test_nl_to_format_runs_two_passes_on_the_bare_adapter(cache_dir):
    """Same behaviour without the cache decorator in the way."""
    base = _RecordingLLM()
    adapter = LlamaIndexStructuredLLMAdapter(base)

    await adapter.predict_structured(
        Answer,
        _Bundle(),
        strategy=StructuredDecodingStrategy.NL_TO_FORMAT,
        topic="t",
    )

    assert base.completions == ["REASON t"]
    assert "because reasons" in base.structured[0]


@pytest.mark.asyncio
async def test_direct_strategy_makes_no_reasoning_call(cache_dir):
    base = _RecordingLLM()
    llm = DiskCachedStructuredLLM(
        LlamaIndexStructuredLLMAdapter(base), cache_dir=cache_dir
    )

    await llm.predict_structured(
        Answer, _Bundle(), strategy=StructuredDecodingStrategy.DIRECT, topic="t"
    )

    assert base.completions == []
    assert base.structured == ["DIRECT t"]


@pytest.mark.asyncio
async def test_strategy_is_part_of_the_cache_key(cache_dir):
    """A DIRECT answer must not be served to a NL_TO_FORMAT request.

    Both strategies decode the same bundle with the same args; before F-10 the
    key covered only prompt + args + schema, so whichever ran first answered
    for both.
    """
    base = _RecordingLLM()
    llm = DiskCachedStructuredLLM(
        LlamaIndexStructuredLLMAdapter(base), cache_dir=cache_dir
    )

    await llm.predict_structured(
        Answer, _Bundle(), strategy=StructuredDecodingStrategy.DIRECT, topic="t"
    )
    await llm.predict_structured(
        Answer, _Bundle(), strategy=StructuredDecodingStrategy.NL_TO_FORMAT, topic="t"
    )

    assert base.completions == ["REASON t"], "NL_TO_FORMAT was served the DIRECT entry"


@pytest.mark.asyncio
async def test_llm_kwargs_are_part_of_the_cache_key(cache_dir):
    base = _RecordingLLM()
    llm = DiskCachedStructuredLLM(
        LlamaIndexStructuredLLMAdapter(base), cache_dir=cache_dir
    )

    await llm.predict_structured(
        Answer,
        _Bundle(),
        strategy=StructuredDecodingStrategy.DIRECT,
        llm_kwargs={"temperature": 0.0},
        topic="t",
    )
    await llm.predict_structured(
        Answer,
        _Bundle(),
        strategy=StructuredDecodingStrategy.DIRECT,
        llm_kwargs={"temperature": 1.0},
        topic="t",
    )

    assert len(base.structured) == 2, "a different temperature reused the cached answer"


@pytest.mark.asyncio
async def test_repeated_identical_call_hits_the_cache(cache_dir):
    """The key changes above must not have broken caching itself."""
    base = _RecordingLLM()
    llm = DiskCachedStructuredLLM(
        LlamaIndexStructuredLLMAdapter(base), cache_dir=cache_dir
    )

    for _ in range(2):
        await llm.predict_structured(
            Answer,
            _Bundle(),
            strategy=StructuredDecodingStrategy.NL_TO_FORMAT,
            topic="t",
        )

    assert len(base.completions) == 1, "reasoning pass was not cached"
    assert len(base.structured) == 1, "format pass was not cached"


def test_ensure_structured_llm_does_not_rewrap_a_cached_llm(cache_dir):
    inner = DiskCachedStructuredLLM(
        LlamaIndexStructuredLLMAdapter(_RecordingLLM()), cache_dir=cache_dir
    )
    assert ensure_structured_llm(inner) is inner
