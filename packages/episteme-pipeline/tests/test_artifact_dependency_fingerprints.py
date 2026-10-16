from tests.helpers.artifact_mappers import (
    map_phase1_output_to_artifacts,
    map_phase2_output_to_artifacts,
)
from episteme_pipeline.contracts.phase_contracts import (
    L1Chunk,
    L1Document,
    L2Entity,
    Phase1Output,
    Phase2Output,
)


def test_phase1_artifacts_have_dependency_fingerprints() -> None:
    artifacts = map_phase1_output_to_artifacts(
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
        run_id="run-1",
    )

    assert all(artifact.dependency_fingerprint for artifact in artifacts)


def test_phase2_artifacts_have_dependency_fingerprints() -> None:
    artifacts = map_phase2_output_to_artifacts(
        Phase2Output(
            entities=[L2Entity(id="e1", label="PERSON", name="Kant", source_chunk_ids=["chunk-1"])],
            local_triples=[],
        ),
        run_id="run-1",
    )

    assert all(artifact.dependency_fingerprint for artifact in artifacts)
