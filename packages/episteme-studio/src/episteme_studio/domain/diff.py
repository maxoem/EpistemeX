"""Domain models for deterministic run-to-run diffing and progression analysis."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from episteme_studio.domain.graph import GraphView


class NodeDiffStatus(StrEnum):
    """Categorical difference status of a node between baseline and candidate runs.

    Attributes
    ----------
    RETAINED : str
        Node is present in both baseline (Run A) and candidate (Run B).
    GAINED : str
        Node was discovered in candidate (Run B) but absent from baseline (Run A).
    LOST : str
        Node was present in baseline (Run A) but absent from candidate (Run B).
    """

    RETAINED = "retained"
    GAINED = "gained"
    LOST = "lost"


class EdgeDiffStatus(StrEnum):
    """Categorical difference status of an edge between baseline and candidate runs.

    Attributes
    ----------
    RETAINED : str
        Edge is structurally preserved across both runs with compatible semantics.
    GAINED : str
        Edge was discovered in candidate (Run B) but absent from baseline (Run A).
    LOST : str
        Edge was present in baseline (Run A) but absent from candidate (Run B).
    POLARITY_INVERTED : str
        Edge connects the same source and target endpoints, but the argumentative
        polarity inverted (e.g. SUPPORTS (+1) in Run A vs ATTACKS (-1) in Run B).
    WEIGHT_SHIFTED : str
        Edge is present in both runs with identical polarity, but confidence or weight
        deviated beyond the sensitivity threshold.
    """

    RETAINED = "retained"
    GAINED = "gained"
    LOST = "lost"
    POLARITY_INVERTED = "polarity_inverted"
    WEIGHT_SHIFTED = "weight_shifted"


class PolarityInversion(BaseModel):
    """Detailed record of an argumentative contradiction or polarity inversion between runs.

    Parameters
    ----------
    edge_id : str
        Canonical composite edge identifier.
    source : str
        Source node identifier.
    target : str
        Target node identifier.
    source_label : str
        Human-readable label of the source node.
    target_label : str
        Human-readable label of the target node.
    predicate_a : str
        Predicate extracted in baseline Run A (e.g. 'SUPPORTS' or 'BESTAETIGT').
    polarity_a : int or None
        Polarity in Run A (+1 support, -1 attack, 0 neutral, or None).
    weight_a : float or None
        Edge weight or confidence in Run A.
    predicate_b : str
        Predicate extracted in candidate Run B (e.g. 'REFUTES' or 'WIDERSPRICHT').
    polarity_b : int or None
        Polarity in Run B (+1 support, -1 attack, 0 neutral, or None).
    weight_b : float or None
        Edge weight or confidence in Run B.
    scope : str
        Relational scope ('local' or 'global').
    """

    edge_id: str
    source: str
    target: str
    source_label: str
    target_label: str
    predicate_a: str
    polarity_a: int | None = None
    weight_a: float | None = None
    predicate_b: str
    polarity_b: int | None = None
    weight_b: float | None = None
    scope: str = "global"


class ConfigDeltaItem(BaseModel):
    """Single configuration divergence between baseline and candidate runs.

    Parameters
    ----------
    path : str
        Dot-separated configuration key path (e.g. 'models.llm_model').
    category : str
        Functional configuration tier ('models', 'prompts', 'phase', 'general').
    value_a : Any
        Resolved parameter value in baseline Run A.
    value_b : Any
        Resolved parameter value in candidate Run B.
    """

    path: str
    category: str
    value_a: Any = None
    value_b: Any = None


class DiffKPIs(BaseModel):
    """Executive key performance and divergence indicators between two pipeline runs.

    Parameters
    ----------
    nodes_retained : int
        Number of nodes shared by both runs.
    nodes_gained : int
        Number of new nodes introduced in Run B.
    nodes_lost : int
        Number of nodes present in Run A but missing in Run B.
    edges_retained : int
        Number of edges shared by both runs.
    edges_gained : int
        Number of new edges introduced in Run B.
    edges_lost : int
        Number of edges present in Run A but dropped in Run B.
    polarity_inversions_count : int
        Total number of direct polarity inversions detected.
    jaccard_node_similarity : float
        Jaccard similarity index of node sets: |A ∩ B| / |A ∪ B|.
    jaccard_edge_similarity : float
        Jaccard similarity index of edge endpoint tuples.
    l2_entity_delta : int
        Net change in L2 entities (Run B count minus Run A count).
    l3_atom_delta : int
        Net change in L3 argument components / theory atoms.
    max_rho_drift : float
        Maximum absolute change in gradual strength (|Δρ|) across shared atoms.
    """

    nodes_retained: int = 0
    nodes_gained: int = 0
    nodes_lost: int = 0
    edges_retained: int = 0
    edges_gained: int = 0
    edges_lost: int = 0
    polarity_inversions_count: int = 0
    jaccard_node_similarity: float = 1.0
    jaccard_edge_similarity: float = 1.0
    l2_entity_delta: int = 0
    l3_atom_delta: int = 0
    max_rho_drift: float = 0.0


class GraphDiffView(BaseModel):
    """Complete unified graph difference payload for the episteme-studio workbench.

    Parameters
    ----------
    run_a_id : str
        Identifier of baseline Run A.
    run_b_id : str
        Identifier of candidate Run B.
    union_graph : GraphView
        Combined graph view holding the union of all nodes and edges from both runs.
    node_diff : dict of str to NodeDiffStatus
        Lookup mapping each node ID in the union to its diff status.
    edge_diff : dict of str to EdgeDiffStatus
        Lookup mapping each edge ID in the union to its diff status.
    polarity_inversions : list of PolarityInversion
        List of all detected semantic/argumentative contradictions.
    rho_deltas : dict of str to float
        Map of shared Theory Atom ID to gradual strength change (rho_B - rho_A).
    config_diff : list of ConfigDeltaItem
        List of non-identical configuration parameters across the two runs.
    kpis : DiffKPIs
        Computed executive summary metrics.
    """

    run_a_id: str
    run_b_id: str
    union_graph: GraphView
    node_diff: dict[str, NodeDiffStatus] = Field(default_factory=dict)
    edge_diff: dict[str, EdgeDiffStatus] = Field(default_factory=dict)
    polarity_inversions: list[PolarityInversion] = Field(default_factory=list)
    rho_deltas: dict[str, float] = Field(default_factory=dict)
    config_diff: list[ConfigDeltaItem] = Field(default_factory=list)
    kpis: DiffKPIs = Field(default_factory=DiffKPIs)
