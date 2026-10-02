"""Decision engine module for System 1 non-generative, typed inference.

This package provides concrete implementations of the
:class:`~episteme_pipeline.protocols.decision.DecisionEngine` protocol,
including :class:`LayaDecisionEngine` for local Apple Silicon MLX inference,
:class:`TransformersDecisionEngine` for cross-platform PyTorch execution,
:class:`MockJevDecisionEngine` for deterministic in-memory testing, and
:class:`ObservableDecisionEngine` for telemetry tracking and domain event
publishing.
"""

from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.decision.gleaning import JevGleaningGate
from episteme_pipeline.decision.jev_client import (
    DecisionEngineError,
    LayaDecisionEngine,
    TransformersDecisionEngine,
)
from episteme_pipeline.decision.mock import (
    MockJevDecisionEngine,
    compute_conformal_prediction_set,
)
from episteme_pipeline.decision.observable import ObservableDecisionEngine

__all__ = [
    "ConformalCalibrator",
    "DecisionEngineError",
    "JevGleaningGate",
    "LayaDecisionEngine",
    "TransformersDecisionEngine",
    "MockJevDecisionEngine",
    "compute_conformal_prediction_set",
    "ObservableDecisionEngine",
]
