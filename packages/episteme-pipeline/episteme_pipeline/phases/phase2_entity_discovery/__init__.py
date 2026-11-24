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

import logging
from typing import Any

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
from episteme_pipeline.artifacts.models import (
    ArtifactKind,
)
from episteme_pipeline.artifacts.subgraph_reader import ArtifactSubgraphReader
from episteme_pipeline.config import Phase2Config
from episteme_pipeline.contracts.domain import (
    GlobalStructuralAnchor,
    L1Chunk,
    L2Entity,
    L2Triple,
)
from episteme_pipeline.contracts.phase_contracts import EpistemicCurationLedger
from episteme_pipeline.events.models import UnlinkableMentionError
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
from episteme_pipeline.protocols.graph_store import (
    GraphReader,
    GraphWriter,
    NoOpCheckpointStore,
    PhaseCheckpointStore,
    ProcessingGraph,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runtime.batch_executor import (
    CallableOutputCodec,
    CheckpointedStreamExecutor,
    SystematicBatchFailureError,
)
from episteme_pipeline.schema.default_schema import (
    SchemaConfig,
    StructuralRelationType,
)

logger = logging.getLogger(__name__)

_PHASE_TAG = "phase2"

type _ChunkDiscoveryStepOutput = tuple[
    list[tuple[L2Entity, str | None]],
    list[L2Triple],
    str,
]


def _extract_stream_key(chunk: L1Chunk) -> tuple[str, str]:
    """Derive the ``(source_doc_id, chapter_id)`` sequential stream key for a chunk."""
    meta = chunk.metadata if isinstance(chunk.metadata, dict) else {}
    chapter = chunk.chapter_id or meta.get("chapter") or meta.get("section_path") or ""
    return (chunk.source_doc_id, str(chapter))


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
    reads_kinds = frozenset({ArtifactKind.DOCUMENT, ArtifactKind.CHUNK})
    writes_kinds = frozenset(
        {
            ArtifactKind.ENTITY_MENTION,
            ArtifactKind.LINKED_ENTITY,
            ArtifactKind.LOCAL_RELATION,
        }
    )
    conformal_tasks = frozenset(
        {"phase2_entity_discovery", "p2_linking", "phase2_linking"}
    )

    def __init__(
        self,
        config: Phase2Config,
        schema: SchemaConfig,
        *,
        llm: Any,
        embedding_model: EmbeddingModel | None = None,
        graph_store: ProcessingGraph | PhaseCheckpointStore | None = None,
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
        graph_store : ProcessingGraph | PhaseCheckpointStore | None, optional
            Optional checkpoint or processing graph store.
        ner_extractor : NERExtractor or None, optional
            Custom NERExtractor. Defaults to LLMNERExtractor if None.
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

        self.working_memory_manager = (
            working_memory_manager or EpisodicWorkingMemoryManager()
        )
        self._stream_memory_managers: dict[
            tuple[str, str], EpisodicWorkingMemoryManager
        ] = {}
        self._checkpoint_store: PhaseCheckpointStore = (
            graph_store
            if isinstance(graph_store, PhaseCheckpointStore)
            else NoOpCheckpointStore()
        )

    @property
    def checkpoint_store(self) -> PhaseCheckpointStore:
        """Return the active checkpoint store for within-phase stream checkpointing."""
        return self._checkpoint_store

    def _get_stream_memory_manager(
        self,
        stream_key: tuple[str, str],
        anchor: GlobalStructuralAnchor | None = None,
    ) -> EpisodicWorkingMemoryManager:
        """Retrieve or fork an episodic working memory manager scoped to ``stream_key``."""
        if stream_key not in self._stream_memory_managers:
            self._stream_memory_managers[stream_key] = self.working_memory_manager.fork(
                anchor=anchor
            )
        return self._stream_memory_managers[stream_key]

    async def run(
        self, input: Phase1ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        """Execute Phase 2 entity extraction and local relation discovery.

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
        self._stream_memory_managers.clear()
        anchor = (
            context.pipeline_input.structural_anchor
            if context and context.pipeline_input
            else None
        )
        curation_ledger = (
            context.pipeline_input.resolved_curation_ledger()
            if context and context.pipeline_input
            else None
        )
        effective_phase = (
            f"{_PHASE_TAG}:{context.lineage_fingerprint}"
            if context and context.lineage_fingerprint
            else _PHASE_TAG
        )

        chunks = await select_pending_chunks(
            self.graph_store, effective_phase, input.chunks
        )

        reader = input.to_graph_reader()
        if isinstance(self.graph_store, GraphReader) and not (
            context and context.lineage_fingerprint
        ):
            for existing_entity in await self.graph_store.get_entities():
                reader.register_entity(existing_entity)

        all_entities: list[L2Entity] = []
        all_triples: list[L2Triple] = []
        mention_envelopes: dict[tuple[str, str], str] = {}
        checkpoint_store = self.checkpoint_store

        if isinstance(context, ArtifactExecutionContext):
            hydration = context.hydrator(self.phase_key, self.name).hydrate_phase2(
                chunks
            )
            chunks = hydration.delta_chunks
            all_entities.extend(hydration.entities)
            all_triples.extend(hydration.triples)
            mention_envelopes.update(hydration.mention_envelopes)
            for ent in hydration.entities:
                reader.register_entity(ent)

        chunk_codec = CallableOutputCodec[_ChunkDiscoveryStepOutput](
            serializer=lambda out: {
                "chunk_id": out[2],
                "entities": [
                    {"entity": entity.model_dump(mode="json"), "envelope": env}
                    for entity, env in out[0]
                ],
                "triples": [t.model_dump(mode="json") for t in out[1]],
            },
            deserializer=lambda raw: (
                [
                    (L2Entity.model_validate(item["entity"]), item.get("envelope"))
                    for item in raw.get("entities", [])
                ],
                [L2Triple.model_validate(t) for t in raw.get("triples", [])],
                str(raw.get("chunk_id", "")),
            ),
        )

        def _register_recovered_outputs(
            recovered: list[_ChunkDiscoveryStepOutput],
        ) -> None:
            for resolved_entities, triples, chunk_id in recovered:
                for ent, env in resolved_entities:
                    all_entities.append(ent)
                    reader.register_entity(ent)
                    if env:
                        mention_envelopes[(ent.id, chunk_id)] = env
                all_triples.extend(triples)

        async def _process_chunk_step(
            chunk: L1Chunk, memory_mgr: EpisodicWorkingMemoryManager
        ) -> _ChunkDiscoveryStepOutput:
            (
                resolved_entities,
                triples,
                chunk_id,
                memory_update,
                boundary_detected,
                transitional_summary,
            ) = await self._process_chunk(
                chunk,
                anchor=anchor,
                reader=reader,
                phase_tag=effective_phase,
                memory_mgr=memory_mgr,
                curation_ledger=curation_ledger,
            )
            memory_mgr.process_step(
                chunk=chunk,
                state_delta=memory_update,
                semantic_boundary_detected=boundary_detected,
                transitional_summary=transitional_summary,
            )
            return resolved_entities, triples, chunk_id

        async def _persist_chunk_step(
            _chunk: L1Chunk, output: _ChunkDiscoveryStepOutput
        ) -> None:
            resolved_entities, triples, chunk_id = output
            entities_to_upsert: list[L2Entity] = []
            relations_to_upsert: list[dict[str, Any]] = []

            for entity, env in resolved_entities:
                entities_to_upsert.append(entity)
                all_entities.append(entity)
                reader.register_entity(entity)
                if env:
                    mention_envelopes[(entity.id, chunk_id)] = env
                relations_to_upsert.append(
                    {
                        "from_id": entity.id,
                        "relation_type": StructuralRelationType.EXTRACTED_FROM.value,
                        "to_id": chunk_id,
                        "properties": {"confidence": 1.0, "textual_envelope": env},
                    }
                )

            all_triples.extend(triples)

            if isinstance(self.graph_store, GraphWriter):
                if entities_to_upsert:
                    await self.graph_store.upsert_entities(entities_to_upsert)
                if relations_to_upsert:
                    await self.graph_store.upsert_relations(relations_to_upsert)
                if triples:
                    await self.graph_store.upsert_triples(list(triples))

            if self.graph_store is not None:
                await self.graph_store.mark_chunks_processed(
                    [chunk_id], effective_phase
                )

        progress_task = f"Phase 2: {len(chunks)} chunks"
        with self.progress_scope(
            progress_task, total_items=len(chunks), description="Entity Discovery"
        ) as advance:
            executor = CheckpointedStreamExecutor[
                tuple[str, str],
                L1Chunk,
                EpisodicWorkingMemoryManager,
                _ChunkDiscoveryStepOutput,
            ](
                checkpoint_store=checkpoint_store,
                phase_tag=effective_phase,
                item_key_fn=lambda c: c.id,
                stream_key_fn=_extract_stream_key,
                sort_key_fn=lambda c: c.sequence_index,
                init_state_fn=lambda k: self._get_stream_memory_manager(
                    k, anchor=anchor
                ),
                restore_state_fn=lambda mgr, snap: mgr.restore_state(snap),
                snapshot_state_fn=lambda mgr: mgr.snapshot_state(),
                process_item_fn=_process_chunk_step,
                persist_item_fn=_persist_chunk_step,
                output_codec=chunk_codec,
                max_concurrent_streams=self.config.max_concurrent_chapters,
                first_batch_size=self.config.batch_size,
                guard_systematic_failure=True,
            )
            try:
                await executor.execute(
                    chunks,
                    all_items=input.chunks,
                    on_item_advance=advance,
                    on_recovered=_register_recovered_outputs,
                )
            except SystematicBatchFailureError as exc:
                raise SystematicChunkFailure(
                    str(exc).replace("items", "chunks")
                ) from exc

        if not chunks and not all_entities and not all_triples:
            return ArtifactCollection([])

        deduped_entities, deduped_triples, rewritten_envelopes = (
            self._deduplicate_entities(
                all_entities,
                curation_ledger=curation_ledger,
                triples=all_triples,
                mention_envelopes=mention_envelopes,
            )
        )
        return self._build_artifacts(
            deduped_entities,
            deduped_triples,
            rewritten_envelopes,
            context.run_id,
        )

    @staticmethod
    def _deduplicate_entities(
        entities: list[L2Entity],
        curation_ledger: EpistemicCurationLedger | None = None,
        *,
        triples: list[L2Triple] | None = None,
        mention_envelopes: dict[tuple[str, str], str] | None = None,
    ) -> tuple[list[L2Entity], list[L2Triple], dict[tuple[str, str], str]]:
        """Deduplicate entities by ID and must-link constraints and rewrite incident state.

        Parameters
        ----------
        entities : list of L2Entity
            Discovered or hydrated entities across processed chunks.
        curation_ledger : EpistemicCurationLedger or None, optional
            Optional HITL curation ledger enforcing must-link entity merges.
        triples : list of L2Triple or None, optional
            Local relation triples whose endpoints are remapped on merge.
        mention_envelopes : dict of tuple of (str, str) to str or None, optional
            Mention textual envelopes keyed by ``(entity_id, chunk_id)``.

        Returns
        -------
        tuple of (list of L2Entity, list of L2Triple, dict of tuple of (str, str) to str)
            Deduplicated entities, endpoint-remapped triples, and remapped mention envelopes.
        """
        merged: dict[str, L2Entity] = {}
        merged_members: dict[str, list[tuple[str, str]]] = {}
        id_remap: dict[str, str] = {}
        for entity in entities:
            target_id = id_remap.get(entity.id, entity.id)
            if target_id not in merged and curation_ledger is not None:
                for existing_id, members in merged_members.items():
                    if any(
                        curation_ledger.is_must_link(
                            entity.id, m_id, entity.name, m_name
                        )
                        for m_id, m_name in members
                    ):
                        target_id = existing_id
                        break

            if target_id != entity.id:
                id_remap[entity.id] = target_id

            if target_id not in merged:
                merged[target_id] = entity.model_copy(
                    update={
                        "id": target_id,
                        "source_chunk_ids": list(
                            dict.fromkeys(entity.source_chunk_ids)
                        ),
                    }
                )
                merged_members[target_id] = [(entity.id, entity.name)]
            else:
                existing = merged[target_id]
                merged_members[target_id].append((entity.id, entity.name))
                combined_chunks = list(
                    dict.fromkeys(existing.source_chunk_ids + entity.source_chunk_ids)
                )
                conf_candidates = [
                    c for c in (existing.confidence, entity.confidence) if c is not None
                ]
                merged[target_id] = existing.model_copy(
                    update={
                        "source_chunk_ids": combined_chunks,
                        "description": existing.description or entity.description,
                        "textual_envelope": existing.textual_envelope
                        or entity.textual_envelope,
                        "confidence": (
                            max(conf_candidates) if conf_candidates else None
                        ),
                    }
                )

        rewritten_envelopes: dict[tuple[str, str], str] = {}
        if mention_envelopes:
            for (ent_id, chunk_id), env_text in mention_envelopes.items():
                canon_id = id_remap.get(ent_id, ent_id)
                key = (canon_id, chunk_id)
                if key not in rewritten_envelopes or (
                    not rewritten_envelopes[key] and env_text
                ):
                    rewritten_envelopes[key] = env_text

        rewritten_triples: list[L2Triple] = []
        if triples:
            deduped_triples: dict[tuple[str, str, str, str, str | None], L2Triple] = {}
            for triple in triples:
                new_subj = id_remap.get(triple.subject_id, triple.subject_id)
                new_obj = id_remap.get(triple.object_id, triple.object_id)
                if triple.subject_id != triple.object_id and new_subj == new_obj:
                    continue
                updated = (
                    triple.model_copy(
                        update={"subject_id": new_subj, "object_id": new_obj}
                    )
                    if (new_subj != triple.subject_id or new_obj != triple.object_id)
                    else triple
                )
                t_key = (
                    updated.subject_id,
                    updated.predicate,
                    updated.object_id,
                    updated.scope,
                    updated.source_chunk_id if updated.scope == "local" else None,
                )
                existing_t = deduped_triples.get(t_key)
                if existing_t is None or updated.confidence > existing_t.confidence:
                    deduped_triples[t_key] = updated
            rewritten_triples = list(deduped_triples.values())

        return list(merged.values()), rewritten_triples, rewritten_envelopes

    def _build_artifacts(
        self,
        deduped_entities: list[L2Entity],
        all_triples: list[L2Triple],
        mention_envelopes: dict[tuple[str, str], str],
        run_id: str,
    ) -> ArtifactCollection:
        """Construct Phase 2 mention, linked entity, and local relation artifacts."""
        artifacts = []
        for entity in deduped_entities:
            mention_artifact_ids = []
            for chunk_id in entity.source_chunk_ids:
                mention_id = f"mention::{entity.id}::{chunk_id}"
                mention_artifact_ids.append(f"artifact::{mention_id}")
                env_text = mention_envelopes.get(
                    (entity.id, chunk_id), entity.textual_envelope
                )
                mention_entity = (
                    entity.model_copy(update={"textual_envelope": env_text})
                    if env_text != entity.textual_envelope
                    else entity
                )
                artifacts.append(
                    build_entity_mention_artifact(
                        mention_entity,
                        chunk_id,
                        run_id=run_id,
                        phase_name=self.name,
                        method="phase2.entity_discovery",
                    )
                )
            artifacts.append(
                build_linked_entity_artifact(
                    entity,
                    mention_artifact_ids,
                    run_id=run_id,
                    phase_name=self.name,
                    method="phase2.entity_discovery",
                )
            )
        for triple in all_triples:
            artifacts.append(
                build_local_relation_artifact(
                    triple,
                    run_id=run_id,
                    phase_name=self.name,
                    method="phase2.entity_discovery",
                )
            )
        return ArtifactCollection(artifacts)

    async def _process_chunk(
        self,
        chunk: L1Chunk,
        anchor: GlobalStructuralAnchor | None = None,
        reader: GraphReader | None = None,
        phase_tag: str = _PHASE_TAG,
        memory_mgr: EpisodicWorkingMemoryManager | None = None,
        curation_ledger: EpistemicCurationLedger | None = None,
    ) -> tuple[
        list[tuple[L2Entity, str | None]],
        list[L2Triple],
        str,
        dict[str, Any] | None,
        bool,
        str | None,
    ]:
        mgr = (
            memory_mgr
            if memory_mgr is not None
            else self._get_stream_memory_manager(
                _extract_stream_key(chunk), anchor=anchor
            )
        )
        effective_anchor = anchor or mgr.get_effective_anchor(chunk)
        (
            entities,
            triples,
            memory_update,
            boundary_detected,
            transitional_summary,
        ) = await self.ner_extractor.extract(
            chunk_id=chunk.id,
            chunk_text=chunk.text,
            schema=self.schema,
            memory=mgr.state,
            anchor=effective_anchor,
        )

        # Apply confidence threshold filtering if configured
        if self.config.ner_confidence_threshold > 0.0:
            entities = [
                e
                for e in entities
                if e.confidence is None
                or e.confidence >= self.config.ner_confidence_threshold
            ]

        if self.config.local_relation_confidence_threshold > 0.0:
            triples = [
                t
                for t in triples
                if t.confidence >= self.config.local_relation_confidence_threshold
            ]

        if not entities and not triples:
            # Nothing extracted — optionally annotate the chunk for diagnostics
            if isinstance(self.graph_store, GraphWriter):
                try:
                    await self.graph_store.upsert_node(
                        label="Chunk",
                        node_id=chunk.id,
                        properties={f"{phase_tag}_skipped": True},
                    )
                except Exception:  # noqa: BLE001, S110 baseline
                    pass
            return (
                [],
                [],
                chunk.id,
                memory_update,
                boundary_detected,
                transitional_summary,
            )

        # Entity linking: redirect to existing canonical IDs where possible
        resolved_entities: list[tuple[L2Entity, str | None]] = []
        id_redirect: dict[str, str] = {}  # extracted_id -> canonical_id
        link_store: GraphReader = (
            reader
            if reader is not None
            else (
                self.graph_store
                if isinstance(self.graph_store, GraphReader)
                else ArtifactSubgraphReader()
            )
        )

        for entity in entities:
            # Passed explicitly so that an injected linker (which the runner did
            # not construct) still honours the configured values.
            try:
                canonical = None
                if curation_ledger is not None:
                    # Check must-link constraints against existing entities
                    store_entities = (
                        await link_store.get_entities()
                        if isinstance(link_store, GraphReader)
                        else []
                    )
                    for existing in store_entities:
                        if curation_ledger.is_must_link(
                            entity.id, existing.id, entity.name, existing.name
                        ):
                            canonical = existing
                            break

                if canonical is None:
                    canonical = await self.entity_linker.link(
                        entity,
                        link_store,
                        top_k=self.config.top_k_linking_candidates,
                        threshold=self.config.linking_confidence_threshold,
                    )

                # Check cannot-link constraint
                if canonical is not None and curation_ledger is not None:  # noqa: SIM102 baseline
                    if curation_ledger.is_cannot_link(
                        entity.id, canonical.id, entity.name, canonical.name
                    ):
                        logger.info(
                            "Curation ledger cannot-link rejected link between %s and %s",
                            entity.name,
                            canonical.name,
                        )
                        canonical = None

                if canonical is not None and canonical.id != entity.id:
                    id_redirect[entity.id] = canonical.id
                    # Append this chunk as a source of the canonical entity
                    canonical = canonical.model_copy(
                        update={
                            "source_chunk_ids": canonical.source_chunk_ids + [chunk.id]
                        }
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
        resolved_triples: list[L2Triple] = [
            triple.model_copy(
                update={
                    "subject_id": id_redirect.get(triple.subject_id, triple.subject_id),
                    "object_id": id_redirect.get(triple.object_id, triple.object_id),
                }
            )
            for triple in triples
        ]

        return (
            resolved_entities,
            resolved_triples,
            chunk.id,
            memory_update,
            boundary_detected,
            transitional_summary,
        )
