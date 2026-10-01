"""
DenseRetrievalGlobalRelationExtractor — SOTA GlobalRelationExtractor implementation.

Strategy (Retrieve-then-Rerank-then-Extract):

1. Global Candidate Generation (The Prior):
   Instead of chunk-bound co-occurrence, we embed entities globally (using their
   name/description). We compute dense vector similarities to find entities that 
   are semantically related across the entire corpus, breaking document boundaries.

2. Contextual Envelopes (Entity-in-Context):
   We retrieve the subgraph envelopes for each candidate entity. In a true SOTA
   pipeline, we could also use marker tokens (e.g. `[E1] entity [/E1]`) to embed 
   these contexts to focus attention dynamically on the entity within its chunk.

3. Cross-Encoder Reranking (High Precision Filter):
   We pass the paired entities and their envelopes to the `RelationReranker`. 
   Unlike a Bi-Encoder, a Cross-Encoder evaluates the pair jointly, allowing self-attention
   to deeply cross-reference concept k in chunk A with concept k in chunk B.
   Only candidate pairs that score above `reranker_threshold` proceed.

4. LLM Triple Decoding (Edge Enhancement):
   The LLM operates purely on high-probability candidate pairs to classify the 
   schema-aligned relationship (e.g., CAUSED_BY) using `GLOBAL_RELATION_PROMPT`.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Optional

import numpy as np

from llama_index.core import PromptTemplate

from episteme_pipeline.config import Phase3Config
from episteme_pipeline.contracts.domain import L2Entity, L2Triple, SubGraph, CandidatePair
from episteme_pipeline.prompts.default_prompts import PAIR_GATING_DECISION_PROMPT
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.phases.phase3_global_relations.models import GlobalRelationOutput
from episteme_pipeline.phases.phase3_global_relations.rerankers import (
    build_relation_reranker_inputs,
    summarize_reranker_text_pair,
)
from episteme_pipeline.protocols import DecisionEngine
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor, RelationReranker, EmbeddingModel
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.protocols.tracing import TraceSink, NoOpTraceSink
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils import format_envelope

# Events support
from episteme_pipeline.events.bus import EventEmitter, NoOpEventEmitter
from episteme_pipeline.events.models import (
    DenseCandidatesGenerated, RerankerScoreAssigned, CandidateRejectedByThreshold,
    LLMRelationDecoded, SchemaValidationRejectedRelation, TripleCommitted, EntityProcessed, ProgressAdvanced,
    ProgressStarted, ProgressCompleted
)

logger = logging.getLogger(__name__)

# Alias for backwards-compatibility within this module
_DenseCandidate = CandidatePair


@dataclass(frozen=True)
class EnvelopeOverflowContext:
    """Context passed to reranker overflow handlers.

    Parameters
    ----------
    entity_a
        Query-side entity for the reranker attempt.
    entity_b
        Document-side entity for the reranker attempt.
    graph_store
        Graph reader used to refetch envelopes if the handler wants to.
    env_a
        Current query-side envelope.
    env_b
        Current document-side envelope.
    current_depth
        Current subgraph traversal depth represented by the envelopes.
    reranker_input
        Size metadata for the current reranker input.
    error
        Exception raised by the reranker.
    retry_index
        Zero-based retry index for this overflow recovery path.
    refetch_envelopes
        Helper that refetches both envelopes for a new depth.
    """

    entity_a: L2Entity
    entity_b: L2Entity
    graph_store: GraphReader
    env_a: SubGraph
    env_b: SubGraph
    current_depth: int
    reranker_input: dict[str, object]
    error: Exception
    retry_index: int
    refetch_envelopes: Callable[[int], Awaitable[tuple[SubGraph, SubGraph]]]


@dataclass(frozen=True)
class EnvelopeOverflowResolution:
    """Resolved overflow state returned by an overflow handler.

    Parameters
    ----------
    env_a
        Replacement query-side envelope.
    env_b
        Replacement document-side envelope.
    strategy
        Short identifier describing how the overflow was handled.
    metadata
        Handler-specific metadata to surface in observability.
    """

    env_a: SubGraph
    env_b: SubGraph
    strategy: str
    metadata: dict[str, object]


type EnvelopeOverflowHandler = Callable[
    [EnvelopeOverflowContext],
    EnvelopeOverflowResolution | Awaitable[EnvelopeOverflowResolution | None] | None,
]


def make_reduce_depth_overflow_handler(
    depth_step: int = 1,
) -> EnvelopeOverflowHandler:
    """Return an overflow handler that refetches envelopes at a shallower depth.

    Parameters
    ----------
    depth_step
        Number of traversal levels to remove on each overflow retry.

    Returns
    -------
    EnvelopeOverflowHandler
        Handler that retries with reduced subgraph depth until depth 1.
    """

    async def _handler(
        context: EnvelopeOverflowContext,
    ) -> EnvelopeOverflowResolution | None:
        next_depth = context.current_depth - depth_step
        if next_depth < 1:
            return None

        env_a, env_b = await context.refetch_envelopes(next_depth)
        return EnvelopeOverflowResolution(
            env_a=env_a,
            env_b=env_b,
            strategy="reduce_subgraph_depth",
            metadata={
                "previous_depth": context.current_depth,
                "next_depth": next_depth,
                "depth_step": depth_step,
            },
        )

    return _handler


class DenseRetrievalGlobalRelationExtractor(GlobalRelationExtractor):
    """
    SOTA GlobalRelationExtractor leveraging dense embeddings for candidate 
    generation and a cross-encoder for relational reranking prior to LLM extraction.
    """

    def __init__(
        self, 
        llm, 
        embedding_model: EmbeddingModel, 
        reranker: RelationReranker,
        config: Phase3Config,
        envelope_overflow_handler: EnvelopeOverflowHandler | None = None,
        # Kept for backward compatibility
        trace_sink: Optional[TraceSink] = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        self.llm = ensure_structured_llm(llm)
        self.embedding_model = embedding_model
        self.reranker = reranker
        self.config = config
        self.envelope_overflow_handler = envelope_overflow_handler
        self.trace_sink = trace_sink or NoOpTraceSink()
        self.decision_engine = decision_engine

    @property
    def event_emitter(self) -> EventEmitter:
        from episteme_pipeline.events.context import get_event_emitter
        return get_event_emitter()

    async def get_structural_neighborhood(
        self,
        entity: L2Entity,
        graph_store: GraphReader,
        depth: int = 2,
    ) -> SubGraph:
        return await graph_store.get_neighborhood(entity.id, depth=depth)

    async def extract(
        self,
        entities: list[L2Entity],
        graph_store: GraphReader,
        schema: SchemaConfig,
    ) -> list[L2Triple]:
        if len(entities) < 2:
            return []
            
        # Emit event for entity processing
        for entity in entities:
            self.event_emitter.emit(EntityProcessed(
                entity_id=entity.id,
                entity_name=entity.name,
                entity_type=entity.label,
                run_id=None,
                phase="phase3_dense"
            ))
            
        # Optionally trace dense candidate generation
        with self.trace_sink.span(
            name="phase3.dense.candidates",
            input={
                "entities": [_entity_summary(e) for e in entities],
                "threshold": self.config.dense_similarity_threshold,
            },
            enabled=self.config.trace_dense_retrieval,
        ) as span:
            candidates = await self._generate_dense_candidates(entities)
            span.update(
                output={
                    "candidate_count": len(candidates),
                    "candidates": [_candidate_summary(c) for c in candidates[:10]],
                }
            )
        logger.info(
            "Phase 3 (Dense): %d entities → %d global candidate pairs",
            len(entities),
            len(candidates),
        )

        progress_task = f"Phase 3: {len(candidates)} global pairs"
        self.event_emitter.emit(ProgressStarted(task_name=progress_task, total_items=len(candidates), description="Global Relations"))

        sem = asyncio.Semaphore(50)
        async def _extract_with_sem(candidate: _DenseCandidate) -> L2Triple | None:
            async with sem:
                res = await self._extract_pair(candidate, graph_store, schema)
                self.event_emitter.emit(ProgressAdvanced(task_name=progress_task, advance=1))
                return res

        tasks = [
            _extract_with_sem(candidate) for candidate in candidates
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        self.event_emitter.emit(ProgressCompleted(task_name=progress_task))

        triples: list[L2Triple] = []
        for candidate, result in zip(candidates, results):
            if isinstance(result, Exception):
                logger.error(
                    "Phase 3 pair (%s, %s) failed: %s",
                    candidate.entity_a.id,
                    candidate.entity_b.id,
                    result,
                )
                continue
            if result is not None:
                triples.append(result)

        logger.info(
            "Phase 3 (Dense): extracted %d global triples",
            len(triples)
        )
        return triples

    async def candidate_pairs(
        self, entities: list[L2Entity]
    ) -> list[CandidatePair]:
        """Generate candidate entity pairs via dense embedding retrieval.

        Parameters
        ----------
        entities : list[L2Entity]
            Entities considered for candidate pairing.

        Returns
        -------
        list[CandidatePair]
            Dense candidate pairs above configured similarity threshold.
        """
        return await self._generate_dense_candidates(entities)

    async def extract_pair(
        self,
        pair: CandidatePair,
        graph_store: GraphReader,
        schema: SchemaConfig,
    ) -> L2Triple | None:
        """Extract a relation triple for a single candidate pair.

        Parameters
        ----------
        pair : CandidatePair
            Candidate entity pair to evaluate.
        graph_store : GraphReader
            Graph reader for envelope retrieval.
        schema : SchemaConfig
            Schema configuration defining valid relation types.

        Returns
        -------
        L2Triple | None
            Extracted triple if validated, otherwise None.
        """
        return await self._extract_pair(pair, graph_store, schema)

    async def _generate_dense_candidates(
        self, entities: list[L2Entity]
    ) -> list[_DenseCandidate]:
        """Embed entities and compute dense candidate pairs.

        Parameters
        ----------
        entities
            Entities considered for global relation extraction.

        Returns
        -------
        list[_DenseCandidate]
            Candidate pairs that exceeded the dense similarity threshold, sorted
            by descending dense score and capped by configured limits.
        """
        # Sort entities deterministically to ensure order-invariant candidate generation
        entities = sorted(entities, key=lambda e: e.id)

        # Step 1: Embed textual envelopes (T_A x T_B proximity)
        # We fallback to name/description only if textual_envelope is mysteriously missing
        embed_texts = [
            ent.textual_envelope if ent.textual_envelope else f"{ent.name} {ent.description or ''}".strip()
            for ent in entities
        ]

        # Note: In practice, we'd chunk these for large batches, but for
        # reasonable entity counts (<200), hitting the endpoint once is fine.
        # Ideally this should use our new EnvelopeBiEncoder, but for compatibility 
        # with the existing embedding_model signature, we pass the text.
        embeddings = await self.embedding_model.aget_text_embedding_batch(embed_texts)

        # Step 2: Compute dense cosine similarities
        #
        # For n entities, this produces (n choose 2) = ~n²/2 pairs. For n=50,
        # that's ~1250 pairs. Still manageable in memory and useful downstream.
        #
        # For scaling beyond 100-200 entities, we'd switch to FAISS/ANN search.
        entity_vectors = np.array(embeddings)
        norms = np.linalg.norm(entity_vectors, axis=1, keepdims=True)
        normalized_vectors = entity_vectors / norms

        similarity_matrix = np.dot(normalized_vectors, normalized_vectors.T)

        # Collect top-k pairs per entity, or globally if preferred
        candidates: list[_DenseCandidate] = []
        for i in range(len(entities)):
            row_scores = [(j, similarity_matrix[i, j]) for j in range(i + 1, len(entities))]
            row_scores.sort(key=lambda x: x[1], reverse=True)
            for j, score in row_scores[:self.config.max_candidates_per_entity_pair]:
                # Emit event for each candidate pair evaluation
                candidates.append(_DenseCandidate(
                    score=float(score),
                    entity_a=entities[i],
                    entity_b=entities[j],
                ))

        # Emit event for dense candidates generated
        self.event_emitter.emit(DenseCandidatesGenerated(
            candidate_count=len(candidates),
            candidates=[{
                "entity_a": candidate.entity_a.id,
                "entity_b": candidate.entity_b.id,
                "score": candidate.score
            } for candidate in candidates[:10]],  # First 10 for brevity
            entities_count=len(entities),
            run_id=None,
            phase="phase3_dense"
        ))
        
        # Filter candidates by dense similarity threshold
        filtered_candidates = [
            c for c in candidates if c.score >= self.config.dense_similarity_threshold
        ]
        
        # Apply Jev pair gating if enabled
        return await self.filter_candidate_pairs(filtered_candidates)

    async def filter_candidate_pairs(self, pairs: list[CandidatePair]) -> list[CandidatePair]:
        """Fast Cartesian pair pre-gating using Decision Engine.

        Filters candidate entity pairs using fast binary decision evaluation
        before heavy cross-encoder reranking or LLM extraction.

        Parameters
        ----------
        pairs : list of CandidatePair
            The candidate entity pairs to filter.

        Returns
        -------
        list of CandidatePair
            The filtered candidate pairs surviving gating or stochastic audit.
        """
        if not self.config.use_jev_pair_gating or not self.decision_engine:
            return pairs

        prompts = getattr(self.config, "global_relation_prompts", None)
        if prompts is not None:
            template = prompts.decision_template
        else:
            template = PAIR_GATING_DECISION_PROMPT

        if not template or not template.strip():
            raise ValueError(
                "No decision prompt configured for DenseRetrievalGlobalRelationExtractor pair gating."
            )
        template = template.strip()

        import random
        gated_pairs = []
        
        for pair in pairs:
            entity_a = pair.entity_a
            entity_b = pair.entity_b
            
            question = template.format(entity_a=entity_a.name, entity_b=entity_b.name)
            context = f"Entity A: {entity_a.description or entity_a.name}\nEntity B: {entity_b.description or entity_b.name}"
            
            decision = await self.decision_engine.evaluate_noul(
                state=context,
                question=question,
            )
            
            is_related = decision.passed
            threshold = self.config.pair_gating_threshold
            p_has_relation = decision.probability if is_related else (1.0 - decision.probability)
            
            if p_has_relation >= threshold or (not is_related and random.random() < self.config.pair_gating_audit_rate):
                gated_pairs.append(pair)
            
        return gated_pairs

    async def _extract_pair(
        self,
        candidate: _DenseCandidate,
        graph_store: GraphReader,
        schema: SchemaConfig,
    ) -> L2Triple | None:
        """Run the full rerank-and-extract pipeline on a candidate pair."""
        entity_a, entity_b = candidate.entity_a, candidate.entity_b

        async def _fetch_envelopes(depth: int) -> tuple[SubGraph, SubGraph]:
            return await asyncio.gather(
                self.get_structural_neighborhood(entity_a, graph_store, depth=depth),
                self.get_structural_neighborhood(entity_b, graph_store, depth=depth),
            )

        # 1. Fetch contextual neighborhood envelopes for both entities
        try:
            env_a, env_b = await _fetch_envelopes(self.config.subgraph_depth)
        except Exception as exc:
            logger.warning(
                "Failed to fetch envelopes for pair (%s, %s): %s",
                entity_a.name,
                entity_b.name,
                exc,
            )
            return None

        # 2. Rerank using cross-encoder
        try:
            initial_reranker_input = _reranker_input_summary(
                self.reranker,
                entity_a,
                env_a,
                entity_b,
                env_b,
            )
            initial_reranker_payload = _reranker_trace_payload(
                entity_a,
                env_a,
                entity_b,
                env_b,
            )
            with self.trace_sink.span(
                name="phase3.dense.rerank",
                input={
                    "entity_a": _entity_summary(entity_a),
                    "entity_b": _entity_summary(entity_b),
                    "env_a": _subgraph_summary(env_a),
                    "env_b": _subgraph_summary(env_b),
                    "requested_subgraph_depth": self.config.subgraph_depth,
                    "reranker_input": initial_reranker_input,
                    "reranker_payload": initial_reranker_payload,
                    "threshold": self.config.reranker_threshold,
                },
                enabled=self.config.trace_dense_retrieval,
            ) as span:
                recovery_attempts: list[dict[str, object]] = []
                retry_index = 0
                while True:
                    reranker_input = _reranker_input_summary(
                        self.reranker,
                        entity_a,
                        env_a,
                        entity_b,
                        env_b,
                    )
                    try:
                        # Align with RelationReranker protocol:
                        # (entity_a, env_a, entity_b, env_b)
                        rerank_score = await self.reranker.score_relation(
                            entity_a,
                            env_a,
                            entity_b,
                            env_b,
                        )
                        break
                    except Exception as exc:
                        if self.envelope_overflow_handler is None:
                            span.update(
                                output={
                                    "error": str(exc),
                                    "error_type": type(exc).__name__,
                                    "reranker_input": reranker_input,
                                    "recovery_attempts": recovery_attempts,
                                }
                            )
                            raise

                        try:
                            resolution = await _resolve_envelope_overflow(
                                self.envelope_overflow_handler,
                                EnvelopeOverflowContext(
                                    entity_a=entity_a,
                                    entity_b=entity_b,
                                    graph_store=graph_store,
                                    env_a=env_a,
                                    env_b=env_b,
                                    current_depth=min(env_a.depth, env_b.depth),
                                    reranker_input=reranker_input,
                                    error=exc,
                                    retry_index=retry_index,
                                    refetch_envelopes=_fetch_envelopes,
                                ),
                            )
                        except Exception as handler_exc:
                            span.update(
                                output={
                                    "error": str(handler_exc),
                                    "error_type": type(handler_exc).__name__,
                                    "reranker_input": reranker_input,
                                    "recovery_attempts": recovery_attempts,
                                }
                            )
                            raise

                        if resolution is None:
                            span.update(
                                output={
                                    "error": str(exc),
                                    "error_type": type(exc).__name__,
                                    "reranker_input": reranker_input,
                                    "recovery_attempts": recovery_attempts,
                                }
                            )
                            raise

                        recovery_attempts.append(
                            {
                                "retry_index": retry_index,
                                "error": str(exc),
                                "error_type": type(exc).__name__,
                                "strategy": resolution.strategy,
                                "metadata": resolution.metadata,
                                "reranker_input": reranker_input,
                            }
                        )
                        logger.info(
                            "Recovered Phase 3 reranker overflow for pair (%s, %s) "
                            "using %s",
                            entity_a.name,
                            entity_b.name,
                            resolution.strategy,
                        )
                        env_a, env_b = resolution.env_a, resolution.env_b
                        retry_index += 1

                span.update(
                    output={
                        "rerank_score": rerank_score,
                        "accepted": rerank_score >= self.config.reranker_threshold,
                        "reranker_input": _reranker_input_summary(
                            self.reranker,
                            entity_a,
                            env_a,
                            entity_b,
                            env_b,
                        ),
                        "recovery_attempts": recovery_attempts,
                    }
                )
            
            # Emit reranker score event
            self.event_emitter.emit(RerankerScoreAssigned(
                candidate_pair=(entity_a.id, entity_b.id),
                score=rerank_score,
                accepted=rerank_score >= self.config.reranker_threshold,
                threshold=self.config.reranker_threshold,
                entity_a=_entity_summary(entity_a),
                entity_b=_entity_summary(entity_b),
                reranker_input=_reranker_input_summary(
                    self.reranker,
                    entity_a,
                    env_a,
                    entity_b,
                    env_b,
                ),
                reranker_payload=(
                    _reranker_trace_payload(entity_a, env_a, entity_b, env_b)
                    if self.config.trace_dense_retrieval
                    else None
                ),
                recovery_attempts=recovery_attempts,
                run_id=None,
                phase="phase3_dense"
            ))
            
            # Emit rejection event if score is too low
            if rerank_score < self.config.reranker_threshold:
                self.event_emitter.emit(CandidateRejectedByThreshold(
                    candidate_pair=(entity_a.id, entity_b.id),
                    score=rerank_score,
                    threshold=self.config.reranker_threshold,
                    reason="Below reranker threshold",
                    run_id=None,
                    phase="phase3_dense"
                ))
                return None  # Skip LLM extraction if reranker says no
        except Exception as exc:
            logger.warning(
                "Phase 3 reranker failed for pair (%s, %s): %s",
                entity_a.name,
                entity_b.name,
                exc,
            )
            return None

        # 3. LLM Extraction: structured predict to extract schema-compliant edge
        try:
            envelope_text = format_envelope(env_a, env_b)
            with self.trace_sink.span(
                name="phase3.dense.llm_extract",
                input={
                    "merged_envelope": _merged_envelope_summary(env_a, env_b),
                },
                enabled=self.config.trace_dense_retrieval,
            ) as span:
                raw: GlobalRelationOutput = await self.llm.predict_structured(
                    GlobalRelationOutput,
                    self.config.global_relation_prompts,
                    strategy=self.config.global_relation_decoding_strategy,
                    entity_a_id=entity_a.id,
                    entity_a_name=entity_a.name,
                    entity_a_type=entity_a.label,
                    entity_a_context=entity_a.description or entity_a.name,
                    entity_b_id=entity_b.id,
                    entity_b_name=entity_b.name,
                    entity_b_type=entity_b.label,
                    entity_b_context=entity_b.description or entity_b.name,
                    relation_types=schema.relation_types_str(),
                    subgraph_envelope=envelope_text,
                )
                span.update(output=_global_relation_summary(raw))
            
            # Emit LLM decoding event
            self.event_emitter.emit(LLMRelationDecoded(
                candidate_pair=(entity_a.id, entity_b.id),
                relation=raw.relation,
                direction=raw.direction,
                confidence=raw.confidence,
                raw_response=raw.model_dump() if hasattr(raw, 'model_dump') else str(raw),
                run_id=None,
                phase="phase3_dense"
            ))
        except Exception as exc:
            logger.warning(
                "Phase 3 LLM call failed for pair (%s, %s): %s",
                entity_a.name,
                entity_b.name,
                exc,
            )
            return None

        if raw.relation is None:
            return None

        # Validate relation type against schema
        if raw.relation not in schema.relation_types:
            logger.debug(
                "Discarded unknown relation type %r for pair (%s, %s)",
                raw.relation,
                entity_a.name,
                entity_b.name,
            )
            # Emit schema validation rejection event
            self.event_emitter.emit(SchemaValidationRejectedRelation(
                candidate_pair=(entity_a.id, entity_b.id),
                relation=raw.relation,
                reason=f"Unknown relation type: {raw.relation}",
                run_id=None,
                phase="phase3_dense"
            ))
            return None

        subj_id = entity_a.id if raw.direction == "A_to_B" else entity_b.id
        obj_id = entity_b.id if raw.direction == "A_to_B" else entity_a.id

        # Since this is global extraction, chunks may differ. 
        # We fallback to 'global' if they don't share a source chunk.
        common = set(entity_a.source_chunk_ids) & set(entity_b.source_chunk_ids)
        source_chunk_id = (
            next(iter(common))
            if common
            else "global"
        )

        triple = L2Triple(
            subject_id=subj_id,
            predicate=raw.relation,
            object_id=obj_id,
            confidence=raw.confidence,
            rerank_score=rerank_score,
            scope="global",
            source_chunk_id=source_chunk_id,
        )
        
        # Emit triple committed event
        self.event_emitter.emit(TripleCommitted(
            subject_id=triple.subject_id,
            predicate=triple.predicate,
            object_id=triple.object_id,
            confidence=triple.confidence,
            scope=triple.scope,
            source_chunk_id=triple.source_chunk_id,
            run_id=None,
            phase="phase3_dense"
        ))
        
        return triple


def _entity_summary(entity: L2Entity) -> dict[str, object]:
    """Return a compact entity summary for tracing.

    Parameters
    ----------
    entity
        Entity to summarize.

    Returns
    -------
    dict[str, object]
        Trace-safe entity fields.
    """
    return {
        "id": entity.id,
        "name": entity.name,
        "label": entity.label,
        "source_chunk_ids": list(entity.source_chunk_ids),
    }


def _candidate_summary(candidate: _DenseCandidate) -> dict[str, object]:
    """Return a compact dense candidate summary.

    Parameters
    ----------
    candidate
        Candidate pair to summarize.

    Returns
    -------
    dict[str, object]
        Candidate trace payload.
    """
    return {
        "dense_score": candidate.score,
        "entity_a": _entity_summary(candidate.entity_a),
        "entity_b": _entity_summary(candidate.entity_b),
    }


def _subgraph_summary(subgraph: SubGraph) -> dict[str, object]:
    """Return subgraph size metadata for tracing.

    Parameters
    ----------
    subgraph
        Subgraph envelope to summarize.

    Returns
    -------
    dict[str, object]
        Subgraph metadata without full context text.
    """
    metrics = _subgraph_text_metrics(subgraph)
    return {
        "center_id": subgraph.center_id,
        "node_count": len(subgraph.nodes),
        "triple_count": len(subgraph.triples),
        "depth": subgraph.depth,
        **metrics,
    }


def _merged_envelope_summary(env_a: SubGraph, env_b: SubGraph) -> dict[str, object]:
    """Return size metadata for the merged LLM envelope.

    Parameters
    ----------
    env_a
        First entity envelope.
    env_b
        Second entity envelope.

    Returns
    -------
    dict[str, object]
        Merged envelope size metadata.
    """
    merged_text = format_envelope(env_a, env_b)
    return {
        "node_count": len(env_a.nodes) + len(env_b.nodes),
        "triple_count": len(env_a.triples) + len(env_b.triples),
        **_text_size_metrics(merged_text),
        "env_a": _subgraph_summary(env_a),
        "env_b": _subgraph_summary(env_b),
    }


def _global_relation_summary(raw: GlobalRelationOutput) -> dict[str, object]:
    """Return a compact LLM extraction summary.

    Parameters
    ----------
    raw
        Structured LLM output.

    Returns
    -------
    dict[str, object]
        Trace-safe global relation extraction result.
    """
    return {
        "relation": raw.relation,
        "direction": raw.direction,
        "confidence": raw.confidence,
    }


async def _resolve_envelope_overflow(
    handler: EnvelopeOverflowHandler,
    context: EnvelopeOverflowContext,
) -> EnvelopeOverflowResolution | None:
    """Resolve an overflow handler result regardless of sync/async shape.

    Parameters
    ----------
    handler
        User-provided overflow handler.
    context
        Context for the current overflow.

    Returns
    -------
    EnvelopeOverflowResolution | None
        Resolved handler response.
    """
    result = handler(context)
    if inspect.isawaitable(result):
        return await result
    return result


def _reranker_input_summary(
    reranker: RelationReranker,
    entity_a: L2Entity,
    env_a: SubGraph,
    entity_b: L2Entity,
    env_b: SubGraph,
) -> dict[str, object]:
    """Build trace metadata for the current reranker input.

    Parameters
    ----------
    reranker
        Active reranker implementation.
    entity_a
        Query-side entity.
    env_a
        Query-side envelope.
    entity_b
        Document-side entity.
    env_b
        Document-side envelope.

    Returns
    -------
    dict[str, object]
        Size metadata for the reranker pair.
    """
    describe_input = getattr(reranker, "describe_relation_input", None)
    if callable(describe_input):
        return describe_input(entity_a, env_a, entity_b, env_b)

    query, doc_text = build_relation_reranker_inputs(
        entity_a,
        env_a,
        entity_b,
        env_b,
    )
    return summarize_reranker_text_pair(
        query,
        doc_text,
        max_length=getattr(reranker, "max_length", None),
    )


def _reranker_trace_payload(
    entity_a: L2Entity,
    env_a: SubGraph,
    entity_b: L2Entity,
    env_b: SubGraph,
) -> dict[str, str]:
    """Return the exact query/document texts sent to the reranker.

    Parameters
    ----------
    entity_a
        Query-side entity.
    env_a
        Query-side envelope.
    entity_b
        Document-side entity.
    env_b
        Document-side envelope.

    Returns
    -------
    dict[str, str]
        Serialized reranker query and document texts.
    """
    query, doc_text = build_relation_reranker_inputs(
        entity_a,
        env_a,
        entity_b,
        env_b,
    )
    return {
        "query": query,
        "document": doc_text,
    }


def _subgraph_text_metrics(subgraph: SubGraph) -> dict[str, object]:
    """Return serialized text size metadata for a single envelope.

    Parameters
    ----------
    subgraph
        Envelope to summarize.

    Returns
    -------
    dict[str, object]
        Character, byte, and line counts for the standalone envelope text.
    """
    empty_env = SubGraph(center_id="", nodes=[], triples=[], depth=0)
    text = format_envelope(subgraph, empty_env)
    return _text_size_metrics(text)


def _text_size_metrics(text: str) -> dict[str, int]:
    """Return simple serialized-text size metrics.

    Parameters
    ----------
    text
        Text to summarize.

    Returns
    -------
    dict[str, int]
        Character, byte, and line counts.
    """
    return {
        "char_count": len(text),
        "byte_count": len(text.encode("utf-8")),
        "line_count": text.count("\n") + 1 if text else 0,
    }
