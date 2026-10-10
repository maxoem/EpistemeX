"""Disk caching layer for structured LLM predictions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from episteme_pipeline.llm.structured import StructuredLLM
from episteme_pipeline.runs.fingerprints import fingerprint_method, stable_fingerprint

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)

#: Bumped whenever a change to this module makes previously written entries
#: unsafe to reuse. It is part of the key, so a bump invalidates the whole cache
#: without anyone having to remember to delete the directory.
CACHE_VERSION = 2

#: Default cache location. The composition root passes
#: a directory derived from ``ExecutionConfig.runs_dir`` — see
#: ``default_cache_dir`` — so that a run configured to write elsewhere does not
#: quietly deposit its cache under the repo root.
DEFAULT_CACHE_DIR = Path(".pipeline_runs") / "llm_cache"


def default_cache_dir(runs_dir: str | Path | None = None) -> Path:
    """Cache directory for a given ``ExecutionConfig.runs_dir``."""
    if runs_dir is None:
        return DEFAULT_CACHE_DIR
    return Path(runs_dir) / "llm_cache"


class DiskCachedStructuredLLM(StructuredLLM):
    """Wraps a StructuredLLM with a local disk cache to prevent redundant API calls."""

    def __init__(
        self,
        base_llm: StructuredLLM,
        cache_dir: str | Path = DEFAULT_CACHE_DIR,
    ):
        self.base_llm = base_llm
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Attempt to fingerprint the underlying LlamaIndex LLM object if it exists
        self._llm_method = getattr(base_llm, "base_llm", base_llm)
        self._method_fp = fingerprint_method(self._llm_method) or "unknown_llm"

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic disk-cached structured LLM configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing cache version and base LLM fingerprint.
        """
        base_fp = (
            self.base_llm.fingerprint()
            if hasattr(self.base_llm, "fingerprint") and callable(self.base_llm.fingerprint)
            else fingerprint_method(self._llm_method)
        )
        return {
            "class": self.__class__.__name__,
            "cache_version": CACHE_VERSION,
            "base_llm": base_fp,
        }

    def _get_cache_path(
        self,
        cache_prefix: str,
        output_schema: str,
        prompt: Any,
        prompt_args: dict[str, Any],
        *,
        strategy: Any = None,
        llm_kwargs: dict[str, Any] | None = None,
    ) -> Path:
        """Key on everything that can change the response.

        ``strategy`` and ``llm_kwargs`` were previously absent from the key, so
        a NL_TO_FORMAT call and a DIRECT call with the same prompt collided, and
        re-running at a different temperature or token limit returned the
        earlier run's answer (F-10).
        """
        payload = {
            "cache_version": CACHE_VERSION,
            "method": self._method_fp,
            "strategy": str(getattr(strategy, "value", strategy)),
            "output_schema": output_schema,
            # If the prompt is a LlamaIndex PromptTemplate, get its string source
            "prompt": getattr(prompt, "template", str(prompt)),
            "args": {k: str(v) for k, v in prompt_args.items()},
            "llm_kwargs": {k: str(v) for k, v in sorted((llm_kwargs or {}).items())},
        }
        cache_key = stable_fingerprint(payload)
        return self.cache_dir / f"{cache_prefix}_{cache_key}.json"

    async def predict_text(
        self,
        prompt: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> str:
        cache_path = self._get_cache_path(
            "text", "str", prompt, prompt_args, strategy="text", llm_kwargs=llm_kwargs
        )

        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                logger.debug(f"LLM Cache HIT: {cache_path.name}")
                text_result = data["text"]
                from episteme_pipeline.events.context import get_event_emitter
                from episteme_pipeline.events.models import LLMGenerationCompleted

                rendered_prompt = (
                    prompt.format(llm=self.base_llm, **prompt_args)
                    if hasattr(prompt, "format")
                    else str(prompt).format(**prompt_args)
                )
                get_event_emitter().emit(
                    LLMGenerationCompleted(
                        model_name=self._method_fp,
                        prompt=str(rendered_prompt),
                        output_text=text_result,
                        output_json=None,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        duration_seconds=0.0,
                        operation="text_completion",
                        cached=True,
                    )
                )
                return text_result
            except Exception as e:
                logger.warning(f"Failed to read LLM cache at {cache_path}: {e}. Falling back to API.")

        logger.debug(f"LLM Cache MISS: {cache_path.name}")
        result = await self.base_llm.predict_text(
            prompt, llm_kwargs=llm_kwargs, **prompt_args
        )

        try:
            cache_path.write_text(json.dumps({"text": result}, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write LLM cache at {cache_path}: {e}")

        return result

    async def predict_structured(
        self,
        output_cls: type[ModelT],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> ModelT:
        from episteme_pipeline.config import StructuredDecodingStrategy

        if strategy == StructuredDecodingStrategy.NL_TO_FORMAT:
            # Run the two passes through `self`, so each is cached on its own
            # key and pass 2's key includes pass 1's output. execute_nl_to_format
            # calls back into predict_structured with DIRECT, which lands below.
            from episteme_pipeline.llm.structured import execute_nl_to_format
            return await execute_nl_to_format(
                self, output_cls, prompt_bundle, fallback_behavior, llm_kwargs, **prompt_args
            )

        prompt = getattr(prompt_bundle, "direct_template", prompt_bundle)
        cache_path = self._get_cache_path(
            "struct",
            output_cls.__name__,
            prompt,
            prompt_args,
            strategy=strategy,
            llm_kwargs=llm_kwargs,
        )

        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                logger.debug(f"LLM Cache HIT: {cache_path.name}")
                parsed = output_cls.model_validate(data)
                from episteme_pipeline.events.context import get_event_emitter
                from episteme_pipeline.events.models import LLMGenerationCompleted

                rendered_prompt = (
                    prompt.format(llm=self.base_llm, **prompt_args)
                    if hasattr(prompt, "format")
                    else str(prompt).format(**prompt_args)
                )
                get_event_emitter().emit(
                    LLMGenerationCompleted(
                        model_name=self._method_fp,
                        prompt=str(rendered_prompt),
                        output_text=json.dumps(data, ensure_ascii=False),
                        output_json=data,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        duration_seconds=0.0,
                        operation="structured_predict",
                        cached=True,
                    )
                )
                return parsed
            except Exception as e:
                logger.warning(f"Failed to read LLM cache at {cache_path}: {e}. Falling back to API.")

        logger.debug(f"LLM Cache MISS: {cache_path.name}")
        result = await self.base_llm.predict_structured(
            output_cls, prompt_bundle, strategy=strategy, fallback_behavior=fallback_behavior, llm_kwargs=llm_kwargs, **prompt_args
        )

        try:
            cache_path.write_text(result.model_dump_json(), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to write LLM cache at {cache_path}: {e}")

        return result

