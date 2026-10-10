"""FastAPI router for deterministic run-to-run graph and configuration difference analysis."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from episteme_studio.adapters.artifact_reader import ArtifactReader
from episteme_studio.api.deps import get_settings
from episteme_studio.domain.diff import GraphDiffView
from episteme_studio.services.diff_service import DiffService
from episteme_studio.settings import StudioSettings

router = APIRouter(prefix="/api/diff", tags=["diff"])


def get_diff_service(settings: StudioSettings = Depends(get_settings)) -> DiffService:
    """Dependency provider instantiating DiffService with the configured ArtifactReader.

    Parameters
    ----------
    settings : StudioSettings
        Active application settings.

    Returns
    -------
    DiffService
        Instantiated diff service.
    """
    reader = ArtifactReader(
        runs_dir=settings.runs_dir,
        artifacts_dir=settings.artifacts_dir,
        langfuse_host=settings.langfuse_host,
    )
    return DiffService(reader)


@router.get("/runs", response_model=GraphDiffView)
async def diff_runs(
    base_id: str = Query(..., description="Baseline Run A identifier"),
    target_id: str = Query(..., description="Candidate Run B identifier"),
    weight_shift_threshold: float = Query(0.15, ge=0.0, le=1.0, description="Weight shift sensitivity threshold"),
    service: DiffService = Depends(get_diff_service),
) -> GraphDiffView:
    """Compare baseline Run A against candidate Run B and compute topological and semantic diffs.

    Parameters
    ----------
    base_id : str
        Baseline Run A identifier.
    target_id : str
        Candidate Run B identifier.
    weight_shift_threshold : float, default 0.15
        Threshold above which an edge confidence/weight deviation is classified as shifted.
    service : DiffService
        Injected diff service.

    Returns
    -------
    GraphDiffView
        Complete unified diff payload containing union graph, node/edge diff statuses,
        polarity inversions, configuration delta, and summary KPIs.
    """
    try:
        return service.compute_run_diff(
            base_run_id=base_id,
            target_run_id=target_id,
            weight_shift_threshold=weight_shift_threshold,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Run not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute run difference: {e}") from e
