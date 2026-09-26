"""Domain models for knowledge graph evaluation, reports, and benchmarks.

In accordance with architectural constraint D-01, models in this package
must remain strictly decoupled from `episteme_pipeline.*` and `epistemetrics.*`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime.

    Returns
    -------
    datetime
        Current UTC timestamp.
    """
    return datetime.now(timezone.utc)


class EvaluationOutcome(StrEnum):
    """Overall outcome of an evaluation run.

    Attributes
    ----------
    PASS : str
        The run fully satisfied capability and threshold constraints.
    FAIL : str
        One or more critical capability violations or threshold failures occurred.
    WARNING : str
        Non-critical anomalies or partial omissions detected.
    INCONCLUSIVE : str
        Evaluation could not determine compliance due to missing inputs.
    """

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    INCONCLUSIVE = "inconclusive"


class EvaluationMetricValue(BaseModel):
    """Scalar evaluation metric with threshold verification.

    Parameters
    ----------
    name : str
        Canonical metric name (e.g., 'mcc', 'aor', 'pfs', 'f1', 'mrr').
    value : float
        Scalar evaluated value.
    unit : str, default ''
        Measurement unit (e.g., 'ratio', 'count', 'seconds').
    threshold : float or None, optional
        Target requirement threshold if defined.
    passes_threshold : bool or None, optional
        True if the metric meets or exceeds threshold.
    """

    name: str
    value: float
    unit: str = ""
    threshold: float | None = None
    passes_threshold: bool | None = None


class ModelDecompositionEntry(BaseModel):
    """Decomposition completeness statistics for a Bourbaki model class.

    Parameters
    ----------
    class_name : str
        Formal model class name (e.g., 'actual_models', 'potential_models').
    symbol : str
        Mathematical symbol (e.g., 'M', 'Mp', 'GC', 'I0').
    reference_count : int
        Count of components in the reference gold standard.
    predicted_count : int
        Count of components extracted in the predicted graph.
    matched_count : int
        Count of components successfully matched.
    completeness : float
        Coverage ratio (matched / reference).
    """

    class_name: str
    symbol: str
    reference_count: int
    predicted_count: int
    matched_count: int
    completeness: float


class PosetEvaluationDetail(BaseModel):
    """Detailed metrics for specialization poset hierarchy verification.

    Parameters
    ----------
    is_dag : bool
        Whether the specialization graph is an acyclic directed graph.
    root_element : str or None, optional
        Detected single root theory element T_0.
    root_conformity : bool
        Whether the poset strictly satisfies root conformity B(TN) = {T_0}.
    transitive_reduction_f1 : float
        F1 score of transitive reduction edges against gold poset.
    reachability_f1 : float
        F1 score of transitive reachability closures.
    predicted_edge_count : int
        Number of predicted specialization edges.
    reference_edge_count : int
        Number of reference specialization edges.
    """

    is_dag: bool
    root_element: str | None = None
    root_conformity: bool = False
    transitive_reduction_f1: float = 0.0
    reachability_f1: float = 0.0
    predicted_edge_count: int = 0
    reference_edge_count: int = 0


class PolarityConcordanceDetail(BaseModel):
    """Detailed metrics for schema-driven relation polarity concordance.

    Parameters
    ----------
    polarity_accuracy : float
        Ratio of matching polarities among true positive relations.
    polarity_conflict_rate : float
        Rate of severe epistemic inversions (predicting support vs refutation).
    conflicting_pairs_count : int, default 0
        Number of conflicting relation pairs.
    agreed_pairs_count : int, default 0
        Number of agreeing relation pairs.
    """

    polarity_accuracy: float
    polarity_conflict_rate: float
    conflicting_pairs_count: int = 0
    agreed_pairs_count: int = 0


class RetrievalEvaluationDetail(BaseModel):
    """Information retrieval competency ranking metrics.

    Parameters
    ----------
    mrr : float
        Mean Reciprocal Rank across competency benchmark queries.
    hits_at_1 : float
        Hits@1 success rate.
    hits_at_3 : float
        Hits@3 success rate.
    hits_at_10 : float
        Hits@10 success rate.
    ndcg : float
        Normalized Discounted Cumulative Gain.
    num_queries : int, default 0
        Total competency queries evaluated.
    """

    mrr: float = 0.0
    hits_at_1: float = 0.0
    hits_at_3: float = 0.0
    hits_at_10: float = 0.0
    ndcg: float = 0.0
    num_queries: int = 0


class ComparativeMetricDelta(BaseModel):
    """Pairwise comparison delta between pipeline and baseline runs.

    Parameters
    ----------
    metric_name : str
        Canonical metric identifier.
    value_baseline : float
        Score achieved by baseline runner.
    value_pipeline : float
        Score achieved by Episteme pipeline.
    delta : float
        Signed difference (pipeline - baseline).
    favorable : bool or None, optional
        True if delta represents positive improvement.
    winner : str, default 'Tie'
        Which approach performed better ('Pipeline', 'Baseline', or 'Tie').
    """

    metric_name: str
    value_baseline: float
    value_pipeline: float
    delta: float
    favorable: bool | None = None
    winner: str = "Tie"


class EvaluationLevelResult(BaseModel):
    """Evaluation result for a specific pipeline layer or evaluation stage.

    Parameters
    ----------
    run_id : str
        Run identifier evaluated.
    level : str
        Evaluation level ('component', 'stage', 'downstream', 'baseline').
    phase_name : str or None, optional
        Human-readable phase name.
    dataset_ref : str or None, optional
        Target dataset path or name.
    outcome : EvaluationOutcome
        Stage outcome.
    metrics : list of EvaluationMetricValue
        Metrics calculated at this level.
    notes : dict of str to Any, optional
        Additional diagnostics, reports, or category tags.
    evaluated_at : datetime
        Timestamp when evaluation completed.
    """

    run_id: str
    level: str
    phase_name: str | None = None
    dataset_ref: str | None = None
    outcome: EvaluationOutcome = EvaluationOutcome.INCONCLUSIVE
    metrics: list[EvaluationMetricValue] = Field(default_factory=list)
    notes: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: datetime = Field(default_factory=utc_now)


class EvaluationReportSummary(BaseModel):
    """High-level summary of an evaluation report for workbench lists and tables.

    Parameters
    ----------
    evaluation_id : str
        Unique report identifier.
    run_ids : list of str
        Identifiers of participating pipeline runs.
    dataset_ref : str or None, optional
        Target benchmark dataset reference.
    dataset_type : str, default 'gold'
        Category of dataset ('gold', 'silver', 'stress_test').
    outcome : EvaluationOutcome
        Overall synthesized outcome.
    created_at : datetime
        Report generation timestamp.
    key_metrics : dict of str to float
        Primary headline KPIs (e.g. {'mcc': 1.0, 'aor': 0.0, 'f1': 0.88, 'mrr': 0.75}).
    has_markdown : bool, default True
        Whether human-readable Markdown commentary exists.
    has_baseline : bool, default False
        Whether comparative baseline benchmarking was executed.
    """

    evaluation_id: str
    run_ids: list[str] = Field(default_factory=list)
    dataset_ref: str | None = None
    dataset_type: str = "gold"
    outcome: EvaluationOutcome = EvaluationOutcome.INCONCLUSIVE
    created_at: datetime = Field(default_factory=utc_now)
    key_metrics: dict[str, float] = Field(default_factory=dict)
    has_markdown: bool = True
    has_baseline: bool = False


class EvaluationReportDetail(EvaluationReportSummary):
    """Comprehensive evaluation report containing all stages, decompositions, and comparisons.

    Parameters
    ----------
    results_by_level : dict of str to list of EvaluationLevelResult
        Detailed metric breakdowns keyed by evaluation level.
    model_decomposition : list of ModelDecompositionEntry
        Bourbaki structuralist model decomposition completeness.
    poset_detail : PosetEvaluationDetail or None, optional
        Specialization poset hierarchy diagnostics.
    polarity_detail : PolarityConcordanceDetail or None, optional
        Schema-driven polarity concordance breakdown.
    retrieval_detail : RetrievalEvaluationDetail or None, optional
        Downstream competency question retrieval effectiveness.
    comparative_deltas : list of ComparativeMetricDelta
        Comparative baselines deltas.
    summary_markdown : str, default ''
        Full formatted Markdown report commentary.
    omitted_components : list of str
        Identifiers of reference components missing from predicted graph.
    violations : list of dict of str to Any
        Graph schema and disjointness violations detected.
    """

    results_by_level: dict[str, list[EvaluationLevelResult]] = Field(default_factory=dict)
    model_decomposition: list[ModelDecompositionEntry] = Field(default_factory=list)
    poset_detail: PosetEvaluationDetail | None = None
    polarity_detail: PolarityConcordanceDetail | None = None
    retrieval_detail: RetrievalEvaluationDetail | None = None
    comparative_deltas: list[ComparativeMetricDelta] = Field(default_factory=list)
    summary_markdown: str = ""
    omitted_components: list[str] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkDescriptor(BaseModel):
    """Catalog entry describing an available gold-standard benchmark.

    Parameters
    ----------
    id : str
        Unique benchmark identifier (e.g., 'stnb_cpm_pilot', 'scierc_ner').
    name : str
        Human-readable title.
    description : str
        Methodological and domain description.
    task_type : str
        Target task ('structuralist', 'extraction', 'argumentation', 'retrieval').
    gold_standard_path : str
        Filesystem path to gold reference annotations.
    queries_path : str or None, optional
        Filesystem path to competency retrieval queries YAML if available.
    available : bool, default True
        Whether the benchmark files exist on the current filesystem.
    """

    id: str
    name: str
    description: str
    task_type: str
    gold_standard_path: str
    queries_path: str | None = None
    available: bool = True


class EvaluateRunRequest(BaseModel):
    """Payload requesting an evaluation of a completed pipeline run against a benchmark.

    Parameters
    ----------
    run_id : str
        Identifier of the target run to evaluate.
    benchmark_id : str or None, optional
        Identifier of a registered benchmark (e.g., 'stnb_cpm_pilot').
    gold_standard_path : str or None, optional
        Custom filesystem path to gold reference if not using a registered benchmark.
    queries_path : str or None, optional
        Custom path to competency queries YAML.
    strategy : str or None, optional
        Evaluation strategy override ('structuralist', 'extraction', 'argumentation').
    baseline : str or None, optional
        Comparative baseline to run alongside ('naive_kg', 'text_rag', 'zero_shot').
    min_mcc : float, default 1.0
        Minimum Model Component Completeness threshold.
    min_pfs : float, default 0.8
        Minimum Property Fidelity Score threshold.
    sim_threshold : float, default 0.50
        Cosine similarity threshold for soft semantic alignment.
    persist : bool, default True
        Whether to persist the generated report into evaluation/reports/.
    """

    run_id: str
    benchmark_id: str | None = None
    gold_standard_path: str | None = None
    queries_path: str | None = None
    strategy: str | None = None
    baseline: str | None = None
    min_mcc: float = 1.0
    min_pfs: float = 0.8
    sim_threshold: float = 0.50
    persist: bool = True


class CompareRunsRequest(BaseModel):
    """Payload for comparing two pipeline runs against each other or a gold benchmark.

    Parameters
    ----------
    run_id_a : str
        First run identifier (baseline or reference).
    run_id_b : str
        Second run identifier (candidate or experiment).
    gold_standard_path : str or None, optional
        Optional gold reference path to evaluate both runs against.
    axis : str, default 'method'
        Comparison dimension ('method', 'prompt', 'model').
    """

    run_id_a: str
    run_id_b: str
    gold_standard_path: str | None = None
    axis: str = "method"


class ComparativeEvaluationResponse(BaseModel):
    """Response payload containing comparative metrics between two runs.

    Parameters
    ----------
    comparison_id : str
        Unique comparison identifier.
    run_id_a : str
        First run identifier.
    run_id_b : str
        Second run identifier.
    axis : str
        Comparison axis.
    dataset_ref : str or None, optional
        Shared dataset reference.
    deltas : list of ComparativeMetricDelta
        Pairwise metric deltas and winner indicators.
    summary_markdown : str
        Formatted markdown comparison table.
    """

    comparison_id: str
    run_id_a: str
    run_id_b: str
    axis: str
    dataset_ref: str | None = None
    deltas: list[ComparativeMetricDelta] = Field(default_factory=list)
    summary_markdown: str = ""


class EvaluateManifestRequest(BaseModel):
    """Payload for triggering batch evaluation from a YAML manifest file.

    Parameters
    ----------
    manifest_path : str
        Filesystem path to the run manifest YAML.
    baseline : str or None, optional
        Optional comparative baseline override ('naive_kg', 'text_rag', 'zero_shot').
    build_graph : bool, default False
        Whether to invoke pipeline construction prior to evaluation scoring.
    """

    manifest_path: str
    baseline: str | None = None
    build_graph: bool = False
