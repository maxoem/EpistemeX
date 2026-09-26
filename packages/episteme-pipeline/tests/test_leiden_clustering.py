import pytest
pytest.importorskip("graspologic")

from tests.conftest import InMemoryGraphStore
from episteme_pipeline.contracts.domain import L2Entity, L2Triple
from episteme_pipeline.phases.phase5_fusion.leiden_clustering import LeidenTheoryClustering


@pytest.mark.asyncio
async def test_leiden_clustering_fuses_graph_into_communities():
    # Setup graph store with some entities and relations
    store = InMemoryGraphStore()
    
    entities = [
        L2Entity(id="e1", label="CONCEPT", name="Concept 1"),
        L2Entity(id="e2", label="CONCEPT", name="Concept 2"),
        L2Entity(id="e3", label="CONCEPT", name="Concept 3"),
    ]
    for e in entities:
        await store.upsert_entity(e)
        
    triples = [
        L2Triple(subject_id="e1", predicate="RELATED_TO", object_id="e2", confidence=1.0, scope="global", source_chunk_id="global"),
        L2Triple(subject_id="e2", predicate="RELATED_TO", object_id="e3", confidence=1.0, scope="global", source_chunk_id="global"),
    ]
    for t in triples:
        await store.upsert_triple(t)
        
    clustering = LeidenTheoryClustering(max_cluster_size=10)
    await clustering.fuse(store)
    
    # Verify that relations now include IN_COMMUNITY links
    in_comm_relations = [r for r in store._relations if r[1] == "IN_COMMUNITY"]
    assert len(in_comm_relations) > 0
    # Check that community nodes got linked
    for from_id, rel_type, to_id, props in in_comm_relations:
        assert from_id in {"e1", "e2", "e3"}
        assert to_id.startswith("community_")
        assert "level" in props
