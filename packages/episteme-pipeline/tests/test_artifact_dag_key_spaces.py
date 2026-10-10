"""Regression tests for the artifact DAG's two key spaces (O-01).

``artifact_id`` (``artifact::{x}``) is how artifacts reference each other via
``provenance.upstream_artifact_ids``; ``identity_key`` (``{kind}::{x}``) is how
the DAG indexes its nodes. They never coincide. Before O-01 the adjacency maps
were keyed by ``artifact_id`` while ``nodes`` was keyed by ``identity_key``, so
the two shared no keys: staleness propagation was always a no-op and
``topsort`` silently degenerated to insertion order. Both are plain ``str``, so
nothing raised — hence these tests.
"""

from __future__ import annotations

import pytest
from episteme_pipeline.artifacts.invalidate import (
    ArtifactDependencyGraph,
    build_prior_fingerprints,
    find_stale_nodes,
)
from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactProvenance,
    ChunkArtifact,
    DocumentArtifact,
)


def _document(doc_id: str, *, fingerprint: str) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_id=f"artifact::{doc_id}",
        identity_key=f"document::{doc_id}",
        kind=ArtifactKind.DOCUMENT,
        run_id="run-test",
        phase_name="Phase 1: Data Foundation",
        method="test",
        provenance=ArtifactProvenance(source_path=f"/tmp/{doc_id}.md"),
        payload=DocumentArtifact(
            document_id=doc_id, title=doc_id, source_path=f"/tmp/{doc_id}.md"
        ),
        dependency_fingerprint=fingerprint,
    )


def _chunk(
    chunk_id: str, *, doc_id: str, fingerprint: str, upstream: list[str] | None = None
) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        artifact_id=f"artifact::{chunk_id}",
        identity_key=f"chunk::{chunk_id}",
        kind=ArtifactKind.CHUNK,
        run_id="run-test",
        phase_name="Phase 1: Data Foundation",
        method="test",
        provenance=ArtifactProvenance(
            source_document_id=doc_id,
            source_chunk_id=chunk_id,
            # Note: an *artifact_id*, not an identity_key. This is the whole point.
            upstream_artifact_ids=upstream
            if upstream is not None
            else [f"artifact::{doc_id}"],
        ),
        payload=ChunkArtifact(
            chunk_id=chunk_id,
            document_id=doc_id,
            text="x",
            sequence_index=0,
            token_count=1,
        ),
        dependency_fingerprint=fingerprint,
    )


def test_edges_are_keyed_by_identity_key_not_artifact_id() -> None:
    doc = _document("doc1", fingerprint="fp-doc-v1")
    chunk = _chunk("doc1#0", doc_id="doc1", fingerprint="fp-chunk-v1")
    dag = ArtifactDependencyGraph.from_artifacts([doc, chunk])

    # Both sides of every edge must be a key in `nodes`.
    assert dag.downstream["document::doc1"] == {"chunk::doc1#0"}
    assert dag.upstream["chunk::doc1#0"] == {"document::doc1"}
    assert not dag.unresolved_upstream
    for parent, children in dag.downstream.items():
        assert parent in dag.nodes
        assert children <= set(dag.nodes)


def test_add_is_order_independent() -> None:
    """A dependent may be added before the artifact it references."""
    doc = _document("doc1", fingerprint="fp-doc-v1")
    chunk = _chunk("doc1#0", doc_id="doc1", fingerprint="fp-chunk-v1")

    forward = ArtifactDependencyGraph.from_artifacts([doc, chunk])
    reverse = ArtifactDependencyGraph.from_artifacts([chunk, doc])

    assert dict(forward.downstream) == dict(reverse.downstream)
    assert dict(forward.upstream) == dict(reverse.upstream)


def test_staleness_propagates_downstream() -> None:
    """A changed document must invalidate the chunks derived from it."""
    prior = [
        _document("doc1", fingerprint="fp-doc-v1"),
        _chunk("doc1#0", doc_id="doc1", fingerprint="fp-chunk-v1"),
    ]
    # Document changed; the chunk's own fingerprint is untouched.
    current = [
        _document("doc1", fingerprint="fp-doc-v2"),
        _chunk("doc1#0", doc_id="doc1", fingerprint="fp-chunk-v1"),
    ]

    dag = ArtifactDependencyGraph.from_artifacts(current)
    stale = find_stale_nodes(
        dag, build_prior_fingerprints(prior), prior_artifacts=prior
    )

    assert "document::doc1" in stale
    assert "chunk::doc1#0" in stale, "staleness did not propagate across the edge"


def test_unchanged_run_is_not_stale() -> None:
    artifacts = [
        _document("doc1", fingerprint="fp-doc-v1"),
        _chunk("doc1#0", doc_id="doc1", fingerprint="fp-chunk-v1"),
    ]
    dag = ArtifactDependencyGraph.from_artifacts(artifacts)
    stale = find_stale_nodes(
        dag, build_prior_fingerprints(artifacts), prior_artifacts=artifacts
    )
    assert stale == set()


def test_dangling_reference_is_recorded_not_dropped() -> None:
    """An upstream id outside the loaded set is visible, not silently absent.

    This is the normal case for a hydrated phase whose parent-run artifacts were
    not loaded — the graph is incomplete, and a caller must be able to tell that
    apart from "this node has no dependencies".
    """
    orphan = _chunk("doc9#0", doc_id="doc9", fingerprint="fp-chunk-v1")
    dag = ArtifactDependencyGraph.from_artifacts([orphan])

    assert dag.unresolved_upstream["chunk::doc9#0"] == {"artifact::doc9"}
    assert dag.upstream.get("chunk::doc9#0", set()) == set()


def test_topsort_orders_dependencies_first() -> None:
    doc = _document("doc1", fingerprint="fp-doc-v1")
    chunks = [
        _chunk(f"doc1#{i}", doc_id="doc1", fingerprint=f"fp-chunk-{i}")
        for i in range(3)
    ]
    # Insertion order is deliberately the reverse of dependency order, so an
    # implementation that returns insertion order fails this test.
    dag = ArtifactDependencyGraph.from_artifacts([*reversed(chunks), doc])

    order = dag.topsort()
    assert set(order) == set(dag.nodes)
    doc_pos = order.index("document::doc1")
    for chunk in chunks:
        assert doc_pos < order.index(chunk.identity_key)


def test_topsort_detects_cycles() -> None:
    a = _chunk("a", doc_id="doc1", fingerprint="fp-a", upstream=["artifact::b"])
    b = _chunk("b", doc_id="doc1", fingerprint="fp-b", upstream=["artifact::a"])
    dag = ArtifactDependencyGraph.from_artifacts([a, b])
    with pytest.raises(ValueError, match="cycle"):
        dag.topsort()


def test_phase_staleness_map_groups_by_phase_name() -> None:
    prior = [
        _document("doc1", fingerprint="fp-doc-v1"),
        _chunk("doc1#0", doc_id="doc1", fingerprint="fp-chunk-v1"),
    ]
    current = [
        _document("doc1", fingerprint="fp-doc-v2"),
        _chunk("doc1#0", doc_id="doc1", fingerprint="fp-chunk-v1"),
    ]
    dag = ArtifactDependencyGraph.from_artifacts(current)
    by_phase = dag.build_phase_staleness_map(
        build_prior_fingerprints(prior), prior_artifacts=prior
    )
    assert set(by_phase) == {"Phase 1: Data Foundation"}
    assert sorted(by_phase["Phase 1: Data Foundation"]) == [
        "chunk::doc1#0",
        "document::doc1",
    ]
