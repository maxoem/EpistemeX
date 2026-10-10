"""Adapter to export Neo4j graph data into epistemetrics TheoryGraph.

Bridges the Grund GLP Neo4j store (L2 Knowledge Graph and L3 Theory Framework)
to the epistemetrics analytical library.
"""

from __future__ import annotations

import logging

import epistemetrics as em
from episteme_pipeline.protocols.graph_store import GraphReader

logger = logging.getLogger(__name__)


async def export_neo4j_to_theory_graph(
    reader: GraphReader,
    name: str = "Neo4jTheoryGraph",
    include_l2: bool = True,
    include_l3: bool = True,
) -> em.TheoryGraph:
    """Extract L2 entities/triples and L3 theory atoms/relations from Neo4j into a TheoryGraph.

    Parameters
    ----------
    reader : GraphReader
        Connected Neo4j graph reader handle.
    name : str, optional
        Name of the created TheoryGraph (default: "Neo4jTheoryGraph").
    include_l2 : bool, optional
        Whether to export Layer 2 entities and relational triples (default: True).
    include_l3 : bool, optional
        Whether to export Layer 3 theory atoms and argumentative relations (default: True).

    Returns
    -------
    em.TheoryGraph
        Populated TheoryGraph ready for epistemic and structural analysis.
    """
    tg = em.TheoryGraph(name=name)

    if include_l2:
        try:
            entities = await reader.get_entities()
            for ent in entities:
                node_type = em.NodeType.from_str(ent.label)
                epistemic_status = em.EpistemicStatus.NEUTRAL
                if ent.label.upper() in {"AXIOM", "CORE_THEORY", "FOUNDATION"}:
                    epistemic_status = em.EpistemicStatus.HARD_CORE
                elif ent.label.upper() in {"HYPOTHESIS", "AUXILIARY"}:
                    epistemic_status = em.EpistemicStatus.PROTECTIVE_BELT

                tg.add_node(
                    node_id=ent.id,
                    name=ent.name or ent.id,
                    node_type=node_type,
                    epistemic_status=epistemic_status,
                    confidence=ent.confidence or 1.0,
                    description=ent.description,
                    provenance=ent.source_chunk_ids,
                    attributes={"is_mature": ent.is_mature, "layer": "L2"},
                )

            triples = await reader.get_all_entity_triples()
            for tr in triples:
                tg.add_edge(
                    source=tr.subject_id,
                    target=tr.object_id,
                    relation_type=em.RelationType.from_str(tr.predicate),
                    confidence=tr.confidence or 1.0,
                    attributes={"scope": tr.scope, "layer": "L2"},
                )
        except Exception as exc:
            logger.warning("Failed to extract L2 components from Neo4j: %s", exc)

    if include_l3:
        try:
            atoms = await reader.get_theory_atoms()
            for atom in atoms:
                node_type = em.NodeType.from_str(atom.component_type)
                epistemic_status = em.EpistemicStatus.NEUTRAL
                if atom.component_type.upper() in {"AXIOM", "CORE_AXIOM"}:
                    epistemic_status = em.EpistemicStatus.HARD_CORE
                elif atom.component_type.upper() in {"PREMISE", "HYPOTHESIS"}:
                    epistemic_status = em.EpistemicStatus.PROTECTIVE_BELT

                tg.add_node(
                    node_id=atom.id,
                    name=atom.text[:80] if atom.text else atom.id,
                    node_type=node_type,
                    epistemic_status=epistemic_status,
                    confidence=atom.confidence or 1.0,
                    description=atom.text,
                    provenance=[atom.source_chunk_id] if atom.source_chunk_id else [],
                    attributes={"plausibility": atom.plausibility, "layer": "L3"},
                )

            relations = await reader.get_all_theory_relations()
            for rel in relations:
                tg.add_edge(
                    source=rel.source_id,
                    target=rel.target_id,
                    relation_type=em.RelationType.from_str(rel.relation_type),
                    confidence=rel.confidence or 1.0,
                    weight=rel.weight or 1.0,
                    attributes={"scope": rel.scope, "layer": "L3"},
                )
        except Exception as exc:
            logger.warning("Failed to extract L3 components from Neo4j: %s", exc)

    return tg
