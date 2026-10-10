"""
Unit tests for Episodic Working Memory state management, Epistemic Anchors,
and Episodic Eviction Handler mechanics.
"""

from __future__ import annotations

from episteme_pipeline.contracts.domain import GlobalStructuralAnchor, L1Chunk
from episteme_pipeline.phases.phase2_entity_discovery.working_memory import (
    EpisodicEvictionHandler,
    EpisodicWorkingMemoryManager,
    JsonPatchWorkingMemoryState,
    KeyValueWorkingMemoryState,
    PydanticWorkingMemoryState,
)


def test_global_structural_anchor_formatting() -> None:
    """Test string formatting of GlobalStructuralAnchor."""
    anchor = GlobalStructuralAnchor(
        toc_structure=["Chapter 1: Foundations", "Chapter 2: Dialectics"],
        document_summary="Overview of Critique of Pure Reason",
        global_thesis="Transcendental Idealism",
    )
    prompt_str = anchor.to_prompt_context()

    assert "Chapter 1: Foundations" in prompt_str
    assert "Chapter 2: Dialectics" in prompt_str
    assert "Overview of Critique of Pure Reason" in prompt_str
    assert "Transcendental Idealism" in prompt_str


def test_json_patch_working_memory_state() -> None:
    """Test state updates and resets in JsonPatchWorkingMemoryState."""
    state = JsonPatchWorkingMemoryState()

    # Initial state prompt context
    assert "Initial Episode State" in state.to_prompt_context()

    # Apply state delta
    state.update({
        "active_entities": ["Categorical Imperative", "Utilitarianism"],
        "unresolved_references": ["this assumption"],
        "current_argument_branch": "Deontological premise",
    })

    raw = state.get_raw_state()
    assert "Categorical Imperative" in raw["active_entities"]
    assert "this assumption" in raw["unresolved_references"]
    assert raw["current_argument_branch"] == "Deontological premise"

    prompt_str = state.to_prompt_context()
    assert "Categorical Imperative" in prompt_str

    # Reset state on episodic eviction
    state.reset(transitional_summary="Shifted to Teleology section.")
    raw_after_reset = state.get_raw_state()
    assert raw_after_reset["active_entities"] == []
    assert raw_after_reset["unresolved_references"] == []
    assert raw_after_reset["transitional_summary"] == "Shifted to Teleology section."


def test_pydantic_working_memory_state() -> None:
    """Test PydanticWorkingMemoryState updates and resets."""
    state = PydanticWorkingMemoryState()

    state.update({
        "active_entities": ["Synthetic A Priori"],
        "unresolved_references": ["the former claim"],
    })

    raw = state.get_raw_state()
    assert "Synthetic A Priori" in raw["active_entities"]
    assert "the former claim" in raw["unresolved_references"]

    state.reset(transitional_summary="Completed section 1.")
    raw_reset = state.get_raw_state()
    assert raw_reset["active_entities"] == []
    assert raw_reset["transitional_summary"] == "Completed section 1."


def test_key_value_working_memory_state() -> None:
    """Test KeyValueWorkingMemoryState updates and resets."""
    state = KeyValueWorkingMemoryState()

    state.update({"topic": "Epistemology", "author": "Kant"})
    raw = state.get_raw_state()
    assert raw["topic"] == "Epistemology"
    assert raw["author"] == "Kant"

    state.reset()
    assert state.get_raw_state() == {}


def test_episodic_eviction_handler() -> None:
    """Test structural and semantic boundary detection in EpisodicEvictionHandler."""
    handler = EpisodicEvictionHandler()

    chunk1 = L1Chunk(
        id="c1",
        text="Sample text 1",
        source_doc_id="doc1",
        chapter_id="Chapter 1",
        sequence_index=0,
        token_count=10,
    )
    chunk2 = L1Chunk(
        id="c2",
        text="Sample text 2",
        source_doc_id="doc1",
        chapter_id="Chapter 1",
        sequence_index=1,
        token_count=10,
    )
    chunk3 = L1Chunk(
        id="c3",
        text="Sample text 3",
        source_doc_id="doc1",
        chapter_id="Chapter 2",
        sequence_index=2,
        token_count=10,
    )

    # First chunk initializes tracked coordinates
    sig1 = handler.evaluate(chunk1)
    assert not sig1.boundary_detected

    # Same section path -> no boundary
    sig2 = handler.evaluate(chunk2)
    assert not sig2.boundary_detected

    # Semantic boundary trigger
    sig2_sem = handler.evaluate(chunk2, semantic_boundary_detected=True, transitional_summary="Ending argument.")
    assert sig2_sem.boundary_detected
    assert sig2_sem.boundary_type == "semantic"
    assert sig2_sem.transitional_summary == "Ending argument."

    # Section path change -> structural boundary
    sig3 = handler.evaluate(chunk3)
    assert sig3.boundary_detected
    assert sig3.boundary_type == "structural"


def test_episodic_working_memory_manager() -> None:
    """Test complete flow in EpisodicWorkingMemoryManager."""
    anchor = GlobalStructuralAnchor(toc_structure="Book 1")
    manager = EpisodicWorkingMemoryManager(anchor=anchor, state_strategy="json_patch")

    chunk = L1Chunk(
        id="c1",
        text="Sample text",
        source_doc_id="doc1",
        chapter_id="Sec 1",
        sequence_index=0,
        token_count=10,
    )

    # Process step with state update
    manager.process_step(
        chunk=chunk,
        state_delta={"active_entities": ["Concept A"]},
        semantic_boundary_detected=False,
    )

    raw_state = manager.state.get_raw_state()
    assert "Concept A" in raw_state["active_entities"]

    # Trigger semantic boundary eviction
    manager.process_step(
        chunk=chunk,
        state_delta={"active_entities": ["Concept B"]},
        semantic_boundary_detected=True,
        transitional_summary="Section closed.",
    )

    # Short-lived variables reset, transitional summary retained
    raw_after_eviction = manager.state.get_raw_state()
    assert raw_after_eviction["active_entities"] == []
    assert raw_after_eviction["transitional_summary"] == "Section closed."
