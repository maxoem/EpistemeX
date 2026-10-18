"""Event system exports for pipeline observability and research auditing.

This package exposes the minimal public surface of the event system used by the
pipeline. It re-exports protocols, models, and common observers.
"""

from .bus import (
    ContextualEventEmitter,
    EventEmitter,
    EventObserver,
    NoOpEventEmitter,
    SimpleEventEmitter,
)
from .context import get_event_emitter, set_event_emitter, use_event_emitter
from .langfuse_observer import LangfuseObserver
from .models import (
    ArtifactProjected,
    BaseEvent,
    CandidateRejectedByThreshold,
    ChunksGenerated,
    ComponentCompleted,
    ComponentStarted,
    DecisionEvaluationCompleted,
    DecisionEvaluationStarted,
    DecisionGatingTriggered,
    DenseCandidatesGenerated,
    EmbeddingGenerationCompleted,
    EntityLinkingCandidatesRetrieved,
    EntityLinkingReranked,
    EntityMaturationSynthesized,
    EntityProcessed,
    EvaluationCompleted,
    EvaluationScoreLogged,
    FusionDecisionMade,
    LLMDurationMeasured,
    LLMGenerationCompleted,
    LLMRelationDecoded,
    ModalStrengthResolved,
    PhaseCompleted,
    PhaseFailed,
    PhaseReused,
    PipelineEvent,
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
    RerankerScoreAssigned,
    RunCompleted,
    RunFailed,
    RunStarted,
    SchemaValidationRejectedRelation,
    TripleCommitted,
)
from .observers import (
    CompositeObserver,
    JsonlRunObserver,
    LoggingObserver,
    MetricsObserver,
)
from .progress_observer import RichProgressObserver

__all__ = [
    "ArtifactProjected",
    "BaseEvent",
    "CandidateRejectedByThreshold",
    "ChunksGenerated",
    "ComponentCompleted",
    "ComponentStarted",
    "CompositeObserver",
    # Protocols / emitters / context
    "ContextualEventEmitter",
    "DecisionEvaluationCompleted",
    "DecisionEvaluationStarted",
    "DecisionGatingTriggered",
    "DenseCandidatesGenerated",
    "EmbeddingGenerationCompleted",
    "EntityLinkingCandidatesRetrieved",
    "EntityLinkingReranked",
    "EntityMaturationSynthesized",
    # Concrete events
    "EntityProcessed",
    "EvaluationCompleted",
    "EvaluationScoreLogged",
    "EventEmitter",
    "EventObserver",
    "FusionDecisionMade",
    "JsonlRunObserver",
    "LLMDurationMeasured",
    "LLMGenerationCompleted",
    "LLMRelationDecoded",
    "LangfuseObserver",
    # Observers
    "LoggingObserver",
    "MetricsObserver",
    "ModalStrengthResolved",
    "NoOpEventEmitter",
    "PhaseCompleted",
    "PhaseFailed",
    "PhaseReused",
    # Event type union and base
    "PipelineEvent",
    "ProgressAdvanced",
    "ProgressCompleted",
    "ProgressStarted",
    "RerankerScoreAssigned",
    "RichProgressObserver",
    "RunCompleted",
    "RunFailed",
    "RunStarted",
    "SchemaValidationRejectedRelation",
    "SimpleEventEmitter",
    "TripleCommitted",
    "get_event_emitter",
    "set_event_emitter",
    "use_event_emitter",
]

