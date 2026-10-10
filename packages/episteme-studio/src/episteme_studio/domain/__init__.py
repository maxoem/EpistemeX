"""Wire contract domain models for GLP Studio.

These models define the strict contract between backend services and the frontend.
Per decision D-01, modules in this package must never import episteme_pipeline.* or epistemetrics.*.
"""

from .config import ConfigPatch, ConfigView, FieldProvenance, InvalidationPreview
from .errors import ProblemDetail
from .events import StudioEvent
from .graph import GraphView, Layer, StudioEdge, StudioNode
from .overlays import Overlay, OverlayKind
from .runs import (
    ArtifactRef,
    EvidenceChunk,
    EvidenceSpan,
    EvidenceTrail,
    PhaseStatus,
    RunDetail,
    RunStatus,
    RunSummary,
    TextAnchor,
)

__all__ = [
    "ArtifactRef",
    "ConfigPatch",
    "ConfigView",
    "EvidenceChunk",
    "EvidenceSpan",
    "EvidenceTrail",
    "FieldProvenance",
    "GraphView",
    "InvalidationPreview",
    "Layer",
    "Overlay",
    "OverlayKind",
    "PhaseStatus",
    "ProblemDetail",
    "RunDetail",
    "RunStatus",
    "RunSummary",
    "StudioEdge",
    "StudioEvent",
    "StudioNode",
    "TextAnchor",
]
