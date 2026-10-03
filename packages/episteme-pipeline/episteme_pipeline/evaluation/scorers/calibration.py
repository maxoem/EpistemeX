"""Confidence Calibration Evaluator (ECE, MCE, and Brier Score).

Attempts to assess whether extraction and argumentation confidence scores correspond to true empirical probabilities, computing Expected Calibration Error (ECE),
Maximum Calibration Error (MCE), Brier Score, and reliability diagrams.
"""

from __future__ import annotations

import json
from typing import Any, Protocol, Sequence, runtime_checkable
import networkx as nx
import numpy as np
from pydantic import BaseModel, Field

from epistemetrics.core.models import TheoryEdge, TheoryNode
from epistemetrics.graph.theory_graph import TheoryGraph
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryNet,
    TheoryRelation,
)
from episteme_pipeline.evaluation.models import (
    EvaluationLevel,
    EvaluationMetric,
    EvaluationOutcome,
    EvaluationResult,
)


class ReliabilityBin(BaseModel):
    """Statistical summary for a single confidence interval bin in a reliability diagram.

    Parameters
    ----------
    bin_lower : float
        Lower bound of the confidence bin [0.0, 1.0].
    bin_upper : float
        Upper bound of the confidence bin [0.0, 1.0].
    count : int
        Number of predictions assigned to this bin.
    avg_confidence : float
        Mean predicted confidence within the bin.
    accuracy : float
        Empirical accuracy (true positive rate) within the bin.
    calibration_gap : float
        Absolute error |accuracy - avg_confidence|.
    """

    bin_lower: float
    bin_upper: float
    count: int
    avg_confidence: float
    accuracy: float
    calibration_gap: float


class CalibrationResult(BaseModel):
    """Container for probability calibration metrics and reliability diagram data.

    Parameters
    ----------
    ece : float
        Expected Calibration Error (ECE) weighted by bin frequencies.
    mce : float
        Maximum Calibration Error (MCE) across populated bins.
    brier_score : float
        Mean squared error between confidence probabilities and binary outcomes.
    sample_count : int
        Total number of predictions evaluated.
    num_bins : int
        Number of confidence bins configured.
    bins : list of ReliabilityBin
        Sequential confidence interval bins forming the reliability diagram.
    """

    ece: float
    mce: float
    brier_score: float
    sample_count: int
    num_bins: int
    bins: list[ReliabilityBin] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to a serializable dictionary.

        Returns
        -------
        dict of str to Any
            Dictionary representation of calibration metrics.
        """
        return self.model_dump()

    def to_markdown(self) -> str:
        """Format calibration statistics as a Markdown reliability report.

        Returns
        -------
        str
            GitHub-flavored Markdown report.
        """
        lines = [
            "# Confidence Calibration Report",
            "",
            f"- **Expected Calibration Error (ECE):** {self.ece:.4f}",
            f"- **Maximum Calibration Error (MCE):** {self.mce:.4f}",
            f"- **Brier Score:** {self.brier_score:.4f}",
            f"- **Total Evaluated Samples:** {self.sample_count}",
            "",
            "## Reliability Diagram",
            "| Bin Interval | Count | Avg Confidence | Empirical Accuracy | Calibration Gap |",
            "| :---: | :---: | :---: | :---: | :---: |",
        ]
        for b in self.bins:
            if b.count > 0:
                lines.append(
                    f"| `[{b.bin_lower:.2f}, {b.bin_upper:.2f})` | {b.count} | "
                    f"{b.avg_confidence:.4f} | {b.accuracy:.4f} | {b.calibration_gap:.4f} |"
                )
        return "\n".join(lines)


@runtime_checkable
class CalibrationDataExtractor(Protocol):
    """Port defining data extraction interface for calibration scoring.
    """

    def extract_predictions(self, data: Any) -> list[tuple[str, float]]:
        """Extract canonical prediction keys and associated confidence probabilities.

        Parameters
        ----------
        data : Any
            Predicted domain entity, relation, triple, graph, or nested collection.

        Returns
        -------
        list of tuple of (str, float)
            List of (canonical_key, confidence_probability) tuples.
        """
        ...

    def extract_gold_keys(self, data: Any) -> set[str]:
        """Extract canonical keys from ground-truth or reference items.

        Parameters
        ----------
        data : Any
            Reference domain entity, relation, triple, graph, or nested collection.

        Returns
        -------
        set of str
            Set of canonical string keys used for empirical correctness matching.
        """
        ...


class DefaultCalibrationDataExtractor:
    """Default adapter extracting calibration items from domain models and graphs.

    Implements CalibrationDataExtractor for typed contracts (TheoryRelation,
    TheoryAtom, L2Triple), epistemetrics graphs (TheoryGraph, TheoryEdge, TheoryNode),
    NetworkX DiGraphs, and legacy dictionaries without attribute reflection.
    """

    def extract_predictions(self, data: Any) -> list[tuple[str, float]]:
        """Extract canonical keys and confidence probabilities from domain representations.

        Parameters
        ----------
        data : Any
            Domain entity, relation, triple, graph, or nested collection thereof.

        Returns
        -------
        list of tuple of (str, float)
            List of (canonical_key, confidence_score) tuples.
        """
        items: list[tuple[str, float]] = []
        if isinstance(data, (list, tuple, set)):
            for item in data:
                items.extend(self.extract_predictions(item))
            return items

        # Typed Domain Contracts
        if isinstance(data, TheoryRelation):
            key = f"{data.source_id}::{data.relation_type}::{data.target_id}".lower()
            conf = (
                data.calibrated_confidence
                if data.calibrated_confidence is not None
                else (
                    data.empirical_accuracy
                    if data.empirical_accuracy is not None
                    else (
                        data.class_probability
                        if data.class_probability is not None
                        else data.confidence
                    )
                )
            )
            items.append((key, float(conf if conf is not None else 1.0)))
            return items

        if isinstance(data, TheoryAtom):
            key = f"{data.id}::{data.component_type}".lower()
            conf = data.plausibility if data.plausibility is not None else data.confidence
            items.append((key, float(conf if conf is not None else 1.0)))
            return items

        if isinstance(data, L2Triple):
            key = f"{data.subject_id}::{data.predicate}::{data.object_id}".lower()
            items.append((key, float(data.confidence if data.confidence is not None else 1.0)))
            return items

        # Epistemetrics typed domain models
        if isinstance(data, TheoryEdge):
            key = f"{data.source}::{data.relation_type}::{data.target}".lower()
            conf = (
                data.empirical_accuracy
                if data.empirical_accuracy is not None
                else (
                    data.class_probability
                    if data.class_probability is not None
                    else data.confidence
                )
            )
            items.append((key, float(conf if conf is not None else 1.0)))
            return items

        if isinstance(data, TheoryNode):
            key = str(data.id).lower()
            items.append((key, float(data.confidence if data.confidence is not None else 1.0)))
            return items

        if isinstance(data, (L2Entity, L1Chunk)):
            key = str(data.id).lower()
            items.append((key, 1.0))
            return items

        if isinstance(data, TheoryGraph):
            return self.extract_predictions(data.edges)

        if isinstance(data, TheoryNet):
            return self.extract_predictions(data.relations)

        # NetworkX Graphs
        if isinstance(data, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
            for u, v, edge_data in data.edges(data=True):
                lbl = (
                    edge_data.get("relation_type")
                    or edge_data.get("label")
                    or edge_data.get("relation")
                    or ""
                )
                key = f"{u}::{lbl}::{v}".lower()
                conf = float(
                    edge_data.get("calibrated_confidence")
                    or edge_data.get("empirical_accuracy")
                    or edge_data.get("class_probability")
                    or edge_data.get("confidence", 1.0)
                    or 1.0
                )
                items.append((key, conf))
            return items

        # Dictionary representation
        if isinstance(data, dict):
            if "subject_id" in data and "predicate" in data and "object_id" in data:
                key = f"{data['subject_id']}::{data['predicate']}::{data['object_id']}".lower()
                conf = float(data.get("confidence", 1.0) or 1.0)
                items.append((key, conf))
            elif "source_id" in data and "relation_type" in data and "target_id" in data:
                key = f"{data['source_id']}::{data['relation_type']}::{data['target_id']}".lower()
                conf = float(
                    data.get("calibrated_confidence")
                    or data.get("empirical_accuracy")
                    or data.get("class_probability")
                    or data.get("confidence", 1.0)
                    or 1.0
                )
                items.append((key, conf))
            elif "source" in data and "relation_type" in data and "target" in data:
                key = f"{data['source']}::{data['relation_type']}::{data['target']}".lower()
                conf = float(
                    data.get("calibrated_confidence")
                    or data.get("empirical_accuracy")
                    or data.get("class_probability")
                    or data.get("confidence", 1.0)
                    or 1.0
                )
                items.append((key, conf))
            elif "id" in data:
                key = str(data["id"]).lower()
                conf = float(data.get("confidence", 1.0) or 1.0)
                items.append((key, conf))

        return items

    def extract_gold_keys(self, data: Any) -> set[str]:
        """Extract canonical keys from reference items or graphs.

        Parameters
        ----------
        data : Any
            Domain entity, relation, triple, graph, or nested collection thereof.

        Returns
        -------
        set of str
            Canonical string keys for matching with predicted items.
        """
        keys: set[str] = set()
        if isinstance(data, (list, tuple, set)):
            for item in data:
                keys.update(self.extract_gold_keys(item))
            return keys

        # Typed Domain Contracts
        if isinstance(data, TheoryRelation):
            keys.add(f"{data.source_id}::{data.relation_type}::{data.target_id}".lower())
            return keys

        if isinstance(data, TheoryAtom):
            keys.add(str(data.id).lower())
            return keys

        if isinstance(data, L2Triple):
            keys.add(f"{data.subject_id}::{data.predicate}::{data.object_id}".lower())
            return keys

        # Epistemetrics typed domain models
        if isinstance(data, TheoryEdge):
            keys.add(f"{data.source}::{data.relation_type}::{data.target}".lower())
            return keys

        if isinstance(data, TheoryNode):
            keys.add(str(data.id).lower())
            return keys

        if isinstance(data, (L2Entity, L1Chunk)):
            keys.add(str(data.id).lower())
            return keys

        if isinstance(data, TheoryGraph):
            return self.extract_gold_keys(data.edges)

        if isinstance(data, TheoryNet):
            return self.extract_gold_keys(data.relations)

        # NetworkX Graphs
        if isinstance(data, (nx.Graph, nx.DiGraph, nx.MultiGraph, nx.MultiDiGraph)):
            for u, v, edge_data in data.edges(data=True):
                lbl = (
                    edge_data.get("relation_type")
                    or edge_data.get("label")
                    or edge_data.get("relation")
                    or ""
                )
                keys.add(f"{u}::{lbl}::{v}".lower())
            return keys

        # Dictionary representation
        if isinstance(data, dict):
            if "subject_id" in data and "predicate" in data and "object_id" in data:
                keys.add(f"{data['subject_id']}::{data['predicate']}::{data['object_id']}".lower())
            elif "source_id" in data and "relation_type" in data and "target_id" in data:
                keys.add(f"{data['source_id']}::{data['relation_type']}::{data['target_id']}".lower())
            elif "source" in data and "relation_type" in data and "target" in data:
                keys.add(f"{data['source']}::{data['relation_type']}::{data['target']}".lower())
            elif "id" in data:
                keys.add(str(data["id"]).lower())

        return keys


def compute_calibration_metrics(
    confidences: Sequence[float],
    labels: Sequence[int | bool | float],
    num_bins: int = 10,
) -> CalibrationResult:
    """Compute calibration metrics from raw confidences and binary ground-truth labels.

    Pure mathematical calculation of Expected Calibration Error (ECE),
    Maximum Calibration Error (MCE), Brier Score, and reliability diagram bins.
    Independent of domain models and extraction mechanisms.

    Parameters
    ----------
    confidences : Sequence of float
        Predicted confidence scores $p_i \\in [0.0, 1.0]$.
    labels : Sequence of int, bool, or float
        Binary ground-truth indicators $y_i \\in \\{0, 1\\}$.
    num_bins : int, default 10
        Number of equal-width probability bins over [0.0, 1.0].

    Returns
    -------
    CalibrationResult
        Evaluated ECE, MCE, Brier Score, and reliability bins.

    Raises
    ------
    ValueError
        If num_bins is non-positive or if confidences and labels have mismatched lengths.
    """
    if num_bins <= 0:
        raise ValueError("num_bins must be a positive integer.")

    if len(confidences) != len(labels):
        raise ValueError(
            f"Confidences ({len(confidences)}) and labels ({len(labels)}) must have matching length."
        )

    n = len(confidences)
    if n == 0:
        return CalibrationResult(
            ece=0.0,
            mce=0.0,
            brier_score=0.0,
            sample_count=0,
            num_bins=num_bins,
            bins=[],
        )

    confs = np.clip(np.asarray(confidences, dtype=np.float64), 0.0, 1.0)
    labs = np.asarray([1.0 if bool(y) else 0.0 for y in labels], dtype=np.float64)

    # Brier Score = (1/N) * sum((p_i - y_i)^2)
    brier_score = float(np.mean((confs - labs) ** 2))

    bin_edges = np.linspace(0.0, 1.0, num_bins + 1)
    bins_data: list[ReliabilityBin] = []
    weighted_ece = 0.0
    max_gap = 0.0

    for i in range(num_bins):
        lower = float(bin_edges[i])
        upper = float(bin_edges[i + 1])

        if i == num_bins - 1:
            mask = (confs >= lower) & (confs <= upper)
        else:
            mask = (confs >= lower) & (confs < upper)

        count = int(np.sum(mask))
        if count > 0:
            avg_conf = float(np.mean(confs[mask]))
            acc = float(np.mean(labs[mask]))
            gap = float(abs(acc - avg_conf))
            weighted_ece += (count / n) * gap
            if gap > max_gap:
                max_gap = gap
        else:
            avg_conf = (lower + upper) / 2.0
            acc = 0.0
            gap = 0.0

        bins_data.append(
            ReliabilityBin(
                bin_lower=lower,
                bin_upper=upper,
                count=count,
                avg_confidence=avg_conf,
                accuracy=acc,
                calibration_gap=gap,
            )
        )

    return CalibrationResult(
        ece=weighted_ece,
        mce=max_gap,
        brier_score=brier_score,
        sample_count=n,
        num_bins=num_bins,
        bins=bins_data,
    )


class CalibrationScorer:
    """Evaluates probability calibration for extraction and argumentation predictions.

    Computes ECE, MCE, and Brier Score over confidence-binned predictions to detect
    overconfidence and hallucination risks.

    Parameters
    ----------
    num_bins : int, default 10
        Number of equal-width probability bins over [0.0, 1.0].
    max_ece_threshold : float, default 0.15
        Acceptance threshold for Expected Calibration Error.
    max_brier_threshold : float, default 0.25
        Acceptance threshold for Brier Score.
    extractor : CalibrationDataExtractor or None, default None
        Port adapter used to extract predictions and reference elements.
        If None, defaults to DefaultCalibrationDataExtractor.
    """

    def __init__(
        self,
        num_bins: int = 10,
        max_ece_threshold: float = 0.15,
        max_brier_threshold: float = 0.25,
        extractor: CalibrationDataExtractor | None = None,
    ) -> None:
        if num_bins <= 0:
            raise ValueError("num_bins must be a positive integer.")
        self.num_bins = num_bins
        self.max_ece_threshold = max_ece_threshold
        self.max_brier_threshold = max_brier_threshold
        self.extractor: CalibrationDataExtractor = (
            extractor if extractor is not None else DefaultCalibrationDataExtractor()
        )

    def compute_calibration(
        self,
        confidences: Sequence[float],
        labels: Sequence[int | bool | float],
    ) -> CalibrationResult:
        """Compute calibration metrics from raw confidences and binary ground-truth labels.

        Parameters
        ----------
        confidences : Sequence of float
            Predicted confidence scores $p_i \\in [0.0, 1.0]$.
        labels : Sequence of int, bool, or float
            Binary ground-truth indicators $y_i \\in \\{0, 1\\}$.

        Returns
        -------
        CalibrationResult
            Evaluated ECE, MCE, Brier Score, and reliability bins.

        Raises
        ------
        ValueError
            If confidences and labels have mismatched lengths.
        """
        return compute_calibration_metrics(
            confidences=confidences,
            labels=labels,
            num_bins=self.num_bins,
        )

    def evaluate(
        self,
        predicted: Any,
        gold: Any,
    ) -> CalibrationResult:
        """Evaluate calibration by aligning predicted items against reference gold items.

        Extracts confidence scores from predicted triples or relations via the
        configured extractor port, assigns binary match indicators against reference
        elements, and evaluates calibration.

        Parameters
        ----------
        predicted : Any
            Predicted triples, relations, or graph containing confidence attributes.
        gold : Any
            Reference gold items or graph.

        Returns
        -------
        CalibrationResult
            Computed calibration results.
        """
        confs: list[float] = []
        labels: list[int] = []

        # If direct tuple/list of (conf, label) is supplied
        if (
            isinstance(predicted, (list, tuple))
            and predicted
            and isinstance(predicted[0], (tuple, list))
            and len(predicted[0]) == 2
        ):
            for p, y in predicted:
                confs.append(float(p))
                labels.append(1 if y else 0)
            return self.compute_calibration(confs, labels)

        # Extract predictions with confidences via extractor port
        pred_items = self.extractor.extract_predictions(predicted)
        gold_keys = self.extractor.extract_gold_keys(gold)

        for key, conf in pred_items:
            confs.append(conf)
            labels.append(1 if key in gold_keys else 0)

        return self.compute_calibration(confs, labels)

    def evaluate_to_result(
        self,
        predicted: Any,
        gold: Any,
        run_id: str = "eval_run",
        phase_name: str = "Confidence Calibration",
        dataset_ref: str | None = None,
    ) -> EvaluationResult:
        """Evaluate probability calibration and package directly into an EvaluationResult.

        Parameters
        ----------
        predicted : Any
            Predicted representations with confidences.
        gold : Any
            Reference gold standard items.
        run_id : str, default 'eval_run'
            Target run identifier.
        phase_name : str, default 'Confidence Calibration'
            Pipeline phase name.
        dataset_ref : str or None, optional
            Dataset reference identifier.

        Returns
        -------
        EvaluationResult
            Structured result containing ECE, MCE, Brier Score, and reliability diagram.
        """
        cal_res = self.evaluate(predicted, gold)
        passes_ece = cal_res.ece <= self.max_ece_threshold
        passes_brier = cal_res.brier_score <= self.max_brier_threshold
        outcome = (
            EvaluationOutcome.PASS
            if (passes_ece and passes_brier)
            else EvaluationOutcome.WARNING
            if passes_ece
            else EvaluationOutcome.FAIL
        )

        metrics = [
            EvaluationMetric(
                name="ece",
                value=cal_res.ece,
                unit="ratio",
                threshold=self.max_ece_threshold,
                passes_threshold=passes_ece,
            ),
            EvaluationMetric(
                name="mce",
                value=cal_res.mce,
                unit="ratio",
            ),
            EvaluationMetric(
                name="brier_score",
                value=cal_res.brier_score,
                unit="score",
                threshold=self.max_brier_threshold,
                passes_threshold=passes_brier,
            ),
        ]

        diagram_dicts = [b.model_dump() for b in cal_res.bins]
        notes = {
            "markdown_report": cal_res.to_markdown(),
            "sample_count": str(cal_res.sample_count),
            "reliability_diagram": json.dumps(diagram_dicts),
        }

        return EvaluationResult(
            run_id=run_id,
            evaluation_level=EvaluationLevel.STAGE,
            phase_name=phase_name,
            dataset_ref=dataset_ref,
            metrics=metrics,
            notes=notes,
            outcome=outcome,
            reliability_diagram=diagram_dicts,
        )

    def _extract_confidence_items(self, obj: Any) -> list[tuple[str, float]]:
        """Extract canonical keys and confidence scores via the extractor adapter.

        Provided for backward compatibility with existing callers.

        Parameters
        ----------
        obj : Any
            Domain entity, relation, triple, graph, or nested collection thereof.

        Returns
        -------
        list of tuple of (str, float)
            List of (canonical_key, confidence_score) tuples.
        """
        return self.extractor.extract_predictions(obj)

    def _extract_gold_keys(self, obj: Any) -> set[str]:
        """Extract canonical keys from reference items via the extractor adapter.

        Provided for backward compatibility with existing callers.

        Parameters
        ----------
        obj : Any
            Domain entity, relation, triple, graph, or nested collection thereof.

        Returns
        -------
        set of str
            Canonical string keys for matching with predicted items.
        """
        return self.extractor.extract_gold_keys(obj)


__all__ = [
    "CalibrationDataExtractor",
    "CalibrationResult",
    "CalibrationScorer",
    "DefaultCalibrationDataExtractor",
    "ReliabilityBin",
    "compute_calibration_metrics",
]
