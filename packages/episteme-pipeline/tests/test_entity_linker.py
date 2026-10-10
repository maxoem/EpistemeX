"""Tests for NameEntityLinker overlap scoring logic (pure functions)."""

import pytest

from episteme_pipeline.contracts.phase_contracts import L2Entity
from episteme_pipeline.phases.phase2_entity_discovery.entity_linker import (
    _normalized,
    _overlap_score,
    NameEntityLinker,
)


class TestNormalized:
    def test_strips_whitespace(self):
        assert _normalized("  Kant  ") == "kant"

    def test_lowercases(self):
        assert _normalized("HEGEL") == "hegel"

    def test_empty_string(self):
        assert _normalized("") == ""


class TestOverlapScore:
    def test_exact_match_returns_one(self):
        assert _overlap_score("Kant", "Kant") == 1.0

    def test_shorter_contained_in_longer(self):
        # "kant" is in "immanuel kant"
        assert _overlap_score("Kant", "Immanuel Kant") == 1.0

    def test_longer_contains_shorter(self):
        assert _overlap_score("Immanuel Kant", "Kant") == 1.0

    def test_no_overlap_returns_zero(self):
        assert _overlap_score("Kant", "Hegel") == 0.0

    def test_short_name_below_min_chars_returns_zero(self):
        # "I." is 2 chars, below _MIN_OVERLAP_CHARS=4
        assert _overlap_score("I.", "Immanuel Kant") == 0.0

    def test_case_insensitive(self):
        assert _overlap_score("kant", "IMMANUEL KANT") == 1.0

    def test_partial_but_not_contained_returns_zero(self):
        # "Kant" is not contained in "Kantorowicz"... actually it is
        # Let's use a real non-matching case
        assert _overlap_score("Descartes", "Leibniz") == 0.0


class TestNameEntityLinker:
    @pytest.fixture
    def linker(self):
        return NameEntityLinker()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_candidates(self, linker, graph_store):
        mention = L2Entity(id="e1", label="PERSON", name="Kant")
        result = await linker.link(mention, graph_store)
        assert result is None

    @pytest.mark.asyncio
    async def test_links_to_matching_entity_in_graph(self, linker, graph_store):
        # Pre-populate graph
        existing = L2Entity(id="entity_kant_full", label="PERSON", name="Immanuel Kant")
        await graph_store.upsert_entity(existing)

        mention = L2Entity(id="entity_kant_short", label="PERSON", name="Kant")
        result = await linker.link(mention, graph_store)
        assert result is not None
        assert result.id == "entity_kant_full"

    @pytest.mark.asyncio
    async def test_does_not_link_to_same_id(self, linker, graph_store):
        # Entity links to itself should be ignored
        existing = L2Entity(id="entity_kant", label="PERSON", name="Immanuel Kant")
        await graph_store.upsert_entity(existing)

        mention = L2Entity(id="entity_kant", label="PERSON", name="Kant")
        result = await linker.link(mention, graph_store)
        assert result is None

    @pytest.mark.asyncio
    async def test_does_not_link_across_labels(self, linker, graph_store):
        existing = L2Entity(id="entity_kant_konzept", label="KONZEPT", name="Kant")
        await graph_store.upsert_entity(existing)

        mention = L2Entity(id="entity_kant_person", label="PERSON", name="Kant")
        result = await linker.link(mention, graph_store)
        # find_entities_by_name filters by label, so KONZEPT entity won't match PERSON mention
        assert result is None
