"""Decision engine module for System 1 non-generative, typed inference.

This package provides concrete implementations of the
:class:`~episteme_pipeline.protocols.decision.DecisionEngine` protocol,
including :class:`LayaDecisionEngine` for local Apple Silicon MLX inference,
:class:`TransformersDecisionEngine` for cross-platform PyTorch execution,
:class:`MockJevDecisionEngine` for deterministic in-memory testing, and
:class:`ObservableDecisionEngine` for telemetry tracking and domain event
publishing.
"""

from episteme_pipeline.decision.cascade import (
    TriageDecision,
    should_audit_deterministically,
)
from episteme_pipeline.decision.conformal import ConformalCalibrator
from episteme_pipeline.decision.gleaning import JevGleaningGate
from episteme_pipeline.decision.jev_client import (
    AutoDecisionEngine,
    DecisionEngineError,
    LayaDecisionEngine,
    TransformersDecisionEngine,
    resolve_decision_engine,
)
from episteme_pipeline.decision.mock import (
    MockJevDecisionEngine,
    compute_conformal_prediction_set,
)
from episteme_pipeline.decision.modal_resolver import (
    DecisionEngineModalResolver,
    HybridModalResolver,
    ModalSyntaxProfile,
    StructuralistModalResolver,
)
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.decision.strategies import (
    ChoiceQuestionStrategy,
    NoulQuestionStrategy,
    QuestionExecutionStrategy,
    ScoreQuestionStrategy,
    evaluate_questions_sequentially,
    get_question_strategy,
    register_question_strategy,
)

__all__ = [
    "AutoDecisionEngine",
    "ChoiceQuestionStrategy",
    "ConformalCalibrator",
    "DecisionEngineError",
    "DecisionEngineModalResolver",
    "HybridModalResolver",
    "JevGleaningGate",
    "LayaDecisionEngine",
    "MockJevDecisionEngine",
    "ModalSyntaxProfile",
    "NoulQuestionStrategy",
    "ObservableDecisionEngine",
    "QuestionExecutionStrategy",
    "ScoreQuestionStrategy",
    "StructuralistModalResolver",
    "TransformersDecisionEngine",
    "TriageDecision",
    "compute_conformal_prediction_set",
    "evaluate_questions_sequentially",
    "get_question_strategy",
    "register_question_strategy",
    "resolve_decision_engine",
    "should_audit_deterministically",
]

