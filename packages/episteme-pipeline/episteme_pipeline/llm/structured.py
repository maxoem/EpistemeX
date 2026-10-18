"""Structured-output adapter layer for LLM-backed pipeline components.

This module owns the local contract above third-party LLM facades. It keeps
provider-specific structured prediction on the fast path, but adds a
deterministic fallback for wrappers such as ``assistant: {...}`` or fenced JSON
when the facade fails to parse them directly.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from episteme_pipeline.config import StructuredDecodingStrategy
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import LLMDurationMeasured, LLMGenerationCompleted
from episteme_pipeline.llm.metadata import LLMResponseMetadataExtractor

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class StructuredPredictionError(RuntimeError):
    """Raised when a structured prediction cannot be recovered."""


class StructuredLLM(Protocol):
    """Owned boundary for structured LLM prediction in the pipeline."""

    async def predict_structured(
        self,
        output_cls: type[ModelT],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> ModelT:
        """Predict a Pydantic model from a prompt bundle or string."""

    async def predict_text(
        self,
        prompt: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> str:
        """Predict raw text (used for reasoning passes)."""


# ----------------------------------------------------------------------
# Decoding Strategy Handlers (Strategy Pattern)
# ----------------------------------------------------------------------

class BaseOutputDecodingStrategyHandler(ABC):
    """Abstract Strategy interface for structured output decoding."""

    @abstractmethod
    async def decode(
        self,
        adapter: LlamaIndexStructuredLLMAdapter,
        output_cls: type[ModelT],
        prompt_bundle: Any,
        fallback_behavior: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> ModelT:
        """Execute output decoding for the target Pydantic model."""
        ...


def _as_prompt_template(prompt: Any) -> Any:
    """Wrap a bare template string in a ``PromptTemplate``.

    ``StructuredPromptBundle`` stores templates as plain strings, but
    ``BaseLLM.astructured_predict`` requires a ``BasePromptTemplate``. Coercing
    here keeps every phase free to pass its bundle straight through.
    """
    if isinstance(prompt, str):
        from llama_index.core import PromptTemplate

        return PromptTemplate(prompt)
    return prompt


class DirectDecodingStrategyHandler(BaseOutputDecodingStrategyHandler):
    """Direct provider-native constrained decoding (Single pass)."""

    async def decode(
        self,
        adapter: LlamaIndexStructuredLLMAdapter,
        output_cls: type[ModelT],
        prompt_bundle: Any,
        fallback_behavior: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> ModelT:
        prompt = _as_prompt_template(getattr(prompt_bundle, "direct_template", prompt_bundle))
        rendered_prompt = prompt.format(llm=adapter.base_llm, **prompt_args) if hasattr(prompt, "format") else str(prompt).format(**prompt_args)
        start_time = time.time()

        try:
            result = await adapter.base_llm.astructured_predict(
                output_cls,
                prompt,
                llm_kwargs=llm_kwargs,
                **prompt_args,
            )
            duration = time.time() - start_time
            model_name = LLMResponseMetadataExtractor.extract_model_name(adapter.base_llm)
            model_params = LLMResponseMetadataExtractor.extract_model_parameters(adapter.base_llm)
            out_text = result.model_dump_json() if hasattr(result, "model_dump_json") else str(result)
            out_json = result.model_dump() if hasattr(result, "model_dump") else None
            usage = LLMResponseMetadataExtractor.extract_usage(
                result, prompt_text=str(rendered_prompt), output_text=out_text
            )
            p_name = getattr(prompt_bundle, "name", None)
            p_version = getattr(prompt_bundle, "version", None)
            p_label = getattr(prompt_bundle, "label", None)
            adapter.event_emitter.emit(
                LLMDurationMeasured(
                    model_name=model_name,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    duration_seconds=duration,
                    operation="structured_predict",
                )
            )
            adapter.event_emitter.emit(
                LLMGenerationCompleted(
                    model_name=model_name,
                    prompt=str(rendered_prompt),
                    output_text=out_text,
                    output_json=out_json,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    duration_seconds=duration,
                    operation="structured_predict",
                    cached=False,
                    model_parameters=model_params,
                    prompt_name=p_name,
                    prompt_version=p_version,
                    prompt_label=p_label,
                )
            )
            return result

        except Exception as exc:
            recovered = adapter._recover_from_exception(output_cls, exc)
            if recovered is not None:
                return recovered

            if fallback_behavior == "raise":
                raise

            raw_text = await adapter._fallback_complete(
                prompt,
                llm_kwargs=llm_kwargs,
                **prompt_args,
            )
            return adapter._parse_sanitized_output(
                output_cls,
                raw_text,
                recovery_source="completion fallback",
                original_error=exc,
            )


class NlToFormatDecodingStrategyHandler(BaseOutputDecodingStrategyHandler):
    """2-Pass NL-to-Format strategy: Freeform reasoning pass -> Format extraction pass."""

    async def decode(
        self,
        adapter: LlamaIndexStructuredLLMAdapter,
        output_cls: type[ModelT],
        prompt_bundle: Any,
        fallback_behavior: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> ModelT:
        # The two-pass logic lives in ``execute_nl_to_format`` so that a
        # decorated LLM (the disk cache) can drive the same passes through its
        # own cached ``predict_text`` / ``predict_structured`` (F-10).
        return await execute_nl_to_format(
            adapter,
            output_cls,
            prompt_bundle,
            fallback_behavior,
            llm_kwargs,
            **prompt_args,
        )


class TriggerTokenDecodingStrategyHandler(BaseOutputDecodingStrategyHandler):
    """Local inference strategy: trigger token activates logit schema masking."""

    async def decode(
        self,
        adapter: LlamaIndexStructuredLLMAdapter,
        output_cls: type[ModelT],
        prompt_bundle: Any,
        fallback_behavior: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> ModelT:
        logger.info("TRIGGER_TOKEN strategy requested; executing constrained direct decoding on local model.")
        direct_handler = DirectDecodingStrategyHandler()
        return await direct_handler.decode(
            adapter,
            output_cls,
            prompt_bundle,
            fallback_behavior=fallback_behavior,
            llm_kwargs=llm_kwargs,
            **prompt_args,
        )


# Decoding Strategy Registry
DECODING_STRATEGY_HANDLERS: dict[str, BaseOutputDecodingStrategyHandler] = {
    "direct_constrained": DirectDecodingStrategyHandler(),
    "nl_to_format": NlToFormatDecodingStrategyHandler(),
    "trigger_token": TriggerTokenDecodingStrategyHandler(),
}


async def execute_nl_to_format[ModelT: BaseModel](
    llm: StructuredLLM,
    output_cls: type[ModelT],
    prompt_bundle: Any,
    fallback_behavior: Any,
    llm_kwargs: dict[str, Any] | None = None,
    **prompt_args: Any,
) -> ModelT:
    """Run the 2-pass NL-to-Format decode against any ``StructuredLLM``.

    Pass 1 asks for free-form reasoning; pass 2 asks the model to format that
    reasoning into ``output_cls`` using a constrained direct decode.

    ``llm`` is the *whole* structured-LLM stack, not necessarily the bare
    adapter. This used to be ``isinstance(llm, LlamaIndexStructuredLLMAdapter)``
    with a plain direct decode otherwise — and since ``ensure_structured_llm``
    wraps every adapter in ``DiskCachedStructuredLLM``, the isinstance check
    never held. NL_TO_FORMAT, the configured default for NER, global relations,
    ACC and ARC, therefore silently ran as DIRECT everywhere (F-10).

    Driving both passes through ``llm`` also means the cache decorator caches
    the reasoning pass and the format pass separately, and pass 2's cache key
    includes the pass-1 output via ``prompt_args["reasoning_text"]``.

    Recursion is bounded: pass 2 always requests ``DIRECT``, which never routes
    back here.
    """
    from episteme_pipeline.prompts.models import StructuredPromptBundle

    if isinstance(prompt_bundle, StructuredPromptBundle):
        reasoning_prompt = prompt_bundle.reasoning_template
        format_prompt = prompt_bundle.format_template
        direct_target: Any = prompt_bundle
    else:
        reasoning_prompt = getattr(prompt_bundle, "reasoning_template", None)
        format_prompt = getattr(prompt_bundle, "format_template", None)
        direct_target = getattr(prompt_bundle, "direct_template", prompt_bundle)

    async def _direct(target: Any) -> ModelT:
        return await llm.predict_structured(
            output_cls,
            target,
            strategy=StructuredDecodingStrategy.DIRECT,
            fallback_behavior=fallback_behavior,
            llm_kwargs=llm_kwargs,
            **prompt_args,
        )

    if reasoning_prompt is None or format_prompt is None:
        logger.debug(
            "Prompt bundle for %s carries no two-pass templates; decoding directly.",
            output_cls.__name__,
        )
        return await _direct(direct_target)

    try:
        reasoning_text = await llm.predict_text(
            reasoning_prompt, llm_kwargs, **prompt_args
        )
    except Exception as exc:
        logger.warning(
            "Reasoning pass for %s failed (%s: %s); falling back to DIRECT.",
            output_cls.__name__,
            type(exc).__name__,
            exc,
        )
        return await _direct(direct_target)

    prompt_args["reasoning_text"] = reasoning_text
    format_target = (
        prompt_bundle.model_copy(update={"direct_template": format_prompt})
        if isinstance(prompt_bundle, StructuredPromptBundle)
        else format_prompt
    )
    return await _direct(format_target)


@dataclass(frozen=True)
class SanitizedStructuredOutput:
    """Deterministically normalized JSON payload."""

    value: Any
    cleaned_text: str
    actions: tuple[str, ...]


class LlamaIndexStructuredLLMAdapter:
    """Adapter around LlamaIndex-style LLM facades."""

    def __init__(self, base_llm: Any) -> None:
        self.base_llm = base_llm

    @property
    def event_emitter(self) -> EventEmitter:
        """Get active event emitter from contextvar."""
        return get_event_emitter()

    async def predict_text(
        self,
        prompt: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> str:
        """Predict raw text."""
        start_time = time.time()
        rendered_prompt = prompt.format(llm=self.base_llm, **prompt_args) if hasattr(prompt, "format") else str(prompt).format(**prompt_args)
        response = await self.base_llm.acomplete(
            rendered_prompt,
            **(llm_kwargs or {}),
        )
        duration = time.time() - start_time
        model_name = LLMResponseMetadataExtractor.extract_model_name(self.base_llm)
        model_params = LLMResponseMetadataExtractor.extract_model_parameters(self.base_llm)
        out_text = getattr(response, "text", str(response))
        usage = LLMResponseMetadataExtractor.extract_usage(
            response, prompt_text=str(rendered_prompt), output_text=out_text
        )
        self.event_emitter.emit(
            LLMDurationMeasured(
                model_name=model_name,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                duration_seconds=duration,
                operation="text_completion",
            )
        )
        self.event_emitter.emit(
            LLMGenerationCompleted(
                model_name=model_name,
                prompt=str(rendered_prompt),
                output_text=out_text,
                output_json=None,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                duration_seconds=duration,
                operation="text_completion",
                cached=False,
                model_parameters=model_params,
            )
        )
        return out_text

    async def predict_structured(
        self,
        output_cls: type[ModelT],
        prompt_bundle: Any,
        strategy: Any = "direct_constrained",
        fallback_behavior: Any = "retry_then_omit",
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> ModelT:
        """Predict a Pydantic model with strategy routing and fallback recovery."""
        strategy_key = str(getattr(strategy, "value", strategy))
        handler = DECODING_STRATEGY_HANDLERS.get(
            strategy_key, DECODING_STRATEGY_HANDLERS["direct_constrained"]
        )
        return await handler.decode(
            self, output_cls, prompt_bundle, fallback_behavior, llm_kwargs, **prompt_args
        )

    async def _fallback_complete(
        self,
        prompt: Any,
        llm_kwargs: dict[str, Any] | None = None,
        **prompt_args: Any,
    ) -> str:
        """Run a raw completion fallback after strict structured parsing fails."""
        start_time = time.time()
        rendered_prompt = prompt.format(llm=self.base_llm, **prompt_args) if hasattr(prompt, "format") else str(prompt).format(**prompt_args)
        response = await self.base_llm.acomplete(
            rendered_prompt,
            **(llm_kwargs or {}),
        )
        duration = time.time() - start_time
        model_name = LLMResponseMetadataExtractor.extract_model_name(self.base_llm)
        model_params = LLMResponseMetadataExtractor.extract_model_parameters(self.base_llm)
        out_text = getattr(response, "text", str(response))
        usage = LLMResponseMetadataExtractor.extract_usage(
            response, prompt_text=str(rendered_prompt), output_text=out_text
        )
        self.event_emitter.emit(
            LLMDurationMeasured(
                model_name=model_name,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                duration_seconds=duration,
                operation="fallback_complete",
            )
        )
        self.event_emitter.emit(
            LLMGenerationCompleted(
                model_name=model_name,
                prompt=str(rendered_prompt),
                output_text=out_text,
                output_json=None,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                duration_seconds=duration,
                operation="fallback_complete",
                cached=False,
                model_parameters=model_params,
            )
        )
        return out_text


    def _recover_from_exception(
        self,
        output_cls: type[ModelT],
        exc: Exception,
    ) -> ModelT | None:
        """Attempt deterministic recovery from exception payloads."""
        for candidate in _exception_text_candidates(exc):
            try:
                return self._parse_sanitized_output(
                    output_cls,
                    candidate,
                    recovery_source="exception payload",
                    original_error=exc,
                )
            except StructuredPredictionError:
                continue
        return None

    def _parse_sanitized_output(
        self,
        output_cls: type[ModelT],
        raw_text: str,
        *,
        recovery_source: str,
        original_error: Exception,
    ) -> ModelT:
        """Sanitize and validate a raw text payload."""
        try:
            sanitized = sanitize_structured_output(raw_text)
            parsed = output_cls.model_validate(sanitized.value)
        except Exception as parse_exc:
            raise StructuredPredictionError(
                f"Structured prediction recovery failed via {recovery_source}: "
                f"{type(parse_exc).__name__}: {parse_exc}"
            ) from original_error

        logger.warning(
            "Recovered structured prediction for %s via %s (%s; actions=%s).",
            output_cls.__name__,
            recovery_source,
            type(original_error).__name__,
            ",".join(sanitized.actions) or "none",
        )
        return parsed


def ensure_structured_llm(llm: Any | None, use_cache: bool = True) -> StructuredLLM | None:
    """Return an owned structured-output adapter for an LLM facade."""
    if llm is None:
        return None

    from episteme_pipeline.llm.cache import DiskCachedStructuredLLM
    if isinstance(llm, DiskCachedStructuredLLM):
        return llm
        
    if hasattr(llm, "predict_structured") and hasattr(llm, "predict_text"):
        adapter = llm
    else:
        adapter = LlamaIndexStructuredLLMAdapter(llm)
        
    if use_cache:
        return DiskCachedStructuredLLM(adapter)
    return adapter


def sanitize_structured_output(text: str) -> SanitizedStructuredOutput:
    """Extract the first top-level JSON value from an LLM response.

    Parameters
    ----------
    text
        Raw LLM response text.

    Returns
    -------
    SanitizedStructuredOutput
        Parsed JSON plus deterministic normalization metadata.
    """
    stripped = text.strip()
    start_indexes = [idx for idx in (stripped.find("{"), stripped.find("[")) if idx >= 0]
    if not start_indexes:
        raise ValueError("No JSON object or array found in LLM response")

    start = min(start_indexes)
    decoder = json.JSONDecoder()
    value, end = decoder.raw_decode(stripped[start:])

    actions: list[str] = []
    prefix = stripped[:start]
    suffix = stripped[start + end :]
    if prefix:
        actions.append("trimmed_prefix")
        if prefix.strip().lower().startswith("assistant:"):
            actions.append("stripped_role_prefix")
    if suffix.strip():
        actions.append("trimmed_suffix")

    return SanitizedStructuredOutput(
        value=value,
        cleaned_text=json.dumps(value, ensure_ascii=False),
        actions=tuple(actions),
    )


def _exception_text_candidates(exc: Exception) -> list[str]:
    """Return string payload candidates that might contain raw model output."""
    candidates: list[str] = []

    for arg in exc.args:
        if isinstance(arg, str) and arg.strip():
            candidates.append(arg)

    for attr_name in ("raw_response", "text", "response", "completion", "raw"):
        value = getattr(exc, attr_name, None)
        if isinstance(value, str) and value.strip():
            candidates.append(value)
            continue
        nested_text = getattr(value, "text", None)
        if isinstance(nested_text, str) and nested_text.strip():
            candidates.append(nested_text)

    return candidates
