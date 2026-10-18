# Testing Observability

## Testing Goals

- Assert that components emit the right domain events
- Verify observers transform events as expected
- Keep Langfuse optional in tests

## Testing Patterns

- Replace SimpleEventEmitter with a capture observer that appends events for assertions.
- For JSONL, write to a tmp path and read back a few lines.
- For Langfuse, run under run_observability_context when env is present; otherwise assert that code still completes.
- Unit‑test acceptance rates from MetricsObserver using a small set of synthetic events.

## Example Verification Checks

- DenseCandidatesGenerated count matches candidate list length
- RerankerScoreAssigned sets accepted based on threshold
- TripleCommitted includes correct subject/object based on direction
