"""
Phase 3 — Global Relation Extraction

Strategy: TAG + Reranker (no GNN training required)

Steps:
  1. Document-Level Context Pooling via Text-Attributed Graph (TAG)
     - Chunks as nodes; NEXT/CONTAINS edges; embeddings as node attributes
     - For each entity pair candidate, retrieve a local subgraph envelope
       via shared-chunk structural blocking (avoids O(N²) LLM calls)
  2. Complex Triple Decoding (Global Overlap)
     - LLM decodes the final triple with structured output given the
       merged subgraph envelope as context
  3. Noise Filtering (confidence < threshold → discard)
     - Unknown relation types (not in schema) → discarded

GlobalRelationExtractor is ALSO reused by Phase 4 ARC. Pass an instance
via the constructor to share it across phases; Pipeline.from_config() does
this automatically.

See: docs/workflow/3_relation_extraction/1_relation_extraction.puml
     docs/feature/phase_3/step_details.md
"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import batched

from episteme_pipeline.artifacts.builders import build_global_relation_artifact
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase2ArtifactsView,
)
from episteme_pipeline.config import Phase3Config
from episteme_pipeline.contracts.domain import CandidatePair, L2Triple, PhaseItemRecord

from episteme_pipeline.phases.phase3_global_relations.tag_extractor import (
    TAGRelationExtractor,
)
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor
from episteme_pipeline.protocols.graph_store import (
    EntityGraph,
    GraphReader,
    GraphWriter,
    PhaseCheckpointStore,
    ProcessingGraph,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)

from episteme_pipeline.runtime.batch_executor import (
    CheckpointedBatchExecutor,
    SystematicBatchFailureError,
)

_PHASE_TAG = "phase3"


class SystematicPairFailure(SystematicBatchFailureError):
    """Raised when every candidate pair in the initial batch fails identically."""


class Phase3Runner(PhaseRunner[Phase2ArtifactsView]):
    name = "Phase 3: Global Relation Extraction"
    phase_key = "phase3"
    input_view = Phase2ArtifactsView

    def __init__(
        self,
        config: Phase3Config,
        schema: SchemaConfig,
        *,
        llm,
        embedding_model,
        graph_store: ProcessingGraph | EntityGraph | PhaseCheckpointStore | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
    ) -> None:
        self.config = config
        self.schema = schema
        self.llm = llm
        self.embedding_model = embedding_model
        self.graph_store = graph_store
        # Allow injection (shared with Phase 4 ARC) or default to TAG extractor
        self.global_extractor: GlobalRelationExtractor = (
            global_extractor or TAGRelationExtractor(llm, embedding_model, config)
        )

    @property
    def checkpoint_store(self) -> PhaseCheckpointStore | None:
        """Return the graph store if it satisfies PhaseCheckpointStore.

        Returns
        -------
        PhaseCheckpointStore or None
            Checkpoint store instance, or None if not supported.
        """
        if isinstance(self.graph_store, PhaseCheckpointStore):
            return self.graph_store
        return None

    @staticmethod
    def _guard_systematic_failure(
        batch: list[CandidatePair],
        item_records: list[PhaseItemRecord],
        succeeded_total: int,
    ) -> None:
        """Abort Phase 3 if all candidate pairs of the initial batch failed.

        Parameters
        ----------
        batch : list[CandidatePair]
            Candidate pairs evaluated in the batch.
        item_records : list[PhaseItemRecord]
            Checkpoint item records produced by the extractor.
        succeeded_total : int
            Cumulative number of successfully processed pairs prior to this batch.

        Raises
        ------
        SystematicPairFailure
            If every pair in the first evaluated batch failed.
        """
        failed_records = [r for r in item_records if r.status == "failed"]
        if succeeded_total == 0 and len(failed_records) == len(batch) and len(batch) > 0:
            sample_error = failed_records[0].error or "Unknown error"
            raise SystematicPairFailure(
                f"All {len(batch)} candidate pairs of the first batch failed in Phase 3. "
                f"Halting execution: {sample_error}"
            )

    async def run(
        self, input: Phase2ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Execute Phase 3 global relation extraction with resilient checkpointing.

        Parameters
        ----------
        input : Phase2ArtifactsView
            View containing entity and chunk artifacts from Phase 2 / 3b / 4-maturation.
        context : ArtifactExecutionContext
            Pipeline execution context.

        Returns
        -------
        ArtifactCollection
            Generated GlobalRelationArtifact instances.
        """
        effective_phase = (
            f"{_PHASE_TAG}:{context.lineage_fingerprint}"
            if context and context.lineage_fingerprint
            else _PHASE_TAG
        )

        if (
            isinstance(self.graph_store, GraphReader)
            and not (context and context.lineage_fingerprint)
        ):
            entities = await self.graph_store.get_entities()
            if not entities:
                entities = list(input.entities)
        else:
            entities = list(input.entities)

        if len(entities) < 2:
            logger.info("Phase 3: fewer than 2 entities — skipping global extraction.")
            return ArtifactCollection([])

        # Sort entities deterministically to guarantee order-invariant pairing across runs
        entities = sorted(entities, key=lambda e: e.id)

        candidates = await self.global_extractor.candidate_pairs(entities)
        if not candidates:
            logger.info("Phase 3: 0 candidate pairs generated — skipping extraction.")
            return ArtifactCollection([])

        reader: GraphReader = (
            input.to_graph_reader()
            if (
                not isinstance(self.graph_store, GraphReader)
                or (context and context.lineage_fingerprint)
            )
            else self.graph_store
        )

        batch_size = self.config.batch_size
        progress_task = f"Phase 3: {len(candidates)} global candidate pairs"
        checkpoint_store = self.checkpoint_store
        prior_triples: list[L2Triple] = (
            list(await checkpoint_store.get_committed_triples(effective_phase))
            if checkpoint_store is not None
            else []
        )
        all_triples: list[L2Triple] = list(prior_triples)
        succeeded_total = len(prior_triples)

        with self.progress_scope(
            progress_task,
            total_items=len(candidates),
            description="Global Relations",
        ) as advance:
            async def _custom_commit(
                phase: str,
                batch_triples: list[L2Triple],
                batch_records: list[PhaseItemRecord],
            ) -> None:
                if checkpoint_store is not None:
                    await checkpoint_store.commit_phase_batch(
                        phase, batch_triples, batch_records
                    )
                elif isinstance(self.graph_store, GraphWriter) and batch_triples:
                    for triple_chunk in batched(batch_triples, 20):
                        await self.graph_store.upsert_triples(list(triple_chunk))

            executor = CheckpointedBatchExecutor[CandidatePair, L2Triple](
                checkpoint_store=checkpoint_store,
                phase_tag=effective_phase,
                batch_size=batch_size,
                item_key_fn=lambda c: c.key,
                process_batch_fn=lambda batch: self.global_extractor.extract_pairs(
                    batch, reader, self.schema
                ),
                custom_commit_fn=_custom_commit,
                guard_systematic_failure=True,
            )
            try:
                result = await executor.execute(candidates, on_batch_advance=advance)
                all_triples.extend(result.outputs)
            except SystematicBatchFailureError as exc:
                msg = str(exc).replace("items", "candidate pairs")
                raise SystematicPairFailure(msg) from exc

        deduped_triples: list[L2Triple] = []
        seen_triple_keys: set[tuple[str, str, str, str | None]] = set()
        for t in all_triples:
            t_key = (t.subject_id, t.predicate, t.object_id, t.source_chunk_id)
            if t_key not in seen_triple_keys:
                seen_triple_keys.add(t_key)
                deduped_triples.append(t)

        relation_dist: dict[str, int] = defaultdict(int)
        for t in deduped_triples:
            relation_dist[t.predicate] += 1

        artifacts = []
        for triple in deduped_triples:
            artifacts.append(
                build_global_relation_artifact(
                    triple,
                    relation_dist,
                    run_id=context.run_id,
                    phase_name=self.name,
                    method="phase3.global_relations",
                )
            )
        return ArtifactCollection(artifacts)
