import tempfile

import pytest
from pydantic import BaseModel

from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
from episteme_pipeline.llm.structured import StructuredLLM


class _MockModel(BaseModel):
    value: str


class _MockStructuredLLM(StructuredLLM):
    def __init__(self):
        self.calls = 0

    async def predict_structured(self, output_cls, prompt, llm_kwargs=None, **prompt_args):
        self.calls += 1
        return output_cls(value=f"response-{self.calls}")


@pytest.mark.asyncio
async def test_disk_cached_structured_llm_cache_hits():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_llm = _MockStructuredLLM()
        cached_llm = DiskCachedStructuredLLM(base_llm, cache_dir=tmpdir)
        
        # First call (miss)
        res1 = await cached_llm.predict_structured(
            _MockModel, "test prompt with {val}", val="foo"
        )
        assert res1.value == "response-1"
        assert base_llm.calls == 1
        
        # Second call with same args (hit)
        res2 = await cached_llm.predict_structured(
            _MockModel, "test prompt with {val}", val="foo"
        )
        assert res2.value == "response-1"
        assert base_llm.calls == 1
        
        # Third call with different args (miss)
        res3 = await cached_llm.predict_structured(
            _MockModel, "test prompt with {val}", val="bar"
        )
        assert res3.value == "response-2"
        assert base_llm.calls == 2
