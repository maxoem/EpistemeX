"""Domain bridge utilities mapping pipeline contracts to evaluation graph structures."""

from __future__ import annotations

from typing import Any
import networkx as nx

import epistemetrics as em
from episteme_pipeline.artifacts.execution import ArtifactCollection, Phase4ArtifactsView
from episteme_pipeline.contracts.domain import L2Entity, L2Triple, TheoryAtom, TheoryNet, TheoryRelation
from episteme_pipeline.evaluation.scorers.networkx_builder import build_digraph
from episteme_pipeline.projection.theorynet_projector import TheoryNetProjector
from episteme_pipeline.schema.default_schema import SchemaConfig


def l2_triples_to_digraph(entities: list[L2Entity], triples: list[L2Triple]) -> nx.DiGraph:
    """Convert L2 entities and triples to a NetworkX DiGraph.

    Parameters
    ----------
    entities : list of L2Entity
        A list of L2 entities to add as nodes.
    triples : list of L2Triple
        A list of L2 triples to add as directed edges.

    Returns
    -------
    nx.DiGraph
        A NetworkX directed graph where entities are nodes (labeled by name)
        and triples are directed edges (labeled by predicate).
    """
    graph = nx.DiGraph()
    entity_dict = {ent.id: ent for ent in entities}

    for ent in entities:
        name = ent.name or ent.id
        graph.add_node(
            name,
            id=ent.id,
            label=ent.label,
            name=name,
            node_type=ent.label,
            description=ent.description,
            is_mature=ent.is_mature,
        )

    for triple in triples:
        u = entity_dict.get(triple.subject_id)
        v = entity_dict.get(triple.object_id)

        if u and v:
            u_name = u.name or u.id
            v_name = v.name or v.id
            graph.add_edge(
                u_name,
                v_name,
                label=triple.predicate,
                relation=triple.predicate,
                confidence=triple.confidence,
                scope=triple.scope,
            )

    return graph


def theory_net_to_digraph(atoms: list[TheoryAtom], relations: list[TheoryRelation]) -> nx.DiGraph:
    """Convert L3 TheoryAtoms and TheoryRelations to a NetworkX DiGraph.

    Parameters
    ----------
    atoms : list of TheoryAtom
        A list of TheoryAtoms to add as nodes.
    relations : list of TheoryRelation
        A list of TheoryRelations to add as directed edges.

    Returns
    -------
    nx.DiGraph
        A NetworkX directed graph where atoms are nodes (labeled by text)
        and relations are directed edges (labeled by relation_type).
    """
    graph = nx.DiGraph()
    atom_dict = {atom.id: atom for atom in atoms}

    for atom in atoms:
        label = atom.text or atom.id
        graph.add_node(
            label,
            id=atom.id,
            label=label,
            name=label,
            node_type=atom.component_type,
            component_type=atom.component_type,
            confidence=atom.confidence,
            epistemic_status=atom.epistemic_status,
            formal_axiom=atom.text,
        )

    for rel in relations:
        u = atom_dict.get(rel.source_id)
        v = atom_dict.get(rel.target_id)

        if u and v:
            u_label = u.text or u.id
            v_label = v.text or v.id
            graph.add_edge(
                u_label,
                v_label,
                label=rel.relation_type,
                relation=rel.relation_type,
                confidence=rel.confidence,
                scope=rel.scope,
                weight=rel.weight,
            )

    return graph


def theory_net_to_theory_graph(
    theory_net: TheoryNet,
    name: str = "TheoryNetGraph",
) -> em.TheoryGraph:
    """Convert a pipeline TheoryNet instance into an epistemetrics TheoryGraph.

    Parameters
    ----------
    theory_net : TheoryNet
        Domain TheoryNet containing atoms and formal relations.
    name : str, optional
        Name of the created TheoryGraph (default: "TheoryNetGraph").

    Returns
    -------
    em.TheoryGraph
        Populated TheoryGraph container.
    """
    tg = em.TheoryGraph(name=name)

    for atom in theory_net.atoms:
        node_type = em.NodeType.from_str(atom.component_type)
        epistemic_status = (
            em.EpistemicStatus.from_str(atom.epistemic_status)
            if atom.epistemic_status
            else (
                em.EpistemicStatus.HARD_CORE
                if node_type in {em.NodeType.ACTUAL_MODEL, em.NodeType.AXIOM}
                else em.EpistemicStatus.NEUTRAL
            )
        )
        anchor_dict = (
            atom.text_anchor.model_dump()
            if atom.text_anchor
            else (atom.parameters.get("anchor") or atom.parameters.get("text_anchor"))
        )
        attrs = {
            "formalAxiom": atom.text,
            "formal_axiom": atom.text,
            "plausibility": atom.plausibility,
            "layer": "L4",
        }
        if anchor_dict:
            attrs["anchor"] = anchor_dict
            attrs["text_anchor"] = anchor_dict
            attrs["Episteme:textAnchor"] = anchor_dict

        tg.add_node(
            node_id=atom.id,
            name=atom.text[:80] if atom.text else atom.id,
            node_type=node_type,
            epistemic_status=epistemic_status,
            confidence=atom.confidence or 1.0,
            description=atom.text,
            provenance=[atom.source_chunk_id] if atom.source_chunk_id else [],
            attributes=attrs,
        )

    for rel in theory_net.relations:
        tg.add_edge(
            source=rel.source_id,
            target=rel.target_id,
            relation_type=em.RelationType.from_str(rel.relation_type),
            confidence=rel.confidence or 1.0,
            weight=rel.weight or 1.0,
            attributes={"scope": rel.scope, "layer": "L4"},
        )

    return tg


def artifact_collection_to_theory_graph(
    collection: ArtifactCollection,
    name: str = "ArtifactTheoryGraph",
    schema: SchemaConfig | None = None,
) -> em.TheoryGraph:
    """Convert a pipeline ArtifactCollection into an epistemetrics TheoryGraph.

    Projects Phase 4 mined theories through TheoryNetProjector if TheoryNet
    is not directly present, returning a sovereign TheoryGraph.

    Parameters
    ----------
    collection : ArtifactCollection
        Collection of envelopes produced by the pipeline.
    name : str, optional
        Name of the created TheoryGraph (default: "ArtifactTheoryGraph").
    schema : SchemaConfig, optional
        Domain schema configuration for projection.

    Returns
    -------
    em.TheoryGraph
        Populated TheoryGraph container.
    """
    view = Phase4ArtifactsView.from_collection(collection)
    projector = TheoryNetProjector(schema=schema or SchemaConfig())
    theory_net = projector.project(view)
    return theory_net_to_theory_graph(theory_net, name=name)


def gold_standard_to_digraph(triples: list[dict[str, Any]]) -> nx.DiGraph:
    """Convert gold standard dictionary triples to a NetworkX DiGraph.

    Parameters
    ----------
    triples : list of dict
        Triples with 'head', 'relation', 'tail' keys.

    Returns
    -------
    nx.DiGraph
        Directed graph with labeled edges.
    """
    return build_digraph(triples)
