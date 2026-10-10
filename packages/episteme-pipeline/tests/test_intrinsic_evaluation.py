"""Unit tests for pipeline intrinsic evaluation integration."""

import epistemetrics as em
from episteme_pipeline.evaluation import evaluate_theory_graph_components


def test_evaluate_theory_graph_components_integration():
    """Verify that evaluate_theory_graph_components correctly invokes epistemetrics."""
    gold_tg = em.TheoryGraph(name="Gold")
    gold_tg.add_node("T1", name="Theory Element", node_type=em.NodeType.THEORY_ELEMENT)
    gold_tg.add_node("A1", name="Axiom 1", node_type=em.NodeType.AXIOM, attributes={"formalAxiom": "F = m * a"})
    gold_tg.add_edge("T1", "A1", relation_type=em.RelationType.HAS_ACTUAL_MODEL)

    pred_tg = em.TheoryGraph(name="Pred")
    pred_tg.add_node("T1", name="Theory Element", node_type=em.NodeType.THEORY_ELEMENT)
    pred_tg.add_node("A1", name="Axiom 1", node_type=em.NodeType.AXIOM, attributes={"formalAxiom": "F = m * a"})
    pred_tg.add_edge("T1", "A1", relation_type=em.RelationType.HAS_ACTUAL_MODEL)

    result = evaluate_theory_graph_components(pred_tg, gold_tg)
    assert result.is_subsumed is True
    assert result.mcc == 1.0
    assert result.aor == 0.0
    assert result.pfs == 1.0
