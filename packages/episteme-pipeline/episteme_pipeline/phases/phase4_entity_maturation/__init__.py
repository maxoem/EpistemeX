"""
Phase 4 — Entity Maturation (Two-Stage Protocol)

This phase operates asynchronously or as a batch job after entity extraction.
It replaces the naive "first-mention-wins" paradigm with a mathematically rigorous synthesis.

1. Retrieves all `EXTRACTED_FROM` textual envelopes for an entity.
2. Computes the geometric centroid of these envelopes in the latent space.
3. Retrieves the Top-K envelopes closest to the centroid.
4. Uses the LLM to synthesize a definitive, mature description.

Design Note: Maturation synthesizes the canonical entity description before
argument mining begins. This is intentional: argument mining (Phase 4) depends on mature 
entity descriptions for stable linking and clustering. While maturation misses argumentative 
context, and 3b ignores the centroid result, resolving these in parallel or merging their 
evidence gathering would violate phase boundaries.
"""

from __future__ import annotations

import logging
from typing import Any

import torch
from pydantic import BaseModel

from episteme_pipeline.artifacts.execution import (
    ArtifactCollection,
    ArtifactExecutionContext,
    Phase3ArtifactsView,
)
from episteme_pipeline.config import Phase4EntityMaturationConfig
from episteme_pipeline.contracts.domain import L2Entity
from episteme_pipeline.events.bus import EventEmitter
from episteme_pipeline.events.models import (
    EntityMaturationSynthesized,
    ProgressAdvanced,
    ProgressCompleted,
    ProgressStarted,
)
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.protocols.extractors import EmbeddingModel, as_tensor
from episteme_pipeline.protocols.graph_store import ProcessingGraph
from episteme_pipeline.protocols.phase_runner import PhaseRunner

logger = logging.getLogger(__name__)

class EntitySynthesisOutput(BaseModel):
    description: str


def _default_embedding_model() -> EmbeddingModel:
    """Last-resort local encoder, imported lazily to keep ``transformers`` optional."""
    from episteme_pipeline.protocols.extractors import HuggingFaceEmbeddingModel

    logger.warning(
        "Phase 4 maturation received no embedding model and none is configured; "
        "falling back to a default HuggingFaceEmbeddingModel."
    )
    return HuggingFaceEmbeddingModel()


class Phase4EntityMaturationRunner(PhaseRunner[Phase3ArtifactsView]):
    """Runner for Phase 4: Entity Maturation (Batch Epistemic Synthesis).

    This phase addresses the 'epistemic drift' problem in knowledge graph construction.
    Instead of using a naive 'first-mention-wins' approach to name and describe entities,
    this phase runs after Phase 3 to mature and stabilize entities before fusion:
    1. Fetches all mention context envelopes (from `EXTRACTED_FROM` relations).
    2. Encodes envelopes using the Phase 2 Bi-Encoder.
    3. Calculates the geometric centroid of the vectors to find the core meaning.
    4. Ranks envelopes and selects the top-K closest to the centroid.
    5. Calls the LLM to synthesize a canonical description from these top-K envelopes.
    6. Persists the matured entity and marks it as mature (`is_mature = True`).

    Parameters
    ----------
    config : Phase4EntityMaturationConfig
        Configuration options for maturation (e.g. top-K envelopes to select).
    llm : LiteLLM
        LLM instance used for structured description synthesis.
    graph_store : ProcessingGraph
        The underlying Neo4j/graph database client.
    """
    name = "Phase 4: Entity Maturation (Batch Epistemic Synthesis)"
    phase_key = "phase4_maturation"
    input_view = Phase3ArtifactsView

    def __init__(
        self,
        config: Phase4EntityMaturationConfig,
        *,
        llm: Any,
        graph_store: ProcessingGraph,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self.config = config
        self.llm = ensure_structured_llm(llm)
        self.graph_store = graph_store
        self.embedding_model: EmbeddingModel = (
            embedding_model or _default_embedding_model()
        )

    @property
    def event_emitter(self) -> EventEmitter:
        from episteme_pipeline.events.context import get_event_emitter
        return get_event_emitter()

    async def run(self, input: Phase3ArtifactsView, context: ArtifactExecutionContext) -> ArtifactCollection:
        # Note: In a production setting with extremely large inputs, this could be triggered
        # dynamically during Phase 2 when an entity reaches a threshold N of mentions.
        # For pipeline orchestration, it runs post Phase 3.
        
        logger.info("Starting Entity Maturation batch synthesis...")
        from episteme_pipeline.artifacts.builders import build_linked_entity_artifact
        
        all_entities = await self.graph_store.get_entities()
        immature_entities = [e for e in all_entities if not e.is_mature]
        
        logger.info(f"Found {len(immature_entities)} immature entities out of {len(all_entities)} total.")
        
        matured_artifacts = []
        import asyncio
        from itertools import batched
        
        progress_task = f"Phase 4 Maturation: {len(immature_entities)} entities"
        if immature_entities:
            self.event_emitter.emit(
                ProgressStarted(
                    task_name=progress_task,
                    total_items=len(immature_entities),
                    description="Entity Maturation",
                )
            )

        batch_size = self.config.batch_size
        
        # Process and checkpoint in batches to ensure crash resilience
        for batch_idx, entity_batch in enumerate(batched(immature_entities, batch_size)):
            logger.info(f"Maturing batch {batch_idx + 1}...")
            
            # Parallelize the LLM synthesis for this small batch
            tasks = [self._process_entity(entity, context.run_id) for entity in entity_batch]
            matured_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            entities_to_upsert = []
            for entity, matured_entity in zip(entity_batch, matured_results):
                if isinstance(matured_entity, Exception):
                    logger.error(f"Entity Maturation failed for {entity.name}: {matured_entity}")
                    continue
                if matured_entity:
                    entities_to_upsert.append(matured_entity)
                    matured_artifacts.append(
                        build_linked_entity_artifact(
                            matured_entity,
                            [f"artifact::{cid}" for cid in matured_entity.source_chunk_ids],
                            run_id=context.run_id,
                            phase_name=self.name,
                            method="Phase4EntityMaturationRunner",
                        )
                    )
                    
            # Checkpoint graph for this batch
            if entities_to_upsert:
                # Upsert in sub-batches of 500 (though max is 100 here)
                for sub_batch in batched(entities_to_upsert, 500):
                    await self.graph_store.upsert_entities(list(sub_batch))

            self.event_emitter.emit(
                ProgressAdvanced(task_name=progress_task, advance=len(entity_batch))
            )

        if immature_entities:
            self.event_emitter.emit(ProgressCompleted(task_name=progress_task))

            
        if matured_artifacts:
            return ArtifactCollection(matured_artifacts)
        return ArtifactCollection([])

    async def _process_entity(self, entity: L2Entity, run_id: str) -> L2Entity | None:
        # 1. Fetch all textual envelopes from EXTRACTED_FROM edges.
        # No capability check: get_entity_envelopes is part of the GraphReader
        # contract (F-11). It used to be duck-typed, which turned a missing
        # backend method into "this entity has nothing to mature".
        envelopes = await self.graph_store.get_entity_envelopes(entity.id)
        if not envelopes:
            logger.debug(f"Entity {entity.name} has no valid textual envelopes to synthesize.")
            # Mark as mature anyway to avoid reprocessing empty entities
            matured_entity = entity.model_copy(update={"is_mature": True})
            return matured_entity

        # 2. Geometric Centroid Calculation
        # E_ctx(T_i) for all envelopes
        embeddings = as_tensor(
            await self.embedding_model.aget_text_embedding_batch(envelopes)
        )  # Shape: [N, hidden_size]
        
        if len(envelopes) <= self.config.maturation_top_k:
            # Not enough envelopes to filter, just use all of them
            top_k_envelopes = envelopes
        else:
            # Compute geometric centroid C
            centroid = torch.mean(embeddings, dim=0, keepdim=True) # Shape: [1, hidden_size]
            
            # Calculate distances (we can use negative cosine similarity to rank closest)
            # Higher cosine similarity = closer to centroid
            similarities = torch.nn.functional.cosine_similarity(embeddings, centroid)
            
            # Get Top-k indices
            top_k_indices = torch.topk(similarities, self.config.maturation_top_k).indices.tolist()
            top_k_envelopes = [envelopes[i] for i in top_k_indices]
            
        # 3. Generative Fusion via LLM
        formatted_envelopes = "\n---\n".join(top_k_envelopes)

        logger.debug(f"Synthesizing description for {entity.name} using {len(top_k_envelopes)} representative contexts.")

        try:
            raw: EntitySynthesisOutput = await self.llm.predict_structured(
                EntitySynthesisOutput,
                self.config.entity_synthesis_prompts,
                strategy=self.config.entity_synthesis_decoding_strategy,
                entity_name=entity.name,
                envelopes=formatted_envelopes,
            )
            synthesized_desc = raw.description
        except Exception as exc:
            logger.warning(f"Synthesis failed for {entity.name}: {exc}")
            return None
            
        # 4. Update the entity
        matured_entity = entity.model_copy(update={
            "description": synthesized_desc,
            "is_mature": True
        })
        
        logger.info(f"Successfully matured entity {entity.name}.")
        
        # Emit event
        self.event_emitter.emit(
            EntityMaturationSynthesized(
                run_id=run_id,
                phase=self.name,
                entity_id=entity.id,
                entity_name=entity.name,
                envelope_count=len(envelopes),
                top_k_used=len(top_k_envelopes),
                synthesized_description=synthesized_desc,
            )
        )
        return matured_entity
