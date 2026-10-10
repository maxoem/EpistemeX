"""Execution strategies and result decoders for typed decision questions.

This module provides concrete implementations of the
:class:`QuestionExecutionStrategy` protocol, encapsulating single-question
dispatch, Laya MLX input specification generation, and output decoding for each
evaluation modality ("choice", "noul", "score").
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from episteme_pipeline.decision.mock import compute_conformal_prediction_set
from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionQuestion,
    DecisionScore,
    ensure_decision_question,
)

logger = logging.getLogger(__name__)


def estimate_tokens_saved(
    state: Any,
    question: str,
    options: Sequence[Any] | dict[str, Any] | None = None,
) -> int:
    """Heuristic estimate of generative LLM tokens saved by System 1 fast-exit.

    Parameters
    ----------
    state : Any
        The input state block.
    question : str
        The evaluation question.
    options : Sequence or dict or None, default None
        Options or levels considered.

    Returns
    -------
    int
        Estimated tokens saved (input prompt + completion).
    """
    state_len = len(str(state))
    question_len = len(question)
    options_count = len(options) if options else 0
    prompt_tokens = (state_len // 4) + (question_len // 4) + (options_count * 8)
    completion_tokens = 50
    return prompt_tokens + completion_tokens


@runtime_checkable
class QuestionExecutionStrategy(Protocol):
    """Strategy interface for question execution and result decoding.

    Encapsulates modality-specific evaluation rules for single questions,
    batch payload formatting for backends, and unmarshalling of raw predictions
    into strongly typed contracts.
    """

    async def evaluate_single(
        self,
        engine: DecisionEngine,
        state: Any,
        question: DecisionQuestion,
    ) -> DecisionScore | DecisionNoulResult:
        """Execute a single question against an engine instance.

        Parameters
        ----------
        engine : DecisionEngine
            Active decision engine.
        state : Any
            State block or context.
        question : DecisionQuestion
            Typed question to evaluate.

        Returns
        -------
        DecisionScore or DecisionNoulResult
            Evaluation outcome.
        """
        ...

    def to_laya_spec(self, question: DecisionQuestion) -> dict[str, Any]:
        """Convert a DecisionQuestion to a Laya MLX forward pass question spec.

        Parameters
        ----------
        question : DecisionQuestion
            Typed question.

        Returns
        -------
        dict of str to Any
            Laya question payload dictionary.
        """
        ...

    def decode_laya_answer(
        self,
        question: DecisionQuestion,
        raw_answer: Any,
        default_act_p: float,
        state: Any,
        default_confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
    ) -> DecisionScore | DecisionNoulResult:
        """Decode raw Laya MLX prediction output into typed contract result.

        Parameters
        ----------
        question : DecisionQuestion
            Typed question specification.
        raw_answer : Any
            Raw answer output returned by Laya Agent.
        default_act_p : float
            Calibrated empirical accuracy from action metadata.
        state : Any
            Input state block (for token savings estimation).
        default_confidence_threshold : float, default 0.85
            Threshold for binary passing gating.
        conformal_alpha : float, default 0.05
            Significance level for prediction sets.

        Returns
        -------
        DecisionScore or DecisionNoulResult
            Typed evaluation outcome.
        """
        ...


class NoulQuestionStrategy:
    """Execution and decoding strategy for binary 'noul' proposition evaluations."""

    async def evaluate_single(
        self,
        engine: DecisionEngine,
        state: Any,
        question: DecisionQuestion,
    ) -> DecisionNoulResult:
        """Execute a binary statement via engine.evaluate_noul.

        Parameters
        ----------
        engine : DecisionEngine
            Active decision engine.
        state : Any
            State block or context.
        question : DecisionQuestion
            Typed question.

        Returns
        -------
        DecisionNoulResult
            Evaluation outcome.
        """
        return await engine.evaluate_noul(state, question.question)

    def to_laya_spec(self, question: DecisionQuestion) -> dict[str, Any]:
        """Format question into Laya noul question entry.

        Parameters
        ----------
        question : DecisionQuestion
            Typed question.

        Returns
        -------
        dict of str to Any
            Laya dictionary payload.
        """
        return {
            "type": "noul",
            "instructions": question.question,
        }

    def decode_laya_answer(
        self,
        question: DecisionQuestion,
        raw_answer: Any,
        default_act_p: float,
        state: Any,
        default_confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
    ) -> DecisionNoulResult:
        """Decode Laya raw answer into DecisionNoulResult.

        Parameters
        ----------
        question : DecisionQuestion
            Question specification.
        raw_answer : Any
            Raw answer value.
        default_act_p : float
            Empirical accuracy.
        state : Any
            State block.
        default_confidence_threshold : float, default 0.85
            Passing probability threshold.
        conformal_alpha : float, default 0.05
            Unused for binary noul.

        Returns
        -------
        DecisionNoulResult
            Calibrated binary result.
        """
        prob = float(raw_answer) if isinstance(raw_answer, (int, float)) else 0.5
        passed = prob >= default_confidence_threshold
        return DecisionNoulResult(
            probability=prob,
            empirical_accuracy=default_act_p,
            passed=passed,
        )


class ScoreQuestionStrategy:
    """Execution and decoding strategy for ordered scale and rubric 'score' evaluations."""

    async def evaluate_single(
        self,
        engine: DecisionEngine,
        state: Any,
        question: DecisionQuestion,
    ) -> DecisionScore:
        """Execute rubric scoring via engine.evaluate_score.

        Parameters
        ----------
        engine : DecisionEngine
            Active decision engine.
        state : Any
            State block.
        question : DecisionQuestion
            Typed question.

        Returns
        -------
        DecisionScore
            Scored evaluation outcome.
        """
        levels = question.criteria if isinstance(question.criteria, list) else [1, 2, 3]
        return await engine.evaluate_score(state, question.question, levels)

    def to_laya_spec(self, question: DecisionQuestion) -> dict[str, Any]:
        """Format question into Laya score question entry.

        Parameters
        ----------
        question : DecisionQuestion
            Typed question.

        Returns
        -------
        dict of str to Any
            Laya dictionary payload.
        """
        levels = question.criteria if isinstance(question.criteria, list) else [1, 2, 3]
        return {
            "type": "score",
            "instructions": question.question,
            "criteria": [str(lvl) for lvl in levels],
        }

    def decode_laya_answer(
        self,
        question: DecisionQuestion,
        raw_answer: Any,
        default_act_p: float,
        state: Any,
        default_confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
    ) -> DecisionScore:
        """Decode Laya raw answer into DecisionScore.

        Parameters
        ----------
        question : DecisionQuestion
            Question specification.
        raw_answer : Any
            Raw answer value.
        default_act_p : float
            Empirical accuracy.
        state : Any
            State block.
        default_confidence_threshold : float, default 0.85
            Unused for score.
        conformal_alpha : float, default 0.05
            Unused for score.

        Returns
        -------
        DecisionScore
            Scored result.
        """
        levels = question.criteria if isinstance(question.criteria, list) else [1, 2, 3]
        if isinstance(raw_answer, (int, float)):
            idx = min(round(raw_answer), len(levels) - 1)
            selected = levels[idx]
            probs = {
                str(lvl): 0.8 if lvl == selected else round(0.20 / max(1, len(levels) - 1), 4)
                for lvl in levels
            }
        elif isinstance(raw_answer, dict):
            probs = {str(k): float(v) for k, v in raw_answer.items()}
            selected = max(probs, key=probs.get) if probs else levels[0]
        else:
            selected = levels[0]
            probs = {str(lvl): round(1.0 / max(1, len(levels)), 4) for lvl in levels}

        class_prob = probs.get(str(selected), 0.8)
        tokens_saved = estimate_tokens_saved(state, question.question, levels)
        return DecisionScore(
            selected_option=selected,
            class_probability=class_prob,
            empirical_accuracy=default_act_p,
            probabilities=probs,
            prediction_set=[str(selected)],
            tokens_saved_estimate=tokens_saved,
        )


class ChoiceQuestionStrategy:
    """Execution and decoding strategy for categorical classification 'choice' evaluations."""

    async def evaluate_single(
        self,
        engine: DecisionEngine,
        state: Any,
        question: DecisionQuestion,
    ) -> DecisionScore:
        """Execute categorical choice via engine.evaluate_choice.

        Parameters
        ----------
        engine : DecisionEngine
            Active decision engine.
        state : Any
            State block.
        question : DecisionQuestion
            Typed question.

        Returns
        -------
        DecisionScore
            Categorical evaluation outcome.
        """
        opts = question.criteria if question.criteria is not None else []
        return await engine.evaluate_choice(
            state, question.question, opts, alpha=question.alpha
        )

    def to_laya_spec(self, question: DecisionQuestion) -> dict[str, Any]:
        """Format question into Laya choice question entry.

        Parameters
        ----------
        question : DecisionQuestion
            Typed question.

        Returns
        -------
        dict of str to Any
            Laya dictionary payload.
        """
        spec: dict[str, Any] = {
            "type": "choice",
            "instructions": question.question,
        }
        if question.criteria is not None:
            spec["criteria"] = question.criteria
        return spec

    def decode_laya_answer(
        self,
        question: DecisionQuestion,
        raw_answer: Any,
        default_act_p: float,
        state: Any,
        default_confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
    ) -> DecisionScore:
        """Decode Laya raw answer into DecisionScore with conformal prediction set.

        Parameters
        ----------
        question : DecisionQuestion
            Question specification.
        raw_answer : Any
            Raw answer value.
        default_act_p : float
            Empirical accuracy.
        state : Any
            State block.
        default_confidence_threshold : float, default 0.85
            Unused for choice.
        conformal_alpha : float, default 0.05
            Significance level for prediction sets.

        Returns
        -------
        DecisionScore
            Scored categorical outcome.
        """
        options = question.criteria if question.criteria is not None else []
        alpha = question.alpha if question.alpha is not None else conformal_alpha

        if isinstance(raw_answer, dict):
            probs = {str(k): float(v) for k, v in raw_answer.items()}
            selected = max(probs, key=probs.get) if probs else "UNKNOWN"
        elif isinstance(raw_answer, str):
            probs = {raw_answer: 1.0}
            selected = raw_answer
        else:
            opt_list = list(options.keys()) if isinstance(options, dict) else list(options)
            selected = opt_list[0] if opt_list else "UNKNOWN"
            probs = {selected: 0.85}

        class_prob = probs.get(selected, 0.85)
        pred_set = compute_conformal_prediction_set(probs, alpha=alpha)
        tokens_saved = estimate_tokens_saved(state, question.question, options)

        return DecisionScore(
            selected_option=selected,
            class_probability=class_prob,
            empirical_accuracy=default_act_p,
            probabilities=probs,
            prediction_set=pred_set,
            tokens_saved_estimate=tokens_saved,
        )


QUESTION_STRATEGIES: dict[str, QuestionExecutionStrategy] = {
    "noul": NoulQuestionStrategy(),
    "score": ScoreQuestionStrategy(),
    "choice": ChoiceQuestionStrategy(),
}


def get_question_strategy(modality: str) -> QuestionExecutionStrategy:
    """Resolve the execution strategy for a given question modality.

    Parameters
    ----------
    modality : str
        Evaluation modality ("noul", "score", or "choice").

    Returns
    -------
    QuestionExecutionStrategy
        Strategy instance for the modality (defaults to ChoiceQuestionStrategy if unknown).
    """
    strategy = QUESTION_STRATEGIES.get(modality)
    if strategy is None:
        return QUESTION_STRATEGIES["choice"]
    return strategy


def register_question_strategy(
    modality: str,
    strategy: QuestionExecutionStrategy,
) -> None:
    """Register or override an execution strategy for a modality.

    Parameters
    ----------
    modality : str
        Modality key identifier.
    strategy : QuestionExecutionStrategy
        Strategy instance implementing QuestionExecutionStrategy protocol.
    """
    QUESTION_STRATEGIES[modality] = strategy


async def evaluate_questions_sequentially(
    engine: DecisionEngine,
    state: Any,
    questions: dict[str, DecisionQuestion | dict[str, Any]],
) -> dict[str, DecisionScore | DecisionNoulResult]:
    """Evaluate a batch of questions sequentially via their respective strategies.

    Parameters
    ----------
    engine : DecisionEngine
        The active decision engine instance.
    state : Any
        The input state block.
    questions : dict of str to (DecisionQuestion or dict)
        Mapping from question identifiers to question specifications.

    Returns
    -------
    dict of str to (DecisionScore or DecisionNoulResult)
        Mapping from question identifier to evaluation result.
    """
    typed_questions = {k: ensure_decision_question(v) for k, v in questions.items()}
    results: dict[str, DecisionScore | DecisionNoulResult] = {}
    for key, q_item in typed_questions.items():
        strategy = get_question_strategy(q_item.type)
        results[key] = await strategy.evaluate_single(engine, state, q_item)
    return results
