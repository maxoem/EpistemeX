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
from epistemetrics.epistemic.reduction_evaluation import (
    ReductionEvaluationResult,
    evaluate_intertheoretical_links,
)

__all__ = [
    # Intrinsic model component evaluation
    "ModelComponentEvaluationResult",
    "evaluate_model_components",
    "calculate_anchor_iou",
    # Specialization poset hierarchies
    "PosetEvaluationResult",
    "evaluate_specialization_poset",
    # Intertheoretical link prediction
    "ReductionEvaluationResult",
    "evaluate_intertheoretical_links",
    # Diachronic dynamics & degeneration
    "DynamicsEvaluationResult",
    "evaluate_diachronic_dynamics",
    "verify_hard_core_invariance",
]
