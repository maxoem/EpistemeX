"""Tests for the evaluation scaffolding package."""

from episteme_pipeline.evaluation import (
    ComparisonAxis,
    DatasetReference,
    DatasetType,
    EvaluationComparison,
    EvaluationDataset,
    EvaluationErrorBucket,
    EvaluationJudgment,
    EvaluationLevel,
    EvaluationMetric,
    EvaluationOutcome,
    EvaluationReport,
    EvaluationResult,
    EvaluationRubric,
    RatingLevel,
    RubricCriterion,
    RunComparison,
)

# ---------------------------------------------------------------------------
# EvaluationResult
# ---------------------------------------------------------------------------


class TestEvaluationResult:
    def test_default_values(self):
        result = EvaluationResult(
            run_id="run-001", evaluation_level=EvaluationLevel.COMPONENT
        )
        assert result.metrics == []
        assert result.error_buckets == []
        assert result.artifact_refs == []
        assert result.notes == {}
        assert result.outcome == EvaluationOutcome.INCONCLUSIVE
        assert result.phase_name is None
        assert result.dataset_ref is None
        assert result.dataset_type is None
        assert result.evaluated_at is not None

    def test_with_metrics(self):
        result = EvaluationResult(
            run_id="run-001",
            evaluation_level=EvaluationLevel.STAGE,
            phase_name="Phase 3: Global Relation Extraction",
            metrics=[
                EvaluationMetric(name="precision", value=0.85, unit="ratio"),
                EvaluationMetric(name="recall", value=0.72, unit="ratio"),
            ],
        )
        assert len(result.metrics) == 2
        assert result.metrics[0].passes_threshold is None

    def test_with_thresholds(self):
        result = EvaluationResult(
            run_id="run-001",
            evaluation_level=EvaluationLevel.COMPONENT,
            metrics=[
                EvaluationMetric(
                    name="f1", value=0.79, threshold=0.75, passes_threshold=True
                ),
            ],
        )
        assert result.metrics[0].passes_threshold is True

    def test_with_error_buckets(self):
        result = EvaluationResult(
            run_id="run-001",
            evaluation_level=EvaluationLevel.STAGE,
            error_buckets=[
                EvaluationErrorBucket(bucket="false_merge", count=3),
                EvaluationErrorBucket(
                    bucket="false_split",
                    count=7,
                    description="Split across entity clusters",
                ),
            ],
        )
        assert len(result.error_buckets) == 2
        assert result.error_buckets[0].bucket == "false_merge"
        assert result.error_buckets[1].description == "Split across entity clusters"

    def test_with_artifact_refs(self):
        result = EvaluationResult(
            run_id="run-001",
            evaluation_level=EvaluationLevel.END_TO_END,
            artifact_refs=["artifact-001", "artifact-002"],
        )
        assert result.artifact_refs == ["artifact-001", "artifact-002"]

    def test_pass_outcome(self):
        result = EvaluationResult(
            run_id="run-001",
            evaluation_level=EvaluationLevel.COMPONENT,
            outcome=EvaluationOutcome.PASS,
        )
        assert result.outcome == EvaluationOutcome.PASS

    def test_with_dataset_type(self):
        result = EvaluationResult(
            run_id="run-001",
            evaluation_level=EvaluationLevel.DOWNSTREAM,
            dataset_ref="dataset-review-001",
            dataset_type=DatasetType.REVIEW,
        )
        assert result.dataset_type == DatasetType.REVIEW


# ---------------------------------------------------------------------------
# EvaluationReport
# ---------------------------------------------------------------------------


class TestEvaluationReport:
    def test_default_values(self):
        report = EvaluationReport(evaluation_id="eval-001", run_ids=["run-001"])
        assert report.results_by_level == {}
        assert report.summary == ""
        assert report.schema_version is None
        assert report.pipeline_version is None
        assert report.created_at is not None
        assert report.created_at is not None

    def test_with_results_by_level(self):
        report = EvaluationReport(
            evaluation_id="eval-001",
            run_ids=["run-001"],
            dataset_ref="gold-001",
            dataset_type=DatasetType.GOLD,
            schema_version="v2",
            pipeline_version="0.1.0",
            results_by_level={
                EvaluationLevel.STAGE: [
                    EvaluationResult(
                        run_id="run-001",
                        evaluation_level=EvaluationLevel.STAGE,
                        phase_name="Phase 3: Global Relation Extraction",
                        metrics=[EvaluationMetric(name="f1", value=0.79)],
                    ),
                ],
            },
        )
        assert len(report.results_by_level[EvaluationLevel.STAGE]) == 1
        assert report.schema_version == "v2"
        assert report.pipeline_version == "0.1.0"


# ---------------------------------------------------------------------------
# EvaluationDataset
# ---------------------------------------------------------------------------


class TestEvaluationDataset:
    def test_defaults(self):
        dataset = EvaluationDataset(
            dataset_id="gold-001",
            name="Gold Standard Entities",
            dataset_type="gold",
        )
        assert dataset.references == []
        assert dataset.corpus_ref is None
        assert dataset.schema_version is None
        assert dataset.pipeline_version is None

    def test_with_references(self):
        dataset = EvaluationDataset(
            dataset_id="silver-001",
            name="Silver Standard Relations",
            dataset_type="silver",
            corpus_ref="corpus-philosophy-001",
            schema_version="v1",
            references=[
                DatasetReference(
                    dataset_id="ref-001",
                    dataset_type="gold",
                    source_paths=["data/labeled_relations.json"],
                ),
            ],
        )
        assert len(dataset.references) == 1
        assert dataset.references[0].source_paths == ["data/labeled_relations.json"]


# ---------------------------------------------------------------------------
# EvaluationRubric
# ---------------------------------------------------------------------------


class TestEvaluationRubric:
    def test_empty_criteria(self):
        rubric = EvaluationRubric(
            rubric_id="rubric-001",
            name="Global Relation Quality",
            evaluation_level="stage",
        )
        assert rubric.criteria == []

    def test_with_criteria(self):
        rubric = EvaluationRubric(
            rubric_id="rubric-001",
            name="Global Relation Quality",
            evaluation_level="stage",
            criteria=[
                RubricCriterion(
                    name="evidence_strength",
                    description="Sufficiency of source evidence for the relation",
                    levels=[
                        RatingLevel(
                            level="none",
                            label="No Evidence",
                            description="No supporting text",
                            score=0.0,
                        ),
                        RatingLevel(
                            level="weak",
                            label="Weak Evidence",
                            description="One weak mention",
                            score=0.3,
                        ),
                        RatingLevel(
                            level="strong",
                            label="Strong Evidence",
                            description="Multiple consistent mentions",
                            score=1.0,
                        ),
                    ],
                ),
            ],
        )
        assert len(rubric.criteria) == 1
        assert len(rubric.criteria[0].levels) == 3
        assert rubric.criteria[0].levels[-1].score == 1.0


# ---------------------------------------------------------------------------
# EvaluationJudgment
# ---------------------------------------------------------------------------


class TestEvaluationJudgment:
    def test_defaults(self):
        judgment = EvaluationJudgment(
            artifact_ref="artifact-001",
            rubric="rubric-001",
            criterion="evidence_strength",
            level="strong",
            score=1.0,
        )
        assert judgment.reviewer_id == ""
        assert judgment.run_id == ""
        assert judgment.notes == ""

    def test_with_run_linkage(self):
        judgment = EvaluationJudgment(
            artifact_ref="artifact-002",
            rubric="rubric-001",
            criterion="evidence_strength",
            level="weak",
            score=0.3,
            reviewer_id="reviewer-a",
            run_id="run-001",
            notes="Only one distant mention found.",
        )
        assert judgment.run_id == "run-001"
        assert judgment.reviewer_id == "reviewer-a"


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


class TestEvaluationComparison:
    def test_empty_pairwise(self):
        comparison = EvaluationComparison(
            comparison_id="comp-001",
            run_ids=["run-001", "run-002"],
            axis=ComparisonAxis.METHOD,
        )
        assert comparison.pairwise_comparisons == []
        assert comparison.summary == ""

    def test_with_pairwise(self):
        comparison = EvaluationComparison(
            comparison_id="comp-001",
            run_ids=["run-001", "run-002"],
            axis=ComparisonAxis.THRESHOLD,
            dataset_ref="gold-001",
            pairwise_comparisons=[
                RunComparison(
                    run_id_a="run-001",
                    run_id_b="run-002",
                    metric_name="f1",
                    value_a=0.79,
                    value_b=0.82,
                    delta=0.03,
                    winner="b",
                ),
            ],
        )
        assert len(comparison.pairwise_comparisons) == 1
        assert comparison.pairwise_comparisons[0].winner == "b"

    def test_tie(self):
        comparison = EvaluationComparison(
            comparison_id="comp-002",
            run_ids=["run-001", "run-002"],
            axis=ComparisonAxis.PROMPT,
            pairwise_comparisons=[
                RunComparison(
                    run_id_a="run-001",
                    run_id_b="run-002",
                    metric_name="precision",
                    value_a=0.88,
                    value_b=0.88,
                    delta=0.0,
                    winner=None,
                ),
            ],
        )
        assert comparison.pairwise_comparisons[0].winner is None
        assert comparison.pairwise_comparisons[0].delta == 0.0


# ---------------------------------------------------------------------------
# Package-level imports
# ---------------------------------------------------------------------------


class TestPackageImports:
    def test_all_exports(self):
        from episteme_pipeline.evaluation import __all__

        assert "EvaluationReport" in __all__
        assert "EvaluationResult" in __all__
        assert "EvaluationDataset" in __all__
        assert "EvaluationRubric" in __all__
        assert "EvaluationComparison" in __all__
        assert "EvaluationLevel" in __all__
        assert "DatasetType" in __all__
        assert "EvaluationOutcome" in __all__
        assert "EvaluationMetric" in __all__
        assert "EvaluationErrorBucket" in __all__
        assert "EvaluationJudgment" in __all__
        assert "RatingLevel" in __all__
        assert "RubricCriterion" in __all__
        assert "ComparisonAxis" in __all__
        assert "RunComparison" in __all__
        assert "DatasetReference" in __all__
