# Integration Tests for Empty Pipeline Completion

This directory contains integration tests that verify the pipeline behavior when completing with empty results, specifically addressing the `FileNotFoundError` issue.

## The Original Problem

The issue occurred when:
1. Pipeline ran successfully but found no entities (0 candidates, 0 triples)
2. The run tried to write a manifest to `.pipeline_runs/run-{uuid}.json`  
3. A `FileNotFoundError` was thrown because the directory wasn't created properly

Logs showed:
```
INFO:tag_extractor:Phase 3: 25 entities → 0 candidate pairs
INFO:tag_extractor:Phase 3: extracted 0 global triples (confidence ≥ 0.70)
INFO:instance_fusion:Phase 5a: 25 entities → 0 candidate alias pairs
INFO:instance_fusion:Phase 5a: 0 entity merges committed.
FileNotFoundError: [Errno 2] No such file or directory: '.pipeline_runs/run-f12281a0-1267-43fd-8dfa-4c23d9e35789.json'
```

## Tests Included

### `test_empty_pipeline_completion.py`
- Verifies that the exact `FileNotFoundError` scenario no longer occurs
- Tests that manifests can be written even with completely empty results
- Confirms directory creation works properly

### `test_networkx_empty_scenario.py` 
- Tests with actual NetworkX graphs (as requested)
- Covers scenarios with:
  - Completely empty graphs (0 nodes, 0 edges)
  - Partial graphs (nodes but 0 edges)
  - Multiple rapid writes to test reliability

## Key Verification Points

☼ **Directory Creation**: `.pipeline_runs/` directory is created automatically  
☼ **Empty Results Handling**: Works with 0 artifacts/entities found  
☼ **Manifest Persistence**: Files are written and can be read back correctly  
☼ **No FileNotFoundError**: The original error no longer occurs  
☼ **NetworkX Compatibility**: Works with empty/partial NetworkX graphs  

## Running Tests

```bash
# Run all integration tests
uv run pytest tests/integration/ -v

# Run specific test file
uv run pytest tests/integration/test_empty_pipeline_completion.py -v

# Run with output
uv run pytest tests/integration/ -v -s
```

## Resolution

The tests confirm that `JsonRunManifestStore` correctly handles:
1. Automatic directory creation with `mkdir(parents=True, exist_ok=True)`
2. Writing manifests even when artifact collections are empty
3. Reading back manifests with preserved metadata
4. Multiple concurrent writes without race conditions

The `FileNotFoundError` issue has been resolved.
