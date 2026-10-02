"""Decision engine protocol and contract models.

This module defines the abstract ``DecisionEngine`` protocol for System 1
calibrated decision routing, along with the Pydantic result contracts
(``DecisionScore``, ``DecisionNoulResult``) and the engine normalization helper
``ensure_decision_engine``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel, Field


class DecisionScore(BaseModel):
    """Calibrated evaluation result for categorical choice or scored levels.

    Parameters
    ----------
    selected_option : str, int, or None, default None
        The option key, label, or score level selected by the engine.
    class_probability : float
        Softmax probability P(y=c|x) of the selected option.
    empirical_accuracy : float
        Calibrated empirical accuracy frequency of being correct (e.g.
        Laya action.act_probability).
    probabilities : dict of str to float, default dict
        Full categorical probability distribution over candidate options.
    prediction_set : list of str or None, default None
        Conformal prediction set guaranteeing 1 - alpha coverage.
    tokens_saved_estimate : int, default 0
        Estimated generative tokens saved by routing to System 1.
    """

    selected_option: str | int | None = None
    class_probability: float = Field(
        description="Softmax probability P(y=c|x) of selected option."
    )
    empirical_accuracy: float = Field(
        description="Calibrated empirical frequency of being correct (Laya action.act_probability)."
    )
    probabilities: dict[str, float] = Field(
        default_factory=dict,
        description="Full categorical probability distribution.",
    )
    prediction_set: list[str] | None = Field(
        default=None,
        description="Conformal prediction set guaranteeing 1 - alpha coverage.",
    )
    tokens_saved_estimate: int = Field(
        default=0,
        description="Estimated generative tokens saved by routing to System 1.",
    )


class DecisionNoulResult(BaseModel):
    """Calibrated result for binary Noul (yes/no) statement evaluations.

    Parameters
    ----------
    probability : float
        Calibrated probability that the statement is true (P(true) in [0, 1]).
    empirical_accuracy : float
        Calibrated empirical accuracy frequency for this confidence bucket.
    passed : bool
        Boolean evaluation outcome (e.g. probability >= threshold).
    """

    probability: float = Field(
        description="Calibrated probability P(true) in [0, 1]."
    )
    empirical_accuracy: float = Field(
        description="Calibrated empirical accuracy frequency."
    )
    passed: bool = Field(description="Boolean decision outcome flag.")


@runtime_checkable
class DecisionEngine(Protocol):
    """Structural protocol for non-generative, typed System 1 decision engines.

    Implementations evaluate state blocks against typed questions or rubrics,
    emitting calibrated probabilities, conformal prediction sets, and empirical
    accuracy estimates.
    """

    async def evaluate_noul(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
    ) -> DecisionNoulResult:
        """Evaluate a binary yes/no statement against a state block.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload (text chunk, triple context, or metadata).
        question : str
            Binary proposition or decision question to evaluate.

        Returns
        -------
        DecisionNoulResult
            Evaluation outcome containing calibrated probability and empirical
            accuracy.
        """
        ...

    async def evaluate_choice(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        options: list[str] | dict[str, str],
        alpha: float | None = None,
    ) -> DecisionScore:
        """Evaluate a categorical choice over discrete options or rubrics.

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
        ...

    async def evaluate_score(
        self,
        state: str | dict[str, Any] | list[Any],
        question: str,
        levels: list[int | str],
    ) -> DecisionScore:
        """Evaluate an ordered scale or numerical score against a state block.

        Parameters
        ----------
        state : str or dict or list
            Structured state payload.
        question : str
            Scoring question or grading rubric.
        levels : list of int or list of str
            Ordered scale levels (e.g. Likert scale or discrete rubric tiers).

        Returns
        -------
        DecisionScore
            Evaluation score indicating expected level and level probabilities.
        """
        ...


@runtime_checkable
class GleaningStoppingOracle(Protocol):
    """Protocol for evaluating whether an iterative extraction pass should continue.

    Decouples the extraction Actor (generative LLM) from the stopping Critic
    (Jev Noul evaluator or fixed-pass bounds).
    """

    async def should_glean(
        self,
        chunk_text: str,
        current_extractions: list[Any],
        pass_count: int,
    ) -> tuple[bool, float]:
        """Evaluate if extraction should continue for an additional pass.

        Parameters
        ----------
        chunk_text : str
            Source chunk text being extracted.
        current_extractions : list of Any
            Entities or claims discovered in prior passes.
        pass_count : int
            Current iteration pass index (0-indexed).

        Returns
        -------
        tuple of (bool, float)
            Tuple containing boolean decision (True = continue, False = stop)
            and calibrated confidence / empirical accuracy score.
        """
        ...


def ensure_decision_engine(engine: Any | None) -> DecisionEngine | None:
    """Normalise an optional user-supplied object into a DecisionEngine.

    Called at the composition root (``Pipeline.for_task``) to validate protocol
    conformance.

    Parameters
    ----------
    engine : Any or None
        User-supplied engine candidate or None.

    Returns
    -------
    DecisionEngine or None
        The validated decision engine instance, or None if engine was None.

    Raises
    ------
    TypeError
        If engine is not None and does not satisfy the DecisionEngine protocol.
    """
    if engine is None:
        return None
    if isinstance(engine, DecisionEngine):
        return engine
    if (
        callable(getattr(engine, "evaluate_noul", None))
        and callable(getattr(engine, "evaluate_choice", None))
        and callable(getattr(engine, "evaluate_score", None))
    ):
        return engine
    raise TypeError(
        f"{type(engine).__name__} does not satisfy the DecisionEngine protocol: it "
        "must provide async evaluate_noul, evaluate_choice, and evaluate_score methods."
    )
