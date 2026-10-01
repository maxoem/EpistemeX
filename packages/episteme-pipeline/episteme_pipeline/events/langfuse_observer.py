"""Langfuse observer that translates domain and LLM events to Langfuse observations.

This observer maps pipeline events to Langfuse observations for distributed tracing,
token usage accounting, and score logging.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .bus import EventObserver
from .models import (
    PipelineEvent,
    DenseCandidatesGenerated,
    RerankerScoreAssigned,
    LLMRelationDecoded,
    ComponentStarted,
    ComponentCompleted,
    PhaseCompleted,
    ChunksGenerated,
    EntityLinkingCandidatesRetrieved,
    EntityLinkingReranked,
    EntityMaturationSynthesized,
    FusionDecisionMade,
    LLMDurationMeasured,
    LLMGenerationCompleted,
    EmbeddingGenerationCompleted,
    EvaluationCompleted,
    EvaluationScoreLogged,
    DecisionEvaluationCompleted,
    DecisionGatingTriggered,
)

logger = logging.getLogger(__name__)

try:
    from langfuse import get_client
except ImportError:
    get_client = None

try:
    from langfuse.api.resources.commons.types.observation import Observation
except ImportError:
    Observation = None

LANGFUSE_AVAILABLE = get_client is not None


class LangfuseObserver(EventObserver):
    """Observer that maps events to Langfuse spans, generations, and scores.

    This observer converts pipeline domain events into Langfuse observations
    for distributed tracing, token/cost monitoring, and metric tracking. It handles
    component lifecycle events, LLM generation requests/responses with token usage,
    dense retrieval and reranker spans, and evaluation scores.

    Parameters
    ----------
    client : langfuse.Langfuse, optional
        Langfuse client instance. If not provided, uses the default client.

    Raises
    ------
    RuntimeError
        If Langfuse is not installed.
    """

    def __init__(self, client: Any = None) -> None:
        if not LANGFUSE_AVAILABLE:
            raise RuntimeError("Langfuse is not installed")

        self.client = client or get_client()
        self.active_spans: Dict[str, Any] = {}

    def on_event(self, event: PipelineEvent) -> None:
        """Map domain events to Langfuse observations.

        Parameters
        ----------
        event : PipelineEvent
            The event to convert to a Langfuse observation.
        """
        try:
            trace_id, parent_observation_id, trace_context_arg = self._resolve_trace_context(event)

            if isinstance(event, (ComponentStarted, ComponentCompleted, PhaseCompleted)):
                self._handle_lifecycle_event(event, trace_context_arg)
            elif isinstance(event, (LLMGenerationCompleted, EmbeddingGenerationCompleted)):
                self._handle_generation_event(event, trace_context_arg)
            elif isinstance(event, (DecisionEvaluationCompleted, DecisionGatingTriggered)):
                self._handle_decision_event(event, trace_context_arg)
            elif isinstance(event, (EvaluationCompleted, EvaluationScoreLogged)):
                self._handle_evaluation_event(event, trace_id, trace_context_arg)
            elif isinstance(event, LLMDurationMeasured):
                # Handled via LLMGenerationCompleted with full token and prompt metadata
                pass
            else:
                self._handle_domain_event(event, trace_context_arg)
        except Exception as e:
            logger.warning(f"Failed to log event to Langfuse: {e}")

    def _resolve_trace_context(
        self, event: PipelineEvent
    ) -> tuple[Optional[str], Optional[str], Optional[dict[str, str]]]:
        """Extract or derive active trace context.

        Parameters
        ----------
        event : PipelineEvent
            Event carrying optional run_id metadata.

        Returns
        -------
        tuple of (trace_id, parent_observation_id, trace_context_dict)
            Resolved identifiers and trace context dictionary.
        """
        trace_id = None
        parent_observation_id = None
        if hasattr(self.client, "get_current_trace_id"):
            trace_id = self.client.get_current_trace_id()
        if hasattr(self.client, "get_current_observation_id"):
            parent_observation_id = self.client.get_current_observation_id()

        if not trace_id and event.run_id:
            import hashlib
            trace_id = hashlib.md5(event.run_id.encode("utf-8")).hexdigest()

        trace_context: dict[str, str] = {}
        if trace_id:
            trace_context["trace_id"] = trace_id
        if parent_observation_id:
            trace_context["parent_span_id"] = parent_observation_id

        return trace_id, parent_observation_id, (trace_context if trace_context else None)

    def _handle_lifecycle_event(
        self,
        event: ComponentStarted | ComponentCompleted | PhaseCompleted,
        trace_context: Optional[dict[str, str]],
    ) -> None:
        """Handle component and phase lifecycle events."""
        if isinstance(event, ComponentStarted):
            observation = self.client.start_observation(
                as_type="span",
                name=f"component.{event.component_name}",
                trace_context=trace_context,
                input={"description": event.input_description} if event.input_description else None,
            )
            self.active_spans[event.component_name] = observation

        elif isinstance(event, ComponentCompleted):
            span_key = event.component_name
            if span_key in self.active_spans:
                observation = self.active_spans.pop(span_key)
                observation.update(
                    output={
                        "duration_seconds": event.duration_seconds,
                        "success": event.success,
                        "description": event.output_description,
                    }
                )
                observation.end()

        elif isinstance(event, PhaseCompleted):
            observation = self.client.start_observation(
                as_type="span",
                name=f"phase.{event.phase_name}",
                trace_context=trace_context,
                input={"artifact_count": event.artifact_count},
                output={
                    "duration_seconds": event.duration_seconds,
                    "success": event.success,
                    "error": event.error_message,
                },
            )
            observation.end()

    def _handle_generation_event(
        self,
        event: LLMGenerationCompleted | EmbeddingGenerationCompleted,
        trace_context: Optional[dict[str, str]],
    ) -> None:
        """Handle LLM and embedding generation events."""
        if isinstance(event, LLMGenerationCompleted):
            total_tokens = event.total_tokens or (event.prompt_tokens + event.completion_tokens)
            observation = self.client.start_observation(
                as_type="generation",
                name=f"llm.{event.operation}",
                trace_context=trace_context,
                model=event.model_name,
                model_parameters=event.model_parameters or {},
                input=event.prompt,
                output=event.output_json if event.output_json is not None else event.output_text,
                usage_details={
                    "input": event.prompt_tokens,
                    "output": event.completion_tokens,
                    "total": total_tokens,
                },
                metadata=_drop_none(
                    {
                        "cached": event.cached,
                        "duration_seconds": event.duration_seconds,
                        "operation": event.operation,
                        "prompt_name": getattr(event, "prompt_name", None),
                        "prompt_version": getattr(event, "prompt_version", None),
                        "prompt_label": getattr(event, "prompt_label", None),
                    }
                ),
            )
            observation.end()

        elif isinstance(event, EmbeddingGenerationCompleted):
            observation = self.client.start_observation(
                as_type="generation",
                name=f"embed.{event.operation}",
                trace_context=trace_context,
                model=event.model_name,
                input=f"Embedded {event.text_count} texts ({event.total_characters} characters)",
                output={"text_count": event.text_count, "vector_dim": event.vector_dim},
                usage_details={
                    "input": event.prompt_tokens,
                    "output": 0,
                    "total": event.total_tokens,
                },
                metadata=_drop_none(
                    {
                        "cached": event.cached,
                        "duration_seconds": event.duration_seconds,
                        "vector_dim": event.vector_dim,
                        "total_characters": event.total_characters,
                        "operation": event.operation,
                    }
                ),
            )
            observation.end()

    def _handle_decision_event(
        self,
        event: DecisionEvaluationCompleted | DecisionGatingTriggered,
        trace_context: Optional[dict[str, str]],
    ) -> None:
        """Handle discrete decision engine evaluations and dynamic gating events.

        Parameters
        ----------
        event : DecisionEvaluationCompleted or DecisionGatingTriggered
            The decision event to log.
        trace_context : dict of str to str or None
            Active distributed trace context.
        """
        if isinstance(event, DecisionEvaluationCompleted):
            is_active_learning = (
                (event.prediction_set is not None and len(event.prediction_set) > 1)
                or (0.40 <= event.class_probability <= 0.60)
            )

            observation = self.client.start_observation(
                as_type="generation",
                name=f"decision.{event.primitive}",
                trace_context=trace_context,
                model=event.engine_name,
                input={"question": event.question, "primitive": event.primitive},
                output={
                    "selected_value": event.selected_value,
                    "class_probability": event.class_probability,
                    "empirical_accuracy": event.empirical_accuracy,
                    "probabilities": event.probabilities,
                    "prediction_set": event.prediction_set,
                },
                usage_details={
                    "input": event.tokens_saved_estimate,
                    "output": 0,
                    "total": event.tokens_saved_estimate,
                },
                metadata=_drop_none(
                    {
                        "system_1": True,
                        "primitive": event.primitive,
                        "class_probability": event.class_probability,
                        "empirical_accuracy": event.empirical_accuracy,
                        "prediction_set": event.prediction_set,
                        "tokens_saved_estimate": event.tokens_saved_estimate,
                        "is_stochastic_audit": event.is_stochastic_audit,
                        "duration_seconds": event.duration_seconds,
                        "active_learning_candidate": is_active_learning,
                        "prompt_name": event.prompt_name,
                        "prompt_version": event.prompt_version,
                        "prompt_label": event.prompt_label,
                    }
                ),
            )
            observation.end()


        elif isinstance(event, DecisionGatingTriggered):
            observation = self.client.start_observation(
                as_type="span",
                name=f"decision.gate.{event.gate_name}",
                trace_context=trace_context,
                input={
                    "gate_name": event.gate_name,
                    "threshold": event.threshold,
                },
                output={
                    "action_taken": event.action_taken,
                    "empirical_accuracy": event.empirical_accuracy,
                    "prediction_set_size": event.prediction_set_size,
                },
                metadata={
                    "system_1": True,
                    "action_taken": event.action_taken,
                    "threshold": event.threshold,
                },
            )
            observation.end()

    def _handle_evaluation_event(
        self,
        event: EvaluationCompleted | EvaluationScoreLogged,
        trace_id: Optional[str],
        trace_context: Optional[dict[str, str]],
    ) -> None:
        """Handle evaluation metrics and score publishing."""
        if isinstance(event, EvaluationScoreLogged):
            if hasattr(self.client, "create_score") and trace_id:
                self.client.create_score(
                    trace_id=trace_id,
                    name=event.metric_name,
                    value=float(event.score),
                    comment=event.comment,
                )
            observation = self.client.start_observation(
                as_type="span",
                name=f"eval.score.{event.metric_name}",
                trace_context=trace_context,
                input={"metric_name": event.metric_name, "target_id": event.target_id},
                output={"score": event.score, "comment": event.comment},
            )
            observation.end()

        elif isinstance(event, EvaluationCompleted):
            if hasattr(self.client, "create_score") and trace_id:
                for metric_name, score_val in event.metrics.items():
                    self.client.create_score(
                        trace_id=trace_id,
                        name=metric_name,
                        value=float(score_val),
                        comment=f"Outcome: {event.outcome}",
                    )
            observation = self.client.start_observation(
                as_type="span",
                name=f"evaluation.{event.evaluation_id}",
                trace_context=trace_context,
                input={"evaluation_id": event.evaluation_id},
                output={"metrics": event.metrics, "outcome": event.outcome},
            )
            observation.end()

    def _handle_domain_event(
        self, event: PipelineEvent, trace_context: Optional[dict[str, str]]
    ) -> None:
        """Handle domain-specific pipeline events."""
        if isinstance(event, ChunksGenerated):
            observation = self.client.start_observation(
                as_type="span",
                name="phase1.chunking",
                trace_context=trace_context,
                input={
                    "document_id": event.document_id,
                    "document_title": event.document_title,
                },
                output={
                    "chunk_count": event.chunk_count,
                    "token_count": event.token_count,
                },
            )
            observation.end()

        elif isinstance(event, DenseCandidatesGenerated):
            observation = self.client.start_observation(
                as_type="span",
                name="phase3.dense.candidates",
                trace_context=trace_context,
                input={"entities_count": event.entities_count},
                output={
                    "candidate_count": event.candidate_count,
                    "candidates": event.candidates[:10],
                },
            )
            observation.end()

        elif isinstance(event, RerankerScoreAssigned):
            observation = self.client.start_observation(
                as_type="span",
                name="phase3.dense.rerank",
                trace_context=trace_context,
                input=_drop_none(
                    {
                        "candidate_pair": event.candidate_pair,
                        "entity_a": event.entity_a,
                        "entity_b": event.entity_b,
                        "reranker_input": event.reranker_input,
                        "reranker_payload": event.reranker_payload,
                    }
                ),
                output=_drop_none(
                    {
                        "score": event.score,
                        "accepted": event.accepted,
                        "threshold": event.threshold,
                        "reranker_input": event.reranker_input,
                        "recovery_attempts": event.recovery_attempts,
                    }
                ),
            )
            observation.end()

        elif isinstance(event, LLMRelationDecoded):
            observation = self.client.start_observation(
                as_type="span",
                name="phase3.dense.llm_extract",
                trace_context=trace_context,
                input={"candidate_pair": event.candidate_pair},
                output={
                    "relation": event.relation,
                    "direction": event.direction,
                    "confidence": event.confidence,
                },
            )
            observation.end()

        elif isinstance(event, EntityLinkingCandidatesRetrieved):
            observation = self.client.start_observation(
                as_type="span",
                name="phase2.linking.candidates",
                trace_context=trace_context,
                input={"mention_id": event.mention_id, "mention_name": event.mention_name},
                output={
                    "candidate_count": event.candidate_count,
                    "candidates": event.candidates[:10],
                },
            )
            observation.end()

        elif isinstance(event, EntityLinkingReranked):
            observation = self.client.start_observation(
                as_type="span",
                name="phase2.linking.rerank",
                trace_context=trace_context,
                input={
                    "mention_id": event.mention_id,
                    "mention_name": event.mention_name,
                    "candidate_id": event.candidate_id,
                    "candidate_name": event.candidate_name,
                },
                output={
                    "score": event.score,
                    "accepted": event.accepted,
                    "threshold": event.threshold,
                },
            )
            observation.end()

        elif isinstance(event, EntityMaturationSynthesized):
            observation = self.client.start_observation(
                as_type="span",
                name="phase4.maturation.synthesize",
                trace_context=trace_context,
                input={
                    "entity_id": event.entity_id,
                    "entity_name": event.entity_name,
                    "envelope_count": event.envelope_count,
                    "top_k_used": event.top_k_used,
                },
                output={
                    "synthesized_description": event.synthesized_description,
                },
            )
            observation.end()

        elif isinstance(event, FusionDecisionMade):
            observation = self.client.start_observation(
                as_type="span",
                name="phase5.fusion.decision",
                trace_context=trace_context,
                input={
                    "entities_fused": event.entities_fused,
                    "fusion_type": event.fusion_type,
                },
                output={
                    "confidence": event.confidence,
                    "reason": event.reason,
                },
            )
            observation.end()


def _drop_none(payload: dict[str, object | None]) -> dict[str, object]:
    """Return a copy without ``None`` values.

    Parameters
    ----------
    payload : dict[str, object | None]
        Candidate payload dictionary.

    Returns
    -------
    dict[str, object]
        Dictionary containing only non-``None`` values.
    """
    return {key: value for key, value in payload.items() if value is not None}
