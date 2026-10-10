"""Unit tests for diachronic dynamics and Lakatosian degeneration index (ISSUE-031)."""

from __future__ import annotations

import epistemetrics as em
from epistemetrics.epistemic.dynamics import (
    evaluate_diachronic_dynamics,
    verify_hard_core_invariance,
)


def test_dynamics_progressive_research_program():
    """Verify progressive trajectory where novel empirical content outpaces anomalies."""
    # Epoch 0
    t0 = em.TheoryGraph(name="Epoch_0")
    t0.add_node(
        "Axiom_Newton2",
        name="Newton 2",
        node_type=em.NodeType.AXIOM,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={"formalAxiom": "F = m * a"},
    )
    t0.add_node("Paradigm_Orbits", name="Orbits", node_type=em.NodeType.PARADIGM)

    # Epoch 1: Added 1 auxiliary hypothesis, but explained 5 new empirical paradigms with 0 anomalies
    t1 = em.TheoryGraph(name="Epoch_1")
    t1.add_node(
        "Axiom_Newton2",
        name="Newton 2",
        node_type=em.NodeType.AXIOM,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={"formalAxiom": "F = m * a"},
    )
    t1.add_node("Aux_Harmonic", name="Spring Hooke", node_type=em.NodeType.HYPOTHESIS)
    t1.add_node("Paradigm_Orbits", name="Orbits", node_type=em.NodeType.PARADIGM)
    for i in range(5):
        t1.add_node(f"Paradigm_Novel_{i}", name=f"Exp_{i}", node_type=em.NodeType.PARADIGM)

    result = evaluate_diachronic_dynamics([t0, t1])

    assert result.core_invariant is True
    # DI = (1 + 0) / (5 + 1e-6) ~ 0.2 < 1.0 -> Progressive
    assert result.degeneration_index < 0.3
    assert result.is_progressive is True
    assert result.delta_auxiliary == 1
    assert result.delta_empirical_content == 5


def test_dynamics_degenerating_program_with_adhoc_immunization():
    """Verify degenerating program where auxiliary patches accumulate without new content."""
    # Epoch 0
    t0 = {
        "core_axioms": {"A1": "Core Law"},
        "auxiliary_hypotheses": [],
        "anomalies": ["Anom_1"],
        "empirical_content": ["E1"],
    }
    # Epoch 1: 3 new auxiliary hypotheses patched in, no new empirical content, 2 anomalies remain
    t1 = {
        "core_axioms": {"A1": "Core Law"},
        "auxiliary_hypotheses": ["Aux_AdHoc_1", "Aux_AdHoc_2", "Aux_AdHoc_3"],
        "anomalies": ["Anom_1", "Anom_2"],
        "empirical_content": ["E1"],  # Delta emp = 0
    }

    result = evaluate_diachronic_dynamics([t0, t1])

    # DI = (3 + 2) / (0 + 1e-6) >> 1.0 -> Degenerating
    assert result.degeneration_index > 1.0
    assert result.is_progressive is False
    assert result.delta_auxiliary == 3
    assert result.anomalies_count == 2
    assert result.delta_empirical_content == 0
    # Node immunization should detect pure immunizing patches
    for score in result.node_immunization_scores.values():
        assert score == 1.0


def test_dynamics_flags_core_axiom_mutation():
    """Verify invariance checker flags any alteration or dropping of foundational core laws."""
    t0 = em.TheoryGraph(name="Epoch_0")
    t0.add_node(
        "Axiom_Newton2",
        name="Newton 2",
        node_type=em.NodeType.AXIOM,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={"formalAxiom": "F = m * a"},
    )

    # Epoch 1 modifies the formula of the core axiom
    t1 = em.TheoryGraph(name="Epoch_1")
    t1.add_node(
        "Axiom_Newton2",
        name="Newton 2",
        node_type=em.NodeType.AXIOM,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={"formalAxiom": "F = m * a + correction_term"},
    )

    is_inv, violations = verify_hard_core_invariance([t0, t1])
    assert is_inv is False
    assert len(violations) == 1
    assert "modified" in violations[0]["reason"]

    res = evaluate_diachronic_dynamics([t0, t1])
    assert res.core_invariant is False
    assert res.is_progressive is False
