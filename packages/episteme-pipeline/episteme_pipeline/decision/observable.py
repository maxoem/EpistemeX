"""Observable decorator for DecisionEngine implementations.

This module provides :class:`ObservableDecisionEngine`, which wraps any
:class:`~episteme_pipeline.protocols.decision.DecisionEngine` protocol
implementation to measure latency, calculate state hashes, estimate token
savings, apply stochastic false-negative auditing, and publish domain events
to the active event emitter.
"""

from __future__ import annotations

import hashlib
import random
import time
from typing import Any

from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import (
    DecisionEvaluationCompleted,
    DecisionEvaluationStarted,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionScore,
)


class ObservableDecisionEngine:
    """Decorates a :class:`~episteme_pipeline.protocols.decision.DecisionEngine` to emit domain events.

    Parameters
    ----------
    inner : DecisionEngine
        Underlying decision engine instance to decorate.
    engine_name : str or None, default None
        Human-readable name of the decision engine. If omitted, derived from
        the inner engine's attributes or class name.
    prompt_bundle : StructuredPromptBundle or None, default None
        Optional prompt bundle carrying prompt_name, prompt_version, and
        prompt_label for telemetry prompt binding.
    stochastic_audit_rate : float, default 0.0
        Probability in [0, 1] of randomly marking a fast-exit evaluation for
        stochastic auditing (System 2 validation).
    """

    def __init__(
        self,
        inner: Any,
        engine_name: str | None = None,
        prompt_bundle: StructuredPromptBundle | None = None,
        stochastic_audit_rate: float = 0.0,
    ) -> None:
        self.inner = inner
        self.engine_name = (
            engine_name
            or getattr(inner, "name", None)
            or getattr(inner, "model_name", None)
            or type(inner).__name__
        )
        self.prompt_bundle = prompt_bundle
        self.stochastic_audit_rate = stochastic_audit_rate

    @property
    def name(self) -> str:
        """Return the engine name."""
        return self.engine_name

    @staticmethod
    def _compute_state_hash(state: Any) -> tuple[str, int]:
        """Compute stable SHA-256 hash and character count of the input state.

        Parameters
        ----------
        state : Any
            The input state block (string, dict, or list).

        Returns
        -------
        tuple of (str, int)
            Hex-encoded SHA-256 digest and character length.
        """
        state_str = str(state)
        state_hash = hashlib.sha256(state_str.encode("utf-8")).hexdigest()
        return state_hash, len(state_str)

    def _should_audit(self) -> bool:
        """Determine whether the current evaluation should be marked for stochastic audit.

        Returns
        -------
        bool
            True if random sample falls within stochastic_audit_rate.
        """
        if self.stochastic_audit_rate <= 0.0:
            return False
        return random.random() < self.stochastic_audit_rate

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        """Evaluate a binary yes/no statement with latency and event tracking.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Binary proposition or decision question to evaluate.

        Returns
        -------
        DecisionNoulResult
            Evaluation outcome containing calibrated probability and empirical
            accuracy.
        """
        state_hash, char_count = self._compute_state_hash(state)
        emitter = get_event_emitter()

        try:
            emitter.emit(
                DecisionEvaluationStarted(
                    engine_name=self.engine_name,
                    primitive="noul",
                    question=question,
                    state_hash=state_hash,
                    state_character_count=char_count,
                )
            )
        except Exception:
            pass

        t0 = time.perf_counter()
        result = await self.inner.evaluate_noul(state, question)
        duration = time.perf_counter() - t0

        is_audit = self._should_audit()
        tokens_saved = getattr(result, "tokens_saved_estimate", 0)
        if not tokens_saved:
            tokens_saved = (char_count // 4) + (len(question) // 4) + 30

        try:
            emitter.emit(
                DecisionEvaluationCompleted(
                    engine_name=self.engine_name,
                    primitive="noul",
                    question=question,
                    prompt_name=self.prompt_bundle.name if self.prompt_bundle else None,
                    prompt_version=self.prompt_bundle.version if self.prompt_bundle else None,
                    prompt_label=self.prompt_bundle.label if self.prompt_bundle else None,
                    selected_value=result.passed,
                    class_probability=result.probability,
                    empirical_accuracy=result.empirical_accuracy,
                    probabilities={
                        "true": result.probability,
                        "false": max(0.0, 1.0 - result.probability),
                    },
                    prediction_set=None,
                    is_stochastic_audit=is_audit,
                    duration_seconds=duration,
                    tokens_saved_estimate=tokens_saved,
                )
            )
        except Exception:
            pass

        return result

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        """Evaluate a categorical choice with latency and event tracking.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Categorical decision question.
        options : list of str or dict of str to str
            Allowed options or dictionary mapping option labels to rubric definitions.
        alpha : float or None, default None
            Optional significance level for conformal prediction set (1 - alpha coverage).

        Returns
        -------
        DecisionScore
            Categorical evaluation score containing selected option, class
            probability, full probability distribution, and conformal prediction set.
        """
        state_hash, char_count = self._compute_state_hash(state)
        emitter = get_event_emitter()

        try:
            emitter.emit(
                DecisionEvaluationStarted(
                    engine_name=self.engine_name,
                    primitive="choice",
                    question=question,
                    state_hash=state_hash,
                    state_character_count=char_count,
                )
            )
        except Exception:
            pass

        t0 = time.perf_counter()
        result = await self.inner.evaluate_choice(state, question, options, alpha=alpha)
        duration = time.perf_counter() - t0

        is_audit = self._should_audit()
        tokens_saved = result.tokens_saved_estimate or (
            (char_count // 4) + (len(question) // 4) + (len(options) * 8) + 50
        )

        try:
            emitter.emit(
                DecisionEvaluationCompleted(
                    engine_name=self.engine_name,
                    primitive="choice",
                    question=question,
                    prompt_name=self.prompt_bundle.name if self.prompt_bundle else None,
                    prompt_version=self.prompt_bundle.version if self.prompt_bundle else None,
                    prompt_label=self.prompt_bundle.label if self.prompt_bundle else None,
                    selected_value=str(result.selected_option),
                    class_probability=result.class_probability,
                    empirical_accuracy=result.empirical_accuracy,
                    probabilities=result.probabilities,
                    prediction_set=result.prediction_set,
                    is_stochastic_audit=is_audit,
                    duration_seconds=duration,
                    tokens_saved_estimate=tokens_saved,
                )
            )
        except Exception:
            pass

        return result

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[int | str],
    ) -> DecisionScore:
        """Evaluate an ordered scale or score with latency and event tracking.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Scoring question or grading rubric.
        levels : list of int or list of str
            Ordered scale levels.

        Returns
        -------
        DecisionScore
            Evaluation score indicating expected level and level probabilities.
        """
        state_hash, char_count = self._compute_state_hash(state)
        emitter = get_event_emitter()

        try:
            emitter.emit(
                DecisionEvaluationStarted(
                    engine_name=self.engine_name,
                    primitive="score",
                    question=question,
                    state_hash=state_hash,
                    state_character_count=char_count,
                )
            )
        except Exception:
            pass

        t0 = time.perf_counter()
        result = await self.inner.evaluate_score(state, question, levels)
        duration = time.perf_counter() - t0

        is_audit = self._should_audit()
        tokens_saved = result.tokens_saved_estimate or (
            (char_count // 4) + (len(question) // 4) + (len(levels) * 4) + 40
        )

        try:
            emitter.emit(
                DecisionEvaluationCompleted(
                    engine_name=self.engine_name,
                    primitive="score",
                    question=question,
                    prompt_name=self.prompt_bundle.name if self.prompt_bundle else None,
                    prompt_version=self.prompt_bundle.version if self.prompt_bundle else None,
                    prompt_label=self.prompt_bundle.label if self.prompt_bundle else None,
                    selected_value=result.selected_option,
                    class_probability=result.class_probability,
                    empirical_accuracy=result.empirical_accuracy,
                    probabilities=result.probabilities,
                    prediction_set=result.prediction_set,
                    is_stochastic_audit=is_audit,
                    duration_seconds=duration,
                    tokens_saved_estimate=tokens_saved,
                )
            )
        except Exception:
            pass

        return result

    def __getattr__(self, name: str) -> Any:
        """Delegate unhandled attribute and method lookups to the inner engine."""
        return getattr(self.inner, name)
