"""Deterministic in-memory mock decision engine.

This module provides :class:`MockJevDecisionEngine`, an in-memory implementation
of the :class:`~episteme_pipeline.protocols.decision.DecisionEngine` protocol designed
for deterministic unit and integration testing without requiring GPU acceleration,
model checkpoint downloads, or API keys.
"""

from __future__ import annotations

import asyncio
from typing import Any

from episteme_pipeline.protocols.decision import (
    DecisionEngine,
    DecisionNoulResult,
    DecisionScore,
)


def compute_conformal_prediction_set(
    probabilities: dict[str, float],
    alpha: float = 0.05,
) -> list[str]:
    """Compute a conformal prediction set guaranteeing 1 - alpha coverage.

    Sorts candidate labels in descending order of predicted probability and
    accumulates options until the cumulative probability exceeds 1 - alpha.
    Singletons trigger fast-exit in downstream pipeline gating.

    Parameters
    ----------
    probabilities : dict of str to float
        Categorical probability distribution over candidate labels.
    alpha : float, default 0.05
        Significance error level (1 - alpha error coverage guarantee).

    Returns
    -------
    list of str
        Subset of labels included in the conformal prediction set C(X).
    """
    if not probabilities:
        return []

    sorted_items = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    target_mass = 1.0 - alpha

    cum_sum = 0.0
    prediction_set: list[str] = []

    for label, prob in sorted_items:
        prediction_set.append(label)
        cum_sum += prob
        if cum_sum >= target_mass:
            break

    return prediction_set


class MockJevDecisionEngine:
    """In-memory deterministic mock decision engine.

    Enables testing pipeline phases and gating logic by matching state/question
    patterns against pre-registered fixtures, or returning configurable defaults.

    Parameters
    ----------
    default_confidence_threshold : float, default 0.85
        Default threshold for binary noul decisions.
    conformal_alpha : float, default 0.05
        Default significance error level for conformal prediction sets.
    simulated_latency : float, default 0.0
        Simulated latency in seconds to replicate System 1 inference time.
    """

    def __init__(
        self,
        default_confidence_threshold: float = 0.85,
        conformal_alpha: float = 0.05,
        simulated_latency: float = 0.0,
    ) -> None:
        self.default_confidence_threshold = default_confidence_threshold
        self.conformal_alpha = conformal_alpha
        self.simulated_latency = simulated_latency
        self.calls: list[dict[str, Any]] = []
        self._noul_rules: list[dict[str, Any]] = []
        self._choice_rules: list[dict[str, Any]] = []
        self._score_rules: list[dict[str, Any]] = []
        self.should_raise: Exception | None = None

    @property
    def name(self) -> str:
        """Return the mock engine name."""
        return "MockJevDecisionEngine"

    def register_noul_response(
        self,
        question_pattern: str,
        state_pattern: str | None = None,
        probability: float = 0.95,
        empirical_accuracy: float = 0.92,
        passed: bool | None = None,
    ) -> None:
        """Register a fixture response for binary noul questions.

        Parameters
        ----------
        question_pattern : str
            Substring pattern to match against question text (case-insensitive).
        state_pattern : str or None, default None
            Optional substring pattern to match against input state.
        probability : float, default 0.95
            Calibrated proposition probability P(true).
        empirical_accuracy : float, default 0.92
            Calibrated empirical accuracy frequency.
        passed : bool or None, default None
            Explicit boolean flag. If None, derived from probability >= threshold.
        """
        self._noul_rules.append(
            {
                "question_pattern": question_pattern.lower(),
                "state_pattern": state_pattern.lower() if state_pattern else None,
                "probability": probability,
                "empirical_accuracy": empirical_accuracy,
                "passed": passed
                if passed is not None
                else (probability >= self.default_confidence_threshold),
            }
        )

    def register_choice_response(
        self,
        question_pattern: str,
        state_pattern: str | None = None,
        selected_option: str | int | None = None,
        probabilities: dict[str, float] | None = None,
        class_probability: float | None = None,
        empirical_accuracy: float = 0.90,
        prediction_set: list[str] | None = None,
        tokens_saved_estimate: int = 120,
    ) -> None:
        """Register a fixture response for categorical choice questions.

        Parameters
        ----------
        question_pattern : str
            Substring pattern to match against question text (case-insensitive).
        state_pattern : str or None, default None
            Optional substring pattern to match against input state.
        selected_option : str, int, or None, default None
            The winning option to return.
        probabilities : dict of str to float or None, default None
            Categorical probability distribution.
        class_probability : float or None, default None
            Peak softmax probability. If omitted, derived from max(probabilities).
        empirical_accuracy : float, default 0.90
            Calibrated empirical frequency of being correct.
        prediction_set : list of str or None, default None
            Conformal prediction set.
        tokens_saved_estimate : int, default 120
            Estimated LLM tokens saved.
        """
        self._choice_rules.append(
            {
                "question_pattern": question_pattern.lower(),
                "state_pattern": state_pattern.lower() if state_pattern else None,
                "selected_option": selected_option,
                "probabilities": probabilities,
                "class_probability": class_probability,
                "empirical_accuracy": empirical_accuracy,
                "prediction_set": prediction_set,
                "tokens_saved_estimate": tokens_saved_estimate,
            }
        )

    def register_score_response(
        self,
        question_pattern: str,
        state_pattern: str | None = None,
        selected_option: str | int = 1,
        probabilities: dict[str, float] | None = None,
        class_probability: float = 0.85,
        empirical_accuracy: float = 0.88,
        prediction_set: list[str] | None = None,
        tokens_saved_estimate: int = 80,
    ) -> None:
        """Register a fixture response for ordered score questions.

        Parameters
        ----------
        question_pattern : str
            Substring pattern to match against question text.
        state_pattern : str or None, default None
            Optional substring pattern to match against input state.
        selected_option : str or int, default 1
            Expected or selected score level.
        probabilities : dict of str to float or None, default None
            Distribution over levels.
        class_probability : float, default 0.85
            Confidence in the selected level.
        empirical_accuracy : float, default 0.88
            Empirical accuracy estimate.
        prediction_set : list of str or None, default None
            Conformal prediction set over levels.
        tokens_saved_estimate : int, default 80
            Estimated LLM tokens saved.
        """
        self._score_rules.append(
            {
                "question_pattern": question_pattern.lower(),
                "state_pattern": state_pattern.lower() if state_pattern else None,
                "selected_option": selected_option,
                "probabilities": probabilities or {},
                "class_probability": class_probability,
                "empirical_accuracy": empirical_accuracy,
                "prediction_set": prediction_set,
                "tokens_saved_estimate": tokens_saved_estimate,
            }
        )

    def set_simulated_latency(self, latency: float) -> None:
        """Set simulated execution latency in seconds.

        Parameters
        ----------
        latency : float
            Latency duration in seconds.
        """
        self.simulated_latency = max(0.0, latency)

    def reset(self) -> None:
        """Clear all registered fixture rules and call history."""
        self.calls.clear()
        self._noul_rules.clear()
        self._choice_rules.clear()
        self._score_rules.clear()
        self.should_raise = None

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        """Evaluate a binary yes/no statement.

        Parameters
        ----------
        state : str or dict or list
            Input state block.
        question : str
            Binary proposition or question.

        Returns
        -------
        DecisionNoulResult
            Evaluation result.

        Raises
        ------
        Exception
            If ``should_raise`` is configured.
        """
        if self.should_raise is not None:
            raise self.should_raise

        if self.simulated_latency > 0.0:
            await asyncio.sleep(self.simulated_latency)

        state_str = str(state).lower()
        q_str = question.lower()

        matched_rule = None
        for rule in reversed(self._noul_rules):
            if rule["question_pattern"] in q_str:
                if rule["state_pattern"] is None or rule["state_pattern"] in state_str:
                    matched_rule = rule
                    break

        if matched_rule is not None:
            prob = matched_rule["probability"]
            emp_acc = matched_rule["empirical_accuracy"]
            passed = matched_rule["passed"]
        else:
            prob = 0.90
            emp_acc = 0.88
            passed = prob >= self.default_confidence_threshold

        res = DecisionNoulResult(
            probability=prob,
            empirical_accuracy=emp_acc,
            passed=passed,
        )

        self.calls.append(
            {
                "method": "evaluate_noul",
                "state": state,
                "question": question,
                "result": res,
            }
        )
        return res

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        """Evaluate a categorical choice over options.

        Parameters
        ----------
        state : str or dict or list
            Input state block.
        question : str
            Categorical decision question.
        options : list of str or dict of str to str
            Available options.
        alpha : float or None, default None
            Significance level for conformal prediction set.

        Returns
        -------
        DecisionScore
            Categorical evaluation score.

        Raises
        ------
        Exception
            If ``should_raise`` is configured.
        """
        if self.should_raise is not None:
            raise self.should_raise

        if self.simulated_latency > 0.0:
            await asyncio.sleep(self.simulated_latency)

        state_str = str(state).lower()
        q_str = question.lower()
        effective_alpha = alpha if alpha is not None else self.conformal_alpha

        opt_list = list(options.keys()) if isinstance(options, dict) else list(options)
        fallback_option = opt_list[0] if opt_list else "UNKNOWN"

        matched_rule = None
        for rule in reversed(self._choice_rules):
            if rule["question_pattern"] in q_str:
                if rule["state_pattern"] is None or rule["state_pattern"] in state_str:
                    matched_rule = rule
                    break

        if matched_rule is not None:
            selected = matched_rule["selected_option"] or fallback_option
            probs = matched_rule["probabilities"]
            if probs is None:
                probs = {selected: 0.88}
                for opt in opt_list:
                    if opt != selected:
                        probs[opt] = round(0.12 / max(1, len(opt_list) - 1), 4)

            class_prob = matched_rule["class_probability"] or probs.get(selected, 0.88)
            emp_acc = matched_rule["empirical_accuracy"]
            pred_set = matched_rule["prediction_set"]
            if pred_set is None:
                pred_set = compute_conformal_prediction_set(probs, alpha=effective_alpha)
            tokens_saved = matched_rule["tokens_saved_estimate"]
        else:
            selected = fallback_option
            probs = {selected: 0.85}
            rem = 0.15
            other_opts = [opt for opt in opt_list if opt != selected]
            for opt in other_opts:
                probs[opt] = round(rem / len(other_opts), 4)
            class_prob = 0.85
            emp_acc = 0.88
            pred_set = compute_conformal_prediction_set(probs, alpha=effective_alpha)
            tokens_saved = (len(str(state)) // 4) + (len(question) // 4) + (len(opt_list) * 8) + 50

        res = DecisionScore(
            selected_option=selected,
            class_probability=class_prob,
            empirical_accuracy=emp_acc,
            probabilities=probs,
            prediction_set=pred_set,
            tokens_saved_estimate=tokens_saved,
        )

        self.calls.append(
            {
                "method": "evaluate_choice",
                "state": state,
                "question": question,
                "options": options,
                "alpha": alpha,
                "result": res,
            }
        )
        return res

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[int | str],
    ) -> DecisionScore:
        """Evaluate an ordered scale or score against levels.

        Parameters
        ----------
        state : str or dict or list
            Input state block.
        question : str
            Scoring rubric question.
        levels : list of int or list of str
            Ordered levels.

        Returns
        -------
        DecisionScore
            Evaluation score indicating expected level and probabilities.

        Raises
        ------
        Exception
            If ``should_raise`` is configured.
        """
        if self.should_raise is not None:
            raise self.should_raise

        if self.simulated_latency > 0.0:
            await asyncio.sleep(self.simulated_latency)

        state_str = str(state).lower()
        q_str = question.lower()
        fallback_level = levels[0] if levels else 1

        matched_rule = None
        for rule in reversed(self._score_rules):
            if rule["question_pattern"] in q_str:
                if rule["state_pattern"] is None or rule["state_pattern"] in state_str:
                    matched_rule = rule
                    break

        if matched_rule is not None:
            selected = matched_rule["selected_option"]
            probs = matched_rule["probabilities"]
            class_prob = matched_rule["class_probability"]
            emp_acc = matched_rule["empirical_accuracy"]
            pred_set = matched_rule["prediction_set"]
            tokens_saved = matched_rule["tokens_saved_estimate"]
        else:
            selected = fallback_level
            probs = {str(lvl): (0.75 if lvl == selected else round(0.25 / max(1, len(levels) - 1), 4)) for lvl in levels}
            class_prob = 0.75
            emp_acc = 0.80
            pred_set = [str(selected)]
            tokens_saved = (len(str(state)) // 4) + (len(question) // 4) + 40

        res = DecisionScore(
            selected_option=selected,
            class_probability=class_prob,
            empirical_accuracy=emp_acc,
            probabilities=probs,
            prediction_set=pred_set,
            tokens_saved_estimate=tokens_saved,
        )

        self.calls.append(
            {
                "method": "evaluate_score",
                "state": state,
                "question": question,
                "levels": levels,
                "result": res,
            }
        )
        return res

    async def evaluate_batch(
        self,
        state: str | dict[str, Any] | list[Any],
        questions: dict[str, dict[str, Any]],
    ) -> dict[str, DecisionScore | DecisionNoulResult]:
        """Evaluate a batch of questions against a single state block in parallel.

        Parameters
        ----------
        state : str or dict or list
            Structured state block.
        questions : dict of str to dict
            Mapping from key to question definition dictionary containing
            ``type`` ("noul", "choice", "score"), ``question``, and optional
            ``options``, ``levels``, or ``alpha``.

        Returns
        -------
        dict of str to (DecisionScore or DecisionNoulResult)
            Mapping from question key to corresponding result.
        """
        results: dict[str, DecisionScore | DecisionNoulResult] = {}
        for key, q_spec in questions.items():
            q_type = q_spec.get("type", "choice")
            q_text = q_spec.get("instructions", q_spec.get("question", ""))
            if q_type == "noul":
                results[key] = await self.evaluate_noul(state, q_text)
            elif q_type == "choice":
                opts = q_spec.get("criteria", q_spec.get("options", []))
                alpha = q_spec.get("alpha")
                results[key] = await self.evaluate_choice(state, q_text, opts, alpha=alpha)
            elif q_type == "score":
                levels = q_spec.get("criteria", q_spec.get("levels", [1, 2, 3]))
                results[key] = await self.evaluate_score(state, q_text, levels)
            else:
                results[key] = await self.evaluate_noul(state, q_text)
        return results
