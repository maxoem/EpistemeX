"""
TAGRelationExtractor — default GlobalRelationExtractor implementation.

Strategy (Text-Attributed Graph + Reranker):

1. Candidate blocking via shared source_chunk_ids:
   Entities that co-occur in the same chunk are structurally related in the TAG.
   This reduces the candidate space from O(N²) to O(E·k) where k is the average
   chunk co-occurrence count — avoiding an LLM call for every entity pair.
   Each entity is paired with at most `max_candidates_per_entity_pair` partners.

2. Subgraph envelope retrieval:
   For each candidate pair (A, B), retrieve the k-hop neighbourhood of each entity
   from the graph store. The merged envelope becomes the TAG-attributed context for
   the LLM decoding step.

3. LLM triple decoding:
   GLOBAL_RELATION_PROMPT + astructured_predict → GlobalRelationOutput.
   On parsing failure the pair is skipped (logged, not raised).

4. Noise filtering:
   Triples with confidence < Phase3Config.confidence_threshold are discarded.

This extractor is also used by Phase 4 ARC (get_structural_neighborhood is the shared
Graph-RAG primitive).
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from episteme_pipeline.config import Phase3Config
from episteme_pipeline.contracts.domain import (
    CandidatePair,
    L2Entity,
    L2Triple,
    SubGraph,
)
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.phases.phase3_global_relations.models import GlobalRelationOutput
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor
from episteme_pipeline.protocols.graph_store import GraphReader
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils import format_envelope

logger = logging.getLogger(__name__)


class TAGRelationExtractor(GlobalRelationExtractor):
    """
    Default GlobalRelationExtractor using TAG structural blocking + LLM decoding.

    The same instance is reused by Phase 4 ARC via get_structural_neighborhood().
    """

    def __init__(
        self, llm: Any, embedding_model: Any = None, config: Phase3Config | None = None
    ) -> None:
        """Initialize TAGRelationExtractor.

        Parameters
        ----------
        llm : Any
            Underlying language model facade or client.
        embedding_model : Any, optional
            Ignored; retained for call-site compatibility.
        config : Phase3Config or None, optional
            Configuration parameters for Phase 3.
        """
        self.llm = ensure_structured_llm(llm)
        self.config = config or Phase3Config()

    # ------------------------------------------------------------------
    # GlobalRelationExtractor interface
    # ------------------------------------------------------------------

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
        candidate_pairs = self._candidate_pairs(entities)
        logger.info(
            "Phase 3: %d entities → %d candidate pairs",
            len(entities),
            len(candidate_pairs),
        )

        tasks = [
            self._extract_pair(pair.entity_a, pair.entity_b, graph_store, schema)
            for pair in candidate_pairs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        triples: list[L2Triple] = []
        for pair, result in zip(candidate_pairs, results):
            if isinstance(result, Exception):
                logger.error(
                    "Phase 3 pair (%s, %s) failed: %s",
                    pair.entity_a.id,
                    pair.entity_b.id,
                    result,
                )
                continue
            if result is not None:
                triples.append(result)

        logger.info(
            "Phase 3: extracted %d global triples (confidence ≥ %.2f)",
            len(triples),
            self.config.global_relation_confidence_threshold,
        )
        return triples

    async def candidate_pairs(
        self, entities: list[L2Entity]
    ) -> list[CandidatePair]:
        """Generate candidate entity pairs via shared chunk blocking.

        Parameters
        ----------
        entities : list[L2Entity]
            Entities considered for candidate pairing.

        Returns
        -------
        list[CandidatePair]
            Candidate entity pairs.
        """
        return self._candidate_pairs(entities)

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
            Schema configuration.

        Returns
        -------
        L2Triple | None
            Extracted triple if validated, otherwise None.
        """
        return await self._extract_pair(pair.entity_a, pair.entity_b, graph_store, schema)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _candidate_pairs(
        self, entities: list[L2Entity]
    ) -> list[CandidatePair]:
        """
        Block on shared source_chunk_ids. For each entity, cap the number of
        candidate partners to `max_candidates_per_entity_pair` to prevent hub
        entities from blowing up the pair count.
        """
        chunk_to_entities: dict[str, list[L2Entity]] = defaultdict(list)
        sorted_entities = sorted(entities, key=lambda e: e.id)
        for entity in sorted_entities:
            for cid in sorted(entity.source_chunk_ids):
                chunk_to_entities[cid].append(entity)

        # partner_count[entity_id] tracks how many pairs we've already added
        partner_count: dict[str, int] = defaultdict(int)
        seen: set[tuple[str, str]] = set()
        pairs: list[CandidatePair] = []

        for cid in sorted(chunk_to_entities.keys()):
            chunk_entities = chunk_to_entities[cid]
            for i, a in enumerate(chunk_entities):
                for b in chunk_entities[i + 1 :]:
                    if a.id == b.id:
                        continue
                    key = (min(a.id, b.id), max(a.id, b.id))
                    if key in seen:
                        continue
                    if (
                        partner_count[a.id]
                        >= self.config.max_candidates_per_entity_pair
                        or partner_count[b.id]
                        >= self.config.max_candidates_per_entity_pair
                    ):
                        continue
                    seen.add(key)
                    pairs.append(CandidatePair(entity_a=a, entity_b=b))
                    partner_count[a.id] += 1
                    partner_count[b.id] += 1

        return pairs

    async def _extract_pair(
        self,
        entity_a: L2Entity,
        entity_b: L2Entity,
        graph_store: GraphReader,
        schema: SchemaConfig,
    ) -> L2Triple | None:
        env_a, env_b = await asyncio.gather(
            self.get_structural_neighborhood(
                entity_a, graph_store, depth=self.config.subgraph_depth
            ),
            self.get_structural_neighborhood(
                entity_b, graph_store, depth=self.config.subgraph_depth
            ),
        )

        envelope_text = format_envelope(env_a, env_b)

        try:
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

        if raw.confidence < self.config.global_relation_confidence_threshold:
            logger.debug(
                "Discarded (%s)-[%s]->(%s): confidence %.2f < threshold %.2f",
                entity_a.name,
                raw.relation,
                entity_b.name,
                raw.confidence,
                self.config.global_relation_confidence_threshold,
            )
            return None

        # Validate relation type against schema
        if raw.relation not in schema.relation_types:
            logger.debug(
                "Discarded unknown relation type %r for pair (%s, %s)",
                raw.relation,
                entity_a.name,
                entity_b.name,
            )
            return None

        subj_id = entity_a.id if raw.direction == "A_to_B" else entity_b.id
        obj_id = entity_b.id if raw.direction == "A_to_B" else entity_a.id

        # Prefer a shared chunk as the source; fall back to entity_a's first chunk
        common = set(entity_a.source_chunk_ids) & set(entity_b.source_chunk_ids)
        source_chunk_id = (
            next(iter(common))
            if common
            else (
                entity_a.source_chunk_ids[0] if entity_a.source_chunk_ids else "global"
            )
        )

        return L2Triple(
            subject_id=subj_id,
            predicate=raw.relation,
            object_id=obj_id,
            confidence=raw.confidence,
            scope="global",
            source_chunk_id=source_chunk_id,
        )
