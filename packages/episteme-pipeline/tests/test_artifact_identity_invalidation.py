from episteme_pipeline.artifacts.models import (
    ArtifactEnvelope,
    ArtifactKind,
    ArtifactProvenance,
    ChunkArtifact,
)
from episteme_pipeline.runs.fingerprints import stable_fingerprint


def test_artifact_identity_keys_group_same_family() -> None:
    artifacts = [
        ArtifactEnvelope(
            artifact_id="artifact::chunk-1",
            identity_key="chunk::chunk-1",
            kind=ArtifactKind.CHUNK,
            run_id="run-a",
            phase_name="Phase 1: Data Foundation",
            method="phase1.foundation",
            dependency_fingerprint="dep-a",
            provenance=ArtifactProvenance(),
            payload=ChunkArtifact(
                chunk_id="chunk-1",
                document_id="doc-1",
                text="hello",
                sequence_index=0,
                token_count=1,
            ),
        ),
        ArtifactEnvelope(
            artifact_id="artifact::chunk-1",
            identity_key="chunk::chunk-1",
            kind=ArtifactKind.CHUNK,
            run_id="run-b",
            phase_name="Phase 1: Data Foundation",
            method="phase1.foundation",
            dependency_fingerprint="dep-b",
            provenance=ArtifactProvenance(),
            payload=ChunkArtifact(
                chunk_id="chunk-1",
                document_id="doc-1",
                text="hello",
                sequence_index=0,
                token_count=1,
            ),
        ),
    ]

    grouped: dict[str, list[ArtifactEnvelope]] = {}
    for artifact in artifacts:
        grouped.setdefault(artifact.identity_key, []).append(artifact)

    assert len(grouped) == 1
    assert len(grouped["chunk::chunk-1"]) == 2
    assert len({artifact.dependency_fingerprint for artifact in grouped["chunk::chunk-1"]}) == 2


def test_dependency_fingerprint_detects_artifact_family_change() -> None:
    before = stable_fingerprint({"identity_key": "chunk::chunk-1", "dependency_fingerprint": "dep-a"})
    after = stable_fingerprint({"identity_key": "chunk::chunk-1", "dependency_fingerprint": "dep-b"})

    assert before != after
