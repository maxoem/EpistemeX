"""Tests for QBAF gradual semantics solver and weight normalization modes.

Verifies mathematical convergence, numerical stability, decoupled modal
weight ingestion, and empirical accuracy admissibility gating.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest
from epistemetrics.core.models import RelationType
from epistemetrics.epistemic.qbaf import (
    GradualSemanticsModel,
    QBAFGradualSemanticsSolver,
    WeightedQuadraticEnergySolver,
    WeightNormalizationMode,
    compare_qbaf_weight_modes,
    solve_continuous_qbaf,
    solve_qbaf_gradual_semantics,
)
from epistemetrics.graph.theory_graph import TheoryGraph
from scipy.integrate import solve_ivp


class TestQBAFGradualSemantics:
    """Test suite for QBAF gradual semantics solvers."""

    def test_simple_support_and_attack_quadratic(self) -> None:
        """Verify basic support and attack convergence under Quadratic Energy model."""
        nodes = {
            "claim": 0.5,
            "supporter": 0.8,
            "attacker": 0.7,
        }
        edges = [
            ("supporter", "claim", 0.9, 1),  # Support with weight 0.9
            ("attacker", "claim", 0.6, -1),  # Attack with weight 0.6
        ]

        result = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            semantics_model=GradualSemanticsModel.QUADRATIC,
        )

        assert result.converged
        assert len(result.degrees) == 3
        # Since supporter has higher plausibility (0.8) and weight (0.9) than attacker (0.7 * 0.6 = 0.42),
        # net justification for 'claim' should increase above 0.5
        assert result.degrees["claim"] > 0.5
        assert 0.0 <= result.degrees["claim"] <= 1.0

    def test_euler_and_categorizer_models(self) -> None:
        """Verify convergence under Euler and Categorizer models."""
        nodes = {"A": 0.6, "B": 0.9}
        edges = [("B", "A", 0.8, 1)]  # B supports A

        res_euler = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            semantics_model=GradualSemanticsModel.EULER,
        )
        assert res_euler.converged
        assert res_euler.degrees["A"] > 0.6

        res_cat = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            semantics_model=GradualSemanticsModel.CATEGORIZER,
        )
        assert res_cat.converged
        assert res_cat.degrees["A"] > 0.6

    def test_cyclic_argumentation_stability(self) -> None:
        """Verify cyclic dialectical network converges deterministically without oscillation."""
        # Mutual attack loop: A attacks B, B attacks A
        nodes = {"A": 0.7, "B": 0.7}
        edges = [
            ("A", "B", 0.8, -1),
            ("B", "A", 0.8, -1),
        ]

        solver = QBAFGradualSemanticsSolver(
            semantics_model=GradualSemanticsModel.QUADRATIC,
            max_iterations=100,
            tolerance=1e-5,
        )
        result = solver.solve(nodes=nodes, edges=edges)

        assert result.converged
        # Symmetric graph must yield identical justification degrees for A and B
        assert abs(result.degrees["A"] - result.degrees["B"]) < 1e-4
        assert result.degrees["A"] < 0.7  # Degraded by attack

    def test_decoupled_calibrated_modal_weighting(self) -> None:
        """Verify decoupled weight calculation w = M(modal_strength) * P(stance)."""
        tg = TheoryGraph(name="ModalityGraph")
        tg.add_node("axiom_core", confidence=1.0)
        tg.add_node("hypothesis_claim", confidence=0.5)

        # High stance extraction confidence (0.95), but tentative modal hypothesis (M=0.30)
        tg.add_edge(
            source="axiom_core",
            target="hypothesis_claim",
            relation_type=RelationType.SUPPORTS,
            class_probability=0.95,
            modal_strength=0.30,
        )

        edge = tg.edges[0]
        # effective_weight should be M * P = 0.30 * 0.95 = 0.285
        assert pytest.approx(edge.effective_weight, rel=1e-3) == 0.285

        result = solve_qbaf_gradual_semantics(
            nodes=tg.nodes,
            edges=tg.edges,
            normalization_mode=WeightNormalizationMode.CALIBRATED_MODAL,
        )
        assert result.converged
        assert result.degrees["hypothesis_claim"] > 0.5

        # Verify first-class TheoryGraph container ingestion
        res_graph = solve_qbaf_gradual_semantics(
            nodes=tg,
            normalization_mode=WeightNormalizationMode.CALIBRATED_MODAL,
        )
        assert res_graph.converged
        assert (
            res_graph.degrees["hypothesis_claim"] == result.degrees["hypothesis_claim"]
        )

    def test_admissibility_gating_prunes_inadmissible_edges(self) -> None:
        """Verify empirical accuracy below threshold prunes edges."""
        edges = [
            {
                "source": "premise_reliable",
                "target": "conclusion",
                "relation_type": "SUPPORTS",
                "empirical_accuracy": 0.85,
                "class_probability": 0.90,
                "modal_strength": 1.0,
            },
            {
                "source": "premise_uncalibrated",
                "target": "conclusion",
                "relation_type": "ATTACKS",
                "empirical_accuracy": 0.40,  # Below 0.70 threshold!
                "class_probability": 0.95,
                "modal_strength": 1.0,
            },
        ]
        nodes = {
            "conclusion": 0.5,
            "premise_reliable": 0.8,
            "premise_uncalibrated": 0.8,
        }

        # With admissibility threshold 0.70, the low-accuracy attack should be pruned
        res_gated = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            admissibility_threshold=0.70,
        )

        assert res_gated.admissibility_pruned_count == 1
        # Conclusion should be supported and not attacked
        assert res_gated.degrees["conclusion"] > 0.5
        assert res_gated.attack_sums["conclusion"] == 0.0

    def test_compare_weight_modes_detects_distortion(self) -> None:
        """Verify comparative analysis reveals drift between calibrated modal and unweighted binary."""
        nodes = {
            "hypothesis": 0.5,
            "strong_axiom": 0.9,
            "tentative_speculation": 0.9,
        }
        edges = [
            # Strong axiom with deductive modality M=1.0, P=0.95 -> w = 0.95
            {
                "source": "strong_axiom",
                "target": "hypothesis",
                "relation_type": "SUPPORTS",
                "modal_strength": 1.0,
                "class_probability": 0.95,
            },
            # Tentative speculation with weak modality M=0.20, P=0.90 -> w = 0.18
            # In binary unweighted mode, this speculation attacks with w=1.0, severely distorting the outcome!
            {
                "source": "tentative_speculation",
                "target": "hypothesis",
                "relation_type": "ATTACKS",
                "modal_strength": 0.20,
                "class_probability": 0.90,
            },
        ]

        comp = compare_qbaf_weight_modes(
            nodes=nodes,
            edges=edges,
            semantics_model=GradualSemanticsModel.QUADRATIC,
        )

        assert comp.mean_absolute_drift > 0.0
        assert comp.max_drift > 0.0
        assert comp.max_drift_node == "hypothesis"
        # In calibrated mode, strong support (0.95) outweighs weak speculative attack (0.18)
        assert comp.calibrated_result.degrees["hypothesis"] > 0.5
        # In unweighted binary mode, unit attack distorts hypothesis downward
        assert (
            comp.unweighted_result.degrees["hypothesis"]
            < comp.calibrated_result.degrees["hypothesis"]
        )

    def test_duality_cancellation_and_controversy_telemetry(self) -> None:
        """Verify Duality/Balance cancellation (s = w when E = 0) while tracking Keynes-Gärdenfors controversy."""
        # Target X (w=0.5) has symmetric supporter S and attacker A
        nodes = {"X": 0.5, "S": 0.8, "A": 0.8}
        edges = [
            ("S", "X", 0.8, 1),  # Support with weight 0.8
            ("A", "X", 0.8, -1),  # Attack with weight 0.8
        ]

        # 1. Discrete gradual semantics
        res_disc = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            semantics_model=GradualSemanticsModel.QUADRATIC,
        )
        assert res_disc.converged
        assert pytest.approx(res_disc.degrees["X"], abs=1e-4) == 0.5
        assert res_disc.total_weight_of_evidence["X"] > 1.0
        assert res_disc.volatility_index["X"] > 0.5

        # 2. Continuous Quadratic Energy semantics
        res_cont = solve_continuous_qbaf(nodes=nodes, edges=edges)
        assert res_cont.converged
        assert pytest.approx(res_cont.degrees["X"], abs=1e-4) == 0.5
        assert res_cont.total_weight_of_evidence["X"] > 1.0
        assert res_cont.volatility_index["X"] > 0.5

        # Contrast with unattacked, unsupported baseline claim
        res_empty = solve_continuous_qbaf(nodes={"uncontested": 0.5}, edges=[])
        assert pytest.approx(res_empty.degrees["uncontested"], abs=1e-4) == 0.5
        assert res_empty.total_weight_of_evidence["uncontested"] == 0.0
        assert res_empty.volatility_index["uncontested"] == 0.0

    def test_dag_closed_form_vs_ode_equivalence(self) -> None:
        """Verify topological O(|V| + |E|) closed-form evaluation matches adaptive ODE integration (Proposition 5)."""
        # 5-atom argument cascade:
        # A, B (root axioms) -> C, D (intermediate claims) -> E (final thesis)
        base_scores = np.array([0.9, 0.7, 0.5, 0.6, 0.5])
        g_supp = np.zeros((5, 5))
        g_att = np.zeros((5, 5))

        # A (0) supports C (2) with 0.8
        g_supp[0, 2] = 0.8
        # B (1) attacks C (2) with 0.4
        g_att[1, 2] = 0.4
        # B (1) supports D (3) with 0.7
        g_supp[1, 3] = 0.7
        # C (2) supports E (4) with 0.9
        g_supp[2, 4] = 0.9
        # D (3) supports E (4) with 0.6
        g_supp[3, 4] = 0.6

        solver = WeightedQuadraticEnergySolver(rtol=1e-6, atol=1e-8)

        # 1. Closed-form topological sort
        adj = (g_supp + g_att) > 0
        g_nx = nx.DiGraph(adj)
        topo_order = list(nx.topological_sort(g_nx))
        s_closed = solver._solve_dag_closed_form(
            base_scores, g_supp.T, g_att.T, topo_order
        )

        # 2. ODE numerical integration via solve_ivp
        sol = solve_ivp(
            fun=solver._derivatives,
            t_span=(0.0, 50.0),
            y0=base_scores.copy(),
            args=(base_scores, g_supp.T, g_att.T),
            method="RK45",
            rtol=1e-7,
            atol=1e-9,
        )
        s_ode = sol.y[:, -1]

        # Verify equivalence within tolerance across all 5 nodes
        max_diff = np.max(np.abs(s_closed - s_ode))
        assert max_diff < 1e-4

        # Verify solve() fast-path returns s_closed
        s_fast, conv, _ = solver.solve(base_scores, g_supp, g_att)
        assert conv
        np.testing.assert_allclose(s_fast, s_closed, atol=1e-6)

    def test_early_stationary_termination_event(self) -> None:
        """Verify cyclic network terminates integration early via stationary root-finding event."""
        # Mutual attack loop: A attacks B, B attacks A

        solver = WeightedQuadraticEnergySolver(t_max=50.0, atol=1e-5)
        w = np.array([0.7, 0.7])
        g_supp = np.zeros((2, 2))
        g_att = np.array([[0.0, 0.8], [0.8, 0.0]])

        # Execute direct solve
        s_final, converged, _telemetry = solver.solve(w, g_supp, g_att)

        assert converged
        assert pytest.approx(s_final[0], rel=1e-3) == s_final[1]
        assert s_final[0] < 0.7

        # Test solve_ivp event directly to verify termination time < 10.0
        event_tol = max(solver.atol, 1e-4)

        def stationary_event(t, s, w_arr, supp_t, att_t):
            ds = solver._derivatives(t, s, w_arr, supp_t, att_t)
            return float(np.max(np.abs(ds)) - event_tol)

        stationary_event.terminal = True
        stationary_event.direction = -1

        sol = solve_ivp(
            fun=solver._derivatives,
            t_span=(0.0, 50.0),
            y0=w.copy(),
            args=(w, g_supp.T, g_att.T),
            method="RK45",
            rtol=1e-5,
            atol=1e-7,
            events=stationary_event,
        )

        assert sol.status == 1  # Terminated by event
        assert sol.t[-1] < 10.0  # Much earlier than t_max = 50.0

    def test_cyclic_limit_cycle_immunity(self) -> None:
        """Verify cyclic mutual rebuttal loop reaches stable equilibrium without flip-flop oscillation."""
        nodes = {"A": 0.8, "B": 0.8}
        edges = [
            {
                "source": "A",
                "target": "B",
                "relation_type": "ATTACKS",
                "inferential_force": 0.8,
            },
            {
                "source": "B",
                "target": "A",
                "relation_type": "ATTACKS",
                "inferential_force": 0.8,
            },
        ]

        res = solve_continuous_qbaf(nodes=nodes, edges=edges)

        assert res.converged
        assert abs(res.degrees["A"] - res.degrees["B"]) < 1e-4
        assert res.degrees["A"] < 0.8
        assert 0.0 <= res.degrees["A"] <= 1.0

    def test_numerical_stiffness_100_attacker_hub(self) -> None:
        """Verify numerical stability on citation hub attacked by 100 arguments without stiffness breakdown."""
        n_attackers = 100
        nodes = {"hub_claim": 0.8}
        edges = []

        for i in range(n_attackers):
            att_id = f"attacker_{i}"
            nodes[att_id] = 0.8
            edges.append(
                {
                    "source": att_id,
                    "target": "hub_claim",
                    "relation_type": "ATTACKS",
                    "inferential_force": 0.8,
                }
            )

        res = solve_continuous_qbaf(nodes=nodes, edges=edges)

        assert res.converged
        # Severely degraded but strictly positive and bounded in [0, 1]
        assert not np.isnan(res.degrees["hub_claim"])
        assert not np.isinf(res.degrees["hub_claim"])
        assert 0.0 <= res.degrees["hub_claim"] < 0.05
        assert res.degrees["hub_claim"] >= 0.0

    def test_admissibility_mode_hard_vs_soft_gating(self) -> None:
        """Verify Hard pruning drops sub-threshold edge while Soft margin smoothly relaxes weight."""
        nodes = {"conclusion": 0.5, "premise": 0.8}
        # Premise supports conclusion with stance_probability 0.74 (below tau_p = 0.75)
        edges = [
            {
                "source": "premise",
                "target": "conclusion",
                "relation_type": "SUPPORTS",
                "inferential_force": 1.0,
                "stance_probability": 0.74,
                "model_confidence": 0.90,
            }
        ]

        # 1. Hard mode: pruned because P(0.74) < tau_p(0.75)
        res_hard = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            admissibility_mode="hard",
            tau_p=0.75,
            tau_c=0.75,
        )
        assert res_hard.admissibility_pruned_count == 1
        assert pytest.approx(res_hard.degrees["conclusion"]) == 0.5

        # 2. Soft mode: preserved with sigmoidal attenuation sigma(20 * (0.74 - 0.75)) = sigma(-0.2) ~ 0.45
        res_soft = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            admissibility_mode="soft",
            tau_p=0.75,
            tau_c=0.75,
        )
        assert res_soft.admissibility_pruned_count == 0
        # Conclusion receives positive support from relaxed edge
        assert res_soft.degrees["conclusion"] > 0.5


class TestPerspectivalAndSuppositionalScoping:
    """Deterministic unit tests for Issue-054 intensional & perspectival D-QBAF scoping."""

    def test_suppositional_reductio_isolation_prevents_inflation(self) -> None:
        """Verify Reductio assumptions do not inflate asserted claims when isolated."""
        from epistemetrics.core.models import TheoryNode
        from epistemetrics.epistemic.qbaf import QBAFGradualSemanticsSolver

        nodes = [
            TheoryNode(
                id="author_thesis",
                name="Author Thesis",
                base_score=0.5,
                intensional_mode="asserted",
            ),
            TheoryNode(
                id="reductio_premise",
                name="Reductio Premise",
                base_score=0.95,
                intensional_mode="suppositional",
            ),
        ]
        edges = [
            {
                "source": "reductio_premise",
                "target": "author_thesis",
                "relation_type": "SUPPORTS",
                "inferential_force": 1.0,
            }
        ]

        isolated = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            isolate_suppositional=True,
        )
        assert isolated.suppositional_isolated_count == 1
        assert isolated.degrees["author_thesis"] == pytest.approx(0.5)

        unisolated = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            isolate_suppositional=False,
        )
        assert unisolated.suppositional_isolated_count == 0
        assert unisolated.degrees["author_thesis"] > 0.5

        solver = QBAFGradualSemanticsSolver(isolate_suppositional=True)
        continuous = solver.solve_continuous(nodes=nodes, edges=edges)
        assert continuous.converged
        assert continuous.suppositional_isolated_count == 1
        assert continuous.degrees["author_thesis"] == pytest.approx(0.5, abs=1e-4)

    def test_perspective_filtering_author_vs_attributed_agents(self) -> None:
        """Verify attributed opponent claims are isolated under authorial evaluation."""
        nodes = {
            "author_claim": {
                "prior": 0.5,
                "intensional_mode": "asserted",
            },
            "hume_premise": {
                "prior": 0.9,
                "intensional_mode": "attributed",
                "attributed_to": "David Hume",
            },
            "hume_conclusion": {
                "prior": 0.5,
                "intensional_mode": "attributed",
                "attributed_to": "David Hume",
            },
            "leibniz_critique": {
                "prior": 0.85,
                "intensional_mode": "attributed",
                "attributed_to": "Leibniz",
            },
        }
        edges = [
            {
                "source": "hume_premise",
                "target": "author_claim",
                "relation_type": "SUPPORTS",
                "inferential_force": 1.0,
            },
            {
                "source": "hume_premise",
                "target": "hume_conclusion",
                "relation_type": "SUPPORTS",
                "inferential_force": 1.0,
            },
            {
                "source": "leibniz_critique",
                "target": "hume_conclusion",
                "relation_type": "ATTACKS",
                "inferential_force": 1.0,
            },
        ]

        res_author = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            perspective="author",
        )
        assert res_author.perspective == "author"
        assert res_author.perspective_filtered_count == 3
        assert res_author.degrees["author_claim"] == pytest.approx(0.5)

        res_hume = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            perspective="David Hume",
        )
        assert res_hume.perspective == "David Hume"
        assert res_hume.perspective_filtered_count == 2
        assert res_hume.degrees["hume_conclusion"] > 0.5

        res_all = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            perspective="all",
            isolate_attributed=False,
        )
        assert res_all.perspective == "all"
        assert res_all.perspective_filtered_count == 0
        assert res_all.degrees["author_claim"] > 0.5

        res_cont_hume = solve_continuous_qbaf(
            nodes=nodes,
            edges=edges,
            perspective="David Hume",
        )
        assert res_cont_hume.converged
        assert res_cont_hume.perspective_filtered_count == 2
        assert res_cont_hume.degrees["hume_conclusion"] > 0.5

    def test_reductio_ad_absurdum_discharge_vs_unrefuted_supposition(self) -> None:
        """Verify refuted Reductio chains discharge via modus tollens while unrefuted ones stay isolated."""
        nodes = {
            "thesis": {"prior": 0.5, "intensional_mode": "asserted"},
            "rival_supp": {"prior": 0.9, "intensional_mode": "suppositional"},
            "absurd_conseq": {"prior": 0.85, "intensional_mode": "suppositional"},
            "empirical_fact": {"prior": 0.95, "intensional_mode": "asserted"},
            "other_thesis": {"prior": 0.5, "intensional_mode": "asserted"},
            "unrefuted_supp": {"prior": 0.95, "intensional_mode": "suppositional"},
            "false_support_supp": {"prior": 0.9, "intensional_mode": "suppositional"},
        }
        edges = [
            # Classic 2-hop reductio: rival_supp -> absurd_conseq, attacked by empirical_fact
            {
                "source": "rival_supp",
                "target": "absurd_conseq",
                "relation_type": "SUPPORTS",
                "inferential_force": 0.9,
            },
            {
                "source": "empirical_fact",
                "target": "absurd_conseq",
                "relation_type": "ATTACKS",
                "inferential_force": 0.95,
            },
            {
                "source": "rival_supp",
                "target": "thesis",
                "relation_type": "ATTACKS",
                "inferential_force": 0.9,
            },
            # Unrefuted supposition attacking other_thesis stays isolated
            {
                "source": "unrefuted_supp",
                "target": "other_thesis",
                "relation_type": "ATTACKS",
                "inferential_force": 0.95,
            },
            # Refuted supposition that merely SUPPORTED other_thesis must NOT discharge positive support
            {
                "source": "empirical_fact",
                "target": "false_support_supp",
                "relation_type": "ATTACKS",
                "inferential_force": 0.9,
            },
            {
                "source": "false_support_supp",
                "target": "other_thesis",
                "relation_type": "SUPPORTS",
                "inferential_force": 0.9,
            },
        ]

        res = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            perspective="author",
            isolate_suppositional=True,
        )
        assert res.degrees["thesis"] > 0.5
        assert res.degrees["other_thesis"] == pytest.approx(0.5)
        assert res.degrees["unrefuted_supp"] == pytest.approx(0.0)
        assert res.degrees["rival_supp"] < 0.9

        res_cont = solve_continuous_qbaf(
            nodes=nodes,
            edges=edges,
            perspective="author",
            isolate_suppositional=True,
        )
        assert res_cont.converged
        assert res_cont.degrees["thesis"] > 0.5
        assert res_cont.degrees["other_thesis"] == pytest.approx(0.5, abs=1e-4)

    def test_dialectical_mode_preserves_external_attacks_blocks_external_support(
        self,
    ) -> None:
        """Verify isolate_attributed=False keeps incoming opponent ATTACKS while blocking off-perspective SUPPORTS."""
        nodes = {
            "hume_claim": {
                "prior": 0.5,
                "intensional_mode": "attributed",
                "attributed_to": "David Hume",
            },
            "kant_attack": {
                "prior": 0.9,
                "intensional_mode": "attributed",
                "attributed_to": "Immanuel Kant",
            },
            "kant_support": {
                "prior": 0.9,
                "intensional_mode": "attributed",
                "attributed_to": "Immanuel Kant",
            },
            "hume_target_for_support": {
                "prior": 0.5,
                "intensional_mode": "attributed",
                "attributed_to": "David Hume",
            },
        }
        edges = [
            {
                "source": "kant_attack",
                "target": "hume_claim",
                "relation_type": "ATTACKS",
                "inferential_force": 0.9,
            },
            {
                "source": "kant_support",
                "target": "hume_target_for_support",
                "relation_type": "SUPPORTS",
                "inferential_force": 0.9,
            },
        ]

        res_dialectic = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            perspective="David Hume",
            isolate_attributed=False,
        )
        assert res_dialectic.degrees["hume_claim"] < 0.5
        assert res_dialectic.degrees["hume_target_for_support"] == pytest.approx(0.5)

    def test_historical_unattributed_shared_vs_agent_attributed(self) -> None:
        """Verify unattributed historical claims act as shared premises while attributed historical claims isolate."""
        nodes = {
            "author_claim": {"prior": 0.5, "intensional_mode": "asserted"},
            "hist_shared": {"prior": 0.85, "intensional_mode": "historical"},
            "hist_aristotle": {
                "prior": 0.9,
                "intensional_mode": "historical",
                "attributed_to": "Aristotle",
            },
        }
        edges = [
            {
                "source": "hist_shared",
                "target": "author_claim",
                "relation_type": "SUPPORTS",
                "inferential_force": 0.8,
            },
            {
                "source": "hist_aristotle",
                "target": "author_claim",
                "relation_type": "SUPPORTS",
                "inferential_force": 0.9,
            },
        ]

        res_author = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            perspective="author",
        )
        assert res_author.perspective_filtered_count == 1
        assert res_author.degrees["author_claim"] > 0.5
        assert res_author.degrees["hist_aristotle"] == pytest.approx(0.0)

        res_aristotle = solve_qbaf_gradual_semantics(
            nodes=nodes,
            edges=edges,
            perspective="Aristotle",
        )
        assert res_aristotle.degrees["hist_shared"] == pytest.approx(0.85)
        assert res_aristotle.degrees["hist_aristotle"] == pytest.approx(0.9)
