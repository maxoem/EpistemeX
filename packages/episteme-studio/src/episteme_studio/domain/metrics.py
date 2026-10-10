"""Domain models for extensible graph metrics framework, descriptors, and execution results."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class MetricScope(StrEnum):
    """Scope of execution for a graph metric.

    Attributes
    ----------
    GLOBAL : str
        Metric runs across the whole graph or database.
    SINGLE_NODE : str
        Metric evaluates centered around a specific focus node.
    """

    GLOBAL = "global"
    SINGLE_NODE = "single_node"


class MetricDescriptor(BaseModel):
    """Descriptor declaring metadata and configuration schema for a metric.

    Parameters
    ----------
    id : str
        Unique identifier for the metric.
    label : str
        Human-readable title displayed in the UI.
    description : str
        Summary of theoretical intention and algorithmic behavior.
    scope : MetricScope
        Execution scope (global or single_node).
    available : bool, default True
        Whether the execution engine and dependencies are available.
    unavailable_reason : str or None, optional
        Human-readable explanation if unavailable.
    engine : Literal["cypher", "gds", "igraph", "python"], default "cypher"
        Underlying execution engine.
    param_schema : dict of str to Any
        Valid JSON Schema defining accepted parameters for dynamic form generation.
    """

    id: str
    label: str
    description: str
    scope: MetricScope
    available: bool = True
    unavailable_reason: str | None = None
    engine: Literal["cypher", "gds", "igraph", "python", "epistemetrics"] = "cypher"
    param_schema: dict[str, Any] = Field(default_factory=dict)


class AffectedNodeDetail(BaseModel):
    """Explanation of a node's role and marginal contribution to metric result.

    Parameters
    ----------
    roles : list of str
        Roles fulfilled by this node (e.g., ["support"], ["attack"], or ["support", "attack"]).
    net_contribution : float or None, optional
        Marginal delta on focus node strength or centrality score.
    metadata : dict of str to Any
        Supplemental algorithmic details.
    """

    roles: list[str] = Field(default_factory=list)
    net_contribution: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AffectedEdgeDetail(BaseModel):
    """Explanation of an edge's causal contribution along an epistemic path.

    Parameters
    ----------
    source_node_id : str
        Identifier of the source node.
    target_node_id : str
        Identifier of the target node.
    relationship_id : str or None, optional
        Underlying property graph relationship identifier.
    role : str
        Inference role (e.g., "support", "attack", "undercut").
    weight : float or None, optional
        Edge weight phi.
    polarity : int or None, optional
        Polarity indicator (+1, -1, 0, or null).
    hop_distance : int, default 1
        Topological distance from the focus node.
    contribution : float or None, optional
        Signed marginal delta or impact contribution.
    metadata : dict of str to Any
        Supplemental metadata.
    """

    source_node_id: str
    target_node_id: str
    relationship_id: str | None = None
    role: str
    weight: float | None = None
    polarity: int | None = None
    hop_distance: int = 1
    contribution: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricResult(BaseModel):
    """Complete result payload of a metric calculation execution.

    Parameters
    ----------
    execution_id : str
        Unique identifier of the execution run.
    metric_id : str
        Identifier of the metric calculated.
    scope : MetricScope
        Execution scope.
    focus_node_id : str or None, optional
        Identifier of the focus node if single_node scope.
    result_value : float or str or None, optional
        Primary metric score or outcome.
    graph_revision : str
        Fingerprint or version of the graph when calculated.
    duration_ms : int
        Execution runtime in milliseconds.
    summary : dict of str to Any
        Aggregate KPIs and summary statistics.
    affected_nodes : dict of str to AffectedNodeDetail
        Map of node IDs to their causal roles and contributions.
    affected_edges : list of AffectedEdgeDetail
        Participating edges with causal explanations.
    warnings : list of str
        Non-fatal diagnostic warnings.
    computed_at : datetime
        Timestamp when calculation completed.
    """

    execution_id: str
    metric_id: str
    scope: MetricScope
    focus_node_id: str | None = None
    result_value: float | str | None = None
    graph_revision: str
    duration_ms: int
    summary: dict[str, Any] = Field(default_factory=dict)
    affected_nodes: dict[str, AffectedNodeDetail] = Field(default_factory=dict)
    affected_edges: list[AffectedEdgeDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    computed_at: datetime
