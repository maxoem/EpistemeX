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
from episteme_pipeline.events.models import EntityMaturationSynthesized
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.protocols.extractors import EmbeddingModel, as_tensor
from episteme_pipeline.protocols.graph_store import (
    GraphReader,
    GraphWriter,
    PhaseCheckpointStore,
    ProcessingGraph,
)
from episteme_pipeline.protocols.phase_runner import PhaseRunner
from episteme_pipeline.runtime.batch_executor import CheckpointedBatchExecutor

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
    this phase runs after Phase 3b to mature and stabilize canonical entities:
    1. Fetches all mention context envelopes from ``input.entity_envelopes_by_id`` (or ``GraphReader``).
    2. Encodes envelopes using the Phase 2 Bi-Encoder.
    3. Calculates the geometric centroid of the vectors to find the core meaning.
    4. Ranks envelopes and selects the top-K closest to the centroid.
    5. Calls the LLM to synthesize a canonical description from these top-K envelopes.
    6. Emits matured ``LinkedEntityArtifact`` envelopes (`is_mature = True`).

    Parameters
    ----------
    config : Phase4EntityMaturationConfig
        Configuration options for maturation (e.g. top-K envelopes to select).
    llm : LiteLLM
        LLM instance used for structured description synthesis.
    graph_store : ProcessingGraph | GraphReader | None, optional
        Optional graph database client fallback.
    """

    name = "Phase 4: Entity Maturation (Batch Epistemic Synthesis)"
    phase_key = "phase4_maturation"
    input_view = Phase3ArtifactsView

    def __init__(
        self,
        config: Phase4EntityMaturationConfig,
        *,
        llm: Any,
        graph_store: ProcessingGraph | GraphReader | None = None,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self.config = config
        self.llm = ensure_structured_llm(llm)
        self.graph_store = graph_store
        self.embedding_model: EmbeddingModel = (
            embedding_model or _default_embedding_model()
        )

    async def run(
        self, input: Phase3ArtifactsView, context: ArtifactExecutionContext
    ) -> ArtifactCollection:
        logger.info("Starting Entity Maturation batch synthesis...")
        from episteme_pipeline.artifacts.builders import build_linked_entity_artifact

        if input.entities:
            all_entities = list(input.entities)
        elif isinstance(self.graph_store, GraphReader):
            all_entities = await self.graph_store.get_entities()
        else:
            all_entities = []

        immature_entities = [e for e in all_entities if not e.is_mature]

        logger.info(
            f"Found {len(immature_entities)} immature entities out of {len(all_entities)} total."
        )

        matured_artifacts = []
        import asyncio
        from itertools import batched

        progress_task = f"Phase 4 Maturation: {len(immature_entities)} entities"
        batch_size = self.config.batch_size
        checkpoint_store = (
            self.graph_store
            if isinstance(self.graph_store, PhaseCheckpointStore)
            else None
        )
        effective_phase = (
            f"{self.phase_key}:{context.lineage_fingerprint}"
            if context and context.lineage_fingerprint
            else self.phase_key
        )

        async def _maturation_item(entity: L2Entity) -> L2Entity | None:
            return await self._process_entity(
                entity,
                context.run_id,
                input_envelopes=input.entity_envelopes_by_id.get(entity.id),
            )

        async def _on_maturation_batch(
            batch_entities: list[L2Entity],
            records: list[PhaseItemRecord],
        ) -> None:
            for matured_entity in batch_entities:
                mention_ids = [
                    f"artifact::mention::{matured_entity.id}::{cid}"
                    for cid in matured_entity.source_chunk_ids
                ]
                matured_artifacts.append(
                    build_linked_entity_artifact(
                        matured_entity,
                        mention_ids,
                        run_id=context.run_id,
                        phase_name=self.name,
                        method="Phase4EntityMaturationRunner",
                        upstream_artifact_ids=[
                            f"artifact::{matured_entity.id}",
                            *mention_ids,
                        ],
                    )
                )

            if batch_entities and isinstance(self.graph_store, GraphWriter):
                for sub_batch in batched(batch_entities, 500):
                    await self.graph_store.upsert_entities(list(sub_batch))

        with self.progress_scope(
            progress_task,
            total_items=len(immature_entities),
            description="Entity Maturation",
        ) as advance:
            executor = CheckpointedBatchExecutor[L2Entity, L2Entity](
                checkpoint_store=checkpoint_store,
                phase_tag=effective_phase,
                batch_size=batch_size,
                item_key_fn=lambda e: f"maturation::{e.id}",
                process_item_fn=_maturation_item,
                on_batch_complete=_on_maturation_batch,
                guard_systematic_failure=False,
            )
            await executor.execute(immature_entities, on_batch_advance=advance)

        if matured_artifacts:
            return ArtifactCollection(matured_artifacts)
        return ArtifactCollection([])

    async def _process_entity(
        self,
        entity: L2Entity,
        run_id: str,
        input_envelopes: list[str] | None = None,
    ) -> L2Entity | None:
        if input_envelopes:
            envelopes = list(input_envelopes)
        elif isinstance(self.graph_store, GraphReader):
            envelopes = await self.graph_store.get_entity_envelopes(entity.id)
        elif entity.textual_envelope:
            envelopes = [entity.textual_envelope]
        else:
            envelopes = []
        if not envelopes:
            logger.debug(
                f"Entity {entity.name} has no valid textual envelopes to synthesize."
            )
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
