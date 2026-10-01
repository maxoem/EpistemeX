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

import asyncio
import logging
from collections import defaultdict

from episteme_pipeline.config import Phase4Config
from episteme_pipeline.contracts.domain import (
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.phases.phase4_argument_mining.acc_classifier import LLMACCClassifier
from episteme_pipeline.phases.phase4_argument_mining.adu_segmenter import LLMADUSegmenter
from episteme_pipeline.phases.phase4_argument_mining.arc_classifier import TAGARCClassifier
from episteme_pipeline.protocols.argument_mining import (
    ACCClassifier,
    ADUSegmenter,
    ARCClassifier,
)
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor
from episteme_pipeline.phases.chunk_selection import select_pending_chunks
from episteme_pipeline.protocols.graph_store import ProcessingGraph
from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase3ArtifactsView,
)
from episteme_pipeline.artifacts.builders import (
    build_argument_component_artifact,
    build_argument_relation_artifact,
)
from episteme_pipeline.events.bus import EventEmitter, NoOpEventEmitter
from episteme_pipeline.events.models import (
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
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
        graph_store: ProcessingGraph,
        adu_segmenter: ADUSegmenter | None = None,
        acc_classifier: ACCClassifier | None = None,
        arc_classifier: ARCClassifier | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
        decision_engine: Any | None = None,
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
        graph_store : ProcessingGraph
            Active graph store for reading and writing components and relations.
        adu_segmenter : ADUSegmenter or None, default None
            Optional segmenter override. If omitted, constructed per chunk.
        acc_classifier : ACCClassifier or None, default None
            Optional component classifier override.
        arc_classifier : ARCClassifier or None, default None
            Optional relation classifier override.
        global_extractor : GlobalRelationExtractor or None, default None
            Optional global relation extractor used for graph context.
        decision_engine : Any or None, default None
            Optional calibrated decision engine for System 1 triage or cascading.
        """
        self.config = config
        self.schema = schema
        self.llm = llm
        self.embedding_model = embedding_model
        self.graph_store = graph_store
        self.global_extractor = global_extractor
        self.decision_engine = decision_engine
        self._adu_segmenter_override = adu_segmenter
        self._acc_classifier_override = acc_classifier
        self.arc_classifier = arc_classifier or (
            TAGARCClassifier(
                llm=llm,
                embedding_model=embedding_model,
                prompts=config.arc_prompts,
                strategy=config.arc_decoding_strategy,
                confidence_threshold=config.arc_confidence_threshold,
                subgraph_depth=config.arc_subgraph_depth,
                max_candidates_per_component=config.arc_max_candidates_per_component,
                use_priority_rank=config.arc_use_priority_rank,
            )
            if global_extractor is not None
            else None
        )

    @property
    def event_emitter(self) -> EventEmitter:
        from episteme_pipeline.events.context import get_event_emitter
        return get_event_emitter()

    async def run(
        self, input: Phase3ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        chunks = await select_pending_chunks(
            self.graph_store, _PHASE_TAG, input.chunks
        )

        all_components: list[TheoryAtom] = await self.graph_store.get_theory_atoms()
        all_local_relations: list[TheoryRelation] = []

        from itertools import batched
        import asyncio

        progress_task = f"Phase 4: Chunk ADU Extraction ({len(chunks)} chunks)"
        if chunks:
            self.event_emitter.emit(
                ProgressStarted(
                    task_name=progress_task,
                    total_items=len(chunks),
                    description="Chunk ADU Extraction",
                )
            )

        # Process and checkpoint in batches of config.batch_size (defaulting to 50 if missing)
        batch_size = getattr(self.config, "batch_size", 50)
        
        for batch_idx, chunk_batch in enumerate(batched(chunks, batch_size)):
            logger.info(f"Mining arguments for chunk batch {batch_idx + 1}...")
            tasks = [self._process_chunk(chunk.id, chunk.text) for chunk in chunk_batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
    
            new_components = []
            new_local_relations = []
            processed_chunk_ids = []
            relations_to_upsert = []

    
            for chunk, result in zip(chunk_batch, results):
                if isinstance(result, Exception):
                    logger.error(
                        "Chunk %s argument mining failed (will retry): %s", chunk.id, result
                    )
                    continue
                    
                components, local_rels, c_id = result
                    
                new_components.extend(components)
                new_local_relations.extend(local_rels)
                processed_chunk_ids.append(c_id)
    
                for component in components:
                    relations_to_upsert.append({
                        "from_id": component.id,
                        "relation_type": "EXTRACTED_FROM",
                        "to_id": c_id,
                        "properties": {"confidence": 1.0},
                    })
                    for entity_id in component.entity_ids:
                        relations_to_upsert.append({
                            "from_id": component.id,
                            "relation_type": "MENTIONS",
                            "to_id": entity_id,
                            "properties": {"confidence": 1.0},
                        })
                for rel in local_rels:
                    relations_to_upsert.append({
                        "from_id": rel.source_id,
                        "relation_type": rel.relation_type,
                        "to_id": rel.target_id,
                        "properties": {
                            "confidence": rel.confidence,
                            "scope": rel.scope,
                            "weight": rel.weight,
                        },
                    })
    
            all_components.extend(new_components)
            all_local_relations.extend(new_local_relations)
    
            # Batch persist local findings for this checkpoint
            for comp_batch in batched(new_components, 500):
                await self.graph_store.upsert_argument_components(list(comp_batch))
            
            for rel_batch in batched(relations_to_upsert, 500):
                await self.graph_store.upsert_relations(list(rel_batch))
                
            if processed_chunk_ids:
                for processed_batch in batched(processed_chunk_ids, 500):
                    await self.graph_store.mark_chunks_processed(list(processed_batch), _PHASE_TAG)

            self.event_emitter.emit(
                ProgressAdvanced(task_name=progress_task, advance=len(chunk_batch))
            )

        if chunks:
            self.event_emitter.emit(ProgressCompleted(task_name=progress_task))

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
        if self.arc_classifier is not None and self.global_extractor is not None:
            arc_task = "Phase 4: Global ARC Classification"
            self.event_emitter.emit(
                ProgressStarted(
                    task_name=arc_task,
                    total_items=1,
                    description="Cross-Chunk Relation Classification (ARC)",
                )
            )
            try:
                global_relations = await self.arc_classifier.classify_global(
                    local_components=all_components,
                    local_relations=all_local_relations,
                    graph_store=self.graph_store,
                    global_extractor=self.global_extractor,
                    schema=self.schema,
                )
                self.event_emitter.emit(
                    ProgressAdvanced(task_name=arc_task, advance=1, current=1, total_items=1)
                )
            finally:
                self.event_emitter.emit(ProgressCompleted(task_name=arc_task))
            
            # Commit global argument relations
            global_relations_to_upsert = []
            for rel in global_relations:
                global_relations_to_upsert.append({
                    "from_id": rel.source_id,
                    "relation_type": rel.relation_type,
                    "to_id": rel.target_id,
                    "properties": {
                        "confidence": rel.confidence,
                        "scope": rel.scope,
                        "weight": rel.weight,
                    },
                })
            for rel_batch in batched(global_relations_to_upsert, 500):
                await self.graph_store.upsert_relations(list(rel_batch))

        if processed_chunk_ids:
            for chunk_batch in batched(processed_chunk_ids, 500):
                await self.graph_store.mark_chunks_processed(list(chunk_batch), _PHASE_TAG)

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
        self, chunk_id: str, chunk_text: str
    ) -> tuple[list[TheoryAtom], list[TheoryRelation]]:
        # Step 1: ADU Segmentation
        segmenter = self._adu_segmenter_override or LLMADUSegmenter(
            llm=self.llm,
            prompt_template=self.config.adu_segmentation_prompt_template,
        )
        tagged_text, adu_ids = await segmenter.segment(chunk_id, chunk_text)

        if not adu_ids:
            # No argumentative content
            return [], [], chunk_id

        # Step 2: ACC Classification
        chunk_entities = await self.graph_store.get_chunk_entities(chunk_id)

        classifier = self._acc_classifier_override or LLMACCClassifier(
            llm=self.llm,
            prompts=self.config.acc_prompts,
            strategy=self.config.acc_decoding_strategy,
        )
        components, local_relations = await classifier.classify(
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

        if not components:
            return [], [], chunk_id

        return components, local_relations, chunk_id
