from pathlib import Path

import pytest
from episteme_pipeline.artifacts.builders import (
    build_chunk_artifact,
    build_document_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
)
from tests.helpers.artifact_mappers import (
    map_phase3_output_to_artifacts,
    map_phase4_output_to_artifacts,
)
from episteme_pipeline.artifacts.store import JsonArtifactStore
from episteme_pipeline.config import PipelineConfig
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    L1Document,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.contracts.phase_contracts import (
    L2Triple,
    Phase3Output,
    Phase4Output,
    PipelineInput,
)
from episteme_pipeline.pipeline import Pipeline
from episteme_pipeline.runs.models import (
    ExecutionResult,
    RunManifest,
    RunPhaseRecord,
    RunStatus,
)


def test_phase3_mapper_emits_global_relation_artifacts() -> None:
    output = Phase3Output(
        global_triples=[
            L2Triple(
                subject_id="e1",
                predicate="IMPLIZIERT",
                object_id="e2",
                confidence=0.9,
                scope="global",
                source_chunk_id="chunk-1",
            )
        ],
    )

    artifacts = map_phase3_output_to_artifacts(output, run_id="run-1")

    assert len(artifacts) == 1
    assert artifacts[0].kind.value == "global_relation"


def test_phase4_mapper_emits_argument_artifacts() -> None:
    output = Phase4Output(
        theory_atoms=[
            TheoryAtom(
                id="ac1",
                text="Claim text",
                component_type="ANTECEDENT",
                source_chunk_id="chunk-1",
            )
        ],
        argument_relations=[
            TheoryRelation(
                source_id="ac1",
                target_id="ac2",
                relation_type="SUPPORTS",
                confidence=0.8,
                scope="local",
            )
        ],
        qbaf=None,
    )

    artifacts = map_phase4_output_to_artifacts(output, run_id="run-1")

    assert len(artifacts) == 2
    assert {artifact.kind.value for artifact in artifacts} == {
        "theory_atom",
        "theory_relation",
    }


class StubPhase1:
    name = "Phase 1: Data Foundation"
    phase_key = "phase1"

    async def run(self, input, context: ArtifactExecutionContext) -> ArtifactCollection:
        return ArtifactCollection([])


class StubPhase2:
    name = "Phase 2: Entity & Local Relation Discovery"
    phase_key = "phase2"

    async def run(self, input, context: ArtifactExecutionContext) -> ArtifactCollection:
        return ArtifactCollection([])


class StubPhase3:
    name = "Phase 3: Global Relation Extraction"
    phase_key = "phase3"

    async def run(self, input, context: ArtifactExecutionContext) -> ArtifactCollection:
        return ArtifactCollection([])


@pytest.mark.asyncio
async def test_run_from_phase_persists_resume_manifest(tmp_path: Path, graph_store):
    config = PipelineConfig()
    config.execution.persist_run_manifests = True
    config.execution.persist_phase3_artifacts = True
    config.execution.persist_phase4_artifacts = True
    config.execution.runs_dir = str(tmp_path / "runs")
    config.execution.artifacts_dir = str(tmp_path / "artifacts")

    pipeline = Pipeline(
        phases=[StubPhase1(), StubPhase2(), StubPhase3()],
        config=config,
        graph_reader=graph_store,
        projection_graph=graph_store,
        checkpoint_store=graph_store,
    )

    prior = RunManifest(
        run_id="run-old",
        status=RunStatus.COMPLETED,
        phase_records=[
            RunPhaseRecord(
                phase_name="Phase 1: Data Foundation",
                ordinal=1,
                status=RunStatus.COMPLETED,
            )
        ],
    )
    pipeline._manifest_store.write_manifest(prior)

    artifact_store = JsonArtifactStore(tmp_path / "artifacts")
    document = L1Document(
        id="doc-1",
        title="Doc",
        source_path="docs/doc.md",
        chapter_count=1,
        chunk_count=1,
    )
    chunk = L1Chunk(
        id="chunk-1",
        text="Hello",
        source_doc_id="doc-1",
        chapter_id="chap-1",
        sequence_index=0,
        token_count=1,
    )
    await artifact_store.write_artifact(
        build_document_artifact(
            document,
            run_id="run-old",
            phase_name="Phase 1: Data Foundation",
            method="test.phase1",
        )
    )
    await artifact_store.write_artifact(
        build_chunk_artifact(
            chunk,
            run_id="run-old",
            phase_name="Phase 1: Data Foundation",
            method="test.phase1",
        )
    )
    pipeline._artifact_store = artifact_store

    result = await pipeline.run_from_phase(
        2, PipelineInput(source_paths=["docs/doc.md"])
    )

    assert isinstance(result, ExecutionResult)
    manifest_files = list((tmp_path / "runs").glob("*.json"))
    assert len(manifest_files) == 2
