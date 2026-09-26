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


class DynamicsStepDetail(BaseModel):
    """Detailed step transition in a diachronic theory evolution trajectory.

    Parameters
    ----------
    step : str
        Transition identifier (e.g. 'T_0 -> T_1').
    delta_auxiliary : int
        Count of auxiliary hypotheses introduced in this transition.
    anomalies_count : int
        Active empirical anomalies during this transition.
    delta_empirical : int
        Count of novel empirical paradigms or content elements introduced.
    step_degeneration_index : float
        Degeneration index evaluated for this single transition.
    """

    step: str
    delta_auxiliary: int
    anomalies_count: int
    delta_empirical: int
    step_degeneration_index: float


class DynamicsTrajectoryRequest(BaseModel):
    """Request payload to evaluate diachronic Lakatosian degeneration across successive runs.

    Parameters
    ----------
    run_ids : list of str, optional
        Chronological sequence of pipeline run identifiers [T_0, T_1, ..., T_k].
    snapshots : list of dict of str to Any, optional
        Explicit graph snapshot representations if evaluating in-memory or synthetic runs.
    core_node_ids : list of str, optional
        Specific hard-core axiom node identifiers to monitor for invariance.
    epsilon : float, default 1e-6
        Stability constant avoiding division by zero.
    """

    run_ids: list[str] = Field(default_factory=list)
    snapshots: list[dict[str, Any]] | None = None
    core_node_ids: list[str] | None = None
    epsilon: float = 1e-6


class DynamicsTrajectoryResponse(BaseModel):
    """Response payload containing multi-run diachronic trajectory and degeneration metrics.

    Parameters
    ----------
    degeneration_index : float
        Overall Lakatosian Degeneration Index (DI).
    is_progressive : bool
        Whether the trajectory satisfies progressive criteria (DI < 1.0 and core invariant).
    core_invariant : bool
        Whether hard-core axioms remained unchanged across all epochs.
    delta_auxiliary : int
        Total net addition of auxiliary protective belt hypotheses.
    anomalies_count : int
        Final count of unresolved empirical anomalies.
    delta_empirical_content : int
        Total novel empirical phenomena and paradigms explained.
    violated_invariance : list of dict of str to Any
        Details of any detected core mutations or deletions.
    node_immunization_scores : dict of str to float
        Per-node immunization index (II) detecting ad-hoc stratagems.
    trajectory : list of DynamicsStepDetail
        Epoch-by-epoch transition metrics.
    chart_data : dict of str to Any
        Pre-formatted series data for frontend plotting.
    summary_markdown : str
        Formatted Markdown analysis.
    """

    degeneration_index: float
    is_progressive: bool
    core_invariant: bool
    delta_auxiliary: int = 0
    anomalies_count: int = 0
    delta_empirical_content: int = 0
    violated_invariance: list[dict[str, Any]] = Field(default_factory=list)
    node_immunization_scores: dict[str, float] = Field(default_factory=dict)
    trajectory: list[DynamicsStepDetail] = Field(default_factory=list)
    chart_data: dict[str, Any] = Field(default_factory=dict)
    summary_markdown: str = ""


class AdjudicationDecision(StrEnum):
    """Review decision for a human-in-the-loop edge alignment.

    Attributes
    ----------
    TRUE_POSITIVE : str
        Alignment is empirically verified as correct.
    FALSE_POSITIVE : str
        Alignment is rejected as a hallucination or invalid link.
    SCHEMA_ALIAS : str
        Predicted relation is an acceptable semantic alias for the gold predicate.
    """

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    SCHEMA_ALIAS = "schema_alias"


class EdgeAdjudicationItem(BaseModel):
    """A human-adjudicated edge alignment decision.

    Parameters
    ----------
    adjudication_id : str
        Unique identifier for the adjudication record.
    predicted_edge : dict of str to Any
        Predicted relation descriptor (source, predicate, target, confidence).
    reference_edge : dict of str to Any or None, optional
        Candidate reference relation descriptor if partially aligned.
    similarity_score : float, default 0.0
        Similarity score from soft alignment (e.g. GM-GBS or cross-encoder).
    decision : AdjudicationDecision
        Expert verdict (true_positive, false_positive, or schema_alias).
    alias_target : str or None, optional
        Canonical target predicate name when decision is schema_alias.
    rationale : str or None, optional
        Expert commentary or rationale.
    adjudicated_by : str or None, optional
        Identifier of the human reviewer.
    adjudicated_at : datetime
        Timestamp of adjudication.
    """

    adjudication_id: str = Field(default_factory=lambda: f"adj_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}")
    predicted_edge: dict[str, Any]
    reference_edge: dict[str, Any] | None = None
    similarity_score: float = 0.0
    decision: AdjudicationDecision
    alias_target: str | None = None
    rationale: str | None = None
    adjudicated_by: str | None = None
    adjudicated_at: datetime = Field(default_factory=utc_now)


class AdjudicationRequest(BaseModel):
    """Payload to submit edge review adjudications and optionally export curated gold standard.

    Parameters
    ----------
    items : list of EdgeAdjudicationItem
        Adjudication decisions to register.
    gold_standard_path : str or None, optional
        Source reference gold standard path to merge with.
    export_dataset_path : str or None, optional
        Target filesystem path to export the curated JSON-LD dataset.
    """

    items: list[EdgeAdjudicationItem] = Field(default_factory=list)
    gold_standard_path: str | None = None
    export_dataset_path: str | None = None


class AdjudicationResponse(BaseModel):
    """Outcome summary of processed edge adjudications.

    Parameters
    ----------
    adjudicated_count : int
        Count of recorded adjudications.
    stored_items : list of EdgeAdjudicationItem
        Registered adjudication records.
    exported_gold_path : str or None, optional
        Filesystem path of the curated gold standard dataset if exported.
    message : str, default ''
        Informational status message.
    """

    adjudicated_count: int
    stored_items: list[EdgeAdjudicationItem] = Field(default_factory=list)
    exported_gold_path: str | None = None
    message: str = ""


class EvaluationJobStatus(StrEnum):
    """Lifecycle state of an asynchronous evaluation job.

    Attributes
    ----------
    PENDING : str
        Job queued but not yet running.
    RUNNING : str
        Job actively evaluating stages or ranking queries.
    COMPLETED : str
        Job finished successfully with report synthesized.
    FAILED : str
        Job encountered an unhandled execution error.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationJobDescriptor(BaseModel):
    """Descriptor tracking an asynchronous batch evaluation task.

    Parameters
    ----------
    job_id : str
        Unique job identifier.
    status : EvaluationJobStatus
        Current lifecycle state.
    created_at : datetime
        Timestamp when job was created.
    completed_at : datetime or None, optional
        Timestamp when job completed or failed.
    request_type : str, default 'manifest'
        Type of evaluation ('manifest' or 'run').
    report_id : str or None, optional
        Identifier of the generated evaluation report once complete.
    error : str or None, optional
        Error message if execution failed.
    report : EvaluationReportDetail or None, optional
        Synthesized report detail once completed.
    """

    job_id: str
    status: EvaluationJobStatus
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    request_type: str = "manifest"
    report_id: str | None = None
    error: str | None = None
    report: EvaluationReportDetail | None = None


class StartEvaluationJobRequest(BaseModel):
    """Request payload to initiate an asynchronous batch evaluation job.

    Parameters
    ----------
    manifest_path : str or None, optional
        Filesystem path to evaluation YAML manifest.
    run_id : str or None, optional
        Target run identifier if evaluating an existing run.
    benchmark_id : str or None, optional
        Registered benchmark identifier.
    gold_standard_path : str or None, optional
        Custom gold reference path.
    baseline : str or None, optional
        Comparative baseline override.
    build_graph : bool, default False
        Whether to construct graph before scoring.
    """

    manifest_path: str | None = None
    run_id: str | None = None
    benchmark_id: str | None = None
    gold_standard_path: str | None = None
    baseline: str | None = None
    build_graph: bool = False


# =============================================================================
# Evaluation Workbench & Interactive Analytics Models (ISSUE-026 - ISSUE-033)
# =============================================================================


class NodeAlignmentStatus(StrEnum):
    """Alignment classification of an evaluated graph node against reference standard.

    Attributes
    ----------
    TRUE_POSITIVE : str
        Predicted node correctly aligned with a reference gold component.
    FALSE_POSITIVE : str
        Predicted node extracted without corresponding empirical reference.
    FALSE_NEGATIVE : str
        Reference gold component omitted from predicted graph (rendered as ghost node).
    BORDERLINE : str
        Alignment requires expert human adjudication.
    """

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    BORDERLINE = "borderline"


class EdgeAlignmentStatus(StrEnum):
    """Alignment classification of an evaluated graph relation against reference standard.

    Attributes
    ----------
    TRUE_POSITIVE : str
        Predicted relation verified against reference standard.
    FALSE_POSITIVE : str
        Predicted relation not supported by reference standard.
    FALSE_NEGATIVE : str
        Reference relation omitted from predicted graph (rendered as ghost edge).
    BORDERLINE : str
        Relation alignment score falls in uncertainty band [0.80, 0.94].
    POLARITY_CONFLICT : str
        Relation endpoints match but epistemic polarity is inverted (e.g. SUPPORT vs ATTACK).
    """

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    BORDERLINE = "borderline"
    POLARITY_CONFLICT = "polarity_conflict"


class EvaluationNodeOverlay(BaseModel):
    """Interactive node representation for canvas evaluation error projection.

    Parameters
    ----------
    id : str
        Node identifier.
    label : str
        Human-readable entity or axiom label.
    class_name : str or None, optional
        Bourbaki structuralist model class (e.g. 'actual_models', 'potential_models').
    symbol : str or None, optional
        Mathematical symbol (e.g. 'M', 'Mp', 'C', 'I').
    alignment_status : NodeAlignmentStatus
        Verification state (true_positive, false_positive, false_negative, borderline).
    gold_id : str or None, optional
        Matched reference entity ID if aligned.
    similarity_score : float, default 1.0
        Semantic similarity score.
    is_ghost : bool, default False
        True if synthesized from reference standard to render omitted components.
    properties : dict of str to Any, optional
        Additional attributes and violation tags.
    """

    id: str
    label: str
    class_name: str | None = None
    symbol: str | None = None
    alignment_status: NodeAlignmentStatus = NodeAlignmentStatus.TRUE_POSITIVE
    gold_id: str | None = None
    similarity_score: float = 1.0
    is_ghost: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class EvaluationEdgeOverlay(BaseModel):
    """Interactive edge representation for canvas evaluation error projection.

    Parameters
    ----------
    id : str
        Edge identifier.
    source : str
        Source node identifier.
    target : str
        Target node identifier.
    predicate : str
        Relationship predicate name.
    alignment_status : EdgeAlignmentStatus
        Edge alignment state.
    gold_predicate : str or None, optional
        Candidate reference relation predicate.
    similarity_score : float, default 1.0
        Semantic or embedding alignment score.
    is_ghost : bool, default False
        True if synthesized from reference standard.
    evidence_snippet : str or None, optional
        Primary source quote or bounding box coordinates.
    """

    id: str
    source: str
    target: str
    predicate: str
    alignment_status: EdgeAlignmentStatus = EdgeAlignmentStatus.TRUE_POSITIVE
    gold_predicate: str | None = None
    similarity_score: float = 1.0
    is_ghost: bool = False
    evidence_snippet: str | None = None


class EvaluationGraphOverlay(BaseModel):
    """Full graph canvas overlay for projecting evaluation alignment and errors.

    Parameters
    ----------
    evaluation_id : str
        Evaluation report identifier.
    run_id : str
        Participating run identifier.
    benchmark_id : str or None, optional
        Target benchmark dataset reference.
    nodes : list of EvaluationNodeOverlay
        Visual nodes with alignment classifications.
    edges : list of EvaluationEdgeOverlay
        Visual edges with alignment classifications.
    summary_counts : dict of str to int
        Breakdown counts of TP, FP, FN, and conflict elements.
    """

    evaluation_id: str
    run_id: str
    benchmark_id: str | None = None
    nodes: list[EvaluationNodeOverlay] = Field(default_factory=list)
    edges: list[EvaluationEdgeOverlay] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)


class AdjudicationQueueItem(BaseModel):
    """Borderline candidate alignment item queued for human expert adjudication.

    Parameters
    ----------
    candidate_id : str
        Unique candidate identifier.
    evaluation_id : str
        Parent evaluation identifier.
    predicted_edge : dict of str to Any
        Extracted relation descriptor (source, predicate, target).
    reference_edge : dict of str to Any or None, optional
        Candidate reference relation descriptor.
    similarity_score : float
        Soft alignment similarity score in uncertainty window.
    status : str, default 'pending'
        Triage status ('pending' or 'adjudicated').
    current_decision : AdjudicationDecision or None, optional
        Decision recorded if previously reviewed.
    alias_target : str or None, optional
        Canonical predicate name if classified as schema alias.
    evidence_snippet : str or None, optional
        Source text passage or bounding box reference.
    confidence : float, default 1.0
        Original extraction confidence.
    """

    candidate_id: str
    evaluation_id: str
    predicted_edge: dict[str, Any]
    reference_edge: dict[str, Any] | None = None
    similarity_score: float = 0.0
    status: str = "pending"
    current_decision: AdjudicationDecision | None = None
    alias_target: str | None = None
    evidence_snippet: str | None = None
    confidence: float = 1.0


class AdjudicationQueueResponse(BaseModel):
    """Response payload containing candidate relation triage queue.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    total_candidates : int
        Total candidate pairs discovered.
    pending_count : int
        Count of unreviewed candidate pairs.
    adjudicated_count : int
        Count of completed candidate reviews.
    candidates : list of AdjudicationQueueItem
        Candidate items matching requested filter.
    """

    evaluation_id: str
    total_candidates: int
    pending_count: int
    adjudicated_count: int
    candidates: list[AdjudicationQueueItem] = Field(default_factory=list)


class AdjudicateAndRecalculateRequest(BaseModel):
    """Payload to submit edge adjudications and dynamically recompute evaluation scores.

    Parameters
    ----------
    items : list of EdgeAdjudicationItem
        Review adjudications to register.
    export_dataset_path : str or None, optional
        Target filesystem path to export curated gold standard.
    """

    items: list[EdgeAdjudicationItem] = Field(default_factory=list)
    export_dataset_path: str | None = None


class AdjudicateAndRecalculateResponse(BaseModel):
    """Outcome payload with live recalculated evaluation metrics and deltas.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    adjudicated_count : int
        Number of items processed.
    updated_report : EvaluationReportDetail
        Re-evaluated report with updated metrics.
    metric_deltas : dict of str to float
        Instant score differences (e.g. {'f1': +0.03, 'mcc': 0.0}).
    message : str, default ''
        Informational status message.
    """

    evaluation_id: str
    adjudicated_count: int
    updated_report: EvaluationReportDetail
    metric_deltas: dict[str, float] = Field(default_factory=dict)
    message: str = ""


class CalibrationBinDetail(BaseModel):
    """Binned sample statistics for plotting reliability diagrams.

    Parameters
    ----------
    bin_index : int
        Index of the probability interval [0..num_bins-1].
    bin_lower : float
        Lower confidence boundary.
    bin_upper : float
        Upper confidence boundary.
    sample_count : int
        Number of samples in this confidence bucket.
    mean_confidence : float
        Average predicted probability within bin.
    empirical_accuracy : float
        Observed true positive ratio within bin.
    calibration_gap : float
        Absolute discrepancy |mean_confidence - empirical_accuracy|.
    """

    bin_index: int
    bin_lower: float
    bin_upper: float
    sample_count: int
    mean_confidence: float
    empirical_accuracy: float
    calibration_gap: float


class MiscalibratedAssertionItem(BaseModel):
    """Diagnostic descriptor of an overconfident false assertion.

    Parameters
    ----------
    assertion_id : str
        Assertion identifier.
    assertion_type : str
        Type of assertion ('triple', 'entity', 'axiom').
    descriptor : str
        Human-readable assertion summary.
    confidence : float
        High predicted probability score.
    empirical_match : bool, default False
        Empirical ground-truth verification outcome.
    discrepancy : float
        Miscalibration error magnitude.
    evidence_text : str or None, optional
        Source passage snippet.
    rationale : str or None, optional
        Explanation of omission or hallucination.
    """

    assertion_id: str
    assertion_type: str = "triple"
    descriptor: str
    confidence: float
    empirical_match: bool = False
    discrepancy: float = 0.0
    evidence_text: str | None = None
    rationale: str | None = None


class CalibrationReportDetail(BaseModel):
    """Detailed probability calibration diagnostics and reliability diagram data.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    run_id : str
        Evaluated run identifier.
    expected_calibration_error : float
        Expected Calibration Error (ECE).
    maximum_calibration_error : float
        Maximum Calibration Error (MCE).
    brier_score : float
        Mean squared probability error.
    is_well_calibrated : bool
        Whether ECE satisfies threshold constraints (e.g. ECE < 0.05).
    num_samples : int
        Total samples evaluated.
    bins : list of CalibrationBinDetail
        Binned calibration series for reliability curves.
    high_confidence_hallucinations : list of MiscalibratedAssertionItem
        High-confidence assertions that failed empirical verification.
    chart_series : dict of str to Any
        Pre-structured series dataset for frontend plotting.
    """

    evaluation_id: str
    run_id: str
    expected_calibration_error: float
    maximum_calibration_error: float
    brier_score: float
    is_well_calibrated: bool
    num_samples: int
    bins: list[CalibrationBinDetail] = Field(default_factory=list)
    high_confidence_hallucinations: list[MiscalibratedAssertionItem] = Field(default_factory=list)
    chart_series: dict[str, Any] = Field(default_factory=dict)


class BoundingBoxCoordinates(BaseModel):
    """Normalized bounding box coordinates on a scientific document page.

    Parameters
    ----------
    page : int
        Page number (1-indexed).
    x0 : float
        Normalized left coordinate [0.0, 1.0].
    y0 : float
        Normalized top coordinate [0.0, 1.0].
    x1 : float
        Normalized right coordinate [0.0, 1.0].
    y1 : float
        Normalized bottom coordinate [0.0, 1.0].
    """

    page: int
    x0: float
    y0: float
    x1: float
    y1: float


class MultiModalEvidenceAnchor(BaseModel):
    """Evidence anchor linking an extracted construct to multimodal source materials.

    Parameters
    ----------
    anchor_id : str
        Unique anchor identifier.
    doc_id : str
        Source document identifier.
    media_type : str, default 'text'
        Modality type ('text', 'figure', 'equation', 'table').
    verbatim_text : str or None, optional
        Verbatim primary source text quote.
    char_start : int or None, optional
        Character start offset.
    char_end : int or None, optional
        Character end offset.
    bbox : BoundingBoxCoordinates or None, optional
        Visual bounding box if grounded in a diagram or table.
    formula_latex : str or None, optional
        Extracted LaTeX formula if grounded in a math block.
    image_uri : str or None, optional
        URI to cropped snippet or diagram.
    """

    anchor_id: str
    doc_id: str
    media_type: str = "text"
    verbatim_text: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    bbox: BoundingBoxCoordinates | None = None
    formula_latex: str | None = None
    image_uri: str | None = None


class GroundingEvaluationDetail(BaseModel):
    """Detailed multimodal evidence grounding evaluation for a specific theory component.

    Parameters
    ----------
    component_id : str
        Evaluated construct identifier.
    component_type : str
        Construct type ('entity', 'triple', 'axiom').
    label : str
        Human-readable component label.
    predicted_anchor : MultiModalEvidenceAnchor or None, optional
        Evidence anchor produced by the extraction pipeline.
    reference_anchor : MultiModalEvidenceAnchor or None, optional
        Gold reference evidence anchor.
    iou_score : float, default 1.0
        Alignment Grounding IoU (AG_IoU) score.
    grounding_passed : bool, default True
        Whether grounding meets minimum threshold.
    failure_reason : str or None, optional
        Explanation if grounding verification failed.
    """

    component_id: str
    component_type: str = "axiom"
    label: str
    predicted_anchor: MultiModalEvidenceAnchor | None = None
    reference_anchor: MultiModalEvidenceAnchor | None = None
    iou_score: float = 1.0
    grounding_passed: bool = True
    failure_reason: str | None = None


class LeaderboardEntry(BaseModel):
    """Individual run entry in a multi-run benchmark leaderboard matrix.

    Parameters
    ----------
    run_id : str
        Pipeline run identifier.
    evaluation_id : str
        Associated evaluation report identifier.
    benchmark_id : str
        Benchmark identifier evaluated against.
    model_name : str or None, optional
        Underlying LLM or pipeline model name.
    prompt_strategy : str or None, optional
        Prompt strategy or ablation configuration.
    outcome : EvaluationOutcome
        Overall pass/fail outcome.
    evaluated_at : datetime
        Timestamp when evaluation completed.
    metrics : dict of str to float
        Headline KPI scores (mcc, f1, ece, mrr, etc.).
    total_cost_usd : float or None, optional
        Estimated token/API compute cost in USD.
    duration_seconds : float or None, optional
        Execution latency in seconds.
    is_pareto_optimal : bool, default False
        Whether this run resides on the non-dominated Pareto frontier.
    """

    run_id: str
    evaluation_id: str
    benchmark_id: str
    model_name: str | None = None
    prompt_strategy: str | None = None
    outcome: EvaluationOutcome = EvaluationOutcome.INCONCLUSIVE
    evaluated_at: datetime = Field(default_factory=utc_now)
    metrics: dict[str, float] = Field(default_factory=dict)
    total_cost_usd: float | None = None
    duration_seconds: float | None = None
    is_pareto_optimal: bool = False


class ParetoFrontierPoint(BaseModel):
    """A point in multi-dimensional objective space representing a non-dominated run.

    Parameters
    ----------
    run_id : str
        Run identifier.
    coordinates : dict of str to float
        Objective metric coordinates (e.g. {'f1': 0.90, 'cost': 0.12}).
    dominated_by : list of str
        Identifiers of any runs dominating this point.
    """

    run_id: str
    coordinates: dict[str, float]
    dominated_by: list[str] = Field(default_factory=list)


class LeaderboardRequest(BaseModel):
    """Request payload to construct a multi-run benchmark leaderboard and Pareto frontier.

    Parameters
    ----------
    benchmark_id : str or None, optional
        Benchmark identifier to filter runs by.
    run_ids : list of str, optional
        Specific list of run IDs to include.
    pareto_axes : list of str, default ['f1', 'ece']
        Metrics to evaluate for Pareto non-dominance.
    sort_by : str, default 'f1'
        Primary metric to sort leaderboard entries by.
    ascending : bool, default False
        Sort direction.
    """

    benchmark_id: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    pareto_axes: list[str] = Field(default_factory=lambda: ["f1", "ece"])
    sort_by: str = "f1"
    ascending: bool = False


class LeaderboardResponse(BaseModel):
    """Response payload containing benchmark leaderboard matrix and Pareto frontier.

    Parameters
    ----------
    benchmark_id : str or None, optional
        Benchmark identifier evaluated.
    total_runs : int
        Number of participating runs.
    entries : list of LeaderboardEntry
        Sorted run entries.
    pareto_frontier : list of ParetoFrontierPoint
        Identified non-dominated Pareto points.
    summary_markdown : str, default ''
        Formatted markdown leaderboard table.
    """

    benchmark_id: str | None = None
    total_runs: int
    entries: list[LeaderboardEntry] = Field(default_factory=list)
    pareto_frontier: list[ParetoFrontierPoint] = Field(default_factory=list)
    summary_markdown: str = ""


class PerturbationType(StrEnum):
    """Category of synthetic adversarial noise applied to primary text inputs.

    Attributes
    ----------
    TYPO_INSERTION : str
        Character-level typographical insertions and deletions.
    SYNONYM_REPLACEMENT : str
        Domain synonym substitution causing terminology drift.
    SENTENCE_SHUFFLE : str
        Discourse sentence order permutations.
    COMPOSITE : str
        Mixed multi-perturbation stress test.
    """

    TYPO_INSERTION = "typo_insertion"
    SYNONYM_REPLACEMENT = "synonym_replacement"
    SENTENCE_SHUFFLE = "sentence_shuffle"
    COMPOSITE = "composite"


class PerturbationSweepPoint(BaseModel):
    """Evaluated metric score at a specific adversarial noise rate.

    Parameters
    ----------
    noise_level : float
        Perturbation fraction rate (e.g. 0.05, 0.10, 0.20).
    f1_score : float
        Achieved relation extraction F1 score.
    mcc_score : float
        Achieved model component completeness.
    poset_dag_valid : bool
        Whether specialization hierarchy remained an acyclic DAG.
    rdf_delta : float
        Degradation magnitude at this noise rate.
    """

    noise_level: float
    f1_score: float
    mcc_score: float
    poset_dag_valid: bool = True
    rdf_delta: float = 0.0


class NoiseRobustnessReportDetail(BaseModel):
    """Comprehensive adversarial stress-testing and noise robustness evaluation report.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    run_id : str
        Baseline run identifier.
    overall_rdf : float
        Synthesized Robustness Degradation Factor (RDF).
    is_resilient : bool
        True if overall_rdf meets resilience threshold (e.g. RDF < 0.15).
    baseline_f1 : float
        Clean baseline F1 score.
    worst_case_f1 : float
        Minimum F1 achieved under maximum perturbation.
    breakdown_by_perturbation : dict of str to list of PerturbationSweepPoint
        Degradation series keyed by perturbation type.
    chart_series : dict of str to Any
        Pre-formatted line series data for frontend plotting.
    """

    evaluation_id: str
    run_id: str
    overall_rdf: float
    is_resilient: bool
    baseline_f1: float
    worst_case_f1: float
    breakdown_by_perturbation: dict[str, list[PerturbationSweepPoint]] = Field(default_factory=dict)
    chart_series: dict[str, Any] = Field(default_factory=dict)


class StressTestRequest(BaseModel):
    """Payload to trigger adversarial noise perturbation sweeps against a run.

    Parameters
    ----------
    run_id : str
        Target run identifier to stress test.
    benchmark_id : str or None, optional
        Target benchmark dataset.
    perturbation_types : list of PerturbationType
        Types of noise to apply.
    noise_levels : list of float, default [0.05, 0.10, 0.20]
        Noise rates to evaluate.
    """

    run_id: str
    benchmark_id: str | None = None
    perturbation_types: list[PerturbationType] = Field(
        default_factory=lambda: [PerturbationType.TYPO_INSERTION, PerturbationType.SYNONYM_REPLACEMENT]
    )
    noise_levels: list[float] = Field(default_factory=lambda: [0.05, 0.10, 0.20])


class RetrievedCandidateItem(BaseModel):
    """Ranked knowledge graph node returned for a competency question.

    Parameters
    ----------
    rank : int
        Position in ranked result list (1-indexed).
    node_id : str
        Retrieved node identifier.
    label : str
        Human-readable label.
    class_name : str or None, optional
        Model class or ontology type.
    similarity_score : float
        Retrieval similarity score.
    is_gold_target : bool
        Whether this node is an expected gold answer.
    """

    rank: int
    node_id: str
    label: str
    class_name: str | None = None
    similarity_score: float = 0.0
    is_gold_target: bool = False


class CompetencyQueryDiagnosticItem(BaseModel):
    """Detailed evaluation diagnostics for a single downstream competency query.

    Parameters
    ----------
    query_id : str
        Unique query identifier.
    query_text : str
        Natural language competency question.
    target_category : str or None, optional
        Thematic category of the query.
    expected_gold_nodes : list of str
        Identifiers of expected answer nodes.
    retrieved_candidates : list of RetrievedCandidateItem
        Ranked candidate nodes retrieved.
    first_hit_rank : int or None, optional
        Rank of first relevant target (None if not in top K).
    reciprocal_rank : float, default 0.0
        1 / first_hit_rank.
    hits_at_1 : bool, default False
        True if first target was at rank 1.
    hits_at_3 : bool, default False
        True if target was in top 3.
    hits_at_10 : bool, default False
        True if target was in top 10.
    failure_mode : str or None, optional
        Classification of retrieval failure ('omitted_node', 'rank_cutoff', 'low_similarity').
    """

    query_id: str
    query_text: str
    target_category: str | None = None
    expected_gold_nodes: list[str] = Field(default_factory=list)
    retrieved_candidates: list[RetrievedCandidateItem] = Field(default_factory=list)
    first_hit_rank: int | None = None
    reciprocal_rank: float = 0.0
    hits_at_1: bool = False
    hits_at_3: bool = False
    hits_at_10: bool = False
    failure_mode: str | None = None


class RetrievalDiagnosticsResponse(BaseModel):
    """Response payload detailing query-by-query downstream retrieval effectiveness.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    total_queries : int
        Total competency queries evaluated.
    mrr : float
        Mean Reciprocal Rank across queries.
    hits_at_1 : float
        Hits@1 success rate.
    hits_at_10 : float
        Hits@10 success rate.
    queries : list of CompetencyQueryDiagnosticItem
        Per-query diagnostic breakdown.
    """

    evaluation_id: str
    total_queries: int
    mrr: float = 0.0
    hits_at_1: float = 0.0
    hits_at_10: float = 0.0
    queries: list[CompetencyQueryDiagnosticItem] = Field(default_factory=list)


class BenchmarkValidationIssue(BaseModel):
    """Validation anomaly or schema violation detected in a benchmark dataset.

    Parameters
    ----------
    severity : str
        Severity level ('error', 'warning').
    rule_id : str
        Machine-readable rule identifier (e.g. 'DAG_CYCLE_DETECTED', 'DUPLICATE_ID').
    message : str
        Human-readable explanation.
    location : str or None, optional
        JSON-LD path or element identifier where error occurred.
    """

    severity: str = "error"
    rule_id: str
    message: str
    location: str | None = None


class BenchmarkValidationResult(BaseModel):
    """Outcome report from pre-flight benchmark dataset linting.

    Parameters
    ----------
    is_valid : bool
        True if dataset passes all validation rules with zero errors.
    total_entities : int, default 0
        Number of parsed theory constructs.
    total_triples : int, default 0
        Number of parsed relationships.
    is_dag : bool, default True
        Whether specialization relations form an acyclic directed graph.
    root_element : str or None, optional
        Detected single root theory atom T_0.
    issues : list of BenchmarkValidationIssue
        Discovered validation issues or warnings.
    """

    is_valid: bool
    total_entities: int = 0
    total_triples: int = 0
    is_dag: bool = True
    root_element: str | None = None
    issues: list[BenchmarkValidationIssue] = Field(default_factory=list)


class RegisterBenchmarkRequest(BaseModel):
    """Payload to register a new gold-standard benchmark in Episteme Studio.

    Parameters
    ----------
    id : str
        Unique benchmark identifier (slug format).
    name : str
        Human-readable title.
    description : str
        Methodological and scientific description.
    task_type : str, default 'structuralist'
        Benchmark task type ('structuralist', 'extraction', 'argumentation', 'retrieval').
    gold_standard_jsonld : str
        Raw JSON-LD content string or filesystem path.
    queries_yaml : str or None, optional
        Raw YAML content or path for competency queries.
    """

    id: str
    name: str
    description: str
    task_type: str = "structuralist"
    gold_standard_jsonld: str
    queries_yaml: str | None = None
