import pytest

from episteme_pipeline.config import PipelineConfig, ExecutionConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput
from episteme_pipeline.pipeline import Pipeline
from tests.conftest import InMemoryGraphStore
from tests.test_full_pipeline_integration import (
    FullStubPhase1,
    FullStubPhase2,
    FullStubPhase3,
    FullStubPhase5a,
)


class TrackingGraphStore(InMemoryGraphStore):
    """An in-memory graph store that tracks all write calls."""

    def __init__(self) -> None:
        super().__init__()
        self.write_calls: list[tuple] = []

    async def upsert_node(self, label: str, node_id: str, properties: dict) -> None:
        self.write_calls.append(("upsert_node", label, node_id))
        await super().upsert_node(label, node_id, properties)

    async def upsert_relation(self, from_id, relation_type, to_id, properties=None) -> None:
        self.write_calls.append(("upsert_relation", from_id, relation_type, to_id))
        await super().upsert_relation(from_id, relation_type, to_id, properties)

    async def upsert_chunk(self, chunk) -> None:
        self.write_calls.append(("upsert_chunk", chunk.id))
        await super().upsert_chunk(chunk)

    async def upsert_entity(self, entity) -> None:
        self.write_calls.append(("upsert_entity", entity.id))
        await super().upsert_entity(entity)

    async def upsert_triple(self, triple) -> None:
        self.write_calls.append(("upsert_triple", triple.subject_id, triple.predicate, triple.object_id))
        await super().upsert_triple(triple)

    async def upsert_theory_atom(self, component) -> None:
        self.write_calls.append(("upsert_theory_atom", component.id))
        await super().upsert_theory_atom(component)


@pytest.mark.asyncio
async def test_project_artifacts_to_graph_false():
    """Verify that when project_artifacts_to_graph is False, no writes are made to the passed graph stores."""
    config = PipelineConfig(
        execution=ExecutionConfig(
            project_artifacts_to_graph=False,
            persist_run_manifests=False,  # Keep it in-memory
        )
    )

    real_graph_store = TrackingGraphStore()

    # Create the pipeline with real graph store instances
    pipeline = Pipeline(
        phases=[
            FullStubPhase1(),
            FullStubPhase2(),
            FullStubPhase5a(),
            FullStubPhase3(),
        ],
        config=config,
        graph_reader=real_graph_store,
        projection_graph=real_graph_store,
        checkpoint_store=real_graph_store,
    )

    # Run the pipeline
    await pipeline.run(PipelineInput(source_paths=["docs/test.md"]))

    # Verify that NO write calls were made to the passed real_graph_store
    assert len(real_graph_store.write_calls) == 0


@pytest.mark.asyncio
async def test_project_artifacts_to_graph_true():
    """Verify that when project_artifacts_to_graph is True, the projector runs and projects to the graph stores."""
    config = PipelineConfig(
        execution=ExecutionConfig(
            project_artifacts_to_graph=True,
            persist_run_manifests=False,  # Keep it in-memory
        )
    )

    real_graph_store = TrackingGraphStore()

    # Create the pipeline with real graph store instances
    pipeline = Pipeline(
        phases=[
            FullStubPhase1(),
            FullStubPhase2(),
            FullStubPhase5a(),
            FullStubPhase3(),
        ],
        config=config,
        graph_reader=real_graph_store,
        projection_graph=real_graph_store,
        checkpoint_store=real_graph_store,
    )

    # Run the pipeline
    await pipeline.run(PipelineInput(source_paths=["docs/test.md"]))

    # Verify that write calls were made to the passed real_graph_store
    assert len(real_graph_store.write_calls) > 0

    # Let's verify we have chunk and document upserts
    chunk_upserts = [c for c in real_graph_store.write_calls if c[0] == "upsert_chunk"]
    assert len(chunk_upserts) > 0
