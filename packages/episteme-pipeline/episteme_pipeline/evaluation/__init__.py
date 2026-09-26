"""Evaluation scaffolding and benchmarking suite for the theory-graph construction pipeline.

This package provides a unified evaluation framework for knowledge graphs and formal TheoryNets:
- Benchmarks: Structuralist (STNB), SciERC, Arg-Microtexts, SciFact, baseline curation.
- Scorers: Bourbaki structuralist model component decomposition (ModelScorer),
  extrinsic IR evaluation (ExtrinsicRetrievalEvaluator), Graph BERTScore (GM-GBS), and OEP.
- Harness: In-memory and manifest-driven EvaluationHarness.
- Pipelines: Level 2, Level 3, and Level 4 TheoryNet evaluation pipelines.
- Domain models: EvaluationReport, EvaluationResult, EvaluationDataset, EvaluationRubric.
"""

from __future__ import annotations

from episteme_pipeline.evaluation.benchmarks import (
    export_baseline,
    export_neo4j_to_theory_graph,
    load_arg_microtexts_subset,
    load_gold_standard,
    load_scifact_subset,
    load_scierc_subset,
    load_structuralist_benchmark,
    load_structuralist_theory_graph,
    structuralist_digraph_to_theory_graph,
)
from episteme_pipeline.evaluation.comparison import (
    ComparisonAxis,
    EvaluationComparison,
    RunComparison,
)
from episteme_pipeline.evaluation.datasets import DatasetReference, EvaluationDataset
from episteme_pipeline.evaluation.extrinsic import (
    calculate_hits_at_k,
    calculate_mrr,
    calculate_ndcg,
)
from episteme_pipeline.evaluation.harness import (
    EvaluationHarness,
    EvaluationHarnessProtocol,
)
from episteme_pipeline.evaluation.intrinsic import (
    calculate_graph_bertscore,
    calculate_oep_rates,
    evaluate_theory_graph_components,
)
from episteme_pipeline.evaluation.models import (
    DatasetType,
    EvaluationErrorBucket,
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
from episteme_pipeline.evaluation.rubrics import (
    EvaluationJudgment,
    EvaluationRubric,
    RatingLevel,
    RubricCriterion,
)
from episteme_pipeline.evaluation.scorers import (
    ExtrinsicRetrievalEvaluator,
    GraphBERTScoreEvaluator,
    ModelScorer,
    OptimalEditPathEvaluator,
    artifact_collection_to_theory_graph,
    build_digraph,
    gold_standard_to_digraph,
    l2_triples_to_digraph,
    theory_net_to_digraph,
    theory_net_to_theory_graph,
)
from episteme_pipeline.evaluation.strategies import (
    ArgumentationStrategy,
    EvaluationStrategy,
    ExtractionStrategy,
    StrategyRegistry,
    StructuralistStrategy,
    default_registry,
)

__all__ = [
    # harness
    "EvaluationHarness",
    "EvaluationHarnessProtocol",
    # pipelines
    "build_l2_eval_pipeline",
    "build_l3_eval_pipeline",
    "build_l4_theorynet_eval_pipeline",
    # benchmarks
    "load_structuralist_benchmark",
    "load_structuralist_theory_graph",
    "structuralist_digraph_to_theory_graph",
    "load_scierc_subset",
    "load_arg_microtexts_subset",
    "load_scifact_subset",
    "export_baseline",
    "load_gold_standard",
    "export_neo4j_to_theory_graph",
    # scorers
    "ModelScorer",
    "ExtrinsicRetrievalEvaluator",
    "GraphBERTScoreEvaluator",
    "OptimalEditPathEvaluator",
    "build_digraph",
    "l2_triples_to_digraph",
    "theory_net_to_digraph",
    "theory_net_to_theory_graph",
    "artifact_collection_to_theory_graph",
    "gold_standard_to_digraph",
    # strategies
    "EvaluationStrategy",
    "StructuralistStrategy",
    "ExtractionStrategy",
    "ArgumentationStrategy",
    "StrategyRegistry",
    "default_registry",
    # comparison
    "ComparisonAxis",
    "EvaluationComparison",
    "RunComparison",
    # datasets
    "DatasetReference",
    "EvaluationDataset",
    # extrinsic
    "calculate_hits_at_k",
    "calculate_mrr",
    "calculate_ndcg",
    # intrinsic
    "calculate_graph_bertscore",
    "calculate_oep_rates",
    "evaluate_theory_graph_components",
    # models
    "DatasetType",
    "EvaluationErrorBucket",
    "EvaluationLevel",
    "EvaluationMetric",
    "EvaluationOutcome",
    "EvaluationReport",
    "EvaluationResult",
    # rubrics
    "EvaluationJudgment",
    "EvaluationRubric",
    "RatingLevel",
    "RubricCriterion",
]
