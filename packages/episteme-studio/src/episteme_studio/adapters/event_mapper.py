"""Adapter mapping pipeline events to normalized StudioEvents."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from episteme_pipeline.events.models import BaseEvent, get_event_type_name, serialize_event
from episteme_studio.domain.events import StudioEvent

_EVENT_KIND_MAP: dict[str, str] = {
    "ComponentStarted": "phase.component_started",
    "ComponentCompleted": "phase.component_completed",
    "PhaseCompleted": "phase.completed",
    "ProgressStarted": "progress.started",
    "ProgressAdvanced": "progress.step",
    "ProgressCompleted": "progress.completed",
    "ChunksGenerated": "chunks.generated",
    "EntityProcessed": "entity.processed",
    "EntityLinkingCandidatesRetrieved": "entity.linking_candidates",
    "EntityLinkingReranked": "entity.linking_reranked",
    "EntityMaturationSynthesized": "entity.maturation_synthesized",
    "DenseCandidatesGenerated": "relation.dense_candidates",
    "RerankerScoreAssigned": "relation.reranked",
    "CandidateRejectedByThreshold": "relation.rejected",
    "LLMRelationDecoded": "relation.llm_decoded",
    "TripleCommitted": "relation.triple_committed",
    "SchemaValidationRejectedRelation": "relation.schema_rejected",
    "FusionDecisionMade": "fusion.decision",
    "LLMDurationMeasured": "llm.duration",
    "LLMGenerationCompleted": "llm.generation_completed",
    "EmbeddingGenerationCompleted": "embedding.completed",
    "ArtifactProjected": "artifact.projected",
    "EnvelopeInjectionAttempted": "envelope.injection_attempted",
    "EnvelopeInjectionFailed": "envelope.injection_failed",
    "EvaluationCompleted": "eval.completed",
    "EvaluationScoreLogged": "eval.score",
    "ValidationViolationDetected": "validation.violation",
    "TheoreticalClusterIdentified": "theory.cluster_identified",
    "TheoreticalParametersProjected": "theory.parameters_projected",
    "TenabilityEvaluationCompleted": "theory.tenability_completed",
    "TenabilityAnomalyDetected": "theory.anomaly_detected",
    "DecisionEvaluationStarted": "decision.started",
    "DecisionEvaluationCompleted": "decision.completed",
    "DecisionGatingTriggered": "decision.gating_triggered",
    "ModalStrengthResolved": "modal.resolved",
    "TerminalOutput": "terminal.output",
}

_ERROR_EVENTS = {
    "EnvelopeInjectionFailed",
    "ValidationViolationDetected",
}

_WARNING_EVENTS = {
    "CandidateRejectedByThreshold",
    "SchemaValidationRejectedRelation",
    "TenabilityAnomalyDetected",
}


def _normalize_event_type_name(name: str) -> str:
    """Convert PascalCase event class names to dot/snake style kind.

    Parameters
    ----------
    name : str
        The raw class name.

    Returns
    -------
    str
        Normalized kind string.
    """
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1.\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def serialize_pipeline_event(event: Any) -> dict[str, Any]:
    """Serialize a pipeline event to an in-memory dictionary without IO.

    Parameters
    ----------
    event : Any
        PipelineEvent instance or dict.

    Returns
    -------
    dict of str to Any
        Serialized event data.
    """
    if isinstance(event, dict):
        return event.copy()
    if isinstance(event, BaseEvent):
        data = serialize_event(event)
        data["_raw_type"] = get_event_type_name(event)
        return data
    if hasattr(event, "model_dump"):
        data = event.model_dump()
        data["_raw_type"] = event.__class__.__name__
        return data
    return {
        "_raw_type": getattr(event, "__class__", type(event)).__name__,
        "payload": str(event),
    }


def to_studio_event(
    event_data: dict[str, Any] | Any,
    seq: int,
    dropped_before: int = 0,
) -> StudioEvent:
    """Map raw event data or a pipeline event object to a StudioEvent.

    Parameters
    ----------
    event_data : dict of str to Any or Any
        Raw dictionary or event instance.
    seq : int
        Monotonically increasing sequence number for this run.
    dropped_before : int, default 0
        Number of events dropped prior to this event.

    Returns
    -------
    StudioEvent
        Normalized domain event.
    """
    if not isinstance(event_data, dict):
        event_data = serialize_pipeline_event(event_data)

    raw_type = event_data.get("_raw_type", "")
    if not raw_type:
        raw_type = event_data.get("kind", "UnknownEvent")

    kind = _EVENT_KIND_MAP.get(raw_type)
    if not kind:
        kind = _normalize_event_type_name(raw_type)

    level: Literal["debug", "info", "warning", "error"] = "info"
    if event_data.get("level") in ("debug", "info", "warning", "error"):
        level = event_data["level"]
    elif raw_type in _ERROR_EVENTS or "error" in raw_type.lower():
        level = "error"
    elif raw_type in _WARNING_EVENTS or "warning" in raw_type.lower() or "rejected" in raw_type.lower():
        level = "warning"
    elif "duration" in raw_type.lower() or "debug" in raw_type.lower():
        level = "debug"

    ts_val = event_data.get("timestamp")
    if isinstance(ts_val, datetime):
        ts = ts_val
    elif isinstance(ts_val, str):
        try:
            ts = datetime.fromisoformat(ts_val)
        except Exception:
            ts = datetime.now(timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    run_id = str(event_data.get("run_id") or "unknown_run")
    phase = event_data.get("phase")

    message = event_data.get("message")
    if not message:
        if raw_type == "ProgressStarted":
            task = event_data.get("task_name") or "task"
            desc = event_data.get("description") or task
            tot = event_data.get("total_items")
            tot_str = f" ({tot} items)" if tot else ""
            message = f"Subtask started: {desc}{tot_str}"
        elif raw_type == "ProgressAdvanced":
            task = event_data.get("task_name") or "task"
            adv = event_data.get("advance", 1)
            message = f"Subtask advanced: {task} (+{adv})"
        elif raw_type == "ProgressCompleted":
            task = event_data.get("task_name") or "task"
            message = f"Subtask completed: {task}"
        elif raw_type == "DecisionEvaluationCompleted":
            prim = event_data.get("primitive", "decision")
            sel = event_data.get("selected_value")
            acc = float(event_data.get("empirical_accuracy", 0.0) or 0.0)
            dur = float(event_data.get("duration_seconds", 0.0) or 0.0)
            message = f"Decision {prim}: {sel} (acc={acc:.1%}, {dur*1000:.1f}ms)"
        elif raw_type == "DecisionGatingTriggered":
            gate = event_data.get("gate_name", "gate")
            act = event_data.get("action_taken", "action")
            message = f"Gating [{gate}]: {act}"
        elif raw_type == "ModalStrengthResolved":
            atom_id = event_data.get("atom_id", "atom")
            m_val = float(event_data.get("modal_strength", 0.0) or 0.0)
            res_type = event_data.get("resolver_type", "resolver")
            scope = event_data.get("scope_type") or "none"
            clamped_str = " (clamped)" if event_data.get("clamped") else ""
            message = f"Modality resolved [{atom_id}]: M(φ)={m_val:.3f} via {res_type} [scope={scope}]{clamped_str}"
        elif "description" in event_data and event_data["description"]:
            message = str(event_data["description"])
        elif "phase_name" in event_data:
            message = f"Phase '{event_data['phase_name']}' event: {raw_type}"
        elif "entity_name" in event_data:
            message = f"Entity '{event_data['entity_name']}' processed"
        else:
            message = f"Event {raw_type}"

    # Extract extra payload excluding base envelope fields
    payload = {
        k: v
        for k, v in event_data.items()
        if k not in {"timestamp", "run_id", "phase", "_raw_type", "_dropped_before", "message"}
    }

    effective_dropped = event_data.get("_dropped_before", dropped_before)

    return StudioEvent(
        seq=seq,
        run_id=run_id,
        ts=ts,
        kind=kind,
        level=level,
        phase=phase,
        message=message,
        payload=payload,
        dropped_before=effective_dropped,
    )
