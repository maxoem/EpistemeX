"""Objective gleaning gating via Jev Actor-Critic stopping oracle (ISSUE-040).

This module provides :class:`JevGleaningGate`, which decouples the generative
extraction actor (LLM) from an external, calibrated Jev Noul stopping critic.
This eliminates introspective LLM confirmation bias and spurious over-extraction.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from episteme_pipeline.config import GleaningConfig

from episteme_pipeline.contracts.domain import L2Entity, TheoryAtom
from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import DecisionGatingTriggered
from episteme_pipeline.prompts.default_prompts import DECISION_GLEANING_QUESTION
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.decision import DecisionEngine, GleaningStoppingOracle

logger = logging.getLogger(__name__)


class FixedPassGleaningOracle:
    """Fixed-iteration stopping oracle without dynamic classification.

    Parameters
    ----------
    max_passes : int, default 0
        Maximum allowable passes before terminating gleaning.
    """

    def __init__(self, max_passes: int = 0) -> None:
        self.max_passes = max_passes

    async def should_glean(
        self,
        chunk_text: str,
        current_extractions: list[Any],
        pass_count: int,
        max_passes: int | None = None,
        **kwargs: Any,
    ) -> tuple[bool, float]:
        """Evaluate if extraction should continue up to fixed pass limits."""
        effective_max = max_passes if max_passes is not None else self.max_passes
        return pass_count < effective_max, 1.0


class JevGleaningGate:
    """Actor-Critic stopping oracle for iterative extraction and gleaning passes.

    Implements :class:`GleaningStoppingOracle`.

    Parameters
    ----------
    decision_engine : DecisionEngine or None, default None
        Injected calibrated decision engine for System 1 evaluations.
    config : GleaningConfig or None, default None
        Encapsulated gleaning configuration sub-model. Defaults to default
        ``GleaningConfig()`` if None.
    prompts : StructuredPromptBundle or None, default None
        Optional prompt bundle providing customized decision templates.
    default_threshold : float or None, default None
        Optional override for calibrated probability threshold.
    default_audit_rate : float or None, default None
        Optional override for stochastic false-negative audit rate.
    max_passes : int or None, default None
        Optional override for maximum passes permitted.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine | None = None,
        config: GleaningConfig | None = None,
        prompts: StructuredPromptBundle | None = None,
        default_threshold: float | None = None,
        default_audit_rate: float | None = None,
        max_passes: int | None = None,
    ) -> None:
        self.decision_engine = decision_engine
        self.prompts = prompts

        if config is None:
            from episteme_pipeline.config import GleaningConfig

            cfg = GleaningConfig()
        else:
            cfg = config.model_copy()
        if default_threshold is not None:
            cfg.confidence_threshold = default_threshold
        if default_audit_rate is not None:
            cfg.audit_rate = default_audit_rate
        if max_passes is not None:
            cfg.max_passes = max_passes

        self.config = cfg

    @property
    def default_threshold(self) -> float:
        """Calibrated probability threshold from configuration."""
        return self.config.confidence_threshold

    @property
    def default_audit_rate(self) -> float:
        """Stochastic audit rate from configuration."""
        return self.config.audit_rate

    @property
    def max_passes(self) -> int:
        """Maximum allowable gleaning passes from configuration."""
        return self.config.max_passes

    @classmethod
    def create(
        cls,
        decision_engine: DecisionEngine | None,
        config: GleaningConfig,
        prompts: StructuredPromptBundle | None = None,
    ) -> GleaningStoppingOracle:
        """Create an appropriate stopping oracle based on configuration and engine availability.

        Parameters
        ----------
        decision_engine : DecisionEngine or None
            Calibrated decision engine, if available.
        config : GleaningConfig
            Encapsulated gleaning configuration.
        prompts : StructuredPromptBundle or None, default None
            Optional prompt bundle providing customized decision templates.

        Returns
        -------
        GleaningStoppingOracle
            A JevGleaningGate if enabled and engine provided, otherwise a FixedPassGleaningOracle.
        """
        if config.enabled and decision_engine is not None:
            return cls(
                decision_engine=decision_engine,
                config=config,
                prompts=prompts,
            )
        return FixedPassGleaningOracle(max_passes=config.max_passes if config.enabled else 0)

    @staticmethod
    def _format_context(chunk_text: str, current_extractions: list[Any]) -> dict[str, Any]:
        """Format input chunk text and current extractions into structured state.

        Parameters
        ----------
        chunk_text : str
            Raw text of the source chunk.
        current_extractions : list of Any
            List of previously extracted entities, claims, or text spans.

        Returns
        -------
        dict of str to Any
            Structured state payload for decision engine evaluation.
        """
        formatted_items: list[str] = []
        for item in current_extractions:
            if isinstance(item, L2Entity):
                formatted_items.append(f"Entity({item.label}: {item.name})")
            elif isinstance(item, TheoryAtom):
                formatted_items.append(f"Component({item.component_type}: {item.text})")
            else:
                formatted_items.append(str(item))

        return {
            "chunk_text": chunk_text,
            "current_extractions": formatted_items,
            "total_extracted_so_far": len(current_extractions),
        }

    async def should_glean(
        self,
        chunk_text: str,
        current_extractions: list[Any],
        pass_count: int,
        max_passes: int | None = None,
        threshold: float | None = None,
        audit_rate: float | None = None,
    ) -> tuple[bool, float]:
        """Evaluate whether an additional gleaning pass should be executed.

        Parameters
        ----------
        chunk_text : str
            Source chunk text being mined.
        current_extractions : list of Any
            Entities or argument components extracted in prior passes.
        pass_count : int
            Current zero-indexed pass index (0 after initial extraction pass).
        max_passes : int or None, default None
            Maximum allowable gleaning passes. Defaults to instance limit.
        threshold : float or None, default None
            Probability threshold for unextracted propositions. Defaults to instance threshold.
        audit_rate : float or None, default None
            Probability of triggering a stochastic audit pass. Defaults to instance rate.

        Returns
        -------
        tuple of (bool, float)
            Tuple of (should_continue_gleaning, empirical_accuracy).
        """
        effective_max_passes = max_passes if max_passes is not None else self.max_passes
        effective_threshold = threshold if threshold is not None else self.default_threshold
        effective_audit_rate = audit_rate if audit_rate is not None else self.default_audit_rate
        emitter = get_event_emitter()

        # Hard boundary: if pass_count reached or exceeded max_passes, stop unconditionally.
        if pass_count >= effective_max_passes:
            emitter.emit(
                DecisionGatingTriggered(
                    gate_name="gleaning_gate",
                    action_taken="loop_terminated",
                    empirical_accuracy=1.0,
                    threshold=effective_threshold,
                )
            )
            return False, 1.0

        # If no decision engine was injected, fallback to standard continuation until max_passes
        if self.decision_engine is None:
            return True, 1.0

        state = self._format_context(chunk_text, current_extractions)
        question = (
            self.prompts.decision_template
            if self.prompts and self.prompts.decision_template
            else DECISION_GLEANING_QUESTION
        )

        noul_result = await self.decision_engine.evaluate_noul(
            state=state,
            question=question,
        )

        unextracted_prob = noul_result.probability
        emp_accuracy = noul_result.empirical_accuracy

        # Gating evaluation:
        if unextracted_prob >= effective_threshold:
            action_taken = "escalated_to_llm"
            should_run = True
        else:
            # Stochastic audit check: 2% random sample to catch false negatives
            is_audit = (random.random() < effective_audit_rate)
            if is_audit:
                action_taken = "stochastic_audit"
                should_run = True
            else:
                action_taken = "fast_exit"
                should_run = False

        emitter.emit(
            DecisionGatingTriggered(
                gate_name="gleaning_gate",
                action_taken=action_taken,
                empirical_accuracy=emp_accuracy,
                threshold=effective_threshold,
                prediction_set_size=1,
            )
        )

        logger.debug(
            "JevGleaningGate: pass %d/%d, prob=%.3f, threshold=%.3f, action=%s",
            pass_count,
            effective_max_passes,
            unextracted_prob,
            effective_threshold,
            action_taken,
        )

        return should_run, emp_accuracy
