"""Epistemetrics: Formal Theory Graph Evaluation and Epistemic Metrics.

A sovereign Python library for structural, argumentation, and epistemic
evaluation of scientific theory graphs.
"""

from __future__ import annotations

from epistemetrics.analysis import (
    EpistemicReport,
    analyze_theory_graph,
)
from epistemetrics.core.exceptions import (
    AdapterError,
    AlgorithmConvergenceError,
    AlgorithmError,
    DomainValidationError,
    EpistemetricsError,
    GDSNotAvailableError,
    GDSProjectionError,
    GraphNotFoundError,
    RepositoryConnectionError,
)
from epistemetrics.core.models import (
    AlgorithmExecutionMode,
    CentralityResult,
    EpistemicStatus,
    NodeType,
    PartitionResult,
    RelationType,
    TheoryEdge,
    TheoryNode,
)
from epistemetrics.epistemic import (
    DynamicsEvaluationResult,
    ModelComponentEvaluationResult,
    PosetEvaluationResult,
    ReductionEvaluationResult,
    calculate_anchor_iou,
    evaluate_diachronic_dynamics,
    evaluate_intertheoretical_links,
    evaluate_model_components,
    evaluate_specialization_poset,
    verify_hard_core_invariance,
)
from epistemetrics.graph.algorithms import (
    AdaptiveAlgorithmsEngine,
    GraphAlgorithmsEngine,
    NetworkXAlgorithmsEngine,
    betweenness_centrality,
    eigenvector_centrality,
    louvain_communities,
    page_rank,
    weakly_connected_components,
)
from epistemetrics.graph.theory_graph import TheoryGraph

__version__ = "0.1.0"

__all__ = [
    # Core domain graph and analysis
    "TheoryGraph",
    "TheoryNode",
    "TheoryEdge",
    "NodeType",
    "EpistemicStatus",
    "RelationType",
    "analyze_theory_graph",
    "EpistemicReport",
    # Epistemic model component evaluation
    "ModelComponentEvaluationResult",
    "evaluate_model_components",
    "calculate_anchor_iou",
    # Poset specialization hierarchies
    "PosetEvaluationResult",
    "evaluate_specialization_poset",
    # Intertheoretical link prediction
    "ReductionEvaluationResult",
    "evaluate_intertheoretical_links",
    # Diachronic dynamics & degeneration
    "DynamicsEvaluationResult",
    "evaluate_diachronic_dynamics",
    "verify_hard_core_invariance",
    # Engines
    "AdaptiveAlgorithmsEngine",
    "GraphAlgorithmsEngine",
    "NetworkXAlgorithmsEngine",
    # Algorithm entry points
    "betweenness_centrality",
    "eigenvector_centrality",
    "louvain_communities",
    "page_rank",
    "weakly_connected_components",
    # Result models
    "AlgorithmExecutionMode",
    "CentralityResult",
    "PartitionResult",
    # Exceptions
    "AdapterError",
    "AlgorithmConvergenceError",
    "AlgorithmError",
    "DomainValidationError",
    "EpistemetricsError",
    "GDSNotAvailableError",
    "GDSProjectionError",
    "GraphNotFoundError",
    "RepositoryConnectionError",
]
