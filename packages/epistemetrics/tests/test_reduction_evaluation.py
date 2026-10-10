"""Unit tests for intertheoretical link prediction and reduction evaluation (ISSUE-031)."""

from __future__ import annotations

import epistemetrics as em
from epistemetrics.epistemic.reduction_evaluation import (
    evaluate_intertheoretical_links,
)


def test_intertheoretical_links_perfect_match():
    """Verify precision, recall, and F1 when predicted reduction links match reference."""
    ref_tg = em.TheoryGraph(name="RefNet")
    ref_tg.add_node("T_Collision", name="Collision Mechanics", node_type=em.NodeType.THEORY_ELEMENT)
    ref_tg.add_node("T_CPM", name="Classical Particle Mechanics", node_type=em.NodeType.THEORY_ELEMENT)
    ref_tg.add_node("T_Thermodynamics", name="Thermodynamics", node_type=em.NodeType.THEORY_ELEMENT)

    # Cross-theory links
    ref_tg.add_edge("T_Collision", "T_CPM", relation_type=em.RelationType.REDUCES_TO)
    ref_tg.add_edge("T_Thermodynamics", "T_CPM", relation_type=em.RelationType.PRESUPPOSES)

    result = evaluate_intertheoretical_links(ref_tg, ref_tg)

    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f1 == 1.0
    assert result.reduction_links_matched_count == 1
    assert result.presupposition_links_matched_count == 1
    assert len(result.unmatched_ref_links) == 0
    assert len(result.spurious_pred_links) == 0


def test_intertheoretical_links_partial_and_spurious():
    """Verify precision and recall when some links are omitted and extra links are spurious."""
    ref_tg = em.TheoryGraph(name="Ref")
    ref_tg.add_edge("T1", "T2", relation_type=em.RelationType.REDUCES_TO)
    ref_tg.add_edge("T1", "T3", relation_type=em.RelationType.PRESUPPOSES)

    pred_tg = em.TheoryGraph(name="Pred")
    # Correct link
    pred_tg.add_edge("T1", "T2", relation_type=em.RelationType.REDUCES_TO)
    # Spurious link
    pred_tg.add_edge("T2", "T3", relation_type=em.RelationType.REDUCES_TO)
    # Missing: T1 presupposes T3

    result = evaluate_intertheoretical_links(pred_tg, ref_tg)

    # 1 TP (T1->T2), 1 FP (T2->T3), 1 FN (T1->T3)
    assert result.precision == 0.5
    assert result.recall == 0.5
    assert result.f1 == 0.5
    assert len(result.matched_links) == 1
    assert len(result.unmatched_ref_links) == 1
    assert len(result.spurious_pred_links) == 1


def test_intertheoretical_links_node_mapping():
    """Verify node mapping translates predicted node IDs to reference IDs."""
    ref_tg = em.TheoryGraph(name="Ref")
    ref_tg.add_edge("str:T_Gold_1", "str:T_Gold_2", relation_type=em.RelationType.REDUCES_TO)

    pred_tg = em.TheoryGraph(name="Pred")
    pred_tg.add_edge("pred_t1", "pred_t2", relation_type=em.RelationType.REDUCES_TO)

    mapping = {"pred_t1": "str:T_Gold_1", "pred_t2": "str:T_Gold_2"}
    result = evaluate_intertheoretical_links(pred_tg, ref_tg, node_mapping=mapping)

    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f1 == 1.0
