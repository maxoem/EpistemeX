# [0016] Phase 3 Within-Phase Checkpointing, Atomic Batch Recovery, and Poison-Pill Quarantine

Status: Accepted (2026-09-12)

## Context

Global relation extraction (Phase 3) extracts cross-chunk relations across the global entity inventory discovered in Phase 2. For scientific literature corpora containing hundreds or thousands of entities, candidate pairing generates $\mathcal{O}(N^2)$ candidate pairs. Processing these pairs involves dense vector retrieval or cross-encoder reranking (e.g., via `DenseRetrievalGlobalRelationExtractor` or `TAGGlobalRelationExtractor`) followed by structured LLM extraction. Consequently, Phase 3 is one of the most computationally demanding and time-consuming stages of the Episteme pipeline.

Prior to this decision, the Episteme pipeline only possessed phase-level granularity for checkpointing and resumption. If a pipeline run was interrupted during Phase 3 (e.g., due to spot instance preemption, timeout, Out-Of-Memory termination, network disconnection, or an unhandled LLM API error):
1. **Zero Intra-Phase Durability:** The phase extracted relations over a single monolithic `asyncio.gather` sweep across all candidate entity pairs and deferred writing triples to the graph store until the entire sweep completed. Interrupted runs lost 100% of completed work.
2. **The "Poison Pill" Crash Loop:** If a specific entity pair triggered an unhandled exception (e.g., token context overflow, malformed token sequence, or model-side 500 error), the runner crashed prior to any state persistence. Upon pipeline restart, deterministic candidate pairing fed the identical failing pair back into the extractor, triggering an infinite crash loop.
3. **Inconsistent Graph States (Phantom Resumes):** Naive multi-step checkpointing (committing triples and item status in separate transactions) introduced phantom resume risks where items could be marked completed without durable triples, or orphan triples could exist without checkpoint provenance.
4. **Combinatorial Memory Explosion:** Storing processed candidate pair sets in Python memory would scale quadratically $\mathcal{O}(N^2)$, risking driver OOM on large philosophy monographs.
5. **State Desynchronization Across Pipeline Resets:** Re-running the pipeline from Phase 1 or 2 due to upstream document or entity edits left stale Phase 3 checkpoints in the graph store, corrupting incremental runs.

## Decision

We implement within-phase item-level checkpointing, atomic batch commit, dead-letter poison-pill quarantine, and content-sensitive candidate pairing in Phase 3.

### 1. Order-Invariant, Content-Sensitive Pair Identity

Candidate pair identities must be invariant to tuple ordering and sensitive to changes in entity content:
$$K(a, b) = \min(\text{id}_a, \text{id}_b) \mathbin{\Vert} \max(\text{id}_a, \text{id}_b) \mathbin{\Vert} \mathcal{H}(\text{envelope}_a) \mathbin{\Vert} \mathcal{H}(\text{envelope}_b)$$

Where $\mathcal{H}$ denotes a stable 16-character SHA-256 fingerprint of the entity's textual envelope.

* **Symmetry:** $K(a, b) = K(b, a)$ prevents directional duplicate evaluations.
* **Content Sensitivity:** If an entity's textual envelope changes across runs due to upstream re-extraction, the pair key changes, automatically invalidating stale evaluations without requiring manual cache busting.
* **Run Independence:** The key deliberately excludes ephemeral `run_id` strings, enabling run $R_2$ to resume seamlessly from partial progress left by interrupted run $R_1$.

### 2. Lineage-Scoped Candidate Delta Checking & `FileSystemCheckpointStore`

Rather than loading millions of processed pair keys into driver memory, candidate pairs are evaluated in configurable batches (`Phase3Config.batch_size`, default 50). Checkpoints are scoped by `(phase_key, lineage_fingerprint)` where `lineage_fingerprint` is the deterministic hash of upstream phase output fingerprints plus the current phase's config and method fingerprints.

By default, `Pipeline.for_task()` wires `FileSystemCheckpointStore` (an append-only JSONL Write-Ahead Log under `<artifacts_dir>/_checkpoints/` implementing `PhaseCheckpointStore`, including `get_committed_triples(phase)` for crash-resume recovery) so the entire pipeline executes and recovers 100% offline without requiring Neo4j. When a Neo4j `PhaseCheckpointStore` is explicitly supplied, unprocessed items are filtered within the graph store via an indexed Cypher query:

```cypher
UNWIND $items AS item
MATCH (p:PhaseItem {phase: $phase, key: item.key, status: 'completed'})
RETURN item.key AS key
```

A schema constraint enforces index-backed uniqueness and $\mathcal{O}(1)$ lookup performance:
```cypher
CREATE CONSTRAINT phase_item_phase_key IF NOT EXISTS
FOR (p:PhaseItem) REQUIRE (p.phase, p.key) IS UNIQUE
```

### 3. Single-Transaction Atomic Batch Commit

To prevent phantom completions or orphan relation triples, batch writes are fused into a single Cypher write transaction:
* Extracted `L2Triple` instances are merged into the graph.
* `PhaseItemRecord` status markers (`status: "completed" | "failed"`) are merged into `:PhaseItem` nodes.

```cypher
UNWIND $triples AS t
MERGE (s:L2Entity {id: t.subject_id})
MERGE (o:L2Entity {id: t.object_id})
MERGE (s)-[r:GLOBAL_RELATION {predicate: t.predicate, run_id: $run_id}]->(o)
SET r.confidence = t.confidence, r.weight = t.weight
WITH 1 AS _
UNWIND $items AS item
MERGE (p:PhaseItem {phase: $phase, key: item.key})
SET p.status = item.status,
    p.error_message = item.error_message,
    p.run_id = $run_id,
    p.updated_at = timestamp()
```

### 4. Dead-Letter Poison-Pill Quarantine & Systematic Failure Guard

The extractor interface (`GlobalRelationExtractor.extract_pairs`) wraps individual pair extractions in localized exception guards:
* **Quarantine:** If an unhandled exception occurs on a specific candidate pair, the error is caught and recorded as `PhaseItemRecord(key=pair.key, status="failed", error_message=str(exc))`.
* **Dead-Letter State:** The failed status is committed to Neo4j. Subsequent pipeline runs filter out the failed key, preventing poison-pill crash loops.
* **Systematic Failure Guard:** To prevent silently burning API budget or continuing execution when a global failure occurs (e.g., invalid LLM API key, revoked credentials, or network partition), `Phase3Runner` validates the first processed batch:
$$\text{if } B_0 \neq \emptyset \land \frac{|\{item \in B_0 \mid item.status = \text{"failed"}\}|}{|B_0|} = 1.0 \implies \text{Abort}$$
  If 100% of pairs in the initial batch fail, execution immediately terminates with a descriptive `RuntimeError`.

### 5. Automated Checkpoint Invalidation Hook

When the pipeline is invoked with a restart or invalidation starting at or before Phase 3 (e.g., via `pipeline.run_from_phase(k)` with $k \le 3$ or when upstream phases produce new artifacts), the pipeline orchestrator automatically invokes:
```python
await graph_store.clear_phase_checkpoints(phase_name="Phase 3: Global Relation Extraction")
```
This drops all `:PhaseItem {phase: ...}` records for Phase 3, ensuring clean reproducibility without graph corruption.

### 6. Decoupled Extractor Protocol

The `GlobalRelationExtractor` protocol is refined to decouple candidate pair generation from extraction:
* `candidate_pairs(entities, structural_anchor=None)` generates candidate sequences deterministically.
* `extract_pair(pair)` processes an individual pair.
* `extract_pairs(pairs, concurrency=N)` orchestrates bounded parallel execution via `asyncio.Semaphore` with built-in per-pair error quarantine.

## Alternatives Considered

1. **In-Memory Hash Set Checkpointing:** Storing completed pair keys in a Python `set` in the runner. Rejected because it cannot survive process termination or restart, failing the primary objective of intra-phase durability.
2. **Two-Phase Commit (Separate Triples and Checkpoint Writes):** Upserting relation triples first and then saving checkpoint markers in a separate transaction. Rejected because a network failure or process crash between the two operations leaves orphan triples without corresponding checkpoint records, causing duplicated extraction on resume.
3. **Run-Scoped Pair Keys (`run_id::pair_key`):** Incorporating the pipeline `run_id` into the candidate pair key. Rejected because it prevents a subsequent run ($R_2$) from resuming progress made by an aborted run ($R_1$).
4. **Unconditional Failure Swallowing:** Marking failing pairs as failed without a threshold guard. Rejected because a fatal infrastructure failure (e.g., expired API token) would silently consume all candidate pairs, mark them all failed, and complete Phase 3 with an empty graph.

## Consequences

* **Resilience:** Pipeline interruptions during Phase 3 can be resumed immediately, skipping previously processed candidate pairs with zero duplicate LLM calls.
* **Determinism & Stability:** Deterministic entity sorting and order-invariant pair keys guarantee reproducible candidate generation across worker restarts.
* **Observability:** Failed pairs are inspectable in Neo4j via `MATCH (p:PhaseItem {status: 'failed'}) RETURN p`, complete with timestamp and stack trace / error message.
* **Performance:** Cypher-level batch streaming ensures memory consumption in the runner remains strictly $\mathcal{O}(B)$ where $B$ is the batch size, regardless of corpus size.
