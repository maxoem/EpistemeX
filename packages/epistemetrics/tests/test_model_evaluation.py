"""Unit tests for intrinsic model component and property subsumption evaluation.

Verifies Bourbaki structuralist model decomposition across:
- M_p (Potential Models)
- M (Actual Models)
- M_pp (Partial Potential Models)
- GC (Global Constraints)
- I_0 (Paradigmatic Applications)
"""

import epistemetrics as em
import pytest
from epistemetrics.epistemic.model_evaluation import (
    calculate_anchor_iou,
    evaluate_model_components,
    formula_similarity,
)


def _build_gold_cpm_theory_graph() -> em.TheoryGraph:
    """Build a reference Classical Particle Mechanics (CPM) theory graph."""
    tg = em.TheoryGraph(name="Gold_CPM_Theory")

    # 1. Theory Element
    tg.add_node(
        "T_CPM",
        name="Classical Particle Mechanics",
        node_type=em.NodeType.THEORY_ELEMENT,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
    )

    # 2. Potential Model (M_p)
    tg.add_node(
        "Mp_CPM",
        name="M_p(CPM) Kinematics & Signatures",
        node_type=em.NodeType.POTENTIAL_MODEL,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={
            "base_sets": ["P (particles)", "T (time)", "s (space R3)"],
            "signatures": {"mass": "P -> R+", "force": "P x T x N -> R3"},
            "textAnchor": {
                "sourceDocId": "newton_principia_1687",
                "chunkId": "chunk_definitions",
                "charStart": 100,
                "charEnd": 300,
                "verbatimQuote": "Quantity of matter is a measure of the same arising from its density and magnitude.",
            },
        },
    )

    # 3. Actual Model (M)
    tg.add_node(
        "M_CPM_Newton2",
        name="M(CPM) Newton's Second Law",
        node_type=em.NodeType.ACTUAL_MODEL,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={
            "formalAxiom": "\\sum_i f(p, t, i) = m(p) \\cdot \\ddot{s}(p, t)",
            "textAnchor": {
                "sourceDocId": "newton_principia_1687",
                "chunkId": "chunk_law_2",
                "charStart": 500,
                "charEnd": 700,
                "verbatimQuote": "The alteration of motion is ever proportional to the motive force impressed.",
            },
        },
    )

    # 4. Partial Potential Model (M_pp)
    tg.add_node(
        "Mpp_CPM",
        name="M_pp(CPM) Kinematic Observables",
        node_type=em.NodeType.PARTIAL_POTENTIAL_MODEL,
        epistemic_status=em.EpistemicStatus.NEUTRAL,
        attributes={
            "observational_base": ["space-time trajectories s(p, t)"],
            "non_theoretical_terms": ["s", "t", "p"],
            "textAnchor": {
                "sourceDocId": "newton_principia_1687",
                "chunkId": "chunk_scholium",
                "charStart": 1000,
                "charEnd": 1200,
                "verbatimQuote": "Absolute, true, and mathematical time, of itself, and from its own nature flows equably.",
            },
        },
    )

    # 5. Global Constraint (GC)
    tg.add_node(
        "GC_Mass",
        name="GC Mass Invariance",
        node_type=em.NodeType.CONSTRAINT,
        epistemic_status=em.EpistemicStatus.HARD_CORE,
        attributes={
            "invariant_property": "mass m(p) is invariant across distinct systems and times",
        },
    )

    # 6. Paradigm (I_0)
    tg.add_node(
        "I0_HarmonicOscillator",
        name="Paradigmatic Application: Harmonic Oscillator",
        node_type=em.NodeType.PARADIGM,
        epistemic_status=em.EpistemicStatus.NEUTRAL,
        attributes={
            "exemplar_system": "Single particle Hookean spring mass system",
            "textAnchor": {
                "sourceDocId": "newton_principia_1687",
                "chunkId": "chunk_proposition_section",
                "charStart": 1500,
                "charEnd": 1700,
                "verbatimQuote": "If a body is drawn towards a center by a force proportional to the distance.",
            },
        },
    )

    # Structural decomposition edges
    tg.add_edge("T_CPM", "Mp_CPM", relation_type=em.RelationType.HAS_POTENTIAL_MODEL)
    tg.add_edge("T_CPM", "M_CPM_Newton2", relation_type=em.RelationType.HAS_ACTUAL_MODEL)
    tg.add_edge("T_CPM", "Mpp_CPM", relation_type=em.RelationType.HAS_PARTIAL_POTENTIAL_MODEL)
    tg.add_edge("T_CPM", "GC_Mass", relation_type=em.RelationType.HAS_CONSTRAINT)
    tg.add_edge("T_CPM", "I0_HarmonicOscillator", relation_type=em.RelationType.HAS_PARADIGM)

    return tg


class TestModelComponentEvaluation:
    """Test suite for evaluate_model_components and structuralist metrics."""

    def test_complete_identical_graph_evaluation(self):
        gold_tg = _build_gold_cpm_theory_graph()
        pred_tg = _build_gold_cpm_theory_graph()

        res = evaluate_model_components(pred_tg, gold_tg)

        assert isinstance(res, em.ModelComponentEvaluationResult)
        assert res.mcc == 1.0
        assert res.aor == 0.0
        assert res.pfs == 1.0
        assert res.ag_iou == 1.0
        assert res.is_subsumed is True
        assert len(res.unmatched_ref_nodes) == 0
        assert len(res.matched_node_pairs) == 6

        # Check breakdown
        assert res.component_scores["potential_models"] == 1.0
        assert res.component_scores["actual_models"] == 1.0
        assert res.component_scores["partial_potential_models"] == 1.0
        assert res.component_scores["constraints"] == 1.0
        assert res.component_scores["paradigms"] == 1.0

        # Check markdown generation
        md = res.to_markdown()
        assert "PASSED" in md
        assert "Axiomatic Omission Rate (AOR):** 0.0000" in md

    def test_axiomatic_omission_fails_capability_subsumption(self):
        gold_tg = _build_gold_cpm_theory_graph()
        pred_tg = _build_gold_cpm_theory_graph()

        # Remove the actual model (law) from predicted graph
        del pred_tg._nodes["M_CPM_Newton2"]
        pred_tg._edges = [e for e in pred_tg._edges if e.target != "M_CPM_Newton2" and e.source != "M_CPM_Newton2"]
        pred_tg.nx_graph.remove_node("M_CPM_Newton2")

        res = evaluate_model_components(pred_tg, gold_tg)

        # AOR must be 1.0 because the single actual model is missing
        assert res.aor == 1.0
        # Subsumption must fail because laws are omitted
        assert res.is_subsumed is False
        assert "M_CPM_Newton2" in res.unmatched_ref_nodes

    def test_partial_component_omission(self):
        gold_tg = _build_gold_cpm_theory_graph()
        pred_tg = _build_gold_cpm_theory_graph()

        # Omit paradigm
        del pred_tg._nodes["I0_HarmonicOscillator"]
        pred_tg._edges = [e for e in pred_tg._edges if e.target != "I0_HarmonicOscillator"]
        pred_tg.nx_graph.remove_node("I0_HarmonicOscillator")

        res = evaluate_model_components(pred_tg, gold_tg, min_mcc=1.0)

        # 4 out of 5 core components matched
        assert res.mcc == 0.8
        assert res.aor == 0.0  # Laws were not omitted
        assert res.is_subsumed is False  # Fails because min_mcc=1.0 required
        assert "I0_HarmonicOscillator" in res.unmatched_ref_nodes

    def test_property_perturbation_reduces_fidelity(self):
        gold_tg = _build_gold_cpm_theory_graph()
        pred_tg = _build_gold_cpm_theory_graph()

        # Perturb epistemic status on actual model
        node = pred_tg._nodes["M_CPM_Newton2"]
        pred_tg.add_node(
            "M_CPM_Newton2",
            name=node.name,
            node_type=em.NodeType.CLAIM,  # Perturbed type
            epistemic_status=em.EpistemicStatus.PROTECTIVE_BELT,  # Perturbed status
            attributes=node.attributes,
        )

        res = evaluate_model_components(pred_tg, gold_tg)
        assert res.pfs < 1.0

    def test_empty_graphs_zero_division_guard(self):
        empty_ref = em.TheoryGraph(name="EmptyRef")
        empty_pred = em.TheoryGraph(name="EmptyPred")

        res = evaluate_model_components(empty_pred, empty_ref)
        assert res.mcc == 1.0
        assert res.aor == 0.0
        assert res.pfs == 1.0
        assert res.is_subsumed is True

        # Non-empty ref against empty pred
        gold_tg = _build_gold_cpm_theory_graph()
        res2 = evaluate_model_components(empty_pred, gold_tg)
        assert res2.mcc == 0.0
        assert res2.aor == 1.0
        assert res2.is_subsumed is False

    def test_formula_normalization_and_similarity(self):
        f1 = "\\sum_i f(p, t, i) = m(p) \\cdot \\ddot{s}(p, t)"
        f2 = "sum f(p, t, i) = m(p) * ddot s(p, t)"
        assert formula_similarity(f1, f2) > 0.8

        f3 = "E = m * c^2"
        assert formula_similarity(f1, f3) < 0.3

    def test_anchor_iou_calculation(self):
        # Exact match
        a1 = {"charStart": 100, "charEnd": 200, "sourceDocId": "doc1"}
        a2 = {"charStart": 100, "charEnd": 200, "sourceDocId": "doc1"}
        assert calculate_anchor_iou(a1, a2) == 1.0

        # Partial overlap (intersection = 50, union = 150)
        a3 = {"charStart": 150, "charEnd": 250, "sourceDocId": "doc1"}
        assert pytest.approx(calculate_anchor_iou(a1, a3), 0.01) == 50.0 / 150.0

        # Disjoint
        a4 = {"charStart": 300, "charEnd": 400, "sourceDocId": "doc1"}
        assert calculate_anchor_iou(a1, a4) == 0.0

        # Different documents
        a5 = {"charStart": 100, "charEnd": 200, "sourceDocId": "doc2"}
        assert calculate_anchor_iou(a1, a5) == 0.0

    def test_networkx_graph_compatibility(self):
        # Evaluation should accept raw NetworkX DiGraphs
        gold_tg = _build_gold_cpm_theory_graph()
        gold_nx = gold_tg.to_networkx()
        pred_nx = gold_tg.to_networkx()

        res = evaluate_model_components(pred_nx, gold_nx)
        assert res.mcc == 1.0
        assert res.aor == 0.0
        assert res.is_subsumed is True
