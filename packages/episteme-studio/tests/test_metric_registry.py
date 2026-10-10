"""Tests for Story 1: Metric Contracts, Registry, Validation, and Definitions API."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from episteme_studio.app import create_app
from episteme_studio.domain.metrics import (
    MetricDescriptor,
    MetricScope,
)
from episteme_studio.services.metric_service import MetricService
from episteme_studio.settings import StudioSettings


class _MockNeo4jReader:
    """Mock Neo4j reader providing controllable GDS probe responses."""

    def __init__(self, gds_available: bool = False) -> None:
        self._gds_available = gds_available

    async def check_gds_availability(self, timeout: float = 2.0) -> bool:
        return self._gds_available


@pytest.mark.asyncio
async def test_metric_descriptor_models_serialization() -> None:
    """Validate Pydantic serialization and structure of metric domain models."""
    descriptor = MetricDescriptor(
        id="gradual_strength_local",
        label="Local Gradual Strength",
        description="QBAF gradual semantics solver",
        scope=MetricScope.SINGLE_NODE,
        available=True,
        engine="cypher",
        param_schema={
            "type": "object",
            "properties": {
                "max_depth": {"type": "integer", "default": 2},
            },
        },
    )
    dumped = descriptor.model_dump(mode="json")
    assert dumped["id"] == "gradual_strength_local"
    assert dumped["scope"] == "single_node"
    assert dumped["available"] is True
    assert dumped["engine"] == "cypher"
    assert dumped["param_schema"]["properties"]["max_depth"]["type"] == "integer"


@pytest.mark.asyncio
async def test_definitions_endpoint_returns_descriptors_with_valid_schema() -> None:
    """GET /api/metrics/definitions returns registered descriptors with JSON Schemas."""
    app = create_app(StudioSettings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/metrics/definitions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2

        ids = [d["id"] for d in data]
        assert "gradual_strength_local" in ids
        assert "pagerank_global" in ids

        local_metric = next(d for d in data if d["id"] == "gradual_strength_local")
        assert local_metric["scope"] == "single_node"
        assert local_metric["available"] is True
        assert "properties" in local_metric["param_schema"]
        assert "max_depth" in local_metric["param_schema"]["properties"]


@pytest.mark.asyncio
async def test_gds_missing_reports_available_false_with_clear_reason() -> None:
    """When Neo4j GDS probe returns False, GDS-dependent metrics report available: false."""
    mock_reader = _MockNeo4jReader(gds_available=False)
    service = MetricService(neo4j_reader=mock_reader)

    descriptors = await service.list_descriptors()
    pr = next(d for d in descriptors if d.id == "pagerank_global")
    assert pr.available is False
    assert pr.unavailable_reason is not None
    assert "GDS plugin is not installed" in pr.unavailable_reason


@pytest.mark.asyncio
async def test_gds_present_reports_available_true() -> None:
    """When Neo4j GDS probe returns True, GDS-dependent metrics report available: true."""
    mock_reader = _MockNeo4jReader(gds_available=True)
    service = MetricService(neo4j_reader=mock_reader)

    descriptors = await service.list_descriptors()
    pr = next(d for d in descriptors if d.id == "pagerank_global")
    assert pr.available is True
    assert pr.unavailable_reason is None
