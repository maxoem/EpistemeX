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

import networkx as nx

from episteme_pipeline.protocols.fusion import TheoryFusion
from episteme_pipeline.protocols.graph_store import FusionGraph

logger = logging.getLogger(__name__)


class LeidenTheoryClustering(TheoryFusion):
    """
    Applies Hierarchical Leiden community detection to the entity graph.
    """

    def __init__(
        self,
        max_cluster_size: int = 100,
        cluster_layer: str = "theory_atoms"
    ) -> None:
        self.max_cluster_size = max_cluster_size
        self.cluster_layer = cluster_layer

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
                # Map TheoryAtoms and TheoryRelations to generic interface
                # Or just adapt the logic
                await self._run_leiden_for_nodes(graph_store, atoms, relations, "TheoryAtom")
            else:
                logger.info("Phase 5: Theory graph is empty, skipping Leiden clustering for TheoryAtoms.")

    async def _run_leiden_for_nodes(self, graph_store: FusionGraph, nodes, edges, node_type: str) -> None:
        # Build NetworkX Graph
        G = nx.Graph()
        
        # Add nodes
        for n in nodes:
            # handle both L2Entity and TheoryAtom
            label = getattr(n, "label", getattr(n, "component_type", node_type))
            G.add_node(n.id, label=label)
            
        # Add edges (undirected for standard Leiden)
        for e in edges:
            subj_id = getattr(e, "subject_id", getattr(e, "source_id", None))
            obj_id = getattr(e, "object_id", getattr(e, "target_id", None))
            if subj_id is None or obj_id is None:
                continue
                
            conf = e.confidence if hasattr(e, "confidence") and e.confidence is not None else 1.0
            
            if G.has_edge(subj_id, obj_id):
                G[subj_id][obj_id]["weight"] += conf
            else:
                G.add_edge(subj_id, obj_id, weight=conf)

        logger.info(f"Phase 5: NetworkX graph for {node_type} built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

        # Run Hierarchical Leiden
        logger.info("Phase 5: Running Hierarchical Leiden...")
        try:
            from graspologic.partition import hierarchical_leiden
        except ImportError as exc:
            raise ImportError(
                "graspologic is required for Hierarchical Leiden clustering: "
                "pip install graspologic"
            ) from exc

        # graspologic hierarchical_leiden returns a list of Partition objects
        # We'll use the dict representation mapping node -> community ID
        partitions = hierarchical_leiden(G, max_cluster_size=self.max_cluster_size)
        
        # Partitions usually have a format like: list of HierarchicalCluster(node, cluster, level)
        # Or a list of namedtuples. We'll group by level and cluster ID.
        
        communities_by_level = defaultdict(lambda: defaultdict(list))
        
        for p in partitions:
            # p usually has .node, .cluster, .level
            communities_by_level[p.level][p.cluster].append(p.node)
            
        logger.info(f"Phase 5: Leiden clustering found {len(communities_by_level)} levels of hierarchy.")

        # Upsert communities to Graph Store
        total_communities = 0
        communities_to_upsert = []
        for level, clusters in communities_by_level.items():
            for cluster_id, node_ids in clusters.items():
                comm_id = f"community_{node_type.lower()}_{level}_{cluster_id}"
                communities_to_upsert.append({
                    "community_id": comm_id,
                    "level": level,
                    "entity_ids": node_ids
                })
                total_communities += 1
                
        if communities_to_upsert:
            from itertools import batched
            for batch in batched(communities_to_upsert, 500):
                await graph_store.upsert_communities(list(batch))
                
        logger.info(f"Phase 5: Stored {total_communities} Community nodes for {node_type}.")
