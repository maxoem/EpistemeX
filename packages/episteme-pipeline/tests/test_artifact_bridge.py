from pathlib import Path

from tests.helpers.artifact_mappers import (
    map_phase1_output_to_artifacts,
    map_phase2_output_to_artifacts,
)
from episteme_pipeline.artifacts.store import InMemoryArtifactStore, JsonArtifactStore
from episteme_pipeline.contracts.phase_contracts import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    Phase1Output,
    Phase2Output,
)
from episteme_pipeline.runs.models import RunManifest
from episteme_pipeline.runs.persistence import JsonRunManifestStore


def test_phase1_mapper_emits_document_and_chunk_artifacts() -> None:
    output = Phase1Output(
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
                text="Hello world",
                source_doc_id="doc-1",
                chapter_id="chap-1",
                sequence_index=0,
                token_count=2,
            )
        ],
    )

    artifacts = map_phase1_output_to_artifacts(output, run_id="run-1")

    assert len(artifacts) == 2
    assert {artifact.kind.value for artifact in artifacts} == {"document", "chunk"}


def test_phase2_mapper_emits_mentions_entities_and_relations() -> None:
    output = Phase2Output(
        entities=[
            L2Entity(
                id="entity-1",
                label="PERSON",
                name="Kant",
                source_chunk_ids=["chunk-1"],
            )
        ],
        local_triples=[
            L2Triple(
                subject_id="entity-1",
                predicate="INFLUENCES",
                object_id="entity-2",
                confidence=0.9,
                scope="local",
                source_chunk_id="chunk-1",
            )
        ],
    )

    artifacts = map_phase2_output_to_artifacts(output, run_id="run-1")

    assert len(artifacts) == 3
    assert {artifact.kind.value for artifact in artifacts} == {
        "entity_mention",
        "linked_entity",
        "local_relation",
    }


async def test_in_memory_artifact_store_round_trip() -> None:
    artifact = map_phase1_output_to_artifacts(
        Phase1Output(
            documents=[
                L1Document(
                    id="doc-1",
                    title="Doc",
                    source_path="docs/doc.md",
                    chapter_count=1,
                    chunk_count=0,
                )
            ],
            chunks=[],
        ),
        run_id="run-1",
    )[0]
    store = InMemoryArtifactStore()

    await store.write_artifact(artifact)
    loaded = await store.get_artifact(artifact.artifact_id)

    assert loaded is not None
    assert loaded.artifact_id == artifact.artifact_id


async def test_json_artifact_store_round_trip(tmp_path: Path) -> None:
    artifact = map_phase1_output_to_artifacts(
        Phase1Output(
            documents=[],
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
    )[0]
    store = JsonArtifactStore(tmp_path / "artifacts")

    await store.write_artifact(artifact)
    loaded = await store.get_artifact(artifact.artifact_id)

    assert loaded is not None
    assert loaded.run_id == "run-1"


def test_json_run_manifest_store_round_trip(tmp_path: Path) -> None:
    manifest = RunManifest(run_id="run-1", input_sources=["docs/doc.md"])
    store = JsonRunManifestStore(tmp_path / "runs")

    path = store.write_manifest(manifest)
    loaded = store.read_manifest("run-1")

    assert path.exists()
    assert loaded is not None
    assert loaded.run_id == "run-1"
