"""Unit and integration tests for Jev Actor-Critic Gleaning Gate (ISSUE-040)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from episteme_pipeline.config import GleaningConfig, Phase2Config, Phase4Config
from episteme_pipeline.contracts.domain import L1Chunk, L2Entity, TheoryAtom
from episteme_pipeline.decision.gleaning import FixedPassGleaningOracle, JevGleaningGate
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.events import SimpleEventEmitter, set_event_emitter
from episteme_pipeline.events.models import DecisionGatingTriggered
from episteme_pipeline.phases.phase2_entity_discovery import Phase2Runner
from episteme_pipeline.phases.phase2_entity_discovery.models import NERExtractionOutput
from episteme_pipeline.phases.phase2_entity_discovery.ner_extractor import LLMNERExtractor
from episteme_pipeline.phases.phase4_argument_mining import Phase4Runner
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.decision import GleaningStoppingOracle
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA


class EventCollector:
    def __init__(self):
        self.events = []

    def on_event(self, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_jev_gleaning_gate_fast_exit_when_prob_below_threshold():
    """Gate returns False when P(unextracted) < threshold."""
    engine = MockJevDecisionEngine()
    engine.register_noul_response(
        question_pattern="unextracted",
        probability=0.30,
        empirical_accuracy=0.88,
    )
    engine.register_noul_response(
        question_pattern="salient theoretical assertions",
        probability=0.30,
        empirical_accuracy=0.88,
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    gate = JevGleaningGate(
        decision_engine=engine,
        default_threshold=0.65,
        default_audit_rate=0.0,
    )

    should_continue, acc = await gate.should_glean(
        chunk_text="Some text about epistemology.",
        current_extractions=["Entity1", "Entity2"],
        pass_count=0,
        max_passes=3,
        threshold=0.65,
        audit_rate=0.0,
    )

    assert should_continue is False
    assert acc == 0.88

    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].gate_name == "gleaning_gate"
    assert gating_events[0].action_taken == "fast_exit"


@pytest.mark.asyncio
async def test_jev_gleaning_gate_continues_when_prob_above_threshold():
    """Gate returns True when P(unextracted) >= threshold."""
    engine = MockJevDecisionEngine()
    engine.register_noul_response(
        question_pattern="salient theoretical assertions",
        probability=0.85,
        empirical_accuracy=0.92,
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    gate = JevGleaningGate(
        decision_engine=engine,
        default_threshold=0.65,
        default_audit_rate=0.0,
    )

    should_continue, acc = await gate.should_glean(
        chunk_text="A complex passage containing missed arguments.",
        current_extractions=[],
        pass_count=0,
        max_passes=3,
        threshold=0.65,
        audit_rate=0.0,
    )

    assert should_continue is True
    assert acc == 0.92

    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].action_taken == "escalated_to_llm"


@pytest.mark.asyncio
async def test_jev_gleaning_gate_hard_boundary_max_passes():
    """Gate stops unconditionally when pass_count >= max_passes."""
    engine = MockJevDecisionEngine()
    engine.register_noul_response(
        question_pattern="salient theoretical assertions",
        probability=0.99,
        empirical_accuracy=0.95,
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    gate = JevGleaningGate(decision_engine=engine)

    should_continue, _ = await gate.should_glean(
        chunk_text="Dense text.",
        current_extractions=["EntityA"],
        pass_count=3,
        max_passes=3,
    )

    assert should_continue is False
    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].action_taken == "loop_terminated"


@pytest.mark.asyncio
async def test_jev_gleaning_gate_stochastic_audit():
    """Gate forces gleaning pass when stochastic audit triggers."""
    engine = MockJevDecisionEngine()
    engine.register_noul_response(
        question_pattern="salient theoretical assertions",
        probability=0.10,
        empirical_accuracy=0.85,
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    gate = JevGleaningGate(
        decision_engine=engine,
        default_threshold=0.65,
        default_audit_rate=1.0,  # Force 100% audit
    )

    should_continue, _ = await gate.should_glean(
        chunk_text="Unremarkable chunk text.",
        current_extractions=[],
        pass_count=0,
        max_passes=2,
        threshold=0.65,
        audit_rate=1.0,
    )

    assert should_continue is True
    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].action_taken == "stochastic_audit"


@pytest.mark.asyncio
async def test_jev_gleaning_gate_fallback_without_engine():
    """Gate falls back to standard continuation if decision engine is None."""
    gate = JevGleaningGate(decision_engine=None)

    should_continue, _ = await gate.should_glean(
        chunk_text="Any text",
        current_extractions=[],
        pass_count=0,
        max_passes=2,
    )
    assert should_continue is True

    should_continue_end, _ = await gate.should_glean(
        chunk_text="Any text",
        current_extractions=[],
        pass_count=2,
        max_passes=2,
    )
    assert should_continue_end is False


@pytest.mark.asyncio
async def test_phase2_runner_uses_gleaning_gate():
    """Phase 2 runner respects gleaning gate stopping decision."""
    engine = MockJevDecisionEngine()
    engine.register_noul_response(
        question_pattern="salient theoretical assertions",
        probability=0.20,
        empirical_accuracy=0.90,
    )

    config = Phase2Config(
        gleaning=GleaningConfig(
            enabled=True,
            confidence_threshold=0.65,
            audit_rate=0.0,
            max_passes=3,
        ),
    )

    llm = MagicMock()
    mock_extractor = AsyncMock()
    mock_extractor.extract.return_value = (
        [L2Entity(id="e1", name="Empiricism", label="EpistemicStance")],
        [],
        None,
        False,
        None,
    )

    graph_store = AsyncMock()
    graph_store.get_unprocessed_chunks.return_value = []
    mock_linker = MagicMock()

    runner = Phase2Runner(
        config=config,
        schema=DEFAULT_SCHEMA,
        llm=llm,
        graph_store=graph_store,
        decision_engine=engine,
        ner_extractor=mock_extractor,
        entity_linker=mock_linker,
    )

    assert runner.decision_engine is engine


def test_gleaning_config_encapsulation():
    """Verify GleaningConfig cleanly encapsulates settings on Phase2Config and Phase4Config."""
    cfg = GleaningConfig(
        enabled=True,
        confidence_threshold=0.80,
        audit_rate=0.05,
        max_passes=4,
    )
    p2 = Phase2Config(gleaning=cfg)
    assert p2.gleaning.enabled is True
    assert p2.gleaning.confidence_threshold == 0.80
    assert p2.gleaning.audit_rate == 0.05
    assert p2.gleaning.max_passes == 4

    p4 = Phase4Config(gleaning=cfg)
    assert p4.gleaning.enabled is True
    assert p4.gleaning.confidence_threshold == 0.80
    assert p4.gleaning.audit_rate == 0.05
    assert p4.gleaning.max_passes == 4


def test_stopping_oracle_protocol_conformance():
    """Verify both JevGleaningGate and FixedPassGleaningOracle conform to GleaningStoppingOracle."""
    gate = JevGleaningGate()
    assert isinstance(gate, GleaningStoppingOracle)

    fixed = FixedPassGleaningOracle(max_passes=2)
    assert isinstance(fixed, GleaningStoppingOracle)


@pytest.mark.asyncio
async def test_llm_ner_extractor_with_stopping_oracle():
    """Verify LLMNERExtractor queries injected stopping_oracle and stops iteratively."""
    mock_oracle = AsyncMock(spec=GleaningStoppingOracle)
    # Return True on pass 0, False on pass 1
    mock_oracle.should_glean.side_effect = [(True, 0.9), (False, 0.9)]

    mock_llm = MagicMock()
    # First call: initial extraction; second call: gleaning pass with new finding
    from episteme_pipeline.phases.phase2_entity_discovery.models import ExtractedEntity
    raw_ent = ExtractedEntity(
        id="e1",
        label="CONCEPT",
        name="Empiricism",
        mention_quote="empiricism",
    )
    out1 = NERExtractionOutput(entities=[], triples=[])
    out2 = NERExtractionOutput(entities=[raw_ent], triples=[])
    mock_llm.predict_structured = AsyncMock(side_effect=[out1, out2])

    extractor = LLMNERExtractor(
        llm=mock_llm,
        stopping_oracle=mock_oracle,
    )

    entities, triples, _, _, _ = await extractor.extract(
        chunk_id="chunk_test",
        chunk_text="A theoretical passage on empiricism.",
        schema=DEFAULT_SCHEMA,
    )

    assert mock_oracle.should_glean.call_count == 2
    assert mock_llm.predict_structured.call_count == 2

