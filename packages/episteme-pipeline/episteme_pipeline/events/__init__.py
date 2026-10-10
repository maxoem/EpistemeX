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
    PipelineEvent,
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
    RerankerScoreAssigned,
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
    # Protocols / emitters / context
    "ContextualEventEmitter",
    "EventEmitter",
    "EventObserver",
    "NoOpEventEmitter",
    "SimpleEventEmitter",

    "get_event_emitter",
    "set_event_emitter",
    "use_event_emitter",
    # Event type union and base
    "PipelineEvent",
    "BaseEvent",
    # Concrete events
    "EntityProcessed",
    "DenseCandidatesGenerated",
    "RerankerScoreAssigned",
    "CandidateRejectedByThreshold",
    "LLMRelationDecoded",
    "SchemaValidationRejectedRelation",
    "TripleCommitted",
    "FusionDecisionMade",
    "PhaseCompleted",
    "ComponentStarted",
    "ComponentCompleted",
    "LLMDurationMeasured",
    "LLMGenerationCompleted",
    "EmbeddingGenerationCompleted",
    "ArtifactProjected",
    "ChunksGenerated",
    "EntityLinkingCandidatesRetrieved",
    "EntityLinkingReranked",
    "EntityMaturationSynthesized",
    "ProgressStarted",
    "ProgressAdvanced",
    "ProgressCompleted",
    "EvaluationCompleted",
    "EvaluationScoreLogged",
    "ModalStrengthResolved",
    # Observers
    "LoggingObserver",
    "JsonlRunObserver",
    "MetricsObserver",
    "CompositeObserver",
    "RichProgressObserver",
    "LangfuseObserver",
]

