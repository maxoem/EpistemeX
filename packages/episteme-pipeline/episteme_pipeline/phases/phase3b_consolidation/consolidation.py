"""
LatentGraphConsolidation — fast mathematical sweep for parallel collisions (Phase 3b).

Uses vector embeddings of minted Layer 2 nodes to find and merge duplicates
caused by parallel processing. Two nodes are merged if they are within a strict
Euclidean/Cosine distance threshold and share highly overlapping Phase 3 relation edges.
"""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np

from episteme_pipeline.phases.phase3b_consolidation.clustering import (
    BorderlinePairVerifier,
    CanonicalRepresentativeElector,
)
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.fusion import InstanceFusion
from episteme_pipeline.protocols.graph_store import FusionGraph

logger = logging.getLogger(__name__)


def _union_find_components(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """Compute connected components of a graph using Union-Find.

    Parameters
    ----------
    n : int
        The number of nodes in the graph (indexed from 0 to n-1).
    edges : list[tuple[int, int]]
        A list of undirected edges represented as pairs of node indices.

    Returns
    -------
    list[list[int]]
        A list of lists, where each sublist contains the node indices belonging to
        the same connected component.
    """
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    for i, j in edges:
        union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


class LatentGraphConsolidation(InstanceFusion):
    """Mathematical sweep over dense vectors to merge duplicate Layer 2 nodes.

    Parameters
    ----------
    embedding_model : object, optional
        The embedding model used to project textual envelopes into vector space.
    dense_similarity_threshold : float, default 0.85
        The minimum cosine similarity required to consider two nodes as duplicates.
    relation_overlap_threshold : float, default 0.8
        The minimum Jaccard similarity threshold for 1-hop relation edge overlap.
    decision_engine : DecisionEngine or None, default None
        Optional calibrated decision engine for borderline pair verification and
        canonical representative election.
    enable_jev_cluster_verification : bool, default False
        Whether to enable Jev decision engine verification for borderline pairs.
    borderline_similarity_lower : float, default 0.75
        Lower bound of the borderline vector similarity band.
    borderline_similarity_upper : float, default 0.88
        Upper bound of the borderline vector similarity band.
    merge_confidence_threshold : float, default 0.80
        Empirical accuracy threshold required to confirm a borderline merge.
    conformal_merge_alpha : float, default 0.05
        Conformal significance level for borderline merge prediction sets.
    """

    def __init__(
        self,
        embedding_model=None,
        dense_similarity_threshold: float = 0.85,
        relation_overlap_threshold: float = 0.8,
        borderline_similarity_lower: float = 0.75,
        borderline_similarity_upper: float = 0.88,
        verifier: BorderlinePairVerifier | None = None,
        canonical_elector: CanonicalRepresentativeElector | None = None,
        decision_engine: DecisionEngine | None = None,
        enable_jev_cluster_verification: bool = False,
        merge_confidence_threshold: float = 0.80,
        conformal_merge_alpha: float = 0.05,
    ) -> None:
        self.embedding_model = embedding_model
        self.dense_similarity_threshold = dense_similarity_threshold
        self.relation_overlap_threshold = relation_overlap_threshold
        self.borderline_similarity_lower = borderline_similarity_lower
        self.borderline_similarity_upper = borderline_similarity_upper

        if verifier is not None:
            self.verifier = verifier
        elif enable_jev_cluster_verification and decision_engine is not None:
            self.verifier = BorderlinePairVerifier(
                decision_engine=decision_engine,
                confidence_threshold=merge_confidence_threshold,
                conformal_alpha=conformal_merge_alpha,
            )
        else:
            self.verifier = None

        if canonical_elector is not None:
            self.canonical_elector = canonical_elector
        elif enable_jev_cluster_verification and decision_engine is not None:
            self.canonical_elector = CanonicalRepresentativeElector(decision_engine=decision_engine)
        else:
            self.canonical_elector = CanonicalRepresentativeElector()

    @classmethod
    def from_config(
        cls,
        config: Any,
        embedding_model=None,
        decision_engine: DecisionEngine | None = None,
    ) -> LatentGraphConsolidation:
        """Construct LatentGraphConsolidation from Phase3bConfig and decision engine.

        Parameters
        ----------
        config : Phase3bConfig
            Phase 3b configuration.
        embedding_model : object, optional
            Embedding model for projecting textual envelopes into vector space.
        decision_engine : DecisionEngine or None, default None
            Calibrated decision engine for borderline verification and canonical election.

        Returns
        -------
        LatentGraphConsolidation
            Wired instance.
        """
        verifier = None
        canonical_elector = None
        if config.verification.enabled and decision_engine is not None:
            verifier = BorderlinePairVerifier.from_config(config.verification, decision_engine)
            canonical_elector = CanonicalRepresentativeElector(decision_engine=decision_engine)

        return cls(
            embedding_model=embedding_model,
            dense_similarity_threshold=config.dense_similarity_threshold,
            relation_overlap_threshold=config.relation_overlap_threshold,
            borderline_similarity_lower=config.verification.similarity_lower,
            borderline_similarity_upper=config.verification.similarity_upper,
            verifier=verifier,
            canonical_elector=canonical_elector,
        )

    async def _get_relations_for_entity(self, entity_id: str, graph_store: FusionGraph) -> set[str]:
        """Fetch the relation signatures for a given entity.

        Parameters
        ----------
        entity_id : str
            The unique identifier of the entity.
        graph_store : FusionGraph
            The graph store containing the entity neighborhood.

        Returns
        -------
        set[str]
            A set of string signatures representing incoming and outgoing relations.
        """
        env = await graph_store.get_neighborhood(entity_id, depth=1)
        if not env.nodes and not env.triples:
            return set()
        
        signatures = set()
        for t in env.triples:
            if t.subject_id == entity_id:
                signatures.add(f"OUT:{t.predicate}:{t.object_id}")
            elif t.object_id == entity_id:
                signatures.add(f"IN:{t.predicate}:{t.subject_id}")
        return signatures

    def _jaccard(self, set1: set[str], set2: set[str]) -> float:
        """Compute the Jaccard similarity coefficient between two sets.

        Parameters
        ----------
        set1 : set[str]
            The first set of strings.
        set2 : set[str]
            The second set of strings.

        Returns
        -------
        float
            The Jaccard similarity index, ranging from 0.0 to 1.0. Returns 1.0 if
            both sets are empty.
        """
        if not set1 or not set2:
            # If both are empty, Jaccard is mathematically 1.0, but semantically 
            # we return 0.0 for graph merging (isolated nodes aren't automatically identical).
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return float(intersection) / union

    async def fuse(self, graph_store: FusionGraph) -> dict[str, str]:
        """Find and merge duplicate Layer 2 nodes in the graph.

        Finds groups of entities with the same label that meet both the dense similarity
        threshold and structural relation overlap threshold, then maps duplicates to a
        canonical entity.

        Parameters
        ----------
        graph_store : FusionGraph
            The graph store containing Layer 2 entities and relation edges.

        Returns
        -------
        dict[str, str]
            A dictionary mapping duplicate entity IDs to their canonical entity ID.
        """
        if self.embedding_model is None:
            logger.warning("LatentGraphConsolidation: no embedding_model — returning empty map.")
            return {}

        entities = await graph_store.get_entities()
        if len(entities) < 2:
            return {}

        # 1. Embed textual envelopes
        texts = [e.textual_envelope or e.name for e in entities]
        embeddings_list = await self.embedding_model.aget_text_embedding_batch(texts)
        embeddings = np.array(embeddings_list)

        # Normalize for cosine similarity via dot product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        # Avoid division by zero
        norms[norms == 0] = 1e-10
        embeddings_normalized = embeddings / norms
        sim_matrix = np.dot(embeddings_normalized, embeddings_normalized.T)

        n = len(entities)
        edges = []

        definite_threshold = (
            self.borderline_similarity_upper
            if self.verifier is not None
            else self.dense_similarity_threshold
        )

        # 2. Find candidates passing definite threshold or borderline verification
        for i in range(n):
            for j in range(i + 1, n):
                # Only compare entities of the same label
                if entities[i].label != entities[j].label:
                    continue

                sim = float(sim_matrix[i, j])

                if sim >= definite_threshold:
                    rel_i = await self._get_relations_for_entity(entities[i].id, graph_store)
                    rel_j = await self._get_relations_for_entity(entities[j].id, graph_store)
                    if self._jaccard(rel_i, rel_j) >= self.relation_overlap_threshold:
                        edges.append((i, j))
                elif self.verifier is not None and sim >= self.borderline_similarity_lower:
                    rel_i = await self._get_relations_for_entity(entities[i].id, graph_store)
                    rel_j = await self._get_relations_for_entity(entities[j].id, graph_store)
                    selected, emp_acc, pred_set = await self.verifier.verify(
                        entities[i],
                        entities[j],
                        relation_signatures_a=rel_i,
                        relation_signatures_b=rel_j,
                    )
                    is_singleton = (pred_set == ["IDENTICAL_MERGE"])
                    is_high_conf = (
                        selected == "IDENTICAL_MERGE"
                        and emp_acc >= self.verifier.confidence_threshold
                    )
                    if is_singleton or is_high_conf:
                        edges.append((i, j))

        # 4. Cluster connected components
        clusters = _union_find_components(n, edges)

        # 5. Build fused map
        fused_map: dict[str, str] = {}
        for cluster in clusters:
            if len(cluster) < 2:
                continue

            cluster_entities = [entities[idx] for idx in cluster]
            canonical = await self.canonical_elector.elect(cluster_entities)

            for e in cluster_entities:
                if e.id != canonical.id:
                    fused_map[e.id] = canonical.id

        return fused_map
