"""Model Component Decomposition Scorer.

Bridges epistemetrics sovereign model evaluation (Bourbaki structuralist decomposition,
capability subsumption verification G_pred >=cap G_ref) to the pipeline evaluation harness.
"""

from __future__ import annotations

from pathlib import Path

import epistemetrics as em
import networkx as nx
from epistemetrics.epistemic.model_evaluation import ModelComponentEvaluationResult

from episteme_pipeline.artifacts.execution import ArtifactCollection
from episteme_pipeline.contracts.domain import TheoryNet
from episteme_pipeline.evaluation.benchmarks.structuralist import (
    load_structuralist_benchmark,
    structuralist_digraph_to_theory_graph,
)
from episteme_pipeline.evaluation.models import (
    EvaluationErrorBucket,
    EvaluationLevel,
    EvaluationMetric,
    EvaluationOutcome,
    EvaluationResult,
)
from episteme_pipeline.evaluation.scorers.domain_bridge import (
    artifact_collection_to_theory_graph,
    theory_net_to_theory_graph,
)


class ModelScorer:
    """Evaluates formal Bourbaki structuralist model component decomposition."""

    def __init__(
        self,
        min_mcc: float = 1.0,
        min_pfs: float = 0.8,
        sim_threshold: float = 0.50,
    ) -> None:
        """Initialize the model component scorer.

        Parameters
        ----------
        min_mcc : float, optional
            Minimum Model Component Completeness required for subsumption (default: 1.0).
        min_pfs : float, optional
            Minimum Property Fidelity Score required for subsumption (default: 0.8).
        sim_threshold : float, optional
            Minimum node similarity threshold (default: 0.50).
        """
        self.min_mcc = min_mcc
        self.min_pfs = min_pfs
        self.sim_threshold = sim_threshold

    def evaluate(
        self,
        predicted: ArtifactCollection | TheoryNet | em.TheoryGraph | nx.DiGraph,
        gold: str | Path | em.TheoryGraph | nx.DiGraph,
    ) -> ModelComponentEvaluationResult:
        """Evaluate predicted graph or pipeline artifacts against reference gold graph.

        Parameters
        ----------
        predicted : ArtifactCollection, TheoryNet, em.TheoryGraph, or nx.DiGraph
            Predicted representation from pipeline execution.
        gold : str, Path, em.TheoryGraph, or nx.DiGraph
            Gold standard reference graph or filesystem path to an STNB JSON-LD envelope.

        Returns
        -------
        ModelComponentEvaluationResult
            Evaluation results containing MCC, AOR, PFS, AG_IoU, and subsumption status.
        """
        pred_graph = self._ensure_theory_graph(predicted, name="PredictedTheoryGraph")
        gold_graph = self._ensure_gold_theory_graph(gold, name="GoldReferenceGraph")

        return em.evaluate_model_components(
            pred_graph=pred_graph,
            ref_graph=gold_graph,
            min_mcc=self.min_mcc,
            min_pfs=self.min_pfs,
            sim_threshold=self.sim_threshold,
        )

    def evaluate_to_result(
        self,
        predicted: ArtifactCollection | TheoryNet | em.TheoryGraph | nx.DiGraph,
        gold: str | Path | em.TheoryGraph | nx.DiGraph,
        run_id: str = "eval_run",
        phase_name: str = "Phase 6: TheoryNet Projection",
        dataset_ref: str | None = None,
    ) -> EvaluationResult:
        """Evaluate and format directly into an EvaluationResult model.

        Parameters
        ----------
        predicted : ArtifactCollection, TheoryNet, em.TheoryGraph, or nx.DiGraph
            Predicted pipeline artifact or graph.
        gold : str, Path, em.TheoryGraph, or nx.DiGraph
            Reference graph or STNB JSON-LD file path.
        run_id : str, optional
            Run identifier for the result (default: "eval_run").
        phase_name : str, optional
            Phase name associated with the evaluation (default: "Phase 6: TheoryNet Projection").
        dataset_ref : str, optional
            Reference identifier of the dataset (default: None).

        Returns
        -------
        EvaluationResult
            Structured result model ready for inclusion in an EvaluationReport.
        """
        pred_graph = self._ensure_theory_graph(predicted, name="PredictedTheoryGraph")
        gold_graph = self._ensure_gold_theory_graph(gold, name="GoldReferenceGraph")

        eval_result = em.evaluate_model_components(
            pred_graph=pred_graph,
            ref_graph=gold_graph,
            min_mcc=self.min_mcc,
            min_pfs=self.min_pfs,
            sim_threshold=self.sim_threshold,
        )
        outcome = EvaluationOutcome.PASS if eval_result.is_subsumed else EvaluationOutcome.FAIL

        metrics = [
            EvaluationMetric(
                name="mcc",
                value=eval_result.mcc,
                unit="ratio",
                threshold=self.min_mcc,
                passes_threshold=eval_result.mcc >= self.min_mcc,
            ),
            EvaluationMetric(
                name="aor",
                value=eval_result.aor,
                unit="ratio",
                threshold=0.0,
                passes_threshold=eval_result.aor == 0.0,
            ),
            EvaluationMetric(
                name="pfs",
                value=eval_result.pfs,
                unit="ratio",
                threshold=self.min_pfs,
                passes_threshold=eval_result.pfs >= self.min_pfs,
            ),
            EvaluationMetric(
                name="ag_iou",
                value=eval_result.ag_iou,
                unit="ratio",
                threshold=0.5,
                passes_threshold=eval_result.ag_iou >= 0.5,
            ),
            EvaluationMetric(
                name="edge_fidelity",
                value=eval_result.edge_fidelity,
                unit="ratio",
                threshold=0.8,
                passes_threshold=eval_result.edge_fidelity >= 0.8,
            ),
        ]

        from episteme_pipeline.evaluation.scorers.calibration import CalibrationScorer
        cal_scorer = CalibrationScorer()
        cal_res = cal_scorer.evaluate(pred_graph.edges, gold_graph.edges)
        metrics.extend([
            EvaluationMetric(name="ece", value=round(cal_res.ece, 4), unit="ratio"),
            EvaluationMetric(name="brier_score", value=round(cal_res.brier_score, 4), unit="score"),
        ])

        notes = {
            "markdown_report": eval_result.to_markdown(),
            "subsumption_status": "subsumed" if eval_result.is_subsumed else "deficit",
        }

        try:
            poset_result = em.evaluate_specialization_poset(pred_graph, gold_graph)
            if poset_result and (poset_result.num_reference_edges > 0 or poset_result.num_predicted_edges > 0):
                metrics.extend([
                    EvaluationMetric(
                        name="poset_f1",
                        value=poset_result.f1,
                        unit="ratio",
                        threshold=0.8,
                        passes_threshold=poset_result.f1 >= 0.8,
                    ),
                    EvaluationMetric(
                        name="poset_reachability_f1",
                        value=poset_result.reachability_f1,
                        unit="ratio",
                        threshold=0.8,
                        passes_threshold=poset_result.reachability_f1 >= 0.8,
                    ),
                    EvaluationMetric(
                        name="root_conformity",
                        value=1.0 if poset_result.root_conformity else 0.0,
                        unit="bool",
                        threshold=1.0,
                        passes_threshold=poset_result.root_conformity,
                    ),
                    EvaluationMetric(
                        name="is_dag",
                        value=1.0 if poset_result.is_dag else 0.0,
                        unit="bool",
                        threshold=1.0,
                        passes_threshold=poset_result.is_dag,
                    ),
                ])
                notes["poset_markdown"] = poset_result.to_markdown()
                notes["markdown_report"] += "\n\n" + poset_result.to_markdown()
        except Exception:
            pass

        error_buckets = []
        if eval_result.unmatched_ref_nodes:
            error_buckets.append(
                EvaluationErrorBucket(
                    bucket="omitted_reference_components",
                    count=len(eval_result.unmatched_ref_nodes),
                    description=", ".join(eval_result.unmatched_ref_nodes),
                )
            )

        return EvaluationResult(
            run_id=run_id,
            evaluation_level=EvaluationLevel.STAGE,
            phase_name=phase_name,
            dataset_ref=dataset_ref or (str(gold) if isinstance(gold, (str, Path)) else "in_memory_gold"),
            metrics=metrics,
            error_buckets=error_buckets,
            notes=notes,
            outcome=outcome,
        )

    def _ensure_theory_graph(
        self,
        predicted: ArtifactCollection | TheoryNet | em.TheoryGraph | nx.DiGraph,
        name: str = "TheoryGraph",
    ) -> em.TheoryGraph | nx.DiGraph:
        if isinstance(predicted, em.TheoryGraph) or isinstance(predicted, (nx.DiGraph, nx.MultiDiGraph, nx.Graph)):
            return predicted
        if isinstance(predicted, TheoryNet):
            return theory_net_to_theory_graph(predicted, name=name)
        if isinstance(predicted, ArtifactCollection):
            return artifact_collection_to_theory_graph(predicted, name=name)
        raise TypeError(f"Cannot convert {type(predicted).__name__} to an evaluation graph.")

    def _ensure_gold_theory_graph(
        self,
        gold: str | Path | em.TheoryGraph | nx.DiGraph,
        name: str = "GoldGraph",
    ) -> em.TheoryGraph | nx.DiGraph:
        if isinstance(gold, (str, Path)):
            _, nx_gold = load_structuralist_benchmark(gold)
            return structuralist_digraph_to_theory_graph(nx_gold, name=name)
        if isinstance(gold, em.TheoryGraph) or isinstance(gold, (nx.DiGraph, nx.MultiDiGraph, nx.Graph)):
            return gold
        raise TypeError(f"Cannot convert gold reference {type(gold).__name__} to an evaluation graph.")
