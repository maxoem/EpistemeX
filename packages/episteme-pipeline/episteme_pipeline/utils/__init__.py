"""Shared graph formatting utilities for subgraph envelopes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from episteme_pipeline.prompts.input_formatters import (
    InputFormatStrategy,
    format_subgraph_envelope,
)

if TYPE_CHECKING:
    from episteme_pipeline.contracts.domain import SubGraph


def format_envelope(
    env_a: SubGraph, 
    env_b: SubGraph, 
    include_description: bool = True,
    strategy: InputFormatStrategy = InputFormatStrategy.JSON,
) -> str:
    """Render two subgraph envelopes as a structured text block for the LLM prompt.

    Parameters
    ----------
    env_a, env_b:
        The two subgraph envelopes to merge and format.
    include_description:
        Whether to append descriptions after each node name.
    strategy:
        Serialization strategy to use (JSON, YAML, TEXT). Defaults to JSON.
    """
    return format_subgraph_envelope(env_a, env_b, strategy, include_description)
