"""
TAGARCClassifier — default ARCClassifier implementation.

Global Argument Relation Classification via TAG subgraph retrieval + LLM.

Reuses GlobalRelationExtractor.get_structural_neighborhood() (from Phase 3) to
retrieve the k-hop graph neighbourhood of each argument component. The merged
envelope becomes the context for the LLM stance decision (SUPPORTS / ATTACKS).

Candidate blocking: components from DIFFERENT chunks are paired (intra-chunk
relations are already handled by ACC). Each component is paired with at most
`arc_max_candidates_per_component` partners from other chunks.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

import numpy as np

from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation
from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.phases.phase4_argument_mining.models import ARCRelationOutput
from episteme_pipeline.phases.phase4_argument_mining.pairing import (
    build_cross_chunk_candidate_pairs,
)
from episteme_pipeline.protocols.argument_mining import ARCClassifier
from episteme_pipeline.protocols.extractors import GlobalRelationExtractor
from episteme_pipeline.protocols.graph_store import GraphReader, PhaseCheckpointStore
from episteme_pipeline.runtime.batch_executor import CheckpointedBatchExecutor
from episteme_pipeline.schema.default_schema import SchemaConfig
from episteme_pipeline.utils import format_envelope
from episteme_pipeline.utils.similarity import (
    cosine_similarity_matrix,
    csls_similarity_matrix,
    dynamic_k_effective,
    z_score_normalize,
)

logger = logging.getLogger(__name__)


class TAGARCClassifier(ARCClassifier):
    """
    Default ARCClassifier using TAG subgraph retrieval and LLM stance decoding.
    
    This class orchestrates the classification of cross-chunk argument relations
    by pairing theory atoms and predicting relations via an LLM.
    """

    def __init__(
        self,
        llm: Any,
        embedding_model: Any = None,
        prompts: Any = None,
        strategy: str = "direct_constrained",
        confidence_threshold: float = 0.65,
        subgraph_depth: int = 2,
        max_candidates_per_component: int = 10,
        use_priority_rank: bool = False,
        use_csls: bool = True,
        csls_k_nearest: int = 10,
        use_adaptive_k: bool = True,
        adaptive_k_gamma: float = 2.0,
        adaptive_k_min: int = 2,
        z_score_threshold: float | None = None,
        batch_size: int = 20,
    ) -> None:
        """
        Initialize the TAGARCClassifier.

        Parameters
        ----------
        llm : Any
            The language model used for structural prediction.
        embedding_model : Any, optional
            The embedding model for computing dense representations, by default None.
        prompts : Any, optional
            The prompt template configuration, by default None.
        strategy : str, optional
            The prediction strategy, by default "direct_constrained".
        confidence_threshold : float, optional
            The minimum LLM confidence to accept a relation, by default 0.65.
        subgraph_depth : int, optional
            The depth of structural neighborhood to retrieve, by default 2.
        max_candidates_per_component : int, optional
            The max number of cross-chunk partners per component, by default 10.
        use_priority_rank : bool, optional
            If True, falls back to epistemic rank instead of embeddings, by default False.
        use_csls : bool, default True
            Whether to use Cross-Domain Similarity Local Scaling.
        csls_k_nearest : int, default 10
            Neighborhood size for CSLS local scaling.
        use_adaptive_k : bool, default True
            Whether to dynamically scale candidate degree K_eff with sqrt(N).
        adaptive_k_gamma : float, default 2.0
            Scaling multiplier for dynamic K_eff.
        adaptive_k_min : int, default 2
            Minimum candidate degree cap.
        z_score_threshold : float | None, optional
            Optional standardized z-score cutoff for candidate pairs.
        """
        self.llm = ensure_structured_llm(llm)
        self.embedding_model = embedding_model
        self.prompts = prompts
        self.strategy = strategy
        self.confidence_threshold = confidence_threshold
        self.subgraph_depth = subgraph_depth
        self.max_candidates_per_component = max_candidates_per_component
        self.use_priority_rank = use_priority_rank
        self.use_csls = use_csls
        self.csls_k_nearest = csls_k_nearest
        self.use_adaptive_k = use_adaptive_k
        self.adaptive_k_gamma = adaptive_k_gamma
        self.adaptive_k_min = adaptive_k_min
        self.z_score_threshold = z_score_threshold
        self.batch_size = max(1, batch_size)

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic TAG ARC classifier configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing thresholds, subgraph depth, strategy,
            and fingerprints of LLM and embedding model.
        """
        from enum import Enum
        from episteme_pipeline.runs.fingerprints import fingerprint_method

        strategy_str = self.strategy.value if isinstance(self.strategy, Enum) else str(self.strategy)
        return {
            "class": self.__class__.__name__,
            "strategy": strategy_str,
            "confidence_threshold": self.confidence_threshold,
            "subgraph_depth": self.subgraph_depth,
            "max_candidates_per_component": self.max_candidates_per_component,
            "use_priority_rank": self.use_priority_rank,
            "use_csls": self.use_csls,
            "csls_k_nearest": self.csls_k_nearest,
            "use_adaptive_k": self.use_adaptive_k,
            "adaptive_k_gamma": self.adaptive_k_gamma,
            "adaptive_k_min": self.adaptive_k_min,
            "z_score_threshold": self.z_score_threshold,
            "llm": fingerprint_method(self.llm),
            "embedding_model": fingerprint_method(self.embedding_model),
        }

    async def classify_global(
        self,
        local_components: list[TheoryAtom],
        local_relations: list[TheoryRelation],
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor | None = None,
        schema: SchemaConfig | None = None,
    ) -> list[TheoryRelation]:
        """
        Predict cross-chunk argument relations using the LLM.

        Parameters
        ----------
        local_components : list[TheoryAtom]
            The list of theory atoms to pair up.
        local_relations : list[TheoryRelation]
            The relations already extracted locally.
        graph_store : GraphReader
            The graph database reader to fetch subgraph neighborhoods.
        global_extractor : GlobalRelationExtractor | None, optional
            Deprecated / optional global extractor. Subgraphs are fetched directly
            from graph_store.
        schema : SchemaConfig | None, optional
            The pipeline schema definitions. If None, defaults to SchemaConfig().

        Returns
        -------
        list[TheoryRelation]
            A list of successfully predicted global relations.
        """
        effective_schema = schema or SchemaConfig()
        candidate_pairs = await self._cross_chunk_pairs(local_components, effective_schema)
        logger.info(
            "ARC: %d components → %d cross-chunk candidate pairs",
            len(local_components),
            len(candidate_pairs),
        )

        return await self.classify_pairs(
            candidate_pairs,
            graph_store,
            schema=effective_schema,
            global_extractor=global_extractor,
        )

    async def classify_pairs(
        self,
        pairs: list[tuple[TheoryAtom, TheoryAtom]],
        graph_store: GraphReader,
        schema: SchemaConfig | None = None,
        global_extractor: GlobalRelationExtractor | None = None,
    ) -> list[TheoryRelation]:
        """Predict cross-chunk argument relations for specific candidate pairs using the LLM.

        Parameters
        ----------
        pairs : list of tuple of (TheoryAtom, TheoryAtom)
            Candidate argument component pairs to evaluate.
        graph_store : GraphReader
            The graph database reader to fetch subgraph neighborhoods.
        schema : SchemaConfig or None, optional
            The pipeline schema definitions. If None, defaults to SchemaConfig().
        global_extractor : GlobalRelationExtractor or None, optional
            Optional extractor for structural neighborhoods.

        Returns
        -------
        list of TheoryRelation
            A list of successfully predicted global relations for evaluated pairs.
        """
        if not pairs:
            return []
        effective_schema = schema or SchemaConfig()
        checkpoint_store = (
            graph_store if isinstance(graph_store, PhaseCheckpointStore) else None
        )

        async def _eval_pair(pair: tuple[TheoryAtom, TheoryAtom]) -> TheoryRelation | None:
            return await self._classify_pair(
                pair[0],
                pair[1],
                graph_store,
                effective_schema,
                global_extractor=global_extractor,
            )

        executor = CheckpointedBatchExecutor[
            tuple[TheoryAtom, TheoryAtom], TheoryRelation
        ](
            checkpoint_store=checkpoint_store,
            phase_tag="phase4_arc",
            batch_size=self.batch_size,
            item_key_fn=lambda pair: f"arc::{min(pair[0].id, pair[1].id)}::{max(pair[0].id, pair[1].id)}",
            process_item_fn=_eval_pair,
            guard_systematic_failure=False,
        )
        res = await executor.execute(pairs)
        global_relations = res.outputs

        logger.info(
            "ARC: extracted %d global argument relations for %d evaluated pairs",
            len(global_relations),
            len(pairs),
        )
        return global_relations

    async def _cross_chunk_pairs(
        self, components: list[TheoryAtom], schema: SchemaConfig
    ) -> list[tuple[TheoryAtom, TheoryAtom]]:
        """
        Determine which pairs of atoms should be considered for global relations.

        Depending on configuration, this delegates to either a dense embedding
        similarity search or an epistemic priority rank.

        Parameters
        ----------
        components : list[TheoryAtom]
            The components to pair.
        schema : SchemaConfig
            The pipeline schema definitions.

        Returns
        -------
        list[tuple[TheoryAtom, TheoryAtom]]
            The selected pairs of components.
        """
        if len(components) < 2:
            return []

        if self.use_priority_rank or self.embedding_model is None:
            return self._get_pairs_by_priority(components, schema)
        return await self._get_pairs_by_embedding(components)

    def _get_pairs_by_priority(
        self, components: list[TheoryAtom], schema: SchemaConfig
    ) -> list[tuple[TheoryAtom, TheoryAtom]]:
        """
        Generate pairs based on an epistemic priority ranking of component types.

        Parameters
        ----------
        components : list[TheoryAtom]
            The components to pair.
        schema : SchemaConfig
            The schema providing the component type hierarchy.

        Returns
        -------
        list[tuple[TheoryAtom, TheoryAtom]]
            The selected pairs of components.
        """
        return build_cross_chunk_candidate_pairs(
            components, schema, max_candidates_per_component=self.max_candidates_per_component
        )

    async def _get_pairs_by_embedding(
        self, components: list[TheoryAtom]
    ) -> list[tuple[TheoryAtom, TheoryAtom]]:
        """
        Generate pairs based on dense embedding cosine similarity.

        Parameters
        ----------
        components : list[TheoryAtom]
            The components to pair.

        Returns
        -------
        list[tuple[TheoryAtom, TheoryAtom]]
            The selected pairs of components, ordered by highest similarity.
        """
        partner_count: dict[str, int] = defaultdict(int)
        seen: set[tuple[str, str]] = set()
        pairs: list[tuple[TheoryAtom, TheoryAtom]] = []

        texts = [c.text for c in components]
        embeddings = await self.embedding_model.aget_text_embedding_batch(texts)
        
        vectors = np.array(embeddings)
        if self.use_csls:
            sim_matrix = csls_similarity_matrix(vectors, k_nearest=self.csls_k_nearest)
        else:
            sim_matrix = cosine_similarity_matrix(vectors)
        
        num_comp = len(components)
        if self.use_adaptive_k:
            k_eff = dynamic_k_effective(
                n=num_comp,
                k_min=self.adaptive_k_min,
                k_max=self.max_candidates_per_component,
                gamma=self.adaptive_k_gamma,
            )
        else:
            k_eff = self.max_candidates_per_component

        z_scores = (
            z_score_normalize(sim_matrix, symmetric=True)
            if self.z_score_threshold is not None
            else None
        )

        i_indices, j_indices = np.triu_indices(num_comp, k=1)
        similarities = sim_matrix[i_indices, j_indices]
        
        sorted_idx = np.argsort(similarities)[::-1]
        
        for idx in sorted_idx:
            i = i_indices[idx]
            j = j_indices[idx]
            a = components[i]
            b = components[j]
            
            if a.source_chunk_id == b.source_chunk_id:
                continue
                
            if self.z_score_threshold is not None and z_scores is not None:
                if z_scores[i, j] < self.z_score_threshold:
                    continue

            key = (min(a.id, b.id), max(a.id, b.id))
            if key in seen:
                continue
                
            if (
                partner_count[a.id] >= k_eff
                or partner_count[b.id] >= k_eff
            ):
                continue
                
            seen.add(key)
            pairs.append((a, b))
            partner_count[a.id] += 1
            partner_count[b.id] += 1

        return pairs

    async def _classify_pair(
        self,
        component_a: TheoryAtom,
        component_b: TheoryAtom,
        graph_store: GraphReader,
        global_extractor: GlobalRelationExtractor,
        schema: SchemaConfig,
    ) -> TheoryRelation | None:
        """
        Predict the argument relation between two specific theory atoms.

        This fetches the structural neighborhood for both components, merges them
        into an envelope, and prompts the LLM to decide the stance.

        Parameters
        ----------
        component_a : TheoryAtom
            The first theory atom.
        component_b : TheoryAtom
            The second theory atom.
        graph_store : GraphReader
            The graph storage client.
        schema : SchemaConfig
            The schema to validate relation types against.
        global_extractor : GlobalRelationExtractor | None, optional
            Deprecated / optional global extractor. Subgraphs are fetched directly
            from graph_store.

        Returns
        -------
        TheoryRelation | None
            The predicted relation, or None if no valid relation was found.
        """
        env_a, env_b = await asyncio.gather(
            graph_store.get_neighborhood(component_a.id, depth=self.subgraph_depth),
            graph_store.get_neighborhood(component_b.id, depth=self.subgraph_depth),
        )

        envelope_text = format_envelope(env_a, env_b, include_description=False)

        try:
            raw: ARCRelationOutput = await self.llm.predict_structured(
                ARCRelationOutput,
                self.prompts,
                strategy=self.strategy,
                component_a_id=component_a.id,
                component_a_type=component_a.component_type,
                component_a_text=component_a.text,
                component_b_id=component_b.id,
                component_b_type=component_b.component_type,
                component_b_text=component_b.text,
                subgraph_envelope=envelope_text,
                argument_relation_types=schema.argument_relation_types_str(),
            )
        except Exception as exc:
            logger.warning(
                "ARC LLM call failed for (%s, %s): %s",
                component_a.id,
                component_b.id,
                exc,
            )
            return None

        if raw.relation_type is None:
            return None

        if raw.relation_type not in schema.argument_relation_types:
            logger.warning(
                "ARC: discarded unknown relation type %r for pair (%s, %s)",
                raw.relation_type,
                component_a.id,
                component_b.id,
            )
            return None

        if raw.confidence < self.confidence_threshold:
            return None

        source_id = component_a.id if raw.direction == "A_to_B" else component_b.id
        target_id = component_b.id if raw.direction == "A_to_B" else component_a.id

        return TheoryRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=raw.relation_type,
            confidence=raw.confidence,
            scope="global",
            weight=raw.weight if raw.weight is not None else raw.confidence,
        )
