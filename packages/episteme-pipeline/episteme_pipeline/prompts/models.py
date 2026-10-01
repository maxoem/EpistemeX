"""Prompt data models and bundle schemas.

This module defines the ``StructuredPromptBundle`` schema used for configuring
prompt templates across extraction and classification phases.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class StructuredPromptBundle(BaseModel):
    """Container for multi-pass prompt templates and prompt management metadata.

    Attributes
    ----------
    direct_template : str
        Single-pass or direct constrained extraction prompt template.
    reasoning_template : str or None, optional
        Free-form reasoning prompt template (NL-to-Format pass 1).
    format_template : str or None, optional
        Format conversion prompt template (NL-to-Format pass 2).
    gleaning_template : str or None, optional
        Secondary extraction pass template for missed mentions/triples.
    decision_template : str or None, optional
        Decision question or rubric template for System 1 decision engine.
    decision_criteria : dict or list or None, optional
        Rubric criteria definitions or categorical option explanations.
    name : str or None, optional
        Canonical prompt name in prompt store (e.g. 'ner_extraction').
    version : int or str or None, optional
        Prompt version number or semver string from prompt provider.
    label : str or None, optional
        Deployment tag or label (e.g. 'production', 'staging').
    provider : str, default "default"
        Source provider identifier (e.g. 'default', 'langfuse', 'file').
    metadata : dict, default dict
        Provider-specific metadata and model parameters.
    """

    direct_template: str
    reasoning_template: str | None = None
    format_template: str | None = None
    gleaning_template: str | None = None
    decision_template: str | None = None
    decision_criteria: dict[str, str] | list[str] | None = None
    name: str | None = None
    version: int | str | None = None
    label: str | None = None
    provider: str = "default"
    metadata: dict[str, Any] = Field(default_factory=dict)
