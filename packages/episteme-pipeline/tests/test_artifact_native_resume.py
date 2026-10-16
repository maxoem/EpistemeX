from pathlib import Path

import pytest
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    Phase1ArtifactsView,
    Phase2ArtifactsView,
    Phase3ArtifactsView,
    Phase4ArtifactsView,
)
from tests.helpers.artifact_mappers import (
    map_phase1_output_to_artifacts,
    map_phase2_output_to_artifacts,
    map_phase3_output_to_artifacts,
    map_phase4_output_to_artifacts,
)
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.domain import TheoryAtom
from episteme_pipeline.contracts.phase_contracts import (
    L1Chunk,
    L1Document,
    L2Entity,
    L2Triple,
    Phase1Output,
    Phase2Output,
    Phase3Output,
    Phase4Output,
)
from episteme_pipeline.pipeline import Pipeline


class StubPhase:
    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self, input, context):
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_hydrate_previous_collection_builds_phase1_view(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation"),
            StubPhase("Phase 2: Entity & Local Relation Discovery"),
        ],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
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
        run_id="run-old",
    ):
        await artifact_store.write_artifact(artifact)

    pipeline._artifact_store = artifact_store
    collection = await pipeline._hydrate_previous_collection(2, source_run_id="run-old")

    assert collection is not None
    view = Phase1ArtifactsView.from_collection(collection)
    assert view.documents[0].id == "doc-1"
    assert view.chunks[0].id == "chunk-1"


@pytest.mark.asyncio
async def test_hydrate_previous_collection_builds_phase2_view(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation"),
            StubPhase("Phase 2: Entity & Local Relation Discovery"),
            StubPhase("Phase 3: Global Relation Extraction"),
        ],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
    for artifact in map_phase2_output_to_artifacts(
        Phase2Output(
            entities=[L2Entity(id="e1", label="PERSON", name="Kant", source_chunk_ids=["chunk-1"])],
            local_triples=[],
        ),
        run_id="run-old",
    ):
        await artifact_store.write_artifact(artifact)

    pipeline._artifact_store = artifact_store
    collection = await pipeline._hydrate_previous_collection(3, source_run_id="run-old")

    assert collection is not None
    view = Phase2ArtifactsView.from_collection(collection)
    assert view.entities[0].id == "e1"


@pytest.mark.asyncio
async def test_hydrate_previous_collection_builds_phase3_view(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation"),
            StubPhase("Phase 2: Entity & Local Relation Discovery"),
            StubPhase("Phase 3: Global Relation Extraction"),
            StubPhase("Phase 4: Argument Mining"),
        ],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
    for artifact in map_phase3_output_to_artifacts(
        Phase3Output(
            global_triples=[
                L2Triple(
                    subject_id="e1",
                    predicate="IMPLIZIERT",
                    object_id="e2",
                    confidence=0.9,
                    scope="global",
                    source_chunk_id="chunk-1",
                )
            ]
        ),
        run_id="run-old",
    ):
        await artifact_store.write_artifact(artifact)

    pipeline._artifact_store = artifact_store
    collection = await pipeline._hydrate_previous_collection(4, source_run_id="run-old")

    assert collection is not None
    view = Phase3ArtifactsView.from_collection(collection)
    assert len(view.global_triples) == 1


@pytest.mark.asyncio
async def test_hydrate_previous_collection_builds_phase4_view(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[
            StubPhase("Phase 1: Data Foundation"),
            StubPhase("Phase 2: Entity & Local Relation Discovery"),
            StubPhase("Phase 3: Global Relation Extraction"),
            StubPhase("Phase 4: Argument Mining"),
            StubPhase("Phase 5b: Argument Clustering & Theory Fusion"),
        ],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
    for artifact in map_phase4_output_to_artifacts(
        Phase4Output(
            theory_atoms=[
                TheoryAtom(
                    id="ac1",
                    text="Claim",
                    component_type="ANTECEDENT",
                    source_chunk_id="chunk-1",
                )
            ],
            argument_relations=[],
            qbaf=None,
        ),
        run_id="run-old",
    ):
        await artifact_store.write_artifact(artifact)

    pipeline._artifact_store = artifact_store
    collection = await pipeline._hydrate_previous_collection(5, source_run_id="run-old")

    assert collection is not None
    view = Phase4ArtifactsView.from_collection(collection)
    assert len(view.theory_atoms) == 1