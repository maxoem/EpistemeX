"""Distribution-free conformal prediction calibration engine (ISSUE-046, ISSUE-049).

This module implements Split Conformal Prediction for categorical and structured
decision engine outputs. It replaces brittle scalar thresholds with adaptive
prediction sets guaranteeing finite-sample coverage 1 - alpha >= 0.95.
Supports Mondrian (task- and language-stratified) calibration (Vovk et al. 2005).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from episteme_pipeline.protocols.decision import DecisionScore
from episteme_pipeline.protocols.fingerprint import Fingerprintable


class ConformalCalibrator(Fingerprintable):
    """Mondrian Split Conformal Prediction calibrator for classification distributions.

    Computes distribution-free prediction sets C(X) subseteq Y guaranteeing
    P(Y in C(X)) >= 1 - alpha over exchangeable state evaluations, stratified
    by task and language (Mondrian Conformal Prediction, Vovk et al. 2005).

    Parameters
    ----------
    alpha : float, default 0.05
        Target significance error level (coverage guarantee 1 - alpha).
    q_hat : float or None, default None
        Global pre-computed non-conformity quantile cutoff. If None, calibration
        is performed on empirical non-conformity scores via :meth:`calibrate`,
        or defaults to adaptive cumulative mass accumulation.
    stratified_q_hat : dict or None, default None
        Pre-computed stratified quantiles keyed by task_id or (task_id, language).
    """

    def __init__(
        self,
        alpha: float = 0.05,
        q_hat: float | None = None,
        stratified_q_hat: dict[str, float] | dict[tuple[str, str], float] | None = None,
    ) -> None:
        self.alpha = alpha
        self.q_hat = q_hat
        self._stratified_q_hat: dict[tuple[str | None, str | None], float] = {}
        self._stratified_meta: dict[tuple[str | None, str | None], dict[str, Any]] = {}
        self._global_n_cal: int = 0
        self._global_dataset_sha256: str = ""

        if stratified_q_hat:
            for k, v in stratified_q_hat.items():
                if isinstance(k, tuple):
                    self._stratified_q_hat[(k[0], k[1])] = v
                else:
                    self._stratified_q_hat[(str(k), None)] = v

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic JSON-serializable calibration state representation.

        Returns
        -------
        dict of str to Any
            Deterministic dictionary containing Mondrian calibration metadata
            and task-partitioned quantile cutoffs.
        """
        calibration_state: dict[str, Any] = {}
        for (task, lang), q in sorted(
            self._stratified_q_hat.items(),
            key=lambda item: (item[0][0] or "", item[0][1] or ""),
        ):
            meta = self._stratified_meta.get((task, lang), {})
            key = f"{task}_{lang}" if (task and lang) else (task or lang or "global")
            calibration_state[key] = {
                "q_hat": q,
                "n_cal": meta.get("n_cal", 0),
                "dataset_sha256": meta.get("dataset_sha256", ""),
            }
        if self.q_hat is not None and "global" not in calibration_state:
            calibration_state["global"] = {
                "q_hat": self.q_hat,
                "n_cal": self._global_n_cal,
                "dataset_sha256": self._global_dataset_sha256,
            }
        return {
            "class": self.__class__.__name__,
            "alpha": self.alpha,
            "calibration_state": calibration_state,
        }

    def calibrate(
        self,
        calibration_scores: list[float] | np.ndarray,
        alpha: float | None = None,
        task_id: str | None = None,
        language: str | None = None,
        dataset_sha256: str | None = None,
    ) -> float:
        """Calibrate the non-conformity threshold on a held-out calibration split.

        Given non-conformity scores s_i = 1 - P_hat(y_true | x_i), computes the
        empirical quantile at level ceil((n + 1)(1 - alpha)) / n, optionally
        partitioned by task_id and language (Mondrian split).

        Parameters
        ----------
        calibration_scores : list of float or np.ndarray
            Non-conformity scores s_i = 1 - P_hat(y_i | x_i) on calibration points.
        alpha : float or None, default None
            Optional override for the significance level.
        task_id : str or None, optional
            Task identifier to calibrate (e.g. 'p2_linking', 'p4_acc', 'p4_arc').
        language : str or None, optional
            Language identifier ('de', 'en').
        dataset_sha256 : str or None, optional
            SHA-256 fingerprint of the calibration dataset D_cal for provenance.

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

        if task_id is not None or language is not None:
            norm_lang = language.lower() if language else None
            self._stratified_q_hat[(task_id, norm_lang)] = q_val
            self._stratified_meta[(task_id, norm_lang)] = {
                "n_cal": n,
                "dataset_sha256": dataset_sha256 or "",
            }
        else:
            self.q_hat = q_val
            self._global_n_cal = n
            self._global_dataset_sha256 = dataset_sha256 or ""

        self.alpha = effective_alpha
        return q_val

    def get_q_hat(
        self,
        task_id: str | None = None,
        language: str | None = None,
    ) -> float | None:
        """Lookup the calibrated non-conformity cutoff for a task and language.

        Resolution order:
        1. Exact (task_id, language)
        2. Task-only (task_id, None)
        3. Language-only (None, language)
        4. Global self.q_hat

        Parameters
        ----------
        task_id : str or None, optional
            Task identifier.
        language : str or None, optional
            Language code ('de', 'en').

        Returns
        -------
        float or None
            Calibrated quantile cutoff q_hat, or None if uncalibrated.
        """
        norm_lang = language.lower() if language else None

        # 1. Exact match
        if (task_id, norm_lang) in self._stratified_q_hat:
            return self._stratified_q_hat[(task_id, norm_lang)]

        # 2. Task only
        if task_id is not None and (task_id, None) in self._stratified_q_hat:
            return self._stratified_q_hat[(task_id, None)]

        # 3. Language only
        if norm_lang is not None and (None, norm_lang) in self._stratified_q_hat:
            return self._stratified_q_hat[(None, norm_lang)]

        # 4. Global
        return self.q_hat

    def predict_set(
        self,
        score: DecisionScore,
        alpha: float | None = None,
        task_id: str | None = None,
        language: str | None = None,
    ) -> list[str]:
        """Compute the conformal prediction set C(x) for a predicted distribution.

        Parameters
        ----------
        score : DecisionScore
            A :class:`DecisionScore` contract instance.
        alpha : float or None, default None
            Optional significance level override.
        task_id : str or None, optional
            Task identifier for stratified calibration lookup.
        language : str or None, optional
            Language code for stratified calibration lookup.

        Returns
        -------
        list of str
            Subset of candidate labels included in the conformal prediction set C(X).
        """
        effective_alpha = alpha if alpha is not None else self.alpha
        effective_q_hat = self.get_q_hat(task_id, language)

        # If the engine already computed a prediction set under matching alpha, we can use it
        if score.prediction_set is not None and effective_q_hat is None:
            return score.prediction_set

        probabilities = score.probabilities
        if not probabilities:
            if score.selected_option is not None:
                return [str(score.selected_option)]
            return []

        sorted_items = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)

        if effective_q_hat is not None:
            # Calibrated quantile: C(x) = { y in Y | P_hat(y|x) >= 1 - q_hat }
            threshold = 1.0 - effective_q_hat
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
