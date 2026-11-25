"""Recursive Leiden community detection with signed/support-projected graphs.

Constructs a NetworkX projection from Layer 2 entities or Layer 3 argument atoms,
filters or signs dialectical edges according to ``edge_projection`` so adversarial
opponents are not merged under unsigned clustering, runs recursive Leiden
partitioning, computes additive per-community modularity contributions :math:`q_c`,
and persists ``Community`` nodes to the graph store.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Literal

import networkx as nx
from epistemetrics.graph.algorithms.community_metrics import (
    participation_coefficient,
    per_community_modularity,
    signed_modularity,
)

from episteme_pipeline.contracts.domain import (
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.protocols.decision import DecisionEngine
from episteme_pipeline.protocols.fusion import TheoryFusion
from episteme_pipeline.protocols.graph_store import FusionGraph
from episteme_pipeline.schema.default_schema import DEFAULT_SCHEMA, SchemaConfig

if TYPE_CHECKING:
    from episteme_pipeline.config import Phase5Config
    from episteme_pipeline.phases.phase5_fusion.argument_clustering import (
        InterDocumentClusterVerifier,
    )

logger = logging.getLogger(__name__)


def _extract_node_spec(node: Any, default_type: str) -> tuple[str, str]:
    """Extract node identifier and label type."""
    match node:
        case L2Entity():
            return node.id, node.label
        case TheoryAtom():
            return node.id, node.component_type
        case _:
            return str(node), default_type


def _extract_edge_spec(
    edge: Any, schema: SchemaConfig
) -> tuple[str, str, float, int] | None:
    """Extract edge endpoints, confidence magnitude, and epistemic polarity."""
    if isinstance(edge, L2Triple):
        conf = edge.confidence if edge.confidence is not None else 1.0
        pol = schema.relation_polarities.get(edge.predicate, 0)
        return edge.subject_id, edge.object_id, float(conf), int(pol)
    if isinstance(edge, TheoryRelation):
        conf = edge.confidence if edge.confidence is not None else 1.0
        pol = schema.relation_polarities.get(edge.relation_type, 0)
        return edge.source_id, edge.target_id, float(conf), int(pol)
    return None


class LeidenTheoryClustering(TheoryFusion):
    """Applies recursive Leiden community detection with projection hygiene.

    Parameters
    ----------
    max_cluster_size : int, default 100
        Maximum node count per community before recursive subdivision.
    cluster_layer : str, default "theory_atoms"
        Target graph layer (``"theory_atoms"``, ``"l2_entities"``, or ``"both"``).
    cluster_verifier : InterDocumentClusterVerifier or None, default None
        Optional inter-document verifier gating candidate communities.
    edge_projection : {"support_only", "signed", "unsigned"}, default "support_only"
        Handling of adversarial negative-polarity edges:
        - ``"support_only"`` excludes negative-polarity edges so dialectical
          opponents are not merged into a single community.
        - ``"signed"`` clusters on non-negative support edges and scores the
          resulting partition using Traag & Bruggeman (2009) signed modularity
          :math:`Q_{\\text{signed}}`.
        - ``"unsigned"`` retains all edges with positive weights (useful for
          identifying shared debate arenas).
    resolution : float, default 1.0
        Modularity resolution parameter :math:`\\gamma_{\\text{res}}`.
    schema : SchemaConfig or None, optional
        Schema supplying relation polarity mappings.
    """

    def __init__(
        self,
        max_cluster_size: int = 100,
        cluster_layer: str = "theory_atoms",
        cluster_verifier: InterDocumentClusterVerifier | None = None,
        edge_projection: Literal["support_only", "signed", "unsigned"] = "support_only",
        resolution: float = 1.0,
        schema: SchemaConfig | None = None,
        **kwargs: Any,
    ) -> None:
        self.max_cluster_size = max_cluster_size
        self.cluster_layer = cluster_layer
        self.cluster_verifier = cluster_verifier
        self.edge_projection: Literal["support_only", "signed", "unsigned"] = (
            edge_projection
        )
        self.resolution = float(resolution)
        self.schema = schema or DEFAULT_SCHEMA

    @classmethod
    def from_config(
        cls,
        config: Phase5Config,
        decision_engine: DecisionEngine | None = None,
        cluster_verifier: InterDocumentClusterVerifier | None = None,
        schema: SchemaConfig | None = None,
    ) -> LeidenTheoryClustering:
        """Construct LeidenTheoryClustering from Phase5Config."""
        if (
            cluster_verifier is None
            and config.gating.enabled
            and decision_engine is not None
        ):
            from episteme_pipeline.phases.phase5_fusion.argument_clustering import (
                InterDocumentClusterVerifier,
            )

            cluster_verifier = InterDocumentClusterVerifier.from_config(
                config.gating,
                decision_engine,
            )
        return cls(
            max_cluster_size=config.max_cluster_size,
            cluster_layer=config.cluster_layer,
            cluster_verifier=cluster_verifier,
            edge_projection=config.edge_projection,
            resolution=config.resolution,
            schema=schema,
        )

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic Leiden clustering configuration fingerprint."""
        from episteme_pipeline.protocols.fingerprint import Fingerprintable
        from episteme_pipeline.runs.fingerprints import fingerprint_method

        return {
            "class": self.__class__.__name__,
            "max_cluster_size": self.max_cluster_size,
            "cluster_layer": self.cluster_layer,
            "edge_projection": self.edge_projection,
            "resolution": self.resolution,
            "cluster_verifier": (
                self.cluster_verifier.fingerprint()
                if isinstance(self.cluster_verifier, Fingerprintable)
                else fingerprint_method(self.cluster_verifier)
            ),
        }

    async def fuse(self, graph_store: FusionGraph) -> None:
        if self.cluster_layer in ("l2_entities", "both"):
            logger.info(
                "Phase 5: Fetching L2 entities and triples for recursive Leiden clustering."
            )
            entities = await graph_store.get_entities()
            triples = await graph_store.get_all_entity_triples()
            if entities and triples:
                await self._run_leiden_for_nodes(
                    graph_store, entities, triples, "L2Entity"
                )
            else:
                logger.info(
                    "Phase 5: Entity graph is empty, skipping Leiden clustering for L2Entities."
                )

        if self.cluster_layer in ("theory_atoms", "both"):
            logger.info(
                "Phase 5: Fetching TheoryAtoms and TheoryRelations for recursive Leiden clustering."
            )
            atoms = await graph_store.get_theory_atoms()
            relations = await graph_store.get_all_theory_relations()
            if atoms and relations:
                await self._run_leiden_for_nodes(
                    graph_store, atoms, relations, "TheoryAtom"
                )
            else:
                logger.info(
                    "Phase 5: Theory graph is empty, skipping Leiden clustering for TheoryAtoms."
                )

    async def _run_leiden_for_nodes(
        self, graph_store: FusionGraph, nodes: Any, edges: Any, node_type: str
    ) -> None:
        cluster_g = nx.Graph()
        signed_g = nx.Graph()

        for n in nodes:
            nid, label = _extract_node_spec(n, node_type)
            cluster_g.add_node(nid, label=label)
            signed_g.add_node(nid, label=label)

        for e in edges:
            spec = _extract_edge_spec(e, self.schema)
            if spec is None:
                continue
            subj_id, obj_id, conf_val, pol = spec
            if conf_val <= 0.0:
                continue

            signed_w = -conf_val if pol < 0 else conf_val
            if signed_g.has_edge(subj_id, obj_id):
                signed_g[subj_id][obj_id]["weight"] += signed_w
            else:
                signed_g.add_edge(subj_id, obj_id, weight=signed_w)

            if self.edge_projection in ("support_only", "signed") and pol < 0:
                continue

            if cluster_g.has_edge(subj_id, obj_id):
                cluster_g[subj_id][obj_id]["weight"] += conf_val
            else:
                cluster_g.add_edge(subj_id, obj_id, weight=conf_val)

        logger.info(
            "Phase 5: Built %s projection graph (%s) with %d nodes and %d edges.",
            self.edge_projection,
            node_type,
            cluster_g.number_of_nodes(),
            cluster_g.number_of_edges(),
        )

        try:
            from graspologic.partition import hierarchical_leiden
        except ImportError as exc:
            raise ImportError(
                "graspologic is required for recursive Leiden clustering: "
                "pip install graspologic"
            ) from exc

        partitions = hierarchical_leiden(
            cluster_g,
            max_cluster_size=self.max_cluster_size,
            resolution=self.resolution,
        )

        communities_by_level: dict[int, dict[int, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for p in partitions:
            communities_by_level[p.level][p.cluster].append(p.node)

        logger.info(
            "Phase 5: Recursive Leiden found %d resolution scale levels.",
            len(communities_by_level),
        )

        total_communities = 0
        communities_to_upsert = []
        node_map = {n.id: n for n in nodes}

        for level, clusters in communities_by_level.items():
            ordered_cluster_ids = sorted(clusters.keys())
            comm_sets = [set(clusters[cid]) for cid in ordered_cluster_ids]
            if self.edge_projection == "signed":
                q_global, q_by_idx = signed_modularity(
                    signed_g,
                    comm_sets,
                    resolution=self.resolution,
                    weight_property="weight",
                )
            else:
                q_global, q_by_idx = per_community_modularity(
                    cluster_g,
                    comm_sets,
                    resolution=self.resolution,
                    weight_property="weight",
                )
            node_to_comm = {
                nid: idx
                for idx, cid in enumerate(ordered_cluster_ids)
                for nid in clusters[cid]
            }
            part_coeffs = participation_coefficient(
                cluster_g, node_to_comm, weight_property="weight"
            )
            logger.debug(
                "Phase 5: Level %d modularity=%.4f (projection=%s, mean_P=%.4f)",
                level,
                q_global,
                self.edge_projection,
                (
                    sum(part_coeffs.values()) / len(part_coeffs)
                    if part_coeffs
                    else 0.0
                ),
            )

            for idx, cluster_id in enumerate(ordered_cluster_ids):
                node_ids = clusters[cluster_id]
                if self.cluster_verifier is not None and len(node_ids) > 1:
                    cluster_nodes = [
                        node_map[nid] for nid in node_ids if nid in node_map
                    ]
                    if not await self.cluster_verifier.should_fuse(cluster_nodes):
                        logger.info(
                            "Phase 5: Leiden community %s (level %s) rejected by fusion gate",
                            cluster_id,
                            level,
                        )
                        continue

                comm_id = f"community_{node_type.lower()}_{level}_{cluster_id}"
                communities_to_upsert.append(
                    {
                        "community_id": comm_id,
                        "level": level,
                        "entity_ids": node_ids,
                        "modularity_contribution": round(q_by_idx.get(idx, 0.0), 6),
                        "edge_projection": self.edge_projection,
                    }
                )
                total_communities += 1

        if communities_to_upsert:
            from itertools import batched

            for batch in batched(communities_to_upsert, 500):
                await graph_store.upsert_communities(list(batch))

        logger.info(
            "Phase 5: Stored %d Community nodes for %s.", total_communities, node_type
        )
