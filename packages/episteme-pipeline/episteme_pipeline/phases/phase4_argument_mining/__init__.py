"""
Phase 4 — Argument Mining

Steps per chunk (in order):
  1. ADUSegmenter: identify Argumentative Discourse Units, wrap in <ACn> markup
  2. ACCClassifier: classify each ADU (CLAIM/MAJOR_CLAIM/PREMISE) and extract
     local SUPPORTS/ATTACKS relations in a single LLM pass
  3. Graph commit: upsert TheoryAtom nodes + SUPPORTS/ATTACKS + EXTRACTED_FROM edges
  4. Mark chunk as processed (phase4_processed = true)

After all chunks:
  5. ARC: classify cross-chunk SUPPORTS/ATTACKS relations via TAG subgraph envelopes
     (reuses Phase 3 GlobalRelationExtractor — inject to share the same instance)

TheoryNet projection is handled separately by ``TheoryNetProjector`` in the projection layer.

Crash resilience:
  - get_unprocessed_chunks(_PHASE_TAG) resumes from last committed chunk
  - ADU + ACC failures leave the chunk unprocessed → retried on next run
  - ARC is stateless (global MERGE writes are idempotent) → safe to re-run

Note: Global argument clustering / Key Point Analysis happens in Phase 5b.

See: docs/workflow/4_argument_mining/
"""

from __future__ import annotations

import logging

from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
)
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase3ArtifactsView,
)
from episteme_pipeline.config import Phase4Config
from episteme_pipeline.contracts.domain import (
    L1Chunk,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.decision.gleaning import GleaningStoppingOracle, JevGleaningGate
from episteme_pipeline.decision.modal_resolver import HybridModalResolver
from episteme_pipeline.phases.chunk_selection import select_pending_chunks
from episteme_pipeline.phases.phase2_entity_discovery import SystematicChunkFailure
from episteme_pipeline.phases.phase4_argument_mining.acc_classifier import (
    LLMACCClassifier,
)
from episteme_pipeline.phases.phase4_argument_mining.adu_segmenter import (
    LLMADUSegmenter,
)
from episteme_pipeline.phases.phase4_argument_mining.arc_classifier import (
    TAGARCClassifier,
)
from episteme_pipeline.phases.phase4_argument_mining.classifiers import (
    CascadingACCClassifier,
    CascadingARCClassifier,
    JevACCClassifier,
    JevARCClassifier,
)
from episteme_pipeline.protocols.argument_mining import (
    ACCClassifier,
    ADUSegmenter,
    ARCClassifier,
)
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor
from episteme_pipeline.protocols.graph_store import (
    GraphReader,
    GraphWriter,
    PhaseCheckpointStore,
    ProcessingGraph,
)
from episteme_pipeline.protocols.modality import (
    ModalStrengthResolver,
    ensure_modal_strength_resolver,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runtime.batch_executor import (
    CheckpointedBatchExecutor,
    SystematicBatchFailureError,
)
from episteme_pipeline.schema.default_schema import SchemaConfig

logger = logging.getLogger(__name__)


_PHASE_TAG = "phase4"


class Phase4Runner(PhaseRunner[Phase3ArtifactsView]):
    name = "Phase 4: Argument Mining"
    phase_key = "phase4"
    input_view = Phase3ArtifactsView

    def __init__(
        self,
        config: Phase4Config,
        schema: SchemaConfig,
        *,
        llm,
        embedding_model,
        graph_store: ProcessingGraph | PhaseCheckpointStore | None = None,
        adu_segmenter: ADUSegmenter | None = None,
        acc_classifier: ACCClassifier | None = None,
        arc_classifier: ARCClassifier | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
        decision_engine: DecisionEngine | None = None,
        stopping_oracle: GleaningStoppingOracle | None = None,
        modal_resolver: ModalStrengthResolver | None = None,
    ) -> None:
        """Initialize Phase 4 Argument Mining runner.

        Parameters
        ----------
        config : Phase4Config
            Phase 4 configuration parameters.
        schema : SchemaConfig
            Schema taxonomy containing allowable component and relation types.
        llm : Any
            Language model instance.
        embedding_model : Any
            Embedding model for semantic similarity or candidate blocking.
        graph_store : ProcessingGraph | PhaseCheckpointStore | None, optional
            Optional checkpoint or processing graph store.
        adu_segmenter : ADUSegmenter or None, default None
            Optional segmenter override.
        acc_classifier : ACCClassifier or None, default None
            Optional component classifier override.
        arc_classifier : ARCClassifier or None, default None
            Optional relation classifier override.
        global_extractor : GlobalRelationExtractor or None, default None
            Optional global relation extractor used for graph context.
        decision_engine : DecisionEngine or None, default None
            Optional calibrated decision engine for System 1 triage or cascading.
        stopping_oracle : GleaningStoppingOracle or None, default None
            Stopping oracle for actor-critic gleaning passes.
        modal_resolver : ModalStrengthResolver or None, default None
            Propositional modal strength resolver. If None, initialized from config and decision engine.
        """
        self.config = config
        self.schema = schema
        self.llm = llm
        self.embedding_model = embedding_model
        self.graph_store = graph_store
        self.global_extractor = global_extractor
        self.decision_engine = decision_engine

        self.modal_resolver = ensure_modal_strength_resolver(
            modal_resolver
        ) or HybridModalResolver.create(
            config=config.modal_resolver,
            decision_engine=self.decision_engine,
        )

        self.stopping_oracle = stopping_oracle or JevGleaningGate.create(
            decision_engine=decision_engine,
            config=config.gleaning,
            prompts=config.acc_prompts,
        )

        self.adu_segmenter: ADUSegmenter = adu_segmenter or LLMADUSegmenter(
            llm=self.llm,
            prompts=self.config.adu_segmentation_prompts,
        )

        default_llm_acc = LLMACCClassifier(
            llm=self.llm,
            prompts=self.config.acc_prompts,
            strategy=self.config.acc_decoding_strategy,
        )
        self.acc_classifier: ACCClassifier = acc_classifier or (
            CascadingACCClassifier(
                fast_classifier=JevACCClassifier(
                    decision_engine=self.decision_engine,
                    prompts=self.config.acc_prompts,
                    modal_resolver=self.modal_resolver,
                ),
                llm_classifier=default_llm_acc,
                config=self.config,
            )
            if self.decision_engine is not None
            else default_llm_acc
        )

        default_tag_arc = TAGARCClassifier(
            llm=llm,
            embedding_model=embedding_model,
            prompts=config.arc_prompts,
            strategy=config.arc_decoding_strategy,
            confidence_threshold=config.arc_confidence_threshold,
            subgraph_depth=config.arc_subgraph_depth,
            max_candidates_per_component=config.arc_max_candidates_per_component,
            use_priority_rank=config.arc_use_priority_rank,
            use_csls=config.arc_use_csls,
            csls_k_nearest=config.arc_csls_k_nearest,
            use_adaptive_k=config.arc_use_adaptive_k,
            adaptive_k_gamma=config.arc_adaptive_k_gamma,
            adaptive_k_min=config.arc_adaptive_k_min,
            z_score_threshold=config.arc_z_score_threshold,
        )
        self.arc_classifier: ARCClassifier = arc_classifier or (
            CascadingARCClassifier(
                fast_classifier=JevARCClassifier(
                    decision_engine=self.decision_engine,
                    prompts=config.arc_prompts,
                    embedding_model=embedding_model,
                    confidence_threshold=config.arc_confidence_threshold,
                    max_candidates_per_component=config.arc_max_candidates_per_component,
                ),
                llm_classifier=default_tag_arc,
                config=self.config,
            )
            if self.decision_engine is not None
            else default_tag_arc
        )

    @property
    def gleaning_gate(self) -> GleaningStoppingOracle:
        return self.stopping_oracle

    @staticmethod
    def _guard_systematic_failure(
        batch: list[L1Chunk], failures: list[Exception], succeeded: int
    ) -> None:
        """Abort the phase when a whole batch fails identically and nothing has worked yet.

        Parameters
        ----------
        batch : list of L1Chunk
            The chunk batch being evaluated.
        failures : list of Exception
            Exceptions raised by processing chunks in this batch.
        succeeded : int
            Total count of chunks successfully processed so far.

        Raises
        ------
        SystematicChunkFailure
            When all chunks in the first batch fail with the same exception type.
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
            f"error, not a per-chunk data error — aborting Phase 4 instead of "
            f"completing with an empty graph."
        ) from exc

    async def run(
        self, input: Phase3ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        effective_phase = (
            f"{_PHASE_TAG}:{context.lineage_fingerprint}"
            if context and context.lineage_fingerprint
            else _PHASE_TAG
        )
        chunks = await select_pending_chunks(
            self.graph_store, effective_phase, input.chunks
        )

        reader = input.to_graph_reader()
        use_artifact_reader = bool(
            input.entities
            or not isinstance(self.graph_store, GraphReader)
            or (context and context.lineage_fingerprint)
        )
        active_reader: GraphReader = (
            reader
            if use_artifact_reader
            else (
                self.graph_store
                if isinstance(self.graph_store, GraphReader)
                else reader
            )
        )

        if (
            isinstance(self.graph_store, GraphReader)
            and not (context and context.lineage_fingerprint)
        ):
            all_components: list[TheoryAtom] = await self.graph_store.get_theory_atoms()
        else:
            all_components = []
        all_local_relations: list[TheoryRelation] = []

        import asyncio
        from itertools import batched

        checkpoint_store = (
            self.graph_store
            if isinstance(self.graph_store, PhaseCheckpointStore)
            else None
        )

        async def _process_chunk_item(
            chunk: L1Chunk,
        ) -> tuple[list[TheoryAtom], list[TheoryRelation], str]:
            return await self._process_chunk(
                chunk.id, chunk.text, reader=active_reader
            )

        async def _on_chunk_batch_complete(
            batch_results: list[tuple[list[TheoryAtom], list[TheoryRelation], str]],
            records: list[PhaseItemRecord],
        ) -> None:
            new_components = []
            new_local_relations = []
            processed_chunk_ids = []
            relations_to_upsert = []

            for components, local_rels, c_id in batch_results:
                new_components.extend(components)
                new_local_relations.extend(local_rels)
                processed_chunk_ids.append(c_id)

                for component in components:
                    reader.register_theory_atom(component)
                    relations_to_upsert.append(
                        {
                            "from_id": component.id,
                            "relation_type": "EXTRACTED_FROM",
                            "to_id": c_id,
                            "properties": {"confidence": 1.0},
                        }
                    )
                    for entity_id in component.entity_ids:
                        relations_to_upsert.append(
                            {
                                "from_id": component.id,
                                "relation_type": "MENTIONS",
                                "to_id": entity_id,
                                "properties": {"confidence": 1.0},
                            }
                        )
                for local_rel in local_rels:
                    reader.register_theory_relation(local_rel)

            all_components.extend(new_components)
            all_local_relations.extend(new_local_relations)

            # Batch persist local findings when a direct GraphWriter is configured
            if isinstance(self.graph_store, GraphWriter):
                for comp_batch in batched(new_components, 500):
                    await self.graph_store.upsert_argument_components(
                        list(comp_batch)
                    )

                for rel_batch in batched(new_local_relations, 500):
                    await self.graph_store.upsert_theory_relations(list(rel_batch))

                for rel_batch in batched(relations_to_upsert, 500):
                    await self.graph_store.upsert_relations(list(rel_batch))

            if self.graph_store is not None and processed_chunk_ids:
                for processed_batch in batched(processed_chunk_ids, 500):
                    await self.graph_store.mark_chunks_processed(
                        list(processed_batch), effective_phase
                    )

        progress_task = f"Phase 4: Chunk ADU Extraction ({len(chunks)} chunks)"
        with self.progress_scope(
            progress_task,
            total_items=len(chunks),
            description="Chunk ADU Extraction",
        ) as advance:
            batch_size = self.config.batch_size
            executor = CheckpointedBatchExecutor[
                L1Chunk, tuple[list[TheoryAtom], list[TheoryRelation], str]
            ](
                checkpoint_store=checkpoint_store,
                phase_tag=effective_phase,
                batch_size=batch_size,
                item_key_fn=lambda ch: ch.id,
                process_item_fn=_process_chunk_item,
                on_batch_complete=_on_chunk_batch_complete,
                guard_systematic_failure=True,
            )
            try:
                await executor.execute(chunks, on_batch_advance=advance)
            except SystematicBatchFailureError as exc:
                msg = str(exc).replace("items", "chunks")
                raise SystematicChunkFailure(msg) from exc

        # Deduplicate all_components by id to avoid duplicating artifacts or ARC calls
        seen_ids = set()
        unique_components = []
        for c in all_components:
            if c.id not in seen_ids:
                seen_ids.add(c.id)
                unique_components.append(c)
        all_components = unique_components

        # Global argument relation classification (cross-chunk)
        global_relations: list[TheoryRelation] = []
        if self.arc_classifier is not None:
            arc_task = "Phase 4: Global ARC Classification"
            with self.progress_scope(
                arc_task,
                total_items=1,
                description="Cross-Chunk Relation Classification (ARC)",
            ) as advance_arc:
                global_relations = await self.arc_classifier.classify_global(
                    local_components=all_components,
                    local_relations=all_local_relations,
                    graph_store=active_reader,
                    global_extractor=self.global_extractor,
                    schema=self.schema,
                )
                advance_arc(1)

            # Commit global argument relations when a direct GraphWriter is configured
            if isinstance(self.graph_store, GraphWriter):
                for rel_batch in batched(global_relations, 500):
                    await self.graph_store.upsert_theory_relations(list(rel_batch))

        all_relations = all_local_relations + global_relations

        artifacts = []
        for component in all_components:
            artifacts.append(
                build_argument_component_artifact(
                    component,
                    run_id=context.run_id,
                    phase_name=self.name,
                    method="phase4.argument_mining",
                )
            )
        for relation in all_relations:
            artifacts.append(
                build_argument_relation_artifact(
                    relation,
                    run_id=context.run_id,
                    phase_name=self.name,
                    method="phase4.argument_mining",
                )
            )
        return ArtifactCollection(artifacts)

    async def _process_chunk(
        self,
        chunk_id: str,
        chunk_text: str,
        reader: GraphReader | None = None,
    ) -> tuple[list[TheoryAtom], list[TheoryRelation], str]:
        # Step 1: ADU Segmentation
        tagged_text, adu_ids = await self.adu_segmenter.segment(chunk_id, chunk_text)

        if not adu_ids:
            # No argumentative content
            return [], [], chunk_id

        # Step 2: ACC Classification
        active_reader = reader or (
            self.graph_store if isinstance(self.graph_store, GraphReader) else None
        )
        chunk_entities = (
            await active_reader.get_chunk_entities(chunk_id)
            if active_reader is not None
            else []
        )
        components, local_relations = await self.acc_classifier.classify(
            chunk_id=chunk_id,
            tagged_text=tagged_text,
            adu_ids=adu_ids,
            schema=self.schema,
            chunk_entities=chunk_entities,
        )

        if self.config.acc_confidence_threshold > 0.0:
            valid_component_ids = {
                c.id for c in components
                if c.confidence is None or c.confidence >= self.config.acc_confidence_threshold
            }
            components = [c for c in components if c.id in valid_component_ids]
            local_relations = [
                r for r in local_relations
                if r.source_id in valid_component_ids and r.target_id in valid_component_ids
            ]

        # Step 3: Optional Actor-Critic Gleaning Refinement
        pass_count = 0
        while True:
            should_continue, _ = await self.stopping_oracle.should_glean(
                chunk_text=chunk_text,
                current_extractions=components,
                pass_count=pass_count,
            )
            if not should_continue:
                break
            pass_count += 1

            prior_components_text = "\n".join([f"- {c.text}" for c in components])
            refinement_input = (
                f"{chunk_text}\n\n"
                f"Previously identified argument components:\n{prior_components_text}\n"
                f"Please identify any additional missed Argumentative Discourse Units."
            )
            refine_tagged_text, new_adu_ids = await self.adu_segmenter.segment(
                f"{chunk_id}_refine_{pass_count}", refinement_input
            )
            if not new_adu_ids:
                break

            new_components, new_rels = await self.acc_classifier.classify(
                chunk_id=chunk_id,
                tagged_text=refine_tagged_text,
                adu_ids=new_adu_ids,
                schema=self.schema,
                chunk_entities=chunk_entities,
            )
            if not new_components:
                break

            existing_ids = {c.id for c in components}
            added_any = False
            for nc in new_components:
                if nc.id not in existing_ids:
                    components.append(nc)
                    existing_ids.add(nc.id)
                    added_any = True
            for nr in new_rels:
                if nr.source_id in existing_ids and nr.target_id in existing_ids:
                    local_relations.append(nr)

            if not added_any:
                break

        if not components:
            return [], [], chunk_id

        # Resolve authorial propositional modal strength on newly mined components
        if self.modal_resolver:
            for c in components:
                if "modal_strength" not in c.model_fields_set and "base_score" not in c.model_fields_set:
                    c.modal_strength = await self.modal_resolver.resolve_modality(c, context=chunk_text)
                    c.base_score = c.modal_strength

        return components, local_relations, chunk_id
