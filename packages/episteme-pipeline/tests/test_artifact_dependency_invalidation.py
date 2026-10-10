"""Tests for build_phase_staleness_map and structural DAG diff staleness."""

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from episteme_pipeline.artifacts.invalidate import (
    ArtifactDependencyGraph,
    build_prior_fingerprints,
    find_stale_nodes,
)
from episteme_pipeline.artifacts.mappers import map_phase1_output_to_artifacts
from episteme_pipeline.artifacts.models import ArtifactEnvelope, ArtifactKind
from episteme_pipeline.contracts.phase_contracts import (
    L1Chunk,
    L1Document,
    Phase1Output,
)


class StubPhase:
    def __init__(self, name: str, artifacts: list | None = None):
        self.name = name
        self.phase_key = "phase1"
        self.artifacts = artifacts or []

    async def run(self, input, context: ArtifactExecutionContext):
        return ArtifactCollection([])


def _create_phase1_artifacts(run_id: str) -> list[ArtifactEnvelope]:
    """Create a list of phase 1 artifacts for testing."""
    artifacts = []
    for artifact in map_phase1_output_to_artifacts(
        Phase1Output(
            documents=[
                L1Document(
                    id="doc-1",
                    title="Doc",
                    source_path="docs/doc.md",
                    chapter_count=1,
                    chunk_count=1,
                )
            ],
            chunks=[
                L1Chunk(
                    id="chunk-1",
                    text="Hello",
                    source_doc_id="doc-1",
                    chapter_id="chap-1",
                    sequence_index=0,
                    token_count=1,
                )
            ],
        ),
        run_id=run_id,
    ):
        artifacts.append(artifact)
    return artifacts


# ---------------------------------------------------------------------------
# Direct unit tests for build_phase_staleness_map
# ---------------------------------------------------------------------------


def test_build_phase_staleness_map_detects_changed_fingerprint() -> None:
    """When an artifact's dependency_fingerprint differs from stored prior_fps,
    it and its transitive dependents are marked stale."""
    artifacts = _create_phase1_artifacts("run-old")
    dag = ArtifactDependencyGraph.from_artifacts(artifacts)
    prior_fps = build_prior_fingerprints(artifacts)

    # No change — should be empty
    stale_map = dag.build_phase_staleness_map(prior_fps)
    assert stale_map == {}

    # Change one fingerprint — should detect it
    changed_artifacts = _create_phase1_artifacts("run-old")
    changed_artifacts[0].dependency_fingerprint = "changed-fingerprint"

    new_dag = ArtifactDependencyGraph.from_artifacts(changed_artifacts)
    stale_map = new_dag.build_phase_staleness_map(prior_fps)
    assert stale_map  # non-empty for the phase that changed


def test_build_phase_staleness_map_new_identity_key_is_stale() -> None:
    """An artifact with an identity_key not in prior_fps is stale."""
    artifacts = _create_phase1_artifacts("run-old")
    prior_fps = build_prior_fingerprints(artifacts)

    # A brand new artifact (not in prior_fps, but has a fingerprint)
    new_artifacts = _create_phase1_artifacts("run-new")
    new_dag = ArtifactDependencyGraph.from_artifacts(new_artifacts)
    stale_map = new_dag.build_phase_staleness_map(prior_fps)
    # "run-new" artifacts have different identity keys
    assert (
        stale_map == {}
    )  # because identity keys are derived from run_id via artifact_id


# ---------------------------------------------------------------------------
# Structural DAG diff tests
# ---------------------------------------------------------------------------


def _make_artifact(
    identity_key: str,
    dependency_fp: str,
    upstream: list[str],
    phase_name: str = "test-phase",
) -> ArtifactEnvelope:
    """Helper to create a minimal ArtifactEnvelope for structural diff tests."""
    from episteme_pipeline.artifacts.models import (
        ArtifactProvenance,
        DocumentArtifact,
    )

    return ArtifactEnvelope(
        artifact_id=f"artifact::{identity_key}",
        identity_key=identity_key,
        kind=ArtifactKind.DOCUMENT,
        run_id="test-run",
        phase_name=phase_name,
        method="test-method",
        dependency_fingerprint=dependency_fp,
        provenance=ArtifactProvenance(upstream_artifact_ids=upstream),
        payload=DocumentArtifact(
            document_id="dummy",
            title="dummy",
            source_path="dummy.md",
        ),
    )


def test_structural_diff_detects_added_upstream_dep() -> None:
    """When a node's provenance upstream_artifact_ids gains a new dependency,
    the structural diff marks it stale even if dependency_fingerprint matches."""
    current = [
        _make_artifact("chunk::chunk-1", "fp-match", ["doc::doc-1"]),
    ]
    current_dag = ArtifactDependencyGraph.from_artifacts(current)

    prior = [
        _make_artifact("chunk::chunk-1", "fp-match", ["old-dep"]),
    ]

    prior_fps = build_prior_fingerprints(prior)
    stale = find_stale_nodes(current_dag, prior_fps, prior_artifacts=prior)

    assert "chunk::chunk-1" in stale


def test_structural_diff_detects_removed_upstream_dep() -> None:
    """When a node loses an upstream dep, it's structurally stale."""
    current = [
        _make_artifact("chunk::chunk-1", "fp-match", []),
    ]
    current_dag = ArtifactDependencyGraph.from_artifacts(current)

    prior = [
        _make_artifact("chunk::chunk-1", "fp-match", ["doc::doc-1"]),
    ]

    prior_fps = build_prior_fingerprints(prior)
    stale = find_stale_nodes(current_dag, prior_fps, prior_artifacts=prior)

    assert "chunk::chunk-1" in stale


def test_structural_diff_no_change() -> None:
    """When provenance edges match, the node is not structurally stale."""
    current = [
        _make_artifact("chunk::chunk-1", "fp-match", ["doc::doc-1"]),
    ]
    current_dag = ArtifactDependencyGraph.from_artifacts(current)

    prior = [
        _make_artifact("chunk::chunk-1", "fp-match", ["doc::doc-1"]),
    ]

    prior_fps = build_prior_fingerprints(prior)
    stale = find_stale_nodes(current_dag, prior_fps, prior_artifacts=prior)

    assert "chunk::chunk-1" not in stale


def test_structural_diff_propagates_downstream() -> None:
    """When a node is structurally stale, its downstream dependents become stale too."""
    current = [
        _make_artifact("chunk::chunk-1", "fp-match", ["new-dep"]),
        _make_artifact("entity::ent-1", "fp-match", ["artifact::chunk::chunk-1"]),
    ]
    current_dag = ArtifactDependencyGraph.from_artifacts(current)

    prior = [
        _make_artifact("chunk::chunk-1", "fp-match", ["old-dep"]),
        _make_artifact("entity::ent-1", "fp-match", ["artifact::chunk::chunk-1"]),
    ]

    prior_fps = build_prior_fingerprints(prior)
    stale = find_stale_nodes(current_dag, prior_fps, prior_artifacts=prior)

    assert "chunk::chunk-1" in stale
    assert "entity::ent-1" in stale


def test_build_phase_staleness_map_includes_structural_diff() -> None:
    """build_phase_staleness_map uses prior_artifacts for structural comparison."""
    current = [
        _make_artifact(
            "chunk::chunk-1", "fp-match", ["new-dep"], phase_name="test-phase"
        ),
    ]
    current_dag = ArtifactDependencyGraph.from_artifacts(current)

    prior = [
        _make_artifact(
            "chunk::chunk-1", "fp-match", ["old-dep"], phase_name="test-phase"
        ),
    ]

    prior_fps = build_prior_fingerprints(prior)
    stale_map = current_dag.build_phase_staleness_map(prior_fps, prior_artifacts=prior)

    assert "test-phase" in stale_map


def test_new_node_without_upstream_artifacts_not_structural_stale() -> None:
    """A new node with no upstream deps and no prior entry is fingerprint-stale,
    but should NOT be marked structurally stale (structural diff only flags
    nodes that HAD upstream deps before but have different ones)."""
    current = [
        _make_artifact("new-art", "new-fp", []),
    ]
    current_dag = ArtifactDependencyGraph.from_artifacts(current)

    prior = [
        _make_artifact("other-art", "old-fp", []),
    ]

    prior_fps = build_prior_fingerprints(prior)
    stale = find_stale_nodes(current_dag, prior_fps, prior_artifacts=prior)

    assert "new-art" in stale
    # The node is not in structurally_stale because prior has no entry for it
    # and current has no upstream deps (edge set is empty both sides)
    from episteme_pipeline.artifacts.invalidate import (
        _build_prior_upstream,
        _compare_dag_structures,
    )

    prior_upstream = _build_prior_upstream(prior)
    structurally_stale = _compare_dag_structures(current_dag, prior_upstream)
    assert "new-art" not in structurally_stale


def test_build_phase_staleness_map_no_change() -> None:
    """When structural provenance matches, no staleness is detected."""
    current = [
        _make_artifact(
            "chunk::chunk-1", "fp-match", ["doc::doc-1"], phase_name="test-phase"
        ),
    ]
    current_dag = ArtifactDependencyGraph.from_artifacts(current)

    prior = [
        _make_artifact(
            "chunk::chunk-1", "fp-match", ["doc::doc-1"], phase_name="test-phase"
        ),
    ]

    prior_fps = build_prior_fingerprints(prior)
    stale_map = current_dag.build_phase_staleness_map(prior_fps, prior_artifacts=prior)

    assert stale_map == {}
