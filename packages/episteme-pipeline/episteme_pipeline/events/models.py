"""
Pydantic event schemas for the pipeline event system.

These events represent domain-level occurrences in the pipeline that are
scientifically relevant for analysis and reproducibility.

All events inherit from BaseEvent and include timestamp, run_id, and phase for
correlation and filtering.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Any
from pydantic import BaseModel, Field


class UnlinkableMentionError(Exception):
    """Raised when a mention cannot be linked to the graph (e.g., missing envelope)."""
    pass

# Event base class
class BaseEvent(BaseModel):
    """Base class for all pipeline events.
    
    Attributes
    ----------
    timestamp : datetime
        Time when the event was created. Uses UTC timezone.
    run_id : str, optional
        Identifier for the pipeline run this event belongs to.
    phase : str, optional
        Name of the pipeline phase when this event occurred.
    """
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: Optional[str] = None
    phase: Optional[str] = None


# Entity-related events
class EntityProcessed(BaseEvent):
    """An entity was processed.

    Attributes
    ----------
    entity_id : str
        Identifier of the processed entity.
    entity_name : str
        Display name of the entity.
    entity_type : str
        Type/label of the entity (schema class).
    """
    entity_id: str
    entity_name: str
    entity_type: str


# Dense retrieval events
class DenseCandidatesGenerated(BaseEvent):
    """Dense candidate pairs were generated.
    
    This event is emitted when the dense retrieval phase generates candidate
    entity pairs for further processing.
    
    Attributes
    ----------
    candidate_count : int
        Number of candidate pairs generated.
    candidates : list of dict
        List of candidate pairs with their scores and metadata.
    entities_count : int
        Number of entities used to generate candidates.
    """
    candidate_count: int
    candidates: List[dict]  # Simplified representation
    entities_count: int


class RerankerScoreAssigned(BaseEvent):
    """A reranker assigned a score to a candidate pair.
    
    This event is emitted when a reranker processes a candidate pair and assigns
    a score, which determines whether the candidate proceeds to the next stage.
    
    Attributes
    ----------
    candidate_pair : tuple of (str, str)
        Pair of entity IDs that were scored.
    score : float
        Score assigned by the reranker.
    accepted : bool
        Whether the candidate was accepted based on the threshold.
    threshold : float
        Threshold used to determine acceptance.
    entity_a : dict, optional
        Compact metadata for the query-side entity.
    entity_b : dict, optional
        Compact metadata for the document-side entity.
    reranker_input : dict, optional
        Size metadata for the final reranker query/document pair.
    reranker_payload : dict, optional
        Serialized reranker query/document texts for observability backends.
    recovery_attempts : list of dict, optional
        Recovery metadata when the reranker required retries before scoring.
    """
    candidate_pair: tuple[str, str]  # entity IDs
    score: float
    accepted: bool
    threshold: float
    entity_a: Optional[dict[str, Any]] = None
    entity_b: Optional[dict[str, Any]] = None
    reranker_input: Optional[dict[str, Any]] = None
    reranker_payload: Optional[dict[str, str]] = None
    recovery_attempts: Optional[List[dict[str, Any]]] = None


class CandidateRejectedByThreshold(BaseEvent):
    """A candidate was rejected due to not meeting threshold.
    
    This event is emitted when a candidate pair is rejected because its score
    falls below the required threshold.
    
    Attributes
    ----------
    candidate_pair : tuple of (str, str)
        Pair of entity IDs that were rejected.
    score : float
        Score that was below the threshold.
    threshold : float
        Threshold that was not met.
    reason : str
        Reason for rejection (default: "Below threshold").
    """
    candidate_pair: tuple[str, str]  # entity IDs
    score: float
    threshold: float
    reason: str = "Below threshold"


# Entity Linking events
class EntityLinkingCandidatesRetrieved(BaseEvent):
    """Dense candidates retrieved for entity linking.
    
    Attributes
    ----------
    mention_id : str
        ID of the mention being linked.
    mention_name : str
        Name of the mention.
    candidate_count : int
        Number of candidates retrieved.
    candidates : list of dict
        Retrieved candidates with their scores.
    """
    mention_id: str
    mention_name: str
    candidate_count: int
    candidates: List[dict]


class EntityLinkingReranked(BaseEvent):
    """A cross-encoder score assigned to a linking candidate.
    
    Attributes
    ----------
    mention_id : str
        ID of the mention.
    mention_name : str
        Name of the mention.
    candidate_id : str
        ID of the canonical candidate.
    candidate_name : str
        Name of the candidate.
    score : float
        Cross-encoder similarity score.
    accepted : bool
        Whether the candidate was accepted above threshold.
    threshold : float
        Threshold used.
    """
    mention_id: str
    mention_name: str
    candidate_id: str
    candidate_name: str
    score: float
    accepted: bool
    threshold: float


# Maturation events
class EntityMaturationSynthesized(BaseEvent):
    """An entity description was synthesized from its envelopes.
    
    Attributes
    ----------
    entity_id : str
        ID of the mature entity.
    entity_name : str
        Name of the entity.
    envelope_count : int
        Number of textual envelopes used for centroid calculation.
    top_k_used : int
        Number of Top-K envelopes fed into the LLM.
    synthesized_description : str
        The final synthesized description.
    """
    entity_id: str
    entity_name: str
    envelope_count: int
    top_k_used: int
    synthesized_description: str


class EnvelopeInjectionAttempted(BaseEvent):
    """An attempt was made to inject a textual envelope for a mention.
    
    Attributes
    ----------
    mention_name : str
        Name of the mention.
    chunk_id : str
        ID of the chunk where the mention was found.
    """
    mention_name: str
    chunk_id: str

class EnvelopeInjectionFailed(BaseEvent):
    """Failed to inject a textual envelope for a mention after all fallbacks.
    
    Attributes
    ----------
    mention_name : str
        Name of the mention.
    mention_quote : str
        The quote the LLM claimed for the mention.
    chunk_id : str
        ID of the chunk where the mention was found.
    reason : str
        Reason for failure.
    """
    mention_name: str
    mention_quote: str
    chunk_id: str
    reason: str

# LLM processing events
class LLMRelationDecoded(BaseEvent):
    """An LLM decoded a relation from a candidate pair.
    
    This event is emitted when an LLM extracts a semantic relation between
    a candidate pair of entities.
    
    Attributes
    ----------
    candidate_pair : tuple of (str, str)
        Pair of entity IDs between which the relation was decoded.
    relation : str or None
        The relation extracted by the LLM, or None if no relation found.
    direction : str or None
        Direction of the relation (e.g., "forward", "reverse", "bidirectional").
    confidence : float or None
        Confidence score for the extracted relation.
    raw_response : Any, optional
        Raw response from the LLM (may contain sensitive data).
    """
    candidate_pair: tuple[str, str]  # entity IDs
    relation: Optional[str]
    direction: Optional[str]
    confidence: Optional[float]
    raw_response: Optional[Any] = None


class SchemaValidationRejectedRelation(BaseEvent):
    """Schema validation rejected a decoded relation.
    
    This event is emitted when a decoded relation fails schema validation.
    
    Attributes
    ----------
    candidate_pair : tuple of (str, str)
        Pair of entity IDs for which the relation was rejected.
    relation : str
        The relation that was rejected.
    reason : str
        Explanation of why the relation was rejected.
    """
    candidate_pair: tuple[str, str]  # entity IDs
    relation: str
    reason: str


# Triple and artifact events
class TripleCommitted(BaseEvent):
    """A triple was committed to the graph.
    
    This event is emitted when a validated relation is committed as a triple
    to the knowledge graph.
    
    Attributes
    ----------
    subject_id : str
        ID of the subject entity.
    predicate : str
        Predicate representing the relationship.
    object_id : str
        ID of the object entity.
    confidence : float
        Confidence score for the triple.
    scope : str
        Scope or context of the triple.
    source_chunk_id : str
        ID of the source text chunk.
    """
    subject_id: str
    predicate: str
    object_id: str
    confidence: float
    scope: str
    source_chunk_id: str


# Fusion events
class FusionDecisionMade(BaseEvent):
    """A fusion decision was made.

    Attributes
    ----------
    entities_fused : list[str]
        IDs of entities fused together.
    fusion_type : str
        Strategy or mode of fusion used.
    confidence : float
        Confidence score for the fusion decision.
    reason : str, optional
        Optional human-readable rationale.
    """
    entities_fused: List[str]
    fusion_type: str
    confidence: float
    reason: Optional[str] = None


# Performance and metrics events
class PhaseCompleted(BaseEvent):
    """A pipeline phase completed.
    
    This event is emitted when a pipeline phase finishes execution.
    
    Attributes
    ----------
    phase_name : str
        Name of the completed phase.
    duration_seconds : float
        Duration of the phase execution in seconds.
    artifact_count : int
        Number of artifacts produced by the phase.
    success : bool
        Whether the phase completed successfully.
    error_message : str, optional
        Error message if the phase failed.
    """
    phase_name: str
    duration_seconds: float
    artifact_count: int
    success: bool
    error_message: Optional[str] = None


class ComponentStarted(BaseEvent):
    """A component started processing.
    
    This event is emitted when a pipeline component begins processing.
    
    Attributes
    ----------
    component_name : str
        Name of the component that started.
    input_description : str, optional
        Description of the input data.
    """
    component_name: str
    input_description: Optional[str] = None


class ComponentCompleted(BaseEvent):
    """A component completed processing.
    
    This event is emitted when a pipeline component finishes processing.
    
    Attributes
    ----------
    component_name : str
        Name of the component that completed.
    duration_seconds : float
        Duration of component execution in seconds.
    output_description : str, optional
        Description of the output data.
    success : bool
        Whether the component completed successfully.
    error_message : str, optional
        Error message if the component failed.
    """
    component_name: str
    duration_seconds: float
    output_description: Optional[str] = None
    success: bool
    error_message: Optional[str] = None


class LLMDurationMeasured(BaseEvent):
    """Duration of an LLM call was measured.

    Attributes
    ----------
    model_name : str
        Name of the model used.
    prompt_tokens : int
        Number of input tokens.
    completion_tokens : int
        Number of output tokens.
    duration_seconds : float
        Latency in seconds for the operation.
    operation : str
        Operation kind (e.g., "chat", "embedding").
    """
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    duration_seconds: float
    operation: str


class LLMGenerationCompleted(BaseEvent):
    """Complete record of an LLM generation call.

    Emitted when an LLM facade completes a text completion or structured prediction.
    Carries prompt, output, and detailed token usage for observability backends
    (e.g., Langfuse generations).

    Attributes
    ----------
    model_name : str
        Name of the model used (e.g., "openai/gpt-4o-mini").
    prompt : Any
        Rendered prompt string, list of messages, or prompt payload.
    output_text : str
        Raw string output from the LLM.
    output_json : Any, optional
        Structured / parsed JSON representation of the output if available.
    prompt_tokens : int
        Number of input/prompt tokens.
    completion_tokens : int
        Number of output/completion tokens.
    total_tokens : int
        Total tokens consumed.
    duration_seconds : float
        Latency in seconds for the operation.
    operation : str
        Operation kind (e.g., "structured_predict", "text_completion", "fallback_complete").
    cached : bool
        Whether this result was served from cache.
    model_parameters : dict, optional
        Hyperparameters used (e.g., temperature, max_tokens).
    """
    model_name: str
    prompt: Any
    output_text: str
    output_json: Optional[Any] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    operation: str = "structured_predict"
    cached: bool = False
    model_parameters: Optional[dict[str, Any]] = None
    prompt_name: Optional[str] = None
    prompt_version: Optional[str | int] = None
    prompt_label: Optional[str] = None


class EmbeddingGenerationCompleted(BaseEvent):
    """Complete record of an embedding model batch generation call.

    Emitted when an embedding model computes dense vector representations for one
    or more text items.

    Attributes
    ----------
    model_name : str
        Name or identifier of the embedding model.
    text_count : int
        Number of texts processed in the batch.
    total_characters : int
        Total character length across all embedded texts.
    prompt_tokens : int
        Estimated or measured input tokens processed.
    total_tokens : int
        Total tokens consumed.
    duration_seconds : float
        Latency in seconds for the embedding operation.
    vector_dim : int, optional
        Dimensionality of the produced embeddings.
    operation : str
        Operation kind (e.g., "embedding", "batch_embedding").
    cached : bool
        Whether the embeddings were served from a local cache.
    """
    model_name: str
    text_count: int
    total_characters: int
    prompt_tokens: int = 0
    total_tokens: int = 0
    duration_seconds: float = 0.0
    vector_dim: Optional[int] = None
    operation: str = "embedding"
    cached: bool = False


class ArtifactProjected(BaseEvent):

    """An artifact was projected to a target system.

    Attributes
    ----------
    artifact_type : str
        Type of artifact (e.g., "triple", "entity").
    duration_seconds : float
        Projection duration in seconds.
    success : bool
        Whether the projection succeeded.
    """
    artifact_type: str
    duration_seconds: float
    success: bool


class ChunksGenerated(BaseEvent):
    """Chunks were generated for a document.

    Attributes
    ----------
    document_id : str
        Identifier of the document.
    document_title : str
        Title of the document.
    chunk_count : int
        Number of chunks generated.
    token_count : int
        Total token count across all chunks.
    """
    document_id: str
    document_title: str
    chunk_count: int
    token_count: int


# Progress tracking events
class ProgressStarted(BaseEvent):
    """A progress-tracked task has started.

    Attributes
    ----------
    task_name : str
        Name of the task being tracked.
    total_items : int or None
        Total number of items to process, if known.
    description : str
        Optional description of the task.
    """
    task_name: str
    total_items: Optional[int] = None
    description: str = ""


class ProgressAdvanced(BaseEvent):
    """A progress-tracked task has advanced.

    Attributes
    ----------
    task_name : str
        Name of the task being tracked.
    advance : int
        Number of items processed in this step (default: 1).
    """
    task_name: str
    advance: int = 1


class ProgressCompleted(BaseEvent):
    """A progress-tracked task has completed.

    Attributes
    ----------
    task_name : str
        Name of the task that completed.
    """
    task_name: str


class EvaluationCompleted(BaseEvent):
    """An evaluation run has completed.

    Attributes
    ----------
    evaluation_id : str
        ID of the evaluation.
    run_id : str
        ID of the pipeline run.
    metrics : dict[str, float]
        Metrics computed during evaluation.
    outcome : str
        Overall outcome of the evaluation.
    """
    evaluation_id: str
    run_id: str
    metrics: dict[str, float]
    outcome: str


class EvaluationScoreLogged(BaseEvent):
    """An evaluation metric or quality score was logged.

    Emitted when a metric is computed (e.g., epistemic consistency, GM-GBS, OEP,
    relation confidence, clustering modularity) to attach to traces/sessions in
    observability backends.

    Attributes
    ----------
    metric_name : str
        Name of the metric (e.g., "oep_score", "relation_confidence", "cluster_modularity").
    score : float
        Numeric value of the metric.
    comment : str, optional
        Optional human-readable explanation or context.
    target_id : str, optional
        Target entity, triple, cluster, or phase identifier.
    """
    metric_name: str
    score: float
    comment: Optional[str] = None
    target_id: Optional[str] = None


class ValidationViolationDetected(BaseEvent):
    """A graph validation violation was detected.

    Attributes
    ----------
    rule_name : str
        Name of the violated rule.
    source_id : str
        ID of the source node.
    target_id : str
        ID of the target node.
    description : str
        Description of the violation.
    """
    rule_name: str
    source_id: str
    target_id: str
    description: str


# Decision engine & System 1 events
class DecisionEvaluationStarted(BaseEvent):
    """Event emitted when a System 1 decision engine evaluation begins.

    Attributes
    ----------
    engine_name : str
        Identifier or class name of the decision engine.
    primitive : str
        Decision primitive kind ("noul", "choice", "score").
    question : str
        Evaluation question or proposition text.
    state_hash : str
        Stable SHA-256 hash of the input state block.
    state_character_count : int
        Character length of the serialized state block.
    """

    engine_name: str
    primitive: str
    question: str
    state_hash: str
    state_character_count: int


class DecisionEvaluationCompleted(BaseEvent):
    """Event emitted when a System 1 decision engine evaluation completes.

    Attributes
    ----------
    engine_name : str
        Identifier or class name of the decision engine.
    primitive : str
        Decision primitive kind ("noul", "choice", "score").
    question : str
        Evaluation question or proposition text.
    prompt_name : str, optional
        Name of the prompt bundle if resolved via prompt management.
    prompt_version : str or int, optional
        Version of the prompt bundle.
    prompt_label : str, optional
        Deployment label of the prompt (e.g., 'production').
    selected_value : Any
        Evaluation output value (selected option, boolean passed, or score level).
    class_probability : float
        Softmax probability P(y=c|x) of the selected option.
    empirical_accuracy : float
        Calibrated empirical accuracy frequency (Laya action.act_probability).
    probabilities : dict of str to float, optional
        Categorical probability distribution.
    prediction_set : list of str, optional
        Conformal prediction set guaranteeing 1 - alpha coverage.
    is_stochastic_audit : bool
        Whether this evaluation was randomly routed for System 2 validation.
    duration_seconds : float
        Inference latency in seconds.
    tokens_saved_estimate : int
        Estimated generative LLM tokens saved by System 1 fast-exit.
    """

    engine_name: str
    primitive: str
    question: str
    prompt_name: Optional[str] = None
    prompt_version: Optional[str | int] = None
    prompt_label: Optional[str] = None
    selected_value: Any = None
    class_probability: float = 0.0
    empirical_accuracy: float = 0.0
    probabilities: Optional[dict[str, float]] = None
    prediction_set: Optional[list[str]] = None
    is_stochastic_audit: bool = False
    duration_seconds: float = 0.0
    tokens_saved_estimate: int = 0


class DecisionGatingTriggered(BaseEvent):
    """Event emitted when dynamic decision gating or fast-exit routing triggers.

    Attributes
    ----------
    gate_name : str
        Name of the gating checkpoint (e.g., 'gleaning_check', 'acc_triage',
        'cartesian_pair_filter', 'fusion_gate').
    action_taken : str
        Action triggered ('fast_exit', 'escalated_to_llm', 'stochastic_audit',
        'loop_terminated').
    empirical_accuracy : float
        Empirical accuracy estimate of the underlying decision.
    threshold : float
        Decision threshold used to gate the action.
    prediction_set_size : int, optional
        Size of the conformal prediction set at gating time.
    """

    gate_name: str
    action_taken: str
    empirical_accuracy: float
    threshold: float
    prediction_set_size: Optional[int] = None


# Type union for event handling
PipelineEvent = (
    EntityProcessed |
    DenseCandidatesGenerated | RerankerScoreAssigned |
    CandidateRejectedByThreshold | LLMRelationDecoded | SchemaValidationRejectedRelation |
    TripleCommitted | FusionDecisionMade | PhaseCompleted | ComponentStarted |
    ComponentCompleted | LLMDurationMeasured | LLMGenerationCompleted | EmbeddingGenerationCompleted | ArtifactProjected | ChunksGenerated |
    EntityLinkingCandidatesRetrieved | EntityLinkingReranked | EntityMaturationSynthesized |
    EnvelopeInjectionAttempted | EnvelopeInjectionFailed |
    ProgressStarted | ProgressAdvanced | ProgressCompleted |
    EvaluationCompleted | EvaluationScoreLogged | ValidationViolationDetected |
    DecisionEvaluationStarted | DecisionEvaluationCompleted | DecisionGatingTriggered
)



def get_event_type_name(event: BaseEvent) -> str:
    """Get the type name of an event for serialization/logging.
    
    Parameters
    ----------
    event : BaseEvent
        The event instance.
        
    Returns
    -------
    str
        Name of the event class.
    """
    return event.__class__.__name__


def serialize_event(event: BaseEvent) -> dict:
    """Serialize an event to a dictionary.
    
    Parameters
    ----------
    event : BaseEvent
        The event instance to serialize.
        
    Returns
    -------
    dict
        Dictionary representation of the event.
    """
    return event.model_dump()
