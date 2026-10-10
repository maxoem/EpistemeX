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

from episteme_pipeline.evaluation.baselines import (
    BaselineNaiveKG,
    BaselineTextRAG,
    BaselineZeroShotLLM,
)
from episteme_pipeline.evaluation.benchmarks import (
    export_baseline,
    export_neo4j_to_theory_graph,
    load_arg_microtexts_subset,
    load_gold_standard,
    load_scierc_subset,
    load_scifact_subset,
    load_structuralist_benchmark,
    load_structuralist_theory_graph,
    structuralist_digraph_to_theory_graph,
)
from episteme_pipeline.evaluation.comparison import (
    ComparisonAxis,
    EvaluationComparison,
    RunComparison,
    compute_run_comparisons,
    format_comparison_markdown,
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
    CalibrationDataExtractor,
    CalibrationResult,
    CalibrationScorer,
    DefaultCalibrationDataExtractor,
    ExtrinsicRetrievalEvaluator,
    GraphBERTScoreEvaluator,
    GroundingEvaluationResult,
    GroundingScorer,
    ModelScorer,
    OptimalEditPathEvaluator,
    ReliabilityBin,
    artifact_collection_to_theory_graph,
    build_digraph,
    calculate_anchor_iou,
    calculate_bbox_iou,
    calculate_tabular_grounding_iou,
    calculate_visual_grounding_iou,
    compute_calibration_metrics,
    gold_standard_to_digraph,
    l2_triples_to_digraph,
    theory_net_to_digraph,
    theory_net_to_theory_graph,
)
from episteme_pipeline.evaluation.strategies import (
    ArgumentationStrategy,
    EvaluationStrategy,
    ExtractionStrategy,
    NoiseRobustnessStrategy,
    StrategyRegistry,
    StructuralistStrategy,
    apply_entity_synonym_swaps,
    apply_graph_perturbation,
    apply_sentence_shuffling,
    apply_typo_noise,
    compute_rdf,
    default_registry,
)

__all__ = [
    "ArgumentationStrategy",
    "BaselineNaiveKG",
    # baselines
    "BaselineTextRAG",
    "BaselineZeroShotLLM",
    # scorers
    "CalibrationDataExtractor",
    "CalibrationResult",
    "CalibrationScorer",
    # comparison
    "ComparisonAxis",
    # datasets
    "DatasetReference",
    # models
    "DatasetType",
    "DefaultCalibrationDataExtractor",
    "EvaluationComparison",
    "EvaluationDataset",
    "EvaluationErrorBucket",
    # harness
    "EvaluationHarness",
    "EvaluationHarnessProtocol",
    # rubrics
    "EvaluationJudgment",
    "EvaluationLevel",
    "EvaluationMetric",
    "EvaluationOutcome",
    "EvaluationReport",
    "EvaluationResult",
    "EvaluationRubric",
    # strategies
    "EvaluationStrategy",
    "ExtractionStrategy",
    "ExtrinsicRetrievalEvaluator",
    "GraphBERTScoreEvaluator",
    "GroundingEvaluationResult",
    "GroundingScorer",
    "ModelScorer",
    "NoiseRobustnessStrategy",
    "OptimalEditPathEvaluator",
    "RatingLevel",
    "ReliabilityBin",
    "RubricCriterion",
    "RunComparison",
    "StrategyRegistry",
    "StructuralistStrategy",
    "apply_entity_synonym_swaps",
    "apply_graph_perturbation",
    "apply_sentence_shuffling",
    "apply_typo_noise",
    "artifact_collection_to_theory_graph",
    "build_digraph",
    # pipelines
    "build_l2_eval_pipeline",
    "build_l3_eval_pipeline",
    "build_l4_theorynet_eval_pipeline",
    "calculate_anchor_iou",
    "calculate_bbox_iou",
    # intrinsic
    "calculate_graph_bertscore",
    # extrinsic
    "calculate_hits_at_k",
    "calculate_mrr",
    "calculate_ndcg",
    "calculate_oep_rates",
    "calculate_tabular_grounding_iou",
    "calculate_visual_grounding_iou",
    "compute_calibration_metrics",
    "compute_rdf",
    "compute_run_comparisons",
    "default_registry",
    "evaluate_theory_graph_components",
    "export_baseline",
    "export_neo4j_to_theory_graph",
    "format_comparison_markdown",
    "gold_standard_to_digraph",
    "l2_triples_to_digraph",
    "load_arg_microtexts_subset",
    "load_gold_standard",
    "load_scierc_subset",
    "load_scifact_subset",
    # benchmarks
    "load_structuralist_benchmark",
    "load_structuralist_theory_graph",
    "structuralist_digraph_to_theory_graph",
    "theory_net_to_digraph",
    "theory_net_to_theory_graph",
]
