# Resuming Runs

Guide to continuing interrupted pipeline executions and reusing previous results.

## Run Resumption Basics

The pipeline supports resuming execution from previous runs, avoiding redundant computation.

### When Resumption Helps

Resumption is beneficial when:

1. **Pipeline Interruptions**: Execution stopped due to errors, timeouts, or system issues
2. **Incremental Updates**: Adding new documents to an existing graph
3. **Configuration Changes**: Modifying settings for specific phases
4. **Resource Management**: Pausing long-running processes

### How Resumption Works

The pipeline automatically detects:

- Which phases completed successfully in previous runs
- Whether artifacts remain valid for reuse
- Where execution should resume

## Identifying Previous Runs

Locate runs available for resumption:

```python
# List recent runs
from pipeline.runs.persistence import JsonRunManifestStore

manifest_store = JsonRunManifestStore("./.pipeline_runs")
recent_runs = manifest_store.list_recent_manifests(limit=10)

for manifest in recent_runs:
    print(f"Run ID: {manifest.run_id}")
    print(f"Started: {manifest.started_at}")
    print(f"Status: {manifest.status}")
    print("---")
```

## Resuming Execution

Continue from a previous run using the same pipeline instance:

```python
# Resume from last completed phase
result = await pipeline.resume_from_run(
    run_id="run-abc123",
    input=PipelineInput(source_paths=["document.tex"])
)

# Resume from a specific phase
result = await pipeline.resume_from_run(
    run_id="run-abc123",
    input=PipelineInput(source_paths=["document.tex"]),
    from_phase=3  # Start from Phase 3
)
```

## Artifact Reuse

The system automatically reuses valid artifacts from previous runs.

### Reuse Conditions

Artifacts are reused when:

- Input fingerprints match exactly
- Configuration parameters are unchanged
- No invalidated dependencies exist
- Artifact files remain accessible

### Monitoring Reuse

Track which artifacts are being reused:

```python
# The resume operation returns information about reuse decisions
result = await pipeline.resume_from_run(run_id, input)

print("Reused phases:", result.manifest.reused_phase_ordinals)
print("Invalidated phases:", result.manifest.invalidated_phase_ordinals)
print("Parent run:", result.manifest.parent_run_id)
```

## Configuration Changes and Invalidation

Understand how configuration changes affect resumption.

### Compatible Changes

These modifications typically allow artifact reuse:

- Adding new input documents (extends rather than modifies)
- Adjusting confidence thresholds for subsequent filtering
- Changing output formatting options
- Updating non-functional configuration

### Invalidating Changes

These modifications require recomputation:

- Changing LLM models or prompts
- Modifying chunking strategies
- Altering entity extraction parameters
- Updating relationship extraction logic
- Changing graph schema definitions

### Smart Invalidation

The system uses fingerprinting to detect changes:

```python
# Configuration changes automatically invalidate affected phases
# based on content-addressed fingerprints
cfg_v1 = PipelineConfig(phase2=Phase2Config(ner_confidence_threshold=0.8))
cfg_v2 = PipelineConfig(phase2=Phase2Config(ner_confidence_threshold=0.9))

# Different fingerprints trigger invalidation
print(stable_fingerprint(cfg_v1) != stable_fingerprint(cfg_v2))  # True
```

## Incremental Processing & Corpus Evolution

Add new documents to existing runs efficiently without re-processing the entire corpus.

### Extending Input Sets ($\mathcal{G}_t + \Delta D \to \mathcal{G}_{t+1}$)

When new literature is added to an existing project:

```python
from episteme_pipeline.config import PipelineConfig, ExecutionConfig
from episteme_pipeline.contracts.phase_contracts import PipelineInput

# Original run processed documents A and B
original_input = PipelineInput(source_paths=["docA.pdf", "docB.pdf"])
res_1 = await pipeline.run(original_input)

# New run adds document C while automatically reusing A and B results
extended_input = PipelineInput(
    source_paths=["docA.pdf", "docB.pdf", "docC.pdf"],
    curation_ledger_path="curation_ledger.json"  # Optional HITL constraints
)

res_2 = await pipeline.run(
    extended_input,
    parent_run_id=res_1.run_id
)
```

### How Incremental Processing Operates

The orchestrator inspects `RunManifest.document_fingerprints`:

1. **Phase 1 Ingestion**: Documents A and B match prior hashes; their `DocumentArtifact` and `ChunkArtifact` envelopes are hydrated directly. Only `docC.pdf` is parsed and chunked.
2. **Phase 2 Entity Discovery**: Surviving entities, mention envelopes, and local relation triples are retained. NER runs strictly over chunks from `docC.pdf`.
3. **Phase 3 Global Relations**: Candidate entity pairs between two unmodified entities are skipped (their prior `GlobalRelationArtifact` triples are hydrated). Only pairs involving newly discovered entities are extracted.
4. **Phase 4 Argument Mining**: Local argument components (`TheoryAtom`) and relations from A and B chunks are hydrated. Only `docC.pdf` chunks are mined.
5. **Curation Ledger Overrides**: Any expert corrections in `curation_ledger.json` (`SUPPORTS`, `ATTACKS`, `REJECTED`, or modality priors) are enforced across the resulting graphs.

Execution settings are controlled via `ExecutionConfig`:

```python
cfg = PipelineConfig(
    execution=ExecutionConfig(
        allow_phase_reuse=True,
        allow_artifact_hydration=True,
    )
)
```

## Advanced Resumption Patterns

Handle complex resumption scenarios.

### Selective Phase Re-execution

Force re-execution of specific phases:

```python
# Even if artifacts exist, force Phase 3 re-execution
result = await pipeline.run_from_phase(
    phase_number=3,
    input=original_input
)
```

### Hybrid Approaches

Combine manual and automatic resumption:

```python
# Manually process Phase 1 with new settings
phase1_result = await phase1_runner.run(custom_input)

# Resume automatic processing from Phase 2
# using manually generated Phase 1 artifacts
result = await pipeline.resume_from_run(
    run_id="manual-phase1-run",
    input=original_input,
    from_phase=2
)
```

## Troubleshooting Resumption

Address common resumption issues.

### Missing Artifacts

Handle cases where expected artifacts are unavailable:

```python
# System gracefully falls back to re-execution when artifacts are missing
# Check logs for "artifact_missing" events
```

### Fingerprint Mismatches

Diagnose configuration inconsistency issues:

```bash
# Look for fingerprint mismatch warnings in logs
# These indicate why artifacts weren't reused
```

### Dependency Invalidation

Understand cascading invalidation effects:

```python
# If Phase 2 artifacts are invalidated,
# subsequent phases (3, 4, 5) typically also invalidate
# unless specifically configured otherwise
```

## Performance Considerations

Optimize resumption for efficiency.

### Cache Management

Control artifact caching behavior:

```python
cfg = PipelineConfig(
    execution=ExecutionConfig(
        artifact_cache_size=2000,    # Increase cache size
        cache_eviction_policy="lru"  # Least Recently Used eviction
    )
)
```

### Parallel Resumption

Resume multiple independent runs simultaneously:

```python
async def resume_independent_run(run_id, input_data):
    return await pipeline.resume_from_run(run_id, input_data)

# Process multiple runs concurrently
results = await asyncio.gather(*[
    resume_independent_run(run_id, input_data) 
    for run_id in compatible_runs
])
```

## Best Practices

Follow recommended patterns for reliable resumption.

### Run Identification

Use descriptive run identifiers:

```python
# Include meaningful context in run IDs
run_id = f"philosophy-corpus-{datetime.now().strftime('%Y%m%d')}-v1"
```

### State Management

Keep runs organized and manageable:

```python
# Clean up old runs periodically
manifest_store.prune_old_manifests(retention_days=30)
```

### Validation

Verify resumption success:

```python
# Confirm expected reuse occurred
assert len(result.manifest.reused_phase_ordinals) > 0

# Check result integrity
assert result.manifest.status == "completed"
```

## Monitoring and Logging

Track resumption behavior effectively.

### Resumption Events

Monitor key resumption activities:

```python
@emitter.on("run.resumed")
def on_run_resumed(event):
    print(f"Resumed run {event['run_id']} from phase {event['from_phase']}")

@emitter.on("artifact.reused")
def on_artifact_reused(event):
    print(f"Reused artifact: {event['artifact_id']}")
```

### Performance Metrics

Measure resumption efficiency:

```python
# Compare execution time with and without resumption
# Track percentage of work avoided through reuse
reuse_ratio = len(reused_artifacts) / len(total_artifacts)
```

## Next Steps

- Explore [Advanced Configuration](customize_config.md)
- Learn about [Output Inspection](inspect_outputs.md)
- Understand [Evaluation Methods](../research/evaluation_methodology.md)
