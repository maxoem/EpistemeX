"""
Leiden Theory Clustering — global structural community detection.

Constructs a NetworkX graph from all Entity nodes and their relationships,
then applies the Hierarchical Leiden algorithm (via graspologic) to detect
nested communities of theories and concepts.

Communities are stored back into the graph as `Community` nodes.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import networkx as nx

from episteme_pipeline.contracts.domain import L2Entity, L2Triple, TheoryAtom, TheoryRelation
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.fusion import TheoryFusion
from episteme_pipeline.protocols.graph_store import FusionGraph

if TYPE_CHECKING:
    from episteme_pipeline.config import Phase5Config
    from episteme_pipeline.phases.phase5_fusion.argument_clustering import InterDocumentClusterVerifier

logger = logging.getLogger(__name__)


class LeidenTheoryClustering(TheoryFusion):
    """Applies Hierarchical Leiden community detection to the entity graph.

    Parameters
    ----------
    max_cluster_size : int, default 100
        Maximum size of clusters produced by hierarchical Leiden.
    cluster_layer : str, default "theory_atoms"
        Target graph layer to cluster ("theory_atoms", "l2_entities", or "both").
    cluster_verifier : InterDocumentClusterVerifier or None, default None
        Optional inter-document cluster verifier for gating candidate communities.
    decision_engine : DecisionEngine or None, default None
        Optional decision engine fallback.
    enable_fusion_gating : bool, default False
        Whether fusion gating is enabled (when constructing verifier directly).
    conformal_alpha : float, default 0.05
        Conformal error significance level.
    fusion_confidence_threshold : float, default 0.85
        Calibrated empirical accuracy threshold.
    stochastic_audit_rate : float, default 0.02
        Stochastic false-negative audit rate.
    """

    def __init__(
        self,
        max_cluster_size: int = 100,
        cluster_layer: str = "theory_atoms",
        cluster_verifier: InterDocumentClusterVerifier | None = None,
        decision_engine: DecisionEngine | None = None,
        enable_fusion_gating: bool = False,
        conformal_alpha: float = 0.05,
        fusion_confidence_threshold: float = 0.85,
        stochastic_audit_rate: float = 0.02,
    ) -> None:
        self.max_cluster_size = max_cluster_size
        self.cluster_layer = cluster_layer
        if cluster_verifier is not None:
            self.cluster_verifier = cluster_verifier
        elif enable_fusion_gating and decision_engine is not None:
            from episteme_pipeline.phases.phase5_fusion.argument_clustering import InterDocumentClusterVerifier

            self.cluster_verifier = InterDocumentClusterVerifier(
                decision_engine=decision_engine,
                confidence_threshold=fusion_confidence_threshold,
                conformal_alpha=conformal_alpha,
                audit_rate=stochastic_audit_rate,
            )
        else:
            self.cluster_verifier = None

    @classmethod
    def from_config(
        cls,
        config: Phase5Config,
        decision_engine: DecisionEngine | None = None,
        cluster_verifier: InterDocumentClusterVerifier | None = None,
    ) -> LeidenTheoryClustering:
        """Construct LeidenTheoryClustering from Phase5Config and decision engine.

        Parameters
        ----------
        config : Phase5Config
            Phase 5 configuration parameters.
        decision_engine : DecisionEngine or None, default None
            Calibrated decision engine for cluster verification.
        cluster_verifier : InterDocumentClusterVerifier or None, default None
            Optional pre-configured cluster verifier.

        Returns
        -------
        LeidenTheoryClustering
            Configured LeidenTheoryClustering instance.
        """
        if cluster_verifier is None and config.gating.enabled and decision_engine is not None:
            from episteme_pipeline.phases.phase5_fusion.argument_clustering import InterDocumentClusterVerifier

            cluster_verifier = InterDocumentClusterVerifier.from_config(
                config.gating,
                decision_engine,
            )
        return cls(
            cluster_layer=config.cluster_layer,
            cluster_verifier=cluster_verifier,
        )

    async def fuse(self, graph_store: FusionGraph) -> None:
        if self.cluster_layer in ("l2_entities", "both"):
            logger.info("Phase 5: Fetching global entities and relations for Leiden clustering.")
            entities = await graph_store.get_entities()
            triples = await graph_store.get_all_entity_triples()
            if entities and triples:
                await self._run_leiden_for_nodes(graph_store, entities, triples, "L2Entity")
            else:
                logger.info("Phase 5: Entity graph is empty, skipping Leiden clustering for L2Entities.")

        if self.cluster_layer in ("theory_atoms", "both"):
            logger.info("Phase 5: Fetching TheoryAtoms and TheoryRelations for Leiden clustering.")
            atoms = await graph_store.get_theory_atoms()
            relations = await graph_store.get_all_theory_relations()
            if atoms and relations:
                await self._run_leiden_for_nodes(graph_store, atoms, relations, "TheoryAtom")
            else:
                logger.info("Phase 5: Theory graph is empty, skipping Leiden clustering for TheoryAtoms.")

    async def _run_leiden_for_nodes(self, graph_store: FusionGraph, nodes, edges, node_type: str) -> None:
        # Build NetworkX Graph
        G = nx.Graph()

        # Add nodes
        for n in nodes:
            if isinstance(n, L2Entity):
                label = n.label
            elif isinstance(n, TheoryAtom):
                label = n.component_type
            else:
                label = node_type
            G.add_node(n.id, label=label)

        # Add edges (undirected for standard Leiden)
        for e in edges:
            if isinstance(e, L2Triple):
                subj_id, obj_id = e.subject_id, e.object_id
                conf = e.confidence
            elif isinstance(e, TheoryRelation):
                subj_id, obj_id = e.source_id, e.target_id
                conf = e.confidence
            else:
                subj_id = getattr(e, "subject_id", getattr(e, "source_id", None))
                obj_id = getattr(e, "object_id", getattr(e, "target_id", None))
                conf = getattr(e, "confidence", 1.0)
            if subj_id is None or obj_id is None:
                continue

            conf_val = conf if conf is not None else 1.0

            if G.has_edge(subj_id, obj_id):
                G[subj_id][obj_id]["weight"] += conf_val
            else:
                G.add_edge(subj_id, obj_id, weight=conf_val)

        logger.info(
            "Phase 5: NetworkX graph for %s built with %d nodes and %d edges.",
            node_type,
            G.number_of_nodes(),
            G.number_of_edges(),
        )

        # Run Hierarchical Leiden
        logger.info("Phase 5: Running Hierarchical Leiden...")
        try:
            from graspologic.partition import hierarchical_leiden
        except ImportError as exc:
            raise ImportError(
                "graspologic is required for Hierarchical Leiden clustering: "
                "pip install graspologic"
            ) from exc

        partitions = hierarchical_leiden(G, max_cluster_size=self.max_cluster_size)

        communities_by_level = defaultdict(lambda: defaultdict(list))
        for p in partitions:
            communities_by_level[p.level][p.cluster].append(p.node)

        logger.info("Phase 5: Leiden clustering found %d levels of hierarchy.", len(communities_by_level))

        # Upsert communities to Graph Store
        total_communities = 0
        communities_to_upsert = []
        node_map = {n.id: n for n in nodes}

        for level, clusters in communities_by_level.items():
            for cluster_id, node_ids in clusters.items():
                if self.cluster_verifier is not None and len(node_ids) > 1:
                    cluster_nodes = [node_map[nid] for nid in node_ids if nid in node_map]
                    if not await self.cluster_verifier.should_fuse(cluster_nodes):
                        logger.info(
                            "Phase 5: Leiden community %s (level %s) rejected by fusion gate",
                            cluster_id,
                            level,
                        )
                        continue

                comm_id = f"community_{node_type.lower()}_{level}_{cluster_id}"
                communities_to_upsert.append({
                    "community_id": comm_id,
                    "level": level,
                    "entity_ids": node_ids,
                })
                total_communities += 1

        if communities_to_upsert:
            from itertools import batched

            for batch in batched(communities_to_upsert, 500):
                await graph_store.upsert_communities(list(batch))

        logger.info("Phase 5: Stored %d Community nodes for %s.", total_communities, node_type)
