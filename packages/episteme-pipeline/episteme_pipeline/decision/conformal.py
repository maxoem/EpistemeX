"""Distribution-free conformal prediction calibration engine (ISSUE-046).

This module implements Split Conformal Prediction for categorical and structured
decision engine outputs. It replaces brittle scalar thresholds with adaptive
prediction sets guaranteeing finite-sample coverage 1 - alpha >= 0.95.
"""

from __future__ import annotations

import math
import numpy as np

from episteme_pipeline.protocols.decision import DecisionScore


class ConformalCalibrator:
    """Split Conformal Prediction calibrator for classification distributions.

    Computes distribution-free prediction sets C(X) subseteq Y guaranteeing
    P(Y in C(X)) >= 1 - alpha over exchangeable state evaluations.

    Parameters
    ----------
    alpha : float, default 0.05
        Target significance error level (coverage guarantee 1 - alpha).
    q_hat : float or None, default None
        Pre-computed non-conformity quantile cutoff. If None, calibration
        is performed on empirical non-conformity scores via :meth:`calibrate`,
        or defaults to adaptive cumulative mass accumulation.
    """

    def __init__(self, alpha: float = 0.05, q_hat: float | None = None) -> None:
        self.alpha = alpha
        self.q_hat = q_hat

    def calibrate(
        self,
        calibration_scores: list[float] | np.ndarray,
        alpha: float | None = None,
    ) -> float:
        """Calibrate the non-conformity threshold on a held-out calibration split.

        Given non-conformity scores s_i = 1 - P_hat(y_true | x_i), computes the
        empirical quantile at level ceil((n + 1)(1 - alpha)) / n.

        Parameters
        ----------
        calibration_scores : list of float or np.ndarray
            Non-conformity scores s_i = 1 - P_hat(y_i | x_i) on calibration points.
        alpha : float or None, default None
            Optional override for the significance level.

        Returns
        -------
        float
            The calibrated empirical quantile cutoff q_hat.

        Raises
        ------
        ValueError
            If calibration_scores is empty.
        """
        if len(calibration_scores) == 0:
            raise ValueError("calibration_scores cannot be empty for conformal calibration.")

        effective_alpha = alpha if alpha is not None else self.alpha
        scores = np.sort(np.asarray(calibration_scores, dtype=np.float64))
        n = len(scores)

        target_idx = math.ceil((n + 1) * (1.0 - effective_alpha))
        if target_idx > n:
            q_val = 1.0
        else:
            q_val = float(scores[target_idx - 1])

        self.q_hat = q_val
        self.alpha = effective_alpha
        return q_val

    def predict_set(
        self,
        score: DecisionScore,
        alpha: float | None = None,
    ) -> list[str]:
        """Compute the conformal prediction set C(x) for a predicted distribution.

        Parameters
        ----------
        score : DecisionScore
            A :class:`DecisionScore` contract instance.
        alpha : float or None, default None
            Optional significance level override.

        Returns
        -------
        list of str
            Subset of candidate labels included in the conformal prediction set C(X).
        """
        effective_alpha = alpha if alpha is not None else self.alpha

        # If the engine already computed a prediction set under matching alpha, we can use it
        if score.prediction_set is not None and self.q_hat is None:
            return score.prediction_set

        probabilities = score.probabilities
        if not probabilities:
            if score.selected_option is not None:
                return [str(score.selected_option)]
            return []

        sorted_items = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)

        if self.q_hat is not None:
            # Calibrated quantile: C(x) = { y in Y | P_hat(y|x) >= 1 - q_hat }
            threshold = 1.0 - self.q_hat
            prediction_set = [label for label, prob in sorted_items if prob >= threshold]
            # Guarantee at least the argmax if none strictly exceed due to rounding
            if not prediction_set and sorted_items:
                prediction_set = [sorted_items[0][0]]
            return prediction_set

        # Uncalibrated fallback: Cumulative mass accumulation up to 1 - alpha (APS)
        target_mass = 1.0 - effective_alpha
        cum_sum = 0.0
        prediction_set = []

        for label, prob in sorted_items:
            prediction_set.append(label)
            cum_sum += prob
            if cum_sum >= target_mass:
                break

        return prediction_set

    @staticmethod
    def is_singleton(prediction_set: list[str]) -> bool:
        """Check whether the conformal prediction set contains exactly one label.

        Parameters
        ----------
        prediction_set : list of str
            The prediction set C(X).

        Returns
        -------
        bool
            True if exactly one option is predicted, indicating an unambiguous decision.
        """
        return len(prediction_set) == 1

    @classmethod
    def triage(cls, prediction_set: list[str]) -> str:
        """Evaluate triage routing based on the cardinality of the prediction set.

        Parameters
        ----------
        prediction_set : list of str
            Conformal prediction set C(X).

        Returns
        -------
        str
            'fast_exit' if singleton, 'escalate_to_system2' if ambiguous or empty.
        """
        if cls.is_singleton(prediction_set):
            return "fast_exit"
        return "escalate_to_system2"
