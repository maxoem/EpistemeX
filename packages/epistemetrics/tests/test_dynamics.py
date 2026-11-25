"""Unit tests for diachronic dynamics and bounded Lakatosian degeneration proxy."""

from __future__ import annotations

import pytest

import epistemetrics as em
from epistemetrics.epistemic.dynamics import (
    compute_bounded_degeneration_proxy,
    evaluate_diachronic_dynamics,
    verify_hard_core_invariance,
)


def test_bounded_degeneration_proxy_invariants() -> None:
    """Verify [0, 1] bounds, zero-denominator safety, and Fail_a invariance."""
    assert compute_bounded_degeneration_proxy(0, 0, 0) == (0.0, 0.0)

    # Pure novel success
    d0, r0 = compute_bounded_degeneration_proxy(novel_successes=5, direct_failures=0, adhoc_failures=0)
    assert d0 == pytest.approx(0.0)
    assert r0 == pytest.approx(0.0)

    # Pure ad-hoc immunization without novel content saturates at 1.0 (not unbounded)
    d_max, r_max = compute_bounded_degeneration_proxy(novel_successes=0, direct_failures=2, adhoc_failures=3)
    assert d_max == pytest.approx(1.0)
    assert r_max == pytest.approx(1.0)

    # Monotonicity and zero perverse distortion from Fail_a:
    # Adding direct refutations (Fail_a) leaves D_deg invariant and increases R_fail.
    d_a1, r_a1 = compute_bounded_degeneration_proxy(novel_successes=4, direct_failures=1, adhoc_failures=2)
    d_a2, r_a2 = compute_bounded_degeneration_proxy(novel_successes=4, direct_failures=10, adhoc_failures=2)
    assert d_a1 == pytest.approx(d_a2)
    assert d_a1 == pytest.approx(2.0 / 6.0)
    assert r_a2 > r_a1

    # Adding ad-hoc immunizations (Fail_b) strictly increases D_deg
    d_b2, _ = compute_bounded_degeneration_proxy(novel_successes=4, direct_failures=1, adhoc_failures=4)
    assert d_b2 > d_a1

    # Adding corroborated novel predictions strictly decreases D_deg
    d_n2, _ = compute_bounded_degeneration_proxy(novel_successes=8, direct_failures=1, adhoc_failures=2)
    assert d_n2 < d_a1


def test_dynamics_progressive_research_program() -> None:
    """Verify progressive trajectory where novel empirical content outpaces anomalies."""
    t0 = em.TheoryGraph(name="Epoch_0")
    t0.add_node(
        "Axiom_Newton2",
        name="Newton 2",
        node_type=em.NodeType.AXIOM,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={"formalAxiom": "F = m * a"},
    )
    t0.add_node("Paradigm_Orbits", name="Orbits", node_type=em.NodeType.PARADIGM)

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
        t1.add_node(
            f"Paradigm_Novel_{i}", name=f"Exp_{i}", node_type=em.NodeType.PARADIGM
        )
    t1.add_node(
        "Paradigm_Accommodated",
        name="Known Retrodiction",
        node_type=em.NodeType.PARADIGM,
        attributes={"is_accommodated": True},
    )

    result = evaluate_diachronic_dynamics([t0, t1])

    assert result.core_invariant is True
    assert 0.0 <= result.degeneration_index <= 1.0
    assert result.degeneration_index == pytest.approx(0.0)
    assert result.empirical_failure_rate == pytest.approx(0.0)
    assert result.is_progressive is True
    assert result.delta_auxiliary == 1
    assert result.delta_empirical_content == 5
    assert result.accommodated_successes_count == 1


def test_dynamics_degenerating_program_with_adhoc_immunization() -> None:
    """Verify degenerating program where auxiliary patches accumulate without new content."""
    t0 = {
        "core_axioms": {"A1": "Core Law"},
        "auxiliary_hypotheses": [],
        "anomalies": ["Anom_1"],
        "empirical_content": ["E1"],
    }
    t1 = {
        "core_axioms": {"A1": "Core Law"},
        "auxiliary_hypotheses": ["Aux_AdHoc_1", "Aux_AdHoc_2", "Aux_AdHoc_3"],
        "anomalies": ["Anom_1", "Anom_2"],
        "empirical_content": ["E1"],
        "accommodated_successes": ["Retro_1", "Retro_2"],
    }

    result = evaluate_diachronic_dynamics([t0, t1])

    # D_deg = 3 / (0 + 3) = 1.0, R_fail = (2 + 3) / (0 + 2 + 3) = 1.0
    assert result.degeneration_index == pytest.approx(1.0)
    assert result.empirical_failure_rate == pytest.approx(1.0)
    assert result.is_progressive is False
    assert result.delta_auxiliary == 3
    assert result.adhoc_failures_count == 3
    assert result.anomalies_count == 2
    assert result.delta_empirical_content == 0
    assert result.accommodated_successes_count == 2
    for score in result.node_immunization_scores.values():
        assert score == 1.0


def test_dynamics_flags_core_axiom_mutation() -> None:
    """Verify invariance checker flags any alteration or dropping of foundational core laws."""
    t0 = em.TheoryGraph(name="Epoch_0")
    t0.add_node(
        "Axiom_Newton2",
        name="Newton 2",
        node_type=em.NodeType.AXIOM,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={"formalAxiom": "F = m * a"},
    )

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
