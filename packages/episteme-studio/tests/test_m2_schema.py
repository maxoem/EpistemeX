"""Tests for Milestone 2: Schema discovery and polarity/partition resolution."""

from __future__ import annotations

import pytest
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_studio.adapters.schema_mapper import SchemaMapper
from episteme_studio.app import create_app
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_get_schema_endpoint() -> None:
    """GET /api/schema must return the active SchemaConfig dictionary."""
    app = create_app(StudioSettings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/schema")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "node_types" in data
        assert "relation_types" in data
        assert "component_types" in data
        assert "argument_relation_types" in data
        assert "relation_polarities" in data
        assert "component_partitions" in data
        # Check specific default mappings
        assert data["relation_polarities"].get("SUPPORTS_ARG") == 1
        assert data["relation_polarities"].get("ATTACKS") == -1
        assert data["component_partitions"].get("TheoreticalHypothesis") == "A"
        assert data["component_partitions"].get("ObservationUnit") == "B"


def test_schema_mapper_polarity_resolution() -> None:
    """Polarity resolution must preserve null vs 0 distinction (D-12, D-15)."""
    mapper = SchemaMapper()

    # Known positive / negative
    assert mapper.resolve_polarity("SUPPORTS_ARG") == 1
    assert mapper.resolve_polarity("ATTACKS") == -1
    assert mapper.resolve_polarity("UNDERCUTS") == -1

    # Explicitly neutral in schema (SPECIALIZES, CONSTRAINS, RELATED_TO)
    assert mapper.resolve_polarity("SPECIALIZES") == 0
    assert mapper.resolve_polarity("RELATED_TO") == 0

    # Unmapped predicate (e.g. open-vocabulary German from extraction)
    # MUST resolve to None (null on wire), NEVER to 0!
    assert mapper.resolve_polarity("WIDERSPRICHT") is None
    assert mapper.resolve_polarity("UNKNOWN_RELATION") is None


def test_schema_mapper_partition_resolution() -> None:
    """Partition resolution must return 'B', 'A', or None for unknown."""
    mapper = SchemaMapper()

    assert mapper.resolve_partition("ObservationUnit") == "B"
    assert mapper.resolve_partition("EmpiricalStatement") == "B"
    assert mapper.resolve_partition("TheoreticalHypothesis") == "A"
    assert mapper.resolve_partition("CoreExpansion") == "A"
    assert mapper.resolve_partition("NonExistentComponent") is None


def test_schema_mapper_unknown_node_type_graceful() -> None:
    """Unknown node types must resolve to neutral descriptor rather than raising (D-13)."""
    mapper = SchemaMapper()

    # Known L2 node type
    known_l2 = mapper.resolve_node_descriptor("Concept", layer=2)
    assert known_l2["known"] is True
    assert known_l2["type"] == "Concept"

    # Known L3 node type
    known_l3 = mapper.resolve_node_descriptor("TheoreticalHypothesis", layer=3)
    assert known_l3["known"] is True
    assert known_l3["partition"] == "A"
    assert known_l3["definition"] is not None

    # Unknown L2 node type
    unknown_l2 = mapper.resolve_node_descriptor("Methodology", layer=2)
    assert unknown_l2["known"] is False
    assert unknown_l2["type"] == "Methodology"

    # Unknown L3 node type (e.g. unresolved dangling component)
    unknown_l3 = mapper.resolve_node_descriptor("Unresolved", layer=3)
    assert unknown_l3["known"] is False
    assert unknown_l3["partition"] is None


def test_custom_schema_override() -> None:
    """SchemaMapper respects custom SchemaConfig instances."""
    custom_schema = SchemaConfig(
        version="custom-v2",
        relation_polarities={"WIDERSPRICHT": -1, "BESTAETIGT": 1},
        component_partitions={"DataAtom": "B"},
    )
    mapper = SchemaMapper(custom_schema)

    assert mapper.resolve_polarity("WIDERSPRICHT") == -1
    assert mapper.resolve_polarity("BESTAETIGT") == 1
    assert mapper.resolve_polarity("OTHER") is None
    assert mapper.resolve_partition("DataAtom") == "B"
