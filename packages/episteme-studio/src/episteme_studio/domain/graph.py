"""Domain models for property graph projections and views across L1, L2, and L3."""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Literal
from pydantic import BaseModel, Field


class Layer(IntEnum):
    """Pipeline graph representation layer."""

    L1 = 1
    L2 = 2
    L3 = 3


class StudioNode(BaseModel):
    """Normalized graph node for frontend visualization and analysis.

    Parameters
    ----------
    id : str
        Stable node identifier or identity key.
    layer : Layer
        Layer in the theory graph hierarchy (L1, L2, or L3).
    type : str
        Open string representing the semantic node type.
    label : str
        Display label for the node.
    partition : Literal['B', 'A'] or None, optional
        TheoryNet partition (empirical base 'B' vs antecedent 'A') for L3 nodes.
    degree : int, default 0
        Total degree of the node in the current graph projection.
    plausibility : float or None, optional
        Prior plausibility (tau). None denotes unknown, distinct from 0.0.
    confidence : float or None, optional
        Extraction or model confidence score.
    empirical_accuracy : float or None, optional
        Calibrated empirical accuracy frequency from System 1 decision engine.
    modal_strength : float or None, optional
        Author propositional modal certainty M(phi) in [0.0, 1.0].
    base_score : float or None, optional
        Prior base score tau_0 for QBAF semantics.
    scope_type : str or None, optional
        Schurz (2014) structuralist sentence scope classification (e.g. 'Essentieller Allsatz').
    epistemic_status : str or None, optional
        Epistemic classification ('Analytisch' vs. 'Synthetisch').
    modal_resolver : str or None, optional
        Lineage identifier or resolver class that derived modal strength.
    raw_modal_score : float or None, optional
        Raw unconstrained System 1 modality score prior to structural guardrail clamping.
    is_modal_clamped : bool or None, optional
        Whether modal strength was constrained by structuralist syntax bounds.
    qbaf_tau : float or None, optional
        Solved asymptotic equilibrium justification degree tau^*(a).
    total_weight_of_evidence : float or None, optional
        Gross epistemic weight / evidentiary volume E_total (Keynes/Gardenfors).
    volatility_index : float or None, optional
        Epistemic controversy / volatility index V in [0.0, 1.0].
    decision_tier : Literal['system_1', 'system_2', 'legacy'], default 'legacy'
        Execution tier that resolved this node.
    conformal_set_size : int or None, optional
        Size of conformal prediction set C(x) at classification time.
    is_out_of_ontology : bool, default False
        Whether node was classified as novel / out-of-ontology.
    decision_id : str or None, optional
        Lineage identifier linking to discrete decision record.
    resolved : bool, default True
        False if referenced in relations but never persisted as an artifact.
    synthetic : bool, default False
        True if reified (e.g. inference midpoint node for UNDERCUTS).
    parameters : dict of str to float or None, optional
        Bourbaki structuralist model parameter coordinates.
    tenability : dict of str to Any or None, optional
        Theoretical tenability consistency evaluation dictionary.
    props : dict of str to Any, optional
        Additional node properties and attributes.
    """

    id: str
    layer: Layer
    type: str
    label: str
    partition: Literal["B", "A"] | None = None
    degree: int = 0
    plausibility: float | None = None
    confidence: float | None = None
    empirical_accuracy: float | None = None
    modal_strength: float | None = None
    base_score: float | None = None
    scope_type: str | None = None
    epistemic_status: str | None = None
    modal_resolver: str | None = None
    raw_modal_score: float | None = None
    is_modal_clamped: bool | None = None
    qbaf_tau: float | None = None
    total_weight_of_evidence: float | None = None
    volatility_index: float | None = None
    decision_tier: Literal["system_1", "system_2", "legacy"] = "legacy"
    conformal_set_size: int | None = None
    is_out_of_ontology: bool = False
    decision_id: str | None = None
    resolved: bool = True
    synthetic: bool = False
    parameters: dict[str, float] | None = None
    tenability: dict[str, Any] | None = None
    props: dict[str, Any] = Field(default_factory=dict)


class StudioEdge(BaseModel):
    """Normalized graph edge connecting two nodes or reified entities.

    Parameters
    ----------
    id : str
        Unique edge identifier.
    source : str
        Source node identifier.
    target : str
        Target node or edge identifier.
    target_kind : Literal['node', 'edge'], default 'node'
        Target entity type (reserved for reified inference targets).
    type : str
        Raw predicate name (open-vocabulary, e.g. 'WIDERSPRICHT').
    layer : Layer
        Layer in the theory graph hierarchy.
    polarity : int or None, optional
        Argumentative polarity: +1 (support), -1 (attack), 0 (neutral),
        or None (unmapped in schema).
    weight : float or None, optional
        Edge strength / weight (phi). None denotes unknown, distinct from 0.0.
    confidence : float or None, optional
        Extraction or reranker confidence score.
    tenability : float or None, optional
        Edge constraint consistency tenability score (TS_edge).
    empirical_accuracy : float or None, optional
        Calibrated empirical accuracy frequency from System 1 decision engine.
    model_confidence : float or None, optional
        Perception calibration confidence score C.
    stance_probability : float or None, optional
        Perception class probability P(stance).
    inferential_force : float or None, optional
        Toulminian inferential warrant validity I_(j->i) in [0.0, 1.0].
    active_weight : float or None, optional
        Net weight W_ji ingested by gradual semantics.
    is_admissible : bool, default True
        Admissibility status under active bivariate thresholds.
    modal_strength : float or None, optional
        Legacy alias for inferential warrant validity on edges.
    qbaf_tau : float or None, optional
        Propagated QBAF justification degree cache.
    decision_tier : Literal['system_1', 'system_2', 'legacy'], default 'legacy'
        Execution tier that resolved this edge ('system_1', 'system_2', 'legacy').
    conformal_set_size : int or None, optional
        Size of conformal prediction set C(x).
    decision_id : str or None, optional
        Lineage identifier linking to discrete decision record.
    props : dict of str to Any, optional
        Additional edge properties.
    """

    id: str
    source: str
    target: str
    target_kind: Literal["node", "edge"] = "node"
    type: str
    layer: Layer
    polarity: int | None = None
    weight: float | None = None
    confidence: float | None = None
    tenability: float | None = None
    empirical_accuracy: float | None = None
    model_confidence: float | None = None
    stance_probability: float | None = None
    inferential_force: float | None = None
    active_weight: float | None = None
    is_admissible: bool = True
    modal_strength: float | None = None
    qbaf_tau: float | None = None
    decision_tier: Literal["system_1", "system_2", "legacy"] = "legacy"
    conformal_set_size: int | None = None
    decision_id: str | None = None
    props: dict[str, Any] = Field(default_factory=dict)


class GraphView(BaseModel):
    """Self-contained subgraph view delivered over the wire.

    Parameters
    ----------
    nodes : list of StudioNode
        Materialized nodes in the view.
    edges : list of StudioEdge
        Materialized edges in the view.
    source : Literal["artifacts", "neo4j", "fixture"]
        Data source used to assemble this graph view.
    run_id : str or None, optional
        Pipeline run identifier if scoped to a specific run.
    graph_version : str
        Cache and staleness fingerprint of the view.
    schema_version : str
        Version identifier of the schema under which nodes/edges were interpreted.
    truncated : bool, default False
        Whether the node/edge budget truncated the full graph.
    dropped_count : int, default 0
        Number of elements omitted due to budget constraints.
    unmapped_predicates : dict of str to int, optional
        Frequencies of edge predicates that could not be mapped to polarity.
    unresolved_count : int, default 0
        Count of unresolved/dangling nodes materialized.
    layer_counts : dict of int to int, optional
        Element counts per layer to drive visibility toggles.
    """

    nodes: list[StudioNode]
    edges: list[StudioEdge]
    source: Literal["artifacts", "neo4j", "fixture"]
    run_id: str | None = None
    graph_version: str
    schema_version: str
    truncated: bool = False
    dropped_count: int = 0
    unmapped_predicates: dict[str, int] = Field(default_factory=dict)
    unresolved_count: int = 0
    layer_counts: dict[int, int] = Field(default_factory=dict)


class CypherResult(BaseModel):
    """Tabular execution result for ad-hoc Cypher queries.

    Parameters
    ----------
    columns : list of str
        Ordered list of column names returned by the query.
    rows : list of dict of str to Any
        Query rows serialized as dictionary mappings from column name to value.
    row_count : int, default 0
        Number of returned rows.
    execution_time_ms : float, default 0.0
        Server-side query execution latency in milliseconds.
    """

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0


def reify_inferences(
    nodes: list[StudioNode],
    edges: list[StudioEdge],
) -> tuple[list[StudioNode], list[StudioEdge]]:
    """Reify edges that target other edges into synthetic Inference nodes (D-21).

    In argumentation formalisms (e.g. Pollock, ASPIC+), an UNDERCUTS relation attacks
    an inferential step (edge) rather than a conclusion or premise (node). Because
    standard graph visualization engines require edges to terminate on nodes, undercuts
    targeting an edge are reified server-side into a synthetic 'Inference' midpoint node.

    Parameters
    ----------
    nodes : list of StudioNode
        Current list of materialized nodes.
    edges : list of StudioEdge
        Current list of materialized edges.

    Returns
    -------
    tuple of (list of StudioNode, list of StudioEdge)
        Updated nodes (containing newly synthesized Inference nodes) and updated edges
        (with target pointers rewired to the corresponding synthetic node).
    """
    edges_by_id = {e.id: e for e in edges}
    nodes_by_id = {n.id: n for n in nodes}
    synthetic_nodes: dict[str, StudioNode] = {}
    new_edges: list[StudioEdge] = []

    for edge in edges:
        # Check if this edge targets an edge
        is_edge_target = edge.target_kind == "edge" or (
            edge.type.upper() == "UNDERCUTS" and edge.target in edges_by_id
        )

        if is_edge_target:
            target_edge_id = edge.target
            target_edge = edges_by_id.get(target_edge_id)
            syn_id = f"inference::{target_edge_id}"

            if syn_id not in synthetic_nodes and syn_id not in nodes_by_id:
                if target_edge is not None:
                    syn_node = StudioNode(
                        id=syn_id,
                        layer=target_edge.layer,
                        type="Inference",
                        label=f"Inference: {target_edge.type}",
                        synthetic=True,
                        resolved=True,
                        props={
                            "reified_edge_id": target_edge.id,
                            "source": target_edge.source,
                            "target": target_edge.target,
                            "relation_type": target_edge.type,
                        },
                    )
                else:
                    syn_node = StudioNode(
                        id=syn_id,
                        layer=edge.layer,
                        type="Inference",
                        label=f"Inference: {target_edge_id}",
                        synthetic=True,
                        resolved=False,
                        props={"reified_edge_id": target_edge_id},
                    )
                synthetic_nodes[syn_id] = syn_node

            updated_props = dict(edge.props)
            updated_props["original_target_edge_id"] = target_edge_id
            new_edges.append(
                edge.model_copy(
                    update={
                        "target": syn_id,
                        "target_kind": "node",
                        "props": updated_props,
                    }
                )
            )
        else:
            new_edges.append(edge)

    all_nodes = list(nodes_by_id.values()) + list(synthetic_nodes.values())
    return all_nodes, new_edges

