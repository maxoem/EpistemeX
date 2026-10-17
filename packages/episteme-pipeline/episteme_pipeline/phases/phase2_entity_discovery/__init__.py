"""
Phase 2 — Entity & Local Relation Discovery

Steps per chunk (in order):
  1. NERExtractor: LLM structured prediction → ExtractedEntities + local triples
  2. EntityLinker: name-based candidate search → redirect or mint canonical IDs
  3. Graph commit:
     a. Upsert each entity node (MERGE — idempotent)
     b. Upsert each local triple (MERGE)
     c. Upsert EXTRACTED_FROM edge (entity → chunk)
  4. Mark chunk as processed (phase2_processed = true)

Crash resilience:
  - get_unprocessed_chunks() only returns chunks where phase2_processed is not set
  - Re-running Phase 2 after a crash resumes from where it left off
  - NER failures leave the chunk unprocessed → retried on next run

Coreference:
  - Local coreferences (pronouns, aliases within a chunk) are resolved implicitly
    by the LLM extraction prompt — no separate step needed.
  - Cross-chunk alias resolution is handled in Phase 5 Instance-Level Fusion.

See: docs/workflow/2_entity_discovery/1_ner_typing.puml
     docs/workflow/2_entity_discovery/3_entity_linking.puml
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from episteme_pipeline.artifacts.builders import (
    build_entity_mention_artifact,
    build_linked_entity_artifact,
    build_local_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase1ArtifactsView,
)
from episteme_pipeline.config import Phase2Config
from episteme_pipeline.contracts.domain import (
    GlobalStructuralAnchor,
    L1Chunk,
    L2Entity,
    L2Triple,
)

from episteme_pipeline.phases.chunk_selection import select_pending_chunks
from episteme_pipeline.phases.phase2_entity_discovery.entity_linker import (
    NameEntityLinker,
)
from episteme_pipeline.phases.phase2_entity_discovery.jev_entity_linker import (
    CascadingEntityLinker,
    JevEntityLinker,
)
from episteme_pipeline.phases.phase2_entity_discovery.ner_extractor import (
    LLMNERExtractor,
)
from episteme_pipeline.phases.phase2_entity_discovery.sota_entity_linker import (
    DenseEntityLinker,
)
from episteme_pipeline.phases.phase2_entity_discovery.working_memory import (
    EpisodicWorkingMemoryManager,
)
from episteme_pipeline.protocols import DecisionEngine
from episteme_pipeline.protocols.extractors import (
    CrossEncoder,
    EmbeddingModel,
    EntityLinker,
    NERExtractor,
)
from episteme_pipeline.protocols.graph_store import ProcessingGraph
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)

_PHASE_TAG = "phase2"


class SystematicChunkFailure(RuntimeError):
    """Every chunk of the first batch failed the same way.

    Per-chunk exceptions are normally treated as retryable data errors: they are
    logged and the chunk is left unprocessed. That is the right response to a
    malformed chunk, and the wrong response to a misconfigured component — an
    embedding model without the expected interface, an unreachable LLM, missing
    credentials. Those fail identically on *every* chunk, and swallowing them
    lets the run finish with ``status=COMPLETED`` and an empty graph.

    This is raised instead when nothing has succeeded yet and a whole batch
    failed with the same exception type.
    """


class Phase2Runner(PhaseRunner[Phase1ArtifactsView]):
    name = "Phase 2: Entity & Local Relation Discovery"
    phase_key = "phase2"
    input_view = Phase1ArtifactsView

    def __init__(
        self,
        config: Phase2Config,
        schema: SchemaConfig,
        *,
        llm,
        embedding_model: EmbeddingModel | None = None,
        graph_store: ProcessingGraph,
        ner_extractor: NERExtractor | None = None,
        entity_linker: EntityLinker | None = None,
        working_memory_manager: EpisodicWorkingMemoryManager | None = None,
        cross_encoder: CrossEncoder | None = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        """Initialize the Phase 2 runner.

        Parameters
        ----------
        config : Phase2Config
            Configuration settings for Phase 2.
        schema : SchemaConfig
            Graph ontology schema configuration.
        llm : object
            LLM instance used for named entity recognition.
        embedding_model : EmbeddingModel or None, optional
            Embedding model for dense retrieval and entity linking.
        graph_store : ProcessingGraph
            Underlying graph database interface.
        ner_extractor : NERExtractor or None, optional
            Custom NER extractor. Defaults to LLMNERExtractor if None.
        entity_linker : EntityLinker or None, optional
            Custom entity linker. If None, defaults to DenseEntityLinker when
            an embedding_model is provided, or NameEntityLinker otherwise.
        working_memory_manager : EpisodicWorkingMemoryManager or None, optional
            Custom episodic working memory manager.
        cross_encoder : CrossEncoder or None, optional
            Cross encoder for candidate reranking in dense linking.
        decision_engine : DecisionEngine or None, optional
            Optional System 1 decision engine.
        """
        self.config = config
        self.schema = schema
        self.llm = llm
        self.embedding_model = embedding_model
        self.graph_store = graph_store
        self.decision_engine = decision_engine

        self.ner_extractor = ner_extractor or LLMNERExtractor.from_config(
            llm=llm,
            config=config,
            decision_engine=decision_engine,
        )
        self.cross_encoder = cross_encoder
        if entity_linker is not None:
            self.entity_linker = entity_linker
        elif self.embedding_model is not None:
            dense_linker = DenseEntityLinker(
                embedding_model=self.embedding_model,
                cross_encoder=self.cross_encoder,
                tau=config.linking_confidence_threshold,
                top_k=config.top_k_linking_candidates,
            )
            if self.decision_engine is not None:
                fast_linker = JevEntityLinker(
                    decision_engine=self.decision_engine,
                    embedding_model=self.embedding_model,
                    alpha=config.conformal_linking_alpha,
                    top_k=config.top_k_linking_candidates,
                    ooo_threshold=config.jev_ooo_threshold,
                )
                self.entity_linker = CascadingEntityLinker(
                    primary=fast_linker,
                    fallback=dense_linker,
                )
            else:
                self.entity_linker = dense_linker
        else:
            self.entity_linker = NameEntityLinker()

        self.working_memory_manager = working_memory_manager or EpisodicWorkingMemoryManager()
        self._doc_memory_managers: dict[str, EpisodicWorkingMemoryManager] = {}

    def _get_memory_manager(self, doc_id: str) -> EpisodicWorkingMemoryManager:
        """Retrieve or create an episodic working memory manager scoped per document.

        Parameters
        ----------
        doc_id : str
            Source document identifier.

        Returns
        -------
        EpisodicWorkingMemoryManager
            Working memory manager instance scoped to the given document.
        """
        if doc_id not in self._doc_memory_managers:
            if not self._doc_memory_managers:
                self._doc_memory_managers[doc_id] = self.working_memory_manager
            else:
                self._doc_memory_managers[doc_id] = EpisodicWorkingMemoryManager(
                    anchor=self.working_memory_manager.anchor,
                    state_strategy=self.working_memory_manager.state_strategy,
                )
        return self._doc_memory_managers[doc_id]

    async def run(self, input: Phase1ArtifactsView, context: ArtifactExecutionContext) -> ArtifactCollection:
        """
        Execute Phase 2 entity extraction and local relation discovery.

        Parameters
        ----------
        input : Phase1ArtifactsView
            View containing documents and chunks extracted during Phase 1.
        context : ArtifactExecutionContext
            Execution context containing run ID, manifest, and pipeline input.

        Returns
        -------
        ArtifactCollection
            Generated EntityMentionArtifact, LinkedEntityArtifact, and LocalRelationArtifact instances.
        """
        anchor = context.pipeline_input.structural_anchor if context and context.pipeline_input else None

        chunks = await select_pending_chunks(
            self.graph_store, _PHASE_TAG, input.chunks
        )
        if not chunks:
            return ArtifactCollection([])

        # Process chunks sequentially along document order
        chunks = sorted(chunks, key=lambda c: (c.source_doc_id, c.sequence_index))

        all_entities: list[L2Entity] = []
        all_triples: list[L2Triple] = []

        succeeded = 0
        progress_task = f"Phase 2: {len(chunks)} chunks"
        with self.progress_scope(
            progress_task, total_items=len(chunks), description="Entity Discovery"
        ) as advance:
            for i in range(0, len(chunks), self.config.batch_size):
                batch = chunks[i : i + self.config.batch_size]
                batch_entities, batch_triples, failures = await self._process_batch(
                    batch, anchor=anchor
                )
                succeeded += len(batch) - len(failures)
                self._guard_systematic_failure(batch, failures, succeeded)
                all_entities.extend(batch_entities)
                all_triples.extend(batch_triples)
                advance(len(batch))

        # Deduplicate all_entities by entity.id, merging source_chunk_ids across all occurrences
        merged_entities: dict[str, L2Entity] = {}
        for entity in all_entities:
            if entity.id not in merged_entities:
                merged_entities[entity.id] = entity.model_copy(
                    update={"source_chunk_ids": list(dict.fromkeys(entity.source_chunk_ids))}
                )
            else:
                existing = merged_entities[entity.id]
                combined_chunks = list(dict.fromkeys(existing.source_chunk_ids + entity.source_chunk_ids))
                conf_candidates = [c for c in [existing.confidence, entity.confidence] if c is not None]
                merged_entities[entity.id] = existing.model_copy(
                    update={
                        "source_chunk_ids": combined_chunks,
                        "description": existing.description or entity.description,
                        "confidence": max(conf_candidates) if conf_candidates else None,
                    }
                )
        deduped_entities = list(merged_entities.values())

        artifacts = []
        for entity in deduped_entities:
            mention_artifact_ids = []
            for chunk_id in entity.source_chunk_ids:
                mention_id = f"mention::{entity.id}::{chunk_id}"
                mention_artifact_id = f"artifact::{mention_id}"
                mention_artifact_ids.append(mention_artifact_id)
                artifacts.append(build_entity_mention_artifact(entity, chunk_id, run_id=context.run_id, phase_name=self.name, method="phase2.entity_discovery"))
            artifacts.append(build_linked_entity_artifact(entity, mention_artifact_ids, run_id=context.run_id, phase_name=self.name, method="phase2.entity_discovery"))
        for triple in all_triples:
            artifacts.append(build_local_relation_artifact(triple, run_id=context.run_id, phase_name=self.name, method="phase2.entity_discovery"))
        return ArtifactCollection(artifacts)

    @staticmethod
    def _guard_systematic_failure(
        batch: list[L1Chunk], failures: list[Exception], succeeded: int
    ) -> None:
        """Abort the phase when a whole batch fails identically and nothing has worked yet.

        See :class:`SystematicChunkFailure` for the rationale.
        """
        if succeeded or not failures or len(failures) != len(batch):
            return
        failure_types = {type(exc) for exc in failures}
        if len(failure_types) != 1:
            return
        exc = failures[0]
        raise SystematicChunkFailure(
            f"All {len(batch)} chunks of the first batch failed with "
            f"{type(exc).__name__}: {exc}. This is a configuration or interface "
            f"error, not a per-chunk data error — aborting Phase 2 instead of "
            f"completing with an empty graph."
        ) from exc

    async def _process_batch(
        self, chunks: list[L1Chunk], anchor: GlobalStructuralAnchor | None = None
    ) -> tuple[list[L2Entity], list[L2Triple], list[Exception]]:
        """
        Process a batch of L1Chunks concurrently through NER extraction and entity linking.

        Parameters
        ----------
        chunks : list[L1Chunk]
            List of L1Chunk instances to process.
        anchor : GlobalStructuralAnchor | None, optional
            Run-level structural coordinate anchor, by default None.

        Returns
        -------
        tuple[list[L2Entity], list[L2Triple], list[Exception]]
            Discovered entities, local triples, and per-chunk exceptions encountered.
        """
        tasks = [self._process_chunk(chunk, anchor=anchor) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        batch_entities: list[L2Entity] = []
        batch_triples: list[L2Triple] = []
        failures: list[Exception] = []
        
        entities_to_upsert = []
        relations_to_upsert = []
        triples_to_upsert = []
        processed_chunks = []

        for chunk, result in zip(chunks, results):
            if isinstance(result, Exception):
                logger.error(
                    "Chunk %s processing failed (will retry on re-run): %s",
                    chunk.id, result,
                )
                failures.append(result)
                continue
                
            resolved_entities, triples, chunk_id, memory_update, boundary_detected, transitional_summary = result

            memory_mgr = self._get_memory_manager(chunk.source_doc_id)
            memory_mgr.process_step(
                chunk=chunk,
                state_delta=memory_update,
                semantic_boundary_detected=boundary_detected,
                transitional_summary=transitional_summary,
            )
            
            for entity, env in resolved_entities:
                entities_to_upsert.append(entity)
                batch_entities.append(entity)
                relations_to_upsert.append({
                    "from_id": entity.id,
                    "relation_type": "EXTRACTED_FROM",
                    "to_id": chunk_id,
                    "properties": {"confidence": 1.0, "textual_envelope": env}
                })
                
            for triple in triples:
                triples_to_upsert.append(triple)
                batch_triples.append(triple)

            processed_chunks.append(chunk_id)

        from itertools import batched
        if entities_to_upsert:
            for e_batch in batched(entities_to_upsert, 500):
                await self.graph_store.upsert_entities(list(e_batch))
        if relations_to_upsert:
            for r_batch in batched(relations_to_upsert, 500):
                await self.graph_store.upsert_relations(list(r_batch))
        if triples_to_upsert:
            for t_batch in batched(triples_to_upsert, 500):
                await self.graph_store.upsert_triples(list(t_batch))
        if processed_chunks:
            for c_batch in batched(processed_chunks, 500):
                await self.graph_store.mark_chunks_processed(list(c_batch), _PHASE_TAG)

        return batch_entities, batch_triples, failures

    async def _process_chunk(
        self, chunk: L1Chunk, anchor: GlobalStructuralAnchor | None = None
    ) -> tuple[list[tuple[L2Entity, str | None]], list[L2Triple], str, dict[str, Any] | None, bool, str | None]:
        memory_mgr = self._get_memory_manager(chunk.source_doc_id)
        effective_anchor = anchor or memory_mgr.get_effective_anchor(chunk)
        entities, triples, memory_update, boundary_detected, transitional_summary = await self.ner_extractor.extract(
            chunk_id=chunk.id,
            chunk_text=chunk.text,
            schema=self.schema,
            memory=memory_mgr.state,
            anchor=effective_anchor,
        )

        # Apply confidence threshold filtering if configured
        if self.config.ner_confidence_threshold > 0.0:
            entities = [
                e for e in entities
                if e.confidence is None or e.confidence >= self.config.ner_confidence_threshold
            ]

        if self.config.local_relation_confidence_threshold > 0.0:
            triples = [
                t for t in triples
                if t.confidence >= self.config.local_relation_confidence_threshold
            ]

        if not entities and not triples:
            # Nothing extracted — leave chunk UNPROCESSED so it will be retried.
            # Optionally annotate the chunk for easier diagnostics.
            try:
                await self.graph_store.upsert_node(
                    label="Chunk",
                    node_id=chunk.id,
                    properties={f"{_PHASE_TAG}_skipped": True},
                )
            except Exception:
                # Best-effort; lack of this flag must not block execution
                pass
            return [], [], chunk.id, memory_update, boundary_detected, transitional_summary

        # Entity linking: redirect to existing canonical IDs where possible
        resolved_entities: list[tuple[L2Entity, str | None]] = []
        id_redirect: dict[str, str] = {}  # extracted_id -> canonical_id

        from episteme_pipeline.events.models import UnlinkableMentionError

        for entity in entities:
            # Passed explicitly so that an injected linker (which the runner did
            # not construct) still honours the configured values.
            try:
                canonical = await self.entity_linker.link(
                    entity,
                    self.graph_store,
                    top_k=self.config.top_k_linking_candidates,
                    threshold=self.config.linking_confidence_threshold,
                )
                if canonical is not None and canonical.id != entity.id:
                    id_redirect[entity.id] = canonical.id
                    # Append this chunk as a source of the canonical entity
                    canonical = canonical.model_copy(
                        update={"source_chunk_ids": canonical.source_chunk_ids + [chunk.id]}
                    )
                    resolved_entities.append((canonical, entity.textual_envelope))
                else:
                    resolved_entities.append((entity, entity.textual_envelope))
            except UnlinkableMentionError as e:
                # Issue L08 Option E: Mention lacked an envelope or could not be linked.
                # explicitly mint a new graph node.
                logger.info(f"Minting new unlinked entity for {entity.name}: {e}")
                resolved_entities.append((entity, entity.textual_envelope))

        # Apply ID redirects to triples
        resolved_triples: list[L2Triple] = []
        for triple in triples:
            resolved_triples.append(
                triple.model_copy(
                    update={
                        "subject_id": id_redirect.get(triple.subject_id, triple.subject_id),
                        "object_id": id_redirect.get(triple.object_id, triple.object_id),
                    }
                )
            )

        return resolved_entities, resolved_triples, chunk.id, memory_update, boundary_detected, transitional_summary
