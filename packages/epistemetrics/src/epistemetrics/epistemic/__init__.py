"""Epistemic evaluation and structural model analysis.

Operationalizes formal model class decomposition and epistemic capability
evaluation according to the structuralist metatheory of science (STNB).
"""

from __future__ import annotations

from epistemetrics.epistemic.dynamics import (
    DynamicsEvaluationResult,
    evaluate_diachronic_dynamics,
    verify_hard_core_invariance,
)
from epistemetrics.epistemic.model_evaluation import (
    ModelComponentEvaluationResult,
    calculate_anchor_iou,
    evaluate_model_components,
)
from epistemetrics.epistemic.poset_evaluation import (
    PosetEvaluationResult,
    evaluate_specialization_poset,
)
from epistemetrics.epistemic.qbaf import (
    GradualSemanticsModel,
    QBAFComparisonResult,
    QBAFGradualSemanticsSolver,
    QBAFSolverResult,
    WeightedQuadraticEnergySolver,
    WeightNormalizationMode,
    compare_qbaf_weight_modes,
    solve_continuous_qbaf,
    solve_qbaf_gradual_semantics,
)
from epistemetrics.epistemic.reduction_evaluation import (
    ReductionEvaluationResult,
    evaluate_intertheoretical_links,
)

__all__ = [
    # Diachronic dynamics & degeneration
    "DynamicsEvaluationResult",
    # QBAF Gradual Semantics
    "GradualSemanticsModel",
    # Intrinsic model component evaluation
    "ModelComponentEvaluationResult",
    # Specialization poset hierarchies
    "PosetEvaluationResult",
    "QBAFComparisonResult",
    "QBAFGradualSemanticsSolver",
    "QBAFSolverResult",
    # Intertheoretical link prediction
    "ReductionEvaluationResult",
    "WeightNormalizationMode",
    "WeightedQuadraticEnergySolver",
    "calculate_anchor_iou",
    "compare_qbaf_weight_modes",
    "evaluate_diachronic_dynamics",
    "evaluate_intertheoretical_links",
    "evaluate_model_components",
    "evaluate_specialization_poset",
    "solve_continuous_qbaf",
    "solve_qbaf_gradual_semantics",
    "verify_hard_core_invariance",
]
