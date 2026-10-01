"""Unit tests for ObservableDecisionEngine and Langfuse tracing integration.

Covers:
- Latency and state hash calculation on ObservableDecisionEngine.
- Emission of DecisionEvaluationStarted and DecisionEvaluationCompleted events.
- Prompt management telemetry binding (prompt_name, prompt_version, prompt_label).
- Stochastic auditing rate routing (is_stochastic_audit flag).
- DecisionGatingTriggered event emissions.
- LangfuseObserver handling of decision events and Active Learning candidate queue.
- Failure isolation guarantees.
"""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import MagicMock
import pytest

from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.decision.observable import ObservableDecisionEngine
from episteme_pipeline.events import SimpleEventEmitter, use_event_emitter
from episteme_pipeline.events.bus import EventObserver
from episteme_pipeline.events.langfuse_observer import LangfuseObserver
from episteme_pipeline.events.models import (
    DecisionEvaluationCompleted,
    DecisionEvaluationStarted,
    DecisionGatingTriggered,
    PipelineEvent,
)
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.decision import DecisionEngine, ensure_decision_engine


class CapturingObserver(EventObserver):
    """Test observer that records all captured pipeline events in a list."""

    def __init__(self) -> None:
        self.events: list[PipelineEvent] = []

    def on_event(self, event: PipelineEvent) -> None:
        self.events.append(event)


@pytest.mark.asyncio
async def test_observable_decision_engine_events_and_hashes() -> None:
    """Verify ObservableDecisionEngine emits started and completed events with correct state hash."""
    emitter = SimpleEventEmitter()
    observer = CapturingObserver()
    emitter.register_observer(observer)

    mock_inner = MockJevDecisionEngine(default_confidence_threshold=0.85)
    observable = ObservableDecisionEngine(
        inner=mock_inner,
        engine_name="TestJevEngine",
    )
    assert isinstance(observable, DecisionEngine)
    assert observable.name == "TestJevEngine"

    input_state = "Carnap argues for the logical analysis of science."
    expected_hash = hashlib.sha256(input_state.encode("utf-8")).hexdigest()

    with use_event_emitter(emitter):
        # 1. evaluate_noul
        noul_res = await observable.evaluate_noul(input_state, "Is this substantive?")
        assert noul_res.passed is True

        # 2. evaluate_choice
        choice_res = await observable.evaluate_choice(
            input_state, "Classify entity type", ["THEORY", "CONCEPT", "METHOD"]
        )
        assert choice_res.selected_option == "THEORY"

        # 3. evaluate_score
        score_res = await observable.evaluate_score(
            input_state, "Rate formal rigor", [1, 2, 3, 4, 5]
        )
        assert score_res.selected_option == 1

    # Verify event capture count: 3 started + 3 completed = 6 events
    assert len(observer.events) == 6

    # Verify Noul events
    ev_start_noul = observer.events[0]
    assert isinstance(ev_start_noul, DecisionEvaluationStarted)
    assert ev_start_noul.engine_name == "TestJevEngine"
    assert ev_start_noul.primitive == "noul"
    assert ev_start_noul.question == "Is this substantive?"
    assert ev_start_noul.state_hash == expected_hash
    assert ev_start_noul.state_character_count == len(input_state)

    ev_comp_noul = observer.events[1]
    assert isinstance(ev_comp_noul, DecisionEvaluationCompleted)
    assert ev_comp_noul.primitive == "noul"
    assert ev_comp_noul.class_probability == noul_res.probability
    assert ev_comp_noul.empirical_accuracy == noul_res.empirical_accuracy
    assert ev_comp_noul.duration_seconds >= 0.0
    assert ev_comp_noul.tokens_saved_estimate > 0

    # Verify Choice events
    ev_start_choice = observer.events[2]
    assert isinstance(ev_start_choice, DecisionEvaluationStarted)
    assert ev_start_choice.primitive == "choice"

    ev_comp_choice = observer.events[3]
    assert isinstance(ev_comp_choice, DecisionEvaluationCompleted)
    assert ev_comp_choice.primitive == "choice"
    assert ev_comp_choice.selected_value == "THEORY"
    assert ev_comp_choice.prediction_set == choice_res.prediction_set

    # Verify Score events
    ev_start_score = observer.events[4]
    assert isinstance(ev_start_score, DecisionEvaluationStarted)
    assert ev_start_score.primitive == "score"

    ev_comp_score = observer.events[5]
    assert isinstance(ev_comp_score, DecisionEvaluationCompleted)
    assert ev_comp_score.primitive == "score"


@pytest.mark.asyncio
async def test_observable_prompt_management_binding() -> None:
    """Verify prompt metadata (name, version, label) propagates to telemetry events."""
    emitter = SimpleEventEmitter()
    observer = CapturingObserver()
    emitter.register_observer(observer)

    prompt_bundle = StructuredPromptBundle(
        direct_template="Direct prompt",
        name="acc_classification",
        version=3,
        label="production",
    )

    mock_inner = MockJevDecisionEngine()
    observable = ObservableDecisionEngine(
        inner=mock_inner,
        prompt_bundle=prompt_bundle,
    )

    with use_event_emitter(emitter):
        await observable.evaluate_choice("state", "Classify ADU", ["CLAIM", "PREMISE"])

    assert len(observer.events) == 2
    comp_ev = observer.events[1]
    assert isinstance(comp_ev, DecisionEvaluationCompleted)
    assert comp_ev.prompt_name == "acc_classification"
    assert comp_ev.prompt_version == 3
    assert comp_ev.prompt_label == "production"


@pytest.mark.asyncio
async def test_observable_stochastic_auditing() -> None:
    """Verify stochastic audit flag is marked when audit rate triggers."""
    emitter = SimpleEventEmitter()
    observer = CapturingObserver()
    emitter.register_observer(observer)

    mock_inner = MockJevDecisionEngine()

    # Rate 1.0 ensures 100% audit marking
    audited_engine = ObservableDecisionEngine(
        inner=mock_inner,
        stochastic_audit_rate=1.0,
    )

    with use_event_emitter(emitter):
        await audited_engine.evaluate_noul("state", "Is substantive?")

    assert len(observer.events) == 2
    comp_ev = observer.events[1]
    assert isinstance(comp_ev, DecisionEvaluationCompleted)
    assert comp_ev.is_stochastic_audit is True

    # Rate 0.0 ensures 0% audit marking
    observer.events.clear()
    unaudited_engine = ObservableDecisionEngine(
        inner=mock_inner,
        stochastic_audit_rate=0.0,
    )

    with use_event_emitter(emitter):
        await unaudited_engine.evaluate_noul("state", "Is substantive?")

    assert observer.events[1].is_stochastic_audit is False


@pytest.mark.asyncio
async def test_observable_getattr_delegation() -> None:
    """Verify ObservableDecisionEngine delegates custom methods/attributes to inner engine."""
    mock_inner = MockJevDecisionEngine()
    observable = ObservableDecisionEngine(inner=mock_inner)

    # Underlying methods available via passthrough
    observable.register_choice_response(
        question_pattern="test_pattern",
        selected_option="CUSTOM_OPTION",
    )
    assert len(mock_inner._choice_rules) == 1

    res = await observable.evaluate_choice("state", "test_pattern", ["CUSTOM_OPTION", "OTHER"])
    assert res.selected_option == "CUSTOM_OPTION"

    assert len(observable.calls) == 1
    observable.reset()
    assert len(observable.calls) == 0


@pytest.mark.asyncio
async def test_observable_error_isolation() -> None:
    """Verify that event emission exceptions do not abort pipeline execution."""
    broken_emitter = MagicMock()
    broken_emitter.emit.side_effect = RuntimeError("Broken event sink")

    mock_inner = MockJevDecisionEngine()
    observable = ObservableDecisionEngine(inner=mock_inner)

    with use_event_emitter(broken_emitter):
        # Must execute cleanly despite broken emitter
        res = await observable.evaluate_noul("state", "Is valid?")
        assert res.passed is True


def test_langfuse_observer_decision_event_handling() -> None:
    """Verify LangfuseObserver translates DecisionEvaluationCompleted into Langfuse generation observations."""
    mock_client = MagicMock()
    mock_observation = MagicMock()
    mock_client.start_observation.return_value = mock_observation

    observer = LangfuseObserver(client=mock_client)

    # 1. Standard fast-exit decision (singleton set)
    event_fast_exit = DecisionEvaluationCompleted(
        engine_name="LayaDecisionEngine",
        primitive="choice",
        question="Classify relation",
        prompt_name="global_relation",
        prompt_version=2,
        prompt_label="production",
        selected_value="SUPPORTS",
        class_probability=0.92,
        empirical_accuracy=0.94,
        probabilities={"SUPPORTS": 0.92, "ATTACKS": 0.08},
        prediction_set=["SUPPORTS"],
        is_stochastic_audit=False,
        duration_seconds=0.012,
        tokens_saved_estimate=145,
    )

    observer.on_event(event_fast_exit)

    assert mock_client.start_observation.called
    call_kwargs = mock_client.start_observation.call_args[1]
    assert call_kwargs["name"] == "decision.choice"
    assert call_kwargs["model"] == "LayaDecisionEngine"
    assert call_kwargs["metadata"]["system_1"] is True
    assert call_kwargs["metadata"]["active_learning_candidate"] is False
    assert call_kwargs["metadata"]["tokens_saved_estimate"] == 145
    assert mock_observation.end.called


def test_langfuse_observer_active_learning_queue_hook() -> None:
    """Verify LangfuseObserver identifies active learning candidates (|C(X)| > 1 or high entropy)."""
    mock_client = MagicMock()
    mock_observation = MagicMock()
    mock_client.start_observation.return_value = mock_observation

    observer = LangfuseObserver(client=mock_client)

    # Multi-class prediction set (|C(X)| == 2) -> Active Learning candidate
    event_ambiguous = DecisionEvaluationCompleted(
        engine_name="LayaDecisionEngine",
        primitive="choice",
        question="Disambiguate mention",
        selected_value="PHILOSOPHY_OF_MIND",
        class_probability=0.52,
        empirical_accuracy=0.60,
        probabilities={"PHILOSOPHY_OF_MIND": 0.52, "EPISTEMOLOGY": 0.48},
        prediction_set=["PHILOSOPHY_OF_MIND", "EPISTEMOLOGY"],
        duration_seconds=0.015,
        tokens_saved_estimate=120,
    )

    observer.on_event(event_ambiguous)

    call_kwargs = mock_client.start_observation.call_args[1]
    assert call_kwargs["metadata"]["active_learning_candidate"] is True



def test_langfuse_observer_decision_gating_triggered() -> None:
    """Verify LangfuseObserver captures DecisionGatingTriggered events."""
    mock_client = MagicMock()
    mock_span = MagicMock()
    mock_client.start_observation.return_value = mock_span

    observer = LangfuseObserver(client=mock_client)

    gating_event = DecisionGatingTriggered(
        gate_name="acc_triage",
        action_taken="fast_exit",
        empirical_accuracy=0.93,
        threshold=0.85,
        prediction_set_size=1,
    )

    observer.on_event(gating_event)

    assert mock_client.start_observation.called
    call_kwargs = mock_client.start_observation.call_args[1]
    assert call_kwargs["name"] == "decision.gate.acc_triage"
    assert call_kwargs["input"]["threshold"] == 0.85
    assert call_kwargs["output"]["action_taken"] == "fast_exit"
    assert call_kwargs["metadata"]["system_1"] is True
    assert mock_span.end.called
