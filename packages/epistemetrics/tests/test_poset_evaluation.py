"""Unit tests for specialization poset hierarchies and model subsumption (ISSUE-031)."""

from __future__ import annotations

import epistemetrics as em
import networkx as nx
import pytest
from epistemetrics.epistemic.poset_evaluation import (
    check_hierarchical_subsumption,
    compute_specialization_reachability,
    compute_transitive_reduction_f1,
    evaluate_specialization_poset,
)


def test_poset_evaluation_on_valid_dag():
    """Verify that a valid specialization tree passes DAG, root, and subsumption checks."""
    ref_tg = em.TheoryGraph(name="RefGraph")
    ref_tg.add_node("T_Base", name="Base Theory", node_type=em.NodeType.THEORY_ELEMENT)
    ref_tg.add_node("T_Grav", name="Gravitational Theory", node_type=em.NodeType.THEORY_ELEMENT)
    ref_tg.add_node("T_Harmonic", name="Harmonic Theory", node_type=em.NodeType.THEORY_ELEMENT)

    # Base -> Grav, Base -> Harmonic
    ref_tg.add_edge("T_Base", "T_Grav", relation_type=em.RelationType.SPECIALIZES)
    ref_tg.add_edge("T_Base", "T_Harmonic", relation_type=em.RelationType.SPECIALIZES)

    # Add model classes
    ref_tg.add_node("M_Newton", name="Newton's Laws", node_type=em.NodeType.ACTUAL_MODEL)
    ref_tg.add_node("M_Grav", name="Gravitation Law", node_type=em.NodeType.ACTUAL_MODEL)
    ref_tg.add_node("M_Hooke", name="Hooke's Law", node_type=em.NodeType.ACTUAL_MODEL)

    ref_tg.add_edge("T_Base", "M_Newton", relation_type=em.RelationType.HAS_ACTUAL_MODEL)
    ref_tg.add_edge("T_Grav", "M_Grav", relation_type=em.RelationType.HAS_ACTUAL_MODEL)
    ref_tg.add_edge("T_Harmonic", "M_Hooke", relation_type=em.RelationType.HAS_ACTUAL_MODEL)

    result = evaluate_specialization_poset(ref_tg, ref_tg, gold_root_id="T_Base")

    assert result.is_dag is True
    assert result.is_strict_partial_order is True
    assert result.has_unique_root is True
    assert result.root_node == "T_Base"
    assert result.root_conformity is True
    assert result.precision == 1.0
    assert result.recall == 1.0
    assert result.f1 == 1.0
    assert result.reachability_f1 == 1.0
    assert result.hierarchical_subsumption_valid is True
    assert result.hierarchical_subsumption_score == 1.0
    assert len(result.cycles) == 0


def test_poset_detects_cycles_and_flags_non_dag():
    """Verify cycle detection catches circular specialization chains."""
    tg = em.TheoryGraph(name="CyclicGraph")
    tg.add_node("T_A", name="Theory A", node_type=em.NodeType.THEORY_ELEMENT)
    tg.add_node("T_B", name="Theory B", node_type=em.NodeType.THEORY_ELEMENT)
    tg.add_node("T_C", name="Theory C", node_type=em.NodeType.THEORY_ELEMENT)

    # Circular chain: A -> B -> C -> A
    tg.add_edge("T_A", "T_B", relation_type=em.RelationType.SPECIALIZES)
    tg.add_edge("T_B", "T_C", relation_type=em.RelationType.SPECIALIZES)
    tg.add_edge("T_C", "T_A", relation_type=em.RelationType.SPECIALIZES)

    result = evaluate_specialization_poset(tg)

    assert result.is_dag is False
    assert result.is_strict_partial_order is False
    assert len(result.cycles) > 0
    # Root should not be unique in a pure cycle
    assert result.has_unique_root is False


def test_poset_detects_self_loops():
    """Verify irreflexivity checks flag self-loops."""
    tg = em.TheoryGraph(name="SelfLoopGraph")
    tg.add_node("T_Self", name="Self Theory", node_type=em.NodeType.THEORY_ELEMENT)
    tg.add_edge("T_Self", "T_Self", relation_type=em.RelationType.SPECIALIZES)

    result = evaluate_specialization_poset(tg)
    assert result.is_strict_partial_order is False
    assert result.is_dag is False
    assert len(result.cycles) == 1
    assert result.cycles[0] == ["T_Self", "T_Self"]


def test_root_conformity_verification():
    """Verify root conformity requires matching reference root element."""
    pred_tg = em.TheoryGraph(name="Pred")
    pred_tg.add_node("T_WrongRoot", name="Wrong Root", node_type=em.NodeType.THEORY_ELEMENT)
    pred_tg.add_node("T_Sub", name="Sub Theory", node_type=em.NodeType.THEORY_ELEMENT)
    pred_tg.add_edge("T_WrongRoot", "T_Sub", relation_type=em.RelationType.SPECIALIZES)

    result = evaluate_specialization_poset(pred_tg, gold_root_id="T_ExpectedRoot")
    assert result.has_unique_root is True
    assert result.root_node == "T_WrongRoot"
    assert result.root_conformity is False


def test_transitive_reduction_f1_computation():
    """Verify transitive reduction eliminates redundant transitives before F1 calculation."""
    # Ref DAG: A -> B -> C and redundant shortcut A -> C
    ref_dag = nx.DiGraph()
    ref_dag.add_edge("A", "B")
    ref_dag.add_edge("B", "C")
    ref_dag.add_edge("A", "C")  # redundant

    # Pred DAG: A -> B -> C (minimal)
    pred_dag = nx.DiGraph()
    pred_dag.add_edge("A", "B")
    pred_dag.add_edge("B", "C")

    # Transitive reduction of both is {(A, B), (B, C)}
    prec, rec, f1 = compute_transitive_reduction_f1(pred_dag, ref_dag)
    assert prec == 1.0
    assert rec == 1.0
    assert f1 == 1.0


def test_specialization_reachability():
    """Verify reachability path calculation across multi-step derivations."""
    ref_dag = nx.DiGraph()
    ref_dag.add_edge("A", "B")
    ref_dag.add_edge("B", "C")
    # Reachable pairs: (A, B), (B, C), (A, C)

    pred_dag = nx.DiGraph()
    pred_dag.add_edge("A", "B")  # Missing (B, C)

    r_prec, r_rec, r_f1 = compute_specialization_reachability(pred_dag, ref_dag)
    assert r_prec == 1.0
    # Reference has 3 paths: (A,B), (A,C), (B,C); pred only has (A,B) -> recall = 1/3
    assert pytest.approx(r_rec, rel=1e-3) == 1.0 / 3.0
    assert r_f1 < 1.0


def test_hierarchical_subsumption_check():
    """Verify model inheritance subsumption identifies missing specialized laws."""
    tg = em.TheoryGraph(name="SubsumptionTest")
    tg.add_node("T_Parent", name="Parent Theory", node_type=em.NodeType.THEORY_ELEMENT)
    tg.add_node("T_Child", name="Child Theory", node_type=em.NodeType.THEORY_ELEMENT)
    tg.add_edge("T_Parent", "T_Child", relation_type=em.RelationType.SPECIALIZES)

    # Parent has actual model
    tg.add_node("M_Parent", name="Parent Axiom", node_type=em.NodeType.ACTUAL_MODEL)
    tg.add_edge("T_Parent", "M_Parent", relation_type=em.RelationType.HAS_ACTUAL_MODEL)

    # Child has NO actual model (vacuous specialization)
    score, valid, details = check_hierarchical_subsumption(tg)
    assert score == 0.0
    assert valid is False

    # Add child actual model
    tg.add_node("M_Child", name="Child Axiom", node_type=em.NodeType.ACTUAL_MODEL)
    tg.add_edge("T_Child", "M_Child", relation_type=em.RelationType.HAS_ACTUAL_MODEL)

    score_ok, valid_ok, _ = check_hierarchical_subsumption(tg)
    assert score_ok == 1.0
    assert valid_ok is True
