"""Dependency-injected evaluation harness orchestrating intrinsic and extrinsic metrics."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

import networkx as nx
import yaml

import epistemetrics as em
from episteme_pipeline.artifacts.execution import ArtifactCollection
from episteme_pipeline.contracts.domain import TheoryNet
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.events import EventEmitter, NoOpEventEmitter
from episteme_pipeline.events.models import EvaluationCompleted, ValidationViolationDetected
from episteme_pipeline.evaluation.baselines import (
    BaselineNaiveKG,
    BaselineTextRAG,
    BaselineZeroShotLLM,
)
from episteme_pipeline.evaluation.benchmarks.structuralist import load_structuralist_benchmark
from episteme_pipeline.evaluation.comparison import (
    ComparisonAxis,
    EvaluationComparison,
    RunComparison,
    compute_run_comparisons,
    format_comparison_markdown,
)
from episteme_pipeline.evaluation.models import (
    DatasetType,
    EvaluationLevel,
    EvaluationMetric,
    EvaluationOutcome,
    EvaluationReport,
    EvaluationResult,
)
from episteme_pipeline.evaluation.pipelines import (
    build_l2_eval_pipeline,
    build_l3_eval_pipeline,
    build_l4_theorynet_eval_pipeline,
)
from episteme_pipeline.evaluation.scorers.domain_bridge import (
    artifact_collection_to_theory_graph,
    l2_triples_to_digraph,
    theory_net_to_digraph,
)
from episteme_pipeline.evaluation.scorers.gm_gbs import GraphBERTScoreEvaluator
from episteme_pipeline.evaluation.scorers.model_scorer import ModelScorer
from episteme_pipeline.evaluation.scorers.oep import OptimalEditPathEvaluator
from episteme_pipeline.evaluation.scorers.retrieval import ExtrinsicRetrievalEvaluator
from episteme_pipeline.evaluation.strategies import (
    EvaluationStrategy,
    StrategyRegistry,
    default_registry,
)
from episteme_pipeline.graph.in_memory_store import InMemoryGraphStore
from episteme_pipeline.graph.validation import GraphValidator
from episteme_pipeline.protocols.graph_store import ProcessingGraph

logger = logging.getLogger(__name__)


@runtime_checkable
class EvaluationHarnessProtocol(Protocol):
    """Protocol defining the sovereign evaluation harness contract."""

    async def evaluate_in_memory(
        self,
        predicted: Any,
        gold: Any,
        run_id: str = "in_memory_run",
        strategy: str | EvaluationStrategy | None = None,
        dataset_ref: str | None = None,
        **kwargs: Any,
    ) -> EvaluationReport:
        """Evaluate pipeline output directly in memory without requiring remote stores."""
        ...

    async def evaluate_manifest(
        self,
        manifest_path: str | Path,
        build_graph: bool = False,
        strategy: str | EvaluationStrategy | None = None,
        baseline: str | None = None,
    ) -> EvaluationReport:
        """Execute an evaluation run configured by a manifest YAML file."""
        ...


class EvaluationHarness(EvaluationHarnessProtocol):
    """Sovereign evaluation harness for intrinsic and extrinsic pipeline evaluation."""

    def __init__(
        self,
        event_emitter: EventEmitter | None = None,
        model_scorer: ModelScorer | None = None,
        retrieval_scorer: ExtrinsicRetrievalEvaluator | None = None,
        gm_gbs_evaluator: GraphBERTScoreEvaluator | None = None,
        graph_store: ProcessingGraph | None = None,
        strategy_registry: StrategyRegistry | None = None,
        reports_dir: str | Path = "evaluation/reports",
    ) -> None:
        """Initialize the evaluation harness with dependency injection.

        Parameters
        ----------
        event_emitter : EventEmitter, optional
            Event bus for publishing evaluation and validation telemetry.
        model_scorer : ModelScorer, optional
            Scorer for Bourbaki structuralist model component decomposition.
        retrieval_scorer : ExtrinsicRetrievalEvaluator, optional
            Downstream information retrieval evaluator.
        gm_gbs_evaluator : GraphBERTScoreEvaluator, optional
            Graph BERTScore evaluator.
        graph_store : ProcessingGraph, optional
            Graph storage backend (defaults to InMemoryGraphStore).
        strategy_registry : StrategyRegistry, optional
            Registry of evaluation strategies (defaults to default_registry).
        reports_dir : str or Path, optional
            Output directory for persisted JSON and Markdown reports.
        """
        self.event_emitter = event_emitter or NoOpEventEmitter()
        self.model_scorer = model_scorer or ModelScorer()
        self.retrieval_scorer = retrieval_scorer
        self.gm_gbs_evaluator = gm_gbs_evaluator
        self.graph_store = graph_store or InMemoryGraphStore()
        self.strategy_registry = strategy_registry or default_registry
        self.reports_dir = Path(reports_dir)

    async def evaluate_in_memory(
        self,
        predicted: ArtifactCollection | TheoryNet | em.TheoryGraph | nx.DiGraph | Any,
        gold: str | Path | em.TheoryGraph | nx.DiGraph | Any,
        run_id: str = "in_memory_run",
        strategy: str | EvaluationStrategy | None = None,
        dataset_ref: str | None = None,
        min_mcc: float = 1.0,
        min_pfs: float = 0.8,
        sim_threshold: float = 0.50,
        **kwargs: Any,
    ) -> EvaluationReport:
        """Evaluate pipeline output directly in memory using pluggable strategies.

        Supports arbitrary datasets and pipeline layers (L2 extraction, L3 argumentation,
        L4 formal theory-nets) without requiring Neo4j or network connectivity.

        Parameters
        ----------
        predicted : Any
            Predicted representation from pipeline execution.
        gold : Any
            Gold standard reference graph, dataset path, or annotations.
        run_id : str, optional
            Run identifier for reporting (default: "in_memory_run").
        strategy : str or EvaluationStrategy, optional
            Explicit strategy name or instance. If None, automatically inferred from inputs.
        dataset_ref : str, optional
            Dataset reference name or path.
        min_mcc : float, optional
            Minimum MCC threshold for structuralist evaluation (default: 1.0).
        min_pfs : float, optional
            Minimum PFS threshold for structuralist evaluation (default: 0.8).
        sim_threshold : float, optional
            Minimum node similarity threshold (default: 0.50).
        **kwargs : Any
            Additional hyperparameters forwarded to the evaluation strategy.

        Returns
        -------
        EvaluationReport
            Structured evaluation report containing evaluated metrics and markdown summary.
        """
        strat: EvaluationStrategy
        if isinstance(strategy, str):
            strat = self.strategy_registry.get(strategy)
        elif strategy is not None:
            strat = strategy
        else:
            strat = self.strategy_registry.infer(predicted=predicted, gold=gold)

        context = {
            "min_mcc": min_mcc,
            "min_pfs": min_pfs,
            "sim_threshold": sim_threshold,
            "dataset_ref": dataset_ref,
            **kwargs,
        }
        stage_results = await strat.evaluate(
            predicted=predicted,
            gold=gold,
            run_id=run_id,
            context=context,
        )

        results_by_level: dict[str, list[EvaluationResult]] = {}
        metrics_dict: dict[str, float] = {}
        for res in stage_results:
            lvl = str(res.evaluation_level)
            results_by_level.setdefault(lvl, []).append(res)
            for m in res.metrics:
                metrics_dict[m.name] = m.value

        summary_text = "\n\n".join(r.notes.get("markdown_report", "") for r in stage_results)
        primary_ref = (
            stage_results[0].dataset_ref
            if stage_results and stage_results[0].dataset_ref
            else (dataset_ref or (str(gold) if isinstance(gold, (str, Path)) else "in_memory_gold"))
        )
        overall_outcome = (
            "success"
            if all(r.outcome in (EvaluationOutcome.PASS, EvaluationOutcome.WARNING) for r in stage_results)
            else "failure"
        )

        report = EvaluationReport(
            evaluation_id=f"eval_{run_id}",
            run_ids=[run_id],
            dataset_ref=primary_ref,
            dataset_type=DatasetType.GOLD,
            results_by_level=results_by_level,
            summary=summary_text,
        )

        self.event_emitter.emit(
            EvaluationCompleted(
                evaluation_id=report.evaluation_id,
                run_id=run_id,
                metrics=metrics_dict,
                outcome=overall_outcome,
            )
        )

        return report

    async def evaluate_manifest(
        self,
        manifest_path: str | Path,
        build_graph: bool = False,
        strategy: str | EvaluationStrategy | None = None,
        baseline: str | None = None,
    ) -> EvaluationReport:
        """Execute an evaluation run configured by a manifest YAML file.

        Parameters
        ----------
        manifest_path : str or Path
            Filesystem path to the manifest YAML file.
        build_graph : bool, optional
            Whether to invoke pipeline execution prior to scoring (default: False).
        strategy : str or EvaluationStrategy, optional
            Explicit strategy name or instance override.
        baseline : str, optional
            Comparative baseline to evaluate ('text_rag', 'naive_kg', or 'zero_shot').

        Returns
        -------
        EvaluationReport
            Synthesized evaluation report.
        """
        pipeline_start_time = time.perf_counter()
        path = Path(manifest_path)
        if not path.is_file():
            raise FileNotFoundError(f"Manifest not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            manifest: dict[str, Any] = yaml.safe_load(f)

        run_id = str(manifest.get("run_id", "unknown_run"))
        corpus_cfg = manifest.get("corpus", {})
        dataset_type = corpus_cfg.get("dataset_type", "structuralist")
        strategy_name = manifest.get("strategy") or corpus_cfg.get("strategy") or manifest.get("evaluator")
        builder_ref = manifest.get("pipeline_builder") or corpus_cfg.get("pipeline_builder")
        gold_path = corpus_cfg.get("gold_standard_path")
        limit = corpus_cfg.get("limit", 10)

        # Resolve evaluation strategy
        strat: EvaluationStrategy
        if isinstance(strategy, str):
            strat = self.strategy_registry.get(strategy)
        elif strategy is not None:
            strat = strategy
        elif strategy_name:
            strat = self.strategy_registry.get(strategy_name)
        else:
            strat = self.strategy_registry.infer(
                predicted=None, gold=gold_path, dataset_type=dataset_type
            )

        report_results: list[EvaluationResult] = []
        artifacts: ArtifactCollection | None = None

        if build_graph:
            logger.info("Executing pipeline for evaluation using manifest: %s", manifest_path)
            pipeline = self._build_pipeline_for_dataset(
                dataset_type=dataset_type,
                strategy=strat,
                builder_ref=builder_ref,
            )
            input_sources = corpus_cfg.get("input_sources", [])
            texts_dir = corpus_cfg.get("texts_dir")

            if not input_sources and texts_dir and os.path.isdir(texts_dir):
                for fname in os.listdir(texts_dir):
                    if fname.endswith(".txt"):
                        input_sources.append(os.path.join(texts_dir, fname))

            exec_result = await pipeline.run(PipelineInput(source_paths=input_sources[:limit]))
            artifacts = getattr(exec_result, "artifacts", None)

        # Intrinsic scoring via resolved strategy
        downstream_results: list[EvaluationResult] = []
        predicted_target: Any = None
        if gold_path and os.path.exists(gold_path):
            if artifacts is not None:
                predicted_target = artifacts
            else:
                atoms = await self.graph_store.get_theory_atoms()
                rels = await self.graph_store.get_all_theory_relations()
                entities = await self.graph_store.get_entities()
                triples = await self.graph_store.get_all_entity_triples()
                if atoms or rels:
                    predicted_target = TheoryNet(atoms=atoms, relations=rels)
                elif entities or triples:
                    predicted_target = l2_triples_to_digraph(entities, triples)
                else:
                    predicted_target = ArtifactCollection(artifacts=[])

            stage_results = await strat.evaluate(
                predicted=predicted_target,
                gold=gold_path,
                run_id=run_id,
                context={"corpus_cfg": corpus_cfg, "limit": limit, "dataset_ref": str(gold_path)},
            )
            report_results.extend(stage_results)

            # Extrinsic retrieval evaluation
            queries_path = corpus_cfg.get("queries_path")
            if not queries_path and gold_path:
                cand_path = Path(gold_path).parent / f"{Path(gold_path).stem}_queries.yaml"
                if cand_path.is_file():
                    queries_path = str(cand_path)
                else:
                    cand_path = Path(gold_path).parent / "stnb_cpm_queries.yaml"
                    if cand_path.is_file():
                        queries_path = str(cand_path)
                    else:
                        cand_path = Path(__file__).parent / "data" / "stnb_cpm_queries.yaml"
                        if cand_path.is_file() and dataset_type == "structuralist":
                            queries_path = str(cand_path)

            if queries_path and os.path.isfile(queries_path):
                with open(queries_path, "r", encoding="utf-8") as qf:
                    q_data = yaml.safe_load(qf)
                queries = q_data.get("queries", [])
                if queries:
                    retrieval_eval = self.retrieval_scorer or ExtrinsicRetrievalEvaluator(
                        graph_reader=self.graph_store
                    )
                    # Ensure graph store has the target nodes indexed for search
                    if hasattr(self.graph_store, "index_for_search"):
                        if artifacts is not None:
                            self.graph_store.index_for_search(artifacts, run_id=run_id)
                        elif predicted_target is not None:
                            self.graph_store.index_for_search(predicted_target, run_id=run_id)
                        elif gold_path:
                            self.graph_store.index_for_search(gold_path, run_id=run_id)
                    elif hasattr(self.graph_store, "index_theory_graph"):
                        if artifacts is not None:
                            tg = artifact_collection_to_theory_graph(artifacts)
                            self.graph_store.index_theory_graph(tg, run_id=run_id)
                        elif hasattr(predicted_target, "atoms") and predicted_target.atoms:
                            self.graph_store.index_theory_graph(predicted_target, run_id=run_id)

                    retrieval_metrics = await retrieval_eval.evaluate_batch(
                        queries, top_k=10, run_id=run_id
                    )

                    downstream_result = EvaluationResult(
                        run_id=run_id,
                        evaluation_level=EvaluationLevel.DOWNSTREAM,
                        phase_name="Extrinsic Retrieval Evaluation",
                        dataset_ref=str(queries_path),
                        dataset_type=DatasetType.GOLD,
                        metrics=[
                            EvaluationMetric(name="mrr", value=retrieval_metrics.get("MRR", 0.0)),
                            EvaluationMetric(name="hits@1", value=retrieval_metrics.get("Hits@1", 0.0)),
                            EvaluationMetric(name="hits@3", value=retrieval_metrics.get("Hits@3", 0.0)),
                            EvaluationMetric(name="hits@10", value=retrieval_metrics.get("Hits@10", 0.0)),
                            EvaluationMetric(name="ndcg", value=retrieval_metrics.get("nDCG", 0.0)),
                        ],
                        outcome=EvaluationOutcome.PASS if retrieval_metrics.get("MRR", 0.0) > 0.0 else EvaluationOutcome.WARNING,
                        notes={
                            "category": "extrinsic_retrieval",
                            "markdown_report": (
                                "## Extrinsic Retrieval Evaluation Report\n\n"
                                f"- **MRR:** {retrieval_metrics.get('MRR', 0.0):.4f}\n"
                                f"- **Hits@1:** {retrieval_metrics.get('Hits@1', 0.0):.4f}\n"
                                f"- **Hits@3:** {retrieval_metrics.get('Hits@3', 0.0):.4f}\n"
                                f"- **Hits@10:** {retrieval_metrics.get('Hits@10', 0.0):.4f}\n"
                                f"- **nDCG:** {retrieval_metrics.get('nDCG', 0.0):.4f}\n"
                            ),
                        },
                    )
                    downstream_results.append(downstream_result)

        # Validation checks
        violations = await self._run_validation()

        # Build final report
        results_by_level: dict[str, list[EvaluationResult]] = {}
        if report_results:
            results_by_level[EvaluationLevel.STAGE] = report_results
        if downstream_results:
            results_by_level[EvaluationLevel.DOWNSTREAM] = downstream_results

        all_results = report_results + downstream_results
        metrics_all: dict[str, float] = {}
        for res in all_results:
            for m in res.metrics:
                metrics_all[m.name] = m.value

        pipeline_latency = time.perf_counter() - pipeline_start_time
        if "latency" not in metrics_all:
            metrics_all["latency"] = round(pipeline_latency, 4)
        if "token_cost" not in metrics_all:
            metrics_all["token_cost"] = 0.0

        # Baseline execution and comparative scoring
        baseline_name = baseline or manifest.get("baseline")
        if isinstance(baseline_name, str):
            baseline_name = baseline_name.strip().lower()

        baseline_results: list[EvaluationResult] = []
        baseline_metrics: dict[str, float] = {}
        pairwise_comparisons: list[RunComparison] = []
        comparison_obj: EvaluationComparison | None = None
        highlights_md = ""
        baseline_run_id = f"baseline_{baseline_name}_{run_id}" if baseline_name else ""

        if baseline_name in ("text_rag", "naive_kg", "zero_shot"):
            logger.info("Executing comparative baseline '%s' (run_id: %s)", baseline_name, baseline_run_id)

            texts_dir = corpus_cfg.get("texts_dir")
            queries_path = corpus_cfg.get("queries_path")
            if not queries_path and gold_path:
                cand_path = Path(gold_path).parent / f"{Path(gold_path).stem}_queries.yaml"
                if cand_path.is_file():
                    queries_path = str(cand_path)
                else:
                    cand_path = Path(gold_path).parent / "stnb_cpm_queries.yaml"
                    if cand_path.is_file():
                        queries_path = str(cand_path)
                    else:
                        cand_path = Path(__file__).parent / "data" / "stnb_cpm_queries.yaml"
                        if cand_path.is_file() and dataset_type == "structuralist":
                            queries_path = str(cand_path)

            if baseline_name == "text_rag":
                rag_runner = BaselineTextRAG(graph_store=InMemoryGraphStore())
                rag_res, _ = await rag_runner.run_and_evaluate(
                    corpus=gold_path or texts_dir or "",
                    queries=queries_path or "",
                    run_id=baseline_run_id,
                    top_k=10,
                )
                baseline_results.append(rag_res)
                for m in rag_res.metrics:
                    baseline_metrics[m.name] = m.value

            elif baseline_name == "naive_kg":
                naive_runner = BaselineNaiveKG()
                nkg_results, _ = await naive_runner.run_and_evaluate(
                    corpus=gold_path or texts_dir or "",
                    gold=gold_path,
                    run_id=baseline_run_id,
                )
                baseline_results.extend(nkg_results)
                for res in nkg_results:
                    for m in res.metrics:
                        baseline_metrics[m.name] = m.value

            elif baseline_name == "zero_shot":
                zs_runner = BaselineZeroShotLLM()
                zs_results, _ = await zs_runner.run_and_evaluate(
                    corpus=gold_path or texts_dir or "",
                    gold=gold_path,
                    run_id=baseline_run_id,
                )
                baseline_results.extend(zs_results)
                for res in zs_results:
                    for m in res.metrics:
                        baseline_metrics[m.name] = m.value

            # Canonical F1 resolution across representations
            for k in ("poset_f1", "relation_f1", "entity_f1"):
                if k in metrics_all and "f1" not in metrics_all:
                    metrics_all["f1"] = metrics_all[k]
                if k in baseline_metrics and "f1" not in baseline_metrics:
                    baseline_metrics["f1"] = baseline_metrics[k]

            # Compute deltas using RunComparison
            pairwise_comparisons = compute_run_comparisons(
                run_id_a=baseline_run_id,
                run_id_b=run_id,
                metrics_a=baseline_metrics,
                metrics_b=metrics_all,
                axis=ComparisonAxis.METHOD,
            )

            delta_f1 = metrics_all.get("f1", 0.0) - baseline_metrics.get("f1", 0.0)
            delta_mrr = metrics_all.get("mrr", 0.0) - baseline_metrics.get("mrr", 0.0)
            cost_p = metrics_all.get("token_cost", 0.0)
            cost_b = baseline_metrics.get("token_cost", 0.0)
            delta_cost = cost_p - cost_b
            lat_p = metrics_all.get("latency", 0.0)
            lat_b = baseline_metrics.get("latency", 0.0)
            delta_lat = lat_p - lat_b

            highlights_md = (
                f"\n\n## Comparative Baseline Evaluation: {baseline_name.upper()} vs Pipeline\n\n"
                f"- **ΔF1:** {delta_f1:+.4f} (Pipeline: {metrics_all.get('f1', 0.0):.4f} vs Baseline: {baseline_metrics.get('f1', 0.0):.4f})\n"
                f"- **ΔMRR:** {delta_mrr:+.4f} (Pipeline: {metrics_all.get('mrr', 0.0):.4f} vs Baseline: {baseline_metrics.get('mrr', 0.0):.4f})\n"
                f"- **Token Cost:** Pipeline ${cost_p:.4f} vs Baseline ${cost_b:.4f} (Δ ${delta_cost:+.4f})\n"
                f"- **Latency:** Pipeline {lat_p:.4f}s vs Baseline {lat_b:.4f}s (Δ {delta_lat:+.4f}s)\n\n"
                + format_comparison_markdown(pairwise_comparisons, title=f"Side-by-Side Metrics ({baseline_name})", name_a="Baseline", name_b="Pipeline")
            )

            comparison_obj = EvaluationComparison(
                comparison_id=f"comp_{run_id}_vs_{baseline_run_id}",
                run_ids=[baseline_run_id, run_id],
                axis=ComparisonAxis.METHOD,
                dataset_ref=str(gold_path) if gold_path else "manifest_corpus",
                dataset_type=DatasetType.GOLD,
                pairwise_comparisons=pairwise_comparisons,
                summary=highlights_md,
            )
            results_by_level["baseline"] = baseline_results

        report = EvaluationReport(
            evaluation_id=f"eval_{run_id}",
            run_ids=[run_id] + ([baseline_run_id] if baseline_name in ("text_rag", "naive_kg", "zero_shot") else []),
            dataset_ref=str(gold_path) if gold_path else "manifest_corpus",
            dataset_type=DatasetType.GOLD,
            results_by_level=results_by_level,
            pairwise_comparisons=pairwise_comparisons,
            summary="\n\n".join(r.notes.get("markdown_report", "") for r in all_results) + highlights_md,
        )

        self._persist_reports(report, manifest_path=str(manifest_path))

        self.event_emitter.emit(
            EvaluationCompleted(
                evaluation_id=report.evaluation_id,
                run_id=run_id,
                metrics=metrics_all,
                outcome="success" if not violations else "violations_detected",
            )
        )

        return report

    def _build_pipeline_for_dataset(
        self,
        dataset_type: str,
        strategy: EvaluationStrategy | None = None,
        builder_ref: str | Callable[..., Any] | None = None,
    ) -> Any:
        """Resolve and instantiate an execution pipeline for evaluation benchmarks.

        Parameters
        ----------
        dataset_type : str
            Dataset identifier or category name.
        strategy : EvaluationStrategy, optional
            Active evaluation strategy that may supply its own pipeline factory.
        builder_ref : str or Callable, optional
            Explicit pipeline factory callable or dynamic module reference.

        Returns
        -------
        Pipeline
            Configured and instantiated pipeline instance.
        """
        # 1. Explicit builder reference (Callable or dynamic module path string)
        if callable(builder_ref):
            return builder_ref(event_emitter=self.event_emitter, in_memory=True)
        if isinstance(builder_ref, str):
            fn = self.strategy_registry.get_pipeline_builder(builder_ref)
            return fn(event_emitter=self.event_emitter, in_memory=True)

        # 2. Strategy's own build_pipeline method if implemented
        if strategy is not None and hasattr(strategy, "build_pipeline"):
            return getattr(strategy, "build_pipeline")(event_emitter=self.event_emitter, in_memory=True)

        # 3. Lookup builder by dataset_type in registry
        try:
            fn = self.strategy_registry.get_pipeline_builder(dataset_type)
            return fn(event_emitter=self.event_emitter, in_memory=True)
        except ValueError:
            pass

        # 4. Default fallback: Level 4 TheoryNet pipeline
        return build_l4_theorynet_eval_pipeline(event_emitter=self.event_emitter, in_memory=True)

    async def _run_validation(self) -> list[dict[str, Any]]:
        validator = GraphValidator(self.graph_store)
        violations = []
        try:
            for v in await validator.check_direct_disjointness():
                violations.append({"rule_name": "direct_disjointness", **v})
            for v in await validator.check_transitive_disjointness():
                violations.append({"rule_name": "transitive_disjointness", **v})
            for v in await validator.check_type_constraints():
                violations.append({"rule_name": "type_constraints", **v})
        except Exception as e:
            logger.debug("Validation check skipped or failed: %s", e)

        for v in violations:
            self.event_emitter.emit(
                ValidationViolationDetected(
                    rule_name=v.get("rule_name", "unknown"),
                    source_id=v.get("source_id", "unknown"),
                    target_id=v.get("target_id", "unknown"),
                    description=str(v),
                )
            )
        return violations

    def _persist_reports(self, report: EvaluationReport, manifest_path: str) -> None:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.reports_dir / f"report_{report.run_ids[0]}.json"
        md_path = self.reports_dir / f"report_{report.run_ids[0]}.md"

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Evaluation Report: {report.evaluation_id}\n\n")
            f.write(f"- **Manifest:** `{manifest_path}`\n")
            f.write(f"- **Dataset:** `{report.dataset_ref}`\n\n")
            f.write(report.summary)


def main() -> None:
    """CLI entrypoint for running evaluation manifests."""
    parser = argparse.ArgumentParser(description="Episteme Pipeline Evaluation Harness")
    parser.add_argument(
        "--manifest",
        type=str,
        required=True,
        help="Path to evaluation run manifest YAML.",
    )
    parser.add_argument(
        "--build-graph",
        action="store_true",
        help="Whether to execute pipeline prior to scoring.",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        choices=["text_rag", "naive_kg", "zero_shot"],
        default=None,
        help="Comparative baseline to evaluate against pipeline output.",
    )
    args = parser.parse_args()

    harness = EvaluationHarness()
    report = asyncio.run(
        harness.evaluate_manifest(
            args.manifest,
            build_graph=args.build_graph,
            baseline=args.baseline,
        )
    )
    print(f"Evaluation completed: {report.evaluation_id}")
    print(report.summary)


if __name__ == "__main__":
    main()
