"""Unit and integration tests for Phase 3b Jev Borderline Consolidation & Canonical Election (ISSUE-045)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from episteme_pipeline.config import Phase3bConfig
from episteme_pipeline.contracts.domain import L2Entity
from episteme_pipeline.decision.mock import MockJevDecisionEngine
from episteme_pipeline.events import SimpleEventEmitter, set_event_emitter
from episteme_pipeline.events.models import DecisionGatingTriggered
from episteme_pipeline.phases.phase3b_consolidation import Phase3bLatentConsolidationRunner
from episteme_pipeline.phases.phase3b_consolidation.clustering import (
    elect_canonical_representative,
    verify_borderline_pair,
)
from episteme_pipeline.phases.phase3b_consolidation.consolidation import LatentGraphConsolidation
from episteme_pipeline.prompts.models import StructuredPromptBundle


class EventCollector:
    def __init__(self):
        self.events = []

    def on_event(self, event):
        self.events.append(event)


@pytest.mark.asyncio
async def test_verify_borderline_pair_approved_when_singleton_identical():
    """Conformal merge guard approves merge when prediction set is singleton IDENTICAL_MERGE."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="ontological relationship",
        selected_option="IDENTICAL_MERGE",
        probabilities={"IDENTICAL_MERGE": 0.96, "HIERARCHICAL_SUBSUMPTION": 0.03, "DISTINCT_SEPARATE": 0.01},
        empirical_accuracy=0.94,
        prediction_set=["IDENTICAL_MERGE"],
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    entity_a = L2Entity(id="e1", name="Categorical Imperative", label="Concept")
    entity_b = L2Entity(id="e2", name="Kantian Categorical Imperative", label="Concept")

    selected, emp_acc, pred_set = await verify_borderline_pair(
        entity_a,
        entity_b,
        engine,
        alpha=0.05,
        threshold=0.80,
    )

    assert selected == "IDENTICAL_MERGE"
    assert pred_set == ["IDENTICAL_MERGE"]
    assert emp_acc == 0.94

    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].gate_name == "borderline_merge_gate"
    assert gating_events[0].action_taken == "merge_approved"


@pytest.mark.asyncio
async def test_verify_borderline_pair_aborts_hierarchical_subsumption():
    """Conformal merge guard aborts merge when relationship is hierarchical."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="ontological relationship",
        selected_option="HIERARCHICAL_SUBSUMPTION",
        probabilities={"IDENTICAL_MERGE": 0.10, "HIERARCHICAL_SUBSUMPTION": 0.85, "DISTINCT_SEPARATE": 0.05},
        empirical_accuracy=0.89,
        prediction_set=["HIERARCHICAL_SUBSUMPTION"],
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    entity_a = L2Entity(id="e1", name="Imperative", label="Concept")
    entity_b = L2Entity(id="e2", name="Categorical Imperative", label="Concept")

    selected, emp_acc, pred_set = await verify_borderline_pair(
        entity_a,
        entity_b,
        engine,
    )

    assert selected == "HIERARCHICAL_SUBSUMPTION"
    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].action_taken == "merge_aborted"


@pytest.mark.asyncio
async def test_verify_borderline_pair_aborts_on_ambiguous_prediction_set():
    """Multi-class prediction set aborts merge even if IDENTICAL_MERGE is top pick."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="ontological relationship",
        selected_option="IDENTICAL_MERGE",
        probabilities={"IDENTICAL_MERGE": 0.60, "HIERARCHICAL_SUBSUMPTION": 0.35, "DISTINCT_SEPARATE": 0.05},
        empirical_accuracy=0.70,
        prediction_set=["IDENTICAL_MERGE", "HIERARCHICAL_SUBSUMPTION"],  # Ambiguous multi-label set
    )

    emitter = SimpleEventEmitter()
    collector = EventCollector()
    emitter.register_observer(collector)
    set_event_emitter(emitter)

    entity_a = L2Entity(id="e1", name="Transcendental Aesthetic", label="Concept")
    entity_b = L2Entity(id="e2", name="Transcendental Analytic", label="Concept")

    selected, emp_acc, pred_set = await verify_borderline_pair(
        entity_a,
        entity_b,
        engine,
        threshold=0.80,
    )

    assert len(pred_set) == 2
    # Because pred_set is not singleton and emp_acc (0.70) < threshold (0.80), merge is aborted
    gating_events = [e for e in collector.events if isinstance(e, DecisionGatingTriggered)]
    assert len(gating_events) == 1
    assert gating_events[0].action_taken == "merge_aborted"


@pytest.mark.asyncio
async def test_elect_canonical_representative():
    """Jev Choice elects the standard canonical scholarly designation."""
    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="canonical scholarly designation",
        selected_option="Categorical Imperative",
    )

    entities = [
        L2Entity(id="e1", name="Kantian Imperative", label="Concept", source_chunk_ids=["c1"]),
        L2Entity(id="e2", name="Categorical Imperative", label="Concept", source_chunk_ids=["c2"]),
        L2Entity(id="e3", name="CI Principle", label="Concept", source_chunk_ids=["c3"]),
    ]

    canonical = await elect_canonical_representative(entities, engine)
    assert canonical.name == "Categorical Imperative"


@pytest.mark.asyncio
async def test_latent_consolidation_with_borderline_gating():
    """LatentGraphConsolidation merges borderline pairs only when verified by Jev."""
    engine = MockJevDecisionEngine()
    # e1 vs e2 -> IDENTICAL_MERGE (singleton) -> merged
    engine.register_choice_response(
        question_pattern="ontological relationship",
        state_pattern="categorical imperative",
        selected_option="IDENTICAL_MERGE",
        probabilities={"IDENTICAL_MERGE": 0.95, "DISTINCT_SEPARATE": 0.05},
        prediction_set=["IDENTICAL_MERGE"],
        empirical_accuracy=0.92,
    )

    # Mock embedding model returning cosine sim = 0.80 between e1 and e2 (borderline)
    embedding_model = AsyncMock()
    embedding_model.aget_text_embedding_batch.return_value = [
        [1.0, 0.0],
        [0.8, 0.6],  # cos sim with [1, 0] is 0.8
    ]

    graph_store = AsyncMock()
    e1 = L2Entity(id="e1", name="Categorical Imperative", label="Concept", source_chunk_ids=["c1", "c2"])
    e2 = L2Entity(id="e2", name="Kantian categorical imperative", label="Concept", source_chunk_ids=["c1"])
    graph_store.get_entities.return_value = [e1, e2]

    # Structural overlap
    neighborhood = MagicMock()
    neighborhood.nodes = []
    neighborhood.triples = []
    graph_store.get_neighborhood.return_value = neighborhood

    consolidation = LatentGraphConsolidation(
        embedding_model=embedding_model,
        dense_similarity_threshold=0.85,
        relation_overlap_threshold=0.0,
        decision_engine=engine,
        enable_jev_cluster_verification=True,
        borderline_similarity_lower=0.75,
        borderline_similarity_upper=0.88,
        merge_confidence_threshold=0.80,
    )

    fused_map = await consolidation.fuse(graph_store)
    # e2 merged into canonical e1
    assert "e2" in fused_map
    assert fused_map["e2"] == "e1"


@pytest.mark.asyncio
async def test_verify_borderline_pair_uses_prompt_bundle():
    """BorderlinePairVerifier respects custom StructuredPromptBundle templates and criteria."""
    custom_bundle = StructuredPromptBundle(
        direct_template="Concept: {name} (Type: {type})",
        decision_template="Are these two philosophical concepts identical?",
        decision_criteria={
            "YES_MERGE": "Identical concept",
            "NO_KEEP": "Distinct concepts",
        },
        name="custom_borderline_merge",
    )

    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="identical",
        selected_option="YES_MERGE",
        probabilities={"YES_MERGE": 0.95, "NO_KEEP": 0.05},
        prediction_set=["YES_MERGE"],
        empirical_accuracy=0.91,
    )

    entity_a = L2Entity(id="e1", name="Form of the Good", label="Concept")
    entity_b = L2Entity(id="e2", name="Idea of the Good", label="Concept")

    selected, emp_acc, pred_set = await verify_borderline_pair(
        entity_a,
        entity_b,
        engine,
        prompt_bundle=custom_bundle,
    )

    assert selected == "YES_MERGE"
    assert pred_set == ["YES_MERGE"]
    assert emp_acc == 0.91


@pytest.mark.asyncio
async def test_elect_canonical_representative_uses_prompt_bundle():
    """CanonicalRepresentativeElector respects custom StructuredPromptBundle templates."""
    custom_bundle = StructuredPromptBundle(
        direct_template="Name: {name}",
        decision_template="Choose the canonical ancient Greek term:",
        name="custom_canonical_election",
    )

    engine = MockJevDecisionEngine()
    engine.register_choice_response(
        question_pattern="ancient Greek term",
        selected_option="Eudaimonia",
    )

    entities = [
        L2Entity(id="e1", name="Happiness", label="Concept", source_chunk_ids=["c1"]),
        L2Entity(id="e2", name="Eudaimonia", label="Concept", source_chunk_ids=["c2"]),
    ]

    canonical = await elect_canonical_representative(entities, engine, prompt_bundle=custom_bundle)
    assert canonical.name == "Eudaimonia"

