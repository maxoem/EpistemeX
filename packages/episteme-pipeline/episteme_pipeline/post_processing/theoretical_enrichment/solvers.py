"""Tenability optimization solvers for local and constraint evaluation.

Implements structuralist blur minimization (Stegmüller, 1976; Balzer et al., 1987)
over uniformities u_delta, computing the supremum score:
    TS_local(y, M) = sup { 1 - delta | exists x* in M : (Phi(y), x*) in u_delta }
and edge constraint tenability:
    TS_edge(e) = sup { 1 - delta_C | (Phi(y_a), Phi(y_b)) in v_{delta_C} }.
"""

from __future__ import annotations

import ast
import logging
import math
from typing import Any

from episteme_pipeline.contracts.domain import TenabilityResult, TheoryRelation
from episteme_pipeline.post_processing.theoretical_enrichment.enrichment_models import (
    TheoryElementDefinition,
)
from episteme_pipeline.protocols.fingerprint import Fingerprintable

logger = logging.getLogger(__name__)


class SafeFormulaEvaluator:
    """Safe AST-based evaluator for induced mathematical constraint laws.

    Evaluates symbolic arithmetic and functional constraints without using Python's
    eval() function, preventing code injection and syntax crashes.
    """

    _ALLOWED_CALLS = {
        "abs": abs,
        "min": min,
        "max": max,
        "sqrt": lambda x: math.sqrt(max(0.0, float(x))),
    }

    @classmethod
    def evaluate(cls, expression: str, parameters: dict[str, Any]) -> float:
        """Evaluate a constraint expression and return deviation >= 0.0.

        Parameters
        ----------
        expression : str
            Symbolic formula (e.g. 'abs(dopamine - amygdala) * 0.5').
        parameters : dict[str, Any]
            Dictionary of parameter names to numeric values.

        Returns
        -------
        float
            Computed deviation (0.0 represents exact satisfaction).
        """
        if not expression or not expression.strip():
            return 0.0

        try:
            tree = ast.parse(expression.strip(), mode="eval")
            param_lower = {k.lower(): float(v) for k, v in parameters.items() if isinstance(v, (int, float))}
            val = cls._eval_node(tree.body, param_lower, parameters)
            return abs(float(val))
        except Exception as err:
            logger.warning("SafeFormulaEvaluator failed on '%s': %s", expression, err)
            return 1.0

    @classmethod
    def _eval_node(cls, node: ast.AST, param_lower: dict[str, float], raw_params: dict[str, Any]) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant type: {type(node.value)}")

        if isinstance(node, ast.Name):
            name = node.id
            if name in raw_params and isinstance(raw_params[name], (int, float)):
                return float(raw_params[name])
            if name.lower() in param_lower:
                return param_lower[name.lower()]
            return 0.0

        if isinstance(node, ast.UnaryOp):
            operand = cls._eval_node(node.operand, param_lower, raw_params)
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.USub):
                return -operand
            raise ValueError(f"Unsupported unary operator: {type(node.op)}")

        if isinstance(node, ast.BinOp):
            left = cls._eval_node(node.left, param_lower, raw_params)
            right = cls._eval_node(node.right, param_lower, raw_params)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right if right != 0.0 else 1.0
            if isinstance(node.op, ast.Pow):
                return left ** right
            raise ValueError(f"Unsupported binary operator: {type(node.op)}")

        if isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else None
            if func_name in cls._ALLOWED_CALLS:
                args = [cls._eval_node(arg, param_lower, raw_params) for arg in node.args]
                return float(cls._ALLOWED_CALLS[func_name](*args))
            raise ValueError(f"Unsupported function call: {func_name}")

        if isinstance(node, ast.Compare):
            left = cls._eval_node(node.left, param_lower, raw_params)
            if len(node.comparators) == 1 and len(node.ops) == 1:
                right = cls._eval_node(node.comparators[0], param_lower, raw_params)
                op = node.ops[0]
                if isinstance(op, ast.Eq):
                    return abs(left - right)
                if isinstance(op, (ast.Lt, ast.LtE)):
                    return max(0.0, left - right)
                if isinstance(op, (ast.Gt, ast.GtE)):
                    return max(0.0, right - left)
            raise ValueError("Unsupported comparison expression")

        raise ValueError(f"Unsupported AST node: {type(node)}")


def evaluate_formula_safely(expression: str, parameters: dict[str, Any]) -> float:
    """Safe evaluation helper for formula expressions."""
    return SafeFormulaEvaluator.evaluate(expression, parameters)


class TenabilitySolver(Fingerprintable):
    """Solver for local and intertheoretical tenability optimization.

    Parameters
    ----------
    anomaly_threshold : float, optional
        Threshold below which scores are flagged as anomalies, by default 0.5.
    weight_local : float, optional
        Relative weight for local law satisfaction, by default 0.5.
    weight_edge : float, optional
        Relative weight for intertheoretical / constraint consistency, by default 0.5.
    """

    def __init__(
        self,
        anomaly_threshold: float = 0.5,
        weight_local: float = 0.5,
        weight_edge: float = 0.5,
    ) -> None:
        self.anomaly_threshold = anomaly_threshold
        total_w = weight_local + weight_edge
        self.weight_local = weight_local / total_w if total_w > 0 else 0.5
        self.weight_edge = weight_edge / total_w if total_w > 0 else 0.5

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic fingerprint representation of the solver.

        Returns
        -------
        dict[str, Any]
            Deterministic component configuration dictionary.
        """
        return {
            "type": self.__class__.__name__,
            "anomaly_threshold": self.anomaly_threshold,
            "weight_local": self.weight_local,
            "weight_edge": self.weight_edge,
        }

    def solve_local_tenability(
        self,
        parameters: dict[str, Any],
        theory: TheoryElementDefinition,
    ) -> tuple[float, float, list[str]]:
        """Calculate the tightest admissible blur delta* and TS_local score.

        Parameters
        ----------
        parameters : dict[str, Any]
            The postulated theoretical parameters.
        theory : TheoryElementDefinition
            Target theory definition with its core laws M.

        Returns
        -------
        tuple[float, float, list[str]]
            Tuple of (TS_local, delta_star, anomalies).
        """
        if not theory.laws:
            return 1.0, 0.0, []

        deviations: list[float] = []
        anomalies: list[str] = []

        for law in theory.laws:
            dev = law.compute_deviation(parameters)
            deviations.append(dev)
            if dev > theory.max_admissible_blur * self.anomaly_threshold:
                anomalies.append(
                    f"Law '{law.law_id}' deviation {dev:.3f} exceeds threshold "
                    f"under parameters {parameters}"
                )

        delta_star = max(deviations) if deviations else 0.0
        ts_local = max(0.0, min(1.0, 1.0 - (delta_star / theory.max_admissible_blur)))

        if ts_local < self.anomaly_threshold:
            anomalies.append(
                f"Theory '{theory.name}' exhibits low local tenability (TS_local = {ts_local:.3f} < {self.anomaly_threshold})"
            )

        return round(ts_local, 3), round(delta_star, 3), anomalies

    def solve_edge_tenability(
        self,
        source_params: dict[str, Any],
        target_params: dict[str, Any],
        relation: TheoryRelation,
    ) -> tuple[float, float, list[str]]:
        """Evaluate constraint or intertheoretical consistency across an edge.

        Under constraint blurs v_{delta_C}, calculates:
            TS_edge(e) = sup { 1 - delta_C | (Phi(y_a), Phi(y_b)) in v_{delta_C} }

        Parameters
        ----------
        source_params : dict[str, Any]
            Parameters postulated at the source theory/cluster.
        target_params : dict[str, Any]
            Parameters postulated at the target theory/cluster.
        relation : TheoryRelation
            The intertheoretical or constraint relation.

        Returns
        -------
        tuple[float, float, list[str]]
            Tuple of (TS_edge, delta_c, anomalies).
        """
        rel_type = relation.relation_type.upper()
        anomalies: list[str] = []
        deltas: list[float] = []

        shared_keys = set(source_params.keys()) & set(target_params.keys())
        for k in shared_keys:
            val_s = source_params[k]
            val_t = target_params[k]
            if isinstance(val_s, (int, float)) and isinstance(val_t, (int, float)):
                diff = abs(float(val_s) - float(val_t))
                deltas.append(diff)

        if not shared_keys:
            repression = source_params.get("RepressionMagnitude") or target_params.get("RepressionMagnitude")
            amygdala = source_params.get("AmygdalaHyperactivity") or target_params.get("AmygdalaHyperactivity")
            dopamine = source_params.get("DopamineDepletion") or target_params.get("DopamineDepletion")

            if repression is not None and amygdala is not None:
                diff = abs(float(repression) - float(amygdala))
                deltas.append(diff)
            elif repression is not None and dopamine is not None:
                diff = abs(float(repression) - float(dopamine))
                deltas.append(diff)

        delta_c = max(deltas) if deltas else 0.0
        ts_edge = max(0.0, min(1.0, 1.0 - delta_c))

        if ts_edge < self.anomaly_threshold:
            anomalies.append(
                f"Constraint edge '{rel_type}' between {relation.source_id} and {relation.target_id} "
                f"is untenable (TS_edge = {ts_edge:.3f}, delta_C = {delta_c:.3f})"
            )

        return round(ts_edge, 3), round(delta_c, 3), anomalies

    def evaluate_theory_tenability(
        self,
        local_score: float,
        edge_scores: dict[str, float],
        delta_star: float,
        local_anomalies: list[str],
        edge_anomalies: list[str],
    ) -> TenabilityResult:
        """Combine local and edge scores into a final TenabilityResult.

        Parameters
        ----------
        local_score : float
            Local law adherence score (TS_local).
        edge_scores : dict[str, float]
            Map of relation_id -> TS_edge.
        delta_star : float
            Tightest admissible blur found.
        local_anomalies : list[str]
            Local law violation notices.
        edge_anomalies : list[str]
            Constraint violation notices.

        Returns
        -------
        TenabilityResult
            Complete aggregated result.
        """
        avg_edge = (
            sum(edge_scores.values()) / len(edge_scores)
            if edge_scores
            else 1.0
        )

        aggregated = round(
            (self.weight_local * local_score) + (self.weight_edge * avg_edge), 3
        )
        is_tenable = aggregated >= self.anomaly_threshold
        all_anomalies = local_anomalies + edge_anomalies

        return TenabilityResult(
            local_score=local_score,
            edge_scores=edge_scores,
            aggregated_score=aggregated,
            is_tenable=is_tenable,
            tightest_blur=delta_star,
            anomalies=all_anomalies,
        )
