"""Tests for JevEntityLinker and CascadingEntityLinker."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from episteme_pipeline.contracts.domain import L2Entity
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.events.bus import SimpleEventEmitter
from episteme_pipeline.events.context import set_event_emitter
from episteme_pipeline.events.models import (
    EntityLinkingCandidatesRetrieved,
    EntityLinkingReranked,
    UnlinkableMentionError,
)
from episteme_pipeline.phases.phase2_entity_discovery import (
    CascadingEntityLinker,
    DenseEntityLinker,
    JevEntityLinker,
    Phase2Runner,
)
from episteme_pipeline.protocols.extractors import EntityLinker


class MockEmbeddingModel:
    """Deterministic mock embedding model for testing."""

    async def aget_text_embedding(self, text: str) -> list[float]:
        return [1.0, 0.0]

    async def aget_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        results = []
        for t in texts:
            if "Kant" in t:
                results.append([1.0, 0.0])
            elif "Hegel" in t:
                results.append([0.8, 0.2])
            elif "Spinoza" in t:
                results.append([0.1, 0.9])
            else:
                results.append([0.5, 0.5])
        return results


def test_protocol_conformance():
    """Verify both linkers satisfy the EntityLinker ABC."""
    engine = MockJevDecisionEngine()
    embed = MockEmbeddingModel()
    jev_linker = JevEntityLinker(decision_engine=engine, embedding_model=embed)
    cascading_linker = CascadingEntityLinker(primary=jev_linker, fallback=jev_linker)

    assert isinstance(jev_linker, EntityLinker)
    assert isinstance(cascading_linker, EntityLinker)


@pytest.mark.asyncio
async def test_jev_entity_linker_matching():
    """Verify JevEntityLinker links mention when conformal set has single candidate."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="Which entity",
        state_pattern="Kant",
        selected_option="Immanuel Kant",
        prediction_set=["Immanuel Kant"],
        empirical_accuracy=0.96,
    )

    embed = MockEmbeddingModel()
    linker = JevEntityLinker(decision_engine=engine, embedding_model=embed, alpha=0.05)

    candidate_kant = L2Entity(id="e_kant", name="Immanuel Kant", label="PERSON", description="German philosopher")
    candidate_hegel = L2Entity(id="e_hegel", name="G.W.F. Hegel", label="PERSON", description="German idealist")
    mock_store = AsyncMock()
    mock_store.get_entities.return_value = [candidate_kant, candidate_hegel]

    mention = L2Entity(
        id="m1",
        name="Kant",
        label="PERSON",
        textual_envelope="The philosopher [ENT] Kant [\\ENT] wrote the Critique of Pure Reason.",
    )

    events = []
    emitter = SimpleEventEmitter()
    emitter.register_observer(MagicMock(on_event=lambda e: events.append(e)))
    set_event_emitter(emitter)

    matched = await linker.link(mention, mock_store)

    assert matched is not None
    assert matched.id == "e_kant"
    assert matched.name == "Immanuel Kant"

    retrieved_events = [e for e in events if isinstance(e, EntityLinkingCandidatesRetrieved)]
    reranked_events = [e for e in events if isinstance(e, EntityLinkingReranked)]

    assert len(retrieved_events) == 1
    assert retrieved_events[0].mention_name == "Kant"
    assert len(reranked_events) == 1
    assert reranked_events[0].accepted is True
    assert reranked_events[0].candidate_id == "e_kant"


@pytest.mark.asyncio
async def test_jev_entity_linker_out_of_ontology():
    """Verify JevEntityLinker returns None when OUT_OF_ONTOLOGY is selected."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="Which entity",
        state_pattern="Carnap",
        selected_option="OUT_OF_ONTOLOGY",
        prediction_set=["OUT_OF_ONTOLOGY"],
        empirical_accuracy=0.92,
    )

    embed = MockEmbeddingModel()
    linker = JevEntityLinker(decision_engine=engine, embedding_model=embed)

    candidate_kant = L2Entity(id="e_kant", name="Immanuel Kant", label="PERSON", description="German philosopher")
    mock_store = AsyncMock()
    mock_store.get_entities.return_value = [candidate_kant]

    mention = L2Entity(
        id="m2",
        name="Carnap",
        label="PERSON",
        textual_envelope="Rudolf [ENT] Carnap [\\ENT] developed the Aufbau.",
    )

    events = []
    emitter = SimpleEventEmitter()
    emitter.register_observer(MagicMock(on_event=lambda e: events.append(e)))
    set_event_emitter(emitter)

    matched, decision, is_ambiguous = await linker.link_with_decision(mention, mock_store)

    assert matched is None
    assert is_ambiguous is False
    assert decision.selected_option == "OUT_OF_ONTOLOGY"

    reranked_events = [e for e in events if isinstance(e, EntityLinkingReranked)]
    assert len(reranked_events) == 1
    assert reranked_events[0].accepted is False
    assert reranked_events[0].candidate_id == "OUT_OF_ONTOLOGY"


@pytest.mark.asyncio
async def test_jev_entity_linker_ambiguous_escalation():
    """Verify multiple options in conformal prediction set marks decision as ambiguous."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="Which entity",
        state_pattern="Idealism",
        selected_option="German Idealism",
        prediction_set=["German Idealism", "Transcendental Idealism"],
        empirical_accuracy=0.60,
    )

    embed = MockEmbeddingModel()
    linker = JevEntityLinker(decision_engine=engine, embedding_model=embed)

    cand1 = L2Entity(id="e1", name="German Idealism", label="CONCEPT", description="Philosophical movement")
    cand2 = L2Entity(id="e2", name="Transcendental Idealism", label="CONCEPT", description="Kant's doctrine")
    mock_store = AsyncMock()
    mock_store.get_entities.return_value = [cand1, cand2]

    mention = L2Entity(
        id="m3",
        name="Idealism",
        label="CONCEPT",
        textual_envelope="The critique laid the foundation for modern [ENT] idealism [\\ENT].",
    )

    matched, decision, is_ambiguous = await linker.link_with_decision(mention, mock_store)

    assert matched is None
    assert is_ambiguous is True
    assert len(decision.prediction_set) == 2


@pytest.mark.asyncio
async def test_jev_entity_linker_missing_envelope_raises():
    """Verify mention lacking textual envelope raises UnlinkableMentionError."""
    engine = MockJevDecisionEngine()
    linker = JevEntityLinker(decision_engine=engine, embedding_model=MockEmbeddingModel())

    mention_no_env = L2Entity(id="m4", name="Kant", label="PERSON", textual_envelope=None)
    with pytest.raises(UnlinkableMentionError):
        await linker.link(mention_no_env, AsyncMock())


@pytest.mark.asyncio
async def test_jev_entity_linker_empty_candidates_returns_none():
    """Verify empty graph store returns None immediately."""
    engine = MockJevDecisionEngine()
    linker = JevEntityLinker(decision_engine=engine, embedding_model=MockEmbeddingModel())

    mention = L2Entity(id="m5", name="Kant", label="PERSON", textual_envelope="[ENT] Kant [\\ENT]")
    mock_store = AsyncMock()
    mock_store.get_entities.return_value = []

    matched = await linker.link(mention, mock_store)
    assert matched is None


@pytest.mark.asyncio
async def test_cascading_entity_linker_flow():
    """Verify CascadingEntityLinker delegates to primary, respects OoO, and cascades on ambiguity."""
    engine = MockJevDecisionEngine()

    # Ambiguous rule
    engine.register_choice_response(
        question_pattern="Which entity",
        state_pattern="AmbiguousMention",
        selected_option="Candidate A",
        prediction_set=["Candidate A", "Candidate B"],
        empirical_accuracy=0.60,
    )
    # OoO rule
    engine.register_choice_response(
        question_pattern="Which entity",
        state_pattern="NovelMention",
        selected_option="OUT_OF_ONTOLOGY",
        prediction_set=["OUT_OF_ONTOLOGY"],
        empirical_accuracy=0.95,
    )
    # Clear rule
    engine.register_choice_response(
        question_pattern="Which entity",
        state_pattern="ClearMention",
        selected_option="Candidate A",
        prediction_set=["Candidate A"],
        empirical_accuracy=0.98,
    )

    embed = MockEmbeddingModel()
    jev_linker = JevEntityLinker(decision_engine=engine, embedding_model=embed)

    fallback_linker = AsyncMock(spec=EntityLinker)
    fallback_entity = L2Entity(id="e_fallback", name="Resolved by CrossEncoder", label="PERSON")
    fallback_linker.link.return_value = fallback_entity

    cascade = CascadingEntityLinker(primary=jev_linker, fallback=fallback_linker)

    cand_a = L2Entity(id="ca", name="Candidate A", label="PERSON", description="Cand A")
    cand_b = L2Entity(id="cb", name="Candidate B", label="PERSON", description="Cand B")
    mock_store = AsyncMock()
    mock_store.get_entities.return_value = [cand_a, cand_b]

    # 1. Clear mention -> Handled by Jev, fallback NOT called
    mention_clear = L2Entity(
        id="m_clear", name="ClearMention", label="PERSON",
        textual_envelope="Context for [ENT] ClearMention [\\ENT]"
    )
    res_clear = await cascade.link(mention_clear, mock_store)
    assert res_clear is not None
    assert res_clear.id == "ca"
    assert fallback_linker.link.call_count == 0

    # 2. Out-of-Ontology mention -> Jev decisively declares OoO, fallback NOT called
    mention_novel = L2Entity(
        id="m_novel", name="NovelMention", label="PERSON",
        textual_envelope="Context for [ENT] NovelMention [\\ENT]"
    )
    res_novel = await cascade.link(mention_novel, mock_store)
    assert res_novel is None
    assert fallback_linker.link.call_count == 0

    # 3. Ambiguous mention -> Jev prediction set > 1, cascades to fallback!
    mention_ambig = L2Entity(
        id="m_ambig", name="AmbiguousMention", label="PERSON",
        textual_envelope="Context for [ENT] AmbiguousMention [\\ENT]"
    )
    res_ambig = await cascade.link(mention_ambig, mock_store)
    assert res_ambig is fallback_entity
    assert fallback_linker.link.call_count == 1


@pytest.mark.asyncio
async def test_cascading_entity_linker_stochastic_audit():
    """Verify stochastic audit forces fallback execution even when primary would succeed."""
    primary_mock = AsyncMock(spec=EntityLinker)
    fallback_mock = AsyncMock(spec=EntityLinker)
    fallback_mock.link.return_value = L2Entity(id="e_audit", name="Audit Node", label="PERSON")

    # audit_rate = 1.0 forces every call through fallback
    cascade = CascadingEntityLinker(primary=primary_mock, fallback=fallback_mock, audit_rate=1.0)

    mention = L2Entity(id="m_aud", name="Audit", label="PERSON", textual_envelope="[ENT] Audit [\\ENT]")
    result = await cascade.link(mention, AsyncMock())

    assert result is not None
    assert result.id == "e_audit"
    assert primary_mock.link.call_count == 0
    assert fallback_mock.link.call_count == 1


def test_phase2_runner_explicit_entity_linker_injection():
    """Verify Phase2Runner honors an explicitly injected entity_linker."""
    from episteme_pipeline.config import Phase2Config

    custom_linker = MagicMock(spec=EntityLinker)
    config = Phase2Config()

    runner = Phase2Runner(
        config=config,
        schema=MagicMock(),
        llm=MagicMock(),
        graph_store=AsyncMock(),
        entity_linker=custom_linker,
    )

    assert runner.entity_linker is custom_linker


def test_jev_entity_linker_requires_embedding_model():
    """Verify JevEntityLinker raises ValueError when embedding_model is not provided."""
    engine = MockJevDecisionEngine()
    with pytest.raises(ValueError, match="A valid EmbeddingModel must be provided"):
        JevEntityLinker(decision_engine=engine, embedding_model=None)

