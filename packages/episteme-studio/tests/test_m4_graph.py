"""Tests for Milestone 4: Graph materialization from artifacts, evidence trails, and budgeting."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from episteme_studio.app import create_app
from episteme_studio.domain.graph import Layer
from episteme_studio.settings import StudioSettings

LARGEST_RUN_ID = "run-4dd7b5fb-21b9-4236-8e67-ea4363408387"
RUN_EXISTS = (Path(".pipeline_runs") / f"{LARGEST_RUN_ID}.json").exists()
require_largest_run = pytest.mark.skipif(
    not RUN_EXISTS,
    reason=f"Historical run {LARGEST_RUN_ID} not present in .pipeline_runs",
)


@pytest.mark.asyncio
@require_largest_run
async def test_largest_run_graph_materialization() -> None:
    """The 2.3 MB run must render ~100 entities, 260 global relations, 62 local relations."""
    app = create_app(StudioSettings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request with a generous budget to see the full projection
        response = await client.get(f"/api/runs/{LARGEST_RUN_ID}/graph?budget=1000")
        assert response.status_code == 200
        graph = response.json()

        assert graph["run_id"] == LARGEST_RUN_ID
        assert graph["source"] == "artifacts"
        assert "schema_version" in graph

        # Verify layer counts
        layer_counts = graph["layer_counts"]
        assert layer_counts.get("2", 0) >= 70, f"Expected ~100 L2 entities, got {layer_counts.get('2')}"

        # Verify relations
        edges = graph["edges"]
        l2_edges = [e for e in edges if e["layer"] == Layer.L2]
        # Expect ~322 L2 edges (260 global + 62 local)
        assert len(l2_edges) >= 300, f"Expected ~322 L2 edges, got {len(l2_edges)}"

        # Verify unmapped predicates contains open-vocabulary German predicates (D-15)
        unmapped = graph["unmapped_predicates"]
        assert "BEEINFLUSST_VON" in unmapped
        assert "IMPLIZIERT" in unmapped
        assert "BEHANDELT_THEMA" in unmapped


@pytest.mark.asyncio
@require_largest_run
async def test_chunk_embedding_never_in_response() -> None:
    """L1Chunk.embedding must NEVER appear in any response over the wire (SPEC §8 point 6)."""
    app = create_app(StudioSettings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/runs/{LARGEST_RUN_ID}/graph?budget=1000")
        assert response.status_code == 200
        raw_text = response.text

        # Ensure embedding keyword never appears as a property
        data = response.json()
        for node in data["nodes"]:
            assert "embedding" not in node["props"], f"Embedding leaked in node props: {node['id']}"


@pytest.mark.asyncio
@require_largest_run
async def test_node_budget_and_truncation() -> None:
    """Exceeding the node budget sets truncated=True and dropped_count."""
    app = create_app(StudioSettings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request with tiny budget of 10 nodes
        response = await client.get(f"/api/runs/{LARGEST_RUN_ID}/graph?budget=10")
        assert response.status_code == 200
        graph = response.json()

        assert len(graph["nodes"]) == 10
        assert graph["truncated"] is True
        assert graph["dropped_count"] > 0
        # All edges must only connect surviving nodes
        surviving_ids = {n["id"] for n in graph["nodes"]}
        for edge in graph["edges"]:
            assert edge["source"] in surviving_ids
            assert edge["target"] in surviving_ids


@pytest.mark.asyncio
async def test_dangling_component_materialization(tmp_path: Path) -> None:
    """Dangling L3 references must materialize as resolved=False placeholder nodes (D-16)."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    run_id = "run-dangling-test"
    run_art_dir = artifacts_dir / run_id
    run_art_dir.mkdir()

    # Create dummy manifest
    manifest_file = runs_dir / f"{run_id}.json"
    manifest_file.write_text(
        json.dumps({
            "run_id": run_id,
            "status": "completed",
            "created_at": "2026-08-18T10:00:00Z",
            "config_snapshot": {"graph_schema": {}},
        }),
        encoding="utf-8",
    )

    # Create an argument relation pointing to two non-existent components
    rel_file = run_art_dir / "artifact::argument-relation::comp-1::SUPPORTS::comp-2.json"
    rel_file.write_text(
        json.dumps({
            "artifact_id": "artifact::argument-relation::comp-1::SUPPORTS::comp-2",
            "kind": "theory_relation",
            "payload": {
                "source_component_id": "comp-1",
                "target_component_id": "comp-2",
                "relation_type": "SUPPORTS",
            },
        }),
        encoding="utf-8",
    )

    settings = StudioSettings(runs_dir=runs_dir, artifacts_dir=artifacts_dir)
    app = create_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/runs/{run_id}/graph")
        assert response.status_code == 200
        graph = response.json()

        assert graph["unresolved_count"] == 2
        nodes_by_id = {n["id"]: n for n in graph["nodes"]}
        assert "comp-1" in nodes_by_id
        assert nodes_by_id["comp-1"]["resolved"] is False
        assert nodes_by_id["comp-1"]["type"] == "Unresolved"
        assert "comp-2" in nodes_by_id
        assert nodes_by_id["comp-2"]["resolved"] is False


@pytest.mark.asyncio
@require_largest_run
async def test_evidence_trail_endpoint() -> None:
    """GET /api/runs/{id}/evidence/{node_id} traces spans with mode label (D-19)."""
    app = create_app(StudioSettings())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get graph to find a real entity node
        graph_resp = await client.get(f"/api/runs/{LARGEST_RUN_ID}/graph?budget=20")
        nodes = graph_resp.json()["nodes"]
        l2_nodes = [n for n in nodes if n["layer"] == Layer.L2 and n["resolved"]]
        assert len(l2_nodes) > 0
        node = l2_nodes[0]

        evidence_resp = await client.get(f"/api/runs/{LARGEST_RUN_ID}/evidence/{node['id']}")
        assert evidence_resp.status_code == 200
        evidence = evidence_resp.json()

        assert evidence["node_id"] == node["id"]
        assert evidence["layer"] == 2
        assert "chunks" in evidence
        for chunk in evidence["chunks"]:
            assert "chunk_id" in chunk
            assert "text" in chunk
            assert "spans" in chunk
            for span in chunk["spans"]:
                assert span["mode"] in ("exact", "substring", "whole_chunk")
