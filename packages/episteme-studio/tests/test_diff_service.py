"""Unit and integration tests for deterministic run diffing and progression engine."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from episteme_studio.app import create_app
from episteme_studio.domain.diff import NodeDiffStatus
from episteme_studio.domain.graph import GraphView, Layer, StudioEdge, StudioNode
from episteme_studio.domain.runs import RunDetail, RunStatus
from episteme_studio.services.diff_service import DiffService
from episteme_studio.settings import StudioSettings
from httpx import ASGITransport, AsyncClient


def _make_sample_graph_a() -> GraphView:
    nodes = [
        StudioNode(id="entity_1", layer=Layer.L2, type="Concept", label="Concept 1"),
        StudioNode(id="entity_2", layer=Layer.L2, type="Concept", label="Concept 2"),
        StudioNode(id="entity_shared", layer=Layer.L2, type="Concept", label="Shared Concept"),
        StudioNode(id="atom_1", layer=Layer.L3, type="Claim", label="Claim 1", plausibility=0.4),
    ]
    edges = [
        StudioEdge(id="e1", source="entity_1", target="entity_shared", type="SUPPORTS", layer=Layer.L2, polarity=1, weight=0.8),
        StudioEdge(id="e2", source="entity_shared", target="entity_2", type="BESTAETIGT", layer=Layer.L2, polarity=1, weight=0.6),
    ]
    return GraphView(
        nodes=nodes,
        edges=edges,
        source="artifacts",
        run_id="run-a",
        graph_version="a:4:2",
        schema_version="v1",
        truncated=False,
        dropped_count=0,
        unmapped_predicates={},
        unresolved_count=0,
        layer_counts={2: 3, 3: 1},
    )


def _make_sample_graph_b() -> GraphView:
    nodes = [
        StudioNode(id="entity_shared", layer=Layer.L2, type="Concept", label="Shared Concept (Updated)"),
        StudioNode(id="entity_2", layer=Layer.L2, type="Concept", label="Concept 2"),
        StudioNode(id="entity_3", layer=Layer.L2, type="Concept", label="Concept 3 New"),
        StudioNode(id="atom_1", layer=Layer.L3, type="Claim", label="Claim 1", plausibility=0.85),
    ]
    edges = [
        # Inverted polarity on same endpoints: (entity_shared, entity_2) was SUPPORTS (+1), now REFUTES (-1)
        StudioEdge(id="e2_prime", source="entity_shared", target="entity_2", type="WIDERSPRICHT", layer=Layer.L2, polarity=-1, weight=0.9),
        # New edge in B
        StudioEdge(id="e3", source="entity_shared", target="entity_3", type="RELATED_TO", layer=Layer.L2, polarity=0, weight=0.7),
    ]
    return GraphView(
        nodes=nodes,
        edges=edges,
        source="artifacts",
        run_id="run-b",
        graph_version="b:4:2",
        schema_version="v1",
        truncated=False,
        dropped_count=0,
        unmapped_predicates={},
        unresolved_count=0,
        layer_counts={2: 3, 3: 1},
    )


def _make_sample_detail_a() -> RunDetail:
    return RunDetail(
        run_id="run-a",
        status=RunStatus.COMPLETED,
        created_at="2026-09-08T08:00:00Z",
        pipeline_version="0.9.9",
        input_sources=["text.txt"],
        models={"llm_model": "meta-llama/Llama-3-8B", "temperature": "0.2"},
        artifact_count=10,
        size_bytes=1024,
        tags=[],
        phase_records=[],
        artifact_counts_by_kind={},
        graph_schema={},
        config_snapshot={"phase3": {"reranker_threshold": 0.65}, "phase4": {"acc_decoding_strategy": "beam"}},
        fingerprints={},
        unresolved_count=0,
    )


def _make_sample_detail_b() -> RunDetail:
    return RunDetail(
        run_id="run-b",
        status=RunStatus.COMPLETED,
        created_at="2026-09-08T09:00:00Z",
        pipeline_version="0.9.9",
        input_sources=["text.txt"],
        models={"llm_model": "anthropic/claude-3.5-sonnet", "temperature": "0.0"},
        artifact_count=12,
        size_bytes=2048,
        tags=[],
        phase_records=[],
        artifact_counts_by_kind={},
        graph_schema={},
        config_snapshot={"phase3": {"reranker_threshold": 0.80}, "phase4": {"acc_decoding_strategy": "beam"}},
        fingerprints={},
        unresolved_count=0,
    )


def test_diff_service_node_and_edge_classification() -> None:
    """Verify node and edge classification into gained, lost, retained, and polarity_inverted."""
    mock_reader = MagicMock()
    mock_reader.get_graph.side_effect = lambda run_id: _make_sample_graph_a() if run_id == "run-a" else _make_sample_graph_b()
    mock_reader.get_run.side_effect = lambda run_id: _make_sample_detail_a() if run_id == "run-a" else _make_sample_detail_b()

    service = DiffService(reader=mock_reader)
    diff = service.compute_run_diff("run-a", "run-b")

    # Verify Nodes
    assert diff.node_diff["entity_shared"] == NodeDiffStatus.RETAINED
    assert diff.node_diff["entity_2"] == NodeDiffStatus.RETAINED
    assert diff.node_diff["atom_1"] == NodeDiffStatus.RETAINED
    assert diff.node_diff["entity_1"] == NodeDiffStatus.LOST
    assert diff.node_diff["entity_3"] == NodeDiffStatus.GAINED

    # KPIs check
    assert diff.kpis.nodes_retained == 3
    assert diff.kpis.nodes_lost == 1
    assert diff.kpis.nodes_gained == 1

    # Verify Polarity Inversion
    assert len(diff.polarity_inversions) == 1
    inversion = diff.polarity_inversions[0]
    assert inversion.source == "entity_shared"
    assert inversion.target == "entity_2"
    assert inversion.predicate_a == "BESTAETIGT"
    assert inversion.polarity_a == 1
    assert inversion.predicate_b == "WIDERSPRICHT"
    assert inversion.polarity_b == -1

    # Verify Argument Drift
    assert "atom_1" in diff.rho_deltas
    assert diff.rho_deltas["atom_1"] == pytest.approx(0.45, abs=1e-3)
    assert diff.kpis.max_rho_drift == pytest.approx(0.45, abs=1e-3)

    # Verify Config Diff
    config_paths = {item.path for item in diff.config_diff}
    assert "models.llm_model" in config_paths
    assert "models.temperature" in config_paths
    assert "phase3.reranker_threshold" in config_paths
    # phase4.acc_decoding_strategy is identical in both -> should be filtered out
    assert "phase4.acc_decoding_strategy" not in config_paths


@pytest.mark.asyncio
async def test_api_diff_runs_endpoint() -> None:
    """GET /api/diff/runs returns 200 with complete GraphDiffView between existing runs."""
    settings = StudioSettings()
    app = create_app(settings)

    # Pick two existing runs from .pipeline_runs if available
    run_a = "run-96c2cc30-f109-44b7-b9bb-dca728e2b0e4"
    run_b = "run-dd36e818-be22-4373-a83d-99a5a653521d"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/diff/runs?base_id={run_a}&target_id={run_b}")
        if response.status_code == 404:
            pytest.skip("Test runs not present on disk")

        assert response.status_code == 200
        data = response.json()
        assert data["run_a_id"] == run_a
        assert data["run_b_id"] == run_b
        assert "union_graph" in data
        assert "node_diff" in data
        assert "edge_diff" in data
        assert "polarity_inversions" in data
        assert "rho_deltas" in data
        assert "config_diff" in data
        assert "kpis" in data
        assert "jaccard_node_similarity" in data["kpis"]
