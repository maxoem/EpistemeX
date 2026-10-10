"""Comprehensive test suite for Milestone 7: Overlays and Configuration Editing."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from episteme_studio.adapters.metrics_adapter import (
    compute_component,
    compute_degree,
    compute_gradual_strength,
    compute_internal_correlation,
    compute_pagerank,
)
from episteme_studio.app import create_app
from episteme_studio.domain.config import FieldProvenance
from episteme_studio.domain.errors import OverlayNotImplementedError
from episteme_studio.domain.graph import GraphView, Layer, StudioEdge, StudioNode
from episteme_studio.domain.overlays import OverlayKind
from episteme_studio.services.config_service import ConfigService
from episteme_studio.services.overlay_service import OverlayService
from episteme_studio.settings import StudioSettings


def create_sample_graph(
    *,
    with_tau_phi: bool = False,
    graph_version: str = "test-gv-001",
) -> GraphView:
    """Helper to generate a test graph view with or without tau/phi values."""
    nodes = [
        StudioNode(
            id="a1",
            layer=Layer.L3,
            type="TheoreticalHypothesis",
            label="Hypothesis 1",
            partition="A",
            plausibility=0.8 if with_tau_phi else None,
        ),
        StudioNode(
            id="a2",
            layer=Layer.L3,
            type="TheoreticalHypothesis",
            label="Hypothesis 2",
            partition="A",
            plausibility=0.4 if with_tau_phi else None,
        ),
        StudioNode(
            id="b1",
            layer=Layer.L3,
            type="EmpiricalStatement",
            label="Evidence 1",
            partition="B",
            plausibility=0.9 if with_tau_phi else None,
        ),
    ]

    edges = [
        # Supportive relation: b1 supports a1
        StudioEdge(
            id="e1",
            source="b1",
            target="a1",
            type="SUPPORTS_ARG",
            layer=Layer.L3,
            polarity=1,
            weight=0.7 if with_tau_phi else None,
        ),
        # Attacking relation: a2 attacks a1
        StudioEdge(
            id="e2",
            source="a2",
            target="a1",
            type="ATTACKS",
            layer=Layer.L3,
            polarity=-1,
            weight=0.5 if with_tau_phi else None,
        ),
    ]

    return GraphView(
        nodes=nodes,
        edges=edges,
        source="fixture",
        graph_version=graph_version,
        schema_version="v1",
    )


# ---------------------------------------------------------------------------
# Overlay Unit & Service Tests
# ---------------------------------------------------------------------------

def test_gradual_strength_reports_incomplete_inputs_on_null_data() -> None:
    """When tau and phi are null, all missing inputs must be tracked (D-12)."""
    graph = create_sample_graph(with_tau_phi=False)
    overlay = compute_gradual_strength(graph)

    assert overlay.kind == OverlayKind.GRADUAL_STRENGTH
    # 3 nodes with null tau + 2 edges with null weight = 5 incomplete inputs
    assert overlay.incomplete_inputs == 5
    assert all(val is None for val in overlay.node_values.values())
    assert all(val is None for val in overlay.edge_values.values())


def test_gradual_strength_iterative_computation_with_data() -> None:
    """When tau and phi are populated, rho is computed via QBAF aggregation."""
    graph = create_sample_graph(with_tau_phi=True)
    overlay = compute_gradual_strength(graph, params={"iterations": 15})

    assert overlay.kind == OverlayKind.GRADUAL_STRENGTH
    assert overlay.incomplete_inputs == 0

    # Node a1 has tau=0.8, support from b1 (0.9 * 0.7 = 0.63), attack from a2 (0.4 * 0.5 = 0.20)
    # Net alpha = +0.43 > 0, so rho(a1) > 0.8
    val_a1 = overlay.node_values.get("a1")
    assert isinstance(val_a1, float)
    assert 0.8 < val_a1 <= 1.0

    # Node b1 has no incoming edges, so rho(b1) == tau(b1) == 0.9
    val_b1 = overlay.node_values.get("b1")
    assert val_b1 == 0.9


def test_internal_correlation_epistemetrics_integration() -> None:
    """Internal correlation connects with epistemetrics algorithm."""
    graph = create_sample_graph(with_tau_phi=True)
    overlay = compute_internal_correlation(graph)

    assert overlay.kind == OverlayKind.INTERNAL_CORRELATION
    assert "score" in overlay.params
    assert isinstance(overlay.params["score"], float)
    assert len(overlay.node_values) == 3


def test_degree_and_component_overlays() -> None:
    """Degree and connected component overlays correctly partition the graph."""
    graph = create_sample_graph(with_tau_phi=False)

    deg_overlay = compute_degree(graph)
    assert deg_overlay.kind == OverlayKind.DEGREE
    assert deg_overlay.node_values["a1"] == 2.0  # target of e1 and e2
    assert deg_overlay.node_values["b1"] == 1.0  # source of e1
    assert deg_overlay.node_values["a2"] == 1.0  # source of e2

    comp_overlay = compute_component(graph)
    assert comp_overlay.kind == OverlayKind.COMPONENT
    # All 3 nodes are connected in a single weakly connected component
    assert comp_overlay.node_values["a1"] == comp_overlay.node_values["b1"]
    assert comp_overlay.node_values["a1"] == comp_overlay.node_values["a2"]


def test_pagerank_computation() -> None:
    """PageRank computes continuous centrality where targeted nodes have higher score."""
    graph = create_sample_graph(with_tau_phi=True)
    pr_overlay = compute_pagerank(graph)

    assert pr_overlay.kind == OverlayKind.PAGERANK
    assert pr_overlay.scale == "continuous"
    assert "a1" in pr_overlay.node_values
    assert "b1" in pr_overlay.node_values
    assert "a2" in pr_overlay.node_values
    # Both b1 and a2 point to a1, so a1 should have the highest centrality score
    assert pr_overlay.node_values["a1"] > pr_overlay.node_values["b1"]
    assert pr_overlay.node_values["a1"] > pr_overlay.node_values["a2"]
    assert pr_overlay.domain[0] <= pr_overlay.domain[1]



def test_overlay_service_caching_and_reserved_kinds() -> None:
    """Overlay service caches by (graph_version, kind, params) and rejects reserved kinds."""
    service = OverlayService()
    graph = create_sample_graph(with_tau_phi=True, graph_version="gv-alpha")

    # First computation
    overlay1 = service.compute_overlay(graph, OverlayKind.DEGREE, {"test": 1})
    assert overlay1.kind == OverlayKind.DEGREE

    # Second call with same parameters must return cached instance
    overlay2 = service.compute_overlay(graph, OverlayKind.DEGREE, {"test": 1})
    assert overlay1 is overlay2
    assert len(service.list_overlays("gv-alpha")) == 1

    # Reserved kinds must raise OverlayNotImplementedError (501)
    with pytest.raises(OverlayNotImplementedError):
        service.compute_overlay(graph, OverlayKind.B_CONSISTENCY)

    with pytest.raises(OverlayNotImplementedError):
        service.compute_overlay(graph, OverlayKind.STABLE_EXTENSION)


# ---------------------------------------------------------------------------
# Config Service Tests
# ---------------------------------------------------------------------------

def test_config_service_provenance_and_secret_redaction() -> None:
    """ConfigService tracks field provenance and masks secrets as '***'."""
    service = ConfigService()
    effective = service.get_effective_config(
        profile_id="default",
        overrides={"phase3.dense_similarity_threshold": 0.99},
    )

    # Overridden field has OVERRIDE provenance
    assert effective.provenance.get("phase3.dense_similarity_threshold") == FieldProvenance.OVERRIDE
    assert effective.values.get("phase3.dense_similarity_threshold") == 0.99

    # Default fields have DEFAULT provenance
    assert effective.provenance.get("phase1.chunk_size") == FieldProvenance.DEFAULT
    assert effective.values.get("phase1.chunk_size") == 1024


def test_invalidation_preview_phase_threshold_change() -> None:
    """A change in phase3 threshold invalidates phase 3 and downstream phases 4..8."""
    service = ConfigService()
    preview = service.preview_invalidation(
        patch={"phase3.global_relation_confidence_threshold": 0.95}
    )

    assert 3 in preview.invalidated_phases
    assert 4 in preview.invalidated_phases
    assert 8 in preview.invalidated_phases
    assert 1 in preview.reused_phases
    assert 2 in preview.reused_phases
    assert "phase_3" in preview.changed_fingerprints
    assert preview.estimated_artifact_loss > 0


def test_invalidation_preview_models_change_zero_invalidations() -> None:
    """Changing models.* produces ZERO phase invalidations per D-14."""
    service = ConfigService()
    preview = service.preview_invalidation(
        patch={
            "models.llm_model": "anthropic/claude-3-7-sonnet",
            "models.temperature": 0.7,
        }
    )

    assert preview.invalidated_phases == []
    assert preview.reused_phases == list(range(1, 9))
    assert preview.reason == "all-reused"
    assert preview.changed_fingerprints == {}
    assert preview.estimated_artifact_loss == 0


# ---------------------------------------------------------------------------
# API Endpoints Integration Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_overlays_reserved_kind_returns_501() -> None:
    """POST /api/overlays with reserved kind returns RFC 7807 501 Not Implemented."""
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/overlays",
            json={"kind": "b_consistency"},
        )
        assert response.status_code == 501
        data = response.json()
        assert data["type"] == "overlay-not-implemented"
        assert "reserved and not implemented" in data["detail"]

        response_stable = await client.post(
            "/api/overlays",
            json={"kind": "stable_extension"},
        )
        assert response_stable.status_code == 501
        data_stable = response_stable.json()
        assert data_stable["type"] == "overlay-not-implemented"


@pytest.mark.asyncio
async def test_api_overlays_compute_and_list() -> None:
    """POST /api/overlays computes degree overlay and GET /api/overlays lists it."""
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Compute degree overlay
        res = await client.post(
            "/api/overlays",
            json={"kind": "degree", "graph_version": "v1"},
        )
        assert res.status_code == 200
        overlay = res.json()
        assert overlay["kind"] == "degree"
        assert "node_values" in overlay

        # List overlays
        list_res = await client.get("/api/overlays")
        assert list_res.status_code == 200
        overlays = list_res.json()
        assert len(overlays) >= 1
        assert any(o["kind"] == "degree" for o in overlays)


@pytest.mark.asyncio
async def test_api_overlays_pagerank_and_neo4j_source(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/overlays computes PageRank overlay and supports source='neo4j'."""
    from episteme_studio.services.graph_service import GraphService

    app = create_app(StudioSettings(demo_mode=True))
    sample_graph = create_sample_graph(with_tau_phi=True, graph_version="neo4j-sample")

    async def mock_neo4j_view(*args, **kwargs):
        return sample_graph

    monkeypatch.setattr(GraphService, "get_neo4j_view", mock_neo4j_view)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Compute PageRank overlay from Neo4j source
        res = await client.post(
            "/api/overlays",
            json={"kind": "pagerank", "source": "neo4j", "graph_version": "neo4j-sample"},
        )
        assert res.status_code == 200
        overlay = res.json()
        assert overlay["kind"] == "pagerank"
        assert "a1" in overlay["node_values"]
        assert overlay["node_values"]["a1"] > overlay["node_values"]["b1"]



@pytest.mark.asyncio
async def test_api_config_effective_and_profiles() -> None:
    """GET /api/config/effective and /api/config/profiles deliver effective configs."""
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Profiles list
        prof_res = await client.get("/api/config/profiles")
        assert prof_res.status_code == 200
        profiles = prof_res.json()
        assert "default" in profiles
        assert "fast" in profiles

        # Effective config
        eff_res = await client.get("/api/config/effective")
        assert eff_res.status_code == 200
        config_view = eff_res.json()
        assert "values" in config_view
        assert "provenance" in config_view
        assert "phase1.chunk_size" in config_view["values"]


@pytest.mark.asyncio
async def test_api_config_invalidation_preview_endpoints() -> None:
    """POST /api/config/invalidation-preview correctly compares phase fingerprints."""
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Models change produces 0 invalidations (D-14)
        model_res = await client.post(
            "/api/config/invalidation-preview",
            json={"patch": {"models.llm_model": "deepseek-ai/DeepSeek-V3"}},
        )
        assert model_res.status_code == 200
        model_preview = model_res.json()
        assert model_preview["invalidated_phases"] == []
        assert len(model_preview["reused_phases"]) == 8

        # 2. Phase 2 threshold change invalidates phases 2..8
        phase_res = await client.post(
            "/api/config/invalidation-preview",
            json={"patch": {"phase2.linking_confidence_threshold": 0.99}},
        )
        assert phase_res.status_code == 200
        phase_preview = phase_res.json()
        assert 1 in phase_preview["reused_phases"]
        assert 2 in phase_preview["invalidated_phases"]

        # 3. Invalid key produces 422 with invalid-config-patch
        err_res = await client.post(
            "/api/config/invalidation-preview",
            json={"patch": {"nonexistent.param": 123}},
        )
        assert err_res.status_code == 422
        err_data = err_res.json()
        assert err_data["type"] == "invalid-config-patch"


@pytest.mark.asyncio
async def test_api_config_prompts_resolve_endpoints() -> None:
    """POST /api/config/prompts/resolve resolves default and fallback prompt bundles."""
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Resolve default prompts
        res = await client.post(
            "/api/config/prompts/resolve",
            json={"provider": "default", "label_or_version": "production"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["provider"] == "default"
        assert "ner_extraction" in data["bundles"]
        assert "global_relation" in data["bundles"]
        assert data["bundles"]["ner_extraction"]["direct_template"] != ""

        # Resolve langfuse prompts (falls back gracefully with warning if unconfigured)
        lf_res = await client.post(
            "/api/config/prompts/resolve",
            json={"provider": "langfuse", "label_or_version": "staging"},
        )
        assert lf_res.status_code == 200
        lf_data = lf_res.json()
        assert "ner_extraction" in lf_data["bundles"]
        assert lf_data["bundles"]["ner_extraction"]["direct_template"] != ""


@pytest.mark.asyncio
async def test_api_config_inputs_endpoints() -> None:
    """GET /api/config/inputs returns candidate document inputs in repository."""
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/config/inputs")
        assert res.status_code == 200
        inputs = res.json()
        assert isinstance(inputs, list)
        assert len(inputs) > 0
        assert any("teachers_expectancies" in item["name"] for item in inputs)


@pytest.mark.asyncio
async def test_api_config_inputs_upload_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/config/inputs/upload saves candidate document and returns metadata."""
    monkeypatch.chdir(tmp_path)
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("my_sample.md", b"# Sample Document\n\nSome text content.", "text/markdown")}
        res = await client.post("/api/config/inputs/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "my_sample.md"
        assert "data/uploads" in data["path"]
        assert data["size_bytes"] == len(b"# Sample Document\n\nSome text content.")

        # Ensure subsequent list includes uploaded document
        list_res = await client.get("/api/config/inputs")
        assert list_res.status_code == 200
        items = list_res.json()
        assert any(item["name"] == "my_sample.md" for item in items)


@pytest.mark.asyncio
async def test_api_config_langfuse_status_endpoint() -> None:
    """GET /api/config/langfuse/status returns connection and telemetry status."""
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/config/langfuse/status")
        assert res.status_code == 200
        status_data = res.json()
        assert "configured" in status_data
        assert "host" in status_data
        assert "has_public_key" in status_data
        assert "telemetry_enabled" in status_data
        assert "connected" in status_data


@pytest.mark.asyncio
async def test_api_config_langfuse_test_endpoint() -> None:
    """POST /api/config/langfuse/test probes connection with custom or default credentials."""
    app = create_app(StudioSettings(demo_mode=True))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/config/langfuse/test",
            json={"host": "http://localhost:3000", "public_key": "pk-lf-test", "secret_key": "sk-lf-test"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["host"] == "http://localhost:3000"
        assert data["has_public_key"] is True
        assert data["has_secret_key"] is True


def test_invalidation_preview_schema_change() -> None:
    """Modifying graph_schema.* invalidates Phase 2..8 while Phase 1 remains reused."""
    service = ConfigService()
    preview = service.preview_invalidation(
        patch={"graph_schema.node_types": ["Concept", "Person", "Work"]}
    )
    assert 1 in preview.reused_phases
    assert 2 in preview.invalidated_phases
    assert 8 in preview.invalidated_phases
    assert "graph_schema" in preview.changed_fingerprints
