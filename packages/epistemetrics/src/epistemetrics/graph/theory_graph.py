"""Runtime TheoryGraph representation backed by NetworkX.

Operationalizes formal scientific theory nets and knowledge graphs into an
in-memory multi-directed graph structure suitable for epistemic evaluation.
"""

from __future__ import annotations

import copy
from typing import Any, Iterator

import networkx as nx

from epistemetrics.core.models import (
    EpistemicStatus,
    NodeType,
    RelationType,
    TheoryEdge,
    TheoryNode,
)


class TheoryGraph:
    """Runtime mathematical and epistemic graph container.

    Encapsulates an in-memory `networkx.MultiDiGraph` alongside typed
    `TheoryNode` and `TheoryEdge` domain representations, facilitating
    epistemic virtue evaluation and structural graph analysis.

    Parameters
    ----------
    name : str, optional
        Human-readable name of the theory graph (default: "TheoryGraph").

    Attributes
    ----------
    name : str
        Name of the theory graph.
    num_nodes : int
        Number of theory nodes in the graph.
    num_edges : int
        Number of theory relations in the graph.
    nodes : dict[str, TheoryNode]
        Dictionary mapping node IDs to TheoryNode domain objects.
    edges : list[TheoryEdge]
        List of all TheoryEdge domain objects.
    nx_graph : nx.MultiDiGraph
        Underlying NetworkX MultiDiGraph instance.
    """

    def __init__(self, name: str = "TheoryGraph") -> None:
        """Initialize an empty TheoryGraph instance.

        Parameters
        ----------
        name : str, optional
            Descriptive title of the graph (default: "TheoryGraph").
        """
        self._name: str = name
        self._nx_graph: nx.MultiDiGraph = nx.MultiDiGraph(name=name)
        self._nodes: dict[str, TheoryNode] = {}
        self._edges: list[TheoryEdge] = []

    @property
    def name(self) -> str:
        """Return the name of the theory graph.

        Returns
        -------
        str
            Graph name.
        """
        return self._name

    @name.setter
    def name(self, val: str) -> None:
        """Set the name of the theory graph.

        Parameters
        ----------
        val : str
            New name for the graph.
        """
        self._name = val
        self._nx_graph.graph["name"] = val

    @property
    def num_nodes(self) -> int:
        """Return total count of nodes in the graph.

        Returns
        -------
        int
            Node count.
        """
        return len(self._nodes)

    @property
    def num_edges(self) -> int:
        """Return total count of edges in the graph.

        Returns
        -------
        int
            Edge count.
        """
        return len(self._edges)

    @property
    def nodes(self) -> dict[str, TheoryNode]:
        """Return all nodes mapped by domain identifier.

        Returns
        -------
        dict[str, TheoryNode]
            Dictionary of nodes.
        """
        return dict(self._nodes)

    @property
    def edges(self) -> list[TheoryEdge]:
        """Return all edges in the graph.

        Returns
        -------
        list[TheoryEdge]
            List of domain edges.
        """
        return list(self._edges)

    @property
    def nx_graph(self) -> nx.MultiDiGraph:
        """Return underlying NetworkX MultiDiGraph.

        Returns
        -------
        nx.MultiDiGraph
            NetworkX multi-directed graph object.
        """
        return self._nx_graph

    def add_node(
        self,
        node_id: str,
        name: str | None = None,
        node_type: NodeType | str = NodeType.CONCEPT,
        epistemic_status: EpistemicStatus | str = EpistemicStatus.NEUTRAL,
        confidence: float = 1.0,
        description: str | None = None,
        provenance: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TheoryNode:
        """Add a typed node to the TheoryGraph and underlying NetworkX graph.

        Parameters
        ----------
        node_id : str
            Unique domain identifier for the node.
        name : str | None, optional
            Human-readable name or label (defaults to node_id if omitted).
        node_type : NodeType or str, optional
            Epistemic or ontological node type (default: NodeType.CONCEPT).
        epistemic_status : EpistemicStatus or str, optional
            Lakatosian epistemic status (default: EpistemicStatus.NEUTRAL).
        confidence : float, optional
            Confidence score between 0.0 and 1.0 (default: 1.0).
        description : str | None, optional
            Verbatim quote, proposition, or definition.
        provenance : list[str] | None, optional
            List of chunk identifiers or source citations.
        attributes : dict[str, Any] | None, optional
            Dictionary of arbitrary extra domain attributes.
        **kwargs : Any
            Additional arbitrary attributes merged into node attributes.

        Returns
        -------
        TheoryNode
            The created and registered TheoryNode instance.
        """
        resolved_name = name if name is not None else node_id
        resolved_type = NodeType.from_str(node_type)
        resolved_status = EpistemicStatus.from_str(epistemic_status)
        resolved_prov = list(provenance) if provenance is not None else []
        merged_attrs = dict(attributes or {})
        merged_attrs.update(kwargs)

        node = TheoryNode(
            id=node_id,
            name=resolved_name,
            node_type=resolved_type,
            epistemic_status=resolved_status,
            confidence=confidence,
            description=description,
            provenance=resolved_prov,
            attributes=merged_attrs,
        )

        nx_attrs = {
            k: v
            for k, v in merged_attrs.items()
            if k
            not in {
                "name",
                "type",
                "node_type",
                "epistemic_status",
                "confidence",
                "description",
                "provenance",
            }
        }
        self._nodes[node_id] = node
        self._nx_graph.add_node(
            node_id,
            name=resolved_name,
            type=resolved_type.value,
            node_type=resolved_type.value,
            epistemic_status=resolved_status.value,
            confidence=confidence,
            description=description,
            provenance=resolved_prov,
            **nx_attrs,
        )
        return node

    def add_edge(
        self,
        source: str,
        target: str,
        relation_type: RelationType | str = RelationType.EXPLAINS,
        confidence: float = 1.0,
        weight: float = 1.0,
        polarity: int | None = None,
        class_probability: float | None = None,
        empirical_accuracy: float | None = None,
        modal_strength: float = 1.0,
        effective_weight: float | None = None,
        attributes: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TheoryEdge:
        """Add a typed edge between two nodes in the TheoryGraph.

        If either source or target does not exist, an unclassified node is
        implicitly registered to maintain topological validity.

        Parameters
        ----------
        source : str
            Domain identifier of the origin node.
        target : str
            Domain identifier of the destination node.
        relation_type : RelationType or str, optional
            Relational classification (default: RelationType.EXPLAINS).
        confidence : float, optional
            Confidence score (default: 1.0).
        weight : float, optional
            Relational edge weight (default: 1.0).
        polarity : int | None, optional
            Epistemic polarity (+1, -1, 0). If None, defaults to canonical polarity.
        class_probability : float | None, optional
            Softmax probability P(stance).
        empirical_accuracy : float | None, optional
            Calibrated empirical accuracy frequency from decision engine.
        modal_strength : float, default 1.0
            Propositional modal strength score in [0.0, 1.0].
        effective_weight : float | None, optional
            Decoupled mathematical edge weight w = M * P.
        attributes : dict[str, Any] | None, optional
            Additional relation properties.
        **kwargs : Any
            Additional arbitrary attributes merged into edge attributes.

        Returns
        -------
        TheoryEdge
            The created and registered TheoryEdge instance.
        """
        if source not in self._nodes:
            self.add_node(source, name=source, node_type=NodeType.CONCEPT)
        if target not in self._nodes:
            self.add_node(target, name=target, node_type=NodeType.CONCEPT)

        resolved_relation = RelationType.from_str(relation_type)
        resolved_polarity = (
            polarity if polarity is not None else resolved_relation.default_polarity
        )
        merged_attrs = dict(attributes or {})
        merged_attrs.update(kwargs)

        eff_w = effective_weight
        if eff_w is None:
            if class_probability is not None:
                eff_w = float(modal_strength * class_probability)
            else:
                eff_w = float(weight)

        edge = TheoryEdge(
            source=source,
            target=target,
            relation_type=resolved_relation,
            confidence=confidence,
            weight=weight,
            polarity=resolved_polarity,
            class_probability=class_probability,
            empirical_accuracy=empirical_accuracy,
            modal_strength=modal_strength,
            effective_weight=eff_w,
            attributes=merged_attrs,
        )

        self._edges.append(edge)
        nx_edge_attrs = {
            k: v
            for k, v in merged_attrs.items()
            if k
            not in {
                "relation_type",
                "type",
                "confidence",
                "weight",
                "polarity",
            }
        }
        self._nx_graph.add_edge(
            source,
            target,
            relation_type=resolved_relation.value,
            type=resolved_relation.value,
            confidence=confidence,
            weight=weight,
            polarity=resolved_polarity,
            **nx_edge_attrs,
        )
        return edge

    def get_node(self, node_id: str) -> TheoryNode | None:
        """Retrieve a node domain object by its identifier.

        Parameters
        ----------
        node_id : str
            Domain identifier of the node.

        Returns
        -------
        TheoryNode | None
            The node object if found, otherwise None.
        """
        return self._nodes.get(node_id)

    def get_edge(self, source: str, target: str) -> list[TheoryEdge]:
        """Retrieve all edges directed from source to target.

        Parameters
        ----------
        source : str
            Identifier of source node.
        target : str
            Identifier of target node.

        Returns
        -------
        list[TheoryEdge]
            Matching edges between the two nodes.
        """
        return [e for e in self._edges if e.source == source and e.target == target]

    def get_edges(
        self, source: str | None = None, target: str | None = None
    ) -> list[TheoryEdge]:
        """Filter edges by optional source and/or target endpoints.

        Parameters
        ----------
        source : str | None, optional
            Source node filter.
        target : str | None, optional
            Target node filter.

        Returns
        -------
        list[TheoryEdge]
            List of matching edges.
        """
        matches = self._edges
        if source is not None:
            matches = [e for e in matches if e.source == source]
        if target is not None:
            matches = [e for e in matches if e.target == target]
        return matches

    def has_node(self, node_id: str) -> bool:
        """Check if a node ID exists in the graph.

        Parameters
        ----------
        node_id : str
            Domain identifier to check.

        Returns
        -------
        bool
            True if node exists in graph.
        """
        return node_id in self._nodes

    def has_edge(self, source: str, target: str) -> bool:
        """Check if any directed edge exists from source to target.

        Parameters
        ----------
        source : str
            Source node identifier.
        target : str
            Target node identifier.

        Returns
        -------
        bool
            True if at least one edge exists.
        """
        return any(e.source == source and e.target == target for e in self._edges)

    def __contains__(self, node_id: str) -> bool:
        """Check containment of node ID using 'in' operator."""
        return node_id in self._nodes

    def __getitem__(self, node_id: str) -> TheoryNode:
        """Retrieve node domain object using dictionary indexing."""
        if node_id not in self._nodes:
            raise KeyError(f"Node '{node_id}' not found in TheoryGraph.")
        return self._nodes[node_id]

    def __iter__(self) -> Iterator[str]:
        """Iterate over all node domain identifiers in the graph."""
        return iter(self._nodes)

    def __len__(self) -> int:
        """Return total number of nodes in the graph."""
        return len(self._nodes)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the theory graph into a dictionary structure.

        Returns
        -------
        dict[str, Any]
            Dictionary representation of the graph, nodes, and edges.
        """
        return {
            "name": self._name,
            "nodes": [node.model_dump() for node in self._nodes.values()],
            "edges": [edge.model_dump() for edge in self._edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TheoryGraph:
        """Instantiate a TheoryGraph from a dictionary representation.

        Parameters
        ----------
        data : dict[str, Any]
            Serialized theory graph dictionary.

        Returns
        -------
        TheoryGraph
            Reconstituted TheoryGraph instance.
        """
        tg = cls(name=data.get("name", "TheoryGraph"))
        for n in data.get("nodes", []):
            tg.add_node(
                node_id=n["id"],
                name=n.get("name", n["id"]),
                node_type=NodeType.from_str(n.get("node_type", n.get("type", "concept"))),
                epistemic_status=EpistemicStatus.from_str(
                    n.get("epistemic_status", "neutral")
                ),
                confidence=n.get("confidence", 1.0),
                description=n.get("description"),
                provenance=n.get("provenance", []),
                attributes=n.get("attributes", {}),
            )
        for e in data.get("edges", []):
            tg.add_edge(
                source=e["source"],
                target=e["target"],
                relation_type=RelationType.from_str(
                    e.get("relation_type", e.get("type", "explains"))
                ),
                confidence=e.get("confidence", 1.0),
                weight=e.get("weight", 1.0),
                polarity=e.get("polarity"),
                attributes=e.get("attributes", {}),
            )
        return tg

    def to_networkx(self) -> nx.MultiDiGraph:
        """Return a detached deep copy of the underlying NetworkX MultiDiGraph.

        Returns
        -------
        nx.MultiDiGraph
            Copy of NetworkX graph.
        """
        return self._nx_graph.copy()

    @classmethod
    def from_networkx(
        cls, G: nx.Graph | nx.DiGraph | nx.MultiDiGraph, name: str = "ImportedGraph"
    ) -> TheoryGraph:
        """Construct a TheoryGraph from a generic NetworkX graph.

        Parameters
        ----------
        G : nx.Graph or nx.DiGraph or nx.MultiDiGraph
            Source NetworkX graph.
        name : str, optional
            Name for the new TheoryGraph (default: "ImportedGraph").

        Returns
        -------
        TheoryGraph
            Populated TheoryGraph.
        """
        tg = cls(name=name)
        for n, data in G.nodes(data=True):
            reserved_node_keys = {
                "name",
                "node_type",
                "type",
                "epistemic_status",
                "confidence",
                "description",
                "provenance",
            }
            extra_attrs = {k: v for k, v in data.items() if k not in reserved_node_keys}
            tg.add_node(
                node_id=str(n),
                name=str(data.get("name", data.get("label", n))),
                node_type=NodeType.from_str(
                    data.get("node_type", data.get("type", data.get("label", "concept")))
                ),
                epistemic_status=EpistemicStatus.from_str(
                    data.get("epistemic_status", "neutral")
                ),
                confidence=float(data.get("confidence", 1.0)),
                description=data.get("description"),
                provenance=data.get("provenance", []),
                attributes=extra_attrs,
            )

        reserved_edge_keys = {
            "relation_type",
            "type",
            "label",
            "confidence",
            "weight",
            "polarity",
        }
        if G.is_multigraph():
            for u, v, _key, data in G.edges(keys=True, data=True):
                extra_edge_attrs = {
                    k: v for k, v in data.items() if k not in reserved_edge_keys
                }
                tg.add_edge(
                    source=str(u),
                    target=str(v),
                    relation_type=RelationType.from_str(
                        data.get("relation_type", data.get("type", data.get("label", "explains")))
                    ),
                    confidence=float(data.get("confidence", 1.0)),
                    weight=float(data.get("weight", 1.0)),
                    polarity=data.get("polarity"),
                    attributes=extra_edge_attrs,
                )
        else:
            for u, v, data in G.edges(data=True):
                extra_edge_attrs = {
                    k: v for k, v in data.items() if k not in reserved_edge_keys
                }
                tg.add_edge(
                    source=str(u),
                    target=str(v),
                    relation_type=RelationType.from_str(
                        data.get("relation_type", data.get("type", data.get("label", "explains")))
                    ),
                    confidence=float(data.get("confidence", 1.0)),
                    weight=float(data.get("weight", 1.0)),
                    polarity=data.get("polarity"),
                    attributes=extra_edge_attrs,
                )
        return tg

    def copy(self) -> TheoryGraph:
        """Create a deep copy of the TheoryGraph.

        Returns
        -------
        TheoryGraph
            Independent cloned TheoryGraph instance.
        """
        new_tg = TheoryGraph(name=self._name)
        for node in self._nodes.values():
            new_tg.add_node(
                node_id=node.id,
                name=node.name,
                node_type=node.node_type,
                epistemic_status=node.epistemic_status,
                confidence=node.confidence,
                description=node.description,
                provenance=list(node.provenance),
                attributes=copy.deepcopy(node.attributes),
            )
        for edge in self._edges:
            new_tg.add_edge(
                source=edge.source,
                target=edge.target,
                relation_type=edge.relation_type,
                confidence=edge.confidence,
                weight=edge.weight,
                polarity=edge.polarity,
                attributes=copy.deepcopy(edge.attributes),
            )
        return new_tg
