"""Domain models for epistemic and structural graph overlays."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class OverlayKind(StrEnum):
    """Supported and reserved graph overlay kinds."""

    GRADUAL_STRENGTH = "gradual_strength"
    MODAL_STRENGTH = "modal_strength"
    INTERNAL_CORRELATION = "internal_correlation"
    DEGREE = "degree"
    COMPONENT = "component"
    PAGERANK = "pagerank"
    LEIDEN = "leiden"
    TENABILITY = "tenability"
    B_CONSISTENCY = "b_consistency"
    STABLE_EXTENSION = "stable_extension"


class Overlay(BaseModel):
    """Immutable overlay computed over a specific graph version.

    Parameters
    ----------
    id : str
        Unique identifier for the overlay.
    kind : OverlayKind
        Categorical overlay algorithm kind.
    params : dict of str to Any, optional
        Input parameters supplied to the overlay computation.
    node_values : dict of str to float, str, or None, optional
        Map of node ID to computed scalar or category value.
    edge_values : dict of str to float, str, or None, optional
        Map of edge ID to computed scalar or category value.
    scale : Literal["continuous", "categorical", "ordinal"], default "continuous"
        Color/visual mapping scale for client rendering.
    domain : list of float, list of str, or None, optional
        Domain bounds or category values for the scale.
    computed_at : datetime
        Timestamp of overlay computation.
    graph_version : str
        Fingerprint of the graph snapshot the overlay was computed against.
    incomplete_inputs : int, default 0
        Number of nodes or edges skipped due to missing plausibility/weight data.
    """

    id: str
    kind: OverlayKind
    params: dict[str, Any] = Field(default_factory=dict)
    node_values: dict[str, float | str | None] = Field(default_factory=dict)
    edge_values: dict[str, float | str | None] = Field(default_factory=dict)
    scale: Literal["continuous", "categorical", "ordinal"] = "continuous"
    domain: list[float] | list[str] | None = None
    computed_at: datetime
    graph_version: str
    incomplete_inputs: int = 0
