"""Prompt provider implementations.

This module provides concrete implementations of the ``PromptProvider`` protocol,
including local defaults, Langfuse prompt management integration, and file-based loaders.
"""

from __future__ import annotations

import json
import logging
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

from episteme_pipeline.prompts.models import StructuredPromptBundle

if TYPE_CHECKING:
    from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.prompts.default_prompts import (
    ACC_DIRECT_PROMPT,
    ACC_FORMAT_PROMPT,
    ACC_REASONING_PROMPT,
    ADU_SEGMENTATION_PROMPT,
    ARC_DIRECT_PROMPT,
    ARC_FORMAT_PROMPT,
    ARC_REASONING_PROMPT,
    DECISION_ACC_CRITERIA,
    DECISION_ACC_QUESTION,
    DECISION_ARC_CRITERIA,
    DECISION_ARC_QUESTION,
    DECISION_BORDERLINE_MERGE_CRITERIA,
    DECISION_BORDERLINE_MERGE_QUESTION,
    DECISION_BOUNDARY_CRITERIA,
    DECISION_BOUNDARY_QUESTION,
    DECISION_CANONICAL_ELECTION_QUESTION,
    DECISION_EPISTEMIC_RELEVANCE_CRITERIA,
    DECISION_EPISTEMIC_RELEVANCE_QUESTION,
    DECISION_THEORY_FUSION_CRITERIA,
    DECISION_THEORY_FUSION_QUESTION,
    ENTITY_LINKING_PROMPT,
    ENTITY_SYNTHESIS_PROMPT,
    GLOBAL_RELATION_DIRECT_PROMPT,
    GLOBAL_RELATION_FORMAT_PROMPT,
    GLOBAL_RELATION_REASONING_PROMPT,
    NER_DIRECT_PROMPT,
    NER_FORMAT_PROMPT,
    NER_GLEANING_PROMPT,
    NER_REASONING_PROMPT,
    PAIR_GATING_DECISION_PROMPT,
)
from episteme_pipeline.protocols.prompts import PromptProvider

logger = logging.getLogger(__name__)


def _mustache_to_python_format(template: str) -> str:
    """Convert Mustache-style ``{{var}}`` variables to Python format ``{var}``.

    Preserves escaped JSON braces ``{{`` and ``}}`` when they do not represent
    valid variable names.

    Parameters
    ----------
    template : str
        Input template containing potential Mustache variable tags.

    Returns
    -------
    str
        Converted template string compatible with Python ``str.format``.
    """
    # Matches {{ identifier }} or {{identifier}}
    pattern = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
    return pattern.sub(r"{\1}", template)


class DefaultPromptProvider:
    """Default prompt provider serving built-in prompt templates.

    This provider serves the standard baseline prompt templates defined in
    ``episteme_pipeline.prompts.default_prompts`` without external network dependencies.
    """

    def __init__(self) -> None:
        self._bundles: dict[str, StructuredPromptBundle] = {
            "ner_extraction": StructuredPromptBundle(
                direct_template=NER_DIRECT_PROMPT,
                reasoning_template=NER_REASONING_PROMPT,
                format_template=NER_FORMAT_PROMPT,
                gleaning_template=NER_GLEANING_PROMPT,
                name="ner_extraction",
                provider="default",
            ),
            "entity_linking": StructuredPromptBundle(
                direct_template=ENTITY_LINKING_PROMPT,
                name="entity_linking",
                provider="default",
            ),
            "global_relation": StructuredPromptBundle(
                direct_template=GLOBAL_RELATION_DIRECT_PROMPT,
                reasoning_template=GLOBAL_RELATION_REASONING_PROMPT,
                format_template=GLOBAL_RELATION_FORMAT_PROMPT,
                decision_template=PAIR_GATING_DECISION_PROMPT,
                name="global_relation",
                provider="default",
            ),
            "decision_pair_gating": StructuredPromptBundle(
                direct_template=PAIR_GATING_DECISION_PROMPT,
                decision_template=PAIR_GATING_DECISION_PROMPT,
                name="decision_pair_gating",
                provider="default",
            ),
            "entity_synthesis": StructuredPromptBundle(
                direct_template=ENTITY_SYNTHESIS_PROMPT,
                name="entity_synthesis",
                provider="default",
            ),
            "adu_segmentation": StructuredPromptBundle(
                direct_template=ADU_SEGMENTATION_PROMPT,
                name="adu_segmentation",
                provider="default",
            ),
            "acc_classification": StructuredPromptBundle(
                direct_template=ACC_DIRECT_PROMPT,
                reasoning_template=ACC_REASONING_PROMPT,
                format_template=ACC_FORMAT_PROMPT,
                decision_template=DECISION_ACC_QUESTION,
                decision_criteria=DECISION_ACC_CRITERIA,
                name="acc_classification",
                provider="default",
            ),
            "arc_classification": StructuredPromptBundle(
                direct_template=ARC_DIRECT_PROMPT,
                reasoning_template=ARC_REASONING_PROMPT,
                format_template=ARC_FORMAT_PROMPT,
                decision_template=DECISION_ARC_QUESTION,
                decision_criteria=DECISION_ARC_CRITERIA,
                name="arc_classification",
                provider="default",
            ),
            "decision_epistemic_relevance": StructuredPromptBundle(
                direct_template=DECISION_EPISTEMIC_RELEVANCE_QUESTION,
                decision_criteria=DECISION_EPISTEMIC_RELEVANCE_CRITERIA,
                name="decision_epistemic_relevance",
                provider="default",
            ),
            "decision_boundary": StructuredPromptBundle(
                direct_template=DECISION_BOUNDARY_QUESTION,
                decision_criteria=DECISION_BOUNDARY_CRITERIA,
                name="decision_boundary",
                provider="default",
            ),
            "decision_borderline_merge": StructuredPromptBundle(
                direct_template="Name: {name}\nType: {type}\nEnvelope: {envelope}\n1-Hop Relational Neighborhood: {relations}",
                decision_template=DECISION_BORDERLINE_MERGE_QUESTION,
                decision_criteria=DECISION_BORDERLINE_MERGE_CRITERIA,
                name="decision_borderline_merge",
                provider="default",
            ),
            "decision_canonical_election": StructuredPromptBundle(
                direct_template="Name: {name}. Context: {context}",
                decision_template=DECISION_CANONICAL_ELECTION_QUESTION,
                name="decision_canonical_election",
                provider="default",
            ),
            "decision_theory_fusion": StructuredPromptBundle(
                direct_template="Cluster Size: {cluster_node_count}\nMembers: {cluster_members}",
                decision_template=DECISION_THEORY_FUSION_QUESTION,
                decision_criteria=DECISION_THEORY_FUSION_CRITERIA,
                name="decision_theory_fusion",
                provider="default",
            ),
        }
        # Add common aliases
        self._aliases = {
            "ner": "ner_extraction",
            "linking": "entity_linking",
            "global_relations": "global_relation",
            "pair_gating": "decision_pair_gating",
            "decision_pair_gating": "decision_pair_gating",
            "pair_gating_decision": "decision_pair_gating",
            "synthesis": "entity_synthesis",
            "maturation": "entity_synthesis",
            "adu": "adu_segmentation",
            "acc": "acc_classification",
            "arc": "arc_classification",
            "decision_acc": "acc_classification",
            "acc_decision": "acc_classification",
            "decision_arc": "arc_classification",
            "arc_decision": "arc_classification",
            "decision_relevance": "decision_epistemic_relevance",
            "epistemic_relevance": "decision_epistemic_relevance",
            "boundary": "decision_boundary",
            "borderline_merge": "decision_borderline_merge",
            "decision_borderline_merge": "decision_borderline_merge",
            "canonical_election": "decision_canonical_election",
            "decision_canonical_election": "decision_canonical_election",
            "theory_fusion": "decision_theory_fusion",
            "decision_theory_fusion": "decision_theory_fusion",
        }

    def _normalize_name(self, prompt_name: str) -> str:
        """Resolve canonical prompt name from aliases."""
        cleaned = prompt_name.strip().lower()
        return self._aliases.get(cleaned, cleaned)

    def get_bundle(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> StructuredPromptBundle:
        """Retrieve default structured prompt bundle.

        Parameters
        ----------
        prompt_name : str
            Canonical prompt name or registered alias.
        label_or_version : str or int, default "production"
            Ignored for default provider.

        Returns
        -------
        StructuredPromptBundle
            Default structured prompt bundle.

        Raises
        ------
        KeyError
            If prompt_name is unrecognized.
        """
        canonical = self._normalize_name(prompt_name)
        if canonical not in self._bundles:
            raise KeyError(f"Unknown prompt name {prompt_name!r}. Available: {sorted(self._bundles.keys())}")
        bundle = self._bundles[canonical]
        if isinstance(label_or_version, str) and label_or_version != "production":
            return bundle.model_copy(update={"label": label_or_version})
        return bundle.model_copy()

    def get_template(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> str:
        """Retrieve direct prompt template string.

        Parameters
        ----------
        prompt_name : str
            Canonical prompt name or registered alias.
        label_or_version : str or int, default "production"
            Ignored for default provider.

        Returns
        -------
        str
            Direct prompt template string.
        """
        bundle = self.get_bundle(prompt_name, label_or_version)
        return bundle.direct_template

    def populate_config(
        self, config: PipelineConfig, label_or_version: str | int = "production"
    ) -> PipelineConfig:
        """Populate all phase prompts on a PipelineConfig.

        Parameters
        ----------
        config : PipelineConfig
            Target configuration instance.
        label_or_version : str or int, default "production"
            Target deployment label or version identifier.

        Returns
        -------
        PipelineConfig
            Populated configuration instance.
        """
        config.phase2.ner_prompts = self.get_bundle("ner_extraction", label_or_version)
        config.phase2.entity_linking_prompts = self.get_bundle("entity_linking", label_or_version)
        config.phase2.entity_linking_prompt_template = config.phase2.entity_linking_prompts.direct_template

        config.phase3.global_relation_prompts = self.get_bundle("global_relation", label_or_version)

        config.phase4_maturation.entity_synthesis_prompts = self.get_bundle("entity_synthesis", label_or_version)

        config.phase4.adu_segmentation_prompts = self.get_bundle("adu_segmentation", label_or_version)
        config.phase4.adu_segmentation_prompt_template = config.phase4.adu_segmentation_prompts.direct_template
        config.phase4.acc_prompts = self.get_bundle("acc_classification", label_or_version)
        config.phase4.arc_prompts = self.get_bundle("arc_classification", label_or_version)

        config.phase3b.verification.borderline_merge_prompts = self.get_bundle("decision_borderline_merge", label_or_version)
        config.phase3b.verification.canonical_election_prompts = self.get_bundle("decision_canonical_election", label_or_version)
        config.phase5.gating.prompt_bundle = self.get_bundle("decision_theory_fusion", label_or_version)

        return config


class LangfusePromptProvider:
    """Prompt provider backed by Langfuse Prompt Management.

    Fetches managed prompts from Langfuse by name and label/version. If prompts
    do not exist in Langfuse, can automatically upload and version default prompt
    bundles. If Langfuse is unreachable or unconfigured, falls back to a delegate provider.

    Parameters
    ----------
    client : Any, optional
        Langfuse client instance (e.g., ``langfuse.Langfuse`` or ``langfuse.get_client()``).
        If None, attempts to resolve the active Langfuse client.
    fallback : PromptProvider, optional
        Fallback prompt provider used on fetch errors or missing prompts.
        Defaults to ``DefaultPromptProvider``.
    convert_mustache : bool, default True
        Whether to convert Mustache ``{{var}}`` variables into Python ``{var}`` format.
    auto_create_missing : bool, default True
        Whether to automatically create default prompt bundles in Langfuse if they
        do not yet exist.
    """

    def __init__(
        self,
        client: Any = None,
        fallback: PromptProvider | None = None,
        convert_mustache: bool = True,
        auto_create_missing: bool = True,
    ) -> None:
        self.fallback: PromptProvider = fallback or DefaultPromptProvider()
        self.convert_mustache = convert_mustache
        self.auto_create_missing = auto_create_missing
        self._client = client

    @property
    def client(self) -> Any:
        """Lazy-resolve active Langfuse client."""
        if self._client is None:
            try:
                from langfuse import get_client
                self._client = get_client()
            except Exception as exc:
                logger.debug("Could not resolve default Langfuse client: %s", exc)
                self._client = None
        return self._client

    def _fetch_langfuse_prompt(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> Any | None:
        """Fetch raw prompt object from Langfuse client."""
        client = self.client
        if client is None:
            warnings.warn(
                f"Langfuse client is not initialized or unreachable for prompt {prompt_name!r}; "
                f"falling back to default provider.",
                UserWarning,
                stacklevel=2,
            )
            return None

        kwargs: dict[str, Any] = {"name": prompt_name}
        if isinstance(label_or_version, int):
            kwargs["version"] = label_or_version
        else:
            kwargs["label"] = str(label_or_version)

        try:
            if hasattr(client, "get_prompt"):
                return client.get_prompt(**kwargs)
        except Exception as exc:
            msg = (
                f"Failed to fetch prompt {prompt_name!r} (label/version={label_or_version!r}) "
                f"from Langfuse: {exc}; falling back to default provider."
            )
            logger.warning(msg)
            warnings.warn(msg, UserWarning, stacklevel=2)
        return None

    def create_prompt(
        self,
        name: str,
        template: str,
        labels: list[str] | None = None,
        tags: list[str] | None = None,
        config: dict[str, Any] | None = None,
        commit_message: str | None = None,
    ) -> Any:
        """Create or version a prompt template in Langfuse.

        Parameters
        ----------
        name : str
            Unique identifier of the prompt in Langfuse.
        template : str
            The prompt template string.
        labels : list of str, optional
            Deployment labels (e.g., ['production']). Defaults to ['production'].
        tags : list of str, optional
            Categorization tags. Defaults to ['episteme', 'default'].
        config : dict, optional
            Hyperparameters or model configuration metadata to attach.
        commit_message : str, optional
            Commit log message for prompt version tracking.

        Returns
        -------
        Any
            The created Langfuse prompt client instance, or None if Langfuse is unreachable.
        """
        client = self.client
        if client is None or not hasattr(client, "create_prompt"):
            warnings.warn(
                f"Langfuse client is not initialized; cannot create prompt {name!r}.",
                UserWarning,
                stacklevel=2,
            )
            return None

        try:
            return client.create_prompt(
                name=name,
                prompt=template,
                labels=labels or ["production"],
                tags=tags or ["episteme", "default"],
                type="text",
                config=config,
                commit_message=commit_message or f"Registered prompt {name} from Episteme",
            )
        except Exception as exc:
            msg = f"Failed to create prompt {name!r} in Langfuse: {exc}"
            logger.warning(msg)
            warnings.warn(msg, UserWarning, stacklevel=2)
            return None

    def create_bundle(
        self,
        name: str,
        bundle: StructuredPromptBundle,
        label: str = "production",
        tags: list[str] | None = None,
        commit_message: str | None = None,
    ) -> StructuredPromptBundle:
        """Create and version all templates in a StructuredPromptBundle in Langfuse.

        Parameters
        ----------
        name : str
            Base prompt name.
        bundle : StructuredPromptBundle
            Bundle containing direct, reasoning, format, and gleaning templates.
        label : str, default "production"
            Deployment label to assign to the newly created prompts.
        tags : list of str, optional
            Tags to attach in Langfuse.
        commit_message : str, optional
            Commit message for the Langfuse version history.

        Returns
        -------
        StructuredPromptBundle
            Enriched prompt bundle carrying Langfuse version metadata.
        """
        labels = [label]
        tags = tags or ["episteme", "default"]

        direct_obj = self.create_prompt(
            name=name,
            template=bundle.direct_template,
            labels=labels,
            tags=tags,
            config=bundle.metadata,
            commit_message=commit_message or f"Direct prompt for {name}",
        )

        if bundle.reasoning_template:
            self.create_prompt(
                name=f"{name}_reasoning",
                template=bundle.reasoning_template,
                labels=labels,
                tags=tags,
                commit_message=commit_message or f"Reasoning prompt for {name}",
            )

        if bundle.format_template:
            self.create_prompt(
                name=f"{name}_format",
                template=bundle.format_template,
                labels=labels,
                tags=tags,
                commit_message=commit_message or f"Format prompt for {name}",
            )

        if bundle.gleaning_template:
            self.create_prompt(
                name=f"{name}_gleaning",
                template=bundle.gleaning_template,
                labels=labels,
                tags=tags,
                commit_message=commit_message or f"Gleaning prompt for {name}",
            )

        if bundle.decision_template:
            self.create_prompt(
                name=f"{name}_decision",
                template=bundle.decision_template,
                labels=labels,
                tags=tags,
                commit_message=commit_message or f"Decision prompt for {name}",
            )

        version = getattr(direct_obj, "version", bundle.version)
        return bundle.model_copy(
            update={
                "name": name,
                "version": version,
                "label": label,
                "provider": "langfuse" if direct_obj is not None else bundle.provider,
            }
        )

    def sync_defaults_to_langfuse(
        self,
        label: str = "production",
        overwrite: bool = False,
        tags: list[str] | None = None,
    ) -> dict[str, StructuredPromptBundle]:
        """Sync all default structured prompt bundles into Langfuse.

        Iterates over all standard default prompt bundles (NER, entity linking,
        global relations, entity synthesis, ADU segmentation, ACC, ARC). If a prompt
        does not exist in Langfuse (or if overwrite=True), uploads and versions it.

        Parameters
        ----------
        label : str, default "production"
            Target deployment label in Langfuse.
        overwrite : bool, default False
            Whether to force creating a new version even if the prompt already exists.
        tags : list of str, optional
            Tags to associate with the prompts in Langfuse.

        Returns
        -------
        dict of str -> StructuredPromptBundle
            Dictionary of synced prompt bundles keyed by canonical prompt name.
        """
        synced: dict[str, StructuredPromptBundle] = {}
        client = self.client

        default_names = [
            "ner_extraction",
            "entity_linking",
            "global_relation",
            "entity_synthesis",
            "adu_segmentation",
            "acc_classification",
            "arc_classification",
            "decision_epistemic_relevance",
            "decision_boundary",
            "decision_pair_gating",
        ]

        if client is None or not hasattr(client, "create_prompt"):
            warnings.warn(
                "Langfuse client is not initialized; cannot sync default prompts to Langfuse.",
                UserWarning,
                stacklevel=2,
            )
            return {
                name: self.fallback.get_bundle(name, label)
                for name in default_names
            }

        for name in default_names:
            default_bundle = self.fallback.get_bundle(name, label)
            if not overwrite:
                existing = None
                try:
                    if hasattr(client, "get_prompt"):
                        existing = client.get_prompt(name=name, label=label)
                except Exception:
                    existing = None

                if existing is not None:
                    synced[name] = self.get_bundle(name, label)
                    continue

            logger.info("Uploading default prompt bundle %r to Langfuse (label=%r)...", name, label)
            synced[name] = self.create_bundle(
                name=name,
                bundle=default_bundle,
                label=label,
                tags=tags,
                commit_message=f"Initial default bundle for {name} from Episteme baseline",
            )

        return synced

    def _extract_template_text(self, prompt_obj: Any) -> str | None:
        """Extract plain string template from a Langfuse prompt object."""
        if prompt_obj is None:
            return None

        text: str | None = None
        if hasattr(prompt_obj, "prompt"):
            prompt_val = prompt_obj.prompt
            if isinstance(prompt_val, str):
                text = prompt_val
            elif isinstance(prompt_val, list):
                # Chat prompt: combine content of messages
                parts = []
                for msg in prompt_val:
                    if isinstance(msg, dict) and "content" in msg:
                        parts.append(str(msg["content"]))
                    elif hasattr(msg, "content"):
                        parts.append(str(msg.content))
                text = "\n\n".join(parts) if parts else str(prompt_val)
            else:
                text = str(prompt_val)
        elif hasattr(prompt_obj, "compile"):
            # TextPromptClient
            try:
                text = prompt_obj.get_langchain_prompt() if hasattr(prompt_obj, "get_langchain_prompt") else str(prompt_obj)
            except Exception:
                text = str(prompt_obj)

        if text is not None and self.convert_mustache:
            text = _mustache_to_python_format(text)

        return text

    def get_bundle(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> StructuredPromptBundle:
        """Retrieve a structured prompt bundle from Langfuse with fallback.

        Attempts to fetch the primary prompt bundle, as well as multi-pass companion
        prompts (e.g. ``<name>_reasoning``, ``<name>_format``, ``<name>_gleaning``)
        if registered in Langfuse. If missing and ``auto_create_missing`` is True,
        creates the default bundle in Langfuse.

        Parameters
        ----------
        prompt_name : str
            Canonical prompt name.
        label_or_version : str or int, default "production"
            Version number or deployment label.

        Returns
        -------
        StructuredPromptBundle
            Resolved bundle with Langfuse metadata.
        """
        direct_obj = self._fetch_langfuse_prompt(prompt_name, label_or_version)
        if direct_obj is None:
            # Check if auto-create is enabled and we have a valid client
            if self.auto_create_missing and self.client is not None and hasattr(self.client, "create_prompt") and isinstance(label_or_version, str):
                try:
                    fallback_bundle = self.fallback.get_bundle(prompt_name, label_or_version)
                    logger.info("Auto-creating missing prompt bundle %r in Langfuse...", prompt_name)
                    created = self.create_bundle(prompt_name, fallback_bundle, label=label_or_version)
                    if created.provider == "langfuse":
                        return created
                except Exception as exc:
                    logger.warning("Failed to auto-create missing prompt in Langfuse: %s", exc)

            # Fall back to delegate
            logger.debug(
                "Falling back to default provider for prompt bundle %r", prompt_name
            )
            return self.fallback.get_bundle(prompt_name, label_or_version)

        direct_text = self._extract_template_text(direct_obj)
        if not direct_text:
            return self.fallback.get_bundle(prompt_name, label_or_version)

        # Extract Langfuse metadata
        version = getattr(direct_obj, "version", None)
        name = getattr(direct_obj, "name", prompt_name)
        labels = getattr(direct_obj, "labels", None)
        active_label = (
            labels[0] if isinstance(labels, list) and labels else str(label_or_version)
        )
        metadata = getattr(direct_obj, "config", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {"raw_config": metadata}

        # Check for multi-pass companions in Langfuse (e.g., ner_reasoning, decision)
        reasoning_text = self._extract_template_text(
            self._fetch_langfuse_prompt(f"{prompt_name}_reasoning", label_or_version)
        )
        format_text = self._extract_template_text(
            self._fetch_langfuse_prompt(f"{prompt_name}_format", label_or_version)
        )
        gleaning_text = self._extract_template_text(
            self._fetch_langfuse_prompt(f"{prompt_name}_gleaning", label_or_version)
        )
        decision_text = self._extract_template_text(
            self._fetch_langfuse_prompt(f"{prompt_name}_decision", label_or_version)
        )
        decision_criteria = metadata.get("decision_criteria") if isinstance(metadata, dict) else None

        # If companion templates are not in Langfuse, inspect if fallback provides them
        if not reasoning_text or not format_text or not decision_text or not decision_criteria:
            try:
                fallback_bundle = self.fallback.get_bundle(prompt_name, label_or_version)
                if not reasoning_text:
                    reasoning_text = fallback_bundle.reasoning_template
                if not format_text:
                    format_text = fallback_bundle.format_template
                if not gleaning_text:
                    gleaning_text = fallback_bundle.gleaning_template
                if not decision_text:
                    decision_text = fallback_bundle.decision_template
                if not decision_criteria:
                    decision_criteria = fallback_bundle.decision_criteria
            except Exception:
                pass

        return StructuredPromptBundle(
            direct_template=direct_text,
            reasoning_template=reasoning_text,
            format_template=format_text,
            gleaning_template=gleaning_text,
            decision_template=decision_text,
            decision_criteria=decision_criteria,
            name=name,
            version=version,
            label=active_label,
            provider="langfuse",
            metadata=metadata,
        )

    def get_template(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> str:
        """Retrieve direct template string from Langfuse with fallback."""
        bundle = self.get_bundle(prompt_name, label_or_version)
        return bundle.direct_template

    def populate_config(
        self,
        config: PipelineConfig,
        label_or_version: str | int = "production",
        sync_defaults: bool = True,
    ) -> PipelineConfig:
        """Populate all phase prompts on a PipelineConfig from Langfuse.

        Parameters
        ----------
        config : PipelineConfig
            Target configuration instance.
        label_or_version : str or int, default "production"
            Target deployment label or version identifier.
        sync_defaults : bool, default True
            Whether to ensure all default prompt bundles are created and versioned
            in Langfuse if not already present.

        Returns
        -------
        PipelineConfig
            Populated configuration instance.
        """
        if sync_defaults and isinstance(label_or_version, str):
            self.sync_defaults_to_langfuse(label=label_or_version)

        config.phase2.ner_prompts = self.get_bundle("ner_extraction", label_or_version)
        config.phase2.entity_linking_prompts = self.get_bundle("entity_linking", label_or_version)
        config.phase2.entity_linking_prompt_template = config.phase2.entity_linking_prompts.direct_template

        config.phase3.global_relation_prompts = self.get_bundle("global_relation", label_or_version)

        config.phase4_maturation.entity_synthesis_prompts = self.get_bundle("entity_synthesis", label_or_version)

        config.phase4.adu_segmentation_prompts = self.get_bundle("adu_segmentation", label_or_version)
        config.phase4.adu_segmentation_prompt_template = config.phase4.adu_segmentation_prompts.direct_template
        config.phase4.acc_prompts = self.get_bundle("acc_classification", label_or_version)
        config.phase4.arc_prompts = self.get_bundle("arc_classification", label_or_version)

        config.phase3b.verification.borderline_merge_prompts = self.get_bundle("decision_borderline_merge", label_or_version)
        config.phase3b.verification.canonical_election_prompts = self.get_bundle("decision_canonical_election", label_or_version)
        config.phase5.gating.prompt_bundle = self.get_bundle("decision_theory_fusion", label_or_version)

        return config


class FilePromptProvider:
    """Prompt provider loading prompt bundles from JSON or YAML files on disk.

    Parameters
    ----------
    prompts_dir : str or Path
        Directory containing prompt JSON or YAML definition files.
    fallback : PromptProvider, optional
        Fallback provider for missing prompt files. Defaults to ``DefaultPromptProvider``.
    """

    def __init__(
        self,
        prompts_dir: str | Path,
        fallback: PromptProvider | None = None,
    ) -> None:
        self.prompts_dir = Path(prompts_dir)
        self.fallback: PromptProvider = fallback or DefaultPromptProvider()

    def get_bundle(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> StructuredPromptBundle:
        """Load structured prompt bundle from JSON file."""
        candidates = [
            self.prompts_dir / f"{prompt_name}.json",
            self.prompts_dir / f"{prompt_name}_{label_or_version}.json",
        ]
        for path in candidates:
            if path.exists() and path.is_file():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload.setdefault("name", prompt_name)
                    payload.setdefault("provider", "file")
                    payload.setdefault("label", str(label_or_version))
                    return StructuredPromptBundle.model_validate(payload)
                except Exception as exc:
                    logger.warning("Failed to load prompt bundle from %s: %s", path, exc)

        return self.fallback.get_bundle(prompt_name, label_or_version)

    def get_template(
        self, prompt_name: str, label_or_version: str | int = "production"
    ) -> str:
        """Retrieve direct template string from file or fallback."""
        bundle = self.get_bundle(prompt_name, label_or_version)
        return bundle.direct_template

    def populate_config(
        self, config: PipelineConfig, label_or_version: str | int = "production"
    ) -> PipelineConfig:
        """Populate PipelineConfig prompts from file definitions."""
        config.phase2.ner_prompts = self.get_bundle("ner_extraction", label_or_version)
        config.phase2.entity_linking_prompts = self.get_bundle("entity_linking", label_or_version)
        config.phase2.entity_linking_prompt_template = config.phase2.entity_linking_prompts.direct_template

        config.phase3.global_relation_prompts = self.get_bundle("global_relation", label_or_version)

        config.phase4_maturation.entity_synthesis_prompts = self.get_bundle("entity_synthesis", label_or_version)

        config.phase4.adu_segmentation_prompts = self.get_bundle("adu_segmentation", label_or_version)
        config.phase4.adu_segmentation_prompt_template = config.phase4.adu_segmentation_prompts.direct_template
        config.phase4.acc_prompts = self.get_bundle("acc_classification", label_or_version)
        config.phase4.arc_prompts = self.get_bundle("arc_classification", label_or_version)

        config.phase3b.verification.borderline_merge_prompts = self.get_bundle("decision_borderline_merge", label_or_version)
        config.phase3b.verification.canonical_election_prompts = self.get_bundle("decision_canonical_election", label_or_version)
        config.phase5.gating.prompt_bundle = self.get_bundle("decision_theory_fusion", label_or_version)

        return config
