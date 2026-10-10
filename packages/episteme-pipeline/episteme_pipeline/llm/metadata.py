"""Metadata and token usage extraction utilities for LLM responses.

This module provides dedicated extractors to parse token counts, latencies,
model names, and execution parameters from heterogeneous LLM responses
(LlamaIndex CompletionResponse, LiteLLM dictionaries, OpenAI-like objects).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class TokenUsage:
    """Token usage metrics for an LLM invocation.

    Parameters
    ----------
    prompt_tokens : int
        Number of input/prompt tokens.
    completion_tokens : int
        Number of output/completion tokens.
    total_tokens : int
        Total tokens consumed.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TokenUsageExtractorProtocol(Protocol):
    """Protocol for extracting token counts and metadata from LLM responses."""

    def extract_usage(self, response: Any, prompt_text: str | None = None) -> TokenUsage:
        """Extract token usage counts from a response object or fallback text.

        Parameters
        ----------
        response : Any
            The raw response or completion object from the LLM facade.
        prompt_text : str, optional
            The rendered prompt text, used for estimation if response usage is missing.

        Returns
        -------
        TokenUsage
            Parsed or estimated token usage.
        """
        ...


class LLMResponseMetadataExtractor:
    """Extracts token usage, model identifiers, and parameters from LLM responses.

    Adheres to the Single Responsibility Principle by decoupling response
    payload parsing from prediction and serialization logic.
    """

    @staticmethod
    def extract_model_name(llm_instance: Any, default: str = "unknown") -> str:
        """Extract the model name from an LLM instance.

        Parameters
        ----------
        llm_instance : Any
            The LLM facade or client instance.
        default : str, default="unknown"
            Fallback name if no model attribute is found.

        Returns
        -------
        str
            The resolved model name.
        """
        for attr in ("model_name", "model", "_model", "model_id"):
            val = getattr(llm_instance, attr, None)
            if isinstance(val, str) and val.strip():
                return val
        return default

    @staticmethod
    def extract_model_parameters(llm_instance: Any) -> dict[str, Any]:
        """Extract hyperparameters (temperature, max_tokens, etc.) from an LLM.

        Parameters
        ----------
        llm_instance : Any
            The LLM facade instance.

        Returns
        -------
        dict[str, Any]
            Dictionary of model hyperparameters.
        """
        params: dict[str, Any] = {}
        for param in ("temperature", "max_tokens", "top_p", "timeout"):
            val = getattr(llm_instance, param, None)
            if val is not None:
                params[param] = val
        return params

    @classmethod
    def extract_usage(
        cls,
        response: Any,
        prompt_text: str | None = None,
        output_text: str | None = None,
    ) -> TokenUsage:
        """Extract token counts from a response or fallback to heuristics.

        Parameters
        ----------
        response : Any
            The LLM response object (e.g. LlamaIndex CompletionResponse, LiteLLM/OpenAI object, dict).
        prompt_text : str, optional
            The prompt string, used for estimation fallback if provider usage is unavailable.
        output_text : str, optional
            The output string, used for estimation fallback if provider usage is unavailable.

        Returns
        -------
        TokenUsage
            Extracted or estimated token counts.
        """
        # 1. Direct dictionary
        if isinstance(response, dict):
            if "usage" in response and isinstance(response["usage"], dict):
                return cls._from_dict(response["usage"])
            if "prompt_tokens" in response or "completion_tokens" in response or "input_tokens" in response:
                return cls._from_dict(response)


        # 2. LlamaIndex CompletionResponse / ChatResponse additional_kwargs or raw
        additional_kwargs = getattr(response, "additional_kwargs", None)
        if isinstance(additional_kwargs, dict):
            usage = additional_kwargs.get("usage")
            if isinstance(usage, dict):
                return cls._from_dict(usage)
            if hasattr(usage, "prompt_tokens"):
                return cls._from_obj(usage)

        raw = getattr(response, "raw", None)
        if isinstance(raw, dict):
            usage = raw.get("usage")
            if isinstance(usage, dict):
                return cls._from_dict(usage)
        elif raw is not None:
            usage = getattr(raw, "usage", None)
            if usage is not None:
                if isinstance(usage, dict):
                    return cls._from_dict(usage)
                return cls._from_obj(usage)

        # 3. Direct response.usage attribute
        direct_usage = getattr(response, "usage", None)
        if direct_usage is not None:
            if isinstance(direct_usage, dict):
                return cls._from_dict(direct_usage)
            return cls._from_obj(direct_usage)

        # 4. Fallback: estimate via tiktoken or char-length heuristic
        return cls._estimate_usage(prompt_text, output_text)

    @staticmethod
    def _from_dict(d: dict[str, Any]) -> TokenUsage:
        prompt_tokens = int(d.get("prompt_tokens") or d.get("input_tokens") or 0)
        completion_tokens = int(d.get("completion_tokens") or d.get("output_tokens") or 0)
        total_tokens = int(d.get("total_tokens") or (prompt_tokens + completion_tokens))
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _from_obj(obj: Any) -> TokenUsage:
        prompt_tokens = int(getattr(obj, "prompt_tokens", 0) or getattr(obj, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(obj, "completion_tokens", 0) or getattr(obj, "output_tokens", 0) or 0)
        total_tokens = int(getattr(obj, "total_tokens", 0) or (prompt_tokens + completion_tokens))
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Estimate token count for a text string using tiktoken or heuristic.

        Parameters
        ----------
        text : str
            The input string.

        Returns
        -------
        int
            Estimated token count.
        """
        if not text:
            return 0
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            return max(1, len(text) // 4)

    @staticmethod
    def _estimate_usage(prompt_text: str | None, output_text: str | None) -> TokenUsage:
        """Estimate token counts if provider did not supply usage."""
        p_tokens = LLMResponseMetadataExtractor.estimate_tokens(prompt_text or "")
        c_tokens = LLMResponseMetadataExtractor.estimate_tokens(output_text or "")

        return TokenUsage(
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=p_tokens + c_tokens,
        )

