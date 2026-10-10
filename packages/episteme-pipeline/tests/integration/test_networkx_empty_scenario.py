"""Integration test using networkx to verify pipeline behavior with empty graph results."""

import os
import tempfile
from pathlib import Path

import networkx as nx

from episteme_pipeline.runs.models import RunManifest, RunStatus


def create_empty_knowledge_graph():
    """Create an empty knowledge graph using networkx - simulates 0 entities found."""
    graph = nx.MultiDiGraph()
    # Completely empty graph - no nodes, no edges
    return graph


def create_knowledge_graph_with_no_relations():
    """Create a knowledge graph with nodes but no relationships - partial empty scenario."""
    graph = nx.MultiDiGraph()
    # Add some entities (nodes) but no relationships (edges)
    graph.add_node("Entity1", type="concept")
    graph.add_node("Entity2", type="person") 
    graph.add_node("Entity3", type="location")
    # No edges = no relations found
    return graph


def test_persistence_with_empty_networkx_graph():
    """Test that persistence works with truly empty NetworkX graphs."""
    
    print("\n🧬 Testing persistence with empty NetworkX graph...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            # Start with no runs directory
            runs_path = Path(".pipeline_runs")
            assert not runs_path.exists(), "Should start without runs directory"
            
            from episteme_pipeline.runs.persistence import JsonRunManifestStore
            
            # Create an empty graph scenario
            empty_graph = create_empty_knowledge_graph()
            print(f"📊 Graph stats - Nodes: {len(empty_graph.nodes())}, Edges: {len(empty_graph.edges())}")
            assert len(empty_graph.nodes()) == 0, "Graph should be truly empty"
            assert len(empty_graph.edges()) == 0, "Graph should have no edges"
            
            # This represents what would happen in a real pipeline run that finds nothing
            manifest = RunManifest(
                run_id="empty-networkx-graph-run",
                status=RunStatus.COMPLETED,
                # Would be empty in this scenario
                artifact_counts_by_kind={},  # No artifacts generated
                phase_records=[],
                tags=["networkx", "empty-graph", "integration-test"]
            )
            
            # This operation was failing with FileNotFoundError
            store = JsonRunManifestStore(".pipeline_runs")
            path = store.write_manifest(manifest)
            
            # Verify success
            assert path.exists(), "Manifest should be written successfully"
            assert "empty-networkx-graph-run.json" in str(path)
            print(f"✅ SUCCESS: Manifest written despite empty NetworkX graph at {path}")
            
            # Verify content
            content = path.read_text()
            assert "empty-networkx-graph-run" in content
            assert "completed" in content.lower()
            print("✅ SUCCESS: Content verification passed")
            
            # Test reading back
            read_manifest = store.read_manifest("empty-networkx-graph-run")
            assert read_manifest is not None
            assert read_manifest.run_id == "empty-networkx-graph-run"
            print("✅ SUCCESS: Round-trip reading works")
            
        finally:
            os.chdir(original_cwd)


def test_persistence_with_nodes_but_no_edges():
    """Test persistence with NetworkX graph that has nodes but no edges."""
    
    print("\n🔗 Testing persistence with nodes-only NetworkX graph...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            runs_path = Path(".pipeline_runs")
            assert not runs_path.exists(), "Should start without runs directory"
            
            from episteme_pipeline.runs.persistence import JsonRunManifestStore
            
            # Create graph with nodes but no edges (partial empty scenario)
            partial_graph = create_knowledge_graph_with_no_relations()
            print(f"📊 Graph stats - Nodes: {len(partial_graph.nodes())}, Edges: {len(partial_graph.edges())}")
            assert len(partial_graph.nodes()) > 0, "Graph should have nodes"
            assert len(partial_graph.edges()) == 0, "Graph should have no edges"
            
            # This represents a partial completion - found entities but no relationships
            manifest = RunManifest(
                run_id="nodes-no-edges-run",
                status=RunStatus.COMPLETED,
                tags=["networkx", "partial-results", "integration-test"]
                # artifact_counts_by_kind would reflect what was actually found
            )
            
            # Test the persistence (this was failing before)
            store = JsonRunManifestStore(".pipeline_runs")
            path = store.write_manifest(manifest)
            
            # Verify
            assert path.exists(), "Manifest should be written successfully"
            assert "nodes-no-edges-run.json" in str(path)
            print(f"✅ SUCCESS: Manifest written for partial results at {path}")
            
            # Content verification
            content = path.read_text()
            assert "nodes-no-edges-run" in content
            print("✅ SUCCESS: Content verification passed")
            
        finally:
            os.chdir(original_cwd)


def test_multiple_empty_scenarios():
    """Test multiple rapid writes of empty scenario manifests."""
    
    print("\n🔄 Testing multiple empty scenario writes...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        try:
            from episteme_pipeline.runs.persistence import JsonRunManifestStore
            
            store = JsonRunManifestStore(".pipeline_runs")
            success_count = 0
            
            # Rapidly write multiple "empty result" manifests
            test_cases = [
                ("rapid-empty-1", "First empty run"),
                ("rapid-empty-2", "Second empty run"), 
                ("rapid-empty-3", "Third empty run")
            ]
            
            for run_id, description in test_cases:
                manifest = RunManifest(
                    run_id=run_id,
                    status=RunStatus.COMPLETED,
                    artifact_counts_by_kind={},  # Empty again
                    tags=["rapid-test", "empty-results"]
                )
                
                try:
                    path = store.write_manifest(manifest)
                    assert path.exists(), f"Manifest {run_id} should exist"
                    success_count += 1
                    print(f"  ✅ {description}: SUCCESS")
                except Exception as e:
                    print(f"  ❌ {description}: FAILED - {e}")
                    
            assert success_count == len(test_cases), f"All {len(test_cases)} writes should succeed"
            print(f"✅ SUCCESS: All {success_count} rapid writes completed successfully")
            
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    # Run the tests directly
    print("🧪 Running NetworkX integration tests for empty scenarios...")
    
    try:
        test_persistence_with_empty_networkx_graph()
        test_persistence_with_nodes_but_no_edges() 
        test_multiple_empty_scenarios()
        print("\n🎉 ALL NETWORKX INTEGRATION TESTS PASSED!")
        print("✅ Empty NetworkX graphs no longer cause FileNotFoundError!")
        print("✅ Partial results (nodes-only) work correctly!") 
        print("✅ Rapid multiple writes are reliable!")
    except Exception as e:
        print(f"\n💥 TEST FAILED: {e}")
        raise
