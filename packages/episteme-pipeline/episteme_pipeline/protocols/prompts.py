"""Prompt provider protocol definitions.

This module defines the abstract interface for resolving, managing, and injecting
prompt bundles into pipeline configurations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from episteme_pipeline.prompts.models import StructuredPromptBundle

if TYPE_CHECKING:
    from episteme_pipeline.config import PipelineConfig


@runtime_checkable
class PromptProvider(Protocol):
    """Protocol for fetching and populating prompt bundles and templates.

    Implementations can fetch prompt definitions from local default constants,
    remote management systems (such as Langfuse), file stores, or MCP prompt servers.
    """

    def get_bundle(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> StructuredPromptBundle:
        """Retrieve a structured prompt bundle by name and version/label.

        Parameters
        ----------
        prompt_name : str
            Canonical identifier of the prompt bundle (e.g., 'ner', 'global_relation').
        label_or_version : str or int, default "production"
            Version number or target deployment label (e.g., 'production', 'staging').

        Returns
        -------
        StructuredPromptBundle
            Resolved structured prompt bundle containing direct, reasoning, format,
            or gleaning templates, along with version metadata.
        """
        ...

    def get_template(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> str:
        """Retrieve the primary direct template string for a prompt.

        Parameters
        ----------
        prompt_name : str
            Canonical identifier of the prompt.
        label_or_version : str or int, default "production"
            Version number or target deployment label.

        Returns
        -------
        str
            The raw direct prompt template string.
        """
        ...

    def populate_config(
        self, config: PipelineConfig, label_or_version: str | int = "production"
    ) -> PipelineConfig:
        """Populate all phase prompts on a PipelineConfig instance.

        Parameters
        ----------
        config : PipelineConfig
            The configuration instance to enrich with resolved prompts.
        label_or_version : str or int, default "production"
            Target deployment label or version identifier.

        Returns
        -------
        PipelineConfig
            The modified configuration instance with resolved prompt bundles.
        """
        ...
