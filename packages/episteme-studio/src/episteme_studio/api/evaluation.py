"""FastAPI endpoints for knowledge graph evaluation, reports, and benchmarks."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import PlainTextResponse

from episteme_studio.api.deps import get_evaluation_service
from episteme_studio.api.errors import (
    BenchmarkNotFoundException,
    EvaluationReportNotFoundException,
)
from episteme_studio.domain.evaluation import (
    BenchmarkDescriptor,
    ComparativeEvaluationResponse,
    CompareRunsRequest,
    EvaluateManifestRequest,
    EvaluateRunRequest,
    EvaluationReportDetail,
    EvaluationReportSummary,
)
from episteme_studio.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.get("/reports", response_model=list[EvaluationReportSummary])
async def list_evaluation_reports(
    run_id: str | None = Query(None, description="Filter by participating run identifier"),
    outcome: str | None = Query(None, description="Filter by evaluation outcome ('pass', 'fail', 'warning')"),
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[EvaluationReportSummary]:
    """List all available evaluation report summaries.

    Parameters
    ----------
    run_id : str or None, optional
        Filter by participating run ID.
    outcome : str or None, optional
        Filter by outcome status.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    list of EvaluationReportSummary
        Discovered evaluation report summaries.
    """
    return service.list_reports(run_id=run_id, outcome=outcome)


@router.get("/reports/{evaluation_id}", response_model=EvaluationReportDetail)
async def get_evaluation_report(
    evaluation_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportDetail:
    """Retrieve full evaluation report detail by identifier.

    Parameters
    ----------
    evaluation_id : str
        Unique evaluation or run identifier.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationReportDetail
        Full evaluation report detail.

    Raises
    ------
    EvaluationReportNotFoundException
        If the requested evaluation report cannot be found.
    """
    report = service.get_report(evaluation_id)
    if not report:
        raise EvaluationReportNotFoundException(evaluation_id)
    return report


@router.get("/reports/{evaluation_id}/markdown", response_class=PlainTextResponse)
async def get_evaluation_report_markdown(
    evaluation_id: str,
    service: EvaluationService = Depends(get_evaluation_service),
) -> str:
    """Retrieve raw Markdown commentary for an evaluation report.

    Parameters
    ----------
    evaluation_id : str
        Evaluation identifier.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    str
        Markdown report content.

    Raises
    ------
    EvaluationReportNotFoundException
        If the requested evaluation report cannot be found.
    """
    report = service.get_report(evaluation_id)
    if not report:
        raise EvaluationReportNotFoundException(evaluation_id)
    return report.summary_markdown


@router.post("/run", response_model=EvaluationReportDetail, status_code=status.HTTP_201_CREATED)
async def evaluate_run(
    request: EvaluateRunRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportDetail:
    """Evaluate a completed pipeline run against a gold standard benchmark.

    Evaluates the extracted graph or theory atoms of `run_id` in-memory
    against the target gold benchmark, computing structuralist model decomposition,
    poset integrity, polarity concordance, retrieval effectiveness, and comparative baselines.

    Parameters
    ----------
    request : EvaluateRunRequest
        Evaluation request options.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationReportDetail
        Synthesized evaluation report.
    """
    return await service.evaluate_run(request)


@router.post("/manifest", response_model=EvaluationReportDetail, status_code=status.HTTP_200_OK)
async def evaluate_manifest(
    request: EvaluateManifestRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationReportDetail:
    """Trigger a batch evaluation configured by an immutable YAML manifest.

    Parameters
    ----------
    request : EvaluateManifestRequest
        Manifest path and execution options.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    EvaluationReportDetail
        Synthesized evaluation report.
    """
    return await service.evaluate_manifest(request)


@router.post("/compare", response_model=ComparativeEvaluationResponse)
async def compare_runs(
    request: CompareRunsRequest,
    service: EvaluationService = Depends(get_evaluation_service),
) -> ComparativeEvaluationResponse:
    """Compare two evaluated pipeline runs side-by-side.

    Parameters
    ----------
    request : CompareRunsRequest
        Comparison request specifying run identifiers.
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    ComparativeEvaluationResponse
        Pairwise metric deltas and summary comparison markdown.
    """
    return service.compare_runs(request)


@router.get("/benchmarks", response_model=list[BenchmarkDescriptor])
async def list_benchmarks(
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[BenchmarkDescriptor]:
    """List available gold-standard evaluation benchmarks.

    Parameters
    ----------
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    list of BenchmarkDescriptor
        Registered and discovered benchmark descriptors.
    """
    return service.list_benchmarks()


@router.get("/manifests", response_model=list[dict[str, Any]])
async def list_manifests(
    service: EvaluationService = Depends(get_evaluation_service),
) -> list[dict[str, Any]]:
    """List available evaluation run manifests.

    Parameters
    ----------
    service : EvaluationService
        Injected evaluation service.

    Returns
    -------
    list of dict of str to Any
        Discovered manifest descriptors.
    """
    return service.list_manifests()
