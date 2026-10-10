"""Domain events for Theoretical Enrichment and Tenability Evaluation.

Hooked into the centralized EventEmitter to support observability, telemetry,
and Langfuse tracing.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from episteme_pipeline.events.models import BaseEvent


class TheoreticalClusterIdentified(BaseEvent):
    """Emitted when an empirical cluster is mapped to one or more Theory-Elements.

    Attributes
    ----------
    cluster_id : str
        Identifier of the empirical cluster.
    observation_count : int
        Number of ObservationUnit nodes in the cluster.
    claimant_theories : list[str]
        List of theory IDs claiming the cluster as an Intended Application.
    """

    cluster_id: str
    observation_count: int
    claimant_theories: list[str] = Field(default_factory=list)


class TheoreticalParametersProjected(BaseEvent):
    """Emitted when a domain-specific projection (Phi_spec) postuates parameters.

    Attributes
    ----------
    cluster_id : str
        Identifier of the target empirical cluster.
    theory_id : str
        Theory-Element performing the projection.
    parameters : dict[str, Any]
        Postulated theoretical parameters.
    """

    cluster_id: str
    theory_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class TenabilityEvaluationCompleted(BaseEvent):
    """Emitted when local and edge tenability evaluation finishes for a theory.

    Attributes
    ----------
    theory_id : str
        Evaluated Theory-Element.
    local_score : float
        Local tenability score (TS_local).
    aggregated_score : float
        Aggregated tenability score.
    is_tenable : bool
        True if aggregated tenability meets or exceeds the tenability threshold.
    tightest_blur : float
        Tightest admissible blur (delta) reconciling observations with laws.
    """

    theory_id: str
    local_score: float
    aggregated_score: float
    is_tenable: bool
    tightest_blur: float


class TenabilityAnomalyDetected(BaseEvent):
    """Emitted when an untenable node or constraint edge is flagged (TS < 0.5).

    Attributes
    ----------
    element_id : str
        Identifier of the failing node or relation.
    theory_id : str
        Associated Theory-Element.
    score : float
        Tenability score (< 0.5).
    reason : str
        Description of why the model or constraint failed.
    """

    element_id: str
    theory_id: str
    score: float
    reason: str
