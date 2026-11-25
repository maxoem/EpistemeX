"""Epistemic evaluation and structural model analysis.

Operationalizes formal model class decomposition and epistemic capability
evaluation according to the structuralist metatheory of science (STNB).
"""

from __future__ import annotations

from epistemetrics.epistemic.dynamics import (
    DynamicsEvaluationResult,
    compute_bounded_degeneration_proxy,
    evaluate_diachronic_dynamics,
    verify_hard_core_invariance,
)
from epistemetrics.epistemic.lenses import (
    DungLensResult,
    ECHOLensResult,
    compute_dung_extensions,
    project_to_echo_network,
    reduce_bipolar_to_dung,
    solve_echo_lens,
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
    BasePriorPolicy,
    GradualSemanticsModel,
    HyperedgeSpec,
    QBAFComparisonResult,
    QBAFGradualSemanticsSolver,
    QBAFPriorSensitivityResult,
    QBAFSolverResult,
    WeightedQuadraticEnergySolver,
    WeightNormalizationMode,
    compare_prior_policies,
    compare_qbaf_weight_modes,
    solve_continuous_qbaf,
    solve_qbaf_gradual_semantics,
)
from epistemetrics.epistemic.reduction_evaluation import (
    ReductionEvaluationResult,
    evaluate_intertheoretical_links,
)

__all__ = [
    "BasePriorPolicy",
    "DungLensResult",
    "DynamicsEvaluationResult",
    "ECHOLensResult",
    "GradualSemanticsModel",
    "HyperedgeSpec",
    "ModelComponentEvaluationResult",
    "PosetEvaluationResult",
    "QBAFComparisonResult",
    "QBAFGradualSemanticsSolver",
    "QBAFPriorSensitivityResult",
    "QBAFSolverResult",
    "ReductionEvaluationResult",
    "WeightNormalizationMode",
    "WeightedQuadraticEnergySolver",
    "calculate_anchor_iou",
    "compare_prior_policies",
    "compare_qbaf_weight_modes",
    "compute_bounded_degeneration_proxy",
    "compute_dung_extensions",
    "evaluate_diachronic_dynamics",
    "evaluate_intertheoretical_links",
    "evaluate_model_components",
    "evaluate_specialization_poset",
    "project_to_echo_network",
    "reduce_bipolar_to_dung",
    "solve_continuous_qbaf",
    "solve_echo_lens",
    "solve_qbaf_gradual_semantics",
    "verify_hard_core_invariance",
]
