"""RFC 7807 Problem Detail exception classes and response factories."""

from __future__ import annotations

from typing import Any
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

from episteme_studio.domain.errors import ProblemDetail


class StudioProblemException(HTTPException):
    """Exception carrying an RFC 7807 ProblemDetail payload.

    Parameters
    ----------
    type : str
        Machine-readable slug identifying the error condition.
    title : str
        Short summary of the problem type.
    status : int
        HTTP status code.
    detail : str or None, optional
        Human-readable explanation.
    instance : str or None, optional
        URI reference for the specific occurrence.
    extra : dict of str to Any, optional
        Supplemental error context.
    """

    def __init__(
        self,
        type: str,
        title: str,
        status: int,
        detail: str | None = None,
        instance: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.problem = ProblemDetail(
            type=type,
            title=title,
            status=status,
            detail=detail,
            instance=instance,
            extra=extra or {},
        )
        super().__init__(status_code=status, detail=detail)


class Neo4jUnavailableException(StudioProblemException):
    """Raised when Neo4j is not configured or cannot establish a connection."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            type="neo4j-unavailable",
            title="Neo4j Unavailable",
            status=503,
            detail=detail or "Neo4j graph store driver is unavailable or disconnected.",
        )


class Neo4jReadOnlyViolationException(StudioProblemException):
    """Raised when a write query is attempted in read-only Cypher mode."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            type="neo4j-read-only-violation",
            title="Neo4j Read-Only Violation",
            status=403,
            detail=detail or "Cypher console operates in read-only access mode.",
        )


class QueryTimeoutException(StudioProblemException):
    """Raised when a graph or Cypher query exceeds its time budget."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            type="query-timeout",
            title="Query Timeout",
            status=504,
            detail=detail or "Query execution exceeded the configured time limit.",
        )


class ResultTooLargeException(StudioProblemException):
    """Raised when query results exceed the row or node budget cap."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            type="result-too-large",
            title="Result Too Large",
            status=413,
            detail=detail or "Query result exceeded the maximum allowed row or element cap.",
        )


class OverlayNotImplementedException(StudioProblemException):
    """Raised when a requested overlay kind is reserved or not implemented."""

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(
            type="overlay-not-implemented",
            title="Overlay Not Implemented",
            status=501,
            detail=detail or "The requested overlay kind is reserved and not yet implemented.",
        )


class InvalidConfigPatchException(StudioProblemException):
    """Raised when a configuration patch fails validation or contains invalid keys."""

    def __init__(self, detail: str | None = None, extra: dict[str, Any] | None = None) -> None:
        super().__init__(
            type="invalid-config-patch",
            title="Invalid Configuration Patch",
            status=422,
            detail=detail or "The provided configuration patch failed validation.",
            extra=extra,
        )


class EvaluationReportNotFoundException(StudioProblemException):
    """Raised when an evaluation report cannot be found."""

    def __init__(self, evaluation_id: str) -> None:
        super().__init__(
            type="evaluation-report-not-found",
            title="Evaluation Report Not Found",
            status=404,
            detail=f"Evaluation report '{evaluation_id}' was not found.",
        )


class BenchmarkNotFoundException(StudioProblemException):
    """Raised when a requested evaluation benchmark cannot be resolved."""

    def __init__(self, benchmark_id: str) -> None:
        super().__init__(
            type="benchmark-not-found",
            title="Benchmark Not Found",
            status=404,
            detail=f"Evaluation benchmark '{benchmark_id}' was not found on the filesystem.",
        )



def problem_json_response(problem: ProblemDetail) -> JSONResponse:
    """Serialize a ProblemDetail instance into an application/problem+json response.

    Parameters
    ----------
    problem : ProblemDetail
        The error detail instance.

    Returns
    -------
    JSONResponse
        FastAPI JSON response with media type 'application/problem+json'.
    """
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
    )


async def problem_exception_handler(request: Request, exc: StudioProblemException) -> Response:
    """FastAPI exception handler for StudioProblemException.

    Parameters
    ----------
    request : Request
        Incoming HTTP request.
    exc : StudioProblemException
        Caught problem exception.

    Returns
    -------
    Response
        Serialized problem response.
    """
    return problem_json_response(exc.problem)
