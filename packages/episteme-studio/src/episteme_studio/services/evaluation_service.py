"""Service layer orchestrating knowledge graph evaluation queries and execution.

In accordance with SPEC §2, this service layer coordinates domain workflows
and remains free of FastAPI dependencies for complete unit testability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.adapters.evaluation_adapter import EvaluationAdapter
from episteme_studio.domain.evaluation import (
    BenchmarkDescriptor,
    ComparativeEvaluationResponse,
    EvaluateManifestRequest,
    EvaluateRunRequest,
    EvaluationReportDetail,
    EvaluationReportSummary,
    CompareRunsRequest,
)
from episteme_studio.settings import StudioSettings


class EvaluationService:
    """Service managing evaluation reports, benchmark execution, and baseline comparisons.

    Parameters
    ----------
    adapter : EvaluationAdapter
        Underlying evaluation adapter bridging to episteme-pipeline.
    reader : ArtifactReader
        Artifact reader for inspecting run intermediates.
    reports_dir : Path or str, default 'evaluation/reports'
        Output directory for evaluation reports.
    """

    def __init__(
        self,
        adapter: EvaluationAdapter,
        reader: ArtifactReader,
        reports_dir: Path | str = "evaluation/reports",
    ) -> None:
        self.adapter = adapter
        self.reader = reader
        self.reports_dir = Path(reports_dir)

    @classmethod
    def from_settings(cls, settings: StudioSettings) -> EvaluationService:
        """Instantiate EvaluationService from configuration settings.

        Parameters
        ----------
        settings : StudioSettings
            Application configuration settings.

        Returns
        -------
        EvaluationService
            Configured service instance.
        """
        adapter = EvaluationAdapter(
            reports_dir=settings.reports_dir,
        )
        reader = ArtifactReader(
            runs_dir=settings.runs_dir,
            artifacts_dir=settings.artifacts_dir,
            langfuse_host=settings.langfuse_host,
            extra_runs_dirs=settings.extra_runs_dirs,
            extra_artifacts_dirs=settings.extra_artifacts_dirs,
        )
        return cls(adapter=adapter, reader=reader, reports_dir=settings.reports_dir)

    def list_reports(
        self,
        run_id: str | None = None,
        outcome: str | None = None,
    ) -> list[EvaluationReportSummary]:
        """List all discovered evaluation report summaries.

        Parameters
        ----------
        run_id : str or None, optional
            Filter by participating run identifier.
        outcome : str or None, optional
            Filter by evaluation outcome ('pass', 'fail', 'warning').

        Returns
        -------
        list of EvaluationReportSummary
            Summaries sorted newest first.
        """
        return self.adapter.list_reports(run_id=run_id, outcome=outcome)

    def get_report(self, evaluation_id: str) -> EvaluationReportDetail | None:
        """Retrieve full detailed evaluation report by identifier.

        Parameters
        ----------
        evaluation_id : str
            Evaluation identifier.

        Returns
        -------
        EvaluationReportDetail or None
            Detailed report if found, None otherwise.
        """
        return self.adapter.get_report(evaluation_id)

    def get_run_evaluation(self, run_id: str) -> EvaluationReportDetail | None:
        """Retrieve the primary evaluation report associated with a pipeline run.

        Parameters
        ----------
        run_id : str
            Target run identifier.

        Returns
        -------
        EvaluationReportDetail or None
            Report detail if evaluated, None otherwise.
        """
        return self.adapter.get_report(run_id)

    async def evaluate_run(self, request: EvaluateRunRequest) -> EvaluationReportDetail:
        """Evaluate a completed pipeline run against a gold standard benchmark.

        Parameters
        ----------
        request : EvaluateRunRequest
            Run evaluation request parameters.

        Returns
        -------
        EvaluationReportDetail
            Synthesized evaluation report.
        """
        return await self.adapter.evaluate_run(
            run_id=request.run_id,
            reader=self.reader,
            gold_standard_path=request.gold_standard_path,
            benchmark_id=request.benchmark_id,
            queries_path=request.queries_path,
            strategy=request.strategy,
            baseline=request.baseline,
            min_mcc=request.min_mcc,
            min_pfs=request.min_pfs,
            sim_threshold=request.sim_threshold,
            persist=request.persist,
        )

    async def evaluate_manifest(self, request: EvaluateManifestRequest) -> EvaluationReportDetail:
        """Execute a batch evaluation configured by an immutable YAML manifest.

        Parameters
        ----------
        request : EvaluateManifestRequest
            Manifest evaluation request parameters.

        Returns
        -------
        EvaluationReportDetail
            Parsed evaluation report detail.
        """
        return await self.adapter.evaluate_manifest(
            manifest_path=request.manifest_path,
            baseline=request.baseline,
            build_graph=request.build_graph,
        )

    def compare_runs(self, request: CompareRunsRequest) -> ComparativeEvaluationResponse:
        """Compare two evaluated pipeline runs side-by-side.

        Parameters
        ----------
        request : CompareRunsRequest
            Run comparison request.

        Returns
        -------
        ComparativeEvaluationResponse
            Comparative metric deltas and summary markdown.
        """
        return self.adapter.compare_runs(
            run_id_a=request.run_id_a,
            run_id_b=request.run_id_b,
            axis=request.axis,
        )

    def list_benchmarks(self) -> list[BenchmarkDescriptor]:
        """List registered gold-standard benchmarks available for evaluation.

        Returns
        -------
        list of BenchmarkDescriptor
            Discovered benchmark descriptors.
        """
        return self.adapter.discover_benchmarks()

    def list_manifests(self) -> list[dict[str, Any]]:
        """List available declarative evaluation YAML manifests.

        Returns
        -------
        list of dict of str to Any
            Manifest descriptors.
        """
        return self.adapter.discover_manifests()
